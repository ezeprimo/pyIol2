# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0-beta.1] - 2026-11-22

Primera beta publicada en TestPyPI para validar el pipeline de release
(construccion, `twine check`, Trusted Publishing y smoke install). No se publica
en PyPI: el workflow detecta el prerelanzamiento y solo apunta al indice de
pruebas.

### Added

- `IOLClient.get_access_token()` para reutilizar la sesion fuera del cliente
  (por ejemplo en el WebSocket) y `IOLClient.test_authentication()`, que
  devuelve un booleano igual que la version legacy.
- `IOLStreamClient.unsubscribe()` y `unsubscribe_all()`: dan de baja activos
  sin cerrar la conexion, con los tres canales siempre presentes en el frame.
- `scripts/smoke_test.py`: prueba de humo de solo lectura contra la API real,
  con verificacion opcional del handshake del WebSocket.
- `scripts/order_roundtrip.py`: crea, verifica y cancela una compra y una venta,
  cancelando en `finally` aunque algo falle, con baseline de ordenes previas y
  reconciliacion de altas ambiguas. Requiere `--yes`.

### Changed

- `IOLStreamClient.subscribe()` descarta los frames de protocolo (`Success` al
  confirmar la suscripcion, `Pong` del heartbeat) en lugar de entregarlos como
  mensajes sin simbolo ni precio. Una suscripcion rechazada sigue levantando
  `IOLStreamError`.
- `scripts/order_roundtrip.py` se niega a correr con el mercado operando (lo
  detecta por la frescura de la cotizacion) salvo `--allow-open-market`: con la
  rueda abierta una orden limite al precio de referencia puede ejecutarse.
- `scripts/stream_probe.py`: sonda de market data en vivo, de solo lectura.

- `estimate_order()` y `create_order()` rechazan `settlement_term=""` con
  `IOLValidationError`: la cadena vacia no es un default, `None` lo es. Antes se
  mandaba y la API respondia 400 sin detalle.

### Fixed

- `estimate_order()` y `create_order()` ahora mandan siempre `settlement_term`
  (por defecto `DEFAULT_ORDER_SETTLEMENT_TERM`, `T1`): la API responde `400` si
  falta, aunque el contrato lo marque opcional. Probado contra produccion.
  `DEFAULT_SETTLEMENT_TERM` (market data y streaming) se mantiene en `T0`:
  cambiar el default de los dos caminos a la vez movia sin querer el feed que
  piden los consumidores de streaming.

- Los errores de transporte (`httpx.HTTPError`) levantan `IOLConnectionError`,
  que se exportaba pero nunca se usaba.
- Las listas de `quotes` y `trades` de una suscripcion eran la misma instancia,
  asi que dar de baja un canal vaciaba el otro.

## [0.1.0] - 2026-11-21

Primera version publica de `pyiol2-client`, el cliente de la API v1 de IOL
Inversiones (`api.iolinversiones.com` + WebSocket de market data). No es
compatible con `pyiol-client` (API v2): ver la tabla de migracion del README.

### Added

- **Paquete**: distribucion `pyiol2-client` con el modulo `pyIol2`, Python
  `>=3.10`, build con hatchling.
- **Autenticacion**: `TokenManager` e `IOLToken` con OAuth2 password grant,
  renovacion por `refresh_token`, cache en memoria con margen de seguridad y
  renovacion serializada con lock.
- **Cliente REST**: `IOLClient` usable como context manager, con timeout
  configurable y un unico reintento automatico de reautenticacion ante `401`.
- **Estado del servicio**: `get_health_status()` (sin token).
- **Datos de mercado**: `get_market_quote()`, `get_market_depth()`,
  `get_screener_quotes()`, `get_option_chain()`, `get_historical_bars()`.
- **Assets**: `get_asset()`, `get_asset_types()`, `get_asset_panels()`.
- **Cuenta**: `get_account_balances()`, `get_positions()`,
  `get_account_activities()`, `get_trading_operations()`,
  `get_portfolio_history()`.
- **Ordenes**: `estimate_order()`, `create_order()`, `cancel_order()`, con
  validacion local de `quantity` XOR `notional`, `limit_price` obligatorio en
  ordenes `limit` y `X-Idempotency-Key` generado con UUID v4 si no se pasa.
- **Cauciones**: `get_repo_terms()`, `get_repo_quotes()`, `estimate_repo()`,
  `create_repo()`, `cancel_repo()`, con validacion local de `price_type` y
  `rate`.
- **FCI**: `validate_fund_subscription()`, `subscribe_fund()`,
  `validate_fund_redemption()`, `redeem_fund()`, `cancel_fund_operation()`, con
  validacion local de `quantity` XOR `redeem_all`.
- **Watchlists**: `get_watchlists()`, `get_watchlist()`, `create_watchlist()`,
  `rename_watchlist()`, `delete_watchlist()`, `add_watchlist_item()`,
  `remove_watchlist_item()`.
- **Version `_raw()`** de todos los metodos tipados, que devuelve el campo
  `data` de la respuesta sin transformar.
- **Streaming**: `IOLStreamClient` asincronico con autenticacion, `subscribe`,
  heartbeat cada 15 segundos, reconexion con backoff exponencial, reparto
  automatico de conexiones (50 simbolos por conexion de puntas y operaciones, 1
  por conexion de `order_book`) y `StreamMessage` tipado por canal.
- **Modelos**: dataclasses con `from_dict()` para el sobre `{meta, data, error}`
  y para todos los recursos de la v1.
- **Errores**: `IOLAPIError` con `status_code`, `code`, `trace_id`, `details`,
  `method`, `path` y `payload`, mas las subclases `IOLAuthenticationError`,
  `IOLValidationError`, `IOLNotFoundError`, `IOLRateLimitError`,
  `IOLServerError`, `IOLConnectionError` y `IOLStreamError`.
- **Constantes**: `Markets`, `SettlementTerms`, `Countries`, `GrantTypes`,
  `StreamChannels`, `StreamMessageTypes`, `StreamActions` y las URLs base.
- **Tests**: suite con `httpx.MockTransport` y un WebSocket falso, sin red ni
  credenciales.
- **Documentacion**: README con tabla de migracion desde `py_iol`,
  `doc/agent-guide.md`, `doc/api-reference.md`, recetas ejecutables de solo
  lectura, notebooks sin ejecutar y `llms.txt`.
- **CI y publicacion**: workflows de integracion continua y de publicacion con
  Trusted Publishing (TestPyPI primero, PyPI para versiones no prerelease).

[Unreleased]: https://github.com/ezeprimo/pyIol2/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ezeprimo/pyIol2/releases/tag/v0.1.0
