SET DATABASE = qubitcoin;

-- ================================================================
-- BLOCKS TABLE - Core blockchain with VQE/PoSA consensus
-- ================================================================
CREATE TABLE IF NOT EXISTS blocks (
    block_hash BYTES PRIMARY KEY,
    block_height BIGINT NOT NULL UNIQUE,
    version INT NOT NULL DEFAULT 1,
    previous_hash BYTES NOT NULL,
    merkle_root BYTES NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT now(),
    
    -- VQE/PoSA Quantum Mining
    vqe_circuit_hash BYTES NOT NULL,
    hamiltonian_id UUID NOT NULL,
    target_eigenvalue DECIMAL(20, 10) NOT NULL,
    achieved_eigenvalue DECIMAL(20, 10) NOT NULL,
    alignment_score DECIMAL(10, 6) NOT NULL,  -- SUSY alignment (0-100)
    difficulty DECIMAL(20, 10) NOT NULL,
    nonce BIGINT NOT NULL,
    
    -- Miner & Economics (φ-based halving)
    miner_address BYTES NOT NULL,
    era INT NOT NULL DEFAULT 0,  -- Halving era (every φ years = 15.47M blocks)
    base_reward DECIMAL(20, 8) NOT NULL,
    actual_reward DECIMAL(20, 8) NOT NULL,
    total_fees DECIMAL(20, 8) NOT NULL DEFAULT 0,
    
    -- Block Stats
    transaction_count INT NOT NULL DEFAULT 0,
    block_size BIGINT NOT NULL,
    gas_used BIGINT NOT NULL DEFAULT 0,
    gas_limit BIGINT NOT NULL DEFAULT 30000000,
    is_valid BOOL NOT NULL DEFAULT true,
    
    INDEX block_height_idx (block_height DESC),
    INDEX timestamp_idx (timestamp DESC),
    INDEX miner_idx (miner_address),
    INDEX era_idx (era),
    INDEX difficulty_idx (difficulty)
);

-- ================================================================
-- TRANSACTIONS TABLE - All transaction types
-- ================================================================
CREATE TABLE IF NOT EXISTS transactions (
    tx_hash BYTES PRIMARY KEY,
    block_hash BYTES NOT NULL,
    block_height BIGINT NOT NULL,
    tx_index INT NOT NULL,
    version INT NOT NULL DEFAULT 1,
    timestamp TIMESTAMP NOT NULL DEFAULT now(),
    
    -- Transaction Type
    tx_type VARCHAR(20) NOT NULL,  -- 'transfer', 'coinbase', 'contract_deploy', 'contract_call'
    
    -- UTXO Model
    input_count INT NOT NULL DEFAULT 0,
    output_count INT NOT NULL DEFAULT 0,
    total_input DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_output DECIMAL(20, 8) NOT NULL DEFAULT 0,
    fee DECIMAL(20, 8) NOT NULL DEFAULT 0,
    
    -- Quantum-Safe Signatures (Dilithium2)
    signature_pubkey BYTES NOT NULL,
    signature_data BYTES NOT NULL,
    
    -- Privacy & Smart Contracts
    is_confidential BOOL NOT NULL DEFAULT false,
    contract_address BYTES,  -- NULL for non-contract txs
    contract_data BYTES,     -- Contract deployment bytecode or call data
    
    -- Gas (for contract execution)
    gas_limit BIGINT,
    gas_used BIGINT,
    gas_price DECIMAL(20, 8),
    
    -- Metadata
    tx_size BIGINT NOT NULL,
    is_valid BOOL NOT NULL DEFAULT true,
    
    INDEX block_hash_idx (block_hash),
    INDEX block_height_idx (block_height DESC),
    INDEX tx_type_idx (tx_type),
    INDEX timestamp_idx (timestamp DESC),
    INDEX contract_idx (contract_address) WHERE contract_address IS NOT NULL,
    
    CONSTRAINT fk_block FOREIGN KEY (block_hash) 
        REFERENCES blocks(block_hash) ON DELETE CASCADE
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'qbc_blocks', 'Blocks and transactions with VQE consensus')
ON CONFLICT DO NOTHING;
