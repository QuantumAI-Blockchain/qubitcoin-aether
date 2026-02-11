SET DATABASE = qubitcoin;

-- ================================================================
-- CONTRACT EXECUTIONS - All contract calls
-- ================================================================
CREATE TABLE IF NOT EXISTS contract_executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Transaction reference
    tx_hash BYTES NOT NULL,
    block_hash BYTES NOT NULL,
    block_height BIGINT NOT NULL,
    tx_index INT NOT NULL,
    
    -- Execution context
    contract_address BYTES NOT NULL,
    caller_address BYTES NOT NULL,
    function_selector BYTES NOT NULL,  -- First 4 bytes of keccak256(signature)
    function_name VARCHAR(255),
    input_data BYTES NOT NULL,
    
    -- Gas & economics
    gas_limit BIGINT NOT NULL,
    gas_used BIGINT NOT NULL,
    gas_price DECIMAL(20, 8) NOT NULL,
    execution_cost DECIMAL(20, 8) NOT NULL,
    
    -- Execution result
    success BOOL NOT NULL,
    return_data BYTES,
    error_message TEXT,
    revert_reason TEXT,
    
    -- Performance
    execution_time_ms BIGINT,
    opcodes_executed INT,
    
    -- State changes
    storage_writes INT NOT NULL DEFAULT 0,
    storage_reads INT NOT NULL DEFAULT 0,
    logs_count INT NOT NULL DEFAULT 0,
    
    timestamp TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX tx_idx (tx_hash),
    INDEX block_idx (block_height DESC),
    INDEX contract_idx (contract_address),
    INDEX caller_idx (caller_address),
    INDEX function_idx (function_selector),
    INDEX success_idx (success),
    INDEX timestamp_idx (timestamp DESC)
);

-- ================================================================
-- CONTRACT LOGS - Event emissions
-- ================================================================
CREATE TABLE IF NOT EXISTS contract_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Execution reference
    execution_id UUID NOT NULL,
    tx_hash BYTES NOT NULL,
    block_height BIGINT NOT NULL,
    contract_address BYTES NOT NULL,
    
    -- Log data
    log_index INT NOT NULL,
    topic0 BYTES NOT NULL,  -- Event signature
    topic1 BYTES,
    topic2 BYTES,
    topic3 BYTES,
    data BYTES NOT NULL,
    
    -- Decoded (if known)
    event_name VARCHAR(255),
    decoded_data JSONB,
    
    timestamp TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX execution_idx (execution_id),
    INDEX tx_idx (tx_hash),
    INDEX contract_idx (contract_address),
    INDEX topic0_idx (topic0),
    INDEX block_idx (block_height DESC),
    
    CONSTRAINT fk_execution FOREIGN KEY (execution_id) 
        REFERENCES contract_executions(execution_id) ON DELETE CASCADE
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'qvm_execution', 'Contract execution engine and logs')
ON CONFLICT DO NOTHING;
