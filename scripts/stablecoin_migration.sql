-- ============================================================================
-- QUSD STABLECOIN MIGRATION - Integrates with existing contract system
-- ============================================================================
-- Adds stablecoin-specific tables while using existing contracts/token_balances
-- ============================================================================

-- ============================================================================
-- TOKEN METADATA (extends existing token_balances)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tokens (
    token_id STRING PRIMARY KEY,
    contract_id STRING REFERENCES contracts(contract_id),
    symbol STRING UNIQUE NOT NULL,
    name STRING NOT NULL,
    decimals INT DEFAULT 8,
    total_supply DECIMAL(28, 8) DEFAULT 0,
    token_type STRING NOT NULL CHECK (token_type IN ('native', 'stablecoin', 'wrapped', 'governance', 'utility')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT true,
    INDEX idx_symbol (symbol),
    INDEX idx_type (token_type),
    INDEX idx_contract (contract_id)
);

-- Token transfer history
CREATE TABLE IF NOT EXISTS token_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_id STRING REFERENCES tokens(token_id),
    from_address STRING NOT NULL,
    to_address STRING NOT NULL,
    amount DECIMAL(28, 8) NOT NULL,
    txid STRING NOT NULL,
    block_height INT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_from (from_address, timestamp DESC),
    INDEX idx_to (to_address, timestamp DESC),
    INDEX idx_token (token_id, timestamp DESC),
    INDEX idx_txid (txid)
);

-- ============================================================================
-- COLLATERAL SYSTEM (Multi-asset backing)
-- ============================================================================

CREATE TABLE IF NOT EXISTS collateral_types (
    id SERIAL PRIMARY KEY,
    asset_name STRING UNIQUE NOT NULL,
    asset_type STRING NOT NULL CHECK (asset_type IN ('stablecoin', 'crypto', 'native')),
    oracle_feed STRING, -- Price feed identifier
    liquidation_ratio DECIMAL(5, 4) NOT NULL CHECK (liquidation_ratio > 1.0),
    stability_fee DECIMAL(8, 6) DEFAULT 0, -- Annual %
    debt_ceiling DECIMAL(28, 8), -- Max QUSD mintable
    min_collateral DECIMAL(28, 8) DEFAULT 10,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_active (active) WHERE active = true
);

-- Collateral vaults (CDP positions)
CREATE TABLE IF NOT EXISTS collateral_vaults (
    vault_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_address STRING NOT NULL,
    collateral_type_id INT REFERENCES collateral_types(id),
    collateral_amount DECIMAL(28, 8) NOT NULL CHECK (collateral_amount >= 0),
    debt_amount DECIMAL(28, 8) NOT NULL CHECK (debt_amount >= 0),
    collateral_ratio DECIMAL(10, 4),
    interest_accrued DECIMAL(28, 8) DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    liquidated BOOLEAN DEFAULT false,
    liquidated_at TIMESTAMP,
    INDEX idx_owner (owner_address),
    INDEX idx_health (collateral_ratio) WHERE NOT liquidated,
    INDEX idx_type (collateral_type_id)
);

-- ============================================================================
-- RESERVE BACKING (100% reserves for bridged stables)
-- ============================================================================

CREATE TABLE IF NOT EXISTS stable_reserves (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_name STRING NOT NULL,
    amount DECIMAL(28, 8) NOT NULL CHECK (amount >= 0),
    reserve_address STRING NOT NULL, -- Multi-sig vault
    proof_hash STRING NOT NULL, -- Merkle root
    quantum_proof JSONB NOT NULL, -- VQE proof
    block_height INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_asset (asset_name),
    INDEX idx_block (block_height DESC)
);

-- Reserve snapshots (hourly audits)
CREATE TABLE IF NOT EXISTS reserve_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    total_qusd_supply DECIMAL(28, 8) NOT NULL,
    total_reserves_usd DECIMAL(28, 8) NOT NULL,
    collateralization_ratio DECIMAL(10, 4) NOT NULL,
    reserve_breakdown JSONB NOT NULL,
    block_height INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_block (block_height DESC),
    INDEX idx_time (timestamp DESC)
);

-- ============================================================================
-- ORACLE SYSTEM
-- ============================================================================

CREATE TABLE IF NOT EXISTS oracle_sources (
    id SERIAL PRIMARY KEY,
    source_name STRING UNIQUE NOT NULL,
    source_type STRING NOT NULL CHECK (source_type IN ('chainlink', 'band', 'uniswap', 'native', 'aggregated')),
    endpoint STRING,
    public_key STRING,
    reliability_score INT DEFAULT 100 CHECK (reliability_score >= 0 AND reliability_score <= 100),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_active (active) WHERE active = true
);

CREATE TABLE IF NOT EXISTS price_feeds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_pair STRING NOT NULL,
    price DECIMAL(18, 8) NOT NULL CHECK (price > 0),
    source_id INT REFERENCES oracle_sources(id),
    confidence DECIMAL(5, 4),
    block_height INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    signature STRING,
    INDEX idx_pair_time (asset_pair, timestamp DESC),
    INDEX idx_block (block_height DESC)
);

CREATE TABLE IF NOT EXISTS aggregated_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_pair STRING NOT NULL,
    median_price DECIMAL(18, 8) NOT NULL,
    mean_price DECIMAL(18, 8) NOT NULL,
    std_deviation DECIMAL(18, 8),
    num_sources INT NOT NULL,
    min_price DECIMAL(18, 8),
    max_price DECIMAL(18, 8),
    block_height INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid BOOLEAN DEFAULT true,
    INDEX idx_pair_valid (asset_pair, timestamp DESC) WHERE valid = true,
    INDEX idx_block (block_height DESC)
);

-- ============================================================================
-- STABLECOIN OPERATIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS qusd_operations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_type STRING NOT NULL CHECK (operation_type IN ('mint', 'burn', 'liquidation', 'interest')),
    user_address STRING NOT NULL,
    amount DECIMAL(28, 8) NOT NULL,
    collateral_locked DECIMAL(28, 8),
    collateral_type STRING,
    price_at_operation DECIMAL(18, 8),
    quantum_proof JSONB NOT NULL,
    txid STRING NOT NULL,
    block_height INT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status STRING NOT NULL CHECK (status IN ('pending', 'confirmed', 'failed')),
    failure_reason STRING,
    INDEX idx_user (user_address, timestamp DESC),
    INDEX idx_type (operation_type),
    INDEX idx_status (status, timestamp DESC) WHERE status = 'pending',
    INDEX idx_txid (txid)
);

CREATE TABLE IF NOT EXISTS liquidations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vault_id UUID REFERENCES collateral_vaults(vault_id),
    owner_address STRING NOT NULL,
    collateral_seized DECIMAL(28, 8) NOT NULL,
    debt_covered DECIMAL(28, 8) NOT NULL,
    liquidator_address STRING,
    liquidation_price DECIMAL(18, 8) NOT NULL,
    penalty_amount DECIMAL(28, 8),
    block_height INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_owner (owner_address),
    INDEX idx_liquidator (liquidator_address),
    INDEX idx_block (block_height DESC)
);

-- ============================================================================
-- SYSTEM PARAMETERS & RISK
-- ============================================================================

CREATE TABLE IF NOT EXISTS stablecoin_params (
    param_name STRING PRIMARY KEY,
    param_value STRING NOT NULL,
    param_type STRING NOT NULL CHECK (param_type IN ('decimal', 'integer', 'boolean', 'string')),
    description STRING,
    min_value STRING,
    max_value STRING,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by STRING
);

CREATE TABLE IF NOT EXISTS risk_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name STRING NOT NULL,
    metric_value DECIMAL(18, 8) NOT NULL,
    threshold_warning DECIMAL(18, 8),
    threshold_critical DECIMAL(18, 8),
    status STRING NOT NULL CHECK (status IN ('normal', 'warning', 'critical')),
    block_height INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    alert_sent BOOLEAN DEFAULT false,
    INDEX idx_status (status, timestamp DESC) WHERE status != 'normal',
    INDEX idx_metric (metric_name, timestamp DESC)
);

CREATE TABLE IF NOT EXISTS emergency_shutdowns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reason STRING NOT NULL,
    triggered_by STRING NOT NULL,
    block_height INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP,
    resolution_details STRING
);

-- ============================================================================
-- VIEWS
-- ============================================================================

CREATE VIEW IF NOT EXISTS qusd_health AS
SELECT 
    (SELECT total_supply FROM tokens WHERE symbol = 'QUSD') AS total_qusd,
    (SELECT SUM(amount) FROM stable_reserves) AS reserve_backing,
    (SELECT SUM(debt_amount) FROM collateral_vaults WHERE NOT liquidated) AS cdp_debt,
    (SELECT COUNT(*) FROM collateral_vaults WHERE NOT liquidated) AS active_vaults,
    (SELECT COUNT(*) FROM collateral_vaults WHERE collateral_ratio < 1.2 AND NOT liquidated) AS at_risk_vaults;

CREATE VIEW IF NOT EXISTS vault_health AS
SELECT 
    cv.vault_id,
    cv.owner_address,
    ct.asset_name,
    cv.collateral_amount,
    cv.debt_amount,
    cv.collateral_ratio,
    ct.liquidation_ratio,
    cv.interest_accrued,
    CASE 
        WHEN cv.collateral_ratio < ct.liquidation_ratio THEN 'liquidatable'
        WHEN cv.collateral_ratio < ct.liquidation_ratio * 1.1 THEN 'danger'
        WHEN cv.collateral_ratio < ct.liquidation_ratio * 1.2 THEN 'warning'
        ELSE 'safe'
    END AS health_status,
    cv.last_updated
FROM collateral_vaults cv
JOIN collateral_types ct ON cv.collateral_type_id = ct.id
WHERE NOT cv.liquidated;

-- ============================================================================
-- INITIALIZATION DATA
-- ============================================================================

-- Insert collateral types
INSERT INTO collateral_types (asset_name, asset_type, liquidation_ratio, stability_fee, debt_ceiling) VALUES
    ('USDT', 'stablecoin', 1.05, 0.0, 10000000.0),  -- 105%, 0% fee, 10M cap
    ('USDC', 'stablecoin', 1.05, 0.0, 10000000.0),
    ('DAI', 'stablecoin', 1.05, 0.0, 10000000.0),
    ('QBC', 'native', 1.50, 0.02, 5000000.0),       -- 150%, 2% fee, 5M cap
    ('ETH', 'crypto', 1.50, 0.025, 5000000.0)
ON CONFLICT (asset_name) DO NOTHING;

-- Insert oracle sources
INSERT INTO oracle_sources (source_name, source_type, active) VALUES
    ('Chainlink-USDT', 'chainlink', true),
    ('Chainlink-USDC', 'chainlink', true),
    ('Chainlink-DAI', 'chainlink', true),
    ('Chainlink-ETH', 'chainlink', true),
    ('QBC-Oracle', 'native', true),
    ('Aggregated-USD', 'aggregated', true)
ON CONFLICT (source_name) DO NOTHING;

-- Insert system parameters
INSERT INTO stablecoin_params (param_name, param_value, param_type, description) VALUES
    ('peg_tolerance', '0.005', 'decimal', 'Max deviation from $1 (0.5%)'),
    ('min_mint_amount', '10.0', 'decimal', 'Minimum QUSD mint'),
    ('min_burn_amount', '1.0', 'decimal', 'Minimum QUSD burn'),
    ('oracle_update_blocks', '5', 'integer', 'Blocks between oracle updates'),
    ('liquidation_penalty', '0.13', 'decimal', 'Liquidation penalty (13%)'),
    ('reserve_audit_blocks', '100', 'integer', 'Blocks between audits'),
    ('emergency_shutdown', 'false', 'boolean', 'System shutdown flag'),
    ('max_vault_debt', '1000000.0', 'decimal', 'Max debt per vault'),
    ('global_debt_ceiling', '50000000.0', 'decimal', 'Total system debt limit')
ON CONFLICT (param_name) DO NOTHING;

-- Create QUSD token (will be linked to stablecoin contract)
INSERT INTO tokens (token_id, symbol, name, decimals, total_supply, token_type, active) VALUES
    ('qusd-stable-001', 'QUSD', 'Qubitcoin USD Stablecoin', 8, 0, 'stablecoin', false)
ON CONFLICT (symbol) DO NOTHING;

-- Initialize risk metrics tracking
INSERT INTO risk_metrics (metric_name, metric_value, threshold_warning, threshold_critical, status, block_height, timestamp) VALUES
    ('global_collateral_ratio', 999.0, 1.2, 1.1, 'normal', 0, CURRENT_TIMESTAMP),
    ('peg_deviation', 0.0, 0.005, 0.01, 'normal', 0, CURRENT_TIMESTAMP),
    ('total_debt_to_ceiling', 0.0, 0.8, 0.95, 'normal', 0, CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;

-- Create statistics
ANALYZE tokens;
ANALYZE token_transfers;
ANALYZE collateral_types;
ANALYZE collateral_vaults;
ANALYZE stable_reserves;
ANALYZE oracle_sources;
ANALYZE price_feeds;
ANALYZE qusd_operations;

