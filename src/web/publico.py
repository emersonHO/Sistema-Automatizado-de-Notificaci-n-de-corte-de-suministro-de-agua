"""Rutas de la web ciudadana (separadas del panel administrativo)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.config import PUBLIC_REVELAR_ENLACE, TRUST_PROXY
from src.url_publica import url_base
from src.correo import advertencia_smtp_publico
from src.web.consultas import listar_interrupciones
from src.ciudadano import (
    MENSAJE_GENERICO,
    actualizar_prefs,
    avisar_baja,
    cancelar_todo,
    confirmar_publico,
    enviar_correo_alta,
    listar_prefs,
    reenviar_confirmacion,
    registrar_publico,
    usuario_por_token_baja,
    usuario_por_token_gestion,
)
from src.db import conectar
from src.limitacion import permitir
from src.privacidad import enmascarar_correo
from src.suscripciones import listar_zonas_lima
from src.web.seguridad import csrf_token, sesion_admin, validar_csrf

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def _ip(request: Request) -> str:
    if TRUST_PROXY:
        reenviada = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if reenviada:
            return reenviada[:64]
    return (request.client.host if request.client else "0.0.0.0")[:64]


def _ctx(request: Request, **kwargs):
    datos = {
        "request": request,
        "base_url": url_base(),
        "csrf": csrf_token(request),
        "es_admin": sesion_admin(request),
        "flash": request.session.pop("flash", None),
        "aviso_smtp": advertencia_smtp_publico(),
        "aviso_fuente": (
            "La información procede de una fuente pública de un tercero "
            "y no reemplaza los canales oficiales."
        ),
    }
    datos.update(kwargs)
    return datos


@router.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    with conectar() as conexion:
        zonas = [z for z in listar_zonas_lima(conexion) if z["tipo"] == "DISTRITO"]
        listado = listar_interrupciones(conexion, limite=8)
    return templates.TemplateResponse(
        "publico/inicio.html",
        _ctx(
            request,
            zonas=zonas,
            recientes=listado["filas"],
            total_cortes=listado["total"],
        ),
    )


@router.get("/privacidad", response_class=HTMLResponse)
def privacidad(request: Request):
    return templates.TemplateResponse("publico/privacidad.html", _ctx(request))


@router.post("/suscribir")
def suscribir_post(
    request: Request,
    correo: str = Form(...),
    csrf: str = Form(""),
    distrito: str = Form(...),
    consentimiento: str = Form(default=""),
    alerta_nueva: str = Form(default=""),
    alerta_modificada: str = Form(default=""),
    alerta_cancelacion: str = Form(default=""),
    resumen_diario: str = Form(default=""),
    website: str = Form(default=""),
):
    validar_csrf(request, csrf)
    if website.strip():
        request.session["flash"] = MENSAJE_GENERICO
        return RedirectResponse("/#suscribir", status_code=303)
    with conectar() as conexion:
        if not permitir(conexion, f"suscribir:{_ip(request)}", 8, 15):
            conexion.commit()
            request.session["flash"] = MENSAJE_GENERICO
            return RedirectResponse("/#suscribir", status_code=303)
        try:
            resultado = registrar_publico(
                correo,
                [{"zona_id": int(distrito)}] if str(distrito).isdigit() else [],
                consentimiento=consentimiento in {"on", "true", "1", "si", "sí"},
                alerta_nueva=alerta_nueva in {"on", "true", "1"},
                alerta_modificada=alerta_modificada in {"on", "true", "1"},
                alerta_cancelacion=alerta_cancelacion in {"on", "true", "1"},
                resumen_diario=resumen_diario in {"on", "true", "1"},
                conexion=conexion,
            )
            conexion.commit()
        except ValueError as error:
            conexion.rollback()
            request.session["flash"] = str(error)
            return RedirectResponse("/#suscribir", status_code=303)
        except Exception:
            conexion.rollback()
            request.session["flash"] = MENSAJE_GENERICO
            return RedirectResponse("/#suscribir", status_code=303)
    resultado = enviar_correo_alta(resultado)
    mensaje = resultado["mensaje"]
    if resultado.get("smtp") is False:
        mensaje = (
            "Tu registro se guardó. No pudimos enviar el correo ahora; "
            "usa «Reenviar confirmación» en unos minutos o avisa al operador."
        )
    if PUBLIC_REVELAR_ENLACE and resultado.get("token"):
        mensaje += f" Enlace de laboratorio: {url_base()}/confirmar/{resultado['token']}"
    request.session["flash"] = mensaje
    return RedirectResponse("/#suscribir", status_code=303)


@router.post("/reenviar")
def reenviar(request: Request, correo: str = Form(...), csrf: str = Form(""), website: str = Form(default="")):
    validar_csrf(request, csrf)
    with conectar() as conexion:
        if website.strip() or not permitir(conexion, f"reenviar:{_ip(request)}", 5, 15):
            conexion.commit()
            request.session["flash"] = MENSAJE_GENERICO
            return RedirectResponse("/", status_code=303)
        resultado = reenviar_confirmacion(correo, conexion)
        conexion.commit()
    enviar_correo_alta(resultado)
    request.session["flash"] = MENSAJE_GENERICO
    return RedirectResponse("/", status_code=303)


@router.get("/confirmar/{token}", response_class=HTMLResponse)
def confirmar(request: Request, token: str):
    with conectar() as conexion:
        usuario = confirmar_publico(token, conexion)
        conexion.commit()
    if not usuario:
        return templates.TemplateResponse(
            "publico/mensaje.html",
            _ctx(
                request,
                titulo="Enlace no válido",
                mensaje="El enlace caducó o ya se usó. Puedes solicitar uno nuevo en la página de inicio.",
            ),
            status_code=400,
        )
    return templates.TemplateResponse(
        "publico/mensaje.html",
        _ctx(
            request,
            titulo="Suscripción confirmada",
            mensaje=(
                f"El correo {enmascarar_correo(usuario['correo'])} quedó confirmado. "
                "Recibirás avisos cuando una interrupción reportada podría relacionarse con tu distrito. "
                "Eso no confirma que tu vivienda esté afectada."
            ),
        ),
    )


@router.get("/cuenta/{token}", response_class=HTMLResponse)
def cuenta_get(request: Request, token: str):
    with conectar() as conexion:
        usuario = usuario_por_token_gestion(token, conexion)
        if not usuario:
            return templates.TemplateResponse(
                "publico/mensaje.html",
                _ctx(request, titulo="Enlace caducado", mensaje="Solicita un enlace nuevo desde la página de inicio."),
                status_code=400,
            )
        prefs = listar_prefs(usuario["id"], conexion)
    from src.tokens import firmar

    return templates.TemplateResponse(
        "publico/cuenta.html",
        _ctx(
            request,
            token=token,
            baja_token=firmar("baja", usuario["id"]),
            correo=enmascarar_correo(usuario["correo"]),
            pausado=usuario.get("pausado"),
            prefs=prefs,
        ),
    )


@router.post("/cuenta/{token}")
async def cuenta_post(request: Request, token: str, csrf: str = Form("")):
    validar_csrf(request, csrf)
    datos = await request.form()
    with conectar() as conexion:
        usuario = usuario_por_token_gestion(token, conexion)
        if not usuario:
            return RedirectResponse("/", status_code=303)
        prefs = listar_prefs(usuario["id"], conexion)
        subs = {}
        for p in prefs:
            sid = str(p["id"])
            subs[sid] = {
                "alerta_nueva": datos.get(f"nueva_{sid}") == "on",
                "alerta_modificada": datos.get(f"mod_{sid}") == "on",
                "alerta_cancelacion": datos.get(f"can_{sid}") == "on",
                "resumen_diario": datos.get(f"res_{sid}") == "on",
                "pausada": datos.get(f"pau_{sid}") == "on",
            }
        actualizar_prefs(
            usuario["id"],
            {"pausado": datos.get("pausado") == "on", "suscripciones": subs},
            conexion,
        )
        conexion.commit()
    request.session["flash"] = "Preferencias guardadas."
    return RedirectResponse(f"/cuenta/{token}", status_code=303)


@router.get("/baja/{token}", response_class=HTMLResponse)
def baja_get(request: Request, token: str):
    with conectar() as conexion:
        usuario = usuario_por_token_baja(token, conexion)
    if not usuario:
        return templates.TemplateResponse(
            "publico/mensaje.html",
            _ctx(request, titulo="Enlace no válido", mensaje="El enlace de cancelación no es válido o caducó."),
            status_code=400,
        )
    return templates.TemplateResponse(
        "publico/baja.html",
        _ctx(request, token=token, correo=enmascarar_correo(usuario["correo"])),
    )


@router.post("/baja/{token}")
def baja_post(request: Request, token: str, csrf: str = Form(""), confirmar: str = Form(default="")):
    validar_csrf(request, csrf)
    if confirmar not in {"on", "si", "sí", "1"}:
        request.session["flash"] = "Marca la casilla para confirmar la cancelación."
        return RedirectResponse(f"/baja/{token}", status_code=303)
    with conectar() as conexion:
        usuario = usuario_por_token_baja(token, conexion)
        if not usuario:
            return RedirectResponse("/", status_code=303)
        cancelar_todo(usuario["id"], conexion)
        conexion.commit()
    try:
        avisar_baja(usuario["correo"])
    except Exception:
        pass
    return templates.TemplateResponse(
        "publico/mensaje.html",
        _ctx(request, titulo="Suscripción cancelada", mensaje="No enviaremos más avisos a ese correo. El historial interno se conserva con el correo enmascarado en auditoría."),
    )
