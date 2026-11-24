# Arquitectura del MVP

La evolución contenerizada y el diagrama objetivo están en `docs/ARQUITECTURA_OBJETIVO.md`, `docs/PLAN_EVOLUCION_ARQUITECTONICA.md` y `docs/DECISIONES_ARQUITECTONICAS.md`. Este archivo describe el núcleo Python/PostgreSQL que se reutiliza.

## Estilo

Paquete Python único. En Docker hay procesos separados (`web`, `pipeline-worker`, `notification-worker`) sobre el mismo PostgreSQL (outbox transaccional). Interfaz FastAPI + Jinja2 + Bootstrap 5. Sin microservicios de repositorio, sin React y sin infraestructura de pago.

## Flujo

```
Fuente pública externa (tercero)
        → Cliente HTTP (timeout, reintentos, validación)
        → JSON original + metadatos de captura (America/Lima y UTC)
        → Normalización, calidad y características
        → PostgreSQL (interrupciones)
        → Historial versionado (hash de origen vs hash relevante)
        → Correspondencia territorial determinista (Lima Metropolitana)
        → Outbox de notificaciones (PENDIENTE)
        → notification-worker (SIMULADA; SMTP real opt-in, desactivado en Compose)
        → Panel, API interna y métricas
```

## Módulos

| Módulo | Responsabilidad |
|--------|-----------------|
| `src/recolector.py` | Consulta HTTP, validación, persistencia de capturas |
| `src/normalizador.py` | DataFrame, tipos, CSV |
| `src/caracteristicas.py` | Intervalo, día, áreas |
| `src/calidad.py` | Duplicados, vacíos, captura incompleta |
| `src/persistencia.py` | Upsert idempotente e historial |
| `src/hashes.py` | Hash de origen, relevante y técnico |
| `src/correspondencia.py` | Distrito / sector / área |
| `src/suscripciones.py` | Usuarios, zonas, confirmación, baja |
| `src/notificaciones.py` | Outbox, plantillas, reclamo, simulación |
| `src/worker_notificaciones.py` | Bucle del consumidor del outbox |
| `src/worker_pipeline.py` | Bucle de solicitudes de ingesta (no envía avisos) |
| `src/pipeline.py` | Orquestación y candado `pg_try_advisory_lock` |
| `src/web/app.py` | Panel académico |
| `src/evaluacion.py` | Indicadores reproducibles |
| `src/observabilidad.py` | Snapshot SQL de pipeline, cola y outbox |

## Hashes

1. **Origen:** campos de la fuente. Un cambio aquí crea versión de origen.
2. **Relevante:** distrito, áreas, sector, tipo, estado, fechas reportadas, causa y textos de aviso. Solo este hash dispara notificación.
3. **Técnico:** representación completa, incluida columnas derivadas. No genera aviso.

Una incidencia puede volver a un estado anterior: se inserta una nueva fila de historial; no se borra el pasado. Versiones consecutivas con el mismo hash de origen se omiten.

## Correspondencia

- Normalización: mayúsculas, tildes, espacios, alias controlados.
- Coincidencia exacta de distrito canónico → `POTENCIAL`.
- Sector o área exactos → `ESPECIFICA` (sigue sin confirmar la vivienda).
- Callao → `EXCLUIDA_AMBITO`.
- Nombre no canónico → `AMBIGUA` (no notifica).

## Notificaciones

Unicidad persistida: `(suscripcion_id, interrupcion_id, version_relevante, tipo_evento)`.

Además, la generación omite un segundo aviso al mismo `usuario_id` para la misma interrupción, versión relevante y tipo de evento (varias suscripciones del mismo destinatario de prueba no duplican el outbox). Las modificaciones posteriores siguen creando `MODIFICADA` cuando cambia el hash relevante.

Estados: `PENDIENTE` → `EN_PROCESO` → `SIMULADA` (éxito simulado). Reintento: `REINTENTANDO` o `FALLIDA`. También existen `ACEPTADA_SMTP` (opt-in, no usado en Compose), `DESCARTADA`, `CANCELADA` y `ERROR` (reserva). Una simulación exitosa **no** se marca `ENVIADA`.

## Tiempos

- Fuente: `TIMESTAMP` sin zona.
- Sistema: `TIMESTAMPTZ` (UTC). Metadatos de captura también registran hora de America/Lima.
