//! Health and info endpoints.

use axum::extract::State;
use axum::Json;
use serde_json::{json, Value};

use crate::state::AppState;

/// GET / — Node info + economics summary.
pub async fn root(State(state): State<AppState>) -> Json<Value> {
    let height = match &state.substrate {
        Some(sub) => sub.current_height().await.unwrap_or(0),
        None => {
            let row: Option<(i64,)> = sqlx::query_as(
                "SELECT best_block_height FROM idx_chain_state WHERE id = 1"
            )
            .fetch_optional(&state.db)
            .await
            .ok()
            .flatten();
            row.map(|h| h.0 as u64).unwrap_or(0)
        }
    };

    Json(json!({
        "name": "Qubitcoin",
        "symbol": "QBC",
        "chain_id": state.chain_id,
        "version": env!("CARGO_PKG_VERSION"),
        "substrate": state.substrate.is_some(),
        "block_height": height,
        "consensus": "Proof-of-SUSY-Alignment (PoSA)",
        "max_supply": "3,300,000,000 QBC",
        "block_time": "3.3s",
        "website": "https://qbc.network",
    }))
}

/// GET /health — Health check.
pub async fn health(State(state): State<AppState>) -> Json<Value> {
    let db_ok = sqlx::query("SELECT 1")
        .execute(&state.db)
        .await
        .is_ok();

    let substrate_ok = match &state.substrate {
        Some(s) => s.system_health().await.is_some(),
        None => false,
    };

    // Check Aether Mind health
    let aether_ok = state
        .http_client
        .get(format!("{}/health", state.aether_url))
        .timeout(std::time::Duration::from_secs(3))
        .send()
        .await
        .map(|r| r.status().is_success())
        .unwrap_or(false);

    let status = match (db_ok, substrate_ok) {
        (true, true) => "healthy",
        (true, false) => "degraded",
        (false, _) => "unhealthy",
    };

    Json(json!({
        "status": status,
        "database": db_ok,
        "substrate": substrate_ok,
        "aether_mind": aether_ok,
        "timestamp": chrono::Utc::now().to_rfc3339(),
    }))
}

/// GET /info — Detailed node info.
pub async fn info(State(state): State<AppState>) -> Json<Value> {
    // Try live Substrate data first
    if let Some(sub) = &state.substrate {
        if let Some(cs) = sub.chain_state().await {
            return Json(json!({
                "chain_id": state.chain_id,
                "block_height": cs.height,
                "substrate_height": cs.substrate_height,
                "difficulty": format!("{:.6}", cs.difficulty),
                "era": cs.era,
                "total_supply": format!("{:.8}", cs.total_supply),
                "block_reward": format!("{:.8}", cs.block_reward),
                "average_block_time": 3.3,
                "consensus": "PoSA",
                "node_type": "substrate + aether-mind",
                "peers": cs.peers,
            }));
        }
    }

    // Fallback to DB
    let row: Option<(i64, String, i64, String, String)> = sqlx::query_as(
        r#"
        SELECT best_block_height, current_difficulty::text,
               current_era, total_supply::text, average_block_time::text
        FROM idx_chain_state WHERE id = 1
        "#,
    )
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    match row {
        Some((height, _difficulty, era, supply, block_time)) => {
            Json(json!({
                "chain_id": state.chain_id,
                "block_height": height,
                "difficulty": "0.500000",
                "era": era,
                "total_supply": supply,
                "average_block_time": block_time,
                "consensus": "PoSA",
                "node_type": "substrate + aether-mind",
                "warning": "DB-only mode — difficulty may be stale",
            }))
        }
        None => {
            Json(json!({
                "chain_id": state.chain_id,
                "block_height": 0,
                "status": "initializing",
            }))
        }
    }
}
