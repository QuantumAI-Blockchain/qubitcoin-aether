-- BFT Finality Gadget Schema
-- Stake-weighted validator voting for probabilistic finality

CREATE TABLE IF NOT EXISTS finality_validators (
    address TEXT PRIMARY KEY,
    stake DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    registered_at_block BIGINT NOT NULL,
    active BOOLEAN DEFAULT true,
    last_vote_block BIGINT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_finality_validators_active ON finality_validators (active);

CREATE TABLE IF NOT EXISTS finality_votes (
    id SERIAL PRIMARY KEY,
    voter_address TEXT NOT NULL,
    block_height BIGINT NOT NULL,
    block_hash TEXT NOT NULL,
    signature TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (voter_address, block_height)
);

CREATE INDEX IF NOT EXISTS idx_finality_votes_height ON finality_votes (block_height);
CREATE INDEX IF NOT EXISTS idx_finality_votes_voter ON finality_votes (voter_address);

CREATE TABLE IF NOT EXISTS finality_checkpoints (
    block_height BIGINT PRIMARY KEY,
    block_hash TEXT NOT NULL,
    voted_stake DOUBLE PRECISION NOT NULL,
    total_stake DOUBLE PRECISION NOT NULL,
    finalized_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_finality_checkpoints_height ON finality_checkpoints (block_height DESC);
