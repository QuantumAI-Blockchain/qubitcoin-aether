SET DATABASE = qubitcoin;

-- ================================================================
-- SUSY SOLUTIONS - Supersymmetric alignment solutions
-- ================================================================
CREATE TABLE IF NOT EXISTS susy_solutions (
    solution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Problem reference
    hamiltonian_id UUID NOT NULL,
    circuit_id UUID NOT NULL,
    
    -- Block reference
    block_hash BYTES NOT NULL,
    block_height BIGINT NOT NULL,
    miner_address BYTES NOT NULL,
    
    -- Solution quality
    ground_state_energy DECIMAL(20, 10) NOT NULL,
    alignment_score DECIMAL(10, 6) NOT NULL,  -- SUSY alignment (0-100)
    energy_gap DECIMAL(20, 10),
    fidelity DECIMAL(10, 6),
    
    -- Verification
    is_verified BOOL NOT NULL DEFAULT false,
    verification_method VARCHAR(50),
    verified_by_peers INT DEFAULT 0,
    
    -- Research value
    novelty_score DECIMAL(10, 6),  -- How novel is this solution?
    scientific_value VARCHAR(20),  -- 'low', 'medium', 'high', 'breakthrough'
    
    -- IPFS storage
    ipfs_hash VARCHAR(100),
    ipfs_analysis_hash VARCHAR(100),
    
    discovered_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    verified_timestamp TIMESTAMP,
    
    INDEX hamiltonian_idx (hamiltonian_id),
    INDEX circuit_idx (circuit_id),
    INDEX block_idx (block_hash),
    INDEX miner_idx (miner_address),
    INDEX verified_idx (is_verified),
    INDEX alignment_idx (alignment_score DESC),
    INDEX scientific_value_idx (scientific_value),
    
    CONSTRAINT fk_hamiltonian FOREIGN KEY (hamiltonian_id) 
        REFERENCES hamiltonians(hamiltonian_id) ON DELETE CASCADE,
    CONSTRAINT fk_circuit FOREIGN KEY (circuit_id) 
        REFERENCES vqe_circuits(circuit_id) ON DELETE CASCADE
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'research_susy', 'SUSY alignment solutions and research data')
ON CONFLICT DO NOTHING;
