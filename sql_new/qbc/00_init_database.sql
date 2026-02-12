-- ================================================================
-- QUBITCOIN DATABASE INITIALIZATION
-- Production-Grade Schema v1.0.0
-- ================================================================

CREATE DATABASE IF NOT EXISTS qubitcoin;
SET DATABASE = qubitcoin;

-- Application user
CREATE USER IF NOT EXISTS qbc_app WITH PASSWORD 'CHANGE_THIS_IN_PRODUCTION';
GRANT ALL ON DATABASE qubitcoin TO qbc_app;

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version VARCHAR(20) NOT NULL,
    component VARCHAR(50) NOT NULL,
    description TEXT,
    applied_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE INDEX version_component_idx (version, component)
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'init', 'Database initialization')
ON CONFLICT DO NOTHING;
