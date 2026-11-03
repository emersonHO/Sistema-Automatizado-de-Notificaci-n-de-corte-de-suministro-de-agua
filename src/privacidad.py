"""Utilidades para no exponer correos en la interfaz ni en logs."""


def enmascarar_correo(correo: str | None) -> str:
    if not correo or "@" not in correo:
        return "(oculto)"
    local, dominio = correo.split("@", 1)
    visible = local[0] + "***" if local else "***"
    return f"{visible}@{dominio}"
