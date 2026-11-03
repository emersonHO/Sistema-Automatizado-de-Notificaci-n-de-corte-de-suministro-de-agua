# Pruebas

## Cómo ejecutarlas

```powershell
python -m pytest -q
```

Requisito: base PostgreSQL `notificaciones_agua_test` accesible con las mismas credenciales de `.env` salvo el nombre de la base (lo fija `tests/conftest.py`).

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

Las pruebas **no** envían correo real. El fixture `tests/fixtures/captura_minima.json` replica la estructura observada de la API; no pretende ser una captura actual de producción.

## Evaluación cuantitativa

```powershell
python -m src.evaluacion
```

- Precisión y recall: solo `src/casos_evaluacion.py` (etiquetado independiente).
- Tiempos: promedios de `ejecuciones_proceso` en la base conectada.
- Detección de cambios: casos etiquetados de origen/relevante/evento.

No se usa la predicción del sistema como verdad de referencia.
