-- =============================================================================
-- QUBITCOIN L1 PRODUCTION SCHEMA
-- Smart Contracts + Multi-Chain Bridge
-- =============================================================================
-- 
-- This migration adds ONLY what the L1 chain needs:
-- 1. Smart contract execution infrastructure
-- 2. Multi-chain bridge for wQBC/wQUSD wrappers
-- 
-- QUSD stablecoin logic lives in a smart contract, NOT in these tables.
-- =============================================================================

BEGIN;

-- =============================================================================
-- SMART CONTRACT INFRASTRUCTURE
-- =============================================================================

-- Contract storage (key-value storage for each contract)
CREATE TABLE IF NOT EXISTS contract_storage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_address VARCHAR(66) NOT NULL,
    storage_key VARCHAR(66) NOT NULL,
    storage_value TEXT,
    block_height BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(contract_address, storage_key)
);

CREATE INDEX IF NOT EXISTS idx_contract_storage_address ON contract_storage(contract_address);
CREATE INDEX IF NOT EXISTS idx_contract_storage_height ON contract_storage(block_height);

-- Contract events (logs emitted by contracts)
CREATE TABLE IF NOT EXISTS contract_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_address VARCHAR(66) NOT NULL,
    event_name VARCHAR(100) NOT NULL,
    event_data JSONB,
    topics TEXT[],
    block_height BIGINT NOT NULL,
    tx_hash VARCHAR(64),
    log_index INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contract_events_address ON contract_events(contract_address);
CREATE INDEX IF NOT EXISTS idx_contract_events_name ON contract_events(event_name);
CREATE INDEX IF NOT EXISTS idx_contract_events_height ON contract_events(block_height);
CREATE INDEX IF NOT EXISTS idx_contract_events_tx ON contract_events(tx_hash);

-- Contract deployments tracking
CREATE TABLE IF NOT EXISTS contract_deployments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_address VARCHAR(66) UNIQUE NOT NULL,
    deployer_address VARCHAR(66) NOT NULL,
    contract_name VARCHAR(100),
    contract_type VARCHAR(50), -- 'QUSD', 'DEX', 'NFT', etc.
    bytecode TEXT,
    abi JSONB,
    source_code TEXT,
    compiler_version VARCHAR(50),
    deployed_at_height BIGINT NOT NULL,
    deployed_at_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    gas_used BIGINT,
    status VARCHAR(20) DEFAULT 'active',
    metadata JSONB -- For contract-specific metadata
);

CREATE INDEX IF NOT EXISTS idx_contract_deployments_deployer ON contract_deployments(deployer_address);
CREATE INDEX IF NOT EXISTS idx_contract_deployments_height ON contract_deployments(deployed_at_height);
CREATE INDEX IF NOT EXISTS idx_contract_deployments_type ON contract_deployments(contract_type);
CREATE INDEX IF NOT EXISTS idx_contract_deployments_status ON contract_deployments(status);

-- =============================================================================
-- RESERVE TRACKING (For QUSD Transparency Reports)
-- =============================================================================
-- This table tracks what the QUSD contract reports, NOT what it does internally
-- Used for dashboard/transparency only

CREATE TABLE IF NOT EXISTS reserve_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_address VARCHAR(66) NOT NULL, -- QUSD contract address
    snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    block_height BIGINT NOT NULL,
    
    -- Reserve composition (what QUSD contract reports)
    usdc_balance DECIMAL(30, 8) DEFAULT 0,
    usdt_balance DECIMAL(30, 8) DEFAULT 0,
    dai_balance DECIMAL(30, 8) DEFAULT 0,
    total_reserves_usd DECIMAL(30, 8) DEFAULT 0,
    
    -- Supply metrics
    qusd_total_supply DECIMAL(30, 8) DEFAULT 0,
    backing_percentage DECIMAL(10, 6) DEFAULT 0,
    
    -- Metadata
    data_source VARCHAR(50) DEFAULT 'contract_event', -- 'contract_event' or 'oracle'
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_reserve_snapshots_contract ON reserve_snapshots(contract_address);
CREATE INDEX IF NOT EXISTS idx_reserve_snapshots_time ON reserve_snapshots(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_reserve_snapshots_height ON reserve_snapshots(block_height);

-- =============================================================================
-- DROP OLD STABLECOIN TABLES (CDP model we're not using)
-- =============================================================================

-- These were for a CDP model. QUSD is fractional reserve handled in contract.
DROP TABLE IF EXISTS stablecoin_tokens CASCADE;
DROP TABLE IF EXISTS stablecoin_positions CASCADE;
DROP TABLE IF EXISTS stablecoin_liquidations CASCADE;

-- Keep stablecoin_params for general config (min backing ratio, etc.)
-- Keep collateral_types for future expansion
-- Keep oracle_sources for price feeds

-- =============================================================================
-- VERIFICATION
-- =============================================================================

-- Count tables
SELECT COUNT(*) as total_tables 
FROM information_schema.tables 
WHERE table_schema = 'public';

-- Show all tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

COMMIT;

-- =============================================================================
-- SCHEMA SUMMARY
-- =============================================================================
-- 
-- CORE BLOCKCHAIN (existing):
--   blocks, utxos, transactions, supply, solved_hamiltonians
-- 
-- SMART CONTRACTS (added):
--   contracts, contract_storage, contract_events, contract_deployments
-- 
-- BRIDGE (existing from multi_chain_bridge.sql):
--   bridge_deposits, bridge_withdrawals, bridge_validators, bridge_approvals,
--   bridge_events, bridge_config, bridge_stats, bridge_sync_status
-- 
-- TRANSPARENCY (added):
--   reserve_snapshots (for QUSD reporting)
-- 
-- MISC (existing):
--   users, susy_swaps, peer_reputation, ipfs_snapshots, oracle_sources,
--   collateral_types, stablecoin_params
-- 
-- TOTAL: ~52-54 tables
-- =============================================================================
