# Guia de mantenimiento

Runbook para quien mantenga este repositorio, humano o agente de IA. La pregunta
que responde es una sola: **IOL cambio algo, que hago ahora**.

## Fuentes de verdad

| Que | Donde | Que se saca de ahi |
|---|---|---|
| Contrato REST | `https://developers.iolinversiones.com/api/llms` | Los 35 endpoints y sus esquemas |
| Documentacion WebSocket | `https://developers.iolinversiones.com/docs/websocket` | Conexion, canales, limites, codigos de error |
| Guia WebSocket para IA | Descarga de la misma seccion | Lo mismo, en formato listo para cargar como contexto |
| Documento de autenticacion | `https://developers.iolinversiones.com/docs/auth` | OAuth2, TTL del token, refresh |
| Comportamiento real | La API, con tus credenciales | Lo que ningun documento dice |

Los snapshots viven en [`vendor/`](./vendor/README.md). Nada de esto se consulta
en runtime: la libreria no lee los documentos, se usan para implementar y auditar.

## Paso 1 — refrescar y ver que cambio

```bash
curl -s https://developers.iolinversiones.com/api/llms -o doc/vendor/iol-api-v1.md
git diff --stat doc/vendor/
```

Si el diff esta vacio, no hay nada que hacer: se descarta el snapshot y listo. Si
hay cambios, clasificalos antes de tocar codigo:

1. **Endpoint nuevo** → falta un metodo en `client.py` y sus modelos.
2. **Campo nuevo en una respuesta** → falta un atributo en el dataclass.
3. **Campo renombrado o eliminado** → rompe el parseo: es lo mas peligroso.
4. **Valor nuevo en un enum** → falta una constante (`constants.py`).
5. **Mensaje o canal nuevo en el WebSocket** → `stream.py` y `models.py`.

## Paso 2 — mapear el cambio al codigo

La convencion del proyecto no se negocia:

| Archivo | Que va |
|---|---|
| `pyIol2/models.py` | Un dataclass por respuesta, con `from_dict()`, docstring en espanol y defaults tolerantes (si el campo no viene, no revienta) |
| `pyIol2/client.py` | El metodo tipado **y** su gemelo `_raw()`, en ese orden, con la misma firma |
| `pyIol2/constants.py` | Constantes nuevas; nunca literales de protocolo repartidos por el codigo |
| `pyIol2/stream.py` | Canales, acciones y tipos de mensaje del WebSocket |
| `pyIol2/exceptions.py` | Solo si aparece un error con forma nueva |

Reglas que evitan bugs caros:

- **No adivines valores de enum.** Los ids reales se piden a la API
  (`get_asset_types()`, `get_asset_panels()`), no salen del contrato.
- **Un campo que desaparece no se borra del dataclass**: se deja con su default y
  se documenta, porque romper el modelo rompe a todos los usuarios.
- **Las escrituras validan local antes de salir**: si el endpoint nuevo mueve
  plata, agregar la validacion en el cliente (como `quantity` XOR `notional`).
- **Los frames de protocolo se descartan**, no se entregan como datos.

## Paso 3 — verificar, en este orden

Primero lo barato y hermetico, despues lo que toca la API:

```bash
uv run ruff check pyIol2/ tests/ scripts/
uv run ruff format --check pyIol2/ tests/ scripts/
uv run pytest tests/ -q
```

Y recien despues, contra produccion. **En este orden y con estas reglas**:

| Script | Cuando | Ojo |
|---|---|---|
| `scripts/smoke_test.py` | Siempre, es solo lectura | Baseline: 17 de 18 OK; `portfolio/history` falla si la cuenta no esta habilitada |
| `scripts/stream_probe.py` | Si tocaste `stream.py` | Necesita horario de mercado |
| `scripts/stream_stress_probe.py` | Si tocaste sharding, bajas o reconexion | Necesita horario de mercado, ~45s |
| `scripts/safe_write_probe.py` | Si tocaste cualquier escritura | Crea y borra su propia watchlist |
| `scripts/money_write_probe.py` | Si tocaste cauciones o FCI | Sin `--allow-fci-write` no mueve plata |
| `scripts/order_roundtrip.py` | Solo con el mercado **cerrado** | Con la rueda abierta una orden puede ejecutarse; el script se niega, no lo fuerces |

Cada verificacion nueva se documenta en
[`agent-guide.md`](./agent-guide.md), seccion "Lo Que Devuelve la API Real", con
el script que la produjo. Si un comportamiento contradice el snapshot vendorizado,
**gana la API** y el snapshot queda marcado como desactualizado.

## Paso 4 — documentar

- `agent-guide.md` → si cambio el comportamiento observable o una trampa.
- `api-reference.md` → si cambio una firma, un default o un tipo de retorno.
- `CHANGELOG.md` → siempre, bajo `Unreleased`, en el grupo que corresponda.
- `README.md` → si cambio la tabla de migracion o lo que la libreria cubre.
- `doc/vendor/README.md` → la fecha del nuevo sync.

## Paso 5 — publicar

Con `main` protegida, todo entra por PR: rama, commit, PR, checks en verde,
squash. El release sigue [`RELEASE_CHECKLIST.md`](../RELEASE_CHECKLIST.md):
subir la version en `pyproject.toml` y `pyIol2/__init__.py`, CHANGELOG, preflight
local, tag y `publish.yml`.

Recordatorio: **una version publicada no se puede reusar**. Si algo sale mal
despues de publicar, se arregla en la version siguiente.

## Cuando algo no cierra

- El contrato dice una cosa y la API responde otra → gana la API, se documenta en
  el agent guide y se anota en `odd/tasks/` como pendiente de reportar.
- La API devuelve un error sin detalle (`ORDER_REJECTED`, `500 INTERNAL_ERROR`)
  → el unico dato util es el `trace_id`, que las excepciones conservan.
- Un script falla pero el codigo esta bien → revisar el script antes que la
  libreria: ya paso dos veces (un wrapper de `websockets` mal escrito y una
  reconciliacion con argumentos de menos).
