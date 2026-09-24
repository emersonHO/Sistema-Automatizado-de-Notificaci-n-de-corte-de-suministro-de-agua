import json
import csv
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent

CARPETA_RAW = BASE_DIR / "data" / "raw"
CARPETA_PROCESSED = BASE_DIR / "data" / "processed"

CARPETA_PROCESSED.mkdir(parents=True, exist_ok=True)


def cargar_ultimo_json():
    """Carga el archivo JSON más reciente de data/raw."""

    archivos = sorted(CARPETA_RAW.glob("cortes_*.json"))

    if not archivos:
        raise FileNotFoundError(
            f"No existen archivos JSON en: {CARPETA_RAW}"
        )

    archivo = archivos[-1]

    print("Archivo seleccionado:")
    print(archivo.resolve())

    with open(archivo, "r", encoding="utf-8") as f:
        datos = json.load(f)

    return datos, archivo


def normalizar(datos):
    """Convierte los registros de la API en un DataFrame normalizado."""

    if not isinstance(datos, dict):
        raise ValueError("El JSON no tiene formato de objeto.")

    if "data" not in datos:
        raise ValueError("El JSON no contiene el campo 'data'.")

    if not isinstance(datos["data"], list):
        raise ValueError("El campo 'data' no es una lista.")

    df = pd.DataFrame(datos["data"])

    # Fechas  
    columnas_fecha = [
        "fec_deteccion",
        "fec_estimada",
        "creado_en",
        "actualizado_en"
    ]

    for columna in columnas_fecha:

        if columna in df.columns:

            df[columna] = pd.to_datetime(
                df[columna],
                errors="coerce"
            )

    # Variables numéricas
    columnas_numericas = [
        "id",
        "agua",
        "desague"
    ]

    for columna in columnas_numericas:

        if columna in df.columns:

            df[columna] = pd.to_numeric(
                df[columna],
                errors="coerce"
            )

    # Variables de texto
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
        "imagen_url"
    ]

    for columna in columnas_texto:

        if columna in df.columns:

            df[columna] = (
                df[columna]
                .astype("string")
                .str.strip()
            )

    return df


def guardar_dataset(df):

    salida_csv = (
        CARPETA_PROCESSED /
        "interrupciones_normalizadas.csv"
    )

    df.to_csv(
        salida_csv,
        index=False,
        encoding="utf-8-sig",
        sep=",",
        quotechar='"',
        quoting=csv.QUOTE_ALL
    )

    return salida_csv


def main():

    print("=" * 60)
    print("NORMALIZADOR DE INTERRUPCIONES DE AGUA")
    print("=" * 60)

    datos, archivo = cargar_ultimo_json()

    df = normalizar(datos)

    print()
    print("Registros:", len(df))
    print("Columnas:", len(df.columns))

    print()
    print("Columnas encontradas:")
    for columna in df.columns:
        print(f"  - {columna}")

    print()
    print("Tipos de datos:")
    print(df.dtypes)

    salida = guardar_dataset(df)

    print()
    print("Dataset normalizado:")
    print(salida.resolve())

    print()
    print("¿Archivo creado?:", salida.exists())


if __name__ == "__main__":
    main()