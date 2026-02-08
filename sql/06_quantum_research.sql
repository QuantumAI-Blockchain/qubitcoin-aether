SET DATABASE = qubitcoin;

CREATE TABLE IF NOT EXISTS hamiltonians (
    hamiltonian_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hamiltonian_hash BYTES NOT NULL UNIQUE,
    system_type VARCHAR(50) NOT NULL,
    dimension INT NOT NULL,
    qubit_count INT NOT NULL,
    hamiltonian_matrix JSONB NOT NULL,
    difficulty_class VARCHAR(20) NOT NULL,
    is_active BOOL NOT NULL DEFAULT true,
    times_mined BIGINT NOT NULL DEFAULT 0,
    ipfs_hash VARCHAR(100),
    ipfs_metadata_hash VARCHAR(100),
    added_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    INDEX system_type_idx (system_type),
    INDEX active_idx (is_active)
);

CREATE TABLE IF NOT EXISTS vqe_circuits (
    circuit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circuit_hash BYTES NOT NULL UNIQUE,
    hamiltonian_id UUID NOT NULL,
    qubit_count INT NOT NULL,
    circuit_depth INT NOT NULL,
    ansatz_type VARCHAR(50) NOT NULL,
    circuit_definition JSONB NOT NULL,
    achieved_energy DECIMAL(20, 10),
    block_hash BYTES,
    ipfs_hash VARCHAR(100),
    created_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    INDEX hamiltonian_idx (hamiltonian_id),
    CONSTRAINT fk_hamiltonian FOREIGN KEY (hamiltonian_id) REFERENCES hamiltonians(hamiltonian_id)
);

CREATE TABLE IF NOT EXISTS susy_solutions (
    solution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hamiltonian_id UUID NOT NULL,
    circuit_id UUID NOT NULL,
    block_hash BYTES NOT NULL,
    miner_address BYTES NOT NULL,
    ground_state_energy DECIMAL(20, 10) NOT NULL,
    alignment_score DECIMAL(10, 6) NOT NULL,
    is_verified BOOL NOT NULL DEFAULT false,
    ipfs_hash VARCHAR(100),
    discovered_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    INDEX hamiltonian_idx (hamiltonian_id),
    INDEX verified_idx (is_verified),
    CONSTRAINT fk_hamiltonian FOREIGN KEY (hamiltonian_id) REFERENCES hamiltonians(hamiltonian_id),
    CONSTRAINT fk_circuit FOREIGN KEY (circuit_id) REFERENCES vqe_circuits(circuit_id)
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'quantum_research', 'Quantum research');
