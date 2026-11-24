from fastapi.testclient import TestClient

from src.web.app import app


def test_metrics_expuesto(conexion):
    cliente = TestClient(app)
    r = cliente.get("/metrics")
    assert r.status_code == 200
    cuerpo = r.text
    assert "http_requests_total" in cuerpo or "agua_" in cuerpo
    assert "password" not in cuerpo.lower()
    assert "token" not in cuerpo.lower() or "http_requests" in cuerpo
