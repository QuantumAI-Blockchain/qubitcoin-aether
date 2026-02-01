-- Multi-Chain Bridge Database Schema
-- Supports: Ethereum, Polygon, BSC, Arbitrum, Optimism, Avalanche, Base, Solana

-- ============================================================================
-- BRIDGE DEPOSITS (QBC → wQBC on any chain)
-- ============================================================================
CREATE TABLE IF NOT EXISTS bridge_deposits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- QBC side
    qbc_txid STRING NOT NULL,
    qbc_address STRING NOT NULL,
    qbc_amount DECIMAL(18, 8) NOT NULL,
    qbc_confirmations INT DEFAULT 0,
    
    -- Target chain side
    target_chain STRING NOT NULL CHECK (target_chain IN (
        'ethereum', 'polygon', 'bsc', 'arbitrum', 'optimism', 'avalanche', 'base', 'solana'
    )),
    target_address STRING NOT NULL,
    target_txhash STRING,
    target_confirmations INT DEFAULT 0,
    
    -- Status and tracking
    status STRING NOT NULL DEFAULT 'detected' CHECK (status IN (
        'detected', 'confirming', 'pending', 'validating', 'processing', 'completed', 'failed', 'refunded'
    )),
    validator_approvals INT DEFAULT 0,
    required_approvals INT DEFAULT 3,
    
    -- Fees
    bridge_fee DECIMAL(18, 8) DEFAULT 0,
    gas_fee DECIMAL(18, 8) DEFAULT 0,
    
    -- Metadata
    chain_data JSONB,
    error_message STRING,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Indexes
    INDEX idx_deposits_status (status) WHERE status IN ('detected', 'pending', 'processing'),
    INDEX idx_deposits_chain (target_chain, status),
    INDEX idx_deposits_qbc_tx (qbc_txid),
    INDEX idx_deposits_target_tx (target_txhash)
);

-- ============================================================================
-- BRIDGE WITHDRAWALS (wQBC → QBC from any chain)
-- ============================================================================
CREATE TABLE IF NOT EXISTS bridge_withdrawals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source chain side
    source_chain STRING NOT NULL CHECK (source_chain IN (
        'ethereum', 'polygon', 'bsc', 'arbitrum', 'optimism', 'avalanche', 'base', 'solana'
    )),
    source_txhash STRING NOT NULL,
    source_address STRING NOT NULL,
    wqbc_amount DECIMAL(18, 8) NOT NULL,
    source_confirmations INT DEFAULT 0,
    
    -- QBC side
    qbc_address STRING NOT NULL,
    qbc_txid STRING,
    qbc_confirmations INT DEFAULT 0,
    
    -- Status and tracking
    status STRING NOT NULL DEFAULT 'detected' CHECK (status IN (
        'detected', 'confirming', 'pending', 'validating', 'processing', 'completed', 'failed', 'refunded'
    )),
    validator_approvals INT DEFAULT 0,
    required_approvals INT DEFAULT 3,
    
    -- Fees
    bridge_fee DECIMAL(18, 8) DEFAULT 0,
    
    -- Metadata
    chain_data JSONB,
    error_message STRING,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Indexes
    INDEX idx_withdrawals_status (status) WHERE status IN ('detected', 'pending', 'processing'),
    INDEX idx_withdrawals_chain (source_chain, status),
    INDEX idx_withdrawals_source_tx (source_txhash),
    INDEX idx_withdrawals_qbc_tx (qbc_txid)
);

-- ============================================================================
-- BRIDGE VALIDATORS (Multi-sig validators)
-- ============================================================================
CREATE TABLE IF NOT EXISTS bridge_validators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Validator identity
    qbc_address STRING NOT NULL UNIQUE,
    qbc_public_key STRING NOT NULL,
    
    -- Multi-chain addresses
    eth_address STRING,
    sol_address STRING,
    
    -- Status
    active BOOLEAN DEFAULT true,
    weight INT DEFAULT 1 CHECK (weight > 0),
    
    -- Performance tracking
    deposits_approved INT DEFAULT 0,
    withdrawals_approved INT DEFAULT 0,
    false_approvals INT DEFAULT 0,
    uptime_percentage DECIMAL(5, 2) DEFAULT 100.00,
    
    -- Timestamps
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_validators_active (active) WHERE active = true,
    INDEX idx_validators_eth (eth_address),
    INDEX idx_validators_sol (sol_address)
);

-- ============================================================================
-- BRIDGE APPROVALS (Validator signatures)
-- ============================================================================
CREATE TABLE IF NOT EXISTS bridge_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- What's being approved
    operation_type STRING NOT NULL CHECK (operation_type IN ('deposit', 'withdrawal')),
    operation_id UUID NOT NULL,
    
    -- Who approved
    validator_id UUID NOT NULL REFERENCES bridge_validators(id),
    validator_address STRING NOT NULL,
    signature STRING NOT NULL,
    
    -- Chain-specific data
    chain STRING NOT NULL,
    approval_data JSONB,
    
    -- Timestamp
    approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE (operation_type, operation_id, validator_id),
    INDEX idx_approvals_operation (operation_type, operation_id),
    INDEX idx_approvals_validator (validator_id)
);

-- ============================================================================
-- BRIDGE EVENTS (Audit log)
-- ============================================================================
CREATE TABLE IF NOT EXISTS bridge_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Event type
    event_type STRING NOT NULL CHECK (event_type IN (
        'deposit_detected', 'deposit_approved', 'deposit_processed', 'deposit_completed', 'deposit_failed',
        'withdrawal_detected', 'withdrawal_approved', 'withdrawal_processed', 'withdrawal_completed', 'withdrawal_failed',
        'validator_added', 'validator_removed', 'config_updated', 'emergency_pause', 'emergency_resume'
    )),
    
    -- Related entities
    deposit_id UUID REFERENCES bridge_deposits(id),
    withdrawal_id UUID REFERENCES bridge_withdrawals(id),
    validator_id UUID REFERENCES bridge_validators(id),
    
    -- Event data
    chain STRING NOT NULL,
    txhash STRING,
    data JSONB,
    
    -- Timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_events_type (event_type),
    INDEX idx_events_chain (chain, created_at DESC),
    INDEX idx_events_deposit (deposit_id),
    INDEX idx_events_withdrawal (withdrawal_id)
);

-- ============================================================================
-- BRIDGE CONFIG (Per-chain configuration)
-- ============================================================================
CREATE TABLE IF NOT EXISTS bridge_config (
    chain STRING PRIMARY KEY CHECK (chain IN (
        'ethereum', 'polygon', 'bsc', 'arbitrum', 'optimism', 'avalanche', 'base', 'solana'
    )),
    
    -- Contract/Program addresses
    wqbc_token_address STRING,
    bridge_contract_address STRING,
    
    -- Confirmation requirements
    required_confirmations INT DEFAULT 12,
    
    -- Multi-sig settings
    validator_threshold INT DEFAULT 3,
    total_validators INT DEFAULT 5,
    
    -- Fee settings (basis points)
    deposit_fee_bps INT DEFAULT 30,  -- 0.30%
    withdrawal_fee_bps INT DEFAULT 30,
    
    -- Limits
    min_deposit DECIMAL(18, 8) DEFAULT 1.0,
    max_deposit DECIMAL(18, 8) DEFAULT 1000000.0,
    daily_deposit_limit DECIMAL(18, 8) DEFAULT 10000000.0,
    
    min_withdrawal DECIMAL(18, 8) DEFAULT 1.0,
    max_withdrawal DECIMAL(18, 8) DEFAULT 1000000.0,
    daily_withdrawal_limit DECIMAL(18, 8) DEFAULT 10000000.0,
    
    -- Status
    enabled BOOLEAN DEFAULT true,
    paused BOOLEAN DEFAULT false,
    
    -- Metadata
    chain_id INT,
    rpc_url STRING,
    explorer_url STRING,
    config_data JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- BRIDGE STATS (Daily aggregates)
-- ============================================================================
CREATE TABLE IF NOT EXISTS bridge_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain STRING NOT NULL,
    date DATE NOT NULL,
    
    -- Deposit stats
    deposits_count INT DEFAULT 0,
    deposits_volume DECIMAL(18, 8) DEFAULT 0,
    deposits_fees DECIMAL(18, 8) DEFAULT 0,
    
    -- Withdrawal stats
    withdrawals_count INT DEFAULT 0,
    withdrawals_volume DECIMAL(18, 8) DEFAULT 0,
    withdrawals_fees DECIMAL(18, 8) DEFAULT 0,
    
    -- Net flow
    net_flow DECIMAL(18, 8) DEFAULT 0,
    tvl DECIMAL(18, 8) DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE (chain, date),
    INDEX idx_stats_chain_date (chain, date DESC)
);

-- ============================================================================
-- CHAIN SYNC STATUS (Track last processed blocks)
-- ============================================================================
CREATE TABLE IF NOT EXISTS bridge_sync_status (
    chain STRING PRIMARY KEY,
    last_processed_block BIGINT DEFAULT 0,
    last_processed_txhash STRING,
    sync_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sync_timestamp (sync_timestamp DESC)
);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Pending deposits by chain
CREATE VIEW IF NOT EXISTS pending_deposits AS
SELECT 
    target_chain,
    COUNT(*) as count,
    SUM(qbc_amount) as total_amount,
    AVG(qbc_confirmations) as avg_confirmations
FROM bridge_deposits
WHERE status IN ('detected', 'confirming', 'pending', 'processing')
GROUP BY target_chain;

-- Pending withdrawals by chain
CREATE VIEW IF NOT EXISTS pending_withdrawals AS
SELECT 
    source_chain,
    COUNT(*) as count,
    SUM(wqbc_amount) as total_amount,
    AVG(source_confirmations) as avg_confirmations
FROM bridge_withdrawals
WHERE status IN ('detected', 'confirming', 'pending', 'processing')
GROUP BY source_chain;

-- Active validators
CREATE VIEW IF NOT EXISTS active_validators AS
SELECT 
    qbc_address,
    eth_address,
    sol_address,
    weight,
    deposits_approved + withdrawals_approved as total_approvals,
    uptime_percentage,
    last_active
FROM bridge_validators
WHERE active = true
ORDER BY weight DESC, total_approvals DESC;

-- Bridge TVL by chain
CREATE VIEW IF NOT EXISTS bridge_tvl AS
SELECT 
    target_chain as chain,
    SUM(qbc_amount) FILTER (WHERE status = 'completed') as locked_qbc,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_deposits,
    COUNT(*) FILTER (WHERE status IN ('detected', 'pending', 'processing')) as pending_deposits
FROM bridge_deposits
GROUP BY target_chain
UNION ALL
SELECT 
    source_chain as chain,
    -SUM(wqbc_amount) FILTER (WHERE status = 'completed') as locked_qbc,
    -COUNT(*) FILTER (WHERE status = 'completed') as completed_withdrawals,
    COUNT(*) FILTER (WHERE status IN ('detected', 'pending', 'processing')) as pending_withdrawals
FROM bridge_withdrawals
GROUP BY source_chain;

-- ============================================================================
-- INITIAL CONFIGURATION
-- ============================================================================

-- Insert default config for Ethereum
INSERT INTO bridge_config (
    chain, required_confirmations, validator_threshold, total_validators,
    deposit_fee_bps, withdrawal_fee_bps, min_deposit, max_deposit,
    daily_deposit_limit, min_withdrawal, max_withdrawal, daily_withdrawal_limit,
    chain_id, explorer_url
) VALUES (
    'ethereum', 12, 3, 5,
    30, 30, 1.0, 1000000.0,
    10000000.0, 1.0, 1000000.0, 10000000.0,
    1, 'https://etherscan.io'
) ON CONFLICT (chain) DO NOTHING;

-- Insert default config for Solana
INSERT INTO bridge_config (
    chain, required_confirmations, validator_threshold, total_validators,
    deposit_fee_bps, withdrawal_fee_bps, min_deposit, max_deposit,
    daily_deposit_limit, min_withdrawal, max_withdrawal, daily_withdrawal_limit,
    explorer_url
) VALUES (
    'solana', 32, 3, 5,
    30, 30, 1.0, 1000000.0,
    10000000.0, 1.0, 1000000.0, 10000000.0,
    'https://solscan.io'
) ON CONFLICT (chain) DO NOTHING;

-- ============================================================================
-- STATISTICS
-- ============================================================================

ANALYZE bridge_deposits;
ANALYZE bridge_withdrawals;
ANALYZE bridge_validators;
ANALYZE bridge_events;
