# Decisiones arquitectónicas

## ADR-001 — Monolito modular, no microservicios

**Contexto:** Tesis de un desarrollador; diagrama con varias cajas Python.  
**Decisión:** Una imagen y un paquete `src`; procesos `web`, `pipeline` y (luego) `notification-worker`.  
**Estado:** Aceptada.  
**Consecuencia:** Menos duplicación; el aislamiento es de *proceso* y Compose, no de repositorios.

## ADR-002 — Outbox en PostgreSQL, sin broker

**Contexto:** Se pidió no introducir Redis/Kafka/Celery sin necesidad.  
**Decisión:** La cola sigue siendo `notificaciones` + `intentos_notificacion`. n8n no envía el correo de negocio.  
**Estado:** Aceptada.

## ADR-003 — Postgres Docker aislado, sin publicar puerto

**Contexto:** El tesista tiene PostgreSQL en Windows con datos.  
**Decisión:** Compose usa volumen `pgdata` nuevo. No hay `ports` en `db`. No se ejecuta `compose down -v` ni migración automática desde Windows.  
**Estado:** Aceptada.  
**Migración futura:** requerirá autorización y procedimiento de dump/restore con conteos (no ejecutado).

## ADR-004 — n8n orquesta, Python decide

**Contexto:** El diagrama coloca n8n sobre el pipeline.  
**Decisión:** n8n solo HTTP autenticado (fase 2). Correspondencia, hashes y outbox permanecen en Python.  
**Estado:** Aceptada; implementación pendiente.

## ADR-005 — Jobs durables antes de disparar por HTTP largo

**Contexto:** Evitar HTTP abierto durante la ingesta y `Popen` no supervisado.  
**Decisión:** Fase 2 introducirá `solicitudes_ejecucion`. Fase 1 dispara el pipeline con `docker compose run --rm pipeline`.  
**Estado:** Aceptada.

## ADR-006 — Autenticación admin al exponer el panel

**Contexto:** El panel listaba ejecuciones y notificaciones sin auth.  
**Decisión:** Si `ADMIN_PASSWORD` está definido, panel operativo, notificaciones, ejecuciones y métricas exigen sesión. Suscripciones e interrupciones públicas de la fuente siguen accesibles. CSRF en POST con token de sesión.  
**Estado:** Aceptada e implementada en fase 1.  
**Pruebas locales sin contraseña:** el panel permanece abierto (pytest). Compose **debe** definir contraseña.

## ADR-007 — Observabilidad por fases

**Decisión:** Fase 1 = logs diagnosticables (JSON opcional). Prometheus/Grafana = fase 4 con series reales.  
**Estado:** Aceptada.

## ADR-008 — Esquema idempotente, no migrador versionado

**Contexto:** `schema.sql` usa `IF NOT EXISTS`.  
**Decisión:** Fase 1 no pretende Alembic. No hay cambios incompatibles de columnas. Documentar la limitación.  
**Estado:** Aceptada.

## ADR-009 — Capturas en volumen Docker

**Decisión:** `/app/data` monta el volumen `capturas` para sobrevivir al recrear contenedores `web`/`pipeline`.  
**Estado:** Aceptada (verificación empírica depende de Docker en el entorno).
