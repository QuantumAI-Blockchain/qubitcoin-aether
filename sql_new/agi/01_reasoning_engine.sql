SET DATABASE = qubitcoin;

-- ================================================================
-- REASONING OPERATIONS - Inference and deduction
-- ================================================================
CREATE TABLE IF NOT EXISTS reasoning_operations (
    operation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Operation type
    reasoning_type VARCHAR(50) NOT NULL,  -- 'deduction', 'induction', 'abduction', 'analogy', 'causal'
    operation_name VARCHAR(255) NOT NULL,
    
    -- Input
    input_nodes UUID[] NOT NULL,
    input_context JSONB,
    query_text TEXT,
    
    -- Output
    output_nodes UUID[],
    inferred_relations JSONB,
    conclusion TEXT,
    confidence_score DECIMAL(5, 4) NOT NULL,
    
    -- Execution
    execution_time_ms BIGINT NOT NULL,
    computational_steps INT NOT NULL,
    proof_chain JSONB,
    
    -- Blockchain anchoring
    triggered_by_tx BYTES,
    anchored_to_block BIGINT,
    
    -- Verification
    is_verified BOOL NOT NULL DEFAULT false,
    verification_count INT NOT NULL DEFAULT 0,
    consensus_reached BOOL NOT NULL DEFAULT false,
    
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX reasoning_type_idx (reasoning_type),
    INDEX confidence_idx (confidence_score DESC),
    INDEX verified_idx (is_verified),
    INDEX block_idx (anchored_to_block)
);

-- ================================================================
-- INFERENCE RULES - Logic rules for reasoning
-- ================================================================
CREATE TABLE IF NOT EXISTS inference_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Rule definition
    rule_name VARCHAR(255) NOT NULL UNIQUE,
    rule_type VARCHAR(50) NOT NULL,  -- 'modus_ponens', 'syllogism', 'bayesian', 'fuzzy', 'custom'
    
    -- Logic
    premise_pattern JSONB NOT NULL,
    conclusion_pattern JSONB NOT NULL,
    condition_expression TEXT,
    
    -- Confidence
    rule_confidence DECIMAL(5, 4) NOT NULL DEFAULT 1.0,
    success_rate DECIMAL(5, 4) NOT NULL DEFAULT 0.0,
    application_count BIGINT NOT NULL DEFAULT 0,
    
    -- Status
    is_active BOOL NOT NULL DEFAULT true,
    is_validated BOOL NOT NULL DEFAULT false,
    
    -- Governance
    created_by_address BYTES,
    requires_consensus BOOL NOT NULL DEFAULT false,
    
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX type_idx (rule_type),
    INDEX active_idx (is_active) WHERE is_active = true,
    INDEX confidence_idx (rule_confidence DESC)
);

-- ================================================================
-- CAUSAL CHAINS - Cause-effect relationships
-- ================================================================
CREATE TABLE IF NOT EXISTS causal_chains (
    chain_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Chain definition
    cause_node UUID NOT NULL,
    effect_node UUID NOT NULL,
    
    -- Causality strength
    causal_strength DECIMAL(5, 4) NOT NULL,  -- 0.0 to 1.0
    causal_type VARCHAR(50) NOT NULL,  -- 'direct', 'indirect', 'probabilistic', 'deterministic'
    
    -- Evidence
    evidence_count INT NOT NULL DEFAULT 0,
    supporting_data JSONB,
    
    -- Intermediate steps
    intermediate_nodes UUID[],
    path_length INT NOT NULL DEFAULT 1,
    
    -- Validation
    is_validated BOOL NOT NULL DEFAULT false,
    validation_method VARCHAR(50),
    
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX cause_idx (cause_node),
    INDEX effect_idx (effect_node),
    INDEX strength_idx (causal_strength DESC),
    INDEX validated_idx (is_validated),
    
    CONSTRAINT fk_cause FOREIGN KEY (cause_node) 
        REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE,
    CONSTRAINT fk_effect FOREIGN KEY (effect_node) 
        REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'agi_reasoning', 'AetherTree reasoning and inference engine')
ON CONFLICT DO NOTHING;
