"""Captura en segundo plano al arrancar (Render Free no tiene worker de pago)."""

from __future__ import annotations

import logging
import os
import sys
import threading

from src.config import EN_RENDER
from src.db import conectar

logger = logging.getLogger(__name__)


def _en_pruebas() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST")) or "pytest" in sys.modules


def hay_interrupciones() -> bool:
    with conectar() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM interrupciones")
            return int(cursor.fetchone()[0]) > 0


def ejecutar_ciclo_seguro(origen: str = "ARRANQUE") -> None:
    try:
        from src.ciclo_produccion import ejecutar_ciclo

        resumen = ejecutar_ciclo(origen=origen)
        logger.info(
            "Ciclo %s terminado pipelines=%s notif=%s",
            origen,
            resumen.get("pipelines_procesados"),
            resumen.get("lotes_notificacion"),
        )
    except Exception:
        logger.exception("Ciclo %s falló (la web sigue en pie)", origen)


def lanzar_ciclo(origen: str = "MANUAL") -> None:
    hilo = threading.Thread(
        target=ejecutar_ciclo_seguro,
        kwargs={"origen": origen},
        daemon=True,
        name="ciclo-agua",
    )
    hilo.start()


def lanzar_si_vacio() -> None:
    if _en_pruebas():
        return
    crudo = os.getenv("CAPTURAR_AL_ARRANCAR")
    if crudo is None or str(crudo).strip() == "":
        activo = EN_RENDER
    else:
        activo = str(crudo).strip().lower() in {"1", "true", "yes"}
    if not activo:
        return
    try:
        if hay_interrupciones():
            logger.info("Ya hay interrupciones almacenadas; no se lanza captura de arranque")
            return
    except Exception:
        logger.exception("No se pudo consultar interrupciones al arrancar")
        return
    logger.info("Base sin cortes: se lanza captura en segundo plano")
    lanzar_ciclo("ARRANQUE")
