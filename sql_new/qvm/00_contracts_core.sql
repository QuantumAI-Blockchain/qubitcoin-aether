SET DATABASE = qubitcoin;

-- ================================================================
-- CONTRACTS TABLE - Simplified contract registry
-- Aligned with SQLAlchemy ContractModel (database/manager.py)
-- Used by the Python node for basic contract tracking.
-- ================================================================
CREATE TABLE IF NOT EXISTS contracts (
    contract_id VARCHAR(66) PRIMARY KEY DEFAULT gen_random_uuid()::STRING,
    deployer_address VARCHAR NOT NULL,
    contract_type VARCHAR(50) NOT NULL,
    contract_code JSONB NOT NULL,
    contract_state JSONB DEFAULT '{}',
    gas_paid DECIMAL(18, 8) DEFAULT 0,
    block_height BIGINT,
    deployed_at TIMESTAMP DEFAULT now(),
    is_active BOOL DEFAULT true,
    last_executed TIMESTAMP,
    execution_count INT DEFAULT 0,

    INDEX deployer_idx (deployer_address),
    INDEX type_idx (contract_type),
    INDEX active_idx (is_active) WHERE is_active = true
);

-- ================================================================
-- SMART CONTRACTS - Production-grade contract registry
-- Aligned with SQLAlchemy SmartContractModel (database/manager.py)
-- Full contract metadata with verification, IPFS, proxy support.
-- ================================================================
CREATE TABLE IF NOT EXISTS smart_contracts (
    contract_address BYTES PRIMARY KEY,
    creator_address BYTES NOT NULL,
    deployer_tx_hash BYTES NOT NULL,
    deployed_at_height BIGINT NOT NULL,
    deployed_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    bytecode BYTES NOT NULL,
    bytecode_hash BYTES NOT NULL,
    bytecode_size BIGINT NOT NULL,
    contract_name VARCHAR(255),
    contract_type VARCHAR(50) NOT NULL,
    contract_version VARCHAR(20),
    is_verified BOOL NOT NULL DEFAULT false,
    source_code TEXT,
    compiler_version VARCHAR(50),
    optimization_enabled BOOL DEFAULT true,
    balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_gas_used BIGINT NOT NULL DEFAULT 0,
    execution_count BIGINT NOT NULL DEFAULT 0,
    is_active BOOL NOT NULL DEFAULT true,
    is_paused BOOL NOT NULL DEFAULT false,
    is_upgradeable BOOL NOT NULL DEFAULT false,
    proxy_implementation BYTES,
    ipfs_bytecode_hash VARCHAR(100),
    ipfs_source_hash VARCHAR(100),

    INDEX creator_idx (creator_address),
    INDEX contract_type_idx (contract_type),
    INDEX deployed_height_idx (deployed_at_height DESC),
    INDEX verified_idx (is_verified) WHERE is_verified = true,
    INDEX active_idx (is_active) WHERE is_active = true
);

-- ================================================================
-- TOKEN CONTRACTS - ERC20/QRC20 compatible
-- Aligned with SQLAlchemy TokenContractModel (database/manager.py)
-- ================================================================
CREATE TABLE IF NOT EXISTS token_contracts (
    contract_address BYTES PRIMARY KEY,
    token_standard VARCHAR(20) NOT NULL,
    token_name VARCHAR(255) NOT NULL,
    token_symbol VARCHAR(50) NOT NULL,
    decimals INT NOT NULL DEFAULT 18,
    total_supply DECIMAL(30, 8) NOT NULL,
    max_supply DECIMAL(30, 8),
    circulating_supply DECIMAL(30, 8),
    total_holders BIGINT NOT NULL DEFAULT 0,
    total_transfers BIGINT NOT NULL DEFAULT 0,
    is_mintable BOOL NOT NULL DEFAULT false,
    is_burnable BOOL NOT NULL DEFAULT false,
    is_pausable BOOL NOT NULL DEFAULT false,

    INDEX symbol_idx (token_symbol),
    INDEX standard_idx (token_standard),
    INDEX holders_idx (total_holders DESC),

    CONSTRAINT fk_contract FOREIGN KEY (contract_address)
        REFERENCES smart_contracts(contract_address) ON DELETE CASCADE
);

INSERT INTO schema_version (version, component, description)
VALUES ('2.0.0', 'qvm_contracts', 'Contract registries — aligned with SQLAlchemy ORM')
ON CONFLICT DO NOTHING;
