-- Higgs Cognitive Field State
-- Tracks field evolution, excitation events, and per-node mass assignments.
-- Part of the Aether Tree AGI schema.

CREATE TABLE IF NOT EXISTS higgs_field_state (
    id              SERIAL PRIMARY KEY,
    block_height    BIGINT NOT NULL,
    field_value     DOUBLE PRECISION NOT NULL,
    vev             DOUBLE PRECISION NOT NULL,
    mu              DOUBLE PRECISION NOT NULL,
    lambda_coupling DOUBLE PRECISION NOT NULL,
    tan_beta        DOUBLE PRECISION NOT NULL,
    potential_energy DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    mass_gap        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    avg_cognitive_mass DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_excitations INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (block_height)
);

CREATE TABLE IF NOT EXISTS higgs_node_masses (
    id              SERIAL PRIMARY KEY,
    node_id         SMALLINT NOT NULL,     -- 0-9 (Sephirot node ID)
    node_name       VARCHAR(32) NOT NULL,
    yukawa_coupling DOUBLE PRECISION NOT NULL,
    cognitive_mass  DOUBLE PRECISION NOT NULL,
    is_expansion    BOOLEAN NOT NULL DEFAULT false,
    vev_used        DOUBLE PRECISION NOT NULL,
    block_height    BIGINT NOT NULL,       -- Block when mass was last updated
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (node_id, block_height)
);

CREATE TABLE IF NOT EXISTS higgs_excitations (
    id               SERIAL PRIMARY KEY,
    block_height     BIGINT NOT NULL,
    field_deviation  DOUBLE PRECISION NOT NULL,
    deviation_bps    INTEGER NOT NULL,
    energy_released  DOUBLE PRECISION NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for time-series queries
CREATE INDEX IF NOT EXISTS idx_higgs_field_block ON higgs_field_state (block_height DESC);
CREATE INDEX IF NOT EXISTS idx_higgs_excitations_block ON higgs_excitations (block_height DESC);
CREATE INDEX IF NOT EXISTS idx_higgs_masses_node ON higgs_node_masses (node_id, block_height DESC);
