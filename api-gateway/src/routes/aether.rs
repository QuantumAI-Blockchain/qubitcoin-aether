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

/// GET /aether/consciousness — Consciousness metrics.
pub async fn aether_consciousness(State(state): State<AppState>) -> Json<Value> {
    let phi_row: Option<(f64, f64, f64, i64, i64, i64)> = sqlx::query_as(
        r#"
        SELECT phi_value, integration_score, differentiation_score,
               num_nodes, num_edges, block_height
        FROM phi_measurements
        ORDER BY id DESC LIMIT 1
        "#,
    )
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    let events_count: Option<(i64,)> = sqlx::query_as(
        "SELECT COUNT(*) FROM consciousness_events",
    )
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    match phi_row {
        Some((phi, integration, differentiation, nodes, edges, height)) => {
            Json(json!({
                "phi": phi,
                "threshold": 3.0,
                "above_threshold": phi >= 3.0,
                "integration": integration,
                "differentiation": differentiation,
                "knowledge_nodes": nodes,
                "knowledge_edges": edges,
                "consciousness_events": events_count.map(|c| c.0).unwrap_or(0),
                "blocks_processed": height,
            }))
        }
        None => {
            Json(json!({
                "phi": 0.0,
                "threshold": 3.0,
                "above_threshold": false,
                "knowledge_nodes": 0,
                "knowledge_edges": 0,
                "consciousness_events": 0,
                "blocks_processed": 0,
            }))
        }
    }
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
