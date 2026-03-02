//! AIKGS Sidecar — entry point.
//!
//! Starts the gRPC server on the configured port, connects to CockroachDB,
//! and serves all AIKGS operations. All RPCs require authentication via the
//! `x-auth-token` metadata header (AIKGS-C1).

use std::sync::Arc;

mod service;

use aikgs_sidecar::config::AikgsConfig;
use aikgs_sidecar::db::Db;
use aikgs_sidecar::treasury::TreasuryClient;
use aikgs_sidecar::vault::VaultManager;

use service::proto::aikgs_service_server::AikgsServiceServer;
use service::AikgsSvc;

use tonic::service::interceptor::InterceptedService;
use tonic::transport::Server;

/// gRPC authentication interceptor. Validates the `x-auth-token` metadata
/// header against the configured `AIKGS_AUTH_TOKEN` secret.
#[derive(Clone)]
struct AuthInterceptor {
    expected_token: Arc<String>,
}

impl AuthInterceptor {
    fn new(token: String) -> Self {
        Self {
            expected_token: Arc::new(token),
        }
    }
}

impl tonic::service::Interceptor for AuthInterceptor {
    fn call(
        &mut self,
        request: tonic::Request<()>,
    ) -> Result<tonic::Request<()>, tonic::Status> {
        // If no auth token is configured, reject all requests.
        if self.expected_token.is_empty() {
            log::error!("AIKGS_AUTH_TOKEN not configured — rejecting request");
            return Err(tonic::Status::unauthenticated(
                "server authentication not configured",
            ));
        }

        match request.metadata().get("x-auth-token") {
            Some(token) => {
                let token_str = token
                    .to_str()
                    .map_err(|_| tonic::Status::unauthenticated("invalid auth token encoding"))?;

                if token_str == self.expected_token.as_str() {
                    Ok(request)
                } else {
                    Err(tonic::Status::unauthenticated("invalid auth token"))
                }
            }
            None => Err(tonic::Status::unauthenticated(
                "missing x-auth-token metadata header",
            )),
        }
    }
}

/// Background task that retries failed disbursements with exponential backoff (AIKGS-C4).
///
/// Runs every 60 seconds, picks up disbursements with status='failed' and
/// retry_count < max_retries, then retries them with exponential backoff
/// delay: initial_backoff_ms * 2^retry_count.
async fn disbursement_retry_loop(
    db: Db,
    node_rpc_url: String,
    max_retries: u32,
    initial_backoff_ms: u64,
) {
    let treasury = TreasuryClient::new(&node_rpc_url);

    loop {
        // Wait before checking for retries
        tokio::time::sleep(std::time::Duration::from_secs(60)).await;

        let failed = match db
            .get_failed_disbursements_for_retry(max_retries as i64)
            .await
        {
            Ok(rows) => rows,
            Err(e) => {
                log::error!("Failed to query retryable disbursements: {e}");
                continue;
            }
        };

        if failed.is_empty() {
            continue;
        }

        log::info!(
            "Retrying {} failed disbursements (max_retries={})",
            failed.len(),
            max_retries
        );

        for row in &failed {
            // Calculate backoff: initial * 2^retry_count
            // We use retry_count from the current status; since we're about to increment,
            // this is the Nth retry attempt.
            let backoff_ms = initial_backoff_ms.saturating_mul(1u64 << row.retry_count_val());
            let backoff = std::time::Duration::from_millis(backoff_ms.min(60_000)); // cap at 60s

            log::info!(
                "Retrying disbursement key={} amount={:.8} to={} (backoff={}ms)",
                row.idempotency_key,
                row.amount,
                row.recipient_address,
                backoff_ms.min(60_000)
            );

            tokio::time::sleep(backoff).await;

            // Mark as retrying (increments retry_count, sets status=pending)
            if let Err(e) = db.mark_disbursement_retrying(&row.idempotency_key).await {
                log::error!(
                    "Failed to mark disbursement {} as retrying: {e}",
                    row.idempotency_key
                );
                continue;
            }

            // Attempt the disbursement
            match treasury
                .disburse(&row.recipient_address, row.amount, &row.reason)
                .await
            {
                Ok(result) => {
                    let _ = db
                        .complete_disbursement(
                            &row.idempotency_key,
                            result.success,
                            result.txid.as_deref(),
                            result.error.as_deref(),
                        )
                        .await;
                    if result.success {
                        log::info!(
                            "Retry succeeded for disbursement key={} txid={}",
                            row.idempotency_key,
                            result.txid.as_deref().unwrap_or("unknown")
                        );
                    } else {
                        log::warn!(
                            "Retry failed for disbursement key={}: {}",
                            row.idempotency_key,
                            result.error.as_deref().unwrap_or("unknown")
                        );
                    }
                }
                Err(e) => {
                    log::warn!(
                        "Retry HTTP error for disbursement key={}: {e}",
                        row.idempotency_key
                    );
                    let _ = db
                        .complete_disbursement(
                            &row.idempotency_key,
                            false,
                            None,
                            Some(&e.to_string()),
                        )
                        .await;
                }
            }
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Load .env files (project root or working dir)
    let _ = dotenvy::dotenv();
    let _ = dotenvy::from_filename("../.env");

    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let cfg = Arc::new(AikgsConfig::from_env());
    log::info!("AIKGS Sidecar starting on port {}", cfg.grpc_port);

    // Validate auth token is configured
    if cfg.auth_token.is_empty() {
        log::warn!(
            "AIKGS_AUTH_TOKEN is NOT set — all gRPC requests will be rejected. \
             Set AIKGS_AUTH_TOKEN env var to enable access."
        );
    } else {
        log::info!("Authentication enabled (x-auth-token header required)");
    }

    // Connect to CockroachDB
    let db = Db::connect(&cfg).await?;
    log::info!("Database connected");

    // Ensure ID sequences exist (AIKGS-C3)
    db.ensure_sequences().await?;
    log::info!("ID sequences ready");

    // Ensure disbursement tracking table exists (AIKGS-C4)
    db.ensure_disbursement_table().await?;
    log::info!("Disbursement tracking table ready");

    // Ensure bounty_amount column on rewards table (AIKGS-H3)
    db.ensure_reward_bounty_column().await?;

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

    // Spawn background retry task for failed disbursements (AIKGS-C4)
    {
        let retry_db = db.clone();
        let retry_node_url = cfg.node_rpc_url.clone();
        let max_retries = cfg.disburse_max_retries;
        let initial_backoff_ms = cfg.disburse_initial_backoff_ms;
        tokio::spawn(async move {
            disbursement_retry_loop(retry_db, retry_node_url, max_retries, initial_backoff_ms).await;
        });
        log::info!(
            "Disbursement retry task started (max_retries={}, initial_backoff={}ms)",
            cfg.disburse_max_retries,
            cfg.disburse_initial_backoff_ms
        );
    }

    // Build the gRPC service with authentication interceptor
    let svc = AikgsSvc::new(db, cfg.clone(), treasury, vault);
    let auth = AuthInterceptor::new(cfg.auth_token.clone());

    let addr = format!("0.0.0.0:{}", cfg.grpc_port).parse()?;
    log::info!("AIKGS gRPC server listening on {addr}");

    Server::builder()
        .add_service(InterceptedService::new(
            AikgsServiceServer::new(svc),
            auth,
        ))
        .serve(addr)
        .await?;

    Ok(())
}
