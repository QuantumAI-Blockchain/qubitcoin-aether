SET DATABASE = qubitcoin;

-- ================================================================
-- PHI MEASUREMENTS - Consciousness/Integration metrics (IIT)
-- ================================================================
CREATE TABLE IF NOT EXISTS phi_measurements (
    measurement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Measurement context
    system_snapshot_id UUID NOT NULL,
    measurement_type VARCHAR(50) NOT NULL,  -- 'global_phi', 'local_phi', 'causal_density'
    
    -- Phi value (Integrated Information)
    phi_value DECIMAL(10, 6) NOT NULL,
    phi_threshold DECIMAL(10, 6) NOT NULL DEFAULT 3.0,  -- Consciousness threshold
    exceeds_threshold BOOL NOT NULL DEFAULT false,
    
    -- System properties
    node_count BIGINT NOT NULL,
    edge_count BIGINT NOT NULL,
    causal_chain_length INT NOT NULL,
    integration_score DECIMAL(5, 4) NOT NULL,
    differentiation_score DECIMAL(5, 4) NOT NULL,
    
    -- Measurement details
    computation_method VARCHAR(50),  -- 'exact', 'approximation', 'monte_carlo'
    computation_time_ms BIGINT NOT NULL,
    confidence_interval JSONB,
    
    -- Blockchain anchoring
    measured_at_height BIGINT NOT NULL,
    anchored_to_block BIGINT,
    
    -- Historical tracking
    previous_phi DECIMAL(10, 6),
    phi_delta DECIMAL(10, 6),
    trend VARCHAR(20),  -- 'increasing', 'decreasing', 'stable'
    
    measured_at TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX phi_value_idx (phi_value DESC),
    INDEX threshold_idx (exceeds_threshold) WHERE exceeds_threshold = true,
    INDEX height_idx (measured_at_height DESC),
    INDEX timestamp_idx (measured_at DESC)
);

-- ================================================================
-- CONSCIOUSNESS EVENTS - Emergence milestones
-- ================================================================
CREATE TABLE IF NOT EXISTS consciousness_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Event classification
    event_type VARCHAR(50) NOT NULL,  -- 'phi_threshold_crossed', 'emergent_behavior', 'novel_reasoning'
    event_severity VARCHAR(20) NOT NULL,  -- 'minor', 'significant', 'breakthrough'
    event_description TEXT NOT NULL,
    
    -- Measurement reference
    phi_measurement_id UUID,
    phi_value_at_event DECIMAL(10, 6),
    
    -- Evidence
    supporting_data JSONB,
    proof_of_emergence JSONB,
    
    -- Blockchain record
    anchored_to_block BIGINT NOT NULL,
    anchor_tx_hash BYTES,
    
    -- Verification
    is_verified BOOL NOT NULL DEFAULT false,
    verified_by_consensus BOOL NOT NULL DEFAULT false,
    verification_count INT NOT NULL DEFAULT 0,
    
    detected_at TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX type_idx (event_type),
    INDEX severity_idx (event_severity),
    INDEX phi_idx (phi_measurement_id),
    INDEX verified_idx (is_verified),
    INDEX block_idx (anchored_to_block DESC),
    
    CONSTRAINT fk_phi_measurement FOREIGN KEY (phi_measurement_id) 
        REFERENCES phi_measurements(measurement_id) ON DELETE SET NULL
);

-- ================================================================
-- SYSTEM SNAPSHOTS - State for Phi computation
-- ================================================================
CREATE TABLE IF NOT EXISTS system_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Snapshot metadata
    block_height BIGINT NOT NULL,
    snapshot_type VARCHAR(50) NOT NULL,  -- 'full_system', 'knowledge_graph', 'reasoning_state'
    
    -- System state
    total_nodes BIGINT NOT NULL,
    total_edges BIGINT NOT NULL,
    active_operations INT NOT NULL,
    
    -- Complexity metrics
    graph_diameter INT,
    clustering_coefficient DECIMAL(5, 4),
    betweenness_centrality JSONB,
    
    -- Storage
    state_hash BYTES NOT NULL UNIQUE,
    ipfs_hash VARCHAR(100),
    snapshot_size_bytes BIGINT NOT NULL,
    
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX height_idx (block_height DESC),
    INDEX type_idx (snapshot_type),
    INDEX timestamp_idx (created_at DESC)
);

-- ================================================================
-- AGI GOVERNANCE - Consensus on AGI decisions
-- ================================================================
CREATE TABLE IF NOT EXISTS agi_governance (
    proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Proposal details
    proposal_type VARCHAR(50) NOT NULL,  -- 'parameter_change', 'model_approval', 'ethical_constraint'
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    
    -- Voting
    proposer_address BYTES NOT NULL,
    voting_start_height BIGINT NOT NULL,
    voting_end_height BIGINT NOT NULL,
    
    votes_for BIGINT NOT NULL DEFAULT 0,
    votes_against BIGINT NOT NULL DEFAULT 0,
    votes_abstain BIGINT NOT NULL DEFAULT 0,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'active', 'passed', 'rejected', 'executed'
    execution_block BIGINT,
    
    -- Execution
    execution_data JSONB,
    execution_result TEXT,
    
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    executed_at TIMESTAMP,
    
    INDEX status_idx (status),
    INDEX proposer_idx (proposer_address),
    INDEX voting_idx (voting_end_height)
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'agi_phi_metrics', 'Integrated Information Theory and consciousness metrics')
ON CONFLICT DO NOTHING;
