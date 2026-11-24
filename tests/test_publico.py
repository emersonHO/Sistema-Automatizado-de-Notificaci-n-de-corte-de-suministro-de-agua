from fastapi.testclient import TestClient

from src.ciudadano import confirmar_publico, registrar_publico
from src.tokens import firmar
from src.web.app import app


def _csrf(cliente):
    pagina = cliente.get("/")
    inicio = pagina.text.find('name="csrf"')
    fragmento = pagina.text[inicio : inicio + 80]
    return fragmento.split('value="')[1].split('"')[0]


def test_inicio_publico_sin_admin(conexion):
    cliente = TestClient(app)
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Resumen operativo" not in r.text
    assert "SEDAPAL" in r.text
    assert "no es una API oficial" in r.text.lower() or "no es un canal oficial" in r.text.lower() or "no es una API oficial" in r.text


def test_honeypot_no_crea_usuario(conexion):
    cliente = TestClient(app)
    csrf = _csrf(cliente)
    r = cliente.post(
        "/suscribir",
        data={
            "csrf": csrf,
            "correo": "honeypot@example.com",
            "distrito": "1",
            "consentimiento": "on",
            "website": "http://spam.example",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    from src.db import conectar

    with conectar() as cx:
        with cx.cursor() as c:
            c.execute("SELECT COUNT(*) FROM usuarios WHERE correo = %s", ("honeypot@example.com",))
            assert c.fetchone()[0] == 0


def test_ciclo_confirmacion_gestion_baja(conexion):
    from src.db import conectar
    from src.suscripciones import listar_zonas_lima

    with conectar() as cx:
        zonas = [z for z in listar_zonas_lima(cx) if z["tipo"] == "DISTRITO"]
        assert zonas
        zona_id = zonas[0]["id"]
        r = registrar_publico(
            "ciudadano.demo@example.com",
            [{"zona_id": zona_id}],
            consentimiento=True,
            conexion=cx,
        )
        cx.commit()
        assert r["token"]
        usuario = confirmar_publico(r["token"], cx)
        cx.commit()
        assert usuario
        assert usuario["correo"] == "ciudadano.demo@example.com"
        token_g = firmar("gest", usuario["id"], horas=2)
        token_b = firmar("baja", usuario["id"], horas=2)

    cliente = TestClient(app)
    g = cliente.get(f"/cuenta/{token_g}")
    assert g.status_code == 200
    assert "Preferencias" in g.text or "preferencias" in g.text.lower()
    b = cliente.get(f"/baja/{token_b}")
    assert b.status_code == 200
    csrf = b.text[b.text.find('name="csrf"') :]
    token_csrf = csrf.split('value="')[1].split('"')[0]
    r2 = cliente.post(
        f"/baja/{token_b}",
        data={"csrf": token_csrf, "confirmar": "on"},
        follow_redirects=True,
    )
    assert r2.status_code == 200
    assert "cancelada" in r2.text.lower()
