SET DATABASE = qubitcoin;

-- ================================================================
-- BLOCKCHAIN SNAPSHOTS - Full chain snapshots
-- ================================================================
CREATE TABLE IF NOT EXISTS blockchain_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Snapshot metadata
    block_height BIGINT NOT NULL,
    block_hash BYTES NOT NULL,
    snapshot_type VARCHAR(50) NOT NULL,  -- 'full', 'pruned', 'archive', 'state_only'
    
    -- Storage
    ipfs_hash VARCHAR(100) NOT NULL UNIQUE,
    ipfs_size_bytes BIGINT NOT NULL,
    compression VARCHAR(20) NOT NULL DEFAULT 'zstd',
    merkle_root BYTES NOT NULL,
    
    -- Pinning
    is_pinned BOOL NOT NULL DEFAULT false,
    pin_count INT NOT NULL DEFAULT 0,
    
    -- Access
    is_public BOOL NOT NULL DEFAULT true,
    download_count BIGINT NOT NULL DEFAULT 0,
    
    created_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX block_height_idx (block_height DESC),
    INDEX ipfs_hash_idx (ipfs_hash),
    INDEX type_idx (snapshot_type),
    INDEX pinned_idx (is_pinned) WHERE is_pinned = true
);

-- ================================================================
-- IPFS CONTENT REGISTRY - All IPFS content tracking
-- ================================================================
CREATE TABLE IF NOT EXISTS ipfs_content_registry (
    content_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Content identification
    ipfs_hash VARCHAR(100) NOT NULL UNIQUE,
    content_type VARCHAR(50) NOT NULL,  -- 'block', 'transaction', 'contract', 'model', 'dataset', 'snapshot'
    content_category VARCHAR(50),
    
    -- File info
    file_name VARCHAR(255),
    mime_type VARCHAR(100),
    size_bytes BIGINT NOT NULL,
    
    -- Access control
    is_public BOOL NOT NULL DEFAULT true,
    owner_address BYTES,
    access_cost DECIMAL(20, 8) NOT NULL DEFAULT 0,
    
    -- Usage tracking
    download_count BIGINT NOT NULL DEFAULT 0,
    last_accessed TIMESTAMP,
    
    created_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    
    INDEX ipfs_hash_idx (ipfs_hash),
    INDEX content_type_idx (content_type),
    INDEX category_idx (content_category),
    INDEX public_idx (is_public) WHERE is_public = true
);

-- ================================================================
-- IPFS PINS - Pinning service tracking
-- ================================================================
CREATE TABLE IF NOT EXISTS ipfs_pins (
    pin_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Content reference
    ipfs_hash VARCHAR(100) NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    
    -- Pinning service
    pin_service VARCHAR(50) NOT NULL,  -- 'local', 'pinata', 'web3storage', 'fleek'
    service_pin_id VARCHAR(255),
    
    -- Status
    pin_status VARCHAR(20) NOT NULL,  -- 'pinning', 'pinned', 'failed', 'unpinned'
    priority INT NOT NULL DEFAULT 5,  -- 1-10, higher = more important
    
    -- Timestamps
    pin_requested_at TIMESTAMP NOT NULL DEFAULT now(),
    pinned_at TIMESTAMP,
    expires_at TIMESTAMP,
    
    INDEX ipfs_hash_idx (ipfs_hash),
    INDEX status_idx (pin_status),
    INDEX service_idx (pin_service),
    INDEX priority_idx (priority DESC)
);

-- ================================================================
-- IPFS GATEWAYS - Gateway management
-- ================================================================
CREATE TABLE IF NOT EXISTS ipfs_gateways (
    gateway_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    gateway_name VARCHAR(255) NOT NULL,
    gateway_url TEXT NOT NULL,
    gateway_type VARCHAR(50) NOT NULL,  -- 'public', 'private', 'dedicated'
    provider VARCHAR(100),
    
    -- Status
    is_active BOOL NOT NULL DEFAULT true,
    is_default BOOL NOT NULL DEFAULT false,
    health_status VARCHAR(20) DEFAULT 'unknown',  -- 'healthy', 'degraded', 'down', 'unknown'
    
    -- Performance
    average_response_ms BIGINT,
    uptime_percent DECIMAL(5, 2),
    last_health_check TIMESTAMP,
    
    INDEX active_idx (is_active) WHERE is_active = true,
    INDEX default_idx (is_default) WHERE is_default = true,
    INDEX health_idx (health_status)
);

-- Initialize default gateways
INSERT INTO ipfs_gateways (gateway_name, gateway_url, gateway_type, provider, is_default, is_active) VALUES
('IPFS.io Public', 'https://ipfs.io/ipfs/', 'public', 'ipfs.io', true, true),
('Cloudflare IPFS', 'https://cloudflare-ipfs.com/ipfs/', 'public', 'cloudflare', false, true),
('Pinata Dedicated', 'https://gateway.pinata.cloud/ipfs/', 'dedicated', 'pinata', false, true),
('Qubitcoin Local', 'http://localhost:8080/ipfs/', 'private', 'self-hosted', false, true)
ON CONFLICT DO NOTHING;

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'shared_ipfs', 'IPFS storage and content management')
ON CONFLICT DO NOTHING;
