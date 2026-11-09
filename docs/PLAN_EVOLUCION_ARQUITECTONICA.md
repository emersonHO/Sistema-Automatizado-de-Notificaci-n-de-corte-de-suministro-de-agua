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

## Fase 2 — n8n (no implementar ahora)

- Servicio `n8n` + volumen; credenciales distintas; BD n8n separada si usa Postgres.
- Tabla `solicitudes_ejecucion` y endpoints admin autenticados de disparo/consulta **sin** dejar el HTTP abierto durante la ingesta.
- Worker que consume trabajos + advisory lock existente.
- Workflows exportados en `n8n/workflows/`.
- Alertas al administrador (correo Mailpit o webhook).

## Fase 3 — Worker de notificaciones

- Servicio `notification-worker`: bucle `procesar_outbox`.
- Mailpit en laboratorio; SMTP real sigue opt-in.
- Pipeline deja de ser el único consumidor del outbox.

## Fase 4 — Observabilidad

- Logs JSON por defecto en Compose.
- `/metrics` Prometheus desde ejecuciones reales.
- Grafana con dashboard de tiempos, éxitos/fallos; sin cifras inventadas.

## Fase 5 — CI y evaluación

- GitHub Actions: pytest + `compose config` / build.
- Experimentos de latencia controlada, idempotencia y fallos, reportados desde ejecuciones.

## Orden y dependencias

Fase 1 no depende de n8n. Fase 2 depende de un endpoint de jobs (aún no existe). Fase 3 puede adelantarse si se prioriza el desacople del correo; el plan oficial la deja después de n8n. Fase 4 necesita procesos estables. Fase 5 necesita imagen y tests verdes.

## Criterio para no declarar una fase cerrada

Solo con evidencia: comando ejecutado, código HTTP, conteos SQL o pytest. Si Docker no está en el entorno del agente, los archivos se entregan y las pruebas de Compose quedan **pendientes**.
