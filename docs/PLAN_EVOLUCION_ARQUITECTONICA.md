# Plan de evolución arquitectónica

Plan por fases a partir del MVP (rama de implementación) y del diagrama objetivo. **No presenta trabajo futuro como operativo.**

## Diagnóstico inicial (8 nov 2026, America/Lima)

Confirmado en el árbol git:

- Hay aplicación Python, `database/schema.sql`, panel FastAPI, pytest, outbox SQL, pipeline con advisory lock.
- **No hay** `Dockerfile`, `compose.yaml`, n8n, Prometheus, Grafana, GitHub Actions, worker de notificaciones separado.
- `ADMIN_TOKEN` estaba declarado y **no se usaba**.
- PostgreSQL de demostración en Windows del tesista es independiente; esta evolución usa un volumen Docker **nuevo** y no publica el puerto del motor.

Evidencia previa de pytest (`docs/RESULTADOS_PRUEBAS.md`, 2 nov 2026) no se da por vigente hasta reejecutar.

## Principios

1. Reutilizar módulos de `src/`.
2. Una imagen Python, varios comandos.
3. PostgreSQL de dominio = fuente de verdad.
4. n8n solo orquesta HTTP; no SQL de negocio.
5. No `compose down -v`, ni `DROP`/`TRUNCATE` sobre datos de Windows.
6. `CREATE TABLE IF NOT EXISTS` no sustituye migraciones versionadas; fase 1 no introduce cambios incompatibles de esquema.

## Fase 0 — Auditoría y plan

Entregables: este archivo, `docs/ARQUITECTURA_OBJETIVO.md`, `docs/DECISIONES_ARQUITECTONICAS.md`.  
**Estado:** realizada en esta iteración.

## Fase 1 — Contenerización (implementar ahora)

1. Dockerfile (Python 3.12 slim, usuario no root).
2. `.dockerignore`.
3. `compose.yaml`: `db`, `web`, `pipeline` (perfil).
4. Volumen `pgdata` y `capturas`.
5. Red interna; Postgres **sin** `ports:` en el host.
6. Healthchecks `db` y `web`.
7. Variables `.env.docker.example`.
8. Web en `127.0.0.1:8000`.
9. Autenticación administrativa cuando hay contraseña (exposición de red).
10. Logs con formato opcional JSON.
11. Documentar init/migraciones y que no se toca el Postgres de Windows.
12. Pytest en el host; pruebas Compose si hay daemon.

**No incluye** n8n, Mailpit, Prometheus, Grafana ni Actions.

## Fase 2 — n8n (implementada 17 nov 2026)

- Servicio `n8n` (`n8nio/n8n:2.48.4`) + volumen `n8n_data` (SQLite; no usa el Postgres de dominio).
- Tabla `solicitudes_ejecucion` y API Bearer `/internal/v1/pipeline/ejecuciones` (POST 202, GET estado).
- `pipeline-worker` reclama con `SKIP LOCKED` y reutiliza `ejecutar_pipeline()` + lock `570114`.
- Workflows en `n8n/workflows/` (manual y programado **inactivo**).
- Alertas Mailpit: pendientes de fase 3.

Pendiente de operación: activar el cron solo después de validar el workflow manual en la UI de n8n (importar JSON).

## Fase 3 — Worker de notificaciones (implementada 22 nov 2026)

- Servicio `notification-worker` (`python -m src.worker_notificaciones`): reclamo `FOR UPDATE SKIP LOCKED`, estados `EN_PROCESO` / `REINTENTANDO` / `SIMULADA`.
- Destinatarios de prueba = `usuarios` + `suscripciones` (correos ficticios). No se añadió Mailpit: la entrega es archivo JSON en `data/simulaciones/` y el estado terminal de éxito es `SIMULADA`, nunca `ENVIADA`.
- `pipeline-worker` deja `procesar_envios=False`; el CLI local puede seguir consumiendo el outbox con el default del pipeline.
- Consulta Bearer: `GET /internal/v1/notificaciones` y `GET /internal/v1/destinatarios`.
- SMTP real sigue opt-in y **desactivado** en Compose.

## Fase 4 — Observabilidad (implementada 22 nov 2026)

- Logs JSON en Compose con IDs de traza (solicitud, ejecución, notificación, worker).
- Métricas agregadas desde PostgreSQL (`src/observabilidad.py`); panel `/metricas`; `GET /internal/v1/observabilidad`.
- Liveness `GET /salud` y readiness `GET /salud/listo` (healthcheck Compose del `web`).
- **Sin** Prometheus, Grafana ni exporters (ADR-011). Recursos: `scripts/diagnostico.ps1`.

## Fase 5 — Integración, CI y pila de referencia (implementada 22 nov 2026)

- GitHub Actions: pytest con PostgreSQL de servicio, `compose config`, JSON de Grafana, Prometheus YAML, sin `.env` versionado.
- Prometheus `prom/prometheus:v2.54.1` + Grafana `11.3.1` (aprovisionados).
- Mailpit `axllent/mailpit:v1.21.8` (SMTP de laboratorio).
- Adaptador `src/correo.py`; worker respeta `SMTP_ENABLED`.
- Workflow n8n de seguimiento. Panel ampliado (solicitudes, destinatarios, auditoría, servicios).

## Orden y dependencias

Fase 1 no depende de n8n. Fase 2 (jobs HTTP + worker) está implementada. Fase 3 puede adelantarse si se prioriza el desacople del correo; el plan oficial la deja después de n8n. Fase 4 necesita procesos estables. Fase 5 necesita imagen y tests verdes.

## Criterio para no declarar una fase cerrada

Solo con evidencia: comando ejecutado, código HTTP, conteos SQL o pytest. Si Docker no está en el entorno del agente, los archivos se entregan y las pruebas de Compose quedan **pendientes**.
