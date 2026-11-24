# Despliegue de producción (VPS + Docker Compose + Caddy)

Archivo: `compose.prod.yaml`. Guía paso a paso: `docs/GUIA_OPERATIVA_PROPIETARIO.md`.

Puertos públicos: **80 y 443** (Caddy). Nada más.

```bash
cp .env.production.example .env.production
# editar secretos, DOMINIO, SMTP
docker compose --env-file .env.production -f compose.prod.yaml up -d --build
```

DNS: registro A del dominio al IP del VPS **antes** de levantar Caddy (Let's Encrypt).

n8n, Grafana y Prometheus: túnel SSH, no Internet.

```powershell
ssh -L 5678:127.0.0.1:5678 -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 usuario@IP_VPS
```

En el servidor, para n8n hay que publicar temporalmente en localhost del VPS o usar `docker compose exec` / extraer logs. n8n en prod no tiene `ports`. Para administrarlo:

```bash
ssh -L 5678:n8n:5678  # no funciona: n8n no está en host
```

Use un contenedor sidecar o `docker compose -f compose.prod.yaml exec` no abre UI. Opción segura: añadir temporalmente

```yaml
ports:
  - "127.0.0.1:5678:5678"
```

solo en el VPS, nunca 0.0.0.0, y acceder con `ssh -L 5678:127.0.0.1:5678`.

Backup diario: servicio `backup` escribe en volumen `backups`. Copie esos archivos fuera del VPS (`scp`).
