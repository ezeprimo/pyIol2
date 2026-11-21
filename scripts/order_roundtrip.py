#!/usr/bin/env python3
"""
Round-trip de ordenes contra la API real de IOL: crear, verificar y cancelar.

Pensado para validar los caminos de escritura sin riesgo de ejecucion:

- Solo ordenes `limit` con precio imposible de cruzar: la compra muy por debajo
  del mercado y la venta muy por encima.
- Cantidad minima (1 nominal) y vencimiento hoy, para que no sobreviva la rueda.
- Toda orden creada se cancela en un bloque `finally`, aunque el resto falle.
- Credenciales desde IOL_USERNAME / IOL_PASSWORD o el `.env` local; nunca se
  imprimen, tampoco el token.

Uso:
    uv run python scripts/order_roundtrip.py            # muestra el plan y sale
    uv run python scripts/order_roundtrip.py --yes      # ejecuta de verdad
"""

import argparse
import json
import os
import sys
from datetime import date
from typing import Any

from dotenv import load_dotenv

from pyIol2 import IOLAPIError, IOLClient, Markets, SettlementTerms

# Compra: activo que no requiere tenencia previa.
BUY_SYMBOL = "COME"
# Venta: si no hay tenencia, la API tiene que rechazarla (tambien es una prueba).
SELL_SYMBOL = "KO"

MARKET = Markets.BCBA
QUANTITY = 1.0
# El broker rechaza limites fuera de la banda de precio (422 ORDER_REJECTED),
# asi que no se puede usar un precio "imposible". Se usa un 5% de desvio y se
# cancela de inmediato: alcanza para probar el camino sin quedar expuesto.
BUY_FACTOR = 0.95
SELL_FACTOR = 1.05


def _price(client: IOLClient, symbol: str, market: str = MARKET) -> float:
    """Ultimo precio del activo, para calcular el limite."""
    quote = client.get_market_quote(symbol, market, SettlementTerms.T1)
    price = quote.prices.current or quote.prices.close or quote.prices.previous_close
    if not price:
        raise RuntimeError(f"{symbol} no tiene precio de referencia todavia")
    return float(price)


def _pick_held(client: IOLClient) -> tuple[str, str]:
    """
    Elige el primer activo con tenencia suficiente para probar una venta.

    Returns:
        Tupla `(simbolo, mercado)`
    """
    portfolio = client.get_positions("AR")
    candidates = [
        position
        for position in portfolio.positions
        if position.quantity >= QUANTITY and position.instrument.tradable
    ]
    # Los CEDEARs cotizan contra el dolar: se prefieren instrumentos locales
    # para que el limite en pesos tenga sentido.
    candidates.sort(key=lambda position: "CEDEAR" in position.instrument.type.upper())
    if not candidates:
        raise RuntimeError("no hay posiciones con tenencia suficiente para probar la venta")
    chosen = candidates[0]
    return chosen.instrument.symbol, chosen.instrument.exchange or MARKET


def _describe(prefix: str, detail: Any) -> None:
    """Imprime una linea de traza."""
    print(f"{prefix} {detail}")


def _error(exc: IOLAPIError) -> str:
    """Resume un error de la API sin exponer credenciales."""
    parts = [type(exc).__name__, str(exc.message)]
    if exc.status_code is not None:
        parts.append(f"status={exc.status_code}")
    if exc.trace_id:
        parts.append(f"trace_id={exc.trace_id}")
    if exc.details:
        parts.append(f"details={exc.details!r}")
    return " | ".join(parts)


def _full_error(exc: IOLAPIError) -> str:
    """Error con el codigo y el detalle que devuelve la API."""
    detail = _error(exc)
    if exc.code:
        detail += f" | code={exc.code}"
    if exc.payload:
        detail += f" | payload={json.dumps(exc.payload)[:400]}"
    return detail


def _find_order(client: IOLClient, order_id: str, day: str) -> dict[str, Any] | None:
    """Busca una orden del dia por id en las operaciones de trading."""
    operations = client.get_trading_operations(day, day)
    for operation in operations:
        if str(operation.order_id) == str(order_id):
            return {
                "order_id": operation.order_id,
                "symbol": operation.symbol,
                "type": operation.type,
                "status": operation.status,
                "qty": operation.order.qty,
                "price": operation.order.price,
                "term": operation.term,
                "ticket": operation.ticket_id,
            }
    return None


def _cancel(client: IOLClient, order_id: str, created: list[str]) -> None:
    """Cancela una orden y deja la traza."""
    try:
        result = client.cancel_order(order_id)
    except IOLAPIError as exc:
        _describe("[CANCEL FALLA]", f"{order_id}: {_error(exc)}")
        return
    _describe(
        "[CANCEL]",
        f"{result.order_id} cancelled={result.cancelled} status={result.status}",
    )
    if result.cancelled and order_id in created:
        created.remove(order_id)


def main() -> int:
    """Ejecuta el round-trip y devuelve el codigo de salida."""
    parser = argparse.ArgumentParser(
        description="Round-trip de ordenes (crear, verificar, cancelar)"
    )
    parser.add_argument("--yes", action="store_true", help="ejecutar las ordenes de verdad")
    parser.add_argument(
        "--sell-held",
        action="store_true",
        help=f"vender un activo con tenencia en lugar de {SELL_SYMBOL}",
    )
    args = parser.parse_args()

    load_dotenv()
    username = os.getenv("IOL_USERNAME")
    password = os.getenv("IOL_PASSWORD")
    if not username or not password:
        print("Falta IOL_USERNAME o IOL_PASSWORD en el entorno o en el .env")
        return 2

    day = date.today().isoformat()
    created: list[str] = []

    with IOLClient(username, password) as client:
        sell_symbol, sell_market = SELL_SYMBOL, MARKET
        if args.sell_held:
            sell_symbol, sell_market = _pick_held(client)

        buy_price = _price(client, BUY_SYMBOL)
        sell_price = _price(client, sell_symbol, sell_market)
        buy_limit = round(buy_price * BUY_FACTOR, 2)
        sell_limit = round(sell_price * SELL_FACTOR, 2)

        print("Plan (limite con 5% de desvio, cancelacion inmediata):")
        print(f"  compra {QUANTITY:g} {BUY_SYMBOL} limit@{buy_limit} (ultimo {buy_price})")
        print(
            f"  venta  {QUANTITY:g} {sell_symbol} limit@{sell_limit} "
            f"(ultimo {sell_price}, mercado {sell_market})"
        )
        print(f"  vencimiento {day}, plazo por defecto del activo")
        print()

        try:
            estimate = client.estimate_order(
                BUY_SYMBOL,
                "buy",
                quantity=QUANTITY,
                market_id=MARKET,
                order_type="limit",
                limit_price=buy_limit,
                due_date=day,
            )
            _describe(
                "[ESTIMATE]",
                f"{BUY_SYMBOL}: importe={estimate.amount.value} {estimate.amount.currency} "
                f"comision={estimate.commission.value} iva={estimate.regulatory_fees.vat.value}",
            )
        except IOLAPIError as exc:
            _describe("[ESTIMATE FALLA]", _error(exc))

        if not args.yes:
            print()
            print("Sin --yes no se manda nada. Repetir con --yes para ejecutar.")
            return 0

        try:
            buy = client.create_order(
                BUY_SYMBOL,
                "buy",
                quantity=QUANTITY,
                market_id=MARKET,
                order_type="limit",
                limit_price=buy_limit,
                due_date=day,
            )
            _describe(
                "[BUY]",
                f"order_id={buy.order_id} ok={buy.successful_purchase} "
                f"mensajes={[(m.code, m.message) for m in buy.messages]}",
            )
            if buy.order_id:
                created.append(str(buy.order_id))

            try:
                sell = client.create_order(
                    sell_symbol,
                    "sell",
                    quantity=QUANTITY,
                    market_id=sell_market,
                    order_type="limit",
                    limit_price=sell_limit,
                    due_date=day,
                )
                _describe(
                    "[SELL]",
                    f"order_id={sell.order_id} ok={sell.successful_purchase} "
                    f"mensajes={[(m.code, m.message) for m in sell.messages]}",
                )
                if sell.order_id:
                    created.append(str(sell.order_id))
            except IOLAPIError as exc:
                _describe("[SELL RECHAZADA]", _full_error(exc))

            print()
            print("Estado en la cuenta:")
            for order_id in list(created):
                found = _find_order(client, order_id, day)
                _describe("[VERIFY]", found if found is not None else f"{order_id} no aparece")
        finally:
            print()
            print("Cancelando todo lo que quedo vivo:")
            for order_id in list(created):
                _cancel(client, order_id, created)
            if created:
                print(f"  ATENCION: quedaron sin cancelar: {created}")

        if created:
            print()
            print(f"FALLA: quedaron ordenes vivas: {created}")
            return 1

        print()
        print("Estado final:")
        for order_id in created or ["(sin ordenes vivas)"]:
            if order_id.startswith("("):
                print(f"  {order_id}")
                continue
            _describe("[FINAL]", _find_order(client, order_id, day))

    return 0


if __name__ == "__main__":
    sys.exit(main())
