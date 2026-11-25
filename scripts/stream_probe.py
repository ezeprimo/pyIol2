#!/usr/bin/env python3
"""
Sonda de market data en vivo: WebSocket y REST de solo lectura.

No crea ordenes ni operaciones: sirve para verificar el flujo real de puntas,
profundidad y operaciones, y para comparar lo que devuelve el REST.

Uso:
    uv run python scripts/stream_probe.py                    # 15 mensajes o 25s
    uv run python scripts/stream_probe.py --messages 40 --timeout 60
    uv run python scripts/stream_probe.py --symbols GGAL YPFD AL30
"""

import argparse
import asyncio
import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv

from pyIol2 import IOLAPIError, IOLClient, IOLStreamClient, Markets, SettlementTerms


def _say(text: str) -> None:
    """Imprime sin poder romper el flujo."""
    try:
        print(text)
    except Exception:  # noqa: BLE001 - la salida nunca debe abortar la sonda
        pass


def _rest(client: IOLClient, symbols: list[str]) -> None:
    """Foto del REST para comparar contra el WebSocket."""
    _say("== REST (para comparar) ==")
    for symbol in symbols:
        try:
            quote = client.get_market_quote(symbol, Markets.BCBA, SettlementTerms.T1)
        except IOLAPIError as exc:
            _say(f"  {symbol}: quote FALLA {exc.status_code} {exc.message}")
            continue
        _say(
            f"  {symbol}: ultimo={quote.prices.current} variacion={quote.change.percent}% "
            f"volumen={quote.volume.shares} actualizado={quote.last_updated}"
        )

    try:
        depth = client.get_market_depth(symbols[0], Markets.BCBA, SettlementTerms.T1)
        _say(
            f"  depth {symbols[0]}: bids={len(depth.bids)} asks={len(depth.asks)} "
            f"mejor_bid={depth.bids[0].price if depth.bids else '-'} "
            f"mejor_ask={depth.asks[0].price if depth.asks else '-'}"
        )
    except IOLAPIError as exc:
        _say(f"  depth {symbols[0]}: FALLA {exc.status_code} {exc.message}")


def _repos(client: IOLClient) -> None:
    """Cauciones: verifica si el libro existe con el mercado abierto."""
    _say("== Cauciones (ARS) ==")
    try:
        terms = client.get_repo_terms("ARS")
    except IOLAPIError as exc:
        _say(f"  terms FALLA {exc.status_code} {exc.message}")
        return
    _say(f"  plazos: {len(terms)}")
    con_libro = 0
    for term in terms[:12]:
        try:
            quotes = client.get_repo_quotes(term.term_id, "ARS")
        except IOLAPIError as exc:
            _say(f"  term {term.term_id}: FALLA {exc.status_code} {exc.message}")
            continue
        if quotes:
            con_libro += 1
            _say(
                f"  term {term.term_id} ({term.term_days}d): {len(quotes)} ofertas "
                f"bid={quotes[0].bid.rate} ask={quotes[0].ask.rate}"
            )
    _say(f"  plazos con libro en la muestra: {con_libro}")


def _bars(client: IOLClient, symbol: str) -> None:
    """Velas del dia, para ver si el historico ya trae la rueda en curso."""
    end = date.today()
    start = end - timedelta(days=2)
    try:
        bars = client.get_historical_bars(
            symbol, f"{start.isoformat()} 00:00:00", f"{end.isoformat()} 23:59:59", Markets.BCBA
        )
    except IOLAPIError as exc:
        _say(f"  bars {symbol}: FALLA {exc.status_code} {exc.message}")
        return
    ultima = bars.bars[-1] if bars.bars else None
    _say(
        f"  bars {symbol}: total={bars.total_bars}"
        + (f" ultima={ultima.datetime} close={ultima.close}" if ultima else "")
    )


async def _stream(symbols: list[str], messages: int, timeout: float) -> int:
    """Consume el WebSocket y devuelve cuantos mensajes llego a contar."""
    recibidos = 0
    por_tipo: dict[str, int] = {}

    async with IOLStreamClient(token=await _token()) as stream:
        iterator = stream.subscribe(
            symbols, market=Markets.BCBA, term=SettlementTerms.T1, quotes=True, trades=True
        )
        try:
            while recibidos < messages:
                message = await asyncio.wait_for(anext(iterator), timeout=timeout)
                recibidos += 1
                por_tipo[message.type] = por_tipo.get(message.type, 0) + 1
                if message.quote is not None:
                    bid = message.quote.bid
                    offer = message.quote.offer
                    _say(
                        f"  [Q] {message.symbol} bid={bid.price if bid else '-'}"
                        f"x{bid.size if bid else '-'} "
                        f"ask={offer.price if offer else '-'}x{offer.size if offer else '-'} "
                        f"{message.quote.datetime[-8:]}"
                    )
                elif message.trade is not None:
                    trade = message.trade
                    _say(
                        f"  [T] {message.symbol} precio={trade.last_price} "
                        f"var={trade.change_percent}% acum_qty={trade.traded_quantity} "
                        f"operacion={trade.last_quantity}"
                    )
                else:
                    _say(f"  [{message.type}] {message.symbol or '(sin simbolo)'} {message.raw}")
        except (TimeoutError, StopAsyncIteration):
            _say(f"  (sin mas mensajes despues de {recibidos})")
        finally:
            await iterator.aclose()

    _say(f"  total={recibidos} por tipo={por_tipo}")
    return recibidos


async def _token() -> str:
    """Token OAuth para el WebSocket, via el cliente REST."""
    client = IOLClient(os.environ["IOL_USERNAME"], os.environ["IOL_PASSWORD"])
    try:
        return await asyncio.to_thread(client.get_access_token)
    finally:
        client.close()


async def _order_book(symbol: str, messages: int, timeout: float) -> None:
    """Profundidad por WebSocket: un solo titulo por conexion."""
    _say(f"== WebSocket: order_book {symbol} ==")
    recibidos = 0
    async with IOLStreamClient(token=await _token()) as stream:
        iterator = stream.subscribe(
            [symbol],
            market=Markets.BCBA,
            term=SettlementTerms.T1,
            quotes=False,
            trades=False,
            order_book=True,
        )
        try:
            while recibidos < messages:
                message = await asyncio.wait_for(anext(iterator), timeout=timeout)
                recibidos += 1
                book = message.order_book
                if book is None:
                    _say(f"  [{message.type}] {message.raw}")
                    continue
                lados = [
                    (level.side, level.position, level.price, level.size) for level in book.levels
                ]
                _say(f"  [B] {book.symbol} {book.datetime[-8:]}: {lados}")
        except (TimeoutError, StopAsyncIteration):
            _say(f"  (sin mas mensajes despues de {recibidos})")
        finally:
            await iterator.aclose()
    _say(f"  total={recibidos}")


def main() -> int:
    """Corre la sonda completa."""
    parser = argparse.ArgumentParser(description="Sonda de market data en vivo (solo lectura)")
    parser.add_argument("--symbols", nargs="+", default=["GGAL", "YPFD"])
    parser.add_argument("--messages", type=int, default=15)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--skip-stream", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    if not os.getenv("IOL_USERNAME") or not os.getenv("IOL_PASSWORD"):
        _say("Falta IOL_USERNAME o IOL_PASSWORD")
        return 2

    with IOLClient(os.environ["IOL_USERNAME"], os.environ["IOL_PASSWORD"]) as client:
        _rest(client, args.symbols)
        _bars(client, args.symbols[0])
        _repos(client)

    if args.skip_stream:
        return 0

    _say("== WebSocket: quotes + trades ==")
    recibidos = asyncio.run(_stream(args.symbols, args.messages, args.timeout))
    asyncio.run(_order_book(args.symbols[0], 3, args.timeout))

    return 0 if recibidos else 1


if __name__ == "__main__":
    sys.exit(main())
