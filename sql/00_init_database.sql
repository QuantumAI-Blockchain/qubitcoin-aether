CREATE DATABASE IF NOT EXISTS qubitcoin;
SET DATABASE = qubitcoin;
CREATE USER IF NOT EXISTS qbc_app WITH PASSWORD 'change_this_password';
GRANT ALL ON DATABASE qubitcoin TO qbc_app;
CREATE TABLE IF NOT EXISTS schema_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version VARCHAR(20) NOT NULL,
    component VARCHAR(50) NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT now(),
    description TEXT,
    UNIQUE INDEX version_component_idx (version, component)
);
INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'core', 'Initial database setup');
