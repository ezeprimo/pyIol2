#!/usr/bin/env python3
"""
Pruebas de estres del WebSocket contra el servidor real de IOL.

Cubre lo que el WebSocket falso de los tests no puede probar:

1. Reparto de mas de 50 simbolos en varias conexiones.
2. `unsubscribe` real: el servidor deja de mandar ese titulo.
3. `unsubscribe_all` real: deja de llegar todo.
4. Reconexion real: se inyecta un corte en la primera conexion y se verifica
   que el cliente reconecta, se reautentica y vuelve a suscribirse solo.

Solo lectura: no crea ordenes ni operaciones.

Uso:
    uv run python scripts/stream_stress_probe.py
    uv run python scripts/stream_stress_probe.py --only sharding
"""

import argparse
import asyncio
import os
import sys
from typing import Any

from dotenv import load_dotenv

from pyIol2 import IOLClient, IOLStreamClient, Markets, SettlementTerms
from pyIol2.stream import build_symbol_id

MAX_SYMBOLS = 50
SYMBOLS = ["GGAL", "YPFD"]


def _say(text: str) -> None:
    """Imprime sin poder romper el flujo."""
    try:
        print(text)
    except Exception:  # noqa: BLE001 - la salida nunca debe abortar la prueba
        pass


async def _token() -> str:
    """Token OAuth reutilizable para todas las conexiones."""
    client = IOLClient(os.environ["IOL_USERNAME"], os.environ["IOL_PASSWORD"])
    try:
        return await asyncio.to_thread(client.get_access_token)
    finally:
        client.close()


def _universe(limit: int) -> list[str]:
    """Toma simbolos reales del panel de acciones."""
    client = IOLClient(os.environ["IOL_USERNAME"], os.environ["IOL_PASSWORD"])
    try:
        rows = client.get_screener_quotes(
            "acciones", "argaccionespanelgeneral", "AR", SettlementTerms.T0
        )
    finally:
        client.close()
    return [row.instrument.symbol for row in rows[:limit]]


async def test_sharding(token: str) -> bool:
    """Mas de 50 simbolos deben repartirse en varias conexiones."""
    simbolos = _universe(60)
    _say(f"== 1. sharding: {len(simbolos)} simbolos ==")
    recibidos: set[str] = set()

    async with IOLStreamClient(token=token) as stream:
        iterator = stream.subscribe(
            simbolos, market=Markets.BCBA, term=SettlementTerms.T0, quotes=True, trades=True
        )
        try:
            while len(recibidos) < 3:
                message = await asyncio.wait_for(anext(iterator), timeout=25)
                if message.symbol:
                    recibidos.add(message.symbol)
        except (TimeoutError, StopAsyncIteration):
            pass
        conexiones = len(stream._connections)
        tamaños = [len(c.subscribed_ids()) for c in stream._connections]
        await iterator.aclose()

    esperadas = -(-len(simbolos) // MAX_SYMBOLS)
    _say(f"  conexiones={conexiones} (esperadas={esperadas}) simbolos por conexion={tamaños}")
    _say(f"  titulos con datos: {sorted(recibidos)}")
    ok = conexiones == esperadas and all(t <= MAX_SYMBOLS for t in tamaños) and bool(recibidos)
    _say(f"  -> {'OK' if ok else 'FALLA'}")
    return ok


async def test_unsubscribe(token: str) -> bool:
    """Despues de unsubscribe, ese titulo no debe seguir llegando."""
    _say("== 2. unsubscribe real ==")
    async with IOLStreamClient(token=token) as stream:
        iterator = stream.subscribe(
            SYMBOLS, market=Markets.BCBA, term=SettlementTerms.T0, quotes=True, trades=True
        )
        primero = await asyncio.wait_for(anext(iterator), timeout=25)
        _say(f"  primer mensaje: {primero.type} {primero.symbol}")

        bajas = await stream.unsubscribe(["YPFD"], market=Markets.BCBA, term=SettlementTerms.T0)
        _say(f"  unsubscribe devolvio: {bajas}")
        esperado = build_symbol_id("YPFD", Markets.BCBA, SettlementTerms.T0)
        if esperado not in bajas:
            _say("  FALLA: no reporto la baja de YPFD")
            await iterator.aclose()
            return False

        # Gracia: algun mensaje en vuelo puede llegar igual.
        await asyncio.sleep(1.0)
        posteriores = 0
        solo_ggal = True
        try:
            while posteriores < 8:
                message = await asyncio.wait_for(anext(iterator), timeout=15)
                posteriores += 1
                if message.symbol == "YPFD":
                    solo_ggal = False
                _say(f"  post-baja: {message.type} {message.symbol}")
        except (TimeoutError, StopAsyncIteration):
            pass
        await iterator.aclose()

    _say(f"  mensajes post-baja={posteriores} solo_ggal={solo_ggal}")
    ok = solo_ggal and posteriores > 0
    _say(f"  -> {'OK' if ok else 'FALLA'}")
    return ok


async def test_unsubscribe_all(token: str) -> bool:
    """Despues de unsubscribe_all no debe llegar ningun dato."""
    _say("== 3. unsubscribe_all real ==")
    async with IOLStreamClient(token=token) as stream:
        iterator = stream.subscribe(
            SYMBOLS, market=Markets.BCBA, term=SettlementTerms.T0, quotes=True, trades=True
        )
        primero = await asyncio.wait_for(anext(iterator), timeout=25)
        _say(f"  primer mensaje: {primero.type} {primero.symbol}")

        await stream.unsubscribe_all()
        _say("  unsubscribe_all enviado")
        await asyncio.sleep(1.0)

        posteriores = 0
        try:
            while True:
                message = await asyncio.wait_for(anext(iterator), timeout=8)
                posteriores += 1
                if posteriores <= 5:
                    _say(f"  post-baja: {message.type} {message.symbol}")
        except (TimeoutError, StopAsyncIteration):
            pass
        await iterator.aclose()

    _say(f"  mensajes post-baja={posteriores}")
    ok = posteriores == 0
    _say(f"  -> {'OK' if ok else 'FALLA'}")
    return ok


class _DroppingSocket:
    """Envuelve una conexion real y la corta despues de N mensajes."""

    def __init__(self, websocket: Any, drop_after: int):
        self._ws = websocket
        self._drop_after = drop_after
        self._count = 0

    async def send(self, data: str) -> None:
        await self._ws.send(data)

    async def recv(self) -> str:
        return await self._ws.recv()

    async def _messages(self) -> Any:
        """Itera la conexion real y corta despues de N mensajes de datos."""
        while True:
            self._count += 1
            if self._count > self._drop_after:
                raise ConnectionError("corte inyectado por la prueba")
            yield await self._ws.recv()

    def __aiter__(self) -> Any:
        # `websockets` implementa `__aiter__` como corrutina y no expone
        # `__anext__`, asi que se delega con un generador asincrono propio.
        return self._messages()


class _DroppingConnect:
    """Context manager que entrega la conexion real envuelta una sola vez."""

    def __init__(self, connect: Any, url: str, kwargs: dict[str, Any], drop_after: int):
        self._cm = connect(url, **kwargs)
        self._drop_after = drop_after
        self._ws = None

    async def __aenter__(self) -> _DroppingSocket:
        self._ws = await self._cm.__aenter__()
        return _DroppingSocket(self._ws, self._drop_after)

    async def __aexit__(self, *exc: Any) -> None:
        await self._cm.__aexit__(*exc)


async def test_reconnect(token: str) -> bool:
    """Un corte debe producir reconexion, reautenticacion y resuscripcion."""
    from websockets.asyncio.client import connect as real_connect

    _say("== 4. reconexion real (corte inyectado) ==")
    intentos = {"n": 0}

    def factory(url: str, **kwargs: Any) -> Any:
        intentos["n"] += 1
        if intentos["n"] == 1:
            _say("  conexion 1: se corta despues de 2 mensajes")
            return _DroppingConnect(real_connect, url, kwargs, drop_after=2)
        _say(f"  conexion {intentos['n']}: nueva conexion real")
        return real_connect(url, **kwargs)

    stream = IOLStreamClient(token=token, connect_factory=factory)
    recibidos = 0
    async with stream:
        iterator = stream.subscribe(
            ["GGAL"], market=Markets.BCBA, term=SettlementTerms.T0, quotes=True, trades=True
        )
        try:
            while recibidos < 5:
                message = await asyncio.wait_for(anext(iterator), timeout=30)
                recibidos += 1
                _say(f"  mensaje {recibidos}: {message.type} {message.symbol}")
        except (TimeoutError, StopAsyncIteration):
            pass
        await iterator.aclose()

    _say(f"  conexiones abiertas={intentos['n']} mensajes={recibidos}")
    ok = intentos["n"] >= 2 and recibidos >= 5
    _say(f"  -> {'OK' if ok else 'FALLA'}")
    return ok


async def run(only: str | None) -> int:
    """Corre las pruebas y devuelve el codigo de salida."""
    token = await _token()
    pruebas = {
        "sharding": test_sharding,
        "unsubscribe": test_unsubscribe,
        "unsubscribe_all": test_unsubscribe_all,
        "reconnect": test_reconnect,
    }
    elegidas = {only: pruebas[only]} if only else pruebas

    resultados: list[tuple[str, bool]] = []
    for nombre, prueba in elegidas.items():
        try:
            resultados.append((nombre, await prueba(token)))
        except Exception as exc:  # noqa: BLE001 - se informa como prueba fallida
            _say(f"  EXCEPCION {type(exc).__name__}: {exc}")
            resultados.append((nombre, False))
        _say("")

    fallidas = [nombre for nombre, ok in resultados if not ok]
    _say(f"Resumen: {len(resultados) - len(fallidas)} OK, {len(fallidas)} con problemas")
    for nombre in fallidas:
        _say(f"  - {nombre}")
    return 0 if not fallidas else 1


def main() -> int:
    """Punto de entrada."""
    parser = argparse.ArgumentParser(description="Estres del WebSocket de IOL (solo lectura)")
    parser.add_argument(
        "--only",
        choices=["sharding", "unsubscribe", "unsubscribe_all", "reconnect"],
        help="correr solo una prueba",
    )
    args = parser.parse_args()

    load_dotenv()
    if not os.getenv("IOL_USERNAME") or not os.getenv("IOL_PASSWORD"):
        _say("Falta IOL_USERNAME o IOL_PASSWORD")
        return 2
    return asyncio.run(run(args.only))


if __name__ == "__main__":
    sys.exit(main())
