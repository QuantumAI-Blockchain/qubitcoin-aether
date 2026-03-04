-- High-Security Account Policies Schema
-- Opt-in spending limits, whitelists, and time-locks for accounts

CREATE TABLE IF NOT EXISTS security_policies (
    address TEXT PRIMARY KEY,
    daily_limit_qbc DOUBLE PRECISION NOT NULL DEFAULT 0,  -- 0 = no limit
    require_whitelist BOOLEAN DEFAULT false,
    whitelist TEXT[] DEFAULT '{}',
    time_lock_blocks INT DEFAULT 0,  -- delay on large transfers
    time_lock_threshold_qbc DOUBLE PRECISION DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    active BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_security_policies_active ON security_policies (active);

CREATE TABLE IF NOT EXISTS security_spending_log (
    id TEXT PRIMARY KEY,
    address TEXT NOT NULL,
    amount_qbc DOUBLE PRECISION NOT NULL,
    recipient TEXT NOT NULL,
    block_height BIGINT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_security_spending_address ON security_spending_log (address);
CREATE INDEX IF NOT EXISTS idx_security_spending_block ON security_spending_log (block_height);
