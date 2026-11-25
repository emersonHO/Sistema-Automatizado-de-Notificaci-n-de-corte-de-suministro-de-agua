from src.pipeline import ejecutar_pipeline
from src.solicitudes import crear_solicitud, obtener_ejecucion_de_solicitud, obtener_solicitud
from src.worker_pipeline import ciclo_una_vez


def test_worker_fixture_y_no_relanza_terminal(conexion, captura_minima, tmp_path, monkeypatch):
    from src import recolector as rec
    from src import config as cfg

    monkeypatch.setattr(rec, "CARPETA_RAW", tmp_path / "raw")
    rec.CARPETA_RAW.mkdir(parents=True)
    monkeypatch.setattr(cfg, "CARPETA_RAW", tmp_path / "raw")

    fila, _ = crear_solicitud(
        "MANUAL",
        modo="fixture",
        ruta_fixture=str(captura_minima),
        conexion=conexion,
    )
    assert ciclo_una_vez("pytest-worker") is True
    actual = obtener_solicitud(fila["id"])
    assert actual["estado"] in {"COMPLETADO", "COMPLETADO_INCOMPLETO"}
    ejec = obtener_ejecucion_de_solicitud(fila["id"])
    assert ejec is not None
    assert ejec["solicitud_id"] == fila["id"]
    assert actual["ejecucion_id"] == ejec["id"]

    # Relanzar ejecutar_pipeline con el mismo solicitud_id debe chocar el UNIQUE;
    # el worker no debe crear una segunda fila.
    ciclo_una_vez("pytest-worker")
    with conexion.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM ejecuciones_proceso WHERE solicitud_id = %s",
            (fila["id"],),
        )
        assert cursor.fetchone()[0] == 1


def test_pipeline_cli_sin_solicitud(conexion, captura_minima, tmp_path, monkeypatch):
    from src import recolector as rec
    from src import config as cfg

    monkeypatch.setattr(rec, "CARPETA_RAW", tmp_path / "raw")
    rec.CARPETA_RAW.mkdir(parents=True)
    monkeypatch.setattr(cfg, "CARPETA_RAW", tmp_path / "raw")
    resultado = ejecutar_pipeline(
        desde_archivo=captura_minima,
        procesar_envios=False,
        forzar_simulacion=True,
        solicitud_id=None,
    )
    assert resultado["estado"] in {"COMPLETADO", "COMPLETADO_INCOMPLETO"}
    with conexion.cursor() as cursor:
        cursor.execute(
            "SELECT solicitud_id FROM ejecuciones_proceso WHERE id = %s",
            (resultado["ejecucion_id"],),
        )
        assert cursor.fetchone()[0] is None
