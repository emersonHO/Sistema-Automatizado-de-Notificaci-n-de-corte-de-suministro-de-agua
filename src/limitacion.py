"""Rate limiting persistente por clave (IP + ruta)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def permitir(conexion, clave: str, maximo: int, minutos: int) -> bool:
    desde = datetime.now(timezone.utc) - timedelta(minutes=minutos)
    with conexion.cursor() as cursor:
        cursor.execute(
            "DELETE FROM limitacion_solicitudes WHERE ocurrida_en < NOW() - INTERVAL '2 days'"
        )
        cursor.execute(
            """
            SELECT COUNT(*) FROM limitacion_solicitudes
            WHERE clave = %s AND ocurrida_en >= %s
            """,
            (clave, desde),
        )
        n = cursor.fetchone()[0]
        if n >= maximo:
            return False
        cursor.execute(
            "INSERT INTO limitacion_solicitudes (clave) VALUES (%s)",
            (clave,),
        )
    return True
