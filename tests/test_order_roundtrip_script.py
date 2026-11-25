"""
Tests de los helpers del script de round-trip de ordenes.

El script es una frontera de proceso, pero la logica de ventana temporal si se
puede probar en aislamiento: es lo unico que decide si una orden que aparece en
el feed es la que acaba de mandar este proceso.
"""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "order_roundtrip.py"


def _load_script_module():
    """Carga el script como modulo sin ejecutar `main()`."""
    spec = importlib.util.spec_from_file_location("order_roundtrip_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load_script_module()


def test_within_window_acepta_la_misma_hora(script):
    sent_at = datetime(2026, 11, 21, 14, 58, 15)

    assert script._within_window("2026-11-21T14:58:15.143", sent_at) is True


def test_within_window_acepta_dentro_de_la_tolerancia(script):
    sent_at = datetime(2026, 11, 21, 14, 58, 15)

    assert script._within_window("2026-11-21T14:59:10.000", sent_at) is True


def test_within_window_rechaza_una_orden_vieja(script):
    sent_at = datetime(2026, 11, 21, 14, 58, 15)

    assert script._within_window("2026-11-21T09:00:00.000", sent_at) is False


# Offset fijo y no local: si el helper descartara el tzinfo en lugar de
# normalizarlo, el test fallaria en cualquier host, no solo en los que no son UTC-5.
FIXED_OFFSET = timezone(timedelta(hours=-5))


def test_within_window_normaliza_un_offset_no_local(script):
    # 14:58:15 en UTC-5 es otro instante que 14:58:15 local: el helper tiene que
    # convertirlo a la hora local del host antes de comparar.
    aware = datetime(2026, 11, 21, 14, 58, 15, tzinfo=FIXED_OFFSET)
    esperado_local = aware.astimezone().replace(tzinfo=None)

    assert script._within_window(aware.isoformat(), esperado_local) is True


def test_within_window_rechaza_el_mismo_offset_corrido(script):
    aware = datetime(2026, 11, 21, 14, 58, 15, tzinfo=FIXED_OFFSET)
    esperado_local = aware.astimezone().replace(tzinfo=None)

    # Una hora de diferencia cae fuera de la ventana de 120s.
    assert script._within_window(aware.isoformat(), esperado_local + timedelta(hours=1)) is False


def test_within_window_rechaza_tipos_que_no_son_str(script):
    sent_at = datetime(2026, 11, 21, 14, 58, 15)

    assert script._within_window(sent_at, sent_at) is False
    assert script._within_window(20261121, sent_at) is False


def test_within_window_tolera_fecha_ilegible(script):
    assert script._within_window("", datetime.now()) is False
    assert script._within_window(None, datetime.now()) is False
    assert script._within_window("no-es-fecha", datetime.now()) is False


def test_within_window_sin_offset_sigue_funcionando(script):
    # La forma que manda la API en produccion: naive, sin offset.
    sent_at = datetime(2026, 11, 21, 14, 58, 15)

    assert script._within_window("2026-11-21T14:58:15.143", sent_at) is True
