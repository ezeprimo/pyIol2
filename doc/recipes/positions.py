"""Saldos, posiciones e historial de patrimonio. Solo lectura."""

import os
from datetime import datetime, timedelta

from pyIol2 import Countries, IOLAPIError, IOLClient


def main() -> None:
    username = os.environ["IOL_USERNAME"]
    password = os.environ["IOL_PASSWORD"]

    hasta = datetime.now()
    start_date = (hasta - timedelta(days=30)).strftime("%Y-%m-%d")
    end_date = hasta.strftime("%Y-%m-%d")

    try:
        with IOLClient(username, password) as client:
            # Saldos por moneda y por plazo de liquidacion.
            saldos = client.get_account_balances(Countries.ARGENTINA)
            print(f"ARS disponible T0: {saldos.ars.available.t0}")
            print(f"ARS a retirar:     {saldos.ars.available_for_withdrawal}")
            print(f"USD disponible T0: {saldos.usd.available.t0}")

            # Posiciones valuadas en pesos.
            cartera = client.get_positions(Countries.ARGENTINA, valuation_currency="ARS")
            print(f"\nCartera {cartera.account}: {cartera.positions_count} posiciones")
            print(f"Valor de mercado: {cartera.total_market_value} {cartera.currency}")
            for posicion in cartera.positions:
                print(
                    f"  {posicion.instrument.symbol}: "
                    f"{posicion.quantity} x {posicion.market_value.current_price} "
                    f"({posicion.profit_loss.unrealized_pl_percent}%)"
                )

            # Evolucion diaria del patrimonio. Si status es "partial",
            # missing_dates dice que dias no informo la API.
            historial = client.get_portfolio_history(start_date, end_date)
            print(f"\nHistorial: {historial.status}")
            for punto in historial.history:
                print(f"  {punto.date}: ARS {punto.equity.ars} / USD CCL {punto.equity.usd_ccl}")
            if historial.missing_dates:
                print(f"  dias faltantes: {', '.join(historial.missing_dates)}")
    except KeyError as exc:
        raise SystemExit(f"Falta la variable de entorno {exc}") from exc
    except IOLAPIError as exc:
        raise SystemExit(f"Fallo la consulta a IOL: {exc}") from exc


if __name__ == "__main__":
    main()
