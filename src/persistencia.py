
import csv
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb


BASE_DIR = Path(__file__).resolve().parent.parent
ARCHIVO_CSV = (
    BASE_DIR / "data" / "processed"
    / "interrupciones_normalizadas.csv"
)

load_dotenv(BASE_DIR / ".env")


def conectar():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "notificaciones_agua"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        connect_timeout=10,
    )


def convertir_fecha(valor):
    if not valor:
        return None
    return datetime.fromisoformat(valor)


def cargar_csv():
    if not ARCHIVO_CSV.exists():
        raise FileNotFoundError(
            f"No existe el CSV: {ARCHIVO_CSV}"
        )

    with open(
        ARCHIVO_CSV,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as archivo:
        lector = csv.DictReader(archivo)
        registros = []

        for fila in lector:
            # Las celdas vacías se guardan como NULL.
            registro = {
                clave: valor if valor != "" else None
                for clave, valor in fila.items()
            }

            if not registro.get("id"):
                raise ValueError(
                    "Se encontró una incidencia sin ID."
                )

            registro["id"] = int(registro["id"])
            registros.append(registro)

    ids = [r["id"] for r in registros]

    if len(ids) != len(set(ids)):
        raise ValueError(
            "El CSV contiene identificadores duplicados."
        )

    return registros


def calcular_hash(registro):
    contenido = json.dumps(
        registro,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":")
    )

    return hashlib.sha256(
        contenido.encode("utf-8")
    ).hexdigest()


def procesar_registro(cursor, registro):
    identificador = registro["id"]
    nuevo_hash = calcular_hash(registro)

    cursor.execute(
        """
        SELECT hash_contenido
        FROM interrupciones
        WHERE id = %s
        FOR UPDATE
        """,
        (identificador,)
    )

    existente = cursor.fetchone()

    if existente is None:
        cursor.execute(
            """
            INSERT INTO interrupciones (
                id,
                cod_incidencia,
                empresa,
                municipalidad,
                areas_afectadas,
                tipo_incid,
                fec_deteccion,
                fec_estimada,
                actualizado_en_fuente,
                datos,
                hash_contenido
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            """,
            (
                identificador,
                registro.get("cod_incidencia"),
                registro.get("empresa"),
                registro.get("municipalidad"),
                registro.get("areas_afectadas"),
                registro.get("tipo_incid"),
                convertir_fecha(
                    registro.get("fec_deteccion")
                ),
                convertir_fecha(
                    registro.get("fec_estimada")
                ),
                convertir_fecha(
                    registro.get("actualizado_en")
                ),
                Jsonb(registro),
                nuevo_hash,
            )
        )
        return "nuevo"

    if existente[0] != nuevo_hash:
        cursor.execute(
            """
            UPDATE interrupciones
            SET
                cod_incidencia = %s,
                empresa = %s,
                municipalidad = %s,
                areas_afectadas = %s,
                tipo_incid = %s,
                fec_deteccion = %s,
                fec_estimada = %s,
                actualizado_en_fuente = %s,
                datos = %s,
                hash_contenido = %s,
                ultima_captura = NOW()
            WHERE id = %s
            """,
            (
                registro.get("cod_incidencia"),
                registro.get("empresa"),
                registro.get("municipalidad"),
                registro.get("areas_afectadas"),
                registro.get("tipo_incid"),
                convertir_fecha(
                    registro.get("fec_deteccion")
                ),
                convertir_fecha(
                    registro.get("fec_estimada")
                ),
                convertir_fecha(
                    registro.get("actualizado_en")
                ),
                Jsonb(registro),
                nuevo_hash,
                identificador,
            )
        )
        return "actualizado"

    cursor.execute(
        """
        UPDATE interrupciones
        SET ultima_captura = NOW()
        WHERE id = %s
        """,
        (identificador,)
    )

    return "sin_cambios"


def ejecutar_persistencia():
    registros = cargar_csv()

    contadores = {
        "nuevo": 0,
        "actualizado": 0,
        "sin_cambios": 0,
    }

    with conectar() as conexion:
        # Registrar el inicio de la ejecución.
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ejecuciones_proceso (
                    estado, registros_leidos
                )
                VALUES ('EN_PROCESO', %s)
                RETURNING id
                """,
                (len(registros),)
            )
            ejecucion_id = cursor.fetchone()[0]

        conexion.commit()

        try:
            with conexion.cursor() as cursor:
                for registro in registros:
                    resultado = procesar_registro(
                        cursor, registro
                    )
                    contadores[resultado] += 1

                cursor.execute(
                    """
                    UPDATE ejecuciones_proceso
                    SET
                        fecha_fin = NOW(),
                        estado = 'COMPLETADO',
                        registros_nuevos = %s,
                        registros_actualizados = %s,
                        registros_sin_cambios = %s
                    WHERE id = %s
                    """,
                    (
                        contadores["nuevo"],
                        contadores["actualizado"],
                        contadores["sin_cambios"],
                        ejecucion_id,
                    )
                )

            conexion.commit()

        except Exception as error:
            # Deshacer toda la carga incompleta.
            conexion.rollback()

            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ejecuciones_proceso
                    SET
                        fecha_fin = NOW(),
                        estado = 'ERROR',
                        mensaje_error = %s
                    WHERE id = %s
                    """,
                    (str(error), ejecucion_id)
                )

            conexion.commit()
            raise

    print("=" * 55)
    print("PERSISTENCIA EN POSTGRESQL")
    print("=" * 55)
    print("Registros leídos:", len(registros))
    print("Nuevos:", contadores["nuevo"])
    print("Actualizados:", contadores["actualizado"])
    print("Sin cambios:", contadores["sin_cambios"])
    print("Estado: COMPLETADO")


if __name__ == "__main__":
    ejecutar_persistencia()
