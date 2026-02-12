SET DATABASE = qubitcoin;

-- ================================================================
-- CONTRACT STORAGE - Key-value storage for contracts
-- ================================================================
CREATE TABLE IF NOT EXISTS contract_storage (
    storage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_address BYTES NOT NULL,
    storage_key BYTES NOT NULL,
    storage_value BYTES NOT NULL,
    
    -- Metadata
    value_type VARCHAR(50),  -- 'uint256', 'address', 'bytes32', 'string', 'mapping'
    last_modified_height BIGINT NOT NULL,
    last_modified_tx BYTES NOT NULL,
    last_modified_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    
    UNIQUE INDEX contract_key_idx (contract_address, storage_key),
    INDEX contract_idx (contract_address),
    INDEX modified_height_idx (last_modified_height DESC)
);

-- ================================================================
-- CONTRACT STATE SNAPSHOTS - Periodic state checkpoints
-- ================================================================
CREATE TABLE IF NOT EXISTS contract_state_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_address BYTES NOT NULL,
    
    -- Snapshot metadata
    block_height BIGINT NOT NULL,
    block_hash BYTES NOT NULL,
    
    -- State data
    storage_root BYTES NOT NULL,  -- Merkle root of storage
    state_data JSONB NOT NULL,    -- Full state snapshot
    storage_size BIGINT NOT NULL,
    
    -- IPFS
    ipfs_hash VARCHAR(100),
    
    created_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX contract_idx (contract_address),
    INDEX height_idx (block_height DESC),
    
    CONSTRAINT fk_contract FOREIGN KEY (contract_address) 
        REFERENCES smart_contracts(contract_address) ON DELETE CASCADE
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'qvm_storage', 'Contract state storage and snapshots')
ON CONFLICT DO NOTHING;
