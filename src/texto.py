"""Normalización de textos para correspondencia territorial determinista."""

from __future__ import annotations

import re
import unicodedata

_NO_ALNUM = re.compile(r"[^A-Z0-9\s]")
_ESPACIOS = re.compile(r"\s+")
_SECTOR = re.compile(r"\bSECTOR\s*([0-9]{1,6})\b")


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
    texto = normalizar_texto(valor)
    if not texto:
        return None
    encontrado = _SECTOR.search(texto)
    if encontrado:
        return encontrado.group(1)
    if texto.isdigit():
        return texto
    return None


def partir_areas(valor: object) -> list[str]:
    if valor is None:
        return []
    partes = str(valor).split(";")
    resultado = []
    vistos = set()
    for parte in partes:
        normal = normalizar_texto(parte)
        if normal and normal not in vistos:
            vistos.add(normal)
            resultado.append(normal)
    return resultado
