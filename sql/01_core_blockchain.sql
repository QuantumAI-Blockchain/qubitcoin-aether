SET DATABASE = qubitcoin;

CREATE TABLE IF NOT EXISTS blocks (
    block_hash BYTES PRIMARY KEY,
    block_height BIGINT NOT NULL UNIQUE,
    version INT NOT NULL DEFAULT 1,
    previous_hash BYTES NOT NULL,
    merkle_root BYTES NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT now(),
    vqe_circuit_hash BYTES NOT NULL,
    hamiltonian_id UUID NOT NULL,
    target_eigenvalue DECIMAL(20, 10) NOT NULL,
    achieved_eigenvalue DECIMAL(20, 10) NOT NULL,
    alignment_score DECIMAL(10, 6) NOT NULL,
    difficulty DECIMAL(20, 10) NOT NULL,
    nonce BIGINT NOT NULL,
    miner_address BYTES NOT NULL,
    block_reward DECIMAL(20, 8) NOT NULL,
    total_fees DECIMAL(20, 8) NOT NULL DEFAULT 0,
    transaction_count INT NOT NULL DEFAULT 0,
    block_size BIGINT NOT NULL,
    is_valid BOOL NOT NULL DEFAULT true,
    INDEX block_height_idx (block_height DESC),
    INDEX timestamp_idx (timestamp DESC),
    INDEX miner_idx (miner_address)
);

CREATE TABLE IF NOT EXISTS transactions (
    tx_hash BYTES PRIMARY KEY,
    block_hash BYTES NOT NULL,
    block_height BIGINT NOT NULL,
    tx_index INT NOT NULL,
    version INT NOT NULL DEFAULT 1,
    timestamp TIMESTAMP NOT NULL DEFAULT now(),
    tx_type VARCHAR(20) NOT NULL,
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

CREATE TABLE IF NOT EXISTS addresses (
    address BYTES PRIMARY KEY,
    address_type VARCHAR(20) NOT NULL,
    public_key BYTES NOT NULL,
    balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    locked_balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    tx_count BIGINT NOT NULL DEFAULT 0,
    first_seen_block BIGINT,
    last_activity_timestamp TIMESTAMP,
    INDEX balance_idx (balance DESC)
);

CREATE TABLE IF NOT EXISTS chain_state (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    best_block_hash BYTES NOT NULL,
    best_block_height BIGINT NOT NULL,
    best_block_timestamp TIMESTAMP NOT NULL,
    total_blocks BIGINT NOT NULL DEFAULT 0,
    total_transactions BIGINT NOT NULL DEFAULT 0,
    total_supply DECIMAL(20, 8) NOT NULL DEFAULT 0,
    current_difficulty DECIMAL(20, 10) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

INSERT INTO chain_state (id, best_block_hash, best_block_height, best_block_timestamp, current_difficulty)
VALUES (1, E'\\x00', 0, now(), 1.0) ON CONFLICT (id) DO NOTHING;

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'core_blockchain', 'Core blockchain tables');
