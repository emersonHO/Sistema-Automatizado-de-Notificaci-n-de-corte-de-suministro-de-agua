# Diagnóstico de arquitectura — Sistema-Notificacion-Agua

**Fecha de auditoría:** 4 de noviembre de 2026 (America/Lima)  
**Rama inspectada:** `cursor/mvp-notificacion-agua-5701` (`42e3d49`)  
**Alcance:** solo lectura de archivos versionados y de documentación existente. **No se modificó código de aplicación ni se alteró PostgreSQL. No se reejecutó pytest ni el pipeline en esta auditoría.**

## Convención de estados

| Estado | Significado en este documento |
|--------|-------------------------------|
| IMPLEMENTADO Y VERIFICADO | Existe código en el repositorio **y** hay pruebas automatizadas y/o evidencia escrita en `docs/RESULTADOS_PRUEBAS.md`. Esta auditoría no reejecutó esas pruebas. |
| IMPLEMENTADO SIN VERIFICAR | Existe código; no hay prueba automatizada dedicada ni evidencia de ejecución citada en el repositorio. |
| PARCIAL | Existe una parte del componente; faltan piezas esenciales. |
| PROPUESTO | Aparece en documentación o variables, no como comportamiento efectivo. |
| NO EXISTE | No hay archivo, módulo ni configuración en el repositorio. |

La evidencia de verificación citada (`20 passed`, pipeline de 185 registros) proviene de `docs/RESULTADOS_PRUEBAS.md` (2 de noviembre de 2026, America/Lima). No se afirma que esos números sigan siendo actuales.

---

## 1. Árbol real del repositorio (archivos rastreados por git)

Excluidos de este árbol: `.venv/`, `.env`, `__pycache__/`, `.pytest_cache/`, `.ipynb_checkpoints/` (salvo los que git aún rastrea), `data/raw/`, `data/processed/` generado localmente, `data/simulaciones/`, `data/evaluacion/`, credenciales.

```text
Sistema-Notificacion-Agua/
├── .env.example
├── .gitignore
├── README.md
├── pytest.ini
├── requirements.txt
├── data/
│   └── processed/
│       └── interrupciones_normalizadas.csv   # rastreados históricamente; .gitignore ignora el resto de processed/
├── database/
│   ├── schema.sql
│   └── sprint2_historial.sql                 # solo \i schema.sql (psql)
├── docs/
│   ├── ARQUITECTURA.md
│   ├── INSTALACION_WINDOWS.md
│   ├── PLAN_IMPLEMENTACION.md
│   ├── PRUEBAS.md
│   └── RESULTADOS_PRUEBAS.md
├── notebooks/
│   └── 01_exploracion.ipynb                  # 0 celdas
├── scripts/
│   ├── __init__.py
│   ├── ejecutar_pipeline.ps1
│   └── init_db.py
├── src/
│   ├── __init__.py
│   ├── calidad.py
│   ├── caracteristicas.py
│   ├── casos_evaluacion.py
│   ├── config.py
│   ├── correspondencia.py
│   ├── db.py
│   ├── evaluacion.py
│   ├── hashes.py
│   ├── normalizador.py
│   ├── notificaciones.py
│   ├── persistencia.py
│   ├── pipeline.py
│   ├── privacidad.py
│   ├── recolector.py
│   ├── suscripciones.py
│   ├── texto.py
│   ├── zonas_lima.py
│   └── web/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py
│       ├── consultas.py
│       ├── static/estilos.css
│       └── templates/*.html
└── tests/
    ├── conftest.py
    ├── fixtures/captura_minima.json
    ├── test_cambios.py
    ├── test_correspondencia.py
    ├── test_normalizador.py
    ├── test_notificaciones.py
    ├── test_pipeline.py
    ├── test_recolector.py
    └── test_web.py
```

También aparecen rastreados (ruido, no arquitectura): `notebooks/.ipynb_checkpoints/01_exploracion-checkpoint.ipynb`, `src/.ipynb_checkpoints/recolector-checkpoint.py`.

**No existen** en el repositorio: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.github/workflows/`, manifiestos Kubernetes, Prometheus, OpenTelemetry, Redis, broker de mensajes.

**Estado del inventario de despliegue:** NO EXISTE (contenedores). IMPLEMENTADO Y VERIFICADO (árbol de aplicación Python/SQL anterior, con evidencia de tests documentada).

---

## 2. Tecnologías y versiones declaradas

Fuente: `requirements.txt` (pinning exacto) y documentación. **No se comprobó en esta auditoría que el entorno local coincida con estos pines.**

| Tecnología | Versión declarada | Uso en código |
|------------|-------------------|---------------|
| Python | 3.12 “o compatible” (`README.md`) | Runtime; no hay `pyproject.toml` ni classifier |
| pandas | 3.0.6 | Normalización |
| numpy | 2.5.3 | Dependencia de pandas |
| requests | 2.34.2 | Cliente HTTP |
| urllib3 / certifi / charset-normalizer / idna / six | pines 2026 | Transsitivas de requests |
| python-dotenv | 1.1.1 | `.env` |
| psycopg[binary] | 3.2.10 | PostgreSQL |
| FastAPI | 0.118.0 | Panel |
| uvicorn | 0.37.0 | Servidor ASGI |
| jinja2 | 3.1.6 | Plantillas |
| python-multipart | 0.0.20 | Formularios |
| pytest | 8.4.2 | Pruebas |
| httpx | 0.28.1 | TestClient / cliente |
| email-validator | 2.3.0 | Declarado; el registro valida correo con una regla propia en `suscripciones.py`, no se observó uso de esta librería |
| PostgreSQL | 16 “o compatible” (`README.md`, `docs/INSTALACION_WINDOWS.md`) | Motor; no hay imagen Docker |
| Bootstrap 5.3.3 | CDN en `base.html` | CSS/JS de interfaz |
| PowerShell | script `scripts/ejecutar_pipeline.ps1` | Automatización Windows |

**Estado:** IMPLEMENTADO (declaración de dependencias). PARCIAL (no hay lockfile de contenedor ni matriz CI).

---

## 3. Módulos Python, responsabilidades y dependencias

Estilo observado: **monolito modular en un paquete `src`**, un proceso para el panel y otro proceso CLI para el pipeline. No hay capas hexagonales formales ni inyección de puertos más allá de pasar `conexion` y `sesion` HTTP.

```text
recolector → normalizador → caracteristicas/calidad
                ↓
          persistencia/hashes  →  correspondencia
                ↓                      ↓
         ejecuciones/capturas    suscripciones/zonas
                ↓                      ↓
              pipeline  →  notificaciones (outbox)  →  SMTP o archivo
                ↓
            web (FastAPI)  ←  consultas SQL
```

| Módulo | Responsabilidad | Depende de | Estado |
|--------|-----------------|------------|--------|
| `config.py` | Env: API, DB, SMTP, rutas, campos hash, `LOCK_KEY=570114` | dotenv | IMPLEMENTADO SIN VERIFICAR (sin test de config) |
| `db.py` | DSN, conexión, aplica `schema.sql` | config, psycopg | IMPLEMENTADO Y VERIFICADO (indirecto: tests de integración) |
| `recolector.py` | GET a API de terceros, reintentos, JSON crudo + `.meta.json` | requests, config | IMPLEMENTADO Y VERIFICADO (`test_recolector.py`) |
| `normalizador.py` | DataFrame, CSV, informe de calidad | pandas, calidad, caracteristicas, zonas_lima | IMPLEMENTADO Y VERIFICADO |
| `caracteristicas.py` | Intervalo, día semana, fin de semana, recuento de áreas | pandas | IMPLEMENTADO Y VERIFICADO |
| `calidad.py` | Duplicados, vacíos, captura incompleta | pandas | IMPLEMENTADO Y VERIFICADO |
| `hashes.py` | SHA-256 origen / relevante / técnico | config | IMPLEMENTADO Y VERIFICADO (`test_cambios.py`) |
| `texto.py` / `zonas_lima.py` | Normalización Unicode y catálogo Lima/Callao | — | IMPLEMENTADO Y VERIFICADO |
| `correspondencia.py` | Matching distrito/sector/área | texto, zonas_lima | IMPLEMENTADO Y VERIFICADO |
| `persistencia.py` | Upsert + historial + `FOR UPDATE` | db, hashes, zonas | IMPLEMENTADO Y VERIFICADO (vía pipeline) |
| `suscripciones.py` | Usuarios, zonas, token, baja | db, texto, zonas | IMPLEMENTADO Y VERIFICADO |
| `notificaciones.py` | Outbox, plantillas, SMTP/simulación | correspondencia, suscripciones, smtplib | IMPLEMENTADO Y VERIFICADO |
| `pipeline.py` | Orquestación, advisory lock, métricas de tiempo | todos los anteriores | IMPLEMENTADO Y VERIFICADO |
| `web/app.py` + `consultas.py` | Panel HTML | FastAPI, db, suscripciones | IMPLEMENTADO Y VERIFICADO (rutas GET; POST de alta no cubierto por test) |
| `evaluacion.py` + `casos_evaluacion.py` | Precisión/recall y hashes sobre casos etiquetados | correspondencia, hashes, db | IMPLEMENTADO Y VERIFICADO (casos unitarios; `python -m src.evaluacion` documentado) |
| `privacidad.py` | Enmascarado de correo | — | IMPLEMENTADO SIN VERIFICAR (usado por web; sin test propio) |
| `scripts/init_db.py` | Aplica esquema y siembra distritos | db, suscripciones | IMPLEMENTADO SIN VERIFICAR |
| `notebooks/01_exploracion.ipynb` | Vacío | — | NO EXISTE (archivo presente, sin contenido) |

`ADMIN_TOKEN` se carga en `config.py` y se importa en `app.py` **sin usarse**.

---

## 4. Flujo completo de datos (API → notificaciones)

```text
https://cortedeagua.net.pe/api.php?dias=N     [dependencia externa, no SEDAPAL]
        │ GET requests, timeout, hasta API_REINTENTOS
        ▼
validar ok + data[] ; comparar total vs len(data)
        ▼
data/raw/cortes_*.json + cortes_*.meta.json
        │ INSERT capturas (ruta, anomalias, captura_completa)
        ▼
DataFrame (fechas, textos, municipalidad_normalizada, ambito_lima)
        + características + informe_calidad.json + CSV processed
        ▼
PostgreSQL interrupciones (hash_origen / hash_relevante / versiones)
        + historial_interrupciones (NUEVA | MODIFICADA | CANCELADA | CAMBIO_TECNICO)
        + ejecuciones_proceso (tiempos, contadores)
        ▼
Si hay cambio relevante o incidencia vigente sin aviso previo:
        correspondencia territorial (solo Lima; Callao EXCLUIDA_AMBITO)
        ▼
INSERT coincidencias_territoriales
INSERT notificaciones estado=PENDIENTE
        UNIQUE (suscripcion_id, interrupcion_id, version_relevante, tipo_evento)
        ▼
procesar_outbox: FOR UPDATE SKIP LOCKED
        → SIMULADA (archivo data/simulaciones/) por defecto
        → ACEPTADA_SMTP solo si SMTP_ENABLED, MODO_ENVIO=real y --envio-real
        → intentos_notificacion
```

Notas de implementación (código, no supuestos):

- El pipeline por defecto llama `procesar_outbox(..., forzar_simulacion=True)` salvo `--envio-real`.
- `notificar_incidencias_vigentes_sin_aviso` genera un primer aviso a suscriptores nuevos sobre incidencias ya persistidas.
- Si `len(data) < total`, estado de ejecución `COMPLETADO_INCOMPLETO`; no se trata la ausencia de un id como cancelación.
- Cancelación solo si `estado` o `tipo_incid` normalizados están en `{CANCELADA, CANCELADO, ANULADA, ANULADO, CANCELACION}`.

**Estado del flujo:** IMPLEMENTADO Y VERIFICADO (fixture + evidencia documentada de API real el 2 nov 2026).

---

## 5. Modelo de datos real (`database/schema.sql`)

Motor: PostgreSQL. Migración: un SQL idempotente (`IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`). No hay herramienta de migraciones (Alembic/Flyway): NO EXISTE.

### Tablas y claves

| Tabla | PK | FK / UNIQUE | Índices explícitos |
|-------|----|-------------|-------------------|
| `interrupciones` | `id BIGINT` (id de **fuente**, no surrogate interno) | — | municipalidad, municipalidad_normalizada, fec_deteccion, tipo_incid |
| `ejecuciones_proceso` | `id BIGSERIAL` | — | ninguno extra |
| `capturas` | `id BIGSERIAL` | `ejecucion_id → ejecuciones_proceso` | ninguno |
| `historial_interrupciones` | `id BIGSERIAL` | `interrupcion_id → interrupciones`; UNIQUE (interrupcion_id, version_origen) | (interrupcion_id, fecha_registro DESC) |
| `zonas` | `id BIGSERIAL` | UNIQUE (tipo, nombre_normalizado); CHECK tipo DISTRITO\|SECTOR\|AREA | nombre_normalizado |
| `usuarios` | `id BIGSERIAL` | UNIQUE correo; UNIQUE token_confirmacion | ninguno extra |
| `suscripciones` | `id BIGSERIAL` | usuario_id, zona_id; UNIQUE (usuario_id, zona_id) | parcial zona_id WHERE activa AND confirmada |
| `coincidencias_territoriales` | `id BIGSERIAL` | ejecucion, interrupcion, suscripcion, zona; CHECK nivel y estado | (interrupcion_id, fecha_registro DESC) |
| `notificaciones` | `id BIGSERIAL` | usuario, suscripcion, interrupcion, coincidencia; UNIQUE (suscripcion_id, interrupcion_id, version_relevante, tipo_evento); CHECK tipo y estado | (estado, creada_en DESC) |
| `intentos_notificacion` | `id BIGSERIAL` | notificacion_id | ninguno |

### Relaciones (lógicas)

```text
usuarios 1──N suscripciones N──1 zonas
ejecuciones_proceso 1──N capturas
ejecuciones_proceso 1──N coincidencias_territoriales
interrupciones 1──N historial_interrupciones
interrupciones 1──N coincidencias_territoriales
interrupciones 1──N notificaciones
suscripciones 1──N coincidencias_territoriales
suscripciones 1──N notificaciones
usuarios 1──N notificaciones
notificaciones 1──N intentos_notificacion
coincidencias_territoriales 1──0..N notificaciones
```

### Tipos de tiempo

- Fuente (`fec_deteccion`, `fec_estimada`, `actualizado_en_fuente`): `TIMESTAMP` sin zona.
- Sistema (`primera_captura`, `ultima_captura`, `fecha_inicio`, etc.): `TIMESTAMPTZ`.

### Observaciones para C4 “contenedor de datos”

- El identificador de negocio de la fuente **es** la PK de `interrupciones`. No hay `id_interno` separado (la tesis lo pedía; el código no lo implementó).
- `usuarios.correo` se almacena en claro.
- Varias FK carecen de índice dedicado (`capturas.ejecucion_id`, `intentos_notificacion.notificacion_id`, `notificaciones.usuario_id`).
- No hay `ON DELETE` explícito (default NO ACTION).
- `sprint2_historial.sql` no define DDL propio.

**Estado:** IMPLEMENTADO Y VERIFICADO (schema aplicado en tests de integración documentados). PARCIAL respecto al requisito de IDs internos vs fuente.

---

## 6. Endpoints y autenticación

Aplicación: FastAPI en `src/web/app.py`. Arranque: `python -m src.web` → uvicorn `127.0.0.1:8000` (no 0.0.0.0).

| Método | Ruta | Función | Auth |
|--------|------|---------|------|
| GET | `/salud` | JSON `{ok, postgres}` | Ninguna. Si Postgres falla, **HTTP 200** con `ok: false` |
| GET | `/` | Panel | Ninguna |
| GET | `/interrupciones` | Listado; query `distrito`, `tipo` | Ninguna |
| GET | `/interrupciones/{id}` | Detalle + historial | Ninguna |
| GET | `/ejecuciones` | Listado de pipeline | Ninguna |
| GET | `/notificaciones` | Listado (correo enmascarado) | Ninguna |
| GET | `/notificaciones/{id}` | Detalle + intentos | Ninguna |
| GET | `/suscripciones` | Formulario; query `correo` lista esa cuenta | Ninguna (el correo en query actúa como “secreto”) |
| POST | `/suscripciones` | Alta; form correo + zonas | Ninguna. El token de confirmación se refleja en el redirect |
| GET | `/suscripciones/confirmar/{token}` | Activa correo | Posesión del token |
| POST | `/suscripciones/{id}/baja` | Baja si el correo coincide | Ninguna (correo en form) |
| GET | `/metricas` | Casos etiquetados + agregados SQL | Ninguna |
| GET | `/static/*` | CSS | Ninguna |

No hay: JWT, sesiones, cookies, CSRF, Basic Auth, OAuth, roles, rate limiting, CORS explícito, HTTPS, uso de `ADMIN_TOKEN`.

Plantillas Jinja2 + Bootstrap CDN. No hay API JSON de negocio (salvo `/salud`).

**Estado autenticación:** NO EXISTE (control de acceso). PARCIAL (token de confirmación de correo y enmascarado en listados).  
**Estado endpoints:** IMPLEMENTADO Y VERIFICADO para GET principales (`test_web.py`). POST alta/baja/confirmar: IMPLEMENTADO SIN VERIFICAR (sin test HTTP de escritura).

---

## 7. Automatización y ejecución de procesos

| Mecanismo | Qué hace | Estado |
|-----------|----------|--------|
| `python -m src.pipeline` | Flujo completo | IMPLEMENTADO Y VERIFICADO |
| `--desde-archivo`, `--sin-outbox`, `--envio-real`, `--dias` | Variantes CLI | IMPLEMENTADO SIN VERIFICAR (flags no todos testeados) |
| `python -m src.recolector` / `normalizador` / persistencia `__main__` | Pasos sueltos legacy | IMPLEMENTADO SIN VERIFICAR |
| `python -m scripts.init_db` | DDL + seed distritos | IMPLEMENTADO SIN VERIFICAR |
| `python -m src.evaluacion` | JSON/CSV en `data/evaluacion/` | IMPLEMENTADO (evidencia 2 nov 2026) |
| `python -m src.web` | Panel | IMPLEMENTADO Y VERIFICADO |
| `scripts/ejecutar_pipeline.ps1` | Invoca el pipeline; documentado para Programador de tareas de Windows | IMPLEMENTADO SIN VERIFICAR (no hay task XML ni prueba del programador) |
| cron Linux / systemd / GitHub Actions / Celery beat | — | NO EXISTE |
| Ejecución periódica dentro de un contenedor | — | NO EXISTE |

El pipeline **no** es un worker desacoplado: corre a demanda en el mismo código que el panel, en otro proceso del mismo host.

---

## 8. Outbox, historial y concurrencia

### Outbox — IMPLEMENTADO Y VERIFICADO

- Tabla `notificaciones` = cola; `intentos_notificacion` = auditoría de envío.
- Inserción con `ON CONFLICT DO NOTHING` sobre `(suscripcion_id, interrupcion_id, version_relevante, tipo_evento)`.
- Consumo: `FOR UPDATE OF n SKIP LOCKED LIMIT 50`.
- Estados: PENDIENTE, SIMULADA, ACEPTADA_SMTP, FALLIDA, DESCARTADA (este último no se asigna en el código inspectado).
- No hay broker externo. No hay worker independiente del pipeline.
- El “outbox transaccional” comparte la conexión del pipeline y hace `commit` por fases (captura, persistencia, coincidencias, outbox), no una única transacción de punta a punta.

### Historial — IMPLEMENTADO Y VERIFICADO

- `historial_interrupciones` con UNIQUE (interrupcion_id, version_origen) y `ON CONFLICT DO NOTHING`.
- Tres hashes: origen, relevante, técnico.
- Reversión A→B→A genera nueva `version_origen`; hashes consecutivos iguales no insertan versión.

### Concurrencia — PARCIAL (implementado, cubierto solo de forma indirecta)

- `pg_try_advisory_lock(570114)` de sesión; se libera en `finally` con `pg_advisory_unlock`.
- `FOR UPDATE` por fila al upsert de interrupciones.
- No hay prueba que lance dos pipelines en paralelo.
- El panel abre conexiones cortas sin pool (`psycopg.connect` por request).

---

## 9. Docker, Compose y volúmenes

| Artefacto | Estado |
|-----------|--------|
| Dockerfile | NO EXISTE |
| docker-compose.yml | NO EXISTE |
| .dockerignore | NO EXISTE |
| Imagen PostgreSQL versionada | NO EXISTE |
| Volúmenes nombrados | NO EXISTE |
| Red bridge / healthcheck compose | NO EXISTE |
| Usuario no root | NO EXISTE |
| MailHog / smtp4dev | NO EXISTE |

Despliegue documentado: Python venv + PostgreSQL instalado en Windows/Linux (`docs/INSTALACION_WINDOWS.md`). Datos de captura en el sistema de archivos del host (`data/raw`, `data/processed`, `data/simulaciones`).

**Estado despliegue contenerizado:** NO EXISTE.

---

## 10. Pruebas, métricas, logs y observabilidad

### Pruebas — IMPLEMENTADO Y VERIFICADO (evidencia documentada, no reejecutada aquí)

| Archivo | Cubre |
|---------|--------|
| `test_recolector.py` | JSON inválido, captura incompleta, reintentos, metadatos |
| `test_normalizador.py` | Calidad, Callao fuera de ámbito |
| `test_correspondencia.py` | Casos etiquetados, tildes |
| `test_cambios.py` | Imagen irrelevante vs área relevante |
| `test_pipeline.py` | Idempotencia, MODIFICADA, fallo de fuente |
| `test_notificaciones.py` | Plantilla y modo simulación |
| `test_web.py` | GET de pantallas y `/salud` |
| `conftest.py` | Base `notificaciones_agua_test` + TRUNCATE |

`docs/RESULTADOS_PRUEBAS.md`: `20 passed in 0.96s` el 2 nov 2026 (America/Lima).

Ausente: cobertura HTML, mutación, load test, contrato OpenAPI, test de SMTP real, CI.

### Métricas experimentales — PARCIAL / IMPLEMENTADO Y VERIFICADO en laboratorio pequeño

- Tiempos por etapa en `ejecuciones_proceso` (`tiempo_*_ms`) y panel `/ejecuciones`.
- Precisión/recall **solo** sobre `src/casos_evaluacion.py` (7 correspondencia, 5 cambios).
- `/metricas` mezcla esos casos con `COUNT` de la BD conectada.
- Latencia publicación→detección sobre API real: **no implementada** (documentado como limitación).

### Logs — PARCIAL

- `logging.basicConfig` nivel INFO en CLI (`pipeline`, `recolector`, `normalizador`).
- `logger.exception` en fallos de pipeline y SMTP.
- Formato texto, no JSON estructurado.
- No hay correlación `trace_id`.
- Correos: se evita loguear destinatarios en simulaciones (campo `destinatario_enmascarado`); fallos SMTP registran id de notificación, no necesariamente el correo.

### Observabilidad de producto — NO EXISTE

No hay OpenTelemetry, Prometheus, Grafana, Sentry, health de liveness/readiness distinto de `/salud`, métricas de proceso, ni dashboards externos.

---

## 11. Riesgos, SPOF y dependencias externas

### Dependencias externas

1. **API** `https://cortedeagua.net.pe/api.php` — único origen de incidencias; esquema no contractual; sin paginación.
2. **PostgreSQL** — único almacén y única cola.
3. **SMTP** (opt-in) — entrega no confirmada (`ACEPTADA_SMTP`).
4. **CDN Bootstrap** — el panel depende de Internet para CSS/JS.
5. **Sistema de archivos local** — capturas y simulaciones.

### Puntos únicos de fallo

| SPOF | Efecto |
|------|--------|
| API de terceros caída | Pipeline ERROR; datos previos se conservan (código) |
| PostgreSQL caído | Panel y pipeline inoperantes; `/salud` lo reporta pero con HTTP 200 |
| Un solo proceso pipeline | Advisory lock evita duplicar; no hay cola de reintento de ejecuciones fallidas |
| Host único sin contenedor | No hay receta reproducible de runtime |
| Panel sin autenticación | Lectura de incidencias, ejecuciones y notificaciones enmascaradas por cualquiera que alcance el puerto |
| Token de confirmación en URL de redirect | Fuga en historial del navegador y logs de proxy |
| PK = id de fuente | Colisión o reutilización de ids del tercero rompería integridad |

### Riesgos técnicos adicionales

- Conexiones sin pool; no hay timeout de statement.
- `listar_notificaciones` carga hasta 1000 filas y filtra en Python para el detalle.
- Semilla de zonas y `aplicar_esquema` en cada arranque del panel y del pipeline.
- `email-validator` no usado; validación de correo laxa (`"@" in correo`).
- Notebook y checkpoints versionados no aportan diseño.

---

## 12. Componentes faltantes para una arquitectura contenerizada reproducible

Necesarios y **ausentes** (NO EXISTE):

1. `Dockerfile` multi-stage (deps + app, usuario no root, `PYTHONUNBUFFERED`).
2. `docker-compose.yml` con servicios al menos: `db` (Postgres 16 + volumen), `web`, `pipeline` (o `worker` one-shot/cron).
3. Volumen para `data/raw` y opcionalmente `data/processed` / `data/simulaciones`.
4. `./database/schema.sql` aplicado por entrypoint o servicio `migrate`.
5. Red interna; web no publica Postgres.
6. Healthchecks: `pg_isready`, `GET /salud` interpretado como ready solo si `ok`.
7. `.env` de compose sin secretos en imagen; secrets o env_file.
8. Servicio SMTP de laboratorio (MailHog) para demostración sin Internet de correo.
9. Bind 0.0.0.0 detrás de compose; no solo 127.0.0.1.
10. `.dockerignore` (excluir `.venv`, `data/raw`, `.env`).
11. Job de pipeline programado (`ofelia`, cron sidecar, o restart `on-failure` con intervalo documentado).
12. CI que construya la imagen y corra pytest contra el servicio `db`.

Opcionales para el objetivo “eventos + medible”:

- Worker de outbox separado del job de ingesta.
- Export Prometheus / OpenTelemetry.
- Identificador interno surrogate además del id de fuente.
- Autenticación del panel.
- Reverse proxy (Caddy/nginx) con TLS de desarrollo.

---

## Inventario de componentes (visión C4)

| Componente C4 (propuesto para diagramas) | Tipo | Estado actual |
|------------------------------------------|------|----------------|
| Persona: usuario suscriptor | Actor | IMPLEMENTADO Y VERIFICADO (flujo form + confirmación; SMTP real no) |
| Persona: investigador / demo | Actor | IMPLEMENTADO (panel abierto) |
| Sistema: Sistema-Notificacion-Agua | Software System | IMPLEMENTADO (MVP monolítico) |
| Contenedor: Cliente de ingesta | `recolector` | IMPLEMENTADO Y VERIFICADO |
| Contenedor: Normalización | `normalizador` + calidad | IMPLEMENTADO Y VERIFICADO |
| Contenedor: Persistencia e historial | `persistencia` + PostgreSQL | IMPLEMENTADO Y VERIFICADO |
| Contenedor: Correspondencia | `correspondencia` | IMPLEMENTADO Y VERIFICADO |
| Contenedor: Gestión de suscripciones | `suscripciones` + web POST | IMPLEMENTADO Y VERIFICADO / POST sin test |
| Contenedor: Outbox y envío | `notificaciones` | IMPLEMENTADO Y VERIFICADO (simulación) |
| Contenedor: Orquestador pipeline | `pipeline` | IMPLEMENTADO Y VERIFICADO |
| Contenedor: Panel web | FastAPI | IMPLEMENTADO Y VERIFICADO |
| Contenedor: Evaluador experimental | `evaluacion` | IMPLEMENTADO Y VERIFICADO (casos pequeños) |
| Contenedor: PostgreSQL | BD | IMPLEMENTADO (instalación local; no imagen) |
| Contenedor: Sistema de archivos de capturas | `data/` | IMPLEMENTADO SIN VERIFICAR (gitignore; no backup) |
| Sistema externo: API cortedeagua.net.pe | External | IMPLEMENTADO como cliente; no controlado |
| Sistema externo: SMTP | External | PARCIAL (código listo; desactivado por defecto) |
| Contenedor: Docker Compose / orquestación | Runtime | NO EXISTE |
| Contenedor: Broker de eventos | Runtime | NO EXISTE (eventos = filas SQL) |
| Contenedor: Observabilidad | Runtime | NO EXISTE |
| Contenedor: CI | Runtime | NO EXISTE |

---

## Tabla de brechas: actual vs arquitectura objetivo

Objetivo declarado para la tesis (interpretación de esta auditoría, no un documento de producto aparte): **modular, contenerizada, orientada a eventos y medible experimentalmente**.

| Dimensión | Arquitectura actual (evidencia en repo) | Arquitectura objetivo | Brecha |
|-----------|-----------------------------------------|----------------------|--------|
| Modularidad | Paquete Python único; módulos por etapa | Contenedores/servicios con fronteras claras (ingesta, dominio, outbox, web) | Media: módulos existen; no hay procesos ni imágenes separados |
| Eventos | Historial + outbox SQL; pipeline síncrono | Productor/consumidor desacoplados; at-least-once explícito; DLQ | Media: patrón outbox sí; no hay bus ni worker autónomo |
| Contenerización | venv + Postgres del host | Compose reproducible (app, db, job, smtp lab) | **Alta — NO EXISTE** |
| Datos | PK = id fuente; JSONB; tres hashes | Id interno + id fuente; migraciones versionadas | Media |
| Seguridad | Panel abierto; correo en claro; token en URL | Auth de panel, secretos, TLS, no filtrar tokens | **Alta** |
| Automatización | CLI + script PowerShell documentado | Scheduler en contenedor + CI | Alta |
| Observabilidad | logging INFO + columnas de tiempo + `/salud` | Trazas, métricas, logs estructurados, probes | Alta |
| Evaluación | 7+5 casos etiquetados; tiempos de ejecución reales documentados una vez | Suite experimental reproducible en compose (precisión, recall, idempotencia, latencia controlada) | Media: base existe; no empaquetada ni escalada |
| Disponibilidad | Un host, un Postgres, una API externa | Reintentos de job, volumen persistente, degradación documentada | Media (reintentos HTTP sí; HA no) |
| Interfaz | HTML servidor + CDN | Misma UI servida desde imagen, assets locales | Baja/media |

### Lectura para diagramas C4 y de despliegue

- **C4 Nivel 1 (contexto):** Sistema académico → API de terceros, PostgreSQL, SMTP opcional, usuario, investigador. El CDN Bootstrap es dependencia de la UI.
- **C4 Nivel 2 (contenedores) hoy:** un contenedor lógico “aplicación Python” + “PostgreSQL” + “filesystem”. Dibujar Docker como *objetivo*, no como as-is.
- **C4 Nivel 3 (componentes):** los módulos de la sección 3; el pipeline es el orquestador, no un bus.
- **Despliegue as-is:** un nodo (Windows/Linux), procesos `python -m src.web` y `python -m src.pipeline`, Postgres localhost, directorio `data/`.
- **Despliegue to-be:** servicios Compose (db, web, pipeline-cron, mailhog) y volúmenes; pendiente de implementación.

---

## Limitaciones de esta auditoría

- No se ejecutó pytest, pipeline ni consultas SQL contra la base.
- No se inspeccionó el contenido de `.env` local (está en `.gitignore`).
- Los archivos bajo `data/raw` y `data/simulaciones` pueden existir en el disco de desarrollo; no forman parte del diseño versionado.
- `docs/ARQUITECTURA.md` describe el diseño del MVP; este diagnóstico prevalece cuando hay diferencia entre prosa y código (p. ej. `ADMIN_TOKEN` no autentica; no hay Docker).
