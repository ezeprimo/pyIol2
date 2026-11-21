"""Tests del cliente REST contra un doble de la API."""

import uuid
from datetime import date

import httpx
import pytest

from pyIol2 import (
    IOLAPIError,
    IOLAuthenticationError,
    IOLClient,
    IOLConnectionError,
    IOLNotFoundError,
    IOLServerError,
    IOLValidationError,
    Markets,
    SettlementTerms,
)
from tests.conftest import (
    ACTIVITIES_PAYLOAD,
    ASSET_PAYLOAD,
    BALANCES_PAYLOAD,
    BARS_PAYLOAD,
    DEPTH_PAYLOAD,
    FCI_OPERATION_PAYLOAD,
    HISTORY_PAYLOAD,
    OPERATIONS_PAYLOAD,
    OPTIONS_PAYLOAD,
    ORDER_ESTIMATE_PAYLOAD,
    ORDER_RESULT_PAYLOAD,
    POSITIONS_PAYLOAD,
    QUOTE_PAYLOAD,
    REPO_QUOTES_PAYLOAD,
    REPO_TERMS_PAYLOAD,
    SCREENER_PAYLOAD,
    WATCHLIST_PAYLOAD,
    error_envelope,
)


def test_token_se_pide_una_sola_vez_y_se_usa_en_el_header(client, stub):
    stub.set("GET", "/broker/market-data/GGAL/quote", QUOTE_PAYLOAD)

    client.get_market_quote("GGAL")
    client.get_market_quote("GGAL")

    quote_calls = [r for r in stub.requests if r["path"].endswith("/quote")]
    assert len(quote_calls) == 2
    assert stub.token_calls == 1
    assert quote_calls[0]["headers"]["authorization"] == "Bearer token-1"


def test_health_no_lleva_token(client, stub):
    stub.set("GET", "/health", {"status": "ok", "version": "1.0.0", "uptime": 10})

    health = client.get_health_status()

    assert health.status == "ok"
    assert stub.token_calls == 0
    assert "authorization" not in stub.last("GET", "/health")["headers"]


def test_get_market_quote_arma_path_params_y_modelo(client, stub):
    stub.set("GET", "/broker/market-data/GGAL/quote", QUOTE_PAYLOAD)

    quote = client.get_market_quote("GGAL", Markets.BCBA, SettlementTerms.T0)

    request = stub.last("GET", "/broker/market-data/GGAL/quote")
    assert request["params"] == {"market": "BCBA", "term": "T0"}
    assert quote.symbol == "GGAL"
    assert quote.prices.current == 6030.0
    assert quote.change.percent == 0.33
    assert quote.volume.shares == 25000.0
    assert quote.maturity_date is None


def test_get_market_quote_raw_devuelve_dict(client, stub):
    stub.set("GET", "/broker/market-data/GGAL/quote", QUOTE_PAYLOAD)

    raw = client.get_market_quote_raw("GGAL")

    assert isinstance(raw, dict)
    assert raw["prices"]["current"] == 6030.0


def test_get_market_depth_parsea_libro(client, stub):
    stub.set("GET", "/broker/market-data/GGAL/depth", DEPTH_PAYLOAD)

    depth = client.get_market_depth("GGAL")

    assert [level.position for level in depth.bids] == [1, 2]
    assert depth.asks[0].price == 6030.0


def test_screener_usa_filtros_documentados(client, stub):
    stub.set("GET", "/broker/market-data/screener", SCREENER_PAYLOAD)

    entries = client.get_screener_quotes("stocks", "bluechips", "AR", "T0")

    request = stub.last("GET", "/broker/market-data/screener")
    assert request["params"] == {
        "country": "AR",
        "asset_type": "stocks",
        "panel": "bluechips",
        "term": "T0",
    }
    assert entries[0].instrument.symbol == "GGAL"
    assert entries[0].book.ask.price == 6030.0


def test_get_option_chain_parsea_strike(client, stub):
    stub.set("GET", "/broker/market-data/GGAL/options", OPTIONS_PAYLOAD)

    options = client.get_option_chain("GGAL")

    assert stub.last("GET", "/broker/market-data/GGAL/options")["params"] == {"market": "BCBA"}
    assert options[0].option.strike_price == 6030.0
    assert options[0].option.type == "call"


def test_historical_bars_usa_from_y_to(client, stub):
    stub.set("GET", "/broker/market-data/GGAL/bars", BARS_PAYLOAD)

    bars = client.get_historical_bars("GGAL", "2026-01-01 00:00:00", "2026-01-02 00:00:00")

    assert stub.last("GET", "/broker/market-data/GGAL/bars")["params"] == {
        "market": "BCBA",
        "from": "2026-01-01 00:00:00",
        "to": "2026-01-02 00:00:00",
    }
    assert bars.total_bars == 2
    assert bars.bars[1].close == 6028.0


def test_get_account_balances_parsea_plazos(client, stub):
    stub.set("GET", "/broker/accounts/AR/balances", BALANCES_PAYLOAD)

    balances = client.get_account_balances("AR")

    assert balances.ars.totals.t1 == 2000.0
    assert balances.ars.available.t0 == 900.0
    assert balances.usd.available_for_withdrawal == 5.0


def test_get_positions_parsea_instrumento_y_costo(client, stub):
    stub.set("GET", "/broker/accounts/AR/positions", POSITIONS_PAYLOAD)

    portfolio = client.get_positions("AR", "ARS")

    assert stub.last("GET", "/broker/accounts/AR/positions")["params"] == {
        "valuation_currency": "ARS"
    }
    position = portfolio.positions[0]
    assert position.instrument.symbol == "GGAL"
    assert position.instrument.tradable is True
    assert position.cost_basis.average_entry_price == 5500.0
    assert position.profit_loss.unrealized_pl == 10600.0
    assert position.parent_instrument is None
    assert portfolio.total_market_value == 120600.0


def test_get_account_activities_manda_filtros_solo_si_se_pasan(client, stub):
    stub.set("GET", "/broker/accounts/activities", ACTIVITIES_PAYLOAD)

    activities = client.get_account_activities(
        "2025-12-01", "2025-12-31", state="completed", currency="ARS"
    )

    assert stub.last("GET", "/broker/accounts/activities")["params"] == {
        "start_date": "2025-12-01",
        "end_date": "2025-12-31",
        "state": "completed",
        "currency": "ARS",
    }
    assert activities[0].activity_type == "Buy"
    assert activities[0].fees.vat == 33.6


def test_get_trading_operations_parsea_orden_y_ejecucion(client, stub):
    stub.set("GET", "/broker/accounts/activities/operations", OPERATIONS_PAYLOAD)

    operations = client.get_trading_operations("2025-12-01", "2025-12-31", symbol="GGAL")

    assert stub.last("GET", "/broker/accounts/activities/operations")["params"]["symbol"] == "GGAL"
    assert operations[0].order.qty == 20.0
    assert operations[0].executed.price == 6030.0
    assert operations[0].asset_type == "stocks"


def test_get_portfolio_history_expone_estado_y_faltantes(client, stub):
    stub.set("GET", "/broker/accounts/AR/portfolio/history", HISTORY_PAYLOAD)

    history = client.get_portfolio_history("2025-12-01", "2025-12-31", "AR")

    assert history.status == "complete"
    assert history.missing_dates == []
    point = history.history[0]
    assert point.equity.usd_mep == 101.2
    assert point.cash_flow.deposits_ars == 100.0


def test_repo_terms_y_quotes(client, stub):
    stub.set("GET", "/broker/market-data/repos/terms", REPO_TERMS_PAYLOAD)
    stub.set("GET", "/broker/market-data/repos/quotes", REPO_QUOTES_PAYLOAD)

    terms = client.get_repo_terms("ARS")
    quotes = client.get_repo_quotes(1, "ARS")

    assert terms[0].term_days == 1
    assert quotes[0].bid.rate == 35.5
    assert stub.last("GET", "/broker/market-data/repos/quotes")["params"] == {
        "term_id": "1",
        "currency": "ARS",
    }


def test_estimate_repo_limit_sin_tasa_falla_sin_llamar_a_la_api(client, stub):
    with pytest.raises(IOLValidationError):
        client.estimate_repo(1000.0, 1, price_type="limit")

    assert all(not r["path"].endswith("/repos/estimate") for r in stub.requests)


def test_create_order_manda_idempotencia_y_vencimiento_por_defecto(client, stub):
    stub.set("POST", "/broker/orders", ORDER_RESULT_PAYLOAD, status=201)

    result = client.create_order("GGAL", "buy", quantity=10)

    request = stub.last("POST", "/broker/orders")
    assert request["body"] == {
        "symbol": "GGAL",
        "market_id": "BCBA",
        "side": "buy",
        "order_type": "market",
        "due_date": date.today().isoformat(),
        "quantity": 10,
        "settlement_term": "T1",
    }
    key = request["headers"]["x-idempotency-key"]
    assert uuid.UUID(key).version == 4
    assert result.order_id == "ord-1"
    assert result.successful_purchase is True


def test_create_order_acepta_clave_de_idempotencia_explicita(client, stub):
    stub.set("POST", "/broker/orders", ORDER_RESULT_PAYLOAD, status=201)

    client.create_order("GGAL", "sell", notional=50000, idempotency_key="clave-fija")

    request = stub.last("POST", "/broker/orders")
    assert request["headers"]["x-idempotency-key"] == "clave-fija"
    assert request["body"]["notional"] == 50000
    assert "quantity" not in request["body"]


def test_create_order_valida_quantity_y_notional(client, stub):
    with pytest.raises(IOLValidationError):
        client.create_order("GGAL", "buy")

    with pytest.raises(IOLValidationError):
        client.create_order("GGAL", "buy", quantity=1, notional=1)

    assert all(not r["path"].endswith("/broker/orders") for r in stub.requests)


def test_create_order_limit_exige_precio(client, stub):
    with pytest.raises(IOLValidationError):
        client.create_order("GGAL", "buy", quantity=1, order_type="limit")


def test_create_order_rechaza_side_invalido(client, stub):
    with pytest.raises(IOLValidationError):
        client.create_order("GGAL", "hold", quantity=1)


def test_estimate_order_parsea_comisiones(client, stub):
    stub.set("POST", "/broker/orders/estimate", ORDER_ESTIMATE_PAYLOAD)

    estimate = client.estimate_order(
        "GGAL", "buy", quantity=20, order_type="limit", limit_price=6030
    )

    assert estimate.amount.value == 120600.0
    assert estimate.regulatory_fees.market_fee.value == 12.0
    assert estimate.regulatory_fees.vat.value == 33.6


def test_cancel_order_usa_delete(client, stub):
    stub.set(
        "DELETE",
        "/broker/orders/ord-1",
        {"cancelled": True, "order_id": "ord-1", "status": "cancelled"},
    )

    result = client.cancel_order("ord-1")

    assert result.cancelled is True
    assert stub.last("DELETE", "/broker/orders/ord-1")["method"] == "DELETE"


def test_fci_suscripcion_valida_y_envia(client, stub):
    stub.set(
        "POST",
        "/broker/mutual-funds/subscriptions/validate",
        {"valid": True, "messages": [{"code": "0", "message": "ok"}]},
    )
    stub.set("POST", "/broker/mutual-funds/subscriptions", FCI_OPERATION_PAYLOAD, status=201)

    validation = client.validate_fund_subscription("IOLCAMA", 1000.0)
    result = client.subscribe_fund("IOLCAMA", 1000.0)

    assert validation.valid is True
    assert result.transaction_id == "tx-1"
    assert stub.last("POST", "/broker/mutual-funds/subscriptions")["body"] == {
        "symbol": "IOLCAMA",
        "amount": 1000.0,
    }


def test_fci_rescate_exige_cantidad_o_redeem_all(client, stub):
    with pytest.raises(IOLValidationError):
        client.redeem_fund("IOLCAMA")

    stub.set("POST", "/broker/mutual-funds/redemptions", FCI_OPERATION_PAYLOAD, status=201)
    client.redeem_fund("IOLCAMA", redeem_all=True)

    assert stub.last("POST", "/broker/mutual-funds/redemptions")["body"] == {
        "symbol": "IOLCAMA",
        "redeem_all": True,
    }


def test_asset_types_panels_y_detalle(client, stub):
    stub.set("GET", "/broker/assets/types", [{"id": "stocks", "name": "Acciones"}])
    stub.set("GET", "/broker/assets/panels", [{"id": "bluechips", "name": "Blue chips"}])
    stub.set("GET", "/broker/assets/GGAL", ASSET_PAYLOAD)

    types = client.get_asset_types("AR")
    panels = client.get_asset_panels("stocks", "AR")
    asset = client.get_asset("GGAL")

    assert types[0].id == "stocks"
    assert panels[0].id == "bluechips"
    assert asset.trading_info.minimum_quantity == 1
    assert stub.last("GET", "/broker/assets/panels")["params"] == {
        "country": "AR",
        "asset_type": "stocks",
    }


def test_watchlists_crud(client, stub):
    stub.set("GET", "/broker/watchlists", [WATCHLIST_PAYLOAD])
    stub.set("GET", "/broker/watchlists/7", WATCHLIST_PAYLOAD)
    stub.set("POST", "/broker/watchlists", WATCHLIST_PAYLOAD, status=201)
    stub.set("PUT", "/broker/watchlists/7", {"id": 7, "name": "Nueva", "renamed": True})
    stub.set("DELETE", "/broker/watchlists/7", {"id": 7, "deleted": True})
    stub.set(
        "POST",
        "/broker/watchlists/7/items",
        {"watchlist_id": 7, "symbol": "GGAL", "market": "BCBA", "added": True},
    )
    stub.set(
        "DELETE",
        "/broker/watchlists/7/items/GGAL",
        {"watchlist_id": 7, "symbol": "GGAL", "market": "BCBA", "removed": True},
    )

    assert client.get_watchlists()[0].items[0].quote.last_price == 6030.0
    assert client.get_watchlist(7, "T0").name == "Seguimiento"
    assert client.create_watchlist("Seguimiento", [{"symbol": "GGAL", "market": "BCBA"}]).id == 7
    assert client.rename_watchlist(7, "Nueva").renamed is True
    assert client.delete_watchlist(7).deleted is True
    assert client.add_watchlist_item(7, "GGAL").added is True
    assert client.remove_watchlist_item(7, "GGAL").removed is True
    assert stub.last("GET", "/broker/watchlists/7")["params"] == {"term": "T0"}


def test_error_400_se_traduce_a_validacion_con_trace_id(client, stub):
    stub.set(
        "POST",
        "/broker/orders",
        error_envelope("Falta el precio limite", code=1002, status=400, trace_id="trace-9"),
        status=400,
        raw=True,
    )

    with pytest.raises(IOLValidationError) as error:
        client.create_order("GGAL", "buy", quantity=1)

    assert error.value.status_code == 400
    assert error.value.code == 1002
    assert error.value.trace_id == "trace-9"


def test_error_404_se_traduce_a_not_found(client, stub):
    with pytest.raises(IOLNotFoundError):
        client.get_market_quote("NOEXISTE")


def test_error_500_se_traduce_a_server_error(client, stub):
    stub.set(
        "GET",
        "/broker/market-data/GGAL/quote",
        error_envelope("Error interno", status=500),
        status=500,
        raw=True,
    )

    with pytest.raises(IOLServerError):
        client.get_market_quote("GGAL")


def test_error_con_mensaje_de_la_api_y_sin_meta(client, stub):
    stub.set(
        "GET",
        "/broker/market-data/GGAL/quote",
        {"error": {"message": "simbolo invalido"}},
        status=400,
        raw=True,
    )

    with pytest.raises(IOLAPIError) as error:
        client.get_market_quote("GGAL")

    assert "simbolo invalido" in str(error.value)


def test_401_renueva_token_y_reintenta_una_sola_vez(client, stub):
    stub.set_sequence(
        "GET",
        "/broker/market-data/GGAL/quote",
        [(401, error_envelope("vencido", status=401)), (200, QUOTE_PAYLOAD)],
    )

    quote = client.get_market_quote("GGAL")

    quote_calls = [r for r in stub.requests if r["path"].endswith("/quote")]
    assert len(quote_calls) == 2
    assert stub.token_calls == 2
    assert quote_calls[0]["headers"]["authorization"] == "Bearer token-1"
    assert quote_calls[1]["headers"]["authorization"] == "Bearer token-2"
    assert quote.symbol == "GGAL"


def test_401_persistente_levanta_authentication_error(client, stub):
    stub.set(
        "GET",
        "/broker/market-data/GGAL/quote",
        error_envelope("Token invalido", status=401),
        status=401,
        raw=True,
    )

    with pytest.raises(IOLAuthenticationError):
        client.get_market_quote("GGAL")

    quote_calls = [r for r in stub.requests if r["path"].endswith("/quote")]
    assert len(quote_calls) == 2


def test_close_no_falla_con_cliente_externo(stub):

    http = httpx.Client(transport=stub.transport())
    client = IOLClient("u", "p", client=http)
    client.close()
    # El cliente externo sigue usable: IOLClient no lo cierra.
    assert not http.is_closed
    http.close()


def test_error_de_transporte_se_reporta_como_connection_error(stub):
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red")

    http = httpx.Client(transport=httpx.MockTransport(boom))
    client = IOLClient("u", "p", client=http)

    with pytest.raises(IOLConnectionError) as error:
        client.get_market_quote("GGAL")

    assert "No se pudo conectar" in str(error.value)


def test_get_access_token_devuelve_el_token_vigente(client, stub):
    stub.set("GET", "/broker/market-data/GGAL/quote", QUOTE_PAYLOAD)

    token = client.get_access_token()
    client.get_market_quote("GGAL")

    assert token == "token-1"
    assert stub.token_calls == 1


def test_test_authentication_devuelve_true_con_sesion_valida(client, stub):
    stub.set("GET", "/broker/assets/types", [{"id": "stocks", "name": "Acciones"}])

    assert client.test_authentication() is True


def test_test_authentication_devuelve_false_si_rechazan_la_sesion(stub, make_client):
    stub.set(
        "GET",
        "/broker/assets/types",
        error_envelope("Token invalido", status=401),
        status=401,
        raw=True,
    )
    client = make_client()

    assert client.test_authentication() is False


def test_create_order_manda_settlement_term_por_defecto(client, stub):
    # La API responde 400 sin settlement_term, aunque el contrato lo diga opcional.
    stub.set("POST", "/broker/orders", ORDER_RESULT_PAYLOAD, status=201)

    client.create_order("GGAL", "buy", quantity=1)

    assert stub.last("POST", "/broker/orders")["body"]["settlement_term"] == "T1"


def test_create_order_respeta_settlement_term_explicito(client, stub):
    stub.set("POST", "/broker/orders", ORDER_RESULT_PAYLOAD, status=201)

    client.create_order("GGAL", "buy", quantity=1, settlement_term="T0")

    assert stub.last("POST", "/broker/orders")["body"]["settlement_term"] == "T0"


def test_el_default_de_streaming_no_cambia_por_el_de_las_ordenes(client, stub):
    # Hallazgo del review: el plazo de ordenes es T1, el de market data sigue T0.
    stub.set("GET", "/broker/market-data/GGAL/quote", QUOTE_PAYLOAD)

    client.get_market_quote("GGAL")

    assert stub.last("GET", "/broker/market-data/GGAL/quote")["params"]["term"] == "T0"


def test_settlement_term_vacio_es_invalido(client, stub):
    with pytest.raises(IOLValidationError):
        client.create_order("GGAL", "buy", quantity=1, settlement_term="")

    assert all(not r["path"].endswith("/broker/orders") for r in stub.requests)


def test_settlement_term_none_usa_el_default_de_ordenes(client, stub):
    stub.set("POST", "/broker/orders", ORDER_RESULT_PAYLOAD, status=201)

    client.create_order("GGAL", "buy", quantity=1, settlement_term=None)

    assert stub.last("POST", "/broker/orders")["body"]["settlement_term"] == "T1"
