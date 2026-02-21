SET DATABASE = qubitcoin;

-- ================================================================
-- SEPHIROT STATE - Persistent cognitive node state across restarts
-- ================================================================
CREATE TABLE IF NOT EXISTS sephirot_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Node identity (unique per role)
    node_id VARCHAR(50) NOT NULL,
    role VARCHAR(50) NOT NULL UNIQUE,

    -- Serialized state (JSON blob of all node-specific data)
    state_json JSONB NOT NULL,

    -- Timestamps
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    created_at TIMESTAMP NOT NULL DEFAULT now(),

    INDEX role_idx (role),
    INDEX updated_idx (updated_at DESC)
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'agi_sephirot_state', 'Sephirot cognitive node persistent state')
ON CONFLICT DO NOTHING;
