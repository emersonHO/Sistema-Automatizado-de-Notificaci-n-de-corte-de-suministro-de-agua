"""Tokens de un solo uso (hash) y tokens firmados para gestión/baja."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from src.config import SESSION_SECRET, TOKEN_HORAS_CONFIRMACION, TOKEN_HORAS_GESTION


def hashear(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def nuevo_token() -> str:
    return secrets.token_urlsafe(32)


def firmar(proposito: str, usuario_id: int, horas: int | None = None) -> str:
    vida = horas if horas is not None else TOKEN_HORAS_GESTION
    exp = int(time.time()) + int(vida) * 3600
    cuerpo = f"{proposito}.{int(usuario_id)}.{exp}"
    firma = hmac.new(SESSION_SECRET.encode("utf-8"), cuerpo.encode("utf-8"), hashlib.sha256).hexdigest()[
        :32
    ]
    return f"{cuerpo}.{firma}"


def verificar(token: str, proposito: str) -> int | None:
    if not token or token.count(".") < 3:
        return None
    proposito_t, uid_t, exp_t, firma = token.rsplit(".", 3)
    if proposito_t != proposito:
        return None
    try:
        uid = int(uid_t)
        exp = int(exp_t)
    except ValueError:
        return None
    if exp < int(time.time()):
        return None
    cuerpo = f"{proposito_t}.{uid}.{exp}"
    esperada = hmac.new(
        SESSION_SECRET.encode("utf-8"), cuerpo.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:32]
    if not hmac.compare_digest(firma, esperada):
        return None
    return uid


def enlace_confirmacion(base: str, token: str) -> str:
    return f"{base.rstrip('/')}/confirmar/{token}"


def enlace_gestion(base: str, usuario_id: int) -> str:
    return f"{base.rstrip('/')}/cuenta/{firmar('gest', usuario_id)}"


def enlace_baja(base: str, usuario_id: int) -> str:
    return f"{base.rstrip('/')}/baja/{firmar('baja', usuario_id)}"


def horas_confirmacion() -> int:
    return TOKEN_HORAS_CONFIRMACION
