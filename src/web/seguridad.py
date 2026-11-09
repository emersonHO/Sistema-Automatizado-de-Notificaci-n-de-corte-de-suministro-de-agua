"""Sesión administrativa y CSRF para formularios."""

from __future__ import annotations

import hmac
import secrets

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from src import config


def admin_requerido() -> bool:
    return bool(config.ADMIN_PASSWORD)


def sesion_admin(request: Request) -> bool:
    if not admin_requerido():
        return True
    return request.session.get("admin") is True


def exigir_admin(request: Request) -> None:
    if sesion_admin(request):
        return
    raise HTTPException(
        status_code=303,
        headers={"Location": "/admin/login?siguiente=" + request.url.path},
    )


def _constante(a: str, b: str) -> bool:
    aa, bb = a.encode("utf-8"), b.encode("utf-8")
    if len(aa) != len(bb):
        hmac.compare_digest(aa, aa)
        return False
    return hmac.compare_digest(aa, bb)


def autenticar(usuario: str, password: str) -> bool:
    if not admin_requerido():
        return True
    return _constante(usuario, config.ADMIN_USER) and _constante(password, config.ADMIN_PASSWORD)


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


def validar_csrf(request: Request, token_form: str | None) -> None:
    esperado = request.session.get("csrf")
    if not esperado or not token_form or not hmac.compare_digest(token_form, esperado):
        raise HTTPException(status_code=403, detail="CSRF inválido")


def redirect_login(siguiente: str = "/") -> RedirectResponse:
    return RedirectResponse("/admin/login?siguiente=" + siguiente, status_code=303)
