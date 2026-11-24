# Resultados Fase 3 — motor de notificaciones

**Fecha:** 22 de noviembre de 2026 (America/Lima)  
**Rama de trabajo:** `cursor/fase1-contenedores-5701`

## Objetivo

Desacoplar generación, procesamiento simulado y trazabilidad de avisos sin rediseñar las fases 1 y 2, sin SMTP real y sin borrar datos.

## Arquitectura

```text
pipeline-worker  -> coincidencias + notificaciones PENDIENTE
notification-worker -> FOR UPDATE SKIP LOCKED -> EN_PROCESO -> SIMULADA
FastAPI GET /internal/v1/notificaciones (Bearer)
Panel HTML /notificaciones (sesión admin)
```

El CLI `python -m src.pipeline` puede seguir consumiendo el outbox en laboratorio. En Compose, `pipeline-worker` usa `procesar_envios=False`.

## Pruebas ejecutadas

```text
docker compose --env-file .env.docker run --rm -e DB_NAME=notificaciones_agua_test web python -m pytest -q --tb=short
41 passed in 8.29s
```

Base: `notificaciones_agua_test` en el PostgreSQL Docker (no se truncó `notificaciones_agua`). No se ejecutó `docker compose down -v`.

## Servicios observados

Tras `docker compose --env-file .env.docker up -d --build db web pipeline-worker notification-worker n8n`:

- `db` healthy (5432/tcp interno, sin publicación en el host)
- `web` healthy en `127.0.0.1:8000`
- `pipeline-worker` Up
- `notification-worker` Up; log: esquema aplicado e inicio del bucle
- `n8n` healthy en `127.0.0.1:5678`

## Limitaciones

- Entrega **simulada**; no hay canal real.
- Matching distrital = afectación **potencial**, no vivienda.
- At-least-once, no exactly-once.
- Mailpit no se añadió (decisión: simulación por archivo + estado `SIMULADA`).
