"""Adaptador SMTP desacoplado. No afirma lectura ni entrega al buzón."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from src.config import (
    MODO_ENVIO,
    OPERACION_PUBLICA,
    SMTP_ENABLED,
    SMTP_FROM,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_STARTTLS,
    SMTP_TIMEOUT,
    SMTP_USER,
)

logger = logging.getLogger(__name__)

MODOS_SMTP = frozenset({"real", "smtp", "mailpit"})


def debe_enviar_smtp() -> bool:
    return bool(SMTP_ENABLED) and MODO_ENVIO in MODOS_SMTP


def modo_canal() -> str:
    if debe_enviar_smtp():
        return "smtp"
    if OPERACION_PUBLICA:
        return "smtp_no_configurado"
    return "simulacion"


def advertencia_smtp_publico() -> str | None:
    if not OPERACION_PUBLICA:
        return None
    if MODO_ENVIO == "mailpit":
        return (
            "OPERACION_PUBLICA está activa con Mailpit. Mailpit no entrega correo a Internet. "
            "Configure SMTP_ENABLED=true y MODO_ENVIO=real."
        )
    if not debe_enviar_smtp():
        return (
            "OPERACION_PUBLICA está activa pero SMTP no está listo "
            "(SMTP_ENABLED=true, MODO_ENVIO=real, SMTP_HOST, SMTP_FROM). "
            "No se enviarán correos a ciudadanos ni se fingirá el envío."
        )
    if not SMTP_FROM or SMTP_FROM.endswith("@localhost"):
        return "SMTP_FROM sigue en un valor de laboratorio. Use el correo remitente real."
    return None


def enviar(
    destinatario: str,
    asunto: str,
    texto: str,
    html: str,
    *,
    host: str | None = None,
    puerto: int | None = None,
) -> str:
    """Envía al servidor SMTP configurado. Devuelve un mensaje de auditoría.

    ACEPTADA_SMTP en el outbox significa que el servidor aceptó el mensaje,
    no que el destinatario lo leyó.
    """
    mensaje = EmailMessage()
    mensaje["Subject"] = asunto or "(sin asunto)"
    mensaje["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM))
    mensaje["To"] = destinatario
    mensaje.set_content(texto or "")
    if html:
        mensaje.add_alternative(html, subtype="html")
    destino = host or SMTP_HOST
    puerto_n = SMTP_PORT if puerto is None else puerto
    with smtplib.SMTP(destino, puerto_n, timeout=SMTP_TIMEOUT) as cliente:
        if SMTP_STARTTLS:
            cliente.starttls()
        if SMTP_USER:
            cliente.login(SMTP_USER, SMTP_PASSWORD)
        cliente.send_message(mensaje)
    logger.info(
        "SMTP aceptó el mensaje",
        extra={"evento": "smtp_aceptado", "estado": "ACEPTADA_SMTP"},
    )
    return (
        f"El servidor SMTP {destino}:{puerto_n} aceptó el mensaje; "
        "no se confirma la entrega ni la lectura del buzón."
    )
