# pyIol2 — Cliente Python para la API de IOL Inversiones (REST v1 + WebSocket)

from .auth import IOLToken, TokenManager
from .client import IOLClient
from .constants import (
    API_BASE_URL,
    AUTH_URL,
    STREAM_BASE_URL,
    Countries,
    GrantTypes,
    Markets,
    SettlementTerms,
    StreamActions,
    StreamChannels,
    StreamMessageTypes,
)
from .exceptions import (
    IOLAPIError,
    IOLAuthenticationError,
    IOLConnectionError,
    IOLNotFoundError,
    IOLRateLimitError,
    IOLServerError,
    IOLStreamError,
    IOLValidationError,
)
from .models import (
    AccountBalances,
    Activity,
    AssetDetail,
    AssetPanel,
    AssetType,
    Balance,
    CancelResult,
    FundCancelResult,
    FundOperationResult,
    FundValidationResult,
    HealthStatus,
    HistoricalBar,
    HistoricalBars,
    Instrument,
    IOLMeta,
    IOLResponse,
    MarketDepth,
    MarketQuote,
    Operation,
    OperationMessage,
    OptionQuote,
    OrderEstimate,
    OrderResult,
    Portfolio,
    PortfolioHistory,
    Position,
    RepoEstimate,
    RepoOrderResult,
    RepoQuote,
    RepoTerm,
    ScreenerEntry,
    StreamLevel,
    StreamOrderBookMessage,
    StreamQuoteMessage,
    StreamTradeMessage,
    Watchlist,
    WatchlistItem,
)
from .stream import IOLStreamClient, StreamMessage

__version__ = "0.1.0-beta.1"

__all__ = [
    "__version__",
    # Clientes
    "IOLClient",
    "IOLStreamClient",
    "StreamMessage",
    # Autenticacion
    "IOLToken",
    "TokenManager",
    # Constantes
    "API_BASE_URL",
    "AUTH_URL",
    "STREAM_BASE_URL",
    "Countries",
    "GrantTypes",
    "Markets",
    "SettlementTerms",
    "StreamActions",
    "StreamChannels",
    "StreamMessageTypes",
    # Excepciones
    "IOLAPIError",
    "IOLAuthenticationError",
    "IOLConnectionError",
    "IOLNotFoundError",
    "IOLRateLimitError",
    "IOLServerError",
    "IOLStreamError",
    "IOLValidationError",
    # Modelos: sobre de la API
    "IOLMeta",
    "IOLResponse",
    "HealthStatus",
    # Modelos: datos de mercado
    "MarketQuote",
    "MarketDepth",
    "ScreenerEntry",
    "OptionQuote",
    "HistoricalBar",
    "HistoricalBars",
    # Modelos: assets
    "AssetDetail",
    "AssetType",
    "AssetPanel",
    # Modelos: cuenta
    "AccountBalances",
    "Balance",
    "Instrument",
    "Portfolio",
    "Position",
    "Activity",
    "Operation",
    "PortfolioHistory",
    # Modelos: ordenes
    "OrderEstimate",
    "OrderResult",
    "OperationMessage",
    "CancelResult",
    # Modelos: cauciones
    "RepoEstimate",
    "RepoOrderResult",
    "RepoQuote",
    "RepoTerm",
    # Modelos: FCI
    "FundCancelResult",
    "FundOperationResult",
    "FundValidationResult",
    # Modelos: watchlists
    "Watchlist",
    "WatchlistItem",
    # Modelos: streaming
    "StreamLevel",
    "StreamOrderBookMessage",
    "StreamQuoteMessage",
    "StreamTradeMessage",
]
