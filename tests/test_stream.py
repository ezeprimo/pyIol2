"""Tests del cliente de streaming con una conexion WebSocket simulada."""

import asyncio
import contextlib
import json
from typing import Any

import pytest

from pyIol2 import IOLStreamError, IOLValidationError, StreamMessage
from pyIol2.stream import IOLStreamClient, build_symbol_id

AUTH_OK = json.dumps({"code": 200, "msg": "Connected"})


def quote_message(symbol: str = "GGAL") -> str:
    """Mensaje de puntas serializado."""
    return json.dumps(
        {
            "type": "Q",
            "msg": {
                "S": symbol,
                "M": "BCBA",
                "T": "T0",
                "D": "2026-01-01T12:00:00-03:00",
                "V": [
                    {"T": "BID", "X": 100, "P": 6025.0, "N": 1},
                    {"T": "OFFER", "X": 150, "P": 6030.0, "N": 1},
                ],
            },
        }
    )


def trade_message(symbol: str = "GGAL") -> str:
    """Mensaje de operaciones serializado."""
    return json.dumps(
        {
            "type": "T",
            "msg": {
                "S": symbol,
                "M": "BCBA",
                "T": "T0",
                "P": 6030.0,
                "V": 0.33,
                "TS": 25000,
                "TP": 150000000,
                "X": 20,
                "D": "2026-01-01T12:00:00-03:00",
            },
        }
    )


class FakeConnection:
    """Conexion WebSocket simulada con una cola de mensajes entrantes."""

    def __init__(self, inbound: list[str], sent: list[dict[str, Any]], delay: float = 0.0):
        self.inbound = list(inbound)
        self.sent = sent
        self.delay = delay
        self.closed = False

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.closed = True

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self) -> str:
        return self.inbound.pop(0)

    def __aiter__(self) -> "FakeConnection":
        return self

    async def __anext__(self) -> str:
        if not self.inbound:
            raise StopAsyncIteration
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.inbound.pop(0)


class FakeServer:
    """Fabrica de conexiones falsas que registra cada conexion abierta."""

    def __init__(
        self,
        inbound_after_auth: list[str] | None = None,
        auth_response: str = AUTH_OK,
        delay: float = 0.0,
    ):
        self.inbound_after_auth = inbound_after_auth or []
        self.auth_response = auth_response
        self.delay = delay
        self.connections: list[FakeConnection] = []
        self.sent: list[dict[str, Any]] = []
        self.urls: list[str] = []

    def connect(self, url: str, **kwargs: Any) -> FakeConnection:
        self.urls.append(url)
        connection = FakeConnection(
            [self.auth_response, *self.inbound_after_auth], self.sent, delay=self.delay
        )
        self.connections.append(connection)
        return connection


def make_stream(server: FakeServer, **kwargs: Any) -> IOLStreamClient:
    """Arma un cliente de streaming con el servidor falso."""
    return IOLStreamClient(token="token-1", connect_factory=server.connect, **kwargs)


def test_build_symbol_id_usa_el_formato_documentado():
    assert build_symbol_id("GGAL", "BCBA", "T0") == "GGAL|BCBA|T0"


async def test_sin_credenciales_ni_token_falla():
    with pytest.raises(IOLValidationError):
        IOLStreamClient()


async def test_sin_simbolos_falla():
    stream = make_stream(FakeServer())

    with pytest.raises(IOLValidationError):
        async for _ in stream.subscribe([]):
            pass


async def test_sin_canales_falla():
    stream = make_stream(FakeServer())

    with pytest.raises(IOLValidationError):
        async for _ in stream.subscribe(["GGAL"], quotes=False, trades=False):
            pass


async def test_order_book_admite_un_solo_simbolo():
    stream = make_stream(FakeServer())

    with pytest.raises(IOLValidationError):
        async for _ in stream.subscribe(["GGAL", "YPFD"], order_book=True):
            pass


async def test_autenticacion_y_suscripcion_arman_el_mensaje_documentado():
    server = FakeServer([quote_message()])
    stream = make_stream(server)

    async for _ in stream.subscribe(["GGAL"], quotes=True, trades=False):
        break

    assert server.sent[0] == {"action": "auth_token", "token": "token-1"}
    assert server.sent[1] == {
        "action": "subscribe",
        "trades": [],
        "quotes": ["GGAL|BCBA|T0"],
        "order_book": [],
    }


async def test_las_tres_claves_de_subscribe_siempre_viajan():
    server = FakeServer([quote_message()])
    stream = make_stream(server)

    async for _ in stream.subscribe(["GGAL"], quotes=True, trades=True):
        break

    subscribe = server.sent[1]
    assert set(subscribe) == {"action", "trades", "quotes", "order_book"}
    assert subscribe["quotes"] == subscribe["trades"] == ["GGAL|BCBA|T0"]


async def test_entrega_los_mensajes_en_orden():
    server = FakeServer([quote_message(), trade_message()])
    stream = make_stream(server)

    agen = stream.subscribe(["GGAL"])
    first = await asyncio.wait_for(anext(agen), timeout=5)
    second = await asyncio.wait_for(anext(agen), timeout=5)
    await agen.aclose()

    assert isinstance(first, StreamMessage)
    assert first.type == "Q"
    assert first.quote is not None
    assert first.quote.bid.price == 6025.0
    assert second.type == "T"
    assert second.trade is not None
    assert second.trade.last_price == 6030.0


async def test_reparte_los_simbolos_en_varias_conexiones():
    server = FakeServer()
    stream = make_stream(server, max_symbols=50)
    symbols = [f"SYM{index}" for index in range(120)]

    agen = stream.subscribe(symbols)
    pending = asyncio.create_task(anext(agen))
    await asyncio.sleep(0.05)
    pending.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await pending
    await agen.aclose()

    assert len(server.connections) == 3
    assert stream.max_symbols == 50


async def test_order_book_abre_una_conexion_propia():
    server = FakeServer()
    stream = make_stream(server)

    agen = stream.subscribe(["GGAL"], quotes=False, trades=False, order_book=True)
    pending = asyncio.create_task(anext(agen))
    await asyncio.sleep(0.05)
    pending.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await pending
    await agen.aclose()

    assert server.sent[1]["order_book"] == ["GGAL|BCBA|T0"]
    assert server.sent[1]["quotes"] == []


async def test_heartbeat_manda_pings():
    server = FakeServer([quote_message(), quote_message()], delay=0.05)
    stream = make_stream(server, heartbeat_interval=0.01)

    agen = stream.subscribe(["GGAL"])
    await asyncio.wait_for(anext(agen), timeout=5)
    await asyncio.sleep(0.05)
    await agen.aclose()

    assert {"action": "ping"} in server.sent


async def test_autenticacion_rechazada_llega_al_consumidor():
    server = FakeServer(auth_response=json.dumps({"code": 401, "msg": "Token invalido"}))
    stream = make_stream(server)

    with pytest.raises(IOLStreamError) as error:
        async for _ in stream.subscribe(["GGAL"]):
            pass

    assert "rechazo la autenticacion" in str(error.value)


async def test_error_del_servidor_llega_al_consumidor():
    server = FakeServer([json.dumps({"type": "Error", "code": 400, "msg": "Argument Error"})])
    stream = make_stream(server)

    with pytest.raises(IOLStreamError) as error:
        async for _ in stream.subscribe(["GGAL"]):
            pass

    assert error.value.ws_code == 400
    assert "Argument Error" in str(error.value)


async def test_order_book_excedido_se_reporta_como_error_de_stream():
    server = FakeServer(
        [json.dumps({"type": "Error", "code": 401, "msg": "Order Book Subscribed Exceded"})]
    )
    stream = make_stream(server)

    with pytest.raises(IOLStreamError) as error:
        async for _ in stream.subscribe(["GGAL"], quotes=False, trades=False, order_book=True):
            pass

    assert error.value.ws_code == 401
    assert "Order Book" in str(error.value)


async def test_close_libera_las_tareas():
    server = FakeServer()
    stream = make_stream(server)

    agen = stream.subscribe(["GGAL"])
    await asyncio.sleep(0.02)
    await agen.aclose()

    assert stream._tasks == []
