"""Casos etiquetados de forma independiente a las predicciones del sistema."""

INCIDENCIA_SANTA_ANITA = {
    "id": 125524,
    "cod_incidencia": "M-20261014083038-299",
    "municipalidad": "SANTA ANITA",
    "areas_afectadas": "Urb. Santa Aurelia; Cooperativa Santa Aurelia",
    "infor_web": "Sector 168",
    "tipo_incid": "PROGRAMADA",
    "estado": "MANUAL",
    "causa": "Limpieza de reservorio",
    "fec_deteccion": "2026-10-16 14:00:00",
    "fec_estimada": "2026-10-16 23:00:00",
    "ciudad": "Lima y Callao",
}

INCIDENCIA_CALLAO = {
    "id": 1,
    "municipalidad": "VENTANILLA",
    "areas_afectadas": "AA.HH. Ejemplo",
    "infor_web": "Sector 1",
    "tipo_incid": "PROGRAMADA",
    "estado": "MANUAL",
    "causa": "Mantenimiento",
    "fec_deteccion": "2026-10-16 08:00:00",
    "fec_estimada": "2026-10-16 12:00:00",
}

ZONA_SANTA_ANITA = {
    "id": 1,
    "tipo": "DISTRITO",
    "nombre": "Santa Anita",
    "nombre_normalizado": "SANTA ANITA",
    "distrito_padre": "SANTA ANITA",
    "ambito_lima": True,
}
ZONA_SECTOR_168 = {
    "id": 2,
    "tipo": "SECTOR",
    "nombre": "Sector 168",
    "nombre_normalizado": "SECTOR 168",
    "distrito_padre": "SANTA ANITA",
    "ambito_lima": True,
}
ZONA_AREA = {
    "id": 3,
    "tipo": "AREA",
    "nombre": "Urb. Santa Aurelia",
    "nombre_normalizado": "URB SANTA AURELIA",
    "distrito_padre": "SANTA ANITA",
    "ambito_lima": True,
}
ZONA_MIRAFLORES = {
    "id": 4,
    "tipo": "DISTRITO",
    "nombre": "Miraflores",
    "nombre_normalizado": "MIRAFLORES",
    "distrito_padre": "MIRAFLORES",
    "ambito_lima": True,
}
ZONA_SECTOR_OTRO_DISTRITO = {
    "id": 5,
    "tipo": "SECTOR",
    "nombre": "Sector 168",
    "nombre_normalizado": "SECTOR 168",
    "distrito_padre": "ATE",
    "ambito_lima": True,
}

CASOS_CORRESPONDENCIA = [
    {"id": "distrito_positivo", "interrupcion": INCIDENCIA_SANTA_ANITA, "zona": ZONA_SANTA_ANITA, "esperado": True},
    {"id": "sector_positivo", "interrupcion": INCIDENCIA_SANTA_ANITA, "zona": ZONA_SECTOR_168, "esperado": True},
    {"id": "area_positiva", "interrupcion": INCIDENCIA_SANTA_ANITA, "zona": ZONA_AREA, "esperado": True},
    {"id": "distrito_negativo", "interrupcion": INCIDENCIA_SANTA_ANITA, "zona": ZONA_MIRAFLORES, "esperado": False},
    {"id": "callao_excluido", "interrupcion": INCIDENCIA_CALLAO, "zona": ZONA_SANTA_ANITA, "esperado": False},
    {
        "id": "sector_distrito_distinto",
        "interrupcion": INCIDENCIA_SANTA_ANITA,
        "zona": ZONA_SECTOR_OTRO_DISTRITO,
        "esperado": False,
    },
    {
        "id": "ambiguo",
        "interrupcion": {**INCIDENCIA_SANTA_ANITA, "municipalidad": "DISTRITO DESCONOCIDO XYZ"},
        "zona": ZONA_SANTA_ANITA,
        "esperado": False,
    },
]


def _inc(**kwargs):
    base = dict(INCIDENCIA_SANTA_ANITA)
    base.update(kwargs)
    return base


CASOS_CAMBIOS = [
    {
        "id": "nueva",
        "anterior": None,
        "actual": _inc(),
        "espera_origen": True,
        "espera_relevante": True,
        "espera_evento": "NUEVA",
    },
    {
        "id": "sin_cambios",
        "anterior": _inc(),
        "actual": _inc(),
        "espera_origen": False,
        "espera_relevante": False,
        "espera_evento": "CAMBIO_TECNICO",
    },
    {
        "id": "irrelevante_imagen",
        "anterior": _inc(imagen_url="a.jpg"),
        "actual": _inc(imagen_url="b.jpg"),
        "espera_origen": True,
        "espera_relevante": False,
        "espera_evento": "CAMBIO_TECNICO",
    },
    {
        "id": "relevante_areas",
        "anterior": _inc(),
        "actual": _inc(areas_afectadas="Otra urbanización"),
        "espera_origen": True,
        "espera_relevante": True,
        "espera_evento": "MODIFICADA",
    },
    {
        "id": "cancelada",
        "anterior": _inc(estado="MANUAL"),
        "actual": _inc(estado="CANCELADA"),
        "espera_origen": True,
        "espera_relevante": True,
        "espera_evento": "CANCELADA",
    },
]
