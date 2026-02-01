-- Create contracts table
CREATE TABLE IF NOT EXISTS contracts (
    contract_id STRING PRIMARY KEY,
    deployer_address STRING NOT NULL,
    contract_type STRING NOT NULL CHECK (contract_type IN ('token', 'nft', 'launchpad', 'escrow', 'governance', 'quantum_gate', 'stablecoin', 'vault', 'oracle')),
    contract_code JSONB NOT NULL,
    contract_state JSONB NOT NULL,
    gas_paid DECIMAL(18, 8) NOT NULL,
    block_height INT NOT NULL,
    deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_executed TIMESTAMP,
    execution_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    INDEX idx_deployer (deployer_address),
    INDEX idx_type (contract_type),
    INDEX idx_block (block_height DESC)
);

-- Create contract executions table
CREATE TABLE IF NOT EXISTS contract_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id STRING REFERENCES contracts(contract_id),
    caller_address STRING NOT NULL,
    function_name STRING NOT NULL,
    args JSONB NOT NULL,
    result JSONB,
    gas_used DECIMAL(18, 8) NOT NULL,
    block_height INT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN NOT NULL,
    INDEX idx_contract (contract_id, timestamp DESC),
    INDEX idx_caller (caller_address, timestamp DESC)
);
