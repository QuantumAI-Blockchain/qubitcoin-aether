//! AIKGS Sidecar — entry point.
//!
//! Starts the gRPC server on the configured port, connects to CockroachDB,
//! and serves all AIKGS operations.

use std::sync::Arc;

mod service;

use aikgs_sidecar::config::AikgsConfig;
use aikgs_sidecar::db::Db;
use aikgs_sidecar::treasury::TreasuryClient;
use aikgs_sidecar::vault::VaultManager;

use service::proto::aikgs_service_server::AikgsServiceServer;
use service::AikgsSvc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Load .env files (project root or working dir)
    let _ = dotenvy::dotenv();
    let _ = dotenvy::from_filename("../.env");

    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let cfg = Arc::new(AikgsConfig::from_env());
    log::info!("AIKGS Sidecar starting on port {}", cfg.grpc_port);

    // Connect to CockroachDB
    let db = Db::connect(&cfg).await?;
    log::info!("Database connected");

    // Treasury client (calls Python node RPC for disbursements)
    let treasury = TreasuryClient::new(&cfg.node_rpc_url);
    if treasury.check_health().await {
        log::info!("Python node reachable at {}", cfg.node_rpc_url);
    } else {
        log::warn!(
            "Python node NOT reachable at {} — disbursements will retry later",
            cfg.node_rpc_url
        );
    }

    // Vault (optional — needs master key)
    let vault = if cfg.vault_master_key_hex.is_empty() {
        log::warn!("AIKGS_VAULT_MASTER_KEY not set — API key vault disabled");
        None
    } else {
        match VaultManager::new(&cfg.vault_master_key_hex) {
            Ok(v) => {
                log::info!("API key vault initialized");
                Some(v)
            }
            Err(e) => {
                log::error!("Vault init failed: {e} — vault disabled");
                None
            }
        }
    };

    // Build the gRPC service
    let svc = AikgsSvc::new(db, cfg.clone(), treasury, vault);

    let addr = format!("0.0.0.0:{}", cfg.grpc_port).parse()?;
    log::info!("AIKGS gRPC server listening on {addr}");

    tonic::transport::Server::builder()
        .add_service(AikgsServiceServer::new(svc))
        .serve(addr)
        .await?;

    Ok(())
}
