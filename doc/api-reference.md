# pyIol2 API Reference

Referencia derivada del codigo de `pyIol2/client.py`, `pyIol2/stream.py`,
`pyIol2/models.py` y `pyIol2/constants.py`. Las firmas y los defaults son los
reales; si algo no coincide, manda el codigo.

Convenciones de esta pagina:

- Todos los metodos tipados tienen un gemelo `_raw()` con **la misma firma** y
  el mismo comportamiento de red, que devuelve `dict[str, Any]` (o
  `list[dict[str, Any]]`) con el campo `data` de la respuesta. Los `_raw()` no
  devuelven `meta` ni `error`.
- Los metodos sin token usan `authenticated=False`: solo `get_health_status()`.
- Todo error de la API o de red se propaga como `IOLAPIError` o una subclase.
  Las validaciones locales fallan con `IOLValidationError` **antes** de enviar
  la request.
- Defaults de protocolo: `DEFAULT_MARKET = Markets.BCBA` (`"BCBA"`),
  `DEFAULT_SETTLEMENT_TERM = SettlementTerms.T0` (`"T0"`),
  `DEFAULT_COUNTRY = Countries.ARGENTINA` (`"AR"`),
  `DEFAULT_TIMEOUT = 30.0`.

## Cliente REST

### `IOLClient(username, password, *, base_url=API_BASE_URL, timeout=DEFAULT_TIMEOUT, client=None)`

Crea el cliente REST. La autenticacion es perezosa: el token se pide en la
primera request autenticada.

- `username` (`str`) — usuario de IOL.
- `password` (`str`) — contrasena de IOL.
- `base_url` (`str`) — default `https://api.iolinversiones.com`.
- `timeout` (`float`) — timeout por request, en segundos; default `30.0`.
- `client` (`httpx.Client | None`) — cliente HTTP ya armado; si se pasa, el
  cliente no lo cierra.

### `__enter__()` / `__exit__(...)` / `close()`

Context manager y cierre explicito. `close()` cierra el `httpx.Client` solo si
lo creo esta instancia (`_owns_client`).

## Estado del servicio

### `get_health_status()`

Estado del servicio de la API. No requiere token.

- **Retorna** `HealthStatus` (`status`, `timestamp`, `uptime`, `version`).
- **Raw** `get_health_status_raw()` → `dict[str, Any]`.

## Datos de mercado

### `get_market_quote(symbol, market=Markets.BCBA, term=SettlementTerms.T0)`

Cotizacion de mercado de un activo.

- `symbol` (`str`) — simbolo, por ejemplo `GGAL`.
- `market` (`str`) — mercado segun `Markets`.
- `term` (`str`) — plazo segun `SettlementTerms`.
- **Retorna** `MarketQuote` (`prices`, `change`, `volume`, `currency`,
  `lot_size`, `last_updated`).
- **Raw** `get_market_quote_raw(...)` → `dict[str, Any]`.

### `get_market_depth(symbol, market=Markets.BCBA, term=SettlementTerms.T0)`

Profundidad del libro de ordenes.

- `symbol`, `market`, `term` — igual que `get_market_quote`.
- **Retorna** `MarketDepth` con `bids` y `asks` (`list[DepthLevel]`).
- **Raw** `get_market_depth_raw(...)` → `dict[str, Any]`.

### `get_screener_quotes(asset_type, panel, country=Countries.ARGENTINA, term=SettlementTerms.T0)`

Cotizaciones de un panel de un tipo de activo.

- `asset_type` (`str`) — id de tipo de activo, de `get_asset_types()`.
- `panel` (`str`) — id de panel, de `get_asset_panels()`.
- `country` (`str`) — pais segun `Countries`.
- `term` (`str`) — plazo.
- **Retorna** `list[ScreenerEntry]` (`instrument`, `quotes`, `book`).
- **Raw** `get_screener_quotes_raw(...)` → `list[dict[str, Any]]`.
- **Ojo con los ids**: contra la API real `asset_type` vale `acciones`,
  `cedears`, `etfs`, `opciones`, `bonos`, `letras`, `obligaciones_negociables`,
  `fondos`, `cauciones`, `cheques`, `indices` o `monedas`, y `panel` es un id
  como `argaccionespanelgeneral`. No hay `stocks` ni `bluechips`: los ids se
  piden con `get_asset_types()` y `get_asset_panels()`.
- **Errores** `IOLAPIError` si el par `asset_type`/`panel` no existe.

### `get_option_chain(symbol, market=Markets.BCBA)`

Cadena de opciones de un titulo subyacente.

- `symbol` (`str`) — subyacente.
- `market` (`str`) — mercado.
- **Retorna** `list[OptionQuote]` (`symbol`, `option`, `quotes`, `book`).
- **Raw** `get_option_chain_raw(...)` → `list[dict[str, Any]]`.

### `get_historical_bars(symbol, start, end, market=Markets.BCBA)`

Serie historica OHLCV.

- `symbol` (`str`) — simbolo.
- `start` (`str`) — desde, `YYYY-MM-DD HH:MM:SS`.
- `end` (`str`) — hasta, `YYYY-MM-DD HH:MM:SS`.
- `market` (`str`) — mercado.
- **Retorna** `HistoricalBars` (`symbol`, `market`, `total_bars`, `bars`).
- **Raw** `get_historical_bars_raw(...)` → `dict[str, Any]`.

## Cauciones (repos)

### `get_repo_terms(currency="ARS")`

Plazos de caucion disponibles.

- `currency` (`str`) — `ARS` o `USD`.
- **Retorna** `list[RepoTerm]` (`term_id`, `term_days`, `due_date`,
  `min_amount`, `max_amount`).
- **Raw** `get_repo_terms_raw(currency)` → `list[dict[str, Any]]`.

### `get_repo_quotes(term_id, currency="ARS")`

Libro de cauciones para un plazo.

- `term_id` (`int`) — id de plazo, de `get_repo_terms()`.
- `currency` (`str`) — `ARS` o `USD`.
- **Retorna** `list[RepoQuote]` (`position`, `bid`, `ask`).
- **Raw** `get_repo_quotes_raw(...)` → `list[dict[str, Any]]`.

### `estimate_repo(amount, term_id, *, currency="ARS", price_type="market", rate=None)`

Estima los costos de una caucion. No tiene efectos.

- `amount` (`float`) — importe a colocar.
- `term_id` (`int`) — id de plazo.
- `currency` (`str`) — `ARS` o `USD`.
- `price_type` (`str`) — `market` o `limit`.
- `rate` (`float | None`) — tasa; obligatoria si `price_type="limit"`.
- **Retorna** `list[RepoEstimate]`.
- **Errores** `IOLValidationError` si `price_type` es invalido o falta `rate`.
- **Raw** `estimate_repo_raw(...)` → `list[dict[str, Any]]`.

### `create_repo(amount, term_id, *, currency="ARS", price_type="market", rate=None, idempotency_key=None)`

Toma una caucion. **Mueve dinero real.**

- Mismos argumentos que `estimate_repo`, mas:
- `idempotency_key` (`str | None`) — UUID v4 para el header
  `X-Idempotency-Key`; se genera uno si no se pasa.
- **Retorna** `RepoOrderResult` (`order_id`).
- **Raw** `create_repo_raw(...)` → `dict[str, Any]`.

### `cancel_repo(order_id)`

Cancela una caucion tomada. **Efecto real.**

- `order_id` (`str`) — id devuelto por `create_repo()`.
- **Retorna** `CancelResult` (`cancelled`, `order_id`, `status`).
- **Raw** `cancel_repo_raw(order_id)` → `dict[str, Any]`.

## Assets

### `get_asset(symbol, market=Markets.BCBA)`

Datos de un activo y sus condiciones de negociacion.

- **Retorna** `AssetDetail` (`trading_info` con `lot_size`,
  `minimum_investment`, `minimum_quantity`).
- **Raw** `get_asset_raw(...)` → `dict[str, Any]`.

### `get_asset_types(country=Countries.ARGENTINA)`

Tipos de activo disponibles para filtrar el screener.

- `country` (`str`) — pais segun `Countries`.
- **Retorna** `list[AssetType]` (`id`, `name`).
- **Raw** `get_asset_types_raw(country)` → `list[dict[str, Any]]`.

### `get_asset_panels(asset_type, country=Countries.ARGENTINA)`

Paneles de trading disponibles para un tipo de activo.

- `asset_type` (`str`) — id de `get_asset_types()`.
- `country` (`str`) — pais.
- **Retorna** `list[AssetPanel]` (`id`, `name`).
- **Raw** `get_asset_panels_raw(...)` → `list[dict[str, Any]]`.

## Cuenta

### `get_account_balances(country=Countries.ARGENTINA)`

Saldos de la cuenta en pesos y en dolares.

- `country` (`str`) — pais de la cuenta.
- **Retorna** `AccountBalances` (`ars`, `usd`, cada uno `Balance` con `totals`,
  `available`, `committed` y `available_for_withdrawal`).
- **Raw** `get_account_balances_raw(country)` → `dict[str, Any]`.

### `get_positions(country=Countries.ARGENTINA, valuation_currency=None)`

Posiciones de la cartera.

- `country` (`str`) — pais de la cuenta.
- `valuation_currency` (`str | None`) — `ARS`, `USD`, `MEP` o `CCL`; si es
  `None` no se envia el parametro.
- **Retorna** `Portfolio` (`account`, `currency`, `positions`,
  `positions_count`, `total_market_value`).
- **Raw** `get_positions_raw(...)` → `dict[str, Any]`.

### `get_account_activities(start_date, end_date, *, movement_type=None, state=None, country=None, currency=None)`

Movimientos de cuenta: depositos, retiros, operaciones, rentas y demas.

- `start_date` (`str`) / `end_date` (`str`) — `YYYY-MM-DD`.
- `movement_type` (`str | None`) — filtro de tipo de movimiento.
- `state` (`str | None`) — `all`, `completed`, `pending`, `cancelled`.
- `country` (`str | None`) — `all`, `AR`, `US`.
- `currency` (`str | None`) — `all`, `ARS`, `USD`.
- Los filtros opcionales solo se envian si no son `None`.
- **Retorna** `list[Activity]`.
- **Raw** `get_account_activities_raw(...)` → `list[dict[str, Any]]`.

### `get_trading_operations(start_date, end_date, *, state=None, transaction_type=None, symbol=None, term=None, asset_type=None, currency=None, country=None, transaction_id=None)`

Operaciones de trading del periodo, con lo pedido y lo ejecutado.

- `start_date`, `end_date` (`str`) — `YYYY-MM-DD`.
- `state` (`str | None`) — `all`, `completed`, `pending`, `cancelled`,
  `finished`.
- `transaction_type` (`str | None`) — `purchase`, `sale`, `subscription`,
  `redemption`, `repo`, ...
- `symbol`, `term`, `asset_type`, `currency`, `country`, `transaction_id`
  (`str | None`) — filtros opcionales.
- **Retorna** `list[Operation]` (`order`, `executed`, `status`, `term`, ...).
- **Raw** `get_trading_operations_raw(...)` → `list[dict[str, Any]]`.

### `get_portfolio_history(start_date, end_date, country=Countries.ARGENTINA)`

Evolucion diaria del patrimonio de la cuenta.

- `start_date`, `end_date` (`str`) — `YYYY-MM-DD`.
- `country` (`str`) — pais de la cuenta.
- **Retorna** `PortfolioHistory` (`account`, `status`, `history`,
  `missing_dates`). Si `status` es `partial`, revisar `missing_dates`.
- **Raw** `get_portfolio_history_raw(...)` → `dict[str, Any]`.

## Ordenes

Validacion local comun: `side` es `buy` o `sell`, `order_type` es `limit` o
`market`, hay `quantity` o `notional` pero no los dos, y `limit_price` es
obligatorio cuando `order_type="limit"`. `due_date` vacio se completa con la
fecha de hoy.

### `estimate_order(symbol, side, *, quantity=None, notional=None, market_id=Markets.BCBA, order_type="market", limit_price=None, settlement_term=None, due_date=None)`

Estima comisiones y cargos de una orden. No tiene efectos.

- `symbol` (`str`) — simbolo del activo.
- `side` (`str`) — `buy` o `sell`.
- `quantity` (`float | None`) — nominales; excluyente con `notional`.
- `notional` (`float | None`) — monto en moneda; excluyente con `quantity`.
- `market_id` (`str`) — mercado segun `Markets`.
- `order_type` (`str`) — `limit` o `market`.
- `limit_price` (`float | None`) — obligatorio en ordenes `limit`.
- `settlement_term` (`str | None`) — plazo de liquidacion. Si es `None` se
  manda `DEFAULT_ORDER_SETTLEMENT_TERM` (`T1`): la API responde 400 si el
  cuerpo no lo incluye, aunque el contrato lo marque opcional. El default de
  market data y streaming sigue siendo `DEFAULT_SETTLEMENT_TERM` (`T0`).
- `due_date` (`str | None`) — `YYYY-MM-DD`; default hoy.
- **Retorna** `OrderEstimate` (`amount`, `commission`, `regulatory_fees`).
- **Raw** `estimate_order_raw(...)` → `dict[str, Any]`.

### `create_order(symbol, side, *, quantity=None, notional=None, market_id=Markets.BCBA, order_type="market", limit_price=None, settlement_term=None, due_date=None, idempotency_key=None)`

Da de alta una orden. **Mueve dinero real.**

- Mismos argumentos que `estimate_order`, mas:
- `idempotency_key` (`str | None`) — UUID v4 para `X-Idempotency-Key`; se
  genera uno si no se pasa.
- **Retorna** `OrderResult` (`order_id`, `successful_purchase`, `messages`).
- **Raw** `create_order_raw(...)` → `dict[str, Any]`.

### `cancel_order(order_id)`

Cancela una orden. **Efecto real.**

- `order_id` (`str`) — id devuelto por `create_order()`.
- **Retorna** `CancelResult`.
- **Raw** `cancel_order_raw(order_id)` → `dict[str, Any]`.

## Fondos comunes de inversion (FCI)

### `validate_fund_subscription(symbol, amount)`

Valida una suscripcion sin enviarla. No tiene efectos.

- `symbol` (`str`) — simbolo del fondo.
- `amount` (`float`) — monto a suscribir.
- **Retorna** `FundValidationResult` (`valid`, `messages`).
- **Raw** `validate_fund_subscription_raw(...)` → `dict[str, Any]`.

### `subscribe_fund(symbol, amount, *, idempotency_key=None)`

Suscribe a un FCI. **Mueve dinero real.**

- `symbol` (`str`), `amount` (`float`).
- `idempotency_key` (`str | None`) — se genera uno si no se pasa.
- **Retorna** `FundOperationResult` (`transaction_id`, `successful`,
  `messages`).
- **Raw** `subscribe_fund_raw(...)` → `dict[str, Any]`.

### `validate_fund_redemption(symbol, *, quantity=None, redeem_all=False)`

Valida un rescate sin enviarlo. No tiene efectos.

- `symbol` (`str`) — simbolo del fondo.
- `quantity` (`float | None`) — cantidad a rescatar; se ignora si
  `redeem_all=True`.
- `redeem_all` (`bool`) — rescatar la tenencia completa.
- **Retorna** `FundValidationResult`.
- **Errores** `IOLValidationError` si no hay `quantity` ni `redeem_all=True`.
- **Raw** `validate_fund_redemption_raw(...)` → `dict[str, Any]`.

### `redeem_fund(symbol, *, quantity=None, redeem_all=False, idempotency_key=None)`

Rescata un FCI. **Mueve dinero real.**

- `symbol` (`str`), `quantity` (`float | None`), `redeem_all` (`bool`),
  `idempotency_key` (`str | None`).
- **Retorna** `FundOperationResult`.
- **Errores** `IOLValidationError` si no hay `quantity` ni `redeem_all=True`.
- **Raw** `redeem_fund_raw(...)` → `dict[str, Any]`.

### `cancel_fund_operation(transaction_id)`

Cancela una suscripcion o rescate de FCI pendiente. **Efecto real.**

- `transaction_id` (`str`) — id devuelto por `subscribe_fund()` o
  `redeem_fund()`.
- **Retorna** `FundCancelResult` (`cancelled`, `status`, `transaction_id`).
- **Raw** `cancel_fund_operation_raw(transaction_id)` → `dict[str, Any]`.

## Watchlists

### `get_watchlists()`

Lista de watchlists de la cuenta con sus cotizaciones.

- **Retorna** `list[Watchlist]` (`id`, `name`, `items_count`, `items`).
- **Raw** `get_watchlists_raw()` → `list[dict[str, Any]]`.

### `get_watchlist(watchlist_id, term=None)`

Una watchlist por id.

- `watchlist_id` (`int`) — id de la lista.
- `term` (`str | None`) — plazo de las cotizaciones; si es `None` no se envia.
- **Retorna** `Watchlist`.
- **Raw** `get_watchlist_raw(watchlist_id, term)` → `dict[str, Any]`.

### `create_watchlist(name, items=None)`

Crea una watchlist. **Efecto real** (sin dinero).

- `name` (`str`) — nombre de la lista.
- `items` (`list[dict[str, str]] | None`) — items iniciales, cada uno con
  `symbol` y `market`; default lista vacia.
- **Retorna** `Watchlist`.
- **Raw** `create_watchlist_raw(name, items)` → `dict[str, Any]`.

### `rename_watchlist(watchlist_id, name)`

Renombra una watchlist. **Efecto real.**

- `watchlist_id` (`int`), `name` (`str`) — nombre nuevo.
- **Retorna** `WatchlistRenamed` (`id`, `name`, `renamed`).
- **Raw** `rename_watchlist_raw(...)` → `dict[str, Any]`.

### `delete_watchlist(watchlist_id)`

Elimina una watchlist. **Efecto real.**

- `watchlist_id` (`int`).
- **Retorna** `WatchlistDeleted` (`id`, `deleted`).
- **Raw** `delete_watchlist_raw(watchlist_id)` → `dict[str, Any]`.

### `add_watchlist_item(watchlist_id, symbol, market=Markets.BCBA)`

Agrega un activo a una watchlist. **Efecto real.**

- `watchlist_id` (`int`), `symbol` (`str`), `market` (`str`).
- **Retorna** `WatchlistItemAdded` (`watchlist_id`, `symbol`, `market`,
  `added`).
- **Raw** `add_watchlist_item_raw(...)` → `dict[str, Any]`.

### `remove_watchlist_item(watchlist_id, symbol, market=None)`

Quita un activo de una watchlist. **Efecto real.**

- `watchlist_id` (`int`), `symbol` (`str`).
- `market` (`str | None`) — si hace falta desambiguar; si es `None` no se
  envia.
- **Retorna** `WatchlistItemRemoved` (`watchlist_id`, `symbol`, `market`,
  `removed`).
- **Raw** `remove_watchlist_item_raw(...)` → `dict[str, Any]`.

## Cliente de Streaming

### `IOLStreamClient(username=None, password=None, *, token=None, base_url=STREAM_BASE_URL, max_symbols=50, heartbeat_interval=15.0, reconnect_attempts=5, connect_factory=None)`

Cliente asincronico del WebSocket de market data.

- `username`, `password` (`str | None`) — credenciales para pedir el token.
- `token` (`str | None`) — access token ya emitido; si se pasa, no se piden
  credenciales.
- `base_url` (`str`) — default `wss://stream-marketdata.invertironline.com`.
- `max_symbols` (`int`) — simbolos por conexion de puntas y operaciones;
  default `50`.
- `heartbeat_interval` (`float`) — segundos entre pings; default `15.0`.
- `reconnect_attempts` (`int`) — reintentos por conexion; default `5`.
- `connect_factory` (`ConnectFactory | None`) — conector alternativo, para
  tests.
- **Errores** `IOLValidationError` si no hay `token` ni credenciales, o si
  `max_symbols < 1`.

### `__aenter__()` / `__aexit__(...)` / `close()`

Context manager asincronico. `close()` cancela las tareas y cierra las
conexiones; tambien se llama al salir del `async for`.

### `get_access_token()`

Devuelve el token para autenticar el WebSocket: usa `token` si se paso al
construir, y si no pide uno nuevo por `/auth/token`.

- **Retorna** `str`.
- **Raw** — no aplica.

### `subscribe(symbols, *, market=Markets.BCBA, term=SettlementTerms.T0, quotes=True, trades=True, order_book=False)`

Abre las conexiones necesarias y devuelve un iterador de mensajes.

- `symbols` (`list[str]`) — simbolos a seguir.
- `market` (`str`) — mercado de todos los simbolos.
- `term` (`str`) — plazo de todos los simbolos.
- `quotes` (`bool`) — pedir puntas; default `True`.
- `trades` (`bool`) — pedir operaciones; default `True`.
- `order_book` (`bool`) — pedir profundidad; admite un solo simbolo por
  llamada; default `False`.
- **Retorna** `AsyncIterator[StreamMessage]`.
- **Errores** `IOLValidationError` si no hay simbolos, si no se pide ningun
  canal o si `order_book` viene con mas de un simbolo. `IOLStreamError` si el
  servidor rechaza la autenticacion, informa un error o se agotan los
  reintentos.
- **Limites** 50 simbolos por conexion para `quotes`/`trades` (reparto
  automatico); 1 para `order_book`.

### `unsubscribe(symbols, *, market=Markets.BCBA, term=SettlementTerms.T0)`

Da de baja activos sin cerrar las conexiones abiertas.

- `symbols` (`list[str]`) — simbolos a desuscribir.
- `market` (`str`), `term` (`str`) — mercado y plazo de esos simbolos.
- **Retorna** `list[str]` con los identificadores `SIMBOLO|MERCADO|PLAZO` que
  estaban efectivamente suscriptos; si viene vacia, no habia nada que dar de
  baja y la libreria no manda ningun frame.
- **Cuando usarlo** para achicar el seguimiento sin reconectar. La conexion
  sigue viva y los mensajes ya suscriptos siguen llegando.

### `unsubscribe_all()`

Da de baja todas las suscripciones de todas las conexiones abiertas, sin
cerrarlas. No devuelve nada.

### `StreamMessage`

Mensaje tipado del WebSocket.

- `type: str` — `Q` puntas, `B` profundidad, `T` operaciones.
- `symbol: str`, `market: str`, `term: str`.
- `quote: StreamQuoteMessage | None` — si `type == "Q"`.
- `order_book: StreamOrderBookMessage | None` — si `type == "B"`.
- `trade: StreamTradeMessage | None` — si `type == "T"`.
- `raw: dict[str, Any]` — JSON original.
- `from_dict(data)` — constructor.

## Constantes

| Nombre | Valores |
|--------|---------|
| `API_BASE_URL` | `https://api.iolinversiones.com` |
| `AUTH_URL` | `https://api.iolinversiones.com/auth/token` |
| `STREAM_BASE_URL` | `wss://stream-marketdata.invertironline.com` |
| `Markets` | `BCBA="BCBA"`, `NYSE="NYSE"`, `NASDAQ="NASDAQ"`, `AMEX="AMEX"` |
| `SettlementTerms` | `T0="T0"`, `T1="T1"`; default `T0` |
| `Countries` | `ARGENTINA="AR"`, `USA="US"`, `ALL="all"` |
| `GrantTypes` | `PASSWORD="password"`, `REFRESH_TOKEN="refresh_token"` |
| `StreamChannels` | `QUOTES="quotes"`, `ORDER_BOOK="order_book"`, `TRADES="trades"` |
| `StreamMessageTypes` | `QUOTE="Q"`, `ORDER_BOOK="B"`, `TRADES="T"`, `ERROR="Error"` |
| `StreamActions` | `AUTH`, `AUTH_TOKEN`, `SUBSCRIBE`, `UNSUBSCRIBE`, `UNSUBSCRIBE_ALL`, `PING`, `DISCONNECT` (valores en minuscula) |
| Limites del stream | 50 simbolos por conexion, 1 para `order_book`, heartbeat 15s, backoff 1s→30s, 5 reintentos |

## Modelos

Todos los modelos son dataclasses con `from_dict()` y campos con default, y se
importan desde `pyIol2`. Los modelos anidados se documentan dentro de su padre.

### Sobre de la API

- `IOLMeta`: `timestamp`, `path`, `method`, `status_code`, `trace_id`,
  `total_count`.
- `IOLResponse`: `data`, `meta: IOLMeta`, `error: dict | None`.
- `HealthStatus`: `status`, `timestamp`, `uptime`, `version`.

### Datos de mercado

- `MarketQuote`: `symbol`, `market`, `settlement_term`, `currency`, `lot_size`,
  `maturity_date`, `last_updated`, `prices: Prices`, `change: PriceChange`,
  `volume: Volume`.
  - `Prices`: `close`, `current`, `high`, `low`, `open`, `previous_close`.
  - `PriceChange`: `amount`, `percent`.
  - `Volume`: `amount`, `shares`.
- `MarketDepth`: `symbol`, `market`, `settlement_term`, `lot_size`,
  `last_updated`, `bids: list[DepthLevel]`, `asks: list[DepthLevel]`.
  - `DepthLevel`: `position`, `price`, `size`.
- `ScreenerEntry`: `instrument: InstrumentSummary`, `quotes: QuoteSnapshot`,
  `book: OrderBookTop`.
- `OptionQuote`: `symbol`, `option: OptionTerms`, `quotes: QuoteSnapshot`,
  `book: OrderBookTop`.
- `HistoricalBar`: `datetime`, `timestamp`, `open`, `high`, `low`, `close`,
  `volume`.
- `HistoricalBars`: `symbol`, `market`, `total_bars`, `bars`.

### Assets

- `AssetDetail`: `symbol`, `name`, `asset_type`, `market`, `country`,
  `currency`, `default_settlement_term`, `trading_info: AssetTradingInfo`.
- `AssetType`: `id`, `name`.
- `AssetPanel`: `id`, `name`.

### Cuenta

- `AccountBalances`: `ars: Balance`, `usd: Balance`.
  - `Balance`: `currency`, `totals: SettlementTotals`,
    `available: SettlementTotals`, `committed: SettlementTotals`,
    `available_for_withdrawal`.
  - `SettlementTotals`: `t0`, `t1`, `t2`, `t3`.
- `Portfolio`: `account`, `currency`, `positions: list[Position]`,
  `positions_count`, `total_market_value`.
- `Position`: `instrument: Instrument`, `parent_instrument`,
  `quantity`, `availability: PositionAvailability`,
  `cost_basis: CostBasis`, `market_value: MarketValue`, `profit_loss: ProfitLoss`,
  `portfolio_weight_percent`, `is_accredited`, `maturity_date`.
- `Instrument`: `symbol`, `name`, `type`, `asset_class`, `country`, `currency`,
  `exchange`, `lot_size`, `minimum_quantity`, `tradable`.
- `Activity`: `id`, `ticket_id`, `activity_type`, `activity_type_id`,
  `account_type`, `currency`, `status`, `qty`, `price`, `net_amount`,
  `fees: ActivityFees`, `trade_date`, `settlement_date`.
- `Operation`: `order_id`, `ticket_id`, `symbol`, `description`, `type`,
  `asset_type`, `currency`, `term`, `status`, `order_date`, `execution_date`,
  `order: OperationLeg`, `executed: OperationLeg`.
- `PortfolioHistory`: `account`, `status`, `history: list[PortfolioHistoryPoint]`,
  `missing_dates`.
  - `PortfolioHistoryPoint`: `date`, `cash_flow: CashFlow`, `equity: Equity`,
    `exchange_rate: ExchangeRate`, `has_pledged_collateral`.
  - `CashFlow`: `deposits_ars`, `deposits_usd`, `withdrawals_ars`,
    `withdrawals_usd`.
  - `Equity`: `ars`, `usd_ccl`, `usd_mep`.
  - `ExchangeRate`: `ccl`, `mep`.

### Ordenes

- `OrderEstimate`: `amount: MoneyAmount`, `commission: MoneyAmount`,
  `regulatory_fees: RegulatoryFees`.
  - `MoneyAmount`: `currency`, `value`.
  - `RegulatoryFees`: `market_fee: MoneyAmount`, `vat: MoneyAmount`.
- `OrderResult`: `order_id`, `successful_purchase`, `messages: list[OperationMessage]`.
- `OperationMessage`: `code`, `message`.
- `CancelResult`: `cancelled`, `order_id`, `status`.

### Cauciones

- `RepoTerm`: `term_id`, `term_days`, `due_date`, `min_amount`, `max_amount`.
- `RepoQuote`: `position`, `bid: RepoRateAmount`, `ask: RepoRateAmount`.
- `RepoEstimate`: `amount`, `commission_currency`, `commission_type`,
  `fee_type`, `vat_amount`.
- `RepoOrderResult`: `order_id`.

### FCI

- `FundValidationResult`: `valid`, `messages`.
- `FundOperationResult`: `transaction_id`, `successful`, `messages`.
- `FundCancelResult`: `cancelled`, `status`, `transaction_id`.

### Watchlists

- `Watchlist`: `id`, `name`, `items_count`, `items: list[WatchlistItem]`.
- `WatchlistItem`: `symbol`, `market`, `name`, `asset_type`, `settlement_term`,
  `quote: WatchlistQuote`.
  - `WatchlistQuote`: `last_price`, `change_percent`, `best_bid`,
    `best_bid_size`, `best_ask`, `best_ask_size`, `average_price`, `currency`,
    `volume`, `traded_quantity`, `traded_amount`, `last_updated`.

### Streaming

- `StreamQuoteMessage`: `symbol`, `market`, `term`, `datetime`,
  `levels: list[StreamLevel]`.
- `StreamOrderBookMessage`: `symbol`, `market`, `term`, `datetime`,
  `levels: list[StreamLevel]`.
- `StreamTradeMessage`: `symbol`, `market`, `term`, `datetime`, `last_price`,
  `change_percent`, `traded_quantity`, `traded_amount`, `last_quantity`.
- `StreamLevel`: `side`, `price`, `size`, `position`.

### Autenticacion

- `IOLToken`: `access_token`, `refresh_token`, `token_type`, `expires_in`,
  `expires_at`.
- `TokenManager`: `get_access_token()`, `refresh()`, `invalidate()`, propiedad
  `token`.

## Excepciones

| Clase | Base | Uso |
|-------|------|-----|
| `IOLAPIError` | `Exception` | Error generico; trae `message`, `status_code`, `code`, `trace_id`, `details`, `method`, `path`, `payload` |
| `IOLAuthenticationError` | `IOLAPIError` | `401` / `403` |
| `IOLValidationError` | `IOLAPIError` | `400` / `422` y validaciones locales |
| `IOLNotFoundError` | `IOLAPIError` | `404` |
| `IOLRateLimitError` | `IOLAPIError` | `429` |
| `IOLServerError` | `IOLAPIError` | `5xx` |
| `IOLConnectionError` | `IOLAPIError` | Fallo de conexion HTTP o de red antes de obtener respuesta |
| `IOLStreamError` | `IOLAPIError` | Error del WebSocket; agrega `ws_code` |
