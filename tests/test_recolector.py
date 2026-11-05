import json

import pytest
import requests

from src.recolector import (
    RespuestaFuenteError,
    analizar_completitud,
    guardar_respuesta,
    obtener_datos,
    validar_respuesta,
)


def test_validar_respuesta_ok():
    validar_respuesta({"ok": True, "data": []})


def test_validar_respuesta_no_ok():
    with pytest.raises(RespuestaFuenteError):
        validar_respuesta({"ok": False, "data": []})


def test_captura_incompleta():
    meta = analizar_completitud({"ok": True, "total": 10, "data": [{"id": 1}]})
    assert meta["captura_completa"] is False
    assert meta["total_recibido"] == 1


def test_captura_completa():
    meta = analizar_completitud({"ok": True, "total": 1, "data": [{"id": 1}]})
    assert meta["captura_completa"] is True


def test_guardar_respuesta_y_meta(tmp_path, monkeypatch):
    from src import recolector as rec

    monkeypatch.setattr(rec, "CARPETA_RAW", tmp_path)
    datos = {"ok": True, "total": 1, "data": [{"id": 1}]}
    ruta = guardar_respuesta(datos, dias=14)
    assert ruta.exists()
    meta_path = ruta.with_name(ruta.name.removesuffix(".json") + ".meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["total_recibido"] == 1
    assert "fecha_captura_utc" in meta
    assert "tercero" in meta["nota_fuente"].lower() or "SEDAPAL" in meta["nota_fuente"]


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("error")

    def json(self):
        return self._payload


class _Sesion:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        if self.calls < 2:
            raise requests.ConnectionError("caida")
        return _FakeResp(self.payload)


def test_reintentos(monkeypatch):
    monkeypatch.setattr("src.recolector.API_REINTENTOS", 3)
    monkeypatch.setattr("src.recolector.time.sleep", lambda *_: None)
    sesion = _Sesion({"ok": True, "data": []})
    datos = obtener_datos(dias=1, sesion=sesion)
    assert datos["ok"] is True
    assert sesion.calls == 2
