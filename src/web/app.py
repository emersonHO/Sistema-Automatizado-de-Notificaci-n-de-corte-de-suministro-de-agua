"""Panel web del MVP (FastAPI + Jinja2)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config import ADMIN_TOKEN, BASE_URL
from src.db import aplicar_esquema, conectar
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
from src.zonas_lima import DISTRITOS_LIMA

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Sistema de notificación de interrupciones de agua")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def _startup():
    aplicar_esquema()
    conexion = conectar()
    try:
        sembrar_zonas(conexion)
        conexion.commit()
    finally:
        conexion.close()


def _ctx(request: Request, **kwargs):
    datos = {
        "request": request,
        "base_url": BASE_URL,
        "aviso_fuente": (
            "La información procede de una fuente pública de un tercero "
            "y no reemplaza los canales oficiales."
        ),
    }
    datos.update(kwargs)
    return datos


@app.get("/salud")
def salud():
    try:
        with conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT 1")
        return {"ok": True, "postgres": True}
    except Exception as error:
        return {"ok": False, "postgres": False, "error": str(error)}


@app.get("/", response_class=HTMLResponse)
def panel(request: Request):
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
    with conectar() as conexion:
        filas = listar_ejecuciones(conexion)
    return templates.TemplateResponse("ejecuciones.html", _ctx(request, filas=filas))


@app.get("/notificaciones", response_class=HTMLResponse)
def notificaciones(request: Request):
    with conectar() as conexion:
        filas = listar_notificaciones(conexion)
    return templates.TemplateResponse("notificaciones.html", _ctx(request, filas=filas))


@app.get("/notificaciones/{notificacion_id}", response_class=HTMLResponse)
def notificacion_detalle(request: Request, notificacion_id: int):
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
def suscripciones_get(request: Request, correo: str | None = None, mensaje: str | None = None):
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
            mensaje=mensaje,
        ),
    )


@app.post("/suscripciones")
def suscripciones_post(
    request: Request,
    correo: str = Form(...),
    zonas: list[str] = Form(default=[]),
    sector: str = Form(default=""),
    distrito_sector: str = Form(default=""),
    area: str = Form(default=""),
    distrito_area: str = Form(default=""),
):
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
        return RedirectResponse(
            "/suscripciones?mensaje=" + "Selecciona al menos una zona.",
            status_code=303,
        )
    with conectar() as conexion:
        resultado = suscribir(correo, seleccion, conexion=conexion)
        conexion.commit()
        usuario = resultado["usuario"]
        token = usuario.get("token_confirmacion")
        if usuario.get("correo_confirmado"):
            msg = "Suscripción actualizada. El correo ya estaba confirmado."
        else:
            msg = (
                "Registro creado. Confirma el correo antes de activar envíos. "
                f"Enlace de demostración: {BASE_URL}/suscripciones/confirmar/{token}"
            )
    return RedirectResponse(
        f"/suscripciones?correo={correo}&mensaje={msg}",
        status_code=303,
    )


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
def baja(suscripcion_id: int, correo: str = Form(...)):
    with conectar() as conexion:
        ok = dar_baja(suscripcion_id, correo, conexion=conexion)
        conexion.commit()
    msg = "Suscripción dada de baja." if ok else "No se pudo dar de baja (correo no coincidente)."
    return RedirectResponse(f"/suscripciones?correo={correo}&mensaje={msg}", status_code=303)


@app.get("/metricas", response_class=HTMLResponse)
def metricas(request: Request):
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
