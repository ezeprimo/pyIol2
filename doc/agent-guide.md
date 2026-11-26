# pyIol2 Agent Guide

Guia para agentes de IA que construyen aplicaciones con `pyiol2-client`. Se
apoya en el codigo del repositorio, no en comportamiento no documentado de la
API de IOL.

## Camino Corto

1. Instalar `pyiol2-client` y dejar las credenciales fuera del codigo.
2. Elegir el cliente: `IOLClient` (sync, REST) o `IOLStreamClient` (async,
   WebSocket).
3. Empezar por metodos de lectura y por los modelos tipados.
4. Antes de cualquier metodo que mueva dinero: validar, mostrar el resumen,
   pedir confirmacion y guardar el `idempotency_key`.

```python
import os

from pyIol2 import IOLAPIError, IOLClient

with IOLClient(os.environ["IOL_USERNAME"], os.environ["IOL_PASSWORD"]) as client:
    cotizacion = client.get_market_quote("GGAL")
    print(cotizacion.prices.current, cotizacion.change.percent)
```

## Instalacion

```bash
uv add pyiol2-client     # o: pip install pyiol2-client
```

Para trabajar desde el repositorio: `uv sync --all-extras`. El runtime necesita
Python `>=3.10`, `httpx`, `cachetools` y `websockets`.

## Credenciales y Autenticacion

Las credenciales se pasan al constructor y nunca se escriben en el codigo, los
prompts, los logs ni los fixtures:

```python
import os

username = os.environ["IOL_USERNAME"]
password = os.environ["IOL_PASSWORD"]
```

`IOLClient` no autentica al construirse: pide el token en la primera request
autenticada. `TokenManager` lo cachea en memoria y lo renueva con
`refresh_token` antes de que venza. Si una request devuelve `401`, el cliente
invalida el token y la reintenta **una sola vez**: ese status significa que la
request fue rechazada antes de ejecutarse, asi que reintentarla no duplica
efectos. Cualquier otro error se propaga sin reintento.

`get_health_status()` es el unico metodo sin token y sirve para distinguir un
problema de credenciales de un problema del servicio:

```python
with IOLClient(username, password) as client:
    print(client.get_health_status().status)      # no requiere token
    print(client.get_account_balances().ars.totals.t0)  # primera request autenticada
```

Nunca loguees `IOLToken.access_token` ni el header `Authorization`. Si necesitas
diagnostico, loguea el path y el `trace_id`.

## Sync vs Async

| Tarea | Cliente | Modelo de ejecucion |
|-------|---------|---------------------|
| Cotizaciones, cuenta, ordenes, FCI, cauciones, watchlists | `IOLClient` | Sincronico, `with` |
| Market data en tiempo real | `IOLStreamClient` | Asincronico, `async with` |

`IOLClient` usa `httpx.Client` y acepta un `client=` ya configurado y un
`timeout` en segundos (30 por defecto). No hay version async del cliente REST:
si tu aplicacion es asincronica, corre las llamadas REST en un thread
(`asyncio.to_thread`) y deja el WebSocket en el loop.

```python
import asyncio

from pyIol2 import IOLClient


async def leer_posiciones(username: str, password: str):
    def run():
        with IOLClient(username, password) as client:
            return client.get_positions()

    return await asyncio.to_thread(run)
```

## Regla de `_raw()`

Cada metodo tipado tiene un gemelo `_raw()` con la misma firma.

- El metodo tipado devuelve una dataclass exportada por `pyIol2` y usa nombres
  en snake_case (`prices.current`, `change.percent`).
- El metodo `_raw()` devuelve el campo `data` de la respuesta, sin normalizar y
  sin el sobre: **no** incluye `meta` ni `error`. Si necesitas el `trace_id` de
  una respuesta exitosa, hoy no esta disponible por la API publica; el
  `trace_id` de los errores viene en la excepcion.
- Usa `_raw()` solo cuando necesites un campo que el modelo no expone, y
  aislalo en un adaptador: no dejes diccionarios de la API en el dominio.

```python
with IOLClient(username, password) as client:
    crudo = client.get_market_quote_raw("GGAL")
    print(crudo["prices"]["current"])   # nombres de la API, no del modelo
```

## Errores y `trace_id`

Todo fallo de red, de contrato o de la API se propaga como `IOLAPIError` o una
subclase. La excepcion trae `status_code`, `code`, `trace_id`, `details`,
`method`, `path` y `payload`.

| Excepcion | Cuando aparece |
|-----------|----------------|
| `IOLAuthenticationError` | `401` / `403`: credenciales, token o permisos |
| `IOLValidationError` | `400` / `422`, o validacion local antes de enviar |
| `IOLNotFoundError` | `404`: simbolo o recurso inexistente |
| `IOLRateLimitError` | `429`: limite de requests |
| `IOLServerError` | `5xx`: error del servidor de IOL |
| `IOLStreamError` | error del WebSocket (`type: "Error"`), con `ws_code` |
| `IOLAPIError` | base: conexion, respuesta no JSON y cualquier otro caso |

```python
from pyIol2 import IOLAPIError, IOLClient

try:
    with IOLClient(username, password) as client:
        client.get_market_quote("NOEXISTE")
except IOLAPIError as exc:
    print(exc.status_code, exc.code)
    print(f"trace_id={exc.trace_id}")   # este dato pide el soporte de IOL
    raise
```

Reglas:

- Captura `IOLAPIError` en el borde de la aplicacion y traduce a tu dominio; no
  dejes escapar el `payload` crudo a la UI.
- Un `IOLValidationError` de validacion local significa que la request **nunca
  salio**: es seguro corregir y volver a intentar.
- Un `IOLStreamError` con `ws_code == 401` puede ser un token vencido **o** una
  suscripcion de `order_book` con mas de un simbolo. Revisa el pedido antes de
  renovar el token.
- Un `429` o un `5xx` no se reintentan solos: decidilo vos, con backoff y solo
  en lecturas.

## Ciclo de Vida del Streaming

```python
import asyncio

from pyIol2 import IOLStreamClient


async def main():
    async with IOLStreamClient(username, password) as stream:      # 1. auth
        async for message in stream.subscribe(                     # 2. subscribe
            ["GGAL", "YPFD"],
            quotes=True,
            trades=True,
        ):
            print(message.type, message.symbol)
            break                                                  # 4. teardown


asyncio.run(main())
```

1. **Auth**: el cliente pide el token OAuth (o usa el que le pasaste con
   `token=`) y manda `{"action": "auth_token", "token": ...}` en cada conexion.
   Si el servidor rechaza la sesion, levanta `IOLStreamError`.
2. **Subscribe**: manda `{"action": "subscribe", "trades": [...], "quotes": [...],
   "order_book": [...]}` con identificadores `SIMBOLO|MERCADO|PLAZO`. Los tres
   canales van siempre; los que no pediste van como lista vacia.
3. **Heartbeat**: el cliente manda un `ping` cada 15 segundos mientras la
   conexion este abierta. El servidor no hace ping, asi que no lo desactives.
4. **Teardown**: al salir del `async for` o del `async with`, `close()` cancela
   las tareas y cierra las conexiones. Si solo querés dejar de seguir algunos
   simbolos, usá `unsubscribe(symbols, market=..., term=...)` o
   `unsubscribe_all()`: mandan el frame correspondiente y dejan la conexión
   abierta. Cerrar la conexión también termina la suscripción.

Detalles que importan:

- `subscribe()` es un generador asincronico: sin `break` o sin cancelacion, el
  `async for` espera mensajes para siempre.
- La reconexion es automatica con backoff exponencial (1s hasta 30s, 5
  intentos por conexion) y vuelve a autenticar y a suscribir.
- Si una conexion muere de forma definitiva, el error se publica en el
  consumidor: el `async for` levanta `IOLStreamError` en vez de quedarse
  colgado.
- `StreamMessage` trae `type` (`Q` puntas, `B` profundidad, `T` operaciones),
  `symbol`, `market`, `term`, el sub-modelo correspondiente (`quote`,
  `order_book`, `trade`) y `raw` con el JSON original.

## Limites del Streaming

| Canal | Limite | Que hace la libreria |
|-------|--------|----------------------|
| `quotes` y `trades` | 50 simbolos por conexion | Reparte en varias conexiones sola |
| `order_book` | 1 simbolo por conexion | Rechaza con `IOLValidationError` si pides mas de uno |
| Canales por llamada | al menos uno | `IOLValidationError` si no pedis ninguno |
| Simbolos por llamada | al menos uno | `IOLValidationError` con lista vacia |

El reparto automatico es por cantidad de simbolos: si pedis 120 simbolos de
puntas, la libreria abre tres conexiones y las alimenta con la misma cola. La
profundidad no se reparte: pedila de a un titulo por vez.

```python
# Bien: profundidad de un solo titulo
async for message in stream.subscribe(["GGAL"], quotes=False, trades=False, order_book=True):
    ...

# Error: IOLValidationError
async for message in stream.subscribe(["GGAL", "YPFD"], order_book=True):
    ...
```

## Ordenes: Lo Que Acepta el Broker

Verificado con `scripts/order_roundtrip.py` contra produccion, mercado cerrado.

- **`settlement_term` es obligatorio de hecho.** El contrato lo marca opcional,
  pero sin el la API responde `400`. `estimate_order` y `create_order` mandan
  `DEFAULT_ORDER_SETTLEMENT_TERM` (`T1`) por defecto y aceptan otro valor. El
  default de market data y streaming (`DEFAULT_SETTLEMENT_TERM`) sigue en `T0`:
  son dos constantes distintas a proposito.
- **El limite tiene banda de precio.** Un precio muy lejos del mercado se
  rechaza con `422` y `code: "ORDER_REJECTED"`; en las pruebas, `0.25x` del
  ultimo fue rechazado y `0.95x` fue aceptado. No hay documentacion del ancho de
  la banda: no diseñes la operatoria asumiendo un valor.
- **`ORDER_REJECTED` no explica nada**: `details` viene vacio y el mensaje es
  siempre "The order was not accepted". Lo unico util para reclamar es el
  `trace_id`, que la excepcion conserva.
- **Las ordenes `market` se rechazan fuera de horario.** Usar `limit`.
- **No alcanza con tener saldo**: una compra de PAMP a 4316 con 3064 de saldo
  disponible fue rechazada con el mismo codigo opaco. Antes de mandar una orden
  real, comparar el importe estimado con `get_account_balances()`.
- **La banda de precio no es simetrica.** Medido con KO (CEDEAR, ultimo
  34.820): la venta se acepto **solo al precio de referencia** (`1.00x`), y
  `0.95x`, `0.99x` y `1.05x` fueron rechazadas. La compra, en cambio, se acepto
  `0.95x` abajo. Si tu limite cae fuera de esa banda, no hay forma de saberlo
  antes: el rechazo es el mismo `ORDER_REJECTED` sin detalle.
- **Las ventas si funcionan.** El problema anterior era el precio, no la
  tenencia: con `1.00x` del ultimo, una venta de KO (24 disponibles) y de PAMP
  se aceptan, quedan `pending` y se cancelan igual que las compras. La orden
  `market` de venta tambien se acepto.
- **`settlement_term=""` es un error local.** Un term vacio no significa "usar
  el default": `None` es el default, y la cadena vacia levanta
  `IOLValidationError` antes de salir a la red.
- **La API no correlaciona requests con ordenes.** El feed de operaciones
  devuelve 13 campos (`order_id`, `ticket_id`, `order_date`, `type`, `status`,
  `symbol`, `description`, `asset_type`, `term`, `currency`, `order`, `executed`,
  `execution_date`) y ninguno es la `X-Idempotency-Key` que mandamos. Si el alta
  queda ambigua (el broker la acepta y la respuesta se pierde), la unica forma
  de reconocerla es por atributos mas su `order_date` dentro de la ventana en que
  se mando el request.
- **El feed de operaciones no es inmediato.** Una orden recien creada tarda unos
  segundos en aparecer en `get_trading_operations()`; verificar con una espera
  acotada (5 intentos cada 2s) y no con una sola consulta.
- **El camino de compra si quedo validado de punta a punta**: crear, encontrar
  la orden en `get_trading_operations()` con `status: "pending"` en segundos, y
  `cancel_order()` devolviendo `cancelled: True` con `status: "cancelled"`.

## Escrituras Inocuas y Estimaciones

Verificado con `scripts/safe_write_probe.py` contra produccion, mercado abierto.

- **Las watchlists funcionan de punta a punta**: crear, leer, renombrar, agregar
  un item, leerlo con su cotizacion en vivo, quitarlo y borrar la lista. El item
  agregado aparece con `last_price`, `best_bid` y `best_ask` reales. Es el unico
  CRUD de escritura sin riesgo: se puede probar cuando quieras.
- **`estimate_order` usa la punta vendedora para una compra a mercado.** Con
  `quantity=1` sobre GGAL devolvio `importe=4602.5`, que era el `best_ask` del
  momento, no el ultimo precio. O sea: la estimacion es realista y no optimista.
- **La comision ronda el 0.5% del importe** (4602.5 -> 23.01; 5000 -> 25), mas
  IVA sobre la comision y un fee de mercado aparte. No hardcodees el porcentaje:
  sale de la API y puede cambiar por tipo de activo.
- **`estimate_repo` devuelve varios componentes por plazo**, no un total. En la
  muestra vinieron dos entradas por plazo: el interes del periodo y la
  comision+IVA (`vat_amount` = 21% de la comision, `commission_type` =
  `Porcentaje`, `fee_type` distinto). Si vas a mostrar el costo total, sumala por
  plazo; no asumas que la lista trae una sola fila.
- **El monto minimo manda**: `get_repo_terms()` trae `min_amount` por plazo
  (100.000 ARS en la muestra); estimar por debajo no tiene sentido.

## Cauciones y FCI: Lo Que Aceptan

Verificado con `scripts/money_write_probe.py` con el mercado cerrado. Los dos
caminos se ejercitaron hasta donde se puede sin mover plata.

- **`estimate_repo` devuelve componentes con nombre.** Dos por plazo en la
  muestra: `fee_type = "Derechos de Mercado"` (0.50) y `fee_type = "Comision"`
  (4.93). Sumalos para el costo total; el `vat_amount` es el 21% de cada uno.
- **El minimo de caucion es 100.000 ARS** por plazo (`min_amount`). Con un saldo
  menor el alta no se puede ni intentar en serio — y ojo con lo que devuelve:
  **`500 INTERNAL_ERROR` con "Ocurrio un error al procesar la solicitud"**, no un
  `422` con "saldo insuficiente". No hay validacion amable: si vas a operar
  cauciones, compará el importe con `get_account_balances()` antes de mandar.
- **El `cancel_repo` de un id inexistente proxea el servicio legacy.** Devuelve
  `422` con un cuerpo que **no** es el sobre `{meta, data, error}`:
  `{"success":false,"message":"Transaction was not found.",...}` y una cadena
  `Service https://activities.invertironline.com/api/clients/<id>/operations/<n>`.
  La libreria lo traduce igual a `IOLValidationError`, pero el payload viene de
  otro host: no lo parsees esperando `meta.trace_id`.
- **FCI no tiene catalogo en la v1.** No hay endpoint que liste fondos, asi que el
  simbolo tiene que venir de afuera (la doc de IOL usa `IOLCAMA`).
  `validate_fund_subscription("IOLCAMA", 1000)` devuelve `valid=True`; es el
  unico chequeo previo disponible.
- **`validate_fund_redemption` sin tenencia da `FCI-23`**: "No se encontró el
  título para el cliente". Es la forma de detectar que no tenes el fondo antes de
  intentar rescatar.
- **La suscripcion y su cancelacion funcionan de punta a punta.** Verificado con
  100 ARS en `IOLCAMA`: `subscribe_fund` devolvio `successful=True` con
  `transaction_id`, y `cancel_fund_operation` sobre ese id devolvio
  `cancelled=True` / `status=cancelled`. Sin residuo, comprobado de tres formas:
  el saldo ARS quedo **identico** (3.064,88 antes y despues), no aparecio ningun
  movimiento en `get_account_activities()`, y en `get_trading_operations()` la
  operacion figura como `Suscripción FCI` con `status=cancelled` y `qty=0`.
- **`validate_fund_subscription` no valida montos chicos**: acepta desde 50 ARS
  (probado 50, 100, 200, 300, 500 y 1000, todos `valid=True`). No sirve para
  descubrir el minimo real del fondo; el rechazo, si existe, llega recien en el
  alta.

## Streaming Verificado en Serio

Probado con `scripts/stream_stress_probe.py` contra el servidor real, con el
mercado abierto. Los cuatro escenarios pasaron:

- **Reparto de mas de 50 titulos.** Con 60 simbolos se abren **2 conexiones**
  (`[50, 10]`) y llegan datos de las dos. El limite de 50 es por canal y por
  conexion, y el reparto es automatico: no armes el sharding a mano.
- **`unsubscribe` lo respeta el servidor.** Pedir la baja de YPFD devuelve
  `['YPFD|BCBA|T0']` y despues llegan solo mensajes de GGAL. El frame que arma
  la libreria es el que el servidor espera.
- **`unsubscribe_all` tambien.** Despues de mandarlo no llego ningun mensaje en
  una ventana de 8 segundos, con la conexion abierta.
- **La reconexion funciona de verdad.** Cortando la conexion a proposito, el
  cliente registra `reintento 1/5 en 1.0s`, abre una conexion nueva, se
  reautentica, **vuelve a suscribirse solo** y siguen llegando mensajes. No hace
  falta reconstruir nada desde la aplicacion.

Detalle de implementacion util si escribis tu propio wrapper: en `websockets` 17
`ClientConnection` implementa `__aiter__` como corrutina y **no** expone
`__anext__`, asi que para envolver una conexion hay que delegar con un generador
asincrono propio, no con `await ws.__anext__()`.

## Nunca Reintentar una Escritura Incierta

Estos metodos tienen efectos reales sobre la cuenta:

- `create_order()`, `cancel_order()`
- `create_repo()`, `cancel_repo()`
- `subscribe_fund()`, `redeem_fund()`, `cancel_fund_operation()`
- `create_watchlist()`, `rename_watchlist()`, `delete_watchlist()`,
  `add_watchlist_item()`, `remove_watchlist_item()` (sin dinero, pero mutan
  estado de la cuenta)

Regla: **un timeout, un corte de conexion o un `5xx` no prueban que la
operacion no se ejecuto.** Antes de reenviar:

1. Consulta `get_trading_operations(...)` o `get_account_activities(...)` y
   busca la operacion por simbolo, cantidad y horario.
2. Si la operacion existe, reconcilia con el `order_id` / `transaction_id` en
   lugar de reenviar.
3. Si vas a reenviar la misma intencion, reutiliza el mismo `idempotency_key`:
   los endpoints de ordenes, cauciones y FCI lo exigen en el header
   `X-Idempotency-Key`. Si no lo pasas, el cliente genera uno nuevo por llamada
   (UUID v4), asi que dos llamadas son dos operaciones.

Antes de enviar cualquier escritura, usa la estimacion cuando exista:
`estimate_order()` y `estimate_repo()` calculan comisiones y cargos;
`validate_fund_subscription()` y `validate_fund_redemption()` validan la
operacion de FCI. Ninguna de las cuatro tiene efectos.

Y valida localmente lo que el cliente ya valida, para no depender de la
excepcion: `quantity` XOR `notional`, `limit_price` obligatorio si
`order_type="limit"`, `rate` obligatorio si `price_type="limit"`, y
`quantity` XOR `redeem_all` en rescates de FCI.

## Simbolos Utiles

| Simbolo | Para que |
|---------|----------|
| `IOLClient` | Cliente REST sincronico |
| `IOLStreamClient` | Cliente WebSocket asincronico |
| `StreamMessage` | Mensaje del WebSocket |
| `IOLAPIError` y subclases | Manejo de errores |
| `Markets` | `BCBA`, `NYSE`, `NASDAQ`, `AMEX` |
| `SettlementTerms` | `T0`, `T1` |
| `Countries` | `ARGENTINA`, `USA`, `ALL` |
| `StreamChannels` | `QUOTES`, `ORDER_BOOK`, `TRADES` |
| `StreamMessageTypes` | `QUOTE`, `ORDER_BOOK`, `TRADES`, `ERROR` |
| `StreamActions` | Acciones del protocolo WebSocket |
| `MarketQuote`, `MarketDepth` | Cotizacion y libro |
| `ScreenerEntry`, `OptionQuote`, `HistoricalBars` | Listados, opciones e historicos |
| `AccountBalances`, `Portfolio`, `Position` | Cuenta y cartera |
| `Activity`, `Operation`, `PortfolioHistory` | Movimientos y evolucion |
| `OrderEstimate`, `OrderResult`, `CancelResult` | Ordenes |
| `RepoTerm`, `RepoQuote`, `RepoEstimate`, `RepoOrderResult` | Cauciones |
| `FundValidationResult`, `FundOperationResult`, `FundCancelResult` | FCI |
| `Watchlist`, `WatchlistItem` | Listas de favoritos |
| `IOLToken`, `TokenManager` | Autenticacion |

## Arquitectura de una Aplicacion

- **Adaptador de infraestructura**: es el unico lugar que importa `pyIol2`,
  posee las credenciales, el cliente y la traduccion de errores.
- **Servicios**: eligen endpoints, aplican reglas de negocio y limites, y piden
  confirmacion antes de un efecto.
- **Modelos de dominio**: guardan los valores que la aplicacion necesita; no
  exponen los `dict` de la API.
- **Jobs y UI**: leen o envian comandos aprobados; nunca reintentan una orden a
  ciegas.
- **Auditoria**: registra timestamps, entradas, `order_id` y respuestas
  saneadas para conciliar.

Separa el objeto que lee del que escribe: un servicio que solo muestra precios
no deberia tener en la mano algo capaz de enviar ordenes. Inyecta el adaptador
para poder testear con `httpx.MockTransport` y un WebSocket falso.

## Lo Que Devuelve la API Real

Verificado contra el servidor de produccion con `scripts/smoke_test.py` (17 de
18 pasos OK, mercado cerrado). Diferencias con lo que uno esperaria leyendo el
contrato:

- **`asset_type` va en castellano.** Los ids reales son `acciones`, `cedears`,
  `etfs`, `opciones`, `bonos`, `letras`, `obligaciones_negociables`, `fondos`,
  `cauciones`, `cheques`, `indices`, `monedas`. No existe `stocks`: los ids se
  piden siempre con `get_asset_types()`.
- **`panel` tambien es un id propio**: por ejemplo `argaccionespanelgeneral`,
  `argaccionesmerval`, `argcedearstodos`, `argbonostodos`. Salen de
  `get_asset_panels(asset_type, country)`.
- **El plazo de la respuesta no siempre coincide con el pedido.** `GGAL` con
  `term=T0` devuelve `settlement_term: "T1"`: la API normaliza al plazo con el
  que cotiza el activo. No asserts `response.settlement_term == request.term`.
- **`/broker/accounts/{country}/portfolio/history` exige whitelisting.** Con una
  cuenta no habilitada responde `404` con `{"error": "client_not_whitelisted",
  "clientId": ...}`, un sobre que **no** sigue el formato `{meta, data, error}`
  y donde `error` es un string. La libreria lo traduce a `IOLNotFoundError` con
  el texto original; si lo necesitas, pedi la habilitacion a IOL.
- **El WebSocket confirma la suscripcion con `{"type": "Success"}`.** No esta en
  el contrato publicado. La libreria lo descarta junto con `Pong`
  (`STREAM_PROTOCOL_TYPES`): `subscribe()` solo entrega datos de mercado, y una
  suscripcion rechazada se manifiesta como `IOLStreamError`, no como mensaje.
- **Con el mercado abierto el flujo es continuo.** Verificado en rueda: en pocos
  segundos llegan 9 `Q` y 2 `T` para dos titulos, el `depth` por REST trae 5+5
  niveles y el canal `order_book` del WebSocket entrega los 10 niveles actualizados
  (el tamaño del nivel 5 cambia entre mensajes, o sea que es en vivo).
- **Los mensajes `T` traen acumulados del dia** (`TS` y `TP`), no deltas: para
  saber cuanto se opero en esa operacion esta `X`.
- **Cauciones solo tiene libro en horario de mercado.** Con la rueda abierta los
  81 plazos devuelven ofertas (se verificaron 12 de 12 con 5 ofertas cada uno);
  cerrada devolvia `[]`. No confundir eso con un mapeo de `term_id` roto.
- **Con el mercado cerrado**: `depth` devuelve las listas vacias, `repos/quotes`
  devuelve `[]` para todos los plazos y el stream solo entrega el `Success`.
  Que las listas vengan vacias no es un error.
- **`bars[].datetime` no tiene un formato estable**: en la misma cuenta llego
  como `"2026-01-01 10:00:00"` (sin zona) y como
  `"2026-11-25T15:40:10.000Z"` (ISO con `Z`). Si parseas historicos, contempla
  los dos o usa `bars[].timestamp`, que es unix y no cambia.
- **`balances` y `positions` funcionan sin whitelisting**; `watchlists`,
  `activities` y `activities/operations` tambien, incluso fuera de horario.

## Lectura Adicional

- [`api-reference.md`](./api-reference.md): firma y retorno de cada metodo.
- [`recipes/`](./recipes/): scripts cortos de solo lectura.
- [`notebooks/`](./notebooks/): recorrido interactivo.
- [`vendor/iol-api-v1.md`](./vendor/iol-api-v1.md): contrato congelado de la API.
- [`../SECURITY.md`](../SECURITY.md): como reportar un problema de seguridad.
