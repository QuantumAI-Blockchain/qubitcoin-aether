-- L1 ↔ L2 Internal Bridge Log
-- Tracks deposits (L1 UTXO → L2 QVM account) and withdrawals (L2 → L1)

CREATE TABLE IF NOT EXISTS l1l2_bridge_log (
    id              SERIAL PRIMARY KEY,
    txid            VARCHAR(64) NOT NULL UNIQUE,
    direction       VARCHAR(10) NOT NULL CHECK (direction IN ('deposit', 'withdraw')),
    l1_address      VARCHAR(64) NOT NULL,
    l2_address      VARCHAR(64) NOT NULL,
    amount          DECIMAL(30, 8) NOT NULL CHECK (amount > 0),
    status          VARCHAR(20) NOT NULL DEFAULT 'confirmed',
    block_height    BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_l1l2_bridge_l1 ON l1l2_bridge_log (l1_address);
CREATE INDEX IF NOT EXISTS idx_l1l2_bridge_l2 ON l1l2_bridge_log (l2_address);
CREATE INDEX IF NOT EXISTS idx_l1l2_bridge_dir ON l1l2_bridge_log (direction);
CREATE INDEX IF NOT EXISTS idx_l1l2_bridge_created ON l1l2_bridge_log (created_at DESC);
