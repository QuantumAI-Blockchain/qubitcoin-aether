SET DATABASE = qubitcoin;

-- ================================================================
-- GAS PRICE ORACLE - Dynamic gas pricing
-- ================================================================
CREATE TABLE IF NOT EXISTS gas_price_oracle (
    oracle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    block_height BIGINT NOT NULL,
    
    -- Gas prices (in QBC wei)
    base_fee DECIMAL(20, 8) NOT NULL,
    priority_fee_percentile_50 DECIMAL(20, 8) NOT NULL,
    priority_fee_percentile_75 DECIMAL(20, 8) NOT NULL,
    priority_fee_percentile_90 DECIMAL(20, 8) NOT NULL,
    
    -- Network utilization
    gas_used BIGINT NOT NULL,
    gas_limit BIGINT NOT NULL,
    utilization_percent DECIMAL(5, 2) NOT NULL,
    
    -- Sample stats
    sample_size INT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX height_idx (block_height DESC),
    INDEX timestamp_idx (timestamp DESC)
);

-- ================================================================
-- OPCODE COSTS - QVM instruction gas costs
-- ================================================================
CREATE TABLE IF NOT EXISTS opcode_costs (
    opcode_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opcode_name VARCHAR(50) NOT NULL UNIQUE,
    opcode_value INT NOT NULL,
    
    -- Gas costs
    base_gas_cost BIGINT NOT NULL,
    memory_gas_cost BIGINT NOT NULL DEFAULT 0,
    storage_gas_cost BIGINT NOT NULL DEFAULT 0,
    
    -- Metadata
    category VARCHAR(50) NOT NULL,  -- 'arithmetic', 'storage', 'control', 'crypto'
    description TEXT,
    is_quantum_enhanced BOOL NOT NULL DEFAULT false,
    
    INDEX opcode_idx (opcode_value),
    INDEX category_idx (category)
);

-- Initialize common opcodes
INSERT INTO opcode_costs (opcode_name, opcode_value, base_gas_cost, category, description) VALUES
('STOP', 0, 0, 'control', 'Halts execution'),
('ADD', 1, 3, 'arithmetic', '32-bit addition'),
('MUL', 2, 5, 'arithmetic', '32-bit multiplication'),
('SUB', 3, 3, 'arithmetic', '32-bit subtraction'),
('DIV', 4, 5, 'arithmetic', '32-bit division'),
('SLOAD', 54, 800, 'storage', 'Load word from storage'),
('SSTORE', 55, 20000, 'storage', 'Save word to storage'),
('CALL', 241, 700, 'control', 'Call another contract'),
('CREATE', 240, 32000, 'control', 'Create new contract')
ON CONFLICT DO NOTHING;

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'qvm_gas', 'Gas metering and pricing oracle')
ON CONFLICT DO NOTHING;
