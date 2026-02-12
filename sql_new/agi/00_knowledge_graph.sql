SET DATABASE = qubitcoin;

-- ================================================================
-- KNOWLEDGE NODES - Core knowledge representation
-- ================================================================
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Node identity
    node_type VARCHAR(50) NOT NULL,  -- 'concept', 'entity', 'relation', 'rule', 'pattern'
    node_label VARCHAR(500) NOT NULL,
    node_hash BYTES NOT NULL UNIQUE,
    
    -- Content
    content_text TEXT,
    content_embedding FLOAT8[],  -- Vector embedding (e.g., 768-dim)
    content_metadata JSONB,
    
    -- Confidence & validation
    confidence_score DECIMAL(5, 4) NOT NULL DEFAULT 0.5,  -- 0.0 to 1.0
    validation_count INT NOT NULL DEFAULT 0,
    consensus_weight DECIMAL(10, 6) NOT NULL DEFAULT 1.0,
    
    -- Blockchain anchoring
    anchored_to_block BIGINT,
    anchor_tx_hash BYTES,
    is_immutable BOOL NOT NULL DEFAULT false,
    
    -- Relationships
    parent_nodes UUID[],
    child_nodes UUID[],
    related_nodes UUID[],
    
    -- Source tracking
    source_type VARCHAR(50),  -- 'blockchain', 'oracle', 'user_input', 'ai_generated', 'consensus'
    source_address BYTES,
    
    -- IPFS
    ipfs_hash VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX type_idx (node_type),
    INDEX label_idx (node_label),
    INDEX confidence_idx (confidence_score DESC),
    INDEX anchor_idx (anchored_to_block),
    INDEX source_idx (source_type)
);

-- ================================================================
-- KNOWLEDGE EDGES - Relationships between nodes
-- ================================================================
CREATE TABLE IF NOT EXISTS knowledge_edges (
    edge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Edge definition
    source_node UUID NOT NULL,
    target_node UUID NOT NULL,
    edge_type VARCHAR(50) NOT NULL,  -- 'is_a', 'part_of', 'related_to', 'causes', 'implies'
    edge_weight DECIMAL(5, 4) NOT NULL DEFAULT 1.0,
    
    -- Directionality
    is_bidirectional BOOL NOT NULL DEFAULT false,
    
    -- Evidence
    evidence_count INT NOT NULL DEFAULT 0,
    confidence_score DECIMAL(5, 4) NOT NULL DEFAULT 0.5,
    
    -- Metadata
    properties JSONB,
    
    -- Blockchain anchoring
    anchored_to_block BIGINT,
    
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    
    UNIQUE INDEX edge_unique_idx (source_node, target_node, edge_type),
    INDEX source_idx (source_node),
    INDEX target_idx (target_node),
    INDEX type_idx (edge_type),
    INDEX weight_idx (edge_weight DESC),
    
    CONSTRAINT fk_source FOREIGN KEY (source_node) 
        REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE,
    CONSTRAINT fk_target FOREIGN KEY (target_node) 
        REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'agi_knowledge_graph', 'AetherTree knowledge graph structure')
ON CONFLICT DO NOTHING;
