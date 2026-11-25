# Cliente de streaming (WebSocket) de market data de IOL Inversiones

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from .auth import IOLToken
from .constants import (
    AUTH_URL,
    DEFAULT_MARKET,
    DEFAULT_SETTLEMENT_TERM,
    DEFAULT_TIMEOUT,
    STREAM_BASE_URL,
    STREAM_DEFAULT_RECONNECT_DELAY_SECONDS,
    STREAM_HEARTBEAT_INTERVAL_SECONDS,
    STREAM_MAX_ORDER_BOOK_PER_CONNECTION,
    STREAM_MAX_RECONNECT_ATTEMPTS,
    STREAM_MAX_RECONNECT_DELAY_SECONDS,
    STREAM_MAX_SYMBOLS_PER_CONNECTION,
    STREAM_PROTOCOL_TYPES,
    GrantTypes,
    StreamActions,
    StreamChannels,
    StreamMessageTypes,
)
from .exceptions import IOLStreamError, IOLValidationError
from .models import StreamOrderBookMessage, StreamQuoteMessage, StreamTradeMessage

__all__ = ["IOLStreamClient", "StreamMessage"]

logger = logging.getLogger(__name__)

# Firma del conector de WebSocket, para poder inyectar uno falso en los tests.
ConnectFactory = Callable[..., Awaitable[Any]]


@dataclass
class StreamMessage:
    """
    Mensaje recibido del WebSocket de market data.

    Attributes:
        type: `Q` puntas, `B` profundidad, `T` operaciones
        symbol: Simbolo del activo
        market: Mercado
        term: Plazo de liquidacion
        quote: Mensaje de puntas, si `type` es `Q`
        order_book: Mensaje de profundidad, si `type` es `B`
        trade: Mensaje de operaciones, si `type` es `T`
        raw: Mensaje original, sin transformar
    """

    type: str = ""
    symbol: str = ""
    market: str = ""
    term: str = ""
    quote: StreamQuoteMessage | None = None
    order_book: StreamOrderBookMessage | None = None
    trade: StreamTradeMessage | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamMessage":
        """Construye el mensaje a partir del JSON recibido."""
        message_type = str(data.get("type", ""))
        message: dict[str, Any] = data.get("msg") if isinstance(data.get("msg"), dict) else {}

        if message_type == StreamMessageTypes.QUOTE:
            quote = StreamQuoteMessage.from_dict(message)
            return cls(
                type=message_type,
                symbol=quote.symbol,
                market=quote.market,
                term=quote.term,
                quote=quote,
                raw=data,
            )
        if message_type == StreamMessageTypes.ORDER_BOOK:
            book = StreamOrderBookMessage.from_dict(message)
            return cls(
                type=message_type,
                symbol=book.symbol,
                market=book.market,
                term=book.term,
                order_book=book,
                raw=data,
            )
        if message_type == StreamMessageTypes.TRADES:
            trade = StreamTradeMessage.from_dict(message)
            return cls(
                type=message_type,
                symbol=trade.symbol,
                market=trade.market,
                term=trade.term,
                trade=trade,
                raw=data,
            )
        return cls(
            type=message_type,
            symbol=str(message.get("S", "")),
            market=str(message.get("M", "")),
            term=str(message.get("T", "")),
            raw=data,
        )


def build_symbol_id(symbol: str, market: str, term: str) -> str:
    """
    Arma el identificador de activo que espera el WebSocket.

    Args:
        symbol: Simbolo del activo
        market: Mercado
        term: Plazo de liquidacion

    Returns:
        Identificador `SYMBOL|MARKET|TERM`, por ejemplo `GGAL|BCBA|T0`
    """
    return f"{symbol}|{market}|{term}"


class _MarketDataConnection:
    """
    Una conexion WebSocket autenticada y suscripta.

    Mantiene el heartbeat, reintenta con backoff exponencial y vuelve a
    suscribirse cuando se reconecta. Publica los mensajes de datos en la cola
    compartida del cliente.
    """

    def __init__(
        self,
        *,
        url: str,
        auth_payload: dict[str, Any],
        quotes: list[str],
        trades: list[str],
        order_book: list[str],
        queue: "asyncio.Queue[StreamMessage | None]",
        connect_factory: ConnectFactory,
        heartbeat_interval: float,
        max_attempts: int,
        reconnect_delay: float,
        max_reconnect_delay: float,
    ):
        self._url = url
        self._auth_payload = auth_payload
        self._quotes = quotes
        self._trades = trades
        self._order_book = order_book
        self._queue = queue
        self._connect = connect_factory
        self._heartbeat_interval = heartbeat_interval
        self._max_attempts = max_attempts
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay
        self._control: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def run(self) -> None:
        """
        Corre la conexion hasta que se cierra definitivamente.

        Raises:
            IOLStreamError: Si se agotan los reintentos o la API rechaza la sesion
        """
        delay = self._reconnect_delay
        attempt = 0
        while True:
            try:
                await self._session()
                return
            except IOLStreamError:
                raise
            except (OSError, asyncio.TimeoutError) as exc:
                attempt += 1
                if attempt > self._max_attempts:
                    raise IOLStreamError(
                        f"Se agotaron los reintentos del WebSocket: {exc}"
                    ) from exc
                logger.warning(
                    "WebSocket desconectado (%s), reintento %s/%s en %.1fs",
                    exc,
                    attempt,
                    self._max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._max_reconnect_delay)

    async def _session(self) -> None:
        """Abre una conexion, se autentica, se suscribe y consume mensajes."""
        async with self._connect(self._url, open_timeout=DEFAULT_TIMEOUT) as websocket:
            await websocket.send(json.dumps(self._auth_payload))
            await self._await_auth(websocket)
            await websocket.send(json.dumps(self._subscribe_payload()))
            heartbeat = asyncio.create_task(self._heartbeat(websocket))
            control = asyncio.create_task(self._pump_control(websocket))
            try:
                async for raw in websocket:
                    await self._handle(json.loads(raw))
            finally:
                for task in (heartbeat, control):
                    task.cancel()
                for task in (heartbeat, control):
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

    async def _await_auth(self, websocket: Any) -> None:
        """Espera la respuesta de autenticacion y falla si la rechaza."""
        raw = await asyncio.wait_for(websocket.recv(), timeout=DEFAULT_TIMEOUT)
        payload = json.loads(raw)
        code = payload.get("code")
        if code != 200:
            raise IOLStreamError(
                f"El WebSocket rechazo la autenticacion: {payload.get('msg', payload)}",
                code=code if isinstance(code, int) else None,
                payload=payload,
            )

    def _subscribe_payload(self) -> dict[str, Any]:
        """
        Arma el mensaje de suscripcion.

        Las tres claves son obligatorias: las que no se usan van como lista
        vacia, o el servidor responde 400.
        """
        return {
            "action": StreamActions.SUBSCRIBE,
            "trades": self._trades,
            "quotes": self._quotes,
            "order_book": self._order_book,
        }

    async def _heartbeat(self, websocket: Any) -> None:
        """Manda un ping periodico mientras la conexion este abierta."""
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            await websocket.send(json.dumps({"action": StreamActions.PING}))

    async def _pump_control(self, websocket: Any) -> None:
        """Envia los mensajes de control que encola el cliente."""
        while True:
            frame = await self._control.get()
            await websocket.send(json.dumps(frame))

    def subscribed_ids(self) -> list[str]:
        """Identificadores de activo suscriptos en esta conexion."""
        return sorted(set(self._quotes) | set(self._trades) | set(self._order_book))

    async def unsubscribe(self, symbol_ids: list[str]) -> list[str]:
        """
        Da de baja los activos indicados en esta conexion.

        Args:
            symbol_ids: Identificadores `SYMBOL|MARKET|TERM` a desuscribir

        Returns:
            Los identificadores que esta conexion tenia efectivamente suscriptos
        """
        frame: dict[str, Any] = {"action": StreamActions.UNSUBSCRIBE}
        removed: list[str] = []
        for channel, current in (
            (StreamChannels.TRADES, self._trades),
            (StreamChannels.QUOTES, self._quotes),
            (StreamChannels.ORDER_BOOK, self._order_book),
        ):
            matches = [symbol_id for symbol_id in current if symbol_id in symbol_ids]
            frame[channel] = matches
            for symbol_id in matches:
                if symbol_id not in removed:
                    removed.append(symbol_id)
                current.remove(symbol_id)
        if removed:
            await self._control.put(frame)
        return removed

    async def unsubscribe_all(self) -> None:
        """Da de baja todas las suscripciones de esta conexion."""
        self._quotes.clear()
        self._trades.clear()
        self._order_book.clear()
        await self._control.put({"action": StreamActions.UNSUBSCRIBE_ALL})

    async def _handle(self, payload: dict[str, Any]) -> None:
        """Traduce un mensaje entrante y lo publica en la cola."""
        if payload.get("type") in STREAM_PROTOCOL_TYPES:
            logger.debug("Frame de protocolo descartado: %s", payload)
            return
        if payload.get("type") == StreamMessageTypes.ERROR:
            raise IOLStreamError(
                str(payload.get("msg", "Error del WebSocket")),
                code=payload.get("code") if isinstance(payload.get("code"), int) else None,
                payload=payload,
            )
        await self._queue.put(StreamMessage.from_dict(payload))


class IOLStreamClient:
    """
    Cliente de streaming de market data de IOL.

    Se usa como context manager asincronico:

    ```python
    async with IOLStreamClient("usuario", "password") as stream:
        async for message in stream.subscribe(["GGAL"], quotes=True, trades=True):
            print(message.type, message.symbol)
    ```

    Si se piden mas de 50 simbolos de puntas u operaciones, la libreria abre
    tantas conexiones como haga falta y las reparte sola. La profundidad
    (`order_book`) admite un solo titulo por conexion, asi que se pide de a uno.

    Args:
        username: Usuario de IOL; se usa para pedir el token OAuth
        password: Contrasena de IOL
        token: Access token ya emitido; si se pasa, no se piden credenciales
        base_url: URL del WebSocket
        max_symbols: Maximo de titulos por conexion de puntas y operaciones
        heartbeat_interval: Segundos entre pings
        reconnect_attempts: Reintentos por conexion ante cortes
        connect_factory: Conector de WebSocket alternativo (para tests)
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        *,
        token: str | None = None,
        base_url: str = STREAM_BASE_URL,
        max_symbols: int = STREAM_MAX_SYMBOLS_PER_CONNECTION,
        heartbeat_interval: float = STREAM_HEARTBEAT_INTERVAL_SECONDS,
        reconnect_attempts: int = STREAM_MAX_RECONNECT_ATTEMPTS,
        connect_factory: ConnectFactory | None = None,
    ):
        if not token and not (username and password):
            raise IOLValidationError("hay que pasar username y password, o un token ya emitido")
        if max_symbols < 1:
            raise IOLValidationError("max_symbols tiene que ser mayor a cero")

        self.base_url = base_url
        self.max_symbols = max_symbols
        self.heartbeat_interval = heartbeat_interval
        self.reconnect_attempts = reconnect_attempts
        self._username = username
        self._password = password
        self._token = token
        self._connect = connect_factory or _default_connect()
        self._tasks: list[asyncio.Task] = []
        self._connections: list[_MarketDataConnection] = []

    async def __aenter__(self) -> "IOLStreamClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Cancela las conexiones y tareas activas."""
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks.clear()
        self._connections.clear()

    async def get_access_token(self) -> str:
        """
        Devuelve el token para autenticar el WebSocket.

        Si se paso un token al construir el cliente, lo usa tal cual. Si no,
        pide uno nuevo con las credenciales por el endpoint OAuth de la API.
        """
        if self._token:
            return self._token
        self._token = await asyncio.to_thread(self._fetch_token)
        return self._token

    def _fetch_token(self) -> str:
        """Pide un token OAuth usando usuario y contrasena."""
        response = httpx.post(
            AUTH_URL,
            json={
                "grant_type": GrantTypes.PASSWORD,
                "username": self._username,
                "password": self._password,
            },
            timeout=DEFAULT_TIMEOUT,
        )
        payload = response.json()
        if response.status_code >= 400 or payload.get("error"):
            raise IOLStreamError.from_envelope(payload, response.status_code)
        return IOLToken.from_dict(payload.get("data") or {}).access_token

    def _auth_payload(self, token: str) -> dict[str, Any]:
        """Arma el mensaje de autenticacion del WebSocket."""
        return {"action": StreamActions.AUTH_TOKEN, "token": token}

    def _shards(self, symbol_ids: list[str]) -> list[list[str]]:
        """Reparte los simbolos en tandas que respetan el limite por conexion."""
        return [
            symbol_ids[index : index + self.max_symbols]
            for index in range(0, len(symbol_ids), self.max_symbols)
        ]

    async def subscribe(
        self,
        symbols: list[str],
        *,
        market: str = DEFAULT_MARKET,
        term: str = DEFAULT_SETTLEMENT_TERM,
        quotes: bool = True,
        trades: bool = True,
        order_book: bool = False,
    ) -> AsyncIterator[StreamMessage]:
        """
        Abre las conexiones necesarias y devuelve un iterador de mensajes.

        Args:
            symbols: Simbolos a seguir
            market: Mercado de todos los simbolos
            term: Plazo de liquidacion de todos los simbolos
            quotes: Pedir puntas
            trades: Pedir operaciones
            order_book: Pedir profundidad; admite un solo simbolo por llamada

        Yields:
            StreamMessage con cada dato de mercado. Los frames de protocolo
            (`Success` al confirmar la suscripcion, `Pong` del heartbeat) se
            descartan: si la suscripcion no fue aceptada, el iterador levanta
            `IOLStreamError` en lugar de emitir un mensaje.

        Raises:
            IOLValidationError: Si no se pide ningun canal, si no hay simbolos
                o si se pide `order_book` para mas de un simbolo
        """
        if not symbols:
            raise IOLValidationError("hay que indicar al menos un simbolo")
        if not (quotes or trades or order_book):
            raise IOLValidationError("hay que pedir al menos un canal de datos")
        if order_book and len(symbols) > STREAM_MAX_ORDER_BOOK_PER_CONNECTION:
            raise IOLValidationError(
                "order_book admite un solo simbolo por conexion: "
                "pedi la profundidad de a un titulo por vez"
            )

        token = await self.get_access_token()
        symbol_ids = [build_symbol_id(symbol, market, term) for symbol in symbols]
        queue: asyncio.Queue = asyncio.Queue()

        if order_book:
            # La profundidad admite un titulo por conexion; los otros canales
            # pueden viajar en la misma conexion que el order_book.
            plans = [
                (
                    symbol_ids if quotes else [],
                    symbol_ids if trades else [],
                    symbol_ids,
                )
            ]
        else:
            # Cada canal lleva su propia lista: compartir la misma instancia
            # haria que un unsubscribe vaciara los dos canales a la vez.
            plans = [
                (list(shard) if quotes else [], list(shard) if trades else [], [])
                for shard in self._shards(symbol_ids)
            ]

        for quote_ids, trade_ids, book_ids in plans:
            connection = _MarketDataConnection(
                url=self.base_url,
                auth_payload=self._auth_payload(token),
                quotes=quote_ids,
                trades=trade_ids,
                order_book=book_ids,
                queue=queue,
                connect_factory=self._connect,
                heartbeat_interval=self.heartbeat_interval,
                max_attempts=self.reconnect_attempts,
                reconnect_delay=STREAM_DEFAULT_RECONNECT_DELAY_SECONDS,
                max_reconnect_delay=STREAM_MAX_RECONNECT_DELAY_SECONDS,
            )
            self._connections.append(connection)
            self._tasks.append(asyncio.create_task(self._run_connection(connection, queue)))

        try:
            while True:
                message = await queue.get()
                if message is None:
                    return
                if isinstance(message, BaseException):
                    raise message
                yield message
        finally:
            await self.close()

    async def unsubscribe(
        self,
        symbols: list[str],
        *,
        market: str = DEFAULT_MARKET,
        term: str = DEFAULT_SETTLEMENT_TERM,
    ) -> list[str]:
        """
        Da de baja activos sin cerrar las conexiones.

        Args:
            symbols: Simbolos a desuscribir
            market: Mercado de esos simbolos
            term: Plazo de liquidacion de esos simbolos

        Returns:
            Los identificadores que estaban efectivamente suscriptos y se dieron
            de baja; si la lista viene vacia, no habia nada que desuscribir
        """
        symbol_ids = [build_symbol_id(symbol, market, term) for symbol in symbols]
        removed: list[str] = []
        for connection in self._connections:
            removed.extend(await connection.unsubscribe(symbol_ids))
        return removed

    async def unsubscribe_all(self) -> None:
        """Da de baja todas las suscripciones de todas las conexiones abiertas."""
        for connection in self._connections:
            await connection.unsubscribe_all()

    @staticmethod
    async def _run_connection(connection: _MarketDataConnection, queue: asyncio.Queue) -> None:
        """
        Corre una conexion y publica su error final en la cola.

        Sin esto, un error de la conexion moriria dentro de la task y el
        consumidor quedaria esperando para siempre.
        """
        try:
            await connection.run()
        except asyncio.CancelledError:
            raise
        except BaseException as exc:  # noqa: BLE001 - se re-lanza en el consumidor
            await queue.put(exc)


def _default_connect() -> ConnectFactory:
    """Devuelve el conector real de `websockets`, importado a demanda."""
    from websockets.asyncio.client import connect

    return connect
