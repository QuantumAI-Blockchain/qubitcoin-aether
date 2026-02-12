SET DATABASE = qubitcoin;

-- ================================================================
-- VQE CIRCUITS - Variational quantum circuits
-- ================================================================
CREATE TABLE IF NOT EXISTS vqe_circuits (
    circuit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circuit_hash BYTES NOT NULL UNIQUE,
    hamiltonian_id UUID NOT NULL,
    
    -- Circuit properties
    qubit_count INT NOT NULL,
    circuit_depth INT NOT NULL,
    gate_count INT NOT NULL,
    ansatz_type VARCHAR(50) NOT NULL,  -- 'hardware_efficient', 'uccsd', 'custom'
    
    -- Circuit definition
    circuit_definition JSONB NOT NULL,  -- Gates, parameters, topology
    optimized_parameters JSONB,
    
    -- Performance
    achieved_energy DECIMAL(20, 10),
    convergence_iterations INT,
    execution_time_ms BIGINT,
    
    -- Block reference
    block_hash BYTES,
    block_height BIGINT,
    miner_address BYTES,
    
    -- IPFS storage
    ipfs_hash VARCHAR(100),
    
    created_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX hamiltonian_idx (hamiltonian_id),
    INDEX block_idx (block_hash),
    INDEX ansatz_idx (ansatz_type),
    INDEX energy_idx (achieved_energy),
    
    CONSTRAINT fk_hamiltonian FOREIGN KEY (hamiltonian_id) 
        REFERENCES hamiltonians(hamiltonian_id) ON DELETE CASCADE
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'research_circuits', 'VQE circuit solutions')
ON CONFLICT DO NOTHING;
