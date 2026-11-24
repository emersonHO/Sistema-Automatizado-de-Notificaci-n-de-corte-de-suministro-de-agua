# Avisos de interrupciones de agua (Lima Metropolitana)

MVP de tesis: consulta la fuente pública de un **tercero** `https://cortedeagua.net.pe/api.php` (no es API oficial de SEDAPAL), guarda incidencias en PostgreSQL, permite suscripciones voluntarias por distrito y envía avisos por correo cuando hay coincidencia territorial **potencial**. Eso **no confirma** que una vivienda esté sin servicio.

La fuente entrega como máximo **500** registros por respuesta. `last_sync` no se usa para omitir consultas (puede ir desfasado). Por defecto **no** se envía `dias`.

## Uso local (Docker Desktop)

Vea [`docs/GUIA_LOCAL.md`](docs/GUIA_LOCAL.md).

| En esta PC | URL |
|------------|-----|
| Ciudadanos | http://127.0.0.1:8000 |
| Administración | http://127.0.0.1:8000/admin |
| n8n | http://127.0.0.1:5678 |
| Prometheus / Grafana / Mailpit | :9090 / :3000 / :8025 |

PostgreSQL no se publica. No ejecute `docker compose down -v`.

## Despliegue (Render Free)

[`docs/GUIA_DESPLIEGUE_RENDER.md`](docs/GUIA_DESPLIEGUE_RENDER.md). n8n no va a Render; el ciclo de 15 min es GitHub Actions (`python -m src.ciclo_produccion`). Correo en Render: Resend (HTTPS).

## n8n local

[`n8n/README.md`](n8n/README.md). No active el programado contra la misma base que Actions.

## Pruebas

```powershell
python -m pytest -q
```

Usan `notificaciones_agua_test`, no la base de demostración.
