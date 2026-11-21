"""Streaming de market data con un tope de mensajes. Solo lectura."""

import asyncio
import os

from pyIol2 import IOLAPIError, IOLStreamClient, Markets, SettlementTerms

MAX_MENSAJES = 10


async def main() -> None:
    username = os.environ["IOL_USERNAME"]
    password = os.environ["IOL_PASSWORD"]
    symbol = os.getenv("IOL_SYMBOL", "GGAL")
    recibidos = 0

    # El cliente se autentica, se suscribe y mantiene el heartbeat solo.
    async with IOLStreamClient(username, password) as stream:
        async for mensaje in stream.subscribe(
            [symbol],
            market=Markets.BCBA,
            term=SettlementTerms.T0,
            quotes=True,
            trades=True,
        ):
            print(f"{mensaje.type} {mensaje.symbol} {mensaje.market} {mensaje.term}")
            if mensaje.quote is not None:
                for nivel in mensaje.quote.levels:
                    print(f"  {nivel.side} {nivel.price} x {nivel.size}")
            if mensaje.trade is not None:
                print(f"  ultimo {mensaje.trade.last_price} ({mensaje.trade.change_percent}%)")

            # Sin este corte el async for espera mensajes para siempre.
            recibidos += 1
            if recibidos >= MAX_MENSAJES:
                print(f"Corte a los {MAX_MENSAJES} mensajes")
                break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyError as exc:
        raise SystemExit(f"Falta la variable de entorno {exc}") from exc
    except (IOLAPIError, KeyboardInterrupt) as exc:
        raise SystemExit(f"Streaming interrumpido: {exc}") from exc
