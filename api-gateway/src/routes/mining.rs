//! Mining statistics endpoints.
//!
//! Reads live mining data from Substrate RPC.
//! Historical data from CockroachDB.

use axum::extract::State;
use axum::Json;
use serde_json::{json, Value};

use crate::state::{AppState, DIFFICULTY_SCALE, FORK_OFFSET};

/// GET /mining/stats — Mining statistics (live from Substrate).
pub async fn mining_stats(State(state): State<AppState>) -> Json<Value> {
    // Get live state from Substrate
    let (difficulty, blocks_mined, height, era, peers) = match &state.substrate {
        Some(sub) => {
            match sub.chain_state().await {
                Some(cs) => (
                    format!("{:.6}", cs.difficulty),
                    cs.blocks_mined,
                    cs.height,
                    cs.era,
                    cs.peers,
                ),
                None => ("0.500000".to_string(), 0, 0, 0, 0),
            }
        }
        None => ("0.500000".to_string(), 0, 0, 0, 0),
    };

    // Get recent mining activity from DB
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

    let phi: f64 = 1.618033988749895;
    let block_reward = 15.27 / phi.powi(era as i32);

    Json(json!({
        "block_height": height,
        "current_difficulty": difficulty,
        "current_era": era,
        "current_reward": format!("{:.8}", block_reward),
        "blocks_mined_substrate": blocks_mined,
        "average_block_time": 3.3,
        "unique_miners": miner_count.map(|c| c.0).unwrap_or(0),
        "peers": peers,
        "consensus": "Proof-of-SUSY-Alignment (PoSA)",
        "mining_algorithm": "VQE (4-qubit SUSY Hamiltonian)",
        "difficulty_direction": "higher = easier",
        "fork_offset": FORK_OFFSET,
        "recent_blocks": recent,
    }))
}

/// GET /mining/difficulty — Current difficulty (live from Substrate).
pub async fn mining_difficulty(State(state): State<AppState>) -> Json<Value> {
    // Read live difficulty from Substrate
    let (difficulty_str, difficulty_raw) = match &state.substrate {
        Some(sub) => {
            match sub.current_difficulty().await {
                Some(raw) => (format!("{:.6}", raw as f64 / DIFFICULTY_SCALE), raw),
                None => ("0.500000".to_string(), 500_000),
            }
        }
        None => ("0.500000".to_string(), 500_000),
    };

    // Get recent difficulty adjustments from DB blocks
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
        "current_difficulty": difficulty_str,
        "difficulty_raw": difficulty_raw,
        "difficulty_scale": DIFFICULTY_SCALE,
        "adjustment_window": 144,
        "max_adjustment": "10%",
        "direction": "higher = easier",
        "source": if state.substrate.is_some() { "substrate_live" } else { "fallback" },
        "history": history_vals,
    }))
}
