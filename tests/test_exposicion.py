from fastapi.testclient import TestClient

from src.web.app import app
from src.web.exposicion import host_es_tunel, ruta_permitida_en_tunel


def test_host_tunel():
    assert host_es_tunel("abc-def.trycloudflare.com")
    assert host_es_tunel("x.trycloudflare.com:443")
    assert not host_es_tunel("127.0.0.1:8000")
    assert not host_es_tunel("web:8000")


def test_rutas_tunel():
    assert ruta_permitida_en_tunel("/")
    assert ruta_permitida_en_tunel("/suscribir")
    assert ruta_permitida_en_tunel("/confirmar/abc")
    assert ruta_permitida_en_tunel("/cuenta/tok")
    assert ruta_permitida_en_tunel("/baja/tok")
    assert ruta_permitida_en_tunel("/privacidad")
    assert ruta_permitida_en_tunel("/interrupciones")
    assert ruta_permitida_en_tunel("/static/publico.css")
    assert not ruta_permitida_en_tunel("/admin")
    assert not ruta_permitida_en_tunel("/admin/login")
    assert not ruta_permitida_en_tunel("/internal/v1/pipeline")
    assert not ruta_permitida_en_tunel("/metrics")
    assert not ruta_permitida_en_tunel("/metricas")
    assert not ruta_permitida_en_tunel("/estado")
    assert not ruta_permitida_en_tunel("/solicitudes")
    assert not ruta_permitida_en_tunel("/destinatarios")
    assert not ruta_permitida_en_tunel("/auditoria")
    assert not ruta_permitida_en_tunel("/ejecuciones")
    assert not ruta_permitida_en_tunel("/notificaciones")
    assert not ruta_permitida_en_tunel("/salud")


def test_middleware_bloquea_admin_en_tunel(conexion):
    cliente = TestClient(app)
    host = {"host": "demo.trycloudflare.com"}
    assert cliente.get("/admin", headers=host).status_code == 404
    assert cliente.get("/admin/login", headers=host).status_code == 404
    assert cliente.get("/metrics", headers=host).status_code == 404
    assert cliente.get("/internal/v1/pipeline/ejecuciones", headers=host).status_code == 404
    publico = cliente.get("/", headers=host)
    assert publico.status_code == 200
    assert "Suscribirse" in publico.text or "suscribir" in publico.text.lower()


def test_localhost_sigue_viendo_login(conexion):
    cliente = TestClient(app)
    r = cliente.get("/admin/login")
    assert r.status_code == 200
