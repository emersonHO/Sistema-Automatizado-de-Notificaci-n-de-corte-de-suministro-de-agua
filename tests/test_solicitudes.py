from src.db import conectar
from src.solicitudes import (
    EjecucionActiva,
    IdempotenciaConflicto,
    crear_solicitud,
    obtener_ejecucion_de_solicitud,
    reclamar_solicitud,
    reconciliar_solicitud,
)


def test_crear_e_idempotencia(conexion):
    a, nueva = crear_solicitud(
        "MANUAL",
        solo_si_libre=False,
        modo="api",
        idempotency_key="clave-prueba-001",
        conexion=conexion,
    )
    assert nueva is True
    assert a["estado"] == "PENDIENTE"
    b, nueva2 = crear_solicitud(
        "MANUAL",
        solo_si_libre=False,
        modo="api",
        idempotency_key="clave-prueba-001",
        conexion=conexion,
    )
    assert nueva2 is False
    assert b["id"] == a["id"]
    try:
        crear_solicitud(
            "PROGRAMADA",
            solo_si_libre=False,
            modo="api",
            idempotency_key="clave-prueba-001",
            conexion=conexion,
        )
        assert False, "debía conflictuar"
    except IdempotenciaConflicto:
        pass


def test_solo_si_libre(conexion):
    crear_solicitud("MANUAL", solo_si_libre=False, conexion=conexion)
    try:
        crear_solicitud("PROGRAMADA", solo_si_libre=True, conexion=conexion)
        assert False, "debía rechazar"
    except EjecucionActiva:
        pass


def test_reclamar_y_reconciliar_sin_ejecucion(conexion):
    crear_solicitud("MANUAL", conexion=conexion)
    tomada = reclamar_solicitud("test-worker", conexion=conexion)
    assert tomada["estado"] == "EN_PROCESO"
    resultado = reconciliar_solicitud(tomada, conexion=conexion)
    assert resultado["estado"] in {"PENDIENTE", "ERROR_RECUPERACION"}
    assert obtener_ejecucion_de_solicitud(tomada["id"], conexion) is None


def test_reconciliar_ejecucion_terminal(conexion):
    fila, _ = crear_solicitud("MANUAL", conexion=conexion)
    tomada = reclamar_solicitud("test-worker", conexion=conexion)
    with conectar() as cx:
        with cx.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ejecuciones_proceso (estado, solicitud_id, registros_leidos)
                VALUES ('COMPLETADO', %s, 2)
                RETURNING id
                """,
                (tomada["id"],),
            )
            eid = cursor.fetchone()[0]
        cx.commit()
    cerrado = reconciliar_solicitud(tomada, conexion=conexion)
    assert cerrado["estado"] == "COMPLETADO"
    assert cerrado["ejecucion_id"] == eid
    assert obtener_ejecucion_de_solicitud(tomada["id"], conexion)["solicitud_id"] == tomada["id"]
