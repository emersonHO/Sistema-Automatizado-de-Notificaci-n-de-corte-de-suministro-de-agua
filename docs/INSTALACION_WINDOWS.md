# Instalación y demostración en Windows

La guía operativa paso a paso (instalación, n8n, fixture, Mailpit, Prometheus, Grafana, demo de tesis) está en `docs/GUIA_OPERATIVA_COMPLETA.md`. Este archivo resume el arranque local.

## 1. Python y PostgreSQL

1. Instale Python 3.12 y marque “Add python.exe to PATH”.
2. Instale PostgreSQL y recuerde la contraseña del usuario `postgres`.
3. En pgAdmin o `psql`:

```sql
CREATE DATABASE notificaciones_agua;
```

## 2. Proyecto

```powershell
cd C:\ruta\Sistema-Notificacion-Agua
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Valores mínimos:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=notificaciones_agua
DB_USER=postgres
DB_PASSWORD=su_password
SMTP_ENABLED=false
MODO_ENVIO=simulacion
```

```powershell
python -m scripts.init_db
```

## 3. Demostración

Terminal 1:

```powershell
python -m src.pipeline
python -m src.pipeline
```

La segunda ejecución debe reportar `sin_cambios` si la fuente no varió.

Terminal 2:

```powershell
python -m src.web
```

Abra http://127.0.0.1:8000

1. Panel: totales de la base real (no cifras inventadas).
2. Interrupciones: filtro por distrito y detalle con historial.
3. Suscripciones: registre un correo propio de prueba, confirme el enlace mostrado y **no** active SMTP real.
4. Vuelva a ejecutar el pipeline: si hay coincidencia, verá notificaciones `SIMULADA`.
5. Los archivos de simulación quedan en `data\simulaciones\`.

## 4. Programador de tareas

1. Abra el Programador de tareas.
2. Crear tarea básica → desencadenador diario o cada hora.
3. Acción: Iniciar un programa.

Programa:

```
powershell.exe
```

Argumentos:

```
-ExecutionPolicy Bypass -File C:\ruta\Sistema-Notificacion-Agua\scripts\ejecutar_pipeline.ps1
```

Inicie en: `C:\ruta\Sistema-Notificacion-Agua`

La tarea usa el modo simulación a menos que cambie `.env`.

## 5. Correo real (opt-in)

Solo con autorización explícita:

```
SMTP_ENABLED=true
MODO_ENVIO=real
SMTP_HOST=...
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=...
```

```powershell
python -m src.pipeline --envio-real
```

El estado `ACEPTADA_SMTP` significa que el servidor aceptó el mensaje, no que el buzón lo recibió.

## 6. Si la API no responde

El pipeline registra `ERROR`, conserva las interrupciones previas y no interpreta ausencias como cancelación.

Puede demostrar el flujo con el fixture:

```powershell
python -m src.pipeline --desde-archivo tests\fixtures\captura_minima.json
```

## 7. Docker Compose (fases 1 a 5)

Esto **no** usa ni borra el PostgreSQL instalado en Windows. El servicio `db` no publica puerto en el host.

1. Instale Docker Desktop.
2. En la carpeta del proyecto:

```powershell
copy .env.docker.example .env.docker
notepad .env.docker
```

Defina `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, `SESSION_SECRET`, `INTERNAL_API_TOKEN`, `N8N_ENCRYPTION_KEY` y `GRAFANA_ADMIN_PASSWORD` distintos a los de Windows.

```powershell
docker compose --env-file .env.docker up -d --build
```

| UI | URL |
|----|-----|
| Panel | http://127.0.0.1:8000 |
| n8n | http://127.0.0.1:5678 |
| Prometheus | http://127.0.0.1:9090 |
| Grafana | http://127.0.0.1:3000 |
| Mailpit | http://127.0.0.1:8025 |

n8n: cree el usuario propietario; credencial Header Auth `FastAPI interno` (`Authorization` = `Bearer` + `INTERNAL_API_TOKEN`) e importe `n8n/workflows/*.json`. El programado permanece **inactivo** hasta validar. Detalle: `n8n/README.md`.

Grafana: usuario de `.env.docker`; datasource Prometheus ya provisionado. Dashboards en carpeta «Avisos de agua».

Mailpit no envía a Internet. Para laboratorio: `SMTP_ENABLED=true`, `MODO_ENVIO=mailpit`, destinatarios `@example.com`. Recree `notification-worker`.

Pipeline (misma imagen, perfil):

```powershell
docker compose --env-file .env.docker --profile pipeline run --rm pipeline
```

Captura de prueba (sin llamar a la API):

```powershell
docker compose --env-file .env.docker --profile pipeline run --rm pipeline python -m src.pipeline --desde-archivo /app/tests/fixtures/captura_minima.json
```

Repita el comando: no debe crear incidencias duplicadas.

Para detener **sin** borrar el volumen Docker:

```powershell
docker compose --env-file .env.docker down
```

**No ejecute** `docker compose down -v` salvo que acepte perder la base Docker.

Atajo: `.\scripts\compose.ps1 up`

Salud y métricas:

- Liveness: http://127.0.0.1:8000/salud
- Readiness: http://127.0.0.1:8000/salud/listo
- Panel: http://127.0.0.1:8000/metricas (admin)
- JSON interno: `GET /internal/v1/observabilidad` con Bearer
- Recursos Docker: `.\scripts\diagnostico.ps1`

Logs del motor de avisos:

```powershell
docker compose --env-file .env.docker logs -f notification-worker
```

El `pipeline-worker` deja notificaciones en `PENDIENTE`. El `notification-worker` las procesa: `SIMULADA` (defecto) o `ACEPTADA_SMTP` si SMTP está habilitado hacia Mailpit/externo.

Métricas Prometheus: http://127.0.0.1:8000/metrics (raspadas en la red interna).

Respaldo PostgreSQL Docker (no borra datos):

```powershell
docker exec notificacion-agua-db-1 pg_dump -U agua notificaciones_agua > respaldo.sql
```

Restaurar exige autorización explícita y no se hace con `down -v`. Volumen n8n: `n8n_data`. Grafana: `grafana_data`. Prometheus: `prometheus_data`.

## 8. Operación habitual (PowerShell)

Desde la carpeta del repositorio, con `.env.docker` ya creado.

```powershell
# Levantar
docker compose --env-file .env.docker up -d --build

# Reconstruir imágenes
docker compose --env-file .env.docker build --no-cache web

# Estado
docker compose --env-file .env.docker ps

# Logs
docker compose --env-file .env.docker logs --tail 80 web
docker compose --env-file .env.docker logs --tail 80 pipeline-worker
docker compose --env-file .env.docker logs --tail 80 notification-worker

# Reiniciar un worker (no borra volúmenes)
docker compose --env-file .env.docker restart notification-worker
docker compose --env-file .env.docker restart pipeline-worker

# Métricas
Invoke-WebRequest http://127.0.0.1:8000/salud
Invoke-WebRequest http://127.0.0.1:8000/metrics
Invoke-WebRequest http://127.0.0.1:9090/-/healthy

# Panel
Start-Process http://127.0.0.1:8000

# Pipeline de laboratorio (perfil, no sustituye al worker)
docker compose --env-file .env.docker --profile pipeline run --rm pipeline

# Workflow programado: activarlo en n8n (http://127.0.0.1:5678) solo después de validar el manual
# SMTP laboratorio: SMTP_ENABLED=true y MODO_ENVIO=mailpit, luego
docker compose --env-file .env.docker up -d notification-worker
Start-Process http://127.0.0.1:8025

# Detener sin borrar datos
docker compose --env-file .env.docker down

# Recuperar tras un fallo de un contenedor
docker compose --env-file .env.docker up -d
```

**No use** `docker compose down -v` como parada habitual.

API interna (token Bearer de `INTERNAL_API_TOKEN`):

- `GET /internal/v1/notificaciones`
- `GET /internal/v1/notificaciones/{id}`
- `GET /internal/v1/destinatarios`

La migración desde el PostgreSQL de Windows requiere dump, restore y conteos; no está automatizada (hace falta autorización explícita).
