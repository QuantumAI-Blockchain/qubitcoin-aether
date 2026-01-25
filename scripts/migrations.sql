-- Qubitcoin Production Database Schema
-- Run on CockroachDB v23.2+

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Users table
CREATE TABLE IF NOT EXISTS users (
    address STRING PRIMARY KEY,
    public_key BYTES NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_last_activity (last_activity DESC)
);

-- UTXO table (Unspent Transaction Outputs)
CREATE TABLE IF NOT EXISTS utxos (
    txid STRING NOT NULL,
    vout INT NOT NULL,
    amount DECIMAL(18, 8) NOT NULL CHECK (amount > 0),
    address STRING NOT NULL,
    proof JSONB NOT NULL,
    block_height INT,
    spent BOOLEAN DEFAULT false NOT NULL,
    spent_by STRING,
    spent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (txid, vout),
    INDEX idx_address_unspent (address) WHERE spent = false,
    INDEX idx_block_height (block_height DESC)
);

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    txid STRING PRIMARY KEY,
    inputs JSONB NOT NULL,
    outputs JSONB NOT NULL,
    fee DECIMAL(18, 8) NOT NULL CHECK (fee >= 0),
    signature STRING NOT NULL,
    public_key STRING NOT NULL,
    timestamp FLOAT NOT NULL,
    status STRING NOT NULL CHECK (status IN ('pending', 'confirmed', 'rejected')),
    block_height INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status) WHERE status = 'pending',
    INDEX idx_block_height (block_height),
    INDEX idx_timestamp (timestamp DESC)
);

-- Blocks table
CREATE TABLE IF NOT EXISTS blocks (
    height INT PRIMARY KEY,
    prev_hash STRING NOT NULL,
    proof_json JSONB NOT NULL,
    difficulty FLOAT NOT NULL CHECK (difficulty > 0),
    created_at TIMESTAMP NOT NULL,
    block_hash STRING,
    INDEX idx_created_at (created_at DESC)
);

-- Supply tracking
CREATE TABLE IF NOT EXISTS supply (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    total_minted DECIMAL(18, 8) DEFAULT 0 CHECK (total_minted >= 0 AND total_minted <= 21000000)
);

INSERT INTO supply (id, total_minted) VALUES (1, 0) ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- RESEARCH TABLES
-- ============================================================================

-- Solved Hamiltonians (SUSY research data)
CREATE TABLE IF NOT EXISTS solved_hamiltonians (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hamiltonian JSONB NOT NULL,
    params JSONB NOT NULL,
    energy FLOAT NOT NULL,
    miner_address STRING,
    block_height INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_energy (energy),
    INDEX idx_block_height (block_height)
);

-- SUSY Swaps (privacy mixing)
CREATE TABLE IF NOT EXISTS susy_swaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participants JSONB NOT NULL,
    transforms JSONB NOT NULL,
    status STRING NOT NULL CHECK (status IN ('initiating', 'entangled', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    INDEX idx_status (status)
);

-- ============================================================================
-- P2P & NETWORK TABLES
-- ============================================================================

-- Peer reputation
CREATE TABLE IF NOT EXISTS peer_reputation (
    peer_id STRING PRIMARY KEY,
    score INT DEFAULT 100 CHECK (score >= 0 AND score <= 100),
    messages_sent INT DEFAULT 0,
    messages_received INT DEFAULT 0,
    blocks_provided INT DEFAULT 0,
    invalid_data_count INT DEFAULT 0,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    banned BOOLEAN DEFAULT false,
    ban_reason STRING,
    INDEX idx_score (score DESC)
);

-- IPFS snapshots
CREATE TABLE IF NOT EXISTS ipfs_snapshots (
    cid STRING PRIMARY KEY,
    block_height INT NOT NULL,
    chain_hash STRING NOT NULL,
    size_bytes BIGINT,
    pinned BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_block_height (block_height DESC)
);

-- ============================================================================
-- VIEWS
-- ============================================================================

CREATE VIEW IF NOT EXISTS balances AS
SELECT 
    address,
    SUM(amount) AS balance,
    COUNT(*) AS utxo_count
FROM utxos
WHERE spent = false
GROUP BY address;

CREATE VIEW IF NOT EXISTS recent_blocks AS
SELECT 
    height,
    prev_hash,
    difficulty,
    created_at,
    (SELECT COUNT(*) FROM transactions WHERE block_height = blocks.height) AS tx_count
FROM blocks
ORDER BY height DESC
LIMIT 100;

-- ============================================================================
-- INITIALIZATION
-- ============================================================================

-- Create statistics for query optimizer
ANALYZE users;
ANALYZE utxos;
ANALYZE transactions;
ANALYZE blocks;
