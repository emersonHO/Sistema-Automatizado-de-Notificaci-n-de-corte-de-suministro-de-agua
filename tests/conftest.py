from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.pop("DATABASE_URL", None)
os.environ.pop("POSTGRES_URL", None)
os.environ["DATABASE_URL"] = ""
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "notificaciones_agua_test")
os.environ.setdefault("DB_USER", "agua")
os.environ.setdefault("DB_PASSWORD", "agua_local_dev")
os.environ.setdefault("SMTP_ENABLED", "false")
os.environ.setdefault("MODO_ENVIO", "simulacion")
os.environ["CORREO_PROVEEDOR"] = ""
os.environ["RESEND_API_KEY"] = ""
# El contenedor Compose puede traer ADMIN_PASSWORD; los tests HTML asumen panel abierto
# salvo que el caso de prueba active la auth con monkeypatch.
os.environ["ADMIN_PASSWORD"] = ""

from src import config as config_mod  # noqa: E402

config_mod.DATABASE_URL = ""
config_mod.DB_NAME = os.environ["DB_NAME"]
config_mod.DB_USER = os.environ["DB_USER"]
config_mod.DB_PASSWORD = os.environ["DB_PASSWORD"]
config_mod.SMTP_ENABLED = False
config_mod.MODO_ENVIO = "simulacion"
config_mod.CORREO_PROVEEDOR = ""
config_mod.RESEND_API_KEY = ""
config_mod.ADMIN_PASSWORD = ""
config_mod.EN_RENDER = False

POSTGRES_DISPONIBLE = False


def pytest_configure():
    global POSTGRES_DISPONIBLE
    import psycopg

    try:
        conn = psycopg.connect(
            host=os.environ["DB_HOST"],
            port=os.environ["DB_PORT"],
            dbname="notificaciones_agua_test",
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            connect_timeout=5,
        )
        conn.close()
        POSTGRES_DISPONIBLE = True
    except Exception:
        POSTGRES_DISPONIBLE = False


def pytest_collection_modifyitems(config, items):
    if POSTGRES_DISPONIBLE:
        return
    skip = pytest.mark.skip(
        reason="PostgreSQL de prueba (notificaciones_agua_test) no está disponible en este entorno"
    )
    for item in items:
        ruta = str(getattr(item, "fspath", ""))
        if any(
            nombre in ruta
            for nombre in (
                "test_web.py",
                "test_pipeline.py",
                "test_notificaciones.py",
                "test_interno.py",
                "test_solicitudes.py",
                "test_worker.py",
                "test_worker_notificaciones.py",
                "test_fase3_notificaciones.py",
                "test_observabilidad.py",
                "test_metricas_prom.py",
                "test_e2e_flujo.py",
                "test_publico.py",
            )
        ):
            item.add_marker(skip)
        if "conexion" in getattr(item, "fixturenames", ()):
            item.add_marker(skip)


@pytest.fixture
def conexion():
    if not POSTGRES_DISPONIBLE:
        pytest.skip("PostgreSQL de prueba no disponible")
    from src.db import aplicar_esquema, conectar
    from src.suscripciones import sembrar_zonas

    aplicar_esquema()
    conn = conectar()
    sembrar_zonas(conn)
    conn.commit()
    with conn.cursor() as cursor:
        cursor.execute(
            """
            TRUNCATE TABLE
                intentos_notificacion,
                notificaciones,
                coincidencias_territoriales,
                suscripciones,
                usuarios,
                historial_interrupciones,
                capturas,
                interrupciones,
                ejecuciones_proceso,
                solicitudes_ejecucion
            RESTART IDENTITY CASCADE
            """
        )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def captura_minima():
    return Path(__file__).parent / "fixtures" / "captura_minima.json"
