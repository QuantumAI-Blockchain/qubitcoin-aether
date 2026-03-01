-- AIKGS (Aether Incentivized Knowledge Growth System) Schema
-- 10 tables for contribution tracking, rewards, affiliates, bounties, curation

-- Contributions ledger
CREATE TABLE IF NOT EXISTS aikgs_contributions (
    id              SERIAL PRIMARY KEY,
    contribution_id BIGINT NOT NULL UNIQUE,
    contributor_address VARCHAR(128) NOT NULL,
    content_hash    VARCHAR(64) NOT NULL,
    knowledge_node_id BIGINT,
    quality_score   FLOAT NOT NULL DEFAULT 0.0 CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
    novelty_score   FLOAT NOT NULL DEFAULT 0.0 CHECK (novelty_score >= 0.0 AND novelty_score <= 1.0),
    combined_score  FLOAT NOT NULL DEFAULT 0.0 CHECK (combined_score >= 0.0 AND combined_score <= 1.0),
    tier            VARCHAR(16) NOT NULL DEFAULT 'bronze' CHECK (tier IN ('bronze', 'silver', 'gold', 'diamond')),
    domain          VARCHAR(64) NOT NULL DEFAULT 'general',
    reward_amount   DECIMAL(20,8) NOT NULL DEFAULT 0 CHECK (reward_amount >= 0),
    status          VARCHAR(32) NOT NULL DEFAULT 'accepted' CHECK (status IN ('pending', 'accepted', 'rejected_spam', 'rejected', 'disputed')),
    block_height    BIGINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_aikgs_contributions_contributor ON aikgs_contributions (contributor_address);
CREATE INDEX IF NOT EXISTS idx_aikgs_contributions_domain ON aikgs_contributions (domain);
CREATE INDEX IF NOT EXISTS idx_aikgs_contributions_tier ON aikgs_contributions (tier);
CREATE INDEX IF NOT EXISTS idx_aikgs_contributions_content_hash ON aikgs_contributions (content_hash);
CREATE INDEX IF NOT EXISTS idx_aikgs_contributions_block_height ON aikgs_contributions (block_height);
CREATE INDEX IF NOT EXISTS idx_aikgs_contributions_created_at ON aikgs_contributions (created_at);

-- Reward distributions
CREATE TABLE IF NOT EXISTS aikgs_rewards (
    id              SERIAL PRIMARY KEY,
    contribution_id BIGINT NOT NULL REFERENCES aikgs_contributions(contribution_id),
    contributor_address VARCHAR(128) NOT NULL,
    amount          DECIMAL(20,8) NOT NULL CHECK (amount >= 0),
    base_reward     DECIMAL(20,8) NOT NULL CHECK (base_reward >= 0),
    quality_factor  FLOAT NOT NULL CHECK (quality_factor >= 0),
    novelty_factor  FLOAT NOT NULL CHECK (novelty_factor >= 0),
    tier_multiplier FLOAT NOT NULL CHECK (tier_multiplier >= 0),
    streak_multiplier FLOAT NOT NULL CHECK (streak_multiplier >= 0),
    staking_boost   FLOAT NOT NULL DEFAULT 1.0 CHECK (staking_boost >= 0),
    early_bonus     FLOAT NOT NULL DEFAULT 1.0 CHECK (early_bonus >= 0),
    block_height    BIGINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_aikgs_rewards_contributor ON aikgs_rewards (contributor_address);
CREATE INDEX IF NOT EXISTS idx_aikgs_rewards_block_height ON aikgs_rewards (block_height);
CREATE INDEX IF NOT EXISTS idx_aikgs_rewards_contribution ON aikgs_rewards (contribution_id);

-- Affiliate registrations
CREATE TABLE IF NOT EXISTS aikgs_affiliates (
    id              SERIAL PRIMARY KEY,
    address         VARCHAR(128) NOT NULL UNIQUE,
    referrer_address VARCHAR(128),
    referral_code   VARCHAR(32) NOT NULL UNIQUE,
    l1_referrals    INT NOT NULL DEFAULT 0,
    l2_referrals    INT NOT NULL DEFAULT 0,
    total_l1_commission DECIMAL(20,8) NOT NULL DEFAULT 0,
    total_l2_commission DECIMAL(20,8) NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_aikgs_affiliates_referrer ON aikgs_affiliates (referrer_address);
CREATE INDEX IF NOT EXISTS idx_aikgs_affiliates_code ON aikgs_affiliates (referral_code);

-- Commission events
CREATE TABLE IF NOT EXISTS aikgs_commissions (
    id              SERIAL PRIMARY KEY,
    affiliate_address VARCHAR(128) NOT NULL,
    contributor_address VARCHAR(128) NOT NULL,
    amount          DECIMAL(20,8) NOT NULL CHECK (amount >= 0),
    level           SMALLINT NOT NULL CHECK (level IN (1, 2)),
    contribution_id BIGINT NOT NULL REFERENCES aikgs_contributions(contribution_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_aikgs_commissions_affiliate ON aikgs_commissions (affiliate_address);
CREATE INDEX IF NOT EXISTS idx_aikgs_commissions_contribution ON aikgs_commissions (contribution_id);

-- Contributor profiles (reputation + progressive unlocks)
CREATE TABLE IF NOT EXISTS aikgs_profiles (
    id              SERIAL PRIMARY KEY,
    address         VARCHAR(128) NOT NULL UNIQUE,
    reputation_points FLOAT NOT NULL DEFAULT 0,
    level           INT NOT NULL DEFAULT 1,
    level_name      VARCHAR(32) NOT NULL DEFAULT 'Novice',
    total_contributions INT NOT NULL DEFAULT 0,
    best_streak     INT NOT NULL DEFAULT 0,
    current_streak  INT NOT NULL DEFAULT 0,
    gold_count      INT NOT NULL DEFAULT 0,
    diamond_count   INT NOT NULL DEFAULT 0,
    bounties_fulfilled INT NOT NULL DEFAULT 0,
    referrals       INT NOT NULL DEFAULT 0,
    badges          JSONB NOT NULL DEFAULT '[]',
    unlocked_features JSONB NOT NULL DEFAULT '["basic_chat","contribute"]',
    last_contribution_at TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_aikgs_profiles_level ON aikgs_profiles (level);
CREATE INDEX IF NOT EXISTS idx_aikgs_profiles_reputation ON aikgs_profiles (reputation_points DESC);

-- Knowledge bounties
CREATE TABLE IF NOT EXISTS aikgs_bounties (
    id              SERIAL PRIMARY KEY,
    bounty_id       BIGINT NOT NULL UNIQUE,
    domain          VARCHAR(64) NOT NULL,
    description     TEXT NOT NULL,
    gap_hash        VARCHAR(64) NOT NULL,
    reward_amount   DECIMAL(20,8) NOT NULL CHECK (reward_amount >= 0),
    boost_multiplier FLOAT NOT NULL DEFAULT 1.0 CHECK (boost_multiplier > 0),
    status          VARCHAR(32) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'claimed', 'fulfilled', 'expired', 'cancelled')),
    claimer_address VARCHAR(128),
    contribution_id BIGINT REFERENCES aikgs_contributions(contribution_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    CHECK (expires_at > created_at)
);
CREATE INDEX IF NOT EXISTS idx_aikgs_bounties_status ON aikgs_bounties (status);
CREATE INDEX IF NOT EXISTS idx_aikgs_bounties_domain ON aikgs_bounties (domain);
CREATE INDEX IF NOT EXISTS idx_aikgs_bounties_expires_at ON aikgs_bounties (expires_at);

-- Seasonal events
CREATE TABLE IF NOT EXISTS aikgs_seasons (
    id              SERIAL PRIMARY KEY,
    season_id       BIGINT NOT NULL UNIQUE,
    name            VARCHAR(128) NOT NULL,
    domain          VARCHAR(64) NOT NULL,
    boost_multiplier FLOAT NOT NULL CHECK (boost_multiplier > 0),
    starts_at       TIMESTAMPTZ NOT NULL,
    ends_at         TIMESTAMPTZ NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT true,
    CHECK (starts_at < ends_at)
);
CREATE INDEX IF NOT EXISTS idx_aikgs_seasons_active ON aikgs_seasons (active) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_aikgs_seasons_domain ON aikgs_seasons (domain);

-- Curation rounds
CREATE TABLE IF NOT EXISTS aikgs_curation_rounds (
    id              SERIAL PRIMARY KEY,
    contribution_id BIGINT NOT NULL UNIQUE REFERENCES aikgs_contributions(contribution_id),
    required_votes  INT NOT NULL DEFAULT 3 CHECK (required_votes > 0),
    votes_for       INT NOT NULL DEFAULT 0 CHECK (votes_for >= 0),
    votes_against   INT NOT NULL DEFAULT 0 CHECK (votes_against >= 0),
    status          VARCHAR(32) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    finalized_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_aikgs_curation_rounds_status ON aikgs_curation_rounds (status);

-- Curation reviews
CREATE TABLE IF NOT EXISTS aikgs_curation_reviews (
    id              SERIAL PRIMARY KEY,
    contribution_id BIGINT NOT NULL REFERENCES aikgs_contributions(contribution_id),
    curator_address VARCHAR(128) NOT NULL,
    vote            BOOLEAN NOT NULL,
    comment         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(contribution_id, curator_address)
);
CREATE INDEX IF NOT EXISTS idx_aikgs_curation_reviews_curator ON aikgs_curation_reviews (curator_address);

-- API Key Vault (encrypted keys stored separately)
CREATE TABLE IF NOT EXISTS aikgs_api_keys (
    id              SERIAL PRIMARY KEY,
    key_id          VARCHAR(32) NOT NULL UNIQUE,
    provider        VARCHAR(32) NOT NULL,
    model           VARCHAR(64) NOT NULL DEFAULT '',
    owner_address   VARCHAR(128) NOT NULL,
    encrypted_key   BYTEA NOT NULL,
    is_shared       BOOLEAN NOT NULL DEFAULT false,
    shared_reward_bps INT NOT NULL DEFAULT 1500 CHECK (shared_reward_bps >= 0 AND shared_reward_bps <= 10000),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    use_count       INT NOT NULL DEFAULT 0 CHECK (use_count >= 0),
    label           VARCHAR(128) NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_aikgs_api_keys_owner ON aikgs_api_keys (owner_address);
CREATE INDEX IF NOT EXISTS idx_aikgs_api_keys_provider ON aikgs_api_keys (provider);
CREATE INDEX IF NOT EXISTS idx_aikgs_api_keys_shared ON aikgs_api_keys (is_shared) WHERE is_shared = true;
