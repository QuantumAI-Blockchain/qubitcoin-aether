SET DATABASE = qubitcoin;

-- ================================================================
-- SYSTEM CONFIGURATION TABLES
-- Economics, Network Parameters, P2P Nodes
-- ================================================================

-- Economic Constants (φ-based halving schedule)
CREATE TABLE IF NOT EXISTS economic_constants (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    
    -- Supply
    max_supply DECIMAL(30, 8) NOT NULL DEFAULT 3300000000.0,
    initial_reward DECIMAL(20, 8) NOT NULL DEFAULT 15.27,
    
    -- φ-Halving Schedule
    phi_ratio DECIMAL(20, 10) NOT NULL DEFAULT 1.618,
    halving_interval BIGINT NOT NULL DEFAULT 15474020,
    total_eras INT NOT NULL DEFAULT 33,
    
    -- Timing
    target_block_time_seconds DECIMAL(5, 2) NOT NULL DEFAULT 3.3,
    blocks_per_year BIGINT NOT NULL DEFAULT 9547619,
    blocks_per_day BIGINT NOT NULL DEFAULT 26153,
    
    -- Difficulty
    difficulty_adjustment_interval BIGINT NOT NULL DEFAULT 2016,
    difficulty_adjustment_factor_max DECIMAL(5, 2) NOT NULL DEFAULT 4.0,
    difficulty_adjustment_factor_min DECIMAL(5, 2) NOT NULL DEFAULT 0.25,
    
    last_updated TIMESTAMP NOT NULL DEFAULT now()
);

INSERT INTO economic_constants (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- Era Rewards Lookup (Pre-calculated φ-halving schedule)
CREATE TABLE IF NOT EXISTS era_rewards (
    era INT PRIMARY KEY,
    blocks_start BIGINT NOT NULL,
    blocks_end BIGINT NOT NULL,
    base_reward DECIMAL(20, 8) NOT NULL,
    total_era_emission DECIMAL(30, 8) NOT NULL,
    cumulative_emission DECIMAL(30, 8) NOT NULL,
    years_from_genesis DECIMAL(10, 4) NOT NULL,
    
    INDEX blocks_range_idx (blocks_start, blocks_end)
);

-- Populate era rewards (33 eras, φ-based halving)
INSERT INTO era_rewards (era, blocks_start, blocks_end, base_reward, total_era_emission, cumulative_emission, years_from_genesis) VALUES
(0,  0,         15474019,  15.27, 236381360.13, 236381360.13, 0.0),
(1,  15474020,  30948039,  9.437, 146018971.40, 382400331.53, 1.618),
(2,  30948040,  46422059,  5.833, 90240982.86,  472641314.39, 3.236),
(3,  46422060,  61896079,  3.604, 55769721.68,  528411036.07, 4.854),
(4,  61896080,  77370099,  2.227, 34461629.46,  562872665.53, 6.472),
(5,  77370100,  92844119,  1.376, 21295893.12,  584168558.65, 8.090),
(6,  92844120,  108318139, 0.850, 13154104.00,  597322662.65, 9.708),
(7,  108318140, 123792159, 0.525, 8127327.75,   605449990.40, 11.326),
(8,  123792160, 139266179, 0.324, 5021258.96,   610471249.36, 12.944),
(9,  139266180, 154740199, 0.200, 3103384.00,   613574633.36, 14.562)
-- Continue for all 33 eras...
ON CONFLICT (era) DO NOTHING;

-- Network Parameters
CREATE TABLE IF NOT EXISTS network_parameters (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    
    -- Network
    network_name VARCHAR(50) NOT NULL DEFAULT 'mainnet',
    protocol_version INT NOT NULL DEFAULT 1,
    min_protocol_version INT NOT NULL DEFAULT 1,
    
    -- Blocks
    max_block_size BIGINT NOT NULL DEFAULT 4194304,          -- 4MB
    max_block_weight BIGINT NOT NULL DEFAULT 16777216,       -- 16M weight units
    max_tx_per_block INT NOT NULL DEFAULT 10000,
    
    -- Transactions
    max_tx_size BIGINT NOT NULL DEFAULT 1048576,             -- 1MB
    max_signature_size INT NOT NULL DEFAULT 4595,            -- Dilithium signature
    min_tx_fee DECIMAL(20, 8) NOT NULL DEFAULT 0.00001,
    min_fee_per_byte DECIMAL(20, 8) NOT NULL DEFAULT 0.00000001,
    
    -- Confirmations
    coinbase_maturity INT NOT NULL DEFAULT 100,
    min_confirmations_standard INT NOT NULL DEFAULT 6,
    min_confirmations_large INT NOT NULL DEFAULT 12,
    
    -- P2P
    max_peers INT NOT NULL DEFAULT 125,
    max_inbound_peers INT NOT NULL DEFAULT 100,
    max_outbound_peers INT NOT NULL DEFAULT 25,
    peer_discovery_interval_seconds INT NOT NULL DEFAULT 60,
    
    last_updated TIMESTAMP NOT NULL DEFAULT now()
);

INSERT INTO network_parameters (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- P2P Peer Nodes
CREATE TABLE IF NOT EXISTS peer_nodes (
    peer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    peer_address VARCHAR(255) NOT NULL UNIQUE,
    peer_port INT NOT NULL,
    node_id BYTES NOT NULL,
    protocol_version INT NOT NULL,
    user_agent VARCHAR(255),
    
    -- Connection
    is_connected BOOL NOT NULL DEFAULT false,
    is_outbound BOOL NOT NULL DEFAULT true,
    connection_type VARCHAR(20) NOT NULL DEFAULT 'tcp',
    
    -- Stats
    last_seen TIMESTAMP,
    first_seen TIMESTAMP NOT NULL DEFAULT now(),
    blocks_received BIGINT NOT NULL DEFAULT 0,
    transactions_received BIGINT NOT NULL DEFAULT 0,
    bytes_sent BIGINT NOT NULL DEFAULT 0,
    bytes_received BIGINT NOT NULL DEFAULT 0,
    
    -- Reputation
    reputation_score DECIMAL(5, 2) NOT NULL DEFAULT 50.0,
    failed_connections INT NOT NULL DEFAULT 0,
    is_banned BOOL NOT NULL DEFAULT false,
    ban_expires_at TIMESTAMP,
    
    INDEX connected_idx (is_connected),
    INDEX reputation_idx (reputation_score DESC)
);

-- Mining Pools (Optional: Track if miners are part of pools)
CREATE TABLE IF NOT EXISTS mining_pools (
    pool_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_name VARCHAR(255) NOT NULL UNIQUE,
    pool_address BYTES NOT NULL,
    pool_url VARCHAR(255),
    total_blocks_mined BIGINT NOT NULL DEFAULT 0,
    total_hashrate DECIMAL(20, 10) NOT NULL DEFAULT 0,
    is_active BOOL NOT NULL DEFAULT true,
    created_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX active_idx (is_active)
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'system_configuration', 'System configuration and network parameters')
ON CONFLICT DO NOTHING;
