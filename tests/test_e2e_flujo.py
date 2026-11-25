"""Flujo integral sobre notificaciones_agua_test. No usa notificaciones_agua."""

from __future__ import annotations

import os
import socket

from src.db import conectar
from src.pipeline import ejecutar_pipeline
from src.suscripciones import confirmar_correo, suscribir
from src.worker_notificaciones import ciclo_una_vez


def _suscribir(correo: str, zonas: list[dict]):
    with conectar() as cx:
        r = suscribir(correo, zonas, conexion=cx)
        confirmar_correo(r["usuario"]["token_confirmacion"], conexion=cx)
        cx.commit()
    return r


def _parche_raw(monkeypatch, tmp_path):
    from src import recolector as rec
    from src import config as cfg
    from src import notificaciones as notif

    raw = tmp_path / "raw"
    sim = tmp_path / "sim"
    raw.mkdir()
    sim.mkdir()
    monkeypatch.setattr(rec, "CARPETA_RAW", raw)
    monkeypatch.setattr(cfg, "CARPETA_RAW", raw)
    monkeypatch.setattr(cfg, "CARPETA_SIMULACIONES", sim)
    monkeypatch.setattr(notif, "CARPETA_SIMULACIONES", sim)
    return raw, sim


def test_e2e_fixture_matching_outbox_simulacion(conexion, captura_minima, tmp_path, monkeypatch):
    _parche_raw(monkeypatch, tmp_path)
    _suscribir(
        "e2e.santa@example.com",
        [{"tipo": "DISTRITO", "nombre": "Santa Anita"}],
    )
    primero = ejecutar_pipeline(
        desde_archivo=captura_minima, procesar_envios=False, forzar_simulacion=True
    )
    assert primero["estado"] in {"COMPLETADO", "COMPLETADO_INCOMPLETO"}
    assert primero["calidad"]["valido"] is True
    assert primero["contadores"]["nuevo"] >= 1
    assert primero["coincidencias"]["notificaciones_creadas"] >= 1

    with conectar() as cx:
        with cx.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM interrupciones WHERE id IN (125524, 125516)")
            assert cursor.fetchone()[0] == 2
            cursor.execute(
                """
                SELECT n.estado, n.tipo_evento FROM notificaciones n
                JOIN usuarios u ON u.id = n.usuario_id
                WHERE u.correo = 'e2e.santa@example.com'
                """
            )
            filas = cursor.fetchall()
    assert filas
    assert all(e[0] == "PENDIENTE" for e in filas)
    assert any(e[1] == "NUEVA" for e in filas)

    trabajo = ciclo_una_vez(worker_id="e2e-sim", limite=20)
    assert trabajo is True
    with conectar() as cx:
        with cx.cursor() as cursor:
            cursor.execute(
                """
                SELECT n.estado, n.canal, COUNT(*) AS c
                FROM notificaciones n
                JOIN usuarios u ON u.id = n.usuario_id
                WHERE u.correo = 'e2e.santa@example.com'
                GROUP BY 1, 2
                """
            )
            por_estado = {(r[0], r[1]): r[2] for r in cursor.fetchall()}
            cursor.execute(
                "SELECT COUNT(*) FROM intentos_notificacion"
            )
            intentos = cursor.fetchone()[0]
    assert por_estado.get(("SIMULADA", "simulacion"), 0) >= 1
    assert intentos >= 1
    sims = list((tmp_path / "sim").glob("*.json"))
    assert sims, "Debe existir archivo de simulación"

    segundo = ejecutar_pipeline(
        desde_archivo=captura_minima, procesar_envios=False, forzar_simulacion=True
    )
    assert segundo["contadores"]["nuevo"] == 0
    assert segundo["coincidencias"]["notificaciones_creadas"] == 0
    with conectar() as cx:
        with cx.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM notificaciones")
            n = cursor.fetchone()[0]
    assert n == sum(por_estado.values())


def test_e2e_sin_territorio_no_notifica(conexion, captura_minima, tmp_path, monkeypatch):
    _parche_raw(monkeypatch, tmp_path)
    _suscribir("e2e.lince@example.com", [{"tipo": "DISTRITO", "nombre": "Lince"}])
    ejecutar_pipeline(desde_archivo=captura_minima, procesar_envios=False, forzar_simulacion=True)
    with conectar() as cx:
        with cx.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM notificaciones")
            assert cursor.fetchone()[0] == 0


def test_e2e_smtp_laboratorio_mailpit(conexion, captura_minima, tmp_path, monkeypatch):
    host = os.environ.get("MAILPIT_SMTP_HOST", "mailpit")
    puerto = int(os.environ.get("MAILPIT_SMTP_PORT", "1025"))
    try:
        socket.create_connection((host, puerto), timeout=2).close()
    except OSError:
        try:
            socket.create_connection(("127.0.0.1", puerto), timeout=2).close()
            host = "127.0.0.1"
        except OSError:
            import pytest

            pytest.skip("Mailpit SMTP no alcanzable (esperado fuera de la red Compose)")

    _parche_raw(monkeypatch, tmp_path)
    from src import correo as correo_mod
    from src.notificaciones import procesar_outbox

    monkeypatch.setattr(correo_mod, "SMTP_ENABLED", True)
    monkeypatch.setattr(correo_mod, "MODO_ENVIO", "mailpit")
    monkeypatch.setattr(correo_mod, "SMTP_HOST", host)
    monkeypatch.setattr(correo_mod, "SMTP_PORT", puerto)
    monkeypatch.setattr(correo_mod, "SMTP_STARTTLS", False)
    monkeypatch.setattr(correo_mod, "SMTP_USER", "")
    monkeypatch.setattr(correo_mod, "SMTP_PASSWORD", "")
    monkeypatch.setattr(correo_mod, "SMTP_FROM", "lab@localhost")

    _suscribir(
        "e2e.mailpit@example.com",
        [{"tipo": "DISTRITO", "nombre": "Independencia"}],
    )
    ejecutar_pipeline(desde_archivo=captura_minima, procesar_envios=False, forzar_simulacion=True)
    with conectar() as cx:
        resumen = procesar_outbox(cx, limite=20, forzar_simulacion=False, worker_id="e2e-mailpit")
        cx.commit()
        with cx.cursor() as cursor:
            cursor.execute(
                """
                SELECT n.estado FROM notificaciones n
                JOIN usuarios u ON u.id = n.usuario_id
                WHERE u.correo = 'e2e.mailpit@example.com'
                """
            )
            estados = [r[0] for r in cursor.fetchall()]
            cursor.execute("SELECT COUNT(*) FROM intentos_notificacion WHERE resultado = 'ACEPTADA_SMTP'")
            aceptadas = cursor.fetchone()[0]
    assert resumen.get("aceptadas_smtp") or all(e == "ACEPTADA_SMTP" for e in estados)
    assert estados
    assert all(e == "ACEPTADA_SMTP" for e in estados)
    assert aceptadas >= 1

    with conectar() as cx:
        segundo = procesar_outbox(cx, limite=20, forzar_simulacion=False, worker_id="e2e-mailpit")
        cx.commit()
    assert int(segundo.get("procesadas") or 0) == 0
