# Plan de implementación — Sistema de Notificación de Interrupciones de Agua

**Proyecto:** Sistema-Notificacion-Agua  
**Tesis:** Desarrollo de un sistema automatizado de notificación proactiva de interrupciones del servicio de agua potable para usuarios de Lima Metropolitana  
**Fecha de auditoría:** 2 de noviembre de 2026 (America/Lima)

Este documento se actualiza conforme avanza la implementación. Conserva el estado para continuar sin repetir trabajo.

---

## Fase A — Diagnóstico del repositorio (estado inicial)

### Archivos reales inspectados

| Ruta | Estado |
|------|--------|
| `src/recolector.py` | Existe. Consulta `https://cortedeagua.net.pe/api.php` con `dias=14`. Sin reintentos, sin backoff, metadatos incompletos (no compara `total` vs `len(data)`, timestamps naive). |
| `src/normalizador.py` | Existe. Lee el JSON más reciente, convierte fechas/números/textos, escribe CSV y llama a `crear_caracteristicas()`. Sin informe de calidad ni detección de captura incompleta. |
| `src/caracteristicas.py` | Existe. Calcula intervalo, día de semana, fin de semana y cantidad de áreas. |
| `src/persistencia.py` | Existe. Carga CSV a PostgreSQL. Hash de **toda** la fila CSV (incluye columnas derivadas). No hay historial versionado. |
| `src/prueba_cambio.py` | **No existe.** |
| `database/schema.sql` | Existe. Tablas `interrupciones` y `ejecuciones_proceso` solamente. |
| `database/sprint2_historial.sql` | **No existe.** |
| `requirements.txt` | Solo cliente HTTP y pandas. Faltan `psycopg`, FastAPI, pytest, dotenv. |
| `.env` / `.env.example` | **No existen.** |
| `tests/` | **No existen.** |
| Interfaz web | **No existe.** |
| Pipeline unificado | **No existe.** |
| `data/processed/interrupciones_normalizadas.csv` | Presente (captura previa de 214 registros). `data/raw/` vacío en este entorno. |

### Compatibilidad entre módulos

- Recolector y normalizador son compatibles entre sí (JSON `ok` + `data`).
- Persistencia depende de PostgreSQL y de un CSV generado; el hash actual trataría como cambio cualquier diferencia de representación (NaN, formato de fecha, columnas derivadas).
- No hay orquestación: cada script se ejecuta por separado.

### PostgreSQL en este entorno

- Servidor instalado y arrancado para desarrollo local (PostgreSQL 16).
- Base `notificaciones_agua` creada para el MVP. No se borran capturas originales.

### Estado por sprint (al iniciar)

| Sprint | Objetivo | Estado inicial |
|--------|----------|----------------|
| 1 | Ingesta, normalización, BD | Parcial (cliente HTTP básico, CSV, esquema mínimo) |
| 2 | Cambios, historial, automatización | No iniciado |
| 3 | Usuarios, zonas, notificaciones | No iniciado |
| 4 | Idempotencia, panel, métricas | No iniciado |
| 5 | Pruebas integrales y evaluación | No iniciado |

---

## Arquitectura elegida

Arquitectura modular en un solo proceso Python, PostgreSQL como único almacén y cola (outbox transaccional). Interfaz FastAPI + Jinja2 + Bootstrap 5 (CDN). Sin microservicios, sin React, sin nube de pago.

```
Fuente pública externa (cortedeagua.net.pe)
        |
        v
Cliente HTTP (reintentos, timeout, validación)
        |
        v
Captura original JSON + metadatos de captura
        |
        v
Normalización, calidad y características
        |
        v
PostgreSQL (interrupciones + historial + ejecuciones)
        |
        v
Detección de novedades y cambios (hash origen vs hash relevante)
        |
        v
Correspondencia territorial determinista (Lima Metropolitana)
        |
        v
Outbox de notificaciones (unicidad por versión relevante)
        |
        v
Envío SMTP (desactivado por defecto) o simulación
        |
        v
Panel web + métricas + auditoría
```

### Decisiones y supuestos documentados

1. La API consultada es de un **tercero**, no una API oficial de SEDAPAL.
2. `fec_deteccion` y `fec_estimada` se tratan como **fechas reportadas por la fuente**, no como inicio real ni restauración confirmada.
3. No hay paginación: si `len(data) < total`, la captura se marca incompleta y **no** se interpreta la ausencia de un id como cancelación.
4. Callao se conserva en datos originales y se **excluye** de la correspondencia territorial del MVP.
5. Coincidencia por distrito **no** implica afectación de todas las viviendas.
6. Cancelación solo si el campo `estado` o `tipo_incid` coincide con un conjunto cerrado (`CANCELADA`, `ANULADA` y equivalentes explícitos).
7. Envío real de correo desactivado por defecto (`SMTP_ENABLED=false`, `MODO_ENVIO=simulacion`).
8. Tiempos de la fuente: `TIMESTAMP` sin zona. Tiempos del sistema: `TIMESTAMPTZ` (UTC).
9. Unicidad de notificación: `(suscripcion_id, interrupcion_id, version_relevante, tipo_evento)`, no `(interrupcion_id, usuario_id, tipo_evento)`.

---

## Orden de implementación

1. Configuración, esquema SQL completo, conexión y migraciones.
2. Ingesta robusta + metadatos + calidad (Sprint 1).
3. Persistencia idempotente + historial + hashes diferenciados (Sprints 1–2).
4. Pipeline con bloqueo consultivo y registro de tiempos (Sprint 2).
5. Zonas Lima, usuarios, suscripciones, confirmación de correo (Sprint 3).
6. Correspondencia territorial y outbox (Sprint 3–4).
7. SMTP simulado y plantillas (Sprint 3–4).
8. Panel FastAPI (Sprint 4).
9. Evaluación cuantitativa con casos etiquetados (Sprint 5).
10. Pruebas pytest, documentación y scripts Windows.

---

## Correspondencia con historias / criterios

Ver secciones de sprints 1–5 en este mismo archivo y `docs/PRUEBAS.md`. Los criterios de aceptación del MVP (sección 13 del enunciado) se verifican con pruebas automatizadas y con el escenario de demostración local.

---

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| API de terceros caída o incompleta | Timeouts, reintentos, captura incompleta, conservar datos previos |
| Semántica incierta de fechas | No afirmar inicio/fin reales; etiquetar como “reportadas” |
| Falsos positivos territoriales | Exactitud + alias controlados; casos ambiguos no notifican |
| Correos reales en pruebas | Modo simulación por defecto; pytest nunca habilita SMTP |
| Hash demasiado amplio | Separar hash de origen, hash relevante y representación técnica |
| Ejecuciones concurrentes | `pg_try_advisory_lock` |

---

## Registro de avance

- [x] Fase A — auditoría
- [x] Fase B — este plan
- [x] Sprint 1 — ingesta, normalización, persistencia
- [x] Sprint 2 — historial, cambios, pipeline
- [x] Sprint 3 — usuarios, zonas, notificaciones
- [x] Sprint 4 — panel, idempotencia, métricas
- [x] Sprint 5 — pruebas, evaluación, documentación
