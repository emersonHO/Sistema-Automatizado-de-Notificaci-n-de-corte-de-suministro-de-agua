"""Cabeceras de seguridad HTTP."""

from starlette.middleware.base import BaseHTTPMiddleware


class CabecerasSeguridad(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        respuesta = await call_next(request)
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        respuesta.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        respuesta.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net data:"
        )
        return respuesta
