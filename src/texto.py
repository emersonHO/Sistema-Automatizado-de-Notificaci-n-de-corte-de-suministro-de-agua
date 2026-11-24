"""Normalización de textos para correspondencia territorial determinista."""

from __future__ import annotations

import re
import unicodedata

_NO_ALNUM = re.compile(r"[^A-Z0-9\s]")
_ESPACIOS = re.compile(r"\s+")
_SEP_AREAS = re.compile(r"[;\n\r|]+")
_NUMEROS = re.compile(r"\b(\d{1,6})\b")


def normalizar_texto(valor: object) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if not texto or texto.lower() in {"nan", "none", "null"}:
        return ""
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.upper().replace(".", " ")
    texto = _NO_ALNUM.sub(" ", texto)
    return _ESPACIOS.sub(" ", texto).strip()


def extraer_numero_sector(valor: object) -> str | None:
    nums = extraer_sectores(valor)
    if nums:
        return nums[0]
    texto = normalizar_texto(valor)
    if texto.isdigit():
        return texto
    return None


def partir_areas(valor: object) -> list[str]:
    if valor is None:
        return []
    partes = _SEP_AREAS.split(str(valor))
    resultado = []
    vistos = set()
    for parte in partes:
        normal = normalizar_texto(parte)
        if normal and normal not in vistos:
            vistos.add(normal)
            resultado.append(normal)
    return resultado


def extraer_sectores(valor: object) -> list[str]:
    """Números de sector citados en infor_web (p. ej. 'Sectores 312, 313 y 314')."""
    texto = normalizar_texto(valor)
    if "SECTOR" not in texto:
        return []
    vistos = []
    for num in _NUMEROS.findall(texto):
        if num not in vistos:
            vistos.append(num)
    return vistos


def resumen_ubicaciones(areas_afectadas: object, infor_web: object) -> dict:
    partes = partir_areas(areas_afectadas)
    sectores = extraer_sectores(infor_web)
    original = "" if areas_afectadas is None else str(areas_afectadas).strip()
    return {
        "texto_original": original or None,
        "partes": partes,
        "sectores": sectores,
        "confianza": "parcial" if (original and not partes and not sectores) else "extraida",
    }
