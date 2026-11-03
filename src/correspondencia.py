"""Correspondencia territorial determinista y explicable.

Niveles:
- AREA: coincidencia exacta de un área reportada (tras normalizar).
- SECTOR: coincidencia exacta del número de sector.
- DISTRITO: coincidencia exacta del distrito canónico.

Una coincidencia de distrito se clasifica como POTENCIAL, nunca como
confirmación de afectación por vivienda. AREA y SECTOR son ESPECIFICA
(más precisas, aún sin confirmar el predio).
Callao se marca EXCLUIDA_AMBITO. Nombres no canónicos: AMBIGUA.
"""

from __future__ import annotations

from typing import Mapping

from src.texto import extraer_numero_sector, partir_areas
from src.zonas_lima import canonizar_distrito, etiqueta_sector


def evaluar_interrupcion(registro: Mapping) -> dict:
    municipalidad = registro.get("municipalidad")
    canon, ambito = canonizar_distrito(municipalidad)
    sector = etiqueta_sector(registro.get("infor_web"))
    areas = partir_areas(registro.get("areas_afectadas"))
    return {
        "id": registro.get("id"),
        "canon_distrito": canon,
        "ambito": ambito,
        "sector": sector,
        "numero_sector": extraer_numero_sector(registro.get("infor_web")),
        "areas": areas,
    }


def evaluar_par(interrupcion: Mapping, zona: Mapping) -> dict | None:
    """Evalúa una zona de interés contra una interrupción.

    zona: {id, tipo, nombre, nombre_normalizado, distrito_padre, ambito_lima}
    """
    eval_inc = evaluar_interrupcion(interrupcion)
    tipo = zona["tipo"]
    nombre_n = zona["nombre_normalizado"]

    if eval_inc["ambito"] == "VACIO":
        return {
            "nivel": tipo,
            "estado": "AMBIGUA",
            "explicacion": "La incidencia no declara municipalidad utilizable.",
        }
    if eval_inc["ambito"] == "AMBIGUO":
        return {
            "nivel": tipo,
            "estado": "AMBIGUA",
            "explicacion": (
                "La municipalidad reportada no coincide con un distrito canónico "
                "de Lima Metropolitana ni de Callao."
            ),
        }
    if eval_inc["ambito"] == "CALLAO":
        return {
            "nivel": tipo,
            "estado": "EXCLUIDA_AMBITO",
            "explicacion": (
                "La incidencia corresponde a Callao; el MVP no genera "
                "correspondencia territorial fuera de Lima Metropolitana."
            ),
        }

    if tipo == "DISTRITO":
        if eval_inc["canon_distrito"] == nombre_n:
            return {
                "nivel": "DISTRITO",
                "estado": "POTENCIAL",
                "explicacion": (
                    f"Coincidencia de distrito ({nombre_n}). Esto no confirma "
                    "que todas las viviendas del distrito estén afectadas."
                ),
            }
        return None

    if tipo == "SECTOR":
        numero_zona = extraer_numero_sector(zona.get("nombre")) or extraer_numero_sector(nombre_n)
        if numero_zona and eval_inc["numero_sector"] == numero_zona:
            distrito_padre = zona.get("distrito_padre")
            if distrito_padre and eval_inc["canon_distrito"] != distrito_padre:
                return {
                    "nivel": "SECTOR",
                    "estado": "AMBIGUA",
                    "explicacion": (
                        "El número de sector coincide, pero el distrito de la "
                        "incidencia no coincide con el distrito de la zona."
                    ),
                }
            return {
                "nivel": "SECTOR",
                "estado": "ESPECIFICA",
                "explicacion": (
                    f"Coincidencia de sector ({eval_inc['sector']}). "
                    "Sigue siendo una afectación potencial, no confirmada por vivienda."
                ),
            }
        return None

    if tipo == "AREA":
        if nombre_n in eval_inc["areas"]:
            return {
                "nivel": "AREA",
                "estado": "ESPECIFICA",
                "explicacion": (
                    f"Coincidencia exacta del área reportada ({nombre_n}). "
                    "No se afirma afectación confirmada de una vivienda."
                ),
            }
        return None

    return None


def coincidencia_notificable(resultado: dict | None) -> bool:
    if not resultado:
        return False
    return resultado["estado"] in {"POTENCIAL", "ESPECIFICA"}
