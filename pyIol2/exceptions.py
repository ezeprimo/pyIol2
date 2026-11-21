# Excepciones de la API de IOL Inversiones

from typing import Any

__all__ = [
    "IOLAPIError",
    "IOLAuthenticationError",
    "IOLValidationError",
    "IOLNotFoundError",
    "IOLRateLimitError",
    "IOLServerError",
    "IOLConnectionError",
    "IOLStreamError",
]


class IOLAPIError(Exception):
    """
    Error generico de la API de IOL.

    La API v1 responde siempre con el sobre `{meta, data, error}`. Cuando `error`
    no es nulo, esta excepcion conserva el mensaje, el codigo, los detalles y el
    `trace_id`, que es el dato que pide el soporte de IOL para investigar un caso.

    Attributes:
        message: Mensaje de error devuelto por la API
        status_code: Codigo HTTP de la respuesta
        code: Codigo de error propio de la API, si lo informa
        trace_id: Identificador de la request para debug y soporte
        details: Detalle adicional, normalmente errores de validacion
        method: Metodo HTTP de la request que fallo
        path: Path de la request que fallo
        payload: Cuerpo completo de la respuesta, sin transformar
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: int | None = None,
        trace_id: str | None = None,
        details: Any = None,
        method: str | None = None,
        path: str | None = None,
        payload: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.trace_id = trace_id
        self.details = details
        self.method = method
        self.path = path
        self.payload = payload

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.code is not None:
            parts.append(f"code={self.code}")
        if self.trace_id:
            parts.append(f"trace_id={self.trace_id}")
        if self.method and self.path:
            parts.append(f"{self.method} {self.path}")
        return " | ".join(parts)

    @classmethod
    def from_envelope(
        cls,
        payload: dict[str, Any] | None,
        status_code: int | None = None,
    ) -> "IOLAPIError":
        """
        Construye la excepcion concreta a partir del sobre de respuesta.

        Args:
            payload: Cuerpo completo de la respuesta de la API
            status_code: Codigo HTTP recibido

        Returns:
            Instancia de la subclase que corresponde al status HTTP
        """
        payload = payload or {}
        meta = payload.get("meta") or {}
        error = payload.get("error") or {}

        if not isinstance(error, dict):
            error = {"message": str(error)}

        message = error.get("message") or f"Error HTTP {status_code}"
        kwargs = {
            "status_code": status_code,
            "code": error.get("code"),
            "trace_id": meta.get("trace_id"),
            "details": error.get("details"),
            "method": meta.get("method"),
            "path": meta.get("path"),
            "payload": payload,
        }

        exception_class: type[IOLAPIError] = cls
        if status_code == 401:
            exception_class = IOLAuthenticationError
        elif status_code == 403:
            exception_class = IOLAuthenticationError
        elif status_code == 404:
            exception_class = IOLNotFoundError
        elif status_code == 422:
            exception_class = IOLValidationError
        elif status_code == 429:
            exception_class = IOLRateLimitError
        elif status_code is not None and status_code >= 500:
            exception_class = IOLServerError
        elif status_code == 400:
            exception_class = IOLValidationError
        return exception_class(message, **kwargs)


class IOLAuthenticationError(IOLAPIError):
    """Credenciales invalidas, token vencido o permisos insuficientes."""


class IOLValidationError(IOLAPIError):
    """La request no cumple el contrato: falta un campo o el formato es invalido."""


class IOLNotFoundError(IOLAPIError):
    """El recurso pedido no existe (por ejemplo, un simbolo desconocido)."""


class IOLRateLimitError(IOLAPIError):
    """Se supero el limite de requests de la API."""


class IOLServerError(IOLAPIError):
    """Error interno del servidor de IOL. Conviene reintentar con backoff."""


class IOLConnectionError(IOLAPIError):
    """No se pudo establecer la conexion HTTP o WebSocket."""


class IOLStreamError(IOLAPIError):
    """
    Error informado por el WebSocket de market data.

    El servidor manda `{type: "Error", code: <int>, msg: <str>}`. El codigo 401
    tambien aparece cuando se pide mas de un titulo de `order_book` en la misma
    conexion: en ese caso no es un problema de token y no hay que renovarlo.
    """

    def __init__(self, message: str, *, code: int | None = None, **kwargs: Any):
        super().__init__(message, status_code=code, **kwargs)
        self.ws_code = code

    def __str__(self) -> str:
        return f"{self.message} | ws_code={self.ws_code}"
