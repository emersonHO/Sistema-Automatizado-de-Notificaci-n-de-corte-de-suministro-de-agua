# Observabilidad (Fase 4)

Timestamps de métricas y logs JSON: **UTC** (`datetime.now(timezone.utc).isoformat()`).

Fase 5 añade Prometheus (`/metrics`) y Grafana aprovisionado. El snapshot SQL **sigue** siendo la fuente de verdad de conteos. CPU/memoria de contenedores: `docker stats` y métricas de proceso del `web`. Un fallo de Grafana no detiene el pipeline.

## Auditoría previa (bloque 4.1)

| Componente | Mecanismos existentes | Datos disponibles | Deficiencias | Cambio | Prioridad |
|------------|----------------------|-------------------|--------------|--------|-----------|
| Logs | JSON o texto; `exc` en JSON | ts, level, logger, msg | Sin IDs de solicitud/ejecución/notificación | Campos de traza opcionales | Alta |
| PostgreSQL | Tablas de ejecuciones, solicitudes, notificaciones, intentos | Conteos, tiempos de etapa, estados | Sin percentiles ni espera en cola calculados en API | `src/observabilidad.py` | Alta |
| `/salud` | SELECT 1; 503 si falla BD | postgres bool | Mezclaba liveness y readiness (reinicio del web si BD titila) | `/salud` vivo; `/salud/listo` listo | Alta |
| Panel | Totales e última ejecución | Interrupciones, notif. básicas | Sin cola ni percentiles | Página `/metricas` | Media |
| `evaluacion.py` | Precisión etiquetada + AVG ejecuciones | Casos + promedios | Completado incompleto agrupado con OK; sin cola | Snapshot unificado | Media |
| Workers | Logs de reclamo | worker_id en columnas | Polling ruidoso si se loguea vacío | Solo log con trabajo o recuperación | Media |
| Docker | health db/web/n8n | compose ps | Health web apuntaba a `/salud` | `/salud/listo`; stats por script | Media |
| n8n | `/healthz` | HTTP | No acoplar FastAPI a n8n | Diagnóstico aparte | Baja |
| Prometheus/Grafana | Planificado en evolución | — | Coste de operación > beneficio en MVP | Fase 4: no (ADR-011). Fase 5: sí, no bloqueantes (ADR-012) | — |

## Endpoints

| Ruta | Auth | Rol |
|------|------|-----|
| `GET /salud` | ninguna | Liveness (HTTP 200 si el proceso responde) |
| `GET /salud/listo` | ninguna | Readiness (PostgreSQL `SELECT 1`; 503 si no) |
| `GET /internal/v1/observabilidad` | Bearer | Snapshot JSON |
| `GET /metricas` | sesión admin si hay `ADMIN_PASSWORD` | Dashboard HTML |

Ninguno envía correo ni encola pipeline.

## Fórmulas

- Duración de ejecución: `fecha_fin - fecha_inicio` (s).
- Espera de solicitud: `reclamada_en - creada_en`.
- Espera de notificación: `procesada_en - creada_en`.
- Procesamiento de notificación: `finalizada_en - procesada_en`.
- Tasa sin error de pipeline: `(COMPLETADO + COMPLETADO_INCOMPLETO) / (COMPLETADO + COMPLETADO_INCOMPLETO + ERROR)`.
- Tasa completo estricto: `COMPLETADO / mismo denominador`.
- Tasa de simulación: `SIMULADA / (SIMULADA + FALLIDA + ACEPTADA_SMTP)`.
- Reintentos: `sum(GREATEST(intentos - 1, 0))`.
- Recuperaciones de outbox: columna `recuperaciones` incrementada al reclamar huérfanas.

Medianas y p95: `percentile_cont` de PostgreSQL; `null` si no hay filas.

## Logs

Campos extra: `evento`, `solicitud_id`, `ejecucion_id`, `notificacion_id`, `worker_id`, `estado`, `intentos`.  
Eventos: `pipeline_inicio`, `pipeline_fin`, `pipeline_error`, `solicitud_reclamada`, `notificacion_reclamada`, `notificacion_resultado`, `notificacion_error`, `notificacion_recuperada`.

## Recursos

```powershell
.\scripts\diagnostico.ps1
```

No persiste muestras de CPU (haría falta un exporter). El RSS del proceso `web` aparece en `/salud/listo` solo en Linux (`/proc/self/status`).

## Prometheus y Grafana (fase 5)

| Pieza | Valor real |
|-------|------------|
| Scrape | `web:8000/metrics` cada 15 s (`observability/prometheus/prometheus.yml`) |
| UI Prometheus | http://127.0.0.1:9090 |
| UI Grafana | http://127.0.0.1:3000 |
| Datasource | uid `prometheus` → `http://prometheus:9090` |
| Dashboards | Estado general, Pipeline, Notificaciones, Infraestructura (proceso web) |

`/metrics` está en el mismo proceso FastAPI, publicado solo en `127.0.0.1:8000`. Las etiquetas son `estado`, `handler`, `code`, `agregado`, `tipo`, `job` — nunca IDs. Un fallo de scrape no detiene workers.

No hay cadvisor: no se monta el socket Docker. CPU/RAM de otros contenedores: `docker stats`.

## Evaluación experimental

Usar fixtures (`captura_minima.json`) y `notificaciones_agua_test`. No llamar a la API pública para generar carga. `python -m src.evaluacion` sigue siendo el reporte de casos etiquetados más el snapshot de la base conectada.
