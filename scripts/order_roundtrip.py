#!/usr/bin/env python3
"""
Round-trip de ordenes contra la API real de IOL: crear, verificar y cancelar.

Pensado para validar los caminos de escritura sin riesgo de ejecucion:

- Solo ordenes `limit`, con un colchon del 5% sobre el precio de referencia y
  la garantia de que el limite calculado nunca coincide con ese precio.
- Cantidad minima (1 nominal) y vencimiento hoy, para que no sobreviva la rueda.
- Toda orden creada se cancela en un bloque `finally`. El id se registra antes
  de cualquier log, y si el alta queda ambigua se reconcilia contra las
  operaciones del dia: nunca se reintenta un alta.
- Credenciales desde IOL_USERNAME / IOL_PASSWORD o el `.env` local; nunca se
  imprimen, tampoco el token.

Uso:
    uv run python scripts/order_roundtrip.py            # muestra el plan y sale
    uv run python scripts/order_roundtrip.py --yes      # ejecuta de verdad
"""

import argparse
import json
import math
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
# asi que no se puede usar un precio "imposible". Un 5% de desvio alcanza para
# probar el camino sin quedar expuesto, y se cancela de inmediato.
BUY_FACTOR = 0.95
SELL_FACTOR = 1.05
TICK = 0.01
# Estados en los que la orden ya no puede ejecutarse.
CLOSED_STATUSES = ("cancelled", "canceled", "finished", "rejected", "expired")


def _say(text: str) -> None:
    """
    Imprime sin poder romper el flujo.

    Un stdout cerrado no puede impedir que se cancelen ordenes reales.
    """
    try:
        print(text)
    except Exception:  # noqa: BLE001 - la salida nunca debe abortar la limpieza
        pass


def _describe(prefix: str, detail: Any) -> None:
    """Imprime una linea de traza."""
    _say(f"{prefix} {detail}")


def _error(exc: IOLAPIError) -> str:
    """Resume un error de la API sin exponer credenciales."""
    parts = [type(exc).__name__, str(exc.message)]
    if exc.status_code is not None:
        parts.append(f"status={exc.status_code}")
    if exc.code:
        parts.append(f"code={exc.code}")
    if exc.trace_id:
        parts.append(f"trace_id={exc.trace_id}")
    if exc.details:
        parts.append(f"details={exc.details!r}")
    return " | ".join(parts)


def _full_error(exc: IOLAPIError) -> str:
    """Error con el payload que devuelve la API, para diagnostico."""
    detail = _error(exc)
    if exc.payload:
        detail += f" | payload={json.dumps(exc.payload)[:400]}"
    return detail


def _price(client: IOLClient, symbol: str, market: str = MARKET) -> float:
    """Ultimo precio del activo, para calcular el limite."""
    quote = client.get_market_quote(symbol, market, SettlementTerms.T1)
    price = quote.prices.current or quote.prices.close or quote.prices.previous_close
    if not price:
        raise RuntimeError(f"{symbol} no tiene precio de referencia todavia")
    return float(price)


def _limit(last: float, factor: float, side: str) -> float:
    """
    Calcula un limite con colchon real.

    Redondear a dos decimales puede dejar el limite igual al precio de
    referencia en instrumentos baratos, o sea sin colchon: se fuerza al menos
    un tick de diferencia.

    Args:
        last: Precio de referencia
        factor: 0.95 para compra, 1.05 para venta
        side: `buy` o `sell`

    Returns:
        Precio limite, garantizado distinto de `last` y del lado correcto
    """
    if side == "buy":
        limit = math.floor(last * factor / TICK) * TICK
        if limit >= last:
            limit = math.floor((last - TICK) / TICK) * TICK
        if limit <= 0:
            raise RuntimeError(f"no hay precio valido para comprar {last}")
        return round(limit, 2)

    limit = math.ceil(last * factor / TICK) * TICK
    if limit <= last:
        limit = math.ceil((last + TICK) / TICK) * TICK
    return round(limit, 2)


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


def _open_orders(client: IOLClient, day: str) -> list[dict[str, Any]]:
    """Ordenes del dia que todavia pueden ejecutarse."""
    try:
        operations = client.get_trading_operations(day, day)
    except IOLAPIError as exc:
        _describe("[RECONCILE FALLA]", _error(exc))
        return []
    return [
        {
            "order_id": str(operation.order_id),
            "symbol": operation.symbol,
            "status": operation.status,
            "qty": operation.order.qty,
            "price": operation.order.price,
        }
        for operation in operations
        if str(operation.status).lower() not in CLOSED_STATUSES
    ]


def _find_order(client: IOLClient, order_id: str, day: str) -> dict[str, Any] | None:
    """Busca una orden del dia por id en las operaciones de trading."""
    try:
        operations = client.get_trading_operations(day, day)
    except IOLAPIError as exc:
        _describe("[VERIFY FALLA]", _error(exc))
        return None
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


def _reconcile(
    client: IOLClient,
    day: str,
    symbol: str,
    price: float,
    quantity: float,
    already: list[str],
) -> list[str]:
    """
    Busca ordenes que coincidan con un alta que quedo ambigua.

    Cuando el POST falla despues de que el broker lo acepto, el cliente no tiene
    el id. Se reconcilia contra las operaciones del dia en lugar de reintentar:
    el alta es incierta, no fallida.

    Returns:
        Ids de ordenes vivas que no estaban registradas
    """
    matches = [
        order["order_id"]
        for order in _open_orders(client, day)
        if order["symbol"] == symbol
        and abs(float(order["price"]) - float(price)) < TICK / 2
        and abs(float(order["qty"]) - float(quantity)) < TICK / 2
        and order["order_id"] not in already
    ]
    return matches


def _cancel(client: IOLClient, order_id: str, alive: list[str]) -> bool:
    """
    Cancela una orden.

    El id sale de la lista de vivas antes de imprimir nada, para que un stdout
    roto no deje una orden creada sin cancelar.

    Returns:
        True si quedo cancelada
    """
    if order_id in alive:
        alive.remove(order_id)
    try:
        result = client.cancel_order(order_id)
    except IOLAPIError as exc:
        _describe("[CANCEL FALLA]", f"{order_id}: {_full_error(exc)}")
        alive.append(order_id)
        return False
    _describe("[CANCEL]", f"{result.order_id} cancelled={result.cancelled} status={result.status}")
    if not result.cancelled:
        alive.append(order_id)
        return False
    return True


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
        _say("Falta IOL_USERNAME o IOL_PASSWORD en el entorno o en el .env")
        return 2

    day = date.today().isoformat()
    alive: list[str] = []
    problems: list[str] = []

    with IOLClient(username, password) as client:
        sell_symbol, sell_market = SELL_SYMBOL, MARKET
        if args.sell_held:
            sell_symbol, sell_market = _pick_held(client)

        buy_reference = _price(client, BUY_SYMBOL)
        sell_reference = _price(client, sell_symbol, sell_market)
        buy_limit = _limit(buy_reference, BUY_FACTOR, "buy")
        sell_limit = _limit(sell_reference, SELL_FACTOR, "sell")

        # Sin colchon real no se manda nada: es la unica garantia de no ejecucion.
        if buy_limit >= buy_reference or sell_limit <= sell_reference:
            _say("FALLA: los limites calculados no tienen colchon; no se manda nada")
            return 2

        _say("Plan (limite con 5% de desvio, cancelacion inmediata):")
        _say(f"  compra {QUANTITY:g} {BUY_SYMBOL} limit@{buy_limit} (referencia {buy_reference})")
        _say(
            f"  venta  {QUANTITY:g} {sell_symbol} limit@{sell_limit} "
            f"(referencia {sell_reference}, mercado {sell_market})"
        )
        _say(f"  vencimiento {day}, plazo por defecto del activo")
        _say("")

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
            _say("")
            _say("Sin --yes no se manda nada. Repetir con --yes para ejecutar.")
            return 0

        try:
            for symbol, side, market, limit in (
                (BUY_SYMBOL, "buy", MARKET, buy_limit),
                (sell_symbol, "sell", sell_market, sell_limit),
            ):
                label = "[BUY]" if side == "buy" else "[SELL]"
                try:
                    result = client.create_order(
                        symbol,
                        side,
                        quantity=QUANTITY,
                        market_id=market,
                        order_type="limit",
                        limit_price=limit,
                        due_date=day,
                    )
                except IOLAPIError as exc:
                    _describe(f"{label} RECHAZADA", _full_error(exc))
                    # El alta es incierta: puede haberse aceptado y fallado la
                    # respuesta. Se reconcilia en lugar de reintentar.
                    recovered = _reconcile(client, day, symbol, limit, QUANTITY, alive)
                    for order_id in recovered:
                        _describe("[RECONCILIADA]", f"{order_id} aparece viva en la cuenta")
                        alive.append(order_id)
                    continue

                # El id se registra antes de cualquier log: si imprimir falla, la
                # limpieza igual lo conoce.
                if result.order_id:
                    alive.append(str(result.order_id))
                _describe(
                    label,
                    f"order_id={result.order_id} ok={result.successful_purchase} "
                    f"mensajes={[(m.code, m.message) for m in result.messages]}",
                )
                if not result.order_id:
                    problems.append(f"{symbol} {side}: la API no devolvio order_id")

            _say("")
            _say("Estado en la cuenta:")
            for order_id in list(alive):
                found = _find_order(client, order_id, day)
                if found is None:
                    problems.append(f"{order_id} no aparece en las operaciones del dia")
                    _describe("[VERIFY]", f"{order_id} no aparece")
                else:
                    _describe("[VERIFY]", found)
        finally:
            _say("")
            _say("Cancelando todo lo que quedo vivo:")
            for order_id in list(alive):
                _cancel(client, order_id, alive)
            if alive:
                problems.append(f"quedaron sin cancelar: {alive}")

        _say("")
        if alive:
            _say(f"FALLA: quedaron ordenes vivas: {alive}")
            return 1

        _say("Estado final:")
        _say("  (sin ordenes vivas)")

    if problems:
        _say("")
        _say(f"FALLA: {len(problems)} problema(s) en la verificacion")
        for problem in problems:
            _say(f"  - {problem}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
