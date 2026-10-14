
CREATE TABLE IF NOT EXISTS interrupciones (
    id BIGINT PRIMARY KEY,
    cod_incidencia TEXT,
    empresa TEXT,
    municipalidad TEXT,
    areas_afectadas TEXT,
    tipo_incid TEXT,
    fec_deteccion TIMESTAMP,
    fec_estimada TIMESTAMP,
    actualizado_en_fuente TIMESTAMP,
    datos JSONB NOT NULL,
    hash_contenido CHAR(64) NOT NULL,
    primera_captura TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ultima_captura TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_interrupciones_municipalidad
ON interrupciones (municipalidad);

CREATE INDEX IF NOT EXISTS idx_interrupciones_fecha
ON interrupciones (fec_deteccion);

CREATE TABLE IF NOT EXISTS ejecuciones_proceso (
    id BIGSERIAL PRIMARY KEY,
    fecha_inicio TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_fin TIMESTAMPTZ,
    estado TEXT NOT NULL DEFAULT 'EN_PROCESO',
    registros_leidos INTEGER NOT NULL DEFAULT 0,
    registros_nuevos INTEGER NOT NULL DEFAULT 0,
    registros_actualizados INTEGER NOT NULL DEFAULT 0,
    registros_sin_cambios INTEGER NOT NULL DEFAULT 0,
    mensaje_error TEXT
);
