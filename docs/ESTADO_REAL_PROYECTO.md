# Estado real del proyecto (operación pública)

Fecha: 22 nov 2026.

| Capacidad | Clasificación |
|-----------|----------------|
| Web ciudadana `/` | IMPLEMENTADO |
| Alta, honeypot, rate limit, consentimiento | IMPLEMENTADO + TEST AUTOMATIZADO |
| Confirmación por token hasheado | IMPLEMENTADO + TEST AUTOMATIZADO |
| Correo de confirmación SMTP | IMPLEMENTADO; PENDIENTE DE CONFIGURACIÓN EXTERNA en producción |
| Gestión y baja por token firmado | IMPLEMENTADO + TEST AUTOMATIZADO |
| Preferencias (tipos de alerta, pausa, resumen) | IMPLEMENTADO |
| Pipeline + workers + outbox | IMPLEMENTADO + TEST AUTOMATIZADO |
| n8n 15 min `modo=api` | IMPLEMENTADO (JSON); PENDIENTE DE VALIDACIÓN MANUAL (activar en UI) |
| Alertas admin / resumen diario | IMPLEMENTADO (API + workflows inactivos) |
| SMTP real sin fallback silencioso a simulación | IMPLEMENTADO; PENDIENTE DE CONFIGURACIÓN EXTERNA |
| Caddy + compose.prod | IMPLEMENTADO; VERIFICADO EN PRODUCCIÓN: no |
| Prometheus/Grafana | IMPLEMENTADO; VERIFICADO LOCALMENTE (fase 5) |
| Backup automático volumen | IMPLEMENTADO; restore no ejecutado |
| GitHub Actions YAML | IMPLEMENTADO; run remoto PENDIENTE DE VALIDACIÓN MANUAL |
| Matching ≠ predio | IMPLEMENTADO (textos y reglas) |
| Fuente oficial SEDAPAL | NO IMPLEMENTADO (no hay API documentada) |

Producción **no** está viva en un VPS de este entorno. Localmente sigue `compose.yaml` (Mailpit, localhost).
