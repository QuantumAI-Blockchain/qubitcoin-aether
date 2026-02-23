-- ================================================================
-- MULTI-CHAIN BRIDGE — Transfer Tracking
-- Domain: bridge | Schema v1.0.0
-- ================================================================

SET DATABASE = qubitcoin;

CREATE TABLE IF NOT EXISTS bridge_transfers (
    transfer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_chain VARCHAR(50) NOT NULL,
    destination_chain VARCHAR(50) NOT NULL,
    source_tx_hash VARCHAR(255) NOT NULL,
    sender_address VARCHAR(255) NOT NULL,
    recipient_address VARCHAR(255) NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    bridge_fee DECIMAL(20, 8) NOT NULL,
    status VARCHAR(50) NOT NULL,
    initiated_timestamp TIMESTAMP NOT NULL DEFAULT now(),
    completed_timestamp TIMESTAMP,
    INDEX source_chain_idx (source_chain),
    INDEX dest_chain_idx (destination_chain),
    INDEX status_idx (status),
    INDEX sender_idx (sender_address),
    CONSTRAINT fk_source_chain FOREIGN KEY (source_chain) REFERENCES supported_chains(chain_id),
    CONSTRAINT fk_dest_chain FOREIGN KEY (destination_chain) REFERENCES supported_chains(chain_id)
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'bridge_transfers', 'Bridge transfer tracking')
ON CONFLICT DO NOTHING;
