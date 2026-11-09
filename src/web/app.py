"""Panel web del MVP (FastAPI + Jinja2)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src.config import BASE_URL, SESSION_SECRET
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
from src.web.consultas import (
    detalle_interrupcion,
    intentos_de,
    listar_ejecuciones,
    listar_interrupciones,
    listar_notificaciones,
    resumen_panel,
)
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

app = FastAPI(title="Sistema de notificación de interrupciones de agua")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,
)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def _startup():
    configurar_logging()
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
        "base_url": BASE_URL,
        "aviso_fuente": (
            "La información procede de una fuente pública de un tercero "
            "y no reemplaza los canales oficiales."
        ),
        "es_admin": sesion_admin(request),
        "auth_activa": admin_requerido(),
        "csrf": csrf_token(request),
        "flash": flash,
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
    try:
        with conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT 1")
        return {"ok": True, "postgres": True}
    except Exception as error:
        return JSONResponse(
            {"ok": False, "postgres": False, "error": str(error)},
            status_code=503,
        )


@app.get("/admin/login", response_class=HTMLResponse)
def login_get(request: Request, siguiente: str = "/"):
    if sesion_admin(request) and admin_requerido():
        return RedirectResponse(siguiente or "/", status_code=303)
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
    siguiente: str = Form("/"),
):
    validar_csrf(request, csrf)
    if not autenticar(usuario, password):
        return templates.TemplateResponse(
            "login.html",
            _ctx(request, siguiente=siguiente, error="Credenciales incorrectas."),
            status_code=401,
        )
    request.session["admin"] = True
    destino = siguiente if siguiente.startswith("/") else "/"
    return RedirectResponse(destino, status_code=303)


@app.post("/admin/logout")
def logout(request: Request, csrf: str = Form("")):
    validar_csrf(request, csrf)
    request.session.clear()
    return RedirectResponse("/suscripciones", status_code=303)


@app.get("/", response_class=HTMLResponse)
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
):
    with conectar() as conexion:
        filas = listar_interrupciones(conexion, distrito=distrito, tipo=tipo)
    return templates.TemplateResponse(
        "interrupciones.html",
        _ctx(request, filas=filas, distrito=distrito or "", tipo=tipo or "", distritos=DISTRITOS_LIMA),
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
def notificaciones(request: Request):
    bloqueo = _exige_admin(request)
    if bloqueo:
        return bloqueo
    with conectar() as conexion:
        filas = listar_notificaciones(conexion)
    return templates.TemplateResponse("notificaciones.html", _ctx(request, filas=filas))


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
                    f"{BASE_URL}/suscripciones/confirmar/{token}"
                )
    return RedirectResponse("/suscripciones", status_code=303)


@app.get("/suscripciones/confirmar/{token}", response_class=HTMLResponse)
def confirmar(request: Request, token: str):
    with conectar() as conexion:
        usuario = confirmar_correo(token, conexion=conexion)
        conexion.commit()
    if not usuario:
        return templates.TemplateResponse(
            "mensaje.html",
            _ctx(request, titulo="Token inválido", mensaje="El enlace no es válido o ya fue utilizado."),
            status_code=400,
        )
    return templates.TemplateResponse(
        "mensaje.html",
        _ctx(
            request,
            titulo="Correo confirmado",
            mensaje=(
                f"La cuenta {enmascarar_correo(usuario['correo'])} quedó confirmada. "
                "Los envíos reales siguen desactivados hasta habilitar SMTP."
            ),
        ),
    )


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
    except Exception as error:
        ejec = {"error": str(error)}
    return templates.TemplateResponse(
        "metricas.html",
        _ctx(
            request,
            correspondencia={k: v for k, v in corr.items() if k != "detalle"},
            cambios={k: v for k, v in camb.items() if k != "detalle"},
            ejecuciones=ejec,
        ),
    )
