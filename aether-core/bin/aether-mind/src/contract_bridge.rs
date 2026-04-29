//! Contract Bridge — connects Aether Mind to on-chain smart contracts via QVM RPC.
//!
//! Provides ABI encoding/decoding and typed methods for each Aether contract.
//! Talks to the Python node's JSON-RPC endpoint (QVM executor).

use anyhow::{anyhow, Result};
use serde::{Deserialize, Serialize};
use tiny_keccak::{Hasher, Keccak};

// ── ABI Helpers ──────────────────────────────────────────────────────────────

fn keccak256(data: &[u8]) -> [u8; 32] {
    let mut hasher = Keccak::v256();
    let mut output = [0u8; 32];
    hasher.update(data);
    hasher.finalize(&mut output);
    output
}

fn selector(sig: &str) -> [u8; 4] {
    let hash = keccak256(sig.as_bytes());
    [hash[0], hash[1], hash[2], hash[3]]
}

fn encode_uint256(val: u64) -> [u8; 32] {
    let mut buf = [0u8; 32];
    buf[24..32].copy_from_slice(&val.to_be_bytes());
    buf
}

fn encode_address(addr: &str) -> [u8; 32] {
    let clean = addr.trim_start_matches("0x");
    let bytes = hex::decode(clean).unwrap_or_default();
    let mut buf = [0u8; 32];
    if bytes.len() <= 20 {
        buf[32 - bytes.len()..].copy_from_slice(&bytes);
    }
    buf
}

fn encode_bytes32(data: &[u8]) -> [u8; 32] {
    let mut buf = [0u8; 32];
    let len = data.len().min(32);
    buf[..len].copy_from_slice(&data[..len]);
    buf
}

fn encode_string(s: &str) -> Vec<u8> {
    let bytes = s.as_bytes();
    let mut encoded = Vec::new();
    // offset pointer (points to start of dynamic data = 32 bytes in)
    encoded.extend_from_slice(&encode_uint256(32));
    // length
    encoded.extend_from_slice(&encode_uint256(bytes.len() as u64));
    // data padded to 32-byte boundary
    encoded.extend_from_slice(bytes);
    let pad = (32 - (bytes.len() % 32)) % 32;
    encoded.extend(vec![0u8; pad]);
    encoded
}

fn decode_uint256(data: &[u8]) -> u64 {
    if data.len() < 32 {
        return 0;
    }
    let mut bytes = [0u8; 8];
    bytes.copy_from_slice(&data[24..32]);
    u64::from_be_bytes(bytes)
}

fn decode_bool(data: &[u8]) -> bool {
    if data.len() < 32 {
        return false;
    }
    data[31] != 0
}

// ── Contract Bridge ──────────────────────────────────────────────────────────

#[derive(Clone)]
pub struct ContractBridge {
    client: reqwest::Client,
    qvm_url: String,
    from_address: String,
    // Contract addresses (proxy addresses from registry)
    pub consciousness_dashboard: String,
    pub proof_of_thought: String,
    pub api_subscription: String,
    pub emergency_shutdown: String,
    pub higgs_field: String,
    pub aether_soul: String,
    pub constitutional_ai: String,
    pub synaptic_staking: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct JsonRpcRequest {
    jsonrpc: String,
    method: String,
    params: serde_json::Value,
    id: u64,
}

#[derive(Serialize, Deserialize, Debug)]
struct JsonRpcResponse {
    jsonrpc: String,
    id: u64,
    result: Option<serde_json::Value>,
    error: Option<serde_json::Value>,
}

#[derive(Serialize, Clone, Debug)]
pub struct ContractAddresses {
    pub consciousness_dashboard: String,
    pub proof_of_thought: String,
    pub api_subscription: String,
    pub emergency_shutdown: String,
    pub higgs_field: String,
    pub aether_soul: String,
    pub constitutional_ai: String,
    pub synaptic_staking: String,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SubscriptionInfo {
    pub balance: u64,
    pub tier: u8,
    pub chats_remaining: u64,
}

impl ContractBridge {
    pub fn new() -> Self {
        let qvm_url = std::env::var("QVM_RPC_URL")
            .unwrap_or_else(|_| "http://localhost:5001".to_string());
        let from_address = std::env::var("CONTRACT_OWNER_ADDRESS")
            .unwrap_or_else(|_| "1ca2afb858e3efeb882bbf0c8a47529c2c7bd7cb".to_string());

        Self {
            client: reqwest::Client::new(),
            qvm_url,
            from_address,
            consciousness_dashboard: "0xa854077769070717f4f37ac847be3dfa19a87640".to_string(),
            proof_of_thought: "0xea693f2eb8fbfa4a42e67529610910608d4bb5cd".to_string(),
            api_subscription: "0x686b794096953ecb9ffc44454ded2489eb00f58e".to_string(),
            emergency_shutdown: "0x104cf0b92a3f6768f55e211aad4f311ff2d3eef3".to_string(),
            higgs_field: "0xb4807f595441cff8506daa371674d515b46bc591".to_string(),
            aether_soul: "0x0000000000000000000000000000000000000000".to_string(), // Not in registry yet
            constitutional_ai: "0x4661650cb5527c8f101e14ae6dd5593923749ffe".to_string(),
            synaptic_staking: "0xc45bea55e7239a8063dbfe3a5de09b98ce729946".to_string(),
        }
    }

    // ── Low-level RPC ──────────────────────────────────────────────────────

    async fn eth_call(&self, to: &str, data: &[u8]) -> Result<Vec<u8>> {
        let hex_data = format!("0x{}", hex::encode(data));
        let req = JsonRpcRequest {
            jsonrpc: "2.0".into(),
            method: "eth_call".into(),
            params: serde_json::json!([
                {
                    "from": format!("0x{}", self.from_address),
                    "to": to,
                    "data": hex_data,
                },
                "latest"
            ]),
            id: 1,
        };

        let resp: JsonRpcResponse = self.client
            .post(&format!("{}/jsonrpc", self.qvm_url))
            .json(&req)
            .send()
            .await?
            .json()
            .await?;

        if let Some(err) = resp.error {
            return Err(anyhow!("eth_call error: {}", err));
        }

        let result_hex = resp.result
            .and_then(|v| v.as_str().map(|s| s.to_string()))
            .unwrap_or_default();

        let clean = result_hex.trim_start_matches("0x");
        hex::decode(clean).map_err(|e| anyhow!("hex decode: {}", e))
    }

    async fn eth_send_tx(&self, to: &str, data: &[u8]) -> Result<String> {
        let hex_data = format!("0x{}", hex::encode(data));
        let req = JsonRpcRequest {
            jsonrpc: "2.0".into(),
            method: "eth_sendTransaction".into(),
            params: serde_json::json!([
                {
                    "from": format!("0x{}", self.from_address),
                    "to": to,
                    "data": hex_data,
                    "gas": "0x1e8480",
                }
            ]),
            id: 1,
        };

        let resp: JsonRpcResponse = self.client
            .post(&format!("{}/jsonrpc", self.qvm_url))
            .json(&req)
            .send()
            .await?
            .json()
            .await?;

        if let Some(err) = resp.error {
            return Err(anyhow!("eth_sendTransaction error: {}", err));
        }

        resp.result
            .and_then(|v| v.as_str().map(|s| s.to_string()))
            .ok_or_else(|| anyhow!("no tx hash in response"))
    }

    /// Check if QVM is reachable.
    pub async fn is_available(&self) -> bool {
        let req = JsonRpcRequest {
            jsonrpc: "2.0".into(),
            method: "eth_chainId".into(),
            params: serde_json::json!([]),
            id: 1,
        };
        match self.client.post(&format!("{}/jsonrpc", self.qvm_url))
            .json(&req)
            .send()
            .await
        {
            Ok(resp) => resp.status().is_success(),
            Err(_) => false,
        }
    }

    // ── Tier 1: Emergency Shutdown ─────────────────────────────────────────

    /// Check if the emergency shutdown is active.
    /// Calls EmergencyShutdown.getStatus() -> (bool shutdown_, uint256 shutdownAt, uint256 signers_)
    pub async fn is_shutdown(&self) -> Result<bool> {
        // getStatus() -> first return value is the bool
        let sel = selector("getStatus()");
        let data = self.eth_call(&self.emergency_shutdown, &sel).await?;
        Ok(decode_bool(&data))
    }

    // ── Tier 1: Consciousness Dashboard ────────────────────────────────────

    /// Record phi measurement on-chain.
    /// Calls ConsciousnessDashboard.recordPhi(uint256 phi, uint256 integration,
    ///   uint256 differentiation, uint256 coherence, uint256 knowledgeNodes,
    ///   uint256 knowledgeEdges, HiggsData higgs)
    /// HiggsData is (uint256 vev, uint256 mass, uint256 deviation)
    pub async fn record_phi(
        &self,
        phi: u64,
        integration: u64,
        differentiation: u64,
        coherence: u64,
        nodes: u64,
        edges: u64,
        higgs_vev: u64,
        higgs_mass: u64,
        higgs_dev: u64,
    ) -> Result<String> {
        let sel = selector(
            "recordPhi(uint256,uint256,uint256,uint256,uint256,uint256,(uint256,uint256,uint256))"
        );
        let mut data = Vec::with_capacity(4 + 9 * 32);
        data.extend_from_slice(&sel);
        data.extend_from_slice(&encode_uint256(phi));
        data.extend_from_slice(&encode_uint256(integration));
        data.extend_from_slice(&encode_uint256(differentiation));
        data.extend_from_slice(&encode_uint256(coherence));
        data.extend_from_slice(&encode_uint256(nodes));
        data.extend_from_slice(&encode_uint256(edges));
        // HiggsData struct (inline tuple)
        data.extend_from_slice(&encode_uint256(higgs_vev));
        data.extend_from_slice(&encode_uint256(higgs_mass));
        data.extend_from_slice(&encode_uint256(higgs_dev));

        self.eth_send_tx(&self.consciousness_dashboard, &data).await
    }

    // ── Tier 1: Proof of Thought ───────────────────────────────────────────

    /// Submit a proof-of-thought attestation.
    /// Calls ProofOfThought.submitProof(uint256 taskId, address submitter,
    ///   bytes32 solutionHash, bytes32 quantumProofHash, uint256 blockHeight)
    pub async fn submit_proof(
        &self,
        solution_hash: [u8; 32],
        quantum_hash: [u8; 32],
        block_height: u64,
    ) -> Result<String> {
        let sel = selector(
            "submitProof(uint256,address,bytes32,bytes32,uint256)"
        );
        let mut data = Vec::with_capacity(4 + 5 * 32);
        data.extend_from_slice(&sel);
        data.extend_from_slice(&encode_uint256(0)); // taskId = 0 (autonomous PoT)
        data.extend_from_slice(&encode_address(&self.from_address)); // submitter
        data.extend_from_slice(&encode_bytes32(&solution_hash));
        data.extend_from_slice(&encode_bytes32(&quantum_hash));
        data.extend_from_slice(&encode_uint256(block_height));

        self.eth_send_tx(&self.proof_of_thought, &data).await
    }

    // ── Tier 1: API Subscription ───────────────────────────────────────────

    /// Check a user's subscription status.
    /// Calls AetherAPISubscription.getAccount(address user)
    /// Returns (balance, tier, dailyRate, chatLimit, queryLimit, inferenceLimit, totalDeposited, totalSpent)
    pub async fn check_subscription(&self, user: &str) -> Result<SubscriptionInfo> {
        let sel = selector("getAccount(address)");
        let mut data = Vec::with_capacity(4 + 32);
        data.extend_from_slice(&sel);
        data.extend_from_slice(&encode_address(user));

        let result = self.eth_call(&self.api_subscription, &data).await?;
        // Parse first 3 words: balance (uint256), tier (uint8 encoded as uint256), chatLimit
        let balance = if result.len() >= 32 { decode_uint256(&result[0..32]) } else { 0 };
        let tier = if result.len() >= 64 { decode_uint256(&result[32..64]) as u8 } else { 0 };
        let chat_limit = if result.len() >= 160 { decode_uint256(&result[96..128]) } else { 0 };

        Ok(SubscriptionInfo {
            balance,
            tier,
            chats_remaining: chat_limit,
        })
    }

    /// Deduct a fee from a user's balance.
    /// Calls AetherAPISubscription.deductFee(address user, string callType)
    pub async fn deduct_fee(&self, user: &str, call_type: &str) -> Result<String> {
        let sel = selector("deductFee(address,string)");
        let mut data = Vec::with_capacity(4 + 32 + 96);
        data.extend_from_slice(&sel);
        data.extend_from_slice(&encode_address(user));
        // String is dynamic — offset then content
        let str_encoded = encode_string(call_type);
        data.extend_from_slice(&str_encoded);

        self.eth_send_tx(&self.api_subscription, &data).await
    }

    // ── Tier 2: Higgs Field ────────────────────────────────────────────────

    /// Update the Higgs field value on-chain.
    /// Calls HiggsField.updateFieldValue(uint256 newFieldValue)
    pub async fn update_higgs_field(&self, field_value: u64) -> Result<String> {
        let sel = selector("updateFieldValue(uint256)");
        let mut data = Vec::with_capacity(4 + 32);
        data.extend_from_slice(&sel);
        data.extend_from_slice(&encode_uint256(field_value));

        self.eth_send_tx(&self.higgs_field, &data).await
    }

    /// Get field state from HiggsField contract.
    /// Returns (vev, currentField, mu, lambda, tanBeta, avgMass, totalMass, massGap, totalExcitations)
    pub async fn get_higgs_field_state(&self) -> Result<(u64, u64)> {
        let sel = selector("getFieldState()");
        let result = self.eth_call(&self.higgs_field, &sel).await?;
        let vev = if result.len() >= 32 { decode_uint256(&result[0..32]) } else { 0 };
        let current = if result.len() >= 64 { decode_uint256(&result[32..64]) } else { 0 };
        Ok((vev, current))
    }

    // ── Tier 2: Aether Soul ────────────────────────────────────────────────

    /// Update personality traits on-chain.
    /// Calls AetherSoul.updatePersonality(uint16 curiosity, uint16 warmth, uint16 honesty,
    ///   uint16 humility, uint16 playfulness, uint16 depth, uint16 courage,
    ///   string voiceDirective, string[] coreValues,
    ///   uint16 explorationBias, uint16 intuitionBias, uint16 actionBias)
    /// Simplified: just update the 7 numeric traits.
    pub async fn update_soul_personality(&self, traits: [u64; 7]) -> Result<String> {
        // This contract may not be deployed yet
        if self.aether_soul == "0x0000000000000000000000000000000000000000" {
            return Err(anyhow!("AetherSoul contract not deployed"));
        }

        let sel = selector(
            "updatePersonality(uint16,uint16,uint16,uint16,uint16,uint16,uint16,string,string[],uint16,uint16,uint16)"
        );
        let mut data = Vec::with_capacity(4 + 12 * 32 + 128);
        data.extend_from_slice(&sel);
        // 7 traits as uint16 (encoded as uint256 words)
        for &t in &traits {
            data.extend_from_slice(&encode_uint256(t));
        }
        // voiceDirective (dynamic — offset)
        // For now, skip dynamic params. The contract may reject,
        // but this is best-effort transparency.
        // TODO: proper dynamic encoding when AetherSoul is deployed

        // Skip sending if not deployed
        self.eth_send_tx(&self.aether_soul, &data).await
    }

    // ── Tier 2: Constitutional AI ──────────────────────────────────────────

    /// Get count of constitutional principles.
    /// Calls ConstitutionalAI.getPrincipleCount() -> (uint256 total, uint256 active)
    pub async fn get_principle_count(&self) -> Result<(u64, u64)> {
        let sel = selector("getPrincipleCount()");
        let result = self.eth_call(&self.constitutional_ai, &sel).await?;
        let total = if result.len() >= 32 { decode_uint256(&result[0..32]) } else { 0 };
        let active = if result.len() >= 64 { decode_uint256(&result[32..64]) } else { 0 };
        Ok((total, active))
    }

    /// Check if an operation is vetoed.
    pub async fn is_operation_vetoed(&self, operation_hash: &[u8; 32]) -> Result<bool> {
        let sel = selector("isOperationVetoed(bytes32)");
        let mut data = Vec::with_capacity(4 + 32);
        data.extend_from_slice(&sel);
        data.extend_from_slice(operation_hash);

        let result = self.eth_call(&self.constitutional_ai, &data).await?;
        Ok(decode_bool(&result))
    }

    // ── Tier 2: Synaptic Staking ───────────────────────────────────────────

    /// Update utility for a staking connection.
    /// Calls SynapticStaking.updateUtility(uint256 connectionId, uint256 newUtility)
    pub async fn update_staking_utility(
        &self,
        connection_id: u64,
        utility: u64,
    ) -> Result<String> {
        let sel = selector("updateUtility(uint256,uint256)");
        let mut data = Vec::with_capacity(4 + 2 * 32);
        data.extend_from_slice(&sel);
        data.extend_from_slice(&encode_uint256(connection_id));
        data.extend_from_slice(&encode_uint256(utility));

        self.eth_send_tx(&self.synaptic_staking, &data).await
    }

    /// Get connection count.
    pub async fn get_connection_count(&self) -> Result<u64> {
        let sel = selector("getConnectionCount()");
        let result = self.eth_call(&self.synaptic_staking, &sel).await?;
        Ok(decode_uint256(&result))
    }

    // ── Status ─────────────────────────────────────────────────────────────

    pub fn addresses(&self) -> ContractAddresses {
        ContractAddresses {
            consciousness_dashboard: self.consciousness_dashboard.clone(),
            proof_of_thought: self.proof_of_thought.clone(),
            api_subscription: self.api_subscription.clone(),
            emergency_shutdown: self.emergency_shutdown.clone(),
            higgs_field: self.higgs_field.clone(),
            aether_soul: self.aether_soul.clone(),
            constitutional_ai: self.constitutional_ai.clone(),
            synaptic_staking: self.synaptic_staking.clone(),
        }
    }
}
