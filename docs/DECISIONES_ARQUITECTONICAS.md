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
**Estado:** Aceptada e implementada en fase 2.  
**Contrato:** Bearer `INTERNAL_API_TOKEN` hacia `http://web:8000/internal/v1/...`. n8n no usa cookies ni CSRF. El token se guarda como credencial Header Auth en n8n; los JSON de workflow no lo incluyen ni leen `$env`. Timeout de 15 min en el workflow no cancela la solicitud ni el pipeline.

## ADR-005 — Jobs durables antes de disparar por HTTP largo

**Contexto:** Evitar HTTP abierto durante la ingesta y `Popen` no supervisado.  
**Decisión:** POST interno encola en `solicitudes_ejecucion` (HTTP 202). `pipeline-worker` reclama con `FOR UPDATE SKIP LOCKED` y llama `ejecutar_pipeline(solicitud_id=...)`. El candado `pg_try_advisory_lock(570114)` permanece solo dentro del pipeline. El perfil Compose `pipeline` sigue como CLI de laboratorio (bypass de la cola).  
**Estado:** Aceptada e implementada en fase 2.  
**Trazabilidad:** `ejecuciones_proceso.solicitud_id` (UNIQUE parcial) y `solicitudes_ejecucion.ejecucion_id`. Reconciliación por `solicitud_id` + `pg_stat_activity(backend_pid)`, no por fechas ni por la sola presencia del advisory lock.  
**n8n:** imagen `n8nio/n8n:2.48.4`, SQLite en volumen `n8n_data`, UI en `127.0.0.1:5678`.

## ADR-010 — Worker de notificaciones separado, simulación obligatoria en Compose

**Contexto:** El pipeline de las fases 1–2 también consumía el outbox al final de la ingesta.  
**Decisión:** Reutilizar `notificaciones` / `intentos_notificacion` / `usuarios` / `suscripciones`. Añadir columnas de reclamo (worker, pid, backoff) sin recrear tablas. `notification-worker` es el consumidor en Docker. El éxito simulado termina en `SIMULADA`. No se introduce Mailpit ni SMTP. No se crea una tabla paralela de destinatarios. Un mismo usuario no recibe dos filas para el mismo evento (`usuario_id` + interrupción + versión + tipo).  
**Estado:** Aceptada e implementada en fase 3.  
**Garantía:** at-least-once con idempotencia de reclamo y de clave de evento; no exactly-once de entrega.

## ADR-006 — Autenticación admin al exponer el panel

**Contexto:** El panel listaba ejecuciones y notificaciones sin auth.  
**Decisión:** Si `ADMIN_PASSWORD` está definido, panel operativo, notificaciones, ejecuciones y métricas exigen sesión. Suscripciones e interrupciones públicas de la fuente siguen accesibles. CSRF en POST con token de sesión.  
**Estado:** Aceptada e implementada en fase 1.  
**Pruebas locales sin contraseña:** el panel permanece abierto (pytest). Compose **debe** definir contraseña.

## ADR-007 — Observabilidad por fases

**Decisión:** Fase 1 = logs diagnosticables (JSON opcional). Fase 4 = métricas SQL + panel + `/salud/listo`, sin Prometheus.  
**Estado:** Superada por ADR-011.

## ADR-011 — Observabilidad ligera, sin Prometheus ni Grafana

**Contexto:** El plan de evolución citaba `/metrics` Prometheus y Grafana. El volumen del MVP cabe en PostgreSQL (`ejecuciones_proceso`, `solicitudes_ejecucion`, `notificaciones`, `intentos_notificacion`). Añadir dos servicios, volúmenes y dashboards aumentaría CPU/RAM y puertos sin mejorar la tesis si las cifras salen de las mismas tablas.  
**Decisión:** Agregar `src/observabilidad.py`, `GET /internal/v1/observabilidad`, liveness/readiness y enriquecer `/metricas`. CPU/memoria vía `docker stats` (`scripts/diagnostico.ps1`). No publicar puertos nuevos.  
**Estado:** Complementada por ADR-012 (Prometheus/Grafana/Mailpit en fase 5, sin sustituir el snapshot SQL).

## ADR-012 — Prometheus, Grafana y Mailpit como complementos no bloqueantes

**Contexto:** El diagrama de referencia de la tesis incluye Prometheus, Grafana y SMTP de laboratorio. ADR-011 evitó esa pila en la fase 4 por coste. La fase 5 la incorpora porque el diagrama es la referencia de entrega.  
**Decisión:** Prometheus raspa `web:8000/metrics`. Grafana se aprovisiona desde archivos. Mailpit recibe SMTP de laboratorio. Ninguno va en la ruta crítica del pipeline ni del outbox. Sin cadvisor ni socket Docker publicado. CPU/RAM de contenedor siguen pudiendo leerse con `docker stats`. SMTP externo solo con `SMTP_ENABLED=true` y `MODO_ENVIO` en `real`/`smtp`/`mailpit`.  
**Estado:** Aceptada e implementada en fase 5.

## ADR-008 — Esquema idempotente, no migrador versionado

**Contexto:** `schema.sql` usa `IF NOT EXISTS`.  
**Decisión:** Fase 1 no pretende Alembic. No hay cambios incompatibles de columnas. Documentar la limitación.  
**Estado:** Aceptada.

## ADR-009 — Capturas en volumen Docker

**Decisión:** `/app/data` monta el volumen `capturas` para sobrevivir al recrear contenedores `web`/`pipeline`.  
**Estado:** Aceptada (verificación empírica depende de Docker en el entorno).
