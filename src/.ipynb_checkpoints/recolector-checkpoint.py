import requests
import json
from datetime import datetime
from pathlib import Path


URL = "https://cortedeagua.net.pe/api.php"

DIAS = 14

BASE_DIR = Path(__file__).resolve().parent.parent
CARPETA_RAW = BASE_DIR / "data" / "raw"
CARPETA_RAW.mkdir(parents=True, exist_ok=True)


def obtener_datos(dias):
    """Consulta la API y devuelve la respuesta JSON."""

    respuesta = requests.get(
        URL,
        params={"dias": dias},
        timeout=30
    )

    respuesta.raise_for_status()

    datos = respuesta.json()

    return datos


def validar_respuesta(datos):
    """Realiza validaciones básicas de la respuesta."""

    if not isinstance(datos, dict):
        raise ValueError("La respuesta no tiene formato de objeto JSON.")

    if datos.get("ok") is not True:
        raise ValueError("La API indicó que la consulta no fue exitosa.")

    if "data" not in datos:
        raise ValueError("La respuesta no contiene el campo 'data'.")

    if not isinstance(datos["data"], list):
        raise ValueError("El campo 'data' no es una lista.")

    return True


def guardar_respuesta(datos):
    """Guarda la respuesta original sin modificar."""

    fecha_captura = datetime.now()

    nombre = (
        f"cortes_"
        f"{fecha_captura.strftime('%Y%m%d_%H%M%S')}.json"
    )

    ruta = CARPETA_RAW / nombre

    datos["fecha_captura_local"] = fecha_captura.isoformat()

    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(
            datos,
            archivo,
            ensure_ascii=False,
            indent=2
        )

    return ruta


def main():

    print("=" * 60)
    print("RECOLECTOR DE INTERRUPCIONES DE AGUA")
    print("=" * 60)

    fecha_inicio = datetime.now()

    print("Fecha de captura:", fecha_inicio)
    print("Parámetro dias:", DIAS)
    print()

    datos = obtener_datos(DIAS)

    validar_respuesta(datos)

    registros = datos["data"]

    print("Consulta realizada correctamente")
    print("Estado:", datos.get("ok"))
    print("Registros obtenidos:", len(registros))
    print("Total reportado:", datos.get("total"))
    print("Última sincronización:", datos.get("last_sync"))
    print("Última incidencia:", datos.get("last_new_at"))

    ruta = guardar_respuesta(datos)

    print()
    print("Datos almacenados en:")
    print(ruta)


if __name__ == "__main__":
    main()