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

mod auth;
mod config;
mod ratelimit;
mod routes;
mod state;

use std::sync::Arc;

use anyhow::Result;
use axum::middleware;
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

    // Rate limiters
    let chat_limiter = ratelimit::create_limiter(1, 10); // 10 burst, 1/s replenish = ~10/min
    let general_limiter = ratelimit::create_limiter(10, 60); // 60 burst, 10/s replenish = ~60/min

    // Auth middleware for subscription-based chat access
    let free_tier_tracker = auth::create_free_tier_tracker();

    // Build route groups
    let api_routes = build_api_routes(
        state.clone(), chat_limiter, general_limiter,
        free_tier_tracker,
    );

    // Mount bare routes + /v1 versioned routes
    let app = Router::new()
        .merge(api_routes.clone())
        .nest("/v1", api_routes)
        .layer(TraceLayer::new_for_http())
        .layer(cors);

    // Start server
    let listener = tokio::net::TcpListener::bind(&config.listen_addr).await?;
    info!("API Gateway listening on {}", config.listen_addr);
    info!("  REST API: http://{}/", config.listen_addr);
    info!("  Versioned: http://{}/v1/", config.listen_addr);
    info!("  JSON-RPC: http://{}/jsonrpc", config.listen_addr);
    info!("  Health:   http://{}/health", config.listen_addr);
    info!("  Rate limits: chat=10/min, general=60/min");

    axum::serve(listener, app).await?;

    Ok(())
}

/// Build all API routes with rate limiting and auth applied per group.
fn build_api_routes(
    state: AppState,
    chat_limiter: ratelimit::SharedLimiter,
    general_limiter: ratelimit::SharedLimiter,
    free_tier_tracker: auth::SharedFreeTierTracker,
) -> Router {
    // Auth state tuple: (aether_url, tracker, http_client)
    let auth_state = (
        state.aether_url.clone(),
        free_tier_tracker,
        state.http_client.clone(),
    );

    // ── Chat routes (auth + rate limit: 10 req/min) ───────────
    let chat_routes = Router::new()
        .route("/aether/chat", post(routes::aether::aether_chat))
        .route("/aether/chat/message", post(routes::aether::aether_chat))
        .route("/aether/chat/session", post(routes::aether::aether_chat_session))
        .route_layer(middleware::from_fn_with_state(
            auth_state,
            auth::auth_middleware,
        ))
        .route_layer(middleware::from_fn_with_state(
            chat_limiter,
            ratelimit::rate_limit_middleware,
        ))
        .with_state(state.clone());

    // ── All other routes (60 req/min) ───────────────────────────
    let general_routes = Router::new()
        // Health & Info
        .route("/", get(routes::health::root))
        .route("/health", get(routes::health::health))
        .route("/info", get(routes::health::info))

        // Chain & Blocks
        .route("/block/{height}", get(routes::chain::get_block_by_height))
        .route("/block/hash/{hash}", get(routes::chain::get_block_by_hash))
        .route("/chain/info", get(routes::chain::chain_info))
        .route("/chain/tip", get(routes::chain::chain_tip))
        .route("/chain/blocks", get(routes::chain::list_blocks))
        .route("/economics/emission", get(routes::chain::emission_schedule))
        .route("/susy-database", get(routes::chain::susy_database))

        // Wallet & Balances
        .route("/balance/{address}", get(routes::wallet::get_balance))
        .route("/utxos/{address}", get(routes::wallet::get_utxos))
        .route("/mempool", get(routes::wallet::get_mempool))
        .route("/transfer", post(routes::wallet::transfer))

        // Mining
        .route("/mining/stats", get(routes::mining::mining_stats))
        .route("/mining/difficulty", get(routes::mining::mining_difficulty))

        // Aether Tree (non-chat)
        .route("/aether/info", get(routes::aether::aether_info))
        .route("/aether/phi", get(routes::aether::aether_phi))
        .route("/aether/phi/history", get(routes::aether::aether_phi_history))
        .route("/aether/knowledge", get(routes::aether::aether_knowledge))
        .route("/aether/gates", get(routes::aether::aether_gates))
        .route("/aether/consciousness", get(routes::aether::aether_consciousness))
        .route("/aether/chat/fee", get(routes::aether::aether_chat_fee))
        .route("/aether/chat/history/{session_id}", get(routes::aether::aether_chat_history))
        .route("/aether/pot", get(routes::aether::aether_pot))
        .route("/aether/contracts/status", get(routes::aether::aether_contracts_status))
        .route("/aether/neural-payload", get(routes::aether::aether_neural_payload))
        .route("/aether/health", get(routes::aether::aether_health))
        .route("/aether/gradients", get(routes::aether::aether_gradients).post(routes::aether::aether_gradients_submit))
        .route("/aether/rewards/pool", get(routes::aether::aether_rewards_pool))
        .route("/aether/rewards/claim", post(routes::aether::aether_rewards_claim))
        .route("/aether/rewards/{miner_id}", get(routes::aether::aether_rewards_miner))

        // JSON-RPC (MetaMask/Web3)
        .route("/jsonrpc", post(routes::jsonrpc::handle_jsonrpc))
        .route_layer(middleware::from_fn_with_state(
            general_limiter,
            ratelimit::rate_limit_middleware,
        ))
        .with_state(state);

    Router::new()
        .merge(chat_routes)
        .merge(general_routes)
}
