"""Configuración centralizada mediante variables de entorno."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

ZONA_SISTEMA = os.getenv("ZONA_SISTEMA", "America/Lima")

API_URL = os.getenv("API_URL", "https://cortedeagua.net.pe/api.php")
API_DIAS = int(os.getenv("API_DIAS", "14"))
API_TIMEOUT = float(os.getenv("API_TIMEOUT", "30"))
API_REINTENTOS = int(os.getenv("API_REINTENTOS", "3"))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "notificaciones_agua")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

SMTP_ENABLED = os.getenv("SMTP_ENABLED", "false").lower() in {"1", "true", "yes"}
MODO_ENVIO = os.getenv("MODO_ENVIO", "simulacion").strip().lower()
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "notificaciones@localhost")
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() in {"1", "true", "yes"}

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

CARPETA_RAW = BASE_DIR / "data" / "raw"
CARPETA_PROCESSED = BASE_DIR / "data" / "processed"
CARPETA_SIMULACIONES = BASE_DIR / "data" / "simulaciones"
CARPETA_EVALUACION = BASE_DIR / "data" / "evaluacion"

LOCK_KEY = 570114

CAMPOS_ORIGEN = (
    "id",
    "cod_incidencia",
    "empresa",
    "ciudad",
    "tipo_incid",
    "estado",
    "municipalidad",
    "causa",
    "areas_afectadas",
    "fec_deteccion",
    "fec_estimada",
    "infor_web",
    "descripcion",
    "tipo_red",
    "diametro",
    "agua",
    "desague",
    "facilityid",
    "cod_sunass",
    "vusuario",
    "fuente",
    "imagen_url",
    "creado_en",
    "actualizado_en",
)

CAMPOS_RELEVANTES = (
    "municipalidad",
    "areas_afectadas",
    "infor_web",
    "tipo_incid",
    "estado",
    "fec_deteccion",
    "fec_estimada",
    "causa",
    "descripcion",
    "tipo_red",
    "agua",
)

ESTADOS_CANCELACION = frozenset(
    {"CANCELADA", "CANCELADO", "ANULADA", "ANULADO", "CANCELACION"}
)
