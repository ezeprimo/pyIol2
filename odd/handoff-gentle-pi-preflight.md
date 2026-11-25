# Handoff: defecto en el preflight de entrega de gentle-pi

Reporte medido, no instrucción de mutar nada. Para pasarle a la sesión de Pi que
trabaja sobre `D:/MisProyectos/gentle-shell`.

## Contexto

Sesión en `D:/MisProyectos/iol/pyIol2`. Al pushear, el preflight de entrega de RDD
denegó la entrega varias veces con:

```
RDD pre-delivery: The bounded preflight was cancelled or timed out.
This delivery command was not run. Review outcomes do not authorize delivery.
```

## Causa localizada

`C:/Users/ezepr/.pi/agent/npm/node_modules/gentle-pi/lib/review-delivery-preflight.ts`
(gentle-pi 4.8.0), línea 45:

```ts
const bounded = AbortSignal.any([AbortSignal.timeout(10_000), ...(signal ? [signal] : [])]);
```

Ese único presupuesto de 10 s cubre, por cada root, esta secuencia:

1. `cli.reviewMode({ operation: "status" })` → spawn `gentle-ai`
2. `identity()` → `git rev-parse` (dos veces, `--revs-only`)
3. `committedRangeUntrackedExclusion()` → `cli.targetStatus` → spawn `gentle-ai`
4. `cli.assess({ baseRef, committedOnly })` → spawn `gentle-ai`
5. y si `reviewDue`, otro `cli.targetStatus` más

El ganador de la carrera es la promesa `expired`, que devuelve **el mismo
mensaje** por timeout de 10 s y por abort de la señal padre (`ctx.signal`, ver
`extensions/gentle-ai.ts:13267`), así que el diagnóstico es ambiguo por diseño.

## Mediciones en esta máquina (Windows 11, repo chico)

| Paso | Medición |
|---|---|
| CLI crudo, máquina ociosa: `review mode status` | 218 ms |
| CLI crudo: `review status` | 144 ms |
| CLI crudo: `review assess` | 1 844 ms |
| **Total CLI crudo** | **2 207 ms** |
| Mismo `assess` por la ruta del adapter de Pi | 7 873 / 8 169 / 9 796 / 10 919 ms |

Las cuatro últimas son `metrics.steps[].elapsed_ms` de cuatro llamadas
`gentle_review_run` de la misma sesión: el adapter tarda ~4× más que el CLI
directo. Suma estimada del preflight completo: **8.5 a 11.5 s contra un techo de
10 s**, de ahí la denegación intermitente.

Contraprueba que **no** sirve: `git push --dry-run` pasó, pero un dry-run no
parece clasificarse como entrega, así que el preflight ni corre. No valida nada
del gate.

## Trabajo perdido

Con el worktree limpio (`git status --porcelain --untracked-files=normal` vacío),
el paso 3 es puro costo: consulta el inventario de untracked para declarar la
exclusión y no hay ninguno.

## Fix propuesto (a criterio del dueño del repo)

- **a)** Saltear el lookup nativo de inventario cuando no hay untracked
  (chequeo barato, ~50 ms), devolviendo `{}`. Recupera ~3 s del presupuesto.
- **b)** Mensajes distintos para abort de señal vs timeout, para no confundir
  cancelación con lentitud.
- **c)** Opcional: subir el techo o hacerlo configurable por entorno.

## Qué se pide

Confirmar o refutar el diagnóstico leyendo el código y, si es correcto, proponer
el fix (o el PR) según las convenciones de gentle-shell.

Workaround mientras tanto: el humano corre `git push` desde su propio shell, que
no pasa por el gate.
