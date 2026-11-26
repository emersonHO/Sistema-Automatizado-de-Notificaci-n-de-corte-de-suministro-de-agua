"""Restringe rutas administrativas cuando la petición llega por el túnel público."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

PREFIJOS_PUBLICOS = (
    "/",
    "/suscribir",
    "/reenviar",
    "/confirmar",
    "/cuenta",
    "/baja",
    "/privacidad",
    "/interrupciones",
    "/estadisticas",
    "/acceso",
    "/static",
)


def host_es_tunel(host: str) -> bool:
    nombre = (host or "").split(":")[0].lower()
    return nombre.endswith(".trycloudflare.com") or nombre.endswith(".cfargotunnel.com")


def ruta_permitida_en_tunel(path: str) -> bool:
    if path in {"/", ""}:
        return True
    for prefijo in PREFIJOS_PUBLICOS:
        if prefijo != "/" and (path == prefijo or path.startswith(prefijo + "/")):
            return True
    return False


class FiltroTunelPublico(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        host = request.headers.get("host", "")
        if host_es_tunel(host) and not ruta_permitida_en_tunel(request.url.path):
            return PlainTextResponse("No encontrado", status_code=404)
        return await call_next(request)
