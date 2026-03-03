//! Wallet and balance endpoints.
//!
//! GET /balance/{address}     — Address balance
//! GET /utxos/{address}       — UTXOs for address
//! POST /transfer             — Send QBC transaction

use axum::extract::{Path, State};
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::state::AppState;

/// GET /balance/{address} — Get address balance.
pub async fn get_balance(
    State(state): State<AppState>,
    Path(address): Path<String>,
) -> Json<Value> {
    let addr_bytes = hex::decode(address.trim_start_matches("0x")).unwrap_or_default();

    let row: Option<(String, String, String, i64, i64)> = sqlx::query_as(
        r#"
        SELECT balance::text, total_received::text, total_sent::text,
               tx_count, utxo_count
        FROM addresses WHERE address = $1
        "#,
    )
    .bind(&addr_bytes)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    match row {
        Some((balance, received, sent, tx_count, utxo_count)) => {
            Json(json!({
                "address": format!("0x{}", hex::encode(&addr_bytes)),
                "balance": balance,
                "total_received": received,
                "total_sent": sent,
                "tx_count": tx_count,
                "utxo_count": utxo_count,
            }))
        }
        None => {
            Json(json!({
                "address": format!("0x{}", hex::encode(&addr_bytes)),
                "balance": "0",
                "total_received": "0",
                "total_sent": "0",
                "tx_count": 0,
                "utxo_count": 0,
            }))
        }
    }
}

/// GET /utxos/{address} — Get unspent transaction outputs for address.
pub async fn get_utxos(
    State(state): State<AppState>,
    Path(address): Path<String>,
) -> Json<Value> {
    let addr_bytes = hex::decode(address.trim_start_matches("0x")).unwrap_or_default();

    let rows: Vec<(Vec<u8>, i32, String)> = sqlx::query_as(
        r#"
        SELECT tx_hash, output_index, amount::text
        FROM transaction_outputs
        WHERE recipient_address = $1 AND is_spent = false
        ORDER BY amount DESC
        "#,
    )
    .bind(&addr_bytes)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();

    let utxos: Vec<Value> = rows
        .into_iter()
        .map(|(txid, vout, amount)| {
            json!({
                "txid": format!("0x{}", hex::encode(&txid)),
                "vout": vout,
                "amount": amount,
            })
        })
        .collect();

    let total: f64 = utxos
        .iter()
        .filter_map(|u| u["amount"].as_str()?.parse::<f64>().ok())
        .sum();

    Json(json!({
        "address": format!("0x{}", hex::encode(&addr_bytes)),
        "utxos": utxos,
        "count": utxos.len(),
        "total": format!("{:.8}", total),
    }))
}

/// GET /mempool — Pending transactions.
pub async fn get_mempool(State(state): State<AppState>) -> Json<Value> {
    let rows: Vec<(Vec<u8>, i64, String, String)> = sqlx::query_as(
        r#"
        SELECT tx_hash, tx_size, fee::text, received_timestamp::text
        FROM mempool
        WHERE is_valid = true
        ORDER BY fee_per_byte DESC
        LIMIT 100
        "#,
    )
    .bind(100i64)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();

    let txs: Vec<Value> = rows
        .into_iter()
        .map(|(hash, size, fee, ts)| {
            json!({
                "tx_hash": format!("0x{}", hex::encode(&hash)),
                "size": size,
                "fee": fee,
                "received": ts,
            })
        })
        .collect();

    Json(json!({
        "pending": txs.len(),
        "transactions": txs,
    }))
}

#[derive(Deserialize)]
pub struct TransferRequest {
    pub from_address: String,
    pub to_address: String,
    pub amount: String,
    pub signature: Option<String>,
}

/// POST /transfer — Submit a QBC transfer transaction.
///
/// In the Substrate architecture, this proxies to the Substrate node's
/// extrinsic submission. The actual transfer is a UTXO transaction
/// submitted via the qbc-utxo pallet.
pub async fn transfer(
    State(_state): State<AppState>,
    Json(_req): Json<TransferRequest>,
) -> Json<Value> {
    // TODO: Build and submit Substrate extrinsic for UTXO transfer
    // This requires constructing a signed extrinsic and submitting
    // via the Substrate RPC.
    Json(json!({
        "error": "Direct transfer via API gateway is not yet implemented. Use Substrate RPC or the mining client.",
        "hint": "Submit signed extrinsics directly to the Substrate node's JSON-RPC endpoint."
    }))
}
