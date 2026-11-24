# Guía del propietario (despliegue en Internet)

**Escenario actual sin pago:** no use esta guía. Use [`docs/GUIA_DESPLIEGUE_GRATUITO_WINDOWS.md`](GUIA_DESPLIEGUE_GRATUITO_WINDOWS.md) (Cloudflare Quick Tunnel desde Windows). Lo que sigue es el camino **de pago** (VPS + dominio) para cuando decida contratar infraestructura.

Esta guía asume Windows en su PC y un VPS Linux (Ubuntu 24.04). Los secretos los genera usted. Cursor no puede registrar el dominio ni pagar el hosting.

## 1–5. Hosting, VPS y dominio

Recomendación: **VPS Ubuntu 24.04** (DigitalOcean, Hetzner, Linode, Contabo).  
Tamaño razonable: **2 vCPU, 4 GB RAM, 40 GB SSD** (~5–8 USD/mes). n8n + Grafana caben justos; 8 GB es más holgado.

Dominio: cualquier registrador (.pe, Namecheap, etc.). Cree un registro **A** `@` (y `www` si quiere) hacia la IP pública del VPS. Espere la propagación DNS (`nslookup tudominio`).

Gastos anuales típicos: VPS 60–100 USD + dominio 10–40 USD + SMTP (Brevo/Sendinblue tiene cuota gratuita limitada; luego de pago).

## 6. SSH desde Windows (PowerShell)

```powershell
ssh usuario@IP_DEL_VPS
```

La primera vez acepte la huella. Use clave SSH (`ssh-keygen` y copie la pública al VPS).

## 7. Firewall en el VPS (consola Linux)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

No abra 5432, 5678, 9090 ni 3000.

## 8–10. Docker y código

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# cierre sesión SSH y vuelva a entrar
git clone https://github.com/emersonHO/Sistema-Automatizado-de-Notificaci-n-de-corte-de-suministro-de-agua.git
cd Sistema-Automatizado-de-Notificaci-n-de-corte-de-suministro-de-agua
```

## 11–14. Variables y secretos

```bash
cp .env.production.example .env.production
nano .env.production
openssl rand -hex 32   # repita para cada secreto
```

Rellene `DOMINIO`, `CADDY_EMAIL`, `BASE_URL=https://DOMINIO`, contraseñas, `INTERNAL_API_TOKEN`, `N8N_ENCRYPTION_KEY`, SMTP. Deje `SMTP_ENABLED=false` hasta verificar el dominio del remitente.

## 15–17. SMTP, Caddy, HTTPS

1. Cree cuenta en Brevo (u otro SMTP). Verifique el dominio/remitente.
2. Ponga host/usuario/contraseña en `.env.production`.
3. DNS A debe apuntar al VPS **antes** de `up`.
4. Arranque:

```bash
docker compose --env-file .env.production -f compose.prod.yaml up -d --build
docker compose --env-file .env.production -f compose.prod.yaml ps
```

Caddy obtiene el certificado solo. Si falla, `docker compose ... logs caddy`. Causas típicas: DNS aún no apunta, puerto 80 filtrado.

## 18–20. n8n y pipeline

Publique n8n solo en loopback (añada `127.0.0.1:5678:5678` al servicio n8n **en el VPS** si hace falta la UI) y conéctese:

```powershell
ssh -L 5678:127.0.0.1:5678 usuario@IP_VPS
```

Abra http://127.0.0.1:5678. Credencial Header Auth `FastAPI interno`. Importe `n8n/workflows/pipeline-programado.json` (15 min, `modo=api`). Actívelo **después** de una prueba manual `modo=api`.

No active el workflow de fixture en producción. `INTERNAL_PERMITIR_FIXTURE=false`.

## 21–24. Verificar ciudadano

1. `https://DOMINIO` — formulario.
2. Suscriba un correo **suyo**.
3. Confirme.
4. Espere una corrida del pipeline o encole `modo=api`.
5. Si hay matching, el worker envía (con SMTP_ENABLED=true).
6. Use el enlace de baja del correo.

## 25–32. Observabilidad, logs, backup, actualización

Túnel: `-L 9090:127.0.0.1:9090 -L 3000:127.0.0.1:3000` (requiere publicar esos puertos en 127.0.0.1 del VPS igual que n8n).

```bash
docker compose --env-file .env.production -f compose.prod.yaml logs --tail 100 web
docker compose --env-file .env.production -f compose.prod.yaml restart notification-worker
docker compose --env-file .env.production -f compose.prod.yaml pull
docker compose --env-file .env.production -f compose.prod.yaml up -d --build
docker compose --env-file .env.production -f compose.prod.yaml down   # conserva volúmenes
```

**Prohibido:** `down -v`.

Backups: volumen `backups`; copie con `scp` (ver `docs/BACKUP_RECUPERACION.md`).

Tras reinicio del VPS, Docker `restart: unless-stopped` levanta solos.

## 33–35. Costos, cuentas y riesgos

Cuentas: GitHub, registrador de dominio, VPS, SMTP.  
Riesgos: fuente de terceros inestable; spam si el SMTP no está autenticado (SPF/DKIM); datos personales (Ley 29733); saturación de la API pública si baja el intervalo de 15 min; `ACEPTADA_SMTP` ≠ leído. Empiece con pocos suscriptores de prueba.
