"""Adaptadores de correo. SMTP local/Mailpit; Resend por HTTPS en Render.

ACEPTADA_SMTP / aceptación del proveedor no implica entrega ni lectura.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

import httpx

from src.config import (
    CORREO_PROVEEDOR,
    MODO_ENVIO,
    OPERACION_PUBLICA,
    RESEND_API_KEY,
    RESEND_API_URL,
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


def proveedor() -> str:
    if CORREO_PROVEEDOR in {"resend", "smtp", "mailpit", "simulacion"}:
        return CORREO_PROVEEDOR
    if MODO_ENVIO == "resend":
        return "resend"
    if MODO_ENVIO == "mailpit":
        return "mailpit"
    if SMTP_ENABLED and MODO_ENVIO in MODOS_SMTP:
        return "smtp"
    return "simulacion"


def debe_enviar_smtp() -> bool:
    """True si hay un transporte real configurado (SMTP o Resend). Nombre histórico."""
    canal = proveedor()
    if canal == "resend":
        return bool(RESEND_API_KEY) and MODO_ENVIO != "simulacion"
    if canal in {"smtp", "mailpit"}:
        return bool(SMTP_ENABLED) and MODO_ENVIO in MODOS_SMTP | {"mailpit", "real", "smtp"}
    return bool(SMTP_ENABLED) and MODO_ENVIO in MODOS_SMTP


def modo_canal() -> str:
    if proveedor() == "resend" and debe_enviar_smtp():
        return "resend"
    if debe_enviar_smtp():
        return "smtp"
    if OPERACION_PUBLICA:
        return "correo_no_configurado"
    return "simulacion"


def advertencia_smtp_publico() -> str | None:
    if not OPERACION_PUBLICA:
        return None
    if proveedor() == "mailpit" or MODO_ENVIO == "mailpit":
        return (
            "OPERACION_PUBLICA está activa con Mailpit. Mailpit no entrega correo a Internet. "
            "En Render use CORREO_PROVEEDOR=resend y RESEND_API_KEY."
        )
    if proveedor() == "resend" and not RESEND_API_KEY:
        return "CORREO_PROVEEDOR=resend pero falta RESEND_API_KEY. No se enviarán correos ni se fingirá el envío."
    if proveedor() == "resend":
        if not SMTP_FROM or SMTP_FROM.endswith("@localhost"):
            return "SMTP_FROM debe ser un remitente autorizado en Resend (onboarding o dominio verificado)."
        return None
    if not debe_enviar_smtp():
        return (
            "OPERACION_PUBLICA está activa pero no hay transporte de correo "
            "(CORREO_PROVEEDOR=resend + RESEND_API_KEY, o SMTP local). "
            "No se enviarán correos a ciudadanos ni se fingirá el envío."
        )
    if not SMTP_FROM or SMTP_FROM.endswith("@localhost"):
        return "SMTP_FROM sigue en un valor de laboratorio. Use el correo remitente real."
    return None


def formato_remitente() -> str:
    """Resend rechaza From anidado del tipo Nombre <Nombre <correo>>."""
    crudo = (SMTP_FROM or "").strip()
    nombre = (SMTP_FROM_NAME or "Avisos de agua Lima").strip()
    if "<" in crudo and ">" in crudo:
        return crudo
    if not crudo:
        return formataddr((nombre, "onboarding@resend.dev"))
    return formataddr((nombre, crudo))


def _remitente() -> str:
    return formato_remitente()


def _enviar_smtp(
    destinatario: str,
    asunto: str,
    texto: str,
    html: str,
    *,
    host: str | None = None,
    puerto: int | None = None,
) -> str:
    mensaje = EmailMessage()
    mensaje["Subject"] = asunto or "(sin asunto)"
    mensaje["From"] = _remitente()
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


def _enviar_resend(destinatario: str, asunto: str, texto: str, html: str) -> str:
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY no configurada")
    cuerpo = {
        "from": _remitente(),
        "to": [destinatario],
        "subject": asunto or "(sin asunto)",
        "text": texto or "",
    }
    if html:
        cuerpo["html"] = html
    try:
        respuesta = httpx.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=cuerpo,
            timeout=SMTP_TIMEOUT,
        )
    except httpx.HTTPError as error:
        raise RuntimeError("No se pudo contactar a Resend") from error
    if respuesta.status_code >= 400:
        detalle = (respuesta.text or "")[:240]
        logger.error(
            "Resend rechazó el envío",
            extra={
                "evento": "resend_rechazo",
                "http_status": respuesta.status_code,
                "detalle": detalle,
            },
        )
        pista = ""
        if respuesta.status_code in {403, 422}:
            pista = (
                " Revise RESEND_API_KEY y SMTP_FROM "
                "(use onboarding@resend.dev o un dominio verificado en Resend)."
            )
        raise RuntimeError(
            f"Resend rechazó el envío (HTTP {respuesta.status_code}).{pista}"
        )
    identificador = ""
    try:
        identificador = str((respuesta.json() or {}).get("id") or "")
    except ValueError:
        identificador = ""
    logger.info(
        "Resend aceptó el mensaje",
        extra={
            "evento": "resend_aceptado",
            "estado": "ACEPTADA_SMTP",
            "proveedor_id": identificador[:80],
        },
    )
    return (
        f"Resend aceptó el mensaje id={identificador or 's/n'}; "
        "no se confirma la entrega ni la lectura del buzón."
    )


def enviar(
    destinatario: str,
    asunto: str,
    texto: str,
    html: str,
    *,
    host: str | None = None,
    puerto: int | None = None,
) -> str:
    """Entrega al transporte configurado. No afirma lectura ni buzón."""
    if proveedor() == "resend":
        return _enviar_resend(destinatario, asunto, texto, html)
    return _enviar_smtp(destinatario, asunto, texto, html, host=host, puerto=puerto)
