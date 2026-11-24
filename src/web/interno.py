"""API interna para n8n. Autenticación Bearer; no usa sesión ni CSRF."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src import config
from src.solicitudes import (
    EjecucionActiva,
    IdempotenciaConflicto,
    crear_solicitud,
    listar_solicitudes,
    obtener_ejecucion_de_solicitud,
    obtener_solicitud,
    resumen_para_api,
)
from src.db import conectar
from src.web.consultas import (
    estadisticas_notificaciones,
    intentos_de,
    listar_destinatarios,
    listar_notificaciones,
    obtener_notificacion,
)
from src.web.seguridad import secreto_igual

router = APIRouter(prefix="/internal/v1", tags=["interno"])

_CLAVE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class CuerpoEjecucion(BaseModel):
    origen: str = Field(..., examples=["MANUAL"])
    solo_si_libre: bool = False
    modo: str = "api"
    ruta_fixture: str | None = None


def _json(contenido: dict, codigo: int):
    return JSONResponse(contenido, status_code=codigo)


def exigir_token(authorization: str | None) -> None:
    if not config.INTERNAL_API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail={"ok": False, "codigo": "API_INTERNA_NO_CONFIGURADA"},
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail={"ok": False, "codigo": "NO_AUTORIZADO"},
        )
    presentado = authorization.split(" ", 1)[1].strip()
    if not secreto_igual(presentado, config.INTERNAL_API_TOKEN):
        raise HTTPException(
            status_code=401,
            detail={"ok": False, "codigo": "NO_AUTORIZADO"},
        )


def _serializar(payload: dict) -> dict:
    out = {}
    for clave, valor in payload.items():
        if isinstance(valor, datetime):
            out[clave] = valor.isoformat()
        elif isinstance(valor, dict):
            out[clave] = _serializar(valor)
        else:
            out[clave] = valor
    return out


def _validar_fixture(ruta: str | None) -> Path | None:
    if not ruta:
        raise HTTPException(
            status_code=400,
            detail={"ok": False, "codigo": "FIXTURE_REQUERIDO"},
        )
    if not config.INTERNAL_PERMITIR_FIXTURE:
        raise HTTPException(
            status_code=400,
            detail={"ok": False, "codigo": "FIXTURE_NO_PERMITIDO"},
        )
    base = config.CARPETA_FIXTURES.resolve()
    candidata = (base / Path(ruta).name).resolve()
    if base not in candidata.parents and candidata != base:
        raise HTTPException(
            status_code=400,
            detail={"ok": False, "codigo": "FIXTURE_RUTA_INVALIDA"},
        )
    if not candidata.is_file():
        raise HTTPException(
            status_code=400,
            detail={"ok": False, "codigo": "FIXTURE_NO_ENCONTRADO"},
        )
    return candidata


@router.post("/pipeline/ejecuciones")
def encolar(
    cuerpo: CuerpoEjecucion,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    exigir_token(authorization)
    if idempotency_key and not _CLAVE.match(idempotency_key):
        return _json({"ok": False, "codigo": "IDEMPOTENCY_KEY_INVALIDA"}, 400)
    ruta = None
    if cuerpo.modo.strip().lower() == "fixture":
        ruta = str(_validar_fixture(cuerpo.ruta_fixture))
    try:
        fila, creada = crear_solicitud(
            origen=cuerpo.origen,
            solo_si_libre=cuerpo.solo_si_libre,
            modo=cuerpo.modo,
            ruta_fixture=ruta,
            idempotency_key=idempotency_key,
        )
    except ValueError as error:
        return _json({"ok": False, "codigo": "SOLICITUD_INVALIDA", "mensaje": str(error)}, 400)
    except EjecucionActiva:
        return _json({"ok": False, "codigo": "EJECUCION_ACTIVA"}, 409)
    except IdempotenciaConflicto:
        return _json({"ok": False, "codigo": "IDEMPOTENCIA_CONFLICTO"}, 409)
    resumen = resumen_para_api(fila)
    resumen["mensaje"] = "Solicitud registrada" if creada else "Solicitud existente (idempotencia)"
    return _json(_serializar(resumen), 202 if creada else 200)


@router.get("/pipeline/ejecuciones/{solicitud_id}")
def consultar(solicitud_id: int, authorization: str | None = Header(default=None)):
    exigir_token(authorization)
    fila = obtener_solicitud(solicitud_id)
    if not fila:
        return _json({"ok": False, "codigo": "NO_ENCONTRADA"}, 404)
    ejecucion = obtener_ejecucion_de_solicitud(solicitud_id)
    return _serializar(resumen_para_api(fila, ejecucion))


@router.get("/pipeline/ejecuciones")
def listar(
    authorization: str | None = Header(default=None),
    limite: int = Query(default=20, ge=1, le=100),
    estado: str | None = None,
):
    exigir_token(authorization)
    filas = listar_solicitudes(limite=limite, estado=estado)
    return {
        "ok": True,
        "solicitudes": [_serializar(resumen_para_api(f)) for f in filas],
    }


@router.get("/notificaciones")
def listar_notif(
    authorization: str | None = Header(default=None),
    limite: int = Query(default=50, ge=1, le=200),
    estado: str | None = None,
):
    exigir_token(authorization)
    with conectar() as conexion:
        filas = listar_notificaciones(conexion, limite=limite, estado=estado)
        resumen = estadisticas_notificaciones(conexion)
    return {
        "ok": True,
        "estadisticas": resumen,
        "notificaciones": [_serializar(dict(f)) for f in filas],
    }


@router.get("/notificaciones/{notificacion_id}")
def detalle_notif(notificacion_id: int, authorization: str | None = Header(default=None)):
    exigir_token(authorization)
    with conectar() as conexion:
        fila = obtener_notificacion(conexion, notificacion_id)
        if not fila:
            return _json({"ok": False, "codigo": "NO_ENCONTRADA"}, 404)
        intentos = [dict(i) for i in intentos_de(conexion, notificacion_id)]
    return {
        "ok": True,
        "notificacion": _serializar(fila),
        "intentos": [_serializar(i) for i in intentos],
    }


@router.get("/destinatarios")
def destinatarios(
    authorization: str | None = Header(default=None),
    limite: int = Query(default=100, ge=1, le=200),
):
    exigir_token(authorization)
    with conectar() as conexion:
        filas = listar_destinatarios(conexion, limite=limite)
    return {
        "ok": True,
        "destinatarios": [_serializar(dict(f)) for f in filas],
    }


@router.get("/observabilidad")
def observabilidad_api(authorization: str | None = Header(default=None)):
    exigir_token(authorization)
    from src.observabilidad import snapshot

    with conectar() as conexion:
        data = snapshot(conexion)
    return {"ok": True, **_serializar(data)}


@router.post("/resumenes")
def resumenes_api(authorization: str | None = Header(default=None)):
    exigir_token(authorization)
    from src.resumenes import generar_resumenes

    with conectar() as conexion:
        data = generar_resumenes(conexion)
        conexion.commit()
    return {"ok": True, **data}


@router.post("/alertas-admin")
def alertas_admin(authorization: str | None = Header(default=None)):
    exigir_token(authorization)
    from src.config import ADMIN_ALERT_EMAIL
    from src.ciudadano import _enviar_transaccional
    from src.observabilidad import snapshot
    from src.plantillas_correo import alerta_admin

    if not ADMIN_ALERT_EMAIL:
        return {"ok": True, "enviada": False, "motivo": "ADMIN_ALERT_EMAIL vacío"}
    with conectar() as conexion:
        data = snapshot(conexion)
    pipe = data.get("pipeline") or {}
    sol = data.get("solicitudes") or {}
    if int(pipe.get("fallidas") or 0) == 0 and int(sol.get("error") or 0) == 0:
        return {"ok": True, "enviada": False, "motivo": "sin fallos recientes"}
    cuerpo = (
        f"Ejecuciones en ERROR: {pipe.get('fallidas')}\n"
        f"Solicitudes en ERROR: {sol.get('error')}\n"
        f"Notificaciones pendientes: {(data.get('notificaciones') or {}).get('pendientes')}\n"
    )
    asunto, texto, html = alerta_admin("Alerta operativa — avisos de agua", cuerpo)
    _enviar_transaccional(ADMIN_ALERT_EMAIL, asunto, texto, html)
    return {"ok": True, "enviada": True}
