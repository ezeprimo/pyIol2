# pyIol2

Cliente Python no oficial para la **API de IOL Inversiones**: la plataforma nueva
(`api.iolinversiones.com`), con REST tipado y streaming de market data por
WebSocket.

| Campo | Valor |
|-------|-------|
| Paquete | `pyiol2-client` |
| Modulo | `pyIol2` |
| Version | 0.1.0 |
| Python | >=3.10 |
| Autor | Ezequiel Primon |
| Repositorio | https://github.com/ezeprimo/pyIol2 |

> Este proyecto es el sucesor de [`py_iol`](https://github.com/ezeprimo/py_iol),
> que envuelve la API v2 (`api.invertironline.com`). Las dos APIs no son
> compatibles entre si: la v1 usa otro host, otro esquema de autenticacion y otro
> formato de simbolo (`GGAL|BCBA|T0`). Por eso son dos paquetes distintos y no
> dos versiones del mismo.

## Que incluye

- **REST tipado**: dataclasses con `from_dict()` para cada respuesta y su
  version `_raw()` cuando necesitas el JSON crudo.
- **Autenticacion OAuth2** con cache de token y renovacion por `refresh_token`.
- **Streaming WebSocket** de market data: puntas, profundidad y operaciones en
  tiempo real, con heartbeat, reconexion y reparto automatico de conexiones.
- **Errores tipados** con el `trace_id` de la API, que es el dato que pide el
  soporte de IOL.
- Cobertura completa de la v1: cotizaciones, profundidad del libro y serie
  historica, screener, cadena de opciones, saldos, posiciones, movimientos,
  operaciones, historial de patrimonio, ordenes, cauciones, FCI y watchlists.
- Documentacion para personas y para agentes de IA, notebooks ejecutables y
  recetas cortas.

## Instalacion

```bash
# Con uv (recomendado)
uv add pyiol2-client

# Con pip
pip install pyiol2-client
```

Para desarrollo del proyecto:

```bash
git clone https://github.com/ezeprimo/pyIol2.git
cd pyIol2
uv sync --all-extras
```

## Configuracion

Las credenciales van por entorno o en un `.env` local, nunca en el codigo:

```dotenv
IOL_USERNAME=tu_usuario_iol
IOL_PASSWORD=tu_password_iol
```

El `.env` esta ignorado por git y no debe commitearse.

## Uso basico

```python
from pyIol2 import IOLClient, Markets, SettlementTerms

with IOLClient("usuario", "password") as client:
    # Cotizacion de GGAL contado inmediato
    cotizacion = client.get_market_quote("GGAL", market=Markets.BCBA, term=SettlementTerms.T0)
    print(cotizacion.prices.current, cotizacion.change.percent)

    # Posiciones de la cuenta
    for posicion in client.get_positions().positions:
        print(posicion.instrument.symbol, posicion.quantity, posicion.market_value.current_price)
```

Todos los metodos tipados tienen su gemelo `_raw()`, que devuelve el campo
`data` de la respuesta sin transformar:

```python
with IOLClient("usuario", "password") as client:
    crudo = client.get_market_quote_raw("GGAL")
    print(crudo["prices"]["current"])
```

## Streaming en tiempo real

```python
import asyncio

from pyIol2 import IOLStreamClient, Markets, SettlementTerms


async def main():
    async with IOLStreamClient("usuario", "password") as stream:
        async for message in stream.subscribe(
            symbols=["GGAL"],
            market=Markets.BCBA,
            term=SettlementTerms.T0,
            quotes=True,
            trades=True,
        ):
            print(message.type, message.symbol, message.raw)


asyncio.run(main())
```

La libreria autentica cada conexion, manda el `subscribe`, mantiene el heartbeat
y reparte los simbolos en tantas conexiones como haga falta (50 por conexion
para puntas y operaciones, 1 para profundidad).

## Migracion desde py_iol

`py_iol` habla la API v2 y `pyIol2` habla la v1. No hay capa de compatibilidad:
aunque el nombre de la clase sea el mismo (`IOLClient`), apunta a otro host y
usa otras constantes, asi que conviene migrar modulo por modulo.

### Metodos

| `py_iol` (API v2) | `pyIol2` (API v1) |
|-------------------|-------------------|
| `test_authentication()` | `get_health_status()` (sin token) o `get_account_balances()` |
| `get_profile_data()` | sin equivalente: la v1 no expone perfil |
| `get_stock_quote(symbol, market, settlement_term)` | `get_market_quote(symbol, market, term)` |
| `get_stock_quote_detailed(simbolo, mercado)` | `get_market_depth(symbol, market, term)` |
| `get_stock_data(symbol, market)` | `get_asset(symbol, market)` |
| `get_stock_options(symbol, market)` | `get_option_chain(symbol, market)` |
| `get_market_instruments(pais)` | `get_screener_quotes(asset_type, panel, country)` |
| `get_massive_quotes(instrumento, pais)` | `get_screener_quotes(asset_type, panel, country)` |
| `get_panel_quotes(instrumento, panel, pais)` | `get_screener_quotes(asset_type, panel, country)` |
| `get_account_status()` | `get_account_balances(country)` |
| `get_portfolio(pais)` | `get_positions(country, valuation_currency)` |
| `get_operations(...)` | `get_trading_operations(start_date, end_date, ...)` |
| `get_operation_detail(numero)` | sin equivalente dedicado: `get_trading_operations(..., transaction_id=...)` |
| `buy(...)` / `sell(...)` | `create_order(symbol, side="buy" / "sell", ...)` |
| `buy_dollar_bond(...)` / `sell_dollar_bond(...)` | `create_order(...)` sobre el simbolo del bono |
| `cancel_operation(numero)` | `cancel_order(order_id)` |
| `get_fci_list()`, `get_fci_detail()`, `get_fci_types()`, `get_fci_managers()`, `get_fci_types_by_manager()` | sin equivalente: la v1 no expone el catalogo de FCI |
| `subscribe_fci(simbolo, monto, solo_validar)` | `validate_fund_subscription()` y `subscribe_fund()` |
| `redeem_fci(simbolo, cantidad, monto, solo_validar)` | `validate_fund_redemption()` y `redeem_fund()` |
| `*_mep_*` (dolar MEP) | sin equivalente en la v1 |
| `*_cpd_*` (cheques de pago diferido) | sin equivalente en la v1 |
| Metodos de asesores | sin equivalente en la v1 |

### Lo que agrega la v1

- `get_historical_bars(symbol, start, end, market)` — serie OHLCV historica.
- `get_market_depth(symbol, market, term)` — profundidad del libro.
- `get_screener_quotes(asset_type, panel, country, term)` — listado de un panel,
  con `get_asset_types()` y `get_asset_panels()` para descubrir los ids.
- `get_account_activities(...)`, `get_portfolio_history(...)` — movimientos y
  evolucion diaria del patrimonio.
- Cauciones: `get_repo_terms()`, `get_repo_quotes()`, `estimate_repo()`,
  `create_repo()`, `cancel_repo()`.
- Watchlists: `get_watchlists()`, `get_watchlist()`, `create_watchlist()`,
  `rename_watchlist()`, `delete_watchlist()`, `add_watchlist_item()`,
  `remove_watchlist_item()`.
- Streaming de market data con `IOLStreamClient`.

### Diferencias de vocabulario

| Tema | `py_iol` | `pyIol2` |
|------|----------|----------|
| Host REST | `api.invertironline.com` | `api.iolinversiones.com` |
| `Markets.BCBA` | `"bCBA"` | `"BCBA"` |
| `SettlementTerms` | `T0`, `T1`, `T2`, `T3`; default `T1` | `T0`, `T1`; default `T0` |
| `Countries` | `"argentina"`, `"estados_Unidos"` | `"AR"`, `"US"`, `"all"` |
| Identificador de activo | simbolo + mercado + plazo por parametro | igual en REST; el WebSocket usa `GGAL|BCBA|T0` |
| `_raw()` | puede normalizar listas y envoltorios | devuelve el campo `data` de la v1, sin normalizar |
| Errores | `IOLAPIError` | `IOLAPIError` y sus subclases, con `trace_id` |

Los ids de tipo de activo y de panel del screener son datos de la API: se piden
con `get_asset_types()` y `get_asset_panels()`, no son alias fijos como
`"acciones"` o `"merval"`.

## Documentacion

- [`doc/README.md`](doc/README.md) — indice de la documentacion
- [`doc/agent-guide.md`](doc/agent-guide.md) — como usar la libreria desde un agente de IA
- [`doc/api-reference.md`](doc/api-reference.md) — referencia de todos los metodos publicos
- [`doc/recipes/`](doc/recipes) — recetas cortas y ejecutables
- [`doc/notebooks/`](doc/notebooks) — notebooks paso a paso
- [`scripts/README.md`](scripts/README.md) — las herramientas de verificacion contra la API real
- [`doc/vendor/iol-api-v1.md`](doc/vendor/iol-api-v1.md) — contrato de la API congelado tal como lo publica IOL
- [`llms.txt`](llms.txt) — mapa del repositorio para agentes
- [`CHANGELOG.md`](CHANGELOG.md) — historial de versiones
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — como contribuir
- [`SECURITY.md`](SECURITY.md) — politica de seguridad
- [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) — como se publica

## Estado

`0.x`. La API v1 de IOL es nueva y puede cambiar sin aviso: hasta que se
estabilice, los cambios incompatibles llegan en versiones `0.MINOR.0`. Los
metodos de escritura (ordenes, FCI, cauciones) mueven dinero real: valida los
datos antes de llamarlos.

## Licencia

MIT. Ver [`LICENCE`](LICENCE).
