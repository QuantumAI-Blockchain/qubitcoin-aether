//! Aether Tree endpoints — proxied to the standalone Aether service.
//!
//! The API gateway forwards /aether/* requests to the Aether service
//! (running on AETHER_SERVICE_URL, default :5001). Some data (phi, knowledge stats)
//! is also available from the indexer DB for fast reads.

use axum::extract::{Path, Query, State};
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::state::AppState;

/// GET /aether/info — Aether engine status (proxied to aether-mind V5).
pub async fn aether_info(State(state): State<AppState>) -> Json<Value> {
    proxy_to_aether(&state, "/aether/info").await
}

/// GET /aether/phi — Current Phi (consciousness) value (proxied to aether-mind V5).
pub async fn aether_phi(State(state): State<AppState>) -> Json<Value> {
    proxy_to_aether(&state, "/aether/phi").await
}

#[derive(Deserialize)]
pub struct HistoryParams {
    pub limit: Option<i64>,
}

/// GET /aether/phi/history — Phi value over time.
pub async fn aether_phi_history(
    State(state): State<AppState>,
    Query(params): Query<HistoryParams>,
) -> Json<Value> {
    let limit = params.limit.unwrap_or(100).min(1000);

    let rows: Vec<(f64, i64, i64, i64)> = sqlx::query_as(
        r#"
        SELECT phi_value, block_height, num_nodes, num_edges
        FROM phi_measurements
        ORDER BY id DESC
        LIMIT $1
        "#,
    )
    .bind(limit)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();

    let history: Vec<Value> = rows
        .into_iter()
        .rev()  // Oldest first
        .map(|(phi, height, nodes, edges)| {
            json!({
                "block": height,
                "phi": phi,
                "nodes": nodes,
                "edges": edges,
            })
        })
        .collect();

    Json(json!({ "history": history }))
}

/// GET /aether/knowledge — Knowledge graph statistics.
pub async fn aether_knowledge(State(state): State<AppState>) -> Json<Value> {
    let row: Option<(i64, i64)> = sqlx::query_as(
        r#"
        SELECT num_nodes, num_edges
        FROM phi_measurements
        ORDER BY id DESC LIMIT 1
        "#,
    )
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    let (nodes, edges) = row.unwrap_or((0, 0));

    Json(json!({
        "total_nodes": nodes,
        "total_edges": edges,
        "node_types": ["assertion", "observation", "inference", "axiom"],
        "edge_types": ["supports", "contradicts", "derives", "requires", "refines"],
    }))
}

/// GET /aether/consciousness — Consciousness metrics (live from aether-mind + gates).
pub async fn aether_consciousness(State(state): State<AppState>) -> Json<Value> {
    // Fetch live phi and gates from aether-mind in parallel
    let phi_url = format!("{}/aether/phi", state.aether_url);
    let gates_url = format!("{}/aether/gates", state.aether_url);

    // Fetch both in parallel, then parse
    let (phi_resp, gates_resp) = tokio::join!(
        state.http_client.get(&phi_url).send(),
        state.http_client.get(&gates_url).send(),
    );
    let phi_data: Option<Value> = match phi_resp {
        Ok(resp) => resp.json().await.ok(),
        Err(_) => None,
    };
    let gates_data: Option<Value> = match gates_resp {
        Ok(resp) => resp.json().await.ok(),
        Err(_) => None,
    };

    let phi = phi_data.as_ref()
        .and_then(|d| d["phi"].as_f64())
        .unwrap_or(0.0);
    let knowledge_nodes = phi_data.as_ref()
        .and_then(|d| d["knowledge_vectors"].as_i64())
        .unwrap_or(0);
    let phi_micro = phi_data.as_ref()
        .and_then(|d| d["phi_history_recent"].as_array())
        .and_then(|arr| arr.first())
        .and_then(|h| h["phi_micro"].as_f64())
        .unwrap_or(0.0);
    let phi_meso = phi_data.as_ref()
        .and_then(|d| d["phi_history_recent"].as_array())
        .and_then(|arr| arr.first())
        .and_then(|h| h["phi_meso"].as_f64())
        .unwrap_or(0.0);
    let phi_macro = phi_data.as_ref()
        .and_then(|d| d["phi_history_recent"].as_array())
        .and_then(|arr| arr.first())
        .and_then(|h| h["phi_macro"].as_f64())
        .unwrap_or(0.0);
    let chain_height = phi_data.as_ref()
        .and_then(|d| d["chain_height"].as_i64())
        .unwrap_or(0);

    let gates_passed = gates_data.as_ref()
        .and_then(|d| d["gates_passed"].as_i64())
        .unwrap_or(0);
    let gates_total = gates_data.as_ref()
        .and_then(|d| d["gates_total"].as_i64())
        .unwrap_or(10);
    let phi_ceiling = gates_data.as_ref()
        .and_then(|d| d["phi_ceiling"].as_f64())
        .unwrap_or(0.0);
    let gates = gates_data.as_ref()
        .and_then(|d| d.get("gates").cloned());

    Json(json!({
        "phi": phi,
        "phi_micro": phi_micro,
        "phi_meso": phi_meso,
        "phi_macro": phi_macro,
        "threshold": 3.0,
        "above_threshold": phi >= 3.0,
        "knowledge_nodes": knowledge_nodes,
        "knowledge_edges": 0,
        "blocks_processed": chain_height,
        "consciousness_events": 0,
        "gates_passed": gates_passed,
        "gates_total": gates_total,
        "gate_ceiling": phi_ceiling,
        "gates": gates,
    }))
}

/// Proxy an Aether endpoint to the standalone Aether service.
async fn proxy_to_aether(state: &AppState, path: &str) -> Json<Value> {
    let url = format!("{}{}", state.aether_url, path);
    match state.http_client.get(&url).send().await {
        Ok(resp) => {
            match resp.json::<Value>().await {
                Ok(body) => Json(body),
                Err(_) => Json(json!({ "error": "Invalid response from Aether service" })),
            }
        }
        Err(_) => Json(json!({ "error": "Aether service unavailable" })),
    }
}

/// POST /aether/chat/message — Forward chat to Aether service.
pub async fn aether_chat(
    State(state): State<AppState>,
    Json(body): Json<Value>,
) -> Json<Value> {
    let url = format!("{}/aether/chat", state.aether_url);
    match state
        .http_client
        .post(&url)
        .json(&body)
        .send()
        .await
    {
        Ok(resp) => match resp.json::<Value>().await {
            Ok(data) => Json(data),
            Err(_) => Json(json!({ "error": "Invalid response from Aether service" })),
        },
        Err(_) => Json(json!({ "error": "Aether service unavailable" })),
    }
}

/// POST /aether/chat/session — Create or resume a chat session.
pub async fn aether_chat_session(
    State(_state): State<AppState>,
) -> Json<Value> {
    let session_id = uuid::Uuid::new_v4().to_string();
    Json(json!({
        "session_id": session_id,
        "free_messages_remaining": 5,
        "status": "active",
    }))
}

/// GET /aether/chat/fee — Check fee for chat message.
pub async fn aether_chat_fee(
    Query(_params): Query<HistoryParams>,
) -> Json<Value> {
    Json(json!({
        "fee_required": false,
        "fee_amount": 0.0,
        "currency": "QBC",
        "reason": "v5_free_tier",
    }))
}

/// GET /aether/chat/history/{session_id} — Forward to Aether service.
pub async fn aether_chat_history(
    State(state): State<AppState>,
    Path(session_id): Path<String>,
) -> Json<Value> {
    proxy_to_aether(&state, &format!("/aether/chat/history/{}", session_id)).await
}

/// GET /aether/pot — Proof-of-Thought attestation (proxied to aether-mind V5).
pub async fn aether_pot(State(state): State<AppState>) -> Json<Value> {
    proxy_to_aether(&state, "/aether/pot").await
}

/// GET /aether/neural-payload — Neural training payload for block inclusion.
pub async fn aether_neural_payload(State(state): State<AppState>) -> Json<Value> {
    proxy_to_aether(&state, "/aether/neural-payload").await
}

/// GET /aether/health — Aether Mind health check (proxied).
pub async fn aether_health(State(state): State<AppState>) -> Json<Value> {
    proxy_to_aether(&state, "/health").await
}

/// GET /aether/gradients — Gradient aggregation status (proxied to aether-mind V5).
pub async fn aether_gradients(State(state): State<AppState>) -> Json<Value> {
    proxy_to_aether(&state, "/aether/gradients").await
}

/// POST /aether/gradients — Submit gradients (proxied to aether-mind V5).
pub async fn aether_gradients_submit(
    State(state): State<AppState>,
    Json(body): Json<Value>,
) -> Json<Value> {
    let url = format!("{}/aether/gradients", state.aether_url);
    match state.http_client.post(&url).json(&body).send().await {
        Ok(resp) => match resp.json::<Value>().await {
            Ok(data) => Json(data),
            Err(_) => Json(json!({ "error": "Invalid response from Aether service" })),
        },
        Err(_) => Json(json!({ "error": "Aether service unavailable" })),
    }
}

/// GET /aether/rewards/pool — Gradient reward pool status.
pub async fn aether_rewards_pool(State(state): State<AppState>) -> Json<Value> {
    proxy_to_aether(&state, "/aether/rewards/pool").await
}

/// GET /aether/rewards/{miner_id} — Miner reward balance.
pub async fn aether_rewards_miner(
    State(state): State<AppState>,
    Path(miner_id): Path<String>,
) -> Json<Value> {
    proxy_to_aether(&state, &format!("/aether/rewards/{}", miner_id)).await
}

/// POST /aether/rewards/claim — Claim gradient rewards.
pub async fn aether_rewards_claim(
    State(state): State<AppState>,
    Json(body): Json<Value>,
) -> Json<Value> {
    let url = format!("{}/aether/rewards/claim", state.aether_url);
    match state.http_client.post(&url).json(&body).send().await {
        Ok(resp) => match resp.json::<Value>().await {
            Ok(data) => Json(data),
            Err(_) => Json(json!({ "error": "Invalid response from Aether service" })),
        },
        Err(_) => Json(json!({ "error": "Aether service unavailable" })),
    }
}
