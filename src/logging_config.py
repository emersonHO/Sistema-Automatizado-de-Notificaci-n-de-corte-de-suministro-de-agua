"""Registro de logs: texto (por defecto) o JSON (Compose).

Timestamps en UTC con sufijo Z / offset. Campos de traza opcionales:
evento, solicitud_id, ejecucion_id, notificacion_id, worker_id.
No registrar tokens, contraseñas ni cuerpos de mensaje.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from src.config import LOG_FORMAT, LOG_LEVEL

CAMPOS_TRAZA = (
    "evento",
    "solicitud_id",
    "ejecucion_id",
    "notificacion_id",
    "worker_id",
    "estado",
    "intentos",
)


def extra_traza(**kwargs) -> dict:
    return {clave: valor for clave, valor in kwargs.items() if valor is not None}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for campo in CAMPOS_TRAZA:
            valor = getattr(record, campo, None)
            if valor is not None:
                payload[campo] = valor
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configurar_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    if LOG_FORMAT == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    root.addHandler(handler)
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
