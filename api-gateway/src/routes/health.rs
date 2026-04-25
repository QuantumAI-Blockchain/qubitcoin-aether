//! Health and info endpoints.

use axum::extract::State;
use axum::Json;
use serde_json::{json, Value};

use crate::state::AppState;

/// GET / — Node info + economics summary.
pub async fn root(State(state): State<AppState>) -> Json<Value> {
    let height: Option<(i64,)> = sqlx::query_as(
        "SELECT best_block_height FROM idx_chain_state WHERE id = 1"
    )
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    Json(json!({
        "name": "Qubitcoin",
        "symbol": "QBC",
        "chain_id": state.chain_id,
        "version": "1.0.0",
        "substrate": true,
        "block_height": height.map(|h| h.0).unwrap_or(0),
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
        Some(s) => s.rpc.chain_get_finalized_head().await.is_ok(),
        None => false,
    };

    let status = if db_ok { "healthy" } else { "degraded" };

    Json(json!({
        "status": status,
        "database": db_ok,
        "substrate": substrate_ok,
        "aether_mind": true,
        "timestamp": chrono::Utc::now().to_rfc3339(),
    }))
}

/// GET /info — Detailed node info.
pub async fn info(State(state): State<AppState>) -> Json<Value> {
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
        Some((height, difficulty, era, supply, block_time)) => {
            Json(json!({
                "chain_id": state.chain_id,
                "block_height": height,
                "difficulty": difficulty,
                "era": era,
                "total_supply": supply,
                "average_block_time": block_time,
                "consensus": "PoSA",
                "node_type": "substrate + aether-mind",
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
