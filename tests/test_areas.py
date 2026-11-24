from src.texto import extraer_sectores, partir_areas, resumen_ubicaciones


def test_partir_areas_punto_y_coma_y_saltos():
    texto = "Urb. La Capullana; A.H. Villa los Heraldos\nP.J. César Vallejo"
    partes = partir_areas(texto)
    assert any("CAPULLANA" in p for p in partes)
    assert any("HERALDOS" in p for p in partes)
    assert any("VALLEJO" in p for p in partes)


def test_sectores_multiples():
    assert extraer_sectores("Sectores 312, 313 y 314") == ["312", "313", "314"]
    assert extraer_sectores("Sector 212") == ["212"]
    assert extraer_sectores("sin dato") == []


def test_resumen_conserva_original():
    r = resumen_ubicaciones("Asoc. Virgen; Cuadrante: Av. Canta", "Sector 60")
    assert r["texto_original"].startswith("Asoc.")
    assert r["sectores"] == ["60"]
    assert r["partes"]
