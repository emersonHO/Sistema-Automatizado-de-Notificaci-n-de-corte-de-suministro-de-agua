# Resultados Fase 2 — n8n y cola de pipeline

**Fecha:** 17–18 de noviembre de 2026 (America/Lima)  
**Rama de trabajo:** `cursor/fase1-contenedores-5701`

## Objetivo

Orquestar el pipeline existente desde n8n sin duplicar la lógica Python: HTTP interno autenticado, cola `solicitudes_ejecucion`, worker persistente y `ejecutar_pipeline()`.

## Arquitectura implementada

```text
n8n (127.0.0.1:5678, SQLite en n8n_data)
  -> Bearer INTERNAL_API_TOKEN
  -> FastAPI http://web:8000/internal/v1/pipeline/ejecuciones  (202)
  -> solicitudes_ejecucion
  -> pipeline-worker (FOR UPDATE SKIP LOCKED)
  -> ejecutar_pipeline(solicitud_id) + pg_try_advisory_lock(570114)
  -> ejecuciones_proceso.solicitud_id
```

SMTP real sigue desactivado. Mailpit, Prometheus, Grafana y notification-worker no se añadieron.

## Componentes añadidos

| Pieza | Detalle |
|-------|---------|
| Tabla `solicitudes_ejecucion` | Cola, firma de idempotencia, `backend_pid` |
| `ejecuciones_proceso.solicitud_id` | UNIQUE parcial |
| `src/solicitudes.py` | Alta, GET, reclamo, cierre, reconciliación |
| `src/web/interno.py` | API Bearer |
| `src/worker_pipeline.py` | Bucle persistente |
| Servicio Compose `pipeline-worker` | Misma imagen que `web` |
| Servicio `n8n` | `n8nio/n8n:2.48.4` (manifest amd64/arm64 verificado antes del pull) |
| Volumen `n8n_data` | `/home/node/.n8n` |
| Workflows | `n8n/workflows/*.json` (`active: false`) |

## Endpoints

| Método | Ruta | Auth |
|--------|------|------|
| POST | `/internal/v1/pipeline/ejecuciones` | Bearer |
| GET | `/internal/v1/pipeline/ejecuciones/{id}` | Bearer |
| GET | `/internal/v1/pipeline/ejecuciones` | Bearer |

El POST no ejecuta el pipeline. Códigos: 202 nueva, 200 idempotente, 401, 409, 404, 503 si falta token de servidor.

## Pruebas ejecutadas

| ID | Resultado |
|----|-----------|
| Pytest en imagen web contra `notificaciones_agua_test` | **30 passed** (6.68 s). No se truncó `notificaciones_agua`. |
| `/salud` host y desde contenedor n8n | 200 `ok/postgres true` |
| POST/GET interno sin Bearer | 401 |
| GET listado con token (desde `web`) | 200 `solicitudes: []` |
| `db` PortBindings | `{}` (no publicado) |
| n8n `healthz` | 200 `{"status":"ok"}` UI `127.0.0.1:5678` |
| Restart n8n | vuelve `healthy`; permanece `database.sqlite` |
| Volúmenes | `pgdata`, `capturas`, `n8n_data` |
| Dominio | 50 zonas; existe `solicitudes_ejecucion` |
| Worker | arrancó; logs JSON |
| Workflow n8n en la UI | **no importado ni ejecutado** en esta sesión (JSON listo, `active: false`) |
| POST `modo=api` contra la API pública | **no ejecutado** (evitar escritura no controlada en el dominio) |
| Flujo fixture + worker | **sí**, en pytest (`test_worker.py`) sobre BD de prueba |

## Limitaciones

- El workflow programado permanece inactivo. Hay que importarlo a mano en n8n.
- Auth n8n: credencial Header Auth `FastAPI interno` (no `$env`). `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`.
- El workflow **manual** usa `modo=fixture` y exige `INTERNAL_PERMITIR_FIXTURE=true` en `web`.
- **Fase 2 no está validada de extremo a extremo en la UI de n8n** hasta que se importe el JSON, se ejecute Test workflow y coincidan las filas SQL.
- El perfil `pipeline` (CLI) no crea fila en `solicitudes_ejecucion`; el lock 570114 serializa igual.
- No se afirma exactly-once: idempotencia HTTP + UNIQUE de `solicitud_id` + hashes del pipeline.

## Pendientes

- Importar credencial + workflow manual, ejecutar Test workflow con fixture y verificar el JOIN SQL.
- Activar el programado solo después de esa validación (el programado usa `modo=api`).
- Completar evidencias F2-WF-* en n8n.
