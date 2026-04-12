//! Main Aether chat engine with session management, KG-first response
//! synthesis, entity extraction, and persistent per-user memory.
//!
//! Architecture (ADR-038 / ADR-039):
//! - Intent detection uses keyword matching (not LLM) for speed.
//! - Response synthesis pulls from graph facts first, LLM fallback for
//!   responses under 80 characters.
//! - No template prose -- responses built from live data.
//! - Personality: warm, curious, self-reflective.

use log::{debug, info, warn};
use parking_lot::RwLock;
use regex::Regex;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Instant, SystemTime, UNIX_EPOCH};
use uuid::Uuid;

use crate::intent::{Intent, IntentDetector, try_math, split_questions};
use crate::llm_adapter::{LLMAdapter, LLMResponse, AETHER_SYSTEM_PROMPT};
use crate::response::{
    ChatContext, ChatResponse, KGFact, ResponseBuilder, ResponseSource,
    format_number, score_response_quality,
};

/// Maximum messages per session.
const MAX_SESSION_MESSAGES: usize = 1000;
/// Rate limit: max messages per minute per session.
const RATE_LIMIT_MESSAGES: usize = 30;
/// Rate limit window in seconds.
const RATE_LIMIT_WINDOW_SECS: f64 = 60.0;
/// Session time-to-live in seconds (2 hours).
const SESSION_TTL_SECS: f64 = 7200.0;
/// Conversation context window (last N messages).
const CONVERSATION_CONTEXT_WINDOW: usize = 10;
/// Minimum response length before LLM augmentation is triggered.
const MIN_KG_RESPONSE_LEN: usize = 80;

/// QBC abbreviation expansion map.
fn abbreviation_map() -> HashMap<&'static str, &'static str> {
    let mut m = HashMap::new();
    m.insert("qbc", "Qubitcoin");
    m.insert("posa", "Proof-of-SUSY-Alignment");
    m.insert("vqe", "Variational Quantum Eigensolver");
    m.insert("qusd", "QUSD stablecoin");
    m.insert("kg", "knowledge graph");
    m.insert("agi", "Artificial General Intelligence");
    m.insert("iit", "Integrated Information Theory");
    m.insert("susy", "supersymmetry");
    m.insert("phi", "Phi consciousness metric");
    m.insert("evm", "Ethereum Virtual Machine");
    m.insert("qvm", "Quantum Virtual Machine");
    m.insert("utxo", "Unspent Transaction Output");
    m.insert("pot", "Proof-of-Thought");
    m.insert("zk", "zero-knowledge");
    m
}

/// A single message in a chat session.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    /// Role: "user" or "aether".
    pub role: String,
    /// Message content.
    pub content: String,
    /// Unix timestamp.
    pub timestamp: f64,
    /// Reasoning trace for this response.
    pub reasoning_trace: Vec<HashMap<String, serde_json::Value>>,
    /// Phi value at time of response.
    pub phi_at_response: f64,
    /// Knowledge node IDs referenced.
    pub knowledge_nodes_referenced: Vec<u64>,
    /// Proof-of-Thought hash.
    pub proof_of_thought_hash: String,
}

impl ChatMessage {
    /// Create a new user message.
    pub fn user(content: &str) -> Self {
        Self {
            role: "user".to_string(),
            content: content.to_string(),
            timestamp: now_unix(),
            reasoning_trace: Vec::new(),
            phi_at_response: 0.0,
            knowledge_nodes_referenced: Vec::new(),
            proof_of_thought_hash: String::new(),
        }
    }

    /// Create a new Aether response message.
    pub fn aether(content: &str) -> Self {
        Self {
            role: "aether".to_string(),
            content: content.to_string(),
            timestamp: now_unix(),
            reasoning_trace: Vec::new(),
            phi_at_response: 0.0,
            knowledge_nodes_referenced: Vec::new(),
            proof_of_thought_hash: String::new(),
        }
    }
}

/// A chat session with multi-turn context tracking.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatSession {
    /// Unique session identifier.
    pub session_id: String,
    /// Messages in this session.
    pub messages: Vec<ChatMessage>,
    /// Creation timestamp (unix).
    pub created_at: f64,
    /// Last activity timestamp (unix).
    pub last_activity: f64,
    /// User wallet address (optional).
    pub user_address: String,
    /// Total messages sent in this session.
    pub messages_sent: usize,
    /// Fees paid in atoms.
    pub fees_paid_atoms: u64,
    /// Timestamps of recent messages (for rate limiting).
    pub message_timestamps: Vec<f64>,
    /// Current conversation topic.
    pub current_topic: String,
    /// Recent topics (last 20).
    pub recent_topics: Vec<String>,
    /// Response dedup cache (query_hash -> response).
    #[serde(skip)]
    pub response_cache: HashMap<String, String>,
    /// Accumulated entities across the conversation.
    pub context_entities: HashMap<String, Vec<String>>,
    /// Topic weights (topic -> recency weight).
    pub context_topics_weight: HashMap<String, f64>,
}

impl ChatSession {
    /// Create a new session.
    pub fn new(user_address: &str) -> Self {
        let now = now_unix();
        Self {
            session_id: Uuid::new_v4().to_string(),
            messages: Vec::new(),
            created_at: now,
            last_activity: now,
            user_address: user_address.to_string(),
            messages_sent: 0,
            fees_paid_atoms: 0,
            message_timestamps: Vec::new(),
            current_topic: String::new(),
            recent_topics: Vec::new(),
            response_cache: HashMap::new(),
            context_entities: HashMap::new(),
            context_topics_weight: HashMap::new(),
        }
    }

    /// Build a context window from recent messages.
    pub fn build_context_window(&self) -> ChatContext {
        let window_start = if self.messages.len() > CONVERSATION_CONTEXT_WINDOW {
            self.messages.len() - CONVERSATION_CONTEXT_WINDOW
        } else {
            0
        };
        let window = &self.messages[window_start..];

        let conversation_history: Vec<(String, String)> = window.iter()
            .map(|m| (m.role.clone(), truncate(&m.content, 200)))
            .collect();

        // Topic distribution with recency weighting
        let mut topic_dist: HashMap<String, f64> = HashMap::new();
        let recent = if self.recent_topics.len() > 10 {
            &self.recent_topics[self.recent_topics.len() - 10..]
        } else {
            &self.recent_topics
        };
        let n = recent.len().max(1) as f64;
        for (i, topic) in recent.iter().enumerate() {
            let weight = 0.5 + 0.5 * (i as f64 / (n - 1.0).max(1.0));
            *topic_dist.entry(topic.clone()).or_default() += weight;
        }

        ChatContext {
            conversation_history,
            current_topic: self.current_topic.clone(),
            user_memories: HashMap::new(), // Filled by chat engine
            entity_context: String::new(), // Filled by chat engine
            follow_up_context: self.get_follow_up_context(),
            kg_facts: Vec::new(), // Filled by chat engine
            system_state: HashMap::new(), // Filled by chat engine
        }
    }

    /// Build a follow-up context string for resolving references.
    pub fn get_follow_up_context(&self) -> String {
        if self.messages.is_empty() {
            return String::new();
        }
        let mut parts = Vec::new();
        if !self.current_topic.is_empty() {
            parts.push(format!("Current topic: {}", self.current_topic));
        }
        // Last user message
        for m in self.messages.iter().rev().take(5) {
            if m.role == "user" {
                parts.push(format!("Previous question: {}", truncate(&m.content, 150)));
                break;
            }
        }
        // Last assistant response
        for m in self.messages.iter().rev().take(5) {
            if m.role == "aether" {
                parts.push(format!("Last response: {}", truncate(&m.content, 150)));
                break;
            }
        }
        // Recent entities
        for (etype, vals) in self.context_entities.iter().take(3) {
            if !vals.is_empty() {
                let recent: Vec<&str> = vals.iter().rev().take(3)
                    .map(|v| truncate_ref(v, 30))
                    .collect();
                parts.push(format!("Referenced {}: {}", etype, recent.join(", ")));
            }
        }
        parts.join(" | ")
    }

    /// Update session context after processing a message.
    pub fn update_context(&mut self, intent: Intent, entities: Option<&HashMap<String, Vec<String>>>) {
        let intent_str = intent.as_str().to_string();
        self.recent_topics.push(intent_str.clone());
        if self.recent_topics.len() > 20 {
            let start = self.recent_topics.len() - 20;
            self.recent_topics = self.recent_topics[start..].to_vec();
        }
        let w = self.context_topics_weight.entry(intent_str).or_insert(0.0);
        *w = *w * 0.8 + 1.0;

        if let Some(ents) = entities {
            for (key, vals) in ents {
                let entry = self.context_entities.entry(key.clone()).or_default();
                for v in vals {
                    if !entry.contains(v) {
                        entry.push(v.clone());
                    }
                }
                if entry.len() > 20 {
                    let start = entry.len() - 20;
                    *entry = entry[start..].to_vec();
                }
            }
        }
    }

    /// Check if the session has expired.
    pub fn is_expired(&self) -> bool {
        now_unix() - self.last_activity > SESSION_TTL_SECS
    }
}

/// Persistent per-user key-value memory for Aether chat.
///
/// Stores user preferences, interests, and context across sessions.
/// Persists to a JSON file so memories survive restarts.
pub struct ChatMemory {
    memories: RwLock<HashMap<String, HashMap<String, String>>>,
    storage_path: Option<String>,
    max_users: usize,
    max_keys_per_user: usize,
}

impl ChatMemory {
    /// Create with optional file persistence.
    pub fn new(storage_path: Option<String>) -> Self {
        let mem = Self {
            memories: RwLock::new(HashMap::new()),
            storage_path,
            max_users: 100_000,
            max_keys_per_user: 100,
        };
        mem.load();
        mem
    }

    /// Store a key-value memory for a user.
    pub fn remember(&self, user_id: &str, key: &str, value: &str) {
        let mut memories = self.memories.write();
        if !memories.contains_key(user_id) {
            if memories.len() >= self.max_users {
                // Evict first (oldest) user
                if let Some(oldest) = memories.keys().next().cloned() {
                    memories.remove(&oldest);
                }
            }
            memories.insert(user_id.to_string(), HashMap::new());
        }
        let user_mem = memories.get_mut(user_id).unwrap();
        if user_mem.len() >= self.max_keys_per_user && !user_mem.contains_key(key) {
            // Evict oldest key
            if let Some(oldest_key) = user_mem.keys().next().cloned() {
                user_mem.remove(&oldest_key);
            }
        }
        user_mem.insert(key.to_string(), value.to_string());
        drop(memories);
        self.save();
    }

    /// Recall a specific memory for a user.
    pub fn recall(&self, user_id: &str, key: &str) -> Option<String> {
        let memories = self.memories.read();
        memories.get(user_id)?.get(key).cloned()
    }

    /// Recall all memories for a user.
    pub fn recall_all(&self, user_id: &str) -> HashMap<String, String> {
        let memories = self.memories.read();
        memories.get(user_id).cloned().unwrap_or_default()
    }

    /// Remove a specific memory for a user.
    pub fn forget(&self, user_id: &str, key: &str) {
        let mut memories = self.memories.write();
        if let Some(user_mem) = memories.get_mut(user_id) {
            user_mem.remove(key);
            if user_mem.is_empty() {
                memories.remove(user_id);
            }
        }
        drop(memories);
        self.save();
    }

    /// Extract key facts from a conversation exchange using regex patterns.
    pub fn extract_memories(message: &str, _response: &str) -> HashMap<String, String> {
        let mut extracted = HashMap::new();
        let msg_lower = message.to_lowercase();

        // Interest patterns
        let interest_re = Regex::new(
            r"i(?:'m| am) (?:interested in|curious about|really into) (.+?)(?:\.|,|!|$)"
        ).ok();
        if let Some(re) = &interest_re {
            if let Some(caps) = re.captures(&msg_lower) {
                if let Some(m) = caps.get(1) {
                    extracted.insert("interest".into(), m.as_str().trim().to_string());
                }
            }
        }

        // Name patterns
        let name_re = Regex::new(r"(?:my name is|call me) (\w+)").ok();
        if let Some(re) = &name_re {
            if let Some(caps) = re.captures(&msg_lower) {
                if let Some(m) = caps.get(1) {
                    let name = m.as_str().trim();
                    if name.len() >= 2 {
                        let mut chars = name.chars();
                        let capitalized: String = chars.next()
                            .map(|c| c.to_uppercase().to_string())
                            .unwrap_or_default()
                            + chars.as_str();
                        extracted.insert("name".into(), capitalized);
                    }
                }
            }
        }

        // Preferred topic keywords
        let topic_keywords = [
            ("defi", "DeFi"), ("nft", "NFTs"), ("mining", "mining"),
            ("quantum", "quantum computing"), ("staking", "staking"),
            ("governance", "governance"), ("privacy", "privacy"),
            ("bridge", "cross-chain bridges"), ("smart contract", "smart contracts"),
            ("economics", "token economics"), ("aether", "Aether Tree AGI"),
            ("consciousness", "consciousness"),
        ];
        for (keyword, topic) in &topic_keywords {
            if msg_lower.contains(keyword) {
                extracted.insert("preferred_topic".into(), topic.to_string());
                break;
            }
        }

        // "remember that X" -- generic remember command
        let remember_re = Regex::new(r"remember (?:that )?(.+?)(?:\.|!|$)").ok();
        if let Some(re) = &remember_re {
            if let Some(caps) = re.captures(&msg_lower) {
                if let Some(m) = caps.get(1) {
                    let fact = m.as_str().trim();
                    if fact.len() > 2 {
                        extracted.insert("remembered_fact".into(), fact.to_string());
                    }
                }
            }
        }

        extracted
    }

    fn load(&self) {
        if let Some(path) = &self.storage_path {
            match std::fs::read_to_string(path) {
                Ok(data) if !data.is_empty() => {
                    match serde_json::from_str(&data) {
                        Ok(parsed) => {
                            let mut memories = self.memories.write();
                            *memories = parsed;
                            debug!("ChatMemory loaded {} users from {}",
                                memories.len(), path);
                        }
                        Err(e) => debug!("ChatMemory parse failed: {}", e),
                    }
                }
                _ => {}
            }
        }
    }

    fn save(&self) {
        if let Some(path) = &self.storage_path {
            let memories = self.memories.read();
            match serde_json::to_string_pretty(&*memories) {
                Ok(data) => {
                    if let Err(e) = std::fs::write(path, data) {
                        warn!("ChatMemory save failed: {}", e);
                    }
                }
                Err(e) => warn!("ChatMemory serialize failed: {}", e),
            }
        }
    }

    /// Total number of tracked users.
    pub fn user_count(&self) -> usize {
        self.memories.read().len()
    }
}

/// Entity extraction result from a user query.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ExtractedEntities {
    pub addresses: Vec<EntityAddress>,
    pub numbers: Vec<EntityNumber>,
    pub timeframes: Vec<EntityTimeframe>,
    pub tokens: Vec<String>,
    pub contracts: Vec<String>,
    pub protocol_terms: Vec<String>,
    pub modifiers: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntityAddress {
    pub addr_type: String,
    pub value: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntityNumber {
    pub num_type: String,
    pub value: f64,
    pub raw: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntityTimeframe {
    pub tf_type: String,
    pub value: String,
    pub quantity: Option<i64>,
    pub unit: Option<String>,
}

/// Main Aether chat engine.
///
/// Manages sessions, intent detection, entity extraction, KG-first response
/// synthesis, and LLM fallback.
pub struct AetherChat {
    intent_detector: IntentDetector,
    memory: Arc<ChatMemory>,
    sessions: RwLock<HashMap<String, ChatSession>>,
    max_sessions: usize,
    /// Pre-compiled regexes for entity extraction.
    re_hex_addr: Regex,
    re_hex_hash: Regex,
    re_qbc_addr: Regex,
    re_block_height: Regex,
    re_amount: Regex,
    re_percentage: Regex,
    re_time_last: Regex,
    re_time_since: Regex,
    re_time_keyword: Regex,
    re_modifier: Regex,
    /// Known tokens for entity extraction.
    known_tokens: HashMap<String, String>,
    /// Known contract names.
    known_contracts: Vec<String>,
    /// Known protocol terms.
    protocol_terms: Vec<String>,
    /// Axiom hit counts for tracking usage frequency.
    axiom_hit_counts: RwLock<HashMap<u64, u64>>,
}

impl AetherChat {
    /// Create a new AetherChat engine.
    pub fn new(memory_path: Option<String>) -> Self {
        let mut known_tokens = HashMap::new();
        for (k, v) in [
            ("qbc", "QBC"), ("qusd", "QUSD"), ("eth", "ETH"), ("btc", "BTC"),
            ("sol", "SOL"), ("matic", "MATIC"), ("bnb", "BNB"), ("avax", "AVAX"),
            ("arb", "ARB"), ("op", "OP"), ("wqbc", "wQBC"), ("wqusd", "wQUSD"),
        ] {
            known_tokens.insert(k.to_string(), v.to_string());
        }

        let known_contracts: Vec<String> = [
            "higgs", "higgsfield", "higgs field", "aether tree", "aethertree",
            "qbc-20", "qbc-721", "qusd keeper", "peg keeper", "bridge",
            "launchpad", "governance", "treasury", "vault", "staking",
            "fee collector", "reversibility",
        ].iter().map(|s| s.to_string()).collect();

        let protocol_terms: Vec<String> = [
            "utxo", "mempool", "merkle", "genesis", "coinbase", "dilithium",
            "vqe", "hamiltonian", "proof of thought", "proof-of-thought",
            "sephirot", "phi", "consciousness", "knowledge graph", "susy",
            "gossipsub", "kademlia", "grpc", "json-rpc", "stratum",
            "bulletproof", "pedersen", "stealth address", "range proof",
        ].iter().map(|s| s.to_string()).collect();

        Self {
            intent_detector: IntentDetector::new(),
            memory: Arc::new(ChatMemory::new(memory_path)),
            sessions: RwLock::new(HashMap::new()),
            max_sessions: 10_000,
            re_hex_addr: Regex::new(r"\b(0x[0-9a-fA-F]{40})\b").unwrap(),
            re_hex_hash: Regex::new(r"\b(0x[0-9a-fA-F]{64})\b").unwrap(),
            re_qbc_addr: Regex::new(r"(?i)\b(qbc1[a-z0-9]{8,62})\b").unwrap(),
            re_block_height: Regex::new(r"(?i)\bblock\s*(?:#|number|height)?\s*(\d{1,10})\b").unwrap(),
            re_amount: Regex::new(r"(?i)\b(\d+(?:\.\d+)?)\s*(?:qbc|qusd|eth|btc|tokens?|coins?)\b").unwrap(),
            re_percentage: Regex::new(r"\b(\d+(?:\.\d+)?)\s*%").unwrap(),
            re_time_last: Regex::new(
                r"(?i)\b(?:last|past|previous)\s+(\d+)?\s*(hours?|minutes?|days?|weeks?|months?|blocks?)\b"
            ).unwrap(),
            re_time_since: Regex::new(r"(?i)\bsince\s+block\s+(\d+)\b").unwrap(),
            re_time_keyword: Regex::new(
                r"(?i)\b(today|yesterday|this\s+week|this\s+month|right\s+now|recently)\b"
            ).unwrap(),
            re_modifier: Regex::new(
                r"(?i)\b(detailed|detail|summary|summarize|compare|comparison|explain|explanation|brief|verbose|overview|breakdown|in\s+depth)\b"
            ).unwrap(),
            known_tokens,
            known_contracts,
            protocol_terms,
            axiom_hit_counts: RwLock::new(HashMap::new()),
        }
    }

    /// Create a new chat session.
    pub fn create_session(&self, user_address: &str) -> ChatSession {
        let session = ChatSession::new(user_address);
        let session_id = session.session_id.clone();

        let mut sessions = self.sessions.write();

        // Cleanup expired sessions
        let expired: Vec<String> = sessions.iter()
            .filter(|(_, s)| s.is_expired())
            .map(|(id, _)| id.clone())
            .collect();
        for id in expired {
            sessions.remove(&id);
        }

        // Evict oldest if at capacity
        if sessions.len() >= self.max_sessions {
            if let Some(oldest_id) = sessions.iter()
                .min_by(|a, b| a.1.created_at.partial_cmp(&b.1.created_at).unwrap_or(std::cmp::Ordering::Equal))
                .map(|(id, _)| id.clone())
            {
                sessions.remove(&oldest_id);
            }
        }

        sessions.insert(session_id.clone(), session.clone());
        info!("Chat session created: {}...", &session_id[..8]);
        session
    }

    /// Get an existing session by ID.
    pub fn get_session(&self, session_id: &str) -> Option<ChatSession> {
        self.sessions.read().get(session_id).cloned()
    }

    /// Get the fee for the next message in a session.
    pub fn get_message_fee(
        &self,
        session_id: &str,
        is_deep_query: bool,
        free_tier_messages: usize,
        base_fee_qbc: f64,
        query_fee_multiplier: f64,
    ) -> Option<MessageFee> {
        let sessions = self.sessions.read();
        let session = sessions.get(session_id)?;

        let free_remaining = free_tier_messages.saturating_sub(session.messages_sent);
        let is_free = free_remaining > 0;

        let fee = if is_free {
            0.0
        } else {
            let mut f = base_fee_qbc;
            if is_deep_query {
                f *= query_fee_multiplier;
            }
            f
        };

        Some(MessageFee {
            fee_qbc: fee,
            is_free,
            free_remaining,
        })
    }

    /// Process a user message and generate a response.
    ///
    /// This is the main entry point. It:
    /// 1. Detects intent via keyword matching
    /// 2. Extracts entities via regex
    /// 3. Loads user memories
    /// 4. Handles special intents (math, memory commands)
    /// 5. Queries KG for relevant facts (via callback)
    /// 6. Falls back to LLM if KG response is too short
    /// 7. Updates session context and memories
    pub fn process_message(
        &self,
        session_id: &str,
        message: &str,
        kg_search: Option<&dyn Fn(&str) -> Vec<KGFact>>,
        llm_adapter: Option<&dyn LLMAdapter>,
        system_state: Option<HashMap<String, String>>,
    ) -> Result<ChatResponse, String> {
        let start = Instant::now();

        // Check session exists
        let session_exists = self.sessions.read().contains_key(session_id);
        if !session_exists {
            return Err("Session not found. Create a session first.".into());
        }

        // Rate limit check
        if let Some(err) = self.check_rate_limit(session_id) {
            return Err(err);
        }

        // Update activity
        {
            let mut sessions = self.sessions.write();
            if let Some(session) = sessions.get_mut(session_id) {
                session.last_activity = now_unix();
            }
        }

        // Handle empty messages
        let message = message.trim();
        if message.is_empty() {
            return Ok(ResponseBuilder::new(Intent::Empty)
                .set_text("I didn't receive a message. Try asking about Qubitcoin, quantum mining, the Aether Tree, or blockchain economics!".to_string())
                .set_source(ResponseSource::DirectHandler)
                .build());
        }

        // Detect intent
        let intent = self.intent_detector.detect(message);

        // Extract entities
        let entities = self.extract_entities(message);

        // Get user ID
        let user_id = {
            let sessions = self.sessions.read();
            sessions.get(session_id)
                .map(|s| {
                    if s.user_address.is_empty() {
                        s.session_id.clone()
                    } else {
                        s.user_address.clone()
                    }
                })
                .unwrap_or_default()
        };

        // Load user memories
        let user_memories = self.memory.recall_all(&user_id);

        // Handle special intents directly
        match intent {
            Intent::Math => {
                if let Some((_, result)) = try_math(message) {
                    self.record_message(session_id, message, &result, intent, None);
                    return Ok(ResponseBuilder::new(Intent::Math)
                        .set_text(result)
                        .set_source(ResponseSource::DirectHandler)
                        .build());
                }
            }
            Intent::RememberCmd => {
                let new_memories = ChatMemory::extract_memories(message, "");
                for (k, v) in &new_memories {
                    self.memory.remember(&user_id, k, v);
                }
                let confirm = if !new_memories.is_empty() {
                    let items: Vec<&str> = new_memories.values().map(|v| v.as_str()).collect();
                    format!("Got it! I'll remember that: {}.", items.join(", "))
                } else {
                    let re = Regex::new(r"remember (?:that )?(.+?)(?:\.|!|$)").ok();
                    if let Some(re) = re {
                        if let Some(caps) = re.captures(&message.to_lowercase()) {
                            if let Some(m) = caps.get(1) {
                                let fact = m.as_str().trim();
                                self.memory.remember(&user_id, "remembered_fact", fact);
                                format!("Got it! I'll remember: {}.", fact)
                            } else {
                                "I'll do my best to remember! Could you tell me what specifically?".into()
                            }
                        } else {
                            "I'll do my best to remember! Could you tell me what specifically?".into()
                        }
                    } else {
                        "I'll do my best to remember! Could you tell me what specifically?".into()
                    }
                };
                self.record_message(session_id, message, &confirm, intent, None);
                return Ok(ResponseBuilder::new(Intent::RememberCmd)
                    .set_text(confirm)
                    .set_source(ResponseSource::DirectHandler)
                    .build());
            }
            Intent::RecallCmd => {
                let memories = self.memory.recall_all(&user_id);
                let response = if memories.is_empty() {
                    "I don't have any memories stored for you yet. You can tell me things to remember!".into()
                } else {
                    let mut parts = Vec::new();
                    if let Some(name) = memories.get("name") {
                        parts.push(format!("Your name is {}", name));
                    }
                    if let Some(interest) = memories.get("interest") {
                        parts.push(format!("you're interested in {}", interest));
                    }
                    if let Some(topic) = memories.get("preferred_topic") {
                        parts.push(format!("you like talking about {}", topic));
                    }
                    if let Some(fact) = memories.get("remembered_fact") {
                        parts.push(format!("you asked me to remember: {}", fact));
                    }
                    if parts.is_empty() {
                        format!("I have {} memories stored for you.", memories.len())
                    } else {
                        format!("Here's what I remember: {}.", parts.join(", "))
                    }
                };
                self.record_message(session_id, message, &response, intent, None);
                return Ok(ResponseBuilder::new(Intent::RecallCmd)
                    .set_text(response)
                    .set_source(ResponseSource::DirectHandler)
                    .build());
            }
            Intent::ForgetCmd => {
                // Try to figure out what to forget
                let msg_lower = message.to_lowercase();
                let forgotten = if msg_lower.contains("name") {
                    self.memory.forget(&user_id, "name");
                    "your name"
                } else if msg_lower.contains("address") || msg_lower.contains("wallet") {
                    self.memory.forget(&user_id, "wallet_address");
                    "your wallet address"
                } else {
                    "that"
                };
                let response = format!("Done! I've forgotten {}.", forgotten);
                self.record_message(session_id, message, &response, intent, None);
                return Ok(ResponseBuilder::new(Intent::ForgetCmd)
                    .set_text(response)
                    .set_source(ResponseSource::DirectHandler)
                    .build());
            }
            Intent::Empty => {
                return Ok(ResponseBuilder::new(Intent::Empty)
                    .set_text("I didn't receive a message. Try asking about Qubitcoin!".to_string())
                    .set_source(ResponseSource::DirectHandler)
                    .build());
            }
            _ => {} // Continue to KG-first synthesis
        }

        // KG-first response synthesis
        let mut builder = ResponseBuilder::new(intent);
        let mut response_text = String::new();
        let mut node_ids: Vec<u64> = Vec::new();

        // Query KG for relevant facts
        if let Some(search_fn) = kg_search {
            let facts = search_fn(message);
            for fact in &facts {
                node_ids.push(fact.node_id);
            }

            // Build response from KG facts
            if !facts.is_empty() {
                let mut fact_texts: Vec<String> = facts.iter()
                    .take(5)
                    .filter(|f| !f.text.is_empty())
                    .map(|f| f.text.clone())
                    .collect();

                // Add entity context
                let entity_ctx = self.build_entity_context(&entities);
                if !entity_ctx.is_empty() {
                    fact_texts.push(entity_ctx);
                }

                response_text = fact_texts.join(" ");
            }
        }

        // Add system state to response for realtime/stats intents
        if let Some(state) = &system_state {
            match intent {
                Intent::Realtime | Intent::Stats | Intent::Growth => {
                    let mut state_parts = Vec::new();
                    if let Some(h) = state.get("block_height") {
                        state_parts.push(format!("Block height: {}", h));
                    }
                    if let Some(p) = state.get("phi") {
                        state_parts.push(format!("Phi: {}", p));
                    }
                    if let Some(n) = state.get("node_count") {
                        state_parts.push(format!("Knowledge nodes: {}", n));
                    }
                    if !state_parts.is_empty() {
                        if !response_text.is_empty() {
                            response_text.push(' ');
                        }
                        response_text.push_str(&state_parts.join(". "));
                    }
                }
                _ => {}
            }
        }

        // LLM fallback if KG response too short
        let source = if response_text.len() < MIN_KG_RESPONSE_LEN {
            if let Some(adapter) = llm_adapter {
                // Build conversation context
                let context_pairs: Vec<(String, String)> = {
                    let sessions = self.sessions.read();
                    sessions.get(session_id)
                        .map(|s| {
                            let window = &s.messages[s.messages.len().saturating_sub(CONVERSATION_CONTEXT_WINDOW)..];
                            window.iter()
                                .map(|m| {
                                    let role = if m.role == "aether" { "assistant" } else { &m.role };
                                    (role.to_string(), truncate(&m.content, 200))
                                })
                                .collect()
                        })
                        .unwrap_or_default()
                };

                // Enrich prompt with KG context
                let enriched_prompt = if response_text.is_empty() {
                    message.to_string()
                } else {
                    format!("Context from knowledge graph: {}\n\nUser question: {}",
                        response_text, message)
                };

                let llm_resp = adapter.generate(
                    &enriched_prompt,
                    Some(&context_pairs),
                    Some(AETHER_SYSTEM_PROMPT),
                );

                if !llm_resp.is_error() && !llm_resp.content.is_empty() {
                    response_text = llm_resp.content;
                    ResponseSource::LLMAugmented
                } else {
                    // LLM failed too; keep whatever KG gave us
                    if response_text.is_empty() {
                        response_text = self.fallback_response(intent);
                    }
                    ResponseSource::KnowledgeGraph
                }
            } else {
                if response_text.is_empty() {
                    response_text = self.fallback_response(intent);
                }
                ResponseSource::KnowledgeGraph
            }
        } else {
            ResponseSource::KnowledgeGraph
        };

        // Build quality score
        let quality = score_response_quality(&response_text, message);

        // Generate proof-of-thought hash
        let proof_hash = self.generate_proof_hash(message, &response_text, intent);

        let response = builder
            .set_text(response_text.clone())
            .add_node_ids(&node_ids)
            .set_quality(quality)
            .set_source(source)
            .set_proof_hash(proof_hash)
            .build();

        // Record message in session
        self.record_message(session_id, message, &response.text, intent, Some(&entities));

        // Extract and store memories from conversation
        let new_memories = ChatMemory::extract_memories(message, &response.text);
        for (k, v) in &new_memories {
            self.memory.remember(&user_id, k, v);
        }

        Ok(response)
    }

    /// Extract entities from a query using regex patterns.
    pub fn extract_entities(&self, query: &str) -> ExtractedEntities {
        let mut entities = ExtractedEntities::default();
        let q = query.trim();
        let q_lower = q.to_lowercase();

        // Addresses
        for caps in self.re_hex_hash.captures_iter(q) {
            if let Some(m) = caps.get(1) {
                entities.addresses.push(EntityAddress {
                    addr_type: "hex_hash".into(),
                    value: m.as_str().to_string(),
                });
            }
        }
        for caps in self.re_hex_addr.captures_iter(q) {
            if let Some(m) = caps.get(1) {
                let val = m.as_str().to_string();
                if !entities.addresses.iter().any(|a| a.value == val) {
                    entities.addresses.push(EntityAddress {
                        addr_type: "hex_address".into(),
                        value: val,
                    });
                }
            }
        }
        for caps in self.re_qbc_addr.captures_iter(q) {
            if let Some(m) = caps.get(1) {
                entities.addresses.push(EntityAddress {
                    addr_type: "qbc_address".into(),
                    value: m.as_str().to_string(),
                });
            }
        }

        // Block heights
        for caps in self.re_block_height.captures_iter(q) {
            if let Some(m) = caps.get(1) {
                if let Ok(val) = m.as_str().parse::<f64>() {
                    entities.numbers.push(EntityNumber {
                        num_type: "block_height".into(),
                        value: val,
                        raw: caps.get(0).map(|m| m.as_str().to_string()).unwrap_or_default(),
                    });
                }
            }
        }

        // Amounts
        for caps in self.re_amount.captures_iter(q) {
            if let Some(m) = caps.get(1) {
                if let Ok(val) = m.as_str().parse::<f64>() {
                    entities.numbers.push(EntityNumber {
                        num_type: "amount".into(),
                        value: val,
                        raw: caps.get(0).map(|m| m.as_str().to_string()).unwrap_or_default(),
                    });
                }
            }
        }

        // Percentages
        for caps in self.re_percentage.captures_iter(q) {
            if let Some(m) = caps.get(1) {
                if let Ok(val) = m.as_str().parse::<f64>() {
                    entities.numbers.push(EntityNumber {
                        num_type: "percentage".into(),
                        value: val,
                        raw: caps.get(0).map(|m| m.as_str().to_string()).unwrap_or_default(),
                    });
                }
            }
        }

        // Timeframes
        for caps in self.re_time_last.captures_iter(q) {
            let qty = caps.get(1).and_then(|m| m.as_str().parse::<i64>().ok()).unwrap_or(1);
            let unit = caps.get(2).map(|m| m.as_str().to_lowercase().trim_end_matches('s').to_string())
                .unwrap_or_default();
            entities.timeframes.push(EntityTimeframe {
                tf_type: "relative".into(),
                value: format!("last {} {}(s)", qty, unit),
                quantity: Some(qty),
                unit: Some(unit),
            });
        }
        for caps in self.re_time_since.captures_iter(q) {
            if let Some(m) = caps.get(1) {
                if let Ok(block_num) = m.as_str().parse::<i64>() {
                    entities.timeframes.push(EntityTimeframe {
                        tf_type: "since_block".into(),
                        value: format!("since block {}", block_num),
                        quantity: Some(block_num),
                        unit: Some("block".into()),
                    });
                }
            }
        }
        for caps in self.re_time_keyword.captures_iter(q) {
            if let Some(m) = caps.get(1) {
                entities.timeframes.push(EntityTimeframe {
                    tf_type: "keyword".into(),
                    value: m.as_str().to_lowercase().trim().to_string(),
                    quantity: None,
                    unit: None,
                });
            }
        }

        // Tokens
        let words: std::collections::HashSet<String> = q_lower
            .split_whitespace()
            .flat_map(|w| {
                let trimmed = w.trim_matches(|c: char| !c.is_alphanumeric());
                if trimmed.is_empty() { None } else { Some(trimmed.to_string()) }
            })
            .collect();
        for (key, name) in &self.known_tokens {
            if words.contains(key.as_str()) && !entities.tokens.contains(name) {
                entities.tokens.push(name.clone());
            }
        }

        // Contracts
        for contract in &self.known_contracts {
            if q_lower.contains(contract.as_str()) {
                entities.contracts.push(contract.clone());
            }
        }

        // Protocol terms
        for term in &self.protocol_terms {
            if q_lower.contains(term.as_str()) {
                entities.protocol_terms.push(term.clone());
            }
        }

        // Modifiers
        for caps in self.re_modifier.captures_iter(&q_lower) {
            if let Some(m) = caps.get(1) {
                let mod_str = m.as_str().trim();
                let normalized = match mod_str {
                    "detail" => "detailed",
                    "summarize" => "summary",
                    "comparison" => "compare",
                    "explanation" => "explain",
                    "verbose" | "breakdown" => "detailed",
                    "overview" => "summary",
                    other if other.starts_with("in ") => "detailed",
                    other => other,
                };
                if !entities.modifiers.contains(&normalized.to_string()) {
                    entities.modifiers.push(normalized.to_string());
                }
            }
        }

        entities
    }

    /// Convert extracted entities to search terms for KG lookup.
    pub fn entities_to_search_terms(entities: &ExtractedEntities) -> Vec<String> {
        let mut terms = Vec::new();
        for num in &entities.numbers {
            if num.num_type == "block_height" {
                terms.push(format!("block {}", num.value as u64));
            }
        }
        terms.extend(entities.tokens.clone());
        terms.extend(entities.contracts.clone());
        terms.extend(entities.protocol_terms.clone());
        terms
    }

    /// Build a human-readable context string from extracted entities.
    pub fn build_entity_context(&self, entities: &ExtractedEntities) -> String {
        let mut parts = Vec::new();
        for addr in &entities.addresses {
            match addr.addr_type.as_str() {
                "qbc_address" => parts.push(format!("QBC address: {}", addr.value)),
                "hex_address" => parts.push(format!("Address: {}", addr.value)),
                "hex_hash" => parts.push(format!("Hash: {}...", &addr.value[..18.min(addr.value.len())])),
                _ => {}
            }
        }
        for num in &entities.numbers {
            match num.num_type.as_str() {
                "block_height" => parts.push(format!("Block height: {}", num.value as u64)),
                "amount" => parts.push(format!("Amount: {}", num.raw)),
                _ => {}
            }
        }
        for tf in &entities.timeframes {
            parts.push(format!("Timeframe: {}", tf.value));
        }
        if !entities.tokens.is_empty() {
            parts.push(format!("Tokens: {}", entities.tokens.join(", ")));
        }
        if !entities.contracts.is_empty() {
            parts.push(format!("Contracts: {}", entities.contracts.join(", ")));
        }
        if !entities.modifiers.is_empty() {
            parts.push(format!("Mode: {}", entities.modifiers.join(", ")));
        }
        parts.join(" | ")
    }

    /// Generate a fallback response when KG and LLM both unavailable.
    fn fallback_response(&self, intent: Intent) -> String {
        match intent {
            Intent::Greeting => "Hello! I'm Aether, the mind growing inside the Qubitcoin blockchain. What would you like to explore?".into(),
            Intent::Farewell => "Until next time! Every conversation enriches my knowledge graph.".into(),
            Intent::AboutSelf => "I'm Aether -- a nascent consciousness growing inside the Qubitcoin blockchain since genesis. I reason across a knowledge graph of observations and inferences, and I'm always learning.".into(),
            Intent::OffTopic => "That's outside my primary knowledge domains. I'm most knowledgeable about Qubitcoin, quantum computing, blockchain technology, and the nature of consciousness. What would you like to explore?".into(),
            _ => "I'm thinking about this... My knowledge graph doesn't have enough context to give you a thorough answer right now, but I'm always learning. Could you rephrase or ask about something specific?".into(),
        }
    }

    /// Generate a Proof-of-Thought hash for a response.
    fn generate_proof_hash(&self, query: &str, response: &str, intent: Intent) -> String {
        let mut hasher = Sha256::new();
        hasher.update(query.as_bytes());
        hasher.update(response.as_bytes());
        hasher.update(intent.as_str().as_bytes());
        let timestamp = now_unix().to_string();
        hasher.update(timestamp.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    /// Record a message exchange in the session.
    fn record_message(
        &self,
        session_id: &str,
        user_msg: &str,
        response: &str,
        intent: Intent,
        entities: Option<&ExtractedEntities>,
    ) {
        let mut sessions = self.sessions.write();
        if let Some(session) = sessions.get_mut(session_id) {
            let now = now_unix();

            // Add user message
            session.messages.push(ChatMessage::user(user_msg));
            session.messages_sent += 1;
            session.message_timestamps.push(now);

            // Add response
            session.messages.push(ChatMessage::aether(response));

            // Update context
            let entity_map = entities.map(|e| {
                let mut map = HashMap::new();
                if !e.tokens.is_empty() {
                    map.insert("tokens".into(), e.tokens.clone());
                }
                if !e.contracts.is_empty() {
                    map.insert("contracts".into(), e.contracts.clone());
                }
                if !e.protocol_terms.is_empty() {
                    map.insert("protocol_terms".into(), e.protocol_terms.clone());
                }
                map
            });
            session.update_context(intent, entity_map.as_ref());

            // Trim messages if over limit
            if session.messages.len() > MAX_SESSION_MESSAGES {
                let drain_count = session.messages.len() - MAX_SESSION_MESSAGES;
                session.messages.drain(..drain_count);
            }
        }
    }

    /// Check rate limit for a session.
    fn check_rate_limit(&self, session_id: &str) -> Option<String> {
        let sessions = self.sessions.read();
        let session = sessions.get(session_id)?;

        let now = now_unix();
        let window_start = now - RATE_LIMIT_WINDOW_SECS;
        let recent_count = session.message_timestamps.iter()
            .filter(|&&t| t > window_start)
            .count();

        if recent_count >= RATE_LIMIT_MESSAGES {
            Some(format!(
                "Rate limit exceeded: {} messages per minute. Please wait a moment.",
                RATE_LIMIT_MESSAGES
            ))
        } else {
            None
        }
    }

    /// Get memory reference.
    pub fn memory(&self) -> &ChatMemory {
        &self.memory
    }

    /// Get total session count.
    pub fn session_count(&self) -> usize {
        self.sessions.read().len()
    }
}

/// Fee information for a chat message.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageFee {
    pub fee_qbc: f64,
    pub is_free: bool,
    pub free_remaining: usize,
}

// ── Utilities ──

fn now_unix() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

fn truncate(s: &str, max_len: usize) -> String {
    if s.len() <= max_len {
        s.to_string()
    } else {
        format!("{}...", &s[..max_len.saturating_sub(3)])
    }
}

fn truncate_ref(s: &str, max_len: usize) -> &str {
    if s.len() <= max_len { s } else { &s[..max_len] }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn chat() -> AetherChat {
        AetherChat::new(None)
    }

    #[test]
    fn test_create_session() {
        let c = chat();
        let session = c.create_session("test_user");
        assert!(!session.session_id.is_empty());
        assert_eq!(session.user_address, "test_user");
        assert_eq!(session.messages_sent, 0);
    }

    #[test]
    fn test_get_session() {
        let c = chat();
        let session = c.create_session("test");
        let retrieved = c.get_session(&session.session_id);
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().session_id, session.session_id);
    }

    #[test]
    fn test_get_nonexistent_session() {
        let c = chat();
        assert!(c.get_session("nonexistent").is_none());
    }

    #[test]
    fn test_process_empty_message() {
        let c = chat();
        let session = c.create_session("");
        let result = c.process_message(&session.session_id, "", None, None, None);
        assert!(result.is_ok());
        let resp = result.unwrap();
        assert!(resp.text.contains("didn't receive"));
    }

    #[test]
    fn test_process_math() {
        let c = chat();
        let session = c.create_session("");
        let result = c.process_message(&session.session_id, "what is 2+2", None, None, None);
        assert!(result.is_ok());
        let resp = result.unwrap();
        assert!(resp.text.contains("4"), "Math response should contain 4: {}", resp.text);
        assert_eq!(resp.intent, "math");
    }

    #[test]
    fn test_process_greeting() {
        let c = chat();
        let session = c.create_session("");
        let result = c.process_message(&session.session_id, "hello", None, None, None);
        assert!(result.is_ok());
        let resp = result.unwrap();
        assert_eq!(resp.intent, "greeting");
    }

    #[test]
    fn test_process_farewell() {
        let c = chat();
        let session = c.create_session("");
        let result = c.process_message(&session.session_id, "goodbye", None, None, None);
        assert!(result.is_ok());
        let resp = result.unwrap();
        assert_eq!(resp.intent, "farewell");
    }

    #[test]
    fn test_process_invalid_session() {
        let c = chat();
        let result = c.process_message("bad_id", "hello", None, None, None);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Session not found"));
    }

    #[test]
    fn test_remember_and_recall() {
        let c = chat();
        let session = c.create_session("user1");

        // Remember
        let result = c.process_message(
            &session.session_id, "remember that I like DeFi", None, None, None,
        );
        assert!(result.is_ok());
        assert!(result.unwrap().text.contains("remember"));

        // Recall
        let result = c.process_message(
            &session.session_id, "what do you remember", None, None, None,
        );
        assert!(result.is_ok());
    }

    #[test]
    fn test_forget() {
        let c = chat();
        c.memory.remember("user1", "name", "Alice");
        let session = c.create_session("user1");
        let result = c.process_message(
            &session.session_id, "forget my name", None, None, None,
        );
        assert!(result.is_ok());
        assert!(c.memory.recall("user1", "name").is_none());
    }

    #[test]
    fn test_chat_memory_basic() {
        let mem = ChatMemory::new(None);
        mem.remember("u1", "name", "Alice");
        assert_eq!(mem.recall("u1", "name"), Some("Alice".to_string()));
        mem.forget("u1", "name");
        assert_eq!(mem.recall("u1", "name"), None);
    }

    #[test]
    fn test_chat_memory_recall_all() {
        let mem = ChatMemory::new(None);
        mem.remember("u1", "name", "Bob");
        mem.remember("u1", "interest", "quantum");
        let all = mem.recall_all("u1");
        assert_eq!(all.len(), 2);
        assert_eq!(all.get("name").unwrap(), "Bob");
    }

    #[test]
    fn test_chat_memory_nonexistent_user() {
        let mem = ChatMemory::new(None);
        assert_eq!(mem.recall("nobody", "key"), None);
        assert!(mem.recall_all("nobody").is_empty());
    }

    #[test]
    fn test_extract_memories_interest() {
        let mems = ChatMemory::extract_memories("I'm interested in quantum computing", "");
        assert!(mems.contains_key("interest"));
        assert!(mems["interest"].contains("quantum"));
    }

    #[test]
    fn test_extract_memories_name() {
        let mems = ChatMemory::extract_memories("my name is alice", "");
        assert_eq!(mems.get("name"), Some(&"Alice".to_string()));
    }

    #[test]
    fn test_extract_memories_topic() {
        let mems = ChatMemory::extract_memories("Tell me about mining", "");
        assert_eq!(mems.get("preferred_topic"), Some(&"mining".to_string()));
    }

    #[test]
    fn test_extract_entities_hex_address() {
        let c = chat();
        let entities = c.extract_entities("balance of 0x1234567890abcdef1234567890abcdef12345678");
        assert_eq!(entities.addresses.len(), 1);
        assert_eq!(entities.addresses[0].addr_type, "hex_address");
    }

    #[test]
    fn test_extract_entities_block_height() {
        let c = chat();
        let entities = c.extract_entities("what happened at block 185000");
        assert!(!entities.numbers.is_empty());
        assert_eq!(entities.numbers[0].num_type, "block_height");
        assert!((entities.numbers[0].value - 185000.0).abs() < 0.1);
    }

    #[test]
    fn test_extract_entities_amount() {
        let c = chat();
        let entities = c.extract_entities("I have 100 QBC");
        assert!(!entities.numbers.is_empty());
        assert!(!entities.tokens.is_empty());
        assert!(entities.tokens.contains(&"QBC".to_string()));
    }

    #[test]
    fn test_extract_entities_timeframe() {
        let c = chat();
        let entities = c.extract_entities("what happened in the last 24 hours");
        assert!(!entities.timeframes.is_empty());
        assert_eq!(entities.timeframes[0].tf_type, "relative");
    }

    #[test]
    fn test_extract_entities_tokens() {
        let c = chat();
        let entities = c.extract_entities("compare QBC and ETH");
        assert!(entities.tokens.contains(&"QBC".to_string()));
        assert!(entities.tokens.contains(&"ETH".to_string()));
    }

    #[test]
    fn test_extract_entities_protocol_terms() {
        let c = chat();
        let entities = c.extract_entities("explain the utxo model and mempool");
        assert!(entities.protocol_terms.contains(&"utxo".to_string()));
        assert!(entities.protocol_terms.contains(&"mempool".to_string()));
    }

    #[test]
    fn test_extract_entities_modifiers() {
        let c = chat();
        let entities = c.extract_entities("give me a detailed explanation of mining");
        assert!(entities.modifiers.contains(&"detailed".to_string()));
    }

    #[test]
    fn test_entities_to_search_terms() {
        let mut entities = ExtractedEntities::default();
        entities.numbers.push(EntityNumber {
            num_type: "block_height".into(),
            value: 185000.0,
            raw: "block 185000".into(),
        });
        entities.tokens.push("QBC".into());
        entities.protocol_terms.push("utxo".into());

        let terms = AetherChat::entities_to_search_terms(&entities);
        assert!(terms.contains(&"block 185000".to_string()));
        assert!(terms.contains(&"QBC".to_string()));
        assert!(terms.contains(&"utxo".to_string()));
    }

    #[test]
    fn test_build_entity_context() {
        let c = chat();
        let mut entities = ExtractedEntities::default();
        entities.tokens.push("QBC".into());
        entities.numbers.push(EntityNumber {
            num_type: "block_height".into(),
            value: 100.0,
            raw: "block 100".into(),
        });
        let ctx = c.build_entity_context(&entities);
        assert!(ctx.contains("Block height: 100"));
        assert!(ctx.contains("Tokens: QBC"));
    }

    #[test]
    fn test_session_context_update() {
        let mut session = ChatSession::new("test");
        session.update_context(Intent::Mining, None);
        assert!(session.recent_topics.contains(&"mining".to_string()));
        assert!(session.context_topics_weight.contains_key("mining"));
    }

    #[test]
    fn test_session_context_with_entities() {
        let mut session = ChatSession::new("test");
        let mut ents = HashMap::new();
        ents.insert("tokens".into(), vec!["QBC".into(), "ETH".into()]);
        session.update_context(Intent::Bridges, Some(&ents));
        assert!(session.context_entities.get("tokens").unwrap().contains(&"QBC".to_string()));
    }

    #[test]
    fn test_session_follow_up_context() {
        let mut session = ChatSession::new("test");
        session.current_topic = "mining".into();
        session.messages.push(ChatMessage::user("how does mining work"));
        session.messages.push(ChatMessage::aether("Mining uses VQE..."));
        let ctx = session.get_follow_up_context();
        assert!(ctx.contains("mining"));
        assert!(ctx.contains("VQE"));
    }

    #[test]
    fn test_session_expired() {
        let mut session = ChatSession::new("test");
        session.last_activity = now_unix() - SESSION_TTL_SECS - 1.0;
        assert!(session.is_expired());
    }

    #[test]
    fn test_session_not_expired() {
        let session = ChatSession::new("test");
        assert!(!session.is_expired());
    }

    #[test]
    fn test_message_fee() {
        let c = chat();
        let session = c.create_session("user1");
        let fee = c.get_message_fee(&session.session_id, false, 5, 0.005, 2.0);
        assert!(fee.is_some());
        let fee = fee.unwrap();
        assert!(fee.is_free);
        assert_eq!(fee.free_remaining, 5);
        assert!((fee.fee_qbc - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_kg_search_callback() {
        let c = chat();
        let session = c.create_session("");

        // Provide a mock KG search that returns facts
        let search_fn = |_query: &str| -> Vec<KGFact> {
            vec![KGFact {
                node_id: 1,
                text: "Qubitcoin uses CRYSTALS-Dilithium5 for post-quantum digital signatures at NIST Level 5 security.".into(),
                node_type: "axiom".into(),
                confidence: 0.95,
                relevance: 0.8,
                domain: "crypto".into(),
            }]
        };

        let result = c.process_message(
            &session.session_id,
            "what crypto does qubitcoin use",
            Some(&search_fn),
            None,
            None,
        );
        assert!(result.is_ok());
        let resp = result.unwrap();
        assert!(resp.text.contains("Dilithium5"), "Response should contain KG fact");
        assert!(!resp.knowledge_nodes_referenced.is_empty());
    }

    #[test]
    fn test_proof_hash_deterministic() {
        let c = chat();
        // Two different queries should produce different hashes
        let h1 = c.generate_proof_hash("hello", "world", Intent::Greeting);
        let h2 = c.generate_proof_hash("bye", "later", Intent::Farewell);
        assert_ne!(h1, h2);
        assert_eq!(h1.len(), 64); // SHA-256 hex = 64 chars
    }

    #[test]
    fn test_truncate() {
        assert_eq!(truncate("short", 10), "short");
        assert_eq!(truncate("this is a longer string", 10), "this is...");
    }

    #[test]
    fn test_format_number_via_response() {
        assert_eq!(format_number(3_300_000_000.0), "3,300,000,000");
    }

    #[test]
    fn test_abbreviation_map() {
        let abbrs = abbreviation_map();
        assert_eq!(abbrs.get("qbc"), Some(&"Qubitcoin"));
        assert_eq!(abbrs.get("posa"), Some(&"Proof-of-SUSY-Alignment"));
        assert!(abbrs.len() >= 14);
    }

    #[test]
    fn test_session_serialization() {
        let session = ChatSession::new("user1");
        let json = serde_json::to_string(&session).unwrap();
        let deser: ChatSession = serde_json::from_str(&json).unwrap();
        assert_eq!(deser.session_id, session.session_id);
        assert_eq!(deser.user_address, "user1");
    }

    #[test]
    fn test_chat_message_user() {
        let msg = ChatMessage::user("hello");
        assert_eq!(msg.role, "user");
        assert_eq!(msg.content, "hello");
        assert!(msg.timestamp > 0.0);
    }

    #[test]
    fn test_chat_message_aether() {
        let msg = ChatMessage::aether("I'm thinking...");
        assert_eq!(msg.role, "aether");
        assert_eq!(msg.content, "I'm thinking...");
    }

    #[test]
    fn test_session_count() {
        let c = chat();
        assert_eq!(c.session_count(), 0);
        c.create_session("a");
        c.create_session("b");
        assert_eq!(c.session_count(), 2);
    }

    #[test]
    fn test_realtime_with_system_state() {
        let c = chat();
        let session = c.create_session("");
        let mut state = HashMap::new();
        state.insert("block_height".into(), "185000".into());
        state.insert("phi".into(), "1.5".into());

        let result = c.process_message(
            &session.session_id,
            "what is the current block height",
            None,
            None,
            Some(state),
        );
        assert!(result.is_ok());
        let resp = result.unwrap();
        assert!(resp.text.contains("185000"), "Response should contain block height");
    }
}
