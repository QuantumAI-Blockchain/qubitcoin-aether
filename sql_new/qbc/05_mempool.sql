SET DATABASE = qubitcoin;

-- ================================================================
-- MEMPOOL - Unconfirmed transactions
-- ================================================================
CREATE TABLE IF NOT EXISTS mempool (
    tx_hash BYTES PRIMARY KEY,
    
    -- Raw transaction data
    raw_tx BYTES NOT NULL,
    tx_size BIGINT NOT NULL,
    
    -- Fee economics
    fee DECIMAL(20, 8) NOT NULL,
    fee_per_byte DECIMAL(20, 8) NOT NULL,
    gas_price DECIMAL(20, 8),  -- For contract txs
    
    -- Prioritization
    priority_score DECIMAL(10, 2) NOT NULL,
    
    -- Propagation tracking
    received_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    first_seen_peer VARCHAR(255),
    propagation_count INT NOT NULL DEFAULT 0,
    
    -- Validation
    is_valid BOOL NOT NULL DEFAULT true,
    validation_errors TEXT,
    
    INDEX fee_idx (fee DESC),
    INDEX priority_idx (priority_score DESC),
    INDEX timestamp_idx (received_timestamp),
    INDEX gas_price_idx (gas_price DESC) WHERE gas_price IS NOT NULL
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'qbc_mempool', 'Transaction mempool')
ON CONFLICT DO NOTHING;
