# Arquitectura final (operación pública)

Ciudadano → Caddy (HTTPS) → FastAPI (`web`) → PostgreSQL.  
n8n orquesta por HTTP interno Bearer. `pipeline-worker` y `notification-worker` no se sustituyen por n8n.  
Prometheus/Grafana/n8n/PostgreSQL no se publican en Internet.

Fuente de interrupciones: `API_URL` (tercero, no SEDAPAL). Matching distrital = posible afectación, no predio.

Producción VPS: `compose.prod.yaml`. Laboratorio: `compose.yaml` (Mailpit, puertos localhost).  
Público gratis en Windows: perfil Compose `publico` (`caddy-publico` + `tunel` Quick Tunnel). Guía: `docs/GUIA_DESPLIEGUE_GRATUITO_WINDOWS.md`.

Tokens: confirmación hasheada y de un solo uso; gestión y baja firmadas (HMAC).
