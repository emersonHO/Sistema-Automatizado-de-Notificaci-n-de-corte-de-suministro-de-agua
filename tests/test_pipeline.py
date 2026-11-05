import json
from pathlib import Path

from src.db import conectar
from src.pipeline import ejecutar_pipeline
from src.suscripciones import confirmar_correo, suscribir


def _contar(sql, params=None):
    with conectar() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchone()[0]


def test_pipeline_idempotente_y_notificacion(conexion, captura_minima, tmp_path, monkeypatch):
    from src import recolector as rec
    from src import config as cfg

    monkeypatch.setattr(rec, "CARPETA_RAW", tmp_path / "raw")
    rec.CARPETA_RAW.mkdir(parents=True)
    monkeypatch.setattr(cfg, "CARPETA_RAW", tmp_path / "raw")

    with conectar() as cx:
        resultado = suscribir(
            "usuario.prueba@example.com",
            [{"tipo": "DISTRITO", "nombre": "Santa Anita"}],
            conexion=cx,
        )
        token = resultado["usuario"]["token_confirmacion"]
        confirmar_correo(token, conexion=cx)
        cx.commit()

    primero = ejecutar_pipeline(desde_archivo=captura_minima, procesar_envios=True, forzar_simulacion=True)
    assert primero["estado"] in {"COMPLETADO", "COMPLETADO_INCOMPLETO"}
    assert primero["contadores"]["nuevo"] == 2
    assert primero["coincidencias"]["notificaciones_creadas"] >= 1
    notif_1 = _contar("SELECT COUNT(*) FROM notificaciones")

    segundo = ejecutar_pipeline(desde_archivo=captura_minima, procesar_envios=True, forzar_simulacion=True)
    assert segundo["contadores"]["nuevo"] == 0
    assert segundo["contadores"]["sin_cambios"] == 2
    assert segundo["coincidencias"]["notificaciones_creadas"] == 0
    notif_2 = _contar("SELECT COUNT(*) FROM notificaciones")
    assert notif_2 == notif_1

    modificado = json.loads(captura_minima.read_text(encoding="utf-8"))
    modificado["data"][0]["areas_afectadas"] = "Urbanización distinta"
    ruta = tmp_path / "modificado.json"
    ruta.write_text(json.dumps(modificado), encoding="utf-8")
    tercero = ejecutar_pipeline(desde_archivo=ruta, procesar_envios=True, forzar_simulacion=True)
    assert tercero["contadores"]["actualizado"] >= 1
    assert tercero["contadores"]["cambios_relevantes"] >= 1
    notif_3 = _contar("SELECT COUNT(*) FROM notificaciones")
    assert notif_3 > notif_2
    tipos = _contar("SELECT COUNT(*) FROM notificaciones WHERE tipo_evento = 'MODIFICADA'")
    assert tipos >= 1

    # Cambio irrelevante (imagen) no crea notificación nueva.
    irrel = json.loads(ruta.read_text(encoding="utf-8"))
    irrel["data"][0]["imagen_url"] = "otra.png"
    ruta2 = tmp_path / "irrel.json"
    ruta2.write_text(json.dumps(irrel), encoding="utf-8")
    cuarto = ejecutar_pipeline(desde_archivo=ruta2, procesar_envios=True, forzar_simulacion=True)
    assert cuarto["contadores"]["cambios_relevantes"] == 0
    assert _contar("SELECT COUNT(*) FROM notificaciones") == notif_3


def test_fallo_de_fuente_registrable(conexion, monkeypatch):
    from src.recolector import RespuestaFuenteError, recolectar

    def boom(**kwargs):
        raise RespuestaFuenteError("fuente caida")

    monkeypatch.setattr("src.pipeline.recolectar", boom)
    try:
        ejecutar_pipeline()
        assert False, "debía fallar"
    except RespuestaFuenteError:
        with conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT estado FROM ejecuciones_proceso ORDER BY id DESC LIMIT 1"
                )
                fila = cursor.fetchone()
        assert fila[0] == "ERROR"
