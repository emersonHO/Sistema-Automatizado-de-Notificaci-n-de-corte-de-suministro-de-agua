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
    modo TEXT NOT NULL DEFAULT 'simulacion'
);
