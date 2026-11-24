from __future__ import annotations

import time

from psycopg.rows import dict_row

from src.privacidad import enmascarar_correo


def resumen_panel(conexion) -> dict:
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM interrupciones")
        total = cursor.fetchone()["n"]
        cursor.execute(
            """
            SELECT * FROM ejecuciones_proceso
            ORDER BY fecha_inicio DESC
            LIMIT 1
            """
        )
        ultima = cursor.fetchone()
        cursor.execute(
            """
            SELECT estado, COUNT(*) AS n
            FROM notificaciones
            GROUP BY estado
            """
        )
        estados = {fila["estado"]: fila["n"] for fila in cursor.fetchall()}
        cursor.execute(
            """
            SELECT id, cod_incidencia, municipalidad, tipo_incid, estado,
                   fec_deteccion, fec_estimada, ultima_captura, version_relevante
            FROM interrupciones
            ORDER BY ultima_captura DESC
            LIMIT 15
            """
        )
        recientes = list(cursor.fetchall())
        cursor.execute(
            """
            SELECT COUNT(*) FILTER (WHERE tipo_evento = 'NUEVA') AS nuevas,
                   COUNT(*) FILTER (WHERE tipo_evento = 'MODIFICADA') AS modificadas
            FROM historial_interrupciones
            WHERE fecha_registro >= NOW() - INTERVAL '14 days'
            """
        )
        hist = cursor.fetchone()
    return {
        "total_interrupciones": total,
        "ultima": ultima,
        "estados_notif": estados,
        "recientes": recientes,
        "nuevas_14d": hist["nuevas"] if hist else 0,
        "modificadas_14d": hist["modificadas"] if hist else 0,
    }


def listar_interrupciones(conexion, distrito=None, tipo=None, limite=200):
    filtros = []
    params: list = []
    if distrito:
        filtros.append("municipalidad_normalizada = %s")
        params.append(distrito.strip().upper())
    if tipo:
        filtros.append("tipo_incid = %s")
        params.append(tipo.strip().upper())
    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    sql = f"""
        SELECT id, cod_incidencia, municipalidad, tipo_incid, estado, causa,
               areas_afectadas, infor_web, fec_deteccion, fec_estimada,
               ambito_lima, version_relevante, ultima_captura
        FROM interrupciones
        {where}
        ORDER BY fec_deteccion DESC NULLS LAST
        LIMIT %s
    """
    params.append(limite)
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(sql, params)
        return list(cursor.fetchall())


def detalle_interrupcion(conexion, interrupcion_id: int):
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT * FROM interrupciones WHERE id = %s", (interrupcion_id,))
        fila = cursor.fetchone()
        if not fila:
            return None, []
        cursor.execute(
            """
            SELECT version_origen, version_relevante, tipo_evento, cambio_relevante,
                   campos_modificados, fecha_registro
            FROM historial_interrupciones
            WHERE interrupcion_id = %s
            ORDER BY version_origen
            """,
            (interrupcion_id,),
        )
        historial = list(cursor.fetchall())
    return fila, historial


def listar_ejecuciones(conexion, limite=100):
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT * FROM ejecuciones_proceso
            ORDER BY fecha_inicio DESC
            LIMIT %s
            """,
            (limite,),
        )
        return list(cursor.fetchall())


def estadisticas_notificaciones(conexion) -> dict:
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT estado, COUNT(*) AS n
            FROM notificaciones
            GROUP BY estado
            """
        )
        por_estado = {fila["estado"]: fila["n"] for fila in cursor.fetchall()}
        cursor.execute("SELECT COUNT(*) AS n FROM notificaciones")
        total = cursor.fetchone()["n"]
        cursor.execute("SELECT COUNT(*) AS n FROM intentos_notificacion")
        intentos = cursor.fetchone()["n"]
        cursor.execute(
            """
            SELECT COUNT(*) AS n FROM usuarios
            WHERE correo_confirmado IS TRUE
            """
        )
        destinatarios = cursor.fetchone()["n"]
    return {
        "total": total,
        "por_estado": por_estado,
        "intentos": intentos,
        "destinatarios_confirmados": destinatarios,
    }


def obtener_notificacion(conexion, notificacion_id: int):
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT n.id, n.interrupcion_id, n.tipo_evento, n.nivel_coincidencia,
                   n.estado, n.canal, n.motivo, n.intentos, n.max_intentos,
                   n.ultimo_error, n.creada_en, n.actualizada_en,
                   n.procesada_en, n.finalizada_en, n.proximo_intento,
                   n.version_relevante, n.suscripcion_id, n.asunto,
                   u.correo, z.nombre AS zona, z.tipo AS zona_tipo
            FROM notificaciones n
            JOIN usuarios u ON u.id = n.usuario_id
            JOIN suscripciones s ON s.id = n.suscripcion_id
            JOIN zonas z ON z.id = s.zona_id
            WHERE n.id = %s
            """,
            (notificacion_id,),
        )
        fila = cursor.fetchone()
        if not fila:
            return None
        fila = dict(fila)
        fila["destinatario"] = enmascarar_correo(fila.pop("correo"))
        return fila


def listar_destinatarios(conexion, limite=200):
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT u.id AS usuario_id, u.correo, u.correo_confirmado, u.creado_en,
                   s.id AS suscripcion_id, s.activa, s.confirmada,
                   z.tipo AS zona_tipo, z.nombre AS zona
            FROM usuarios u
            LEFT JOIN suscripciones s ON s.usuario_id = u.id
            LEFT JOIN zonas z ON z.id = s.zona_id
            ORDER BY u.id, s.id
            LIMIT %s
            """,
            (limite,),
        )
        filas = []
        for fila in cursor.fetchall():
            fila = dict(fila)
            fila["destinatario"] = enmascarar_correo(fila.pop("correo"))
            filas.append(fila)
        return filas


def listar_notificaciones(conexion, limite=200, estado: str | None = None):
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT n.id, n.interrupcion_id, n.tipo_evento, n.nivel_coincidencia,
                   n.estado, n.canal, n.motivo, n.intentos, n.ultimo_error, n.creada_en,
                   n.version_relevante, n.suscripcion_id, u.correo,
                   z.nombre AS zona, z.tipo AS zona_tipo
            FROM notificaciones n
            JOIN usuarios u ON u.id = n.usuario_id
            JOIN suscripciones s ON s.id = n.suscripcion_id
            JOIN zonas z ON z.id = s.zona_id
            WHERE (%s::text IS NULL OR n.estado = %s)
            ORDER BY n.creada_en DESC
            LIMIT %s
            """,
            (estado, estado, limite),
        )
        filas = []
        for fila in cursor.fetchall():
            fila = dict(fila)
            fila["destinatario"] = enmascarar_correo(fila.pop("correo"))
            filas.append(fila)
        return filas


def listar_auditoria(conexion, limite=100):
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT h.id, h.interrupcion_id, h.tipo_evento, h.cambio_relevante,
                   h.version_origen, h.version_relevante, h.fecha_registro,
                   i.municipalidad, i.cod_incidencia
            FROM historial_interrupciones h
            JOIN interrupciones i ON i.id = h.interrupcion_id
            ORDER BY h.fecha_registro DESC
            LIMIT %s
            """,
            (limite,),
        )
        return list(cursor.fetchall())


def sondear_url(url: str, timeout: float = 1.5) -> dict:
    import urllib.error
    import urllib.request

    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            codigo = resp.getcode()
        return {
            "ok": 200 <= codigo < 400,
            "codigo": codigo,
            "ms": int((time.perf_counter() - inicio) * 1000),
        }
    except Exception as error:
        return {
            "ok": False,
            "codigo": None,
            "ms": int((time.perf_counter() - inicio) * 1000),
            "error": str(error)[:160],
        }


def intentos_de(conexion, notificacion_id: int):
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT fecha_intento, resultado, mensaje, modo, worker_id
            FROM intentos_notificacion
            WHERE notificacion_id = %s
            ORDER BY fecha_intento
            """,
            (notificacion_id,),
        )
        return list(cursor.fetchall())
