"""Conexión PostgreSQL y aplicación del esquema."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from src import config

logger = logging.getLogger(__name__)


def url_base_datos() -> str:
    for clave in ("DATABASE_URL", "POSTGRES_URL"):
        valor = (os.getenv(clave) or "").strip().strip('"').strip("'")
        if valor:
            return valor
    return (config.DATABASE_URL or "").strip().strip('"').strip("'")


def conninfo() -> str:
    url = url_base_datos()
    if url:
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        ssl = config.DB_SSLMODE or ("require" if config.EN_RENDER else "")
        if ssl and "sslmode=" not in url.lower():
            union = "&" if "?" in url else "?"
            url = f"{url}{union}sslmode={ssl}"
        return url
    if config.EN_RENDER:
        raise RuntimeError(
            "En Render no hay PostgreSQL en localhost. Enlace la base al Web Service "
            "(Environment → Add from PostgreSQL) o defina DATABASE_URL con la "
            "Internal Database URL. No copie DB_HOST=localhost."
        )
    partes = [
        f"host={config.DB_HOST}",
        f"port={config.DB_PORT}",
        f"dbname={config.DB_NAME}",
        f"user={config.DB_USER}",
        f"password={config.DB_PASSWORD}",
        "connect_timeout=10",
    ]
    if config.DB_SSLMODE:
        partes.append(f"sslmode={config.DB_SSLMODE}")
    return " ".join(partes)


def dsn() -> str:
    return conninfo()


def _host_para_log(info: str) -> str:
    if "://" in info:
        try:
            parsed = urlparse(info)
            return parsed.hostname or "(sin host)"
        except Exception:
            return "(url)"
    for parte in info.split():
        if parte.startswith("host="):
            return parte.split("=", 1)[1]
    return "(local)"


def conectar(row_factory=None, intentos: int = 8):
    ultimo: Exception | None = None
    info = conninfo()
    for n in range(1, max(1, intentos) + 1):
        try:
            conexion = psycopg.connect(info)
            if row_factory is not None:
                conexion.row_factory = row_factory
            if n == 1:
                logger.info(
                    "PostgreSQL conectado",
                    extra={"evento": "db_ok", "host": _host_para_log(info)},
                )
            return conexion
        except Exception as error:
            ultimo = error
            logger.warning(
                "PostgreSQL no disponible (intento %s/%s) host=%s",
                n,
                intentos,
                _host_para_log(info),
            )
            if n < intentos:
                time.sleep(min(8, n * 2))
    raise ultimo


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
