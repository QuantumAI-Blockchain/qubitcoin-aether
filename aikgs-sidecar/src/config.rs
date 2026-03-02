//! AIKGS Sidecar configuration — loaded from environment variables.

use std::env;

/// All configurable parameters for the AIKGS sidecar.
#[derive(Debug, Clone)]
pub struct AikgsConfig {
    // ── gRPC server ──
    pub grpc_port: u16,

    // ── Authentication ──
    /// Shared secret for gRPC authentication. If empty, all requests are rejected.
    pub auth_token: String,

    // ── Database ──
    pub database_url: String,

    // ── Python node RPC (for treasury disbursement) ──
    pub node_rpc_url: String,

    // ── Reward engine ──
    pub base_reward_qbc: f64,
    pub max_reward_qbc: f64,
    pub initial_pool_qbc: f64,
    pub early_threshold: i64,
    pub early_max_bonus: f64,

    // ── Affiliate commissions ──
    pub l1_commission_rate: f64,
    pub l2_commission_rate: f64,

    // ── Bounties ──
    pub max_bounty_reward: f64,

    // ── Rate limiting ──
    pub max_daily_submissions: i32,

    // ── Scoring weights ──
    pub quality_weight: f64,
    pub novelty_weight: f64,

    // ── Vault encryption ──
    pub vault_master_key_hex: String,

    // ── Treasury ──
    pub treasury_address: String,

    // ── Disbursement limits (AIKGS-C2) ──
    /// Maximum single disbursement amount in QBC.
    pub max_single_disbursement: f64,
    /// Maximum total daily disbursement amount in QBC.
    pub max_daily_disbursement: f64,
    /// Maximum number of disbursements per hour (rate limit).
    pub max_disbursements_per_hour: i64,

    // ── Retry settings (AIKGS-C4) ──
    /// Maximum number of retry attempts for failed disbursements.
    pub disburse_max_retries: u32,
    /// Initial backoff delay in milliseconds for retries.
    pub disburse_initial_backoff_ms: u64,

    // ── Query limits (AIKGS-H8) ──
    /// Default page size for list queries when the caller does not specify a limit.
    pub query_default_limit: i32,
    /// Maximum page size for list queries (hard cap, cannot be exceeded).
    pub query_max_limit: i32,
}

impl AikgsConfig {
    /// Load configuration from environment variables with sensible defaults.
    pub fn from_env() -> Self {
        Self {
            grpc_port: env_u16("AIKGS_GRPC_PORT", 50052),
            auth_token: env_str("AIKGS_AUTH_TOKEN", ""),
            database_url: env_str(
                "DATABASE_URL",
                "postgresql://root@localhost:26257/qbc?sslmode=disable",
            ),
            node_rpc_url: env_str("AIKGS_NODE_RPC_URL", "http://localhost:5000"),
            base_reward_qbc: env_f64("AIKGS_BASE_REWARD_QBC", 0.05),
            max_reward_qbc: env_f64("AIKGS_MAX_REWARD_QBC", 0.5),
            initial_pool_qbc: env_f64("AIKGS_INITIAL_POOL_QBC", 1_000_000.0),
            early_threshold: env_i64("AIKGS_EARLY_THRESHOLD", 10_000),
            early_max_bonus: env_f64("AIKGS_EARLY_MAX_BONUS", 2.0),
            l1_commission_rate: env_f64("AIKGS_L1_COMMISSION_RATE", 0.05),
            l2_commission_rate: env_f64("AIKGS_L2_COMMISSION_RATE", 0.02),
            max_bounty_reward: env_f64("AIKGS_MAX_BOUNTY_REWARD", 2.5),
            max_daily_submissions: env_i32("AIKGS_MAX_DAILY_SUBMISSIONS", 50),
            quality_weight: env_f64("AIKGS_QUALITY_WEIGHT", 0.6),
            novelty_weight: env_f64("AIKGS_NOVELTY_WEIGHT", 0.4),
            vault_master_key_hex: env_str("AIKGS_VAULT_MASTER_KEY", ""),
            treasury_address: env_str("AIKGS_TREASURY_ADDRESS", ""),
            max_single_disbursement: env_f64("AIKGS_MAX_SINGLE_DISBURSEMENT", 0.5),
            max_daily_disbursement: env_f64("AIKGS_MAX_DAILY_DISBURSEMENT", 500.0),
            max_disbursements_per_hour: env_i64("AIKGS_MAX_DISBURSEMENTS_PER_HOUR", 100),
            disburse_max_retries: env_u32("AIKGS_DISBURSE_MAX_RETRIES", 3),
            disburse_initial_backoff_ms: env_u64("AIKGS_DISBURSE_INITIAL_BACKOFF_MS", 1000),
            query_default_limit: env_i32("AIKGS_QUERY_DEFAULT_LIMIT", 50),
            query_max_limit: env_i32("AIKGS_QUERY_MAX_LIMIT", 1000),
        }
    }
}

fn env_str(key: &str, default: &str) -> String {
    env::var(key).unwrap_or_else(|_| default.to_string())
}

fn env_f64(key: &str, default: f64) -> f64 {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_u16(key: &str, default: u16) -> u16 {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_i32(key: &str, default: i32) -> i32 {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_i64(key: &str, default: i64) -> i64 {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_u32(key: &str, default: u32) -> u32 {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_u64(key: &str, default: u64) -> u64 {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}
