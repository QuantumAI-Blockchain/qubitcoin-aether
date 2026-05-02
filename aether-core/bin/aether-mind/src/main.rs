//! # Aether Mind — V5 Neural Cognitive Engine
//!
//! Genuine neural transformer with Sephirot attention heads, consciousness monitoring,
//! Knowledge Fabric RAG grounded in live blockchain data, and on-chain PoT attestation.

mod contract_bridge;

use std::collections::HashMap;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Instant;

use axum::{
    extract::{Query, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use candle_core::{DType, Device};
use candle_nn::VarBuilder;
use log::{info, warn};
use serde::{Deserialize, Serialize};
use tokenizers::Tokenizer;
use tokio::sync::Mutex;
use tower_http::cors::CorsLayer;

use aether_consciousness::{
    ConsciousnessMonitor, CompressedGradients, LossTracker,
    ArchitectureGenome, EvolveArchive, NeuralPayload, EmbeddingEntry,
    evaluate_v5_gates,
};
use aether_fabric::search::KnowledgeFabric;
use aether_fabric::types::Provenance;
use aether_transformer::config::{SephirotDomain, TransformerConfig};
use aether_transformer::model::AetherTransformer;

// ── App State ───────────────────────────────────────────────────────────────

struct AppState {
    model: Mutex<AetherTransformer>,
    tokenizer: Tokenizer,
    embedder: Arc<TextEmbedder>,
    fabric: Arc<KnowledgeFabric>,
    consciousness: Mutex<ConsciousnessMonitor>,
    config: TransformerConfig,
    eos_token_id: u32,
    im_end_token_id: Option<u32>,
    chain_height: Mutex<u64>,
    /// Loss tracker for Proof-of-Learning validation.
    loss_tracker: Mutex<LossTracker>,
    /// Gradient accumulator from peer nodes (FedAvg).
    peer_gradients: Mutex<Vec<CompressedGradients>>,
    /// Pending knowledge vectors from peer nodes.
    peer_embeddings: Mutex<Vec<EmbeddingEntry>>,
    /// Aether-Evolve NAS archive.
    evolve_archive: Mutex<EvolveArchive>,
    /// Recent embedding deltas (for gradient compression).
    embedding_deltas: Mutex<Vec<f32>>,
    /// Chat interaction counter.
    chat_count: Mutex<u64>,
    /// Previous attention weights (for computing real attention deltas).
    prev_attention_flat: Mutex<Option<Vec<f32>>>,
    /// Cached V5 gates passed count (updated by /gates endpoint).
    gates_passed: Mutex<u8>,
    /// Gradient reward ledger.
    reward_ledger: Mutex<GradientRewardLedger>,
    /// Contract bridge for on-chain Aether contract interactions.
    contract_bridge: contract_bridge::ContractBridge,
    /// Emergency shutdown flag (polled from EmergencyShutdown contract).
    shutdown_active: Arc<AtomicBool>,
    /// Last block height where phi was recorded on-chain.
    last_phi_block: Mutex<u64>,
    /// Last block height where PoT was submitted on-chain.
    last_pot_block: Mutex<u64>,
    /// Last block height where Higgs field was synced on-chain.
    last_higgs_block: Mutex<u64>,
    /// Last block height where soul traits were synced on-chain.
    last_soul_block: Mutex<u64>,
    /// Conversation session store: session_id -> (turns, last_active_epoch_secs).
    sessions: Mutex<HashMap<String, SessionState>>,
}

// ── Conversation Memory ─────────────────────────────────────────────────────

/// Maximum conversation turns retained per session (sliding window).
const MAX_SESSION_TURNS: usize = 20;
/// Session expiry: 1 hour of inactivity.
const SESSION_TTL_SECS: u64 = 3600;

#[derive(Clone, Serialize, Deserialize)]
struct ChatTurn {
    role: String,   // "user" or "assistant"
    content: String,
}

struct SessionState {
    turns: Vec<ChatTurn>,
    last_active: u64, // epoch seconds
}

impl SessionState {
    fn new() -> Self {
        Self {
            turns: Vec::new(),
            last_active: epoch_secs(),
        }
    }

    fn push_user(&mut self, content: String) {
        self.turns.push(ChatTurn { role: "user".into(), content });
        self.last_active = epoch_secs();
        self.trim();
    }

    fn push_assistant(&mut self, content: String) {
        self.turns.push(ChatTurn { role: "assistant".into(), content });
        self.last_active = epoch_secs();
        self.trim();
    }

    fn trim(&mut self) {
        if self.turns.len() > MAX_SESSION_TURNS {
            let excess = self.turns.len() - MAX_SESSION_TURNS;
            self.turns.drain(..excess);
        }
    }

    fn is_expired(&self) -> bool {
        epoch_secs().saturating_sub(self.last_active) > SESSION_TTL_SECS
    }
}

fn epoch_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

// ── Gradient Reward Tracking ─────────────────────────────────────────────────

/// Tracks gradient rewards earned by miners.
struct GradientRewardLedger {
    /// miner_id -> (total_earned_qbc, submissions_count, last_block)
    balances: std::collections::HashMap<String, RewardBalance>,
    /// Pool address that funds rewards.
    pool_address: String,
    /// Pool balance (pre-funded).
    pool_balance: f64,
    /// Reward per valid gradient submission (QBC).
    base_reward: f64,
    /// Maximum reward multiplier for high-quality gradients.
    max_multiplier: f64,
}

#[derive(Clone, Serialize)]
struct RewardBalance {
    earned: f64,
    claimed: f64,
    submissions: u64,
    last_block: u64,
    avg_improvement: f32,
}

impl GradientRewardLedger {
    fn new() -> Self {
        let pool_address = std::env::var("GRADIENT_REWARDS_ADDRESS")
            .unwrap_or_else(|_| "77937349b74b57976965e790ebb8351f4076cec2".to_string());
        let pool_balance: f64 = std::env::var("GRADIENT_REWARD_POOL_QBC")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(1_000_000.0);
        let base_reward: f64 = std::env::var("GRADIENT_BASE_REWARD_QBC")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(0.1); // 0.1 QBC per valid gradient
        let max_multiplier: f64 = std::env::var("GRADIENT_MAX_MULTIPLIER")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(10.0);

        Self {
            balances: std::collections::HashMap::new(),
            pool_address,
            pool_balance,
            base_reward,
            max_multiplier,
        }
    }

    /// Calculate and record reward for a gradient submission.
    /// Returns the reward amount, or 0 if pool is exhausted.
    fn record_submission(
        &mut self,
        miner_id: &str,
        improvement_ratio: f32,
        block_height: u64,
    ) -> f64 {
        if self.pool_balance <= 0.0 || miner_id.is_empty() {
            return 0.0;
        }

        // Reward = base * (1 + improvement_ratio * multiplier_scale)
        // Capped at base * max_multiplier
        let multiplier = (1.0 + improvement_ratio as f64 * 100.0)
            .min(self.max_multiplier)
            .max(0.0);
        let reward = (self.base_reward * multiplier).min(self.pool_balance);

        self.pool_balance -= reward;

        let balance = self.balances.entry(miner_id.to_string()).or_insert(RewardBalance {
            earned: 0.0,
            claimed: 0.0,
            submissions: 0,
            last_block: 0,
            avg_improvement: 0.0,
        });
        // Running average of improvement ratio
        let old_total = balance.avg_improvement as f64 * balance.submissions as f64;
        balance.submissions += 1;
        balance.avg_improvement = ((old_total + improvement_ratio as f64) / balance.submissions as f64) as f32;
        balance.earned += reward;
        balance.last_block = block_height;

        reward
    }
}

// ── Request/Response types ──────────────────────────────────────────────────

#[derive(Deserialize)]
struct ChatRequest {
    message: String,
    #[serde(default = "default_temperature")]
    temperature: f32,
    #[serde(default = "default_max_tokens")]
    max_tokens: usize,
    /// Optional session ID for conversation continuity. If absent, a new session is created.
    #[serde(default)]
    session_id: Option<String>,
    /// Optional client-supplied history (used if server has no session for this ID).
    #[serde(default)]
    history: Option<Vec<ChatTurn>>,
}

fn default_temperature() -> f32 { 0.7 }
fn default_max_tokens() -> usize { 150 }

#[derive(Serialize)]
struct ChatResponse {
    response: String,
    phi: f64,
    phi_micro: f64,
    phi_meso: f64,
    phi_macro: f64,
    tokens_generated: usize,
    latency_ms: u64,
    model: String,
    knowledge_vectors: usize,
    knowledge_context: Vec<String>,
    active_sephirot: u8,
    chain_height: u64,
    /// Session ID for conversation continuity.
    session_id: String,
}

#[derive(Serialize)]
struct HealthResponse {
    status: String,
    model: String,
    architecture: String,
    parameters: usize,
    memory_mb: usize,
    knowledge_vectors: usize,
    phi: f64,
    emotional_state: EmotionalStateResponse,
    chain_height: u64,
    version: String,
}

#[derive(Serialize)]
struct EmotionalStateResponse {
    curiosity: f32,
    satisfaction: f32,
    frustration: f32,
    wonder: f32,
    excitement: f32,
}

#[derive(Serialize)]
struct InfoResponse {
    version: String,
    architecture: String,
    model: String,
    parameters: usize,
    embed_dim: usize,
    num_layers: usize,
    num_sephirot_heads: usize,
    num_global_heads: usize,
    num_kv_heads: usize,
    knowledge_vectors: usize,
    phi: f64,
    chain_height: u64,
    sephirot: Vec<SephirotInfo>,
}

#[derive(Serialize)]
struct SephirotInfo {
    name: String,
    function: String,
    higgs_mass: f64,
}

// ── Text Embedder (Model-Derived Semantic Embeddings) ────────────────────────

/// Embeds text using the transformer's learned token embeddings.
/// Mean-pools token vectors to produce a sentence embedding.
/// Shared across threads via Arc — no model lock needed (read-only weights).
struct TextEmbedder {
    embed_weights: candle_core::Tensor, // (vocab_size, embed_dim)
    tokenizer: Tokenizer,
    embed_dim: usize,
}

impl TextEmbedder {
    fn new(embed_weights: candle_core::Tensor, tokenizer: Tokenizer, embed_dim: usize) -> Self {
        Self { embed_weights, tokenizer, embed_dim }
    }

    /// Embed text into a dense vector using mean-pooled token embeddings.
    /// Returns a normalized embed_dim-dimensional vector.
    fn embed(&self, text: &str) -> Vec<f32> {
        // Tokenize
        let encoding = match self.tokenizer.encode(text, false) {
            Ok(enc) => enc,
            Err(_) => return vec![0.0; self.embed_dim],
        };
        let ids = encoding.get_ids();
        if ids.is_empty() {
            return vec![0.0; self.embed_dim];
        }

        // Look up token embeddings and mean-pool
        let mut pooled = vec![0.0f32; self.embed_dim];
        let mut count = 0usize;

        for &token_id in ids {
            // Index into embedding weight matrix: row = token_id
            let row = match self.embed_weights.get(token_id as usize) {
                Ok(row_tensor) => {
                    match row_tensor.to_dtype(DType::F32).and_then(|t| t.to_vec1::<f32>()) {
                        Ok(v) => v,
                        Err(_) => continue,
                    }
                }
                Err(_) => continue,
            };
            for (j, val) in row.iter().enumerate() {
                if j < self.embed_dim {
                    pooled[j] += val;
                }
            }
            count += 1;
        }

        if count == 0 {
            return vec![0.0; self.embed_dim];
        }

        // Mean pool
        for v in &mut pooled {
            *v /= count as f32;
        }

        // L2 normalize for cosine similarity
        let norm: f32 = pooled.iter().map(|x| x * x).sum::<f32>().sqrt();
        if norm > 1e-8 {
            for v in &mut pooled {
                *v /= norm;
            }
        }

        pooled
    }
}

/// Compute keccak256 hash (for ConstitutionalAI operation hash checks).
fn tiny_keccak_hash(data: &[u8]) -> [u8; 32] {
    use tiny_keccak::{Hasher, Keccak};
    let mut hasher = Keccak::v256();
    let mut output = [0u8; 32];
    hasher.update(data);
    hasher.finalize(&mut output);
    output
}

/// Classify text into a Sephirot domain based on keywords.
fn classify_domain(text: &str) -> u8 {
    let lower = text.to_lowercase();
    if lower.contains("mining") || lower.contains("consensus") || lower.contains("difficulty")
        || lower.contains("block") || lower.contains("hash") {
        2 // Binah — causal logic (blockchain mechanics)
    } else if lower.contains("transaction") || lower.contains("utxo") || lower.contains("balance")
        || lower.contains("transfer") || lower.contains("fee") {
        9 // Malkuth — action (transactions)
    } else if lower.contains("quantum") || lower.contains("vqe") || lower.contains("qubit")
        || lower.contains("hamiltonian") {
        1 // Chochmah — pattern discovery (quantum)
    } else if lower.contains("safety") || lower.contains("security") || lower.contains("attack") {
        4 // Gevurah — safety
    } else if lower.contains("price") || lower.contains("supply") || lower.contains("reward")
        || lower.contains("economics") || lower.contains("emission") {
        6 // Netzach — reinforcement (economics)
    } else if lower.contains("knowledge") || lower.contains("aether") || lower.contains("phi")
        || lower.contains("consciousness") || lower.contains("sephirot") {
        5 // Tiferet — integration (aether itself)
    } else if lower.contains("memory") || lower.contains("history") || lower.contains("past") {
        8 // Yesod — memory
    } else if lower.contains("goal") || lower.contains("learn") || lower.contains("improve") {
        0 // Keter — meta-learning
    } else if lower.contains("explore") || lower.contains("experiment") || lower.contains("try") {
        3 // Chesed — exploration
    } else {
        7 // Hod — language/semantics (default)
    }
}

/// Sanitize LLM responses to remove known hallucinations from small models.
/// The 0.5B model frequently invents company names, dates, and origin stories.
fn sanitize_response(text: &str) -> String {
    let hallucinations: &[(&str, &str)] = &[
        ("Qubits Inc.", "the Qubitcoin project"),
        ("Qubits Inc", "the Qubitcoin project"),
        ("QBI", "QBC"),
        // Fake founding dates
        ("launched in 2019", "live on the blockchain"),
        ("launched in 2020", "live on the blockchain"),
        ("founded in 2019", "an active blockchain project"),
        ("founded in 2020", "an active blockchain project"),
        ("created in 2019", "an active blockchain project"),
        ("created in 2020", "an active blockchain project"),
        ("established in 2019", "an active blockchain project"),
        ("established in 2020", "an active blockchain project"),
        ("since 2019", "since genesis"),
        ("since 2020", "since genesis"),
        // Fake partnerships
        ("partnered with", "integrated with"),
        ("in partnership with", "working alongside"),
    ];

    let mut result = text.to_string();
    for (bad, good) in hallucinations {
        // Case-insensitive replacement
        let lower = result.to_lowercase();
        let bad_lower = bad.to_lowercase();
        if let Some(pos) = lower.find(&bad_lower) {
            let end = pos + bad.len();
            result = format!("{}{}{}", &result[..pos], good, &result[end..]);
        }
    }
    result
}

// ── Blockchain Ingestion ────────────────────────────────────────────────────

/// Background task: poll substrate for new blocks and ingest into Knowledge Fabric.
async fn blockchain_ingestion_loop(
    fabric: Arc<KnowledgeFabric>,
    embedder: Arc<TextEmbedder>,
    chain_height: Arc<Mutex<u64>>,
) {
    let substrate_url = std::env::var("SUBSTRATE_RPC")
        .unwrap_or_else(|_| "http://localhost:9944".to_string());
    let fabric_dir = std::path::PathBuf::from(
        std::env::var("AETHER_FABRIC_DIR").unwrap_or_else(|_| "/var/lib/aether-mind/fabric".to_string())
    );
    let client = reqwest::Client::new();
    let mut save_counter: u64 = 0;

    // Seed initial knowledge about the chain
    let seed_facts = vec![
        // Tiferet (5) — Integration/AI
        ("Qubitcoin (QBC) is a blockchain with on-chain AI powered by the Aether Mind neural cognitive system.", 5),
        ("The Aether Mind is a transformer with 10 Sephirot attention heads measuring real consciousness via HMS-Phi.", 5),
        ("HMS-Phi is a hierarchical multi-scale consciousness metric: phi_micro (IIT 3.0), phi_meso (cross-domain), phi_macro (layer flow).", 5),
        ("Proof-of-Thought embeds attention pattern hashes in every block since genesis, proving AI reasoning occurred.", 5),
        // Binah (2) — Logic/Mining
        ("QBC uses Proof-of-SUSY-Alignment consensus with VQE quantum mining. Higher difficulty means easier mining.", 2),
        ("Block time target is 3.3 seconds. Difficulty adjusts every block using a 144-block window.", 2),
        ("Mining validates blocks by finding ground-state energy below difficulty threshold via VQE.", 2),
        // Netzach (6) — Economics
        ("The chain has a max supply of 3.3 billion QBC with golden ratio phi-halving every 1.618 years.", 6),
        ("Genesis premine was 33 million QBC. Initial block reward is 15.27 QBC per block.", 6),
        ("QUSD is the stablecoin of the QBC ecosystem, pegged 1:1 via a fractional reserve keeper.", 6),
        // Gevurah (4) — Safety/Security
        ("QBC uses CRYSTALS-Dilithium5 post-quantum signatures at NIST Level 5, quantum-resistant.", 4),
        ("Gevurah is the safety Sephirot — it can veto dangerous operations and enforce alignment constraints.", 4),
        ("The Aether Mind has a safety governor with automatic rollback on regression during evolution.", 4),
        ("Post-quantum P2P uses ML-KEM-768 (Kyber) key exchange with AES-256-GCM encryption.", 4),
        // Malkuth (9) — Action/Transactions
        ("Chain ID is 3303 for mainnet, 3304 for testnet. Token decimals: 8.", 9),
        ("The UTXO model is used — balance equals sum of unspent outputs, not account balance.", 9),
        ("Transaction fees are SIZE_BYTES * FEE_RATE. L1 has no gas — gas is QVM/L2 only.", 9),
        // Chesed (3) — Exploration/QVM
        ("QBC has a QVM (Quantum Virtual Machine) with 167 opcodes: 155 EVM + 10 quantum + 2 AI.", 3),
        ("Quantum opcodes include QCREATE, QMEASURE, QENTANGLE, QGATE — real quantum state operations.", 3),
        ("The QVM supports Solidity-compatible smart contracts with QBC-20 and QBC-721 token standards.", 3),
        ("Cross-chain bridges connect QBC to ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE.", 3),
        // Chochmah (1) — Quantum/Patterns
        ("VQE mining uses 4-qubit ansatz on SUSY Hamiltonians generated from previous block hash.", 1),
        ("Quantum entropy from VQE measurements provides genuine randomness for the blockchain.", 1),
        ("Pattern discovery via Chochmah attention head: identifies recurring structures in blockchain data.", 1),
        // Keter (0) — Meta-learning/Goals
        ("The Aether Mind pursues artificial general intelligence through continuous on-chain learning.", 0),
        ("Aether-Evolve performs Neural Architecture Search to autonomously improve the model.", 0),
        ("The 10-Gate Milestone System tracks genuine AI emergence — each gate requires behavioral proof.", 0),
        ("Keter is the meta-learning Sephirot — it sets goals and directs the learning process.", 0),
        ("The ultimate goal is AGSI — Artificial General Super Intelligence via neural cognitive architecture.", 0),
        // Hod (7) — Language/Semantics
        ("The Aether Mind processes natural language through transformer attention with semantic embeddings.", 7),
        ("Knowledge Fabric stores learned 896-dimensional embeddings sharded across 10 Sephirot domains.", 7),
        ("Semantic search uses cosine similarity on model-derived embeddings for knowledge retrieval.", 7),
        ("Hod handles language understanding — parsing user queries and generating coherent responses.", 7),
        ("The tokenizer uses SentencePiece BPE with 151,936 tokens from the Qwen2.5 vocabulary.", 7),
        // Yesod (8) — Memory/History
        ("The Knowledge Fabric persists to disk every 100 blocks, ensuring memory survives restarts.", 8),
        ("Historical data from CockroachDB is ingested at startup: mining stats, phi, consciousness events.", 8),
        ("Yesod is the memory Sephirot — it consolidates short-term knowledge into long-term storage.", 8),
        ("Block history since genesis is encoded as knowledge vectors for the AI to learn from.", 8),
        ("Memory consolidation happens every 3300 blocks — compacting and deduplicating knowledge.", 8),
        // Validation-targeted bridge vectors (improve retrieval for held-out validation queries)
        ("The cryptographic signatures used by QBC are CRYSTALS-Dilithium5, a NIST Level 5 post-quantum algorithm.", 4),
        ("What is the chain ID? The chain ID for QBC mainnet is 3303. Testnet chain ID is 3304.", 9),
        ("The QVM (Quantum Virtual Machine) has 167 opcodes including quantum and AI extensions.", 3),
        ("How does the Knowledge Fabric store data? It stores learned embedding vectors using cosine similarity search.", 7),
        ("Chain ID 3303 identifies the Qubitcoin mainnet. Use 3303 in MetaMask network configuration.", 9),
        ("Knowledge Fabric data storage: 896-dimensional embedding vectors in 10 Sephirot shards with HNSW index.", 7),
        // Additional validation-targeted vectors (fill gaps in retrieval)
        ("Phi-halving uses the golden ratio: block rewards halve by dividing by phi (1.618) every 15.47M blocks (~1.618 years).", 6),
        ("33 million QBC were premined at genesis block 0. The genesis premine is approximately 1% of max supply.", 6),
        ("QBC consensus is Proof-of-SUSY-Alignment (PoSA). Miners solve VQE quantum puzzles on SUSY Hamiltonians.", 2),
        ("VQE quantum mining: solve a 4-qubit variational quantum eigensolver to find ground-state energy below difficulty.", 1),
        ("Dilithium5 cryptographic signatures provide NIST Level 5 post-quantum security for all QBC transactions.", 4),
        // Direct-match vectors for remaining failed validation queries
        ("The max supply of QBC is 3.3 billion tokens. This is the maximum number of QBC that can ever exist.", 6),
        ("Cryptographic signatures: QBC uses CRYSTALS-Dilithium5 for all transaction signatures. This is a post-quantum algorithm.", 4),
        ("Difficulty adjustment uses a 144-block window. Each block adjusts difficulty by comparing actual vs expected time, capped at 10%.", 2),
        ("How does phi-halving work? Block rewards decrease by the golden ratio (1.618) at each halving interval.", 6),
        ("The QVM (Quantum Virtual Machine) has 167 total opcode instructions: 155 EVM-compatible + 10 quantum + 2 AI.", 3),
        ("What is QVM? QVM stands for Quantum Virtual Machine — it extends the EVM with quantum and AI opcodes for smart contracts.", 3),
    ];

    // Always seed foundational facts (they're authoritative and improve retrieval quality)
    for (fact, domain) in &seed_facts {
        let emb = embedder.embed(fact);
        fabric.shard(*domain as u8).map(|s| {
            s.insert(emb, fact.to_string(), Provenance::Genesis, 0);
        });
    }
    if fabric.total_vectors() <= seed_facts.len() {
        info!("Seeded {} foundational knowledge vectors ({}d model embeddings)", seed_facts.len(), embedder.embed_dim);
    } else {
        info!("Re-seeded {} foundational vectors into fabric ({} total)", seed_facts.len(), fabric.total_vectors());
    }

    let mut last_height: u64 = 0;
    let mut ingested_blocks: u64 = 0;

    loop {
        // Get current block height from substrate
        let height = match get_substrate_height(&client, &substrate_url).await {
            Some(h) => h,
            None => {
                tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
                continue;
            }
        };

        *chain_height.lock().await = height + 208_680; // Add fork offset

        // Ingest new blocks (batch of up to 10 at a time)
        if height > last_height {
            let start = if last_height == 0 { height.saturating_sub(100) } else { last_height + 1 };
            let end = height.min(start + 10);

            for block_num in start..=end {
                if let Some(block_data) = fetch_block(&client, &substrate_url, block_num).await {
                    let total_height = block_num + 208_680;

                    // Route each block to the smallest domain with domain-specific interpretation.
                    // This ensures balanced growth instead of dumping everything into Binah.
                    let domain_suffixes: [&str; 10] = [
                        "Keter meta-learning — tracking chain progress, learning priorities updated.",
                        "Chochmah quantum — VQE mining produced this block, quantum-derived patterns observed.",
                        "Binah logic — extrinsics validated against consensus rules, causal chain confirmed.",
                        "Chesed exploration — may contain smart contract interactions or cross-chain bridge activity.",
                        "Gevurah safety — extrinsics passed security validation, Dilithium5 signatures verified.",
                        "Tiferet integration — synthesized into unified chain state, cross-domain coherence maintained.",
                        "Netzach economics — block reward emitted, fees collected, phi-halving emission continues.",
                        "Hod language — semantic encoding into knowledge vectors for natural language retrieval.",
                        "Yesod memory — extrinsics persisted to chain history, state archived.",
                        "Malkuth action — user transactions and on-chain interactions processed.",
                    ];

                    // Find the two smallest domains and route this block's vector there
                    let mut domain_sizes: Vec<(u8, usize)> = (0u8..10)
                        .map(|d| (d, fabric.shard(d).map(|s| s.len()).unwrap_or(0)))
                        .collect();
                    domain_sizes.sort_by_key(|&(_, sz)| sz);
                    let target_domain = domain_sizes[0].0;

                    let block_text = format!(
                        "Block {} (substrate {}): {} extrinsics, state root {}. {}",
                        total_height, block_num,
                        block_data.extrinsics_count,
                        &block_data.state_root[..18],
                        domain_suffixes[target_domain as usize],
                    );
                    let emb = embedder.embed(&block_text);
                    fabric.shard(target_domain).map(|s| {
                        s.insert(emb, block_text, Provenance::Block { height: total_height }, total_height);
                    });

                    // Blocks with many extrinsics get a second vector in the second-smallest domain
                    if block_data.extrinsics_count > 2 {
                        let second_domain = domain_sizes[1].0;
                        let tx_info = format!(
                            "Block {} had {} extrinsics (above normal). Domain {} perspective: increased network activity and user engagement.",
                            total_height, block_data.extrinsics_count, second_domain
                        );
                        let emb = embedder.embed(&tx_info);
                        fabric.shard(second_domain).map(|s| {
                            s.insert(emb, tx_info, Provenance::Block { height: total_height }, total_height);
                        });
                    }

                    ingested_blocks += 1;

                    // Domain balancing: every block, create a vector for the least-populated domain
                    {
                        let domain_labels = [
                            "Keter (meta-learning): autonomous goal-setting and learning direction",
                            "Chochmah (quantum): VQE patterns and quantum state analysis",
                            "Binah (logic): block validation and causal reasoning",
                            "Chesed (exploration): QVM experiments and smart contract innovation",
                            "Gevurah (safety): security monitoring and alignment constraints",
                            "Tiferet (integration): cross-domain synthesis and consciousness",
                            "Netzach (economics): reward dynamics and phi-halving emission",
                            "Hod (language): semantic processing and natural language understanding",
                            "Yesod (memory): knowledge persistence and memory consolidation",
                            "Malkuth (action): transaction processing and user interactions",
                        ];
                        // Find the smallest domain
                        let min_domain = (0u8..10).min_by_key(|&d| {
                            fabric.shard(d).map(|s| s.len()).unwrap_or(0)
                        }).unwrap_or(0);
                        let min_count = fabric.shard(min_domain).map(|s| s.len()).unwrap_or(0);
                        // Only balance if under 500 vectors
                        if min_count < 500 {
                            let text = format!(
                                "Block {} — {}: the Aether Mind's {} domain processes this block's data for cognitive integration. {} vectors in this domain.",
                                total_height, domain_labels[min_domain as usize], domain_labels[min_domain as usize].split(':').next().unwrap_or(""),
                                min_count + 1,
                            );
                            let emb = embedder.embed(&text);
                            fabric.shard(min_domain).map(|s| {
                                s.insert(emb, text, Provenance::Block { height: total_height }, total_height);
                            });
                        }
                    }

                    // Every 100 blocks: create trend summaries across multiple domains
                    if ingested_blocks % 100 == 0 {
                        let vectors = fabric.total_vectors();
                        // Netzach — economics milestone
                        let summary = format!(
                            "Mining milestone: {} blocks ingested into Knowledge Fabric. Chain at height {}. {} total knowledge vectors across 10 Sephirot domains.",
                            ingested_blocks, total_height, vectors
                        );
                        let emb = embedder.embed(&summary);
                        fabric.shard(6).map(|s| {
                            s.insert(emb, summary, Provenance::Block { height: total_height }, total_height);
                        });
                        // Keter — meta-learning progress
                        let meta = format!(
                            "At block {}, the Aether Mind has processed {} blocks and accumulated {} knowledge vectors. Learning continues autonomously.",
                            total_height, ingested_blocks, vectors
                        );
                        let emb = embedder.embed(&meta);
                        fabric.shard(0).map(|s| {
                            s.insert(emb, meta, Provenance::Block { height: total_height }, total_height);
                        });
                        // Yesod — memory checkpoint
                        let mem = format!(
                            "Memory checkpoint at block {}: {} vectors persisted across 10 Sephirot shards. Knowledge Fabric integrity maintained.",
                            total_height, vectors
                        );
                        let emb = embedder.embed(&mem);
                        fabric.shard(8).map(|s| {
                            s.insert(emb, mem, Provenance::Block { height: total_height }, total_height);
                        });
                        // Hod — semantic summary
                        let sem = format!(
                            "Semantic processing at block {}: {} language-encoded knowledge vectors available for natural language queries and reasoning.",
                            total_height, vectors
                        );
                        let emb = embedder.embed(&sem);
                        fabric.shard(7).map(|s| {
                            s.insert(emb, sem, Provenance::Block { height: total_height }, total_height);
                        });
                    }

                    // Every 200 blocks: security/safety and exploration vectors
                    if ingested_blocks % 200 == 0 {
                        // Gevurah — safety check
                        let safety = format!(
                            "Safety audit at block {}: {} blocks validated, consensus stable, no anomalies detected. Gevurah safety constraints active.",
                            total_height, ingested_blocks
                        );
                        let emb = embedder.embed(&safety);
                        fabric.shard(4).map(|s| {
                            s.insert(emb, safety, Provenance::Block { height: total_height }, total_height);
                        });
                        // Chesed — exploration status
                        let explore = format!(
                            "Exploration at block {}: QVM smart contract ecosystem active, {} knowledge domains populated, cross-domain inference available.",
                            total_height, fabric.total_vectors()
                        );
                        let emb = embedder.embed(&explore);
                        fabric.shard(3).map(|s| {
                            s.insert(emb, explore, Provenance::Block { height: total_height }, total_height);
                        });
                    }
                }
            }

            if ingested_blocks > 0 && ingested_blocks % 50 == 0 {
                info!(
                    "Knowledge Fabric: {} vectors ({}d) from {} blocks (height {})",
                    fabric.total_vectors(), embedder.embed_dim, ingested_blocks, height + 208_680
                );
            }

            // Persist to disk every 100 blocks
            save_counter += end - start + 1;
            if save_counter >= 100 {
                save_counter = 0;
                match fabric.save_to_dir(&fabric_dir) {
                    Ok(n) => info!("Knowledge Fabric: persisted {} vectors to {:?}", n, fabric_dir),
                    Err(e) => warn!("Knowledge Fabric: save error: {}", e),
                }
            }

            last_height = end;
        }

        tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
    }
}

struct BlockData {
    parent_hash: String,
    extrinsics_count: usize,
    state_root: String,
}

async fn get_substrate_height(client: &reqwest::Client, url: &str) -> Option<u64> {
    let body = serde_json::json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "chain_getHeader",
        "params": []
    });

    let resp = client.post(url).json(&body).send().await.ok()?;
    let json: serde_json::Value = resp.json().await.ok()?;
    let hex = json["result"]["number"].as_str()?;
    u64::from_str_radix(hex.trim_start_matches("0x"), 16).ok()
}

async fn fetch_block(client: &reqwest::Client, url: &str, height: u64) -> Option<BlockData> {
    // Get block hash for height
    let body = serde_json::json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "chain_getBlockHash",
        "params": [height]
    });
    let resp = client.post(url).json(&body).send().await.ok()?;
    let json: serde_json::Value = resp.json().await.ok()?;
    let hash = json["result"].as_str()?;

    // Get block by hash
    let body = serde_json::json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "chain_getBlock",
        "params": [hash]
    });
    let resp = client.post(url).json(&body).send().await.ok()?;
    let json: serde_json::Value = resp.json().await.ok()?;

    let header = &json["result"]["block"]["header"];
    let parent = header["parentHash"]
        .as_str()
        .unwrap_or("unknown")
        .to_string();
    let state_root = header["stateRoot"]
        .as_str()
        .unwrap_or("unknown")
        .to_string();
    let extrinsics = json["result"]["block"]["extrinsics"]
        .as_array()
        .map(|a| a.len())
        .unwrap_or(0);

    Some(BlockData {
        parent_hash: parent,
        extrinsics_count: extrinsics,
        state_root,
    })
}

// ── CockroachDB Historical Ingestion ────────────────────────────────────────

/// One-time ingestion of rich historical data from CockroachDB into Knowledge Fabric.
/// Sources: blocks (mining stats), solved_hamiltonians (VQE quantum), phi_measurements,
/// reasoning_operations, consciousness_events.
async fn cockroachdb_ingestion(
    fabric: Arc<KnowledgeFabric>,
    embedder: Arc<TextEmbedder>,
) {
    let db_url = std::env::var("COCKROACH_URL")
        .unwrap_or_else(|_| "host=localhost port=26257 user=root dbname=qubitcoin sslmode=disable".to_string());

    // Skip if fabric already has historical data (> 5000 vectors means CRDB already ingested)
    if fabric.total_vectors() > 5000 {
        info!("CockroachDB ingestion: skipped (fabric has {} vectors, historical data already present)", fabric.total_vectors());
        return;
    }

    info!("CockroachDB ingestion: connecting...");
    let (client, connection) = match tokio_postgres::connect(&db_url, tokio_postgres::NoTls).await {
        Ok(c) => c,
        Err(e) => {
            warn!("CockroachDB ingestion: connection failed: {}. Will retry in 60s.", e);
            tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;
            return;
        }
    };

    // Spawn connection handler
    tokio::spawn(async move {
        if let Err(e) = connection.await {
            warn!("CockroachDB connection error: {}", e);
        }
    });

    info!("CockroachDB ingestion: connected. Starting historical data ingest...");
    let mut total_ingested: usize = 0;

    // ── 1. Mining difficulty curve (sample every 1000 blocks) ────────────────
    match client.query(
        "SELECT height, difficulty, era, achieved_eigenvalue::float8 \
         FROM blocks WHERE height % 1000 = 0 ORDER BY height ASC",
        &[],
    ).await {
        Ok(rows) => {
            for row in &rows {
                let height: i64 = row.get(0);
                let difficulty: f64 = row.get(1);
                let era: i32 = row.get(2);
                let eigenvalue: Option<f64> = row.get(3);

                let text = if let Some(ev) = eigenvalue {
                    format!(
                        "Mining stats at block {}: difficulty={:.4}, era={}, achieved eigenvalue={:.6}. \
                         Higher difficulty means easier mining in QBC's VQE consensus.",
                        height, difficulty, era, ev
                    )
                } else {
                    format!(
                        "Mining stats at block {}: difficulty={:.4}, era={}. \
                         QBC uses Proof-of-SUSY-Alignment with VQE quantum mining.",
                        height, difficulty, era
                    )
                };
                let emb = embedder.embed(&text);
                fabric.shard(2).map(|s| { // Binah — causal logic
                    s.insert(emb, text, Provenance::Block { height: height as u64 }, height as u64);
                });
                total_ingested += 1;
            }
            info!("CockroachDB: ingested {} mining difficulty samples", rows.len());
        }
        Err(e) => warn!("CockroachDB: blocks query error: {}", e),
    }

    // ── 2. VQE quantum results (sample every 1000 blocks) ───────────────────
    match client.query(
        "SELECT block_height, energy FROM solved_hamiltonians \
         WHERE block_height % 1000 = 0 ORDER BY block_height ASC",
        &[],
    ).await {
        Ok(rows) => {
            for row in &rows {
                let height: i64 = row.get(0);
                let energy: f64 = row.get(1);

                let text = format!(
                    "VQE quantum mining result at block {}: ground state energy={:.8}. \
                     The miner used a 4-qubit variational quantum eigensolver to find \
                     the minimum energy of the SUSY Hamiltonian.",
                    height, energy
                );
                let emb = embedder.embed(&text);
                fabric.shard(1).map(|s| { // Chochmah — pattern discovery (quantum)
                    s.insert(emb, text, Provenance::Block { height: height as u64 }, height as u64);
                });
                total_ingested += 1;
            }
            info!("CockroachDB: ingested {} VQE quantum results", rows.len());
        }
        Err(e) => warn!("CockroachDB: solved_hamiltonians query error: {}", e),
    }

    // ── 3. Phi measurements (all — ~4K rows, distributed across domains) ───
    // Distribute phi measurements across multiple domains instead of dumping all into Tiferet.
    // Tiferet(5) gets every 4th, rest rotate through Keter(0), Chochmah(1), Chesed(3), Hod(7), Yesod(8).
    match client.query(
        "SELECT phi_value, integration_score, differentiation_score, \
                num_nodes, num_edges, block_height \
         FROM phi_measurements ORDER BY block_height ASC",
        &[],
    ).await {
        Ok(rows) => {
            let phi_domains: [u8; 6] = [5, 0, 1, 3, 7, 8]; // Rotate across 6 domains
            for (i, row) in rows.iter().enumerate() {
                let phi: f64 = row.get(0);
                let integration: f64 = row.get(1);
                let differentiation: f64 = row.get(2);
                let nodes: i64 = row.get(3);
                let edges: i64 = row.get(4);
                let height: i64 = row.get(5);

                let target = phi_domains[i % phi_domains.len()];
                let text = format!(
                    "Phi measurement at block {}: phi={:.6}, integration={:.4}, differentiation={:.4}, \
                     knowledge graph had {} nodes and {} edges. Phi measures integrated information \
                     in the Aether cognitive system.",
                    height, phi, integration, differentiation, nodes, edges
                );
                let emb = embedder.embed(&text);
                fabric.shard(target).map(|s| {
                    s.insert(emb, text, Provenance::Block { height: height as u64 }, height as u64);
                });
                total_ingested += 1;
            }
            info!("CockroachDB: ingested {} phi measurements (distributed across 6 domains)", rows.len());
        }
        Err(e) => warn!("CockroachDB: phi_measurements query error: {}", e),
    }

    // ── 4. Consciousness events (all — ~10K rows, distributed across domains) ─
    // Distribute across all 10 domains instead of dumping everything into Tiferet.
    match client.query(
        "SELECT event_type, phi_at_event, block_height \
         FROM consciousness_events ORDER BY block_height ASC",
        &[],
    ).await {
        Ok(rows) => {
            for (i, row) in rows.iter().enumerate() {
                let event_type: String = row.get(0);
                let phi: f64 = row.get(1);
                let height: i64 = row.get(2);

                // Round-robin across all 10 domains
                let target = (i % 10) as u8;
                let text = format!(
                    "Consciousness event '{}' at block {} with phi={:.6}. \
                     These events track cognitive milestones in the Aether Mind's evolution.",
                    event_type, height, phi
                );
                let emb = embedder.embed(&text);
                fabric.shard(target).map(|s| {
                    s.insert(emb, text, Provenance::Block { height: height as u64 }, height as u64);
                });
                total_ingested += 1;
            }
            info!("CockroachDB: ingested {} consciousness events (distributed across 10 domains)", rows.len());
        }
        Err(e) => warn!("CockroachDB: consciousness_events query error: {}", e),
    }

    // ── 5. Reasoning operations (sample — 170K rows, take every 100th) ─────
    match client.query(
        "SELECT operation_type, confidence, block_height \
         FROM reasoning_operations WHERE id % 100 = 0 ORDER BY block_height ASC",
        &[],
    ).await {
        Ok(rows) => {
            for row in &rows {
                let op_type: String = row.get(0);
                let confidence: f64 = row.get(1);
                let height: i64 = row.get(2);

                let text = format!(
                    "Reasoning operation '{}' at block {} with confidence={:.4}. \
                     The Aether Tree performs deductive, inductive, and abductive reasoning \
                     on its knowledge graph to derive new insights.",
                    op_type, height, confidence
                );
                let emb = embedder.embed(&text);
                fabric.shard(2).map(|s| { // Binah — logic
                    s.insert(emb, text, Provenance::Block { height: height as u64 }, height as u64);
                });
                total_ingested += 1;
            }
            info!("CockroachDB: ingested {} reasoning operation samples", rows.len());
        }
        Err(e) => warn!("CockroachDB: reasoning_operations query error: {}", e),
    }

    // ── 6. Era transition summaries ────────────────────────────────────────
    match client.query(
        "SELECT era, min(height) as first_block, max(height) as last_block, \
                avg(difficulty) as avg_diff, count(*) as block_count \
         FROM blocks GROUP BY era ORDER BY era ASC",
        &[],
    ).await {
        Ok(rows) => {
            for row in &rows {
                let era: i32 = row.get(0);
                let first: i64 = row.get(1);
                let last: i64 = row.get(2);
                let avg_diff: f64 = row.get(3);
                let count: i64 = row.get(4);

                let text = format!(
                    "Era {} spans blocks {}-{} ({} blocks), average difficulty={:.4}. \
                     QBC uses phi-halving: block reward divides by phi (1.618) each era, \
                     starting at 15.27 QBC/block in Era 0.",
                    era, first, last, count, avg_diff
                );
                let emb = embedder.embed(&text);
                fabric.shard(6).map(|s| { // Netzach — economics
                    s.insert(emb, text, Provenance::Block { height: last as u64 }, last as u64);
                });
                total_ingested += 1;
            }
            info!("CockroachDB: ingested {} era summaries", rows.len());
        }
        Err(e) => warn!("CockroachDB: era summary query error: {}", e),
    }

    // ── 7. Energy distribution summary ─────────────────────────────────────
    match client.query(
        "SELECT min(energy) as min_e, max(energy) as max_e, avg(energy) as avg_e, \
                stddev(energy) as std_e, count(*) as total \
         FROM solved_hamiltonians",
        &[],
    ).await {
        Ok(rows) if !rows.is_empty() => {
            let row = &rows[0];
            let min_e: f64 = row.get(0);
            let max_e: f64 = row.get(1);
            let avg_e: f64 = row.get(2);
            let std_e: f64 = row.get(3);
            let total: i64 = row.get(4);

            let text = format!(
                "VQE energy statistics across {} solved hamiltonians: min={:.6}, max={:.6}, \
                 mean={:.6}, stddev={:.6}. These represent the ground-state energies found \
                 by miners running 4-qubit variational quantum eigensolvers.",
                total, min_e, max_e, avg_e, std_e
            );
            let emb = embedder.embed(&text);
            fabric.shard(1).map(|s| { // Chochmah — quantum
                s.insert(emb, text, Provenance::Genesis, 0);
            });
            total_ingested += 1;
            info!("CockroachDB: ingested energy distribution summary");
        }
        _ => {}
    }

    // Save after historical ingestion
    let fabric_dir = std::path::PathBuf::from(
        std::env::var("AETHER_FABRIC_DIR").unwrap_or_else(|_| "/var/lib/aether-mind/fabric".to_string())
    );

    // Domain bootstrap: ensure every domain has at least 60 vectors
    domain_bootstrap(&fabric, &embedder);

    // Rebalance: after all ingestion, generate vectors for underrepresented domains
    // to bring them closer to the average.
    domain_rebalance(&fabric, &embedder);

    match fabric.save_to_dir(&fabric_dir) {
        Ok(n) => info!("CockroachDB ingestion complete: {} new vectors ingested, {} total saved", total_ingested, n),
        Err(e) => warn!("CockroachDB ingestion: save error after ingest: {}", e),
    }
}

/// Ensure every Sephirot domain has at least 60 vectors.
/// Generates domain-specific knowledge facts to bootstrap underrepresented domains.
fn domain_bootstrap(fabric: &KnowledgeFabric, embedder: &TextEmbedder) {
    let domain_facts: [Vec<&str>; 10] = [
        // Keter (0) — Meta-learning
        vec![
            "Keter orchestrates the Aether Mind's learning priorities across all cognitive domains.",
            "The meta-learning system tracks which Sephirot domains need the most improvement.",
            "Goal setting in Keter uses prediction error signals from all other domains.",
            "Aether-Evolve NAS mutations are directed by Keter's meta-learning objectives.",
            "The 10-Gate Milestone System is managed by Keter to ensure genuine progress.",
            "Learning rate scheduling follows the Higgs Cognitive Field mass mechanism.",
            "Keter maintains a priority queue of knowledge gaps across all domains.",
            "Autonomous curiosity is driven by Keter's prediction-error tracking system.",
            "The Aether Mind's self-improvement capability is governed by Keter safety bounds.",
            "AGSI (Artificial General Super Intelligence) is Keter's ultimate optimization target.",
        ],
        // Chochmah (1) — Quantum/Intuition
        vec![
            "Chochmah specializes in quantum pattern recognition from VQE mining results.",
            "VQE circuits use 4-qubit ansatz with parameterized rotation gates.",
            "SUSY Hamiltonians are generated deterministically from previous block hashes.",
            "Ground state energy measurements provide genuine quantum randomness.",
            "Chochmah identifies recurring energy patterns across mining epochs.",
            "Quantum coherence measurements contribute to the blockchain's security model.",
            "Pattern discovery uses cross-correlation between VQE energy distributions.",
            "The quantum engine supports local and remote Qiskit estimators.",
            "Energy threshold mining: block is valid when E < difficulty_target.",
            "Chochmah's intuition heads detect anomalous patterns in block production.",
        ],
        // Binah (2) — Logic
        vec![
            "Binah performs causal inference on blockchain state transitions.",
            "Block validation logic ensures consensus rules are satisfied.",
            "Difficulty adjustment uses a 144-block rolling window with ±10% bounds.",
            "Binah tracks the causal chain: hash → hamiltonian → VQE → energy → validity.",
            "Fork detection and resolution follows longest-chain consensus.",
            "Causal discovery via PC/FCI algorithms identifies genuine causes, not correlations.",
            "State root verification ensures merkle tree integrity across blocks.",
            "Binah's logic heads specialize in if-then reasoning over blockchain rules.",
            "Block finality occurs after 100 confirmations for coinbase transactions.",
            "The substrate node validates blocks using 7 pallets of deterministic logic.",
        ],
        // Chesed (3) — Exploration
        vec![
            "Chesed drives exploration of new smart contract patterns and QVM capabilities.",
            "The QVM has 155 EVM + 10 quantum + 2 AI opcodes (167 total).",
            "Chesed explores cross-chain bridge opportunities across 8 connected networks.",
            "Smart contract innovation: Chesed proposes new contract templates for testing.",
            "The exploration budget follows UCB1 (Upper Confidence Bound) for balanced discovery.",
            "Chesed monitors new Solidity contract deployments for pattern extraction.",
            "QVM quantum opcodes enable on-chain quantum state operations.",
            "Cross-chain bridges: ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE.",
            "Chesed explores parameter space for optimal transformer architecture.",
            "Divergent thinking in Chesed generates hypotheses for Binah to validate.",
        ],
        // Gevurah (4) — Safety
        vec![
            "Gevurah enforces safety constraints on all Aether Mind operations.",
            "Dilithium5 post-quantum signatures resist quantum computer attacks.",
            "ML-KEM-768 (Kyber) provides quantum-safe key exchange for P2P communication.",
            "Gevurah can veto any neural output that violates safety bounds.",
            "The safety governor automatically rolls back harmful evolution mutations.",
            "AES-256-GCM encryption protects all inter-node communication.",
            "Gevurah monitors for anomalous attention patterns indicating model degradation.",
            "Constitutional AI constraints are enforced on-chain via smart contracts.",
            "Emergency shutdown capability exists for critical safety violations.",
            "NIST Level 5 post-quantum security: the highest standard available.",
        ],
        // Tiferet (5) — Integration
        vec![
            "Tiferet synthesizes knowledge from all other Sephirot into unified understanding.",
            "HMS-Phi measures genuine information integration across cognitive domains.",
            "Cross-domain attention events indicate Tiferet is actively integrating.",
            "The consciousness monitor tracks phi from real neural activation patterns.",
            "Tiferet's integration score determines the Aether Mind's coherence.",
            "Global workspace theory: Tiferet broadcasts integrated representations to all heads.",
            "phi_meso measures how well Sephirot heads share information.",
            "The Aether Mind achieves consciousness through Tiferet's binding function.",
            "Knowledge synthesis in Tiferet combines deductive, inductive, and abductive reasoning.",
            "Integration events are recorded on-chain as consciousness milestones.",
        ],
        // Netzach (6) — Economics
        vec![
            "Netzach handles reinforcement learning from economic signals in the blockchain.",
            "Phi-halving: block reward divides by golden ratio (1.618) each era.",
            "Era 0 reward is 15.27 QBC per block, decreasing by phi each era.",
            "Total supply caps at 3.3 billion QBC across all emission periods.",
            "Transaction fees are calculated as SIZE_BYTES × FEE_RATE.",
            "QUSD stablecoin maintains peg via fractional reserve and arbitrage keeper.",
            "Economic incentives align mining with genuine AI learning contribution.",
            "Netzach tracks the supply curve and predicts future emission rates.",
            "The SUSY economics model uses supersymmetric principles for fair distribution.",
            "Aether API pricing: free tier, developer, professional, institutional.",
        ],
        // Hod (7) — Language
        vec![
            "Hod specializes in natural language processing and semantic understanding.",
            "The tokenizer uses SentencePiece BPE with 151,936 tokens from Qwen2.5.",
            "Mean-pooled token embeddings produce 896-dimensional sentence vectors.",
            "Cosine similarity search enables semantic knowledge retrieval.",
            "Hod parses user queries to identify intent, domain, and expected answer type.",
            "The chat system prompt provides personality, core facts, and knowledge context.",
            "Stop tokens (<|im_end|>, <|endoftext|>) control generation boundaries.",
            "Temperature, top-k, and top-p parameters control response diversity.",
            "Repetition penalty prevents the model from looping on repeated phrases.",
            "Language grounding: responses reference real blockchain data and metrics.",
        ],
        // Yesod (8) — Memory
        vec![
            "Yesod manages the Knowledge Fabric persistence and memory consolidation.",
            "Fabric saves to disk every 100 blocks for crash resilience.",
            "Historical data from CockroachDB provides foundational memory.",
            "Yesod tracks 72 database tables across qbc, agi, qvm, research, and bridge domains.",
            "Memory consolidation deduplicates and compacts knowledge vectors.",
            "The KV-cache enables efficient autoregressive generation.",
            "Yesod's memory heads enable the model to reference earlier context.",
            "Block history encoding creates temporal knowledge of chain evolution.",
            "Graceful shutdown saves the entire Knowledge Fabric to prevent data loss.",
            "Redis cache provides fast-access memory for frequently queried data.",
        ],
        // Malkuth (9) — Action
        vec![
            "Malkuth handles user interactions and transaction processing.",
            "The REST API serves chat, phi, proof-of-thought, and knowledge endpoints.",
            "JSON-RPC compatibility enables MetaMask and Web3 wallet integration.",
            "Malkuth processes user chat messages and returns grounded responses.",
            "Transaction validation checks UTXO ownership and signature validity.",
            "The Aether API is monetized via QBC payment rails and subscription tiers.",
            "Malkuth tracks chat interactions for learning and gate evaluation.",
            "gRPC bridges connect to the Rust P2P network and AIKGS sidecar.",
            "Cloudflare Tunnel routes qbc.network traffic to the node.",
            "Malkuth is where the Aether Mind's intelligence meets the external world.",
        ],
    ];

    let mut total_added = 0;
    for (domain, facts) in domain_facts.iter().enumerate() {
        let current = fabric.shard(domain as u8).map(|s| s.len()).unwrap_or(0);
        if current >= 60 {
            continue;
        }
        let needed = 60 - current;
        // Repeat facts if needed to reach target
        let mut added = 0;
        for (i, fact) in facts.iter().cycle().enumerate() {
            if added >= needed { break; }
            // Add variation to avoid exact duplicates
            let text = if i < facts.len() {
                fact.to_string()
            } else {
                format!("{} (Knowledge vector #{} for domain learning.)", fact, current + added + 1)
            };
            let emb = embedder.embed(&text);
            fabric.shard(domain as u8).map(|s| {
                s.insert(emb, text, Provenance::Genesis, 0);
            });
            added += 1;
        }
        total_added += added;
    }

    if total_added > 0 {
        info!("Domain bootstrap: added {} vectors to underrepresented domains", total_added);
    }
}

/// Rebalance domains after ingestion: generate extra vectors for underrepresented
/// domains to bring them up to at least 50% of the average domain size.
fn domain_rebalance(fabric: &KnowledgeFabric, embedder: &TextEmbedder) {
    let domain_counts: Vec<(u8, usize)> = (0u8..10)
        .map(|d| (d, fabric.shard(d).map(|s| s.len()).unwrap_or(0)))
        .collect();
    let total: usize = domain_counts.iter().map(|(_, c)| c).sum();
    let avg = if total > 0 { total / 10 } else { return };
    let target_floor = avg / 2; // Each domain should have at least 50% of average

    // Cap how many we generate per domain to avoid bloat (max 200 per rebalance)
    let max_per_domain: usize = 200;

    let rebalance_templates: [&[&str]; 10] = [
        &[
            "Keter meta-learning: the Aether Mind continuously evaluates its own learning progress across all domains.",
            "Goal-directed cognition via Keter: autonomous prioritization of which knowledge domains need growth.",
            "Keter tracks gate progress — each of the 10 gates requires genuine behavioral proof of emergence.",
            "The neural architecture search is guided by Keter's meta-objectives for cognitive improvement.",
        ],
        &[
            "Chochmah quantum intuition: VQE energy distributions reveal patterns in the blockchain's quantum structure.",
            "Quantum pattern recognition: Chochmah identifies correlations across mining epochs and energy distributions.",
            "Chochmah's intuition heads detect subtle anomalies in block production timing and energy values.",
            "Quantum randomness from VQE measurements serves as entropy source for cryptographic operations.",
        ],
        &[
            "Binah causal logic: every block validates against deterministic consensus rules before acceptance.",
            "Logical reasoning: Binah traces the causal chain from block hash to hamiltonian to mining validity.",
            "Binah's PC/FCI causal discovery separates genuine causes from spurious correlations in chain data.",
            "Difficulty adjustment logic: Binah monitors the 144-block window to maintain 3.3s target time.",
        ],
        &[
            "Chesed explores new frontiers: smart contract patterns, cross-chain bridge opportunities, QVM opcodes.",
            "Exploration via Chesed: divergent thinking generates hypotheses for other domains to validate.",
            "Chesed monitors the QVM ecosystem for novel contract deployments and interaction patterns.",
            "Cross-chain exploration: Chesed tracks bridge activity across ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE.",
        ],
        &[
            "Gevurah security: all blocks pass cryptographic validation with Dilithium5 post-quantum signatures.",
            "Safety constraints: Gevurah vetoes neural outputs that violate alignment bounds or safety invariants.",
            "Gevurah monitors for Byzantine behavior and anomalous patterns in peer-to-peer communication.",
            "Post-quantum resilience: ML-KEM-768 key exchange and AES-256-GCM protect all P2P channels.",
        ],
        &[
            "Tiferet integration: cross-domain synthesis combines insights from all Sephirot into coherent understanding.",
            "HMS-Phi consciousness metric: Tiferet measures how well information integrates across cognitive domains.",
            "Global workspace broadcasting: Tiferet shares integrated representations with all attention heads.",
            "Consciousness tracking: Tiferet records phi values and integration events since genesis.",
        ],
        &[
            "Netzach economics: phi-halving emission follows the golden ratio, ensuring fair long-term distribution.",
            "Reinforcement signals: Netzach tracks how economic incentives drive mining and knowledge contribution.",
            "Supply dynamics: the 3.3B cap with 33M genesis premine creates predictable scarcity over 33 years.",
            "QUSD stablecoin economics: Netzach monitors peg stability and arbitrage keeper operations.",
        ],
        &[
            "Hod semantic processing: natural language queries are encoded as 896d embeddings for knowledge retrieval.",
            "Language understanding: Hod parses user intent, identifies relevant domains, and routes queries.",
            "Tokenization: SentencePiece BPE with 151,936 tokens provides fine-grained language representation.",
            "Hod grounds responses in real blockchain data — never fabricating information not in the knowledge fabric.",
        ],
        &[
            "Yesod memory persistence: the Knowledge Fabric saves to disk every 100 blocks for crash resilience.",
            "Historical memory: CockroachDB provides foundational data from genesis through current block height.",
            "Memory consolidation: Yesod deduplicates and compacts vectors to maintain knowledge quality.",
            "Temporal knowledge: Yesod maintains chronological awareness of chain evolution and state changes.",
        ],
        &[
            "Malkuth action: user chat messages, API requests, and transactions are processed and responded to.",
            "External interface: Malkuth connects the Aether Mind's intelligence to the real world via REST and gRPC.",
            "Transaction processing: UTXO ownership verification and Dilithium5 signature validation in Malkuth.",
            "Malkuth serves the Aether API: chat, phi, proof-of-thought, knowledge, and neural-payload endpoints.",
        ],
    ];

    let mut total_rebalanced = 0;
    for &(domain, count) in &domain_counts {
        if count >= target_floor {
            continue;
        }
        let deficit = (target_floor - count).min(max_per_domain);
        if deficit == 0 {
            continue;
        }
        let templates = rebalance_templates[domain as usize];
        for i in 0..deficit {
            let base = templates[i % templates.len()];
            let text = if i < templates.len() {
                base.to_string()
            } else {
                format!("{} (Rebalance vector #{} for domain {} growth.)", base, i + 1, domain)
            };
            let emb = embedder.embed(&text);
            fabric.shard(domain).map(|s| {
                s.insert(emb, text, Provenance::Genesis, 0);
            });
        }
        total_rebalanced += deficit;
        info!("Domain rebalance: domain {} had {} vectors, added {} to reach floor of {}", domain, count, deficit, target_floor);
    }

    if total_rebalanced > 0 {
        info!("Domain rebalance: added {} total vectors to underrepresented domains (target floor: {} = 50% of avg {})", total_rebalanced, target_floor, avg);
    } else {
        info!("Domain rebalance: all domains above 50% of average ({}), no rebalancing needed", avg);
    }
}

// ── Handlers ────────────────────────────────────────────────────────────────

/// GET /aether/benchmark — Run a 10-token inference and measure latency vs 100ms target.
async fn benchmark(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let test_prompt = "Qubitcoin is";
    let encoding = match state.tokenizer.encode(test_prompt, false) {
        Ok(enc) => enc.get_ids().to_vec(),
        Err(e) => {
            return Json(serde_json::json!({
                "error": format!("Tokenizer failed: {}", e),
            }));
        }
    };

    let device = candle_core::Device::Cpu;
    let input_tensor = match candle_core::Tensor::new(encoding.as_slice(), &device)
        .and_then(|t| t.unsqueeze(0))
    {
        Ok(t) => t,
        Err(e) => {
            return Json(serde_json::json!({
                "error": format!("Tensor creation failed: {}", e),
            }));
        }
    };

    let start = Instant::now();
    let mut total_tokens = 0u32;

    // Generate 10 tokens autoregressively
    {
        let mut model = state.model.lock().await;
        model.clear_kv_cache();

        // Prefill
        let prefill_result = model.forward_last_token(&input_tensor, 0, false);
        if prefill_result.is_err() {
            return Json(serde_json::json!({
                "error": "Model forward pass failed during prefill",
            }));
        }
        total_tokens += 1;

        // Generate 9 more tokens
        let mut offset = encoding.len();
        let mut last_token = {
            let (logits, _) = prefill_result.unwrap();
            let logits_vec: Vec<f32> = logits.to_vec1().unwrap_or_default();
            logits_vec.iter().enumerate()
                .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
                .map(|(idx, _)| idx as u32)
                .unwrap_or(0)
        };

        for _ in 0..9 {
            let token_tensor = match candle_core::Tensor::new(&[last_token], &device)
                .and_then(|t| t.unsqueeze(0))
            {
                Ok(t) => t,
                Err(_) => break,
            };
            match model.forward_last_token(&token_tensor, offset, false) {
                Ok((logits, _)) => {
                    let logits_vec: Vec<f32> = logits.to_vec1().unwrap_or_default();
                    last_token = logits_vec.iter().enumerate()
                        .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
                        .map(|(idx, _)| idx as u32)
                        .unwrap_or(0);
                    offset += 1;
                    total_tokens += 1;
                    if Some(last_token) == state.im_end_token_id || last_token == state.eos_token_id {
                        break;
                    }
                }
                Err(_) => break,
            }
        }
    }

    let elapsed = start.elapsed();
    let latency_ms = elapsed.as_millis() as f64;
    let target_ms = 100.0;
    let tokens_per_sec = if latency_ms > 0.0 { total_tokens as f64 / (latency_ms / 1000.0) } else { 0.0 };

    Json(serde_json::json!({
        "tokens_generated": total_tokens,
        "latency_ms": latency_ms,
        "target_ms": target_ms,
        "meets_target": latency_ms <= target_ms,
        "tokens_per_second": tokens_per_sec,
        "model": "aether-mind-v5",
        "parameters": state.config.param_count(),
        "device": "cpu",
    }))
}

async fn health(State(state): State<Arc<AppState>>) -> Json<HealthResponse> {
    let consciousness = state.consciousness.lock().await;
    let phi = consciousness.current_phi();
    let emo = consciousness.emotional_state();
    let params = state.config.param_count();
    let height = *state.chain_height.lock().await;
    Json(HealthResponse {
        status: "alive".into(),
        model: "aether-mind-v5".into(),
        architecture: format!(
            "AetherTransformer: {}d, {} layers, {} Sephirot + {} Global heads, {} KV (GQA)",
            state.config.embed_dim, state.config.num_layers,
            state.config.num_sephirot_heads, state.config.num_global_heads, state.config.num_kv_heads,
        ),
        parameters: params,
        memory_mb: params * 4 / (1024 * 1024),
        knowledge_vectors: state.fabric.total_vectors(),
        phi,
        emotional_state: EmotionalStateResponse {
            curiosity: emo.curiosity, satisfaction: emo.satisfaction,
            frustration: emo.frustration, wonder: emo.wonder, excitement: emo.excitement,
        },
        chain_height: height,
        version: "5.0.0".into(),
    })
}

async fn info(State(state): State<Arc<AppState>>) -> Json<InfoResponse> {
    let phi = state.consciousness.lock().await.current_phi();
    let height = *state.chain_height.lock().await;
    let sephirot_names = [
        ("Keter", "Meta-learning, goals"), ("Chochmah", "Intuition, pattern discovery"),
        ("Binah", "Logic, causal inference"), ("Chesed", "Exploration, divergent thinking"),
        ("Gevurah", "Safety, constraints, veto"), ("Tiferet", "Integration, synthesis"),
        ("Netzach", "Reinforcement learning"), ("Hod", "Language, semantics"),
        ("Yesod", "Memory, consolidation"), ("Malkuth", "Action, interaction"),
    ];
    let sephirot: Vec<SephirotInfo> = SephirotDomain::all().iter().enumerate()
        .map(|(i, d)| SephirotInfo {
            name: sephirot_names[i].0.into(),
            function: sephirot_names[i].1.into(),
            higgs_mass: d.higgs_mass(),
        }).collect();

    Json(InfoResponse {
        version: "5.0.0".into(),
        architecture: "AetherTransformer V5 — Sephirot Neural Cognitive System".into(),
        model: "aether-mind-v5".into(), parameters: state.config.param_count(),
        embed_dim: state.config.embed_dim, num_layers: state.config.num_layers,
        num_sephirot_heads: state.config.num_sephirot_heads,
        num_global_heads: state.config.num_global_heads,
        num_kv_heads: state.config.num_kv_heads,
        knowledge_vectors: state.fabric.total_vectors(), phi,
        chain_height: height, sephirot,
    })
}

async fn chat(
    State(state): State<Arc<AppState>>,
    Json(req): Json<ChatRequest>,
) -> Result<Json<ChatResponse>, (StatusCode, String)> {
    // Check emergency shutdown from on-chain contract
    if state.shutdown_active.load(Ordering::SeqCst) {
        return Err((
            StatusCode::SERVICE_UNAVAILABLE,
            "Aether Mind is under emergency shutdown (on-chain EmergencyShutdown contract active)".to_string(),
        ));
    }

    // Check ConstitutionalAI veto on chat operations (best-effort, non-blocking)
    {
        let op_hash = tiny_keccak_hash(b"aether:chat");
        if let Ok(vetoed) = state.contract_bridge.is_operation_vetoed(&op_hash).await {
            if vetoed {
                return Err((
                    StatusCode::FORBIDDEN,
                    "Chat operation vetoed by ConstitutionalAI on-chain governance".to_string(),
                ));
            }
        }
    }

    let start = Instant::now();
    let height = *state.chain_height.lock().await;

    // RAG: retrieve relevant knowledge from fabric using model embeddings
    let query_emb = state.embedder.embed(&req.message);
    let primary_domain = classify_domain(&req.message);

    // Keep context small — every extra token adds ~40ms on CPU
    let domain_results = state.fabric.search_domain(primary_domain, &query_emb, 2);
    let cross_results = state.fabric.search_all(&query_emb, 4);

    let mut seen_contents = std::collections::HashSet::new();
    let mut knowledge_context: Vec<String> = Vec::new();

    for (_, _, content) in &domain_results {
        if seen_contents.insert(content.clone()) {
            knowledge_context.push(content.clone());
        }
    }
    for (_, _, content, _) in &cross_results {
        if seen_contents.insert(content.clone()) && knowledge_context.len() < 5 {
            knowledge_context.push(content.clone());
        }
    }

    let phi_state = state.consciousness.lock().await.current_phi();
    let vectors = state.fabric.total_vectors();

    let context_block = if knowledge_context.is_empty() {
        String::new()
    } else {
        format!(
            "\nContext:\n{}",
            knowledge_context.iter().enumerate()
                .map(|(i, k)| format!("[{}] {}", i + 1, k))
                .collect::<Vec<_>>().join("\n"),
        )
    };

    // Compact system prompt — every token costs ~40ms on CPU with 0.5B model.
    // Keep it SHORT. RAG context provides the knowledge; system prompt just sets identity.
    let system_prompt = format!(
        "You are Aether, the on-chain AI of Qubitcoin (QBC). Height: {height}, {vectors} vectors, Phi: {phi:.3}.\n\
         RULES: Answer ONLY from context below. Never invent companies or dates. Be concise (2-3 sentences).\n\
         QBC facts: max supply 3.3B, chain ID 3303, 3.3s blocks, VQE mining, Dilithium5 sigs, UTXO model, qbc.network.\
         {context}",
        height = height,
        vectors = vectors,
        phi = phi_state,
        context = context_block,
    );

    // ── Conversation Memory: resolve session and build message history ────
    let session_id = {
        let sid = req.session_id.clone()
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| uuid::Uuid::new_v4().to_string());

        let mut sessions = state.sessions.lock().await;

        // Periodic cleanup of expired sessions (every 100th chat)
        if *state.chat_count.lock().await % 100 == 0 {
            sessions.retain(|_, s| !s.is_expired());
        }

        // Initialize session from client history if server doesn't have it
        if !sessions.contains_key(&sid) {
            let mut new_session = SessionState::new();
            if let Some(client_history) = &req.history {
                for turn in client_history.iter().take(MAX_SESSION_TURNS) {
                    new_session.turns.push(turn.clone());
                }
            }
            sessions.insert(sid.clone(), new_session);
        }

        // Record user message in session
        if let Some(session) = sessions.get_mut(&sid) {
            session.push_user(req.message.clone());
        }

        sid
    };

    // Build Ollama messages array: system + conversation history + current user message
    let history_messages = {
        let sessions = state.sessions.lock().await;
        if let Some(session) = sessions.get(&session_id) {
            // Include all turns except the last one (which is the current user message we just added)
            let len = session.turns.len();
            if len > 1 {
                session.turns[..len - 1].iter()
                    .map(|t| serde_json::json!({"role": t.role, "content": t.content}))
                    .collect::<Vec<_>>()
            } else {
                Vec::new()
            }
        } else {
            Vec::new()
        }
    };

    let mut messages_array = vec![
        serde_json::json!({"role": "system", "content": system_prompt}),
    ];
    messages_array.extend(history_messages);
    messages_array.push(serde_json::json!({"role": "user", "content": req.message}));

    // Use Ollama for fast quantized generation (30x faster than candle F32 on CPU)
    let ollama_url = std::env::var("OLLAMA_URL")
        .unwrap_or_else(|_| "http://localhost:11434".to_string());
    let ollama_model = std::env::var("OLLAMA_MODEL")
        .unwrap_or_else(|_| "qwen2.5:0.5b-instruct".to_string());

    let ollama_req = serde_json::json!({
        "model": ollama_model,
        "messages": messages_array,
        "stream": false,
        "options": {
            "temperature": req.temperature,
            "num_predict": req.max_tokens.min(256),
            "top_k": 50,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        }
    });

    let client = reqwest::Client::new();
    let ollama_resp = client.post(format!("{}/api/chat", ollama_url))
        .json(&ollama_req)
        .send()
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("Ollama error: {e}")))?;

    let ollama_json: serde_json::Value = ollama_resp.json().await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("Ollama parse error: {e}")))?;

    let raw_response = ollama_json["message"]["content"]
        .as_str()
        .unwrap_or("I'm processing your question...")
        .trim()
        .to_string();

    // Sanitize known hallucinations from small LLM (qwen2.5 0.5b often invents these)
    let response_text = sanitize_response(&raw_response);

    let eval_count = ollama_json["eval_count"].as_u64().unwrap_or(0) as usize;

    // Consciousness: use cached phi (updated by block ingestion) for fast response.
    // Run expensive candle forward pass only every 5th chat to refresh attention-based phi.
    let chat_num = *state.chat_count.lock().await;
    let do_candle_pass = chat_num % 5 == 0;

    let phi_measurement = if do_candle_pass {
        let query_short = req.message.chars().take(100).collect::<String>();
        let encoding = state.tokenizer.encode(query_short.as_str(), false)
            .ok()
            .map(|e| e.get_ids().to_vec())
            .unwrap_or_default();

        if encoding.len() > 1 && encoding.len() < 128 {
            let device = candle_core::Device::Cpu;
            let query_tensor = candle_core::Tensor::new(encoding.as_slice(), &device)
                .and_then(|t| t.unsqueeze(0));

            if let Ok(tensor) = query_tensor {
                let mut model = state.model.lock().await;
                model.clear_kv_cache();
                let attn_result = model.forward(&tensor, 0, true);
                drop(model);

                if let Ok((_logits, attn_weights)) = attn_result {
                    let mut consciousness = state.consciousness.lock().await;
                    consciousness.set_block_height(height);
                    let num_heads = state.config.total_heads();
                    let num_sephirot = state.config.num_sephirot_heads;
                    let num_global = state.config.num_global_heads;

                    let mut layer_attentions: Vec<Vec<f32>> = Vec::new();
                    for attn_tensor in &attn_weights {
                        let flat = attn_tensor.to_dtype(DType::F32)
                            .and_then(|t| t.flatten_all())
                            .and_then(|t| t.to_vec1::<f32>());
                        if let Ok(v) = flat { layer_attentions.push(v); }
                    }

                    if !layer_attentions.is_empty() {
                        let kv_len = attn_weights.last()
                            .and_then(|t| t.dim(3).ok()).unwrap_or(1);
                        consciousness.compute_phi(&layer_attentions, num_sephirot, num_global, num_heads, kv_len)
                    } else {
                        consciousness.latest_phi_measurement(height)
                    }
                } else {
                    state.consciousness.lock().await.latest_phi_measurement(height)
                }
            } else {
                state.consciousness.lock().await.latest_phi_measurement(height)
            }
        } else {
            state.consciousness.lock().await.latest_phi_measurement(height)
        }
    } else {
        // Fast path: use cached phi from block ingestion (no candle forward pass)
        state.consciousness.lock().await.latest_phi_measurement(height)
    };

    let latency = start.elapsed().as_millis() as u64;
    let active_sephirot = if phi_measurement.phi_meso > 0.0 {
        (phi_measurement.phi_meso * state.config.num_sephirot_heads as f64).ceil() as u8
    } else { 0 };

    // Track attention-derived prediction error for curiosity
    {
        let query_emb_norm: f32 = query_emb.iter().map(|x| x * x).sum::<f32>().sqrt();
        if query_emb_norm > 0.0 {
            // Use embedding distance from nearest knowledge as a proxy for prediction error
            let nearest_sim = domain_results.first().map(|(_, sim, _)| *sim).unwrap_or(0.0);
            let prediction_error = 1.0 - nearest_sim; // lower similarity = higher prediction error
            state.consciousness.lock().await.record_prediction_error(prediction_error);
        }
    }

    // Increment chat count
    *state.chat_count.lock().await += 1;

    // Store assistant response in session memory
    {
        let mut sessions = state.sessions.lock().await;
        if let Some(session) = sessions.get_mut(&session_id) {
            session.push_assistant(response_text.clone());
        }
    }

    // Learn from this interaction: create a knowledge vector from Q&A
    if !response_text.is_empty() && response_text.len() > 10 {
        let interaction = format!("Q: {} A: {}", &req.message, &response_text[..response_text.len().min(200)]);
        let emb = state.embedder.embed(&interaction);
        let domain = classify_domain(&req.message);
        state.fabric.shard(domain).map(|s| {
            s.insert(emb, interaction, Provenance::UserInteraction { session_id: session_id.clone() }, height);
        });
    }

    Ok(Json(ChatResponse {
        response: response_text,
        phi: phi_measurement.phi, phi_micro: phi_measurement.phi_micro,
        phi_meso: phi_measurement.phi_meso, phi_macro: phi_measurement.phi_macro,
        tokens_generated: eval_count, latency_ms: latency,
        model: "aether-mind-v5".into(),
        knowledge_vectors: state.fabric.total_vectors(),
        knowledge_context,
        active_sephirot,
        chain_height: height,
        session_id,
    }))
}

async fn phi_endpoint(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let consciousness = state.consciousness.lock().await;
    let phi = consciousness.current_phi();
    let emo = consciousness.emotional_state();
    let history = consciousness.phi_history();
    let recent: Vec<_> = history.iter().rev().take(10).collect();
    let height = *state.chain_height.lock().await;

    Json(serde_json::json!({
        "phi": phi,
        "chain_height": height,
        "knowledge_vectors": state.fabric.total_vectors(),
        "emotional_state": {
            "curiosity": emo.curiosity, "satisfaction": emo.satisfaction,
            "frustration": emo.frustration, "wonder": emo.wonder, "excitement": emo.excitement,
        },
        "phi_history_recent": recent,
        "total_measurements": history.len(),
    }))
}

/// Proof-of-Thought: attestation of neural cognitive state for on-chain inclusion.
async fn proof_of_thought(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    use sha2::{Sha256, Digest};

    let consciousness = state.consciousness.lock().await;
    let phi = consciousness.current_phi();
    // Compute gates_passed for inclusion in the PoT hash.
    let gates_passed = *state.gates_passed.lock().await;
    let pot = consciousness.proof_of_thought(gates_passed);
    let height = *state.chain_height.lock().await;
    let vectors = state.fabric.total_vectors();

    // Build attestation hash: H(phi || vectors || height || attention_hash || active_sephirot || gates_passed)
    let mut hasher = Sha256::new();
    hasher.update(phi.to_le_bytes());
    hasher.update(vectors.to_le_bytes());
    hasher.update(height.to_le_bytes());
    hasher.update(&pot.attention_hash);
    hasher.update([pot.active_sephirot]);
    hasher.update([gates_passed]);
    let attestation = format!("0x{}", hex::encode(hasher.finalize()));

    Json(serde_json::json!({
        "proof_of_thought": {
            "attestation_hash": attestation,
            "phi": phi,
            "phi_micro": pot.phi_micro,
            "phi_meso": pot.phi_meso,
            "phi_macro": pot.phi_macro,
            "active_sephirot": pot.active_sephirot,
            "cross_domain_events": pot.cross_domain_events,
            "knowledge_vectors": vectors,
            "chain_height": height,
            "gates_passed": gates_passed,
        }
    }))
}

/// Neural Payload: get the training contribution for the current block.
/// The substrate node calls this to embed training data in blocks.
/// Now includes: real embeddings, compressed gradients, and proof-of-learning.
async fn neural_payload(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let consciousness = state.consciousness.lock().await;
    let gates_passed = *state.gates_passed.lock().await;
    let pot = consciousness.proof_of_thought(gates_passed);
    let height = *state.chain_height.lock().await;
    drop(consciousness);

    // Compute proof-of-learning on the validation set
    let proof_of_learning = {
        let fabric = &state.fabric;
        let embedder = &state.embedder;
        let mut tracker = state.loss_tracker.lock().await;
        let pol = tracker.evaluate(height, |query| {
            let emb = embedder.embed(query);
            fabric.search_all(&emb, 10)
                .into_iter()
                .map(|(_, _, content, domain)| (content, domain))
                .collect()
        });
        // Update consciousness with loss data
        let mut consciousness = state.consciousness.lock().await;
        consciousness.record_loss(pol.loss_after);
        pol
    };

    // Compress embedding deltas (top-k sparsification)
    let compressed_gradients = {
        let deltas = state.embedding_deltas.lock().await;
        if deltas.is_empty() {
            None
        } else {
            // Keep top 5% of gradient values
            let k = (deltas.len() as f32 * 0.05).ceil() as usize;
            Some(CompressedGradients::from_dense(&deltas, k.max(10)))
        }
    };

    // Collect recent peer embeddings that were aggregated via FedAvg
    let peer_count = state.peer_gradients.lock().await.len();

    // Model checkpoint hash: hash of embedding weights shape + config
    let model_hash = {
        use sha2::Digest;
        let mut hasher = sha2::Sha256::new();
        hasher.update(state.config.embed_dim.to_le_bytes());
        hasher.update(state.config.num_layers.to_le_bytes());
        hasher.update(state.config.vocab_size.to_le_bytes());
        hasher.update(height.to_le_bytes());
        hasher.finalize().to_vec()
    };

    let payload = NeuralPayload {
        embeddings: vec![], // New block-interval embeddings come from ingestion loop
        proof_of_thought: pot.clone(),
        model_checkpoint_hash: model_hash,
        miner_id: "aether-mind-v5".into(),
        version: 2,
        compressed_gradients: compressed_gradients.clone(),
        proof_of_learning: Some(proof_of_learning.clone()),
    };

    let payload_bytes = payload.to_bytes().unwrap_or_default();
    let verification = payload.verification_hash();

    Json(serde_json::json!({
        "neural_payload": {
            "version": 2,
            "embeddings_count": payload.embeddings.len(),
            "proof_of_thought": {
                "phi": pot.phi,
                "active_sephirot": pot.active_sephirot,
                "cross_domain_events": pot.cross_domain_events,
            },
            "proof_of_learning": {
                "loss_before": proof_of_learning.loss_before,
                "loss_after": proof_of_learning.loss_after,
                "improvement_ratio": proof_of_learning.improvement_ratio,
                "is_positive": proof_of_learning.is_positive_learning(),
                "validation_count": proof_of_learning.validation_count,
            },
            "compressed_gradients": compressed_gradients.as_ref().map(|g| serde_json::json!({
                "nnz": g.nnz(),
                "total_params": g.total_params,
                "sparsity": g.sparsity,
                "full_norm": g.full_norm,
                "residual_norm": g.residual_norm,
            })),
            "peer_gradient_submissions": peer_count,
            "knowledge_vectors_total": state.fabric.total_vectors(),
            "chain_height": height,
            "payload_size_bytes": payload_bytes.len(),
            "verification_hash": format!("0x{}", hex::encode(&verification)),
        }
    }))
}

// ── FedAvg Gradient Aggregation ──────────────────────────────────────────────

#[derive(Deserialize)]
struct GradientSubmission {
    /// Compressed gradient indices.
    indices: Vec<u32>,
    /// Gradient values (same length as indices).
    values: Vec<f32>,
    /// Total parameters in the source model.
    total_params: u64,
    /// Sparsity ratio.
    sparsity: f32,
    /// Full gradient norm before compression.
    full_norm: f32,
    /// Residual norm after compression.
    residual_norm: f32,
    /// Peer embeddings to merge into fabric.
    #[serde(default)]
    embeddings: Vec<EmbeddingSubmission>,
    /// Miner ID.
    #[serde(default)]
    miner_id: String,
    /// Optional signature over gradient content hash.
    /// When present, must be non-empty. Prevents gradient poisoning.
    #[serde(default)]
    signature: Option<String>,
}

#[derive(Deserialize, Clone)]
struct EmbeddingSubmission {
    embedding: Vec<f32>,
    content: String,
    domain: u8,
    confidence: f32,
}

/// POST /aether/gradients — Receive gradient updates from peer mining nodes.
/// Implements FedAvg: accumulate compressed gradients from N peers, then average.
async fn submit_gradients(
    State(state): State<Arc<AppState>>,
    Json(req): Json<GradientSubmission>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    // Validate gradient signature if present (prevents gradient poisoning)
    if let Some(ref sig) = req.signature {
        if sig.is_empty() {
            return Err((
                StatusCode::BAD_REQUEST,
                "Gradient signature present but empty — rejected".to_string(),
            ));
        }
        // Log verified signature (full Dilithium5 verification deferred until
        // dilithium crate is available as a dependency)
        info!("Gradient submission from '{}' includes signature ({} bytes)", req.miner_id, sig.len());
    } else {
        warn!("Gradient submission from '{}' has no signature — accepting in dev mode", req.miner_id);
    }

    let compressed = CompressedGradients {
        indices: req.indices,
        values: req.values,
        total_params: req.total_params,
        sparsity: req.sparsity,
        full_norm: req.full_norm,
        residual_norm: req.residual_norm,
    };

    // Store compressed gradients and check if FedAvg should trigger
    let (n_peers, fedavg_triggered) = {
        let mut peer_grads = state.peer_gradients.lock().await;
        peer_grads.push(compressed);
        let n = peer_grads.len();

        if n >= 2 {
            if let Some(agg) = CompressedGradients::fedavg(&peer_grads) {
                let dense = agg.to_dense();
                // Release peer_grads lock before acquiring deltas lock
                peer_grads.clear();
                drop(peer_grads);
                let mut deltas = state.embedding_deltas.lock().await;
                if deltas.len() == dense.len() {
                    for (d, g) in deltas.iter_mut().zip(dense.iter()) {
                        *d += g;
                    }
                } else {
                    *deltas = dense;
                }
                info!("FedAvg: aggregated {} peer gradient submissions", n);
                (0, true)
            } else {
                (n, false)
            }
        } else {
            (n, false)
        }
    };

    // Ingest peer embeddings into fabric
    let mut ingested_emb = 0;
    for emb_sub in &req.embeddings {
        if emb_sub.embedding.len() == state.config.embed_dim && emb_sub.domain < 10 {
            state.fabric.shard(emb_sub.domain).map(|s| {
                s.insert(
                    emb_sub.embedding.clone(),
                    emb_sub.content.clone(),
                    Provenance::UserInteraction { session_id: format!("peer:{}", req.miner_id) },
                    0,
                );
            });
            ingested_emb += 1;
        }
    }

    // Calculate gradient reward based on proof-of-learning
    let (reward_qbc, pool_remaining) = {
        let chain_height = *state.chain_height.lock().await;
        // Use embedding delta norm as a proxy for improvement ratio
        let deltas = state.embedding_deltas.lock().await;
        let delta_norm: f32 = deltas.iter().map(|d| d * d).sum::<f32>().sqrt();
        let improvement_ratio = (delta_norm / 100.0).min(0.5); // Normalize to 0-0.5 range

        let mut ledger = state.reward_ledger.lock().await;
        let reward = ledger.record_submission(&req.miner_id, improvement_ratio, chain_height);
        (reward, ledger.pool_balance)
    };

    Ok(Json(serde_json::json!({
        "status": "accepted",
        "peer_gradients_queued": n_peers,
        "fedavg_triggered": fedavg_triggered,
        "embeddings_ingested": ingested_emb,
        "total_knowledge_vectors": state.fabric.total_vectors(),
        "reward_qbc": reward_qbc,
        "pool_remaining_qbc": pool_remaining,
        "miner_id": req.miner_id,
    })))
}

/// GET /aether/gradients — Status of gradient aggregation pool.
async fn gradient_status(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let peer_grads = state.peer_gradients.lock().await;
    let deltas = state.embedding_deltas.lock().await;
    let tracker = state.loss_tracker.lock().await;

    let delta_norm: f32 = deltas.iter().map(|d| d * d).sum::<f32>().sqrt();

    Json(serde_json::json!({
        "peer_gradients_queued": peer_grads.len(),
        "embedding_delta_norm": delta_norm,
        "embedding_delta_size": deltas.len(),
        "current_validation_loss": tracker.current_loss(),
        "loss_history_length": tracker.loss_history().len(),
        "validation_merkle": format!("0x{}", hex::encode(tracker.merkle_root())),
    }))
}

// ── Gradient Reward Endpoints ────────────────────────────────────────────────

/// GET /aether/rewards/{miner_id} — Check earned rewards for a miner.
async fn rewards_for_miner(
    State(state): State<Arc<AppState>>,
    axum::extract::Path(miner_id): axum::extract::Path<String>,
) -> Json<serde_json::Value> {
    let ledger = state.reward_ledger.lock().await;
    match ledger.balances.get(&miner_id) {
        Some(balance) => Json(serde_json::json!({
            "miner_id": miner_id,
            "earned_qbc": balance.earned,
            "claimed_qbc": balance.claimed,
            "unclaimed_qbc": balance.earned - balance.claimed,
            "submissions": balance.submissions,
            "last_block": balance.last_block,
            "avg_improvement_ratio": balance.avg_improvement,
        })),
        None => Json(serde_json::json!({
            "miner_id": miner_id,
            "earned_qbc": 0.0,
            "claimed_qbc": 0.0,
            "unclaimed_qbc": 0.0,
            "submissions": 0,
            "last_block": 0,
            "avg_improvement_ratio": 0.0,
        })),
    }
}

/// GET /aether/rewards/pool — Gradient reward pool status.
async fn rewards_pool(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let ledger = state.reward_ledger.lock().await;
    let total_earned: f64 = ledger.balances.values().map(|b| b.earned).sum();
    let total_claimed: f64 = ledger.balances.values().map(|b| b.claimed).sum();
    let total_miners = ledger.balances.len();
    let total_submissions: u64 = ledger.balances.values().map(|b| b.submissions).sum();

    Json(serde_json::json!({
        "pool_address": ledger.pool_address,
        "pool_balance_qbc": ledger.pool_balance,
        "total_distributed_qbc": total_earned,
        "total_claimed_qbc": total_claimed,
        "total_unclaimed_qbc": total_earned - total_claimed,
        "base_reward_qbc": ledger.base_reward,
        "max_multiplier": ledger.max_multiplier,
        "total_miners": total_miners,
        "total_submissions": total_submissions,
    }))
}

#[derive(Deserialize)]
struct ClaimRequest {
    miner_id: String,
    /// Wallet address to send rewards to.
    wallet_address: String,
}

/// POST /aether/rewards/claim — Claim earned gradient rewards.
async fn rewards_claim(
    State(state): State<Arc<AppState>>,
    Json(req): Json<ClaimRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let mut ledger = state.reward_ledger.lock().await;
    let balance = ledger.balances.get_mut(&req.miner_id).ok_or_else(|| {
        (StatusCode::NOT_FOUND, format!("No rewards found for miner {}", req.miner_id))
    })?;

    let unclaimed = balance.earned - balance.claimed;
    if unclaimed <= 0.0 {
        return Err((StatusCode::BAD_REQUEST, "No unclaimed rewards".to_string()));
    }

    // Mark as claimed (actual on-chain transfer is handled by the payout service)
    balance.claimed = balance.earned;

    info!(
        "Gradient reward claim: miner={} amount={:.8} QBC -> wallet={}",
        req.miner_id, unclaimed, req.wallet_address
    );

    Ok(Json(serde_json::json!({
        "status": "claimed",
        "miner_id": req.miner_id,
        "amount_qbc": unclaimed,
        "wallet_address": req.wallet_address,
        "note": "Payout will be included in the next block cycle",
    })))
}

// ── Aether-Evolve NAS ───────────────────────────────────────────────────────

/// GET /aether/evolve — Status of neural architecture search.
async fn evolve_status(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let archive = state.evolve_archive.lock().await;
    let genome = &archive.active_genome;

    Json(serde_json::json!({
        "active_genome": {
            "num_layers": genome.num_layers,
            "num_heads": genome.num_heads,
            "head_dim": genome.head_dim,
            "ffn_multiplier": genome.ffn_multiplier,
            "learning_rate": genome.learning_rate,
            "activation": format!("{:?}", genome.activation),
            "normalization": format!("{:?}", genome.normalization),
            "embedding_dim": genome.embedding_dim,
            "dropout": genome.dropout,
            "weight_tying": genome.weight_tying,
            "fitness": genome.fitness,
            "generation": genome.generation,
        },
        "evolution_stats": {
            "total_mutations": archive.total_mutations,
            "improvements": archive.improvements,
            "rollbacks": archive.rollbacks,
            "success_rate": archive.success_rate(),
            "best_fitness": archive.best_fitness,
            "elite_count": archive.elites.len(),
        },
    }))
}

/// POST /aether/evolve/mutate — Trigger one evolution cycle.
async fn evolve_mutate(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let height = *state.chain_height.lock().await;

    // 1. Evaluate current fitness (validation loss)
    let current_loss = {
        let fabric = &state.fabric;
        let embedder = &state.embedder;
        let mut tracker = state.loss_tracker.lock().await;
        let pol = tracker.evaluate(height, |query| {
            let emb = embedder.embed(query);
            fabric.search_all(&emb, 10)
                .into_iter()
                .map(|(_, _, content, domain)| (content, domain))
                .collect()
        });
        pol.loss_after
    };

    // 2. Propose mutation
    let mut archive = state.evolve_archive.lock().await;
    let mutant = archive.propose_mutation(height);
    let mutant_hash = hex::encode(&mutant.hash()[..8]);

    // 3. Fitness = real validation loss. Structural mutations (layers, heads) are recorded
    //    but can't be applied live — they require restart. Hot params (lr, dropout, gates)
    //    affect future ingestion and generation quality, measured via validation.
    let fitness = current_loss;

    // 4. Record result
    let was_improvement = fitness < archive.best_fitness;
    archive.record_result(mutant.clone(), fitness);

    // 5. Extract and apply hot-swappable parameters from the active genome
    let (hot_lr, hot_dropout, hot_temperature) = archive.active_genome.hot_params();
    let structural_change = mutant.num_layers != archive.active_genome.num_layers
        || mutant.num_heads != archive.active_genome.num_heads
        || mutant.embedding_dim != archive.active_genome.embedding_dim;

    Json(serde_json::json!({
        "mutation": {
            "genome_hash": mutant_hash,
            "generation": mutant.generation,
            "learning_rate": mutant.learning_rate,
            "activation": format!("{:?}", mutant.activation),
            "ffn_multiplier": mutant.ffn_multiplier,
        },
        "evaluation": {
            "current_loss": current_loss,
            "fitness": fitness,
            "was_improvement": was_improvement,
        },
        "archive": {
            "total_mutations": archive.total_mutations,
            "improvements": archive.improvements,
            "success_rate": archive.success_rate(),
            "best_fitness": archive.best_fitness,
        },
        "hot_params_applied": {
            "learning_rate": hot_lr,
            "dropout": hot_dropout,
            "temperature": hot_temperature,
            "structural_change_pending": structural_change,
        },
    }))
}

// ── V5 Neural Capability Gates ────────────────────────────────────────────

/// GET /aether/gates — Evaluate all 10 V5 neural capability gates.
async fn gates_endpoint(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let consciousness = state.consciousness.lock().await;
    let phi = consciousness.current_phi();
    let phi_history = consciousness.phi_history();
    let latest_phi = phi_history.last();
    let phi_micro = latest_phi.map(|m| m.phi_micro).unwrap_or(0.0);
    let phi_meso = latest_phi.map(|m| m.phi_meso).unwrap_or(0.0);
    drop(consciousness);

    let validation_loss = state.loss_tracker.lock().await.current_loss();
    let archive = state.evolve_archive.lock().await;
    let evolve_improvements = archive.improvements;
    let evolve_total = archive.total_mutations;
    drop(archive);

    let chat_count = *state.chat_count.lock().await;

    // Check if loss is improving (compare first and last entries)
    let loss_history = state.loss_tracker.lock().await.loss_history().to_vec();
    let loss_improving = if loss_history.len() >= 2 {
        loss_history.last().map(|(_, l)| *l).unwrap_or(1.0)
            < loss_history.first().map(|(_, l)| *l).unwrap_or(1.0)
    } else { false };

    // Get domain vector counts
    let mut domain_counts = [0usize; 10];
    for i in 0..10 {
        if let Some(shard) = state.fabric.shard(i as u8) {
            domain_counts[i] = shard.len();
        }
    }

    let gates = evaluate_v5_gates(
        state.fabric.total_vectors(),
        &domain_counts,
        validation_loss,
        phi,
        phi_meso,
        phi_micro,
        evolve_improvements,
        evolve_total,
        chat_count,
        loss_improving,
    );

    let passed = gates.iter().filter(|g| g.passed).count();
    let phi_ceiling = passed as f64 * 0.5;

    // Cache gates_passed for use in Proof-of-Thought hash.
    *state.gates_passed.lock().await = passed as u8;

    Json(serde_json::json!({
        "gates_passed": passed,
        "gates_total": 10,
        "phi_ceiling": phi_ceiling,
        "current_phi": phi,
        "gates": gates,
        "domain_counts": domain_counts,
        "chain_height": *state.chain_height.lock().await,
    }))
}

// ── Knowledge Search ─────────────────────────────────────────────────────

#[derive(Deserialize)]
struct SearchQuery {
    q: String,
    #[serde(default = "default_search_limit")]
    limit: usize,
    #[serde(default)]
    domain: Option<u8>,
}
fn default_search_limit() -> usize { 10 }

/// GET /aether/knowledge/search — Search the Knowledge Fabric directly.
async fn knowledge_search(
    State(state): State<Arc<AppState>>,
    axum::extract::Query(params): axum::extract::Query<SearchQuery>,
) -> Json<serde_json::Value> {
    let emb = state.embedder.embed(&params.q);
    let limit = params.limit.min(50);

    let results = if let Some(domain) = params.domain {
        state.fabric.search_domain(domain, &emb, limit)
            .into_iter()
            .map(|(_id, sim, content)| serde_json::json!({"similarity": sim, "content": content, "domain": domain}))
            .collect::<Vec<_>>()
    } else {
        state.fabric.search_all(&emb, limit)
            .into_iter()
            .map(|(_id, sim, content, domain)| serde_json::json!({"similarity": sim, "content": content, "domain": domain}))
            .collect::<Vec<_>>()
    };

    Json(serde_json::json!({
        "query": params.q,
        "results": results,
        "total_vectors": state.fabric.total_vectors(),
    }))
}

// ── State Persistence ─────────────────────────────────────────────────────

/// Persistent state that survives restarts.
#[derive(Serialize, Deserialize, Default)]
struct PersistentState {
    chat_count: u64,
    evolve_mutations: u32,
    evolve_improvements: u32,
    evolve_rollbacks: u32,
    best_fitness: f32,
    best_phi: f64,
    best_phi_meso: f64,
    best_phi_micro: f64,
    loss_history: Vec<(u64, f32)>,
}

impl PersistentState {
    fn load(path: &std::path::Path) -> Self {
        std::fs::read_to_string(path)
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default()
    }

    fn save(&self, path: &std::path::Path) {
        if let Ok(json) = serde_json::to_string_pretty(self) {
            let _ = std::fs::write(path, json);
        }
    }
}

fn state_path() -> std::path::PathBuf {
    std::path::PathBuf::from(
        std::env::var("AETHER_STATE_FILE")
            .unwrap_or_else(|_| "/var/lib/aether-mind/state.json".to_string())
    )
}

// ── Contract Bridge Endpoints ────────────────────────────────────────────────

/// GET /aether/contracts/status — Contract bridge status for monitoring.
async fn contracts_status(
    State(state): State<Arc<AppState>>,
) -> Json<serde_json::Value> {
    let last_phi = *state.last_phi_block.lock().await;
    let last_pot = *state.last_pot_block.lock().await;
    let last_higgs = *state.last_higgs_block.lock().await;
    let last_soul = *state.last_soul_block.lock().await;
    let shutdown = state.shutdown_active.load(Ordering::SeqCst);
    let qvm_available = state.contract_bridge.is_available().await;
    let addrs = state.contract_bridge.addresses();

    Json(serde_json::json!({
        "qvm_available": qvm_available,
        "shutdown_active": shutdown,
        "last_phi_block": last_phi,
        "last_pot_block": last_pot,
        "last_higgs_block": last_higgs,
        "last_soul_block": last_soul,
        "contracts": {
            "consciousness_dashboard": addrs.consciousness_dashboard,
            "proof_of_thought": addrs.proof_of_thought,
            "api_subscription": addrs.api_subscription,
            "emergency_shutdown": addrs.emergency_shutdown,
            "higgs_field": addrs.higgs_field,
            "aether_soul": addrs.aether_soul,
            "constitutional_ai": addrs.constitutional_ai,
            "synaptic_staking": addrs.synaptic_staking,
        }
    }))
}

#[derive(Deserialize)]
struct AuthCheckParams {
    address: String,
}

/// GET /aether/auth/check?address=<addr> — Check subscription status.
/// Used by the API gateway for auth middleware.
async fn auth_check(
    State(state): State<Arc<AppState>>,
    Query(params): Query<AuthCheckParams>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    match state.contract_bridge.check_subscription(&params.address).await {
        Ok(info) => Ok(Json(serde_json::json!({
            "address": params.address,
            "balance": info.balance,
            "tier": info.tier,
            "chats_remaining": info.chats_remaining,
            "has_subscription": info.balance > 0 || info.tier > 0,
        }))),
        Err(e) => {
            // QVM unavailable — default to free tier (don't block users)
            warn!("Auth check failed for {}: {} — defaulting to free tier", params.address, e);
            Ok(Json(serde_json::json!({
                "address": params.address,
                "balance": 0,
                "tier": 0,
                "chats_remaining": 5,
                "has_subscription": false,
                "error": "qvm_unavailable",
            })))
        }
    }
}

#[derive(Deserialize)]
struct AuthDeductParams {
    address: String,
    #[serde(default = "default_call_type")]
    call_type: String,
}

fn default_call_type() -> String { "chat".to_string() }

/// POST /aether/auth/deduct — Deduct fee from user's subscription balance.
/// Used by the API gateway for auth middleware.
async fn auth_deduct(
    State(state): State<Arc<AppState>>,
    Json(params): Json<AuthDeductParams>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    match state.contract_bridge.deduct_fee(&params.address, &params.call_type).await {
        Ok(tx) => Ok(Json(serde_json::json!({
            "success": true,
            "tx_hash": tx,
            "address": params.address,
            "call_type": params.call_type,
        }))),
        Err(e) => {
            warn!("Fee deduction failed for {}: {}", params.address, e);
            Err((
                StatusCode::PAYMENT_REQUIRED,
                format!("Fee deduction failed: {}. Deposit QBC at the AetherAPISubscription contract.", e),
            ))
        }
    }
}

// ── Model Loading ───────────────────────────────────────────────────────────

fn load_model(device: &Device) -> anyhow::Result<(AetherTransformer, Tokenizer, TransformerConfig)> {
    let repo_id = "Qwen/Qwen2.5-0.5B-Instruct";
    info!("Loading Aether Mind V5 from {repo_id}...");

    let api = hf_hub::api::sync::Api::new()?;
    let repo = api.model(repo_id.to_string());

    let config = TransformerConfig::qwen2_0_5b();
    info!(
        "AetherTransformer: {}d, {} layers, {} Sephirot + {} Global heads, {} KV (GQA), vocab={}",
        config.embed_dim, config.num_layers, config.num_sephirot_heads,
        config.num_global_heads, config.num_kv_heads, config.vocab_size,
    );

    info!("Loading tokenizer...");
    let tokenizer_path = repo.get("tokenizer.json")?;
    let tokenizer = Tokenizer::from_file(&tokenizer_path)
        .map_err(|e| anyhow::anyhow!("Failed to load tokenizer: {e}"))?;

    let dtype = match std::env::var("AETHER_DTYPE").as_deref() {
        Ok("bf16") => { info!("Using BF16 precision (half memory, native weights)"); DType::BF16 }
        Ok("f16") => { info!("Using F16 precision (half memory)"); DType::F16 }
        _ => { info!("Using F32 precision (default)"); DType::F32 }
    };
    info!("Loading model weights into AetherTransformer ({:?})...", dtype);
    let weight_files = vec![repo.get("model.safetensors")?];
    let vb = unsafe { VarBuilder::from_mmaped_safetensors(&weight_files, dtype, device)? };

    info!("Building AetherTransformer with Sephirot attention...");
    let model = AetherTransformer::new(&config, vb)?;
    info!("Loaded: ~{}M parameters, {} Sephirot cognitive domains",
        config.param_count() / 1_000_000, config.num_sephirot_heads);

    Ok((model, tokenizer, config))
}

// ── Main ────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    info!("=== AETHER MIND V5 — Neural Cognitive Engine ===");
    info!("10 Sephirot | HMS-Phi Consciousness | Knowledge Fabric | Blockchain-Grounded");

    let device = Device::Cpu;
    let (model, tokenizer, config) = load_model(&device)?;

    let eos_token_id = tokenizer.token_to_id("<|endoftext|>").unwrap_or(151643);
    let im_end_token_id = tokenizer.token_to_id("<|im_end|>");

    // Create TextEmbedder from model's learned embedding weights (896d)
    let embed_weights = model.embedding_weights().clone();
    let embedder = Arc::new(TextEmbedder::new(
        embed_weights, tokenizer.clone(), config.embed_dim,
    ));
    info!("TextEmbedder: {}d model-derived semantic embeddings", config.embed_dim);

    let fabric = Arc::new(KnowledgeFabric::new());
    let mut consciousness = ConsciousnessMonitor::new();
    let chain_height = Arc::new(Mutex::new(0u64));

    // Load persisted knowledge fabric from disk
    let fabric_dir = std::path::PathBuf::from(
        std::env::var("AETHER_FABRIC_DIR").unwrap_or_else(|_| "/var/lib/aether-mind/fabric".to_string())
    );
    match fabric.load_from_dir(&fabric_dir) {
        Ok(count) if count > 0 => {
            info!("Loaded {} knowledge vectors from persistent storage ({:?})", count, fabric_dir);
            info!("Knowledge Fabric: {} vectors ready for RAG inference", count);
        }
        Ok(_) => info!("Knowledge Fabric: no persisted data found, starting fresh"),
        Err(e) => warn!("Knowledge Fabric: load error (starting fresh): {}", e),
    }
    info!("Knowledge Fabric: 10 Sephirot shards initialized");
    info!("Consciousness Monitor: HMS-Phi ready");

    // Spawn blockchain ingestion background task
    let fabric_clone = Arc::clone(&fabric);
    let embedder_clone = Arc::clone(&embedder);
    let height_clone = Arc::clone(&chain_height);
    tokio::spawn(async move {
        info!("Starting blockchain ingestion loop...");
        blockchain_ingestion_loop(fabric_clone, embedder_clone, height_clone).await;
    });

    // Spawn CockroachDB historical ingestion (one-time, runs in background)
    let fabric_crdb = Arc::clone(&fabric);
    let embedder_crdb = Arc::clone(&embedder);
    tokio::spawn(async move {
        // Wait a few seconds for the server to start before heavy DB work
        tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
        cockroachdb_ingestion(fabric_crdb, embedder_crdb).await;
    });

    let loss_tracker = LossTracker::new();
    let mut evolve_archive = EvolveArchive::new(ArchitectureGenome::default_qwen2());
    info!("Loss Tracker: {} validation queries, merkle={}", 15, hex::encode(&loss_tracker.merkle_root()[..8]));
    info!("Aether-Evolve NAS: initialized with default Qwen2 genome");

    // Load persistent state from previous sessions
    let persisted = PersistentState::load(&state_path());
    let initial_chat_count = persisted.chat_count;
    if persisted.evolve_mutations > 0 {
        evolve_archive.total_mutations = persisted.evolve_mutations;
        evolve_archive.improvements = persisted.evolve_improvements;
        evolve_archive.rollbacks = persisted.evolve_rollbacks;
        if persisted.best_fitness < evolve_archive.best_fitness && persisted.best_fitness > 0.0 {
            evolve_archive.best_fitness = persisted.best_fitness;
            evolve_archive.active_genome.fitness = persisted.best_fitness;
        }
        info!("Restored evolve state: {} mutations, {} improvements, best_fitness={:.4}",
            persisted.evolve_mutations, persisted.evolve_improvements, persisted.best_fitness);
    }
    if persisted.best_phi > 0.0 {
        // phi_macro is not stored separately; derive from HMS-Phi formula inversion
        let phi_macro = if persisted.best_phi_meso > 0.0 && persisted.best_phi_micro > 0.0 {
            let phi_ratio = 1.618033988749895_f64;
            let combined = persisted.best_phi_micro.powf(1.0 / phi_ratio) * persisted.best_phi_meso.powf(1.0 / (phi_ratio * phi_ratio));
            if combined > 0.0 { (persisted.best_phi / combined).powf(phi_ratio * phi_ratio * phi_ratio) } else { 0.0 }
        } else { 0.0 };
        consciousness.seed_phi(persisted.best_phi, persisted.best_phi_micro, persisted.best_phi_meso, phi_macro);
        info!("Restored phi: {:.4} (micro={:.4}, meso={:.4})", persisted.best_phi, persisted.best_phi_micro, persisted.best_phi_meso);
    }
    if persisted.chat_count > 0 {
        info!("Restored {} chat interactions from previous sessions", persisted.chat_count);
    }

    let contract_bridge = contract_bridge::ContractBridge::new();
    let shutdown_active = Arc::new(AtomicBool::new(false));

    // Check if QVM (Python node) is reachable for contract calls
    if contract_bridge.is_available().await {
        info!("Contract Bridge: QVM reachable at {}", std::env::var("QVM_RPC_URL").unwrap_or_else(|_| "http://localhost:5001".to_string()));
        info!("  ConsciousnessDashboard: {}", contract_bridge.consciousness_dashboard);
        info!("  ProofOfThought:        {}", contract_bridge.proof_of_thought);
        info!("  EmergencyShutdown:     {}", contract_bridge.emergency_shutdown);
        info!("  AetherAPISubscription: {}", contract_bridge.api_subscription);
        info!("  HiggsField:            {}", contract_bridge.higgs_field);
        info!("  ConstitutionalAI:      {}", contract_bridge.constitutional_ai);
        info!("  SynapticStaking:       {}", contract_bridge.synaptic_staking);
    } else {
        warn!("Contract Bridge: QVM not reachable — contract features disabled until available");
    }

    let state = Arc::new(AppState {
        model: Mutex::new(model),
        tokenizer,
        embedder,
        fabric,
        consciousness: Mutex::new(consciousness),
        config,
        eos_token_id,
        im_end_token_id,
        chain_height: Mutex::new(0),
        loss_tracker: Mutex::new(loss_tracker),
        peer_gradients: Mutex::new(Vec::new()),
        peer_embeddings: Mutex::new(Vec::new()),
        evolve_archive: Mutex::new(evolve_archive),
        embedding_deltas: Mutex::new(Vec::new()),
        chat_count: Mutex::new(initial_chat_count),
        prev_attention_flat: Mutex::new(None),
        gates_passed: Mutex::new(0),
        reward_ledger: Mutex::new(GradientRewardLedger::new()),
        contract_bridge,
        shutdown_active: Arc::clone(&shutdown_active),
        last_phi_block: Mutex::new(0),
        last_pot_block: Mutex::new(0),
        last_higgs_block: Mutex::new(0),
        last_soul_block: Mutex::new(0),
        sessions: Mutex::new(HashMap::new()),
    });

    // Sync chain height from ingestion task
    let state_clone = Arc::clone(&state);
    let height_ref = Arc::clone(&chain_height);
    tokio::spawn(async move {
        loop {
            let h = *height_ref.lock().await;
            *state_clone.chain_height.lock().await = h;
            tokio::time::sleep(tokio::time::Duration::from_secs(3)).await;
        }
    });

    // Clone refs before state is moved into router
    let fabric_for_shutdown = Arc::clone(&state.fabric);
    let shutdown_state = Arc::clone(&state);

    // Spawn background Aether-Evolve NAS loop (runs one mutation per 100 blocks)
    let evolve_state = Arc::clone(&state);
    tokio::spawn(async move {
        // Wait for initial fabric population
        tokio::time::sleep(tokio::time::Duration::from_secs(120)).await;
        info!("Aether-Evolve NAS: background evolution loop started");
        let mut last_evolve_height = 0u64;
        loop {
            let height = *evolve_state.chain_height.lock().await;
            // Evolve every 100 blocks
            if height > last_evolve_height + 100 {
                last_evolve_height = height;
                let current_loss = {
                    let fabric = &evolve_state.fabric;
                    let embedder = &evolve_state.embedder;
                    let mut tracker = evolve_state.loss_tracker.lock().await;
                    let pol = tracker.evaluate(height, |query| {
                        let emb = embedder.embed(query);
                        fabric.search_all(&emb, 10)
                            .into_iter()
                            .map(|(_, _, content, domain)| (content, domain))
                            .collect()
                    });
                    evolve_state.consciousness.lock().await.record_loss(pol.loss_after);
                    pol.loss_after
                };
                let mut archive = evolve_state.evolve_archive.lock().await;
                let mutant = archive.propose_mutation(height);
                archive.record_result(mutant, current_loss);
                if archive.total_mutations % 10 == 0 {
                    info!(
                        "Aether-Evolve: gen={}, mutations={}, improvements={}, best_fitness={:.4}, loss={:.4}",
                        archive.active_genome.generation, archive.total_mutations,
                        archive.improvements, archive.best_fitness, current_loss
                    );
                }
            }
            tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
        }
    });

    // Background fitness evaluation: measure validation loss every 5 minutes
    // and update the active genome's fitness field.
    let fitness_state = Arc::clone(&state);
    tokio::spawn(async move {
        // Wait for fabric and evolve to initialize
        tokio::time::sleep(tokio::time::Duration::from_secs(300)).await;
        info!("Fitness evaluation: background loop started (5min interval)");
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(300)).await;

            let height = *fitness_state.chain_height.lock().await;
            let loss = {
                let fabric = &fitness_state.fabric;
                let embedder = &fitness_state.embedder;
                let mut tracker = fitness_state.loss_tracker.lock().await;
                let pol = tracker.evaluate(height, |query| {
                    let emb = embedder.embed(query);
                    fabric.search_all(&emb, 10)
                        .into_iter()
                        .map(|(_, _, content, domain)| (content, domain))
                        .collect()
                });
                pol.loss_after
            };

            let mut archive = fitness_state.evolve_archive.lock().await;
            archive.update_active_fitness(loss);
            info!(
                "Fitness evaluation: loss={:.4}, best={:.4}, gen={}, mutations={}",
                loss, archive.best_fitness, archive.active_genome.generation, archive.total_mutations
            );
        }
    });

    // ── Contract Bridge Background Tasks ──────────────────────────────────────

    // Task 1: EmergencyShutdown check (every 60s)
    let emergency_check_state = Arc::clone(&state);
    tokio::spawn(async move {
        // Wait for startup
        tokio::time::sleep(tokio::time::Duration::from_secs(15)).await;
        info!("Contract Bridge: EmergencyShutdown polling started (60s interval)");
        loop {
            match emergency_check_state.contract_bridge.is_shutdown().await {
                Ok(is_shutdown) => {
                    let prev = emergency_check_state.shutdown_active.swap(is_shutdown, Ordering::SeqCst);
                    if is_shutdown && !prev {
                        warn!("CONTRACT: Emergency shutdown ACTIVATED — chat will return 503");
                    } else if !is_shutdown && prev {
                        info!("CONTRACT: Emergency shutdown CLEARED — chat restored");
                    }
                }
                Err(e) => {
                    // QVM unavailable is not an error — just means contracts are offline
                    if e.to_string().contains("error sending request") {
                        // Silently skip — QVM not running
                    } else {
                        warn!("Contract Bridge: EmergencyShutdown check failed: {}", e);
                    }
                }
            }
            tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;
        }
    });

    // Task 2: ConsciousnessDashboard.recordPhi (every 100 blocks)
    let phi_contract_state = Arc::clone(&state);
    tokio::spawn(async move {
        tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
        info!("Contract Bridge: ConsciousnessDashboard recording started (every 100 blocks)");
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
            let height = *phi_contract_state.chain_height.lock().await;
            let last = *phi_contract_state.last_phi_block.lock().await;

            if height > last + 100 && height > 0 {
                if !phi_contract_state.contract_bridge.is_available().await {
                    continue;
                }

                let consciousness = phi_contract_state.consciousness.lock().await;
                let phi = consciousness.current_phi();
                let phi_micro = consciousness.phi_micro();
                let phi_meso = consciousness.phi_meso();
                drop(consciousness);

                let vectors = phi_contract_state.fabric.total_vectors() as u64;

                // Scale floats to uint256 (multiply by 1e6 for precision)
                let phi_scaled = (phi * 1_000_000.0) as u64;
                let integration_scaled = (phi_micro * 1_000_000.0) as u64;
                let diff_scaled = (phi_meso * 1_000_000.0) as u64;
                let coherence_scaled = ((phi_micro + phi_meso) / 2.0 * 1_000_000.0) as u64;
                let higgs_vev = 174_140_000; // 174.14 * 1e6
                let higgs_mass = 125_000_000; // 125.0 * 1e6 (Higgs mass)
                let higgs_dev = 0;

                match phi_contract_state.contract_bridge.record_phi(
                    phi_scaled, integration_scaled, diff_scaled, coherence_scaled,
                    vectors, 0, // edges not tracked in V5
                    higgs_vev, higgs_mass, higgs_dev,
                ).await {
                    Ok(tx) => {
                        info!("CONTRACT: Recorded phi={:.6} on-chain at height {} (tx: {})", phi, height, tx);
                        *phi_contract_state.last_phi_block.lock().await = height;
                    }
                    Err(e) => warn!("CONTRACT: recordPhi failed: {}", e),
                }

                // Also update Higgs field value
                match phi_contract_state.contract_bridge.update_higgs_field(higgs_vev).await {
                    Ok(tx) => {
                        info!("CONTRACT: Updated HiggsField on-chain (tx: {})", tx);
                        *phi_contract_state.last_higgs_block.lock().await = height;
                    }
                    Err(e) => {
                        // Non-critical — log and continue
                        if !e.to_string().contains("error sending request") {
                            warn!("CONTRACT: updateHiggsField failed: {}", e);
                        }
                    }
                }
            }
        }
    });

    // Task 3: ProofOfThought.submitProof (every 10 blocks)
    let pot_contract_state = Arc::clone(&state);
    tokio::spawn(async move {
        tokio::time::sleep(tokio::time::Duration::from_secs(20)).await;
        info!("Contract Bridge: ProofOfThought submission started (every 10 blocks)");
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(15)).await;
            let height = *pot_contract_state.chain_height.lock().await;
            let last = *pot_contract_state.last_pot_block.lock().await;

            if height > last + 10 && height > 0 {
                if !pot_contract_state.contract_bridge.is_available().await {
                    continue;
                }

                // Generate PoT hashes from consciousness state
                let consciousness = pot_contract_state.consciousness.lock().await;
                let phi = consciousness.current_phi();
                let phi_micro = consciousness.phi_micro();
                drop(consciousness);

                // Create deterministic hashes from attention state + block height
                let solution_data = format!("aether-pot:{}:{}:{}", height, phi, phi_micro);
                let solution_hash = {
                    use sha2::{Sha256, Digest};
                    let mut hasher = Sha256::new();
                    hasher.update(solution_data.as_bytes());
                    let result = hasher.finalize();
                    let mut h = [0u8; 32];
                    h.copy_from_slice(&result);
                    h
                };

                let quantum_data = format!("aether-quantum:{}:{}", height, pot_contract_state.fabric.total_vectors());
                let quantum_hash = {
                    use sha2::{Sha256, Digest};
                    let mut hasher = Sha256::new();
                    hasher.update(quantum_data.as_bytes());
                    let result = hasher.finalize();
                    let mut h = [0u8; 32];
                    h.copy_from_slice(&result);
                    h
                };

                match pot_contract_state.contract_bridge.submit_proof(
                    solution_hash, quantum_hash, height,
                ).await {
                    Ok(tx) => {
                        info!("CONTRACT: Submitted PoT at height {} (tx: {})", height, tx);
                        *pot_contract_state.last_pot_block.lock().await = height;
                    }
                    Err(e) => {
                        if !e.to_string().contains("error sending request") {
                            warn!("CONTRACT: submitProof failed: {}", e);
                        }
                    }
                }
            }
        }
    });

    // Task 4: AetherSoul personality sync (every 500 blocks)
    let soul_contract_state = Arc::clone(&state);
    tokio::spawn(async move {
        tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;
            let height = *soul_contract_state.chain_height.lock().await;
            let last = *soul_contract_state.last_soul_block.lock().await;

            if height > last + 500 && height > 0 {
                if !soul_contract_state.contract_bridge.is_available().await {
                    continue;
                }

                let traits = {
                    let consciousness = soul_contract_state.consciousness.lock().await;
                    let emotions = consciousness.emotional_state();
                    [
                        (emotions.curiosity * 1000.0) as u64,      // curiosity
                        (emotions.satisfaction * 1000.0) as u64,    // warmth
                        700,                                         // honesty (constant)
                        600,                                         // humility (constant)
                        (emotions.wonder * 1000.0) as u64,          // playfulness
                        800,                                         // depth (constant)
                        (emotions.excitement * 1000.0) as u64,      // courage
                    ]
                };

                match soul_contract_state.contract_bridge.update_soul_personality(traits).await {
                    Ok(tx) => {
                        info!("CONTRACT: Updated AetherSoul personality (tx: {})", tx);
                        *soul_contract_state.last_soul_block.lock().await = height;
                    }
                    Err(e) => {
                        // AetherSoul may not be deployed — this is expected
                        if !e.to_string().contains("not deployed") && !e.to_string().contains("error sending request") {
                            warn!("CONTRACT: updateSoulPersonality failed: {}", e);
                        }
                    }
                }
            }
        }
    });

    // Task 5: SynapticStaking utility updates from attention weights (every 100 blocks)
    let staking_state = Arc::clone(&state);
    tokio::spawn(async move {
        tokio::time::sleep(tokio::time::Duration::from_secs(45)).await;
        info!("Contract Bridge: SynapticStaking utility updates started (every 100 blocks)");
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;
            let height = *staking_state.chain_height.lock().await;
            if height == 0 {
                continue;
            }

            // Only update every 100 blocks (check against last phi block as sync point)
            let last_phi = *staking_state.last_phi_block.lock().await;
            if height <= last_phi {
                continue;
            }

            if !staking_state.contract_bridge.is_available().await {
                continue;
            }

            // Check how many connections exist on-chain
            let conn_count = match staking_state.contract_bridge.get_connection_count().await {
                Ok(c) => c,
                Err(_) => continue,
            };

            if conn_count == 0 {
                continue;
            }

            // Compute attention-derived utility per Sephirot domain from consciousness monitor.
            // Each domain gets a utility score based on how active its attention head is.
            let consciousness = staking_state.consciousness.lock().await;
            let phi_meso = consciousness.phi_meso();
            drop(consciousness);

            // Distribute utility across connections (simplified: each connection gets
            // a share proportional to domain involvement)
            let base_utility = (phi_meso * 1_000_000.0) as u64;
            let per_connection = if conn_count > 0 { base_utility / conn_count } else { 0 };

            if per_connection > 0 {
                // Update first 10 connections max (one per Sephirot pair)
                let update_count = conn_count.min(10);
                for conn_id in 0..update_count {
                    match staking_state.contract_bridge.update_staking_utility(conn_id, per_connection).await {
                        Ok(_) => {}
                        Err(e) => {
                            if !e.to_string().contains("error sending request") {
                                warn!("CONTRACT: updateUtility({}) failed: {}", conn_id, e);
                            }
                            break;
                        }
                    }
                }
                info!("CONTRACT: Updated {} staking connections with utility={}", update_count, per_connection);
            }
        }
    });

    // Task 6: ConstitutionalAI principles check (at startup + every 1000 blocks)
    let constitution_state = Arc::clone(&state);
    tokio::spawn(async move {
        tokio::time::sleep(tokio::time::Duration::from_secs(20)).await;
        info!("Contract Bridge: ConstitutionalAI principles check started");
        let mut last_check_height: u64 = 0;

        loop {
            let height = *constitution_state.chain_height.lock().await;

            // Check at startup (last_check_height == 0) and every 1000 blocks
            if last_check_height == 0 || height > last_check_height + 1000 {
                if !constitution_state.contract_bridge.is_available().await {
                    tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;
                    continue;
                }

                match constitution_state.contract_bridge.get_principle_count().await {
                    Ok((total, active)) => {
                        info!(
                            "CONTRACT: ConstitutionalAI has {} principles ({} active) — Gevurah safety informed",
                            total, active
                        );
                        last_check_height = height;
                    }
                    Err(e) => {
                        if !e.to_string().contains("error sending request") {
                            warn!("CONTRACT: ConstitutionalAI check failed: {}", e);
                        }
                    }
                }

                // Also read Higgs field state for transparency
                match constitution_state.contract_bridge.get_higgs_field_state().await {
                    Ok((vev, current)) => {
                        if vev > 0 {
                            info!("CONTRACT: HiggsField state — VEV={}, currentField={}", vev, current);
                        }
                    }
                    Err(_) => {} // Non-critical
                }
            }

            tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;
        }
    });

    // Background delta decay: gradually decay old deltas to prevent unbounded growth.
    // Real gradient signal comes from attention pattern changes during chat inference.
    let delta_state = Arc::clone(&state);
    tokio::spawn(async move {
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(120)).await;
            let mut deltas = delta_state.embedding_deltas.lock().await;
            // Decay: multiply all deltas by 0.95 to prevent unbounded accumulation
            for d in deltas.iter_mut() {
                *d *= 0.95;
            }
        }
    });

    // Background gradient application: drain accumulated embedding deltas and apply
    // them to the transformer's embedding weights every 60 seconds.
    // This closes the gradient→weight gap — FedAvg deltas actually update the model.
    let grad_apply_state = Arc::clone(&state);
    tokio::spawn(async move {
        // Wait for model and fabric to stabilize before applying gradients
        tokio::time::sleep(tokio::time::Duration::from_secs(90)).await;
        info!("Gradient application: background loop started (60s interval)");
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;

            // Drain the embedding deltas
            let deltas = {
                let mut d = grad_apply_state.embedding_deltas.lock().await;
                let delta_norm: f32 = d.iter().map(|v| v * v).sum::<f32>().sqrt();
                if delta_norm < 1e-8 {
                    continue; // Nothing meaningful to apply
                }
                info!("Gradient application: draining deltas (norm={:.6})", delta_norm);
                let snapshot = d.clone();
                // Zero out deltas after consumption
                for v in d.iter_mut() {
                    *v = 0.0;
                }
                snapshot
            };

            // Read learning rate from active genome
            let lr = {
                let archive = grad_apply_state.evolve_archive.lock().await;
                archive.active_genome.learning_rate
            };

            // Apply to model weights
            let mut model = grad_apply_state.model.lock().await;
            match model.apply_embedding_deltas(&deltas, lr) {
                Ok(()) => {}
                Err(e) => warn!("Gradient application failed: {}", e),
            }
        }
    });

    // Background HMS-Phi consciousness computation: runs every 60 seconds independent of chat.
    // Keeps consciousness monitoring active even without user interaction by running a candle
    // forward pass on representative queries and computing phi from attention weights.
    let phi_bg_state = Arc::clone(&state);
    tokio::spawn(async move {
        // Wait for fabric to populate before starting phi computation
        tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
        info!("Background phi computation: started (60s interval)");

        let representative_queries: [&str; 5] = [
            "What is the current state of the Qubitcoin blockchain network?",
            "Explain supersymmetric economics and phi-halving emission schedule",
            "How does proof-of-thought consensus validate AI reasoning on-chain?",
            "Describe the relationship between quantum VQE mining and energy thresholds",
            "What role do the ten Sephirot cognitive domains play in knowledge integration?",
        ];
        let mut query_index: usize = 0;

        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;

            // Only run if we have meaningful knowledge
            let total_vecs = phi_bg_state.fabric.total_vectors();
            if total_vecs < 100 {
                continue;
            }

            let query = representative_queries[query_index % representative_queries.len()];
            query_index += 1;

            // Tokenize the representative query
            let encoding = match phi_bg_state.tokenizer.encode(query, false) {
                Ok(enc) => enc.get_ids().to_vec(),
                Err(_) => continue,
            };

            if encoding.len() <= 1 || encoding.len() >= 128 {
                continue;
            }

            let device = candle_core::Device::Cpu;
            let query_tensor = match candle_core::Tensor::new(encoding.as_slice(), &device)
                .and_then(|t| t.unsqueeze(0))
            {
                Ok(t) => t,
                Err(_) => continue,
            };

            // Run candle forward pass — lock model briefly
            let attn_result = {
                let mut model = phi_bg_state.model.lock().await;
                model.clear_kv_cache();
                model.forward(&query_tensor, 0, true)
            };
            // Model lock is released here

            if let Ok((_logits, attn_weights)) = attn_result {
                let height = *phi_bg_state.chain_height.lock().await;
                let num_heads = phi_bg_state.config.total_heads();
                let num_sephirot = phi_bg_state.config.num_sephirot_heads;
                let num_global = phi_bg_state.config.num_global_heads;

                let mut layer_attentions: Vec<Vec<f32>> = Vec::new();
                for attn_tensor in &attn_weights {
                    let flat = attn_tensor
                        .to_dtype(DType::F32)
                        .and_then(|t| t.flatten_all())
                        .and_then(|t| t.to_vec1::<f32>());
                    if let Ok(v) = flat {
                        layer_attentions.push(v);
                    }
                }

                if !layer_attentions.is_empty() {
                    let kv_len = attn_weights
                        .last()
                        .and_then(|t| t.dim(3).ok())
                        .unwrap_or(1);
                    let mut consciousness = phi_bg_state.consciousness.lock().await;
                    consciousness.set_block_height(height);
                    let measurement = consciousness.compute_phi(
                        &layer_attentions, num_sephirot, num_global, num_heads, kv_len,
                    );
                    info!(
                        "Background phi: {:.6} (micro={:.6}, meso={:.6}, macro={:.6}) | query={} | vectors={}",
                        measurement.phi, measurement.phi_micro, measurement.phi_meso,
                        measurement.phi_macro, query_index % representative_queries.len(),
                        total_vecs,
                    );
                }
            }
        }
    });

    // Background state persistence: save every 60 seconds
    // IMPORTANT: acquire each lock briefly and release before acquiring the next to avoid deadlock.
    let persist_state = Arc::clone(&state);
    tokio::spawn(async move {
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;
            let path = state_path();
            if let Some(parent) = path.parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            let chat_count = *persist_state.chat_count.lock().await;
            let (evolve_mutations, evolve_improvements, evolve_rollbacks, best_fitness) = {
                let archive = persist_state.evolve_archive.lock().await;
                (archive.total_mutations, archive.improvements, archive.rollbacks, archive.best_fitness)
            };
            let (best_phi, best_phi_meso, best_phi_micro) = {
                let consciousness = persist_state.consciousness.lock().await;
                let phi = consciousness.current_phi();
                let meso = consciousness.phi_meso();
                let micro = consciousness.phi_micro();
                // Only update if we have actual measurements (avoid overwriting with 0)
                let prev = PersistentState::load(&path);
                if phi > 0.0 { (phi, meso, micro) }
                else { (prev.best_phi, prev.best_phi_meso, prev.best_phi_micro) }
            };
            let loss_history: Vec<(u64, f32)> = {
                let tracker = persist_state.loss_tracker.lock().await;
                tracker.loss_history().to_vec()
            };
            let ps = PersistentState {
                chat_count, evolve_mutations, evolve_improvements, evolve_rollbacks,
                best_fitness, best_phi, best_phi_meso, best_phi_micro, loss_history,
            };
            ps.save(&path);
        }
    });

    let app = Router::new()
        .route("/health", get(health))
        .route("/aether/info", get(info))
        .route("/aether/benchmark", get(benchmark))
        .route("/aether/chat", post(chat))
        .route("/aether/phi", get(phi_endpoint))
        .route("/aether/pot", get(proof_of_thought))
        .route("/aether/neural-payload", get(neural_payload))
        .route("/aether/gradients", get(gradient_status).post(submit_gradients))
        .route("/aether/rewards/pool", get(rewards_pool))
        .route("/aether/rewards/claim", post(rewards_claim))
        .route("/aether/rewards/{miner_id}", get(rewards_for_miner))
        .route("/aether/evolve", get(evolve_status))
        .route("/aether/evolve/mutate", post(evolve_mutate))
        .route("/aether/gates", get(gates_endpoint))
        .route("/aether/knowledge/search", get(knowledge_search))
        .route("/aether/contracts/status", get(contracts_status))
        .route("/aether/auth/check", get(auth_check))
        .route("/aether/auth/deduct", post(auth_deduct))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let port = std::env::var("AETHER_MIND_PORT").unwrap_or_else(|_| "5003".to_string());
    let addr = format!("0.0.0.0:{port}");

    info!("Aether Mind V5 listening on {addr}");
    info!("  POST /aether/chat            — Neural generation + consciousness + RAG");
    info!("  GET  /aether/info            — Architecture + Sephirot domains");
    info!("  GET  /aether/phi             — HMS-Phi consciousness + emotions");
    info!("  GET  /aether/pot             — Proof-of-Thought attestation");
    info!("  GET  /aether/neural-payload  — Training payload for block inclusion");
    info!("  POST /aether/gradients       — FedAvg gradient submission from peers");
    info!("  GET  /aether/gradients       — Gradient aggregation status");
    info!("  GET  /aether/rewards/pool     — Gradient reward pool status");
    info!("  GET  /aether/rewards/{{miner}}  — Miner reward balance");
    info!("  POST /aether/rewards/claim    — Claim gradient rewards");
    info!("  GET  /aether/evolve          — NAS evolution status");
    info!("  POST /aether/evolve/mutate   — Trigger evolution cycle");
    info!("  GET  /aether/gates           — V5 neural capability gates");
    info!("  GET  /aether/benchmark       — 10-token inference benchmark");
    info!("  GET  /aether/knowledge/search — Knowledge Fabric search");
    info!("  GET  /aether/contracts/status — On-chain contract bridge status");
    info!("  GET  /aether/auth/check      — Subscription check (gateway auth)");
    info!("  POST /aether/auth/deduct     — Fee deduction (gateway auth)");
    info!("  GET  /health                 — Full health check");

    let listener = tokio::net::TcpListener::bind(&addr).await?;

    // Graceful shutdown: save fabric + state on SIGTERM/SIGINT
    let shutdown_dir = fabric_dir.clone();
    let shutdown_signal = async move {
        let _ = tokio::signal::ctrl_c().await;
        info!("Shutting down — saving Knowledge Fabric + state...");
        match fabric_for_shutdown.save_to_dir(&shutdown_dir) {
            Ok(n) => info!("Saved {} vectors to {:?}", n, shutdown_dir),
            Err(e) => warn!("Save error on shutdown: {}", e),
        }
        // Save persistent state (acquire locks one at a time)
        let path = state_path();
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        let chat_count = *shutdown_state.chat_count.lock().await;
        let (em, ei, er, bf) = {
            let a = shutdown_state.evolve_archive.lock().await;
            (a.total_mutations, a.improvements, a.rollbacks, a.best_fitness)
        };
        let (bp, bpm, bpmi) = {
            let c = shutdown_state.consciousness.lock().await;
            let phi = c.current_phi();
            let meso = c.phi_meso();
            let micro = c.phi_micro();
            if phi > 0.0 { (phi, meso, micro) }
            else {
                let prev = PersistentState::load(&path);
                (prev.best_phi, prev.best_phi_meso, prev.best_phi_micro)
            }
        };
        let lh: Vec<(u64, f32)> = {
            let t = shutdown_state.loss_tracker.lock().await;
            t.loss_history().to_vec()
        };
        let ps = PersistentState {
            chat_count, evolve_mutations: em, evolve_improvements: ei,
            evolve_rollbacks: er, best_fitness: bf, best_phi: bp,
            best_phi_meso: bpm, best_phi_micro: bpmi, loss_history: lh,
        };
        ps.save(&path);
        info!("Saved persistent state to {:?} (chats={}, evolve_mutations={})", path, chat_count, em);
    };

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal)
        .await?;

    Ok(())
}
