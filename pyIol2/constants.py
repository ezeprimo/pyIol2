# Constantes para la API de IOL Inversiones (REST v1 + WebSocket de market data)

# URLs base de la API
API_BASE_URL = "https://api.iolinversiones.com"
AUTH_URL = f"{API_BASE_URL}/auth/token"
STREAM_BASE_URL = "wss://stream-marketdata.invertironline.com"

# Headers por defecto
USER_AGENT = "pyIol2/0.1"

# Vida del access token: la API lo emite por 15 minutos y lo renueva con
# refresh_token. El margen evita usar un token que expira en el camino.
TOKEN_LIFETIME_SECONDS = 15 * 60
TOKEN_SAFETY_MARGIN_SECONDS = 30

# Timeout por defecto de las requests REST, en segundos
DEFAULT_TIMEOUT = 30.0


# Constantes para mercados disponibles.
# A diferencia de la API v2, la v1 usa el codigo de mercado en mayusculas.
class Markets:
    """Mercados disponibles en la API de IOL"""

    BCBA = "BCBA"  # Bolsa de Comercio de Buenos Aires
    NYSE = "NYSE"  # New York Stock Exchange
    NASDAQ = "NASDAQ"  # NASDAQ
    AMEX = "AMEX"  # American Stock Exchange


# Constantes para plazos de liquidacion.
# La v1 solo expone contado inmediato y 24 horas.
class SettlementTerms:
    """Plazos de liquidacion disponibles"""

    T0 = "T0"  # Contado inmediato
    T1 = "T1"  # Liquidacion a 24 horas


# Constantes para tipos de grant del endpoint /auth/token
class GrantTypes:
    """Tipos de grant soportados por /auth/token"""

    PASSWORD = "password"
    REFRESH_TOKEN = "refresh_token"


# Constantes para paises usados en los endpoints de cuenta y de listados.
# A diferencia de la API v2, la v1 usa el codigo corto del pais.
class Countries:
    """Paises disponibles en la API"""

    ARGENTINA = "AR"
    USA = "US"
    ALL = "all"


# Constantes para los canales del WebSocket de market data
class StreamChannels:
    """Canales de datos disponibles en el WebSocket"""

    QUOTES = "quotes"  # Puntas: mejor compra y mejor venta
    ORDER_BOOK = "order_book"  # Profundidad: 5 mejores ofertas por lado
    TRADES = "trades"  # Operaciones: ultimo precio, variacion y volumen


# Tipos de mensaje que llegan por el WebSocket
class StreamMessageTypes:
    """Tipos de mensaje entrantes del WebSocket"""

    QUOTE = "Q"  # Puntas (BID / OFFER)
    ORDER_BOOK = "B"  # Profundidad del libro
    TRADES = "T"  # Operaciones
    ERROR = "Error"  # Error informado por el servidor


# Acciones que acepta el WebSocket
class StreamActions:
    """Acciones de control del WebSocket"""

    AUTH = "auth"
    AUTH_TOKEN = "auth_token"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    UNSUBSCRIBE_ALL = "unsubscribe_all"
    PING = "ping"
    DISCONNECT = "disconnect"


# Limites publicados por el WebSocket
STREAM_MAX_SYMBOLS_PER_CONNECTION = 50
STREAM_MAX_ORDER_BOOK_PER_CONNECTION = 1
STREAM_HEARTBEAT_INTERVAL_SECONDS = 15.0
STREAM_DEFAULT_RECONNECT_DELAY_SECONDS = 1.0
STREAM_MAX_RECONNECT_DELAY_SECONDS = 30.0
STREAM_MAX_RECONNECT_ATTEMPTS = 5

# Lados del libro de ordenes
STREAM_SIDE_BID = "BID"
STREAM_SIDE_OFFER = "OFFER"

# Valores por defecto
DEFAULT_MARKET = Markets.BCBA
DEFAULT_SETTLEMENT_TERM = SettlementTerms.T0
DEFAULT_COUNTRY = Countries.ARGENTINA
