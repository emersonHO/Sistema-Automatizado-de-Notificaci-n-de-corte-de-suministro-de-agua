"""Worker persistente del outbox de notificaciones (Fase 3).

No ejecuta el pipeline ni crea notificaciones nuevas. Solo reclama y simula entrega.
"""

from __future__ import annotations

import logging
import time

from src.config import NOTIF_LOTE, NOTIF_POLL_S, OPERACION_PUBLICA
from src.db import aplicar_esquema, conectar
from src.logging_config import configurar_logging
from src.correo import debe_enviar_smtp
from src.notificaciones import (
    procesar_outbox,
    reconciliar_notificaciones_huerfanas,
    worker_id_local,
)

logger = logging.getLogger(__name__)


def ciclo_una_vez(worker_id: str | None = None, limite: int | None = None) -> bool:
    ident = worker_id or worker_id_local()
    with conectar() as conexion:
        reconciliar_notificaciones_huerfanas(conexion)
        resumen = procesar_outbox(
            conexion,
            limite=limite or NOTIF_LOTE,
            forzar_simulacion=not debe_enviar_smtp() and not OPERACION_PUBLICA,
            worker_id=ident,
        )
        conexion.commit()
    trabajo = int(resumen.get("procesadas") or 0) > 0
    if trabajo:
        logger.info(
            "notification-worker id=%s procesadas=%s simuladas=%s fallidas=%s reintentando=%s",
            ident,
            resumen.get("procesadas"),
            resumen.get("simuladas"),
            resumen.get("fallidas"),
            resumen.get("reintentando"),
        )
    return trabajo


def main() -> None:
    configurar_logging()
    aplicar_esquema()
    ident = worker_id_local()
    logger.info("notification-worker iniciado id=%s poll=%ss", ident, NOTIF_POLL_S)
    while True:
        try:
            trabajo = ciclo_una_vez(ident)
        except Exception:
            logger.exception("Error en el ciclo del notification-worker")
            trabajo = False
        if not trabajo:
            time.sleep(max(0.5, NOTIF_POLL_S))


if __name__ == "__main__":
    main()
