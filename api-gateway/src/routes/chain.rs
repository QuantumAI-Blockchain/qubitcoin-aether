//! Chain and block explorer endpoints.
//!
//! Reads from CockroachDB (populated by the block indexer).

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
        Vec<u8>, i64, Vec<u8>, String, String, Option<Vec<u8>>,
        i32, String, String, i32,
    )> = sqlx::query_as(
        r#"
        SELECT block_hash, block_height, previous_hash,
               difficulty::text, achieved_eigenvalue::text,
               miner_address, era, actual_reward::text,
               total_fees::text, transaction_count
        FROM blocks WHERE block_height = $1
        "#,
    )
    .bind(height)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    match row {
        Some((hash, h, parent, diff, energy, miner, era, reward, fees, tx_count)) => {
            Json(json!({
                "block_hash": format!("0x{}", hex::encode(&hash)),
                "block_height": h,
                "parent_hash": format!("0x{}", hex::encode(&parent)),
                "difficulty": diff,
                "energy": energy,
                "miner_address": miner.map(|m| format!("0x{}", hex::encode(&m))),
                "era": era,
                "reward": reward,
                "total_fees": fees,
                "transaction_count": tx_count,
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
    let hash_bytes = hex::decode(hash.trim_start_matches("0x")).unwrap_or_default();

    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT block_height FROM blocks WHERE block_hash = $1",
    )
    .bind(&hash_bytes)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    match row {
        Some((height,)) => {
            // Reuse get_block_by_height
            get_block_by_height(State(state), Path(height)).await
        }
        None => Json(json!({ "error": "Block not found" })),
    }
}

/// GET /chain/info — Chain statistics.
pub async fn chain_info(State(state): State<AppState>) -> Json<Value> {
    let row: Option<(
        i64, i64, i64, String, i32, String, String,
    )> = sqlx::query_as(
        r#"
        SELECT best_block_height, total_blocks, total_transactions,
               total_supply::text, current_era, current_difficulty::text,
               average_block_time::text
        FROM chain_state WHERE id = 1
        "#,
    )
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    match row {
        Some((height, blocks, txs, supply, era, diff, bt)) => {
            Json(json!({
                "block_height": height,
                "total_blocks": blocks,
                "total_transactions": txs,
                "total_supply": supply,
                "current_era": era,
                "current_difficulty": diff,
                "average_block_time": bt,
                "chain_id": state.chain_id,
                "consensus": "Proof-of-SUSY-Alignment",
                "target_block_time": 3.3,
            }))
        }
        None => Json(json!({ "block_height": 0, "status": "initializing" })),
    }
}

/// GET /chain/tip — Latest block info.
pub async fn chain_tip(State(state): State<AppState>) -> Json<Value> {
    let row: Option<(Vec<u8>, i64)> = sqlx::query_as(
        "SELECT best_block_hash, best_block_height FROM chain_state WHERE id = 1",
    )
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    match row {
        Some((hash, height)) => {
            get_block_by_height(State(state), Path(height)).await
        }
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

    let rows: Vec<(Vec<u8>, i64, Option<Vec<u8>>, i32, String, String)> = sqlx::query_as(
        r#"
        SELECT block_hash, block_height, miner_address,
               transaction_count, actual_reward::text, timestamp::text
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
        .map(|(hash, h, miner, tx_count, reward, ts)| {
            json!({
                "block_hash": format!("0x{}", hex::encode(&hash)),
                "block_height": h,
                "miner": miner.map(|m| format!("0x{}", hex::encode(&m))),
                "transaction_count": tx_count,
                "reward": reward,
                "timestamp": ts,
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
    let mut cumulative: f64 = 33_000_000.0; // Genesis premine

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

/// GET /susy-database — Solved SUSY Hamiltonians (scientific database).
pub async fn susy_database(
    State(state): State<AppState>,
    Query(params): Query<PaginationParams>,
) -> Json<Value> {
    let limit = params.limit.unwrap_or(20).min(100);
    let offset = params.offset.unwrap_or(0);

    let rows: Vec<(i64, String, Option<Vec<u8>>, String)> = sqlx::query_as(
        r#"
        SELECT block_height, ground_state_energy::text,
               miner_address, discovered_timestamp::text
        FROM susy_solutions
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
        .map(|(h, energy, miner, ts)| {
            json!({
                "block_height": h,
                "ground_state_energy": energy,
                "miner": miner.map(|m| format!("0x{}", hex::encode(&m))),
                "timestamp": ts,
            })
        })
        .collect();

    Json(json!({ "solutions": solutions, "count": solutions.len() }))
}
