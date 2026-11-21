#!/usr/bin/env python3
"""
Prueba de humo contra la API real de IOL Inversiones.

Solo hace lecturas: no crea ordenes, cauciones ni operaciones de FCI. Sirve para
verificar el contrato de la API (nombres de campos, sobre de respuesta, auth)
contra el servidor real.

Las credenciales se leen de IOL_USERNAME / IOL_PASSWORD o del `.env` local y
nunca se imprimen; tampoco se imprime el token.

Uso:
    uv run python scripts/smoke_test.py
    uv run python scripts/smoke_test.py --with-stream
"""

import argparse
import asyncio
import sys
from collections.abc import Callable
from datetime import date, timedelta

from dotenv import load_dotenv

from pyIol2 import (
    IOLAPIError,
    IOLClient,
    Markets,
    SettlementTerms,
    StreamMessage,
)

Result = tuple[str, str, str]


def _report(name: str, ok: bool, detail: str) -> Result:
    """Imprime el resultado de un paso y lo devuelve para el resumen."""
    mark = "OK  " if ok else "FALLA"
    print(f"[{mark}] {name}: {detail}")
    return (name, "ok" if ok else "falla", detail)


def _error_detail(exc: IOLAPIError) -> str:
    """Describe un error de la API sin exponer credenciales ni tokens."""
    parts = [type(exc).__name__, str(exc.message)]
    if exc.status_code is not None:
        parts.append(f"status={exc.status_code}")
    if exc.code is not None:
        parts.append(f"code={exc.code}")
    if exc.trace_id:
        parts.append(f"trace_id={exc.trace_id}")
    if exc.details:
        parts.append(f"details={exc.details!r}")
    return " | ".join(parts)


def _quote(client: IOLClient) -> str:
    quote = client.get_market_quote("GGAL", Markets.BCBA, SettlementTerms.T0)
    return (
        f"{quote.symbol} {quote.market} {quote.settlement_term} "
        f"ultimo={quote.prices.current} variacion={quote.change.percent}% "
        f"moneda={quote.currency} lote={quote.lot_size}"
    )


def _depth(client: IOLClient) -> str:
    depth = client.get_market_depth("GGAL", Markets.BCBA, SettlementTerms.T0)
    best_bid = depth.bids[0].price if depth.bids else "sin punta"
    best_ask = depth.asks[0].price if depth.asks else "sin punta"
    return f"{depth.symbol} bids={len(depth.bids)} asks={len(depth.asks)} bid={best_bid} ask={best_ask}"


def _asset(client: IOLClient) -> str:
    asset = client.get_asset("GGAL", Markets.BCBA)
    return (
        f"{asset.symbol} {asset.asset_type} {asset.currency} "
        f"plazo_default={asset.default_settlement_term} "
        f"lote={asset.trading_info.lot_size}"
    )


def _asset_types(client: IOLClient) -> str:
    types = client.get_asset_types("AR")
    names = ", ".join(sorted(item.id for item in types)[:6])
    return f"{len(types)} tipos: {names}"


def _screener(client: IOLClient) -> str:
    types = client.get_asset_types("AR")
    asset_type = types[0].id if types else "acciones"
    panels = client.get_asset_panels(asset_type, "AR")
    if not panels:
        return f"asset_type={asset_type} sin paneles disponibles"
    panel = panels[0].id
    entries = client.get_screener_quotes(asset_type, panel, "AR", SettlementTerms.T0)
    first = entries[0] if entries else None
    detail = f"{len(entries)} filas (asset_type={asset_type}, panel={panel})"
    if first is not None:
        detail += f"; primera={first.instrument.symbol} ultimo={first.quotes.last}"
    return detail


def _options(client: IOLClient) -> str:
    options = client.get_option_chain("GGAL", Markets.BCBA)
    if not options:
        return "sin opciones listadas para GGAL"
    first = options[0]
    return f"{len(options)} opciones; primera={first.symbol} strike={first.option.strike_price}"


def _bars(client: IOLClient) -> str:
    end = date.today()
    start = end - timedelta(days=10)
    bars = client.get_historical_bars(
        "GGAL",
        f"{start.isoformat()} 00:00:00",
        f"{end.isoformat()} 23:59:59",
        Markets.BCBA,
    )
    return f"{bars.symbol} total_bars={bars.total_bars}"


def _repo_terms(client: IOLClient) -> str:
    terms = client.get_repo_terms("ARS")
    if not terms:
        return "sin plazos de caucion"
    quotes = client.get_repo_quotes(terms[0].term_id, "ARS")
    return f"{len(terms)} plazos; quotes del plazo {terms[0].term_id}: {len(quotes)}"


def _balances(client: IOLClient) -> str:
    balances = client.get_account_balances("AR")
    return (
        f"ARS total T0={balances.ars.totals.t0} disponible={balances.ars.available.t0} "
        f"| USD total T0={balances.usd.totals.t0}"
    )


def _positions(client: IOLClient) -> str:
    portfolio = client.get_positions("AR")
    detail = (
        f"{portfolio.positions_count} posiciones "
        f"valor_total={portfolio.total_market_value} {portfolio.currency}"
    )
    if portfolio.positions:
        first = portfolio.positions[0]
        detail += f"; primera={first.instrument.symbol} qty={first.quantity}"
    return detail


def _history(client: IOLClient) -> str:
    end = date.today()
    start = end - timedelta(days=30)
    history = client.get_portfolio_history(start.isoformat(), end.isoformat(), "AR")
    return (
        f"status={history.status} puntos={len(history.history)} "
        f"faltantes={len(history.missing_dates)}"
    )


def _activities(client: IOLClient) -> str:
    end = date.today()
    start = end - timedelta(days=7)
    activities = client.get_account_activities(start.isoformat(), end.isoformat())
    detail = f"{len(activities)} movimientos en 7 dias"
    if activities:
        detail += f"; ultimo={activities[0].activity_type} {activities[0].status}"
    return detail


def _operations(client: IOLClient) -> str:
    end = date.today()
    start = end - timedelta(days=7)
    operations = client.get_trading_operations(start.isoformat(), end.isoformat())
    detail = f"{len(operations)} operaciones en 7 dias"
    if operations:
        detail += f"; ultima={operations[0].symbol} {operations[0].status}"
    return detail


def _watchlists(client: IOLClient) -> str:
    watchlists = client.get_watchlists()
    if not watchlists:
        return "sin watchlists en la cuenta"
    return f"{len(watchlists)} watchlists; primera id={watchlists[0].id} items={watchlists[0].items_count}"


REST_STEPS: list[tuple[str, Callable[[IOLClient], str]]] = [
    (
        "health",
        lambda client: (lambda health: f"{health.status} v{health.version} uptime={health.uptime}")(
            client.get_health_status()
        ),
    ),
    (
        "login OAuth2",
        lambda client: (lambda token: f"token obtenido ({len(token)} caracteres)")(
            client.get_access_token()
        ),
    ),
    (
        "test_authentication",
        lambda client: "acepta la sesion" if client.test_authentication() else "rechaza la sesion",
    ),
    ("quote GGAL", _quote),
    ("depth GGAL", _depth),
    ("asset GGAL", _asset),
    ("asset types", _asset_types),
    ("screener", _screener),
    ("option chain GGAL", _options),
    ("historical bars GGAL", _bars),
    ("repos terms + quotes", _repo_terms),
    ("balances AR", _balances),
    ("positions AR", _positions),
    ("portfolio history 30d", _history),
    ("activities 7d", _activities),
    ("trading operations 7d", _operations),
    ("watchlists", _watchlists),
]


async def _stream_check(username: str, password: str, seconds: float) -> str:
    """Verifica handshake y suscripcion del WebSocket, sin esperar al mercado."""
    from pyIol2 import IOLStreamClient

    received = 0
    async with IOLStreamClient(username, password) as stream:
        iterator = stream.subscribe(["GGAL"], quotes=True, trades=True)
        try:
            while received < 3:
                message: StreamMessage = await asyncio.wait_for(anext(iterator), timeout=seconds)
                received += 1
                print(
                    f"       mensaje type={message.type} {message.symbol} "
                    f"{message.market} {message.term}"
                )
        except (TimeoutError, StopAsyncIteration):
            pass
        finally:
            await iterator.aclose()
    detail = "auth y subscribe OK"
    detail += (
        f"; {received} mensajes en {seconds:.0f}s"
        if received
        else (f"; 0 mensajes en {seconds:.0f}s (esperable con el mercado cerrado)")
    )
    return detail


def main() -> int:
    """Corre la prueba de humo y devuelve el codigo de salida."""
    parser = argparse.ArgumentParser(description="Prueba de humo (solo lectura) de pyIol2")
    parser.add_argument(
        "--with-stream",
        action="store_true",
        help="probar tambien el handshake del WebSocket de market data",
    )
    parser.add_argument(
        "--stream-timeout",
        type=float,
        default=10.0,
        help="segundos de espera por mensaje del WebSocket (default 10)",
    )
    args = parser.parse_args()

    load_dotenv()
    import os

    username = os.getenv("IOL_USERNAME")
    password = os.getenv("IOL_PASSWORD")
    if not username or not password:
        print("Falta IOL_USERNAME o IOL_PASSWORD en el entorno o en el .env")
        return 2

    results: list[Result] = []
    client = IOLClient(username, password)
    try:
        for name, step in REST_STEPS:
            try:
                detail = step(client)
            except IOLAPIError as exc:
                results.append(_report(name, False, _error_detail(exc)))
            except Exception as exc:  # noqa: BLE001 - queremos seguir con el resto
                results.append(_report(name, False, f"{type(exc).__name__}: {exc}"))
            else:
                results.append(_report(name, True, detail))
    finally:
        client.close()

    if args.with_stream:
        try:
            detail = asyncio.run(_stream_check(username, password, args.stream_timeout))
        except Exception as exc:  # noqa: BLE001 - se informa como paso fallido
            results.append(_report("stream GGAL", False, f"{type(exc).__name__}: {exc}"))
        else:
            results.append(_report("stream GGAL", True, detail))

    failed = [result for result in results if result[1] != "ok"]
    print()
    print(f"Resumen: {len(results) - len(failed)} OK, {len(failed)} con problemas")
    for name, _status, detail in failed:
        print(f"  - {name}: {detail}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
