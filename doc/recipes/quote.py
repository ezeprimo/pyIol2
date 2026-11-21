"""Cotizacion de mercado y profundidad del libro. Solo lectura."""

import os

from pyIol2 import IOLAPIError, IOLClient, Markets, SettlementTerms


def main() -> None:
    # El simbolo se puede cambiar por entorno; el resto se toma de las constantes.
    symbol = os.getenv("IOL_SYMBOL", "GGAL")
    username = os.environ["IOL_USERNAME"]
    password = os.environ["IOL_PASSWORD"]

    try:
        with IOLClient(username, password) as client:
            # Cotizacion de punta: ultimo precio, variacion y volumen.
            cotizacion = client.get_market_quote(
                symbol,
                market=Markets.BCBA,
                term=SettlementTerms.T0,
            )
            print(f"{cotizacion.symbol} {cotizacion.market} {cotizacion.settlement_term}")
            print(f"  ultimo: {cotizacion.prices.current} {cotizacion.currency}")
            print(f"  variacion: {cotizacion.change.percent}%")
            print(f"  volumen: {cotizacion.volume.shares} nominales")

            # Profundidad del libro: 5 mejores puntas de cada lado.
            libro = client.get_market_depth(symbol)
            for nivel in libro.bids:
                print(f"  compra {nivel.position}: {nivel.price} x {nivel.size}")
            for nivel in libro.asks:
                print(f"  venta  {nivel.position}: {nivel.price} x {nivel.size}")
    except KeyError as exc:
        raise SystemExit(f"Falta la variable de entorno {exc}") from exc
    except IOLAPIError as exc:
        raise SystemExit(f"Fallo la consulta a IOL: {exc}") from exc


if __name__ == "__main__":
    main()
