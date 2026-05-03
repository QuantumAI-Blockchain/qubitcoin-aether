//! Chain and block explorer endpoints.
//!
//! Live chain state reads directly from Substrate RPC.
//! Historical block data reads from CockroachDB (populated by Python node up to fork).

use axum::extract::{Path, Query, State};
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::state::{AppState, FORK_OFFSET};

/// GET /block/{height} — Get block by height.
///
/// For heights <= FORK_OFFSET: reads from CockroachDB (pre-fork Python blocks).
/// For heights > FORK_OFFSET: reads live from Substrate RPC.
pub async fn get_block_by_height(
    State(state): State<AppState>,
    Path(height): Path<i64>,
) -> Json<Value> {
    let fork_offset = FORK_OFFSET as i64;

    // Post-fork blocks: read from Substrate RPC
    if height > fork_offset {
        let substrate_num = (height - fork_offset) as u64;
        if let Some(block) = get_substrate_block(&state, substrate_num, height).await {
            return Json(block);
        }
        return Json(json!({ "error": "Block not found" }));
    }

    // Pre-fork blocks: read from CockroachDB
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
                "height": h,
                "parent_hash": parent.unwrap_or_default(),
                "difficulty": diff,
                "energy": energy.unwrap_or_default(),
                "miner_address": miner.map(|m| format!("0x{}", hex::encode(&m))),
                "era": era,
                "source": "cockroachdb",
            }))
        }
        None => Json(json!({ "error": "Block not found" })),
    }
}

/// Fetch a block from Substrate RPC and format for the explorer.
async fn get_substrate_block(state: &AppState, substrate_num: u64, display_height: i64) -> Option<Value> {
    let sub = state.substrate.as_ref()?;
    let hash = sub.chain_get_block_hash(substrate_num).await?;
    let block_data = sub.chain_get_block(&hash).await?;

    let header = block_data.get("block")?.get("header")?;
    let parent_hash = header.get("parentHash")?.as_str().unwrap_or_default();
    let extrinsics = block_data.get("block")?.get("extrinsics")?.as_array();
    let tx_count = extrinsics.map(|e| e.len()).unwrap_or(0);

    Some(json!({
        "block_hash": hash,
        "block_height": display_height,
        "height": display_height,
        "substrate_number": substrate_num,
        "parent_hash": parent_hash,
        "state_root": header.get("stateRoot").and_then(|v| v.as_str()).unwrap_or_default(),
        "extrinsics_root": header.get("extrinsicsRoot").and_then(|v| v.as_str()).unwrap_or_default(),
        "tx_count": tx_count,
        "transactions": [],
        "era": 0,
        "difficulty": 0.5,
        "timestamp": std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0),
        "source": "substrate",
    }))
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

/// GET /chain/info — Chain statistics (live from Substrate).
pub async fn chain_info(State(state): State<AppState>) -> Json<Value> {
    // Read live state from Substrate first
    if let Some(sub) = &state.substrate {
        if let Some(cs) = sub.chain_state().await {
            return Json(json!({
                "chain_id": state.chain_id,
                "height": cs.height,
                "block_height": cs.height,
                "substrate_height": cs.substrate_height,
                "total_blocks": cs.blocks_mined,
                "total_supply": format!("{:.8}", cs.total_supply),
                "current_era": cs.era,
                "current_reward": format!("{:.8}", cs.block_reward),
                "difficulty": format!("{:.6}", cs.difficulty),
                "current_difficulty": format!("{:.6}", cs.difficulty),
                "difficulty_raw": cs.difficulty_raw,
                "average_block_time": 3.3,
                "target_block_time": 3.3,
                "max_supply": 3_300_000_000.0_f64,
                "consensus": "Proof-of-SUSY-Alignment",
                "substrate_mode": true,
                "peers": cs.peers,
                "is_syncing": cs.is_syncing,
                "fork_offset": FORK_OFFSET,
            }));
        }
    }

    // Fallback: DB-only mode (no Substrate connection)
    let row: Option<(i64, String, String)> = sqlx::query_as(
        r#"
        SELECT best_block_height, total_supply::text, current_difficulty::text
        FROM idx_chain_state WHERE id = 1
        "#,
    )
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    match row {
        Some((height, supply, _diff)) => {
            Json(json!({
                "chain_id": state.chain_id,
                "height": height,
                "block_height": height,
                "total_supply": supply,
                "current_era": 0,
                "current_reward": "15.27000000",
                "difficulty": "0.500000",
                "current_difficulty": "0.500000",
                "average_block_time": 3.3,
                "target_block_time": 3.3,
                "max_supply": 3_300_000_000.0_f64,
                "consensus": "Proof-of-SUSY-Alignment",
                "substrate_mode": false,
                "peers": 0,
                "warning": "Running in DB-only mode — Substrate not connected",
            }))
        }
        None => {
            Json(json!({
                "chain_id": state.chain_id,
                "height": 0,
                "block_height": 0,
                "status": "initializing",
                "substrate_mode": false,
            }))
        }
    }
}

/// GET /chain/tip — Latest block info.
pub async fn chain_tip(State(state): State<AppState>) -> Json<Value> {
    // Try Substrate: get the actual substrate block number, then add fork offset
    if let Some(sub) = &state.substrate {
        if let Some(substrate_num) = sub.substrate_block_number().await {
            let display_height = FORK_OFFSET as i64 + substrate_num as i64;
            return get_block_by_height(State(state), Path(display_height)).await;
        }
    }

    // Fallback to DB
    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT best_block_height FROM idx_chain_state WHERE id = 1",
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
