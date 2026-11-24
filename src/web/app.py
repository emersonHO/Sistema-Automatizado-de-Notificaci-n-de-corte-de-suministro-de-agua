"""Panel web del MVP (FastAPI + Jinja2)."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from src.config import (
    EN_RENDER,
    PROTEGER_METRICS,
    SESSION_HTTPS,
    SESSION_SECRET,
    TRUST_PROXY,
)
from src.db import aplicar_esquema, conectar
from src.logging_config import configurar_logging
from src.privacidad import enmascarar_correo
from src.suscripciones import (
    confirmar_correo,
    dar_baja,
    listar_zonas_lima,
    sembrar_zonas,
    suscripciones_de_correo,
    suscribir,
)
from src.metricas_prom import exposicion, normalizar_handler, observar_http, registrar as registrar_metricas
from src.solicitudes import listar_solicitudes
from src.correo import advertencia_smtp_publico
from src.url_publica import url_base
from src.web.consultas import (
    detalle_interrupcion,
    intentos_de,
    listar_auditoria,
    listar_destinatarios,
    listar_ejecuciones,
    listar_interrupciones,
    listar_notificaciones,
    resumen_panel,
)
from src.web.cabeceras import CabecerasSeguridad
from src.web.exposicion import FiltroTunelPublico
from src.web.interno import router as router_interno
from src.web.publico import router as router_publico
from src.web.seguridad import (
    admin_requerido,
    autenticar,
    csrf_token,
    sesion_admin,
    validar_csrf,
)
from src.zonas_lima import DISTRITOS_LIMA

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

class _HttpMetricas(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        inicio = time.perf_counter()
        respuesta = await call_next(request)
        handler = normalizar_handler(request.url.path)
        observar_http(
            handler,
            request.method,
            getattr(respuesta, "status_code", 500),
            time.perf_counter() - inicio,
        )
        return respuesta


app = FastAPI(title="Avisos de interrupciones de agua")
app.add_middleware(CabecerasSeguridad)
app.add_middleware(_HttpMetricas)
app.add_middleware(FiltroTunelPublico)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=SESSION_HTTPS,
)
if TRUST_PROXY:
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
app.include_router(router_publico)
app.include_router(router_interno)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def _startup():
    configurar_logging()
    registrar_metricas()
    aplicar_esquema()
    conexion = conectar()
    try:
        sembrar_zonas(conexion)
        conexion.commit()
    finally:
        conexion.close()


def _ctx(request: Request, **kwargs):
    flash = request.session.pop("flash", None)
    datos = {
        "request": request,
        "base_url": url_base(),
        "aviso_smtp": advertencia_smtp_publico(),
        "aviso_fuente": (
            "La información procede de una fuente pública de un tercero "
            "y no reemplaza los canales oficiales."
        ),
        "es_admin": sesion_admin(request),
        "auth_activa": admin_requerido(),
        "csrf": csrf_token(request),
        "flash": flash,
        "nav_actual": request.url.path,
    }
    datos.update(kwargs)
    return datos


def _exige_admin(request: Request):
    if sesion_admin(request):
        return None
    siguiente = request.url.path
    return RedirectResponse("/admin/login?siguiente=" + siguiente, status_code=303)


@app.get("/salud")
def salud():
    """Liveness: el proceso responde. No consulta PostgreSQL (evita reinicios por un blip de BD)."""
    return {
        "ok": True,
        "vivo": True,
        "rol": "liveness",
        "zona_timestamps": "UTC",
    }


@app.get("/metrics")
def metrics(request: Request):
    if PROTEGER_METRICS:
        from src.web.interno import exigir_token

        exigir_token(request.headers.get("authorization"))
    cuerpo, tipo = exposicion()
    return Response(content=cuerpo, media_type=tipo)


@app.get("/salud/listo")
def salud_listo():
    """Readiness: puede atender si PostgreSQL responde. Sin efectos secundarios de negocio."""
    from src.observabilidad import memoria_proceso_kb, postgres_ok

    try:
        listo = postgres_ok()
    except Exception as error:
        return JSONResponse(
            {
                "ok": False,
                "listo": False,
                "postgres": False,
                "rol": "readiness",
                "error": "dependencia_postgres",
                "detalle": str(error)[:200],
            },
            status_code=503,
        )
    cuerpo = {
        "ok": listo,
        "listo": listo,
        "postgres": listo,
        "rol": "readiness",
        "zona_timestamps": "UTC",
        "rss_kb": memoria_proceso_kb(),
    }
    if not listo:
        return JSONResponse(cuerpo, status_code=503)
    return cuerpo


@app.get("/admin/login", response_class=HTMLResponse)
def login_get(request: Request, siguiente: str = "/admin"):
    if sesion_admin(request) and admin_requerido():
        return RedirectResponse(siguiente or "/admin", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        _ctx(request, siguiente=siguiente or "/"),
    )


@app.post("/admin/login")
def login_post(
    request: Request,
    usuario: str = Form(...),
    password: str = Form(...),
    csrf: str = Form(""),
    siguiente: str = Form("/admin"),
):
    validar_csrf(request, csrf)
    if not autenticar(usuario, password):
        return templates.TemplateResponse(
            "login.html",
            _ctx(request, siguiente=siguiente, error="Credenciales incorrectas."),
            status_code=401,
        )
    request.session["admin"] = True
    destino = siguiente if siguiente.startswith("/") else "/admin"
    if destino == "/":
        destino = "/admin"
    return RedirectResponse(destino, status_code=303)


@app.post("/admin/logout")
def logout(request: Request, csrf: str = Form("")):
    validar_csrf(request, csrf)
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def panel(request: Request):
    bloqueo = _exige_admin(request)
    if bloqueo:
        return bloqueo
    with conectar() as conexion:
        resumen = resumen_panel(conexion)
    return templates.TemplateResponse("panel.html", _ctx(request, **resumen))


@app.get("/interrupciones", response_class=HTMLResponse)
def interrupciones(
    request: Request,
    distrito: str | None = None,
    tipo: str | None = None,
    q: str | None = None,
    sector: str | None = None,
    vigencia: str | None = None,
    pagina: int = 1,
):
    with conectar() as conexion:
        listado = listar_interrupciones(
            conexion,
            distrito=distrito,
            tipo=tipo,
            q=q,
            sector=sector,
            vigencia=vigencia,
            pagina=pagina,
        )
    return templates.TemplateResponse(
        "interrupciones.html",
        _ctx(
            request,
            filas=listado["filas"],
            total=listado["total"],
            pagina=listado["pagina"],
            paginas=listado["paginas"],
            distrito=distrito or "",
            tipo=tipo or "",
            q=q or "",
            sector=sector or "",
            vigencia=vigencia or "",
            distritos=DISTRITOS_LIMA,
        ),
    )


@app.get("/interrupciones/{interrupcion_id}", response_class=HTMLResponse)
def interrupcion_detalle(request: Request, interrupcion_id: int):
    with conectar() as conexion:
        fila, historial = detalle_interrupcion(conexion, interrupcion_id)
    if not fila:
        return templates.TemplateResponse(
            "mensaje.html",
            _ctx(request, titulo="No encontrada", mensaje="No existe esa incidencia."),
            status_code=404,
        )
    return templates.TemplateResponse(
        "interrupcion_detalle.html",
        _ctx(request, fila=fila, historial=historial),
    )


@app.get("/ejecuciones", response_class=HTMLResponse)
def ejecuciones(request: Request):
    bloqueo = _exige_admin(request)
    if bloqueo:
        return bloqueo
    with conectar() as conexion:
        filas = listar_ejecuciones(conexion)
    return templates.TemplateResponse("ejecuciones.html", _ctx(request, filas=filas))


@app.get("/notificaciones", response_class=HTMLResponse)
def notificaciones(request: Request, estado: str | None = None):
    bloqueo = _exige_admin(request)
    if bloqueo:
        return bloqueo
    with conectar() as conexion:
        filas = listar_notificaciones(conexion, estado=estado or None)
    return templates.TemplateResponse(
        "notificaciones.html",
        _ctx(request, filas=filas, estado=estado or ""),
    )


@app.get("/notificaciones/{notificacion_id}", response_class=HTMLResponse)
def notificacion_detalle(request: Request, notificacion_id: int):
    bloqueo = _exige_admin(request)
    if bloqueo:
        return bloqueo
    with conectar() as conexion:
        filas = [f for f in listar_notificaciones(conexion, limite=1000) if f["id"] == notificacion_id]
        intentos = intentos_de(conexion, notificacion_id)
    if not filas:
        return templates.TemplateResponse(
            "mensaje.html",
            _ctx(request, titulo="No encontrada", mensaje="No existe esa notificación."),
            status_code=404,
        )
    return templates.TemplateResponse(
        "notificacion_detalle.html",
        _ctx(request, fila=filas[0], intentos=intentos),
    )


@app.get("/suscripciones", response_class=HTMLResponse)
def suscripciones_get(request: Request, correo: str | None = None):
    enlace = request.session.pop("enlace_confirmacion", None)
    with conectar() as conexion:
        zonas = listar_zonas_lima(conexion)
        propias = suscripciones_de_correo(correo, conexion) if correo else []
    return templates.TemplateResponse(
        "suscripciones.html",
        _ctx(
            request,
            zonas=zonas,
            propias=propias,
            correo=correo or "",
            correo_enmascarado=enmascarar_correo(correo) if correo else "",
            enlace_confirmacion=enlace,
        ),
    )


@app.post("/suscripciones")
def suscripciones_post(
    request: Request,
    correo: str = Form(...),
    csrf: str = Form(""),
    zonas: list[str] = Form(default=[]),
    sector: str = Form(default=""),
    distrito_sector: str = Form(default=""),
    area: str = Form(default=""),
    distrito_area: str = Form(default=""),
):
    validar_csrf(request, csrf)
    seleccion = [{"zona_id": int(z)} for z in zonas if str(z).isdigit()]
    if sector.strip():
        seleccion.append(
            {"tipo": "SECTOR", "nombre": sector.strip(), "distrito_padre": distrito_sector or None}
        )
    if area.strip():
        seleccion.append(
            {"tipo": "AREA", "nombre": area.strip(), "distrito_padre": distrito_area or None}
        )
    if not seleccion:
        request.session["flash"] = "Selecciona al menos una zona."
        return RedirectResponse("/suscripciones", status_code=303)
    with conectar() as conexion:
        resultado = suscribir(correo, seleccion, conexion=conexion)
        conexion.commit()
        usuario = resultado["usuario"]
        token = usuario.get("token_confirmacion")
        if usuario.get("correo_confirmado"):
            request.session["flash"] = "Suscripción actualizada. El correo ya estaba confirmado."
        else:
            request.session["flash"] = (
                "Registro creado. Confirma el correo antes de activar envíos."
            )
            if token:
                request.session["enlace_confirmacion"] = (
                    f"{url_base()}/confirmar/{token}"
                )
    return RedirectResponse("/suscripciones", status_code=303)


@app.get("/suscripciones/confirmar/{token}", response_class=HTMLResponse)
def confirmar_legado(request: Request, token: str):
    return RedirectResponse("/confirmar/" + token, status_code=303)


@app.post("/suscripciones/{suscripcion_id}/baja")
def baja(suscripcion_id: int, request: Request, correo: str = Form(...), csrf: str = Form("")):
    validar_csrf(request, csrf)
    with conectar() as conexion:
        ok = dar_baja(suscripcion_id, correo, conexion=conexion)
        conexion.commit()
    request.session["flash"] = (
        "Suscripción dada de baja." if ok else "No se pudo dar de baja (correo no coincidente)."
    )
    return RedirectResponse("/suscripciones", status_code=303)


@app.get("/solicitudes", response_class=HTMLResponse)
def solicitudes_admin(request: Request, estado: str | None = None):
    bloqueo = _exige_admin(request)
    if bloqueo:
        return bloqueo
    with conectar() as conexion:
        filas = listar_solicitudes(limite=100, estado=estado or None, conexion=conexion)
    return templates.TemplateResponse(
        "solicitudes.html",
        _ctx(request, filas=filas, estado=estado or ""),
    )


@app.get("/destinatarios", response_class=HTMLResponse)
def destinatarios_admin(request: Request):
    bloqueo = _exige_admin(request)
    if bloqueo:
        return bloqueo
    with conectar() as conexion:
        filas = listar_destinatarios(conexion)
    return templates.TemplateResponse("destinatarios.html", _ctx(request, filas=filas))


@app.get("/auditoria", response_class=HTMLResponse)
def auditoria(request: Request):
    bloqueo = _exige_admin(request)
    if bloqueo:
        return bloqueo
    with conectar() as conexion:
        filas = listar_auditoria(conexion)
    return templates.TemplateResponse("auditoria.html", _ctx(request, filas=filas))


@app.get("/estado", response_class=HTMLResponse)
def estado_servicios(request: Request):
    bloqueo = _exige_admin(request)
    if bloqueo:
        return bloqueo
    from src.observabilidad import postgres_ok
    from src.web.consultas import sondear_url

    servicios = {
        "web_liveness": sondear_url("http://127.0.0.1:8000/salud"),
        "web_readiness": sondear_url("http://127.0.0.1:8000/salud/listo"),
        "postgres": {"ok": postgres_ok(), "detalle": "consulta SELECT 1"},
    }
    if EN_RENDER:
        servicios["n8n"] = {"ok": None, "detalle": "No forma parte del Web Service de Render; se conserva para laboratorio local."}
        servicios["prometheus"] = {"ok": None, "detalle": "Solo Compose local."}
        servicios["grafana"] = {"ok": None, "detalle": "Solo Compose local."}
        servicios["mailpit"] = {"ok": None, "detalle": "Solo laboratorio local."}
    else:
        servicios.update(
            {
                "n8n": sondear_url("http://n8n:5678/healthz"),
                "prometheus": sondear_url("http://prometheus:9090/-/healthy"),
                "grafana": sondear_url("http://grafana:3000/api/health"),
                "mailpit": sondear_url("http://mailpit:8025/api/v1/info"),
            }
        )
    return templates.TemplateResponse("estado.html", _ctx(request, servicios=servicios))


@app.get("/metricas", response_class=HTMLResponse)
def metricas(request: Request):
    bloqueo = _exige_admin(request)
    if bloqueo:
        return bloqueo
    from src.casos_evaluacion import CASOS_CAMBIOS, CASOS_CORRESPONDENCIA
    from src.evaluacion import evaluar_correspondencia_etiquetada, evaluar_deteccion_cambios, metricas_ejecuciones

    corr = evaluar_correspondencia_etiquetada(CASOS_CORRESPONDENCIA)
    camb = evaluar_deteccion_cambios(CASOS_CAMBIOS)
    try:
        ejec = metricas_ejecuciones()
        obs = ejec.get("observabilidad") or {}
    except Exception as error:
        ejec = {"error": str(error)}
        obs = {}
    return templates.TemplateResponse(
        "metricas.html",
        _ctx(
            request,
            correspondencia={k: v for k, v in corr.items() if k != "detalle"},
            cambios={k: v for k, v in camb.items() if k != "detalle"},
            ejecuciones=ejec,
            obs=obs,
        ),
    )
