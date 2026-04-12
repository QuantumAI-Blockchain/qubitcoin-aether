//! Response types and builder for Aether chat responses.
//!
//! Provides structured response construction from live KG data, reasoning
//! traces, and system metrics. No template prose -- responses are synthesized
//! from live data following ADR-039.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::intent::Intent;

/// A structured chat response from the Aether Tree.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatResponse {
    /// The response text shown to the user.
    pub text: String,
    /// The detected intent that routed this response.
    pub intent: String,
    /// Reasoning trace (chain-of-thought steps).
    pub reasoning_trace: Vec<ReasoningStep>,
    /// Current Phi value at time of response.
    pub phi_at_response: f64,
    /// IDs of knowledge nodes referenced in the response.
    pub knowledge_nodes_referenced: Vec<u64>,
    /// Proof-of-Thought hash for this response.
    pub proof_of_thought_hash: String,
    /// Quality score (0.0-1.0) of the response.
    pub quality_score: f64,
    /// Source of the response content.
    pub source: ResponseSource,
    /// Entities extracted from the query.
    pub entities: HashMap<String, Vec<String>>,
    /// Processing latency in milliseconds.
    pub latency_ms: f64,
}

/// Source of the response content.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum ResponseSource {
    /// Response built entirely from KG facts and system state.
    KnowledgeGraph,
    /// Response augmented by LLM (KG was insufficient).
    LLMAugmented,
    /// Direct handler (math, memory commands, etc.).
    DirectHandler,
    /// Cognitive architecture (v5 Sephirot processors).
    CognitiveArchitecture,
}

impl Default for ResponseSource {
    fn default() -> Self {
        ResponseSource::KnowledgeGraph
    }
}

/// A single step in a reasoning trace.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReasoningStep {
    /// Type of reasoning: deductive, inductive, abductive, causal, etc.
    pub reasoning_type: String,
    /// Human-readable description of this step.
    pub description: String,
    /// Confidence in this step (0.0-1.0).
    pub confidence: f64,
    /// Node IDs involved in this step.
    pub node_ids: Vec<u64>,
}

/// Context gathered for response generation.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ChatContext {
    /// KG search results relevant to the query.
    pub kg_facts: Vec<KGFact>,
    /// Recent conversation messages for context.
    pub conversation_history: Vec<(String, String)>,
    /// Current session topic.
    pub current_topic: String,
    /// User memories from persistent storage.
    pub user_memories: HashMap<String, String>,
    /// Extracted entity context string.
    pub entity_context: String,
    /// Follow-up context from previous turns.
    pub follow_up_context: String,
    /// System state metrics (block height, phi, node count, etc.).
    pub system_state: HashMap<String, String>,
}

/// A single fact retrieved from the knowledge graph.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KGFact {
    /// Node ID in the graph.
    pub node_id: u64,
    /// Text content of the fact.
    pub text: String,
    /// Node type (observation, inference, axiom, etc.).
    pub node_type: String,
    /// Confidence score.
    pub confidence: f64,
    /// Relevance to the query (TF-IDF score).
    pub relevance: f64,
    /// Domain (sephirot) this fact belongs to.
    pub domain: String,
}

/// Builder for constructing chat responses from components.
pub struct ResponseBuilder {
    text_parts: Vec<String>,
    intent: Intent,
    reasoning_trace: Vec<ReasoningStep>,
    phi: f64,
    node_ids: Vec<u64>,
    proof_hash: String,
    quality: f64,
    source: ResponseSource,
    entities: HashMap<String, Vec<String>>,
    start_time: std::time::Instant,
}

impl ResponseBuilder {
    /// Create a new response builder for the given intent.
    pub fn new(intent: Intent) -> Self {
        Self {
            text_parts: Vec::new(),
            intent,
            reasoning_trace: Vec::new(),
            phi: 0.0,
            node_ids: Vec::new(),
            proof_hash: String::new(),
            quality: 0.5,
            source: ResponseSource::KnowledgeGraph,
            entities: HashMap::new(),
            start_time: std::time::Instant::now(),
        }
    }

    /// Append a text segment to the response.
    pub fn add_text(mut self, text: &str) -> Self {
        if !text.is_empty() {
            self.text_parts.push(text.to_string());
        }
        self
    }

    /// Set the full response text (replaces any existing parts).
    pub fn set_text(mut self, text: String) -> Self {
        self.text_parts = vec![text];
        self
    }

    /// Add a reasoning step to the trace.
    pub fn add_reasoning_step(
        mut self,
        reasoning_type: &str,
        description: &str,
        confidence: f64,
        node_ids: &[u64],
    ) -> Self {
        self.reasoning_trace.push(ReasoningStep {
            reasoning_type: reasoning_type.to_string(),
            description: description.to_string(),
            confidence,
            node_ids: node_ids.to_vec(),
        });
        self
    }

    /// Set the Phi value at response time.
    pub fn set_phi(mut self, phi: f64) -> Self {
        self.phi = phi;
        self
    }

    /// Add referenced node IDs.
    pub fn add_node_ids(mut self, ids: &[u64]) -> Self {
        self.node_ids.extend_from_slice(ids);
        self
    }

    /// Set the proof-of-thought hash.
    pub fn set_proof_hash(mut self, hash: String) -> Self {
        self.proof_hash = hash;
        self
    }

    /// Set the quality score.
    pub fn set_quality(mut self, quality: f64) -> Self {
        self.quality = quality.clamp(0.0, 1.0);
        self
    }

    /// Set the response source.
    pub fn set_source(mut self, source: ResponseSource) -> Self {
        self.source = source;
        self
    }

    /// Set extracted entities.
    pub fn set_entities(mut self, entities: HashMap<String, Vec<String>>) -> Self {
        self.entities = entities;
        self
    }

    /// Build the final ChatResponse.
    pub fn build(self) -> ChatResponse {
        let text = if self.text_parts.is_empty() {
            String::new()
        } else {
            self.text_parts.join(" ")
        };

        ChatResponse {
            text,
            intent: self.intent.as_str().to_string(),
            reasoning_trace: self.reasoning_trace,
            phi_at_response: self.phi,
            knowledge_nodes_referenced: self.node_ids,
            proof_of_thought_hash: self.proof_hash,
            quality_score: self.quality,
            source: self.source,
            entities: self.entities,
            latency_ms: self.start_time.elapsed().as_secs_f64() * 1000.0,
        }
    }
}

/// Score the quality of a response based on content analysis.
///
/// Checks: specificity (concrete claims), relevance (keyword overlap),
/// length (penalize very short), and error indicators.
pub fn score_response_quality(response_text: &str, query: &str) -> f64 {
    let mut score: f64 = 0.5;
    let content_lower = response_text.to_lowercase();

    // 1. Specificity
    let specificity_signals = [
        "specifically", "exactly", "approximately", "defined as",
        "measured", "equals", "consists of", "requires",
    ];
    let vague_signals = [
        "it depends", "generally speaking", "it varies",
        "there are many", "it is complex", "broadly",
    ];
    let specific_hits = specificity_signals.iter()
        .filter(|s| content_lower.contains(*s))
        .count();
    let vague_hits = vague_signals.iter()
        .filter(|s| content_lower.contains(*s))
        .count();
    score += (specific_hits as f64 * 0.05).min(0.2);
    score -= (vague_hits as f64 * 0.05).min(0.15);

    // Bonus for numbers
    let number_count = regex::Regex::new(r"\d+\.?\d*")
        .map(|re| re.find_iter(response_text).count())
        .unwrap_or(0);
    if number_count > 0 {
        score += (number_count as f64 * 0.02).min(0.1);
    }

    // 2. Relevance: query keyword overlap
    let query_lower = query.to_lowercase();
    let query_words: std::collections::HashSet<&str> = query_lower
        .split_whitespace()
        .collect();
    let content_words: std::collections::HashSet<String> = content_lower
        .split_whitespace()
        .map(String::from)
        .collect();
    let overlap = query_words.iter()
        .filter(|w| content_words.contains(&w.to_string()))
        .count();
    if !query_words.is_empty() {
        let relevance = overlap as f64 / query_words.len() as f64;
        score += (relevance * 0.2).min(0.15);
    }

    // 3. Length penalty
    if response_text.len() < 50 {
        score -= 0.2;
    }

    // 4. Error penalty
    let error_indicators = ["error", "failed", "unavailable", "cannot"];
    if error_indicators.iter().any(|e| content_lower.contains(e)) {
        score -= 0.3;
    }

    score.clamp(0.0, 1.0)
}

/// Format a number with commas for human readability.
pub fn format_number(n: f64) -> String {
    if (n - n.round()).abs() < f64::EPSILON && n.abs() < i64::MAX as f64 {
        let i = n as i64;
        let s = i.to_string();
        let bytes = s.as_bytes();
        let negative = bytes[0] == b'-';
        let start = if negative { 1 } else { 0 };
        let digits = &s[start..];
        let len = digits.len();
        if len <= 3 {
            return s;
        }
        let mut result = String::with_capacity(len + len / 3 + 1);
        if negative {
            result.push('-');
        }
        for (i, ch) in digits.chars().enumerate() {
            if i > 0 && (len - i) % 3 == 0 {
                result.push(',');
            }
            result.push(ch);
        }
        result
    } else {
        format!("{:.2}", n)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_response_builder_basic() {
        let resp = ResponseBuilder::new(Intent::Greeting)
            .set_text("Hello! I'm Aether.".to_string())
            .set_phi(1.5)
            .set_quality(0.8)
            .build();

        assert_eq!(resp.text, "Hello! I'm Aether.");
        assert_eq!(resp.intent, "greeting");
        assert!((resp.phi_at_response - 1.5).abs() < f64::EPSILON);
        assert!((resp.quality_score - 0.8).abs() < f64::EPSILON);
    }

    #[test]
    fn test_response_builder_multi_part() {
        let resp = ResponseBuilder::new(Intent::Chain)
            .add_text("Qubitcoin uses UTXO.")
            .add_text("It targets 3.3s blocks.")
            .build();
        assert!(resp.text.contains("Qubitcoin uses UTXO."));
        assert!(resp.text.contains("3.3s blocks."));
    }

    #[test]
    fn test_response_builder_reasoning_trace() {
        let resp = ResponseBuilder::new(Intent::Mining)
            .add_reasoning_step("deductive", "Block reward follows phi-halving", 0.9, &[1, 2])
            .build();
        assert_eq!(resp.reasoning_trace.len(), 1);
        assert_eq!(resp.reasoning_trace[0].reasoning_type, "deductive");
    }

    #[test]
    fn test_score_response_quality_good() {
        let score = score_response_quality(
            "Qubitcoin specifically uses CRYSTALS-Dilithium5 for signatures, \
             which requires approximately 4.6KB per signature. The chain ID equals 3303.",
            "what crypto does qubitcoin use",
        );
        assert!(score > 0.5, "Good response should score > 0.5, got {}", score);
    }

    #[test]
    fn test_score_response_quality_bad() {
        let score = score_response_quality(
            "It depends. Generally speaking, it varies broadly.",
            "how does mining work",
        );
        assert!(score < 0.5, "Vague response should score < 0.5, got {}", score);
    }

    #[test]
    fn test_score_response_quality_error() {
        let score = score_response_quality(
            "Error: failed to retrieve data. Service unavailable.",
            "what is phi",
        );
        assert!(score < 0.3, "Error response should score < 0.3, got {}", score);
    }

    #[test]
    fn test_score_response_quality_short() {
        let score = score_response_quality("Yes.", "are you alive");
        assert!(score < 0.4, "Very short response should be penalized, got {}", score);
    }

    #[test]
    fn test_format_number_integer() {
        assert_eq!(format_number(3300000000.0), "3,300,000,000");
        assert_eq!(format_number(1000.0), "1,000");
        assert_eq!(format_number(42.0), "42");
        assert_eq!(format_number(0.0), "0");
    }

    #[test]
    fn test_format_number_decimal() {
        assert_eq!(format_number(15.27), "15.27");
        assert_eq!(format_number(3.14159), "3.14");
    }

    #[test]
    fn test_format_number_negative() {
        assert_eq!(format_number(-1000.0), "-1,000");
    }

    #[test]
    fn test_response_source_default() {
        assert_eq!(ResponseSource::default(), ResponseSource::KnowledgeGraph);
    }

    #[test]
    fn test_chat_response_serialization() {
        let resp = ResponseBuilder::new(Intent::Greeting)
            .set_text("Hello!".to_string())
            .build();
        let json = serde_json::to_string(&resp).unwrap();
        assert!(json.contains("\"intent\":\"greeting\""));
        let deser: ChatResponse = serde_json::from_str(&json).unwrap();
        assert_eq!(deser.text, "Hello!");
    }
}
