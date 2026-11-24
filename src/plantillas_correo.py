"""Plantillas HTML/texto de correo ciudadano. No inventan campos ausentes."""

from __future__ import annotations

from src.config import API_URL, SMTP_FROM_NAME
from src.url_publica import url_base


def _esc(texto: str) -> str:
    return (
        str(texto)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def envoltorio(titulo: str, cuerpo_html: str, pie_enlaces: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(titulo)}</title></head>
<body style="margin:0;background:#f4f1ea;font-family:Segoe UI,Arial,sans-serif;color:#1c2430;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f1ea;padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;background:#fff;border:1px solid #d9d2c4;border-radius:8px;">
<tr><td style="background:#16324f;color:#fff;padding:16px 24px;font-family:Georgia,serif;font-size:18px;">
{_esc(SMTP_FROM_NAME)}</td></tr>
<tr><td style="padding:24px;">
<h1 style="font-size:20px;color:#16324f;font-family:Georgia,serif;">{_esc(titulo)}</h1>
{cuerpo_html}
{pie_enlaces}
<p style="font-size:13px;color:#5b6775;">La información procede de una fuente pública de un tercero
(<a href="{_esc(API_URL)}">{_esc(API_URL)}</a>), no es un canal oficial de SEDAPAL.
Una coincidencia por distrito no confirma que tu vivienda esté afectada.</p>
</td></tr></table>
</td></tr></table>
</body></html>"""


def pie(gestion: str, baja: str) -> str:
    return f"""<p style="font-size:13px;">
<a href="{_esc(gestion)}">Gestionar preferencias</a> ·
<a href="{_esc(baja)}">Cancelar suscripción</a>
</p>"""


def confirmacion(enlace: str) -> tuple[str, str, str]:
    asunto = "Confirma tu suscripción a avisos de interrupciones de agua"
    texto = (
        "Confirma tu correo para activar los avisos.\n\n"
        f"{enlace}\n\nEl enlace caduca. Si no pediste esta suscripción, ignora este mensaje."
    )
    html = envoltorio(
        "Confirma tu suscripción",
        f"<p>Pulsa el botón para activar los avisos en las zonas que elegiste.</p>"
        f'<p><a href="{_esc(enlace)}" style="display:inline-block;background:#16324f;color:#fff;'
        f'padding:12px 20px;border-radius:6px;text-decoration:none;">Confirmar correo</a></p>'
        f"<p>Si el botón no funciona: {_esc(enlace)}</p>",
    )
    return asunto, texto, html


def interrupcion(
    tipo: str,
    interrupcion: dict,
    coincidencia: dict,
    zona: dict,
    gestion: str,
    baja: str,
) -> tuple[str, str, str]:
    asuntos = {
        "NUEVA": "Aviso: interrupción reportada que podría afectar tu zona",
        "MODIFICADA": "Actualización de una interrupción en tu zona de interés",
        "CANCELADA": "Aviso: se informó la cancelación de una interrupción",
    }
    asunto = asuntos.get(tipo, "Aviso de interrupción de agua")
    campos = [
        ("Zona de interés", zona.get("nombre")),
        ("Tipo de zona", zona.get("tipo")),
        ("Nivel de coincidencia", coincidencia.get("nivel")),
        ("Alcance", "Posible afectación territorial; no confirma un domicilio."),
        ("Distrito o zona reportada", interrupcion.get("municipalidad")),
        ("Tipo de interrupción", interrupcion.get("tipo_incid")),
        ("Áreas o referencias", interrupcion.get("areas_afectadas")),
        ("Sector informado", interrupcion.get("infor_web")),
        ("Inicio publicado", interrupcion.get("fec_deteccion")),
        ("Fecha estimada (no confirmada)", interrupcion.get("fec_estimada")),
        ("Causa informada", interrupcion.get("causa")),
        ("Estado informado", interrupcion.get("estado")),
        ("Identificador", interrupcion.get("cod_incidencia") or interrupcion.get("id")),
        ("Fuente", API_URL),
    ]
    lineas = [
        "Se identificó una interrupción reportada que podría afectar una zona de tu suscripción.",
        coincidencia.get("explicacion") or "",
    ]
    items = ""
    for etiqueta, valor in campos:
        if valor is None or str(valor).strip() in {"", "None", "null"}:
            continue
        lineas.append(f"{etiqueta}: {valor}")
        items += f"<li><strong>{_esc(etiqueta)}:</strong> {_esc(valor)}</li>"
    lineas += [
        "",
        "La información procede de una fuente pública de un tercero.",
        "Una coincidencia territorial no confirma que tu vivienda esté afectada.",
        f"Preferencias: {gestion}",
        f"Cancelar: {baja}",
        f"Sitio: {url_base()}",
    ]
    html = envoltorio(
        asunto,
        "<p>Esto <strong>podría afectar</strong> tu zona de interés. No confirma que tu vivienda esté sin servicio.</p>"
        f"<ul>{items}</ul>"
        f"<p>{_esc(coincidencia.get('explicacion') or '')}</p>",
        pie(gestion, baja),
    )
    return asunto, "\n".join(str(x) for x in lineas if x), html


def gestion_acceso(enlace: str) -> tuple[str, str, str]:
    asunto = "Enlace para gestionar tu suscripción de avisos de agua"
    texto = f"Usa este enlace para ver o cambiar tus preferencias:\n{enlace}\n"
    html = envoltorio(
        "Gestionar suscripción",
        f'<p><a href="{_esc(enlace)}">Abrir preferencias</a></p>',
    )
    return asunto, texto, html


def baja_confirmada() -> tuple[str, str, str]:
    asunto = "Suscripción cancelada — avisos de interrupciones de agua"
    texto = "Tu suscripción quedó cancelada. No enviaremos más avisos a este correo."
    html = envoltorio("Suscripción cancelada", f"<p>{texto}</p>")
    return asunto, texto, html


def resumen(zonas: list[str], filas: list[dict], gestion: str, baja: str) -> tuple[str, str, str]:
    asunto = "Resumen diario de interrupciones en tus zonas (opcional)"
    if not filas:
        texto = "No hay interrupciones vigentes registradas hoy para tus zonas."
        html = envoltorio(asunto, f"<p>{texto}</p>", pie(gestion, baja))
        return asunto, texto, html
    lineas = ["Resumen de interrupciones que podrían relacionarse con tus zonas:", ""]
    items = ""
    for f in filas:
        dato = f"{f.get('municipalidad') or '—'} · {f.get('cod_incidencia') or f.get('id')}"
        lineas.append(dato)
        items += f"<li>{_esc(dato)}</li>"
    html = envoltorio(
        asunto,
        f"<p>Zonas: {_esc(', '.join(zonas))}</p><ul>{items}</ul>"
        "<p>Este resumen es opcional. Una coincidencia territorial no confirma afectación de vivienda.</p>",
        pie(gestion, baja),
    )
    return asunto, "\n".join(lineas), html


def alerta_admin(asunto: str, cuerpo: str) -> tuple[str, str, str]:
    html = envoltorio(asunto, f"<pre style='white-space:pre-wrap'>{_esc(cuerpo)}</pre>")
    return asunto, cuerpo, html
