SET DATABASE = qubitcoin;

-- ================================================================
-- GENESIS BLOCK - Block 0
-- Network Launch: February 8, 2026
-- Initial Supply: 33,000,015.27 QBC (33M premine + 15.27 reward)
--
-- Aligned with SQLAlchemy BlockModel / TransactionModel
-- ================================================================

-- Insert Genesis Block
INSERT INTO blocks (
    height,
    prev_hash,
    difficulty,
    proof_json,
    created_at,
    block_hash,
    state_root,
    receipts_root,
    thought_proof
) VALUES (
    0,
    '0000000000000000000000000000000000000000000000000000000000000000',
    1.0,
    '{"type": "genesis", "vqe_params": [], "energy": 0.0, "hamiltonian": "genesis"}'::JSONB,
    1707350400.0,
    '0000000000000000000000000000000000000000000000000000000000000000',
    '',
    '',
    NULL
) ON CONFLICT (height) DO NOTHING;

-- Insert Genesis Transaction (Coinbase)
INSERT INTO transactions (
    txid,
    inputs,
    outputs,
    fee,
    signature,
    public_key,
    timestamp,
    block_height,
    status,
    tx_type,
    to_address,
    data,
    gas_limit,
    gas_price,
    nonce
) VALUES (
    '4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b',
    '[]'::JSONB,
    '[{"address": "genesis_miner", "amount": "33000015.27"}]'::JSONB,
    0,
    'genesis',
    'genesis',
    1707350400.0,
    0,
    'confirmed',
    'coinbase',
    NULL,
    NULL,
    0,
    0,
    0
) ON CONFLICT (txid) DO NOTHING;

-- Insert Genesis UTXOs
-- Mining reward UTXO (15.27 QBC)
INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
VALUES (
    '4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b',
    0,
    15.27,
    'genesis_miner',
    '{"type": "genesis"}'::JSONB,
    0,
    false
) ON CONFLICT (txid, vout) DO NOTHING;

-- Premine UTXO (33M QBC)
INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
VALUES (
    '4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b',
    1,
    33000000,
    'genesis_miner',
    '{"type": "genesis"}'::JSONB,
    0,
    false
) ON CONFLICT (txid, vout) DO NOTHING;

-- Initialize supply tracker
INSERT INTO supply (id, total_minted)
VALUES (1, 33000015.27)
ON CONFLICT (id) DO UPDATE SET total_minted = 33000015.27;

INSERT INTO schema_version (version, component, description)
VALUES ('2.0.0', 'genesis', 'Genesis block — aligned with SQLAlchemy ORM schema')
ON CONFLICT DO NOTHING;

-- ================================================================
-- GENESIS COMPLETE
-- ================================================================
-- Network initialized with:
-- - Block 0: Genesis block (33,000,015.27 QBC total)
--   - Mining reward: 15.27 QBC (vout=0)
--   - Genesis premine: 33,000,000 QBC (vout=1, ~1% of supply)
-- - Era 0: First phi-halving era
-- - Target block time: 3.3 seconds (supersymmetric)
-- - Next halving: Block 15,474,020 (phi years)
-- ================================================================
