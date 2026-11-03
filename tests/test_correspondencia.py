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


def test_distrito_es_potencial_no_confirmado():
    from src.casos_evaluacion import INCIDENCIA_SANTA_ANITA, ZONA_SANTA_ANITA

    r = evaluar_par(INCIDENCIA_SANTA_ANITA, ZONA_SANTA_ANITA)
    assert r["estado"] == "POTENCIAL"
    assert coincidencia_notificable(r)
    assert "no confirma" in r["explicacion"].lower() or "viviendas" in r["explicacion"].lower()
