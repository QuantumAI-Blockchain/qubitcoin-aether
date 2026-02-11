SET DATABASE = qubitcoin;

-- ================================================================
-- TRAINING DATASETS - ML training data on-chain
-- ================================================================
CREATE TABLE IF NOT EXISTS training_datasets (
    dataset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Dataset metadata
    dataset_name VARCHAR(255) NOT NULL,
    dataset_type VARCHAR(50) NOT NULL,  -- 'supervised', 'unsupervised', 'reinforcement', 'multimodal'
    dataset_category VARCHAR(50),  -- 'blockchain', 'quantum', 'reasoning', 'language'
    
    -- Size & structure
    sample_count BIGINT NOT NULL,
    feature_count INT NOT NULL,
    data_format VARCHAR(50) NOT NULL,  -- 'json', 'csv', 'parquet', 'tensor'
    
    -- Storage
    ipfs_hash VARCHAR(100) NOT NULL,
    ipfs_size_bytes BIGINT NOT NULL,
    merkle_root BYTES NOT NULL,
    
    -- Quality metrics
    quality_score DECIMAL(5, 4),
    validation_accuracy DECIMAL(5, 4),
    is_verified BOOL NOT NULL DEFAULT false,
    
    -- Access control
    is_public BOOL NOT NULL DEFAULT true,
    access_cost DECIMAL(20, 8) NOT NULL DEFAULT 0,
    usage_count BIGINT NOT NULL DEFAULT 0,
    
    -- Provenance
    created_by_address BYTES NOT NULL,
    anchored_to_block BIGINT,
    
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX type_idx (dataset_type),
    INDEX category_idx (dataset_category),
    INDEX ipfs_idx (ipfs_hash),
    INDEX public_idx (is_public) WHERE is_public = true,
    INDEX quality_idx (quality_score DESC)
);

-- ================================================================
-- MODEL REGISTRY - Trained AI models
-- ================================================================
CREATE TABLE IF NOT EXISTS model_registry (
    model_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Model metadata
    model_name VARCHAR(255) NOT NULL,
    model_type VARCHAR(50) NOT NULL,  -- 'neural_network', 'transformer', 'bayesian', 'quantum_ml'
    model_architecture VARCHAR(100),
    
    -- Training info
    trained_on_dataset UUID,
    training_epochs INT,
    training_duration_seconds BIGINT,
    
    -- Model storage
    ipfs_model_hash VARCHAR(100) NOT NULL,
    ipfs_weights_hash VARCHAR(100) NOT NULL,
    model_size_bytes BIGINT NOT NULL,
    
    -- Performance metrics
    accuracy DECIMAL(5, 4),
    precision_score DECIMAL(5, 4),
    recall_score DECIMAL(5, 4),
    f1_score DECIMAL(5, 4),
    inference_time_ms BIGINT,
    
    -- Versioning
    version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    parent_model_id UUID,
    
    -- Status
    is_active BOOL NOT NULL DEFAULT true,
    is_verified BOOL NOT NULL DEFAULT false,
    deployment_count BIGINT NOT NULL DEFAULT 0,
    
    -- Ownership
    owner_address BYTES NOT NULL,
    anchored_to_block BIGINT,
    
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX type_idx (model_type),
    INDEX dataset_idx (trained_on_dataset),
    INDEX active_idx (is_active) WHERE is_active = true,
    INDEX accuracy_idx (accuracy DESC),
    INDEX version_idx (version),
    
    CONSTRAINT fk_dataset FOREIGN KEY (trained_on_dataset) 
        REFERENCES training_datasets(dataset_id) ON DELETE SET NULL,
    CONSTRAINT fk_parent_model FOREIGN KEY (parent_model_id) 
        REFERENCES model_registry(model_id) ON DELETE SET NULL
);

-- ================================================================
-- MODEL PREDICTIONS - Inference results on-chain
-- ================================================================
CREATE TABLE IF NOT EXISTS model_predictions (
    prediction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Model reference
    model_id UUID NOT NULL,
    
    -- Input
    input_data JSONB NOT NULL,
    input_hash BYTES NOT NULL,
    
    -- Output
    prediction_result JSONB NOT NULL,
    confidence_score DECIMAL(5, 4) NOT NULL,
    
    -- Execution
    inference_time_ms BIGINT NOT NULL,
    gas_used BIGINT,
    
    -- Validation
    ground_truth JSONB,
    is_correct BOOL,
    
    -- Blockchain
    triggered_by_tx BYTES,
    anchored_to_block BIGINT,
    
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX model_idx (model_id),
    INDEX confidence_idx (confidence_score DESC),
    INDEX block_idx (anchored_to_block),
    
    CONSTRAINT fk_model FOREIGN KEY (model_id) 
        REFERENCES model_registry(model_id) ON DELETE CASCADE
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'agi_training', 'Training datasets and model registry')
ON CONFLICT DO NOTHING;
