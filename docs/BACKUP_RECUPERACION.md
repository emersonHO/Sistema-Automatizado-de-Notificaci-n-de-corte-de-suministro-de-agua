# Backup y recuperación

## Qué se guarda

| Volumen / archivo | Contenido |
|-------------------|-----------|
| `pgdata` | Base PostgreSQL |
| `backups` | `pg-YYYYMMDDThhmmssZ.sql.gz` + `.sha256` (rotación 14 días) |
| `capturas` | JSON de capturas |
| `n8n_data` | Credenciales y workflows importados |
| `grafana_data` | Preferencias Grafana |
| `caddy_data` | Certificados TLS |

El script `deploy/backup.sh` corre cada 24 h en el servicio `backup` de `compose.prod.yaml`. No ejecuta restore.

## PC Windows (despliegue gratuito)

```powershell
.\scripts\respaldo-windows.ps1
```

No usa `-v`. Restauración manual: `docs/GUIA_DESPLIEGUE_GRATUITO_WINDOWS.md`.

## Copiar fuera del VPS (PowerShell en su PC)

```powershell
scp usuario@IP_VPS:~/proyecto/backups/pg-*.sql.gz D:\respaldos\
```

## Restore (laboratorio, autorización explícita)

No lo ejecute contra la base en uso sin copia previa.

```bash
gunzip -c pg-XXXX.sql.gz | docker compose --env-file .env.production -f compose.prod.yaml exec -T db psql -U agua -d notificaciones_agua
```

Verifique `sha256sum -c archivo.sha256` antes. **Nunca** `docker compose down -v` como método de restore.
