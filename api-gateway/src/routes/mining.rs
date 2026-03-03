//! Mining statistics endpoints.
//!
//! Reads mining data from CockroachDB (populated by the block indexer)
//! and Substrate RPC (for live difficulty).

use axum::extract::State;
use axum::Json;
use serde_json::{json, Value};

use crate::state::AppState;

/// GET /mining/stats — Mining statistics.
pub async fn mining_stats(State(state): State<AppState>) -> Json<Value> {
    // Get stats from chain_state + blocks table
    let chain_row: Option<(i64, String, String)> = sqlx::query_as(
        r#"
        SELECT best_block_height, current_difficulty::text,
               average_block_time::text
        FROM chain_state WHERE id = 1
        "#,
    )
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    // Get recent mining activity
    let recent_blocks: Vec<(i64, Option<Vec<u8>>, String, String)> = sqlx::query_as(
        r#"
        SELECT block_height, miner_address,
               achieved_eigenvalue::text, actual_reward::text
        FROM blocks
        WHERE miner_address IS NOT NULL
        ORDER BY block_height DESC
        LIMIT 10
        "#,
    )
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();

    // Get unique miners count
    let miner_count: Option<(i64,)> = sqlx::query_as(
        "SELECT COUNT(DISTINCT miner_address) FROM blocks WHERE miner_address IS NOT NULL",
    )
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    let (height, difficulty, block_time) = chain_row
        .unwrap_or((0, "1000000".to_string(), "3.3".to_string()));

    let recent: Vec<Value> = recent_blocks
        .into_iter()
        .map(|(h, miner, energy, reward)| {
            json!({
                "block_height": h,
                "miner": miner.map(|m| format!("0x{}", hex::encode(&m))),
                "energy": energy,
                "reward": reward,
            })
        })
        .collect();

    Json(json!({
        "block_height": height,
        "current_difficulty": difficulty,
        "average_block_time": block_time,
        "unique_miners": miner_count.map(|c| c.0).unwrap_or(0),
        "consensus": "Proof-of-SUSY-Alignment (PoSA)",
        "mining_algorithm": "VQE (4-qubit SUSY Hamiltonian)",
        "recent_blocks": recent,
    }))
}

/// GET /mining/difficulty — Current difficulty and history.
pub async fn mining_difficulty(State(state): State<AppState>) -> Json<Value> {
    // Query difficulty from Substrate storage
    let current = state
        .substrate
        .rpc
        .chain_get_finalized_head()
        .await
        .ok();

    let difficulty: Option<(String,)> = sqlx::query_as(
        "SELECT current_difficulty::text FROM chain_state WHERE id = 1",
    )
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    // Get recent difficulty adjustments from blocks
    let history: Vec<(i64, String)> = sqlx::query_as(
        r#"
        SELECT block_height, difficulty::text
        FROM blocks
        ORDER BY block_height DESC
        LIMIT 144
        "#,
    )
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();

    let history_vals: Vec<Value> = history
        .into_iter()
        .map(|(h, d)| json!({"height": h, "difficulty": d}))
        .collect();

    Json(json!({
        "current_difficulty": difficulty.map(|d| d.0).unwrap_or_else(|| "1000000".to_string()),
        "adjustment_window": 144,
        "max_adjustment": "10%",
        "direction": "higher = easier",
        "history": history_vals,
    }))
}
