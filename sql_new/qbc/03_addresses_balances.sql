SET DATABASE = qubitcoin;

-- ================================================================
-- ADDRESSES - Balance tracking
-- Aligned with SQLAlchemy AddressModel (database/manager.py)
-- ================================================================
CREATE TABLE IF NOT EXISTS addresses (
    address BYTES PRIMARY KEY,
    balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_received DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_sent DECIMAL(20, 8) NOT NULL DEFAULT 0,
    tx_count BIGINT NOT NULL DEFAULT 0,
    utxo_count BIGINT NOT NULL DEFAULT 0,
    is_contract BOOL NOT NULL DEFAULT false,
    contract_bytecode_hash BYTES,
    first_seen_height BIGINT,
    first_seen_timestamp TIMESTAMP,
    last_active_height BIGINT,
    last_active_timestamp TIMESTAMP,

    INDEX balance_idx (balance DESC),
    INDEX last_active_idx (last_active_height DESC),
    INDEX contract_idx (is_contract) WHERE is_contract = true
);

INSERT INTO schema_version (version, component, description)
VALUES ('2.0.0', 'qbc_addresses', 'Address balances — aligned with SQLAlchemy ORM')
ON CONFLICT DO NOTHING;
