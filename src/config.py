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
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Avisos de agua Lima")
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() in {"1", "true", "yes"}
SMTP_TIMEOUT = float(os.getenv("SMTP_TIMEOUT", "20"))
ADMIN_ALERT_EMAIL = os.getenv("ADMIN_ALERT_EMAIL", "").strip()
SESSION_HTTPS = os.getenv("SESSION_HTTPS", "false").lower() in {"1", "true", "yes"}
TOKEN_HORAS_CONFIRMACION = int(os.getenv("TOKEN_HORAS_CONFIRMACION", "48"))
TOKEN_HORAS_GESTION = int(os.getenv("TOKEN_HORAS_GESTION", "720"))
PUBLIC_REVELAR_ENLACE = os.getenv("PUBLIC_REVELAR_ENLACE", "false").lower() in {
    "1",
    "true",
    "yes",
}
REENVIO_MINUTOS = int(os.getenv("REENVIO_MINUTOS", "15"))
RATE_LIMIT_SUSCRIPCION = int(os.getenv("RATE_LIMIT_SUSCRIPCION", "8"))
OPERACION_PUBLICA = os.getenv("OPERACION_PUBLICA", "false").lower() in {
    "1",
    "true",
    "yes",
}

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-cambiar-sesion")
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("WEB_PORT", "8000"))
LOG_FORMAT = os.getenv("LOG_FORMAT", "text").strip().lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")
INTERNAL_PERMITIR_FIXTURE = os.getenv("INTERNAL_PERMITIR_FIXTURE", "false").lower() in {
    "1",
    "true",
    "yes",
}
WORKER_POLL_S = float(os.getenv("WORKER_POLL_S", "2"))
NOTIF_POLL_S = float(os.getenv("NOTIF_POLL_S", "2"))
NOTIF_MAX_INTENTOS = int(os.getenv("NOTIF_MAX_INTENTOS", "5"))
NOTIF_LOTE = int(os.getenv("NOTIF_LOTE", "20"))
NOTIF_BACKOFF_BASE_S = int(os.getenv("NOTIF_BACKOFF_BASE_S", "5"))
NOTIF_SIMULAR_FALLO = os.getenv("NOTIF_SIMULAR_FALLO", "").lower() in {
    "1",
    "true",
    "yes",
}
CARPETA_FIXTURES = BASE_DIR / "tests" / "fixtures"

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
