# Despliegue en Render Free

No se crea nada desde el código. Usted opera en GitHub, Render y Resend. Secretos solo en paneles, nunca en Git.

## 1. Cuentas

GitHub, Render, Resend.

## 2. GitHub

Repositorio (mejor privado). Compruebe que no hay `.env` ni `.env.docker` versionados.

## 3. Resend

API Key. Sin dominio verificado, el remitente de prueba (`onboarding@resend.dev`) solo sirve de forma fiable hacia **el correo de esa cuenta**.

## 4–8. Render

1. **PostgreSQL Free** (Ohio u Oregon). Guarde Internal URL (web) y External URL (Actions y backups). Caduca ~30 días.
2. **Web Service Free**, runtime Docker, Dockerfile de la raíz, comando `/app/scripts/start-web.sh`, health `/salud`.
3. Enlace Postgres. Región la misma que la base.

## 9. Variables del Web Service

Copie nombres de `.env.render.example`. Obligatorias: `DATABASE_URL` (la pone Render), `DB_SSLMODE=require`, `BASE_URL=https://<servicio>.onrender.com`, `SESSION_SECRET`, `ADMIN_PASSWORD`, `INTERNAL_API_TOKEN`, `OPERACION_PUBLICA=true`, `SESSION_HTTPS=true`, `TRUST_PROXY=true`, `PROTEGER_METRICS=true`, `CORREO_PROVEEDOR=resend`, `MODO_ENVIO=real`, `RESEND_API_KEY`, `SMTP_FROM`, `INTERNAL_PERMITIR_FIXTURE=false`, `API_URL=https://cortedeagua.net.pe/api.php`, `API_DIAS` vacío.

## 10. GitHub Secrets

`DATABASE_URL` (externa), `BASE_URL`, `RESEND_API_KEY`, `SMTP_FROM`.

El workflow `.github/workflows/pipeline-render.yml` corre cada 15 min **UTC** y a mano (`workflow_dispatch`).

## 11–19. Comprobar

1. Deploy → `https://<servicio>.onrender.com/salud`
2. Formulario `/` y listado `/interrupciones` (no deben ser solo 2 si la recolección trajo el lote de la API)
3. `/admin` exige login
4. `/metrics` y `/internal/v1/...` sin token → 401
5. Suscripción con su correo Resend
6. Actions → Pipeline Render → Run
7. Admin: última ejecución, recibidos vs almacenados

## 20. Backup

```powershell
$env:DATABASE_URL = "postgresql://...externa..."
.\scripts\respaldo-render.ps1
```

## 21. Errores frecuentes

| Síntoma | Qué hacer |
|---------|-----------|
| 403 de la API | La fuente bloquea algunas IPs; reintente; no hay paginación inventada |
| Listado con 2 filas | Eran datos de laboratorio; ejecute el pipeline (Actions) con URL base |
| No llega correo | Resend + destinatario de la cuenta; SMTP está bloqueado en Render |
| Cron no corre | Secretos de Actions; timezone UTC |

## 22. Al terminar

Backup, borrar Web y Postgres en Render, deshabilitar el workflow. No use `docker compose down -v` en su PC.
