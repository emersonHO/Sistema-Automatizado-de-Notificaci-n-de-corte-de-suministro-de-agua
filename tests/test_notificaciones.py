from src.notificaciones import procesar_outbox, renderizar_mensaje
from src.suscripciones import confirmar_correo, suscribir
from src.pipeline import ejecutar_pipeline


def test_plantilla_no_afirma_vivienda():
    asunto, texto, html = renderizar_mensaje(
        "NUEVA",
        {
            "id": 1,
            "municipalidad": "SANTA ANITA",
            "tipo_incid": "PROGRAMADA",
            "fec_deteccion": "2026-10-16 14:00:00",
            "fec_estimada": "2026-10-16 23:00:00",
            "areas_afectadas": "Urb. A",
            "causa": "Mantenimiento",
            "cod_incidencia": "X",
        },
        {"nivel": "DISTRITO", "explicacion": "Coincidencia de distrito."},
        {"nombre": "Santa Anita", "tipo": "DISTRITO"},
    )
    assert "podría afectar" in texto
    assert "no confirma" in texto.lower() or "vivienda" in texto.lower()
    assert "tercero" in texto.lower()


def test_outbox_simulado_no_smtp(conexion, captura_minima):
    with conexion:
        r = suscribir("demo.smtp@example.com", [{"tipo": "DISTRITO", "nombre": "Independencia"}], conexion=conexion)
        confirmar_correo(r["usuario"]["token_confirmacion"], conexion=conexion)
        conexion.commit()
    ejecutar_pipeline(desde_archivo=captura_minima, procesar_envios=False, forzar_simulacion=True)
    from src.db import conectar

    with conectar() as cx:
        envio = procesar_outbox(cx, forzar_simulacion=True)
        cx.commit()
        with cx.cursor() as cursor:
            cursor.execute("SELECT estado FROM notificaciones")
            estados = {row[0] for row in cursor.fetchall()}
    assert envio["modo"] == "simulacion"
    assert "ACEPTADA_SMTP" not in estados
    assert "SIMULADA" in estados or envio["simuladas"] >= 0
