-- ================================================================
-- QUBITCOIN DATABASE INITIALIZATION
-- Production-Grade Schema v2.0.0
-- Note: CREATE USER with password is skipped in insecure mode.
--       The qbc_app user is only needed in production (TLS mode).
-- ================================================================

CREATE DATABASE IF NOT EXISTS qubitcoin;
SET DATABASE = qubitcoin;

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version VARCHAR(20) NOT NULL,
    component VARCHAR(50) NOT NULL,
    description TEXT,
    applied_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE INDEX version_component_idx (version, component)
);

-- Supply tracking (used by genesis and node)
CREATE TABLE IF NOT EXISTS supply (
    id BIGINT PRIMARY KEY DEFAULT 1,
    total_minted DECIMAL DEFAULT 0
);

INSERT INTO supply (id, total_minted) VALUES (1, 0) ON CONFLICT (id) DO NOTHING;

INSERT INTO schema_version (version, component, description)
VALUES ('2.0.0', 'init', 'Database initialization')
ON CONFLICT DO NOTHING;
