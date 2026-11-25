# Qué hacer ahora (el error de Render)

El contenedor **sí se construye**. Falla al arrancar porque el Web Service **no tiene** la variable `DATABASE_URL` con la URL de Postgres de Render.

No copie `.env.docker`. Eso es solo para Docker en su PC (`localhost`). En Render no hay Postgres dentro del servicio web.

---

## Parte A — Arreglar el servicio que ya existe

Haga esto en el navegador, en [https://dashboard.render.com](https://dashboard.render.com).

### Paso 1: Abrir el proyecto

1. Entre a Render.
2. En el menú izquierdo pulse **Dashboard**.
3. Pulse el **Web Service** (el que despliega este repositorio; el icono es de un globo o “Web”).
4. No pulse todavía “Manual Deploy”. Primero hay que conectar la base.

### Paso 2: Crear PostgreSQL (si aún no existe)

1. Arriba a la derecha pulse **New +**.
2. Pulse **PostgreSQL**.
3. **Name:** por ejemplo `notificacion-agua-db`.
4. **Database:** deje el valor que Render propone, o ponga `notificaciones_agua`.
5. **User:** deje el que propone Render.
6. **Region:** **la misma** que el Web Service (Oregon, Ohio, etc.). Si el web está en Oregon, la base también Oregon.
7. **Instance type:** **Free**.
8. Pulse **Create Database**.
9. Espere a que el estado sea **Available** (verde). Puede tardar uno o dos minutos.

Si **ya** tiene un PostgreSQL en el dashboard, no cree otro. Use ese. Siga al paso 3.

### Paso 3: Copiar la URL interna (sin pegarla en el chat ni en Git)

1. En el Dashboard pulse el **PostgreSQL** (no el Web Service).
2. Abra la pestaña **Info** (a veces se llama **Connections**).
3. Busque **Internal Database URL**.
4. Pulse el icono de copiar. Empieza por `postgres://` o `postgresql://` y el host **no** es `localhost`. Algo como:
   - `….oregon-postgres.render.com` o
   - `dpg-….render.com`
5. No copie **External Database URL** para el web. Esa es para GitHub Actions (parte C).
6. No envíe esta URL a nadie: lleva usuario y contraseña.

### Paso 4: Poner `DATABASE_URL` en el Web Service (esto es lo que falta)

Haga **una** de las dos formas. La A suele ser más simple.

**Forma A — Enlazar la base (preferida)**

1. Dashboard → pulse de nuevo el **Web Service**.
2. Pestaña **Environment**.
3. Si ve una variable llamada `DATABASE_URL` cuyo valor está **vacío**, pulse los tres puntos → **Delete**. Una `DATABASE_URL` vacía es peor que no tenerla.
4. Si hay `DB_HOST` con valor `localhost`, **Delete**.
5. Pulse **Add Environment Variable** (o **Add from Database** / **Link PostgreSQL**, el texto depende del idioma).
6. Si aparece un selector de bases:
   - elija `notificacion-agua-db` (o el nombre del paso 2);
   - elija la propiedad **Connection String** / **Internal Database URL**;
   - el **Key** debe ser exactamente `DATABASE_URL`.
7. Pulse **Save changes**.

**Forma B — Pegar la URL a mano**

1. Web Service → **Environment**.
2. **Add Environment Variable**.
3. **Key:** `DATABASE_URL` (mayúsculas, sin espacios).
4. **Value:** pegue la **Internal Database URL** del paso 3 (Ctrl+V). Una sola línea, sin comillas, sin espacios al inicio o al final.
5. **Save changes**.

**Comprobación (obligatoria):** en Environment, `DATABASE_URL` debe existir y el valor **no** puede estar vacío. El host **no** puede ser `127.0.0.1` ni `localhost`.

### Paso 5: Resto de variables del Web Service

Siga en **Environment**. Añada cada clave. No pegue `DATABASE_URL` otra vez.

En su PC, PowerShell, genere secretos (tres veces, uno para cada clave):

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copie cada resultado a `SESSION_SECRET`, `ADMIN_PASSWORD` e `INTERNAL_API_TOKEN`.

| Key | Value |
|-----|--------|
| `DB_SSLMODE` | `require` |
| `BASE_URL` | `https://` + el nombre de su servicio + `.onrender.com` (lo ve arriba en el Web Service, botón **Visit**). Ejemplo: `https://avisos-agua.onrender.com`. Sin barra al final. |
| `OPERACION_PUBLICA` | `true` |
| `SESSION_HTTPS` | `true` |
| `TRUST_PROXY` | `true` |
| `PROTEGER_METRICS` | `true` |
| `WEB_HOST` | `0.0.0.0` |
| `SESSION_SECRET` | el texto largo que generó |
| `ADMIN_USER` | `admin` |
| `ADMIN_PASSWORD` | el texto largo que generó |
| `INTERNAL_API_TOKEN` | el texto largo que generó |
| `INTERNAL_PERMITIR_FIXTURE` | `false` |
| `API_URL` | `https://cortedeagua.net.pe/api.php` |
| `API_DIAS` | déjela **sin valor** (vacía). No ponga `0` si el panel no acepta vacío; en ese caso **no cree** esta clave. |
| `ZONA_SISTEMA` | `America/Lima` |
| `CORREO_PROVEEDOR` | `resend` |
| `MODO_ENVIO` | `real` |
| `SMTP_ENABLED` | `false` |
| `RESEND_API_KEY` | la clave de [https://resend.com/api-keys](https://resend.com/api-keys) (empieza por `re_`) |
| `SMTP_FROM` | `Avisos <onboarding@resend.dev>` (si aún no verificó dominio en Resend) |
| `SMTP_FROM_NAME` | `Avisos de agua Lima` |
| `LOG_FORMAT` | `json` |
| `LOG_LEVEL` | `INFO` |

Opcional: `ADMIN_ALERT_EMAIL` = el correo de su cuenta Resend.

Pulse **Save changes**.

### Paso 6: Health check y comando de arranque

1. Web Service → **Settings**.
2. **Health Check Path:** `/salud`
3. **Docker Command:** déjelo **vacío** (usa el `CMD` del Dockerfile). No ponga `uvicorn` a mano.
4. **Save**.

### Paso 7: Volver a desplegar

1. Web Service → **Manual Deploy** → **Deploy latest commit**.
2. Abra **Logs**.
3. Debe desaparecer el `RuntimeError` de `DATABASE_URL`.
4. Debe aparecer algo como PostgreSQL conectado (el host será de Render, no `127.0.0.1`).
5. Cuando el servicio esté **Live**, abra `https://SU-SERVICIO.onrender.com/salud` en el navegador.

Si vuelve a salir el mismo `RuntimeError`, vuelva al paso 4: `DATABASE_URL` sigue vacía o no se guardó.

---

## Parte B — Resend (correo)

1. Entre a [https://resend.com](https://resend.com) y cree una API Key.
2. Péguela en Render como `RESEND_API_KEY` (paso 5).
3. Sin dominio verificado, los envíos fiables son hacia **el mismo correo** con el que se registró en Resend, usando remitente `onboarding@resend.dev`.

---

## Parte C — GitHub Actions (ciclo cada 15 minutos)

El web en Render **no** descarga cortes solo. Eso lo hace el workflow `.github/workflows/pipeline-render.yml`.

1. En el PostgreSQL de Render, pestaña **Info**, copie **External Database URL** (no la Internal).
2. GitHub → su repositorio → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**. Cree cuatro:

| Name | Value |
|------|--------|
| `DATABASE_URL` | External Database URL de Render (paso C.1) |
| `BASE_URL` | el mismo `https://….onrender.com` del paso 5 |
| `RESEND_API_KEY` | la misma `re_…` |
| `SMTP_FROM` | `onboarding@resend.dev` (solo el correo; el nombre lo pone `SMTP_FROM_NAME`) |

3. **Actions** → **Pipeline Render** → **Run workflow**.
4. Cuando termine en verde, en la web abierta `/interrupciones` (puede tardar un minuto).

El horario del cron es **UTC** (cada 15 min). Lima es UTC−5.

---

## Qué no hacer

- No pegue `.env.docker` en Render.
- No cree `DB_HOST=localhost`.
- No deje `DATABASE_URL` vacía.
- No ponga la External URL en el Web Service (puede funcionar, pero la Internal es la correcta para el web).
- No suba `.env` ni URLs de Postgres a Git.
- No ejecute `docker compose down -v` en su PC.

---

## Parte D — Zonas, informes y cuenta (después del deploy)

1. Suba este código y deje que Render despliegue.
2. En la web pública, suscríbase con **distrito + sector y/o área**. No marque «todo el distrito» si no quiere avisos de todo el distrito.
3. Confirme el correo. En «Ya tengo cuenta» pida un enlace para editar zonas, horarios e informes.
4. Abra **Informe de mi zona** cuando quiera un reporte de coincidencias (o de «sin cortes» en el lote actual).
5. GitHub Actions: además de **Pipeline Render** (cada 15 min, avisos inmediatos), active **Informe zonas Render** (diario 07:00 Lima). Usa los mismos secretos.
6. Grafana y Prometheus **no van en Render Free**. En su PC: `docker compose --env-file .env.docker up -d` y abra Grafana en :3000 (dashboards «Avisos de agua»).
7. n8n **solo local** (o n8n Cloud si usted lo contrata). En Render el cron es GitHub. No active `pipeline-programado.json` contra la misma base que Actions.

## Parte E — Después de que el web esté Live

Suba este código a GitHub y deje que Render vuelva a desplegar.

1. Espere **2 minutos** y abra `https://SU-SERVICIO.onrender.com/` y `/interrupciones`.
2. Si sigue en 0 cortes: **Operador** → entre con `ADMIN_USER` / `ADMIN_PASSWORD` → **Actualizar desde la fuente ahora** → recargue.
3. Correo: en Environment, `CORREO_PROVEEDOR=resend`, `RESEND_API_KEY=re_…`, `SMTP_FROM=onboarding@resend.dev`, `MODO_ENVIO=real`, `OPERACION_PUBLICA=true`, `BASE_URL=https://SU-SERVICIO.onrender.com`.
4. Suscríbase con el **mismo correo de la cuenta Resend** (modo prueba). Revise spam.
5. GitHub Secrets (External Database URL + BASE_URL + Resend) y **Actions → Pipeline Render → Run workflow**.

Si la fuente responde 403 desde Render, los cortes no llegarán por esa IP. En ese caso el workflow de GitHub (otra red) es el que debe llenar la base.

## Comprobar que quedó bien

1. `https://SU-SERVICIO.onrender.com/salud` responde.
2. `/` muestra el formulario.
3. `/admin` pide usuario y contraseña (`ADMIN_USER` / `ADMIN_PASSWORD`).
4. Tras el workflow de Actions, `/interrupciones` lista cortes (hasta 500 de la API, no solo 2).
