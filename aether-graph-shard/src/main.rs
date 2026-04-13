//! Aether Graph Shard Service
//!
//! Distributed knowledge graph with domain-based sharding.
//! Designed for 1 trillion+ nodes across 10 Sephirot domains.
//!
//! Usage:
//!   aether-graph-shard --port 50053 --data-dir /data/graph-shards --cache 100000
//!
//! Architecture:
//!   12 domain shards (10 Sephirot + General + CrossDomain)
//!   Each shard: RocksDB + LRU cache + incremental Merkle tree
//!   gRPC service on configurable port (default 50053)

mod merkle;
mod router;
mod service;
mod storage;
mod types;
mod vector_index;

use router::ShardRouter;
use service::proto::graph_shard_service_server::GraphShardServiceServer;
use service::GraphShardServer;
use std::sync::Arc;
use tonic::transport::Server;
use tracing::{info, Level};
use tracing_subscriber::EnvFilter;

#[derive(Debug)]
struct Config {
    port: u16,
    data_dir: String,
    cache_per_shard: usize,
}

impl Config {
    fn from_env() -> Self {
        Self {
            port: std::env::var("GRAPH_SHARD_PORT")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(50053),
            data_dir: std::env::var("GRAPH_SHARD_DATA_DIR")
                .unwrap_or_else(|_| "/data/graph-shards".to_string()),
            cache_per_shard: std::env::var("GRAPH_SHARD_CACHE")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(100_000),
        }
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .with_target(true)
        .with_thread_ids(true)
        .json()
        .init();

    let config = Config::from_env();

    info!(
        port = config.port,
        data_dir = %config.data_dir,
        cache_per_shard = config.cache_per_shard,
        "Starting Aether Graph Shard Service"
    );

    // Initialize the shard router with all domain shards
    let router = Arc::new(ShardRouter::new(&config.data_dir, config.cache_per_shard));
    router.init_shards()?;

    let stats = router.global_stats();
    info!(
        total_nodes = stats.total_nodes,
        total_edges = stats.total_edges,
        active_shards = stats.active_shards,
        "Shards initialized"
    );

    // Build gRPC server
    let addr = format!("0.0.0.0:{}", config.port).parse()?;
    let server = GraphShardServer::new(router.clone());

    info!(%addr, "gRPC server listening");

    // Spawn Prometheus metrics endpoint
    let metrics_port = config.port + 1000; // e.g., 51053
    let metrics_router = router.clone();
    tokio::spawn(async move {
        let app = axum_metrics_server(metrics_router);
        let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", metrics_port))
            .await
            .expect("bind metrics");
        info!(port = metrics_port, "Metrics endpoint listening");
        axum::serve(listener, app).await.ok();
    });

    Server::builder()
        .add_service(GraphShardServiceServer::new(server))
        .serve(addr)
        .await?;

    Ok(())
}

/// Simple HTTP metrics/health endpoint alongside gRPC.
fn axum_metrics_server(router: Arc<ShardRouter>) -> axum::Router {
    use axum::{extract::State, routing::get, Json, Router};

    async fn health(State(router): State<Arc<ShardRouter>>) -> Json<serde_json::Value> {
        let stats = router.global_stats();
        Json(serde_json::json!({
            "status": "healthy",
            "total_nodes": stats.total_nodes,
            "total_edges": stats.total_edges,
            "active_shards": stats.active_shards,
            "merkle_root": stats.global_merkle_root,
        }))
    }

    async fn stats(State(router): State<Arc<ShardRouter>>) -> Json<serde_json::Value> {
        let stats = router.global_stats();
        Json(serde_json::json!(stats))
    }

    Router::new()
        .route("/health", get(health))
        .route("/stats", get(stats))
        .with_state(router)
}
