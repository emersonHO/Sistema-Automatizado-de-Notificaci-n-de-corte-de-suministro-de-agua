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


def test_metrics_protegido(conexion, monkeypatch):
    from src.web import app as app_mod

    monkeypatch.setattr(app_mod, "PROTEGER_METRICS", True)
    from src import config as cfg
    from src.web import interno as interno_mod

    monkeypatch.setattr(cfg, "INTERNAL_API_TOKEN", "token-interno-test")
    monkeypatch.setattr(interno_mod.config, "INTERNAL_API_TOKEN", "token-interno-test")
    cliente = TestClient(app)
    assert cliente.get("/metrics").status_code == 401
    ok = cliente.get("/metrics", headers={"Authorization": "Bearer token-interno-test"})
    assert ok.status_code == 200
