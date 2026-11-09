"""Cliente HTTP para la fuente pública de interrupciones.

La API consultada pertenece a un tercero (cortedeagua.net.pe).
No debe describirse como API oficial de SEDAPAL.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from src.config import (
    API_DIAS,
    API_REINTENTOS,
    API_TIMEOUT,
    API_URL,
    BASE_DIR,
    CARPETA_RAW,
    ZONA_SISTEMA,
)

logger = logging.getLogger(__name__)

URL = API_URL
DIAS = API_DIAS
CARPETA_RAW.mkdir(parents=True, exist_ok=True)


class CapturaIncompletaError(Exception):
    """La fuente reportó más registros de los recibidos."""


class RespuestaFuenteError(Exception):
    """La respuesta no es utilizable."""


def _ahora_local() -> datetime:
    return datetime.now(ZoneInfo(ZONA_SISTEMA))


def obtener_datos(dias: int | None = None, sesion: requests.Session | None = None) -> dict:
    """Consulta la API con reintentos limitados y backoff lineal."""
    parametro = API_DIAS if dias is None else dias
    cliente = sesion or requests
    ultimo_error: Exception | None = None

    for intento in range(1, API_REINTENTOS + 1):
        try:
            respuesta = cliente.get(
                API_URL,
                params={"dias": parametro},
                timeout=API_TIMEOUT,
            )
            respuesta.raise_for_status()
            try:
                datos = respuesta.json()
            except ValueError as error:
                raise RespuestaFuenteError("La respuesta no es un JSON válido.") from error
            return datos
        except (requests.RequestException, RespuestaFuenteError) as error:
            ultimo_error = error
            logger.warning(
                "Fallo al consultar la fuente (intento %s/%s): %s",
                intento,
                API_REINTENTOS,
                error,
            )
            if intento < API_REINTENTOS:
                time.sleep(intento * 2)

    raise RespuestaFuenteError(
        f"No se pudo consultar la fuente después de {API_REINTENTOS} intentos: {ultimo_error}"
    ) from ultimo_error


def validar_respuesta(datos: object) -> dict:
    if not isinstance(datos, dict):
        raise RespuestaFuenteError("La respuesta no tiene formato de objeto JSON.")
    if datos.get("ok") is not True:
        raise RespuestaFuenteError("La API indicó que la consulta no fue exitosa.")
    if "data" not in datos:
        raise RespuestaFuenteError("La respuesta no contiene el campo 'data'.")
    if not isinstance(datos["data"], list):
        raise RespuestaFuenteError("El campo 'data' no es una lista.")
    return {"ok": True}


def analizar_completitud(datos: dict) -> dict:
    registros = datos.get("data") or []
    total_recibido = len(registros)
    total_reportado = datos.get("total")
    anomalias: list[str] = []
    completa = True

    if total_reportado is not None:
        try:
            total_reportado_int = int(total_reportado)
        except (TypeError, ValueError):
            total_reportado_int = None
            anomalias.append("El campo 'total' no es numérico.")
            completa = False
        else:
            if total_recibido < total_reportado_int:
                completa = False
                anomalias.append(
                    "La fuente reportó más registros de los recibidos; "
                    "la captura no se considera completa."
                )
            elif total_recibido > total_reportado_int:
                anomalias.append(
                    "Se recibieron más registros que el total reportado."
                )
    else:
        total_reportado_int = None
        anomalias.append("La respuesta no incluye el campo 'total'.")

    return {
        "total_recibido": total_recibido,
        "total_reportado": total_reportado_int,
        "captura_completa": completa,
        "anomalias": anomalias,
        "last_sync": datos.get("last_sync"),
        "last_new_at": datos.get("last_new_at"),
    }


def guardar_respuesta(datos: dict, dias: int | None = None, extra_meta: dict | None = None) -> Path:
    CARPETA_RAW.mkdir(parents=True, exist_ok=True)
    fecha = _ahora_local()
    nombre = f"cortes_{fecha:%Y%m%d_%H%M%S_%f}"
    ruta = CARPETA_RAW / f"{nombre}.json"
    ruta_meta = CARPETA_RAW / f"{nombre}.meta.json"
    completitud = analizar_completitud(datos)

    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)

    metadatos = {
        "fecha_captura_local": fecha.isoformat(),
        "fecha_captura_utc": datetime.now(timezone.utc).isoformat(),
        "zona_sistema": ZONA_SISTEMA,
        "fuente_url": API_URL,
        "nota_fuente": (
            "Fuente pública de un tercero. No es una API oficial de SEDAPAL."
        ),
        "parametro_dias": API_DIAS if dias is None else dias,
        "total_recibido": completitud["total_recibido"],
        "total_reportado": completitud["total_reportado"],
        "captura_completa": completitud["captura_completa"],
        "anomalias": completitud["anomalias"],
        "last_sync": completitud["last_sync"],
        "last_new_at": completitud["last_new_at"],
        "ruta_archivo": str(ruta),
    }
    if extra_meta:
        metadatos.update(extra_meta)

    with open(ruta_meta, "w", encoding="utf-8") as archivo:
        json.dump(metadatos, archivo, ensure_ascii=False, indent=2)

    if not completitud["captura_completa"]:
        logger.warning("Captura incompleta: %s", "; ".join(completitud["anomalias"]))

    return ruta


def cargar_json(ruta: Path) -> dict:
    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def recolectar(dias: int | None = None, sesion: requests.Session | None = None) -> tuple[dict, Path, dict]:
    datos = obtener_datos(dias=dias, sesion=sesion)
    validar_respuesta(datos)
    ruta = guardar_respuesta(datos, dias=dias)
    meta_path = Path(str(ruta).removesuffix(".json") + ".meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return datos, ruta, meta


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print("=" * 60)
    print("RECOLECTOR DE INTERRUPCIONES DE AGUA")
    print("=" * 60)
    print("Fuente (tercero):", API_URL)
    print("Parámetro dias:", API_DIAS)
    datos, ruta, meta = recolectar()
    print("Consulta realizada correctamente")
    print("Registros obtenidos:", meta.get("total_recibido"))
    print("Total reportado:", meta.get("total_reportado"))
    print("Captura completa:", meta.get("captura_completa"))
    print("Datos almacenados en:", ruta)
    print("Proyecto base:", BASE_DIR)


if __name__ == "__main__":
    main()
