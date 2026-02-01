-- ============================================================================
-- QUSD STABLECOIN SYSTEM - Production-Grade Architecture
-- ============================================================================
-- Multi-collateral, multi-oracle stablecoin with quantum proofs
-- Supports: USDT/USDC/DAI backing, over-collateralization, emergency shutdown
-- ============================================================================

-- ============================================================================
-- SMART CONTRACT INFRASTRUCTURE
-- ============================================================================

-- Smart contracts registry
CREATE TABLE IF NOT EXISTS contracts (
    id SERIAL PRIMARY KEY,
    contract_address STRING UNIQUE NOT NULL,
    contract_type STRING NOT NULL CHECK (contract_type IN ('stablecoin', 'token', 'vault', 'oracle', 'governance')),
    code_hash STRING NOT NULL,
    deployer_address STRING NOT NULL,
    state JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deployed_block INT,
    active BOOLEAN DEFAULT true,
    INDEX idx_type (contract_type),
    INDEX idx_deployer (deployer_address),
    INDEX idx_active (active) WHERE active = true
);

-- Contract events log
CREATE TABLE IF NOT EXISTS contract_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id INT REFERENCES contracts(id),
    event_type STRING NOT NULL,
    event_data JSONB NOT NULL,
    block_height INT NOT NULL,
    txid STRING NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_contract (contract_id, block_height DESC),
    INDEX idx_type (event_type),
    INDEX idx_block (block_height DESC)
);

-- ============================================================================
-- TOKEN SYSTEM
-- ============================================================================

-- Token definitions (ERC-20 like)
CREATE TABLE IF NOT EXISTS tokens (
    id SERIAL PRIMARY KEY,
    symbol STRING UNIQUE NOT NULL,
    name STRING NOT NULL,
    decimals INT DEFAULT 8,
    total_supply DECIMAL(28, 8) DEFAULT 0,
    contract_id INT REFERENCES contracts(id),
    token_type STRING NOT NULL CHECK (token_type IN ('native', 'stablecoin', 'wrapped', 'governance')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_type (token_type)
);

-- Token balances (account model for tokens, UTXO for native QBC)
CREATE TABLE IF NOT EXISTS token_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_id INT REFERENCES tokens(id),
    address STRING NOT NULL,
    balance DECIMAL(28, 8) DEFAULT 0 CHECK (balance >= 0),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (token_id, address),
    INDEX idx_address (address),
    INDEX idx_token (token_id)
);

-- Token transfer history
CREATE TABLE IF NOT EXISTS token_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_id INT REFERENCES tokens(id),
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
-- STABLECOIN COLLATERAL & RESERVES
-- ============================================================================

-- Collateral types (multi-asset backing)
CREATE TABLE IF NOT EXISTS collateral_types (
    id SERIAL PRIMARY KEY,
    asset_name STRING UNIQUE NOT NULL,
    asset_type STRING NOT NULL CHECK (asset_type IN ('crypto', 'fiat', 'commodity')),
    oracle_address STRING,
    liquidation_ratio DECIMAL(5, 4) NOT NULL CHECK (liquidation_ratio > 1.0), -- e.g., 1.5 = 150%
    stability_fee DECIMAL(8, 6) DEFAULT 0, -- Annual interest rate
    min_collateral DECIMAL(28, 8) DEFAULT 0,
    active BOOLEAN DEFAULT true,
    INDEX idx_active (active) WHERE active = true
);

-- Collateral vaults (CDP-style positions)
CREATE TABLE IF NOT EXISTS collateral_vaults (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_address STRING NOT NULL,
    collateral_type_id INT REFERENCES collateral_types(id),
    collateral_amount DECIMAL(28, 8) NOT NULL CHECK (collateral_amount >= 0),
    debt_amount DECIMAL(28, 8) NOT NULL CHECK (debt_amount >= 0), -- QUSD minted
    collateral_ratio DECIMAL(10, 4), -- Current ratio (auto-calculated)
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    liquidated BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_owner (owner_address),
    INDEX idx_ratio (collateral_ratio) WHERE NOT liquidated,
    INDEX idx_collateral_type (collateral_type_id)
);

-- Reserve pool (100% backed reserves for bridged stablecoins)
CREATE TABLE IF NOT EXISTS stable_reserves (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_name STRING NOT NULL, -- USDT, USDC, DAI, etc.
    amount DECIMAL(28, 8) NOT NULL CHECK (amount >= 0),
    proof JSONB NOT NULL, -- Quantum proof of reserves
    reserve_address STRING NOT NULL, -- Multi-sig vault address
    block_height INT NOT NULL,
    attestation_hash STRING, -- Merkle root of reserves
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_asset (asset_name),
    INDEX idx_block (block_height DESC)
);

-- Reserve audit log (immutable trail)
CREATE TABLE IF NOT EXISTS reserve_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    total_qusd_supply DECIMAL(28, 8) NOT NULL,
    total_reserves_usd DECIMAL(28, 8) NOT NULL,
    collateralization_ratio DECIMAL(10, 4) NOT NULL,
    reserve_breakdown JSONB NOT NULL, -- {USDT: x, USDC: y, DAI: z}
    proof_hash STRING NOT NULL,
    auditor_address STRING,
    block_height INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_block (block_height DESC)
);

-- ============================================================================
-- ORACLE SYSTEM (Multi-source price feeds)
-- ============================================================================

-- Oracle sources
CREATE TABLE IF NOT EXISTS oracle_sources (
    id SERIAL PRIMARY KEY,
    source_name STRING UNIQUE NOT NULL, -- Chainlink, Band, QBC-native
    source_type STRING NOT NULL CHECK (source_type IN ('chainlink', 'band', 'uniswap', 'native')),
    endpoint STRING,
    public_key STRING, -- For signature verification
    active BOOLEAN DEFAULT true,
    reliability_score INT DEFAULT 100 CHECK (reliability_score >= 0 AND reliability_score <= 100),
    INDEX idx_active (active) WHERE active = true
);

-- Price feeds (aggregated multi-oracle)
CREATE TABLE IF NOT EXISTS price_feeds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_pair STRING NOT NULL, -- USDT/USD, ETH/USD, etc.
    price DECIMAL(18, 8) NOT NULL CHECK (price > 0),
    source_id INT REFERENCES oracle_sources(id),
    confidence DECIMAL(5, 4), -- 0.95 = 95% confidence
    block_height INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    signature STRING, -- Oracle signature
    INDEX idx_pair (asset_pair, timestamp DESC),
    INDEX idx_block (block_height DESC)
);

-- Aggregated price (median/average of multiple sources)
CREATE TABLE IF NOT EXISTS aggregated_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_pair STRING NOT NULL,
    median_price DECIMAL(18, 8) NOT NULL,
    mean_price DECIMAL(18, 8) NOT NULL,
    std_deviation DECIMAL(18, 8),
    num_sources INT NOT NULL,
    block_height INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid BOOLEAN DEFAULT true, -- False if deviation too high
    INDEX idx_pair (asset_pair, timestamp DESC),
    INDEX idx_valid (valid, asset_pair)
);

-- ============================================================================
-- STABLECOIN OPERATIONS
-- ============================================================================

-- Mint/Burn events
CREATE TABLE IF NOT EXISTS qusd_operations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_type STRING NOT NULL CHECK (operation_type IN ('mint', 'burn', 'liquidation')),
    user_address STRING NOT NULL,
    amount DECIMAL(28, 8) NOT NULL,
    collateral_locked DECIMAL(28, 8), -- For mints
    collateral_type STRING,
    price_at_mint DECIMAL(18, 8), -- Oracle price
    quantum_proof JSONB NOT NULL, -- VQE proof
    txid STRING NOT NULL,
    block_height INT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status STRING NOT NULL CHECK (status IN ('pending', 'confirmed', 'failed')),
    INDEX idx_user (user_address, timestamp DESC),
    INDEX idx_type (operation_type),
    INDEX idx_status (status) WHERE status = 'pending'
);

-- Liquidation queue
CREATE TABLE IF NOT EXISTS liquidations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vault_id UUID REFERENCES collateral_vaults(id),
    owner_address STRING NOT NULL,
    collateral_seized DECIMAL(28, 8) NOT NULL,
    debt_covered DECIMAL(28, 8) NOT NULL,
    liquidator_address STRING,
    liquidation_price DECIMAL(18, 8) NOT NULL,
    penalty_fee DECIMAL(8, 6), -- Liquidation penalty %
    block_height INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_owner (owner_address),
    INDEX idx_block (block_height DESC)
);

-- ============================================================================
-- GOVERNANCE & RISK PARAMETERS
-- ============================================================================

-- System parameters (adjustable via governance)
CREATE TABLE IF NOT EXISTS system_params (
    id SERIAL PRIMARY KEY,
    param_name STRING UNIQUE NOT NULL,
    param_value STRING NOT NULL,
    param_type STRING NOT NULL CHECK (param_type IN ('decimal', 'integer', 'boolean', 'string')),
    description STRING,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by STRING, -- Governance contract address
    INDEX idx_name (param_name)
);

-- Risk monitoring
CREATE TABLE IF NOT EXISTS risk_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name STRING NOT NULL,
    metric_value DECIMAL(18, 8) NOT NULL,
    threshold_min DECIMAL(18, 8),
    threshold_max DECIMAL(18, 8),
    status STRING NOT NULL CHECK (status IN ('normal', 'warning', 'critical')),
    block_height INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status, timestamp DESC) WHERE status != 'normal'
);

-- Emergency shutdown (circuit breaker)
CREATE TABLE IF NOT EXISTS emergency_shutdowns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reason STRING NOT NULL,
    triggered_by STRING NOT NULL,
    block_height INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP
);

-- ============================================================================
-- VIEWS FOR ANALYTICS
-- ============================================================================

CREATE VIEW IF NOT EXISTS qusd_supply_view AS
SELECT 
    (SELECT total_supply FROM tokens WHERE symbol = 'QUSD') AS total_qusd,
    (SELECT SUM(amount) FROM stable_reserves) AS total_reserves_backing,
    (SELECT SUM(debt_amount) FROM collateral_vaults WHERE NOT liquidated) AS total_cdp_debt,
    (SELECT COUNT(*) FROM collateral_vaults WHERE NOT liquidated) AS active_vaults;

CREATE VIEW IF NOT EXISTS collateral_health AS
SELECT 
    cv.id,
    cv.owner_address,
    ct.asset_name,
    cv.collateral_amount,
    cv.debt_amount,
    cv.collateral_ratio,
    ct.liquidation_ratio,
    CASE 
        WHEN cv.collateral_ratio < ct.liquidation_ratio THEN 'danger'
        WHEN cv.collateral_ratio < ct.liquidation_ratio * 1.2 THEN 'warning'
        ELSE 'safe'
    END AS health_status
FROM collateral_vaults cv
JOIN collateral_types ct ON cv.collateral_type_id = ct.id
WHERE NOT cv.liquidated;

-- ============================================================================
-- INITIALIZATION
-- ============================================================================

-- Insert default collateral types
INSERT INTO collateral_types (asset_name, asset_type, liquidation_ratio, stability_fee) VALUES
    ('USDT', 'crypto', 1.10, 0.0), -- 110% collateral, 0% fee (stable)
    ('USDC', 'crypto', 1.10, 0.0),
    ('DAI', 'crypto', 1.10, 0.0),
    ('QBC', 'crypto', 1.50, 0.02), -- 150% collateral, 2% annual fee (volatile)
    ('ETH', 'crypto', 1.50, 0.025)
ON CONFLICT (asset_name) DO NOTHING;

-- Insert default oracle sources
INSERT INTO oracle_sources (source_name, source_type, active) VALUES
    ('Chainlink-Primary', 'chainlink', true),
    ('Chainlink-Secondary', 'chainlink', true),
    ('Band-Protocol', 'band', true),
    ('QBC-Native', 'native', true)
ON CONFLICT (source_name) DO NOTHING;

-- Insert system parameters
INSERT INTO system_params (param_name, param_value, param_type, description) VALUES
    ('qusd.peg_tolerance', '0.005', 'decimal', 'Max deviation from $1.00 (0.5%)'),
    ('qusd.min_mint', '10.0', 'decimal', 'Minimum QUSD mint amount'),
    ('qusd.emergency_shutdown', 'false', 'boolean', 'System shutdown flag'),
    ('oracle.update_frequency', '5', 'integer', 'Blocks between oracle updates'),
    ('liquidation.penalty', '0.13', 'decimal', 'Liquidation penalty (13%)'),
    ('reserves.audit_frequency', '100', 'integer', 'Blocks between reserve audits')
ON CONFLICT (param_name) DO NOTHING;

-- Create QUSD token
INSERT INTO tokens (symbol, name, decimals, total_supply, token_type) VALUES
    ('QUSD', 'Qubitcoin USD', 8, 0, 'stablecoin')
ON CONFLICT (symbol) DO NOTHING;

-- Create statistics for optimizer
ANALYZE contracts;
ANALYZE tokens;
ANALYZE token_balances;
ANALYZE collateral_vaults;
ANALYZE price_feeds;

