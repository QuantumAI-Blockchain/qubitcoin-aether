-- ================================================================
-- QUSD STABLECOIN — Reserves & Debt Tracking
-- Domain: stablecoin | Schema v1.0.0
-- ================================================================

SET DATABASE = qubitcoin;

CREATE TABLE IF NOT EXISTS qusd_reserves (
    reserve_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type VARCHAR(50) NOT NULL,
    amount DECIMAL(30, 8) NOT NULL DEFAULT 0,
    usd_value DECIMAL(30, 8) NOT NULL DEFAULT 0,
    storage_type VARCHAR(50) NOT NULL,
    is_verified BOOL NOT NULL DEFAULT false,
    last_updated TIMESTAMP NOT NULL DEFAULT now(),
    INDEX asset_type_idx (asset_type)
);

CREATE TABLE IF NOT EXISTS qusd_debt (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    total_debt DECIMAL(30, 8) NOT NULL DEFAULT 3300000000.0,
    total_reserves_usd DECIMAL(30, 8) NOT NULL DEFAULT 0,
    backing_percentage DECIMAL(5, 2) GENERATED ALWAYS AS (
        CASE WHEN total_debt > 0 THEN (total_reserves_usd / total_debt * 100) ELSE 100 END
    ) STORED,
    last_updated TIMESTAMP NOT NULL DEFAULT now()
);

INSERT INTO qusd_debt (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'qusd_reserves', 'QUSD reserves and debt tracking')
ON CONFLICT DO NOTHING;
