SET DATABASE = qubitcoin;

CREATE TABLE IF NOT EXISTS smart_contracts (
    contract_address BYTES PRIMARY KEY,
    creator_address BYTES NOT NULL,
    deployer_tx_hash BYTES NOT NULL,
    deployed_at_height BIGINT NOT NULL,
    deployed_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    bytecode BYTES NOT NULL,
    bytecode_hash BYTES NOT NULL,
    contract_type VARCHAR(50) NOT NULL,
    is_verified BOOL NOT NULL DEFAULT false,
    balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    is_active BOOL NOT NULL DEFAULT true,
    INDEX creator_idx (creator_address),
    INDEX contract_type_idx (contract_type)
);

CREATE TABLE IF NOT EXISTS contract_executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_hash BYTES NOT NULL,
    block_height BIGINT NOT NULL,
    contract_address BYTES NOT NULL,
    caller_address BYTES NOT NULL,
    function_signature BYTES NOT NULL,
    gas_limit BIGINT NOT NULL,
    gas_used BIGINT NOT NULL,
    success BOOL NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT now(),
    INDEX contract_idx (contract_address),
    INDEX timestamp_idx (timestamp DESC),
    CONSTRAINT fk_contract FOREIGN KEY (contract_address) REFERENCES smart_contracts(contract_address)
);

CREATE TABLE IF NOT EXISTS token_contracts (
    contract_address BYTES PRIMARY KEY,
    token_standard VARCHAR(20) NOT NULL,
    token_name VARCHAR(255) NOT NULL,
    token_symbol VARCHAR(50) NOT NULL,
    decimals INT,
    total_supply DECIMAL(30, 8),
    total_holders BIGINT NOT NULL DEFAULT 0,
    INDEX symbol_idx (token_symbol),
    CONSTRAINT fk_contract FOREIGN KEY (contract_address) REFERENCES smart_contracts(contract_address)
);

-- Quantum State Persistence (QSP)
CREATE TABLE IF NOT EXISTS quantum_states (
    state_id STRING PRIMARY KEY,
    n_qubits INT NOT NULL,
    contract_address STRING NOT NULL,
    block_height BIGINT NOT NULL,
    measured BOOL NOT NULL DEFAULT false,
    entangled_with STRING,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    INDEX contract_idx (contract_address),
    INDEX block_height_idx (block_height),
    INDEX unmeasured_idx (measured) WHERE measured = false
);

-- Entanglement registry
CREATE TABLE IF NOT EXISTS entanglement_pairs (
    pair_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_a STRING NOT NULL,
    state_b STRING NOT NULL,
    block_height BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    is_active BOOL NOT NULL DEFAULT true,
    INDEX state_a_idx (state_a),
    INDEX state_b_idx (state_b),
    INDEX active_idx (is_active) WHERE is_active = true
);

-- Compliance registry (KYC/AML)
CREATE TABLE IF NOT EXISTS compliance_registry (
    address STRING PRIMARY KEY,
    kyc_level INT NOT NULL DEFAULT 0,
    aml_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
    sanctions_checked BOOL NOT NULL DEFAULT false,
    last_verified TIMESTAMP,
    jurisdiction VARCHAR(10),
    daily_limit DECIMAL(20, 8) NOT NULL DEFAULT 10000,
    is_blocked BOOL NOT NULL DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    INDEX kyc_level_idx (kyc_level),
    INDEX blocked_idx (is_blocked) WHERE is_blocked = true
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.1.0', 'smart_contracts', 'QSP, entanglement registry, compliance');
