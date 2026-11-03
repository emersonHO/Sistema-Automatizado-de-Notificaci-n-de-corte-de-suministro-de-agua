"""Validaciones de calidad sobre el conjunto normalizado."""

from __future__ import annotations

from typing import Any

import pandas as pd


COLUMNAS_OBLIGATORIAS = ("id", "cod_incidencia", "municipalidad")


def evaluar_calidad(df: pd.DataFrame, meta_captura: dict | None = None) -> dict[str, Any]:
    informe: dict[str, Any] = {
        "registros": int(len(df)),
        "columnas": int(len(df.columns)),
        "errores": [],
        "advertencias": [],
    }

    if "id" not in df.columns:
        informe["errores"].append("No existe la columna id.")
        return informe

    ids = df["id"]
    vacios = ids.isna() | (ids.astype("string").str.strip() == "")
    informe["identificadores_vacios"] = int(vacios.sum())
    if informe["identificadores_vacios"]:
        informe["errores"].append("Existen identificadores vacíos.")

    duplicados = ids.dropna().duplicated().sum()
    informe["identificadores_duplicados"] = int(duplicados)
    if duplicados:
        informe["errores"].append("Existen identificadores duplicados.")

    for columna in ("fec_deteccion", "fec_estimada"):
        if columna in df.columns:
            nulos = int(df[columna].isna().sum())
            informe[f"nulos_{columna}"] = nulos
            if nulos:
                informe["advertencias"].append(
                    f"{columna} tiene {nulos} valores nulos; no se interpreta como inicio o fin confirmado del servicio."
                )

    if "municipalidad" in df.columns:
        informe["municipalidades_vacias"] = int(
            df["municipalidad"].isna().sum()
            + (df["municipalidad"].astype("string").str.strip() == "").sum()
        )

    if meta_captura:
        informe["captura_completa"] = bool(meta_captura.get("captura_completa", True))
        informe["total_reportado"] = meta_captura.get("total_reportado")
        informe["total_recibido"] = meta_captura.get("total_recibido")
        if not informe["captura_completa"]:
            informe["advertencias"].append(
                "Captura incompleta: no se debe interpretar la ausencia de una incidencia como cancelación."
            )

    informe["valido"] = len(informe["errores"]) == 0
    return informe
