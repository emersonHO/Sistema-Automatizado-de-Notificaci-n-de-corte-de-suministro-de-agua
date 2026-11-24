"""Worker persistente: reclama solicitudes y llama a ejecutar_pipeline()."""

from __future__ import annotations

import logging
import os
import socket
import threading
import time
from pathlib import Path

from src.config import WORKER_POLL_S
# El pipeline-worker no consume el outbox: eso corresponde a notification-worker.
from src.db import aplicar_esquema
from src.logging_config import configurar_logging
from src.pipeline import ejecutar_pipeline
from src.solicitudes import (
    cerrar_desde_ejecucion,
    marcar_error_pre_pipeline,
    obtener_ejecucion_de_solicitud,
    obtener_solicitud,
    pulso_heartbeat,
    reclamar_solicitud,
    reconciliar_huerfanas,
)

logger = logging.getLogger(__name__)


def _worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def _latido(solicitud_id: int, stop: threading.Event) -> None:
    while not stop.wait(15):
        try:
            pulso_heartbeat(solicitud_id)
        except Exception:
            logger.exception("Fallo al actualizar heartbeat de solicitud %s", solicitud_id)


def _cerrar_si_terminal(solicitud_id: int) -> bool:
    ejecucion = obtener_ejecucion_de_solicitud(solicitud_id)
    if ejecucion and ejecucion["estado"] in {"COMPLETADO", "COMPLETADO_INCOMPLETO", "ERROR"}:
        cerrar_desde_ejecucion(solicitud_id)
        return True
    return False


def _procesar(solicitud: dict) -> None:
    solicitud_id = int(solicitud["id"])
    stop = threading.Event()
    hilo = threading.Thread(target=_latido, args=(solicitud_id, stop), daemon=True)
    hilo.start()
    try:
        if _cerrar_si_terminal(solicitud_id):
            logger.info("Solicitud %s ya tenía ejecución terminal; no se relanza", solicitud_id)
            return
        desde = None
        if solicitud.get("modo") == "fixture" and solicitud.get("ruta_fixture"):
            desde = Path(solicitud["ruta_fixture"])
        try:
            resultado = ejecutar_pipeline(
                desde_archivo=desde,
                procesar_envios=False,
                forzar_simulacion=True,
                solicitud_id=solicitud_id,
            )
            logger.info(
                "Pipeline de solicitud %s estado=%s ejecucion_id=%s",
                solicitud_id,
                resultado.get("estado"),
                resultado.get("ejecucion_id"),
            )
        except Exception:
            logger.exception("Excepción al ejecutar pipeline de solicitud %s", solicitud_id)
        if _cerrar_si_terminal(solicitud_id):
            return
        actual = obtener_solicitud(solicitud_id)
        if actual and actual["estado"] == "EN_PROCESO":
            reencolar = actual["intentos_worker"] < actual["max_intentos"]
            marcar_error_pre_pipeline(
                solicitud_id,
                "Fallo del worker antes de persistir la ejecución",
                reencolar=reencolar,
            )
    finally:
        stop.set()


def ciclo_una_vez(worker_id: str | None = None) -> bool:
    """Reconciliar y reclamar una solicitud. True si procesó algo."""
    reconciliar_huerfanas()
    tomada = reclamar_solicitud(worker_id or _worker_id())
    if not tomada:
        return False
    logger.info(
        "Reclamada solicitud %s origen=%s",
        tomada["id"],
        tomada.get("origen"),
        extra={
            "evento": "solicitud_reclamada",
            "solicitud_id": tomada["id"],
            "worker_id": worker_id or _worker_id(),
        },
    )
    _procesar(tomada)
    return True


def main() -> None:
    configurar_logging()
    aplicar_esquema()
    ident = _worker_id()
    logger.info("pipeline-worker iniciado id=%s poll=%ss", ident, WORKER_POLL_S)
    while True:
        try:
            trabajo = ciclo_una_vez(ident)
        except Exception:
            logger.exception("Error en el ciclo del worker")
            trabajo = False
        if not trabajo:
            time.sleep(max(0.5, WORKER_POLL_S))


if __name__ == "__main__":
    main()
