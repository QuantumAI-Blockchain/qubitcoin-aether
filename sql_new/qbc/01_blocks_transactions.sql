SET DATABASE = qubitcoin;

-- ================================================================
-- BLOCKS TABLE - Core blockchain
-- Aligned with SQLAlchemy BlockModel (database/manager.py)
-- The ORM uses height as primary key with simplified columns.
-- Additional production columns can be added via ALTER TABLE
-- as the codebase evolves.
-- ================================================================
CREATE TABLE IF NOT EXISTS blocks (
    height BIGINT PRIMARY KEY,
    prev_hash VARCHAR(64),
    difficulty FLOAT8,
    proof_json JSONB,
    created_at FLOAT8,
    block_hash VARCHAR(64),
    state_root VARCHAR(64) DEFAULT '',
    receipts_root VARCHAR(64) DEFAULT '',
    thought_proof JSONB,
    cumulative_weight FLOAT8 DEFAULT 0,

    INDEX block_hash_idx (block_hash),
    INDEX height_desc_idx (height DESC)
);

-- ================================================================
-- TRANSACTIONS TABLE - All transaction types
-- Aligned with SQLAlchemy TransactionModel (database/manager.py)
-- The ORM stores inputs/outputs as JSON for simplicity.
-- The normalized transaction_inputs/transaction_outputs tables
-- (in 02_utxo_model.sql) provide referential integrity on top.
-- ================================================================
CREATE TABLE IF NOT EXISTS transactions (
    txid VARCHAR(64) PRIMARY KEY,
    inputs JSONB,
    outputs JSONB,
    fee DECIMAL,
    signature VARCHAR,
    public_key VARCHAR,
    timestamp FLOAT8,
    block_height BIGINT,
    status VARCHAR DEFAULT 'pending',
    tx_type VARCHAR(20) DEFAULT 'transfer',
    to_address VARCHAR,
    data TEXT,
    gas_limit BIGINT DEFAULT 0,
    gas_price DECIMAL DEFAULT 0,
    nonce BIGINT DEFAULT 0,

    INDEX block_height_idx (block_height DESC),
    INDEX status_idx (status),
    INDEX tx_type_idx (tx_type),
    INDEX to_address_idx (to_address) WHERE to_address IS NOT NULL
);

INSERT INTO schema_version (version, component, description)
VALUES ('2.0.0', 'qbc_blocks', 'Blocks and transactions — aligned with SQLAlchemy ORM')
ON CONFLICT DO NOTHING;
