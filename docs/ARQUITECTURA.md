# Arquitectura del MVP

La evolución contenerizada y el diagrama objetivo están en `docs/ARQUITECTURA_OBJETIVO.md`, `docs/PLAN_EVOLUCION_ARQUITECTONICA.md` y `docs/DECISIONES_ARQUITECTONICAS.md`. Este archivo describe el núcleo Python/PostgreSQL que se reutiliza.

## Estilo

Proceso único en Python, PostgreSQL como almacén y cola transaccional (outbox), interfaz FastAPI + Jinja2 + Bootstrap 5. Sin microservicios, sin React y sin infraestructura de pago.

## Flujo

```
Fuente pública externa (tercero)
        → Cliente HTTP (timeout, reintentos, validación)
        → JSON original + metadatos de captura (America/Lima y UTC)
        → Normalización, calidad y características
        → PostgreSQL (interrupciones)
        → Historial versionado (hash de origen vs hash relevante)
        → Correspondencia territorial determinista (Lima Metropolitana)
        → Outbox de notificaciones
        → Simulación SMTP o envío real (opt-in)
        → Panel y métricas
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
| `src/notificaciones.py` | Outbox, plantillas, simulación SMTP |
| `src/pipeline.py` | Orquestación y candado `pg_try_advisory_lock` |
| `src/web/app.py` | Panel académico |
| `src/evaluacion.py` | Indicadores reproducibles |

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

Unicidad: `(suscripcion_id, interrupcion_id, version_relevante, tipo_evento)`.

No se usa `(interrupcion_id, usuario_id, tipo_evento)` como única clave, para permitir varias modificaciones legítimas.

Estados: `PENDIENTE`, `SIMULADA`, `ACEPTADA_SMTP`, `FALLIDA`, `DESCARTADA`.

## Tiempos

- Fuente: `TIMESTAMP` sin zona.
- Sistema: `TIMESTAMPTZ` (UTC). Metadatos de captura también registran hora de America/Lima.
