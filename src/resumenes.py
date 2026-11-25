"""Resumen diario opcional. No duplica el pipeline ni inventa incidencias."""

from __future__ import annotations

from datetime import date

from psycopg.rows import dict_row

from src.config import ZONA_SISTEMA
from src.url_publica import url_base
from src.ciudadano import _enviar_transaccional
from src.correspondencia import coincidencia_notificable, evaluar_par
from src.plantillas_correo import resumen as plantilla_resumen
from src.tokens import enlace_baja, enlace_gestion


def generar_resumenes(conexion, fecha: date | None = None) -> dict:
    dia = fecha or date.today()
    enviados = 0
    omitidos = 0
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT DISTINCT u.id, u.correo
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.activa AND s.confirmada AND COALESCE(s.resumen_diario, FALSE)
              AND COALESCE(s.pausada, FALSE) = FALSE
              AND u.activo AND u.correo_confirmado
              AND COALESCE(u.pausado, FALSE) = FALSE
            """
        )
        usuarios = list(cursor.fetchall())
        cursor.execute(
            """
            SELECT id, municipalidad, areas_afectadas, infor_web, tipo_incid, estado,
                   causa, fec_deteccion, fec_estimada, cod_incidencia, datos
            FROM interrupciones
            WHERE ambito_lima IS TRUE
              AND (ultima_captura::date = CURRENT_DATE OR fec_deteccion::date = CURRENT_DATE
                   OR actualizado_en_fuente::date = CURRENT_DATE)
            """
        )
        interrupciones = list(cursor.fetchall())

    from src.suscripciones import suscripciones_activas

    activas = [s for s in suscripciones_activas(conexion) if s.get("resumen_diario")]
    por_usuario: dict[int, list] = {}
    for sus in activas:
        por_usuario.setdefault(sus["usuario_id"], []).append(sus)

    for usuario in usuarios:
        uid = usuario["id"]
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO resumenes_enviados (usuario_id, fecha_local, estado)
                VALUES (%s, %s, 'EN_PROCESO')
                ON CONFLICT (usuario_id, fecha_local) DO NOTHING
                RETURNING id
                """,
                (uid, dia),
            )
            if cursor.fetchone() is None:
                omitidos += 1
                continue
        filas = []
        nombres = []
        for sus in por_usuario.get(uid, []):
            nombres.append(sus["nombre"])
            zona = {
                "id": sus["zona_id"],
                "tipo": sus["tipo"],
                "nombre": sus["nombre"],
                "nombre_normalizado": sus["nombre_normalizado"],
                "distrito_padre": sus["distrito_padre"],
                "ambito_lima": sus["ambito_lima"],
            }
            for fila in interrupciones:
                registro = dict(fila.get("datos") or {})
                registro.update({k: fila[k] for k in fila if k != "datos"})
                resultado = evaluar_par(registro, zona)
                if coincidencia_notificable(resultado):
                    filas.append(registro)
        # deduplicar por id
        vistos = set()
        unicas = []
        for f in filas:
            i = f.get("id")
            if i in vistos:
                continue
            vistos.add(i)
            unicas.append(f)
        asunto, texto, html = plantilla_resumen(
            sorted(set(nombres)),
            unicas,
            enlace_gestion(url_base(), uid),
            enlace_baja(url_base(), uid),
        )
        try:
            _enviar_transaccional(usuario["correo"], asunto, texto, html)
            from src.correo import debe_enviar_smtp

            estado = "ACEPTADA_SMTP" if debe_enviar_smtp() else "SIMULADA"
            with conexion.cursor() as cursor:
                cursor.execute(
                    "UPDATE resumenes_enviados SET estado = %s WHERE usuario_id = %s AND fecha_local = %s",
                    (estado, uid, dia),
                )
            enviados += 1
        except Exception as error:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE resumenes_enviados
                    SET estado = 'FALLIDA', detalle = %s
                    WHERE usuario_id = %s AND fecha_local = %s
                    """,
                    (str(error)[:500], uid, dia),
                )
    return {"enviados": enviados, "omitidos": omitidos, "fecha": str(dia), "zona": ZONA_SISTEMA}
