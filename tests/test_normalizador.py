import json

from src.calidad import evaluar_calidad
from src.normalizador import normalizar
from src.caracteristicas import crear_caracteristicas


def test_normalizar_y_caracteristicas(captura_minima):
    datos = json.loads(captura_minima.read_text(encoding="utf-8"))
    df = crear_caracteristicas(normalizar(datos))
    assert len(df) == 2
    assert df["id"].is_unique
    assert df["cantidad_areas_reportadas"].iloc[0] == 2
    assert bool(df["ambito_lima"].iloc[0]) is True
    informe = evaluar_calidad(df, {"captura_completa": True, "total_recibido": 2, "total_reportado": 2})
    assert informe["valido"]
    assert informe["identificadores_duplicados"] == 0
    assert informe["identificadores_vacios"] == 0


def test_callao_no_es_ambito_lima():
    datos = {
        "ok": True,
        "data": [
            {
                "id": 9,
                "cod_incidencia": "X",
                "municipalidad": "VENTANILLA",
                "areas_afectadas": "Zona A",
                "fec_deteccion": "2026-01-01 00:00:00",
                "fec_estimada": "2026-01-01 03:00:00",
            }
        ],
    }
    df = normalizar(datos)
    assert bool(df["ambito_lima"].iloc[0]) is False
