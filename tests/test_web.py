from fastapi.testclient import TestClient

from src.web.app import app


def test_salud():
    cliente = TestClient(app)
    resp = cliente.get("/salud")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_panel_y_suscripcion(conexion):
    cliente = TestClient(app)
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Panel principal" in r.text
    r = cliente.get("/interrupciones")
    assert r.status_code == 200
    r = cliente.get("/suscripciones")
    assert r.status_code == 200
    r = cliente.get("/notificaciones")
    assert r.status_code == 200
    r = cliente.get("/ejecuciones")
    assert r.status_code == 200
    r = cliente.get("/metricas")
    assert r.status_code == 200
    assert "Precisión" in r.text
