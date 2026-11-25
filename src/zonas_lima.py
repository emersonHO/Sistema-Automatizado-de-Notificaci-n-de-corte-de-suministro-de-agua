"""Distritos de Lima Metropolitana y exclusión de Callao.

La correspondencia territorial del MVP se limita a Lima Metropolitana.
Los registros de Callao se conservan en la captura original.
"""

from __future__ import annotations

from src.texto import extraer_numero_sector, normalizar_texto

DISTRITOS_LIMA = (
    "LIMA",
    "ANCON",
    "ATE",
    "BARRANCO",
    "BRENA",
    "CARABAYLLO",
    "CHACLACAYO",
    "CHORRILLOS",
    "CIENEGUILLA",
    "COMAS",
    "EL AGUSTINO",
    "INDEPENDENCIA",
    "JESUS MARIA",
    "LA MOLINA",
    "LA VICTORIA",
    "LINCE",
    "LOS OLIVOS",
    "LURIGANCHO",
    "LURIN",
    "MAGDALENA DEL MAR",
    "MIRAFLORES",
    "PACHACAMAC",
    "PUCUSANA",
    "PUEBLO LIBRE",
    "PUENTE PIEDRA",
    "PUNTA HERMOSA",
    "PUNTA NEGRA",
    "RIMAC",
    "SAN BARTOLO",
    "SAN BORJA",
    "SAN ISIDRO",
    "SAN JUAN DE LURIGANCHO",
    "SAN JUAN DE MIRAFLORES",
    "SAN LUIS",
    "SAN MARTIN DE PORRES",
    "SAN MIGUEL",
    "SANTA ANITA",
    "SANTA MARIA DEL MAR",
    "SANTA ROSA",
    "SANTIAGO DE SURCO",
    "SURQUILLO",
    "VILLA EL SALVADOR",
    "VILLA MARIA DEL TRIUNFO",
)

DISTRITOS_CALLAO = (
    "CALLAO",
    "BELLAVISTA",
    "CARMEN DE LA LEGUA REYNOSO",
    "LA PERLA",
    "LA PUNTA",
    "VENTANILLA",
    "MI PERU",
)

# Alias controlados (no similitud difusa). Clave ya normalizada.
ALIAS_DISTRITO = {
    "CERCADO": "LIMA",
    "CERCADO DE LIMA": "LIMA",
    "LIMA CERCADO": "LIMA",
    "SJL": "SAN JUAN DE LURIGANCHO",
    "SAN JUAN LURIGANCHO": "SAN JUAN DE LURIGANCHO",
    "SJM": "SAN JUAN DE MIRAFLORES",
    "SAN JUAN MIRAFLORES": "SAN JUAN DE MIRAFLORES",
    "SMP": "SAN MARTIN DE PORRES",
    "SAN MARTIN PORRES": "SAN MARTIN DE PORRES",
    "VMT": "VILLA MARIA DEL TRIUNFO",
    "VILLA MARIA TRIUNFO": "VILLA MARIA DEL TRIUNFO",
    "VES": "VILLA EL SALVADOR",
    "SURCO": "SANTIAGO DE SURCO",
    "MAGDALENA": "MAGDALENA DEL MAR",
    "CHORRILLO": "CHORRILLOS",
    "LURIGANCHO CHOSICA": "LURIGANCHO",
    "CHOSICA": "LURIGANCHO",
    "CARMEN DE LA LEGUA": "CARMEN DE LA LEGUA REYNOSO",
}


def canonizar_distrito(valor: object) -> tuple[str | None, str]:
    """Devuelve (canon, estado) donde estado es LIMA, CALLAO, AMBIGUO o VACIO."""
    normal = normalizar_texto(valor)
    if not normal:
        return None, "VACIO"
    if normal in ALIAS_DISTRITO:
        normal = ALIAS_DISTRITO[normal]
    if normal in DISTRITOS_LIMA:
        return normal, "LIMA"
    if normal in DISTRITOS_CALLAO:
        return normal, "CALLAO"
    return None, "AMBIGUO"


def es_ambito_lima(valor: object) -> bool:
    _, estado = canonizar_distrito(valor)
    return estado == "LIMA"


def etiqueta_sector(valor: object) -> str | None:
    numero = extraer_numero_sector(valor)
    if numero is None:
        return None
    return f"SECTOR {numero}"
