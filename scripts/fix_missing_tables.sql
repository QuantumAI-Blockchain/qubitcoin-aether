-- Fix missing tables

-- Stablecoin tokens table
CREATE TABLE IF NOT EXISTS stablecoin_tokens (
    token_id STRING PRIMARY KEY,
    symbol STRING NOT NULL UNIQUE,
    name STRING NOT NULL,
    total_supply DECIMAL(18, 8) DEFAULT 0,
    total_debt DECIMAL(18, 8) DEFAULT 0,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_active (active) WHERE active = true
);

-- Insert QUSD if not exists
INSERT INTO stablecoin_tokens (token_id, symbol, name, total_supply, total_debt, active)
VALUES ('qusd-stable-001', 'QUSD', 'Qubitcoin USD', 0, 0, true)
ON CONFLICT (token_id) DO NOTHING;

-- Stablecoin positions (user collateral)
CREATE TABLE IF NOT EXISTS stablecoin_positions (
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_id STRING NOT NULL REFERENCES stablecoin_tokens(token_id),
    owner_address STRING NOT NULL,
    collateral_type STRING NOT NULL,
    collateral_amount DECIMAL(18, 8) NOT NULL CHECK (collateral_amount >= 0),
    debt_amount DECIMAL(18, 8) NOT NULL CHECK (debt_amount >= 0),
    collateral_ratio DECIMAL(10, 4),
    status STRING NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'liquidated', 'closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_owner (owner_address),
    INDEX idx_status (status),
    INDEX idx_token (token_id)
);

-- Liquidation events
CREATE TABLE IF NOT EXISTS stablecoin_liquidations (
    liquidation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID NOT NULL REFERENCES stablecoin_positions(position_id),
    liquidator_address STRING NOT NULL,
    collateral_seized DECIMAL(18, 8) NOT NULL,
    debt_repaid DECIMAL(18, 8) NOT NULL,
    penalty_amount DECIMAL(18, 8) NOT NULL,
    liquidated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_position (position_id),
    INDEX idx_liquidator (liquidator_address)
);

-- Contract storage
CREATE TABLE IF NOT EXISTS contract_storage (
    contract_id STRING NOT NULL,
    storage_key STRING NOT NULL,
    storage_value JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (contract_id, storage_key),
    INDEX idx_contract (contract_id)
);

-- Contract events
CREATE TABLE IF NOT EXISTS contract_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id STRING NOT NULL,
    event_name STRING NOT NULL,
    event_data JSONB NOT NULL,
    block_height INT,
    tx_id STRING,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_contract (contract_id),
    INDEX idx_event_name (event_name),
    INDEX idx_block (block_height)
);

-- Contract deployments
CREATE TABLE IF NOT EXISTS contract_deployments (
    deployment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id STRING NOT NULL UNIQUE,
    deployer_address STRING NOT NULL,
    contract_type STRING NOT NULL,
    deployment_tx STRING,
    block_height INT,
    deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_deployer (deployer_address),
    INDEX idx_type (contract_type)
);

ANALYZE stablecoin_tokens;
ANALYZE stablecoin_positions;
ANALYZE stablecoin_liquidations;
ANALYZE contract_storage;
ANALYZE contract_events;
ANALYZE contract_deployments;
