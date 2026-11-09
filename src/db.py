"""Conexión PostgreSQL y aplicación del esquema."""

from __future__ import annotations

import logging
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from src import config

logger = logging.getLogger(__name__)


def dsn() -> str:
    return (
        f"host={config.DB_HOST} port={config.DB_PORT} dbname={config.DB_NAME} "
        f"user={config.DB_USER} password={config.DB_PASSWORD} connect_timeout=10"
    )


def conectar(row_factory=None):
    conexion = psycopg.connect(dsn())
    if row_factory is not None:
        conexion.row_factory = row_factory
    return conexion


def conectar_dict():
    return conectar(row_factory=dict_row)


def aplicar_esquema(conexion=None) -> None:
    ruta = config.BASE_DIR / "database" / "schema.sql"
    sql = Path(ruta).read_text(encoding="utf-8")
    propia = conexion is None
    if propia:
        conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql)
        conexion.commit()
        logger.info("Esquema aplicado desde %s", ruta)
    finally:
        if propia:
            conexion.close()
