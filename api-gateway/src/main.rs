//! Qubitcoin API Gateway — REST + JSON-RPC on port 5000.
//!
//! This is the single HTTP entry point for:
//! - Frontend (qbc.network) REST API calls
//! - MetaMask/Web3 eth_* JSON-RPC
//! - Prometheus metrics
//!
//! Data sources:
//! - CockroachDB (block/tx data populated by the indexer)
//! - Substrate RPC (live chain state via WebSocket)
//! - Aether service (proxied for AI endpoints)

mod config;
mod routes;
mod state;

use std::sync::Arc;

use anyhow::Result;
use axum::routing::{get, post};
use axum::Router;
use clap::Parser;
use sqlx::postgres::PgPoolOptions;
use tower_http::cors::{Any, CorsLayer};
use tower_http::trace::TraceLayer;
use tracing::info;
use tracing_subscriber::EnvFilter;

use crate::config::Config;
use crate::state::{AppState, SubstrateRpc};

#[tokio::main]
async fn main() -> Result<()> {
    let config = Config::parse();

    // Initialize logging
    let filter = EnvFilter::try_new(&config.log_level)
        .unwrap_or_else(|_| EnvFilter::new("info"));
    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_target(true)
        .init();

    info!("═══════════════════════════════════════════════════");
    info!("  Qubitcoin API Gateway v{}", env!("CARGO_PKG_VERSION"));
    info!("═══════════════════════════════════════════════════");

    // Connect to CockroachDB
    info!("Connecting to CockroachDB...");
    let db = PgPoolOptions::new()
        .max_connections(config.db_pool_size)
        .connect(&config.database_url)
        .await?;
    sqlx::query("SELECT 1").execute(&db).await?;
    info!("CockroachDB connected");

    // Connect to Substrate node (optional — gateway works DB-only)
    info!("Connecting to Substrate node: {}", config.substrate_ws_url);
    let substrate = SubstrateRpc::connect(&config.substrate_ws_url).await;

    // Build shared state
    let state = AppState {
        db,
        substrate: substrate.map(Arc::new),
        aether_url: config.aether_service_url.clone(),
        chain_id: config.chain_id,
        http_client: reqwest::Client::new(),
    };

    // Build CORS layer
    let cors = CorsLayer::new()
        .allow_origin(Any) // TODO: restrict in production
        .allow_methods(Any)
        .allow_headers(Any);

    // Build router
    let app = Router::new()
        // ── Health & Info ─────────────────────────────────────
        .route("/", get(routes::health::root))
        .route("/health", get(routes::health::health))
        .route("/info", get(routes::health::info))

        // ── Chain & Blocks ────────────────────────────────────
        .route("/block/{height}", get(routes::chain::get_block_by_height))
        .route("/block/hash/{hash}", get(routes::chain::get_block_by_hash))
        .route("/chain/info", get(routes::chain::chain_info))
        .route("/chain/tip", get(routes::chain::chain_tip))
        .route("/chain/blocks", get(routes::chain::list_blocks))
        .route("/economics/emission", get(routes::chain::emission_schedule))
        .route("/susy-database", get(routes::chain::susy_database))

        // ── Wallet & Balances ─────────────────────────────────
        .route("/balance/{address}", get(routes::wallet::get_balance))
        .route("/utxos/{address}", get(routes::wallet::get_utxos))
        .route("/mempool", get(routes::wallet::get_mempool))
        .route("/transfer", post(routes::wallet::transfer))

        // ── Mining ────────────────────────────────────────────
        .route("/mining/stats", get(routes::mining::mining_stats))
        .route("/mining/difficulty", get(routes::mining::mining_difficulty))

        // ── Aether Tree ───────────────────────────────────────
        .route("/aether/info", get(routes::aether::aether_info))
        .route("/aether/phi", get(routes::aether::aether_phi))
        .route("/aether/phi/history", get(routes::aether::aether_phi_history))
        .route("/aether/knowledge", get(routes::aether::aether_knowledge))
        .route("/aether/consciousness", get(routes::aether::aether_consciousness))
        .route("/aether/chat", post(routes::aether::aether_chat))
        .route("/aether/chat/message", post(routes::aether::aether_chat))
        .route("/aether/chat/session", post(routes::aether::aether_chat_session))
        .route("/aether/chat/fee", get(routes::aether::aether_chat_fee))
        .route("/aether/chat/history/{session_id}", get(routes::aether::aether_chat_history))

        // ── JSON-RPC (MetaMask/Web3) ──────────────────────────
        .route("/jsonrpc", post(routes::jsonrpc::handle_jsonrpc))

        // ── Middleware ────────────────────────────────────────
        .layer(TraceLayer::new_for_http())
        .layer(cors)
        .with_state(state);

    // Also handle JSON-RPC on POST / (MetaMask sends to root)
    // This is handled by checking Content-Type in a middleware
    // For now, /jsonrpc is the explicit endpoint

    // Start server
    let listener = tokio::net::TcpListener::bind(&config.listen_addr).await?;
    info!("API Gateway listening on {}", config.listen_addr);
    info!("  REST API: http://{}/", config.listen_addr);
    info!("  JSON-RPC: http://{}/jsonrpc", config.listen_addr);
    info!("  Health:   http://{}/health", config.listen_addr);

    axum::serve(listener, app).await?;

    Ok(())
}
