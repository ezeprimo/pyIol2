#!/usr/bin/env python3
"""
Prueba de escrituras inocuas contra la API real de IOL.

Cubre lo que los tests unitarios no pueden: los endpoints de escritura cuyo
efecto es cosmetico o reversible.

- Watchlists: crear, verificar, renombrar, agregar un item, verificarlo,
  quitarlo y borrar la lista. Solo opera sobre la lista que crea esta corrida:
  nunca toca las watchlists existentes de la cuenta.
- Estimaciones: `estimate_order` y `estimate_repo`, que son de solo lectura.

NO crea ordenes, cauciones ni operaciones de FCI: no mueve dinero.

Uso:
    uv run python scripts/safe_write_probe.py
    uv run python scripts/safe_write_probe.py --keep   # no borra la watchlist
"""

import argparse
import os
import sys
from datetime import date

from dotenv import load_dotenv

from pyIol2 import IOLAPIError, IOLClient, Markets, SettlementTerms

PREFIX = "pyIol2 probe"
SYMBOL = "GGAL"


def _say(text: str) -> None:
    """Imprime sin poder romper el flujo."""
    try:
        print(text)
    except Exception:  # noqa: BLE001 - la salida nunca debe abortar la limpieza
        pass


def _error(exc: IOLAPIError) -> str:
    """Resume un error sin exponer credenciales."""
    parts = [type(exc).__name__, str(exc.message)]
    if exc.status_code is not None:
        parts.append(f"status={exc.status_code}")
    if exc.code:
        parts.append(f"code={exc.code}")
    if exc.trace_id:
        parts.append(f"trace_id={exc.trace_id}")
    return " | ".join(parts)


def _watchlists(client: IOLClient, name: str, keep: bool) -> bool:
    """
    Ejercita el CRUD completo de watchlists.

    Returns:
        True si todos los pasos pasaron
    """
    _say("== Watchlists (CRUD completo) ==")
    creada = None
    ok = True

    existentes = {w.id for w in client.get_watchlists()}
    _say(f"  watchlists de la cuenta antes: {sorted(existentes)}")

    try:
        lista = client.create_watchlist(name)
        creada = lista.id
        _say(f"  create -> id={lista.id} nombre={lista.name!r} items={lista.items_count}")
        if not lista.id:
            _say("  FALLA: la API no devolvio id")
            return False

        leida = client.get_watchlist(creada, SettlementTerms.T1)
        _say(f"  get    -> id={leida.id} nombre={leida.name!r} items={leida.items_count}")
        ok = ok and leida.id == creada

        renombrada = client.rename_watchlist(creada, f"{name} renombrada")
        _say(f"  rename -> id={renombrada.id} nombre={renombrada.name!r} ok={renombrada.renamed}")
        ok = ok and renombrada.renamed

        agregado = client.add_watchlist_item(creada, SYMBOL, Markets.BCBA)
        _say(
            f"  add    -> {agregado.symbol} {agregado.market} "
            f"added={agregado.added} lista={agregado.watchlist_id}"
        )
        ok = ok and agregado.added

        con_item = client.get_watchlist(creada, SettlementTerms.T1)
        simbolos = [item.symbol for item in con_item.items]
        _say(f"  get    -> {con_item.items_count} items: {simbolos}")
        if SYMBOL not in simbolos:
            _say(f"  FALLA: {SYMBOL} no aparece despues del add")
            ok = False
        else:
            item = next(i for i in con_item.items if i.symbol == SYMBOL)
            _say(
                f"  quote  -> {SYMBOL} last={item.quote.last_price} "
                f"bid={item.quote.best_bid} ask={item.quote.best_ask}"
            )

        quitado = client.remove_watchlist_item(creada, SYMBOL, Markets.BCBA)
        _say(f"  remove -> {quitado.symbol} removed={quitado.removed}")
        ok = ok and quitado.removed

        sin_item = client.get_watchlist(creada, SettlementTerms.T1)
        _say(f"  get    -> {sin_item.items_count} items despues del remove")
        if sin_item.items_count != 0:
            _say("  FALLA: el item sigue estando")
            ok = False
    except IOLAPIError as exc:
        _say(f"  FALLA: {_error(exc)}")
        ok = False
    finally:
        if creada and not keep:
            try:
                borrada = client.delete_watchlist(creada)
                _say(f"  delete -> id={borrada.id} deleted={borrada.deleted}")
                ok = ok and borrada.deleted
            except IOLAPIError as exc:
                _say(f"  DELETE FALLA (revisar a mano id={creada}): {_error(exc)}")
                ok = False
        elif creada:
            _say(f"  (se conserva la watchlist {creada} por --keep)")

    despues = {w.id for w in client.get_watchlists()}
    _say(f"  watchlists de la cuenta despues: {sorted(despues)}")
    if not keep and creada and creada in despues:
        _say("  FALLA: la watchlist de prueba quedo viva")
        ok = False
    return ok


def _estimate_order(client: IOLClient) -> bool:
    """Estima una orden de compra: solo lectura, no crea nada."""
    _say("== estimate_order (solo lectura) ==")
    try:
        market = client.estimate_order(SYMBOL, "buy", quantity=1, order_type="market")
        _say(
            f"  market qty 1: importe={market.amount.value} {market.amount.currency} "
            f"comision={market.commission.value} iva={market.regulatory_fees.vat.value} "
            f"fee_mercado={market.regulatory_fees.market_fee.value}"
        )
    except IOLAPIError as exc:
        _say(f"  market FALLA: {_error(exc)}")
        return False

    try:
        quote = client.get_market_quote(SYMBOL, Markets.BCBA, SettlementTerms.T1)
        limite = round(quote.prices.current * 0.99, 2)
        limit = client.estimate_order(
            SYMBOL, "buy", quantity=1, order_type="limit", limit_price=limite
        )
        _say(f"  limit {limite}: importe={limit.amount.value} comision={limit.commission.value}")
    except IOLAPIError as exc:
        _say(f"  limit FALLA: {_error(exc)}")
        return False

    try:
        monto = client.estimate_order(SYMBOL, "buy", notional=5000, order_type="market")
        _say(
            f"  market notional 5000: importe={monto.amount.value} comision={monto.commission.value}"
        )
    except IOLAPIError as exc:
        _say(f"  notional FALLA: {_error(exc)}")
        return False
    return True


def _estimate_repo(client: IOLClient) -> bool:
    """Estima una caución: solo lectura, no crea nada."""
    _say("== estimate_repo (solo lectura) ==")
    try:
        terms = client.get_repo_terms("ARS")
    except IOLAPIError as exc:
        _say(f"  terms FALLA: {_error(exc)}")
        return False
    if not terms:
        _say("  sin plazos de caución")
        return False

    ok = True
    for term in terms[:2]:
        monto = max(float(term.min_amount or 0), 10000.0)
        try:
            estimaciones = client.estimate_repo(monto, term.term_id, currency="ARS")
        except IOLAPIError as exc:
            _say(f"  term {term.term_id} ({term.term_days}d, {monto}): FALLA {_error(exc)}")
            ok = False
            continue
        if not estimaciones:
            _say(f"  term {term.term_id} ({term.term_days}d, {monto}): sin estimaciones")
            continue
        for est in estimaciones:
            _say(
                f"  term {term.term_id} ({term.term_days}d, {monto}): importe={est.amount} "
                f"comision={est.commission_type}/{est.commission_currency} iva={est.vat_amount}"
            )
    return ok


def main() -> int:
    """Corre la sonda y devuelve el codigo de salida."""
    parser = argparse.ArgumentParser(description="Escrituras inocuas y estimaciones (IOL real)")
    parser.add_argument("--keep", action="store_true", help="no borrar la watchlist de prueba")
    args = parser.parse_args()

    load_dotenv()
    username = os.getenv("IOL_USERNAME")
    password = os.getenv("IOL_PASSWORD")
    if not username or not password:
        _say("Falta IOL_USERNAME o IOL_PASSWORD en el entorno o en el .env")
        return 2

    nombre = f"{PREFIX} {date.today().isoformat()}"
    resultados: list[tuple[str, bool]] = []

    with IOLClient(username, password) as client:
        resultados.append(("watchlists CRUD", _watchlists(client, nombre, args.keep)))
        resultados.append(("estimate_order", _estimate_order(client)))
        resultados.append(("estimate_repo", _estimate_repo(client)))

    _say("")
    fallidos = [nombre for nombre, ok in resultados if not ok]
    _say(f"Resumen: {len(resultados) - len(fallidos)} OK, {len(fallidos)} con problemas")
    for nombre in fallidos:
        _say(f"  - {nombre}")
    return 0 if not fallidos else 1


if __name__ == "__main__":
    sys.exit(main())
