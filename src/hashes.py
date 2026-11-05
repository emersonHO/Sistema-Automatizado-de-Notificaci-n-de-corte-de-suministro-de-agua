"""Hashes estables: origen, relevante y representación técnica."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Iterable, Mapping

from src.config import CAMPOS_ORIGEN, CAMPOS_RELEVANTES


def _vacio(valor: object) -> bool:
    if valor is None:
        return True
    if isinstance(valor, float) and valor != valor:  # NaN
        return True
    texto = str(valor).strip()
    return texto == "" or texto.lower() in {"nan", "none", "nat", "null"}


def normalizar_valor(valor: object) -> str | int | float | None:
    if _vacio(valor):
        return None
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    if hasattr(valor, "isoformat") and not isinstance(valor, str):
        try:
            return valor.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(valor)
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        if valor.is_integer():
            return int(valor)
        return round(valor, 6)
    texto = str(valor).strip()
    if "T" in texto and len(texto) >= 19:
        texto = texto.replace("T", " ")[:19]
    return texto


def calcular_hash_campos(registro: Mapping, campos: Iterable[str]) -> str:
    payload = {campo: normalizar_valor(registro.get(campo)) for campo in campos}
    contenido = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def hash_origen(registro: Mapping) -> str:
    return calcular_hash_campos(registro, CAMPOS_ORIGEN)


def hash_relevante(registro: Mapping) -> str:
    return calcular_hash_campos(registro, CAMPOS_RELEVANTES)


def hash_tecnico(registro: Mapping) -> str:
    payload = {
        clave: normalizar_valor(valor)
        for clave, valor in sorted(registro.items(), key=lambda x: str(x[0]))
    }
    contenido = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def campos_modificados(anterior: Mapping | None, actual: Mapping, campos: Iterable[str]) -> dict:
    cambios = {}
    for campo in campos:
        viejo = normalizar_valor(None if anterior is None else anterior.get(campo))
        nuevo = normalizar_valor(actual.get(campo))
        if viejo != nuevo:
            cambios[campo] = {"antes": viejo, "despues": nuevo}
    return cambios
