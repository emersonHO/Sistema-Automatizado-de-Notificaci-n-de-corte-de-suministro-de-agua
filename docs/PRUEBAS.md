# Pruebas

## Cómo ejecutarlas

```powershell
python -m pytest -q
```

Requisito: base PostgreSQL `notificaciones_agua_test` accesible con las mismas credenciales de `.env` salvo el nombre de la base (lo fija `tests/conftest.py`). Si esa base no existe, pytest **omite** las pruebas de web, pipeline y notificaciones en lugar de abortar toda la suite.

```sql
CREATE DATABASE notificaciones_agua_test OWNER agua;
```

En Windows, si usa el usuario `postgres`:

```sql
CREATE DATABASE notificaciones_agua_test;
```

y ajuste `DB_USER` / `DB_PASSWORD` en el entorno antes de pytest.

## Qué cubren

| Archivo | Alcance |
|---------|---------|
| `tests/test_recolector.py` | Validación JSON, captura incompleta, reintentos, metadatos |
| `tests/test_normalizador.py` | Tipos, áreas, ámbito Lima vs Callao, calidad |
| `tests/test_correspondencia.py` | Casos etiquetados, tildes, distrito potencial |
| `tests/test_cambios.py` | Hash origen vs relevante, imagen irrelevante |
| `tests/test_pipeline.py` | Idempotencia, NUEVA/MODIFICADA, fallo de fuente |
| `tests/test_notificaciones.py` | Plantillas y SMTP simulado |
| `tests/test_web.py` | Rutas del panel |
| `tests/test_interno.py` | API interna Bearer |
| `tests/test_solicitudes.py` | Cola de solicitudes |
| `tests/test_worker.py` | pipeline-worker |
| `tests/test_fase3_notificaciones.py` | Esquema aditivo, matching, API de notificaciones |
| `tests/test_worker_notificaciones.py` | Reclamo, reintentos, recuperación del outbox |
| `tests/test_observabilidad.py` | Snapshot, salud, API de métricas, logs JSON |
| `tests/test_correo.py` | Adaptador SMTP y opt-in |
| `tests/test_metricas_prom.py` | Endpoint `/metrics` |
| `tests/test_e2e_flujo.py` | Fixture → matching → outbox → simulación; Mailpit si el SMTP es alcanzable |
| `tests/test_workflows_n8n.py` | JSON de n8n sin secretos y rutas internas |

Las pruebas **no** envían correo real. El fixture `tests/fixtures/captura_minima.json` replica la estructura observada de la API; no pretende ser una captura actual de producción.

## Evaluación cuantitativa

```powershell
python -m src.evaluacion
```

- Precisión y recall: solo `src/casos_evaluacion.py` (etiquetado independiente).
- Tiempos: promedios de `ejecuciones_proceso` en la base conectada.
- Detección de cambios: casos etiquetados de origen/relevante/evento.

No se usa la predicción del sistema como verdad de referencia.
