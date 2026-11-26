from fastapi.testclient import TestClient

from src.web.app import app


def test_salud():
    cliente = TestClient(app)
    resp = cliente.get("/salud")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["vivo"] is True


def test_panel_y_suscripcion(conexion):
    cliente = TestClient(app)
    r = cliente.get("/")
    assert r.status_code == 200
    assert "suscribir" in r.text.lower() or "Registrarme" in r.text
    r = cliente.get("/admin")
    assert r.status_code == 200
    assert "Resumen operativo" in r.text
    r = cliente.get("/interrupciones")
    assert r.status_code == 200
    r = cliente.get("/estadisticas")
    assert r.status_code == 200
    assert "Estadísticas" in r.text
    js = cliente.get("/estadisticas.json")
    assert js.status_code == 200
    assert "suscriptores" in js.json()
    assert "correo" not in js.json()
    r = cliente.get("/suscripciones")
    assert r.status_code == 200
    r = cliente.get("/notificaciones")
    assert r.status_code == 200
    r = cliente.get("/ejecuciones")
    assert r.status_code == 200
    r = cliente.get("/metricas")
    assert r.status_code == 200
    assert "Precisión" in r.text
    r = cliente.get("/solicitudes")
    assert r.status_code == 200
    r = cliente.get("/destinatarios")
    assert r.status_code == 200
    r = cliente.get("/auditoria")
    assert r.status_code == 200
    r = cliente.get("/estado")
    assert r.status_code == 200
    r = cliente.get("/metrics")
    assert r.status_code == 200


def test_admin_exige_login_cuando_hay_password(conexion, monkeypatch):
    from src import config as cfg

    monkeypatch.setattr(cfg, "ADMIN_PASSWORD", "secreto-test")
    monkeypatch.setattr(cfg, "ADMIN_USER", "admin")
    cliente = TestClient(app)
    r = cliente.get("/ejecuciones", follow_redirects=False)
    assert r.status_code == 303
    assert "/admin/login" in r.headers["location"]
    login_page = cliente.get("/admin/login")
    assert login_page.status_code == 200
    csrf = cliente.cookies.get("session")  # sesión firmada; el token CSRF va en HTML
    assert "csrf" in login_page.text
    # extraer token del formulario
    inicio = login_page.text.find('name="csrf"')
    assert inicio != -1
    fragmento = login_page.text[inicio: inicio + 80]
    token = fragmento.split('value="')[1].split('"')[0]
    r = cliente.post(
        "/admin/login",
        data={"usuario": "admin", "password": "secreto-test", "csrf": token, "siguiente": "/ejecuciones"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    r = cliente.get("/ejecuciones")
    assert r.status_code == 200
    assert "Ejecuciones" in r.text
