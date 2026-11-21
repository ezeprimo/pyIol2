"""Tests de los modelos: parseo de las respuestas documentadas por la API."""

import json

from pyIol2 import (
    AccountBalances,
    Activity,
    AssetDetail,
    HealthStatus,
    HistoricalBars,
    IOLMeta,
    IOLResponse,
    MarketDepth,
    MarketQuote,
    Operation,
    OptionQuote,
    Portfolio,
    PortfolioHistory,
    RepoQuote,
    ScreenerEntry,
    StreamLevel,
    StreamMessage,
    StreamOrderBookMessage,
    StreamQuoteMessage,
    StreamTradeMessage,
    Watchlist,
)
from tests.conftest import (
    ACTIVITIES_PAYLOAD,
    ASSET_PAYLOAD,
    BALANCES_PAYLOAD,
    BARS_PAYLOAD,
    DEPTH_PAYLOAD,
    HISTORY_PAYLOAD,
    OPERATIONS_PAYLOAD,
    OPTIONS_PAYLOAD,
    POSITIONS_PAYLOAD,
    QUOTE_PAYLOAD,
    REPO_QUOTES_PAYLOAD,
    SCREENER_PAYLOAD,
    WATCHLIST_PAYLOAD,
    envelope,
)


def test_iol_response_expone_meta_y_trace_id():
    response = IOLResponse.from_dict(envelope({"a": 1}, trace_id="trace-42", total_count=7))

    assert response.data == {"a": 1}
    assert response.trace_id == "trace-42"
    assert response.meta.total_count == 7
    assert response.error is None


def test_iol_meta_tolera_payload_vacio():
    meta = IOLMeta.from_dict({})

    assert meta.status_code == 0
    assert meta.trace_id == ""


def test_market_quote_parseo_completo():
    quote = MarketQuote.from_dict(QUOTE_PAYLOAD)

    assert quote.symbol == "GGAL"
    assert quote.settlement_term == "T0"
    assert quote.prices.open == 5990.0
    assert quote.prices.previous_close == 6010.0
    assert quote.change.amount == 20.0
    assert quote.volume.amount == 150000000.0
    assert quote.maturity_date is None


def test_market_depth_parseo_de_niveles():
    depth = MarketDepth.from_dict(DEPTH_PAYLOAD)

    assert depth.bids[1].position == 2
    assert depth.bids[1].price == 6020.0
    assert depth.asks[0].size == 150.0


def test_screener_entry_anida_instrumento_precios_y_libro():
    entry = ScreenerEntry.from_dict(SCREENER_PAYLOAD[0])

    assert entry.instrument.symbol == "GGAL"
    assert entry.quotes.last == 6030.0
    assert entry.book.bid.size == 100.0


def test_option_quote_parsea_contrato():
    option = OptionQuote.from_dict(OPTIONS_PAYLOAD[0])

    assert option.symbol == "GFGC6030F"
    assert option.option.strike_price == 6030.0
    assert option.option.state == "abierta"


def test_historical_bars_parsea_serie():
    bars = HistoricalBars.from_dict(BARS_PAYLOAD)

    assert bars.total_bars == 2
    assert len(bars.bars) == 2
    assert bars.bars[0].timestamp == 1767261600
    assert bars.bars[1].volume == 900.0


def test_balances_parsea_totales_disponibles_y_comprometidos():
    balances = AccountBalances.from_dict(BALANCES_PAYLOAD)

    assert balances.ars.currency == "ARS"
    assert balances.ars.totals.t1 == 2000.0
    assert balances.ars.committed.t0 == 100.0
    assert balances.ars.available_for_withdrawal == 800.0
    assert balances.usd.available.t1 == 20.0


def test_portfolio_parsea_posicion_completa():
    portfolio = Portfolio.from_dict(POSITIONS_PAYLOAD)

    assert portfolio.account == "123456"
    assert portfolio.positions_count == 1
    position = portfolio.positions[0]
    assert position.instrument.exchange == "BCBA"
    assert position.quantity == 20.0
    assert position.availability.quantity_available == 20.0
    assert position.cost_basis.entry_date == "2025-12-01"
    assert position.market_value.price_change_percent == 0.33
    assert position.portfolio_weight_percent == 100.0


def test_position_con_parent_instrument_lo_parsea():
    payload = json.loads(json.dumps(POSITIONS_PAYLOAD))
    payload["positions"][0]["parent_instrument"] = payload["positions"][0]["instrument"]

    portfolio = Portfolio.from_dict(payload)

    assert portfolio.positions[0].parent_instrument is not None
    assert portfolio.positions[0].parent_instrument.symbol == "GGAL"


def test_activity_parsea_comisiones():
    activity = Activity.from_dict(ACTIVITIES_PAYLOAD[0])

    assert activity.id == "act-1"
    assert activity.activity_type == "Buy"
    assert activity.fees.commission == 150.0
    assert activity.net_amount == -120783.6


def test_operation_parsea_orden_y_ejecucion():
    operation = Operation.from_dict(OPERATIONS_PAYLOAD[0])

    assert operation.order.qty == 20.0
    assert operation.executed.amount == 120600.0
    assert operation.asset_type == "stocks"


def test_portfolio_history_parsea_equity_y_tipo_de_cambio():
    history = PortfolioHistory.from_dict(HISTORY_PAYLOAD)

    point = history.history[0]
    assert point.date == "2025-12-20"
    assert point.equity.ars == 120600.0
    assert point.exchange_rate.ccl == 1200.0
    assert point.has_pledged_collateral is False


def test_repo_quote_parsea_tasas():
    quote = RepoQuote.from_dict(REPO_QUOTES_PAYLOAD[0])

    assert quote.bid.rate == 35.5
    assert quote.ask.amount == 400000.0


def test_watchlist_parsea_items_y_quote():
    watchlist = Watchlist.from_dict(WATCHLIST_PAYLOAD)

    assert watchlist.id == 7
    assert watchlist.items_count == 1
    item = watchlist.items[0]
    assert item.symbol == "GGAL"
    assert item.quote.last_price == 6030.0
    assert item.quote.best_ask_size == 150.0


def test_asset_detail_parsea_trading_info():
    asset = AssetDetail.from_dict(ASSET_PAYLOAD)

    assert asset.asset_type == "stocks"
    assert asset.default_settlement_term == "T0"
    assert asset.trading_info.minimum_investment == 6030.0


def test_health_status_parsea_version():
    health = HealthStatus.from_dict({"status": "ok", "version": "1.0.0", "uptime": 12.5})

    assert health.status == "ok"
    assert health.version == "1.0.0"
    assert health.uptime == 12.5


def test_modelos_toleran_payload_vacio():
    assert MarketQuote.from_dict({}).symbol == ""
    assert Portfolio.from_dict({}).positions == []
    assert HistoricalBars.from_dict({}).bars == []
    assert Watchlist.from_dict({}).items == []


def test_stream_message_parsea_quote():
    payload = {
        "type": "Q",
        "msg": {
            "S": "GGAL",
            "M": "BCBA",
            "T": "T0",
            "D": "2026-01-01T12:00:00-03:00",
            "V": [
                {"T": "BID", "X": 100, "P": 6025.0, "N": 1},
                {"T": "OFFER", "X": 150, "P": 6030.0, "N": 1},
            ],
        },
    }

    message = StreamMessage.from_dict(payload)

    assert message.type == "Q"
    assert message.symbol == "GGAL"
    assert message.market == "BCBA"
    assert message.term == "T0"
    assert message.quote is not None
    assert message.quote.bid is not None
    assert message.quote.bid.price == 6025.0
    assert message.quote.offer is not None
    assert message.quote.offer.size == 150.0
    assert message.raw == payload


def test_stream_quote_message_sin_puntas_no_falla():
    quote = StreamQuoteMessage.from_dict({"S": "GGAL", "V": []})

    assert quote.bid is None
    assert quote.offer is None


def test_stream_message_parsea_order_book():
    payload = {
        "type": "B",
        "msg": {
            "S": "AL30",
            "M": "BCBA",
            "T": "T0",
            "V": [{"T": "BID", "X": 10, "P": 100.0, "N": 1}],
        },
    }

    message = StreamMessage.from_dict(payload)

    assert message.type == "B"
    assert message.symbol == "AL30"
    assert message.order_book is not None
    assert message.order_book.levels[0].side == "BID"
    assert message.trade is None


def test_stream_message_parsea_trades():
    payload = {
        "type": "T",
        "msg": {
            "S": "GGAL",
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

    message = StreamMessage.from_dict(payload)

    assert message.type == "T"
    assert message.trade is not None
    assert message.trade.last_price == 6030.0
    assert message.trade.traded_quantity == 25000
    assert message.trade.traded_amount == 150000000
    assert message.trade.last_quantity == 20


def test_stream_message_desconocido_no_falla():
    message = StreamMessage.from_dict({"type": "Pong", "msg": {"S": "GGAL"}})

    assert message.type == "Pong"
    assert message.quote is None
    assert message.raw["type"] == "Pong"


def test_stream_level_mapea_las_claves_cortas():
    level = StreamLevel.from_dict({"T": "OFFER", "X": 5, "P": 10.5, "N": 3})

    assert level.side == "OFFER"
    assert level.size == 5
    assert level.price == 10.5
    assert level.position == 3


def test_stream_order_book_message_parsea_varios_niveles():
    book = StreamOrderBookMessage.from_dict(
        {"S": "GGAL", "M": "BCBA", "T": "T0", "V": [{"T": "BID", "X": 1, "P": 1.0, "N": 5}]}
    )

    assert book.levels[0].position == 5


def test_stream_trade_message_defaults():
    trade = StreamTradeMessage.from_dict({})

    assert trade.symbol == ""
    assert trade.last_price == 0.0
