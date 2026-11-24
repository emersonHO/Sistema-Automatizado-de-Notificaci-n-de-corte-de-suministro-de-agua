# Informe técnico — Fase 5 (integración y consolidación)

Fecha de evidencia local: 22 nov 2026.  
Entorno: Windows, Docker Desktop, rama `cursor/fase1-contenedores-5701`.  
No se ejecutó `docker compose down -v`. No se truncaron tablas de `notificaciones_agua`. Las pruebas usaron `notificaciones_agua_test` o llamadas SMTP de laboratorio a Mailpit.

---

## 1. Resumen ejecutivo

La fase 5 conecta la pila de referencia (Compose + FastAPI + workers + n8n + PostgreSQL + Mailpit + Prometheus + Grafana + GitHub Actions) sobre el código de las fases 1–4, sin recrear el pipeline ni el outbox.

Lo verificado en este entorno: Compose en marcha, `/metrics` con series `agua_*` reales, Prometheus con targets `prometheus` y `web` en `up`, Grafana con datasource y cuatro dashboards, Mailpit con un mensaje de laboratorio, pytest **53 passed**.

Lo pendiente de operador/externo: importar en la UI de n8n el workflow de seguimiento; activar el programado; ejecutar GitHub Actions en el remoto (el YAML existe; no hubo push); SMTP de proveedor real (opt-in, sin credenciales en el repo).

---

## 2. Arquitectura final

Fuentes externas → Compose (`interna`) → n8n (HTTP Bearer) → FastAPI (`web`) → `pipeline-worker` / `notification-worker` → PostgreSQL (verdad de proceso) + volumen `capturas`. Observabilidad: logs JSON, snapshot SQL, Prometheus, Grafana. Correo de laboratorio: Mailpit (`1025` interno, UI `8025` en localhost).

PostgreSQL **no** se publica en el host. UIs administrativas en `127.0.0.1`.

---

## 3. Comparación con el diagrama de referencia

| Caja del diagrama | Implementación | Notas |
|-------------------|----------------|-------|
| API pública de interrupciones | `API_URL` → cortedeagua.net.pe (tercero) | No se presenta como API oficial SEDAPAL |
| Fuentes oficiales adicionales | No hay conector | Sin API documentada accesible; no se simuló |
| Investigador / admin | Panel FastAPI + sesión | `ADMIN_PASSWORD` |
| Ciudadano suscrito | `usuarios` / `suscripciones` | Datos de prueba |
| SMTP | `src/correo.py` + Mailpit | Externo opt-in |
| n8n workflows | JSON en `n8n/workflows/` | Manual y programado ya existían; seguimiento añadido |
| Ingesta / normalización / cambios | `src.pipeline` | Sin duplicar en n8n |
| Matching y eventos | Python | Idempotencia outbox |
| FastAPI + panel | `src.web` | Rutas ampliadas |
| Workers | dos procesos | `procesar_envios=False` en pipeline-worker |
| JSON + PostgreSQL + outbox | volumen + esquema aditivo | |
| Prometheus + Grafana | Compose + provisioning | Complemento no bloqueante (ADR-012) |
| GitHub Actions | `.github/workflows/ci.yml` | Archivo listo; run en GitHub pendiente de push |

---

## 4. Componentes implementados

- Adaptador SMTP `src/correo.py`.
- Métricas Prometheus `src/metricas_prom.py` (`DominioCollector`, sin labels de ID).
- Middleware HTTP + `GET /metrics`.
- Mailpit, Prometheus, Grafana en `compose.yaml`.
- Dashboards y datasource provisionados.
- Workflow n8n `seguimiento-observabilidad.json`.
- CI: pytest, compose config, YAML Prometheus, JSON Grafana, rechazo de `.env` versionado.
- Panel: resumen, solicitudes, destinatarios, auditoría, estado de servicios, filtros de notificaciones, estilos institucionales.

---

## 5. Servicios Docker (evidencia `docker compose ps`)

| Nombre | Estado observado | Puertos |
|--------|------------------|---------|
| notificacion-agua-db-1 | Up (healthy) | 5432/tcp **sin publicar** |
| notificacion-agua-web-1 | Up (healthy) | 127.0.0.1:8000 |
| notificacion-agua-pipeline-worker-1 | Up | — |
| notificacion-agua-notification-worker-1 | Up | — |
| notificacion-agua-n8n-1 | Up (healthy) | 127.0.0.1:5678 |
| notificacion-agua-mailpit-1 | Up (healthy) | 127.0.0.1:8025 |
| notificacion-agua-prometheus-1 | Up | 127.0.0.1:9090 |
| notificacion-agua-grafana-1 | Up | 127.0.0.1:3000 |

Volúmenes: `pgdata`, `capturas`, `n8n_data`, `prometheus_data`, `grafana_data`.

---

## 6. Configuración de n8n

- Imagen `n8nio/n8n:2.48.4`.
- `N8N_ENCRYPTION_KEY` persistente vía `.env.docker` y volumen `n8n_data`.
- `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`.
- Credencial Header Auth «FastAPI interno» (no va en los JSON).
- n8n no ejecuta Docker ni SQL.

---

## 7. Workflows disponibles

| Archivo | Uso | Activación |
|---------|-----|------------|
| `n8n/workflows/pipeline-manual.json` | POST solicitud + poll + timeout | Manual (Test workflow) |
| `n8n/workflows/pipeline-programado.json` | Cron + `solo_si_libre` | **Inactivo** hasta validar |
| `n8n/workflows/seguimiento-observabilidad.json` | GET observabilidad + notificaciones | Consulta; no sustituye Grafana |

Importación de seguimiento en la UI de n8n: **pendiente de operador** en esta sesión (el JSON está versionado). Manual/programado se importaron en fase 2.

---

## 8. Funcionamiento SMTP

- Defecto: `SMTP_ENABLED=false`, `MODO_ENVIO=simulacion` → `SIMULADA` + archivos en `data/simulaciones`.
- Laboratorio: `SMTP_ENABLED=true`, `MODO_ENVIO=mailpit`, host `mailpit:1025` → `ACEPTADA_SMTP` si el worker envía; **aceptación ≠ lectura del buzón**.
- Externo: mismas variables; no hay secretos en Git.

**Prueba de laboratorio (22 nov 2026):** desde `web` con SMTP forzado a Mailpit se envió a `lab.prueba@example.test`. Mailpit `GET /api/v1/messages` devolvió `total:1`, asunto «Prueba laboratorio Mailpit Fase 5». El worker en Compose **sigue** con simulación (SMTP desactivado por defecto); no se procesó outbox real hacia Internet.

---

## 9. Prometheus y targets

`GET http://127.0.0.1:9090/api/v1/targets`:

- `job=prometheus` health `up`
- `job=web` health `up`

`agua_postgres_up` = 1 (`instance=web:8000`).  
`/-/healthy` HTTP 200.

---

## 10. Grafana y dashboards

- Salud API: `database: ok`, versión `11.3.1`.
- Datasource Prometheus (uid `prometheus`, `http://prometheus:9090`, default, readOnly).
- Proxy Grafana → Prometheus: `up` = 1 para prometheus y web.
- Dashboards provisionados: Estado general (`agua-estado`), Pipeline (`agua-pipeline`), Notificaciones (`agua-notif`), Infraestructura proceso web (`agua-infra`).

El dashboard de infraestructura usa métricas de proceso del `web`, no cadvisor. No se inventan series de CPU de otros contenedores.

---

## 11. API y panel

Rutas nuevas/consolidadas: `/solicitudes`, `/destinatarios`, `/auditoria`, `/estado`, filtro `?estado=` en notificaciones, `/metrics`.  
Liveness `/salud` (`vivo: true`). Readiness `/salud/listo`.  
Panel visual: fondo claro, navegación por secciones, no hay cifras ficticias.

---

## 12. Modelo de datos

PostgreSQL sigue siendo la fuente de verdad. Cambios de esquema **aditivos** (`IF NOT EXISTS`). Outbox con unicidad `(suscripcion_id, interrupcion_id, version_relevante, tipo_evento)` y skip a nivel usuario. No se recreó la base Docker. No se migró el PostgreSQL de Windows.

Métrica observada en la base Docker: 4 ejecuciones `COMPLETADO`; 0 notificaciones en el snapshot (el outbox de demostración en este volumen está vacío o ya no cuenta en esos estados). Eso es dato real, no relleno.

---

## 13. Seguridad

- `.env` / `.env.docker` no versionados (`git ls-files` vacío para esos paths).
- Postgres sin `ports` en el host.
- UIs en `127.0.0.1`.
- Sin Docker socket.
- Token interno Bearer; CSRF en POST del panel.
- SMTP off por defecto.
- Destinatario de prueba Mailpit: dominio `example.test`.
- Grafana con contraseña de `.env.docker` (cambiar en cada instalación).
- n8n encryption key persistente.

---

## 14. GitHub Actions

Archivo: `.github/workflows/ci.yml`.  
Triggers: `push` a `main`/`master` y `pull_request`.  
Pasos: Python 3.12, Postgres 16.6 de servicio, pytest, `docker compose config`, validación Prometheus/Grafana, grep de `.env` versionado.  
Acciones fijadas: `actions/checkout@v4.2.2`, `actions/setup-python@v5.3.0`.

**Ejecución en github.com:** no verificada (no se hizo push). Clasificación: implementado, pendiente de CI remoto.

---

## 15. Tests ejecutados

```text
docker compose --env-file .env.docker run --rm -e DB_NAME=notificaciones_agua_test web python -m pytest -q
```

Resultado: **53 passed** (≈28 s). Suite independiente de `notificaciones_agua`.

---

## 16. Comandos ejecutados (sesión de cierre)

- `docker compose --env-file .env.docker up -d --build` → exit 0  
- `docker compose --env-file .env.docker ps`  
- HTTP: `/salud`, `/metrics`, Prometheus `/-/healthy` y `/api/v1/targets`, Grafana `/api/health` y `/api/search`, Mailpit `/api/v1/info` y `/api/v1/messages`  
- Envío SMTP laboratorio vía `docker compose exec` + `src.correo.enviar`  
- `git status` / `git ls-files` de secretos  

No se llamó a la API pública para generar carga. No se hizo `down -v`.

---

## 17. Resultados reales (extracto)

```text
salud {"ok":true,"vivo":true,"rol":"liveness","zona_timestamps":"UTC"}
metrics True (serie agua_postgres_up presente)
prom 200
grafana 11.3.1 database ok
mailpit Version v1.21.8; tras prueba: Messages 1
targets: prometheus up; web up
agua_pipeline_ejecuciones{estado="COMPLETADO"} 4
agua_notificaciones{estado="SIMULADA"} 0
```

---

## 18. Evidencias

- Compose recreó `web`, workers, y creó `mailpit`, `prometheus`, `grafana` y volúmenes asociados.
- Grafana listó 4 dashboards en carpeta «Avisos de agua».
- Mailpit almacenó el mensaje de laboratorio (ID `C5mPBDcZ9Nvpi6SVsefTHe`).
- Pytest 53 en contenedor `web` contra `notificaciones_agua_test`.

---

## 19. Archivos creados (fase 5 y consolidación)

`.github/workflows/ci.yml`, `src/correo.py`, `src/metricas_prom.py`, `observability/**`, `n8n/workflows/seguimiento-observabilidad.json`, plantillas `solicitudes.html`, `destinatarios.html`, `auditoria.html`, `estado.html`, `tests/test_correo.py`, `tests/test_metricas_prom.py`, este informe.

(Otros untracked — workers, n8n, observabilidad SQL — pertenecen a fases 2–4 y se conservan.)

---

## 20. Archivos modificados

`compose.yaml`, `requirements.txt`, `src/notificaciones.py`, `src/web/app.py`, `src/web/consultas.py`, plantillas y `estilos.css`, `.env.docker.example`, README, instalación, ADRs (ADR-012), arquitectura objetivo, plan de evolución, pruebas, `scripts/compose.ps1`.

---

## 21. Archivos eliminados y motivo

Ninguno en esta fase. No se borraron tests de fases anteriores, capturas, ni evidencia experimental. Código muerto no se eliminó de forma agresiva: se reutilizó el pipeline y el outbox.

**Conservados a propósito:** `docs/RESULTADOS_FASE_2.md` … `_FASE_4.md`, `docs/DIAGNOSTICO_ARQUITECTURA.md`, fixtures, `scripts/ejecutar_pipeline.ps1`, perfil Compose `pipeline`.

---

## 22. Variables de entorno

Ver `.env.docker.example` (sin secretos reales). Obligatorias a personalizar: `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, `SESSION_SECRET`, `INTERNAL_API_TOKEN`, `N8N_ENCRYPTION_KEY`, `GRAFANA_ADMIN_PASSWORD`. SMTP vacío/desactivado por defecto.

---

## 23. Instalación

Procedimiento Windows/PowerShell: `docs/INSTALACION_WINDOWS.md` (secciones 7 y 8). Resumen: clonar, copiar `.env.docker.example` → `.env.docker`, `docker compose --env-file .env.docker up -d --build`, importar workflows n8n, opcional Mailpit.

---

## 24. Operación

Comandos listos para copiar en `docs/INSTALACION_WINDOWS.md` §8. Atajo: `.\scripts\compose.ps1 up`. Diagnóstico: `.\scripts\diagnostico.ps1`.

---

## 25. Backup y recuperación

```powershell
docker exec notificacion-agua-db-1 pg_dump -U agua notificaciones_agua > respaldo.sql
```

Volúmenes a respaldar: `pgdata`, `n8n_data`, `capturas`, `grafana_data`, `prometheus_data`. Restauración SQL solo con autorización explícita. Parada habitual: `docker compose down` **sin** `-v`.

---

## 26. Limitaciones

- No hay API oficial SEDAPAL integrable; no hay segundo conector.
- Workers sin HTTP de health propio; recuperación = `restart unless-stopped`.
- Sin cadvisor (no se publica el socket Docker).
- `ACEPTADA_SMTP` ≠ entrega al buzón ni lectura.
- Idempotencia at-least-once, no exactly-once.
- `fec_estimada` no es restablecimiento confirmado.
- Callao fuera del matching territorial.
- Grafana/Prometheus no son ruta crítica: su caída no debe detener el pipeline (no hay `depends_on` desde workers hacia ellos).

---

## 27. Problemas conocidos

- Primera `up` puede tardar varios minutos en descargar imágenes fijadas.
- Healthcheck de Mailpit en Compose se dejó en `service_started` para el worker (la imagen reportó healthy en `ps` igualmente).
- El workflow de seguimiento no se reimportó en n8n en esta sesión.
- CI de GitHub no se observó en la pestaña Actions.
- Snapshot de notificaciones en el volumen Docker actual: ceros; no indica fallo del collector.

---

## 28. Checklist de aceptación

Ver sección 29.

---

## 29. Estado real de cada criterio

| # | Criterio | Estado |
|---|----------|--------|
| 1 | Compose levanta la arquitectura | **Verificado** |
| 2 | PostgreSQL conserva datos | **Verificado** (db Up 49 min; sin `-v`) |
| 3 | FastAPI funciona | **Verificado** (`/salud`) |
| 4 | Pipeline escenarios permitidos | **Verificado** (pytest + ejecuciones COMPLETADO=4) |
| 5 | pipeline-worker | **Verificado** (Up; cola 0 pendiente) |
| 6 | notification-worker | **Verificado** (Up; SMTP default simulación) |
| 7 | n8n inicia ejecuciones | **Implementado**; re-test UI no repetido en esta sesión (fase 2) |
| 8 | n8n consulta resultados | **Implementado** (workflows JSON) |
| 9 | Genera notificaciones | **Implementado** (outbox + tests fase 3); volumen demo con 0 filas ahora |
| 10 | Simulación | **Verificado** (pytest + modo default) |
| 11 | Mailpit inspecciona correos | **Verificado** (1 mensaje laboratorio) |
| 12 | SMTP externo sin cambiar código | **Implementado**; **pendiente externo** (sin credenciales) |
| 13 | Prometheus métricas reales | **Verificado** |
| 14 | Targets saludables | **Verificado** |
| 15 | Grafana consulta Prometheus | **Verificado** (proxy `up`) |
| 16 | Dashboards con datos | **Verificado** (series `agua_*` y `up`) |
| 17 | Logs correlación | **Implementado** (campos JSON; no se re-trazó un E2E de solicitud en este cierre) |
| 18 | GitHub Actions | **Implementado**; run remoto **pendiente** |
| 19 | Pytest | **Verificado** 53 passed |
| 20 | Panel profesional | **Implementado** (plantillas/CSS; no se recorrió cada ruta en navegador en este cierre) |
| 21 | Guía instalación | **Implementado** (`INSTALACION_WINDOWS.md`) |
| 22 | Recuperación reinicios | **Implementado** (`restart`, `up -d`); reinicio completo no forzado para no tumbar el stack en medio de la evidencia |
| 23 | No pérdida al down sin `-v` | **Diseño verificado**; down no ejecutado en el cierre |
| 24 | Sin secretos versionados | **Verificado** |
| 25 | Errores críticos documentados | **Verificado** (esta sección) |

---

## 30. Preparación para la entrega final del proyecto

El repositorio puede clonarse, configurarse con `.env.docker` y levantarse con Docker Desktop en Windows. La integración de servicios de la arquitectura de referencia está **implementada** y, en lo que este entorno permite, **verificada**.

No se declara el sistema libre de fallas. Quedan validaciones de operador (n8n UI, CI remoto, SMTP de proveedor, recorrido visual completo del panel, segundo conector oficial inexistente).

Listo para tesis en modo demostración local con simulación o Mailpit. No listo para envío masivo a ciudadanos ni para afirmar cobertura oficial SEDAPAL.

---

## Cierre operativo (22 nov 2026, tarde)

Guía de uso: `docs/GUIA_OPERATIVA_COMPLETA.md` (enlazada desde el README).

**Pytest:** `60 passed` en `notificaciones_agua_test` (incluye E2E fixture→matching→outbox→simulación, SMTP Mailpit en red Compose, y contrato de workflows n8n). No se truncó `notificaciones_agua`.

**Panel:** sesión administrativa verificada en navegador. Resumen con 2 interrupciones del fixture (125524, 125516), última ejecución `COMPLETADO`, calidad `válido`. `/estado`: web, n8n, Prometheus, Grafana y Mailpit **Disponible**.

**Mailpit:** 4 mensajes acumulados de laboratorio (prueba SMTP del adaptador + E2E en base de prueba). Destinatarios `@example.com`. SMTP de Compose sigue en simulación por defecto.

**n8n UI:** importar/activar el workflow de seguimiento sigue siendo paso de operador (`n8n/README.md`). JSON actualizado con manejo de error HTTP. Programado inactivo.

**GitHub Actions:** archivo listo; ejecución en github.com no observada (sin push).

**Eliminados:** ninguno.

**Creados en este cierre:** `docs/GUIA_OPERATIVA_COMPLETA.md`, `tests/test_e2e_flujo.py`, `tests/test_workflows_n8n.py`.

## Operación pública (posterior al cierre de integración)

Web ciudadana en `/`, administración en `/admin`, ciclo de confirmación/gestión/baja, `compose.prod.yaml` + Caddy, backups, SMTP de producción opt-in. Detalle: `docs/ESTADO_REAL_PROYECTO.md`. No hay instancia pública verificada en este entorno.
