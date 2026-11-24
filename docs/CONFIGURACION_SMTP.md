# Configuración SMTP

Variables (`.env.docker` o `.env.production`):

```
SMTP_ENABLED=true
MODO_ENVIO=real
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=avisos@tudominio
SMTP_FROM_NAME=Avisos de agua Lima
SMTP_TIMEOUT=20
```

Laboratorio: `MODO_ENVIO=mailpit`, `SMTP_HOST=mailpit`, `SMTP_PORT=1025`, `SMTP_STARTTLS=false`.

Si SMTP está habilitado y el envío falla, la notificación queda `REINTENTANDO` o `FALLIDA`. **No** pasa a `SIMULADA` en silencio.

`ACEPTADA_SMTP` = el servidor aceptó el mensaje. No es lectura ni entrega garantizada al buzón.

No ponga secretos en Git ni en los JSON de n8n. Habilite SMTP solo cuando el dominio y el remitente estén verificados en el proveedor.

## Gmail (sin dominio, pocos suscriptores)

Para el despliegue gratuito en Windows (`docs/GUIA_DESPLIEGUE_GRATUITO_WINDOWS.md`):

```
SMTP_ENABLED=true
MODO_ENVIO=real
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_USER=su.cuenta@gmail.com
SMTP_PASSWORD=contraseña-de-aplicación
SMTP_FROM=su.cuenta@gmail.com
SMTP_FROM_NAME=Avisos de agua Lima
```

Requisitos que debe cumplir usted: verificación en dos pasos en Google y [contraseña de aplicación](https://myaccount.google.com/apppasswords). Cuotas bajas (orientativamente 100–500/día); Google puede limitar correo automático. No es un remitente transaccional con SPF/DKIM de dominio propio.

Con `OPERACION_PUBLICA=true`, si SMTP no está listo el sistema no guarda `SIMULADA` haciéndole creer que avisó a un ciudadano.
