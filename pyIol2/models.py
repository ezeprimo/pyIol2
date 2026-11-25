# Modelos de datos para la API de IOL Inversiones (v1)
#
# Cada modelo expone `from_dict()` y refleja el campo `data` de la respuesta.
# El sobre de la API (`meta`, `data`, `error`) se modela en `IOLResponse`.

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    # Sobre de la API
    "IOLMeta",
    "IOLResponse",
    "HealthStatus",
    # Datos de mercado
    "PriceChange",
    "Prices",
    "Volume",
    "MarketQuote",
    "DepthLevel",
    "MarketDepth",
    "BookSide",
    "OrderBookTop",
    "InstrumentSummary",
    "QuoteSnapshot",
    "ScreenerEntry",
    "OptionTerms",
    "OptionQuote",
    "HistoricalBar",
    "HistoricalBars",
    # Assets
    "AssetTradingInfo",
    "AssetDetail",
    "AssetType",
    "AssetPanel",
    # Cuenta
    "SettlementTotals",
    "Balance",
    "AccountBalances",
    "PositionAvailability",
    "CostBasis",
    "Instrument",
    "MarketValue",
    "ProfitLoss",
    "Position",
    "Portfolio",
    "ActivityFees",
    "Activity",
    "OperationLeg",
    "Operation",
    "CashFlow",
    "Equity",
    "ExchangeRate",
    "PortfolioHistoryPoint",
    "PortfolioHistory",
    # Ordenes
    "OperationMessage",
    "OrderResult",
    "MoneyAmount",
    "RegulatoryFees",
    "OrderEstimate",
    "CancelResult",
    # Cauciones
    "RepoTerm",
    "RepoRateAmount",
    "RepoQuote",
    "RepoEstimate",
    "RepoOrderResult",
    # FCI
    "FundOperationResult",
    "FundValidationResult",
    "FundCancelResult",
    # Watchlists
    "WatchlistQuote",
    "WatchlistItem",
    "Watchlist",
    "WatchlistItemAdded",
    "WatchlistItemRemoved",
    "WatchlistRenamed",
    "WatchlistDeleted",
    # Streaming
    "StreamLevel",
    "StreamQuoteMessage",
    "StreamOrderBookMessage",
    "StreamTradeMessage",
]


def _as_dict(value: Any) -> dict[str, Any]:
    """Devuelve el valor como dict, o un dict vacio si no lo es."""
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    """Devuelve el valor como lista, o una lista vacia si no lo es."""
    return value if isinstance(value, list) else []


def _messages(data: dict[str, Any]) -> list["OperationMessage"]:
    """Normaliza la lista de mensajes de una operacion."""
    return [OperationMessage.from_dict(item) for item in _as_list(data.get("messages"))]


# ---------------------------------------------------------------------------
# Sobre de la API
# ---------------------------------------------------------------------------


@dataclass
class IOLMeta:
    """
    Metadatos que la API devuelve en cada respuesta.

    `trace_id` identifica la request y es el dato que pide el soporte de IOL
    cuando hay que investigar un problema.
    """

    timestamp: str = ""
    path: str = ""
    method: str = ""
    status_code: int = 0
    trace_id: str = ""
    total_count: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IOLMeta":
        data = _as_dict(data)
        total_count = data.get("total_count")
        return cls(
            timestamp=data.get("timestamp", ""),
            path=data.get("path", ""),
            method=data.get("method", ""),
            status_code=int(data.get("status_code") or 0),
            trace_id=data.get("trace_id", ""),
            total_count=int(total_count) if total_count is not None else None,
        )


@dataclass
class IOLResponse:
    """
    Sobre completo de la API: `{meta, data, error}`.

    Attributes:
        data: Contenido de la respuesta, sin transformar
        meta: Metadatos de la request
        error: Error informado por la API, o None
    """

    data: Any = None
    meta: IOLMeta = field(default_factory=IOLMeta)
    error: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IOLResponse":
        data = _as_dict(data)
        return cls(
            data=data.get("data"),
            meta=IOLMeta.from_dict(_as_dict(data.get("meta"))),
            error=data.get("error"),
        )

    @property
    def trace_id(self) -> str:
        """Atajo al trace_id de la respuesta."""
        return self.meta.trace_id


@dataclass
class HealthStatus:
    """Estado del servicio de la API."""

    status: str = ""
    timestamp: str = ""
    uptime: float = 0.0
    version: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HealthStatus":
        data = _as_dict(data)
        return cls(
            status=data.get("status", ""),
            timestamp=data.get("timestamp", ""),
            uptime=data.get("uptime") or 0.0,
            version=data.get("version", ""),
        )


# ---------------------------------------------------------------------------
# Datos de mercado
# ---------------------------------------------------------------------------


@dataclass
class PriceChange:
    """Variacion de precio del dia."""

    amount: float = 0.0
    percent: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PriceChange":
        data = _as_dict(data)
        return cls(
            amount=data.get("amount") or 0.0,
            percent=data.get("percent") or 0.0,
        )


@dataclass
class Prices:
    """Precios relevantes de la rueda."""

    close: float = 0.0
    current: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    previous_close: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Prices":
        data = _as_dict(data)
        return cls(
            close=data.get("close") or 0.0,
            current=data.get("current") or 0.0,
            high=data.get("high") or 0.0,
            low=data.get("low") or 0.0,
            open=data.get("open") or 0.0,
            previous_close=data.get("previous_close") or 0.0,
        )


@dataclass
class Volume:
    """Volumen operado: monto y nominales."""

    amount: float = 0.0
    shares: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Volume":
        data = _as_dict(data)
        return cls(
            amount=data.get("amount") or 0.0,
            shares=data.get("shares") or 0.0,
        )


@dataclass
class MarketQuote:
    """
    Cotizacion de mercado de un activo.

    Attributes:
        symbol: Simbolo del activo
        market: Mercado, en mayusculas (por ejemplo BCBA)
        settlement_term: Plazo de liquidacion (T0 o T1)
        currency: Moneda de operacion
        lot_size: Lamina minima
        maturity_date: Vencimiento, para instrumentos que lo tienen
        last_updated: Fecha y hora de la ultima actualizacion
        prices: Precios de la rueda
        change: Variacion del dia
        volume: Volumen operado
    """

    symbol: str = ""
    market: str = ""
    settlement_term: str = ""
    currency: str = ""
    lot_size: float = 0.0
    maturity_date: str | None = None
    last_updated: str = ""
    prices: Prices = field(default_factory=Prices)
    change: PriceChange = field(default_factory=PriceChange)
    volume: Volume = field(default_factory=Volume)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MarketQuote":
        data = _as_dict(data)
        return cls(
            symbol=data.get("symbol", ""),
            market=data.get("market", ""),
            settlement_term=data.get("settlement_term", ""),
            currency=data.get("currency", ""),
            lot_size=data.get("lot_size") or 0.0,
            maturity_date=data.get("maturity_date"),
            last_updated=data.get("last_updated", ""),
            prices=Prices.from_dict(_as_dict(data.get("prices"))),
            change=PriceChange.from_dict(_as_dict(data.get("change"))),
            volume=Volume.from_dict(_as_dict(data.get("volume"))),
        )


@dataclass
class DepthLevel:
    """Nivel del libro de ordenes."""

    position: int = 0
    price: float = 0.0
    size: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DepthLevel":
        data = _as_dict(data)
        return cls(
            position=int(data.get("position") or 0),
            price=data.get("price") or 0.0,
            size=data.get("size") or 0.0,
        )


@dataclass
class MarketDepth:
    """Profundidad del libro: ofertas de compra y de venta."""

    symbol: str = ""
    market: str = ""
    settlement_term: str = ""
    lot_size: float = 0.0
    last_updated: str = ""
    bids: list[DepthLevel] = field(default_factory=list)
    asks: list[DepthLevel] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MarketDepth":
        data = _as_dict(data)
        return cls(
            symbol=data.get("symbol", ""),
            market=data.get("market", ""),
            settlement_term=data.get("settlement_term", ""),
            lot_size=data.get("lot_size") or 0.0,
            last_updated=data.get("last_updated", ""),
            bids=[DepthLevel.from_dict(item) for item in _as_list(data.get("bids"))],
            asks=[DepthLevel.from_dict(item) for item in _as_list(data.get("asks"))],
        )


@dataclass
class BookSide:
    """Precio y cantidad de un lado del libro."""

    price: float = 0.0
    size: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BookSide":
        data = _as_dict(data)
        return cls(price=data.get("price") or 0.0, size=data.get("size") or 0.0)


@dataclass
class OrderBookTop:
    """Mejor punta de compra y de venta."""

    bid: BookSide = field(default_factory=BookSide)
    ask: BookSide = field(default_factory=BookSide)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrderBookTop":
        data = _as_dict(data)
        return cls(
            bid=BookSide.from_dict(_as_dict(data.get("bid"))),
            ask=BookSide.from_dict(_as_dict(data.get("ask"))),
        )


@dataclass
class InstrumentSummary:
    """Datos basicos de un instrumento dentro de un listado."""

    symbol: str = ""
    name: str = ""
    market: str = ""
    currency: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstrumentSummary":
        data = _as_dict(data)
        return cls(
            symbol=data.get("symbol", ""),
            name=data.get("name", ""),
            market=data.get("market", ""),
            currency=data.get("currency", ""),
        )


@dataclass
class QuoteSnapshot:
    """Instantanea de precios usada en listados y en la cadena de opciones."""

    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    last: float = 0.0
    change_percent: float = 0.0
    volume: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuoteSnapshot":
        data = _as_dict(data)
        return cls(
            open=data.get("open") or 0.0,
            high=data.get("high") or 0.0,
            low=data.get("low") or 0.0,
            close=data.get("close") or 0.0,
            last=data.get("last") or 0.0,
            change_percent=data.get("change_percent") or 0.0,
            volume=data.get("volume") or 0.0,
        )


@dataclass
class ScreenerEntry:
    """Fila del screener de mercado."""

    instrument: InstrumentSummary = field(default_factory=InstrumentSummary)
    quotes: QuoteSnapshot = field(default_factory=QuoteSnapshot)
    book: OrderBookTop = field(default_factory=OrderBookTop)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScreenerEntry":
        data = _as_dict(data)
        return cls(
            instrument=InstrumentSummary.from_dict(_as_dict(data.get("instrument"))),
            quotes=QuoteSnapshot.from_dict(_as_dict(data.get("quotes"))),
            book=OrderBookTop.from_dict(_as_dict(data.get("book"))),
        )


@dataclass
class OptionTerms:
    """Condiciones del contrato de opcion."""

    strike_price: float = 0.0
    type: str = ""
    state: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OptionTerms":
        data = _as_dict(data)
        return cls(
            strike_price=data.get("strike_price") or 0.0,
            type=data.get("type", ""),
            state=data.get("state", ""),
        )


@dataclass
class OptionQuote:
    """Opcion de la cadena de un titulo."""

    symbol: str = ""
    option: OptionTerms = field(default_factory=OptionTerms)
    quotes: QuoteSnapshot = field(default_factory=QuoteSnapshot)
    book: OrderBookTop = field(default_factory=OrderBookTop)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OptionQuote":
        data = _as_dict(data)
        return cls(
            symbol=data.get("symbol", ""),
            option=OptionTerms.from_dict(_as_dict(data.get("option"))),
            quotes=QuoteSnapshot.from_dict(_as_dict(data.get("quotes"))),
            book=OrderBookTop.from_dict(_as_dict(data.get("book"))),
        )


@dataclass
class HistoricalBar:
    """
    Vela OHLCV historica.

    Attributes:
        datetime: Fecha y hora tal como la manda la API. Se observaron dos
            formatos en produccion: `"2026-01-01 10:00:00"` (sin zona) y
            `"2026-11-25T15:40:10.000Z"` (ISO 8601 con `Z`). Se guarda como
            viene; para ordenar o filtrar usar `timestamp`, que es unix en
            segundos y no cambia de formato.
        timestamp: Segundos unix de la vela
        open, high, low, close: Precios de la vela
        volume: Volumen operado en la vela
    """

    datetime: str = ""
    timestamp: int = 0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoricalBar":
        data = _as_dict(data)
        return cls(
            datetime=data.get("datetime", ""),
            timestamp=int(data.get("timestamp") or 0),
            open=data.get("open") or 0.0,
            high=data.get("high") or 0.0,
            low=data.get("low") or 0.0,
            close=data.get("close") or 0.0,
            volume=data.get("volume") or 0.0,
        )


@dataclass
class HistoricalBars:
    """Serie historica de un activo."""

    symbol: str = ""
    market: str = ""
    total_bars: int = 0
    bars: list[HistoricalBar] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoricalBars":
        data = _as_dict(data)
        return cls(
            symbol=data.get("symbol", ""),
            market=data.get("market", ""),
            total_bars=int(data.get("total_bars") or 0),
            bars=[HistoricalBar.from_dict(item) for item in _as_list(data.get("bars"))],
        )


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------


@dataclass
class AssetTradingInfo:
    """Condiciones de negociacion de un activo."""

    lot_size: float = 0.0
    minimum_investment: float = 0.0
    minimum_quantity: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetTradingInfo":
        data = _as_dict(data)
        return cls(
            lot_size=data.get("lot_size") or 0.0,
            minimum_investment=data.get("minimum_investment") or 0.0,
            minimum_quantity=data.get("minimum_quantity") or 0.0,
        )


@dataclass
class AssetDetail:
    """Datos de un activo y sus condiciones de negociacion."""

    symbol: str = ""
    name: str = ""
    asset_type: str = ""
    market: str = ""
    country: str = ""
    currency: str = ""
    default_settlement_term: str = ""
    trading_info: AssetTradingInfo = field(default_factory=AssetTradingInfo)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetDetail":
        data = _as_dict(data)
        return cls(
            symbol=data.get("symbol", ""),
            name=data.get("name", ""),
            asset_type=data.get("asset_type", ""),
            market=data.get("market", ""),
            country=data.get("country", ""),
            currency=data.get("currency", ""),
            default_settlement_term=data.get("default_settlement_term", ""),
            trading_info=AssetTradingInfo.from_dict(_as_dict(data.get("trading_info"))),
        )


@dataclass
class AssetType:
    """Tipo de activo disponible para filtros."""

    id: str = ""
    name: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetType":
        data = _as_dict(data)
        return cls(id=data.get("id", ""), name=data.get("name", ""))


@dataclass
class AssetPanel:
    """Panel de trading disponible para filtros."""

    id: str = ""
    name: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetPanel":
        data = _as_dict(data)
        return cls(id=data.get("id", ""), name=data.get("name", ""))


# ---------------------------------------------------------------------------
# Cuenta
# ---------------------------------------------------------------------------


@dataclass
class SettlementTotals:
    """Importes por plazo de liquidacion."""

    t0: float = 0.0
    t1: float = 0.0
    t2: float = 0.0
    t3: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SettlementTotals":
        data = _as_dict(data)
        return cls(
            t0=data.get("t0") or 0.0,
            t1=data.get("t1") or 0.0,
            t2=data.get("t2") or 0.0,
            t3=data.get("t3") or 0.0,
        )


@dataclass
class Balance:
    """Saldo de una moneda, separado por plazo."""

    currency: str = ""
    totals: SettlementTotals = field(default_factory=SettlementTotals)
    available: SettlementTotals = field(default_factory=SettlementTotals)
    committed: SettlementTotals = field(default_factory=SettlementTotals)
    available_for_withdrawal: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Balance":
        data = _as_dict(data)
        return cls(
            currency=data.get("currency", ""),
            totals=SettlementTotals.from_dict(_as_dict(data.get("totals"))),
            available=SettlementTotals.from_dict(_as_dict(data.get("available"))),
            committed=SettlementTotals.from_dict(_as_dict(data.get("committed"))),
            available_for_withdrawal=data.get("available_for_withdrawal") or 0.0,
        )


@dataclass
class AccountBalances:
    """Saldos de la cuenta en pesos y en dolares."""

    ars: Balance = field(default_factory=Balance)
    usd: Balance = field(default_factory=Balance)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AccountBalances":
        data = _as_dict(data)
        return cls(
            ars=Balance.from_dict(_as_dict(data.get("ars"))),
            usd=Balance.from_dict(_as_dict(data.get("usd"))),
        )


@dataclass
class PositionAvailability:
    """Cantidades disponibles, retenidas y pendientes de una posicion."""

    quantity_available: float = 0.0
    quantity_held: float = 0.0
    quantity_pending: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PositionAvailability":
        data = _as_dict(data)
        return cls(
            quantity_available=data.get("quantity_available") or 0.0,
            quantity_held=data.get("quantity_held") or 0.0,
            quantity_pending=data.get("quantity_pending") or 0.0,
        )


@dataclass
class CostBasis:
    """Costo de entrada de una posicion."""

    average_entry_price: float = 0.0
    days_held: int = 0
    entry_date: str | None = None
    total_cost: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CostBasis":
        data = _as_dict(data)
        return cls(
            average_entry_price=data.get("average_entry_price") or 0.0,
            days_held=int(data.get("days_held") or 0),
            entry_date=data.get("entry_date"),
            total_cost=data.get("total_cost") or 0.0,
        )


@dataclass
class Instrument:
    """Instrumento financiero segun la API."""

    symbol: str = ""
    name: str = ""
    type: str = ""
    asset_class: str = ""
    country: str | None = None
    currency: str = ""
    exchange: str = ""
    lot_size: float = 0.0
    minimum_quantity: float = 0.0
    tradable: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Instrument":
        data = _as_dict(data)
        return cls(
            symbol=data.get("symbol", ""),
            name=data.get("name", ""),
            type=data.get("type", ""),
            asset_class=data.get("asset_class", ""),
            country=data.get("country"),
            currency=data.get("currency", ""),
            exchange=data.get("exchange", ""),
            lot_size=data.get("lot_size") or 0.0,
            minimum_quantity=data.get("minimum_quantity") or 0.0,
            tradable=bool(data.get("tradable")),
        )


@dataclass
class MarketValue:
    """Valor de mercado de una posicion."""

    current_price: float = 0.0
    price_change: float = 0.0
    price_change_percent: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MarketValue":
        data = _as_dict(data)
        return cls(
            current_price=data.get("current_price") or 0.0,
            price_change=data.get("price_change") or 0.0,
            price_change_percent=data.get("price_change_percent") or 0.0,
        )


@dataclass
class ProfitLoss:
    """Resultado no realizado de una posicion."""

    unrealized_pl: float = 0.0
    unrealized_pl_percent: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProfitLoss":
        data = _as_dict(data)
        return cls(
            unrealized_pl=data.get("unrealized_pl") or 0.0,
            unrealized_pl_percent=data.get("unrealized_pl_percent") or 0.0,
        )


@dataclass
class Position:
    """
    Posicion de la cartera.

    `parent_instrument` aparece en derivados (por ejemplo opciones) y apunta al
    activo subyacente; es None en el resto de los casos.
    """

    instrument: Instrument = field(default_factory=Instrument)
    parent_instrument: Instrument | None = None
    quantity: float = 0.0
    availability: PositionAvailability = field(default_factory=PositionAvailability)
    cost_basis: CostBasis = field(default_factory=CostBasis)
    market_value: MarketValue = field(default_factory=MarketValue)
    profit_loss: ProfitLoss = field(default_factory=ProfitLoss)
    portfolio_weight_percent: float = 0.0
    is_accredited: bool = False
    maturity_date: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Position":
        data = _as_dict(data)
        parent = data.get("parent_instrument")
        return cls(
            instrument=Instrument.from_dict(_as_dict(data.get("instrument"))),
            parent_instrument=Instrument.from_dict(parent) if isinstance(parent, dict) else None,
            quantity=data.get("quantity") or 0.0,
            availability=PositionAvailability.from_dict(_as_dict(data.get("availability"))),
            cost_basis=CostBasis.from_dict(_as_dict(data.get("cost_basis"))),
            market_value=MarketValue.from_dict(_as_dict(data.get("market_value"))),
            profit_loss=ProfitLoss.from_dict(_as_dict(data.get("profit_loss"))),
            portfolio_weight_percent=data.get("portfolio_weight_percent") or 0.0,
            is_accredited=bool(data.get("is_accredited")),
            maturity_date=data.get("maturity_date"),
        )


@dataclass
class Portfolio:
    """Cartera consolidada de una cuenta."""

    account: str = ""
    currency: str = ""
    positions: list[Position] = field(default_factory=list)
    positions_count: int = 0
    total_market_value: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Portfolio":
        data = _as_dict(data)
        return cls(
            account=data.get("account", ""),
            currency=data.get("currency", ""),
            positions=[Position.from_dict(item) for item in _as_list(data.get("positions"))],
            positions_count=int(data.get("positions_count") or 0),
            total_market_value=data.get("total_market_value") or 0.0,
        )


@dataclass
class ActivityFees:
    """Comisiones y cargos de un movimiento de cuenta."""

    commission: float = 0.0
    other: float = 0.0
    vat: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActivityFees":
        data = _as_dict(data)
        return cls(
            commission=data.get("commission") or 0.0,
            other=data.get("other") or 0.0,
            vat=data.get("vat") or 0.0,
        )


@dataclass
class Activity:
    """Movimiento de cuenta (deposito, retiro, operacion, renta, etc.)."""

    id: str = ""
    ticket_id: str = ""
    activity_type: str = ""
    activity_type_id: int = 0
    account_type: str = ""
    currency: str = ""
    status: str = ""
    qty: float = 0.0
    price: float = 0.0
    net_amount: float = 0.0
    fees: ActivityFees = field(default_factory=ActivityFees)
    trade_date: str = ""
    settlement_date: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Activity":
        data = _as_dict(data)
        return cls(
            id=str(data.get("id", "")),
            ticket_id=data.get("ticket_id", ""),
            activity_type=data.get("activity_type", ""),
            activity_type_id=int(data.get("activity_type_id") or 0),
            account_type=data.get("account_type", ""),
            currency=data.get("currency", ""),
            status=data.get("status", ""),
            qty=data.get("qty") or 0.0,
            price=data.get("price") or 0.0,
            net_amount=data.get("net_amount") or 0.0,
            fees=ActivityFees.from_dict(_as_dict(data.get("fees"))),
            trade_date=data.get("trade_date", ""),
            settlement_date=data.get("settlement_date", ""),
        )


@dataclass
class OperationLeg:
    """Datos de la orden o de la ejecucion de una operacion."""

    amount: float = 0.0
    price: float = 0.0
    qty: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OperationLeg":
        data = _as_dict(data)
        return cls(
            amount=data.get("amount") or 0.0,
            price=data.get("price") or 0.0,
            qty=data.get("qty") or 0.0,
        )


@dataclass
class Operation:
    """
    Operacion de trading con su orden original y su ejecucion.

    `order` es lo pedido y `executed` lo efectivamente ejecutado.
    """

    order_id: str = ""
    ticket_id: str = ""
    symbol: str = ""
    description: str = ""
    type: str = ""
    asset_type: str | None = None
    currency: str = ""
    term: str = ""
    status: str = ""
    order_date: str = ""
    execution_date: str = ""
    order: OperationLeg = field(default_factory=OperationLeg)
    executed: OperationLeg = field(default_factory=OperationLeg)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Operation":
        data = _as_dict(data)
        return cls(
            order_id=str(data.get("order_id", "")),
            ticket_id=data.get("ticket_id", ""),
            symbol=data.get("symbol", ""),
            description=data.get("description", ""),
            type=data.get("type", ""),
            asset_type=data.get("asset_type"),
            currency=data.get("currency", ""),
            term=data.get("term", ""),
            status=data.get("status", ""),
            order_date=data.get("order_date", ""),
            execution_date=data.get("execution_date", ""),
            order=OperationLeg.from_dict(_as_dict(data.get("order"))),
            executed=OperationLeg.from_dict(_as_dict(data.get("executed"))),
        )


@dataclass
class CashFlow:
    """Depositos y retiros del periodo."""

    deposits_ars: float = 0.0
    deposits_usd: float = 0.0
    withdrawals_ars: float = 0.0
    withdrawals_usd: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CashFlow":
        data = _as_dict(data)
        deposits = _as_dict(data.get("deposits"))
        withdrawals = _as_dict(data.get("withdrawals"))
        return cls(
            deposits_ars=deposits.get("ars") or 0.0,
            deposits_usd=deposits.get("usd") or 0.0,
            withdrawals_ars=withdrawals.get("ars") or 0.0,
            withdrawals_usd=withdrawals.get("usd") or 0.0,
        )


@dataclass
class Equity:
    """Patrimonio de la cuenta valuado en distintas monedas."""

    ars: float = 0.0
    usd_ccl: float = 0.0
    usd_mep: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Equity":
        data = _as_dict(data)
        return cls(
            ars=data.get("ars") or 0.0,
            usd_ccl=data.get("usd_ccl") or 0.0,
            usd_mep=data.get("usd_mep") or 0.0,
        )


@dataclass
class ExchangeRate:
    """Tipos de cambio usados en la valuacion."""

    ccl: float = 0.0
    mep: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExchangeRate":
        data = _as_dict(data)
        return cls(ccl=data.get("ccl") or 0.0, mep=data.get("mep") or 0.0)


@dataclass
class PortfolioHistoryPoint:
    """Punto diario de la evolucion de la cuenta."""

    date: str = ""
    cash_flow: CashFlow = field(default_factory=CashFlow)
    equity: Equity = field(default_factory=Equity)
    exchange_rate: ExchangeRate = field(default_factory=ExchangeRate)
    has_pledged_collateral: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PortfolioHistoryPoint":
        data = _as_dict(data)
        return cls(
            date=data.get("date", ""),
            cash_flow=CashFlow.from_dict(_as_dict(data.get("cash_flow"))),
            equity=Equity.from_dict(_as_dict(data.get("equity"))),
            exchange_rate=ExchangeRate.from_dict(_as_dict(data.get("exchange_rate"))),
            has_pledged_collateral=bool(data.get("has_pledged_collateral")),
        )


@dataclass
class PortfolioHistory:
    """
    Evolucion historica de la cuenta.

    `status` es `complete` o `partial`: si es `partial`, `missing_dates` dice
    que dias no pudo valuar la API.
    """

    account: str = ""
    status: str = ""
    history: list[PortfolioHistoryPoint] = field(default_factory=list)
    missing_dates: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PortfolioHistory":
        data = _as_dict(data)
        return cls(
            account=data.get("account", ""),
            status=data.get("status", ""),
            history=[
                PortfolioHistoryPoint.from_dict(item) for item in _as_list(data.get("history"))
            ],
            missing_dates=[str(item) for item in _as_list(data.get("missing_dates"))],
        )


# ---------------------------------------------------------------------------
# Ordenes
# ---------------------------------------------------------------------------


@dataclass
class OperationMessage:
    """Mensaje de la API sobre una orden o transaccion."""

    code: str = ""
    message: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OperationMessage":
        data = _as_dict(data)
        return cls(
            code=str(data.get("code", "")),
            message=data.get("message", ""),
        )


@dataclass
class OrderResult:
    """
    Resultado de dar de alta una orden.

    Attributes:
        order_id: Identificador de la orden creada
        successful_purchase: True si la compra se ejecuto o quedo aceptada
        messages: Mensajes de la API, incluidos los rechazos
    """

    order_id: str = ""
    successful_purchase: bool = False
    messages: list[OperationMessage] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrderResult":
        data = _as_dict(data)
        return cls(
            order_id=str(data.get("order_id", "")),
            successful_purchase=bool(data.get("successful_purchase")),
            messages=_messages(data),
        )


@dataclass
class MoneyAmount:
    """Importe con su moneda."""

    currency: str = ""
    value: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MoneyAmount":
        data = _as_dict(data)
        return cls(currency=data.get("currency", ""), value=data.get("value") or 0.0)


@dataclass
class RegulatoryFees:
    """Cargos regulatorios de una orden."""

    market_fee: MoneyAmount = field(default_factory=MoneyAmount)
    vat: MoneyAmount = field(default_factory=MoneyAmount)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegulatoryFees":
        data = _as_dict(data)
        return cls(
            market_fee=MoneyAmount.from_dict(_as_dict(data.get("market_fee"))),
            vat=MoneyAmount.from_dict(_as_dict(data.get("vat"))),
        )


@dataclass
class OrderEstimate:
    """Estimacion de costos antes de enviar una orden."""

    amount: MoneyAmount = field(default_factory=MoneyAmount)
    commission: MoneyAmount = field(default_factory=MoneyAmount)
    regulatory_fees: RegulatoryFees = field(default_factory=RegulatoryFees)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrderEstimate":
        data = _as_dict(data)
        return cls(
            amount=MoneyAmount.from_dict(_as_dict(data.get("amount"))),
            commission=MoneyAmount.from_dict(_as_dict(data.get("commission"))),
            regulatory_fees=RegulatoryFees.from_dict(_as_dict(data.get("regulatory_fees"))),
        )


@dataclass
class CancelResult:
    """Resultado de cancelar una orden o una transaccion."""

    cancelled: bool = False
    order_id: str = ""
    status: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CancelResult":
        data = _as_dict(data)
        return cls(
            cancelled=bool(data.get("cancelled")),
            order_id=str(data.get("order_id", "")),
            status=data.get("status", ""),
        )


# ---------------------------------------------------------------------------
# Cauciones
# ---------------------------------------------------------------------------


@dataclass
class RepoTerm:
    """Plazo de caucion disponible."""

    term_id: int = 0
    term_days: int = 0
    due_date: str = ""
    min_amount: float = 0.0
    max_amount: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoTerm":
        data = _as_dict(data)
        return cls(
            term_id=int(data.get("term_id") or 0),
            term_days=int(data.get("term_days") or 0),
            due_date=data.get("due_date", ""),
            min_amount=data.get("min_amount") or 0.0,
            max_amount=data.get("max_amount") or 0.0,
        )


@dataclass
class RepoRateAmount:
    """Tasa e importe de un lado del libro de cauciones."""

    rate: float = 0.0
    amount: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoRateAmount":
        data = _as_dict(data)
        return cls(rate=data.get("rate") or 0.0, amount=data.get("amount") or 0.0)


@dataclass
class RepoQuote:
    """Oferta del libro de cauciones."""

    position: int = 0
    bid: RepoRateAmount = field(default_factory=RepoRateAmount)
    ask: RepoRateAmount = field(default_factory=RepoRateAmount)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoQuote":
        data = _as_dict(data)
        return cls(
            position=int(data.get("position") or 0),
            bid=RepoRateAmount.from_dict(_as_dict(data.get("bid"))),
            ask=RepoRateAmount.from_dict(_as_dict(data.get("ask"))),
        )


@dataclass
class RepoEstimate:
    """Estimacion de costos de una caucion."""

    amount: float = 0.0
    commission_currency: str = ""
    commission_type: str = ""
    fee_type: str = ""
    vat_amount: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoEstimate":
        data = _as_dict(data)
        return cls(
            amount=data.get("amount") or 0.0,
            commission_currency=data.get("commission_currency", ""),
            commission_type=data.get("commission_type", ""),
            fee_type=data.get("fee_type", ""),
            vat_amount=data.get("vat_amount") or 0.0,
        )


@dataclass
class RepoOrderResult:
    """Resultado de tomar una caucion."""

    order_id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoOrderResult":
        data = _as_dict(data)
        return cls(order_id=str(data.get("order_id", "")))


# ---------------------------------------------------------------------------
# FCI
# ---------------------------------------------------------------------------


@dataclass
class FundOperationResult:
    """Resultado de suscribir o rescatar un FCI."""

    transaction_id: str | None = None
    successful: bool = False
    messages: list[OperationMessage] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FundOperationResult":
        data = _as_dict(data)
        raw_id = data.get("transaction_id")
        return cls(
            transaction_id=str(raw_id) if raw_id is not None else None,
            successful=bool(data.get("successful")),
            messages=_messages(data),
        )


@dataclass
class FundValidationResult:
    """Resultado de validar una operacion de FCI antes de enviarla."""

    valid: bool = False
    messages: list[OperationMessage] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FundValidationResult":
        data = _as_dict(data)
        return cls(valid=bool(data.get("valid")), messages=_messages(data))


@dataclass
class FundCancelResult:
    """Resultado de cancelar una suscripcion o rescate de FCI."""

    cancelled: bool = False
    status: str = ""
    transaction_id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FundCancelResult":
        data = _as_dict(data)
        return cls(
            cancelled=bool(data.get("cancelled")),
            status=data.get("status", ""),
            transaction_id=str(data.get("transaction_id", "")),
        )


# ---------------------------------------------------------------------------
# Watchlists
# ---------------------------------------------------------------------------


@dataclass
class WatchlistQuote:
    """Cotizacion resumida de un item de watchlist."""

    last_price: float | None = None
    change_percent: float | None = None
    best_bid: float | None = None
    best_bid_size: float | None = None
    best_ask: float | None = None
    best_ask_size: float | None = None
    average_price: float | None = None
    currency: str | None = None
    volume: float | None = None
    traded_quantity: float | None = None
    traded_amount: float | None = None
    last_updated: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WatchlistQuote":
        data = _as_dict(data)
        return cls(
            last_price=data.get("last_price"),
            change_percent=data.get("change_percent"),
            best_bid=data.get("best_bid"),
            best_bid_size=data.get("best_bid_size"),
            best_ask=data.get("best_ask"),
            best_ask_size=data.get("best_ask_size"),
            average_price=data.get("average_price"),
            currency=data.get("currency"),
            volume=data.get("volume"),
            traded_quantity=data.get("traded_quantity"),
            traded_amount=data.get("traded_amount"),
            last_updated=data.get("last_updated"),
        )


@dataclass
class WatchlistItem:
    """Activo dentro de una watchlist."""

    symbol: str = ""
    market: str | None = None
    name: str | None = None
    asset_type: str | None = None
    settlement_term: str | None = None
    quote: WatchlistQuote = field(default_factory=WatchlistQuote)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WatchlistItem":
        data = _as_dict(data)
        return cls(
            symbol=data.get("symbol", ""),
            market=data.get("market"),
            name=data.get("name"),
            asset_type=data.get("asset_type"),
            settlement_term=data.get("settlement_term"),
            quote=WatchlistQuote.from_dict(_as_dict(data.get("quote"))),
        )


@dataclass
class Watchlist:
    """Lista de favoritos con sus items y cotizaciones."""

    id: int = 0
    name: str | None = None
    items_count: int = 0
    items: list[WatchlistItem] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Watchlist":
        data = _as_dict(data)
        return cls(
            id=int(data.get("id") or 0),
            name=data.get("name"),
            items_count=int(data.get("items_count") or 0),
            items=[WatchlistItem.from_dict(item) for item in _as_list(data.get("items"))],
        )


@dataclass
class WatchlistItemAdded:
    """Resultado de agregar un activo a una watchlist."""

    watchlist_id: int = 0
    symbol: str = ""
    market: str = ""
    added: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WatchlistItemAdded":
        data = _as_dict(data)
        return cls(
            watchlist_id=int(data.get("watchlist_id") or 0),
            symbol=data.get("symbol", ""),
            market=data.get("market", ""),
            added=bool(data.get("added")),
        )


@dataclass
class WatchlistItemRemoved:
    """Resultado de quitar un activo de una watchlist."""

    watchlist_id: int = 0
    symbol: str = ""
    market: str | None = None
    removed: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WatchlistItemRemoved":
        data = _as_dict(data)
        return cls(
            watchlist_id=int(data.get("watchlist_id") or 0),
            symbol=data.get("symbol", ""),
            market=data.get("market"),
            removed=bool(data.get("removed")),
        )


@dataclass
class WatchlistRenamed:
    """Resultado de renombrar una watchlist."""

    id: int = 0
    name: str = ""
    renamed: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WatchlistRenamed":
        data = _as_dict(data)
        return cls(
            id=int(data.get("id") or 0),
            name=data.get("name", ""),
            renamed=bool(data.get("renamed")),
        )


@dataclass
class WatchlistDeleted:
    """Resultado de eliminar una watchlist."""

    id: int = 0
    deleted: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WatchlistDeleted":
        data = _as_dict(data)
        return cls(id=int(data.get("id") or 0), deleted=bool(data.get("deleted")))


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


@dataclass
class StreamLevel:
    """
    Nivel de precio de un mensaje del WebSocket.

    Attributes:
        side: BID (compra) u OFFER (venta)
        price: Precio del nivel
        size: Cantidad disponible a ese precio
        position: Numero de nivel dentro de su lado (1 es el mejor)
    """

    side: str = ""
    price: float = 0.0
    size: float = 0.0
    position: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamLevel":
        data = _as_dict(data)
        return cls(
            side=data.get("T", ""),
            price=data.get("P") or 0.0,
            size=data.get("X") or 0.0,
            position=int(data.get("N") or 0),
        )


@dataclass
class StreamQuoteMessage:
    """Mensaje de puntas (type=Q): mejor compra y mejor venta."""

    symbol: str = ""
    market: str = ""
    term: str = ""
    datetime: str = ""
    levels: list[StreamLevel] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamQuoteMessage":
        data = _as_dict(data)
        return cls(
            symbol=data.get("S", ""),
            market=data.get("M", ""),
            term=data.get("T", ""),
            datetime=data.get("D", ""),
            levels=[StreamLevel.from_dict(item) for item in _as_list(data.get("V"))],
        )

    @property
    def bid(self) -> StreamLevel | None:
        """Mejor punta de compra, si vino en el mensaje."""
        return next((level for level in self.levels if level.side == "BID"), None)

    @property
    def offer(self) -> StreamLevel | None:
        """Mejor punta de venta, si vino en el mensaje."""
        return next((level for level in self.levels if level.side == "OFFER"), None)


@dataclass
class StreamOrderBookMessage:
    """Mensaje de profundidad (type=B): hasta 5 niveles por lado."""

    symbol: str = ""
    market: str = ""
    term: str = ""
    datetime: str = ""
    levels: list[StreamLevel] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamOrderBookMessage":
        data = _as_dict(data)
        return cls(
            symbol=data.get("S", ""),
            market=data.get("M", ""),
            term=data.get("T", ""),
            datetime=data.get("D", ""),
            levels=[StreamLevel.from_dict(item) for item in _as_list(data.get("V"))],
        )


@dataclass
class StreamTradeMessage:
    """
    Mensaje de operaciones (type=T).

    Attributes:
        last_price: Ultimo precio operado
        change_percent: Variacion porcentual del dia
        traded_quantity: Nominales operados en el dia, acumulado
        traded_amount: Monto operado en el dia, acumulado
        last_quantity: Cantidad de la operacion que genero el mensaje
    """

    symbol: str = ""
    market: str = ""
    term: str = ""
    datetime: str = ""
    last_price: float = 0.0
    change_percent: float = 0.0
    traded_quantity: float = 0.0
    traded_amount: float = 0.0
    last_quantity: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamTradeMessage":
        data = _as_dict(data)
        return cls(
            symbol=data.get("S", ""),
            market=data.get("M", ""),
            term=data.get("T", ""),
            datetime=data.get("D", ""),
            last_price=data.get("P") or 0.0,
            change_percent=data.get("V") or 0.0,
            traded_quantity=data.get("TS") or 0.0,
            traded_amount=data.get("TP") or 0.0,
            last_quantity=data.get("X") or 0.0,
        )
