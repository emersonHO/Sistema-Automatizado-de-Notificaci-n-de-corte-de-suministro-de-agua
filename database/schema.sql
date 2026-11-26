-- Esquema completo del MVP. Idempotente (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
-- No elimina tablas ni registros existentes.

CREATE TABLE IF NOT EXISTS interrupciones (
    id BIGINT PRIMARY KEY,
    cod_incidencia TEXT,
    empresa TEXT,
    municipalidad TEXT,
    municipalidad_normalizada TEXT,
    areas_afectadas TEXT,
    tipo_incid TEXT,
    estado TEXT,
    infor_web TEXT,
    causa TEXT,
    ciudad TEXT,
    fec_deteccion TIMESTAMP,
    fec_estimada TIMESTAMP,
    actualizado_en_fuente TIMESTAMP,
    ambito_lima BOOLEAN,
    datos JSONB NOT NULL,
    hash_contenido CHAR(64),
    hash_origen CHAR(64) NOT NULL DEFAULT repeat('0', 64),
    hash_relevante CHAR(64) NOT NULL DEFAULT repeat('0', 64),
    version_origen INTEGER NOT NULL DEFAULT 1,
    version_relevante INTEGER NOT NULL DEFAULT 1,
    primera_captura TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ultima_captura TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE interrupciones ADD COLUMN IF NOT EXISTS municipalidad_normalizada TEXT;
ALTER TABLE interrupciones ADD COLUMN IF NOT EXISTS estado TEXT;
ALTER TABLE interrupciones ADD COLUMN IF NOT EXISTS infor_web TEXT;
ALTER TABLE interrupciones ADD COLUMN IF NOT EXISTS causa TEXT;
ALTER TABLE interrupciones ADD COLUMN IF NOT EXISTS ciudad TEXT;
ALTER TABLE interrupciones ADD COLUMN IF NOT EXISTS ambito_lima BOOLEAN;
ALTER TABLE interrupciones ADD COLUMN IF NOT EXISTS hash_contenido CHAR(64);
ALTER TABLE interrupciones ADD COLUMN IF NOT EXISTS hash_origen CHAR(64);
ALTER TABLE interrupciones ADD COLUMN IF NOT EXISTS hash_relevante CHAR(64);
ALTER TABLE interrupciones ADD COLUMN IF NOT EXISTS version_origen INTEGER NOT NULL DEFAULT 1;
ALTER TABLE interrupciones ADD COLUMN IF NOT EXISTS version_relevante INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS idx_interrupciones_municipalidad
ON interrupciones (municipalidad);

CREATE INDEX IF NOT EXISTS idx_interrupciones_mun_norm
ON interrupciones (municipalidad_normalizada);

CREATE INDEX IF NOT EXISTS idx_interrupciones_fecha
ON interrupciones (fec_deteccion);

CREATE INDEX IF NOT EXISTS idx_interrupciones_tipo
ON interrupciones (tipo_incid);

CREATE TABLE IF NOT EXISTS ejecuciones_proceso (
    id BIGSERIAL PRIMARY KEY,
    fecha_inicio TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_fin TIMESTAMPTZ,
    estado TEXT NOT NULL DEFAULT 'EN_PROCESO',
    registros_leidos INTEGER NOT NULL DEFAULT 0,
    registros_nuevos INTEGER NOT NULL DEFAULT 0,
    registros_actualizados INTEGER NOT NULL DEFAULT 0,
    registros_sin_cambios INTEGER NOT NULL DEFAULT 0,
    cambios_origen INTEGER NOT NULL DEFAULT 0,
    cambios_relevantes INTEGER NOT NULL DEFAULT 0,
    cambios_tecnicos INTEGER NOT NULL DEFAULT 0,
    coincidencias INTEGER NOT NULL DEFAULT 0,
    coincidencias_ambiguas INTEGER NOT NULL DEFAULT 0,
    notificaciones_creadas INTEGER NOT NULL DEFAULT 0,
    captura_completa BOOLEAN,
    tiempo_descarga_ms INTEGER,
    tiempo_normalizacion_ms INTEGER,
    tiempo_persistencia_ms INTEGER,
    tiempo_correspondencia_ms INTEGER,
    tiempo_notificaciones_ms INTEGER,
    ruta_captura TEXT,
    mensaje_error TEXT,
    detalle JSONB
);

ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS cambios_origen INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS cambios_relevantes INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS cambios_tecnicos INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS coincidencias INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS coincidencias_ambiguas INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS notificaciones_creadas INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS captura_completa BOOLEAN;
ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS tiempo_descarga_ms INTEGER;
ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS tiempo_normalizacion_ms INTEGER;
ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS tiempo_persistencia_ms INTEGER;
ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS tiempo_correspondencia_ms INTEGER;
ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS tiempo_notificaciones_ms INTEGER;
ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS ruta_captura TEXT;
ALTER TABLE ejecuciones_proceso ADD COLUMN IF NOT EXISTS detalle JSONB;

-- Fase 2: cola de solicitudes (n8n). Aditivo; no elimina datos.
CREATE TABLE IF NOT EXISTS solicitudes_ejecucion (
    id BIGSERIAL PRIMARY KEY,
    estado TEXT NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN (
            'PENDIENTE',
            'EN_PROCESO',
            'COMPLETADO',
            'COMPLETADO_INCOMPLETO',
            'ERROR',
            'ERROR_RECUPERACION',
            'CANCELADA'
        )),
    origen TEXT NOT NULL
        CHECK (origen IN ('MANUAL', 'PROGRAMADA')),
    modo TEXT NOT NULL DEFAULT 'api'
        CHECK (modo IN ('api', 'fixture')),
    ruta_fixture TEXT,
    idempotency_key TEXT UNIQUE,
    ejecucion_id BIGINT REFERENCES ejecuciones_proceso (id),
    creada_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reclamada_en TIMESTAMPTZ,
    heartbeat_en TIMESTAMPTZ,
    lease_hasta TIMESTAMPTZ,
    finalizada_en TIMESTAMPTZ,
    worker_id TEXT,
    backend_pid INTEGER,
    intentos_worker INTEGER NOT NULL DEFAULT 0,
    max_intentos INTEGER NOT NULL DEFAULT 3,
    mensaje_error TEXT,
    detalle JSONB,
    cuerpo_origen TEXT NOT NULL,
    cuerpo_solo_si_libre BOOLEAN NOT NULL DEFAULT FALSE,
    cuerpo_modo TEXT NOT NULL DEFAULT 'api',
    cuerpo_ruta_fixture TEXT
);

CREATE INDEX IF NOT EXISTS idx_solicitudes_pendientes
    ON solicitudes_ejecucion (id)
    WHERE estado = 'PENDIENTE';

CREATE INDEX IF NOT EXISTS idx_solicitudes_en_proceso
    ON solicitudes_ejecucion (lease_hasta)
    WHERE estado = 'EN_PROCESO';

ALTER TABLE ejecuciones_proceso
    ADD COLUMN IF NOT EXISTS solicitud_id BIGINT REFERENCES solicitudes_ejecucion (id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ejecuciones_solicitud
    ON ejecuciones_proceso (solicitud_id)
    WHERE solicitud_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS capturas (
    id BIGSERIAL PRIMARY KEY,
    ejecucion_id BIGINT REFERENCES ejecuciones_proceso (id),
    fecha_captura TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    parametro_dias INTEGER,
    total_reportado INTEGER,
    total_recibido INTEGER,
    captura_completa BOOLEAN NOT NULL DEFAULT TRUE,
    last_sync TEXT,
    last_new_at TEXT,
    ruta_archivo TEXT NOT NULL,
    ruta_meta TEXT,
    anomalias JSONB
);

CREATE TABLE IF NOT EXISTS historial_interrupciones (
    id BIGSERIAL PRIMARY KEY,
    interrupcion_id BIGINT NOT NULL REFERENCES interrupciones (id),
    version_origen INTEGER NOT NULL,
    version_relevante INTEGER NOT NULL,
    tipo_evento TEXT NOT NULL,
    cambio_relevante BOOLEAN NOT NULL DEFAULT FALSE,
    hash_origen CHAR(64) NOT NULL,
    hash_relevante CHAR(64) NOT NULL,
    campos_modificados JSONB,
    datos JSONB NOT NULL,
    fecha_registro TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (interrupcion_id, version_origen)
);

CREATE INDEX IF NOT EXISTS idx_historial_interrupcion
ON historial_interrupciones (interrupcion_id, fecha_registro DESC);

CREATE TABLE IF NOT EXISTS zonas (
    id BIGSERIAL PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('DISTRITO', 'SECTOR', 'AREA')),
    nombre TEXT NOT NULL,
    nombre_normalizado TEXT NOT NULL,
    distrito_padre TEXT,
    ambito_lima BOOLEAN NOT NULL DEFAULT TRUE,
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (tipo, nombre_normalizado)
);

CREATE INDEX IF NOT EXISTS idx_zonas_norm ON zonas (nombre_normalizado);

CREATE TABLE IF NOT EXISTS usuarios (
    id BIGSERIAL PRIMARY KEY,
    correo TEXT NOT NULL UNIQUE,
    correo_confirmado BOOLEAN NOT NULL DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    token_confirmacion TEXT UNIQUE,
    token_generado_en TIMESTAMPTZ,
    confirmado_en TIMESTAMPTZ,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS suscripciones (
    id BIGSERIAL PRIMARY KEY,
    usuario_id BIGINT NOT NULL REFERENCES usuarios (id),
    zona_id BIGINT NOT NULL REFERENCES zonas (id),
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    confirmada BOOLEAN NOT NULL DEFAULT FALSE,
    creada_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    baja_en TIMESTAMPTZ,
    UNIQUE (usuario_id, zona_id)
);

CREATE INDEX IF NOT EXISTS idx_suscripciones_zona
ON suscripciones (zona_id) WHERE activa AND confirmada;

CREATE TABLE IF NOT EXISTS coincidencias_territoriales (
    id BIGSERIAL PRIMARY KEY,
    ejecucion_id BIGINT REFERENCES ejecuciones_proceso (id),
    interrupcion_id BIGINT NOT NULL REFERENCES interrupciones (id),
    suscripcion_id BIGINT NOT NULL REFERENCES suscripciones (id),
    zona_id BIGINT NOT NULL REFERENCES zonas (id),
    nivel TEXT NOT NULL CHECK (nivel IN ('DISTRITO', 'SECTOR', 'AREA')),
    estado TEXT NOT NULL CHECK (estado IN ('POTENCIAL', 'ESPECIFICA', 'AMBIGUA', 'EXCLUIDA_AMBITO')),
    explicacion TEXT NOT NULL,
    fecha_registro TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coincidencias_inc
ON coincidencias_territoriales (interrupcion_id, fecha_registro DESC);

CREATE TABLE IF NOT EXISTS notificaciones (
    id BIGSERIAL PRIMARY KEY,
    usuario_id BIGINT NOT NULL REFERENCES usuarios (id),
    suscripcion_id BIGINT NOT NULL REFERENCES suscripciones (id),
    interrupcion_id BIGINT NOT NULL REFERENCES interrupciones (id),
    coincidencia_id BIGINT REFERENCES coincidencias_territoriales (id),
    version_relevante INTEGER NOT NULL,
    hash_relevante CHAR(64) NOT NULL,
    tipo_evento TEXT NOT NULL CHECK (tipo_evento IN ('NUEVA', 'MODIFICADA', 'CANCELADA')),
    nivel_coincidencia TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN (
            'PENDIENTE', 'SIMULADA', 'ACEPTADA_SMTP', 'FALLIDA', 'DESCARTADA'
        )),
    asunto TEXT,
    cuerpo_texto TEXT,
    cuerpo_html TEXT,
    ultimo_error TEXT,
    intentos INTEGER NOT NULL DEFAULT 0,
    creada_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizada_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (suscripcion_id, interrupcion_id, version_relevante, tipo_evento)
);

CREATE INDEX IF NOT EXISTS idx_notificaciones_estado
ON notificaciones (estado, creada_en DESC);

CREATE TABLE IF NOT EXISTS intentos_notificacion (
    id BIGSERIAL PRIMARY KEY,
    notificacion_id BIGINT NOT NULL REFERENCES notificaciones (id),
    fecha_intento TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resultado TEXT NOT NULL,
    codigo_smtp TEXT,
    mensaje TEXT,
    modo TEXT NOT NULL DEFAULT 'simulacion',
    worker_id TEXT
);

ALTER TABLE intentos_notificacion ADD COLUMN IF NOT EXISTS worker_id TEXT;

-- Fase 3: columnas de reclamo, reintento y trazabilidad (aditivo, no destructivo).
ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS canal TEXT NOT NULL DEFAULT 'simulacion';
ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS motivo TEXT;
ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS proximo_intento TIMESTAMPTZ;
ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS max_intentos INTEGER NOT NULL DEFAULT 5;
ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS worker_id TEXT;
ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS heartbeat_en TIMESTAMPTZ;
ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS backend_pid INTEGER;
ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS procesada_en TIMESTAMPTZ;
ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS finalizada_en TIMESTAMPTZ;
ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS recuperaciones INTEGER NOT NULL DEFAULT 0;

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT c.conname
        FROM pg_constraint c
        WHERE c.conrelid = 'notificaciones'::regclass
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) LIKE '%PENDIENTE%'
          AND pg_get_constraintdef(c.oid) LIKE '%estado%'
    LOOP
        EXECUTE format('ALTER TABLE notificaciones DROP CONSTRAINT %I', r.conname);
    END LOOP;
    ALTER TABLE notificaciones ADD CONSTRAINT notificaciones_estado_check
        CHECK (estado IN (
            'PENDIENTE',
            'EN_PROCESO',
            'REINTENTANDO',
            'SIMULADA',
            'ACEPTADA_SMTP',
            'FALLIDA',
            'ERROR',
            'DESCARTADA',
            'CANCELADA'
        ));
EXCEPTION
    WHEN duplicate_object THEN
        NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_notificaciones_outbox
ON notificaciones (creada_en)
WHERE estado IN ('PENDIENTE', 'REINTENTANDO', 'FALLIDA', 'EN_PROCESO');

CREATE INDEX IF NOT EXISTS idx_intentos_notificacion
ON intentos_notificacion (notificacion_id, fecha_intento);

-- Operación pública: preferencias, consentimiento, tokens hasheados, rate limit.
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS pausado BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS consentimiento_en TIMESTAMPTZ;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ultimo_reenvio_en TIMESTAMPTZ;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS token_confirmacion_expira TIMESTAMPTZ;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS correo_pendiente TEXT;

ALTER TABLE suscripciones ADD COLUMN IF NOT EXISTS alerta_nueva BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE suscripciones ADD COLUMN IF NOT EXISTS alerta_modificada BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE suscripciones ADD COLUMN IF NOT EXISTS alerta_cancelacion BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE suscripciones ADD COLUMN IF NOT EXISTS resumen_diario BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE suscripciones ADD COLUMN IF NOT EXISTS pausada BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS limitacion_solicitudes (
    id BIGSERIAL PRIMARY KEY,
    clave TEXT NOT NULL,
    ocurrida_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_limitacion_clave_tiempo
    ON limitacion_solicitudes (clave, ocurrida_en DESC);

ALTER TABLE interrupciones ADD COLUMN IF NOT EXISTS areas_partes JSONB;
ALTER TABLE interrupciones ADD COLUMN IF NOT EXISTS sectores_detectados TEXT;

CREATE INDEX IF NOT EXISTS idx_interrupciones_areas_gin
ON interrupciones USING GIN (areas_partes);

CREATE TABLE IF NOT EXISTS resumenes_enviados (
    id BIGSERIAL PRIMARY KEY,
    usuario_id BIGINT NOT NULL REFERENCES usuarios (id),
    fecha_local DATE NOT NULL,
    estado TEXT NOT NULL,
    detalle TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (usuario_id, fecha_local)
);

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS aviso_inmediato BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ventana_inicio TIME;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ventana_fin TIME;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS resumen_frecuencia TEXT NOT NULL DEFAULT 'ninguno';
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS informe_sin_cortes BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS alerta_programada BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS alerta_imprevista BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS silenciar_finde BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS formato_correo TEXT NOT NULL DEFAULT 'completo';
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS max_avisos_dia INTEGER NOT NULL DEFAULT 8;

ALTER TABLE suscripciones ADD COLUMN IF NOT EXISTS incluir_todo_distrito BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE resumenes_enviados ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'diario';
ALTER TABLE resumenes_enviados DROP CONSTRAINT IF EXISTS resumenes_enviados_usuario_id_fecha_local_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_resumenes_usuario_fecha_tipo
    ON resumenes_enviados (usuario_id, fecha_local, tipo);
