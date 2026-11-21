"""Tests de las constantes: los valores son los que viajan por el cable."""

from pyIol2 import (
    Countries,
    GrantTypes,
    Markets,
    SettlementTerms,
    StreamActions,
    StreamChannels,
    StreamMessageTypes,
    constants,
)


def test_mercados_van_en_mayusculas_como_pide_la_v1():
    assert Markets.BCBA == "BCBA"
    assert Markets.NYSE == "NYSE"
    assert Markets.NASDAQ == "NASDAQ"
    assert Markets.AMEX == "AMEX"


def test_plazos_solo_t0_y_t1():
    assert SettlementTerms.T0 == "T0"
    assert SettlementTerms.T1 == "T1"


def test_paises_usan_el_codigo_corto():
    assert Countries.ARGENTINA == "AR"
    assert Countries.USA == "US"
    assert Countries.ALL == "all"


def test_grant_types_documentados():
    assert GrantTypes.PASSWORD == "password"
    assert GrantTypes.REFRESH_TOKEN == "refresh_token"


def test_canales_y_acciones_del_websocket():
    assert StreamChannels.QUOTES == "quotes"
    assert StreamChannels.ORDER_BOOK == "order_book"
    assert StreamChannels.TRADES == "trades"
    assert StreamActions.AUTH_TOKEN == "auth_token"
    assert StreamActions.SUBSCRIBE == "subscribe"
    assert StreamActions.PING == "ping"


def test_tipos_de_mensaje_del_websocket():
    assert StreamMessageTypes.QUOTE == "Q"
    assert StreamMessageTypes.ORDER_BOOK == "B"
    assert StreamMessageTypes.TRADES == "T"
    assert StreamMessageTypes.ERROR == "Error"


def test_limites_del_websocket():
    assert constants.STREAM_MAX_SYMBOLS_PER_CONNECTION == 50
    assert constants.STREAM_MAX_ORDER_BOOK_PER_CONNECTION == 1
    assert constants.STREAM_HEARTBEAT_INTERVAL_SECONDS <= 15


def test_urls_de_la_api():
    assert constants.API_BASE_URL == "https://api.iolinversiones.com"
    assert constants.AUTH_URL.endswith("/auth/token")
    assert constants.STREAM_BASE_URL.startswith("wss://")


def test_defaults_coherentes():
    assert constants.DEFAULT_MARKET == Markets.BCBA
    assert constants.DEFAULT_SETTLEMENT_TERM == SettlementTerms.T1
    assert constants.DEFAULT_COUNTRY == Countries.ARGENTINA
