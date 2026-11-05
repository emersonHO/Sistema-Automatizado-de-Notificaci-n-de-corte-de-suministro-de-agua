"""Cola transaccional (outbox) y envío SMTP desactivado por defecto."""

from __future__ import annotations

import json
import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from psycopg.rows import dict_row
from src.config import (
    BASE_URL,
    CARPETA_SIMULACIONES,
    MODO_ENVIO,
    SMTP_ENABLED,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_STARTTLS,
    SMTP_USER,
    ZONA_SISTEMA,
)
from src.correspondencia import coincidencia_notificable, evaluar_par
from src.suscripciones import suscripciones_activas

logger = logging.getLogger(__name__)

ASUNTOS = {
    "NUEVA": "Aviso: interrupción reportada que podría afectar tu zona de interés",
    "MODIFICADA": "Actualización: cambió una interrupción vinculada a tu zona de interés",
    "CANCELADA": "Aviso: se reportó la cancelación de una interrupción en tu zona de interés",
}


def _enmascarar(correo: str) -> str:
    if not correo or "@" not in correo:
        return "***"
    local, dominio = correo.split("@", 1)
    if len(local) <= 1:
        visible = "*"
    else:
        visible = local[0] + "***"
    return f"{visible}@{dominio}"


def renderizar_mensaje(tipo: str, interrupcion: dict, coincidencia: dict, zona: dict) -> tuple[str, str, str]:
    asunto = ASUNTOS[tipo]
    distrito = interrupcion.get("municipalidad") or "No informado"
    areas = interrupcion.get("areas_afectadas") or "No informado"
    causa = interrupcion.get("causa") or "No informado"
    tipo_inc = interrupcion.get("tipo_incid") or "No informado"
    fec_det = interrupcion.get("fec_deteccion") or "No informado"
    fec_est = interrupcion.get("fec_estimada") or "No informado"
    ref = interrupcion.get("cod_incidencia") or interrupcion.get("id")
    nivel = coincidencia.get("nivel")
    explicacion = coincidencia.get("explicacion")

    texto = f"""Se ha identificado una interrupción reportada que podría afectar una de las zonas que registraste.

Zona de interés: {zona.get("nombre")} ({zona.get("tipo")})
Nivel de coincidencia: {nivel}
Distrito reportado: {distrito}
Tipo de interrupción: {tipo_inc}
Fechas y horas reportadas por la fuente: {fec_det} a {fec_est}
Áreas afectadas reportadas: {areas}
Motivo informado: {causa}
Identificador de referencia: {ref}
Detección por el sistema (UTC): {datetime.now(timezone.utc).isoformat()}

{explicacion}

Importante:
- La información procede de una fuente pública de un tercero y puede actualizarse.
- Una coincidencia territorial no confirma que tu vivienda esté afectada.
- Este sistema no reemplaza los canales oficiales de la empresa prestadora.

Si ya no deseas recibir avisos, usa la opción de baja en el panel de suscripciones.
"""
    html = f"""<!DOCTYPE html>
<html lang="es"><body style="font-family:Georgia,serif;color:#1b1b1b">
<p>Se ha identificado una interrupción reportada que <strong>podría afectar</strong> una de las zonas que registraste.</p>
<ul>
<li>Zona de interés: {zona.get("nombre")} ({zona.get("tipo")})</li>
<li>Nivel de coincidencia: {nivel}</li>
<li>Distrito reportado: {distrito}</li>
<li>Tipo de interrupción: {tipo_inc}</li>
<li>Fechas y horas reportadas: {fec_det} a {fec_est}</li>
<li>Áreas afectadas reportadas: {areas}</li>
<li>Motivo informado: {causa}</li>
<li>Identificador de referencia: {ref}</li>
</ul>
<p>{explicacion}</p>
<p><em>La información procede de una fuente pública de un tercero y puede actualizarse. Este aviso no confirma la afectación de una vivienda ni reemplaza los canales oficiales.</em></p>
</body></html>"""
    return asunto, texto, html


def crear_coincidencias_y_notificaciones(conexion, registros: list[dict], eventos: list[dict], ejecucion_id: int | None) -> dict:
    """Crea coincidencias y filas de outbox solo para eventos relevantes."""
    activas = suscripciones_activas(conexion)
    por_id = {int(r["id"]): r for r in registros}
    creadas = 0
    coincidencias = 0
    ambiguas = 0
    with conexion.cursor(row_factory=dict_row) as cursor:
        for evento in eventos:
            if not evento.get("cambio_relevante"):
                continue
            tipo = evento.get("tipo_evento")
            if tipo not in {"NUEVA", "MODIFICADA", "CANCELADA"}:
                continue
            registro = por_id.get(int(evento["id"]))
            if registro is None:
                cursor.execute("SELECT datos FROM interrupciones WHERE id = %s", (evento["id"],))
                fila = cursor.fetchone()
                registro = fila["datos"] if fila else None
            if not registro:
                continue
            for sus in activas:
                zona = {
                    "id": sus["zona_id"],
                    "tipo": sus["tipo"],
                    "nombre": sus["nombre"],
                    "nombre_normalizado": sus["nombre_normalizado"],
                    "distrito_padre": sus["distrito_padre"],
                    "ambito_lima": sus["ambito_lima"],
                }
                resultado = evaluar_par(registro, zona)
                if resultado is None:
                    continue
                cursor.execute(
                    """
                    INSERT INTO coincidencias_territoriales (
                        ejecucion_id, interrupcion_id, suscripcion_id, zona_id,
                        nivel, estado, explicacion
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        ejecucion_id,
                        int(evento["id"]),
                        sus["suscripcion_id"],
                        sus["zona_id"],
                        resultado["nivel"],
                        resultado["estado"],
                        resultado["explicacion"],
                    ),
                )
                coincidencia_id = cursor.fetchone()["id"]
                coincidencias += 1
                if resultado["estado"] == "AMBIGUA":
                    ambiguas += 1
                if not coincidencia_notificable(resultado):
                    continue
                asunto, texto, html = renderizar_mensaje(tipo, registro, resultado, zona)
                cursor.execute(
                    """
                    INSERT INTO notificaciones (
                        usuario_id, suscripcion_id, interrupcion_id, coincidencia_id,
                        version_relevante, hash_relevante, tipo_evento, nivel_coincidencia,
                        estado, asunto, cuerpo_texto, cuerpo_html
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, 'PENDIENTE', %s, %s, %s
                    )
                    ON CONFLICT (suscripcion_id, interrupcion_id, version_relevante, tipo_evento)
                    DO NOTHING
                    """,
                    (
                        sus["usuario_id"],
                        sus["suscripcion_id"],
                        int(evento["id"]),
                        coincidencia_id,
                        evento["version_relevante"],
                        evento["hash_relevante"],
                        tipo,
                        resultado["nivel"],
                        asunto,
                        texto,
                        html,
                    ),
                )
                creadas += cursor.rowcount
    return {
        "coincidencias": coincidencias,
        "coincidencias_ambiguas": ambiguas,
        "notificaciones_creadas": creadas,
    }


def notificar_incidencias_vigentes_sin_aviso(conexion, ejecucion_id: int | None) -> dict:
    """Avisa a suscriptores nuevos sobre incidencias ya persistidas.

    Solo crea un primer aviso (NUEVA o CANCELADA) si esa suscripción aún no
    tiene ninguna notificación para la incidencia. Las modificaciones
    posteriores siguen el flujo de eventos relevantes.
    """
    activas = suscripciones_activas(conexion)
    creadas = 0
    coincidencias = 0
    ambiguas = 0
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id, municipalidad, areas_afectadas, infor_web, tipo_incid, estado,
                   causa, fec_deteccion, fec_estimada, cod_incidencia, datos,
                   version_relevante, hash_relevante
            FROM interrupciones
            WHERE ambito_lima IS TRUE
            """
        )
        interrupciones = list(cursor.fetchall())
        for fila in interrupciones:
            registro = dict(fila.get("datos") or {})
            registro.update({k: fila[k] for k in fila if k != "datos"})
            tipo = "CANCELADA" if str(fila.get("estado") or "").upper() in {
                "CANCELADA", "CANCELADO", "ANULADA", "ANULADO", "CANCELACION"
            } else "NUEVA"
            for sus in activas:
                cursor.execute(
                    """
                    SELECT 1 FROM notificaciones
                    WHERE suscripcion_id = %s AND interrupcion_id = %s
                    LIMIT 1
                    """,
                    (sus["suscripcion_id"], fila["id"]),
                )
                if cursor.fetchone():
                    continue
                zona = {
                    "id": sus["zona_id"],
                    "tipo": sus["tipo"],
                    "nombre": sus["nombre"],
                    "nombre_normalizado": sus["nombre_normalizado"],
                    "distrito_padre": sus["distrito_padre"],
                    "ambito_lima": sus["ambito_lima"],
                }
                resultado = evaluar_par(registro, zona)
                if resultado is None:
                    continue
                cursor.execute(
                    """
                    INSERT INTO coincidencias_territoriales (
                        ejecucion_id, interrupcion_id, suscripcion_id, zona_id,
                        nivel, estado, explicacion
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        ejecucion_id,
                        fila["id"],
                        sus["suscripcion_id"],
                        sus["zona_id"],
                        resultado["nivel"],
                        resultado["estado"],
                        resultado["explicacion"],
                    ),
                )
                coincidencia_id = cursor.fetchone()["id"]
                coincidencias += 1
                if resultado["estado"] == "AMBIGUA":
                    ambiguas += 1
                if not coincidencia_notificable(resultado):
                    continue
                asunto, texto, html = renderizar_mensaje(tipo, registro, resultado, zona)
                cursor.execute(
                    """
                    INSERT INTO notificaciones (
                        usuario_id, suscripcion_id, interrupcion_id, coincidencia_id,
                        version_relevante, hash_relevante, tipo_evento, nivel_coincidencia,
                        estado, asunto, cuerpo_texto, cuerpo_html
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, 'PENDIENTE', %s, %s, %s
                    )
                    ON CONFLICT (suscripcion_id, interrupcion_id, version_relevante, tipo_evento)
                    DO NOTHING
                    """,
                    (
                        sus["usuario_id"],
                        sus["suscripcion_id"],
                        fila["id"],
                        coincidencia_id,
                        fila["version_relevante"],
                        fila["hash_relevante"],
                        tipo,
                        resultado["nivel"],
                        asunto,
                        texto,
                        html,
                    ),
                )
                creadas += cursor.rowcount
    return {
        "coincidencias": coincidencias,
        "coincidencias_ambiguas": ambiguas,
        "notificaciones_creadas": creadas,
    }


def _enviar_smtp(destinatario: str, asunto: str, texto: str, html: str) -> None:
    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = SMTP_FROM
    mensaje["To"] = destinatario
    mensaje.set_content(texto)
    mensaje.add_alternative(html, subtype="html")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as cliente:
        if SMTP_STARTTLS:
            cliente.starttls()
        if SMTP_USER:
            cliente.login(SMTP_USER, SMTP_PASSWORD)
        cliente.send_message(mensaje)


def _guardar_simulacion(notificacion: dict, destinatario: str) -> Path:
    CARPETA_SIMULACIONES.mkdir(parents=True, exist_ok=True)
    nombre = f"notif_{notificacion['id']}_{datetime.now(timezone.utc):%Y%m%d%H%M%S}.json"
    ruta = CARPETA_SIMULACIONES / nombre
    payload = {
        "notificacion_id": notificacion["id"],
        "destinatario_enmascarado": _enmascarar(destinatario),
        "tipo_evento": notificacion["tipo_evento"],
        "interrupcion_id": notificacion["interrupcion_id"],
        "asunto": notificacion["asunto"],
        "cuerpo_texto": notificacion["cuerpo_texto"],
        "modo": "simulacion",
        "zona_sistema": ZONA_SISTEMA,
        "base_url": BASE_URL,
    }
    ruta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def procesar_outbox(conexion, limite: int = 50, forzar_simulacion: bool = False) -> dict:
    modo = "simulacion"
    enviar_real = False
    if not forzar_simulacion and SMTP_ENABLED and MODO_ENVIO == "real":
        modo = "real"
        enviar_real = True

    procesadas = 0
    simuladas = 0
    aceptadas = 0
    fallidas = 0
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT n.*, u.correo
            FROM notificaciones n
            JOIN usuarios u ON u.id = n.usuario_id
            WHERE n.estado IN ('PENDIENTE', 'FALLIDA')
            ORDER BY n.creada_en
            FOR UPDATE OF n SKIP LOCKED
            LIMIT %s
            """,
            (limite,),
        )
        filas = list(cursor.fetchall())
        for fila in filas:
            procesadas += 1
            try:
                if enviar_real:
                    _enviar_smtp(fila["correo"], fila["asunto"], fila["cuerpo_texto"], fila["cuerpo_html"])
                    estado = "ACEPTADA_SMTP"
                    resultado = "ACEPTADA_SMTP"
                    aceptadas += 1
                    mensaje = "El servidor SMTP aceptó el mensaje; no se confirma la entrega al buzón."
                else:
                    _guardar_simulacion(fila, fila["correo"])
                    estado = "SIMULADA"
                    resultado = "SIMULADA"
                    simuladas += 1
                    mensaje = "Envío simulado. No se contactó a un destinatario real."
                cursor.execute(
                    """
                    INSERT INTO intentos_notificacion (notificacion_id, resultado, mensaje, modo)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (fila["id"], resultado, mensaje, modo),
                )
                cursor.execute(
                    """
                    UPDATE notificaciones
                    SET estado = %s, intentos = intentos + 1, ultimo_error = NULL, actualizada_en = NOW()
                    WHERE id = %s
                    """,
                    (estado, fila["id"]),
                )
            except Exception as error:
                fallidas += 1
                logger.exception("Fallo al procesar notificación %s", fila["id"])
                cursor.execute(
                    """
                    INSERT INTO intentos_notificacion (notificacion_id, resultado, mensaje, modo)
                    VALUES (%s, 'FALLIDA', %s, %s)
                    """,
                    (fila["id"], str(error), modo),
                )
                cursor.execute(
                    """
                    UPDATE notificaciones
                    SET estado = 'FALLIDA', intentos = intentos + 1, ultimo_error = %s, actualizada_en = NOW()
                    WHERE id = %s
                    """,
                    (str(error), fila["id"]),
                )
    return {
        "procesadas": procesadas,
        "simuladas": simuladas,
        "aceptadas_smtp": aceptadas,
        "fallidas": fallidas,
        "modo": modo,
    }
