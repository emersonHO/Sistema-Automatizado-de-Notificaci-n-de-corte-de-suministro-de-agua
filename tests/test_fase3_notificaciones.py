from src.db import aplicar_esquema, conectar
from src.notificaciones import procesar_outbox, renderizar_mensaje
from src.pipeline import ejecutar_pipeline
from src.suscripciones import confirmar_correo, suscribir
from src.web.app import app


def _suscribir(correo: str, zonas: list[dict]):
    with conectar() as cx:
        r = suscribir(correo, zonas, conexion=cx)
        confirmar_correo(r["usuario"]["token_confirmacion"], conexion=cx)
        cx.commit()
    return r


def test_esquema_aditivo_idempotente(conexion):
    aplicar_esquema()
    aplicar_esquema()
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'notificaciones'
              AND column_name IN ('canal', 'motivo', 'proximo_intento', 'max_intentos',
                                  'worker_id', 'heartbeat_en', 'backend_pid',
                                  'procesada_en', 'finalizada_en')
            """
        )
        columnas = {fila[0] for fila in cursor.fetchall()}
    assert columnas >= {
        "canal",
        "motivo",
        "proximo_intento",
        "max_intentos",
        "worker_id",
        "procesada_en",
        "finalizada_en",
    }


def test_plantilla_omite_nulos():
    asunto, texto, html = renderizar_mensaje(
        "NUEVA",
        {"id": 9, "municipalidad": "LINCE"},
        {"nivel": "DISTRITO", "explicacion": "Coincidencia de distrito."},
        {"nombre": "Lince", "tipo": "DISTRITO"},
    )
    assert "None" not in texto
    assert "null" not in texto.lower()
    assert "podría afectar" in texto
    assert "estimada" in texto.lower() or "fec_estimada" not in texto
    assert "Fecha estimada de restablecimiento" not in texto
    assert "Lince" in texto
    assert asunto


def test_sin_destinatario_no_crea_notificacion(conexion, captura_minima, tmp_path, monkeypatch):
    from src import recolector as rec
    from src import config as cfg

    monkeypatch.setattr(rec, "CARPETA_RAW", tmp_path / "raw")
    rec.CARPETA_RAW.mkdir(parents=True)
    monkeypatch.setattr(cfg, "CARPETA_RAW", tmp_path / "raw")
    ejecutar_pipeline(desde_archivo=captura_minima, procesar_envios=False, forzar_simulacion=True)
    with conectar() as cx:
        with cx.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM notificaciones")
            assert cursor.fetchone()[0] == 0


def test_no_suscrito_no_recibe(conexion, captura_minima, tmp_path, monkeypatch):
    from src import recolector as rec
    from src import config as cfg

    monkeypatch.setattr(rec, "CARPETA_RAW", tmp_path / "raw")
    rec.CARPETA_RAW.mkdir(parents=True)
    monkeypatch.setattr(cfg, "CARPETA_RAW", tmp_path / "raw")
    _suscribir("lince.prueba@example.com", [{"tipo": "DISTRITO", "nombre": "Lince"}])
    ejecutar_pipeline(desde_archivo=captura_minima, procesar_envios=False, forzar_simulacion=True)
    with conectar() as cx:
        with cx.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM notificaciones")
            assert cursor.fetchone()[0] == 0


def test_suscrito_recibe_y_multi_sub_no_duplica(conexion, captura_minima, tmp_path, monkeypatch):
    from src import recolector as rec
    from src import config as cfg

    monkeypatch.setattr(rec, "CARPETA_RAW", tmp_path / "raw")
    rec.CARPETA_RAW.mkdir(parents=True)
    monkeypatch.setattr(cfg, "CARPETA_RAW", tmp_path / "raw")
    _suscribir(
        "santa.prueba@example.com",
        [
            {"tipo": "DISTRITO", "nombre": "Santa Anita"},
            {"tipo": "AREA", "nombre": "Urb. Santa Aurelia", "distrito_padre": "Santa Anita"},
        ],
    )
    primero = ejecutar_pipeline(
        desde_archivo=captura_minima, procesar_envios=False, forzar_simulacion=True
    )
    assert primero["coincidencias"]["notificaciones_creadas"] >= 1
    with conectar() as cx:
        with cx.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM notificaciones n
                JOIN usuarios u ON u.id = n.usuario_id
                WHERE u.correo = 'santa.prueba@example.com'
                """
            )
            n1 = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT interrupcion_id, tipo_evento, version_relevante, COUNT(*)
                FROM notificaciones
                GROUP BY 1, 2, 3
                HAVING COUNT(*) > 1
                """
            )
            assert cursor.fetchall() == []
    segundo = ejecutar_pipeline(
        desde_archivo=captura_minima, procesar_envios=False, forzar_simulacion=True
    )
    assert segundo["coincidencias"]["notificaciones_creadas"] == 0
    with conectar() as cx:
        with cx.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM notificaciones")
            assert cursor.fetchone()[0] == n1


def test_interno_consulta_notificaciones(conexion, captura_minima, tmp_path, monkeypatch):
    from src import recolector as rec
    from src import config as cfg
    from src.web import interno as interno_mod
    from fastapi.testclient import TestClient

    monkeypatch.setattr(rec, "CARPETA_RAW", tmp_path / "raw")
    rec.CARPETA_RAW.mkdir(parents=True)
    monkeypatch.setattr(cfg, "CARPETA_RAW", tmp_path / "raw")
    monkeypatch.setattr(cfg, "INTERNAL_API_TOKEN", "token-interno-test")
    monkeypatch.setattr(interno_mod.config, "INTERNAL_API_TOKEN", "token-interno-test")
    _suscribir("api.prueba@example.com", [{"tipo": "DISTRITO", "nombre": "Independencia"}])
    ejecutar_pipeline(desde_archivo=captura_minima, procesar_envios=False, forzar_simulacion=True)
    cliente = TestClient(app)
    assert cliente.get("/internal/v1/notificaciones").status_code == 401
    auth = {"Authorization": "Bearer token-interno-test"}
    lista = cliente.get("/internal/v1/notificaciones", headers=auth)
    assert lista.status_code == 200
    cuerpo = lista.json()
    assert cuerpo["ok"] is True
    assert cuerpo["estadisticas"]["total"] >= 1
    nid = cuerpo["notificaciones"][0]["id"]
    detalle = cliente.get(f"/internal/v1/notificaciones/{nid}", headers=auth)
    assert detalle.status_code == 200
    assert detalle.json()["notificacion"]["estado"] == "PENDIENTE"
    dest = cliente.get("/internal/v1/destinatarios", headers=auth)
    assert dest.status_code == 200
    assert dest.json()["ok"] is True
    faltante = cliente.get("/internal/v1/notificaciones/999999", headers=auth)
    assert faltante.status_code == 404
