-- Transaction Reversibility Schema
-- Opt-in reversal windows with guardian approval

CREATE TABLE IF NOT EXISTS reversal_requests (
    request_id TEXT PRIMARY KEY,
    txid TEXT NOT NULL,
    requester TEXT NOT NULL,
    reason TEXT NOT NULL,
    window_expires_block BIGINT NOT NULL,
    guardian_approvals TEXT[] DEFAULT '{}',
    status TEXT DEFAULT 'pending',  -- pending, approved, executed, expired, rejected
    created_at TIMESTAMPTZ DEFAULT now(),
    executed_at TIMESTAMPTZ,
    reversal_txid TEXT
);

CREATE INDEX IF NOT EXISTS idx_reversal_requests_txid ON reversal_requests (txid);
CREATE INDEX IF NOT EXISTS idx_reversal_requests_status ON reversal_requests (status);
CREATE INDEX IF NOT EXISTS idx_reversal_requests_requester ON reversal_requests (requester);

CREATE TABLE IF NOT EXISTS security_guardians (
    address TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    added_at BIGINT NOT NULL,
    added_by TEXT NOT NULL,
    removed_at BIGINT,
    active BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_security_guardians_active ON security_guardians (active);

CREATE TABLE IF NOT EXISTS transaction_windows (
    txid TEXT PRIMARY KEY,
    window_blocks INT NOT NULL DEFAULT 0,
    set_by TEXT NOT NULL,
    set_at_block BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transaction_windows_set_by ON transaction_windows (set_by);
