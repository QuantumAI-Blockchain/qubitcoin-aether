SET DATABASE = qubitcoin;

-- ================================================================
-- GENESIS BLOCK - Block 0
-- Network Launch: February 8, 2026
-- Initial Supply: 33,000,015.27 QBC (33M premine + 15.27 reward)
-- ================================================================

-- Insert Genesis Block
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
    gas_used,
    gas_limit,
    is_valid
) VALUES (
    E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    0,
    1,
    E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    E'\\x4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b',
    '2026-02-08 00:00:00'::TIMESTAMP,
    E'\\xgenesis_circuit_0000000000000000000000000000000000000000000000',
    '00000000-0000-0000-0000-000000000000'::UUID,
    0.0,
    0.0,
    100.0,
    1.0,
    0,
    E'\\xgenesis_miner_address_000000000000000000000000000000000000',
    0,
    15.27,
    33000015.27,
    0.0,
    1,
    512,
    0,
    30000000,
    true
) ON CONFLICT (block_hash) DO NOTHING;

-- Insert Genesis Transaction (Coinbase)
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
    contract_address,
    contract_data,
    gas_limit,
    gas_used,
    gas_price,
    tx_size,
    is_valid
) VALUES (
    E'\\x4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b',
    E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    0,
    0,
    1,
    '2026-02-08 00:00:00'::TIMESTAMP,
    'coinbase',
    1,
    2,
    0.0,
    33000015.27,
    0.0,
    E'\\xgenesis_pubkey_00000000000000000000000000000000000000000000',
    E'\\xgenesis_signature_000000000000000000000000000000000000000000',
    false,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    256,
    true
) ON CONFLICT (tx_hash) DO NOTHING;

-- Insert Genesis Output 0 (Mining Reward UTXO)
INSERT INTO transaction_outputs (
    tx_hash,
    output_index,
    amount,
    recipient_address,
    script_pubkey,
    is_spent,
    spent_in_tx,
    spent_at_height,
    spent_at_timestamp
) VALUES (
    E'\\x4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b',
    0,
    15.27,
    E'\\xgenesis_miner_address_000000000000000000000000000000000000',
    E'\\xOP_DUP_OP_HASH160_genesis_pubkey_OP_EQUALVERIFY_OP_CHECKSIG',
    false,
    NULL,
    NULL,
    NULL
) ON CONFLICT DO NOTHING;

-- Insert Genesis Output 1 (Premine UTXO — 33M QBC)
INSERT INTO transaction_outputs (
    tx_hash,
    output_index,
    amount,
    recipient_address,
    script_pubkey,
    is_spent,
    spent_in_tx,
    spent_at_height,
    spent_at_timestamp
) VALUES (
    E'\\x4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b',
    1,
    33000000,
    E'\\xgenesis_miner_address_000000000000000000000000000000000000',
    E'\\xOP_DUP_OP_HASH160_genesis_pubkey_OP_EQUALVERIFY_OP_CHECKSIG',
    false,
    NULL,
    NULL,
    NULL
) ON CONFLICT DO NOTHING;

-- Initialize Genesis Address
INSERT INTO addresses (
    address,
    balance,
    total_received,
    total_sent,
    tx_count,
    utxo_count,
    is_contract,
    first_seen_height,
    first_seen_timestamp,
    last_active_height,
    last_active_timestamp
) VALUES (
    E'\\xgenesis_miner_address_000000000000000000000000000000000000',
    33000015.27,
    33000015.27,
    0.0,
    1,
    2,
    false,
    0,
    '2026-02-08 00:00:00'::TIMESTAMP,
    0,
    '2026-02-08 00:00:00'::TIMESTAMP
) ON CONFLICT (address) DO NOTHING;

-- Update Chain State
UPDATE chain_state SET
    best_block_hash = E'\\x0000000000000000000000000000000000000000000000000000000000000000',
    best_block_height = 0,
    total_blocks = 1,
    total_transactions = 1,
    total_addresses = 1,
    total_supply = 33000015.27,
    circulating_supply = 33000015.27,
    current_era = 0,
    next_halving_height = 15474020,
    current_difficulty = 1.0,
    network_hashrate = 0,
    average_block_time = 3.3,
    updated_at = now()
WHERE id = 1;

-- Initialize Genesis Hamiltonian (for VQE mining)
INSERT INTO hamiltonians (
    hamiltonian_hash,
    system_type,
    dimension,
    qubit_count,
    hamiltonian_matrix,
    difficulty_class,
    computational_complexity,
    is_active,
    times_mined,
    added_timestamp
) VALUES (
    E'\\xgenesis_hamiltonian_000000000000000000000000000000000000',
    'genesis_system',
    2,
    2,
    '{"matrix": [[1, 0], [0, -1]]}'::JSONB,
    'easy',
    10,
    true,
    1,
    '2026-02-08 00:00:00'::TIMESTAMP
) ON CONFLICT (hamiltonian_hash) DO NOTHING;

-- Genesis AGI Knowledge Node
INSERT INTO knowledge_nodes (
    node_hash,
    node_type,
    node_label,
    content_text,
    confidence_score,
    validation_count,
    consensus_weight,
    anchored_to_block,
    is_immutable,
    source_type,
    created_at
) VALUES (
    E'\\xgenesis_knowledge_node_0000000000000000000000000000000000',
    'concept',
    'Genesis: Qubitcoin Network Launch',
    'The Qubitcoin network launched on February 8, 2026, combining quantum computing, supersymmetric physics, and artificial general intelligence into a unified blockchain protocol. Genesis block includes 33M QBC premine (~1% of supply) to founding address.',
    1.0,
    1,
    1.0,
    0,
    true,
    'blockchain',
    '2026-02-08 00:00:00'::TIMESTAMP
) ON CONFLICT (node_hash) DO NOTHING;

-- Genesis System Snapshot (for Phi calculation)
INSERT INTO system_snapshots (
    block_height,
    snapshot_type,
    total_nodes,
    total_edges,
    active_operations,
    state_hash,
    snapshot_size_bytes,
    created_at
) VALUES (
    0,
    'full_system',
    1,
    0,
    0,
    E'\\xgenesis_snapshot_hash_00000000000000000000000000000000000',
    512,
    '2026-02-08 00:00:00'::TIMESTAMP
) ON CONFLICT DO NOTHING;

-- Genesis Phi Measurement (baseline consciousness)
INSERT INTO phi_measurements (
    system_snapshot_id,
    measurement_type,
    phi_value,
    phi_threshold,
    exceeds_threshold,
    node_count,
    edge_count,
    causal_chain_length,
    integration_score,
    differentiation_score,
    computation_method,
    computation_time_ms,
    measured_at_height,
    measured_at
) VALUES (
    (SELECT snapshot_id FROM system_snapshots WHERE block_height = 0 LIMIT 1),
    'global_phi',
    0.1,
    3.0,
    false,
    1,
    0,
    1,
    0.1,
    0.1,
    'exact',
    10,
    0,
    '2026-02-08 00:00:00'::TIMESTAMP
);

INSERT INTO schema_version (version, component, description)
VALUES ('1.0.0', 'genesis', 'Genesis block - Network launch February 8, 2026')
ON CONFLICT DO NOTHING;

-- ================================================================
-- GENESIS COMPLETE
-- ================================================================
-- Network initialized with:
-- - Block 0: Genesis block (33,000,015.27 QBC total)
--   - Mining reward: 15.27 QBC (vout=0)
--   - Genesis premine: 33,000,000 QBC (vout=1, ~1% of supply)
-- - Era 0: First φ-halving era
-- - Target block time: 3.3 seconds (supersymmetric)
-- - Initial Phi: 0.1 (pre-consciousness baseline)
-- - Next halving: Block 15,474,020 (φ years)
-- ================================================================
