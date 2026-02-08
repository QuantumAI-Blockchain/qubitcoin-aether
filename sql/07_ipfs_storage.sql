SET DATABASE = qubitcoin;

CREATE TABLE IF NOT EXISTS blockchain_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    block_height BIGINT NOT NULL,
    block_hash BYTES NOT NULL,
    ipfs_hash VARCHAR(100) NOT NULL UNIQUE,
    ipfs_size_bytes BIGINT NOT NULL,
    snapshot_type VARCHAR(50) NOT NULL,
    compression VARCHAR(20) NOT NULL DEFAULT 'zstd',
    merkle_root BYTES NOT NULL,
    is_pinned BOOL NOT NULL DEFAULT false,
    is_public BOOL NOT NULL DEFAULT true,
    created_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    INDEX block_height_idx (block_height DESC),
    INDEX ipfs_hash_idx (ipfs_hash)
);

CREATE TABLE IF NOT EXISTS ipfs_pins (
    pin_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ipfs_hash VARCHAR(100) NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    node_id VARCHAR(100) NOT NULL,
    pin_status VARCHAR(20) NOT NULL,
    priority INT NOT NULL DEFAULT 5,
    pin_timestamp TIMESTAMP,
    INDEX ipfs_hash_idx (ipfs_hash),
    INDEX content_type_idx (content_type),
    INDEX status_idx (pin_status)
);

CREATE TABLE IF NOT EXISTS ipfs_content_registry (
    content_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ipfs_hash VARCHAR(100) NOT NULL UNIQUE,
    content_type VARCHAR(50) NOT NULL,
    content_category VARCHAR(50),
    file_name VARCHAR(255),
    size_bytes BIGINT NOT NULL,
    is_public BOOL NOT NULL DEFAULT true,
    download_count BIGINT NOT NULL DEFAULT 0,
    created_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    INDEX ipfs_hash_idx (ipfs_hash),
    INDEX content_type_idx (content_type)
);

CREATE TABLE IF NOT EXISTS ipfs_gateways (
    gateway_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gateway_name VARCHAR(255) NOT NULL,
    gateway_url TEXT NOT NULL,
    gateway_type VARCHAR(50) NOT NULL,
    provider VARCHAR(100),
    is_active BOOL NOT NULL DEFAULT true,
    is_default BOOL NOT NULL DEFAULT false,
    INDEX active_idx (is_active)
);

INSERT INTO ipfs_gateways (gateway_name, gateway_url, gateway_type, provider, is_default) VALUES
('IPFS.io Public', 'https://ipfs.io/ipfs/', 'public', 'ipfs.io', true),
('Cloudflare IPFS', 'https://cloudflare-ipfs.com/ipfs/', 'public', 'cloudflare', false),
('Qubitcoin Local', 'http://localhost:8083/ipfs/', 'private', 'self-hosted', false)
ON CONFLICT DO NOTHING;

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'ipfs_storage', 'IPFS storage management');
