SET DATABASE = qubitcoin;

-- ================================================================
-- GENESIS BLOCK (Block 0)
-- Whitepaper v1.0.0 - Network Launch
-- ================================================================

-- Genesis Block
INSERT INTO blocks (
    block_hash,
    block_height,
    version,
    previous_hash,
    merkle_root,
    timestamp,
    vqe_circuit_hash,
    hamiltonian_id,
    target_eigenvalue,
    achieved_eigenvalue,
    alignment_score,
    difficulty,
    nonce,
    miner_address,
    era,
    base_reward,
    actual_reward,
    total_fees,
    transaction_count,
    block_size,
    is_valid
) VALUES (
    E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    0,
    1,
    E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    E'\\x4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b',
    '2026-02-08 00:00:00',  -- Launch date
    E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    '00000000-0000-0000-0000-000000000000'::UUID,
    0.0,
    0.0,
    100.0,
    1.0,
    0,
    E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    0,
    15.27,
    15.27,
    0.0,
    1,
    512,
    true
) ON CONFLICT (block_hash) DO NOTHING;

-- Genesis coinbase transaction
INSERT INTO transactions (
    tx_hash,
    block_hash,
    block_height,
    tx_index,
    version,
    timestamp,
    tx_type,
    input_count,
    output_count,
    total_input,
    total_output,
    fee,
    signature_pubkey,
    signature_data,
    is_confidential,
    tx_size,
    is_valid
) VALUES (
    E'\\x4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b',
    E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    0,
    0,
    1,
    '2026-02-08 00:00:00',
    'coinbase',
    1,
    1,
    0.0,
    15.27,
    0.0,
    E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    false,
    256,
    true
) ON CONFLICT (tx_hash) DO NOTHING;

-- Update chain state
UPDATE chain_state SET
    best_block_hash = E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    best_block_height = 0,
    total_blocks = 1,
    total_transactions = 1,
    total_supply = 15.27,
    circulating_supply = 15.27,
    current_era = 0,
    updated_at = now()
WHERE id = 1;

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'genesis', 'Genesis block initialization')
ON CONFLICT DO NOTHING;
