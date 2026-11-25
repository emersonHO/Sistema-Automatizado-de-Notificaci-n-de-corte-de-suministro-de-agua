"""Métricas de observabilidad calculadas desde PostgreSQL.

No inventa valores: si no hay filas, los promedios y percentiles quedan en null.
SIMULADA no se interpreta como correo enviado.
COMPLETADO_INCOMPLETO no se clasifica como ERROR.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from psycopg.rows import dict_row

from src.db import conectar

ZONA_METRICAS = "UTC"


def _num(valor):
    if valor is None:
        return None
    return float(valor)


def _int(valor) -> int:
    return int(valor or 0)


def memoria_proceso_kb() -> int | None:
    try:
        for linea in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
            if linea.startswith("VmRSS:"):
                return int(linea.split()[1])
    except OSError:
        return None
    return None


def postgres_ok(conexion=None) -> bool:
    propia = conexion is None
    if propia:
        try:
            conexion = conectar()
        except Exception:
            return False
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:
        return False
    finally:
        if propia:
            conexion.close()


def _duraciones_pipeline(cursor) -> dict:
    cursor.execute(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE estado = 'COMPLETADO') AS completadas,
            COUNT(*) FILTER (WHERE estado = 'COMPLETADO_INCOMPLETO') AS incompletas,
            COUNT(*) FILTER (WHERE estado = 'ERROR') AS fallidas,
            COUNT(*) FILTER (WHERE estado = 'EN_PROCESO') AS en_proceso,
            AVG(EXTRACT(EPOCH FROM (fecha_fin - fecha_inicio)))
                FILTER (WHERE fecha_fin IS NOT NULL) AS duracion_promedio_s,
            AVG(tiempo_descarga_ms) AS promedio_descarga_ms,
            AVG(tiempo_normalizacion_ms) AS promedio_normalizacion_ms,
            AVG(tiempo_persistencia_ms) AS promedio_persistencia_ms,
            AVG(tiempo_correspondencia_ms) AS promedio_correspondencia_ms,
            AVG(tiempo_notificaciones_ms) AS promedio_notificaciones_ms,
            SUM(registros_leidos) AS registros_leidos,
            SUM(registros_nuevos) AS registros_nuevos,
            SUM(registros_actualizados) AS registros_actualizados,
            SUM(registros_sin_cambios) AS registros_sin_cambios,
            SUM(notificaciones_creadas) AS notificaciones_generadas
        FROM ejecuciones_proceso
        """
    )
    fila = dict(cursor.fetchone())
    cursor.execute(
        """
        SELECT
            percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (fecha_fin - fecha_inicio)))
                AS duracion_mediana_s,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (fecha_fin - fecha_inicio)))
                AS duracion_p95_s
        FROM ejecuciones_proceso
        WHERE fecha_fin IS NOT NULL
        """
    )
    percentiles = dict(cursor.fetchone() or {})
    fila["duracion_mediana_s"] = percentiles.get("duracion_mediana_s")
    fila["duracion_p95_s"] = percentiles.get("duracion_p95_s")
    cursor.execute(
        """
        SELECT id, estado, fecha_inicio, fecha_fin, registros_leidos,
               solicitud_id, mensaje_error, captura_completa
        FROM ejecuciones_proceso
        ORDER BY fecha_inicio DESC
        LIMIT 1
        """
    )
    ultima = cursor.fetchone()
    terminales = _int(fila["completadas"]) + _int(fila["incompletas"]) + _int(fila["fallidas"])
    sin_error = _int(fila["completadas"]) + _int(fila["incompletas"])
    return {
        "total": _int(fila["total"]),
        "completadas": _int(fila["completadas"]),
        "incompletas": _int(fila["incompletas"]),
        "fallidas": _int(fila["fallidas"]),
        "en_proceso": _int(fila["en_proceso"]),
        "duracion_promedio_s": _num(fila["duracion_promedio_s"]),
        "duracion_mediana_s": _num(fila["duracion_mediana_s"]),
        "duracion_p95_s": _num(fila["duracion_p95_s"]),
        "promedio_descarga_ms": _num(fila["promedio_descarga_ms"]),
        "promedio_normalizacion_ms": _num(fila["promedio_normalizacion_ms"]),
        "promedio_persistencia_ms": _num(fila["promedio_persistencia_ms"]),
        "promedio_correspondencia_ms": _num(fila["promedio_correspondencia_ms"]),
        "promedio_notificaciones_ms": _num(fila["promedio_notificaciones_ms"]),
        "registros_leidos": _int(fila["registros_leidos"]),
        "registros_nuevos": _int(fila["registros_nuevos"]),
        "registros_actualizados": _int(fila["registros_actualizados"]),
        "registros_sin_cambios": _int(fila["registros_sin_cambios"]),
        "notificaciones_generadas": _int(fila["notificaciones_generadas"]),
        "tasa_sin_error": (sin_error / terminales) if terminales else None,
        "tasa_completo_estricto": (_int(fila["completadas"]) / terminales) if terminales else None,
        "ultima": dict(ultima) if ultima else None,
        "notas": [
            "COMPLETADO_INCOMPLETO cuenta como ejecución sin error (captura incompleta), no como fallida.",
            "Los percentiles requieren al menos una ejecución con fecha_fin.",
        ],
    }


def _solicitudes(cursor) -> dict:
    cursor.execute(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE estado = 'PENDIENTE') AS pendientes,
            COUNT(*) FILTER (WHERE estado = 'EN_PROCESO') AS en_proceso,
            COUNT(*) FILTER (WHERE estado = 'ERROR') AS error,
            COUNT(*) FILTER (WHERE estado = 'ERROR_RECUPERACION') AS recuperacion,
            COUNT(*) FILTER (WHERE estado = 'CANCELADA') AS canceladas,
            AVG(EXTRACT(EPOCH FROM (reclamada_en - creada_en)))
                FILTER (WHERE reclamada_en IS NOT NULL) AS espera_promedio_s
        FROM solicitudes_ejecucion
        """
    )
    fila = dict(cursor.fetchone())
    cursor.execute(
        """
        SELECT percentile_cont(0.5) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM (reclamada_en - creada_en))
        ) AS espera_mediana_s
        FROM solicitudes_ejecucion
        WHERE reclamada_en IS NOT NULL
        """
    )
    mediana = cursor.fetchone()
    fila["espera_mediana_s"] = mediana["espera_mediana_s"] if mediana else None
    return {
        "total": _int(fila["total"]),
        "pendientes": _int(fila["pendientes"]),
        "en_proceso": _int(fila["en_proceso"]),
        "error": _int(fila["error"]),
        "recuperacion": _int(fila["recuperacion"]),
        "canceladas": _int(fila["canceladas"]),
        "espera_cola_promedio_s": _num(fila["espera_promedio_s"]),
        "espera_cola_mediana_s": _num(fila["espera_mediana_s"]),
        "formula_espera": "reclamada_en - creada_en (UTC)",
    }


def _notificaciones(cursor) -> dict:
    cursor.execute(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE estado = 'PENDIENTE') AS pendientes,
            COUNT(*) FILTER (WHERE estado = 'EN_PROCESO') AS en_proceso,
            COUNT(*) FILTER (WHERE estado = 'SIMULADA') AS simuladas,
            COUNT(*) FILTER (WHERE estado = 'REINTENTANDO') AS reintentando,
            COUNT(*) FILTER (WHERE estado = 'FALLIDA') AS fallidas,
            COUNT(*) FILTER (WHERE estado = 'CANCELADA') AS canceladas,
            COUNT(*) FILTER (WHERE estado = 'DESCARTADA') AS descartadas,
            COUNT(*) FILTER (WHERE estado = 'ACEPTADA_SMTP') AS aceptadas_smtp,
            COUNT(*) FILTER (WHERE estado = 'ERROR') AS error,
            COALESCE(SUM(intentos), 0) AS intentos_acumulados,
            COALESCE(SUM(GREATEST(intentos - 1, 0)), 0) AS reintentos,
            COALESCE(SUM(recuperaciones), 0) AS recuperaciones,
            AVG(EXTRACT(EPOCH FROM (procesada_en - creada_en)))
                FILTER (WHERE procesada_en IS NOT NULL) AS espera_promedio_s,
            AVG(EXTRACT(EPOCH FROM (finalizada_en - procesada_en)))
                FILTER (WHERE finalizada_en IS NOT NULL AND procesada_en IS NOT NULL)
                AS procesamiento_promedio_s
        FROM notificaciones
        """
    )
    fila = dict(cursor.fetchone())
    cursor.execute(
        """
        SELECT resultado, COUNT(*) AS n
        FROM intentos_notificacion
        GROUP BY resultado
        """
    )
    intentos_por_resultado = {row["resultado"]: row["n"] for row in cursor.fetchall()}
    cursor.execute("SELECT COUNT(*) AS n FROM intentos_notificacion")
    total_intentos_filas = cursor.fetchone()["n"]
    simuladas = _int(fila["simuladas"])
    fallidas = _int(fila["fallidas"])
    terminales_sim = simuladas + fallidas + _int(fila["aceptadas_smtp"])
    return {
        "total": _int(fila["total"]),
        "pendientes": _int(fila["pendientes"]),
        "en_proceso": _int(fila["en_proceso"]),
        "simuladas": simuladas,
        "reintentando": _int(fila["reintentando"]),
        "fallidas": fallidas,
        "canceladas": _int(fila["canceladas"]),
        "descartadas": _int(fila["descartadas"]),
        "aceptadas_smtp": _int(fila["aceptadas_smtp"]),
        "error": _int(fila["error"]),
        "intentos_acumulados_en_filas": _int(fila["intentos_acumulados"]),
        "filas_intentos": _int(total_intentos_filas),
        "reintentos": _int(fila["reintentos"]),
        "recuperaciones": _int(fila["recuperaciones"]),
        "espera_cola_promedio_s": _num(fila["espera_promedio_s"]),
        "procesamiento_promedio_s": _num(fila["procesamiento_promedio_s"]),
        "tasa_simulacion_exitosa": (simuladas / terminales_sim) if terminales_sim else None,
        "intentos_por_resultado": intentos_por_resultado,
        "notas": [
            "SIMULADA no equivale a correo enviado ni recibido.",
            "reintentos = sum(GREATEST(intentos - 1, 0)) sobre notificaciones.",
            "recuperaciones se incrementan al devolver EN_PROCESO huérfanas.",
        ],
    }


def _capacidad(cursor) -> dict:
    cursor.execute("SELECT COUNT(*) AS n FROM interrupciones")
    interrupciones = cursor.fetchone()["n"]
    cursor.execute(
        """
        SELECT COUNT(*) FILTER (WHERE correo_confirmado) AS confirmados
        FROM usuarios
        """
    )
    destinatarios = cursor.fetchone()["confirmados"]
    cursor.execute(
        """
        SELECT COUNT(*) FILTER (WHERE activa AND confirmada) AS n
        FROM suscripciones
        """
    )
    suscripciones = cursor.fetchone()["n"]
    return {
        "interrupciones_persistidas": _int(interrupciones),
        "destinatarios_confirmados": _int(destinatarios),
        "suscripciones_activas": _int(suscripciones),
    }


def snapshot(conexion=None) -> dict:
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor(row_factory=dict_row) as cursor:
            pipeline = _duraciones_pipeline(cursor)
            solicitudes = _solicitudes(cursor)
            notificaciones = _notificaciones(cursor)
            capacidad = _capacidad(cursor)
        return {
            "generado_utc": datetime.now(timezone.utc).isoformat(),
            "zona_timestamps": ZONA_METRICAS,
            "pipeline": pipeline,
            "solicitudes": solicitudes,
            "notificaciones": notificaciones,
            "capacidad": capacidad,
            "proceso": {"rss_kb": memoria_proceso_kb()},
        }
    finally:
        if propia:
            conexion.close()
