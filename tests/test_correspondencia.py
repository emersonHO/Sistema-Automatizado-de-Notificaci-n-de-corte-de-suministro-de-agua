from src.casos_evaluacion import CASOS_CORRESPONDENCIA
from src.correspondencia import coincidencia_notificable, evaluar_par
from src.evaluacion import evaluar_correspondencia_etiquetada
from src.texto import normalizar_texto


def test_tildes_y_espacios():
    assert normalizar_texto("  Santa  Ánita ") == "SANTA ANITA"


def test_casos_etiquetados():
    metricas = evaluar_correspondencia_etiquetada(CASOS_CORRESPONDENCIA)
    assert metricas["fp"] == 0
    assert metricas["fn"] == 0
    assert metricas["precision"] == 1
    assert metricas["recall"] == 1


def test_area_parcial_no_es_todo_el_distrito():
    incidencia = {
        "id": 9,
        "municipalidad": "ATE",
        "areas_afectadas": "A.H. El Amauta zona A; Sectores 163, 164, 176",
        "infor_web": "Sectores 163, 164, 176",
    }
    zona_area = {
        "id": 1,
        "tipo": "AREA",
        "nombre": "El Amauta",
        "nombre_normalizado": "ATE EL AMAUTA",
        "distrito_padre": "ATE",
        "ambito_lima": True,
    }
    zona_otro = {
        "id": 2,
        "tipo": "AREA",
        "nombre": "Otra urbanización",
        "nombre_normalizado": "ATE OTRA URBANIZACION",
        "distrito_padre": "ATE",
        "ambito_lima": True,
    }
    zona_distrito = {
        "id": 3,
        "tipo": "DISTRITO",
        "nombre": "Ate",
        "nombre_normalizado": "ATE",
        "distrito_padre": "ATE",
        "ambito_lima": True,
    }
    r = evaluar_par(incidencia, zona_area)
    assert r and r["estado"] == "ESPECIFICA"
    assert evaluar_par(incidencia, zona_otro) is None
    d = evaluar_par(incidencia, zona_distrito)
    assert d and d["estado"] == "POTENCIAL"


def test_distrito_es_potencial_no_confirmado():
    from src.casos_evaluacion import INCIDENCIA_SANTA_ANITA, ZONA_SANTA_ANITA

    r = evaluar_par(INCIDENCIA_SANTA_ANITA, ZONA_SANTA_ANITA)
    assert r["estado"] == "POTENCIAL"
    assert coincidencia_notificable(r)
    assert "no confirma" in r["explicacion"].lower() or "viviendas" in r["explicacion"].lower()
