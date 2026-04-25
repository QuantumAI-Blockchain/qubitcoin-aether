//! Chain and block explorer endpoints.
//!
//! Reads from CockroachDB (populated by the Python node / indexer).

use axum::extract::{Path, Query, State};
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::state::AppState;

/// GET /block/{height} — Get block by height.
pub async fn get_block_by_height(
    State(state): State<AppState>,
    Path(height): Path<i64>,
) -> Json<Value> {
    let row: Option<(
        String, i64, Option<String>, f64, Option<String>,
        Option<Vec<u8>>, i32,
    )> = sqlx::query_as(
        r#"
        SELECT block_hash, block_height, prev_hash,
               difficulty, achieved_eigenvalue::text,
               miner_address, era
        FROM blocks WHERE block_height = $1
        "#,
    )
    .bind(height)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    match row {
        Some((hash, h, parent, diff, energy, miner, era)) => {
            Json(json!({
                "block_hash": hash,
                "block_height": h,
                "parent_hash": parent.unwrap_or_default(),
                "difficulty": diff,
                "energy": energy.unwrap_or_default(),
                "miner_address": miner.map(|m| format!("0x{}", hex::encode(&m))),
                "era": era,
            }))
        }
        None => Json(json!({ "error": "Block not found" })),
    }
}

/// GET /block/hash/{hash} — Get block by hash.
pub async fn get_block_by_hash(
    State(state): State<AppState>,
    Path(hash): Path<String>,
) -> Json<Value> {
    let hash_clean = hash.trim_start_matches("0x");

    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT block_height FROM blocks WHERE block_hash = $1",
    )
    .bind(hash_clean)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    match row {
        Some((height,)) => get_block_by_height(State(state), Path(height)).await,
        None => Json(json!({ "error": "Block not found" })),
    }
}

/// GET /chain/info — Chain statistics.
pub async fn chain_info(State(state): State<AppState>) -> Json<Value> {
    let row: Option<(
        i64, i64, i64, String, i64, String, String,
    )> = sqlx::query_as(
        r#"
        SELECT best_block_height, total_blocks, total_transactions,
               total_supply::text, current_era, current_difficulty::text,
               average_block_time::text
        FROM idx_chain_state WHERE id = 1
        "#,
    )
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    match row {
        Some((height, blocks, txs, supply, era, diff, bt)) => {
            Json(json!({
                "chain_id": state.chain_id,
                "height": height,
                "block_height": height,
                "total_blocks": blocks,
                "total_transactions": txs,
                "total_supply": supply,
                "current_era": era,
                "current_reward": 15.27_f64 / 1.618033988749895_f64.powi(era as i32),
                "difficulty": diff,
                "current_difficulty": diff,
                "average_block_time": bt,
                "target_block_time": 3.3,
                "max_supply": 3300000000.0_f64,
                "consensus": "Proof-of-SUSY-Alignment",
                "substrate_mode": true,
            }))
        }
        None => Json(json!({
            "chain_id": state.chain_id,
            "height": 0,
            "block_height": 0,
            "status": "initializing",
        })),
    }
}

/// GET /chain/tip — Latest block info.
pub async fn chain_tip(State(state): State<AppState>) -> Json<Value> {
    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT best_block_height FROM chain_state WHERE id = 1",
    )
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    match row {
        Some((height,)) => get_block_by_height(State(state), Path(height)).await,
        None => Json(json!({ "block_height": 0 })),
    }
}

#[derive(Deserialize)]
pub struct PaginationParams {
    pub limit: Option<i64>,
    pub offset: Option<i64>,
}

/// GET /chain/blocks — List recent blocks.
pub async fn list_blocks(
    State(state): State<AppState>,
    Query(params): Query<PaginationParams>,
) -> Json<Value> {
    let limit = params.limit.unwrap_or(20).min(100);
    let offset = params.offset.unwrap_or(0);

    let rows: Vec<(String, i64, Option<Vec<u8>>, i32, f64)> = sqlx::query_as(
        r#"
        SELECT block_hash, block_height, miner_address,
               era, difficulty
        FROM blocks
        ORDER BY block_height DESC
        LIMIT $1 OFFSET $2
        "#,
    )
    .bind(limit)
    .bind(offset)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();

    let blocks: Vec<Value> = rows
        .into_iter()
        .map(|(hash, h, miner, era, diff)| {
            json!({
                "block_hash": hash,
                "block_height": h,
                "miner": miner.map(|m| format!("0x{}", hex::encode(&m))),
                "era": era,
                "difficulty": diff,
            })
        })
        .collect();

    Json(json!({ "blocks": blocks, "count": blocks.len() }))
}

/// GET /economics/emission — Emission schedule.
pub async fn emission_schedule() -> Json<Value> {
    let phi: f64 = 1.618033988749895;
    let initial_reward: f64 = 15.27;
    let halving_interval: u64 = 15_474_020;

    let mut eras = Vec::new();
    let mut cumulative: f64 = 33_000_000.0;

    for era in 0..33 {
        let reward = initial_reward / phi.powi(era);
        let blocks = halving_interval;
        let era_supply = blocks as f64 * reward;
        cumulative += era_supply;

        eras.push(json!({
            "era": era,
            "block_reward": format!("{:.8}", reward),
            "era_blocks": blocks,
            "era_supply": format!("{:.2}", era_supply),
            "cumulative_supply": format!("{:.2}", cumulative.min(3_300_000_000.0)),
        }));

        if cumulative >= 3_300_000_000.0 {
            break;
        }
    }

    Json(json!({
        "max_supply": "3,300,000,000",
        "genesis_premine": "33,000,000",
        "halving_interval": halving_interval,
        "halving_type": "phi (golden ratio)",
        "eras": eras,
    }))
}

/// GET /susy-database — Solved SUSY Hamiltonians.
pub async fn susy_database(
    State(state): State<AppState>,
    Query(params): Query<PaginationParams>,
) -> Json<Value> {
    let limit = params.limit.unwrap_or(20).min(100);
    let offset = params.offset.unwrap_or(0);

    let rows: Vec<(i64, f64)> = sqlx::query_as(
        r#"
        SELECT block_height, difficulty
        FROM blocks
        WHERE achieved_eigenvalue IS NOT NULL
        ORDER BY block_height DESC
        LIMIT $1 OFFSET $2
        "#,
    )
    .bind(limit)
    .bind(offset)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();

    let solutions: Vec<Value> = rows
        .into_iter()
        .map(|(h, diff)| {
            json!({
                "block_height": h,
                "difficulty": diff,
            })
        })
        .collect();

    Json(json!({ "solutions": solutions, "count": solutions.len() }))
}
