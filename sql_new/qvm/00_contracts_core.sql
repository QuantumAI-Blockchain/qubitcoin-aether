SET DATABASE = qubitcoin;

-- ================================================================
-- SMART CONTRACTS - QVM contract registry
-- ================================================================
CREATE TABLE IF NOT EXISTS smart_contracts (
    contract_address BYTES PRIMARY KEY,
    
    -- Deployment info
    creator_address BYTES NOT NULL,
    deployer_tx_hash BYTES NOT NULL,
    deployed_at_height BIGINT NOT NULL,
    deployed_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    
    -- Contract code
    bytecode BYTES NOT NULL,
    bytecode_hash BYTES NOT NULL,
    bytecode_size BIGINT NOT NULL,
    
    -- Contract metadata
    contract_name VARCHAR(255),
    contract_type VARCHAR(50) NOT NULL,  -- 'standard', 'token', 'nft', 'defi', 'dao', 'oracle'
    contract_version VARCHAR(20),
    
    -- Verification
    is_verified BOOL NOT NULL DEFAULT false,
    source_code TEXT,
    compiler_version VARCHAR(50),
    optimization_enabled BOOL DEFAULT true,
    
    -- Economics
    balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_gas_used BIGINT NOT NULL DEFAULT 0,
    execution_count BIGINT NOT NULL DEFAULT 0,
    
    -- State
    is_active BOOL NOT NULL DEFAULT true,
    is_paused BOOL NOT NULL DEFAULT false,
    is_upgradeable BOOL NOT NULL DEFAULT false,
    proxy_implementation BYTES,  -- For upgradeable contracts
    
    -- IPFS
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
-- ================================================================
CREATE TABLE IF NOT EXISTS token_contracts (
    contract_address BYTES PRIMARY KEY,
    
    -- Token standard
    token_standard VARCHAR(20) NOT NULL,  -- 'QRC20', 'QRC721', 'QRC1155'
    
    -- Token info
    token_name VARCHAR(255) NOT NULL,
    token_symbol VARCHAR(50) NOT NULL,
    decimals INT NOT NULL DEFAULT 18,
    
    -- Supply
    total_supply DECIMAL(30, 8) NOT NULL,
    max_supply DECIMAL(30, 8),
    circulating_supply DECIMAL(30, 8),
    
    -- Holders
    total_holders BIGINT NOT NULL DEFAULT 0,
    total_transfers BIGINT NOT NULL DEFAULT 0,
    
    -- Features
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
VALUES ('1.0.0', 'qvm_contracts', 'Smart contract registry and token standards')
ON CONFLICT DO NOTHING;
