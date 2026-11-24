from fastapi.testclient import TestClient

from src.web.app import app


def test_interno_sin_token(conexion, monkeypatch):
    from src import config as cfg
    from src.web import interno as interno_mod

    monkeypatch.setattr(cfg, "INTERNAL_API_TOKEN", "token-interno-test")
    monkeypatch.setattr(interno_mod.config, "INTERNAL_API_TOKEN", "token-interno-test")
    cliente = TestClient(app)
    r = cliente.post("/internal/v1/pipeline/ejecuciones", json={"origen": "MANUAL"})
    assert r.status_code == 401
    r = cliente.post(
        "/internal/v1/pipeline/ejecuciones",
        json={"origen": "MANUAL"},
        headers={"Authorization": "Bearer token-incorrecto-x"},
    )
    assert r.status_code == 401


def test_interno_encolar_consultar(conexion, monkeypatch):
    from src import config as cfg
    from src.web import interno as interno_mod

    monkeypatch.setattr(cfg, "INTERNAL_API_TOKEN", "token-interno-test")
    monkeypatch.setattr(interno_mod.config, "INTERNAL_API_TOKEN", "token-interno-test")
    auth = {"Authorization": "Bearer token-interno-test"}
    cliente = TestClient(app)
    r = cliente.post(
        "/internal/v1/pipeline/ejecuciones",
        json={"origen": "MANUAL", "solo_si_libre": False, "modo": "api"},
        headers={**auth, "Idempotency-Key": "n8n-test-clave01"},
    )
    assert r.status_code == 202
    cuerpo = r.json()
    assert cuerpo["ok"] is True
    assert cuerpo["estado"] == "PENDIENTE"
    sid = cuerpo["solicitud_id"]
    r2 = cliente.post(
        "/internal/v1/pipeline/ejecuciones",
        json={"origen": "MANUAL", "solo_si_libre": False, "modo": "api"},
        headers={**auth, "Idempotency-Key": "n8n-test-clave01"},
    )
    assert r2.status_code == 200
    assert r2.json()["solicitud_id"] == sid
    r3 = cliente.get(f"/internal/v1/pipeline/ejecuciones/{sid}", headers=auth)
    assert r3.status_code == 200
    assert r3.json()["solicitud_id"] == sid
    r4 = cliente.get("/internal/v1/pipeline/ejecuciones/999999", headers=auth)
    assert r4.status_code == 404
    r5 = cliente.post(
        "/internal/v1/pipeline/ejecuciones",
        json={"origen": "PROGRAMADA", "solo_si_libre": False, "modo": "api"},
        headers={**auth, "Idempotency-Key": "n8n-test-clave01"},
    )
    assert r5.status_code == 409
    lista = cliente.get("/internal/v1/pipeline/ejecuciones", headers=auth)
    assert lista.status_code == 200
    assert lista.json()["ok"] is True
    obs = cliente.get("/internal/v1/observabilidad", headers=auth)
    assert obs.status_code == 200
    assert obs.json()["ok"] is True
    notas = cliente.get("/internal/v1/notificaciones", headers=auth)
    assert notas.status_code == 200
    assert notas.json()["ok"] is True


def test_interno_sin_configurar(conexion, monkeypatch):
    from src import config as cfg
    from src.web import interno as interno_mod

    monkeypatch.setattr(cfg, "INTERNAL_API_TOKEN", "")
    monkeypatch.setattr(interno_mod.config, "INTERNAL_API_TOKEN", "")
    cliente = TestClient(app)
    r = cliente.post(
        "/internal/v1/pipeline/ejecuciones",
        json={"origen": "MANUAL"},
        headers={"Authorization": "Bearer x"},
    )
    assert r.status_code == 503
