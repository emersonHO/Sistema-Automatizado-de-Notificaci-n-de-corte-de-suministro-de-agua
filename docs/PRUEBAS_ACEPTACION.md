# Pruebas de aceptación (operación real)

Los fixtures y pytest **no** sustituyen esta lista. SMTP real y dominio público requieren su configuración.

## A — Acceso público
Abrir `https://DOMINIO` desde un teléfono. HTTPS válido. Formulario usable. No debe verse el panel de KPIs administrativos.

## B — Suscripción
Correo de prueba **suyo**. Distrito Lima. Consentimiento. Mensaje genérico (no enumeración). Correo de confirmación. Enlace. Preferencias activas en PostgreSQL (`correo_confirmado`).

## C — Automatización
n8n workflow programado **activo** (15 min, `modo=api`, `solo_si_libre`). Solicitud en `/admin` → solicitudes. `pipeline-worker` la reclama.

## D — Recopilación
`modo=api` llama `API_URL`. Captura en volumen. Ejecución `COMPLETADO` o `COMPLETADO_INCOMPLETO`. Si la fuente falla: `ERROR`, sin borrar interrupciones previas.

## E — Matching
La interrupción y la suscripción coinciden por distrito. El correo dice **podría afectar**, no “tu casa está cortada”.

## F — Notificación
Outbox `PENDIENTE` → worker → `ACEPTADA_SMTP` con SMTP real. Reejecutar el pipeline no duplica el mismo evento. Fallo SMTP → reintento, no `SIMULADA`.

## G — Gestión
Enlace de preferencias. Pausa. Cancelación. Deja de generar avisos.

## H — Observabilidad
Prometheus targets (túnel). Grafana dashboards. Logs JSON con ids de solicitud/ejecución.

## I — Resiliencia
`docker compose ... restart notification-worker`. Cola persiste. Backup presente. Sin `down -v`.

Pytest (laboratorio, base `notificaciones_agua_test`):

```powershell
docker compose --env-file .env.docker run --rm -e DB_NAME=notificaciones_agua_test web python -m pytest -q --tb=short
```
