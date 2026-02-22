SET DATABASE = qubitcoin;

-- ================================================================
-- KNOWLEDGE NODES - Core knowledge representation
-- Aligned with SQLAlchemy ORM (database/models.py KnowledgeNode)
-- ================================================================
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,

    -- Node identity
    node_type VARCHAR(50) NOT NULL,  -- 'assertion', 'observation', 'inference', 'axiom', 'prediction', 'meta_observation'
    content_hash VARCHAR(64) NOT NULL,

    -- Content (JSONB for flexible schema)
    content JSONB NOT NULL,

    -- Confidence & validation
    confidence FLOAT NOT NULL DEFAULT 0.5,  -- 0.0 to 1.0

    -- Blockchain anchoring
    source_block BIGINT,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT now(),

    INDEX type_idx (node_type),
    INDEX confidence_idx (confidence DESC),
    INDEX source_block_idx (source_block)
);

-- ================================================================
-- KNOWLEDGE EDGES - Relationships between nodes
-- Aligned with SQLAlchemy ORM (database/models.py KnowledgeEdge)
-- ================================================================
CREATE TABLE IF NOT EXISTS knowledge_edges (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,

    -- Edge definition
    from_node_id BIGINT NOT NULL,
    to_node_id BIGINT NOT NULL,
    edge_type VARCHAR(50) NOT NULL,  -- 'supports', 'contradicts', 'derives', 'requires', 'refines', 'causes', 'abstracts', 'analogous_to'
    weight FLOAT NOT NULL DEFAULT 1.0,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT now(),

    UNIQUE INDEX edge_unique_idx (from_node_id, to_node_id, edge_type),
    INDEX from_idx (from_node_id),
    INDEX to_idx (to_node_id),
    INDEX type_idx (edge_type)
);

INSERT INTO schema_version (version, component, description)
VALUES ('2.0.0', 'agi_knowledge_graph', 'AetherTree knowledge graph — aligned with ORM (BigInt IDs)')
ON CONFLICT DO NOTHING;
