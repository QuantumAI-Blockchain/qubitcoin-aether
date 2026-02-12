SET DATABASE = qubitcoin;

-- ================================================================
-- HAMILTONIANS - Quantum systems for VQE mining
-- ================================================================
CREATE TABLE IF NOT EXISTS hamiltonians (
    hamiltonian_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hamiltonian_hash BYTES NOT NULL UNIQUE,
    
    -- System properties
    system_type VARCHAR(50) NOT NULL,  -- 'heisenberg', 'ising', 'hubbard', 'fermi_hubbard'
    dimension INT NOT NULL,
    qubit_count INT NOT NULL,
    
    -- Hamiltonian definition
    hamiltonian_matrix JSONB NOT NULL,
    expected_ground_energy DECIMAL(20, 10),
    
    -- Difficulty classification
    difficulty_class VARCHAR(20) NOT NULL,  -- 'easy', 'medium', 'hard', 'research'
    computational_complexity INT NOT NULL,  -- Estimated gate count
    
    -- Mining stats
    is_active BOOL NOT NULL DEFAULT true,
    times_mined BIGINT NOT NULL DEFAULT 0,
    best_solution_energy DECIMAL(20, 10),
    best_solution_miner BYTES,
    
    -- IPFS storage
    ipfs_hash VARCHAR(100),
    ipfs_metadata_hash VARCHAR(100),
    
    -- Timestamps
    added_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    last_mined_timestamp TIMESTAMP,
    
    INDEX system_type_idx (system_type),
    INDEX active_idx (is_active),
    INDEX difficulty_idx (difficulty_class),
    INDEX qubit_count_idx (qubit_count)
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'research_hamiltonians', 'Quantum Hamiltonians for VQE mining')
ON CONFLICT DO NOTHING;
