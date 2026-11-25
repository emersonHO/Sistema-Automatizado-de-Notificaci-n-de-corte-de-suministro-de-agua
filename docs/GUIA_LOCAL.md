# Uso local (Windows, Docker Desktop)

## Arranque

```powershell
cd C:\Workdesk\Sistema-Automatizado-de-Notificaci-n-de-corte-de-suministro-de-agua
copy .env.docker.example .env.docker
notepad .env.docker
```

Defina contraseñas distintas de los ejemplos. Deje `API_DIAS` vacío. `INTERNAL_PERMITIR_FIXTURE=false` en operación.

```powershell
docker compose --env-file .env.docker up -d --build
```

Abra:

- Ciudadano: http://127.0.0.1:8000
- Operador: http://127.0.0.1:8000/admin
- Prometheus: http://127.0.0.1:9090
- Grafana: http://127.0.0.1:3000 (usuario/clave de `.env.docker`)
- n8n: http://127.0.0.1:5678 (vea `n8n/README.md`; no lo active a la vez que GitHub Actions contra Render)
- Mailpit: http://127.0.0.1:8025

En el registro indique **sector y/o área**. «Todo el distrito» es opcional y genera avisos potenciales de todo el distrito.

## Recolección (fuente real)

```powershell
docker compose --env-file .env.docker --profile pipeline run --rm pipeline python -m src.pipeline --sin-outbox
```

Si la fuente responde 403 (bloqueo de bots), la consulta fallará; los datos previos se conservan. n8n local: `n8n/README.md`.

Laboratorio con Mailpit: `SMTP_ENABLED=true`, `MODO_ENVIO=mailpit`. No use destinatarios reales.

## Parar (sin borrar datos)

```powershell
docker compose --env-file .env.docker down
```

Nunca `down -v`.
