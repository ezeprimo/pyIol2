"""Estimacion de costos de una orden. No envia nada y no tiene efectos."""

import os

from pyIol2 import IOLAPIError, IOLClient, Markets, SettlementTerms


def main() -> None:
    symbol = os.getenv("IOL_SYMBOL", "GGAL")
    # Se pide por nominales: cambiar a notional para estimar por monto.
    quantity = float(os.getenv("IOL_QUANTITY", "1"))
    username = os.environ["IOL_USERNAME"]
    password = os.environ["IOL_PASSWORD"]

    try:
        with IOLClient(username, password) as client:
            # estimate_order solo calcula: la orden no se crea.
            estimacion = client.estimate_order(
                symbol,
                "buy",
                quantity=quantity,
                market_id=Markets.BCBA,
                order_type="market",
                settlement_term=SettlementTerms.T0,
            )
            print(f"Estimacion de compra de {quantity} {symbol}")
            print(f"  importe:    {estimacion.amount.value} {estimacion.amount.currency}")
            print(f"  comision:   {estimacion.commission.value} {estimacion.commission.currency}")
            print(
                f"  derecho de mercado: {estimacion.regulatory_fees.market_fee.value} "
                f"{estimacion.regulatory_fees.market_fee.currency}"
            )
            print(
                f"  IVA: {estimacion.regulatory_fees.vat.value} "
                f"{estimacion.regulatory_fees.vat.currency}"
            )
    except KeyError as exc:
        raise SystemExit(f"Falta la variable de entorno {exc}") from exc
    except IOLAPIError as exc:
        raise SystemExit(f"Fallo la estimacion: {exc}") from exc


if __name__ == "__main__":
    main()
