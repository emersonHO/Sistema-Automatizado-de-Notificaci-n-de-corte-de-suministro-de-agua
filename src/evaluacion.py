"""Indicadores técnicos a partir de casos etiquetados y ejecuciones reales.

No inventa métricas: si no hay casos etiquetados, el reporte lo declara.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from src.config import BASE_DIR, CARPETA_EVALUACION
from src.correspondencia import coincidencia_notificable, evaluar_par
from src.db import conectar
from src.hashes import hash_origen, hash_relevante
from src.persistencia import tipo_evento_historial


def precision_recall(resultados: list[dict]) -> dict:
    vp = sum(1 for r in resultados if r["esperado"] and r["obtenido"])
    fp = sum(1 for r in resultados if (not r["esperado"]) and r["obtenido"])
    fn = sum(1 for r in resultados if r["esperado"] and (not r["obtenido"]))
    vn = sum(1 for r in resultados if (not r["esperado"]) and (not r["obtenido"]))
    precision = vp / (vp + fp) if (vp + fp) else None
    recall = vp / (vp + fn) if (vp + fn) else None
    return {
        "vp": vp,
        "fp": fp,
        "fn": fn,
        "vn": vn,
        "precision": precision,
        "recall": recall,
        "casos": len(resultados),
    }


def evaluar_correspondencia_etiquetada(casos: list[dict]) -> dict:
    """Cada caso: interrupcion, zona, esperado (bool), opcionalmente estado_esperado."""
    detalle = []
    for caso in casos:
        resultado = evaluar_par(caso["interrupcion"], caso["zona"])
        obtenido = coincidencia_notificable(resultado)
        detalle.append(
            {
                "id": caso.get("id"),
                "esperado": bool(caso["esperado"]),
                "obtenido": obtenido,
                "estado_obtenido": None if resultado is None else resultado["estado"],
                "nivel_obtenido": None if resultado is None else resultado["nivel"],
                "explicacion": None if resultado is None else resultado["explicacion"],
            }
        )
    metricas = precision_recall(detalle)
    metricas["detalle"] = detalle
    return metricas


def evaluar_deteccion_cambios(casos: list[dict]) -> dict:
    """Casos: {anterior, actual, espera_origen, espera_relevante, espera_evento?}."""
    correctos_origen = 0
    correctos_relevante = 0
    correctos_evento = 0
    detalle = []
    for caso in casos:
        anterior = caso.get("anterior")
        actual = caso["actual"]
        h_or_a = hash_origen(anterior) if anterior else None
        h_or_b = hash_origen(actual)
        h_re_a = hash_relevante(anterior) if anterior else None
        h_re_b = hash_relevante(actual)
        cambio_origen = h_or_a != h_or_b
        cambio_relevante = h_re_a != h_re_b
        evento = tipo_evento_historial(anterior, actual, cambio_relevante)
        ok_origen = cambio_origen == bool(caso["espera_origen"])
        ok_rel = cambio_relevante == bool(caso["espera_relevante"])
        ok_evento = True
        if "espera_evento" in caso:
            ok_evento = evento == caso["espera_evento"]
        correctos_origen += int(ok_origen)
        correctos_relevante += int(ok_rel)
        correctos_evento += int(ok_evento)
        detalle.append(
            {
                "id": caso.get("id"),
                "cambio_origen": cambio_origen,
                "cambio_relevante": cambio_relevante,
                "evento": evento,
                "ok_origen": ok_origen,
                "ok_relevante": ok_rel,
                "ok_evento": ok_evento,
            }
        )
    n = len(casos) or 1
    return {
        "casos": len(casos),
        "aciertos_origen": correctos_origen,
        "aciertos_relevante": correctos_relevante,
        "aciertos_evento": correctos_evento,
        "exactitud_origen": correctos_origen / n if casos else None,
        "exactitud_relevante": correctos_relevante / n if casos else None,
        "detalle": detalle,
    }


def metricas_ejecuciones(conexion=None) -> dict:
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) ,
                       COUNT(*) FILTER (WHERE estado LIKE 'COMPLETADO%'),
                       COUNT(*) FILTER (WHERE estado = 'ERROR'),
                       AVG(EXTRACT(EPOCH FROM (fecha_fin - fecha_inicio)))
                           FILTER (WHERE fecha_fin IS NOT NULL),
                       AVG(tiempo_descarga_ms),
                       AVG(tiempo_normalizacion_ms),
                       AVG(tiempo_persistencia_ms),
                       AVG(tiempo_correspondencia_ms),
                       AVG(tiempo_notificaciones_ms)
                FROM ejecuciones_proceso
                """
            )
            fila = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM interrupciones")
            total_inc = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM notificaciones")
            total_n = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT estado, COUNT(*) FROM notificaciones GROUP BY estado
                """
            )
            estados = {row[0]: row[1] for row in cursor.fetchall()}
        return {
            "ejecuciones": fila[0],
            "ejecuciones_ok": fila[1],
            "ejecuciones_error": fila[2],
            "duracion_promedio_s": float(fila[3]) if fila[3] is not None else None,
            "promedio_descarga_ms": float(fila[4]) if fila[4] is not None else None,
            "promedio_normalizacion_ms": float(fila[5]) if fila[5] is not None else None,
            "promedio_persistencia_ms": float(fila[6]) if fila[6] is not None else None,
            "promedio_correspondencia_ms": float(fila[7]) if fila[7] is not None else None,
            "promedio_notificaciones_ms": float(fila[8]) if fila[8] is not None else None,
            "interrupciones": total_inc,
            "notificaciones": total_n,
            "notificaciones_por_estado": estados,
        }
    finally:
        if propia:
            conexion.close()


def escribir_reporte(nombre: str, payload: dict) -> Path:
    CARPETA_EVALUACION.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ruta_json = CARPETA_EVALUACION / f"{nombre}_{stamp}.json"
    ruta_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    if "detalle" in payload:
        ruta_csv = CARPETA_EVALUACION / f"{nombre}_{stamp}.csv"
        filas = payload["detalle"]
        if filas:
            with open(ruta_csv, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(filas[0].keys()))
                writer.writeheader()
                writer.writerows(filas)
    return ruta_json


def main() -> None:
    from src.casos_evaluacion import CASOS_CAMBIOS, CASOS_CORRESPONDENCIA

    corr = evaluar_correspondencia_etiquetada(CASOS_CORRESPONDENCIA)
    camb = evaluar_deteccion_cambios(CASOS_CAMBIOS)
    try:
        ejec = metricas_ejecuciones()
    except Exception as error:
        ejec = {"error": str(error), "nota": "No se leyeron ejecuciones reales de PostgreSQL."}
    reporte = {
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "correspondencia": {k: v for k, v in corr.items() if k != "detalle"},
        "deteccion_cambios": {k: v for k, v in camb.items() if k != "detalle"},
        "ejecuciones": ejec,
        "limitaciones": [
            "La precisión y el recall se calculan solo sobre casos etiquetados, no sobre predicciones del sistema usadas como verdad.",
            "La latencia de detección respecto a la publicación en la fuente solo puede medirse en pruebas controladas; la API no documenta una fecha de publicación contractual.",
            "ACEPTADA_SMTP no implica entrega al buzón del usuario.",
        ],
    }
    ruta = escribir_reporte("reporte_evaluacion", reporte)
    escribir_reporte("correspondencia_detalle", corr)
    escribir_reporte("cambios_detalle", camb)
    print(json.dumps({"ruta": str(ruta), **reporte}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
