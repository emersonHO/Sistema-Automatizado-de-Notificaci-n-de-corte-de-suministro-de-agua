from __future__ import annotations

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


def listar_notificaciones(conexion, limite=200):
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT n.id, n.interrupcion_id, n.tipo_evento, n.nivel_coincidencia,
                   n.estado, n.intentos, n.ultimo_error, n.creada_en,
                   n.version_relevante, n.suscripcion_id, u.correo,
                   z.nombre AS zona, z.tipo AS zona_tipo
            FROM notificaciones n
            JOIN usuarios u ON u.id = n.usuario_id
            JOIN suscripciones s ON s.id = n.suscripcion_id
            JOIN zonas z ON z.id = s.zona_id
            ORDER BY n.creada_en DESC
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


def intentos_de(conexion, notificacion_id: int):
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT fecha_intento, resultado, mensaje, modo
            FROM intentos_notificacion
            WHERE notificacion_id = %s
            ORDER BY fecha_intento
            """,
            (notificacion_id,),
        )
        return list(cursor.fetchall())
