SET DATABASE = qubitcoin;

-- ================================================================
-- CORE BLOCKCHAIN TABLES
-- Implements: UTXO model, PoSA consensus, φ-based economics
-- ================================================================

-- Blocks table (UPDATED with era tracking)
CREATE TABLE IF NOT EXISTS blocks (
    block_hash BYTES PRIMARY KEY,
    block_height BIGINT NOT NULL UNIQUE,
    version INT NOT NULL DEFAULT 1,
    previous_hash BYTES NOT NULL,
    merkle_root BYTES NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT now(),
    
    -- VQE/PoSA specific
    vqe_circuit_hash BYTES NOT NULL,
    hamiltonian_id UUID NOT NULL,
    target_eigenvalue DECIMAL(20, 10) NOT NULL,
    achieved_eigenvalue DECIMAL(20, 10) NOT NULL,
    alignment_score DECIMAL(10, 6) NOT NULL,
    difficulty DECIMAL(20, 10) NOT NULL,
    nonce BIGINT NOT NULL,
    
    -- Miner & rewards
    miner_address BYTES NOT NULL,
    era INT NOT NULL DEFAULT 0,                    -- NEW: φ-halving era
    base_reward DECIMAL(20, 8) NOT NULL,           -- NEW: Base block reward for era
    actual_reward DECIMAL(20, 8) NOT NULL,         -- NEW: Total reward (base + fees)
    total_fees DECIMAL(20, 8) NOT NULL DEFAULT 0,
    
    -- Stats
    transaction_count INT NOT NULL DEFAULT 0,
    block_size BIGINT NOT NULL,
    is_valid BOOL NOT NULL DEFAULT true,
    
    INDEX block_height_idx (block_height DESC),
    INDEX timestamp_idx (timestamp DESC),
    INDEX miner_idx (miner_address),
    INDEX era_idx (era)
);

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    tx_hash BYTES PRIMARY KEY,
    block_hash BYTES NOT NULL,
    block_height BIGINT NOT NULL,
    tx_index INT NOT NULL,
    version INT NOT NULL DEFAULT 1,
    timestamp TIMESTAMP NOT NULL DEFAULT now(),
    tx_type VARCHAR(20) NOT NULL,              -- standard, coinbase, contract
    input_count INT NOT NULL DEFAULT 0,
    output_count INT NOT NULL DEFAULT 0,
    total_input DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_output DECIMAL(20, 8) NOT NULL DEFAULT 0,
    fee DECIMAL(20, 8) NOT NULL DEFAULT 0,
    signature_pubkey BYTES NOT NULL,
    signature_data BYTES NOT NULL,
    is_confidential BOOL NOT NULL DEFAULT false,
    tx_size BIGINT NOT NULL,
    is_valid BOOL NOT NULL DEFAULT true,
    
    INDEX block_hash_idx (block_hash),
    INDEX tx_type_idx (tx_type),
    INDEX timestamp_idx (timestamp DESC),
    CONSTRAINT fk_block FOREIGN KEY (block_hash) REFERENCES blocks(block_hash) ON DELETE CASCADE
);

-- NEW: Transaction Inputs (UTXO model)
CREATE TABLE IF NOT EXISTS transaction_inputs (
    input_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_hash BYTES NOT NULL,
    input_index INT NOT NULL,
    previous_tx_hash BYTES NOT NULL,
    previous_output_index INT NOT NULL,
    script_sig BYTES NOT NULL,
    sequence BIGINT NOT NULL DEFAULT 4294967295,
    
    UNIQUE INDEX tx_input_idx (tx_hash, input_index),
    INDEX prev_output_idx (previous_tx_hash, previous_output_index),
    CONSTRAINT fk_transaction FOREIGN KEY (tx_hash) REFERENCES transactions(tx_hash) ON DELETE CASCADE
);

-- NEW: Transaction Outputs (UTXO model)
CREATE TABLE IF NOT EXISTS transaction_outputs (
    output_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_hash BYTES NOT NULL,
    output_index INT NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    recipient_address BYTES NOT NULL,
    script_pubkey BYTES NOT NULL,
    is_spent BOOL NOT NULL DEFAULT false,
    spent_in_tx BYTES,
    spent_at_height BIGINT,
    
    UNIQUE INDEX tx_output_idx (tx_hash, output_index),
    INDEX recipient_idx (recipient_address),
    INDEX unspent_idx (is_spent) WHERE is_spent = false,
    CONSTRAINT fk_transaction FOREIGN KEY (tx_hash) REFERENCES transactions(tx_hash) ON DELETE CASCADE
);

-- NEW: Address Balances
CREATE TABLE IF NOT EXISTS addresses (
    address BYTES PRIMARY KEY,
    balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_received DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_sent DECIMAL(20, 8) NOT NULL DEFAULT 0,
    tx_count BIGINT NOT NULL DEFAULT 0,
    utxo_count BIGINT NOT NULL DEFAULT 0,
    first_seen_height BIGINT,
    last_active_height BIGINT,
    last_active_timestamp TIMESTAMP,
    
    INDEX balance_idx (balance DESC),
    INDEX last_active_idx (last_active_height DESC)
);

-- NEW: Chain State (Singleton table)
CREATE TABLE IF NOT EXISTS chain_state (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    best_block_hash BYTES NOT NULL,
    best_block_height BIGINT NOT NULL DEFAULT 0,
    total_blocks BIGINT NOT NULL DEFAULT 0,
    total_transactions BIGINT NOT NULL DEFAULT 0,
    total_supply DECIMAL(30, 8) NOT NULL DEFAULT 0,
    circulating_supply DECIMAL(30, 8) NOT NULL DEFAULT 0,
    current_era INT NOT NULL DEFAULT 0,
    current_difficulty DECIMAL(20, 10) NOT NULL DEFAULT 1.0,
    network_hashrate DECIMAL(20, 10) NOT NULL DEFAULT 0,
    average_block_time DECIMAL(10, 2) NOT NULL DEFAULT 3.3,
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

-- Initialize chain state with genesis values
INSERT INTO chain_state (
    id, 
    best_block_hash, 
    best_block_height,
    current_difficulty
) VALUES (
    1, 
    E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    0,
    1.0
) ON CONFLICT (id) DO NOTHING;

-- NEW: Mempool (Unconfirmed transactions)
CREATE TABLE IF NOT EXISTS mempool (
    tx_hash BYTES PRIMARY KEY,
    raw_tx BYTES NOT NULL,
    tx_size BIGINT NOT NULL,
    fee DECIMAL(20, 8) NOT NULL,
    fee_per_byte DECIMAL(20, 8) NOT NULL,
    priority_score DECIMAL(10, 2) NOT NULL,
    received_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    first_seen_peer VARCHAR(255),
    propagation_count INT NOT NULL DEFAULT 0,
    
    INDEX fee_idx (fee DESC),
    INDEX priority_idx (priority_score DESC),
    INDEX timestamp_idx (received_timestamp)
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'core_blockchain', 'Core blockchain with UTXO model')
ON CONFLICT DO NOTHING;
