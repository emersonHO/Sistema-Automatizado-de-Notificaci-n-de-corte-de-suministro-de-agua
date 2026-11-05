"""Persistencia idempotente e historial versionado."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from typing import Any, Mapping

from psycopg.types.json import Jsonb

from src.config import CAMPOS_ORIGEN, CAMPOS_RELEVANTES, ESTADOS_CANCELACION
from src.db import conectar as db_conectar
from src.hashes import campos_modificados, hash_origen, hash_relevante, hash_tecnico
from src.texto import normalizar_texto
from src.zonas_lima import canonizar_distrito, es_ambito_lima
from src.config import CARPETA_PROCESSED

logger = logging.getLogger(__name__)

ARCHIVO_CSV = CARPETA_PROCESSED / "interrupciones_normalizadas.csv"


def conectar():
    return db_conectar()


def _jsonable(valor: Any) -> Any:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    if hasattr(valor, "item"):
        try:
            return valor.item()
        except Exception:
            return str(valor)
    if isinstance(valor, float) and valor != valor:
        return None
    return valor


def registro_a_json(registro: Mapping) -> dict:
    return {clave: _jsonable(valor) for clave, valor in registro.items()}


def convertir_fecha(valor):
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=None)
    texto = str(valor).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto[:26], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return None


def _es_cancelacion(registro: Mapping) -> bool:
    for campo in ("estado", "tipo_incid"):
        texto = normalizar_texto(registro.get(campo))
        if texto in ESTADOS_CANCELACION:
            return True
    return False


def tipo_evento_historial(anterior: Mapping | None, actual: Mapping, relevante: bool) -> str:
    if anterior is None:
        return "NUEVA"
    if _es_cancelacion(actual) and not _es_cancelacion(anterior):
        return "CANCELADA"
    if relevante:
        return "MODIFICADA"
    return "CAMBIO_TECNICO"


def cargar_csv():
    if not ARCHIVO_CSV.exists():
        raise FileNotFoundError(f"No existe el CSV: {ARCHIVO_CSV}")
    with open(ARCHIVO_CSV, "r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        registros = []
        for fila in lector:
            registro = {clave: valor if valor != "" else None for clave, valor in fila.items()}
            if not registro.get("id"):
                raise ValueError("Se encontró una incidencia sin ID.")
            registro["id"] = int(float(registro["id"]))
            registros.append(registro)
    ids = [r["id"] for r in registros]
    if len(ids) != len(set(ids)):
        raise ValueError("El CSV contiene identificadores duplicados.")
    return registros


def _insertar_historial(cursor, interrupcion_id, version_origen, version_relevante, tipo, relevante, h_origen, h_rel, cambios, datos):
    cursor.execute(
        """
        INSERT INTO historial_interrupciones (
            interrupcion_id, version_origen, version_relevante, tipo_evento,
            cambio_relevante, hash_origen, hash_relevante, campos_modificados, datos
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (interrupcion_id, version_origen) DO NOTHING
        """,
        (
            interrupcion_id,
            version_origen,
            version_relevante,
            tipo,
            relevante,
            h_origen,
            h_rel,
            Jsonb(cambios),
            Jsonb(datos),
        ),
    )


def procesar_registro(cursor, registro: Mapping) -> dict:
    identificador = int(registro["id"])
    h_origen = hash_origen(registro)
    h_rel = hash_relevante(registro)
    h_tec = hash_tecnico(registro)
    canon, _estado_dist = canonizar_distrito(registro.get("municipalidad"))
    ambito = es_ambito_lima(registro.get("municipalidad"))
    datos = registro_a_json(registro)

    cursor.execute(
        """
        SELECT hash_origen, hash_relevante, hash_contenido, version_origen, version_relevante, datos
        FROM interrupciones
        WHERE id = %s
        FOR UPDATE
        """,
        (identificador,),
    )
    existente = cursor.fetchone()

    if existente is None:
        cursor.execute(
            """
            INSERT INTO interrupciones (
                id, cod_incidencia, empresa, municipalidad, municipalidad_normalizada,
                areas_afectadas, tipo_incid, estado, infor_web, causa, ciudad,
                fec_deteccion, fec_estimada, actualizado_en_fuente, ambito_lima,
                datos, hash_contenido, hash_origen, hash_relevante,
                version_origen, version_relevante
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, 1, 1
            )
            """,
            (
                identificador,
                registro.get("cod_incidencia"),
                registro.get("empresa"),
                registro.get("municipalidad"),
                canon,
                registro.get("areas_afectadas"),
                registro.get("tipo_incid"),
                registro.get("estado"),
                registro.get("infor_web"),
                registro.get("causa"),
                registro.get("ciudad"),
                convertir_fecha(registro.get("fec_deteccion")),
                convertir_fecha(registro.get("fec_estimada")),
                convertir_fecha(registro.get("actualizado_en")),
                ambito,
                Jsonb(datos),
                h_tec,
                h_origen,
                h_rel,
            ),
        )
        _insertar_historial(
            cursor, identificador, 1, 1, "NUEVA", True, h_origen, h_rel, {}, datos
        )
        return {
            "resultado": "nuevo",
            "id": identificador,
            "cambio_origen": True,
            "cambio_relevante": True,
            "cambio_tecnico": False,
            "tipo_evento": "NUEVA",
            "version_relevante": 1,
            "hash_relevante": h_rel,
        }

    hash_origen_prev, hash_rel_prev, hash_tec_prev, ver_origen, ver_rel, datos_prev = existente
    mismo_origen = hash_origen_prev == h_origen
    mismo_relevante = hash_rel_prev == h_rel
    mismo_tecnico = (hash_tec_prev == h_tec) if hash_tec_prev else True

    if mismo_origen:
        cursor.execute(
            "UPDATE interrupciones SET ultima_captura = NOW() WHERE id = %s",
            (identificador,),
        )
        return {
            "resultado": "sin_cambios",
            "id": identificador,
            "cambio_origen": False,
            "cambio_relevante": False,
            "cambio_tecnico": False,
            "tipo_evento": None,
            "version_relevante": ver_rel,
            "hash_relevante": h_rel,
        }

    nueva_ver_origen = (ver_origen or 1) + 1
    nueva_ver_rel = ver_rel or 1
    relevante = not mismo_relevante
    if relevante:
        nueva_ver_rel = (ver_rel or 1) + 1

    previo = datos_prev if isinstance(datos_prev, dict) else {}
    cambios = campos_modificados(previo, registro, CAMPOS_ORIGEN if not relevante else CAMPOS_RELEVANTES)
    if not relevante:
        cambios = campos_modificados(previo, registro, CAMPOS_ORIGEN)
    tipo = tipo_evento_historial(previo, registro, relevante)

    cursor.execute(
        """
        UPDATE interrupciones
        SET
            cod_incidencia = %s,
            empresa = %s,
            municipalidad = %s,
            municipalidad_normalizada = %s,
            areas_afectadas = %s,
            tipo_incid = %s,
            estado = %s,
            infor_web = %s,
            causa = %s,
            ciudad = %s,
            fec_deteccion = %s,
            fec_estimada = %s,
            actualizado_en_fuente = %s,
            ambito_lima = %s,
            datos = %s,
            hash_contenido = %s,
            hash_origen = %s,
            hash_relevante = %s,
            version_origen = %s,
            version_relevante = %s,
            ultima_captura = NOW()
        WHERE id = %s
        """,
        (
            registro.get("cod_incidencia"),
            registro.get("empresa"),
            registro.get("municipalidad"),
            canon,
            registro.get("areas_afectadas"),
            registro.get("tipo_incid"),
            registro.get("estado"),
            registro.get("infor_web"),
            registro.get("causa"),
            registro.get("ciudad"),
            convertir_fecha(registro.get("fec_deteccion")),
            convertir_fecha(registro.get("fec_estimada")),
            convertir_fecha(registro.get("actualizado_en")),
            ambito,
            Jsonb(datos),
            h_tec,
            h_origen,
            h_rel,
            nueva_ver_origen,
            nueva_ver_rel,
            identificador,
        ),
    )
    _insertar_historial(
        cursor,
        identificador,
        nueva_ver_origen,
        nueva_ver_rel,
        tipo,
        relevante,
        h_origen,
        h_rel,
        cambios,
        datos,
    )
    resultado = "actualizado"
    return {
        "resultado": resultado,
        "id": identificador,
        "cambio_origen": True,
        "cambio_relevante": relevante,
        "cambio_tecnico": (not relevante) and (not mismo_tecnico or True),
        "tipo_evento": tipo,
        "version_relevante": nueva_ver_rel,
        "hash_relevante": h_rel,
        "campos_modificados": cambios,
    }


def persistir_registros(registros: list[Mapping], conexion=None, ejecucion_id: int | None = None) -> dict:
    propia = conexion is None
    if propia:
        conexion = conectar()
    contadores = {
        "nuevo": 0,
        "actualizado": 0,
        "sin_cambios": 0,
        "cambios_origen": 0,
        "cambios_relevantes": 0,
        "cambios_tecnicos": 0,
    }
    eventos = []
    try:
        with conexion.cursor() as cursor:
            for registro in registros:
                detalle = procesar_registro(cursor, registro)
                contadores[detalle["resultado"]] += 1
                if detalle["cambio_origen"]:
                    contadores["cambios_origen"] += 1
                if detalle["cambio_relevante"]:
                    contadores["cambios_relevantes"] += 1
                    eventos.append(detalle)
                elif detalle["cambio_origen"]:
                    contadores["cambios_tecnicos"] += 1
        if propia:
            conexion.commit()
    finally:
        if propia:
            conexion.close()
    return {"contadores": contadores, "eventos_notificables": eventos, "ejecucion_id": ejecucion_id}


def ejecutar_persistencia():
    registros = cargar_csv()
    with conectar() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ejecuciones_proceso (estado, registros_leidos)
                VALUES ('EN_PROCESO', %s)
                RETURNING id
                """,
                (len(registros),),
            )
            ejecucion_id = cursor.fetchone()[0]
        conexion.commit()
        try:
            resultado = persistir_registros(registros, conexion=conexion, ejecucion_id=ejecucion_id)
            conexion.commit()
            c = resultado["contadores"]
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ejecuciones_proceso
                    SET fecha_fin = NOW(), estado = 'COMPLETADO',
                        registros_nuevos = %s, registros_actualizados = %s,
                        registros_sin_cambios = %s, cambios_origen = %s,
                        cambios_relevantes = %s, cambios_tecnicos = %s
                    WHERE id = %s
                    """,
                    (
                        c["nuevo"],
                        c["actualizado"],
                        c["sin_cambios"],
                        c["cambios_origen"],
                        c["cambios_relevantes"],
                        c["cambios_tecnicos"],
                        ejecucion_id,
                    ),
                )
            conexion.commit()
        except Exception as error:
            conexion.rollback()
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ejecuciones_proceso
                    SET fecha_fin = NOW(), estado = 'ERROR', mensaje_error = %s
                    WHERE id = %s
                    """,
                    (str(error), ejecucion_id),
                )
            conexion.commit()
            raise
    print("=" * 55)
    print("PERSISTENCIA EN POSTGRESQL")
    print("=" * 55)
    print("Registros leídos:", len(registros))
    print("Nuevos:", resultado["contadores"]["nuevo"])
    print("Actualizados:", resultado["contadores"]["actualizado"])
    print("Sin cambios:", resultado["contadores"]["sin_cambios"])
    print("Cambios relevantes:", resultado["contadores"]["cambios_relevantes"])
    print("Estado: COMPLETADO")
    return resultado


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ejecutar_persistencia()
