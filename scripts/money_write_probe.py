#!/usr/bin/env python3
"""
Sonda de escrituras con dinero, disenada para no mover dinero.

Cubre los dos caminos de escritura que faltaban: cauciones (repos) y FCI. La
estrategia es distinta en cada uno, y en los dos el objetivo es ejercitar el
endpoint sin dejar una posicion abierta.

- **Cauciones**: la caución minima es de 100.000 ARS por plazo. Si el saldo
  disponible es menor, el alta se rechaza por fondos y no se mueve nada: eso es
  lo que se prueba. Si a pesar de todo el broker la acepta, se cancela al instante
  en un `finally`.
- **FCI**: solo se llaman los endpoints de validacion, que son de lectura. Una
  suscripcion real mueve plata a un fondo y la cancelacion depende de la ventana
  del dia; no se ejecuta sin `--allow-fci-write`, que esta sonda nunca pasa sola.

Uso:
    uv run python scripts/money_write_probe.py            # solo lectura: estimaciones y validaciones
    uv run python scripts/money_write_probe.py --yes      # agrega el alta de caucion y el cancel de prueba
    uv run python scripts/money_write_probe.py --yes --allow-fci-write   # NO recomendado sin leer el README
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from pyIol2 import IOLAPIError, IOLClient

FUND_SYMBOL = "IOLCAMA"
FUND_AMOUNT = 1000.0


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
    if exc.details:
        parts.append(f"details={exc.details!r}")
    return " | ".join(parts)


def _repos(client: IOLClient, yes: bool) -> bool:
    """Estima y, si se pide, intenta un alta que el saldo no puede pagar."""
    _say("== Cauciones ==")
    try:
        terms = client.get_repo_terms("ARS")
    except IOLAPIError as exc:
        _say(f"  terms FALLA: {_error(exc)}")
        return False
    if not terms:
        _say("  sin plazos")
        return False

    term = terms[0]
    saldo = client.get_account_balances("AR").ars.available.t0
    minimo = float(term.min_amount or 0)
    _say(f"  term {term.term_id} ({term.term_days}d): min={minimo} max={term.max_amount}")
    _say(f"  saldo disponible: {saldo} ARS")
    _say(f"  el alta se puede probar sin riesgo: {saldo < minimo} (saldo < minimo)")

    try:
        estimaciones = client.estimate_repo(minimo, term.term_id, currency="ARS")
        _say(f"  estimate: {len(estimaciones)} componentes")
        for est in estimaciones:
            _say(
                f"    importe={est.amount} comision={est.commission_type}"
                f"/{est.commission_currency} fee={est.fee_type} iva={est.vat_amount}"
            )
    except IOLAPIError as exc:
        _say(f"  estimate FALLA: {_error(exc)}")

    if not yes:
        _say("  (sin --yes no se intenta el alta)")
        return True

    creada = None
    ok = True
    try:
        resultado = client.create_repo(minimo, term.term_id, currency="ARS", price_type="market")
        creada = resultado.order_id
        _say(f"  create -> ACEPTADA order_id={creada} (inesperado: el saldo no alcanzaba)")
    except IOLAPIError as exc:
        _say(f"  create -> rechazada como se esperaba: {_error(exc)}")
    finally:
        if creada:
            try:
                cancelada = client.cancel_repo(creada)
                _say(
                    f"  cancel -> id={cancelada.order_id} cancelled={cancelada.cancelled} status={cancelada.status}"
                )
                ok = cancelada.cancelled
            except IOLAPIError as exc:
                _say(f"  CANCEL FALLO (revisar a mano id={creada}): {_error(exc)}")
                ok = False

    try:
        cliente = IOLClient(os.environ["IOL_USERNAME"], os.environ["IOL_PASSWORD"])
        try:
            cliente.cancel_repo("0")
            _say("  cancel de id inexistente -> aceptado (inesperado)")
        except IOLAPIError as exc:
            _say(f"  cancel de id inexistente -> error esperado: {_error(exc)}")
        finally:
            cliente.close()
    except OSError as exc:
        _say(f"  cancel de id inexistente -> no se pudo probar: {exc}")
    return ok


def _fci(client: IOLClient, allow_write: bool) -> bool:
    """Valida operaciones de FCI (lectura) y, solo con permiso, suscribe."""
    _say("== FCI ==")
    try:
        validacion = client.validate_fund_subscription(FUND_SYMBOL, FUND_AMOUNT)
        _say(f"  validate suscripcion {FUND_SYMBOL} {FUND_AMOUNT}: valid={validacion.valid}")
        for message in validacion.messages:
            _say(f"    mensaje {message.code}: {message.message}")
    except IOLAPIError as exc:
        _say(f"  validate suscripcion FALLA: {_error(exc)}")

    try:
        rescate = client.validate_fund_redemption(FUND_SYMBOL, quantity=1)
        _say(f"  validate rescate {FUND_SYMBOL} qty 1: valid={rescate.valid}")
        for message in rescate.messages:
            _say(f"    mensaje {message.code}: {message.message}")
    except IOLAPIError as exc:
        _say(f"  validate rescate FALLA: {_error(exc)}")

    if not allow_write:
        _say("  (suscripcion y rescate NO se ejecutan: moverian plata a un fondo)")
        _say("  (se habilitan con --allow-fci-write, solo con un simbolo verificado)")
        return True

    _say("  ADVERTENCIA: ejecutando suscripcion real")
    transaccion = None
    try:
        resultado = client.subscribe_fund(FUND_SYMBOL, FUND_AMOUNT)
        transaccion = resultado.transaction_id
        _say(f"  subscribe -> ok={resultado.successful} transaccion={transaccion}")
    except IOLAPIError as exc:
        _say(f"  subscribe -> rechazada: {_error(exc)}")
        return True
    finally:
        if transaccion:
            try:
                cancelada = client.cancel_fund_operation(transaccion)
                _say(
                    f"  cancel -> id={cancelada.transaction_id} "
                    f"cancelled={cancelada.cancelled} status={cancelada.status}"
                )
            except IOLAPIError as exc:
                _say(f"  CANCEL FALLO (revisar a mano transaccion={transaccion}): {_error(exc)}")
    return True


def main() -> int:
    """Corre la sonda y devuelve el codigo de salida."""
    parser = argparse.ArgumentParser(
        description="Escrituras con dinero, sin dejar posiciones abiertas"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="intentar el alta de caucion (rechazo esperado por saldo) y el cancel de un id inexistente",
    )
    parser.add_argument(
        "--allow-fci-write",
        action="store_true",
        help="ejecutar suscripcion real de FCI; solo con un simbolo verificado y asumiendo el riesgo",
    )
    args = parser.parse_args()

    load_dotenv()
    username = os.getenv("IOL_USERNAME")
    password = os.getenv("IOL_PASSWORD")
    if not username or not password:
        _say("Falta IOL_USERNAME o IOL_PASSWORD en el entorno o en el .env")
        return 2

    resultados: list[tuple[str, bool]] = []
    with IOLClient(username, password) as client:
        resultados.append(("cauciones", _repos(client, args.yes)))
        resultados.append(("FCI", _fci(client, args.allow_fci_write)))

    _say("")
    fallidos = [nombre for nombre, ok in resultados if not ok]
    _say(f"Resumen: {len(resultados) - len(fallidos)} OK, {len(fallidos)} con problemas")
    for nombre in fallidos:
        _say(f"  - {nombre}")
    return 0 if not fallidos else 1


if __name__ == "__main__":
    sys.exit(main())
