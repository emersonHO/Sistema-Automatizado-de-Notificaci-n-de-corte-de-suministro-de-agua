"""Ciclo público de suscripción: alta, confirmación, preferencias y baja."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from psycopg.rows import dict_row

from email_validator import EmailNotValidError, validate_email

from src.config import OPERACION_PUBLICA, REENVIO_MINUTOS
from src.url_publica import url_base
from src.correo import debe_enviar_smtp, enviar as enviar_smtp, modo_canal
from src.notificaciones import _guardar_simulacion
from src.plantillas_correo import baja_confirmada, confirmacion, gestion_acceso
from src.suscripciones import asegurar_zona
from src.tokens import (
    enlace_baja,
    enlace_confirmacion,
    enlace_gestion,
    hashear,
    horas_confirmacion,
    nuevo_token,
    verificar,
)

logger = logging.getLogger(__name__)


MENSAJE_GENERICO = (
    "Si el correo es válido, recibirás un mensaje con el siguiente paso. "
    "Revisa también la carpeta de no deseados."
)


def _enviar_transaccional(correo: str, asunto: str, texto: str, html: str) -> str:
    if debe_enviar_smtp():
        return enviar_smtp(correo, asunto, texto, html)
    if OPERACION_PUBLICA:
        logger.error(
            "SMTP no configurado en operación pública; no se simula un envío real",
            extra={"evento": "smtp_no_configurado"},
        )
        raise RuntimeError("SMTP_NO_CONFIGURADO")
    _guardar_simulacion(
        {
            "id": 0,
            "tipo_evento": "TRANSACCIONAL",
            "asunto": asunto,
            "cuerpo_texto": texto,
            "cuerpo_html": html,
            "version_relevante": 0,
        },
        correo,
    )
    return "simulacion"


def registrar_publico(
    correo: str,
    zonas: list[dict],
    *,
    consentimiento: bool,
    alerta_nueva: bool = True,
    alerta_modificada: bool = True,
    alerta_cancelacion: bool = True,
    resumen_diario: bool = False,
    conexion,
) -> dict:
    if not consentimiento:
        raise ValueError("Debes aceptar el aviso de privacidad y el envío de avisos.")
    correo = (correo or "").strip().lower()
    try:
        correo = validate_email(correo, check_deliverability=False).normalized
    except EmailNotValidError as error:
        raise ValueError("Correo electrónico no válido.") from error
    if not zonas:
        raise ValueError("Selecciona al menos un distrito de Lima Metropolitana.")

    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "SELECT id, correo_confirmado, ultimo_reenvio_en FROM usuarios WHERE lower(correo) = %s",
            (correo,),
        )
        existente = cursor.fetchone()
        token_plain = None
        if existente and existente["correo_confirmado"]:
            usuario_id = existente["id"]
        else:
            token_plain = nuevo_token()
            expira = datetime.now(timezone.utc) + timedelta(hours=horas_confirmacion())
            cursor.execute(
                """
                INSERT INTO usuarios (
                    correo, token_confirmacion, token_generado_en, token_confirmacion_expira,
                    consentimiento_en, ultimo_reenvio_en
                )
                VALUES (%s, %s, NOW(), %s, NOW(), NOW())
                ON CONFLICT (correo) DO UPDATE
                SET token_confirmacion = EXCLUDED.token_confirmacion,
                    token_generado_en = NOW(),
                    token_confirmacion_expira = EXCLUDED.token_confirmacion_expira,
                    ultimo_reenvio_en = NOW(),
                    consentimiento_en = COALESCE(usuarios.consentimiento_en, NOW()),
                    activo = TRUE
                RETURNING id, correo_confirmado
                """,
                (correo, hashear(token_plain), expira),
            )
            fila = cursor.fetchone()
            usuario_id = fila["id"]

        creadas = []
        for item in zonas:
            if item.get("zona_id"):
                zona_id = int(item["zona_id"])
            else:
                zona = asegurar_zona(
                    item["tipo"], item["nombre"], item.get("distrito_padre"), conexion=conexion
                )
                zona_id = zona["id"]
            cursor.execute(
                """
                INSERT INTO suscripciones (
                    usuario_id, zona_id, confirmada, activa,
                    alerta_nueva, alerta_modificada, alerta_cancelacion, resumen_diario
                )
                VALUES (
                    %s, %s,
                    (SELECT correo_confirmado FROM usuarios WHERE id = %s),
                    TRUE, %s, %s, %s, %s
                )
                ON CONFLICT (usuario_id, zona_id) DO UPDATE
                SET activa = TRUE, baja_en = NULL, pausada = FALSE,
                    alerta_nueva = EXCLUDED.alerta_nueva,
                    alerta_modificada = EXCLUDED.alerta_modificada,
                    alerta_cancelacion = EXCLUDED.alerta_cancelacion,
                    resumen_diario = EXCLUDED.resumen_diario,
                    confirmada = suscripciones.confirmada
                      OR EXCLUDED.confirmada
                RETURNING id
                """,
                (
                    usuario_id,
                    zona_id,
                    usuario_id,
                    alerta_nueva,
                    alerta_modificada,
                    alerta_cancelacion,
                    resumen_diario,
                ),
            )
            creadas.append(cursor.fetchone()["id"])

        cursor.execute(
            "SELECT correo_confirmado FROM usuarios WHERE id = %s",
            (usuario_id,),
        )
        confirmado = cursor.fetchone()["correo_confirmado"]

    tipo_correo = None
    if confirmado:
        tipo_correo = "gestion"
    elif token_plain:
        tipo_correo = "confirmacion"
    return {
        "ok": True,
        "mensaje": MENSAJE_GENERICO,
        "token": token_plain,
        "usuario_id": usuario_id,
        "correo": correo,
        "confirmado": bool(confirmado),
        "tipo_correo": tipo_correo,
        "ids_suscripcion": creadas,
    }


def reenviar_confirmacion(correo: str, conexion) -> dict:
    correo = (correo or "").strip().lower()
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id, correo_confirmado, ultimo_reenvio_en
            FROM usuarios WHERE lower(correo) = %s
            """,
            (correo,),
        )
        fila = cursor.fetchone()
        if not fila or fila["correo_confirmado"]:
            return {"ok": True, "mensaje": MENSAJE_GENERICO}
        if fila["ultimo_reenvio_en"]:
            limite = fila["ultimo_reenvio_en"]
            if limite.tzinfo is None:
                limite = limite.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - limite < timedelta(minutes=REENVIO_MINUTOS):
                return {"ok": True, "mensaje": MENSAJE_GENERICO}
        token_plain = nuevo_token()
        expira = datetime.now(timezone.utc) + timedelta(hours=horas_confirmacion())
        cursor.execute(
            """
            UPDATE usuarios
            SET token_confirmacion = %s, token_generado_en = NOW(),
                token_confirmacion_expira = %s, ultimo_reenvio_en = NOW()
            WHERE id = %s
            """,
            (hashear(token_plain), expira, fila["id"]),
        )
    return {
        "ok": True,
        "mensaje": MENSAJE_GENERICO,
        "token": token_plain,
        "correo": correo,
        "tipo_correo": "confirmacion",
    }


def confirmar_publico(token: str, conexion) -> dict | None:
    digest = hashear(token)
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            UPDATE usuarios
            SET correo_confirmado = TRUE,
                confirmado_en = NOW(),
                token_confirmacion = NULL,
                token_confirmacion_expira = NULL
            WHERE token_confirmacion = %s
              AND (token_confirmacion_expira IS NULL OR token_confirmacion_expira > NOW())
            RETURNING id, correo
            """,
            (digest,),
        )
        usuario = cursor.fetchone()
        if not usuario:
            return None
        cursor.execute(
            """
            UPDATE suscripciones
            SET confirmada = TRUE
            WHERE usuario_id = %s AND baja_en IS NULL
            """,
            (usuario["id"],),
        )
    return usuario


def usuario_por_token_gestion(token: str, conexion) -> dict | None:
    uid = verificar(token, "gest")
    if not uid:
        return None
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id, correo, correo_confirmado, activo, pausado
            FROM usuarios WHERE id = %s AND activo
            """,
            (uid,),
        )
        return cursor.fetchone()


def usuario_por_token_baja(token: str, conexion) -> dict | None:
    uid = verificar(token, "baja")
    if not uid:
        return None
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "SELECT id, correo, activo FROM usuarios WHERE id = %s",
            (uid,),
        )
        return cursor.fetchone()


def listar_prefs(usuario_id: int, conexion) -> list[dict]:
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT s.id, s.activa, s.confirmada, s.pausada, s.alerta_nueva,
                   s.alerta_modificada, s.alerta_cancelacion, s.resumen_diario,
                   z.tipo, z.nombre
            FROM suscripciones s
            JOIN zonas z ON z.id = s.zona_id
            WHERE s.usuario_id = %s
            ORDER BY z.nombre
            """,
            (usuario_id,),
        )
        return list(cursor.fetchall())


def actualizar_prefs(usuario_id: int, cambios: dict, conexion) -> None:
    with conexion.cursor() as cursor:
        if "pausado" in cambios:
            cursor.execute(
                "UPDATE usuarios SET pausado = %s WHERE id = %s",
                (bool(cambios["pausado"]), usuario_id),
            )
        for sid, prefs in (cambios.get("suscripciones") or {}).items():
            cursor.execute(
                """
                UPDATE suscripciones
                SET alerta_nueva = %s,
                    alerta_modificada = %s,
                    alerta_cancelacion = %s,
                    resumen_diario = %s,
                    pausada = %s
                WHERE id = %s AND usuario_id = %s
                """,
                (
                    bool(prefs.get("alerta_nueva")),
                    bool(prefs.get("alerta_modificada")),
                    bool(prefs.get("alerta_cancelacion")),
                    bool(prefs.get("resumen_diario")),
                    bool(prefs.get("pausada")),
                    int(sid),
                    usuario_id,
                ),
            )


def cancelar_todo(usuario_id: int, conexion) -> None:
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            UPDATE suscripciones
            SET activa = FALSE, baja_en = NOW(), pausada = TRUE
            WHERE usuario_id = %s AND baja_en IS NULL
            """,
            (usuario_id,),
        )
        cursor.execute(
            "UPDATE usuarios SET activo = FALSE, pausado = TRUE WHERE id = %s",
            (usuario_id,),
        )


def avisar_baja(correo: str) -> None:
    asunto, texto, html = baja_confirmada()
    try:
        _enviar_transaccional(correo, asunto, texto, html)
    except RuntimeError:
        logger.error("No se envió el aviso de baja: SMTP no configurado")


def modo_correo() -> str:
    return modo_canal()


def enviar_correo_alta(resultado: dict) -> dict:
    """Envía confirmación o enlace de gestión. No debe llamarse dentro de una transacción abierta que se pueda revertir."""
    tipo = resultado.get("tipo_correo")
    correo = resultado.get("correo")
    if not tipo or not correo:
        return {**resultado, "correo_enviado": False}
    try:
        if tipo == "gestion":
            asunto, texto, html = gestion_acceso(
                enlace_gestion(url_base(), int(resultado["usuario_id"]))
            )
        else:
            token = resultado.get("token")
            if not token:
                return {**resultado, "correo_enviado": False}
            asunto, texto, html = confirmacion(enlace_confirmacion(url_base(), token))
        _enviar_transaccional(correo, asunto, texto, html)
        return {**resultado, "correo_enviado": True, "smtp": True}
    except Exception:
        logger.exception(
            "Fallo al enviar correo transaccional; la suscripción ya está persistida",
            extra={"evento": "correo_transaccional_fallo"},
        )
        return {**resultado, "correo_enviado": False, "smtp": False}
