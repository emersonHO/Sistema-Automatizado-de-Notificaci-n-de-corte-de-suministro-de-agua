"""Un ciclo de producción sin workers permanentes.

Usa la cola y el pipeline existentes: encola (si procede), reclama solicitudes
con pipeline-worker y vacía el outbox con notification-worker.
Pensado para GitHub Actions / Render Free (sin Background Worker de pago).
"""

from __future__ import annotations

import logging
import os
import uuid

from src.db import aplicar_esquema
from src.logging_config import configurar_logging
from src.solicitudes import EjecucionActiva, IdempotenciaConflicto, crear_solicitud
from src.worker_notificaciones import ciclo_una_vez as ciclo_notificaciones
from src.worker_pipeline import ciclo_una_vez as ciclo_pipeline

logger = logging.getLogger(__name__)


def ejecutar_ciclo(
    *,
    origen: str = "PROGRAMADA",
    encolar: bool = True,
    max_pipeline: int = 8,
    max_notif: int = 40,
) -> dict:
    aplicar_esquema()
    solicitud = None
    if encolar:
        clave = (os.getenv("IDEMPOTENCY_KEY") or "").strip() or f"gha-{uuid.uuid4().hex[:24]}"
        try:
            fila, creada = crear_solicitud(
                origen=origen,
                solo_si_libre=True,
                modo="api",
                idempotency_key=clave[:128],
            )
            solicitud = {"id": fila.get("id"), "creada": creada, "estado": fila.get("estado")}
        except EjecucionActiva:
            logger.info("Hay una solicitud activa; se reclama la existente")
            solicitud = {"activa": True}
        except IdempotenciaConflicto as error:
            logger.info("Idempotencia con firma distinta: %s", error)
            solicitud = {"conflicto_idempotencia": True}

    pipelines = 0
    for _ in range(max(1, max_pipeline)):
        if not ciclo_pipeline():
            break
        pipelines += 1

    notificaciones = 0
    for _ in range(max(1, max_notif)):
        if not ciclo_notificaciones():
            break
        notificaciones += 1

    return {
        "ok": True,
        "solicitud": solicitud,
        "pipelines_procesados": pipelines,
        "lotes_notificacion": notificaciones,
    }


def main() -> int:
    configurar_logging()
    try:
        resumen = ejecutar_ciclo()
    except Exception:
        logger.exception("Fallo en ciclo de producción")
        return 1
    logger.info(
        "Ciclo terminado pipelines=%s notif_lotes=%s",
        resumen.get("pipelines_procesados"),
        resumen.get("lotes_notificacion"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
