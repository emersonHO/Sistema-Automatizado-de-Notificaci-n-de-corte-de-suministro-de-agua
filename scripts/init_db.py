"""Aplica el esquema y siembra distritos. No borra datos existentes."""

from src.db import aplicar_esquema, conectar
from src.suscripciones import sembrar_zonas


def main() -> None:
    aplicar_esquema()
    conexion = conectar()
    try:
        sembrar_zonas(conexion)
        conexion.commit()
        print("Esquema aplicado y zonas de Lima/Callao sembradas (sin borrar datos).")
    finally:
        conexion.close()


if __name__ == "__main__":
    main()
