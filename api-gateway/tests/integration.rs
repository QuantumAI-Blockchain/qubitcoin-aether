//! Integration tests for the Qubitcoin API Gateway.
//!
//! These tests run against a LIVE gateway at http://localhost:5000.
//! They are marked `#[ignore]` by default — run explicitly with:
//!
//!   cargo test --test integration -- --ignored
//!
//! Prerequisites:
//!   - API gateway running on port 5000
//!   - CockroachDB available (gateway needs it for startup)

use reqwest::Client;
use serde_json::{json, Value};

const BASE_URL: &str = "http://localhost:5000";

/// Build a shared HTTP client for all tests.
fn client() -> Client {
    Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .expect("Failed to build HTTP client")
}

// ═══════════════════════════════════════════════════════════════════════
// Health & Info Endpoints
// ═══════════════════════════════════════════════════════════════════════

#[tokio::test]
#[ignore]
async fn test_root_returns_200_with_node_identity() {
    let resp = client()
        .get(format!("{}/", BASE_URL))
        .send()
        .await
        .expect("GET / failed");

    assert_eq!(resp.status(), 200, "Root endpoint should return 200");

    let body: Value = resp.json().await.expect("Root response is not valid JSON");

    assert_eq!(body["name"], "Qubitcoin", "name field must be 'Qubitcoin'");
    assert_eq!(body["symbol"], "QBC", "symbol field must be 'QBC'");
    assert_eq!(body["chain_id"], 3303, "chain_id must be 3303");
    assert!(body["version"].is_string(), "version must be a string");
    assert!(body["block_height"].is_number(), "block_height must be a number");
    assert_eq!(body["consensus"], "Proof-of-SUSY-Alignment (PoSA)");
    assert_eq!(body["block_time"], "3.3s");
    assert_eq!(body["website"], "https://qbc.network");
}

#[tokio::test]
#[ignore]
async fn test_health_returns_200_with_status() {
    let resp = client()
        .get(format!("{}/health", BASE_URL))
        .send()
        .await
        .expect("GET /health failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("Health response is not valid JSON");

    // status must be one of: healthy, degraded, unhealthy
    let status = body["status"].as_str().expect("status must be a string");
    assert!(
        ["healthy", "degraded", "unhealthy"].contains(&status),
        "status '{}' is not a valid health status",
        status
    );

    // Boolean fields must be present
    assert!(body["database"].is_boolean(), "database field must be boolean");
    assert!(body["substrate"].is_boolean(), "substrate field must be boolean");
    assert!(body["aether_mind"].is_boolean(), "aether_mind field must be boolean");
    assert!(body["timestamp"].is_string(), "timestamp must be an RFC3339 string");
}

#[tokio::test]
#[ignore]
async fn test_info_returns_200_with_chain_details() {
    let resp = client()
        .get(format!("{}/info", BASE_URL))
        .send()
        .await
        .expect("GET /info failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("Info response is not valid JSON");

    assert_eq!(body["chain_id"], 3303);
    assert!(body["block_height"].is_number(), "block_height must be a number");
    assert!(body["consensus"].is_string(), "consensus must be a string");
}

// ═══════════════════════════════════════════════════════════════════════
// Chain Endpoints
// ═══════════════════════════════════════════════════════════════════════

#[tokio::test]
#[ignore]
async fn test_chain_info_returns_expected_fields() {
    let resp = client()
        .get(format!("{}/chain/info", BASE_URL))
        .send()
        .await
        .expect("GET /chain/info failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("chain/info response is not valid JSON");

    // Required fields regardless of Substrate or DB-only mode
    assert_eq!(body["chain_id"], 3303, "chain_id must be 3303");
    assert!(body["height"].is_number(), "height must be a number");
    assert!(body["block_height"].is_number(), "block_height must be a number");
    assert!(body["max_supply"].is_number(), "max_supply must be a number");

    // height and block_height should be identical
    assert_eq!(
        body["height"], body["block_height"],
        "height and block_height must match"
    );

    // If not in initializing state, check more fields
    if body.get("status").and_then(|s| s.as_str()) != Some("initializing") {
        assert!(
            body["total_supply"].is_string(),
            "total_supply must be a string (formatted decimal)"
        );
        assert!(
            body["difficulty"].is_string() || body["current_difficulty"].is_string(),
            "difficulty or current_difficulty must be present as a string"
        );
        assert!(body["current_era"].is_number(), "current_era must be a number");
        assert!(body["current_reward"].is_string(), "current_reward must be a string");
        assert!(body["consensus"].is_string(), "consensus must be a string");
    }
}

#[tokio::test]
#[ignore]
async fn test_chain_tip_returns_200() {
    let resp = client()
        .get(format!("{}/chain/tip", BASE_URL))
        .send()
        .await
        .expect("GET /chain/tip failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("chain/tip response is not valid JSON");

    // Should return either a block object or a height indicator
    assert!(
        body.get("block_height").is_some() || body.get("block_hash").is_some(),
        "chain/tip must return block_height or block_hash"
    );
}

#[tokio::test]
#[ignore]
async fn test_chain_blocks_returns_list() {
    let resp = client()
        .get(format!("{}/chain/blocks?limit=5", BASE_URL))
        .send()
        .await
        .expect("GET /chain/blocks failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("chain/blocks response is not valid JSON");

    assert!(body["blocks"].is_array(), "blocks must be an array");
    assert!(body["count"].is_number(), "count must be a number");

    let blocks = body["blocks"].as_array().unwrap();
    assert!(blocks.len() <= 5, "should return at most 5 blocks when limit=5");

    // Validate structure of each block
    for block in blocks {
        assert!(block["block_hash"].is_string(), "block must have block_hash");
        assert!(block["block_height"].is_number(), "block must have block_height");
        assert!(block["era"].is_number(), "block must have era");
        assert!(block["difficulty"].is_number(), "block must have difficulty");
    }
}

#[tokio::test]
#[ignore]
async fn test_chain_blocks_pagination() {
    let resp = client()
        .get(format!("{}/chain/blocks?limit=3&offset=0", BASE_URL))
        .send()
        .await
        .expect("GET /chain/blocks?limit=3&offset=0 failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.unwrap();
    let first_page = body["blocks"].as_array().unwrap().clone();

    // Fetch second page
    let resp2 = client()
        .get(format!("{}/chain/blocks?limit=3&offset=3", BASE_URL))
        .send()
        .await
        .expect("GET /chain/blocks?limit=3&offset=3 failed");

    assert_eq!(resp2.status(), 200);

    let body2: Value = resp2.json().await.unwrap();
    let second_page = body2["blocks"].as_array().unwrap().clone();

    // If both pages have data, ensure they are different blocks
    if !first_page.is_empty() && !second_page.is_empty() {
        assert_ne!(
            first_page[0]["block_height"], second_page[0]["block_height"],
            "Paginated results should return different blocks"
        );
    }
}

#[tokio::test]
#[ignore]
async fn test_get_block_by_height() {
    // Block 1 should exist on any chain with more than 1 block
    let resp = client()
        .get(format!("{}/block/1", BASE_URL))
        .send()
        .await
        .expect("GET /block/1 failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("block/1 response is not valid JSON");

    // Either a valid block or a "not found" error
    if body.get("error").is_none() {
        assert!(body["block_hash"].is_string(), "block must have block_hash");
        assert_eq!(body["block_height"], 1, "block_height must match requested height");
        assert!(body["era"].is_number(), "block must have era");
    }
}

#[tokio::test]
#[ignore]
async fn test_get_block_nonexistent_returns_error() {
    // Use an absurdly high block number that should not exist
    let resp = client()
        .get(format!("{}/block/999999999999", BASE_URL))
        .send()
        .await
        .expect("GET /block/999999999999 failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.unwrap();
    assert!(
        body.get("error").is_some(),
        "Nonexistent block should return an error field"
    );
}

// ═══════════════════════════════════════════════════════════════════════
// Balance & Wallet Endpoints
// ═══════════════════════════════════════════════════════════════════════

#[tokio::test]
#[ignore]
async fn test_balance_known_miner_address() {
    // Known miner address from CLAUDE.md
    let addr = "1ca2afb858e3efeb882bbf0c8a47529c2c7bd7cb";
    let resp = client()
        .get(format!("{}/balance/{}", BASE_URL, addr))
        .send()
        .await
        .expect("GET /balance/{addr} failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("balance response is not valid JSON");

    assert!(body["address"].is_string(), "address must be present");
    assert!(body["balance"].is_string(), "balance must be a string (decimal)");
    assert!(body["tx_count"].is_number(), "tx_count must be a number");
    assert!(body["utxo_count"].is_number(), "utxo_count must be a number");
}

#[tokio::test]
#[ignore]
async fn test_balance_unknown_address_returns_zero() {
    // Arbitrary address that almost certainly has no balance
    let addr = "0000000000000000000000000000000000000000";
    let resp = client()
        .get(format!("{}/balance/{}", BASE_URL, addr))
        .send()
        .await
        .expect("GET /balance/zeros failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.unwrap();
    assert_eq!(body["balance"], "0", "Unknown address should have zero balance");
    assert_eq!(body["tx_count"], 0);
    assert_eq!(body["utxo_count"], 0);
}

#[tokio::test]
#[ignore]
async fn test_balance_with_0x_prefix() {
    // The endpoint should handle 0x-prefixed addresses
    let addr = "0x1ca2afb858e3efeb882bbf0c8a47529c2c7bd7cb";
    let resp = client()
        .get(format!("{}/balance/{}", BASE_URL, addr))
        .send()
        .await
        .expect("GET /balance/0x... failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.unwrap();
    assert!(body["address"].is_string(), "address field must be returned");
}

#[tokio::test]
#[ignore]
async fn test_utxos_endpoint() {
    let addr = "1ca2afb858e3efeb882bbf0c8a47529c2c7bd7cb";
    let resp = client()
        .get(format!("{}/utxos/{}", BASE_URL, addr))
        .send()
        .await
        .expect("GET /utxos/{addr} failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("utxos response is not valid JSON");

    assert!(body["address"].is_string(), "address must be present");
    assert!(body["utxos"].is_array(), "utxos must be an array");
    assert!(body["count"].is_number(), "count must be a number");
    assert!(body["total"].is_string(), "total must be a string (decimal)");
}

#[tokio::test]
#[ignore]
async fn test_mempool_endpoint() {
    let resp = client()
        .get(format!("{}/mempool", BASE_URL))
        .send()
        .await
        .expect("GET /mempool failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("mempool response is not valid JSON");

    assert!(body["pending"].is_number(), "pending must be a number");
    assert!(body["transactions"].is_array(), "transactions must be an array");
}

// ═══════════════════════════════════════════════════════════════════════
// Mining Endpoints
// ═══════════════════════════════════════════════════════════════════════

#[tokio::test]
#[ignore]
async fn test_mining_stats_returns_expected_fields() {
    let resp = client()
        .get(format!("{}/mining/stats", BASE_URL))
        .send()
        .await
        .expect("GET /mining/stats failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("mining/stats response is not valid JSON");

    assert!(body["current_difficulty"].is_string(), "current_difficulty must be a string");
    assert!(body["current_era"].is_number(), "current_era must be a number");
    assert!(body["current_reward"].is_string(), "current_reward must be a string");
    assert_eq!(body["consensus"], "Proof-of-SUSY-Alignment (PoSA)");
    assert_eq!(body["mining_algorithm"], "VQE (4-qubit SUSY Hamiltonian)");
    assert_eq!(body["difficulty_direction"], "higher = easier");
    assert!(body["recent_blocks"].is_array(), "recent_blocks must be an array");
}

#[tokio::test]
#[ignore]
async fn test_mining_difficulty_returns_expected_fields() {
    let resp = client()
        .get(format!("{}/mining/difficulty", BASE_URL))
        .send()
        .await
        .expect("GET /mining/difficulty failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("mining/difficulty response is not valid JSON");

    assert!(body["current_difficulty"].is_string(), "current_difficulty must be present");
    assert!(body["difficulty_raw"].is_number(), "difficulty_raw must be a number");
    assert!(body["difficulty_scale"].is_number(), "difficulty_scale must be a number");
    assert_eq!(body["adjustment_window"], 144);
    assert_eq!(body["max_adjustment"], "10%");
    assert_eq!(body["direction"], "higher = easier");
    assert!(
        body["source"].is_string(),
        "source must indicate 'substrate_live' or 'fallback'"
    );
    assert!(body["history"].is_array(), "history must be an array");
}

// ═══════════════════════════════════════════════════════════════════════
// Aether Tree Endpoints
// ═══════════════════════════════════════════════════════════════════════

#[tokio::test]
#[ignore]
async fn test_aether_info_returns_200() {
    let resp = client()
        .get(format!("{}/aether/info", BASE_URL))
        .send()
        .await
        .expect("GET /aether/info failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("aether/info response is not valid JSON");
    // Proxied endpoint: should return either valid data or an error message
    assert!(body.is_object(), "aether/info must return a JSON object");
}

#[tokio::test]
#[ignore]
async fn test_aether_phi_returns_200() {
    let resp = client()
        .get(format!("{}/aether/phi", BASE_URL))
        .send()
        .await
        .expect("GET /aether/phi failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("aether/phi response is not valid JSON");
    assert!(body.is_object(), "aether/phi must return a JSON object");
}

#[tokio::test]
#[ignore]
async fn test_aether_gates_returns_200() {
    let resp = client()
        .get(format!("{}/aether/gates", BASE_URL))
        .send()
        .await
        .expect("GET /aether/gates failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("aether/gates response is not valid JSON");
    assert!(body.is_object(), "aether/gates must return a JSON object");
}

#[tokio::test]
#[ignore]
async fn test_aether_chat_fee_returns_200() {
    let resp = client()
        .get(format!("{}/aether/chat/fee", BASE_URL))
        .send()
        .await
        .expect("GET /aether/chat/fee failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("aether/chat/fee response is not valid JSON");

    assert!(body["currency"].is_string(), "currency must be a string");
    assert_eq!(body["currency"], "QBC");
}

#[tokio::test]
#[ignore]
async fn test_aether_consciousness_returns_200() {
    let resp = client()
        .get(format!("{}/aether/consciousness", BASE_URL))
        .send()
        .await
        .expect("GET /aether/consciousness failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("consciousness response is not valid JSON");

    assert!(body["phi"].is_number(), "phi must be a number");
    assert!(body["threshold"].is_number(), "threshold must be a number");
    assert_eq!(body["threshold"], 3.0);
    assert!(body["above_threshold"].is_boolean(), "above_threshold must be boolean");
    assert!(body["gates_passed"].is_number(), "gates_passed must be a number");
    assert!(body["gates_total"].is_number(), "gates_total must be a number");
}

#[tokio::test]
#[ignore]
async fn test_aether_knowledge_returns_200() {
    let resp = client()
        .get(format!("{}/aether/knowledge", BASE_URL))
        .send()
        .await
        .expect("GET /aether/knowledge failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("knowledge response is not valid JSON");

    assert!(body["total_nodes"].is_number(), "total_nodes must be a number");
    assert!(body["total_edges"].is_number(), "total_edges must be a number");
    assert!(body["node_types"].is_array(), "node_types must be an array");
    assert!(body["edge_types"].is_array(), "edge_types must be an array");
}

// ═══════════════════════════════════════════════════════════════════════
// Economics Endpoint
// ═══════════════════════════════════════════════════════════════════════

#[tokio::test]
#[ignore]
async fn test_economics_emission_schedule() {
    let resp = client()
        .get(format!("{}/economics/emission", BASE_URL))
        .send()
        .await
        .expect("GET /economics/emission failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("emission response is not valid JSON");

    assert_eq!(body["max_supply"], "3,300,000,000");
    assert_eq!(body["genesis_premine"], "33,000,000");
    assert_eq!(body["halving_interval"], 15_474_020u64);
    assert_eq!(body["halving_type"], "phi (golden ratio)");
    assert!(body["eras"].is_array(), "eras must be an array");

    let eras = body["eras"].as_array().unwrap();
    assert!(!eras.is_empty(), "eras should have at least one entry");

    // Verify first era has the initial reward
    let first_era = &eras[0];
    assert_eq!(first_era["era"], 0);
    assert_eq!(first_era["block_reward"], "15.27000000");
}

// ═══════════════════════════════════════════════════════════════════════
// JSON-RPC Endpoints
// ═══════════════════════════════════════════════════════════════════════

#[tokio::test]
#[ignore]
async fn test_jsonrpc_eth_chain_id() {
    let resp = client()
        .post(format!("{}/jsonrpc", BASE_URL))
        .json(&json!({
            "jsonrpc": "2.0",
            "method": "eth_chainId",
            "params": [],
            "id": 1
        }))
        .send()
        .await
        .expect("POST /jsonrpc eth_chainId failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("JSON-RPC response is not valid JSON");

    assert_eq!(body["jsonrpc"], "2.0");
    assert_eq!(body["id"], 1);
    assert!(body.get("error").is_none(), "eth_chainId should not return an error");

    // Chain ID 3303 = 0xce7
    let result = body["result"].as_str().expect("result must be a hex string");
    assert_eq!(result, "0xce7", "Chain ID must be 0xce7 (3303)");
}

#[tokio::test]
#[ignore]
async fn test_jsonrpc_eth_block_number() {
    let resp = client()
        .post(format!("{}/jsonrpc", BASE_URL))
        .json(&json!({
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 2
        }))
        .send()
        .await
        .expect("POST /jsonrpc eth_blockNumber failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.unwrap();

    assert_eq!(body["jsonrpc"], "2.0");
    assert_eq!(body["id"], 2);
    assert!(body.get("error").is_none(), "eth_blockNumber should not return an error");

    let result = body["result"].as_str().expect("result must be a hex string");
    assert!(result.starts_with("0x"), "Block number must be hex-prefixed");

    // Parse the block number to verify it is a valid integer
    let height =
        u64::from_str_radix(result.trim_start_matches("0x"), 16).expect("Must be valid hex");
    assert!(height > 0, "Block number should be > 0 on a live chain");
}

#[tokio::test]
#[ignore]
async fn test_jsonrpc_net_version() {
    let resp = client()
        .post(format!("{}/jsonrpc", BASE_URL))
        .json(&json!({
            "jsonrpc": "2.0",
            "method": "net_version",
            "params": [],
            "id": 3
        }))
        .send()
        .await
        .expect("POST /jsonrpc net_version failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.unwrap();

    assert_eq!(body["jsonrpc"], "2.0");
    let result = body["result"].as_str().expect("result must be a string");
    assert_eq!(result, "3303", "net_version must return '3303'");
}

#[tokio::test]
#[ignore]
async fn test_jsonrpc_web3_client_version() {
    let resp = client()
        .post(format!("{}/jsonrpc", BASE_URL))
        .json(&json!({
            "jsonrpc": "2.0",
            "method": "web3_clientVersion",
            "params": [],
            "id": 4
        }))
        .send()
        .await
        .expect("POST /jsonrpc web3_clientVersion failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.unwrap();

    let result = body["result"].as_str().expect("result must be a string");
    assert!(
        result.contains("Qubitcoin"),
        "Client version must contain 'Qubitcoin'"
    );
}

#[tokio::test]
#[ignore]
async fn test_jsonrpc_eth_gas_price() {
    let resp = client()
        .post(format!("{}/jsonrpc", BASE_URL))
        .json(&json!({
            "jsonrpc": "2.0",
            "method": "eth_gasPrice",
            "params": [],
            "id": 5
        }))
        .send()
        .await
        .expect("POST /jsonrpc eth_gasPrice failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.unwrap();
    let result = body["result"].as_str().expect("result must be a hex string");
    assert!(result.starts_with("0x"), "Gas price must be hex-prefixed");
}

#[tokio::test]
#[ignore]
async fn test_jsonrpc_eth_estimate_gas() {
    let resp = client()
        .post(format!("{}/jsonrpc", BASE_URL))
        .json(&json!({
            "jsonrpc": "2.0",
            "method": "eth_estimateGas",
            "params": [],
            "id": 6
        }))
        .send()
        .await
        .expect("POST /jsonrpc eth_estimateGas failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.unwrap();
    let result = body["result"].as_str().expect("result must be a hex string");
    // Default is 21000 = 0x5208
    assert_eq!(result, "0x5208", "estimateGas should return 21000 (0x5208)");
}

#[tokio::test]
#[ignore]
async fn test_jsonrpc_unknown_method_returns_error() {
    let resp = client()
        .post(format!("{}/jsonrpc", BASE_URL))
        .json(&json!({
            "jsonrpc": "2.0",
            "method": "eth_nonExistentMethod",
            "params": [],
            "id": 99
        }))
        .send()
        .await
        .expect("POST /jsonrpc unknown method failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.unwrap();

    assert!(body.get("error").is_some(), "Unknown method must return an error");
    assert_eq!(body["error"]["code"], -32601, "Error code must be -32601 (method not found)");
    assert_eq!(body["id"], 99);
}

#[tokio::test]
#[ignore]
async fn test_jsonrpc_invalid_json_returns_parse_error() {
    let resp = client()
        .post(format!("{}/jsonrpc", BASE_URL))
        .header("content-type", "application/json")
        .body("{not valid json}")
        .send()
        .await
        .expect("POST /jsonrpc with invalid JSON failed");

    // Axum may return 400 or 422 for malformed JSON bodies
    let status = resp.status().as_u16();
    assert!(
        status == 400 || status == 422 || status == 200,
        "Invalid JSON should return 400, 422, or 200 with parse error"
    );
}

#[tokio::test]
#[ignore]
async fn test_jsonrpc_batch_request() {
    let resp = client()
        .post(format!("{}/jsonrpc", BASE_URL))
        .json(&json!([
            {"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 10},
            {"jsonrpc": "2.0", "method": "net_version", "params": [], "id": 11}
        ]))
        .send()
        .await
        .expect("POST /jsonrpc batch request failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.unwrap();
    assert!(body.is_array(), "Batch response must be an array");

    let results = body.as_array().unwrap();
    assert_eq!(results.len(), 2, "Batch should return 2 responses");
}

#[tokio::test]
#[ignore]
async fn test_jsonrpc_eth_get_balance() {
    let resp = client()
        .post(format!("{}/jsonrpc", BASE_URL))
        .json(&json!({
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": ["0x0000000000000000000000000000000000000000", "latest"],
            "id": 12
        }))
        .send()
        .await
        .expect("POST /jsonrpc eth_getBalance failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.unwrap();
    assert_eq!(body["jsonrpc"], "2.0");

    let result = body["result"].as_str().expect("result must be a hex string");
    assert!(result.starts_with("0x"), "Balance must be hex-prefixed");
}

// ═══════════════════════════════════════════════════════════════════════
// Versioned Routes (/v1/*)
// ═══════════════════════════════════════════════════════════════════════

#[tokio::test]
#[ignore]
async fn test_v1_health_returns_200() {
    let resp = client()
        .get(format!("{}/v1/health", BASE_URL))
        .send()
        .await
        .expect("GET /v1/health failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("/v1/health response is not valid JSON");

    let status = body["status"].as_str().expect("status must be a string");
    assert!(
        ["healthy", "degraded", "unhealthy"].contains(&status),
        "/v1/health status must be valid"
    );
}

#[tokio::test]
#[ignore]
async fn test_v1_chain_info_returns_200() {
    let resp = client()
        .get(format!("{}/v1/chain/info", BASE_URL))
        .send()
        .await
        .expect("GET /v1/chain/info failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("/v1/chain/info response is not valid JSON");

    assert_eq!(body["chain_id"], 3303, "/v1/chain/info chain_id must be 3303");
    assert!(body["height"].is_number(), "height must be present");
}

#[tokio::test]
#[ignore]
async fn test_v1_root_returns_200() {
    let resp = client()
        .get(format!("{}/v1/", BASE_URL))
        .send()
        .await
        .expect("GET /v1/ failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("/v1/ response is not valid JSON");
    assert_eq!(body["name"], "Qubitcoin");
    assert_eq!(body["chain_id"], 3303);
}

#[tokio::test]
#[ignore]
async fn test_v1_mining_stats_returns_200() {
    let resp = client()
        .get(format!("{}/v1/mining/stats", BASE_URL))
        .send()
        .await
        .expect("GET /v1/mining/stats failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("/v1/mining/stats response is not valid JSON");
    assert!(body["current_difficulty"].is_string());
}

#[tokio::test]
#[ignore]
async fn test_v1_jsonrpc_returns_200() {
    let resp = client()
        .post(format!("{}/v1/jsonrpc", BASE_URL))
        .json(&json!({
            "jsonrpc": "2.0",
            "method": "eth_chainId",
            "params": [],
            "id": 20
        }))
        .send()
        .await
        .expect("POST /v1/jsonrpc failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.unwrap();
    assert_eq!(body["result"], "0xce7");
}

// ═══════════════════════════════════════════════════════════════════════
// SUSY Database Endpoint
// ═══════════════════════════════════════════════════════════════════════

#[tokio::test]
#[ignore]
async fn test_susy_database_returns_200() {
    let resp = client()
        .get(format!("{}/susy-database?limit=5", BASE_URL))
        .send()
        .await
        .expect("GET /susy-database failed");

    assert_eq!(resp.status(), 200);

    let body: Value = resp.json().await.expect("susy-database response is not valid JSON");

    assert!(body["solutions"].is_array(), "solutions must be an array");
    assert!(body["count"].is_number(), "count must be a number");
}

// ═══════════════════════════════════════════════════════════════════════
// Cross-Cutting: Response Format Consistency
// ═══════════════════════════════════════════════════════════════════════

#[tokio::test]
#[ignore]
async fn test_all_get_endpoints_return_json() {
    let endpoints = vec![
        "/",
        "/health",
        "/info",
        "/chain/info",
        "/chain/tip",
        "/chain/blocks",
        "/mining/stats",
        "/mining/difficulty",
        "/aether/info",
        "/aether/phi",
        "/aether/gates",
        "/aether/knowledge",
        "/aether/chat/fee",
        "/aether/consciousness",
        "/economics/emission",
        "/mempool",
    ];

    let c = client();

    for endpoint in &endpoints {
        let resp = c
            .get(format!("{}{}", BASE_URL, endpoint))
            .send()
            .await
            .unwrap_or_else(|_| panic!("GET {} failed to connect", endpoint));

        assert_eq!(
            resp.status(),
            200,
            "GET {} returned status {}",
            endpoint,
            resp.status()
        );

        let content_type = resp
            .headers()
            .get("content-type")
            .and_then(|v| v.to_str().ok())
            .unwrap_or("");
        assert!(
            content_type.contains("application/json"),
            "GET {} content-type '{}' must contain 'application/json'",
            endpoint,
            content_type
        );

        let body: Value = resp
            .json()
            .await
            .unwrap_or_else(|_| panic!("GET {} response body is not valid JSON", endpoint));
        assert!(
            body.is_object() || body.is_array(),
            "GET {} must return a JSON object or array",
            endpoint
        );
    }
}
