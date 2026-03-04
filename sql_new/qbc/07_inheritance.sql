-- Inheritance Protocol Schema
-- Dead-man's switch for QBC asset transfer to designated beneficiaries

CREATE TABLE IF NOT EXISTS inheritance_plans (
    owner_address TEXT PRIMARY KEY,
    beneficiary_address TEXT NOT NULL,
    inactivity_blocks BIGINT NOT NULL DEFAULT 2618200,  -- ~100 days at 3.3s/block
    last_heartbeat_block BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    active BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_inheritance_plans_beneficiary ON inheritance_plans (beneficiary_address);
CREATE INDEX IF NOT EXISTS idx_inheritance_plans_active ON inheritance_plans (active);
CREATE INDEX IF NOT EXISTS idx_inheritance_plans_heartbeat ON inheritance_plans (last_heartbeat_block);

CREATE TABLE IF NOT EXISTS inheritance_claims (
    claim_id TEXT PRIMARY KEY,
    owner_address TEXT NOT NULL,
    beneficiary_address TEXT NOT NULL,
    initiated_at_block BIGINT NOT NULL,
    grace_expires_block BIGINT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, executed, cancelled
    executed_at TIMESTAMPTZ,
    execution_txid TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_inheritance_claims_owner ON inheritance_claims (owner_address);
CREATE INDEX IF NOT EXISTS idx_inheritance_claims_beneficiary ON inheritance_claims (beneficiary_address);
CREATE INDEX IF NOT EXISTS idx_inheritance_claims_status ON inheritance_claims (status);
