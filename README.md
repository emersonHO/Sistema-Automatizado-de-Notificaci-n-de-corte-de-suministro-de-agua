# Sistema de notificación de interrupciones de agua (Lima Metropolitana)

Proyecto de tesis de Ingeniería de Software:

**Desarrollo de un sistema automatizado de notificación proactiva de interrupciones del servicio de agua potable para usuarios de Lima Metropolitana.**

El sistema consulta periódicamente una **fuente pública de un tercero** (`https://cortedeagua.net.pe/api.php`), normaliza las incidencias, las persiste en PostgreSQL, detecta novedades y cambios relevantes, las relaciona con zonas de interés registradas de forma voluntaria y genera avisos por correo (desactivado por defecto).

No reemplaza los canales oficiales de la empresa prestadora. Una coincidencia territorial **no confirma** que una vivienda esté afectada.

## Requisitos

- Python 3.12 o compatible
- PostgreSQL 16 o compatible **o** Docker Desktop para la pila Compose (fase 1)
- Windows 10/11 para la demostración local prevista (también funciona en Linux)

La pila Docker usa un volumen **nuevo** y **no publica** el puerto de PostgreSQL. No sustituye ni borra el servidor Postgres que ya tenga en Windows.

## Instalación

```powershell
cd Sistema-Notificacion-Agua
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edite `.env` con la contraseña de PostgreSQL. No confirme envío real de correo hasta tener autorización.

## PostgreSQL

```sql
CREATE DATABASE notificaciones_agua;
```

```powershell
python -m scripts.init_db
```

## Pipeline completo

```powershell
python -m src.pipeline
```

Opciones útiles:

```powershell
python -m src.pipeline --desde-archivo tests\fixtures\captura_minima.json
python -m src.pipeline --sin-outbox
```

El envío SMTP real exige `SMTP_ENABLED=true`, `MODO_ENVIO=real` y `--envio-real`. Por defecto el modo es **simulación**: los mensajes se guardan en `data/simulaciones/` y no se contacta a destinatarios reales.

## Aplicación web (sin Docker)

```powershell
python -m src.web
```

Abra `http://127.0.0.1:8000` (web ciudadana). Administración: `/admin`.

## Docker Compose (fases 1 a 5)

```powershell
copy .env.docker.example .env.docker
notepad .env.docker
docker compose --env-file .env.docker up -d --build
```

Defina `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, `SESSION_SECRET`, `INTERNAL_API_TOKEN`, `N8N_ENCRYPTION_KEY` y `GRAFANA_ADMIN_PASSWORD`.

| Servicio | Dirección |
|----------|-----------|
| Web ciudadana | http://127.0.0.1:8000 |
| Panel admin | http://127.0.0.1:8000/admin |
| n8n | http://127.0.0.1:5678 |
| Prometheus | http://127.0.0.1:9090 |
| Grafana | http://127.0.0.1:3000 |
| Mailpit | http://127.0.0.1:8025 |
| PostgreSQL | no publicado |

n8n: credencial Header Auth `FastAPI interno`; importar `n8n/workflows/*.json`. El programado permanece **inactivo** hasta validar. Detalle: `n8n/README.md`.

SMTP de laboratorio: `SMTP_ENABLED=true` y `MODO_ENVIO=mailpit` (destinatarios ficticios). Por defecto sigue la simulación (`SIMULADA`).

**Ciudadano:** [`docs/GUIA_CIUDADANO.md`](docs/GUIA_CIUDADANO.md)  
**Público gratis desde Windows (sin VPS ni dominio):** [`docs/GUIA_DESPLIEGUE_GRATUITO_WINDOWS.md`](docs/GUIA_DESPLIEGUE_GRATUITO_WINDOWS.md) — `.\scripts\iniciar-publico.ps1`  
**VPS de pago (opcional, más adelante):** [`docs/DEPLOYMENT_PRODUCTION.md`](docs/DEPLOYMENT_PRODUCTION.md) · [`docs/GUIA_OPERATIVA_PROPIETARIO.md`](docs/GUIA_OPERATIVA_PROPIETARIO.md)  
**Laboratorio local:** [`docs/GUIA_OPERATIVA_COMPLETA.md`](docs/GUIA_OPERATIVA_COMPLETA.md)

Instalación Windows (complemento): `docs/INSTALACION_WINDOWS.md`.

## Documentación de arquitectura

- `docs/ARQUITECTURA.md` — núcleo del MVP
- `docs/ARQUITECTURA_OBJETIVO.md` — diagrama C4/Mermaid objetivo
- `docs/PLAN_EVOLUCION_ARQUITECTONICA.md` — fases 0–5
- `docs/DECISIONES_ARQUITECTONICAS.md` — ADRs
- `docs/DIAGNOSTICO_ARQUITECTURA.md` — auditoría previa
- `docs/RESULTADOS_FASE_2.md` — evidencia de n8n y la cola
- `docs/RESULTADOS_FASE_3.md` — motor de notificaciones y worker de outbox
- `docs/OBSERVABILIDAD.md` — métricas, salud y fórmulas (fase 4)
- `docs/RESULTADOS_FASE_4.md` — evidencia de observabilidad
- `docs/RESULTADOS_FASE_5.md` — integración Prometheus, Grafana, Mailpit y CI
- `docs/GUIA_OPERATIVA_COMPLETA.md` — instalación, uso, demostración y diagnóstico

## Pruebas

```powershell
python -m pytest -q
```

Las pruebas de integración usan la base `notificaciones_agua_test` (no la base de demostración).

```powershell
python -m src.evaluacion
```

Los reportes se escriben en `data/evaluacion/`. Precisión y recall se calculan solo sobre casos etiquetados.

## Automatización en Windows

Vea `docs/INSTALACION_WINDOWS.md` y el script `scripts/ejecutar_pipeline.ps1`.

## Documentación adicional

- `docs/PLAN_IMPLEMENTACION.md`
- `docs/PRUEBAS.md`
- `docs/RESULTADOS_PRUEBAS.md`
- `docs/INSTALACION_WINDOWS.md`

## Limitaciones

- La API consultada no es oficial de SEDAPAL y puede cambiar o fallar.
- `fec_deteccion` y `fec_estimada` se tratan como fechas reportadas, no como inicio o restauración confirmados.
- Si la captura es incompleta, no se interpreta la ausencia de un identificador como cancelación.
- Callao se conserva en los datos originales y se excluye de la correspondencia territorial del MVP.
- `ACEPTADA_SMTP` no implica entrega al buzón.
