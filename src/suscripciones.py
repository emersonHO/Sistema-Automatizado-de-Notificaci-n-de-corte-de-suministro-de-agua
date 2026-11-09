"""Usuarios, zonas de interés y suscripciones voluntarias."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from psycopg.rows import dict_row

from src.db import conectar
from src.texto import extraer_numero_sector, normalizar_texto
from src.zonas_lima import DISTRITOS_CALLAO, DISTRITOS_LIMA, canonizar_distrito


def sembrar_zonas(conexion=None) -> int:
    propia = conexion is None
    if propia:
        conexion = conectar()
    insertadas = 0
    with conexion.cursor() as cursor:
        for nombre in DISTRITOS_LIMA:
            cursor.execute(
                """
                INSERT INTO zonas (tipo, nombre, nombre_normalizado, distrito_padre, ambito_lima)
                VALUES ('DISTRITO', %s, %s, %s, TRUE)
                ON CONFLICT (tipo, nombre_normalizado) DO NOTHING
                """,
                (nombre.title(), nombre, nombre),
            )
            insertadas += cursor.rowcount
        for nombre in DISTRITOS_CALLAO:
            cursor.execute(
                """
                INSERT INTO zonas (tipo, nombre, nombre_normalizado, distrito_padre, ambito_lima)
                VALUES ('DISTRITO', %s, %s, %s, FALSE)
                ON CONFLICT (tipo, nombre_normalizado) DO NOTHING
                """,
                (nombre.title(), nombre, nombre),
            )
            insertadas += cursor.rowcount
    if propia:
        conexion.commit()
        conexion.close()
    return insertadas


def listar_zonas_lima(conexion=None) -> list[dict]:
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT id, tipo, nombre, nombre_normalizado, distrito_padre, ambito_lima
                FROM zonas
                WHERE activa AND ambito_lima
                ORDER BY tipo, nombre_normalizado
                """
            )
            return list(cursor.fetchall())
    finally:
        if propia:
            conexion.close()


def asegurar_zona(tipo: str, nombre: str, distrito_padre: str | None = None, conexion=None) -> dict:
    tipo = tipo.upper()
    if tipo not in {"DISTRITO", "SECTOR", "AREA"}:
        raise ValueError("Tipo de zona no permitido.")
    if tipo == "DISTRITO":
        canon, ambito = canonizar_distrito(nombre)
        if ambito != "LIMA" or canon is None:
            raise ValueError("Solo se aceptan distritos de Lima Metropolitana.")
        nombre_norm = canon
        nombre_mostrar = canon.title()
        padre = canon
        lima = True
    elif tipo == "SECTOR":
        numero = extraer_numero_sector(nombre)
        if not numero:
            raise ValueError("El sector debe incluir un número (por ejemplo: Sector 168).")
        nombre_norm = f"SECTOR {numero}"
        nombre_mostrar = nombre_norm.title()
        padre_canon, estado = canonizar_distrito(distrito_padre) if distrito_padre else (None, "VACIO")
        if distrito_padre and estado != "LIMA":
            raise ValueError("El distrito padre del sector debe pertenecer a Lima Metropolitana.")
        padre = padre_canon
        lima = True
    else:
        nombre_norm = normalizar_texto(nombre)
        if not nombre_norm:
            raise ValueError("El área no puede estar vacía.")
        nombre_mostrar = nombre.strip()
        padre_canon, estado = canonizar_distrito(distrito_padre) if distrito_padre else (None, "VACIO")
        if distrito_padre and estado != "LIMA":
            raise ValueError("El distrito padre del área debe pertenecer a Lima Metropolitana.")
        padre = padre_canon
        lima = True

    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                INSERT INTO zonas (tipo, nombre, nombre_normalizado, distrito_padre, ambito_lima)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (tipo, nombre_normalizado)
                DO UPDATE SET nombre = EXCLUDED.nombre
                RETURNING id, tipo, nombre, nombre_normalizado, distrito_padre, ambito_lima
                """,
                (tipo, nombre_mostrar, nombre_norm, padre, lima),
            )
            zona = cursor.fetchone()
        if propia:
            conexion.commit()
        return zona
    finally:
        if propia:
            conexion.close()


def registrar_usuario(correo: str, conexion=None) -> dict:
    correo = (correo or "").strip().lower()
    if "@" not in correo or "." not in correo.split("@")[-1]:
        raise ValueError("Correo electrónico no válido.")
    token = secrets.token_urlsafe(32)
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                INSERT INTO usuarios (correo, token_confirmacion, token_generado_en)
                VALUES (%s, %s, NOW())
                ON CONFLICT (correo) DO UPDATE
                SET token_confirmacion = CASE
                        WHEN usuarios.correo_confirmado THEN usuarios.token_confirmacion
                        ELSE EXCLUDED.token_confirmacion
                    END,
                    token_generado_en = CASE
                        WHEN usuarios.correo_confirmado THEN usuarios.token_generado_en
                        ELSE NOW()
                    END,
                    activo = TRUE
                RETURNING id, correo, correo_confirmado, activo, token_confirmacion
                """,
                (correo, token),
            )
            return cursor.fetchone()
    finally:
        if propia:
            conexion.commit()
            conexion.close()


def confirmar_correo(token: str, conexion=None) -> dict | None:
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                UPDATE usuarios
                SET correo_confirmado = TRUE,
                    confirmado_en = NOW(),
                    token_confirmacion = NULL
                WHERE token_confirmacion = %s
                RETURNING id, correo, correo_confirmado
                """,
                (token,),
            )
            usuario = cursor.fetchone()
            if usuario:
                cursor.execute(
                    """
                    UPDATE suscripciones
                    SET confirmada = TRUE
                    WHERE usuario_id = %s AND baja_en IS NULL
                    """,
                    (usuario["id"],),
                )
        if propia:
            conexion.commit()
        return usuario
    finally:
        if propia:
            conexion.close()


def suscribir(correo: str, zonas: list[dict], conexion=None) -> dict:
    """zonas: lista de {tipo, nombre, distrito_padre?} o {zona_id}."""
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        usuario = registrar_usuario(correo, conexion=conexion)
        creadas = []
        with conexion.cursor(row_factory=dict_row) as cursor:
            for item in zonas:
                if item.get("zona_id"):
                    zona_id = int(item["zona_id"])
                else:
                    zona = asegurar_zona(
                        item["tipo"],
                        item["nombre"],
                        item.get("distrito_padre"),
                        conexion=conexion,
                    )
                    zona_id = zona["id"]
                cursor.execute(
                    """
                    INSERT INTO suscripciones (usuario_id, zona_id, confirmada, activa)
                    VALUES (%s, %s, %s, TRUE)
                    ON CONFLICT (usuario_id, zona_id) DO UPDATE
                    SET activa = TRUE, baja_en = NULL,
                        confirmada = EXCLUDED.confirmada OR suscripciones.confirmada
                    RETURNING id, zona_id, activa, confirmada
                    """,
                    (usuario["id"], zona_id, usuario["correo_confirmado"]),
                )
                creadas.append(cursor.fetchone())
        if propia:
            conexion.commit()
        return {"usuario": usuario, "suscripciones": creadas}
    finally:
        if propia:
            conexion.close()


def dar_baja(suscripcion_id: int, correo: str, conexion=None) -> bool:
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE suscripciones s
                SET activa = FALSE, baja_en = NOW()
                FROM usuarios u
                WHERE s.id = %s AND s.usuario_id = u.id
                  AND lower(u.correo) = lower(%s)
                """,
                (suscripcion_id, correo.strip()),
            )
            ok = cursor.rowcount > 0
        if propia:
            conexion.commit()
        return ok
    finally:
        if propia:
            conexion.close()


def suscripciones_de_correo(correo: str, conexion=None) -> list[dict]:
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT s.id, s.activa, s.confirmada, s.creada_en, s.baja_en,
                       z.tipo, z.nombre, z.nombre_normalizado, u.correo_confirmado
                FROM suscripciones s
                JOIN zonas z ON z.id = s.zona_id
                JOIN usuarios u ON u.id = s.usuario_id
                WHERE lower(u.correo) = lower(%s)
                ORDER BY s.creada_en DESC
                """,
                (correo.strip(),),
            )
            return list(cursor.fetchall())
    finally:
        if propia:
            conexion.close()


def suscripciones_activas(conexion) -> list[dict]:
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT s.id AS suscripcion_id, s.usuario_id, s.zona_id,
                   z.tipo, z.nombre, z.nombre_normalizado, z.distrito_padre, z.ambito_lima,
                   u.correo, u.correo_confirmado, u.activo
            FROM suscripciones s
            JOIN zonas z ON z.id = s.zona_id
            JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.activa AND s.confirmada AND u.activo AND u.correo_confirmado
              AND z.activa AND z.ambito_lima
            """
        )
        return list(cursor.fetchall())
