SET DATABASE = qubitcoin;

-- ================================================================
-- CHAIN STATE - Global blockchain state (singleton)
-- ================================================================
CREATE TABLE IF NOT EXISTS chain_state (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    
    -- Current best chain
    best_block_hash BYTES NOT NULL,
    best_block_height BIGINT NOT NULL DEFAULT 0,
    
    -- Statistics
    total_blocks BIGINT NOT NULL DEFAULT 0,
    total_transactions BIGINT NOT NULL DEFAULT 0,
    total_addresses BIGINT NOT NULL DEFAULT 0,
    
    -- Economics (φ-halving model)
    total_supply DECIMAL(30, 8) NOT NULL DEFAULT 0,
    circulating_supply DECIMAL(30, 8) NOT NULL DEFAULT 0,
    current_era INT NOT NULL DEFAULT 0,
    next_halving_height BIGINT NOT NULL DEFAULT 15474020,  -- φ years
    
    -- Mining & Consensus
    current_difficulty DECIMAL(20, 10) NOT NULL DEFAULT 1.0,
    network_hashrate DECIMAL(20, 10) NOT NULL DEFAULT 0,
    average_block_time DECIMAL(10, 2) NOT NULL DEFAULT 3.3,  -- Target: 3.3s
    
    -- QVM stats
    total_contracts BIGINT NOT NULL DEFAULT 0,
    total_contract_calls BIGINT NOT NULL DEFAULT 0,
    
    -- AGI stats
    total_knowledge_nodes BIGINT NOT NULL DEFAULT 0,
    total_reasoning_operations BIGINT NOT NULL DEFAULT 0,
    current_phi_score DECIMAL(10, 6) NOT NULL DEFAULT 0,
    
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

-- Initialize chain state
INSERT INTO chain_state (
    id, best_block_hash, best_block_height, current_difficulty
) VALUES (
    1,
    E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    0,
    1.0
) ON CONFLICT (id) DO NOTHING;

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'qbc_chain_state', 'Global blockchain state')
ON CONFLICT DO NOTHING;
