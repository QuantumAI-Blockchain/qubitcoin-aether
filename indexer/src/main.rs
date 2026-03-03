//! Qubitcoin Block Indexer — subscribes to finalized Substrate blocks
//! and writes block/transaction/UTXO data to CockroachDB.
//!
//! Usage:
//!     qbc-indexer                                          # Default settings
//!     qbc-indexer --substrate-ws-url ws://node:9944        # Custom node
//!     qbc-indexer --database-url postgresql://...          # Custom DB
//!     qbc-indexer --backfill --start-height 0              # Backfill from genesis
//!
//! Environment variables:
//!     SUBSTRATE_WS_URL    WebSocket endpoint (default: ws://127.0.0.1:9944)
//!     DATABASE_URL        CockroachDB connection string
//!     DB_POOL_SIZE        Connection pool size (default: 10)
//!     START_HEIGHT        Start indexing from this height (default: 0)
//!     BACKFILL            Enable backfill mode (default: false)
//!     LOG_LEVEL           Logging level (default: info)

mod config;
mod db;
mod indexer;
mod substrate;
mod types;

use anyhow::Result;
use clap::Parser;
use tracing::info;
use tracing_subscriber::EnvFilter;

use crate::config::Config;
use crate::indexer::Indexer;

#[tokio::main]
async fn main() -> Result<()> {
    let config = Config::parse();

    // Initialize structured logging
    let filter = EnvFilter::try_new(&config.log_level)
        .unwrap_or_else(|_| EnvFilter::new("info"));

    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_target(true)
        .with_thread_ids(false)
        .with_file(false)
        .init();

    info!("═══════════════════════════════════════════════════");
    info!("  Qubitcoin Block Indexer v{}", env!("CARGO_PKG_VERSION"));
    info!("═══════════════════════════════════════════════════");
    info!("Substrate: {}", config.substrate_ws_url);
    info!("Database:  {}...", &config.database_url[..config.database_url.len().min(40)]);
    info!("Backfill:  {}", config.backfill);

    // Create and run the indexer
    let mut indexer = Indexer::new(config).await?;

    // Handle Ctrl+C gracefully
    let shutdown = tokio::signal::ctrl_c();

    tokio::select! {
        result = indexer.run() => {
            if let Err(e) = result {
                tracing::error!("Indexer error: {:?}", e);
            }
        }
        _ = shutdown => {
            info!("Shutdown signal received");
        }
    }

    indexer.shutdown().await;
    Ok(())
}
