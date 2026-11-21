"""
Configuracion y fixtures compartidas para los tests.

Las pruebas no tocan la red: cada request se resuelve con un `httpx.MockTransport`
que registra lo que se pidio y devuelve el sobre de la API.
"""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from pyIol2 import IOLClient

TOKEN_PAYLOAD = {
    "access_token": "token-1",
    "refresh_token": "refresh-1",
    "expires_in": 900,
    "expires_at": "2026-01-01T00:00:00Z",
    "token_type": "bearer",
}


def envelope(
    data: Any,
    *,
    status: int = 200,
    trace_id: str = "trace-abc",
    method: str = "GET",
    path: str = "/broker/market-data/GGAL/quote",
    total_count: int | None = None,
) -> dict[str, Any]:
    """Arma el sobre exitoso `{meta, data, error}` que devuelve la API."""
    meta: dict[str, Any] = {
        "timestamp": "2026-01-01T12:00:00.000Z",
        "path": path,
        "method": method,
        "status_code": status,
        "trace_id": trace_id,
    }
    if total_count is not None:
        meta["total_count"] = total_count
    return {"meta": meta, "data": data, "error": None}


def error_envelope(
    message: str = "Solicitud invalida",
    *,
    code: int = 1001,
    status: int = 400,
    trace_id: str = "trace-error",
    details: Any = None,
) -> dict[str, Any]:
    """Arma el sobre de error que devuelve la API."""
    return {
        "meta": {
            "timestamp": "2026-01-01T12:00:00.000Z",
            "path": "/broker/orders",
            "method": "POST",
            "status_code": status,
            "trace_id": trace_id,
        },
        "data": None,
        "error": {"message": message, "code": code, "details": details},
    }


class StubAPI:
    """
    Doble de la API de IOL sobre `httpx.MockTransport`.

    Registra cada request y resuelve por ruta. El endpoint de token responde
    solo, salvo que se configure otra cosa con `set_token_response`.
    """

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.routes: dict[tuple[str, str], dict[str, Any]] = {}
        self.statuses: dict[tuple[str, str], int] = {}
        self.sequences: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = {}
        self.token_calls = 0
        self.token_response: dict[str, Any] | None = None
        self.token_status = 200

    def set(
        self, method: str, path: str, payload: Any, status: int = 200, raw: bool = False
    ) -> None:
        """
        Registra la respuesta de una ruta.

        Por defecto envuelve `payload` en el sobre de la API. Con `raw=True` el
        valor se usa tal cual, para poder montar sobres de error a mano.
        """
        self.routes[(method.upper(), path)] = payload if raw else envelope(payload, status=status)
        self.statuses[(method.upper(), path)] = status

    def set_sequence(self, method: str, path: str, responses: list[tuple[int, Any]]) -> None:
        """
        Registra una secuencia de respuestas para una ruta.

        La ultima respuesta se repite si se pide la ruta mas veces que la
        secuencia. Sirve para probar reintentos y errores intermitentes.
        """
        key = (method.upper(), path)
        self.sequences[key] = [
            (status, envelope(payload, status=status)) for status, payload in responses
        ]

    def set_token_response(self, payload: dict[str, Any], status: int = 200) -> None:
        """Reemplaza la respuesta del endpoint de token."""
        self.token_response = payload
        self.token_status = status

    def handler(self, request: httpx.Request) -> httpx.Response:
        """Resuelve una request y la registra."""
        body = json.loads(request.content) if request.content else None
        self.requests.append(
            {
                "method": request.method,
                "path": request.url.path,
                "params": dict(request.url.params),
                "body": body,
                "headers": dict(request.headers),
            }
        )

        if request.url.path == "/auth/token":
            self.token_calls += 1
            payload = self.token_response or envelope(
                {**TOKEN_PAYLOAD, "access_token": f"token-{self.token_calls}"}
            )
            return httpx.Response(self.token_status, json=payload)

        key = (request.method, request.url.path)
        sequence = self.sequences.get(key)
        if sequence:
            status, payload = sequence.pop(0) if len(sequence) > 1 else sequence[0]
            return httpx.Response(status, json=payload)
        if key not in self.routes:
            return httpx.Response(404, json=error_envelope("Not found", status=404))
        return httpx.Response(self.statuses.get(key, 200), json=self.routes[key])

    def transport(self) -> httpx.MockTransport:
        """Transporte listo para inyectar en un `httpx.Client`."""
        return httpx.MockTransport(self.handler)

    def last(self, method: str | None = None, path: str | None = None) -> dict[str, Any]:
        """Ultima request registrada, opcionalmente filtrando por ruta."""
        for request in reversed(self.requests):
            if method and request["method"] != method:
                continue
            if path and request["path"] != path:
                continue
            return request
        raise AssertionError(f"No se encontro request {method} {path}")


@pytest.fixture
def stub() -> StubAPI:
    """Doble de la API con respuestas por ruta."""
    return StubAPI()


@pytest.fixture
def make_client(stub: StubAPI) -> Callable[..., IOLClient]:
    """Fabrica clientes IOL apoyados en el doble de la API."""
    clients: list[IOLClient] = []

    def _make(**kwargs: Any) -> IOLClient:
        http = httpx.Client(transport=stub.transport())
        client = IOLClient("usuario", "password", client=http, **kwargs)
        clients.append(client)
        return client

    return _make


@pytest.fixture
def client(stub: StubAPI, make_client: Callable[..., IOLClient]) -> IOLClient:
    """Cliente IOL apoyado en el doble de la API."""
    return make_client()


# ---------------------------------------------------------------------------
# Payloads de ejemplo, con la forma documentada por la API
# ---------------------------------------------------------------------------

QUOTE_PAYLOAD: dict[str, Any] = {
    "symbol": "GGAL",
    "market": "BCBA",
    "settlement_term": "T0",
    "currency": "ARS",
    "lot_size": 1,
    "maturity_date": None,
    "last_updated": "2026-01-01T12:00:00-03:00",
    "prices": {
        "close": 6040.0,
        "current": 6030.0,
        "high": 6100.0,
        "low": 5980.0,
        "open": 5990.0,
        "previous_close": 6010.0,
    },
    "change": {"amount": 20.0, "percent": 0.33},
    "volume": {"amount": 150000000.0, "shares": 25000.0},
}

DEPTH_PAYLOAD: dict[str, Any] = {
    "symbol": "GGAL",
    "market": "BCBA",
    "settlement_term": "T0",
    "lot_size": 1,
    "last_updated": "2026-01-01T12:00:00-03:00",
    "bids": [
        {"position": 1, "price": 6025.0, "size": 100.0},
        {"position": 2, "price": 6020.0, "size": 250.0},
    ],
    "asks": [{"position": 1, "price": 6030.0, "size": 150.0}],
}

SCREENER_PAYLOAD: list[dict[str, Any]] = [
    {
        "instrument": {"symbol": "GGAL", "name": "Grupo Financiero Galicia", "market": "BCBA"},
        "quotes": {
            "open": 5990.0,
            "high": 6100.0,
            "low": 5980.0,
            "close": 6040.0,
            "last": 6030.0,
            "change_percent": 0.33,
            "volume": 25000.0,
        },
        "book": {
            "bid": {"price": 6025.0, "size": 100.0},
            "ask": {"price": 6030.0, "size": 150.0},
        },
    }
]

OPTIONS_PAYLOAD: list[dict[str, Any]] = [
    {
        "symbol": "GFGC6030F",
        "option": {"strike_price": 6030.0, "type": "call", "state": "abierta"},
        "quotes": {"last": 120.0, "change_percent": -1.5, "volume": 30.0},
        "book": {"bid": {"price": 118.0, "size": 5.0}, "ask": {"price": 122.0, "size": 7.0}},
    }
]

BARS_PAYLOAD: dict[str, Any] = {
    "symbol": "GGAL",
    "market": "BCBA",
    "total_bars": 2,
    "bars": [
        {
            "datetime": "2026-01-01 10:00:00",
            "timestamp": 1767261600,
            "open": 5990.0,
            "high": 6010.0,
            "low": 5985.0,
            "close": 6005.0,
            "volume": 1200.0,
        },
        {
            "datetime": "2026-01-01 10:05:00",
            "timestamp": 1767261900,
            "open": 6005.0,
            "high": 6030.0,
            "low": 6000.0,
            "close": 6028.0,
            "volume": 900.0,
        },
    ],
}

BALANCES_PAYLOAD: dict[str, Any] = {
    "ars": {
        "currency": "ARS",
        "totals": {"t0": 1000.0, "t1": 2000.0, "t2": 0.0, "t3": 0.0},
        "available": {"t0": 900.0, "t1": 1900.0, "t2": 0.0, "t3": 0.0},
        "committed": {"t0": 100.0, "t1": 100.0, "t2": 0.0, "t3": 0.0},
        "available_for_withdrawal": 800.0,
    },
    "usd": {
        "currency": "USD",
        "totals": {"t0": 10.0, "t1": 20.0, "t2": 0.0, "t3": 0.0},
        "available": {"t0": 10.0, "t1": 20.0, "t2": 0.0, "t3": 0.0},
        "committed": {"t0": 0.0, "t1": 0.0, "t2": 0.0, "t3": 0.0},
        "available_for_withdrawal": 5.0,
    },
}

POSITIONS_PAYLOAD: dict[str, Any] = {
    "account": "123456",
    "currency": "ARS",
    "positions_count": 1,
    "total_market_value": 120600.0,
    "positions": [
        {
            "instrument": {
                "symbol": "GGAL",
                "name": "Grupo Financiero Galicia",
                "type": "ACCIONES",
                "asset_class": "equity",
                "country": "AR",
                "currency": "ARS",
                "exchange": "BCBA",
                "lot_size": 1,
                "minimum_quantity": 1,
                "tradable": True,
            },
            "parent_instrument": None,
            "quantity": 20.0,
            "availability": {
                "quantity_available": 20.0,
                "quantity_held": 0.0,
                "quantity_pending": 0.0,
            },
            "cost_basis": {
                "average_entry_price": 5500.0,
                "days_held": 30,
                "entry_date": "2025-12-01",
                "total_cost": 110000.0,
            },
            "market_value": {
                "current_price": 6030.0,
                "price_change": 20.0,
                "price_change_percent": 0.33,
            },
            "profit_loss": {"unrealized_pl": 10600.0, "unrealized_pl_percent": 9.64},
            "portfolio_weight_percent": 100.0,
            "is_accredited": False,
            "maturity_date": None,
        }
    ],
}

ACTIVITIES_PAYLOAD: list[dict[str, Any]] = [
    {
        "id": "act-1",
        "ticket_id": "tk-1",
        "account_type": "individual",
        "activity_type": "Buy",
        "activity_type_id": 2,
        "currency": "ARS",
        "fees": {"commission": 150.0, "other": 10.0, "vat": 33.6},
        "net_amount": -120783.6,
        "price": 6030.0,
        "qty": 20.0,
        "status": "completed",
        "trade_date": "2025-12-20",
        "settlement_date": "2025-12-22",
    }
]

OPERATIONS_PAYLOAD: list[dict[str, Any]] = [
    {
        "order_id": "ord-1",
        "ticket_id": "tk-1",
        "symbol": "GGAL",
        "description": "Compra GGAL",
        "type": "Compra",
        "asset_type": "stocks",
        "currency": "ARS",
        "term": "T0",
        "status": "finished",
        "order_date": "2025-12-20T10:00:00-03:00",
        "execution_date": "2025-12-20T10:00:05-03:00",
        "order": {"amount": 120600.0, "price": 6030.0, "qty": 20.0},
        "executed": {"amount": 120600.0, "price": 6030.0, "qty": 20.0},
    }
]

HISTORY_PAYLOAD: dict[str, Any] = {
    "account": "123456",
    "status": "complete",
    "missing_dates": [],
    "history": [
        {
            "date": "2025-12-20",
            "cash_flow": {
                "deposits": {"ars": 100.0, "usd": 0.0},
                "withdrawals": {"ars": 0.0, "usd": 0.0},
            },
            "equity": {"ars": 120600.0, "usd_ccl": 100.5, "usd_mep": 101.2},
            "exchange_rate": {"ccl": 1200.0, "mep": 1190.0},
            "has_pledged_collateral": False,
        }
    ],
}

ORDER_RESULT_PAYLOAD: dict[str, Any] = {
    "order_id": "ord-1",
    "successful_purchase": True,
    "messages": [{"code": "0", "message": "Orden aceptada"}],
}

ORDER_ESTIMATE_PAYLOAD: dict[str, Any] = {
    "amount": {"currency": "ARS", "value": 120600.0},
    "commission": {"currency": "ARS", "value": 150.0},
    "regulatory_fees": {
        "market_fee": {"currency": "ARS", "value": 12.0},
        "vat": {"currency": "ARS", "value": 33.6},
    },
}

REPO_TERMS_PAYLOAD: list[dict[str, Any]] = [
    {
        "term_id": 1,
        "term_days": 1,
        "due_date": "2026-01-02",
        "min_amount": 1000.0,
        "max_amount": 10000000.0,
    }
]

REPO_QUOTES_PAYLOAD: list[dict[str, Any]] = [
    {
        "position": 1,
        "bid": {"rate": 35.5, "amount": 500000.0},
        "ask": {"rate": 36.0, "amount": 400000.0},
    }
]

FCI_OPERATION_PAYLOAD: dict[str, Any] = {
    "transaction_id": "tx-1",
    "successful": True,
    "messages": [{"code": "0", "message": "Suscripcion aceptada"}],
}

WATCHLIST_PAYLOAD: dict[str, Any] = {
    "id": 7,
    "name": "Seguimiento",
    "items_count": 1,
    "items": [
        {
            "symbol": "GGAL",
            "market": "BCBA",
            "name": "Grupo Financiero Galicia",
            "asset_type": "stocks",
            "settlement_term": "T0",
            "quote": {
                "last_price": 6030.0,
                "change_percent": 0.33,
                "best_bid": 6025.0,
                "best_bid_size": 100.0,
                "best_ask": 6030.0,
                "best_ask_size": 150.0,
                "average_price": 6015.0,
                "currency": "ARS",
                "volume": 25000.0,
                "traded_quantity": 25000.0,
                "traded_amount": 150000000.0,
                "last_updated": "2026-01-01T12:00:00-03:00",
            },
        }
    ],
}

ASSET_PAYLOAD: dict[str, Any] = {
    "symbol": "GGAL",
    "name": "Grupo Financiero Galicia",
    "asset_type": "stocks",
    "market": "BCBA",
    "country": "AR",
    "currency": "ARS",
    "default_settlement_term": "T0",
    "trading_info": {"lot_size": 1, "minimum_investment": 6030.0, "minimum_quantity": 1},
}
