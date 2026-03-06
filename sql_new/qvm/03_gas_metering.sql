SET DATABASE = qubitcoin;

-- ================================================================
-- OPCODE GAS TABLE - QVM instruction gas costs (simplified)
-- Aligned with SQLAlchemy OpcodeGasModel (database/manager.py)
-- ================================================================
CREATE TABLE IF NOT EXISTS opcode_gas (
    opcode INT PRIMARY KEY,
    name VARCHAR(20) NOT NULL,
    gas_cost BIGINT NOT NULL,
    category VARCHAR(20) DEFAULT 'arithmetic'
);

-- Initialize common opcodes
INSERT INTO opcode_gas (opcode, name, gas_cost, category) VALUES
(0, 'STOP', 0, 'control'),
(1, 'ADD', 3, 'arithmetic'),
(2, 'MUL', 5, 'arithmetic'),
(3, 'SUB', 3, 'arithmetic'),
(4, 'DIV', 5, 'arithmetic'),
(84, 'SLOAD', 800, 'storage'),
(85, 'SSTORE', 20000, 'storage'),
(241, 'CALL', 700, 'control'),
(240, 'CREATE', 32000, 'control')
ON CONFLICT DO NOTHING;

-- ================================================================
-- GAS PRICE ORACLE - Dynamic gas pricing
-- Aligned with SQLAlchemy GasPriceOracleModel (database/manager.py)
-- ================================================================
CREATE TABLE IF NOT EXISTS gas_price_oracle (
    oracle_id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::STRING,
    block_height BIGINT NOT NULL,
    base_fee DECIMAL(20, 8) NOT NULL,
    priority_fee_percentile_50 DECIMAL(20, 8) NOT NULL,
    priority_fee_percentile_75 DECIMAL(20, 8) NOT NULL,
    priority_fee_percentile_90 DECIMAL(20, 8) NOT NULL,
    gas_used BIGINT NOT NULL,
    gas_limit BIGINT NOT NULL,
    utilization_percent DECIMAL(5, 2) NOT NULL,
    sample_size INT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT now(),

    INDEX height_idx (block_height DESC),
    INDEX timestamp_idx (timestamp DESC)
);

-- ================================================================
-- OPCODE COSTS - Production-grade QVM instruction definitions
-- Aligned with SQLAlchemy OpcodeCostModel (database/manager.py)
-- ================================================================
CREATE TABLE IF NOT EXISTS opcode_costs (
    opcode_id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::STRING,
    opcode_name VARCHAR(50) NOT NULL UNIQUE,
    opcode_value INT NOT NULL,
    base_gas_cost BIGINT NOT NULL,
    memory_gas_cost BIGINT NOT NULL DEFAULT 0,
    storage_gas_cost BIGINT NOT NULL DEFAULT 0,
    category VARCHAR(50) NOT NULL,
    description TEXT,
    is_quantum_enhanced BOOL NOT NULL DEFAULT false,

    INDEX opcode_idx (opcode_value),
    INDEX category_idx (category)
);

INSERT INTO schema_version (version, component, description)
VALUES ('2.0.0', 'qvm_gas', 'Gas metering — aligned with SQLAlchemy ORM')
ON CONFLICT DO NOTHING;
