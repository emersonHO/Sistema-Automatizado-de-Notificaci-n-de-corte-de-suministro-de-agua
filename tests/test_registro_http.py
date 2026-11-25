from fastapi.testclient import TestClient

from src.web.app import app


def _csrf(cliente):
    pagina = cliente.get("/")
    inicio = pagina.text.find('name="csrf"')
    fragmento = pagina.text[inicio : inicio + 80]
    return fragmento.split('value="')[1].split('"')[0]


def _zona_id(cliente):
    pagina = cliente.get("/")
    marca = 'name="distrito"'
    i = pagina.text.find(marca)
    bloque = pagina.text[i : i + 800]
    for linea in bloque.split("<option"):
        if 'value="' in linea and 'value=""' not in linea:
            return linea.split('value="')[1].split('"')[0]
    raise AssertionError("No hay distritos en el formulario")


def test_formulario_persiste_usuario_y_distrito(conexion):
    cliente = TestClient(app)
    csrf = _csrf(cliente)
    zona = _zona_id(cliente)
    correo = "registro.http@example.com"
    r = cliente.post(
        "/suscribir",
        data={
            "csrf": csrf,
            "correo": correo,
            "distrito": zona,
            "todo_distrito": "on",
            "consentimiento": "on",
            "alerta_nueva": "on",
            "alerta_modificada": "on",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    from src.db import conectar

    with conectar() as cx:
        with cx.cursor() as c:
            c.execute("SELECT id, correo FROM usuarios WHERE correo = %s", (correo,))
            usuario = c.fetchone()
            assert usuario is not None
            c.execute(
                "SELECT COUNT(*) FROM suscripciones WHERE usuario_id = %s AND zona_id = %s AND activa",
                (usuario[0], int(zona)),
            )
            assert c.fetchone()[0] == 1


def test_registro_no_se_borra_si_falla_el_correo(conexion, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("transporte caído")

    monkeypatch.setattr("src.ciudadano._enviar_transaccional", boom)
    cliente = TestClient(app)
    csrf = _csrf(cliente)
    zona = _zona_id(cliente)
    correo = "sobrevive.correo@example.com"
    r = cliente.post(
        "/suscribir",
        data={
            "csrf": csrf,
            "correo": correo,
            "distrito": zona,
            "todo_distrito": "on",
            "consentimiento": "on",
            "alerta_nueva": "on",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    from src.db import conectar

    with conectar() as cx:
        with cx.cursor() as c:
            c.execute("SELECT COUNT(*) FROM usuarios WHERE correo = %s", (correo,))
            assert c.fetchone()[0] == 1


def test_checkbox_desmarcado_no_queda_en_on(conexion):
    cliente = TestClient(app)
    csrf = _csrf(cliente)
    zona = _zona_id(cliente)
    correo = "prefs.off@example.com"
    cliente.post(
        "/suscribir",
        data={
            "csrf": csrf,
            "correo": correo,
            "distrito": zona,
            "todo_distrito": "on",
            "consentimiento": "on",
        },
        follow_redirects=False,
    )
    from src.db import conectar

    with conectar() as cx:
        with cx.cursor() as c:
            c.execute(
                """
                SELECT s.alerta_nueva, s.alerta_modificada
                FROM suscripciones s
                JOIN usuarios u ON u.id = s.usuario_id
                WHERE u.correo = %s
                """,
                (correo,),
            )
            fila = c.fetchone()
            assert fila == (False, False)
