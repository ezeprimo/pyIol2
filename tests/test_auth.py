"""Tests del administrador de tokens OAuth2."""

import httpx
import pytest

from pyIol2 import IOLAuthenticationError, IOLToken, TokenManager
from tests.conftest import StubAPI, envelope, error_envelope


def make_manager(stub: StubAPI, margin: int = 30) -> TokenManager:
    """Arma un TokenManager sobre el doble de la API."""
    http = httpx.Client(transport=stub.transport())
    return TokenManager("usuario", "clave", http_client=http, safety_margin=margin)


def test_login_inicial_usa_grant_password(stub):
    manager = make_manager(stub)

    token = manager.get_access_token()

    assert token == "token-1"
    request = stub.last("POST", "/auth/token")
    assert request["body"] == {"grant_type": "password", "username": "usuario", "password": "clave"}


def test_token_se_cachea_entre_llamadas(stub):
    manager = make_manager(stub)

    manager.get_access_token()
    manager.get_access_token()

    assert stub.token_calls == 1


def test_invalidate_fuerza_renovacion(stub):
    manager = make_manager(stub)
    manager.get_access_token()

    manager.invalidate()

    assert manager.get_access_token() == "token-2"
    assert stub.token_calls == 2


def test_renovacion_usa_refresh_token(stub):
    manager = make_manager(stub)
    manager.get_access_token()

    manager.refresh()

    request = stub.last("POST", "/auth/token")
    assert request["body"] == {"grant_type": "refresh_token", "refresh_token": "refresh-1"}


def test_refresh_fallido_no_pisa_el_token_actual(stub):
    manager = make_manager(stub)
    manager.get_access_token()

    stub.set_token_response(error_envelope("refresh vencido", status=401), status=401)

    with pytest.raises(IOLAuthenticationError):
        manager.refresh()
    # El token anterior sigue en memoria: un refresh fallido no rompe la sesion.
    assert manager.token is not None
    assert manager.token.access_token == "token-1"


def test_tras_invalidar_vuelve_a_pedir_con_password(stub):
    manager = make_manager(stub)
    manager.get_access_token()
    manager.invalidate()

    stub.set_token_response(
        envelope({"access_token": "token-3", "refresh_token": "refresh-3", "expires_in": 900})
    )

    assert manager.get_access_token() == "token-3"
    assert stub.last("POST", "/auth/token")["body"] == {
        "grant_type": "password",
        "username": "usuario",
        "password": "clave",
    }


def test_credenciales_invalidas_levanta_authentication_error(stub):
    stub.set_token_response(error_envelope("Credenciales invalidas", status=401), status=401)
    manager = make_manager(stub)

    with pytest.raises(IOLAuthenticationError) as error:
        manager.get_access_token()

    assert error.value.status_code == 401
    assert "Credenciales invalidas" in str(error.value)


def test_respuesta_sin_access_token_levanta_error(stub):
    stub.set_token_response(envelope({"refresh_token": "r"}))
    manager = make_manager(stub)

    with pytest.raises(Exception) as error:
        manager.get_access_token()

    assert "access_token" in str(error.value)


def test_iol_token_from_dict_tolera_campos_faltantes():
    token = IOLToken.from_dict({"access_token": "a"})

    assert token.access_token == "a"
    assert token.refresh_token == ""
    assert token.token_type == "bearer"
    assert token.expires_in > 0
