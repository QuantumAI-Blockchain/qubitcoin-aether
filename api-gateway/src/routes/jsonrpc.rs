//! Ethereum-compatible JSON-RPC handler.
//!
//! Implements eth_*, net_*, web3_* methods for MetaMask/Web3 compatibility.
//! Data is read from CockroachDB (block data) and Substrate RPC (live state).
//!
//! POST / (with Content-Type: application/json)
//! POST /jsonrpc
//!
//! Request:  {"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1}
//! Response: {"jsonrpc": "2.0", "result": "0xce7", "id": 1}

use axum::extract::State;
use axum::Json;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tracing::debug;

use crate::state::AppState;

#[derive(Deserialize)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub method: String,
    #[serde(default)]
    pub params: Vec<Value>,
    pub id: Value,
}

#[derive(Serialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<Value>,
    pub id: Value,
}

/// Handle a JSON-RPC request (single or batch).
pub async fn handle_jsonrpc(
    State(state): State<AppState>,
    Json(request): Json<Value>,
) -> Json<Value> {
    // Check if it's a batch request (array)
    if let Value::Array(requests) = &request {
        let mut responses = Vec::new();
        for req in requests {
            if let Ok(rpc_req) = serde_json::from_value::<JsonRpcRequest>(req.clone()) {
                responses.push(dispatch_method(&state, rpc_req).await);
            }
        }
        return Json(json!(responses));
    }

    // Single request
    match serde_json::from_value::<JsonRpcRequest>(request) {
        Ok(rpc_req) => {
            let response = dispatch_method(&state, rpc_req).await;
            Json(serde_json::to_value(response).unwrap_or_default())
        }
        Err(_) => Json(json!({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": "Parse error"},
            "id": null,
        })),
    }
}

async fn dispatch_method(state: &AppState, req: JsonRpcRequest) -> JsonRpcResponse {
    debug!("JSON-RPC: {}", req.method);

    let result = match req.method.as_str() {
        "eth_chainId" => Ok(json!(format!("0x{:x}", state.chain_id))),
        "net_version" => Ok(json!(state.chain_id.to_string())),
        "web3_clientVersion" => Ok(json!("Qubitcoin/1.0.0/Substrate")),

        "eth_blockNumber" => eth_block_number(state).await,
        "eth_getBlockByNumber" => eth_get_block_by_number(state, &req.params).await,
        "eth_getBlockByHash" => eth_get_block_by_hash(state, &req.params).await,
        "eth_getBalance" => eth_get_balance(state, &req.params).await,
        "eth_getTransactionCount" => eth_get_transaction_count(state, &req.params).await,
        "eth_getCode" => eth_get_code(state, &req.params).await,
        "eth_getStorageAt" => Ok(json!("0x0")), // Stub
        "eth_getTransactionByHash" => eth_get_tx_by_hash(state, &req.params).await,
        "eth_getTransactionReceipt" => eth_get_tx_receipt(state, &req.params).await,
        "eth_sendRawTransaction" => Ok(json!("0x0")), // Requires Substrate proxy
        "eth_sendTransaction" => Ok(json!("0x0")),     // Requires Substrate proxy
        "eth_call" => Ok(json!("0x")),                 // Stub — needs QVM
        "eth_estimateGas" => Ok(json!("0x5208")),      // 21000 default
        "eth_gasPrice" => Ok(json!("0x3b9aca00")),     // 1 gwei
        "eth_getLogs" => Ok(json!([])),                 // Stub
        "eth_mining" => Ok(json!(false)),
        "eth_hashrate" => Ok(json!("0x0")),

        _ => Err(json!({
            "code": -32601,
            "message": format!("Method not found: {}", req.method),
        })),
    };

    match result {
        Ok(value) => JsonRpcResponse {
            jsonrpc: "2.0".to_string(),
            result: Some(value),
            error: None,
            id: req.id,
        },
        Err(error) => JsonRpcResponse {
            jsonrpc: "2.0".to_string(),
            result: None,
            error: Some(error),
            id: req.id,
        },
    }
}

// ═══════════════════════════════════════════════════════════════════════
// Method Implementations
// ═══════════════════════════════════════════════════════════════════════

async fn eth_block_number(state: &AppState) -> Result<Value, Value> {
    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT best_block_height FROM idx_chain_state WHERE id = 1",
    )
    .fetch_optional(&state.db)
    .await
    .map_err(|_| json!({"code": -32000, "message": "Database error"}))?;

    let height = row.map(|r| r.0).unwrap_or(0);
    Ok(json!(format!("0x{:x}", height)))
}

async fn eth_get_block_by_number(
    state: &AppState,
    params: &[Value],
) -> Result<Value, Value> {
    let block_tag = params.first().and_then(|v| v.as_str()).unwrap_or("latest");

    let height: i64 = if block_tag == "latest" || block_tag == "pending" {
        let row: Option<(i64,)> = sqlx::query_as(
            "SELECT best_block_height FROM idx_chain_state WHERE id = 1",
        )
        .fetch_optional(&state.db)
        .await
        .map_err(|_| json!({"code": -32000, "message": "Database error"}))?;
        row.map(|r| r.0).unwrap_or(0)
    } else if block_tag == "earliest" {
        0
    } else {
        i64::from_str_radix(block_tag.trim_start_matches("0x"), 16).unwrap_or(0)
    };

    get_block_as_eth(state, height).await
}

async fn eth_get_block_by_hash(
    state: &AppState,
    params: &[Value],
) -> Result<Value, Value> {
    let hash_hex = params.first().and_then(|v| v.as_str()).unwrap_or("");
    let hash_clean = hash_hex.trim_start_matches("0x");

    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT block_height FROM blocks WHERE block_hash = $1",
    )
    .bind(hash_clean)
    .fetch_optional(&state.db)
    .await
    .map_err(|_| json!({"code": -32000, "message": "Database error"}))?;

    match row {
        Some((height,)) => get_block_as_eth(state, height).await,
        None => Ok(Value::Null),
    }
}

async fn get_block_as_eth(state: &AppState, height: i64) -> Result<Value, Value> {
    let row: Option<(String, Option<String>, f64)> = sqlx::query_as(
        r#"
        SELECT block_hash, prev_hash, created_at
        FROM blocks WHERE block_height = $1
        "#,
    )
    .bind(height)
    .fetch_optional(&state.db)
    .await
    .map_err(|_| json!({"code": -32000, "message": "Database error"}))?;

    match row {
        Some((hash, parent, created_at)) => {
            Ok(json!({
                "number": format!("0x{:x}", height),
                "hash": format!("0x{}", hash),
                "parentHash": format!("0x{}", parent.unwrap_or_default()),
                "nonce": "0x0",
                "sha3Uncles": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "logsBloom": "0x".to_string() + &"0".repeat(512),
                "transactionsRoot": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "stateRoot": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "receiptsRoot": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "miner": "0x0000000000000000000000000000000000000000",
                "difficulty": "0x1",
                "totalDifficulty": "0x1",
                "extraData": "0x",
                "size": "0x0",
                "gasLimit": format!("0x{:x}", 30_000_000u64),
                "gasUsed": "0x0",
                "timestamp": format!("0x{:x}", created_at as u64),
                "transactions": [],
                "uncles": [],
            }))
        }
        None => Ok(Value::Null),
    }
}

async fn eth_get_balance(
    state: &AppState,
    params: &[Value],
) -> Result<Value, Value> {
    let address = params.first().and_then(|v| v.as_str()).unwrap_or("");
    let addr_bytes = hex::decode(address.trim_start_matches("0x")).unwrap_or_default();

    let row: Option<(String,)> = sqlx::query_as(
        "SELECT balance::text FROM addresses WHERE address = $1",
    )
    .bind(&addr_bytes)
    .fetch_optional(&state.db)
    .await
    .map_err(|_| json!({"code": -32000, "message": "Database error"}))?;

    let balance_str = row.map(|r| r.0).unwrap_or_else(|| "0".to_string());
    let balance: f64 = balance_str.parse().unwrap_or(0.0);
    // Convert QBC to wei-like representation (multiply by 10^18 for MetaMask)
    let wei = (balance * 1e18) as u128;

    Ok(json!(format!("0x{:x}", wei)))
}

async fn eth_get_transaction_count(
    state: &AppState,
    params: &[Value],
) -> Result<Value, Value> {
    let address = params.first().and_then(|v| v.as_str()).unwrap_or("");
    let addr_bytes = hex::decode(address.trim_start_matches("0x")).unwrap_or_default();

    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT tx_count FROM addresses WHERE address = $1",
    )
    .bind(&addr_bytes)
    .fetch_optional(&state.db)
    .await
    .map_err(|_| json!({"code": -32000, "message": "Database error"}))?;

    let count = row.map(|r| r.0).unwrap_or(0);
    Ok(json!(format!("0x{:x}", count)))
}

async fn eth_get_code(
    state: &AppState,
    params: &[Value],
) -> Result<Value, Value> {
    // No smart contracts in the indexer DB currently
    // This would need QVM state
    Ok(json!("0x"))
}

async fn eth_get_tx_by_hash(
    state: &AppState,
    params: &[Value],
) -> Result<Value, Value> {
    let hash_hex = params.first().and_then(|v| v.as_str()).unwrap_or("");
    let hash_bytes = hex::decode(hash_hex.trim_start_matches("0x")).unwrap_or_default();

    let row: Option<(Vec<u8>, i64, i32, String, String)> = sqlx::query_as(
        r#"
        SELECT block_hash, block_height, tx_index,
               total_output::text, fee::text
        FROM transactions WHERE tx_hash = $1
        "#,
    )
    .bind(&hash_bytes)
    .fetch_optional(&state.db)
    .await
    .map_err(|_| json!({"code": -32000, "message": "Database error"}))?;

    match row {
        Some((block_hash, height, index, value, _fee)) => {
            Ok(json!({
                "hash": format!("0x{}", hex::encode(&hash_bytes)),
                "blockHash": format!("0x{}", hex::encode(&block_hash)),
                "blockNumber": format!("0x{:x}", height),
                "transactionIndex": format!("0x{:x}", index),
                "from": "0x0000000000000000000000000000000000000000",
                "to": "0x0000000000000000000000000000000000000000",
                "value": format!("0x{:x}", value.parse::<f64>().unwrap_or(0.0) as u128),
                "gas": "0x5208",
                "gasPrice": "0x3b9aca00",
                "input": "0x",
                "nonce": "0x0",
            }))
        }
        None => Ok(Value::Null),
    }
}

async fn eth_get_tx_receipt(
    state: &AppState,
    params: &[Value],
) -> Result<Value, Value> {
    let hash_hex = params.first().and_then(|v| v.as_str()).unwrap_or("");
    let hash_bytes = hex::decode(hash_hex.trim_start_matches("0x")).unwrap_or_default();

    let row: Option<(Vec<u8>, i64, i32, bool)> = sqlx::query_as(
        r#"
        SELECT block_hash, block_height, tx_index, is_valid
        FROM transactions WHERE tx_hash = $1
        "#,
    )
    .bind(&hash_bytes)
    .fetch_optional(&state.db)
    .await
    .map_err(|_| json!({"code": -32000, "message": "Database error"}))?;

    match row {
        Some((block_hash, height, index, is_valid)) => {
            Ok(json!({
                "transactionHash": format!("0x{}", hex::encode(&hash_bytes)),
                "blockHash": format!("0x{}", hex::encode(&block_hash)),
                "blockNumber": format!("0x{:x}", height),
                "transactionIndex": format!("0x{:x}", index),
                "from": "0x0000000000000000000000000000000000000000",
                "to": "0x0000000000000000000000000000000000000000",
                "cumulativeGasUsed": "0x5208",
                "gasUsed": "0x5208",
                "contractAddress": null,
                "logs": [],
                "logsBloom": "0x" .to_string() + &"0".repeat(512),
                "status": if is_valid { "0x1" } else { "0x0" },
                "type": "0x0",
            }))
        }
        None => Ok(Value::Null),
    }
}
