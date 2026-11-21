# Cliente REST para la API de IOL Inversiones (v1)

import uuid
from datetime import date
from typing import Any

import httpx

from .auth import TokenManager
from .constants import (
    API_BASE_URL,
    DEFAULT_COUNTRY,
    DEFAULT_MARKET,
    DEFAULT_ORDER_SETTLEMENT_TERM,
    DEFAULT_SETTLEMENT_TERM,
    DEFAULT_TIMEOUT,
    USER_AGENT,
)
from .exceptions import IOLAPIError, IOLConnectionError, IOLValidationError
from .models import (
    AccountBalances,
    Activity,
    AssetDetail,
    AssetPanel,
    AssetType,
    CancelResult,
    FundCancelResult,
    FundOperationResult,
    FundValidationResult,
    HealthStatus,
    HistoricalBars,
    MarketDepth,
    MarketQuote,
    Operation,
    OptionQuote,
    OrderEstimate,
    OrderResult,
    Portfolio,
    PortfolioHistory,
    RepoEstimate,
    RepoOrderResult,
    RepoQuote,
    RepoTerm,
    ScreenerEntry,
    Watchlist,
    WatchlistDeleted,
    WatchlistItemAdded,
    WatchlistItemRemoved,
    WatchlistRenamed,
)

__all__ = ["IOLClient"]

ORDER_IDEMPOTENCY_HEADER = "X-Idempotency-Key"

# Codigos de estado que ameritan un unico reintento automatico de autenticacion.
AUTH_RETRY_STATUSES = (401,)


class IOLClient:
    """
    Cliente para la API de IOL Inversiones.

    Se usa como context manager para liberar las conexiones HTTP:

    ```python
    with IOLClient("usuario", "password") as client:
        cotizacion = client.get_market_quote("GGAL")
        print(cotizacion.prices.current)
    ```

    Todos los metodos tipados tienen su version `_raw()` que devuelve el `dict`
    del campo `data` sin transformar.

    Attributes:
        base_url: URL base de la API
        timeout: Timeout por defecto de cada request, en segundos
    """

    def __init__(
        self,
        username: str,
        password: str,
        *,
        base_url: str = API_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._owns_client = client is None
        self._http = client or httpx.Client(timeout=timeout)
        self._tokens = TokenManager(username, password, http_client=self._http)

    def __enter__(self) -> "IOLClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        """Cierra el cliente HTTP si lo creo esta instancia."""
        if self._owns_client:
            self._http.close()

    # ------------------------------------------------------------------
    # Autenticacion
    # ------------------------------------------------------------------

    def get_access_token(self) -> str:
        """
        Devuelve el access token vigente, renovandolo si hace falta.

        Sirve para reutilizar la sesion HTTP en el WebSocket o en otra
        herramienta. No lo loguees ni lo persistas en texto plano.

        Returns:
            El JWT para el header Authorization
        """
        return self._tokens.get_access_token()

    def test_authentication(self) -> bool:
        """
        Verifica que las credenciales funcionan.

        Hace una request autenticada barata. Si preferis el detalle del error,
        usa `get_access_token()` y captura la excepcion.

        Returns:
            True si la API acepta la sesion
        """
        try:
            self._get_data("GET", "/broker/assets/types", params={"country": DEFAULT_COUNTRY})
        except IOLAPIError:
            return False
        return True

    # ------------------------------------------------------------------
    # Transporte
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        """Headers comunes a toda request autenticada."""
        return {
            "Authorization": f"Bearer {self._tokens.get_access_token()}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        """
        Ejecuta una request y devuelve el sobre completo de la API.

        Un 401 se reintenta una sola vez con un token renovado: la request fue
        rechazada antes de ejecutarse, asi que reintentarla no duplica efectos.
        El resto de los errores no se reintentan para no arriesgar operaciones.

        Args:
            method: Verbo HTTP
            path: Path relativo a `base_url`
            params: Query string
            json: Cuerpo JSON
            headers: Headers adicionales
            authenticated: Si la request lleva token

        Returns:
            El sobre `{meta, data, error}` como dict

        Raises:
            IOLAPIError: Cualquier error devuelto por la API o de conexion
        """
        url = f"{self.base_url}{path}"
        request_headers = dict(headers or {})
        attempt = 0

        while True:
            if authenticated:
                request_headers.update(self._headers())
            try:
                response = self._http.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=request_headers,
                    timeout=self.timeout,
                )
            except httpx.HTTPError as exc:
                raise IOLConnectionError(f"No se pudo conectar con {url}: {exc}") from exc

            payload = self._parse_payload(response)
            if authenticated and response.status_code in AUTH_RETRY_STATUSES and attempt == 0:
                attempt += 1
                self._tokens.invalidate()
                continue

            if response.status_code >= 400 or payload.get("error"):
                raise IOLAPIError.from_envelope(payload, response.status_code)

            return payload

    @staticmethod
    def _parse_payload(response: httpx.Response) -> dict[str, Any]:
        """Devuelve el JSON de la respuesta, o un sobre de error si no es JSON."""
        try:
            payload = response.json()
        except ValueError:
            return {"error": {"message": response.text or "Respuesta no JSON"}}
        return payload if isinstance(payload, dict) else {"data": payload}

    def _get_data(self, method: str, path: str, **kwargs) -> Any:
        """Ejecuta la request y devuelve solo el campo `data`."""
        return self._request(method, path, **kwargs).get("data")

    # ------------------------------------------------------------------
    # Estado del servicio
    # ------------------------------------------------------------------

    def get_health_status(self) -> HealthStatus:
        """
        Consulta el estado del servicio de la API.

        Returns:
            HealthStatus con version, uptime y estado
        """
        data = self._get_data("GET", "/health", authenticated=False)
        return HealthStatus.from_dict(data or {})

    def get_health_status_raw(self) -> dict[str, Any]:
        """Version JSON de `get_health_status`."""
        return self._get_data("GET", "/health", authenticated=False) or {}

    # ------------------------------------------------------------------
    # Datos de mercado
    # ------------------------------------------------------------------

    def get_market_quote(
        self,
        symbol: str,
        market: str = DEFAULT_MARKET,
        term: str = DEFAULT_SETTLEMENT_TERM,
    ) -> MarketQuote:
        """
        Cotizacion de mercado de un activo.

        Args:
            symbol: Simbolo del activo (por ejemplo GGAL)
            market: Mercado segun `Markets`
            term: Plazo de liquidacion segun `SettlementTerms`

        Returns:
            MarketQuote con precios, variacion y volumen
        """
        data = self.get_market_quote_raw(symbol, market, term)
        return MarketQuote.from_dict(data)

    def get_market_quote_raw(
        self,
        symbol: str,
        market: str = DEFAULT_MARKET,
        term: str = DEFAULT_SETTLEMENT_TERM,
    ) -> dict[str, Any]:
        """Version JSON de `get_market_quote`."""
        return (
            self._get_data(
                "GET",
                f"/broker/market-data/{symbol}/quote",
                params={"market": market, "term": term},
            )
            or {}
        )

    def get_market_depth(
        self,
        symbol: str,
        market: str = DEFAULT_MARKET,
        term: str = DEFAULT_SETTLEMENT_TERM,
    ) -> MarketDepth:
        """
        Profundidad del libro de ordenes de un activo.

        Args:
            symbol: Simbolo del activo
            market: Mercado segun `Markets`
            term: Plazo de liquidacion

        Returns:
            MarketDepth con las ofertas de compra y de venta
        """
        return MarketDepth.from_dict(self.get_market_depth_raw(symbol, market, term))

    def get_market_depth_raw(
        self,
        symbol: str,
        market: str = DEFAULT_MARKET,
        term: str = DEFAULT_SETTLEMENT_TERM,
    ) -> dict[str, Any]:
        """Version JSON de `get_market_depth`."""
        return (
            self._get_data(
                "GET",
                f"/broker/market-data/{symbol}/depth",
                params={"market": market, "term": term},
            )
            or {}
        )

    def get_screener_quotes(
        self,
        asset_type: str,
        panel: str,
        country: str = DEFAULT_COUNTRY,
        term: str = DEFAULT_SETTLEMENT_TERM,
    ) -> list[ScreenerEntry]:
        """
        Cotizaciones de un panel de un tipo de activo.

        Equivale a las cotizaciones masivas y a los paneles de la API v2, pero en
        una sola llamada.

        Args:
            asset_type: Id de tipo de activo, de `get_asset_types()`
            panel: Id de panel, de `get_asset_panels()`
            country: Pais segun `Countries`
            term: Plazo de liquidacion

        Returns:
            Lista de ScreenerEntry con instrumento, precios y punta del libro
        """
        return [
            ScreenerEntry.from_dict(item)
            for item in self.get_screener_quotes_raw(asset_type, panel, country, term)
        ]

    def get_screener_quotes_raw(
        self,
        asset_type: str,
        panel: str,
        country: str = DEFAULT_COUNTRY,
        term: str = DEFAULT_SETTLEMENT_TERM,
    ) -> list[dict[str, Any]]:
        """Version JSON de `get_screener_quotes`."""
        return (
            self._get_data(
                "GET",
                "/broker/market-data/screener",
                params={
                    "country": country,
                    "asset_type": asset_type,
                    "panel": panel,
                    "term": term,
                },
            )
            or []
        )

    def get_option_chain(
        self,
        symbol: str,
        market: str = DEFAULT_MARKET,
    ) -> list[OptionQuote]:
        """
        Cadena de opciones de un titulo.

        Args:
            symbol: Simbolo del activo subyacente
            market: Mercado segun `Markets`

        Returns:
            Lista de OptionQuote con strike, tipo y punta del libro
        """
        return [OptionQuote.from_dict(item) for item in self.get_option_chain_raw(symbol, market)]

    def get_option_chain_raw(
        self,
        symbol: str,
        market: str = DEFAULT_MARKET,
    ) -> list[dict[str, Any]]:
        """Version JSON de `get_option_chain`."""
        return (
            self._get_data(
                "GET",
                f"/broker/market-data/{symbol}/options",
                params={"market": market},
            )
            or []
        )

    def get_historical_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        market: str = DEFAULT_MARKET,
    ) -> HistoricalBars:
        """
        Serie historica OHLCV de un activo.

        Args:
            symbol: Simbolo del activo
            start: Desde, con formato `YYYY-MM-DD HH:MM:SS`
            end: Hasta, con formato `YYYY-MM-DD HH:MM:SS`
            market: Mercado segun `Markets`

        Returns:
            HistoricalBars con la serie y el total de velas
        """
        return HistoricalBars.from_dict(self.get_historical_bars_raw(symbol, start, end, market))

    def get_historical_bars_raw(
        self,
        symbol: str,
        start: str,
        end: str,
        market: str = DEFAULT_MARKET,
    ) -> dict[str, Any]:
        """Version JSON de `get_historical_bars`."""
        return (
            self._get_data(
                "GET",
                f"/broker/market-data/{symbol}/bars",
                params={"market": market, "from": start, "to": end},
            )
            or {}
        )

    # ------------------------------------------------------------------
    # Cauciones (repos)
    # ------------------------------------------------------------------

    def get_repo_terms(self, currency: str = "ARS") -> list[RepoTerm]:
        """
        Plazos de caucion disponibles.

        Args:
            currency: Moneda de la caucion, ARS o USD

        Returns:
            Lista de RepoTerm
        """
        return [RepoTerm.from_dict(item) for item in self.get_repo_terms_raw(currency)]

    def get_repo_terms_raw(self, currency: str = "ARS") -> list[dict[str, Any]]:
        """Version JSON de `get_repo_terms`."""
        return (
            self._get_data("GET", "/broker/market-data/repos/terms", params={"currency": currency})
            or []
        )

    def get_repo_quotes(self, term_id: int, currency: str = "ARS") -> list[RepoQuote]:
        """
        Libro de cauciones para un plazo.

        Args:
            term_id: Id de plazo, de `get_repo_terms()`
            currency: Moneda de la caucion, ARS o USD

        Returns:
            Lista de RepoQuote con tasa y monto de cada lado
        """
        return [RepoQuote.from_dict(item) for item in self.get_repo_quotes_raw(term_id, currency)]

    def get_repo_quotes_raw(self, term_id: int, currency: str = "ARS") -> list[dict[str, Any]]:
        """Version JSON de `get_repo_quotes`."""
        return (
            self._get_data(
                "GET",
                "/broker/market-data/repos/quotes",
                params={"term_id": term_id, "currency": currency},
            )
            or []
        )

    def estimate_repo(
        self,
        amount: float,
        term_id: int,
        *,
        currency: str = "ARS",
        price_type: str = "market",
        rate: float | None = None,
    ) -> list[RepoEstimate]:
        """
        Estima los costos de una caucion antes de tomarla.

        Args:
            amount: Importe a colocar
            term_id: Id de plazo, de `get_repo_terms()`
            currency: Moneda, ARS o USD
            price_type: `market` o `limit`
            rate: Tasa, obligatoria cuando `price_type` es `limit`

        Returns:
            Lista de RepoEstimate con comisiones e IVA
        """
        return [
            RepoEstimate.from_dict(item)
            for item in self.estimate_repo_raw(
                amount, term_id, currency=currency, price_type=price_type, rate=rate
            )
        ]

    def estimate_repo_raw(
        self,
        amount: float,
        term_id: int,
        *,
        currency: str = "ARS",
        price_type: str = "market",
        rate: float | None = None,
    ) -> list[dict[str, Any]]:
        """Version JSON de `estimate_repo`."""
        body = self._repo_body(amount, term_id, currency, price_type, rate)
        return self._get_data("POST", "/broker/repos/estimate", json=body) or []

    def create_repo(
        self,
        amount: float,
        term_id: int,
        *,
        currency: str = "ARS",
        price_type: str = "market",
        rate: float | None = None,
        idempotency_key: str | None = None,
    ) -> RepoOrderResult:
        """
        Toma una caucion. Mueve dinero real.

        Args:
            amount: Importe a colocar
            term_id: Id de plazo, de `get_repo_terms()`
            currency: Moneda, ARS o USD
            price_type: `market` o `limit`
            rate: Tasa, obligatoria cuando `price_type` es `limit`
            idempotency_key: UUID v4 para evitar duplicados; se genera si no se pasa

        Returns:
            RepoOrderResult con el id de la caucion tomada
        """
        return RepoOrderResult.from_dict(
            self.create_repo_raw(
                amount,
                term_id,
                currency=currency,
                price_type=price_type,
                rate=rate,
                idempotency_key=idempotency_key,
            )
        )

    def create_repo_raw(
        self,
        amount: float,
        term_id: int,
        *,
        currency: str = "ARS",
        price_type: str = "market",
        rate: float | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Version JSON de `create_repo`."""
        body = self._repo_body(amount, term_id, currency, price_type, rate)
        return (
            self._get_data(
                "POST",
                "/broker/repos",
                json=body,
                headers=self._idempotency_headers(idempotency_key),
            )
            or {}
        )

    def cancel_repo(self, order_id: str) -> CancelResult:
        """
        Cancela una caucion tomada.

        Args:
            order_id: Id devuelto por `create_repo()`

        Returns:
            CancelResult con el estado final
        """
        return CancelResult.from_dict(self.cancel_repo_raw(order_id))

    def cancel_repo_raw(self, order_id: str) -> dict[str, Any]:
        """Version JSON de `cancel_repo`."""
        return self._get_data("DELETE", f"/broker/repos/{order_id}") or {}

    @staticmethod
    def _repo_body(
        amount: float,
        term_id: int,
        currency: str,
        price_type: str,
        rate: float | None,
    ) -> dict[str, Any]:
        """Arma y valida el cuerpo de una request de caucion."""
        if price_type not in ("market", "limit"):
            raise IOLValidationError(f"price_type invalido: {price_type}")
        if price_type == "limit" and not rate:
            raise IOLValidationError("rate es obligatorio cuando price_type es 'limit'")
        body: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
            "price_type": price_type,
            "term_id": term_id,
        }
        if rate is not None:
            body["rate"] = rate
        return body

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    def get_asset(self, symbol: str, market: str = DEFAULT_MARKET) -> AssetDetail:
        """
        Datos de un activo y sus condiciones de negociacion.

        Args:
            symbol: Simbolo del activo
            market: Mercado segun `Markets`

        Returns:
            AssetDetail con tipo, moneda, lamina y minimos
        """
        return AssetDetail.from_dict(self.get_asset_raw(symbol, market))

    def get_asset_raw(self, symbol: str, market: str = DEFAULT_MARKET) -> dict[str, Any]:
        """Version JSON de `get_asset`."""
        return self._get_data("GET", f"/broker/assets/{symbol}", params={"market": market}) or {}

    def get_asset_types(self, country: str = DEFAULT_COUNTRY) -> list[AssetType]:
        """
        Tipos de activo disponibles para filtrar el screener.

        Args:
            country: Pais segun `Countries`

        Returns:
            Lista de AssetType
        """
        return [AssetType.from_dict(item) for item in self.get_asset_types_raw(country)]

    def get_asset_types_raw(self, country: str = DEFAULT_COUNTRY) -> list[dict[str, Any]]:
        """Version JSON de `get_asset_types`."""
        return self._get_data("GET", "/broker/assets/types", params={"country": country}) or []

    def get_asset_panels(self, asset_type: str, country: str = DEFAULT_COUNTRY) -> list[AssetPanel]:
        """
        Paneles de trading disponibles para un tipo de activo.

        Args:
            asset_type: Id de tipo de activo, de `get_asset_types()`
            country: Pais segun `Countries`

        Returns:
            Lista de AssetPanel
        """
        return [
            AssetPanel.from_dict(item) for item in self.get_asset_panels_raw(asset_type, country)
        ]

    def get_asset_panels_raw(
        self, asset_type: str, country: str = DEFAULT_COUNTRY
    ) -> list[dict[str, Any]]:
        """Version JSON de `get_asset_panels`."""
        return (
            self._get_data(
                "GET",
                "/broker/assets/panels",
                params={"country": country, "asset_type": asset_type},
            )
            or []
        )

    # ------------------------------------------------------------------
    # Cuenta
    # ------------------------------------------------------------------

    def get_account_balances(self, country: str = DEFAULT_COUNTRY) -> AccountBalances:
        """
        Saldos de la cuenta en pesos y en dolares.

        Args:
            country: Pais de la cuenta segun `Countries`

        Returns:
            AccountBalances con totales, disponibles y comprometidos por plazo
        """
        return AccountBalances.from_dict(self.get_account_balances_raw(country))

    def get_account_balances_raw(self, country: str = DEFAULT_COUNTRY) -> dict[str, Any]:
        """Version JSON de `get_account_balances`."""
        return self._get_data("GET", f"/broker/accounts/{country}/balances") or {}

    def get_positions(
        self,
        country: str = DEFAULT_COUNTRY,
        valuation_currency: str | None = None,
    ) -> Portfolio:
        """
        Posiciones de la cartera.

        Args:
            country: Pais de la cuenta segun `Countries`
            valuation_currency: Moneda de valuacion: ARS, USD, MEP o CCL

        Returns:
            Portfolio con las posiciones y el valor total de mercado
        """
        return Portfolio.from_dict(self.get_positions_raw(country, valuation_currency))

    def get_positions_raw(
        self,
        country: str = DEFAULT_COUNTRY,
        valuation_currency: str | None = None,
    ) -> dict[str, Any]:
        """Version JSON de `get_positions`."""
        params: dict[str, Any] = {}
        if valuation_currency:
            params["valuation_currency"] = valuation_currency
        return self._get_data("GET", f"/broker/accounts/{country}/positions", params=params) or {}

    def get_account_activities(
        self,
        start_date: str,
        end_date: str,
        *,
        movement_type: str | None = None,
        state: str | None = None,
        country: str | None = None,
        currency: str | None = None,
    ) -> list[Activity]:
        """
        Movimientos de cuenta: depositos, retiros, operaciones, rentas y demas.

        Args:
            start_date: Desde, con formato `YYYY-MM-DD`
            end_date: Hasta, con formato `YYYY-MM-DD`
            movement_type: Filtro de tipo de movimiento
            state: Filtro de estado: all, completed, pending, cancelled
            country: Filtro de pais: all, AR, US
            currency: Filtro de moneda: all, ARS, USD

        Returns:
            Lista de Activity
        """
        return [
            Activity.from_dict(item)
            for item in self.get_account_activities_raw(
                start_date,
                end_date,
                movement_type=movement_type,
                state=state,
                country=country,
                currency=currency,
            )
        ]

    def get_account_activities_raw(
        self,
        start_date: str,
        end_date: str,
        *,
        movement_type: str | None = None,
        state: str | None = None,
        country: str | None = None,
        currency: str | None = None,
    ) -> list[dict[str, Any]]:
        """Version JSON de `get_account_activities`."""
        params: dict[str, Any] = {"start_date": start_date, "end_date": end_date}
        for key, value in (
            ("movement_type", movement_type),
            ("state", state),
            ("country", country),
            ("currency", currency),
        ):
            if value:
                params[key] = value
        return self._get_data("GET", "/broker/accounts/activities", params=params) or []

    def get_trading_operations(
        self,
        start_date: str,
        end_date: str,
        *,
        state: str | None = None,
        transaction_type: str | None = None,
        symbol: str | None = None,
        term: str | None = None,
        asset_type: str | None = None,
        currency: str | None = None,
        country: str | None = None,
        transaction_id: str | None = None,
    ) -> list[Operation]:
        """
        Operaciones de trading del periodo, con lo pedido y lo ejecutado.

        Args:
            start_date: Desde, con formato `YYYY-MM-DD`
            end_date: Hasta, con formato `YYYY-MM-DD`
            state: Filtro de estado: all, completed, pending, cancelled, finished
            transaction_type: purchase, sale, subscription, redemption, repo, ...
            symbol: Filtro por simbolo
            term: Filtro por plazo: T0, T1, T2, T3, T4
            asset_type: Filtro por tipo de activo
            currency: Filtro por moneda
            country: Filtro por pais: all, AR, US
            transaction_id: Filtro por id de transaccion

        Returns:
            Lista de Operation
        """
        return [
            Operation.from_dict(item)
            for item in self.get_trading_operations_raw(
                start_date,
                end_date,
                state=state,
                transaction_type=transaction_type,
                symbol=symbol,
                term=term,
                asset_type=asset_type,
                currency=currency,
                country=country,
                transaction_id=transaction_id,
            )
        ]

    def get_trading_operations_raw(
        self,
        start_date: str,
        end_date: str,
        *,
        state: str | None = None,
        transaction_type: str | None = None,
        symbol: str | None = None,
        term: str | None = None,
        asset_type: str | None = None,
        currency: str | None = None,
        country: str | None = None,
        transaction_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Version JSON de `get_trading_operations`."""
        params: dict[str, Any] = {"start_date": start_date, "end_date": end_date}
        for key, value in (
            ("state", state),
            ("transaction_type", transaction_type),
            ("symbol", symbol),
            ("term", term),
            ("asset_type", asset_type),
            ("currency", currency),
            ("country", country),
            ("transaction_id", transaction_id),
        ):
            if value:
                params[key] = value
        return self._get_data("GET", "/broker/accounts/activities/operations", params=params) or []

    def get_portfolio_history(
        self,
        start_date: str,
        end_date: str,
        country: str = DEFAULT_COUNTRY,
    ) -> PortfolioHistory:
        """
        Evolucion diaria del patrimonio de la cuenta.

        Args:
            start_date: Desde, con formato `YYYY-MM-DD`
            end_date: Hasta, con formato `YYYY-MM-DD`
            country: Pais de la cuenta segun `Countries`

        Returns:
            PortfolioHistory; si `status` es `partial`, revisar `missing_dates`
        """
        return PortfolioHistory.from_dict(
            self.get_portfolio_history_raw(start_date, end_date, country)
        )

    def get_portfolio_history_raw(
        self,
        start_date: str,
        end_date: str,
        country: str = DEFAULT_COUNTRY,
    ) -> dict[str, Any]:
        """Version JSON de `get_portfolio_history`."""
        return (
            self._get_data(
                "GET",
                f"/broker/accounts/{country}/portfolio/history",
                params={"start_date": start_date, "end_date": end_date},
            )
            or {}
        )

    # ------------------------------------------------------------------
    # Ordenes
    # ------------------------------------------------------------------

    def estimate_order(
        self,
        symbol: str,
        side: str,
        *,
        quantity: float | None = None,
        notional: float | None = None,
        market_id: str = DEFAULT_MARKET,
        order_type: str = "market",
        limit_price: float | None = None,
        settlement_term: str | None = None,
        due_date: str | None = None,
    ) -> OrderEstimate:
        """
        Estima comisiones y cargos de una orden antes de enviarla.

        Args:
            symbol: Simbolo del activo
            side: `buy` o `sell`
            quantity: Cantidad de nominales (excluyente con `notional`)
            notional: Monto en moneda (excluyente con `quantity`)
            market_id: Mercado segun `Markets`
            order_type: `limit` o `market`
            limit_price: Precio limite, obligatorio en ordenes limit
            settlement_term: Plazo de liquidacion; por defecto `T1`
            due_date: Vencimiento de la orden, `YYYY-MM-DD`

        Returns:
            OrderEstimate con importe, comision y cargos regulatorios
        """
        return OrderEstimate.from_dict(
            self.estimate_order_raw(
                symbol,
                side,
                quantity=quantity,
                notional=notional,
                market_id=market_id,
                order_type=order_type,
                limit_price=limit_price,
                settlement_term=settlement_term,
                due_date=due_date,
            )
        )

    def estimate_order_raw(
        self,
        symbol: str,
        side: str,
        *,
        quantity: float | None = None,
        notional: float | None = None,
        market_id: str = DEFAULT_MARKET,
        order_type: str = "market",
        limit_price: float | None = None,
        settlement_term: str | None = None,
        due_date: str | None = None,
    ) -> dict[str, Any]:
        """Version JSON de `estimate_order`."""
        body = self._order_body(
            symbol,
            side,
            quantity=quantity,
            notional=notional,
            market_id=market_id,
            order_type=order_type,
            limit_price=limit_price,
            settlement_term=settlement_term,
            due_date=due_date,
        )
        return self._get_data("POST", "/broker/orders/estimate", json=body) or {}

    def create_order(
        self,
        symbol: str,
        side: str,
        *,
        quantity: float | None = None,
        notional: float | None = None,
        market_id: str = DEFAULT_MARKET,
        order_type: str = "market",
        limit_price: float | None = None,
        settlement_term: str | None = None,
        due_date: str | None = None,
        idempotency_key: str | None = None,
    ) -> OrderResult:
        """
        Da de alta una orden. Mueve dinero real.

        `quantity` y `notional` son excluyentes: o se pide por nominales o por
        monto. En ordenes `limit` el precio limite es obligatorio.

        Args:
            symbol: Simbolo del activo
            side: `buy` o `sell`
            quantity: Cantidad de nominales
            notional: Monto en moneda
            market_id: Mercado segun `Markets`
            order_type: `limit` o `market`
            limit_price: Precio limite
            settlement_term: Plazo de liquidacion; por defecto `T1`
            due_date: Vencimiento de la orden, `YYYY-MM-DD`; por defecto hoy
            idempotency_key: UUID v4 para evitar duplicados; se genera si no se pasa

        Returns:
            OrderResult con el id de la orden y los mensajes de la API
        """
        return OrderResult.from_dict(
            self.create_order_raw(
                symbol,
                side,
                quantity=quantity,
                notional=notional,
                market_id=market_id,
                order_type=order_type,
                limit_price=limit_price,
                settlement_term=settlement_term,
                due_date=due_date,
                idempotency_key=idempotency_key,
            )
        )

    def create_order_raw(
        self,
        symbol: str,
        side: str,
        *,
        quantity: float | None = None,
        notional: float | None = None,
        market_id: str = DEFAULT_MARKET,
        order_type: str = "market",
        limit_price: float | None = None,
        settlement_term: str | None = None,
        due_date: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Version JSON de `create_order`."""
        body = self._order_body(
            symbol,
            side,
            quantity=quantity,
            notional=notional,
            market_id=market_id,
            order_type=order_type,
            limit_price=limit_price,
            settlement_term=settlement_term,
            due_date=due_date,
        )
        return (
            self._get_data(
                "POST",
                "/broker/orders",
                json=body,
                headers=self._idempotency_headers(idempotency_key),
            )
            or {}
        )

    def cancel_order(self, order_id: str) -> CancelResult:
        """
        Cancela una orden.

        Args:
            order_id: Id devuelto por `create_order()`

        Returns:
            CancelResult con el estado final
        """
        return CancelResult.from_dict(self.cancel_order_raw(order_id))

    def cancel_order_raw(self, order_id: str) -> dict[str, Any]:
        """Version JSON de `cancel_order`."""
        return self._get_data("DELETE", f"/broker/orders/{order_id}") or {}

    @staticmethod
    def _order_body(
        symbol: str,
        side: str,
        *,
        quantity: float | None,
        notional: float | None,
        market_id: str,
        order_type: str,
        limit_price: float | None,
        settlement_term: str | None,
        due_date: str | None,
    ) -> dict[str, Any]:
        """
        Arma y valida el cuerpo de una orden.

        Valida localmente las reglas del contrato para no mandar a la API una
        orden que va a ser rechazada.
        """
        if side not in ("buy", "sell"):
            raise IOLValidationError(f"side invalido: {side}")
        if order_type not in ("limit", "market"):
            raise IOLValidationError(f"order_type invalido: {order_type}")
        if (quantity is None) == (notional is None):
            raise IOLValidationError("hay que indicar quantity o notional, pero no ambos")
        if order_type == "limit" and not limit_price:
            raise IOLValidationError("limit_price es obligatorio en ordenes 'limit'")
        if settlement_term == "":
            raise IOLValidationError(
                "settlement_term no puede ser vacio: usar None para el default u 'T0'/'T1'"
            )

        body: dict[str, Any] = {
            "symbol": symbol,
            "market_id": market_id,
            "side": side,
            "order_type": order_type,
            "due_date": due_date or date.today().isoformat(),
            # La API responde 400 si falta `settlement_term`, aunque el contrato
            # lo marque como opcional: siempre mandamos uno.
            "settlement_term": (
                settlement_term if settlement_term is not None else DEFAULT_ORDER_SETTLEMENT_TERM
            ),
        }
        if quantity is not None:
            body["quantity"] = quantity
        if notional is not None:
            body["notional"] = notional
        if limit_price is not None:
            body["limit_price"] = limit_price
        return body

    @staticmethod
    def _idempotency_headers(idempotency_key: str | None) -> dict[str, str]:
        """Devuelve el header de idempotencia, generando la clave si falta."""
        return {ORDER_IDEMPOTENCY_HEADER: idempotency_key or str(uuid.uuid4())}

    # ------------------------------------------------------------------
    # Fondos comunes de inversion (FCI)
    # ------------------------------------------------------------------

    def validate_fund_subscription(self, symbol: str, amount: float) -> FundValidationResult:
        """
        Valida una suscripcion a un FCI sin enviarla.

        Args:
            symbol: Simbolo del fondo
            amount: Monto a suscribir

        Returns:
            FundValidationResult con el detalle de la validacion
        """
        return FundValidationResult.from_dict(self.validate_fund_subscription_raw(symbol, amount))

    def validate_fund_subscription_raw(self, symbol: str, amount: float) -> dict[str, Any]:
        """Version JSON de `validate_fund_subscription`."""
        return (
            self._get_data(
                "POST",
                "/broker/mutual-funds/subscriptions/validate",
                json={"symbol": symbol, "amount": amount},
            )
            or {}
        )

    def subscribe_fund(
        self,
        symbol: str,
        amount: float,
        *,
        idempotency_key: str | None = None,
    ) -> FundOperationResult:
        """
        Suscribe a un FCI. Mueve dinero real.

        Args:
            symbol: Simbolo del fondo
            amount: Monto a suscribir
            idempotency_key: UUID v4 para evitar duplicados; se genera si no se pasa

        Returns:
            FundOperationResult con el id de la transaccion
        """
        return FundOperationResult.from_dict(
            self.subscribe_fund_raw(symbol, amount, idempotency_key=idempotency_key)
        )

    def subscribe_fund_raw(
        self,
        symbol: str,
        amount: float,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Version JSON de `subscribe_fund`."""
        return (
            self._get_data(
                "POST",
                "/broker/mutual-funds/subscriptions",
                json={"symbol": symbol, "amount": amount},
                headers=self._idempotency_headers(idempotency_key),
            )
            or {}
        )

    def validate_fund_redemption(
        self,
        symbol: str,
        *,
        quantity: float | None = None,
        redeem_all: bool = False,
    ) -> FundValidationResult:
        """
        Valida un rescate de FCI sin enviarlo.

        Args:
            symbol: Simbolo del fondo
            quantity: Cantidad a rescatar; se ignora si `redeem_all` es True
            redeem_all: True para rescatar la tenencia completa

        Returns:
            FundValidationResult con el detalle de la validacion
        """
        return FundValidationResult.from_dict(
            self.validate_fund_redemption_raw(symbol, quantity=quantity, redeem_all=redeem_all)
        )

    def validate_fund_redemption_raw(
        self,
        symbol: str,
        *,
        quantity: float | None = None,
        redeem_all: bool = False,
    ) -> dict[str, Any]:
        """Version JSON de `validate_fund_redemption`."""
        return (
            self._get_data(
                "POST",
                "/broker/mutual-funds/redemptions/validate",
                json=self._redemption_body(symbol, quantity, redeem_all),
            )
            or {}
        )

    def redeem_fund(
        self,
        symbol: str,
        *,
        quantity: float | None = None,
        redeem_all: bool = False,
        idempotency_key: str | None = None,
    ) -> FundOperationResult:
        """
        Rescata un FCI. Mueve dinero real.

        Args:
            symbol: Simbolo del fondo
            quantity: Cantidad a rescatar; se ignora si `redeem_all` es True
            redeem_all: True para rescatar la tenencia completa
            idempotency_key: UUID v4 para evitar duplicados; se genera si no se pasa

        Returns:
            FundOperationResult con el id de la transaccion
        """
        return FundOperationResult.from_dict(
            self.redeem_fund_raw(
                symbol,
                quantity=quantity,
                redeem_all=redeem_all,
                idempotency_key=idempotency_key,
            )
        )

    def redeem_fund_raw(
        self,
        symbol: str,
        *,
        quantity: float | None = None,
        redeem_all: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Version JSON de `redeem_fund`."""
        return (
            self._get_data(
                "POST",
                "/broker/mutual-funds/redemptions",
                json=self._redemption_body(symbol, quantity, redeem_all),
                headers=self._idempotency_headers(idempotency_key),
            )
            or {}
        )

    @staticmethod
    def _redemption_body(
        symbol: str,
        quantity: float | None,
        redeem_all: bool,
    ) -> dict[str, Any]:
        """Arma y valida el cuerpo de un rescate de FCI."""
        if not redeem_all and quantity is None:
            raise IOLValidationError("hay que indicar quantity o redeem_all=True en un rescate")
        body: dict[str, Any] = {"symbol": symbol, "redeem_all": redeem_all}
        if quantity is not None:
            body["quantity"] = quantity
        return body

    def cancel_fund_operation(self, transaction_id: str) -> FundCancelResult:
        """
        Cancela una suscripcion o rescate de FCI pendiente.

        Args:
            transaction_id: Id devuelto por `subscribe_fund()` o `redeem_fund()`

        Returns:
            FundCancelResult con el estado final
        """
        return FundCancelResult.from_dict(self.cancel_fund_operation_raw(transaction_id))

    def cancel_fund_operation_raw(self, transaction_id: str) -> dict[str, Any]:
        """Version JSON de `cancel_fund_operation`."""
        return self._get_data("DELETE", f"/broker/mutual-funds/{transaction_id}") or {}

    # ------------------------------------------------------------------
    # Watchlists (listas de favoritos)
    # ------------------------------------------------------------------

    def get_watchlists(self) -> list[Watchlist]:
        """
        Lista de watchlists de la cuenta con sus cotizaciones.

        Returns:
            Lista de Watchlist
        """
        return [Watchlist.from_dict(item) for item in self.get_watchlists_raw()]

    def get_watchlists_raw(self) -> list[dict[str, Any]]:
        """Version JSON de `get_watchlists`."""
        return self._get_data("GET", "/broker/watchlists") or []

    def get_watchlist(self, watchlist_id: int, term: str | None = None) -> Watchlist:
        """
        Una watchlist por id.

        Args:
            watchlist_id: Id de la watchlist
            term: Plazo con el que se piden las cotizaciones

        Returns:
            Watchlist con sus items
        """
        return Watchlist.from_dict(self.get_watchlist_raw(watchlist_id, term))

    def get_watchlist_raw(self, watchlist_id: int, term: str | None = None) -> dict[str, Any]:
        """Version JSON de `get_watchlist`."""
        params: dict[str, Any] = {}
        if term:
            params["term"] = term
        return self._get_data("GET", f"/broker/watchlists/{watchlist_id}", params=params) or {}

    def create_watchlist(
        self,
        name: str,
        items: list[dict[str, str]] | None = None,
    ) -> Watchlist:
        """
        Crea una watchlist.

        Args:
            name: Nombre de la lista
            items: Items iniciales, cada uno con `symbol` y `market`

        Returns:
            Watchlist creada
        """
        return Watchlist.from_dict(self.create_watchlist_raw(name, items))

    def create_watchlist_raw(
        self,
        name: str,
        items: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Version JSON de `create_watchlist`."""
        body: dict[str, Any] = {"name": name, "items": items or []}
        return self._get_data("POST", "/broker/watchlists", json=body) or {}

    def rename_watchlist(self, watchlist_id: int, name: str) -> WatchlistRenamed:
        """
        Renombra una watchlist.

        Args:
            watchlist_id: Id de la watchlist
            name: Nombre nuevo

        Returns:
            WatchlistRenamed con el resultado
        """
        return WatchlistRenamed.from_dict(self.rename_watchlist_raw(watchlist_id, name))

    def rename_watchlist_raw(self, watchlist_id: int, name: str) -> dict[str, Any]:
        """Version JSON de `rename_watchlist`."""
        return (
            self._get_data("PUT", f"/broker/watchlists/{watchlist_id}", json={"name": name}) or {}
        )

    def delete_watchlist(self, watchlist_id: int) -> WatchlistDeleted:
        """
        Elimina una watchlist.

        Args:
            watchlist_id: Id de la watchlist

        Returns:
            WatchlistDeleted con el resultado
        """
        return WatchlistDeleted.from_dict(self.delete_watchlist_raw(watchlist_id))

    def delete_watchlist_raw(self, watchlist_id: int) -> dict[str, Any]:
        """Version JSON de `delete_watchlist`."""
        return self._get_data("DELETE", f"/broker/watchlists/{watchlist_id}") or {}

    def add_watchlist_item(
        self, watchlist_id: int, symbol: str, market: str = DEFAULT_MARKET
    ) -> WatchlistItemAdded:
        """
        Agrega un activo a una watchlist.

        Args:
            watchlist_id: Id de la watchlist
            symbol: Simbolo del activo
            market: Mercado segun `Markets`

        Returns:
            WatchlistItemAdded con el resultado
        """
        return WatchlistItemAdded.from_dict(
            self.add_watchlist_item_raw(watchlist_id, symbol, market)
        )

    def add_watchlist_item_raw(
        self, watchlist_id: int, symbol: str, market: str = DEFAULT_MARKET
    ) -> dict[str, Any]:
        """Version JSON de `add_watchlist_item`."""
        return (
            self._get_data(
                "POST",
                f"/broker/watchlists/{watchlist_id}/items",
                json={"symbol": symbol, "market": market},
            )
            or {}
        )

    def remove_watchlist_item(
        self,
        watchlist_id: int,
        symbol: str,
        market: str | None = None,
    ) -> WatchlistItemRemoved:
        """
        Quita un activo de una watchlist.

        Args:
            watchlist_id: Id de la watchlist
            symbol: Simbolo del activo
            market: Mercado del activo, si hay que desambiguar

        Returns:
            WatchlistItemRemoved con el resultado
        """
        return WatchlistItemRemoved.from_dict(
            self.remove_watchlist_item_raw(watchlist_id, symbol, market)
        )

    def remove_watchlist_item_raw(
        self,
        watchlist_id: int,
        symbol: str,
        market: str | None = None,
    ) -> dict[str, Any]:
        """Version JSON de `remove_watchlist_item`."""
        params: dict[str, Any] = {}
        if market:
            params["market"] = market
        return (
            self._get_data(
                "DELETE", f"/broker/watchlists/{watchlist_id}/items/{symbol}", params=params
            )
            or {}
        )
