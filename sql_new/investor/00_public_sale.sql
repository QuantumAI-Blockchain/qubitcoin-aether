-- ============================================================================
-- INVESTOR PUBLIC SALE SCHEMA
-- Tables for tracking seed round investments, vesting, and revenue sharing.
-- ============================================================================

-- Round configuration (supports multiple rounds)
CREATE TABLE IF NOT EXISTS investor_rounds (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR(50) NOT NULL,
    token_price    NUMERIC(78,18) NOT NULL,
    hard_cap       NUMERIC(78,18) NOT NULL,
    total_raised   NUMERIC(78,18) NOT NULL DEFAULT 0,
    total_investors INT NOT NULL DEFAULT 0,
    start_time     TIMESTAMPTZ NOT NULL,
    end_time       TIMESTAMPTZ NOT NULL,
    active         BOOLEAN NOT NULL DEFAULT false,
    contract_address VARCHAR(42),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Individual investments (synced from Ethereum events)
CREATE TABLE IF NOT EXISTS investor_investments (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    round_id       INT REFERENCES investor_rounds(id),
    eth_address    VARCHAR(42) NOT NULL,
    qbc_address    VARCHAR(40) NOT NULL,
    token_address  VARCHAR(42),
    token_symbol   VARCHAR(10) NOT NULL,
    amount_raw     NUMERIC(78,18) NOT NULL,
    usd_value      NUMERIC(78,18) NOT NULL,
    qbc_allocated  NUMERIC(78,18) NOT NULL,
    eth_tx_hash    VARCHAR(66) NOT NULL UNIQUE,
    eth_block      BIGINT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_investments_eth ON investor_investments(eth_address);
CREATE INDEX IF NOT EXISTS idx_investments_qbc ON investor_investments(qbc_address);
CREATE INDEX IF NOT EXISTS idx_investments_round ON investor_investments(round_id);

-- Vesting claim records (from QBC chain)
CREATE TABLE IF NOT EXISTS investor_vesting_claims (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    qbc_address     VARCHAR(40) NOT NULL,
    qbc_claimed     NUMERIC(78,18) NOT NULL,
    qusd_claimed    NUMERIC(78,18) NOT NULL,
    vested_fraction NUMERIC(20,18) NOT NULL,
    tx_hash         VARCHAR(66),
    block_height    BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_vesting_qbc ON investor_vesting_claims(qbc_address);

-- Revenue share claims
CREATE TABLE IF NOT EXISTS investor_revenue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    qbc_address     VARCHAR(40) NOT NULL,
    amount          NUMERIC(78,18) NOT NULL,
    acc_per_share   NUMERIC(78,18) NOT NULL,
    tx_hash         VARCHAR(66),
    block_height    BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_revenue_qbc ON investor_revenue(qbc_address);
