-- AGI Persistence Tables
-- Stores neural weights, episodic memory, self-improvement state,
-- metacognition calibration, and temporal series across restarts.

-- Neural Reasoner weights (MLP/GAT model checkpoints)
CREATE TABLE IF NOT EXISTS agi_neural_weights (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name    TEXT NOT NULL DEFAULT 'neural_reasoner',
    version       INT NOT NULL DEFAULT 1,
    weights_blob  BYTEA NOT NULL,
    metadata      JSONB NOT NULL DEFAULT '{}',
    block_height  INT NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_neural_weights_model ON agi_neural_weights (model_name, version DESC);

-- Episodic memory (reasoning episodes that survive restarts)
CREATE TABLE IF NOT EXISTS agi_episodes (
    episode_id         SERIAL PRIMARY KEY,
    block_height       INT NOT NULL,
    input_node_ids     INT[] NOT NULL DEFAULT '{}',
    reasoning_strategy TEXT NOT NULL DEFAULT '',
    conclusion_node_id INT,
    success            BOOLEAN NOT NULL DEFAULT false,
    confidence         FLOAT NOT NULL DEFAULT 0.0,
    replay_count       INT NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_episodes_block ON agi_episodes (block_height DESC);
CREATE INDEX IF NOT EXISTS idx_episodes_strategy ON agi_episodes (reasoning_strategy);

-- Self-improvement domain weights (66-weight matrix)
CREATE TABLE IF NOT EXISTS agi_domain_weights (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain       TEXT NOT NULL,
    strategy     TEXT NOT NULL,
    weight       FLOAT NOT NULL DEFAULT 0.0,
    block_height INT NOT NULL DEFAULT 0,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (domain, strategy)
);

-- Metacognition calibration state
CREATE TABLE IF NOT EXISTS agi_metacognition (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_stats   JSONB NOT NULL DEFAULT '{}',
    domain_stats     JSONB NOT NULL DEFAULT '{}',
    confidence_bins  JSONB NOT NULL DEFAULT '{}',
    strategy_weights JSONB NOT NULL DEFAULT '{}',
    total_evaluations INT NOT NULL DEFAULT 0,
    total_correct    INT NOT NULL DEFAULT 0,
    block_height     INT NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Temporal time-series persistence
CREATE TABLE IF NOT EXISTS agi_time_series (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name  TEXT NOT NULL,
    block_height INT NOT NULL,
    value        FLOAT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_time_series_metric ON agi_time_series (metric_name, block_height DESC);
