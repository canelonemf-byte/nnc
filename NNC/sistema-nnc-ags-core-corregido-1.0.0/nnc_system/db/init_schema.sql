-- Esquema Oficial de Auditoría y Eventos para NNC + AGs-Core Database

CREATE TABLE IF NOT EXISTS eventos_auditados (
    id VARCHAR(64) PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    dominio VARCHAR(32) NOT NULL,
    ecef_x DOUBLE PRECISION NOT NULL,
    ecef_y DOUBLE PRECISION NOT NULL,
    ecef_z DOUBLE PRECISION NOT NULL,
    latitud DOUBLE PRECISION,
    longitud DOUBLE PRECISION,
    altitud_m DOUBLE PRECISION,
    velocidad_m_s DOUBLE PRECISION,
    mach DOUBLE PRECISION,
    gap_triangulacion_m DOUBLE PRECISION,
    estado_clasificacion VARCHAR(64) NOT NULL,
    filtro_h7_animal VARCHAR(64),
    subagente_lora_cargo VARCHAR(64),
    firma_seguridad_hmac VARCHAR(128)
);

CREATE TABLE IF NOT EXISTS metricas_subagentes (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    subagente VARCHAR(64) NOT NULL,
    latencia_ms DOUBLE PRECISION NOT NULL,
    eventos_procesados INT DEFAULT 0,
    memoria_vram_kb DOUBLE PRECISION
);

-- Índices de consulta rápida por dominio y estado
CREATE INDEX IF NOT EXISTS idx_eventos_dominio ON eventos_auditados(dominio);
CREATE INDEX IF NOT EXISTS idx_eventos_estado ON eventos_auditados(estado_clasificacion);
CREATE INDEX IF NOT EXISTS idx_eventos_timestamp ON eventos_auditados(timestamp);
