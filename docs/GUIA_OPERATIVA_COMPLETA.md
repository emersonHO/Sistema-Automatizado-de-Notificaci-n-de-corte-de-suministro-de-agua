# Guía operativa completa

Sistema Automatizado de Notificación de Corte de Suministro de Agua.

Esta guía está pensada para quien clona el repositorio y debe **instalar, demostrar y operar** el sistema en Windows con Docker Desktop. No sustituye los ADR ni los informes de fase; describe el procedimiento real implementado.

La fuente `https://cortedeagua.net.pe/api.php` es de un **tercero**. No es una API oficial de SEDAPAL. Una coincidencia por distrito es una **posible** afectación, no la confirmación de un predio. `SIMULADA` no es un correo enviado. `ACEPTADA_SMTP` significa que el servidor SMTP aceptó el mensaje, no que el destinatario lo leyó.

**Demostración principal:** fixture `tests/fixtures/captura_minima.json` (Santa Anita e Independencia). No depende de interrupciones reales en Internet.

---

## Capítulo 1. Requisitos previos

| Requisito | Cómo comprobarlo en PowerShell |
|-----------|--------------------------------|
| Windows 10/11 | `winver` |
| PowerShell 5+ | `$PSVersionTable.PSVersion` |
| Git | `git --version` |
| Docker Desktop en ejecución | `docker version` |
| Docker Compose v2 | `docker compose version` |
| Navegador | Chrome, Edge o Firefox |

**Recursos mínimos recomendados:** 8 GB de RAM (16 GB cómodos: n8n + Grafana + Prometheus), 10 GB libres en disco, CPU de 4 núcleos.

Docker Desktop debe estar **Started**. Si `docker version` falla, abra Docker Desktop y espere el icono estable.

No se necesita PostgreSQL de Windows. Compose crea un motor **aislado** y **no publica** el puerto 5432 en el host. No ejecute `docker compose down -v`.

---

## Capítulo 2. Descarga y configuración

```powershell
git clone https://github.com/emersonHO/Sistema-Automatizado-de-Notificaci-n-de-corte-de-suministro-de-agua.git
cd Sistema-Automatizado-de-Notificaci-n-de-corte-de-suministro-de-agua
copy .env.docker.example .env.docker
notepad .env.docker
```

Personalice (valores distintos a los de ejemplo):

- `POSTGRES_PASSWORD`
- `ADMIN_PASSWORD`
- `SESSION_SECRET`
- `INTERNAL_API_TOKEN` (mínimo 8 caracteres; el workflow n8n lo usará como `Bearer …`)
- `N8N_ENCRYPTION_KEY`
- `GRAFANA_ADMIN_PASSWORD`

Deje SMTP así para operación segura:

```
SMTP_ENABLED=false
MODO_ENVIO=simulacion
SMTP_HOST=mailpit
SMTP_PORT=1025
```

No confirme `.env.docker` en Git. Compruebe:

```powershell
git check-ignore -v .env.docker
git ls-files .env .env.docker
```

El segundo comando no debe listar esos archivos.

---

## Capítulo 3. Inicio del sistema

```powershell
docker compose --env-file .env.docker up -d --build
```

Atajo: `.\scripts\compose.ps1 up`

Espere 30–90 s (la primera vez puede tardar varios minutos por la descarga de imágenes fijadas).

```powershell
docker compose --env-file .env.docker ps
```

Criterio de éxito: `db`, `web` y `n8n` **healthy**; `mailpit`, `prometheus`, `grafana` y ambos workers **Up**. PostgreSQL no debe mostrar `0.0.0.0:5432`.

Comprobaciones:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/salud
Invoke-RestMethod http://127.0.0.1:8000/salud/listo
Invoke-WebRequest http://127.0.0.1:9090/-/healthy
Invoke-RestMethod http://127.0.0.1:3000/api/health
Invoke-RestMethod http://127.0.0.1:8025/api/v1/info
```

| Si falla | Qué hacer |
|----------|-----------|
| `web` no healthy | `docker compose --env-file .env.docker logs web --tail 80` |
| `db` unhealthy | Espere `pg_isready`; no recree el volumen |
| Puerto ocupado | Cambie el mapeo solo si entiende el impacto; documente el nuevo puerto |
| Imagen no baja | Reintente `up -d --build` con red estable |

---

## Capítulo 4. Configuración inicial de n8n

1. Abra http://127.0.0.1:5678  
2. En la primera visita cree el **usuario propietario** (queda en el volumen `n8n_data`).  
3. **Credentials → Add credential → Header Auth**  
   - Nombre de la credencial: `FastAPI interno` (texto exacto).  
   - Name: `Authorization`  
   - Value: `Bearer ` + el valor de `INTERNAL_API_TOKEN` (un espacio después de Bearer).  
4. **Workflows → Import from File**, en este orden:  
   - `n8n/workflows/pipeline-manual.json`  
   - `n8n/workflows/pipeline-programado.json`  
   - `n8n/workflows/seguimiento-observabilidad.json`  
5. Si n8n pide mapear credenciales, elija `FastAPI interno`.  
6. Deje los tres workflows **inactivos** (el interruptor de Active en gris).  
7. Abra el manual: nodos `Encolar pipeline` y `Consultar estado` deben apuntar a `http://web:8000/internal/v1/...` (red Compose, no localhost).

El JSON **no** contiene el token. `N8N_BLOCK_ENV_ACCESS_IN_NODE=true` impide leer el entorno desde nodos.

El programado usa `modo=api` y `solo_si_libre=true`. **No lo active** hasta validar el manual con fixture.

---

## Capítulo 5. Preparación de usuarios y suscripciones

Use solo correos **ficticios** (`@example.com`).

1. http://127.0.0.1:8000/suscripciones  
2. Correo: `demo.santa@example.com`  
3. Marque el distrito **Santa Anita** (el fixture incluye `municipalidad: SANTA ANITA`). Opcional: Independencia.  
4. Envíe **Registrar**.  
5. Copie el **enlace de confirmación** que muestra la página (no se manda por SMTP en laboratorio).  
6. Ábralo en el navegador. Sin confirmar, el matching no genera avisos.  
7. Consulte el mismo correo en el formulario inferior: `Activa` y `Confirmada` en verdadero.

No hay listado público de correos. El administrador ve destinatarios enmascarados en `/destinatarios`.

Si no hay suscripción coincidente, el pipeline igual persiste interrupciones y deja **cero** filas nuevas en `notificaciones`.

Callao puede aparecer en capturas, pero **no** se acepta como distrito de suscripción de Lima Metropolitana y el matching lo marca fuera de ámbito.

---

## Capítulo 6. Ejecución completa con fixture (demostración principal)

### 6.1 Qué es el fixture

Archivo `tests/fixtures/captura_minima.json`: dos incidencias sintéticas (ids 125524 Santa Anita y 125516 Independencia), con la misma estructura observada en la fuente pública. **No** son avisos oficiales vigentes.

Compruebe que existe:

```powershell
Test-Path .\tests\fixtures\captura_minima.json
```

En la imagen Docker el archivo está en `/app/tests/fixtures/captura_minima.json`.

### 6.2 Habilitar fixture en FastAPI (solo laboratorio)

En `.env.docker`:

```
INTERNAL_PERMITIR_FIXTURE=true
```

```powershell
docker compose --env-file .env.docker up -d web
```

Sin esto, n8n recibe HTTP 400 `FIXTURE_NO_PERMITIDO`. Vuelva a `false` cuando termine la demo.

### 6.3 Encolar (n8n o equivalente)

En n8n, workflow **Pipeline interrupciones — manual (fixture)** → **Test workflow**.

Equivalente HTTP (PowerShell; sustituya el token; escribe en la base Docker `notificaciones_agua`):

```powershell
$tok = (Get-Content .env.docker | Where-Object { $_ -match '^INTERNAL_API_TOKEN=' }) -replace 'INTERNAL_API_TOKEN=',''
$h = @{ Authorization = "Bearer $tok"; 'Idempotency-Key' = "demo-$(Get-Random)" }
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/internal/v1/pipeline/ejecuciones -Headers $h -ContentType 'application/json' -Body '{"origen":"MANUAL","solo_si_libre":false,"modo":"fixture","ruta_fixture":"captura_minima.json"}'
```

Éxito: HTTP **202**, `estado: PENDIENTE`, `solicitud_id` numérico.

### 6.4 Solicitud y worker

Panel: http://127.0.0.1:8000/solicitudes  

```powershell
docker compose --env-file .env.docker logs --tail 50 pipeline-worker
```

Criterio: la solicitud pasa a `EN_PROCESO` y luego a `COMPLETADO` o `COMPLETADO_INCOMPLETO`. `pipeline-worker` registra `Pipeline de solicitud …`.

### 6.5 Recopilación y captura

El modo fixture **no llama** a cortedeagua.net.pe. La captura queda en el volumen `capturas` (`/app/data`). En `ejecuciones_proceso.ruta_captura` está la ruta.

### 6.6 Normalización y calidad

Panel **Ejecuciones**: leídos ≥ 2, columna **Calidad** `válido` (0 err). El JSON `detalle.calidad` en PostgreSQL incluye `errores`, `advertencias`, nulos de fechas (advertencia: las fechas **no** son inicio/fin confirmados).

```powershell
docker exec notificacion-agua-db-1 psql -U agua -d notificaciones_agua -c "SELECT id, estado, registros_leidos, registros_nuevos, coincidencias, notificaciones_creadas, detalle->'calidad' AS calidad FROM ejecuciones_proceso ORDER BY id DESC LIMIT 3;"
```

### 6.7 Detección de cambios

Primera corrida: `registros_nuevos` ≥ 1. Segunda corrida **con el mismo fixture**: `registros_nuevos = 0`, `registros_sin_cambios` ≥ 2, **sin** notificaciones duplicadas.

### 6.8 Matching territorial

Panel **Interrupciones** ids 125524 / 125516. Coincidencias en auditoría y en `coincidencias_territoriales`. Nivel distrito = **potencial**.

### 6.9 Outbox y notification-worker

Panel **Notificaciones**: filas `PENDIENTE` y luego `SIMULADA` (SMTP apagado).

```powershell
docker compose --env-file .env.docker logs --tail 50 notification-worker
```

### 6.10 Archivos de simulación

En el contenedor:

```powershell
docker compose --env-file .env.docker exec web python -c "from pathlib import Path; print(list(Path('data/simulaciones').glob('*.json'))[:5])"
```

El JSON es evidencia de simulación, no un acuse de recibo.

### 6.11 Panel, logs, métricas

- Resumen: http://127.0.0.1:8000  
- Métricas SQL: http://127.0.0.1:8000/metricas  
- Prometheus: http://127.0.0.1:9090/graph  
- Logs JSON: `docker compose --env-file .env.docker logs web --tail 80`

Correlacione `solicitud_id`, `ejecucion_id`, `notificacion_id` en los logs.

### 6.12 Alternativa sin n8n (mismo fixture, mismo worker)

```powershell
docker compose --env-file .env.docker --profile pipeline run --rm pipeline python -m src.pipeline --desde-archivo /app/tests/fixtures/captura_minima.json --sin-outbox
```

`--sin-outbox` / `procesar_envios=False` deja el envío al `notification-worker`. El perfil `pipeline` es CLI de laboratorio, no sustituye a n8n.

---

## Capítulo 7. Prueba SMTP con Mailpit (laboratorio)

No usa Internet. Destinatarios `@example.com`.

1. UI Mailpit: http://127.0.0.1:8025 (SMTP interno `mailpit:1025`, no publicado en el host).  
2. En `.env.docker` **temporalmente**:

```
SMTP_ENABLED=true
MODO_ENVIO=mailpit
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_STARTTLS=false
```

3. Recree **solo** el worker de notificaciones (no `down -v`):

```powershell
docker compose --env-file .env.docker up -d notification-worker
```

4. Genere una notificación nueva (otra suscripción o fixture en base de **prueba**).  
5. En Mailpit debe aparecer el mensaje. En el panel, estado `ACEPTADA_SMTP` e intentos con ese resultado.  
6. Vuelva a `SMTP_ENABLED=false` y `MODO_ENVIO=simulacion`, recree el worker.

Prueba automatizada (base `notificaciones_agua_test`, no toca `notificaciones_agua`):

```powershell
docker compose --env-file .env.docker run --rm -e DB_NAME=notificaciones_agua_test web python -m pytest tests/test_e2e_flujo.py::test_e2e_smtp_laboratorio_mailpit -q --tb=short
```

Una notificación `ACEPTADA_SMTP` no se vuelve a reclamar.

---

## Capítulo 8. Ejecución con fuente real

La URL está en `API_URL` (tercero). n8n programado o:

```powershell
docker compose --env-file .env.docker --profile pipeline run --rm pipeline
```

o POST interno con `"modo":"api"`.

Puede devolver cero incidencias, HTTP de error o captura incompleta. En error el pipeline queda `ERROR`, **no** interpreta ausencias como cancelación. Reejecutar el mismo conjunto no duplica avisos (hashes + unicidad de outbox).

Si la fuente no responde, vuelva al Capítulo 6.

No active el cron de n8n contra la fuente hasta haber validado el manual.

---

## Capítulo 9. Uso del panel administrativo

Inicio de sesión: http://127.0.0.1:8000/admin/login (`ADMIN_USER` / `ADMIN_PASSWORD`). Las suscripciones e interrupciones públicas siguen visibles; el resto exige sesión si hay contraseña.

| Ruta | Uso |
|------|-----|
| `/` | Totales reales de PostgreSQL |
| `/interrupciones` | Listado y detalle con historial |
| `/suscripciones` | Alta voluntaria y confirmación |
| `/ejecuciones` | Conteos, calidad, tiempos |
| `/solicitudes` | Cola n8n / API interna |
| `/notificaciones` | Filtro por estado; detalle con intentos |
| `/destinatarios` | Correos enmascarados |
| `/auditoria` | Trazas |
| `/metricas` | Snapshot SQL (no inventado) |
| `/estado` | Sondeo de n8n, Prometheus, Grafana, Mailpit |

No hay botones decorativos. Un KPI en cero es un cero real.

---

## Capítulo 10. Uso de Prometheus

http://127.0.0.1:9090 → **Status → Targets**: `web` y `prometheus` en **UP**.

Consultas reales (Graph):

```
up
agua_postgres_up
agua_scrape_ok
agua_pipeline_ejecuciones
agua_pipeline_duracion_segundos
agua_pipeline_registros
agua_solicitudes
agua_solicitudes_espera_segundos
agua_notificaciones
agua_notificaciones_reintentos
rate(http_requests_total[5m])
```

No hay labels con IDs de usuario, solicitud o notificación. `/metrics` solo en `127.0.0.1:8000`.

---

## Capítulo 11. Uso de Grafana

http://127.0.0.1:3000 — usuario `GRAFANA_ADMIN_USER` (defecto `admin`) y `GRAFANA_ADMIN_PASSWORD`.

Datasource **Prometheus** (uid `prometheus`, `http://prometheus:9090`) ya provisionado.

Carpeta **Avisos de agua**:

1. **Estado general** — `up` del web, Postgres, pendientes, ERROR de pipeline, HTTP por código.  
2. **Pipeline** — ejecuciones, duración, registros, espera en cola.  
3. **Notificaciones** — estados (SIMULADA ≠ leído), reintentos, tiempos.  
4. **Infraestructura (proceso web)** — RSS y CPU **del proceso FastAPI**, no de todos los contenedores (no hay cadvisor ni socket Docker).

Si un panel está vacío, el valor es ausente o cero; no hay series de relleno.

---

## Capítulo 12. Logs y diagnóstico

```powershell
docker compose --env-file .env.docker logs --tail 100 web
docker compose --env-file .env.docker logs --tail 100 pipeline-worker
docker compose --env-file .env.docker logs --tail 100 notification-worker
docker compose --env-file .env.docker logs --tail 50 n8n
docker compose --env-file .env.docker logs --tail 50 prometheus
.\scripts\diagnostico.ps1
```

| Síntoma | Causa habitual | Qué hacer |
|---------|----------------|-----------|
| PostgreSQL no listo | Arranque | Espere healthy; no `down -v` |
| FastAPI 503 `/salud/listo` | BD | Logs `web` y `db` |
| Worker detenido | Excepción | `restart pipeline-worker` o `notification-worker` |
| 401 n8n | Token | Recredencial Header Auth |
| 400 FIXTURE_NO_PERMITIDO | Flag | `INTERNAL_PERMITIR_FIXTURE=true` y recrear `web` |
| Fixture no encontrado | Nombre de archivo | Solo el basename bajo `tests/fixtures` |
| Sin coincidencias | Distrito / no confirmado | Santa Anita + confirmar enlace |
| Sin destinatarios | Nadie confirmado | Capítulo 5 |
| PENDIENTE eterno | Worker notif | Logs; SMTP no aplica en simulación |
| Mailpit vacío | SMTP off o worker no recreado | Capítulo 7; SMTP no está en el host:1025 |
| Prometheus target down | `web` no healthy | Compose `depends_on` + scrape `web:8000` |
| Grafana sin datos | Datasource / scrape | `/api/health` y Targets |

SMTP externo (solo documentación, **no** habilitar aquí): `SMTP_ENABLED=true`, `MODO_ENVIO=real`, host/puerto/usuario/contraseña/STARTTLS en `.env.docker`, nunca en Git ni en JSON de n8n.

---

## Capítulo 13. Parada y reinicio

```powershell
docker compose --env-file .env.docker down          # conserva volúmenes
docker compose --env-file .env.docker up -d
docker compose --env-file .env.docker build web
docker compose --env-file .env.docker up -d --build
docker compose --env-file .env.docker restart notification-worker
```

`docker compose down` detiene contenedores y **conserva** `pgdata`, `capturas`, `n8n_data`, `prometheus_data`, `grafana_data`.

**`docker compose down -v` borra esos volúmenes. Prohibido en operación habitual.** Tras reiniciar Windows o Docker Desktop: `docker compose --env-file .env.docker up -d` y vuelva a comprobar `/salud/listo`.

---

## Capítulo 14. Backup y recuperación

| Volumen | Contenido |
|---------|-----------|
| `pgdata` | PostgreSQL (interrupciones, cola, outbox, usuarios) |
| `capturas` | JSON de capturas y simulaciones |
| `n8n_data` | Usuario n8n, credenciales cifradas, workflows importados |
| `prometheus_data` | TSDB (~15 días) |
| `grafana_data` | Preferencias Grafana (dashboards también van en Git) |

```powershell
docker exec notificacion-agua-db-1 pg_dump -U agua notificaciones_agua > respaldo.sql
```

Restaurar solo con autorización explícita sobre una instancia de **laboratorio**, nunca con `down -v` improvisado. Workflows n8n se reimportan desde `n8n/workflows/*.json`; la credencial hay que volver a crearla.

---

## Capítulo 15. Guion de demostración de tesis (15–20 min)

Use fixture. No dependa de la API pública.

| Min | Acción | Pantalla / comando | Qué explicar |
|-----|--------|--------------------|--------------|
| 0–2 | Arquitectura | Diagrama / `compose.yaml` | n8n no ejecuta SQL; Postgres es la verdad; fuente de tercero |
| 2–3 | Salud | `docker compose ps`, `/salud/listo` | Healthchecks; Postgres no expuesto |
| 3–5 | Panel | `/` y `/interrupciones` | Cifras reales; matching ≠ predio |
| 5–6 | Suscripción | `/suscripciones` | Correo `@example.com`, Santa Anita, confirmar enlace |
| 6–9 | n8n manual | Test workflow fixture | 202, poll, COMPLETADO vs ERROR |
| 9–11 | Procesamiento | `/solicitudes`, `/ejecuciones` | Worker, calidad, nuevos vs sin cambios |
| 11–13 | Matching y outbox | Interrupción 125524, `/notificaciones` | Potencial; PENDIENTE → SIMULADA |
| 13–14 | Worker | logs `notification-worker` | Archivo de simulación; no es envío |
| 14–16 | Prometheus | Targets + `agua_pipeline_ejecuciones` | Métricas sin IDs |
| 16–18 | Grafana | 4 dashboards | Complemento; un cero es un cero |
| 18–20 | Trazabilidad | Logs JSON / auditoría | IDs de solicitud-ejecución-notificación; limitaciones |

Opcional (si hay tiempo): Mailpit Capítulo 7, luego **restaurar simulación**.

---

## Comandos rápidos

```powershell
docker compose --env-file .env.docker up -d --build
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker down
docker compose --env-file .env.docker run --rm -e DB_NAME=notificaciones_agua_test web python -m pytest -q --tb=short
```

Documentos relacionados: `docs/INSTALACION_WINDOWS.md`, `n8n/README.md`, `docs/OBSERVABILIDAD.md`, `docs/RESULTADOS_FASE_5.md`.
