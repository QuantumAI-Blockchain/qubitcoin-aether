SET DATABASE = qubitcoin;

-- ================================================================
-- REASONING OPERATIONS - Inference and deduction
-- Aligned with SQLAlchemy ORM (database/models.py ReasoningOperation)
-- ================================================================
CREATE TABLE IF NOT EXISTS reasoning_operations (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,

    -- Operation type
    operation_type VARCHAR(30) NOT NULL,  -- 'deduction', 'induction', 'abduction', 'chain_of_thought', 'analogy', 'contradiction_resolution'

    -- Input/Output
    premise_nodes JSONB,           -- List of premise node IDs
    conclusion_node_id BIGINT,     -- ID of the conclusion node created

    -- Confidence
    confidence FLOAT NOT NULL DEFAULT 0.0,

    -- Reasoning chain
    reasoning_chain JSONB,         -- Full reasoning trace

    -- Blockchain anchoring
    block_height BIGINT,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT now(),

    INDEX operation_type_idx (operation_type),
    INDEX confidence_idx (confidence DESC),
    INDEX block_height_idx (block_height)
);

INSERT INTO schema_version (version, component, description)
VALUES ('2.0.0', 'agi_reasoning', 'AetherTree reasoning engine — aligned with ORM')
ON CONFLICT DO NOTHING;
