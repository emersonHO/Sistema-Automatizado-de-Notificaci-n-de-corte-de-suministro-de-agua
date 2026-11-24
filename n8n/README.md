# n8n (Fase 2)

n8n **sigue siendo el orquestador local** (Compose). En Render Free no hay n8n: el intervalo de 15 minutos lo cubre GitHub Actions con `python -m src.ciclo_produccion` (misma cola y mismo `ejecutar_pipeline`). No active `pipeline-programado.json` contra la base de Render a la vez que Actions.

UI local: http://127.0.0.1:5678  
FastAPI interno: `http://web:8000` (red Compose).  
El token **no** va en los JSON. Se guarda como credencial Header Auth en el SQLite de n8n (`n8n_data`).

Los nodos HTTP no leen variables de entorno (`N8N_BLOCK_ENV_ACCESS_IN_NODE=true`).

## Credencial «FastAPI interno»

1. Abra http://127.0.0.1:5678 e inicie sesión (alta de propietario la primera vez).
2. Menú **…** / **Credentials** → **Add credential**.
3. Tipo: **Header Auth** (`httpHeaderAuth`).
4. Nombre de la credencial: `FastAPI interno` (debe coincidir).
5. **Name:** `Authorization`
6. **Value:** `Bearer ` + el valor de `INTERNAL_API_TOKEN` en `.env.docker` (un espacio después de Bearer).
7. Guardar. No copie el token a los workflows.

## Importar workflows

1. **Workflows** → **…** → **Import from File**.
2. Primero: `n8n/workflows/pipeline-manual.json`.
3. Si n8n pide mapear credenciales, elija `FastAPI interno` en ambos nodos HTTP.
4. **No active** el workflow. Ejecútelo con **Test workflow**.
5. Importe `pipeline-programado.json` y déjelo **inactivo** hasta validar. Intervalo **15 minutos**, `modo=api`, `solo_si_libre`. No usa fixtures.
7. `alertas-admin.json` y `resumen-diario.json` también inactivos. El resumen solo cubre quien marcó la casilla opcional.
6. Opcional: `seguimiento-observabilidad.json` (GET de snapshot y notificaciones; no sustituye Grafana). Si FastAPI responde 401/503, el workflow termina en los nodos de error HTTP.

## Prueba manual con fixture (no llama a cortedeagua.net.pe)

Requisito: `INTERNAL_PERMITIR_FIXTURE=true` en `.env.docker` y recrear `web`:

```powershell
docker compose --env-file .env.docker up -d web
```

El POST envía:

```json
{
  "origen": "MANUAL",
  "solo_si_libre": false,
  "modo": "fixture",
  "ruta_fixture": "captura_minima.json"
}
```

Eso **escribe** las dos incidencias del fixture en la base Docker `notificaciones_agua` (datos sintéticos identificables). No usa la API pública.

Si n8n muestra **400 `FIXTURE_NO_PERMITIDO`**, el servicio `web` aún tiene el flag en `false`. Corrija `.env.docker`, ejecute `up -d web` y vuelva a **Test workflow**. El flag debe volver a `false` cuando termine la prueba.

## Comprobar en PostgreSQL

```powershell
docker exec notificacion-agua-db-1 psql -U agua -d notificaciones_agua -c "SELECT s.id AS solicitud_id, s.estado AS estado_solicitud, s.origen, s.modo, s.ejecucion_id, e.id AS ejecucion_id, e.solicitud_id, e.estado AS estado_pipeline, e.registros_leidos, e.registros_nuevos FROM solicitudes_ejecucion s LEFT JOIN ejecuciones_proceso e ON e.solicitud_id = s.id ORDER BY s.id DESC LIMIT 5;"
```

Debe coincidir `s.ejecucion_id` con `e.id` y `e.solicitud_id` con `s.id`.
