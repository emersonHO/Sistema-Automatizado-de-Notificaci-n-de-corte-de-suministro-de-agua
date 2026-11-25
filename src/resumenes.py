"""Resumen periódico. No duplica el pipeline ni inventa incidencias."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row

from src.config import ZONA_SISTEMA
from src.url_publica import url_base
from src.ciudadano import _enviar_transaccional
from src.correspondencia import coincidencia_notificable, evaluar_par
from src.plantillas_correo import resumen as plantilla_resumen
from src.tokens import enlace_baja, enlace_gestion


def generar_resumenes(conexion, fecha: date | None = None, tipo: str | None = None) -> dict:
    tz = ZoneInfo(ZONA_SISTEMA)
    ahora = datetime.now(tz)
    dia = fecha or ahora.date()
    tipo_hoy = tipo or ("semanal" if ahora.weekday() == 0 else "diario")
    enviados = 0
    omitidos = 0
    with conexion.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT DISTINCT u.id, u.correo, COALESCE(u.resumen_frecuencia, 'ninguno') AS frecuencia,
                   COALESCE(u.informe_sin_cortes, TRUE) AS informe_sin_cortes
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.activa AND s.confirmada
              AND COALESCE(s.pausada, FALSE) = FALSE
              AND u.activo AND u.correo_confirmado
              AND COALESCE(u.pausado, FALSE) = FALSE
              AND (
                    COALESCE(s.resumen_diario, FALSE)
                    OR COALESCE(u.resumen_frecuencia, 'ninguno') IN ('diario', 'semanal')
              )
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

    activas = suscripciones_activas(conexion)
    por_usuario: dict[int, list] = {}
    for sus in activas:
        por_usuario.setdefault(sus["usuario_id"], []).append(sus)

    for usuario in usuarios:
        uid = usuario["id"]
        frecuencia = (usuario.get("frecuencia") or "ninguno").lower()
        if frecuencia == "ninguno" and not any(
            s.get("resumen_diario") for s in por_usuario.get(uid, [])
        ):
            omitidos += 1
            continue
        if tipo_hoy == "diario" and frecuencia == "semanal":
            omitidos += 1
            continue
        if tipo_hoy == "semanal" and frecuencia not in {"semanal", "diario"}:
            if not any(s.get("resumen_diario") for s in por_usuario.get(uid, [])):
                omitidos += 1
                continue
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO resumenes_enviados (usuario_id, fecha_local, estado, tipo)
                VALUES (%s, %s, 'EN_PROCESO', %s)
                ON CONFLICT (usuario_id, fecha_local, tipo) DO NOTHING
                RETURNING id
                """,
                (uid, dia, tipo_hoy),
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
        vistos = set()
        unicas = []
        for f in filas:
            i = f.get("id")
            if i in vistos:
                continue
            vistos.add(i)
            unicas.append(f)
        if not unicas and not usuario.get("informe_sin_cortes", True):
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE resumenes_enviados
                    SET estado = 'OMITIDA', detalle = 'sin cortes y usuario no pidió informe vacío'
                    WHERE usuario_id = %s AND fecha_local = %s AND tipo = %s
                    """,
                    (uid, dia, tipo_hoy),
                )
            omitidos += 1
            continue
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
                    """
                    UPDATE resumenes_enviados
                    SET estado = %s WHERE usuario_id = %s AND fecha_local = %s AND tipo = %s
                    """,
                    (estado, uid, dia, tipo_hoy),
                )
            enviados += 1
        except Exception as error:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE resumenes_enviados
                    SET estado = 'FALLIDA', detalle = %s
                    WHERE usuario_id = %s AND fecha_local = %s AND tipo = %s
                    """,
                    (str(error)[:500], uid, dia, tipo_hoy),
                )
    return {
        "enviados": enviados,
        "omitidos": omitidos,
        "fecha": str(dia),
        "tipo": tipo_hoy,
        "zona": ZONA_SISTEMA,
    }


def main() -> int:
    from src.db import aplicar_esquema, conectar
    from src.logging_config import configurar_logging

    configurar_logging()
    aplicar_esquema()
    with conectar() as conexion:
        resumen = generar_resumenes(conexion)
        conexion.commit()
    print(resumen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
