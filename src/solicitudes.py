"""Cola persistente de solicitudes de ejecución del pipeline (Fase 2)."""

from __future__ import annotations

import logging
from typing import Any

from psycopg.rows import dict_row

from src.db import conectar

logger = logging.getLogger(__name__)

ESTADOS_TERMINALES_PIPELINE = frozenset(
    {"COMPLETADO", "COMPLETADO_INCOMPLETO", "ERROR"}
)
ESTADOS_TERMINALES_SOLICITUD = frozenset(
    {
        "COMPLETADO",
        "COMPLETADO_INCOMPLETO",
        "ERROR",
        "ERROR_RECUPERACION",
        "CANCELADA",
    }
)
ESTADOS_ACTIVOS_COLA = frozenset({"PENDIENTE", "EN_PROCESO"})


class IdempotenciaConflicto(Exception):
    def __init__(self, solicitud: dict):
        super().__init__("Idempotency-Key con parámetros incompatibles")
        self.solicitud = solicitud


class EjecucionActiva(Exception):
    def __init__(self):
        super().__init__("Hay una solicitud PENDIENTE o EN_PROCESO")


class FixtureNoPermitido(Exception):
    pass


def _normalizar(
    origen: str,
    solo_si_libre: bool,
    modo: str,
    ruta_fixture: str | None,
) -> tuple[str, bool, str, str | None]:
    origen_n = (origen or "").strip().upper()
    modo_n = (modo or "api").strip().lower()
    if origen_n not in {"MANUAL", "PROGRAMADA"}:
        raise ValueError("origen inválido")
    if modo_n not in {"api", "fixture"}:
        raise ValueError("modo inválido")
    ruta = (ruta_fixture or "").strip() or None
    if modo_n == "api":
        ruta = None
    return origen_n, bool(solo_si_libre), modo_n, ruta


def _misma_firma(fila: dict, origen: str, solo_si_libre: bool, modo: str, ruta: str | None) -> bool:
    return (
        fila["cuerpo_origen"] == origen
        and bool(fila["cuerpo_solo_si_libre"]) == bool(solo_si_libre)
        and fila["cuerpo_modo"] == modo
        and (fila["cuerpo_ruta_fixture"] or None) == (ruta or None)
    )


def hay_solicitud_activa(conexion=None) -> bool:
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM solicitudes_ejecucion
                    WHERE estado = ANY(%s)
                )
                """,
                (list(ESTADOS_ACTIVOS_COLA),),
            )
            return bool(cursor.fetchone()[0])
    finally:
        if propia:
            conexion.close()


def crear_solicitud(
    origen: str,
    solo_si_libre: bool = False,
    modo: str = "api",
    ruta_fixture: str | None = None,
    idempotency_key: str | None = None,
    conexion=None,
) -> tuple[dict, bool]:
    """Inserta o reutiliza por idempotencia. Devuelve (fila, creada)."""
    origen_n, solo, modo_n, ruta = _normalizar(origen, solo_si_libre, modo, ruta_fixture)
    clave = (idempotency_key or "").strip() or None
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        if solo_si_libre and hay_solicitud_activa(conexion):
            raise EjecucionActiva()
        with conexion.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                INSERT INTO solicitudes_ejecucion (
                    estado, origen, modo, ruta_fixture, idempotency_key,
                    cuerpo_origen, cuerpo_solo_si_libre, cuerpo_modo,
                    cuerpo_ruta_fixture
                ) VALUES (
                    'PENDIENTE', %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING *
                """,
                (origen_n, modo_n, ruta, clave, origen_n, solo, modo_n, ruta),
            )
            fila = cursor.fetchone()
            if fila:
                conexion.commit()
                return dict(fila), True
            if not clave:
                conexion.rollback()
                raise RuntimeError("No se pudo insertar la solicitud")
            cursor.execute(
                "SELECT * FROM solicitudes_ejecucion WHERE idempotency_key = %s",
                (clave,),
            )
            existente = cursor.fetchone()
            conexion.commit()
            if not existente:
                raise RuntimeError("Conflicto de idempotencia sin fila")
            existente = dict(existente)
            if not _misma_firma(existente, origen_n, solo, modo_n, ruta):
                raise IdempotenciaConflicto(existente)
            return existente, False
    finally:
        if propia:
            conexion.close()


def obtener_solicitud(solicitud_id: int, conexion=None) -> dict | None:
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "SELECT * FROM solicitudes_ejecucion WHERE id = %s",
                (solicitud_id,),
            )
            fila = cursor.fetchone()
            return dict(fila) if fila else None
    finally:
        if propia:
            conexion.close()


def listar_solicitudes(limite: int = 20, estado: str | None = None, conexion=None) -> list[dict]:
    limite = max(1, min(int(limite), 100))
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        sql = "SELECT * FROM solicitudes_ejecucion"
        params: list[Any] = []
        if estado:
            sql += " WHERE estado = %s"
            params.append(estado)
        sql += " ORDER BY id DESC LIMIT %s"
        params.append(limite)
        with conexion.cursor(row_factory=dict_row) as cursor:
            cursor.execute(sql, params)
            return [dict(f) for f in cursor.fetchall()]
    finally:
        if propia:
            conexion.close()


def obtener_ejecucion_de_solicitud(solicitud_id: int, conexion=None) -> dict | None:
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT * FROM ejecuciones_proceso
                WHERE solicitud_id = %s
                """,
                (solicitud_id,),
            )
            fila = cursor.fetchone()
            return dict(fila) if fila else None
    finally:
        if propia:
            conexion.close()


def pid_sesion_viva(pid: int | None, conexion) -> bool:
    if pid is None:
        return False
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_stat_activity
                WHERE pid = %s AND datname = current_database()
            )
            """,
            (pid,),
        )
        return bool(cursor.fetchone()[0])


def registrar_backend_pid(solicitud_id: int, conexion) -> int:
    with conexion.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        pid = int(cursor.fetchone()[0])
        cursor.execute(
            """
            UPDATE solicitudes_ejecucion
            SET backend_pid = %s, heartbeat_en = NOW()
            WHERE id = %s
            """,
            (pid, solicitud_id),
        )
    conexion.commit()
    return pid


def pulso_heartbeat(solicitud_id: int, conexion=None) -> None:
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE solicitudes_ejecucion
                SET heartbeat_en = NOW(),
                    lease_hasta = NOW() + INTERVAL '2 minutes'
                WHERE id = %s AND estado = 'EN_PROCESO'
                """,
                (solicitud_id,),
            )
        conexion.commit()
    finally:
        if propia:
            conexion.close()


def reclamar_solicitud(worker_id: str, conexion=None) -> dict | None:
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                WITH candidata AS (
                    SELECT id
                    FROM solicitudes_ejecucion
                    WHERE estado = 'PENDIENTE'
                      AND intentos_worker < max_intentos
                    ORDER BY id
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE solicitudes_ejecucion AS s
                SET
                    estado = 'EN_PROCESO',
                    reclamada_en = NOW(),
                    heartbeat_en = NOW(),
                    lease_hasta = NOW() + INTERVAL '2 minutes',
                    worker_id = %s,
                    backend_pid = NULL,
                    intentos_worker = s.intentos_worker + 1
                FROM candidata
                WHERE s.id = candidata.id
                RETURNING s.*
                """,
                (worker_id,),
            )
            fila = cursor.fetchone()
        conexion.commit()
        return dict(fila) if fila else None
    finally:
        if propia:
            conexion.close()


def cerrar_desde_ejecucion(solicitud_id: int, conexion=None) -> dict | None:
    """Copia el estado terminal de ejecuciones_proceso.solicitud_id. No relanza."""
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        ejecucion = obtener_ejecucion_de_solicitud(solicitud_id, conexion)
        if not ejecucion or ejecucion["estado"] not in ESTADOS_TERMINALES_PIPELINE:
            return None
        with conexion.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                UPDATE solicitudes_ejecucion
                SET estado = %s,
                    ejecucion_id = %s,
                    finalizada_en = NOW(),
                    mensaje_error = %s,
                    worker_id = NULL
                WHERE id = %s
                RETURNING *
                """,
                (
                    ejecucion["estado"],
                    ejecucion["id"],
                    ejecucion.get("mensaje_error"),
                    solicitud_id,
                ),
            )
            fila = cursor.fetchone()
        conexion.commit()
        return dict(fila) if fila else None
    finally:
        if propia:
            conexion.close()


def marcar_error_pre_pipeline(
    solicitud_id: int,
    mensaje: str,
    reencolar: bool,
    conexion=None,
) -> dict:
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor(row_factory=dict_row) as cursor:
            if reencolar:
                cursor.execute(
                    """
                    UPDATE solicitudes_ejecucion
                    SET estado = 'PENDIENTE',
                        worker_id = NULL,
                        backend_pid = NULL,
                        heartbeat_en = NULL,
                        lease_hasta = NULL,
                        mensaje_error = %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (mensaje, solicitud_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE solicitudes_ejecucion
                    SET estado = 'ERROR_RECUPERACION',
                        finalizada_en = NOW(),
                        mensaje_error = %s,
                        worker_id = NULL
                    WHERE id = %s
                    RETURNING *
                    """,
                    (mensaje, solicitud_id),
                )
            fila = dict(cursor.fetchone())
        conexion.commit()
        return fila
    finally:
        if propia:
            conexion.close()


def marcar_ejecucion_huerfana(ejecucion_id: int, mensaje: str, conexion) -> None:
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            UPDATE ejecuciones_proceso
            SET fecha_fin = NOW(),
                estado = 'ERROR',
                mensaje_error = %s
            WHERE id = %s AND estado = 'EN_PROCESO'
            """,
            (mensaje, ejecucion_id),
        )
    conexion.commit()


def reconciliar_solicitud(solicitud: dict, conexion=None) -> dict:
    """Alinea una solicitud EN_PROCESO con su ejecución por solicitud_id.

    No usa fechas ni la sola presencia del advisory lock global.
    """
    propia = conexion is None
    if propia:
        conexion = conectar()
    solicitud_id = int(solicitud["id"])
    try:
        actual = obtener_solicitud(solicitud_id, conexion)
        if not actual or actual["estado"] != "EN_PROCESO":
            return actual or solicitud
        ejecucion = obtener_ejecucion_de_solicitud(solicitud_id, conexion)
        pid_vivo = pid_sesion_viva(actual.get("backend_pid"), conexion)

        if ejecucion and ejecucion["estado"] in ESTADOS_TERMINALES_PIPELINE:
            cerrado = cerrar_desde_ejecucion(solicitud_id, conexion)
            return cerrado or actual

        if ejecucion and ejecucion["estado"] == "EN_PROCESO" and pid_vivo:
            logger.info(
                "Solicitud %s activa: ejecución %s pid %s vivo",
                solicitud_id,
                ejecucion["id"],
                actual.get("backend_pid"),
            )
            return actual

        if ejecucion and ejecucion["estado"] == "EN_PROCESO" and not pid_vivo:
            marcar_ejecucion_huerfana(
                ejecucion["id"],
                "Interrumpida: sesión del pipeline no está viva",
                conexion,
            )
            cerrado = cerrar_desde_ejecucion(solicitud_id, conexion)
            return cerrado or actual

        if ejecucion is None and pid_vivo:
            logger.info(
                "Solicitud %s sin ejecución aún; pid %s vivo",
                solicitud_id,
                actual.get("backend_pid"),
            )
            return actual

        # Sin ejecución y sesión muerta: fallo anterior al INSERT del pipeline.
        reencolar = actual["intentos_worker"] < actual["max_intentos"]
        return marcar_error_pre_pipeline(
            solicitud_id,
            "Worker interrumpido antes de registrar la ejecución",
            reencolar=reencolar,
            conexion=conexion,
        )
    finally:
        if propia:
            conexion.close()


def reconciliar_huerfanas(conexion=None) -> int:
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT * FROM solicitudes_ejecucion
                WHERE estado = 'EN_PROCESO'
                ORDER BY id
                """
            )
            filas = [dict(f) for f in cursor.fetchall()]
        n = 0
        for fila in filas:
            antes = fila["estado"]
            despues = reconciliar_solicitud(fila, conexion)
            if despues and despues.get("estado") != antes:
                n += 1
        return n
    finally:
        if propia:
            conexion.close()


def resumen_para_api(solicitud: dict, ejecucion: dict | None = None) -> dict:
    if ejecucion is None and solicitud.get("id"):
        try:
            ejecucion = obtener_ejecucion_de_solicitud(int(solicitud["id"]))
        except Exception:
            ejecucion = None
    pipeline = None
    if ejecucion:
        pipeline = {
            "estado": ejecucion.get("estado"),
            "registros_leidos": ejecucion.get("registros_leidos"),
            "registros_nuevos": ejecucion.get("registros_nuevos"),
            "registros_actualizados": ejecucion.get("registros_actualizados"),
            "registros_sin_cambios": ejecucion.get("registros_sin_cambios"),
            "cambios_relevantes": ejecucion.get("cambios_relevantes"),
            "captura_completa": ejecucion.get("captura_completa"),
            "ruta_captura": ejecucion.get("ruta_captura"),
            "mensaje_error": ejecucion.get("mensaje_error"),
        }
    return {
        "ok": True,
        "solicitud_id": solicitud["id"],
        "ejecucion_id": solicitud.get("ejecucion_id")
        or (ejecucion["id"] if ejecucion else None),
        "estado": solicitud["estado"],
        "origen": solicitud["origen"],
        "creada_en": solicitud.get("creada_en"),
        "reclamada_en": solicitud.get("reclamada_en"),
        "finalizada_en": solicitud.get("finalizada_en"),
        "intentos_worker": solicitud.get("intentos_worker"),
        "mensaje_error": solicitud.get("mensaje_error"),
        "pipeline": pipeline,
    }
