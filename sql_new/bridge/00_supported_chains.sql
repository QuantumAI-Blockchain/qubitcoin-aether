-- ================================================================
-- MULTI-CHAIN BRIDGE — Supported Chains & Validators
-- Domain: bridge | Schema v1.0.0
-- ================================================================

SET DATABASE = qubitcoin;

CREATE TABLE IF NOT EXISTS supported_chains (
    chain_id VARCHAR(50) PRIMARY KEY,
    chain_name VARCHAR(100) NOT NULL UNIQUE,
    chain_type VARCHAR(50) NOT NULL,
    rpc_endpoint TEXT NOT NULL,
    bridge_contract_address VARCHAR(255),
    block_time_seconds INT NOT NULL,
    confirmation_blocks INT NOT NULL,
    base_fee DECIMAL(20, 8) NOT NULL,
    min_transfer_amount DECIMAL(20, 8) NOT NULL,
    max_transfer_amount DECIMAL(20, 8) NOT NULL,
    is_active BOOL NOT NULL DEFAULT true,
    total_transfers BIGINT NOT NULL DEFAULT 0,
    INDEX active_idx (is_active)
);

INSERT INTO supported_chains (chain_id, chain_name, chain_type, rpc_endpoint, block_time_seconds, confirmation_blocks, base_fee, min_transfer_amount, max_transfer_amount) VALUES
('ethereum', 'Ethereum', 'evm', 'https://eth-mainnet.g.alchemy.com/v2/', 12, 12, 0.001, 0.01, 10000.0),
('solana', 'Solana', 'solana', 'https://api.mainnet-beta.solana.com', 1, 32, 0.0001, 0.001, 10000.0),
('polygon', 'Polygon', 'evm', 'https://polygon-mainnet.g.alchemy.com/v2/', 2, 128, 0.0001, 0.01, 10000.0),
('bsc', 'Binance Smart Chain', 'evm', 'https://bsc-dataseed.binance.org/', 3, 15, 0.0002, 0.01, 10000.0),
('avalanche', 'Avalanche C-Chain', 'evm', 'https://api.avax.network/ext/bc/C/rpc', 2, 10, 0.0001, 0.01, 10000.0),
('arbitrum', 'Arbitrum One', 'evm', 'https://arb1.arbitrum.io/rpc', 1, 30, 0.00005, 0.01, 10000.0),
('optimism', 'Optimism', 'evm', 'https://mainnet.optimism.io', 2, 20, 0.00005, 0.01, 10000.0),
('base', 'Base', 'evm', 'https://mainnet.base.org', 2, 20, 0.00005, 0.01, 10000.0)
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS bridge_validators (
    validator_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    validator_address BYTES NOT NULL UNIQUE,
    validator_name VARCHAR(255),
    bonded_amount DECIMAL(20, 8) NOT NULL,
    is_active BOOL NOT NULL DEFAULT true,
    reputation_score DECIMAL(5, 2) NOT NULL DEFAULT 100.0,
    registered_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    INDEX active_idx (is_active)
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'bridge_chains', 'Supported chains and bridge validators')
ON CONFLICT DO NOTHING;
