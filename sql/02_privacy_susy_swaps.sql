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

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'privacy', 'Privacy and Susy Swaps');
