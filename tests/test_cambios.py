from src.casos_evaluacion import CASOS_CAMBIOS, INCIDENCIA_SANTA_ANITA
from src.evaluacion import evaluar_deteccion_cambios
from src.hashes import hash_origen, hash_relevante


def test_deteccion_etiquetada():
    resultado = evaluar_deteccion_cambios(CASOS_CAMBIOS)
    assert resultado["aciertos_origen"] == resultado["casos"]
    assert resultado["aciertos_relevante"] == resultado["casos"]
    assert resultado["aciertos_evento"] == resultado["casos"]


def test_imagen_no_es_relevante():
    a = dict(INCIDENCIA_SANTA_ANITA, imagen_url="a.jpg")
    b = dict(INCIDENCIA_SANTA_ANITA, imagen_url="b.jpg")
    assert hash_origen(a) != hash_origen(b)
    assert hash_relevante(a) == hash_relevante(b)


def test_area_es_relevante():
    a = INCIDENCIA_SANTA_ANITA
    b = dict(INCIDENCIA_SANTA_ANITA, areas_afectadas="Otra")
    assert hash_relevante(a) != hash_relevante(b)
