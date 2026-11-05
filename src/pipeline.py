"""Orquestación del pipeline completo.

Uso:
    python -m src.pipeline
    python -m src.pipeline --desde-archivo data/raw/ejemplo.json
    python -m src.pipeline --procesar-outbox
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from psycopg.types.json import Jsonb

from src.config import API_DIAS, CARPETA_RAW, LOCK_KEY
from src.db import aplicar_esquema, conectar
from src.normalizador import dataframe_a_registros, normalizar_captura
from src.notificaciones import (
    crear_coincidencias_y_notificaciones,
    notificar_incidencias_vigentes_sin_aviso,
    procesar_outbox,
)
from src.persistencia import persistir_registros
from src.recolector import RespuestaFuenteError, cargar_json, recolectar
from src.suscripciones import sembrar_zonas

logger = logging.getLogger(__name__)


def _ms(inicio: float) -> int:
    return int((time.perf_counter() - inicio) * 1000)


def ejecutar_pipeline(
    dias: int | None = None,
    desde_archivo: Path | None = None,
    procesar_envios: bool = True,
    forzar_simulacion: bool = True,
) -> dict:
    aplicar_esquema()
    conexion = conectar()
    sembrar_zonas(conexion)
    conexion.commit()

    with conexion.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,))
        obtenido = cursor.fetchone()[0]
    conexion.commit()
    if not obtenido:
        raise RuntimeError("Hay otra ejecución del pipeline en curso.")

    with conexion.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO ejecuciones_proceso (estado)
            VALUES ('EN_PROCESO')
            RETURNING id
            """
        )
        ejecucion_id = cursor.fetchone()[0]
    conexion.commit()

    tiempos: dict[str, int | None] = {
        "tiempo_descarga_ms": None,
        "tiempo_normalizacion_ms": None,
        "tiempo_persistencia_ms": None,
        "tiempo_correspondencia_ms": None,
        "tiempo_notificaciones_ms": None,
    }
    ruta_captura = None
    captura_completa = True
    resultado: dict = {"ejecucion_id": ejecucion_id, "estado": "EN_PROCESO"}

    try:
        t0 = time.perf_counter()
        if desde_archivo:
            datos = cargar_json(Path(desde_archivo))
            ruta_captura = str(Path(desde_archivo))
            from src.recolector import validar_respuesta, analizar_completitud, guardar_respuesta

            validar_respuesta(datos)
            if Path(desde_archivo).parent != CARPETA_RAW:
                ruta = guardar_respuesta(datos, dias=dias)
                ruta_captura = str(ruta)
            meta = analizar_completitud(datos)
        else:
            datos, ruta, meta = recolectar(dias=dias)
            ruta_captura = str(ruta)
        tiempos["tiempo_descarga_ms"] = _ms(t0)
        captura_completa = bool(meta.get("captura_completa", True))

        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO capturas (
                    ejecucion_id, parametro_dias, total_reportado, total_recibido,
                    captura_completa, last_sync, last_new_at, ruta_archivo, anomalias
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ejecucion_id,
                    dias if dias is not None else API_DIAS,
                    meta.get("total_reportado"),
                    meta.get("total_recibido"),
                    captura_completa,
                    str(meta.get("last_sync")) if meta.get("last_sync") is not None else None,
                    str(meta.get("last_new_at")) if meta.get("last_new_at") is not None else None,
                    ruta_captura,
                    Jsonb(meta.get("anomalias") or []),
                ),
            )
        conexion.commit()

        t1 = time.perf_counter()
        archivo = Path(ruta_captura) if ruta_captura else None
        df, informe, _salida = normalizar_captura(datos, archivo)
        registros = dataframe_a_registros(df)
        tiempos["tiempo_normalizacion_ms"] = int((time.perf_counter() - t1) * 1000)

        t2 = time.perf_counter()
        persistido = persistir_registros(registros, conexion=conexion, ejecucion_id=ejecucion_id)
        conexion.commit()
        tiempos["tiempo_persistencia_ms"] = int((time.perf_counter() - t2) * 1000)

        t3 = time.perf_counter()
        notif = crear_coincidencias_y_notificaciones(
            conexion,
            registros,
            persistido["eventos_notificables"],
            ejecucion_id,
        )
        vigentes = notificar_incidencias_vigentes_sin_aviso(conexion, ejecucion_id)
        notif = {
            "coincidencias": notif["coincidencias"] + vigentes["coincidencias"],
            "coincidencias_ambiguas": notif["coincidencias_ambiguas"] + vigentes["coincidencias_ambiguas"],
            "notificaciones_creadas": notif["notificaciones_creadas"] + vigentes["notificaciones_creadas"],
        }
        conexion.commit()
        tiempos["tiempo_correspondencia_ms"] = int((time.perf_counter() - t3) * 1000)

        envio = {"procesadas": 0, "modo": "omitido"}
        t4 = time.perf_counter()
        if procesar_envios:
            envio = procesar_outbox(conexion, forzar_simulacion=forzar_simulacion)
            conexion.commit()
        tiempos["tiempo_notificaciones_ms"] = int((time.perf_counter() - t4) * 1000)

        c = persistido["contadores"]
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ejecuciones_proceso SET
                    fecha_fin = NOW(),
                    estado = CASE WHEN %s THEN 'COMPLETADO' ELSE 'COMPLETADO_INCOMPLETO' END,
                    registros_leidos = %s,
                    registros_nuevos = %s,
                    registros_actualizados = %s,
                    registros_sin_cambios = %s,
                    cambios_origen = %s,
                    cambios_relevantes = %s,
                    cambios_tecnicos = %s,
                    coincidencias = %s,
                    coincidencias_ambiguas = %s,
                    notificaciones_creadas = %s,
                    captura_completa = %s,
                    tiempo_descarga_ms = %s,
                    tiempo_normalizacion_ms = %s,
                    tiempo_persistencia_ms = %s,
                    tiempo_correspondencia_ms = %s,
                    tiempo_notificaciones_ms = %s,
                    ruta_captura = %s,
                    detalle = %s
                WHERE id = %s
                """,
                (
                    captura_completa,
                    len(registros),
                    c["nuevo"],
                    c["actualizado"],
                    c["sin_cambios"],
                    c["cambios_origen"],
                    c["cambios_relevantes"],
                    c["cambios_tecnicos"],
                    notif["coincidencias"],
                    notif["coincidencias_ambiguas"],
                    notif["notificaciones_creadas"],
                    captura_completa,
                    tiempos["tiempo_descarga_ms"],
                    tiempos["tiempo_normalizacion_ms"],
                    tiempos["tiempo_persistencia_ms"],
                    tiempos["tiempo_correspondencia_ms"],
                    tiempos["tiempo_notificaciones_ms"],
                    ruta_captura,
                    Jsonb(
                        {
                            "calidad": informe,
                            "envio": envio,
                            "fin_utc": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                    ejecucion_id,
                ),
            )
        conexion.commit()
        resultado.update(
            {
                "estado": "COMPLETADO" if captura_completa else "COMPLETADO_INCOMPLETO",
                "contadores": c,
                "coincidencias": notif,
                "envio": envio,
                "tiempos_ms": tiempos,
                "captura_completa": captura_completa,
                "ruta_captura": ruta_captura,
                "registros": len(registros),
                "calidad": informe,
            }
        )
        return resultado
    except Exception as error:
        logger.exception("Fallo del pipeline")
        conexion.rollback()
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ejecuciones_proceso
                SET fecha_fin = NOW(), estado = 'ERROR', mensaje_error = %s,
                    tiempo_descarga_ms = %s, tiempo_normalizacion_ms = %s,
                    tiempo_persistencia_ms = %s, ruta_captura = %s
                WHERE id = %s
                """,
                (
                    str(error),
                    tiempos["tiempo_descarga_ms"],
                    tiempos["tiempo_normalizacion_ms"],
                    tiempos["tiempo_persistencia_ms"],
                    ruta_captura,
                    ejecucion_id,
                ),
            )
        conexion.commit()
        resultado.update({"estado": "ERROR", "error": str(error)})
        raise
    finally:
        try:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
            conexion.commit()
        finally:
            conexion.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline de interrupciones de agua")
    parser.add_argument("--dias", type=int, default=None)
    parser.add_argument("--desde-archivo", type=Path, default=None)
    parser.add_argument("--procesar-outbox", action="store_true", default=True)
    parser.add_argument("--sin-outbox", action="store_true")
    parser.add_argument("--envio-real", action="store_true", help="Requiere SMTP_ENABLED=true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        resultado = ejecutar_pipeline(
            dias=args.dias,
            desde_archivo=args.desde_archivo,
            procesar_envios=not args.sin_outbox,
            forzar_simulacion=not args.envio_real,
        )
    except RespuestaFuenteError as error:
        print("Fallo de la fuente pública. Se conservan los datos previos.")
        print(error)
        return 2
    except RuntimeError as error:
        print(error)
        return 3

    print("=" * 60)
    print("PIPELINE COMPLETADO")
    print("=" * 60)
    print(json.dumps(
        {k: v for k, v in resultado.items() if k != "calidad"},
        ensure_ascii=False,
        indent=2,
        default=str,
    ))
    return 0 if resultado.get("estado") != "ERROR" else 1


if __name__ == "__main__":
    sys.exit(main())
