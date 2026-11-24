"""Cola transaccional (outbox) y entrega simulada. SMTP real permanece opt-in."""

from __future__ import annotations

import json
import logging
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

from psycopg.rows import dict_row

from src.config import (
    API_URL,
    CARPETA_SIMULACIONES,
    NOTIF_BACKOFF_BASE_S,
    NOTIF_MAX_INTENTOS,
    NOTIF_SIMULAR_FALLO,
    ZONA_SISTEMA,
)
from src.correo import debe_enviar_smtp, enviar as enviar_correo, modo_canal
from src.url_publica import url_base
from src.correspondencia import coincidencia_notificable, evaluar_par
from src.solicitudes import pid_sesion_viva
from src.suscripciones import suscripciones_activas

logger = logging.getLogger(__name__)

ASUNTOS = {
    "NUEVA": "Aviso: interrupción reportada que podría afectar tu zona de interés",
    "MODIFICADA": "Actualización: cambió una interrupción vinculada a tu zona de interés",
    "CANCELADA": "Aviso: se reportó la cancelación de una interrupción en tu zona de interés",
}

ESTADOS_RECLAMABLES = ("PENDIENTE", "REINTENTANDO", "FALLIDA")
ESTADOS_TERMINALES = frozenset(
    {"SIMULADA", "ACEPTADA_SMTP", "DESCARTADA", "CANCELADA", "ERROR"}
)


class EntregaSimuladaError(Exception):
    """Fallo controlado de la simulación de entrega (no es un envío real)."""


def _enmascarar(correo: str) -> str:
    if not correo or "@" not in correo:
        return "***"
    local, dominio = correo.split("@", 1)
    if len(local) <= 1:
        visible = "*"
    else:
        visible = local[0] + "***"
    return f"{visible}@{dominio}"


def _dato(valor) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto or texto.lower() in {"none", "null", "nan"}:
        return None
    return texto


def _linea(etiqueta: str, valor) -> str | None:
    texto = _dato(valor)
    if texto is None:
        return None
    return f"{etiqueta}: {texto}"


def renderizar_mensaje(
    tipo: str,
    interrupcion: dict,
    coincidencia: dict,
    zona: dict,
    usuario_id: int | None = None,
) -> tuple[str, str, str]:
    from src.plantillas_correo import interrupcion as plantilla_interrupcion
    from src.tokens import enlace_baja, enlace_gestion

    base = url_base()
    uid = usuario_id or zona.get("usuario_id") or 0
    gestion = enlace_gestion(base, int(uid)) if uid else base
    baja = enlace_baja(base, int(uid)) if uid else base
    return plantilla_interrupcion(tipo, interrupcion, coincidencia, zona, gestion, baja)


def _ya_notificado(cursor, usuario_id: int, interrupcion_id: int, version_relevante: int, tipo: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM notificaciones
        WHERE usuario_id = %s
          AND interrupcion_id = %s
          AND version_relevante = %s
          AND tipo_evento = %s
        LIMIT 1
        """,
        (usuario_id, interrupcion_id, version_relevante, tipo),
    )
    return cursor.fetchone() is not None


def _insertar_notificacion(cursor, sus, evento, coincidencia_id, resultado, asunto, texto, html, tipo: str) -> int:
    if _ya_notificado(
        cursor,
        sus["usuario_id"],
        int(evento["id"]),
        evento["version_relevante"],
        tipo,
    ):
        return 0
    motivo = f"{tipo}: {resultado.get('explicacion') or 'coincidencia notificable'}"
    cursor.execute(
        """
        INSERT INTO notificaciones (
            usuario_id, suscripcion_id, interrupcion_id, coincidencia_id,
            version_relevante, hash_relevante, tipo_evento, nivel_coincidencia,
            estado, canal, motivo, asunto, cuerpo_texto, cuerpo_html, max_intentos
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, 'PENDIENTE', 'simulacion', %s, %s, %s, %s, %s
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
            motivo,
            asunto,
            texto,
            html,
            NOTIF_MAX_INTENTOS,
        ),
    )
    return cursor.rowcount


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
                if tipo == "NUEVA" and not sus.get("alerta_nueva", True):
                    continue
                if tipo == "MODIFICADA" and not sus.get("alerta_modificada", True):
                    continue
                if tipo == "CANCELADA" and not sus.get("alerta_cancelacion", True):
                    continue
                zona = {
                    "id": sus["zona_id"],
                    "tipo": sus["tipo"],
                    "nombre": sus["nombre"],
                    "nombre_normalizado": sus["nombre_normalizado"],
                    "distrito_padre": sus["distrito_padre"],
                    "ambito_lima": sus["ambito_lima"],
                    "usuario_id": sus["usuario_id"],
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
                creadas += _insertar_notificacion(
                    cursor, sus, evento, coincidencia_id, resultado, asunto, texto, html, tipo
                )
    return {
        "coincidencias": coincidencias,
        "coincidencias_ambiguas": ambiguas,
        "notificaciones_creadas": creadas,
    }


def notificar_incidencias_vigentes_sin_aviso(conexion, ejecucion_id: int | None) -> dict:
    """Avisa a suscriptores nuevos sobre incidencias ya persistidas."""
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
                if tipo == "NUEVA" and not sus.get("alerta_nueva", True):
                    continue
                if tipo == "CANCELADA" and not sus.get("alerta_cancelacion", True):
                    continue
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
                    "usuario_id": sus["usuario_id"],
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
                evento = {
                    "id": fila["id"],
                    "version_relevante": fila["version_relevante"],
                    "hash_relevante": fila["hash_relevante"],
                }
                creadas += _insertar_notificacion(
                    cursor, sus, evento, coincidencia_id, resultado, asunto, texto, html, tipo
                )
    return {
        "coincidencias": coincidencias,
        "coincidencias_ambiguas": ambiguas,
        "notificaciones_creadas": creadas,
    }


def _guardar_simulacion(notificacion: dict, destinatario: str) -> Path:
    CARPETA_SIMULACIONES.mkdir(parents=True, exist_ok=True)
    nombre = f"notif_{notificacion['id']}_{datetime.now(timezone.utc):%Y%m%d%H%M%S}.json"
    ruta = CARPETA_SIMULACIONES / nombre
    payload = {
        "notificacion_id": notificacion["id"],
        "destinatario_enmascarado": _enmascarar(destinatario),
        "tipo_evento": notificacion.get("tipo_evento"),
        "interrupcion_id": notificacion.get("interrupcion_id"),
        "asunto": notificacion["asunto"],
        "cuerpo_texto": notificacion["cuerpo_texto"],
        "modo": "simulacion",
        "resultado": "SIMULADA",
        "zona_sistema": ZONA_SISTEMA,
        "base_url": url_base(),
    }
    ruta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def segundos_backoff(intentos: int) -> int:
    base = max(0, NOTIF_BACKOFF_BASE_S)
    return min(3600, base * (2 ** max(0, intentos - 1)))


def worker_id_local() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def reconciliar_notificaciones_huerfanas(conexion) -> int:
    """Devuelve a REINTENTANDO las filas EN_PROCESO cuyo worker ya no está vivo."""
    recuperadas = 0
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id, backend_pid, intentos, max_intentos
            FROM notificaciones
            WHERE estado = 'EN_PROCESO'
            """
        )
        filas = list(cursor.fetchall())
        for fila in filas:
            vivo = pid_sesion_viva(fila.get("backend_pid"), conexion)
            if vivo:
                continue
            max_i = int(fila.get("max_intentos") or NOTIF_MAX_INTENTOS)
            intentos = int(fila.get("intentos") or 0)
            if intentos >= max_i:
                estado = "FALLIDA"
                proximo = None
            else:
                estado = "REINTENTANDO"
                proximo = datetime.now(timezone.utc)
            cursor.execute(
                """
                UPDATE notificaciones
                SET estado = %s,
                    worker_id = NULL,
                    backend_pid = NULL,
                    heartbeat_en = NULL,
                    proximo_intento = %s,
                    recuperaciones = COALESCE(recuperaciones, 0) + 1,
                    ultimo_error = 'Recuperada: sesión del worker no está viva',
                    actualizada_en = NOW()
                WHERE id = %s AND estado = 'EN_PROCESO'
                """,
                (estado, proximo, fila["id"]),
            )
            if cursor.rowcount:
                recuperadas += cursor.rowcount
                logger.warning(
                    "Notificación huérfana recuperada",
                    extra={
                        "evento": "notificacion_recuperada",
                        "notificacion_id": fila["id"],
                        "estado": estado,
                    },
                )
    return recuperadas


def reclamar_notificacion(conexion, worker_id: str | None = None) -> dict | None:
    ident = worker_id or worker_id_local()
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT pg_backend_pid() AS pid")
        pid = int(cursor.fetchone()["pid"])
        cursor.execute(
            """
            WITH candidata AS (
                SELECT n.id
                FROM notificaciones n
                WHERE n.estado IN ('PENDIENTE', 'REINTENTANDO', 'FALLIDA')
                  AND n.intentos < COALESCE(n.max_intentos, %s)
                  AND (n.proximo_intento IS NULL OR n.proximo_intento <= NOW())
                ORDER BY n.creada_en
                LIMIT 1
                FOR UPDATE OF n SKIP LOCKED
            )
            UPDATE notificaciones n
            SET estado = 'EN_PROCESO',
                worker_id = %s,
                backend_pid = %s,
                heartbeat_en = NOW(),
                procesada_en = COALESCE(n.procesada_en, NOW()),
                actualizada_en = NOW()
            FROM candidata
            WHERE n.id = candidata.id
            RETURNING n.*, (SELECT u.correo FROM usuarios u WHERE u.id = n.usuario_id) AS correo
            """,
            (NOTIF_MAX_INTENTOS, ident, pid),
        )
        fila = cursor.fetchone()
        if fila:
            logger.info(
                "Notificación reclamada",
                extra={
                    "evento": "notificacion_reclamada",
                    "notificacion_id": fila["id"],
                    "worker_id": ident,
                    "estado": "EN_PROCESO",
                },
            )
        return dict(fila) if fila else None


def _registrar_intento(cursor, notificacion_id: int, resultado: str, mensaje: str, modo: str, worker_id: str | None) -> None:
    cursor.execute(
        """
        INSERT INTO intentos_notificacion (notificacion_id, resultado, mensaje, modo, worker_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (notificacion_id, resultado, mensaje, modo, worker_id),
    )


def procesar_reclamada(
    conexion,
    fila: dict,
    *,
    forzar_simulacion: bool = True,
    simular_fallo: bool | None = None,
) -> str:
    """Entrega una fila ya reclamada (EN_PROCESO). No crea notificaciones nuevas."""
    if fila.get("estado") in ESTADOS_TERMINALES and fila.get("estado") != "EN_PROCESO":
        return str(fila["estado"])

    modo = "simulacion"
    enviar_real = False
    if not forzar_simulacion and debe_enviar_smtp():
        modo = modo_canal()
        enviar_real = True

    fallar = NOTIF_SIMULAR_FALLO if simular_fallo is None else simular_fallo
    with conexion.cursor(row_factory=dict_row) as cursor:
        try:
            if fallar:
                raise EntregaSimuladaError("Fallo simulado de entrega (NOTIF_SIMULAR_FALLO)")
            if enviar_real:
                mensaje = enviar_correo(
                    fila["correo"], fila["asunto"], fila["cuerpo_texto"], fila["cuerpo_html"]
                )
                estado = "ACEPTADA_SMTP"
                resultado = "ACEPTADA_SMTP"
                cursor.execute(
                    "UPDATE notificaciones SET canal = 'smtp' WHERE id = %s",
                    (fila["id"],),
                )
            else:
                from src.config import OPERACION_PUBLICA

                if OPERACION_PUBLICA:
                    raise RuntimeError(
                        "SMTP_NO_CONFIGURADO: operación pública no simula el envío a ciudadanos"
                    )
                _guardar_simulacion(fila, fila["correo"])
                estado = "SIMULADA"
                resultado = "SIMULADA"
                mensaje = "Envío simulado. No se contactó a un destinatario real ni a SMTP."
            _registrar_intento(cursor, fila["id"], resultado, mensaje, modo, fila.get("worker_id"))
            cursor.execute(
                """
                UPDATE notificaciones
                SET estado = %s,
                    intentos = intentos + 1,
                    ultimo_error = NULL,
                    finalizada_en = NOW(),
                    proximo_intento = NULL,
                    worker_id = NULL,
                    backend_pid = NULL,
                    heartbeat_en = NULL,
                    actualizada_en = NOW()
                WHERE id = %s AND estado = 'EN_PROCESO'
                """,
                (estado, fila["id"]),
            )
            logger.info(
                "Notificación procesada",
                extra={
                    "evento": "notificacion_resultado",
                    "notificacion_id": fila["id"],
                    "worker_id": fila.get("worker_id"),
                    "estado": estado,
                },
            )
            return estado
        except Exception as error:
            logger.exception(
                "Fallo al procesar notificación %s",
                fila["id"],
                extra={"evento": "notificacion_error", "notificacion_id": fila["id"]},
            )
            intentos = int(fila.get("intentos") or 0) + 1
            max_i = int(fila.get("max_intentos") or NOTIF_MAX_INTENTOS)
            if intentos >= max_i:
                estado = "FALLIDA"
                proximo = None
            else:
                estado = "REINTENTANDO"
                proximo = datetime.now(timezone.utc) + timedelta(seconds=segundos_backoff(intentos))
            _registrar_intento(cursor, fila["id"], "FALLIDA", str(error)[:1000], modo, fila.get("worker_id"))
            cursor.execute(
                """
                UPDATE notificaciones
                SET estado = %s,
                    intentos = %s,
                    ultimo_error = %s,
                    proximo_intento = %s,
                    worker_id = NULL,
                    backend_pid = NULL,
                    heartbeat_en = NULL,
                    actualizada_en = NOW()
                WHERE id = %s AND estado = 'EN_PROCESO'
                """,
                (estado, intentos, str(error)[:1000], proximo, fila["id"]),
            )
            return estado


def procesar_outbox(
    conexion,
    limite: int = 50,
    forzar_simulacion: bool = False,
    simular_fallo: bool | None = None,
    worker_id: str | None = None,
) -> dict:
    modo = modo_canal() if (not forzar_simulacion and debe_enviar_smtp()) else "simulacion"

    reconciliar_notificaciones_huerfanas(conexion)
    procesadas = 0
    simuladas = 0
    aceptadas = 0
    fallidas = 0
    reintentando = 0
    ident = worker_id or worker_id_local()
    for _ in range(max(1, limite)):
        fila = reclamar_notificacion(conexion, ident)
        if not fila:
            break
        procesadas += 1
        estado = procesar_reclamada(
            conexion,
            fila,
            forzar_simulacion=forzar_simulacion,
            simular_fallo=simular_fallo,
        )
        if estado == "SIMULADA":
            simuladas += 1
        elif estado == "ACEPTADA_SMTP":
            aceptadas += 1
        elif estado == "REINTENTANDO":
            reintentando += 1
            fallidas += 1
        elif estado == "FALLIDA":
            fallidas += 1
    return {
        "procesadas": procesadas,
        "simuladas": simuladas,
        "aceptadas_smtp": aceptadas,
        "fallidas": fallidas,
        "reintentando": reintentando,
        "modo": modo,
    }
