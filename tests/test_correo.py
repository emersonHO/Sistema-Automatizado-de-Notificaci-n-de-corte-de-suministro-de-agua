from src.correo import debe_enviar_smtp, modo_canal


def test_smtp_apagado_por_defecto(monkeypatch):
    from src import correo as c

    monkeypatch.setattr(c, "SMTP_ENABLED", False)
    monkeypatch.setattr(c, "MODO_ENVIO", "simulacion")
    assert debe_enviar_smtp() is False
    assert modo_canal() == "simulacion"


def test_smtp_opt_in(monkeypatch):
    from src import correo as c

    monkeypatch.setattr(c, "SMTP_ENABLED", True)
    monkeypatch.setattr(c, "MODO_ENVIO", "mailpit")
    assert c.debe_enviar_smtp() is True
    assert c.modo_canal() == "smtp"


def test_enviar_usa_smtp_mock(monkeypatch):
    from src import correo as c

    class Dummy:
        def __init__(self, *a, **k):
            self.sent = None

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def send_message(self, mensaje):
            self.__class__.last = mensaje

        def starttls(self):
            return None

        def login(self, *a):
            return None

    monkeypatch.setattr(c, "smtplib", type("S", (), {"SMTP": Dummy})())
    monkeypatch.setattr(c, "SMTP_STARTTLS", False)
    monkeypatch.setattr(c, "SMTP_USER", "")
    texto = c.enviar("demo@example.com", "Asunto", "Cuerpo", "<p>x</p>", host="mailpit", puerto=1025)
    assert "aceptó" in texto
    assert Dummy.last["To"] == "demo@example.com"
