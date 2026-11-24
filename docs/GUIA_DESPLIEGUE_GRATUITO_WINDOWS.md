# Guía de despliegue público gratuito desde Windows

Esta es la **guía principal** si quiere que ciudadanos reales usen el sistema **sin pagar VPS, dominio ni hosting**.

El servicio corre en **su computadora**. Cualquier persona en Internet llega por un **Cloudflare Quick Tunnel** (`*.trycloudflare.com`) con HTTPS. Si apaga el PC, pierde Internet o cierra Docker Desktop, la web y los avisos se detienen hasta que vuelva a iniciar.

No necesita: VPS, dominio comprado, DNS, abrir puertos del router, IP pública fija, Caddy en un servidor Ubuntu, ni `compose.prod.yaml`. Esos pasos están en `docs/GUIA_OPERATIVA_PROPIETARIO.md` y `docs/DEPLOYMENT_PRODUCTION.md` para **otro** escenario (de pago).

**No se ha verificado en esta entrega** que su túnel, su Gmail ni un flujo con destinatario real funcionen: eso requiere su cuenta, su red y su intervención. Los scripts y el filtrado de rutas sí están en el repositorio.

---

## Alternativa elegida

**Cloudflare Quick Tunnel** (imagen `cloudflare/cloudflared` en Compose, perfil `publico`).

Por qué:

- HTTPS para el ciudadano sin certificado propio.
- No abre puertos en el router.
- No exige IP fija ni dominio.
- El túnel apunta a **Caddy público** (`caddy-publico`), que solo reenvía rutas ciudadanas a FastAPI. n8n, Grafana, Prometheus, PostgreSQL y `/admin` no se publican.

Limitaciones reales (Quick Tunnel / trycloudflare.com):

- La URL **cambia** cada vez que el contenedor `tunel` arranca de nuevo.
- Está pensado para pruebas y demostraciones; no hay SLA. Cloudflare puede limitar o cortar el túnel.
- Debe actualizar `BASE_URL` y el archivo `url_publica.txt` cuando cambie la URL; si no, los correos llevarán enlaces rotos.
- No sustituye un dominio propio ni un túnel con cuenta Cloudflare nombrado (eso ya sería otra configuración).

Correo: **Gmail SMTP con contraseña de aplicación** (la opción más simple sin comprar dominio). Límites típicos del orden de **100–500 mensajes/día**; Gmail puede rechazar o marcar correo automático. No es un servicio transaccional profesional. Condiciones de uso de Google: usted es responsable de cumplirlas.

---

## Arquitectura (esta PC)

```
Ciudadano (celular / otra red)
        HTTPS
        *.trycloudflare.com
        cloudflared (contenedor tunel)
        Caddy :80 interno  → solo / /suscribir /confirmar /cuenta /baja /privacidad /interrupciones /static
        FastAPI (web)
        PostgreSQL (sin puerto en el host)

Usted en localhost:
  http://127.0.0.1:8000        web + admin
  http://127.0.0.1:8000/admin  panel
  http://127.0.0.1:5678        n8n
  http://127.0.0.1:9090        Prometheus
  http://127.0.0.1:3000        Grafana
  http://127.0.0.1:8025        Mailpit (solo laboratorio)
  http://127.0.0.1:8088        Caddy público (filtro, sin túnel)

Cada 15 min (cuando active el workflow): n8n → POST interno → cola → pipeline-worker
  → API https://cortedeagua.net.pe/api.php?dias=14 → PostgreSQL → matching → outbox
  → notification-worker → SMTP real (si SMTP_ENABLED=true y MODO_ENVIO=real)
```

Defensa en profundidad: Caddy niega lo no listado; FastAPI también niega `/admin`, `/internal/v1`, `/metrics`, etc. si el encabezado `Host` termina en `trycloudflare.com`.

---

## Parte A. Cuentas y herramientas

### Qué NO contratar

VPS, dominio, DNS de pago, hosting, certificados, IP fija, abrir DMZ/puertos, Brevo de pago.

### Cuentas que sí debe crear (intervención suya)

1. **Cuenta Google / Gmail** que usará como remitente. Active la verificación en dos pasos. Luego: [Contraseñas de aplicaciones](https://myaccount.google.com/apppasswords). Guarde la clave de 16 caracteres; no la suba a Git.
2. Opcional: cuenta Cloudflare **no es necesaria** para Quick Tunnel.

### Software en Windows

| Herramienta | Para qué | Cómo comprobar |
|-------------|----------|----------------|
| Windows 10/11 | Anfitrión | `winver` |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Contenedores | `docker version` y `docker compose version` |
| Git | Código | `git --version` |
| Visual Studio Code | Editar `.env.docker` | Abrir la carpeta del repo |
| PowerShell 5+ | Scripts | `$PSVersionTable.PSVersion` |
| Python 3.12 (opcional) | pytest en el host | `python --version` |

Docker Desktop: marque **Start Docker Desktop when you sign in** si quiere que sobreviva un reinicio de Windows (los contenedores con `restart: unless-stopped` volverán; el túnel **cambiará de URL**).

Política de scripts (una vez):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Verificar Docker

```powershell
docker info
docker compose version
```

Si `docker info` falla, abra Docker Desktop y espere a “Engine running”.

---

## Parte B. Configuración inicial

### Código

```powershell
cd C:\Workdesk\Sistema-Automatizado-de-Notificaci-n-de-corte-de-suministro-de-agua
```

Si clona de GitHub, use la carpeta real del clon. Abra esa carpeta en VS Code. Debe existir `compose.yaml` en la raíz.

### Archivo de variables

```powershell
copy .env.docker.example .env.docker
notepad .env.docker
```

`.env.docker` **no se versiona**. No pegue contraseñas en `docs/`, n8n JSON ni capturas de pantalla públicas.

### Secretos (valores reales, no los de ejemplo)

En PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Ejecútelo varias veces y asigne:

| Variable | Ejemplo (NO usar en público) | Debe ser |
|----------|------------------------------|----------|
| `POSTGRES_PASSWORD` | `cambiar_password_docker` | Aleatorio largo |
| `SESSION_SECRET` | `cambiar_sesion_larga_aleatoria` | Aleatorio largo |
| `ADMIN_PASSWORD` | `cambiar_admin` | Contraseña fuerte suya |
| `INTERNAL_API_TOKEN` | `cambiar_token_interno_largo` | Aleatorio largo (n8n lo usa) |
| `N8N_ENCRYPTION_KEY` | `cambiar_cifrado_n8n_largo` | Fijo; si lo cambia, n8n no lee credenciales viejas |
| `GRAFANA_ADMIN_PASSWORD` | `cambiar_grafana` | Contraseña fuerte |

`POSTGRES_USER=agua` y `POSTGRES_DB=notificaciones_agua` pueden quedarse si no los cambia. `ADMIN_USER=admin` es el usuario del panel local.

### Variables de operación

| Variable | Laboratorio | Operación pública (ciudadanos) |
|----------|-------------|-------------------------------|
| `API_URL` | `https://cortedeagua.net.pe/api.php` | Igual (fuente real; no la reemplace por fixtures) |
| `API_DIAS` | `14` | `14` |
| `INTERNAL_PERMITIR_FIXTURE` | `false` (o `true` solo en lab) | **`false`** |
| `OPERACION_PUBLICA` | `false` | **`true`** |
| `BASE_URL` | `http://127.0.0.1:8000` | Lo rellena `iniciar-publico.ps1` con `https://….trycloudflare.com` |
| `SMTP_ENABLED` | `false` o Mailpit | **`true`** |
| `MODO_ENVIO` | `simulacion` o `mailpit` | **`real`** (nunca `simulacion` para ciudadanos) |
| `SMTP_HOST` | `mailpit` | `smtp.gmail.com` |
| `SMTP_PORT` | `1025` | `587` |
| `SMTP_STARTTLS` | `false` | `true` |
| `SMTP_FROM` | `notificaciones@localhost` | Su Gmail completo |
| `SMTP_FROM_NAME` | `Avisos de agua Lima` | Nombre visible |
| `SMTP_USER` | vacío | Su Gmail |
| `SMTP_PASSWORD` | vacío | Contraseña de aplicación (16 caracteres, sin espacios) |
| `ADMIN_ALERT_EMAIL` | vacío | Su correo para alertas n8n (opcional) |

`ZONA_SISTEMA=America/Lima` no lo cambie.

Si `OPERACION_PUBLICA=true` y SMTP no está listo, el sistema **no marca SIMULADA como si hubiera enviado**. Verá aviso rojo en `/admin`.

Tras cambiar SMTP u `OPERACION_PUBLICA`, recree workers:

```powershell
docker compose --env-file .env.docker up -d web pipeline-worker notification-worker
```

---

## Parte C. Primera ejecución local (sin Internet público)

Aún con `OPERACION_PUBLICA=false` y SMTP apagado:

```powershell
cd C:\Workdesk\Sistema-Automatizado-de-Notificaci-n-de-corte-de-suministro-de-agua
.\scripts\compose.ps1 up
```

Espere 1–2 minutos. Compruebe:

```powershell
docker compose --env-file .env.docker ps
```

Todos los de la pila base deben estar `running` / healthy: `db`, `web`, `pipeline-worker`, `notification-worker`, `n8n`, `mailpit`, `prometheus`, `grafana`.

Abra **en esta PC**:

- http://127.0.0.1:8000 — formulario ciudadano
- http://127.0.0.1:8000/admin — panel (usuario `ADMIN_USER`)
- http://127.0.0.1:5678 — n8n (cree el usuario propietario la **primera** vez)
- http://127.0.0.1:9090 — Prometheus
- http://127.0.0.1:3000 — Grafana
- http://127.0.0.1:8025 — Mailpit

Logs:

```powershell
docker compose --env-file .env.docker logs -f web
```

Errores frecuentes:

| Síntoma | Qué hacer |
|---------|-----------|
| `docker` no se reconoce | Instale/inicie Docker Desktop |
| Puerto 8000 ocupado | Cierre el otro proceso o cambie el mapeo solo si sabe lo que hace |
| `web` unhealthy | `docker compose --env-file .env.docker logs web` |
| n8n pide cuenta | Es el alta del dueño; no la publique |
| Contraseña Postgres | Debe coincidir con el volumen `pgdata` ya creado; no la cambie a la ligera |

**Nunca** ejecute `docker compose down -v`. Eso borra PostgreSQL, suscripciones y n8n.

---

## Parte D. Exposición pública gratuita

1. Complete SMTP y ponga `OPERACION_PUBLICA=true` en `.env.docker` cuando vaya a recibir suscriptores reales (Parte E).
2. Un solo comando:

```powershell
cd C:\Workdesk\Sistema-Automatizado-de-Notificaci-n-de-corte-de-suministro-de-agua
.\scripts\iniciar-publico.ps1
```

El script: espera Docker Desktop, levanta la pila **y** el perfil `publico` (`caddy-publico`, `tunel`), lee la URL `https://….trycloudflare.com` de los logs, la escribe en `/app/data/url_publica.txt` y en `BASE_URL`.

Si no aparece la URL (~90 s):

```powershell
docker compose --env-file .env.docker logs tunel
.\scripts\aplicar-url-publica.ps1 -Url "https://LA_URL_QUE_SALGA.trycloudflare.com"
```

3. Diagnóstico:

```powershell
.\scripts\diagnostico-publico.ps1
```

`GET /admin` por `http://127.0.0.1:8088` debe ser **404**. `GET /` por `:8088` debe ser **200**.

4. HTTPS: abra la URL `https://….trycloudflare.com` en el navegador. El candado lo pone Cloudflare.

5. **Desde un teléfono con datos móviles** (Wi-Fi del celular **apagado**), abra la misma URL. Debe ver el formulario, no el panel.

6. En el teléfono, pruebe también `https://….trycloudflare.com/admin` y `/metrics`: debe fallar (404 o no encontrado), no el login.

Si reinicia el contenedor `tunel`, la URL **cambia**. Copie la nueva y:

```powershell
.\scripts\aplicar-url-publica.ps1 -Url "https://NUEVA.trycloudflare.com"
```

Los correos ya enviados con la URL vieja quedan inválidos; pida reenvío de confirmación en la web.

Detener solo el túnel (la pila local sigue):

```powershell
.\scripts\detener-publico.ps1 -SoloTunel
```

Detener todo (volúmenes **intactos**):

```powershell
.\scripts\detener-publico.ps1
```

---

## Parte E. Habilitar suscripciones reales

1. Contraseña de aplicación Gmail (Parte A).
2. En `.env.docker`: `SMTP_ENABLED=true`, `MODO_ENVIO=real`, host/puerto/STARTTLS/FROM/USER/PASSWORD como en la tabla.
3. Recree `web` y `notification-worker`.
4. Panel local: http://127.0.0.1:8000/admin — **no** debe aparecer el aviso rojo de SMTP.
5. Con la URL pública del túnel (datos móviles): suscríbase **con su propio correo**.
6. Revise bandeja y spam. El enlace de confirmación debe ser `https://….trycloudflare.com/confirmar/…`, **nunca** `127.0.0.1`.
7. Confirme. Vuelva a la web; puede usar el enlace de preferencias del correo (`/cuenta/…`).
8. En el panel local, Destinatarios: su correo aparece enmascarado; no exponga esa pantalla en Internet.

Preferencias / pausa / baja: solo con los enlaces firmados del correo (`/cuenta/{token}` y `/baja/{token}`).

Gmail puede devolver error de autenticación: revise 2FA, contraseña de aplicación (sin espacios), y que `SMTP_FROM` sea esa cuenta.

---

## Parte F. Flujo completo de extremo a extremo

Haga esto **usted**. No está marcado como “ya validado” en el repositorio.

| Paso | Qué hace | Dónde / comando | Resultado esperado | Si falla |
|------|----------|-----------------|--------------------|----------|
| 1 | Ciudadano abre la web | URL trycloudflare en datos móviles | Formulario, sin menú admin | Túnel caído: logs `tunel`; URL vieja: aplicar-url |
| 2 | Se suscribe | POST `/suscribir` | Mensaje genérico (no revela si el correo existe) | Logs `web`; rate limit 8/15 min |
| 3 | Correo de confirmación | Gmail | Llega con enlace HTTPS del túnel | SMTP: logs `web`; panel aviso SMTP |
| 4 | Confirma | Clic en `/confirmar/…` | Página de confirmado | Token caducado: reenviar |
| 5 | Activa | PostgreSQL | `correo_confirmado` y suscripción `confirmada` | Panel Destinatarios |
| 6 | n8n programado | http://127.0.0.1:5678 | Workflow **Pipeline interrupciones — programado** **activo** | Importar JSON; credencial Header Auth |
| 7 | Recolección | POST interno `modo=api` | Llama `API_URL` real | `INTERNAL_PERMITIR_FIXTURE=false` |
| 8–10 | Validar, persistir, cambios | pipeline-worker | Ejecución en `/ejecuciones` | Logs `pipeline-worker`; fuente caída: error en ejecución, no inventa cancelaciones |
| 11–13 | Matching y outbox | mismo ciclo | Notificación `PENDIENTE` si coincide su distrito | Sin coincidencia: no hay correo (correcto) |
| 14–16 | Worker SMTP | notification-worker | Estado `ACEPTADA_SMTP` y correo en el buzón | `REINTENTANDO`/`FALLIDA` + `intentos_notificacion` |
| 17 | Auditoría | `/notificaciones` e intentos | No interpretar `SIMULADA` como enviado | Si ve SIMULADA con `OPERACION_PUBLICA=true`, SMTP no está en real |
| 18 | Baja | `/baja/…` | Ya no entra en `suscripciones_activas` | Nueva ejecución no debe generar otra fila UNIQUE para el mismo hecho si ya notificado; baja evita futuros |

Credencial n8n **FastAPI interno**: Header `Authorization` = `Bearer ` + `INTERNAL_API_TOKEN`. Detalle: `n8n/README.md`. Active el programado **después** de un **Test workflow** exitoso con `modo=api`.

Para forzar un ciclo sin esperar 15 minutos: en n8n, **Test workflow** del programado (o el manual `pipeline-manual.json` en modo api, no fixture).

Idempotencia: UNIQUE `(suscripcion_id, interrupcion_id, version_relevante, tipo_evento)`.

---

## Operación diaria

1. Encender el PC.
2. Esperar Docker Desktop (icono estable).
3. `.\scripts\iniciar-publico.ps1 -SinRebuild` (más rápido si no cambió código).
4. Anotar la URL nueva si cambió.
5. `.\scripts\diagnostico-publico.ps1`
6. Abrir la URL en el teléfono (datos).
7. Dejar el PC encendido, sin suspender (desactive suspensión en Opciones de energía).

| Evento | Qué ocurre | Qué hacer |
|--------|------------|-----------|
| Apaga el PC | Todo cae | Al encender, iniciar-publico y nueva URL |
| Sin Internet | Túnel y API y SMTP fallan | Al volver, diagnóstico; trabajos `REINTENTANDO` |
| Docker se cierra | Contenedores paran | Abrir Docker Desktop; `iniciar-publico.ps1` |
| n8n caído | No hay disparo cada 15 min | `docker compose --env-file .env.docker restart n8n`; workflow debe seguir activo en `n8n_data` |
| Fuente `cortedeagua.net.pe` no responde | Ejecución en error; no se inventan bajas | Reintenta en el siguiente intervalo |
| SMTP falla | Outbox `REINTENTANDO` luego `FALLIDA` | Logs worker; Gmail; no se convierte en SIMULADA |
| Pendientes | Worker las reclama al volver | `FOR UPDATE SKIP LOCKED` + reconciliación de huérfanas |
| Túnel reinicia | **Otra URL** | `aplicar-url-publica.ps1`; avise a quien tenga un correo viejo sin confirmar |

---

## Monitoreo y administración (solo localhost)

| Qué | URL o comando | Vigilar |
|-----|----------------|---------|
| Panel | http://127.0.0.1:8000/admin | Pendientes, FALLIDA, aviso SMTP, última ejecución |
| n8n | http://127.0.0.1:5678 | Workflow activo; ejecuciones en error |
| Prometheus | http://127.0.0.1:9090 | Targets `web` |
| Grafana | http://127.0.0.1:3000 | Dashboard provisionado |
| Mailpit | http://127.0.0.1:8025 | **Solo lab**; no lo use con `MODO_ENVIO=real` |
| Logs | `docker compose --env-file .env.docker logs --tail 100 notification-worker` | `smtp_aceptado`, `smtp_no_configurado` |
| Contenedores | `.\scripts\diagnostico-publico.ps1` | unhealthy |
| Backup | `.\scripts\respaldo-windows.ps1` | Carpeta `backups/` (no versionada) |

No publique 5678, 9090, 3000, 8025, 8000 ni 5432 a Internet. El mapeo Compose ya es `127.0.0.1:…`.

Intervenir si: SMTP rojo en el panel; más de unas pocas `FALLIDA`; n8n inactivo; túnel sin URL; `INTERNAL_PERMITIR_FIXTURE=true` en público.

---

## Backups y conservación

Nunca borre los volúmenes: `pgdata`, `capturas`, `n8n_data`, `prometheus_data`, `grafana_data`.

```powershell
.\scripts\respaldo-windows.ps1
```

Copia `backups/` a un disco externo. Restaurar **no es automático**. Con autorización explícita y otro dump de seguridad:

```powershell
Get-Content .\backups\pg-YYYYMMDDTHHMMSS.sql -Raw | docker compose --env-file .env.docker exec -T db psql -U agua -d notificaciones_agua
```

n8n: el `.tgz` se extrae al volumen `notificacion-agua_n8n_data` con `docker run` + `tar` (pida ayuda si no está seguro; un tar mal extraído pisa credenciales).

No use `down -v` como “restore”.

---

## Comandos útiles

```powershell
.\scripts\iniciar-publico.ps1
.\scripts\iniciar-publico.ps1 -SinRebuild
.\scripts\diagnostico-publico.ps1
.\scripts\aplicar-url-publica.ps1 -Url "https://xxxx.trycloudflare.com"
.\scripts\detener-publico.ps1
.\scripts\detener-publico.ps1 -SoloTunel
.\scripts\respaldo-windows.ps1
docker compose --env-file .env.docker --profile publico ps
```

---

## Lo que aún requiere su intervención

1. Instalar Docker Desktop y, si quiere, arranque automático.
2. Crear `.env.docker` y secretos reales.
3. Cuenta Gmail, 2FA y contraseña de aplicación.
4. Alta del usuario dueño en n8n, credencial Header Auth, importar `n8n/workflows/*.json`, **activar** el programado de 15 minutos.
5. Ejecutar `iniciar-publico.ps1` y copiar la URL pública (y cada vez que cambie).
6. Probar el formulario desde datos móviles.
7. Confirmar un correo real y, cuando la fuente reporte una interrupción de su distrito, comprobar el aviso.
8. Desactivar suspensión de Windows mientras ofrezca el servicio.
9. Backups periódicos a disco externo.

Hasta que complete esos puntos, el sistema **no** está “en producción pública verificada”.
