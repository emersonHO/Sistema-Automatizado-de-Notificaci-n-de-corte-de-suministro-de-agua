from src import correo as c


class _Resp:
    def __init__(self, codigo, payload):
        self.status_code = codigo
        self._payload = payload

    def json(self):
        return self._payload


def test_resend_aceptado(monkeypatch):
    monkeypatch.setattr(c, "CORREO_PROVEEDOR", "resend")
    monkeypatch.setattr(c, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(c, "MODO_ENVIO", "real")
    monkeypatch.setattr(c, "SMTP_FROM", "avisos@example.com")
    monkeypatch.setattr(c, "SMTP_FROM_NAME", "Avisos")

    def fake_post(url, headers, json, timeout):
        assert "Bearer re_test" in headers["Authorization"]
        assert json["to"] == ["ciudadano@example.com"]
        return _Resp(200, {"id": "abc123"})

    monkeypatch.setattr(c.httpx, "post", fake_post)
    assert c.debe_enviar_smtp() is True
    texto = c.enviar("ciudadano@example.com", "Asunto", "Hola", "<p>Hola</p>")
    assert "abc123" in texto
    assert "no se confirma" in texto.lower()


def test_resend_error_no_simula(monkeypatch):
    monkeypatch.setattr(c, "CORREO_PROVEEDOR", "resend")
    monkeypatch.setattr(c, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(c, "MODO_ENVIO", "real")

    def fake_post(*_a, **_k):
        return _Resp(403, {"message": "forbidden"})

    monkeypatch.setattr(c.httpx, "post", fake_post)
    try:
        c.enviar("ciudadano@example.com", "A", "b", "")
        raise AssertionError("debía fallar")
    except RuntimeError as error:
        assert "403" in str(error)
