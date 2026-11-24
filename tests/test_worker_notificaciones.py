from src.db import conectar
from src.notificaciones import (
    procesar_outbox,
    reclamar_notificacion,
    reconciliar_notificaciones_huerfanas,
)
from src.pipeline import ejecutar_pipeline
from src.suscripciones import confirmar_correo, suscribir
from src.worker_notificaciones import ciclo_una_vez


def _pendientes(conexion, captura_minima, tmp_path, monkeypatch, correo="worker.prueba@example.com"):
    from src import recolector as rec
    from src import config as cfg

    monkeypatch.setattr(rec, "CARPETA_RAW", tmp_path / "raw")
    rec.CARPETA_RAW.mkdir(parents=True)
    monkeypatch.setattr(cfg, "CARPETA_RAW", tmp_path / "raw")
    with conectar() as cx:
        r = suscribir(correo, [{"tipo": "DISTRITO", "nombre": "Santa Anita"}], conexion=cx)
        confirmar_correo(r["usuario"]["token_confirmacion"], conexion=cx)
        cx.commit()
    ejecutar_pipeline(desde_archivo=captura_minima, procesar_envios=False, forzar_simulacion=True)


def test_worker_procesa_pendientes(conexion, captura_minima, tmp_path, monkeypatch):
    _pendientes(conexion, captura_minima, tmp_path, monkeypatch)
    assert ciclo_una_vez("pytest-notif") is True
    with conectar() as cx:
        with cx.cursor() as cursor:
            cursor.execute("SELECT estado FROM notificaciones")
            estados = {fila[0] for fila in cursor.fetchall()}
            cursor.execute("SELECT COUNT(*) FROM intentos_notificacion")
            intentos = cursor.fetchone()[0]
    assert "SIMULADA" in estados
    assert "ACEPTADA_SMTP" not in estados
    assert "ENVIADA" not in estados
    assert intentos >= 1
    assert ciclo_una_vez("pytest-notif") is False


def test_no_reprocesa_simulada(conexion, captura_minima, tmp_path, monkeypatch):
    _pendientes(conexion, captura_minima, tmp_path, monkeypatch, correo="norepro@example.com")
    with conectar() as cx:
        primero = procesar_outbox(cx, forzar_simulacion=True)
        cx.commit()
        segundo = procesar_outbox(cx, forzar_simulacion=True)
        cx.commit()
        with cx.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM intentos_notificacion")
            n_intentos = cursor.fetchone()[0]
    assert primero["simuladas"] >= 1
    assert segundo["procesadas"] == 0
    assert n_intentos == primero["procesadas"]


def test_dos_workers_no_reclaman_la_misma(conexion, captura_minima, tmp_path, monkeypatch):
    _pendientes(conexion, captura_minima, tmp_path, monkeypatch, correo="lock@example.com")
    c1 = conectar()
    c2 = conectar()
    try:
        a = reclamar_notificacion(c1, "w1")
        b = reclamar_notificacion(c2, "w2")
        assert a is not None
        assert b is None or a["id"] != b["id"]
    finally:
        c1.rollback()
        c2.rollback()
        c1.close()
        c2.close()


def test_fallo_simulado_reintento_y_maximo(conexion, captura_minima, tmp_path, monkeypatch):
    from src import notificaciones as notif

    monkeypatch.setattr(notif, "NOTIF_BACKOFF_BASE_S", 0)
    monkeypatch.setattr(notif, "NOTIF_MAX_INTENTOS", 2)
    _pendientes(conexion, captura_minima, tmp_path, monkeypatch, correo="fallo@example.com")
    with conectar() as cx:
        with cx.cursor() as cursor:
            cursor.execute("UPDATE notificaciones SET max_intentos = 2")
        cx.commit()
        r1 = procesar_outbox(cx, forzar_simulacion=True, simular_fallo=True, limite=20)
        cx.commit()
        with cx.cursor() as cursor:
            cursor.execute("SELECT estado, intentos FROM notificaciones")
            filas = list(cursor.fetchall())
        assert r1["fallidas"] >= 1
        assert any(f[0] == "REINTENTANDO" for f in filas)
        r2 = procesar_outbox(cx, forzar_simulacion=True, simular_fallo=True, limite=20)
        cx.commit()
        with cx.cursor() as cursor:
            cursor.execute("SELECT estado, intentos FROM notificaciones")
            filas2 = list(cursor.fetchall())
            cursor.execute("SELECT COUNT(*) FROM intentos_notificacion")
            n_intentos = cursor.fetchone()[0]
        assert any(f[0] == "FALLIDA" and f[1] >= 2 for f in filas2)
        assert r2["procesadas"] >= 1
        r3 = procesar_outbox(cx, forzar_simulacion=True, simular_fallo=True, limite=20)
        cx.commit()
        assert r3["procesadas"] == 0
        assert n_intentos >= 2


def test_recuperacion_en_proceso_huerfana(conexion, captura_minima, tmp_path, monkeypatch):
    _pendientes(conexion, captura_minima, tmp_path, monkeypatch, correo="huerfana@example.com")
    with conectar() as cx:
        with cx.cursor() as cursor:
            cursor.execute(
                """
                UPDATE notificaciones
                SET estado = 'EN_PROCESO', backend_pid = 999999, worker_id = 'muerto'
                """
            )
        cx.commit()
        n = reconciliar_notificaciones_huerfanas(cx)
        cx.commit()
        with cx.cursor() as cursor:
            cursor.execute("SELECT estado FROM notificaciones")
            estados = {fila[0] for fila in cursor.fetchall()}
    assert n >= 1
    assert "EN_PROCESO" not in estados
    assert estados <= {"REINTENTANDO", "FALLIDA", "PENDIENTE"}
    with conectar() as cx:
        r = procesar_outbox(cx, forzar_simulacion=True)
        cx.commit()
    assert r["simuladas"] >= 1
