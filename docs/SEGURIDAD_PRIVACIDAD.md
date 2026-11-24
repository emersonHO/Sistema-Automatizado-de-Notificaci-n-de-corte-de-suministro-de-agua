# Seguridad y privacidad

- HTTPS en producción (Caddy). Cookies `SESSION_HTTPS=true`.
- Cabeceras: nosniff, frame deny, CSP, HSTS en Caddy.
- CSRF en formularios. Honeypot `website`. Rate limit por IP en alta y reenvío.
- Confirmación: token aleatorio hasheado, caducidad, un uso.
- Gestión/baja: token firmado; no se cancelan suscripciones ajenas por id numérico.
- API interna Bearer. Fixture desactivado en producción.
- Postgres, n8n, Prometheus y Grafana sin puertos públicos en `compose.prod.yaml`.
- Correos enmascarados en administración. No registrar el token en claro.
- El operador debe cumplir la Ley de Protección de Datos Personales (banco de datos, derechos ARCO). El software no sustituye ese trámite.
- Retención: la baja detiene avisos; el historial técnico puede conservarse. Anonimización adicional es decisión del operador.
