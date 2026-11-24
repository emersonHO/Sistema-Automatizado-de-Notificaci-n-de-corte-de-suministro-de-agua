import json
import logging

from fastapi.testclient import TestClient

from src.logging_config import JsonFormatter
from src.observabilidad import snapshot
from src.pipeline import ejecutar_pipeline
from src.suscripciones import confirmar_correo, suscribir
from src.web.app import app


def test_salud_liveness_sin_depender_de_metricas():
    cliente = TestClient(app)
    resp = cliente.get("/salud")
    assert resp.status_code == 200
    cuerpo = resp.json()
    assert cuerpo["ok"] is True
    assert cuerpo["vivo"] is True
    assert cuerpo["rol"] == "liveness"
    assert "postgres" not in cuerpo


def test_salud_listo_con_postgres(conexion):
    cliente = TestClient(app)
    resp = cliente.get("/salud/listo")
    assert resp.status_code == 200
    cuerpo = resp.json()
    assert cuerpo["ok"] is True
    assert cuerpo["postgres"] is True
    assert cuerpo["rol"] == "readiness"


def test_snapshot_base_vacia(conexion):
    data = snapshot(conexion)
    assert data["pipeline"]["total"] == 0
    assert data["pipeline"]["duracion_promedio_s"] is None
    assert data["pipeline"]["duracion_p95_s"] is None
    assert data["pipeline"]["tasa_sin_error"] is None
    assert data["solicitudes"]["pendientes"] == 0
    assert data["notificaciones"]["total"] == 0
    assert data["notificaciones"]["tasa_simulacion_exitosa"] is None
    assert data["zona_timestamps"] == "UTC"


def test_snapshot_tras_pipeline_fixture(conexion, captura_minima, tmp_path, monkeypatch):
    from src import recolector as rec
    from src import config as cfg

    monkeypatch.setattr(rec, "CARPETA_RAW", tmp_path / "raw")
    rec.CARPETA_RAW.mkdir(parents=True)
    monkeypatch.setattr(cfg, "CARPETA_RAW", tmp_path / "raw")
    r = suscribir(
        "obs.prueba@example.com",
        [{"tipo": "DISTRITO", "nombre": "Santa Anita"}],
        conexion=conexion,
    )
    confirmar_correo(r["usuario"]["token_confirmacion"], conexion=conexion)
    conexion.commit()
    resultado = ejecutar_pipeline(
        desde_archivo=captura_minima, procesar_envios=False, forzar_simulacion=True
    )
    assert resultado["estado"] in {"COMPLETADO", "COMPLETADO_INCOMPLETO"}
    data = snapshot(conexion)
    assert data["pipeline"]["total"] >= 1
    assert data["pipeline"]["fallidas"] == 0
    assert data["pipeline"]["completadas"] + data["pipeline"]["incompletas"] >= 1
    assert data["pipeline"]["duracion_promedio_s"] is not None
    assert data["pipeline"]["ultima"]["id"] == resultado["ejecucion_id"]
    assert data["notificaciones"]["pendientes"] >= 1
    assert data["notificaciones"]["simuladas"] == 0


def test_incompleto_no_cuenta_como_error(conexion):
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO ejecuciones_proceso (estado, fecha_inicio, fecha_fin, captura_completa)
            VALUES ('COMPLETADO_INCOMPLETO', NOW() - INTERVAL '10 seconds', NOW(), FALSE)
            """
        )
    conexion.commit()
    data = snapshot(conexion)
    assert data["pipeline"]["incompletas"] >= 1
    assert data["pipeline"]["fallidas"] == 0
    assert data["pipeline"]["tasa_sin_error"] == 1.0


def test_api_observabilidad_auth(conexion, monkeypatch):
    from src import config as cfg
    from src.web import interno as interno_mod

    monkeypatch.setattr(cfg, "INTERNAL_API_TOKEN", "token-obs-test")
    monkeypatch.setattr(interno_mod.config, "INTERNAL_API_TOKEN", "token-obs-test")
    cliente = TestClient(app)
    assert cliente.get("/internal/v1/observabilidad").status_code == 401
    ok = cliente.get(
        "/internal/v1/observabilidad",
        headers={"Authorization": "Bearer token-obs-test"},
    )
    assert ok.status_code == 200
    cuerpo = ok.json()
    assert cuerpo["ok"] is True
    assert "pipeline" in cuerpo
    assert "notificaciones" in cuerpo
    assert cuerpo["notificaciones"]["tasa_simulacion_exitosa"] is None or cuerpo["notificaciones"]["simuladas"] >= 0


def test_log_json_incluye_traza():
    fmt = JsonFormatter()
    record = logging.LogRecord(
        name="src.pipeline",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Inicio de ejecución del pipeline",
        args=(),
        exc_info=None,
    )
    record.evento = "pipeline_inicio"
    record.ejecucion_id = 12
    record.solicitud_id = 3
    texto = fmt.format(record)
    payload = json.loads(texto)
    assert payload["evento"] == "pipeline_inicio"
    assert payload["ejecucion_id"] == 12
    assert payload["solicitud_id"] == 3
    assert "ts" in payload
    assert "token" not in payload
    assert "password" not in payload


def test_metricas_html_admin(conexion):
    cliente = TestClient(app)
    r = cliente.get("/metricas")
    assert r.status_code == 200
    assert "Observabilidad" in r.text or "Precisión" in r.text
    assert "SIMULADA" in r.text
