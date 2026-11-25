# Herramientas de `scripts/`

Los scripts de esta carpeta son las pruebas que corren **contra la API real** de
IOL. Los tests de `tests/` no tocan la red: usan `httpx.MockTransport` y un
WebSocket falso. Estos scripts son lo complementario, lo que solo se puede
verificar hablando con producción.

Lo importante antes de correr cualquiera: **la columna "Dinero"**. Cinco de los
seis scripts no pueden mover plata. Uno sí, y está diseñado para no hacerlo por
accidente.

## Resumen

| Script | Qué hace | Escribe | ¿Mueve dinero? | Cuándo correrlo |
|---|---|---|---|---|
| [`validate_version.py`](#validate_versionpy) | Valida tag contra `pyproject.toml` | no | no | Antes de tagear un release; también lo corre el CI |
| [`smoke_test.py`](#smoke_testpy) | 18 pasos REST + handshake del WebSocket | no | no | Después de tocar `client.py` o `models.py` |
| [`stream_probe.py`](#stream_probepy) | Vistazo del market data en vivo | no | no | Después de tocar `stream.py` |
| [`stream_stress_probe.py`](#stream_stress_probepy) | Sharding, bajas y reconexión | no | no | Después de tocar `stream.py`, en horario de mercado |
| [`safe_write_probe.py`](#safe_write_probepy) | CRUD de watchlists + estimaciones | sí (solo su propia watchlist) | no | Después de tocar cualquier método de escritura |
| [`money_write_probe.py`](#money_write_probepy) | Caución y FCI hasta donde no se mueve plata | sí | **no, por diseño** | Con el mercado cerrado, tras tocar cauciones o FCI |
| [`order_roundtrip.py`](#order_roundtrippy) | Crea y cancela una compra y una venta | **sí** | **sí** | Solo con el mercado cerrado, y con `--yes` explícito |

## Requisitos comunes

```bash
uv sync --all-extras
```

Credenciales por entorno o en un `.env` local (ignorado por git, nunca commitear):

```dotenv
IOL_USERNAME=tu_usuario_iol
IOL_PASSWORD=tu_password_iol
```

Todos se ejecutan con `uv run python scripts/<script>.py`. Los que consultan el
mercado necesitan **horario de rueda** para mostrar datos: con el mercado cerrado
devuelven listas vacías, y eso no es un error.

---

## `validate_version.py`

Valida que la versión del tag coincida con la de `pyproject.toml`, y clasifica
según semver: producción, o prerelanzamiento (`alpha`, `beta`, `rc`, `dev`).

```bash
uv run python scripts/validate_version.py v0.1.0
uv run python scripts/validate_version.py v0.1.0-beta.1
uv run python scripts/validate_version.py          # usa el tag exacto de HEAD
```

Sin argumento toma el tag con `git describe --tags --exact-match HEAD`. Lo usa
el workflow `publish.yml` antes de publicar: si la versión no coincide, el job
`validate` falla y no se publica nada.

Salida esperada:

```
OK: Version valida: 0.1.0-beta.1 (PRERELEASE: beta.1)
   Se publicara solo en TestPyPI
```

Códigos de salida: `0` válido, `1` mismatch o formato inválido.

---

## `smoke_test.py`

La prueba de humo general: recorre 18 pasos de solo lectura e informa cuáles
pasan. Sirve para detectar cambios de contrato en la API (campos renombrados,
endpoints nuevos, permisos que faltan).

```bash
uv run python scripts/smoke_test.py
uv run python scripts/smoke_test.py --with-stream --stream-timeout 12
```

| Flag | Para qué |
|---|---|
| `--with-stream` | Agrega el handshake del WebSocket (`auth_token` + `subscribe`) |
| `--stream-timeout` | Segundos de espera por mensaje del stream (default 10) |

Cubre: `/health`, login OAuth2, `test_authentication`, quote, depth, asset, tipos
de asset, screener, cadena de opciones, barras históricas, plazos y libro de
cauciones, saldos, posiciones, historial de patrimonio, movimientos,
operaciones de trading y watchlists.

Devuelve `1` si algún paso falla, e imprime el resumen con el `trace_id` de cada
error para poder reclamar. Baseline conocido: **17 de 18 OK**; el que falla es
`/broker/accounts/{country}/portfolio/history`, que en cuentas sin habilitación
responde `404 client_not_whitelisted`.

---

## `stream_probe.py`

Vistazo del market data en vivo: una foto del REST para comparar, las cauciones,
y el flujo del WebSocket con detalle de cada mensaje.

```bash
uv run python scripts/stream_probe.py
uv run python scripts/stream_probe.py --symbols GGAL YPFD AL30 --messages 40 --timeout 60
uv run python scripts/stream_probe.py --skip-stream        # solo la parte REST
```

| Flag | Para qué |
|---|---|
| `--symbols` | Títulos a seguir (default `GGAL YPFD`) |
| `--messages` | Cuántos mensajes del WebSocket consumir (default 15) |
| `--timeout` | Segundos de espera por mensaje (default 25) |
| `--skip-stream` | Saltea el WebSocket |

Imprime el último precio, variación y `last_updated` de cada título, la
profundidad con mejor bid/ask, la última vela del histórico, los plazos de
caución con sus tasas, y después cada mensaje `Q` (puntas) y `T` (operaciones)
con su hora. Termina con el conteo por tipo.

Con el mercado cerrado: `depth` y cauciones vienen vacíos y el stream solo
entrega el frame de suscripción, que la librería descarta. Devuelve `1` si no
llegó ningún mensaje de datos.

---

## `stream_stress_probe.py`

Las cuatro cosas que el WebSocket falso de los tests no puede probar.

```bash
uv run python scripts/stream_stress_probe.py
uv run python scripts/stream_stress_probe.py --only reconnect
```

| Flag | Para qué |
|---|---|
| `--only` | Corre un solo escenario: `sharding`, `unsubscribe`, `unsubscribe_all` o `reconnect` |

1. **`sharding`**: pide 60 símbolos reales del panel de acciones y verifica que
   se abran exactamente `ceil(60/50) = 2` conexiones, con 50 y 10 símbolos, y que
   lleguen datos en ambas.
2. **`unsubscribe`**: se suscribe a dos títulos, da de baja uno, y confirma que
   el servidor **deja de mandarlo** y sigue mandando el otro.
3. **`unsubscribe_all`**: después de la baja total, verifica que no llegue ningún
   mensaje en una ventana de 8 segundos con el socket abierto.
4. **`reconnect`**: envuelve la conexión real, la corta a propósito, y verifica
   que la librería reintente con backoff, se reautentique y **vuelva a
   suscribirse sola**.

Necesita horario de mercado: sin flujo de datos, los escenarios 1 a 3 no tienen
nada que consumir. Tarda alrededor de 45 segundos completo. Devuelve `1` si algún
escenario falla.

Detalle de implementación si escribís tu propio `connect_factory`: en
`websockets` 17, `ClientConnection` implementa `__aiter__` como corrutina y no
expone `__anext__`, así que un wrapper debe delegar con su propio generador
asíncrono. Es el error que costó una corrida en este mismo script.

---

## `safe_write_probe.py`

El único CRUD de escritura sin riesgo: **watchlists**. Además estima una orden y
una caución, que son de solo lectura.

```bash
uv run python scripts/safe_write_probe.py
uv run python scripts/safe_write_probe.py --keep    # deja la watchlist de prueba
```

| Flag | Para qué |
|---|---|
| `--keep` | No borra la watchlist creada (para inspeccionarla en la web) |

Secuencia: crea una watchlist propia (`pyIol2 probe <fecha>`), la lee, la
renombra, agrega `GGAL`, la vuelve a leer con la cotización en vivo del item,
quita el item, verifica que quede vacía, y la borra. **Solo toca la lista que
creó**: al final compara el conjunto de watchlists contra el inicial y falla si
quedó residuo. La lista real de la cuenta nunca se modifica.

Las estimaciones cubren `estimate_order` en sus tres formas (cantidad, límite y
monto) y `estimate_repo` sobre los dos primeros plazos. Recordá que
`estimate_repo` devuelve **varios componentes por plazo** (interés y comisión con
IVA), no un total.

No mueve dinero. La escritura más riesgosa que hace es una watchlist, que se
borra en un `finally`.

---

## `money_write_probe.py`

Los dos caminos de escritura que faltaban —cauciones y FCI— ejercitados hasta el
borde del dinero. Está diseñado para **no mover plata**.

```bash
uv run python scripts/money_write_probe.py          # solo lectura
uv run python scripts/money_write_probe.py --yes    # agrega el alta de caución y el cancel de prueba
```

| Flag | Para qué |
|---|---|
| `--yes` | Intenta el alta de caución (rechazo esperado por saldo) y el cancel de un id inexistente |
| `--allow-fci-write` | Ejecuta una suscripción real de FCI. **No se pasa por default y no está recomendado** |

Cómo se evita mover plata:

- **Cauciones**: el mínimo es 100.000 ARS por plazo; si el saldo disponible es
  menor, el alta no puede concretarse. Si a pesar de todo el broker la acepta, se
  cancela en un `finally`. Lo que devuelve hoy es `500 INTERNAL_ERROR`, no un
  rechazo amable — dato documentado en el agent guide.
- **FCI**: solo se llaman los endpoints `validate_*`, que son de lectura. Una
  suscripción real mete plata en un fondo y la cancelación depende de la ventana
  del día, así que queda detrás de un flag propio.

Qué verifica: los dos componentes de `estimate_repo` con su `fee_type`, que el
alta de caución devuelve un error en vez de crear algo, que el cancel de un id
inexistente no rompe nada, y que las validaciones de FCI distinguen un fondo que
podés suscribir de uno que no tenés.

## `order_roundtrip.py`

Crea una compra y una venta reales, verifica que aparezcan en la cuenta y las
cancela. Es el único script que **puede ejecutar una operación de verdad**, y está
diseñado para que no lo haga sin que vos lo decidas dos veces.

```bash
uv run python scripts/order_roundtrip.py                        # plan, no manda nada
uv run python scripts/order_roundtrip.py --yes                  # ejecuta y cancela
uv run python scripts/order_roundtrip.py --yes --sell-held      # vende un activo con tenencia
uv run python scripts/order_roundtrip.py --yes --allow-marketable-sell
uv run python scripts/order_roundtrip.py --yes --allow-open-market
```

| Flag | Para qué |
|---|---|
| `--yes` | Sin esto solo imprime el plan y sale. Nada se manda. |
| `--sell-held` | Vende el primer activo con tenencia en lugar de `KO` |
| `--allow-marketable-sell` | Vende al precio de referencia. **La orden puede ejecutarse.** |
| `--allow-open-market` | Permite correr con la rueda operando. **También puede ejecutarse.** |

### Las tres guardas

1. **`--yes` obligatorio.** El default es un plan impreso, sin escrituras.
2. **Se niega a correr con el mercado abierto.** Detecta la frescura de la
   cotización: si se actualizó hace menos de 15 minutos, asume rueda operando y
   aborta. Si no puede determinar el estado, **también aborta** — el script no
   puede probar que sea seguro, así que no manda nada. Se saltea con
   `--allow-open-market`, que es aceptar el riesgo a sabiendas.
3. **Colchón real en el precio.** La compra va 5% debajo del último y la venta 5%
   arriba, o sea pasivas: no se cruzan. El cálculo fuerza al menos un tick de
   diferencia, así que nunca coincide con el precio de referencia, y el script
   aborta antes de mandar nada si el colchón no es real.

### La garantía de limpieza

- **Baseline antes de empezar**: toma los ids de las órdenes vivas y solo puede
  tocar las que aparezcan después. Una orden tuya previa es intangible.
- **El id se registra antes de imprimir**, así un stdout roto no puede dejar una
  orden sin cancelar.
- **Alta ambigua**: si el POST falla después de que el broker lo aceptó, se
  reconcilia contra las operaciones del día (símbolo, lado, plazo, precio,
  cantidad y `order_date` dentro de una ventana) en lugar de reintentar.
- **Se cancela antes de verificar**, porque el feed de operaciones tarda unos
  segundos y una orden viva mientras se espera es una orden ejecutable.
- Sale con código distinto de cero si quedó algo vivo o si la verificación no
  encontró la orden.

### Lo que aprendimos corriéndolo

- El broker rechaza límites fuera de una banda de precio con `422` y
  `code: ORDER_REJECTED`, **sin detalle**: `details` viene vacío y lo único útil
  es el `trace_id`.
- La banda **no es simétrica**: la compra se aceptó 5% abajo; la venta solo al
  precio de referencia (`1.00x`). Con `0.95x`, `0.99x` o `1.05x` la venta se
  rechaza.
- Las órdenes `market` se rechazan fuera de horario.
- No alcanza con tener saldo: una compra por más del disponible se rechaza con
  el mismo código opaco.

Por todo eso el default de la venta es pasivo (puede ser rechazado por banda) y
la variante aceptada es opt-in: una venta al precio de referencia **es
ejecutable**.

---

## Cómo se relacionan con la documentación

Cada verificación contra producción quedó registrada en
[`doc/agent-guide.md`](../doc/agent-guide.md) con el script que la produjo:

| Sección del agent guide | Script |
|---|---|
| "Lo Que Devuelve la API Real" | `smoke_test.py` |
| "Ordenes: Lo Que Acepta el Broker" | `order_roundtrip.py` |
| "Escrituras Inocuas y Estimaciones" | `safe_write_probe.py` |
| "Streaming Verificado en Serio" | `stream_stress_probe.py` |

Y el historial completo de qué se probó, cuándo y con qué resultado está en
[`odd/tasks/v0-1-0-scaffold.md`](../odd/tasks/v0-1-0-scaffold.md), entradas
`L18` en adelante.
