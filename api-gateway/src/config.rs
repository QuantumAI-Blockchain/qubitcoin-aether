//! API Gateway configuration — loaded from CLI args and environment variables.

use clap::Parser;

/// Qubitcoin API Gateway — REST + JSON-RPC server on port 5000.
///
/// Serves as the single entry point for:
/// - REST API endpoints (block explorer, wallet, mining stats)
/// - eth_* JSON-RPC (MetaMask/Web3 compatibility)
/// - Prometheus metrics endpoint
#[derive(Parser, Debug, Clone)]
#[command(name = "qbc-api-gateway", version, about)]
pub struct Config {
    /// HTTP listen address.
    #[arg(long, env = "API_LISTEN_ADDR", default_value = "0.0.0.0:5000")]
    pub listen_addr: String,

    /// Substrate node WebSocket RPC endpoint.
    #[arg(
        long,
        env = "SUBSTRATE_WS_URL",
        default_value = "ws://127.0.0.1:9944"
    )]
    pub substrate_ws_url: String,

    /// CockroachDB connection string.
    #[arg(
        long,
        env = "DATABASE_URL",
        default_value = "postgresql://root@127.0.0.1:26257/qubitcoin?sslmode=disable"
    )]
    pub database_url: String,

    /// Maximum database connection pool size.
    #[arg(long, env = "DB_POOL_SIZE", default_value_t = 20)]
    pub db_pool_size: u32,

    /// Aether service endpoint (for chat/phi/knowledge queries).
    #[arg(
        long,
        env = "AETHER_SERVICE_URL",
        default_value = "http://127.0.0.1:5003"
    )]
    pub aether_service_url: String,

    /// Chain ID for JSON-RPC responses.
    #[arg(long, env = "CHAIN_ID", default_value_t = 3303)]
    pub chain_id: u64,

    /// CORS allowed origins (comma-separated).
    #[arg(
        long,
        env = "CORS_ORIGINS",
        default_value = "http://localhost:3000,https://qbc.network"
    )]
    pub cors_origins: String,

    /// Log level.
    #[arg(long, env = "LOG_LEVEL", default_value = "info")]
    pub log_level: String,
}
