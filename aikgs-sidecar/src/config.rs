//! AIKGS Sidecar configuration — loaded from environment variables.

use std::env;

/// All configurable parameters for the AIKGS sidecar.
#[derive(Debug, Clone)]
pub struct AikgsConfig {
    // ── gRPC server ──
    pub grpc_port: u16,

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
}

impl AikgsConfig {
    /// Load configuration from environment variables with sensible defaults.
    pub fn from_env() -> Self {
        Self {
            grpc_port: env_u16("AIKGS_GRPC_PORT", 50052),
            database_url: env_str(
                "DATABASE_URL",
                "postgresql://root@localhost:26257/qbc?sslmode=disable",
            ),
            node_rpc_url: env_str("AIKGS_NODE_RPC_URL", "http://localhost:5000"),
            base_reward_qbc: env_f64("AIKGS_BASE_REWARD_QBC", 1.0),
            max_reward_qbc: env_f64("AIKGS_MAX_REWARD_QBC", 50.0),
            initial_pool_qbc: env_f64("AIKGS_INITIAL_POOL_QBC", 1_000_000.0),
            early_threshold: env_i64("AIKGS_EARLY_THRESHOLD", 10_000),
            early_max_bonus: env_f64("AIKGS_EARLY_MAX_BONUS", 5.0),
            l1_commission_rate: env_f64("AIKGS_L1_COMMISSION_RATE", 0.05),
            l2_commission_rate: env_f64("AIKGS_L2_COMMISSION_RATE", 0.02),
            max_bounty_reward: env_f64("AIKGS_MAX_BOUNTY_REWARD", 500.0),
            max_daily_submissions: env_i32("AIKGS_MAX_DAILY_SUBMISSIONS", 50),
            quality_weight: env_f64("AIKGS_QUALITY_WEIGHT", 0.6),
            novelty_weight: env_f64("AIKGS_NOVELTY_WEIGHT", 0.4),
            vault_master_key_hex: env_str("AIKGS_VAULT_MASTER_KEY", ""),
            treasury_address: env_str("AIKGS_TREASURY_ADDRESS", ""),
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
