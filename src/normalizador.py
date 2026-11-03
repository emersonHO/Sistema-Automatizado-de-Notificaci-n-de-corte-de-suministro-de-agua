"""Normalización de capturas JSON a un DataFrame y CSV."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.calidad import evaluar_calidad
from src.caracteristicas import crear_caracteristicas
from src.config import CARPETA_PROCESSED, CARPETA_RAW
from src.zonas_lima import canonizar_distrito, es_ambito_lima

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CARPETA_PROCESSED.mkdir(parents=True, exist_ok=True)


def cargar_ultimo_json():
    archivos = sorted(
        archivo
        for archivo in CARPETA_RAW.glob("cortes_*.json")
        if not archivo.name.endswith(".meta.json")
    )
    if not archivos:
        raise FileNotFoundError(f"No existen archivos JSON en: {CARPETA_RAW}")
    archivo = archivos[-1]
    logger.info("Archivo seleccionado: %s", archivo)
    with open(archivo, "r", encoding="utf-8") as handle:
        datos = json.load(handle)
    return datos, archivo


def _cargar_meta(archivo_json: Path) -> dict | None:
    meta = Path(str(archivo_json).replace(".json", ".meta.json"))
    if meta.exists():
        return json.loads(meta.read_text(encoding="utf-8"))
    return None


def normalizar(datos):
    if not isinstance(datos, dict):
        raise ValueError("El JSON no tiene formato de objeto.")
    if "data" not in datos:
        raise ValueError("El JSON no contiene el campo 'data'.")
    if not isinstance(datos["data"], list):
        raise ValueError("El campo 'data' no es una lista.")

    df = pd.DataFrame(datos["data"])
    if df.empty:
        return df

    columnas_fecha = [
        "fec_deteccion",
        "fec_estimada",
        "creado_en",
        "actualizado_en",
    ]
    for columna in columnas_fecha:
        if columna in df.columns:
            df[columna] = pd.to_datetime(df[columna], errors="coerce")

    for columna in ("id", "agua", "desague"):
        if columna in df.columns:
            df[columna] = pd.to_numeric(df[columna], errors="coerce")

    columnas_texto = [
        "cod_incidencia",
        "empresa",
        "ciudad",
        "tipo_incid",
        "estado",
        "municipalidad",
        "causa",
        "areas_afectadas",
        "infor_web",
        "descripcion",
        "tipo_red",
        "diametro",
        "facilityid",
        "cod_sunass",
        "vusuario",
        "fuente",
        "imagen_url",
    ]
    for columna in columnas_texto:
        if columna in df.columns:
            df[columna] = df[columna].astype("string").str.strip()

    if "municipalidad" in df.columns:
        canones = df["municipalidad"].map(lambda v: canonizar_distrito(v)[0])
        df["municipalidad_normalizada"] = pd.Series(canones, dtype="string")
        df["ambito_lima"] = df["municipalidad"].map(es_ambito_lima)
    else:
        df["municipalidad_normalizada"] = pd.Series([None] * len(df), dtype="string")
        df["ambito_lima"] = False

    return df


def dataframe_a_registros(df: pd.DataFrame) -> list[dict]:
    registros = []
    for fila in df.to_dict(orient="records"):
        limpio = {}
        for clave, valor in fila.items():
            if valor is None or (isinstance(valor, float) and valor != valor):
                limpio[clave] = None
            elif hasattr(valor, "to_pydatetime"):
                ts = valor.to_pydatetime() if not pd.isna(valor) else None
                limpio[clave] = None if ts is None or pd.isna(valor) else ts
            elif pd.isna(valor):
                limpio[clave] = None
            else:
                limpio[clave] = valor
        if limpio.get("id") is not None:
            limpio["id"] = int(limpio["id"])
        registros.append(limpio)
    return registros


def guardar_dataset(df):
    CARPETA_PROCESSED.mkdir(parents=True, exist_ok=True)
    salida_csv = CARPETA_PROCESSED / "interrupciones_normalizadas.csv"
    fecha = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    salida_historica = CARPETA_PROCESSED / f"interrupciones_{fecha}.csv"
    for ruta in (salida_csv, salida_historica):
        df.to_csv(
            ruta,
            index=False,
            encoding="utf-8-sig",
            sep=",",
            quotechar='"',
            quoting=csv.QUOTE_ALL,
        )
    return salida_csv


def guardar_informe_calidad(informe: dict) -> Path:
    CARPETA_PROCESSED.mkdir(parents=True, exist_ok=True)
    ruta = CARPETA_PROCESSED / "informe_calidad.json"
    ruta.write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return ruta


def normalizar_captura(datos: dict, archivo: Path | None = None) -> tuple[pd.DataFrame, dict, Path]:
    df = normalizar(datos)
    if not df.empty:
        df = crear_caracteristicas(df)
    meta = _cargar_meta(archivo) if archivo else None
    informe = evaluar_calidad(df, meta)
    if not informe["valido"]:
        raise ValueError("Calidad insuficiente: " + "; ".join(informe["errores"]))
    salida = guardar_dataset(df)
    guardar_informe_calidad(informe)
    return df, informe, salida


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print("=" * 60)
    print("NORMALIZADOR DE INTERRUPCIONES DE AGUA")
    print("=" * 60)
    datos, archivo = cargar_ultimo_json()
    df, informe, salida = normalizar_captura(datos, archivo)
    print("Registros:", len(df))
    print("Columnas:", len(df.columns))
    print("Informe de calidad:", json.dumps(informe, ensure_ascii=False, indent=2, default=str))
    print("Dataset:", salida.resolve())


if __name__ == "__main__":
    main()
