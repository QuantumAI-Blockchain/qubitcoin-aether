-- ================================================================
-- QUSD STABLECOIN — Configuration & Balances
-- Domain: stablecoin | Schema v1.0.0
-- ================================================================

SET DATABASE = qubitcoin;

CREATE TABLE IF NOT EXISTS qusd_config (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    initial_supply DECIMAL(30, 8) NOT NULL DEFAULT 3300000000.0,
    current_supply DECIMAL(30, 8) NOT NULL DEFAULT 3300000000.0,
    target_reserve_ratio DECIMAL(5, 4) NOT NULL DEFAULT 1.0000,
    current_reserve_ratio DECIMAL(5, 4) NOT NULL DEFAULT 0.0000,
    is_active BOOL NOT NULL DEFAULT true,
    last_updated TIMESTAMP NOT NULL DEFAULT now()
);

INSERT INTO qusd_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS qusd_balances (
    address BYTES PRIMARY KEY,
    balance DECIMAL(30, 8) NOT NULL DEFAULT 0,
    locked_balance DECIMAL(30, 8) NOT NULL DEFAULT 0,
    total_minted DECIMAL(30, 8) NOT NULL DEFAULT 0,
    total_burned DECIMAL(30, 8) NOT NULL DEFAULT 0,
    INDEX balance_idx (balance DESC)
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'qusd_config', 'QUSD configuration and balances')
ON CONFLICT DO NOTHING;
