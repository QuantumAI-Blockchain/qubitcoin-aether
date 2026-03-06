SET DATABASE = qubitcoin;

-- ================================================================
-- UTXOS TABLE - Simplified UTXO tracking
-- Aligned with SQLAlchemy UTXOModel (database/manager.py)
-- This is the primary UTXO table used by the Python node.
-- ================================================================
CREATE TABLE IF NOT EXISTS utxos (
    txid VARCHAR(64) NOT NULL,
    vout BIGINT NOT NULL,
    amount DECIMAL,
    address VARCHAR,
    proof JSONB,
    block_height BIGINT,
    spent BOOL DEFAULT false,
    spent_by VARCHAR,

    PRIMARY KEY (txid, vout),
    INDEX address_unspent_idx (address, spent) WHERE spent = false,
    INDEX block_height_idx (block_height DESC)
);

-- ================================================================
-- TRANSACTION INPUTS - Normalized UTXO spending (production)
-- Aligned with SQLAlchemy TransactionInputModel
-- ================================================================
CREATE TABLE IF NOT EXISTS transaction_inputs (
    input_id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::STRING,
    tx_hash VARCHAR(64) NOT NULL,
    input_index INT NOT NULL,
    previous_tx_hash VARCHAR(64) NOT NULL,
    previous_output_index INT NOT NULL,
    script_sig BYTES NOT NULL,
    sequence BIGINT NOT NULL DEFAULT 4294967295,

    UNIQUE INDEX tx_input_idx (tx_hash, input_index),
    INDEX prev_output_idx (previous_tx_hash, previous_output_index)
);

-- ================================================================
-- TRANSACTION OUTPUTS - Normalized UTXO creation (production)
-- Aligned with SQLAlchemy TransactionOutputModel
-- ================================================================
CREATE TABLE IF NOT EXISTS transaction_outputs (
    output_id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::STRING,
    tx_hash VARCHAR(64) NOT NULL,
    output_index INT NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    recipient_address VARCHAR NOT NULL,
    script_pubkey BYTES NOT NULL,
    is_spent BOOL NOT NULL DEFAULT false,
    spent_in_tx VARCHAR(64),
    spent_at_height BIGINT,
    spent_at_timestamp TIMESTAMP,

    UNIQUE INDEX tx_output_idx (tx_hash, output_index),
    INDEX recipient_idx (recipient_address),
    INDEX unspent_idx (is_spent, recipient_address) WHERE is_spent = false,
    INDEX amount_idx (amount DESC)
);

INSERT INTO schema_version (version, component, description)
VALUES ('2.0.0', 'qbc_utxo', 'UTXO model — aligned with SQLAlchemy ORM + normalized tables')
ON CONFLICT DO NOTHING;
