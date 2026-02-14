SET DATABASE = qubitcoin;

CREATE TABLE IF NOT EXISTS confidential_transactions (
    tx_hash BYTES PRIMARY KEY,
    block_hash BYTES NOT NULL,
    block_height BIGINT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT now(),
    input_commitments BYTES[] NOT NULL,
    output_commitments BYTES[] NOT NULL,
    range_proofs BYTES[] NOT NULL,
    fee DECIMAL(20, 8) NOT NULL,
    signature BYTES NOT NULL,
    is_valid BOOL NOT NULL DEFAULT true,
    INDEX block_hash_idx (block_hash),
    CONSTRAINT fk_transaction FOREIGN KEY (tx_hash) REFERENCES transactions(tx_hash) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS stealth_addresses (
    stealth_address BYTES PRIMARY KEY,
    public_spend_key BYTES NOT NULL,
    public_view_key BYTES NOT NULL,
    one_time_pubkey BYTES NOT NULL UNIQUE,
    tx_hash BYTES NOT NULL,
    output_index INT NOT NULL,
    created_at_height BIGINT NOT NULL,
    is_spent BOOL NOT NULL DEFAULT false,
    INDEX tx_hash_idx (tx_hash),
    INDEX unspent_idx (is_spent) WHERE is_spent = false
);

CREATE TABLE IF NOT EXISTS susy_swap_pools (
    pool_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_a_address BYTES NOT NULL,
    token_b_address BYTES NOT NULL,
    token_a_commitment BYTES NOT NULL,
    token_b_commitment BYTES NOT NULL,
    total_swaps BIGINT NOT NULL DEFAULT 0,
    swap_fee_basis_points INT NOT NULL DEFAULT 30,
    is_active BOOL NOT NULL DEFAULT true,
    created_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE INDEX token_pair_idx (token_a_address, token_b_address)
);

-- Key images track spent confidential outputs to prevent double-spending
CREATE TABLE IF NOT EXISTS key_images (
    key_image STRING PRIMARY KEY,          -- Hex-encoded key image (unique per spending key)
    tx_hash BYTES NOT NULL,                -- Transaction that spent this output
    block_height BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    INDEX block_height_idx (block_height),
    INDEX tx_hash_idx (tx_hash)
);

-- Range proof cache for verified proofs (avoid re-verification)
CREATE TABLE IF NOT EXISTS range_proof_cache (
    proof_hash STRING PRIMARY KEY,         -- SHA-256 of serialized proof
    commitment_hash STRING NOT NULL,       -- Hash of the Pedersen commitment
    verified BOOL NOT NULL DEFAULT true,
    verified_at TIMESTAMP NOT NULL DEFAULT now(),
    block_height BIGINT NOT NULL,
    INDEX block_height_idx (block_height)
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.1.0', 'privacy', 'Privacy: key images, range proof cache');
