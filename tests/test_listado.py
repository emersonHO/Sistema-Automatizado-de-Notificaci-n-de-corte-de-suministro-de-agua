from fastapi.testclient import TestClient

from src.web.app import app


def test_listado_muestra_total_y_no_se_queda_en_dos_por_defecto(conexion):
    cliente = TestClient(app)
    r = cliente.get("/interrupciones")
    assert r.status_code == 200
    assert "registro" in r.text.lower()
    assert 'name="q"' in r.text
    assert 'name="vigencia"' in r.text
