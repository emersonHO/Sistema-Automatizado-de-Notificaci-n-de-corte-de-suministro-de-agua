"""Métricas Prometheus. Complementan el snapshot SQL; no sustituyen PostgreSQL.

Las etiquetas son de baja cardinalidad (estado, handler, código). Sin IDs.
Un fallo de scrape no detiene el pipeline ni el outbox.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from prometheus_client.registry import Collector

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Peticiones HTTP del panel y la API",
    ["method", "handler", "code"],
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Duración de peticiones HTTP",
    ["handler"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)


def normalizar_handler(ruta: str) -> str:
    if ruta.startswith("/internal/v1/pipeline"):
        return "internal_pipeline"
    if ruta.startswith("/internal/v1/notificaciones"):
        return "internal_notificaciones"
    if ruta.startswith("/internal/v1/observabilidad"):
        return "internal_observabilidad"
    if ruta.startswith("/internal/v1/destinatarios"):
        return "internal_destinatarios"
    if ruta.startswith("/salud"):
        return "salud"
    if ruta == "/metrics":
        return "metrics"
    if ruta.startswith("/admin"):
        return "admin"
    if ruta.startswith("/static"):
        return "static"
    partes = [p for p in ruta.split("/") if p]
    if not partes:
        return "inicio"
    if partes[0] in {
        "interrupciones",
        "notificaciones",
        "ejecuciones",
        "solicitudes",
        "suscripciones",
        "metricas",
        "destinatarios",
        "estado",
        "auditoria",
    }:
        return partes[0]
    return "otro"


class DominioCollector(Collector):
    def collect(self):
        postgres = GaugeMetricFamily("agua_postgres_up", "1 si PostgreSQL responde")
        scrape = GaugeMetricFamily("agua_scrape_ok", "1 si el snapshot de dominio se leyó")
        try:
            from src.observabilidad import postgres_ok, snapshot

            if not postgres_ok():
                postgres.add_metric([], 0)
                scrape.add_metric([], 0)
                yield postgres
                yield scrape
                return
            postgres.add_metric([], 1)
            data = snapshot()
            scrape.add_metric([], 1)
        except Exception:
            postgres.add_metric([], 0)
            scrape.add_metric([], 0)
            yield postgres
            yield scrape
            return
        yield postgres
        yield scrape
        pipe = data["pipeline"]
        g_ej = GaugeMetricFamily(
            "agua_pipeline_ejecuciones",
            "Ejecuciones del pipeline por estado",
            labels=["estado"],
        )
        g_ej.add_metric(["COMPLETADO"], pipe["completadas"])
        g_ej.add_metric(["COMPLETADO_INCOMPLETO"], pipe["incompletas"])
        g_ej.add_metric(["ERROR"], pipe["fallidas"])
        g_ej.add_metric(["EN_PROCESO"], pipe["en_proceso"])
        yield g_ej
        g_dur = GaugeMetricFamily(
            "agua_pipeline_duracion_segundos",
            "Duración agregada de ejecuciones con fecha_fin",
            labels=["agregado"],
        )
        if pipe["duracion_promedio_s"] is not None:
            g_dur.add_metric(["promedio"], pipe["duracion_promedio_s"])
        if pipe["duracion_mediana_s"] is not None:
            g_dur.add_metric(["mediana"], pipe["duracion_mediana_s"])
        if pipe["duracion_p95_s"] is not None:
            g_dur.add_metric(["p95"], pipe["duracion_p95_s"])
        yield g_dur
        g_reg = GaugeMetricFamily(
            "agua_pipeline_registros",
            "Suma de registros de ejecuciones",
            labels=["tipo"],
        )
        g_reg.add_metric(["leidos"], pipe["registros_leidos"])
        g_reg.add_metric(["nuevos"], pipe["registros_nuevos"])
        g_reg.add_metric(["actualizados"], pipe["registros_actualizados"])
        g_reg.add_metric(["sin_cambios"], pipe["registros_sin_cambios"])
        yield g_reg
        sol = data["solicitudes"]
        g_sol = GaugeMetricFamily(
            "agua_solicitudes",
            "Solicitudes de ejecución por estado",
            labels=["estado"],
        )
        g_sol.add_metric(["PENDIENTE"], sol["pendientes"])
        g_sol.add_metric(["EN_PROCESO"], sol["en_proceso"])
        g_sol.add_metric(["ERROR"], sol["error"])
        g_sol.add_metric(["ERROR_RECUPERACION"], sol["recuperacion"])
        yield g_sol
        g_espera = GaugeMetricFamily(
            "agua_solicitudes_espera_segundos",
            "Espera en cola de solicitudes (reclamada_en - creada_en)",
            labels=["agregado"],
        )
        if sol["espera_cola_promedio_s"] is not None:
            g_espera.add_metric(["promedio"], sol["espera_cola_promedio_s"])
        if sol["espera_cola_mediana_s"] is not None:
            g_espera.add_metric(["mediana"], sol["espera_cola_mediana_s"])
        yield g_espera
        notif = data["notificaciones"]
        g_n = GaugeMetricFamily(
            "agua_notificaciones",
            "Notificaciones por estado (SIMULADA no es correo leído)",
            labels=["estado"],
        )
        for estado, clave in (
            ("PENDIENTE", "pendientes"),
            ("EN_PROCESO", "en_proceso"),
            ("SIMULADA", "simuladas"),
            ("REINTENTANDO", "reintentando"),
            ("FALLIDA", "fallidas"),
            ("ACEPTADA_SMTP", "aceptadas_smtp"),
            ("CANCELADA", "canceladas"),
            ("DESCARTADA", "descartadas"),
        ):
            g_n.add_metric([estado], notif[clave])
        yield g_n
        g_int = GaugeMetricFamily("agua_notificaciones_reintentos", "Suma de reintentos")
        g_int.add_metric([], notif["reintentos"])
        yield g_int
        g_rec = GaugeMetricFamily(
            "agua_notificaciones_recuperaciones",
            "Recuperaciones de filas EN_PROCESO huérfanas",
        )
        g_rec.add_metric([], notif["recuperaciones"])
        yield g_rec
        g_nt = GaugeMetricFamily(
            "agua_notificaciones_tiempo_segundos",
            "Tiempos de outbox",
            labels=["fase"],
        )
        if notif["espera_cola_promedio_s"] is not None:
            g_nt.add_metric(["espera"], notif["espera_cola_promedio_s"])
        if notif["procesamiento_promedio_s"] is not None:
            g_nt.add_metric(["procesamiento"], notif["procesamiento_promedio_s"])
        yield g_nt


_REGISTRADO = False


def registrar() -> None:
    global _REGISTRADO
    if _REGISTRADO:
        return
    REGISTRY.register(DominioCollector())
    _REGISTRADO = True


def exposicion() -> tuple[bytes, str]:
    registrar()
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def observar_http(handler: str, metodo: str, codigo: int, segundos: float) -> None:
    HTTP_REQUESTS.labels(method=metodo, handler=handler, code=str(codigo)).inc()
    HTTP_LATENCY.labels(handler=handler).observe(segundos)
