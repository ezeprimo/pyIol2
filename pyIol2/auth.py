# Autenticacion OAuth2 contra la API de IOL Inversiones

import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .constants import (
    AUTH_URL,
    DEFAULT_TIMEOUT,
    TOKEN_LIFETIME_SECONDS,
    TOKEN_SAFETY_MARGIN_SECONDS,
    USER_AGENT,
    GrantTypes,
)
from .exceptions import IOLAPIError, IOLConnectionError

__all__ = ["IOLToken", "TokenManager"]


@dataclass(frozen=True)
class IOLToken:
    """
    Token OAuth2 emitido por /auth/token.

    Attributes:
        access_token: JWT que se envia en el header Authorization
        refresh_token: Token para renovar el access token sin reenviar la clave
        token_type: Tipo de token, siempre "bearer"
        expires_in: Segundos hasta la expiracion informados por la API
        expires_at: Fecha de expiracion informada por la API (ISO 8601)
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = TOKEN_LIFETIME_SECONDS
    expires_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IOLToken":
        """Construye el token desde el campo `data` de la respuesta."""
        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            token_type=data.get("token_type", "bearer"),
            expires_in=int(data.get("expires_in") or TOKEN_LIFETIME_SECONDS),
            expires_at=data.get("expires_at"),
        )


class TokenManager:
    """
    Administra el ciclo de vida del access token de IOL.

    Hace el login inicial con grant `password` y renueva con grant
    `refresh_token` cuando el token esta por vencer, sin volver a mandar la
    contrasena. Es seguro para uso concurrente: las renovaciones se serializan
    con un lock para que dos threads no pidan token a la vez.

    Args:
        username: Usuario de IOL
        password: Contrasena de IOL
        http_client: Cliente httpx ya configurado, provisto por IOLClient
        auth_url: URL del endpoint de token
        safety_margin: Segundos de margen antes de considerar el token vencido
    """

    def __init__(
        self,
        username: str,
        password: str,
        *,
        http_client: httpx.Client,
        auth_url: str = AUTH_URL,
        safety_margin: int = TOKEN_SAFETY_MARGIN_SECONDS,
    ):
        self._username = username
        self._password = password
        self._http = http_client
        self._auth_url = auth_url
        self._safety_margin = safety_margin

        self._lock = threading.Lock()
        self._token: IOLToken | None = None
        self._expires_monotonic: float = 0.0

    @property
    def token(self) -> IOLToken | None:
        """Ultimo token obtenido, sin renovarlo."""
        return self._token

    def get_access_token(self) -> str:
        """
        Devuelve un access token valido.

        Renueva el token si no existe o si esta dentro del margen de seguridad.

        Returns:
            El JWT para el header Authorization
        """
        with self._lock:
            if self._token is None:
                self._token = self._request_token(GrantTypes.PASSWORD)
            elif self._is_expired():
                self._token = self._request_token(GrantTypes.REFRESH_TOKEN)
            return self._token.access_token

    def refresh(self) -> IOLToken:
        """
        Fuerza una renovacion y devuelve el token nuevo.

        Si el refresh falla porque el refresh token tambien vencio, reintenta con
        usuario y contrasena.

        Returns:
            El token renovado
        """
        with self._lock:
            try:
                self._token = self._request_token(GrantTypes.REFRESH_TOKEN)
            except IOLAPIError:
                self._token = self._request_token(GrantTypes.PASSWORD)
            return self._token

    def invalidate(self) -> None:
        """Descarta el token actual para que la proxima llamada lo renueve."""
        with self._lock:
            self._token = None
            self._expires_monotonic = 0.0

    def _is_expired(self) -> bool:
        """Indica si el token actual esta vencido o dentro del margen."""
        return time.monotonic() >= self._expires_monotonic

    def _request_token(self, grant_type: str) -> IOLToken:
        """
        Pide un token nuevo a /auth/token.

        Args:
            grant_type: `password` para el login inicial o `refresh_token` para renovar

        Returns:
            El token emitido por la API

        Raises:
            IOLAuthenticationError: Si la API rechaza las credenciales
            IOLAPIError: Si la respuesta no respeta el contrato
        """
        body: dict[str, Any] = {"grant_type": grant_type}
        if grant_type == GrantTypes.REFRESH_TOKEN and self._token is not None:
            body["refresh_token"] = self._token.refresh_token
        else:
            body["username"] = self._username
            body["password"] = self._password

        try:
            response = self._http.post(
                self._auth_url,
                json=body,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=DEFAULT_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise IOLConnectionError(f"No se pudo conectar con {self._auth_url}: {exc}") from exc

        payload = self._parse_payload(response)
        if response.status_code >= 400 or payload.get("error"):
            raise IOLAPIError.from_envelope(payload, response.status_code)

        data = payload.get("data")
        if not isinstance(data, dict) or not data.get("access_token"):
            raise IOLAPIError(
                "La respuesta de /auth/token no incluye access_token",
                status_code=response.status_code,
                payload=payload,
            )

        token = IOLToken.from_dict(data)
        lifetime = token.expires_in - self._safety_margin
        self._expires_monotonic = time.monotonic() + max(lifetime, 1)
        return token

    @staticmethod
    def _parse_payload(response: httpx.Response) -> dict[str, Any]:
        """Devuelve el JSON de la respuesta, o un sobre vacio si no es JSON."""
        try:
            payload = response.json()
        except ValueError:
            return {"error": {"message": response.text or "Respuesta no JSON"}}
        return payload if isinstance(payload, dict) else {"data": payload}
