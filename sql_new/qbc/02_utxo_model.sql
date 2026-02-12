SET DATABASE = qubitcoin;

-- ================================================================
-- TRANSACTION INPUTS - UTXO spending
-- ================================================================
CREATE TABLE IF NOT EXISTS transaction_inputs (
    input_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_hash BYTES NOT NULL,
    input_index INT NOT NULL,
    
    -- Previous output reference
    previous_tx_hash BYTES NOT NULL,
    previous_output_index INT NOT NULL,
    
    -- Unlock script (signature)
    script_sig BYTES NOT NULL,
    sequence BIGINT NOT NULL DEFAULT 4294967295,
    
    UNIQUE INDEX tx_input_idx (tx_hash, input_index),
    INDEX prev_output_idx (previous_tx_hash, previous_output_index),
    
    CONSTRAINT fk_transaction FOREIGN KEY (tx_hash) 
        REFERENCES transactions(tx_hash) ON DELETE CASCADE
);

-- ================================================================
-- TRANSACTION OUTPUTS - UTXO creation
-- ================================================================
CREATE TABLE IF NOT EXISTS transaction_outputs (
    output_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_hash BYTES NOT NULL,
    output_index INT NOT NULL,
    
    -- Value & recipient
    amount DECIMAL(20, 8) NOT NULL,
    recipient_address BYTES NOT NULL,
    
    -- Locking script
    script_pubkey BYTES NOT NULL,
    
    -- Spending status
    is_spent BOOL NOT NULL DEFAULT false,
    spent_in_tx BYTES,
    spent_at_height BIGINT,
    spent_at_timestamp TIMESTAMP,
    
    UNIQUE INDEX tx_output_idx (tx_hash, output_index),
    INDEX recipient_idx (recipient_address),
    INDEX unspent_idx (is_spent, recipient_address) WHERE is_spent = false,
    INDEX amount_idx (amount DESC),
    
    CONSTRAINT fk_transaction FOREIGN KEY (tx_hash) 
        REFERENCES transactions(tx_hash) ON DELETE CASCADE
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'qbc_utxo', 'UTXO model - inputs and outputs')
ON CONFLICT DO NOTHING;
