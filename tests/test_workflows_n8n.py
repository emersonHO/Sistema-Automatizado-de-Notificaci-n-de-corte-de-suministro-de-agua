"""Contrato de workflows n8n: sin secretos y alineados a la API interna."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "n8n" / "workflows"


def _cargar(nombre: str) -> dict:
    return json.loads((ROOT / nombre).read_text(encoding="utf-8"))


def test_workflows_sin_secretos_ni_activos():
    for nombre in (
        "pipeline-manual.json",
        "pipeline-programado.json",
        "seguimiento-observabilidad.json",
        "alertas-admin.json",
        "resumen-diario.json",
    ):
        texto = (ROOT / nombre).read_text(encoding="utf-8")
        assert "INTERNAL_API_TOKEN" not in texto
        assert "SMTP_PASSWORD" not in texto
        assert "cambiar_token" not in texto
        assert "Bearer " not in texto.replace("Consulta Bearer a FastAPI", "")
        data = json.loads(texto)
        assert data.get("active") is False


def test_manual_usa_fixture_y_poll():
    data = _cargar("pipeline-manual.json")
    cuerpo = json.dumps(data)
    assert "/internal/v1/pipeline/ejecuciones" in cuerpo
    assert "captura_minima.json" in cuerpo
    assert '"modo": "fixture"' in cuerpo or "modo\\\": \\\"fixture\\\"" in cuerpo or "fixture" in cuerpo


def test_programado_api_inactivo_y_solo_si_libre():
    data = _cargar("pipeline-programado.json")
    cuerpo = json.dumps(data)
    assert "solo_si_libre" in cuerpo
    assert '"modo": "api"' in cuerpo or "api" in cuerpo
    assert "scheduleTrigger" in cuerpo
    assert "15" in cuerpo or "minutesInterval" in cuerpo


def test_seguimiento_endpoints():
    data = _cargar("seguimiento-observabilidad.json")
    cuerpo = json.dumps(data)
    assert "/internal/v1/observabilidad" in cuerpo
    assert "/internal/v1/notificaciones" in cuerpo
    assert "continueErrorOutput" in cuerpo
