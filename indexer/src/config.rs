//! Configuration for the QBC Block Indexer.
//!
//! All values are loaded from CLI args or environment variables.

use clap::Parser;

/// Qubitcoin Block Indexer — subscribes to finalized Substrate blocks
/// and writes block/transaction/UTXO data to CockroachDB.
#[derive(Parser, Debug, Clone)]
#[command(name = "qbc-indexer", version, about)]
pub struct Config {
    /// Substrate node WebSocket RPC endpoint.
    #[arg(
        long,
        env = "SUBSTRATE_WS_URL",
        default_value = "ws://127.0.0.1:9944"
    )]
    pub substrate_ws_url: String,

    /// CockroachDB connection string (PostgreSQL wire protocol).
    #[arg(
        long,
        env = "DATABASE_URL",
        default_value = "postgresql://root@127.0.0.1:26257/qbc?sslmode=disable"
    )]
    pub database_url: String,

    /// Maximum database connection pool size.
    #[arg(long, env = "DB_POOL_SIZE", default_value_t = 10)]
    pub db_pool_size: u32,

    /// Block height to start indexing from (0 = genesis).
    /// If the database already has blocks, resumes from the last indexed height.
    #[arg(long, env = "START_HEIGHT", default_value_t = 0)]
    pub start_height: u64,

    /// Enable backfill mode: index historical blocks before subscribing to new ones.
    #[arg(long, env = "BACKFILL", default_value_t = false)]
    pub backfill: bool,

    /// Log level (trace, debug, info, warn, error).
    #[arg(long, env = "LOG_LEVEL", default_value = "info")]
    pub log_level: String,

    /// Number of QBC decimals (for amount conversion).
    #[arg(long, env = "QBC_DECIMALS", default_value_t = 8)]
    pub qbc_decimals: u32,
}
