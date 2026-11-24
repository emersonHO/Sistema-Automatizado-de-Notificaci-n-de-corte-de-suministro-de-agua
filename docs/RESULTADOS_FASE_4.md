# Resultados Fase 4 — observabilidad

**Fecha:** 22 de noviembre de 2026 (America/Lima)

## Pruebas

```text
docker compose --env-file .env.docker run --rm -e DB_NAME=notificaciones_agua_test web python -m pytest -q --tb=short
49 passed in 8.51s
```

Base: `notificaciones_agua_test`. No se usó `down -v`. No se truncó `notificaciones_agua`.

## Salud (host)

`GET /salud` → `{"ok":true,"vivo":true,"rol":"liveness","zona_timestamps":"UTC"}` HTTP 200  
`GET /salud/listo` → postgres true, `rss_kb`: 63772, HTTP 200  
`web` Compose: healthy (healthcheck `/salud/listo`)

## Recursos (un muestreo `docker stats --no-stream`)

| Contenedor | CPU | Memoria |
|------------|-----|---------|
| n8n | 0.55% | 395 MiB |
| pipeline-worker | 1.20% | 63 MiB |
| web | 0.20% | 43 MiB |
| db | 3.48% | 33 MiB |
| notification-worker | 0.00% | 23 MiB |

Instantánea, no promedio de tesis. Postgres sigue sin puerto en el host.
