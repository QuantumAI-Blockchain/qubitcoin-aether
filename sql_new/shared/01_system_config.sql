SET DATABASE = qubitcoin;

-- ================================================================
-- SYSTEM CONFIG - Global configuration parameters
-- ================================================================
CREATE TABLE IF NOT EXISTS system_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value TEXT NOT NULL,
    config_type VARCHAR(20) NOT NULL,  -- 'string', 'integer', 'decimal', 'boolean', 'json'
    category VARCHAR(50) NOT NULL,  -- 'blockchain', 'qvm', 'agi', 'network', 'economics'
    description TEXT,
    is_mutable BOOL NOT NULL DEFAULT true,
    requires_consensus BOOL NOT NULL DEFAULT false,
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_by BYTES,
    
    INDEX category_idx (category),
    INDEX mutable_idx (is_mutable)
);

-- Initialize core configuration
INSERT INTO system_config (config_key, config_value, config_type, category, description, is_mutable) VALUES
-- Blockchain
('target_block_time', '3.3', 'decimal', 'blockchain', 'Target block time in seconds (supersymmetric)', false),
('max_supply', '3300000000', 'integer', 'blockchain', 'Maximum QBC supply (3.3 billion)', false),
('halving_interval', '15474020', 'integer', 'blockchain', 'Blocks per halving (φ years)', false),
('initial_reward', '15.27', 'decimal', 'blockchain', 'Initial block reward', false),
('difficulty_adjustment_interval', '1000', 'integer', 'blockchain', 'Blocks between difficulty adjustment', true),

-- QVM
('qvm_gas_limit_block', '30000000', 'integer', 'qvm', 'Gas limit per block', true),
('qvm_base_fee', '0.0001', 'decimal', 'qvm', 'Base gas fee in QBC', true),
('qvm_max_contract_size', '24576', 'integer', 'qvm', 'Max contract bytecode size (bytes)', false),

-- AGI
('phi_consciousness_threshold', '3.0', 'decimal', 'agi', 'Phi value for consciousness threshold', true),
('max_knowledge_nodes', '10000000', 'integer', 'agi', 'Maximum knowledge graph nodes', true),
('reasoning_timeout_ms', '5000', 'integer', 'agi', 'Max reasoning operation time', true),

-- Network
('max_peers', '50', 'integer', 'network', 'Maximum peer connections', true),
('min_peers', '3', 'integer', 'network', 'Minimum peer connections', true),
('block_propagation_timeout', '10', 'integer', 'network', 'Block propagation timeout (seconds)', true)

ON CONFLICT DO NOTHING;

-- ================================================================
-- NETWORK PEERS - P2P network tracking
-- ================================================================
CREATE TABLE IF NOT EXISTS network_peers (
    peer_id VARCHAR(255) PRIMARY KEY,
    
    -- Connection info
    ip_address VARCHAR(45) NOT NULL,
    port INT NOT NULL,
    node_type VARCHAR(20) NOT NULL,  -- 'full', 'light', 'mining', 'archive'
    
    -- Status
    is_connected BOOL NOT NULL DEFAULT true,
    connection_quality VARCHAR(20),  -- 'excellent', 'good', 'poor'
    
    -- Statistics
    blocks_shared BIGINT NOT NULL DEFAULT 0,
    transactions_shared BIGINT NOT NULL DEFAULT 0,
    average_latency_ms BIGINT,
    
    -- Version
    client_version VARCHAR(50),
    protocol_version VARCHAR(20),
    
    -- Timestamps
    first_seen TIMESTAMP NOT NULL DEFAULT now(),
    last_seen TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX connected_idx (is_connected) WHERE is_connected = true,
    INDEX node_type_idx (node_type),
    INDEX last_seen_idx (last_seen DESC)
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'shared_config', 'System configuration and network peers')
ON CONFLICT DO NOTHING;
