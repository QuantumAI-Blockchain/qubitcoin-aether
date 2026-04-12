//! Sephirot Cognitive Node Processors
//!
//! Implements the 10 Tree of Life cognitive processors — the actual reasoning
//! logic for each Sephirah node. Ported from `sephirot_nodes.py`.
//!
//! Each processor has domain-specific `process()` and `specialized_reason()`
//! methods, plus shared infrastructure for messaging, serialization, and
//! energy-quality calculations.

use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::csf_transport::SephirahRole;

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

/// Message passed between Sephirot nodes via CSF transport.
#[derive(Debug, Clone)]
pub struct NodeMessage {
    pub sender: SephirahRole,
    pub receiver: SephirahRole,
    pub payload: HashMap<String, serde_json::Value>,
    pub priority: f64,
    pub timestamp: f64,
    pub message_id: String,
}

impl NodeMessage {
    pub fn new(
        sender: SephirahRole,
        receiver: SephirahRole,
        payload: HashMap<String, serde_json::Value>,
        priority: f64,
    ) -> Self {
        let ts = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();
        let raw = format!("{}:{}:{}", sender.value(), receiver.value(), ts);
        let hash = Sha256::digest(raw.as_bytes());
        let id = hex::encode(&hash[..8]); // 16 hex chars
        Self {
            sender,
            receiver,
            payload,
            priority,
            timestamp: ts,
            message_id: id,
        }
    }
}

/// Result from a Sephirah's main processing step.
#[derive(Debug, Clone)]
pub struct ProcessingResult {
    pub role: SephirahRole,
    pub action: String,
    pub output: HashMap<String, serde_json::Value>,
    pub confidence: f64,
    pub messages_out: Vec<NodeMessage>,
    pub success: bool,
}

/// Context for the main `process()` call.
#[derive(Debug, Clone)]
pub struct ProcessingContext {
    pub block_height: u64,
    pub data: HashMap<String, serde_json::Value>,
}

impl ProcessingContext {
    pub fn new(block_height: u64) -> Self {
        Self {
            block_height,
            data: HashMap::new(),
        }
    }

    /// Convenience: get a string value from the context data.
    pub fn get_str(&self, key: &str) -> &str {
        self.data
            .get(key)
            .and_then(|v| v.as_str())
            .unwrap_or("")
    }

    /// Convenience: get an f64 from the context data.
    pub fn get_f64(&self, key: &str) -> f64 {
        self.data
            .get(key)
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0)
    }
}

/// Context for `specialized_reason()`.
#[derive(Debug, Clone)]
pub struct ReasoningContext {
    pub query: String,
    pub knowledge_nodes: Vec<serde_json::Value>,
    pub recent_reasoning: Vec<serde_json::Value>,
    pub energy: f64,
}

impl Default for ReasoningContext {
    fn default() -> Self {
        Self {
            query: String::new(),
            knowledge_nodes: Vec::new(),
            recent_reasoning: Vec::new(),
            energy: 1.0,
        }
    }
}

/// Result from `specialized_reason()`.
#[derive(Debug, Clone)]
pub struct ReasoningResult {
    pub result: String,
    pub confidence: f64,
    pub reasoning_type: String,
    pub steps: Vec<String>,
}

// ---------------------------------------------------------------------------
// Base state shared by all processors
// ---------------------------------------------------------------------------

/// Common mutable state held by every processor.
#[derive(Debug, Clone)]
pub struct BaseState {
    pub inbox: Vec<NodeMessage>,
    pub outbox: Vec<NodeMessage>,
    pub processing_count: u64,
    pub tasks_solved: u64,
    pub knowledge_contributed: u64,
    pub errors: u64,
}

impl Default for BaseState {
    fn default() -> Self {
        Self {
            inbox: Vec::new(),
            outbox: Vec::new(),
            processing_count: 0,
            tasks_solved: 0,
            knowledge_contributed: 0,
            errors: 0,
        }
    }
}

impl BaseState {
    fn consume_inbox(&mut self) -> Vec<NodeMessage> {
        std::mem::take(&mut self.inbox)
    }
}

// ---------------------------------------------------------------------------
// Trait
// ---------------------------------------------------------------------------

/// Core trait for all 10 Sephirot cognitive processors.
pub trait SephirahProcessor: Send {
    /// Which Sephirah this processor implements.
    fn role(&self) -> SephirahRole;

    /// Main per-block processing step.
    fn process(&mut self, context: &ProcessingContext) -> ProcessingResult;

    /// Domain-specific reasoning for a query.
    fn specialized_reason(&self, context: &ReasoningContext) -> ReasoningResult;

    /// Receive a message from another Sephirah.
    fn receive_message(&mut self, msg: NodeMessage);

    /// Drain and return all pending outgoing messages.
    fn drain_outbox(&mut self) -> Vec<NodeMessage>;

    /// Status snapshot for dashboards / API.
    fn get_status(&self) -> HashMap<String, serde_json::Value>;

    /// Serialize processor state for persistence.
    fn serialize_state(&self) -> serde_json::Value;

    /// Restore processor state from persisted data.
    fn deserialize_state(&mut self, data: &serde_json::Value);

    /// Energy quality factor with Higgs mass dampening.
    ///
    /// Sigmoid: `0.1 + 0.9*(1 - e^(-2*energy))`, dampened by cognitive mass.
    fn energy_quality_factor(&self, energy: f64, cognitive_mass: f64) -> f64 {
        let e = energy.max(0.0);
        let base = 0.1 + 0.9 * (1.0 - (-2.0 * e).exp());
        if cognitive_mass > 0.0 {
            let dampen = 1.0 / (1.0 + cognitive_mass / 500.0);
            base * (0.5 + 0.5 * dampen)
        } else {
            base
        }
    }

    /// Performance weight for reward distribution.
    fn get_performance_weight(&self) -> f64 {
        // Default: subclasses expose base_state() for the real calculation
        1.0
    }
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

/// Queue a message in the given outbox.
pub fn send_message(
    outbox: &mut Vec<NodeMessage>,
    sender: SephirahRole,
    receiver: SephirahRole,
    payload: HashMap<String, serde_json::Value>,
    priority: f64,
) {
    outbox.push(NodeMessage::new(sender, receiver, payload, priority));
}

/// Shorthand to build a payload map from key-value pairs.
macro_rules! payload {
    ($($k:expr => $v:expr),* $(,)?) => {{
        let mut m = HashMap::new();
        $( m.insert($k.to_string(), serde_json::json!($v)); )*
        m
    }};
}

// ---------------------------------------------------------------------------
// Shared trait-method implementations via a macro
// ---------------------------------------------------------------------------

macro_rules! impl_common {
    ($ty:ty, $role:expr) => {
        fn role(&self) -> SephirahRole {
            $role
        }

        fn receive_message(&mut self, msg: NodeMessage) {
            self.base.inbox.push(msg);
        }

        fn drain_outbox(&mut self) -> Vec<NodeMessage> {
            std::mem::take(&mut self.base.outbox)
        }

        fn get_status(&self) -> HashMap<String, serde_json::Value> {
            let mut m = HashMap::new();
            m.insert("role".into(), serde_json::json!($role.value()));
            m.insert("processing_count".into(), serde_json::json!(self.base.processing_count));
            m.insert("tasks_solved".into(), serde_json::json!(self.base.tasks_solved));
            m.insert("knowledge_contributed".into(), serde_json::json!(self.base.knowledge_contributed));
            m.insert("errors".into(), serde_json::json!(self.base.errors));
            m.insert("inbox_size".into(), serde_json::json!(self.base.inbox.len()));
            m.insert("outbox_size".into(), serde_json::json!(self.base.outbox.len()));
            m
        }

        fn get_performance_weight(&self) -> f64 {
            let base_w = (self.base.tasks_solved as f64 * 0.5
                + self.base.knowledge_contributed as f64 * 0.3
                + self.base.processing_count as f64 * 0.2)
                .max(1.0);
            base_w
        }
    };
}

// Energy quality helper used inside processor methods.
fn qf(energy: f64) -> f64 {
    let e = energy.max(0.0);
    0.1 + 0.9 * (1.0 - (-2.0 * e).exp())
}

// ---------------------------------------------------------------------------
// 1. Keter — Meta-learning and goal formation
// ---------------------------------------------------------------------------

pub struct KeterProcessor {
    pub base: BaseState,
    pub goals: Vec<serde_json::Value>,
    pub meta_patterns: Vec<serde_json::Value>,
    pub stagnation_counter: u32,
}

impl KeterProcessor {
    pub fn new() -> Self {
        Self {
            base: BaseState::default(),
            goals: Vec::new(),
            meta_patterns: Vec::new(),
            stagnation_counter: 0,
        }
    }
}

impl SephirahProcessor for KeterProcessor {
    impl_common!(KeterProcessor, SephirahRole::Keter);

    fn process(&mut self, context: &ProcessingContext) -> ProcessingResult {
        self.base.processing_count += 1;
        let messages = self.base.consume_inbox();

        // Aggregate reports (especially from Malkuth)
        let reports: Vec<_> = messages
            .iter()
            .filter(|m| m.payload.get("type").and_then(|v| v.as_str()) == Some("report"))
            .collect();

        // Track stagnation via Malkuth KG mutation stats
        let kg_mutations = context.get_f64("kg_mutations") as u64;
        if kg_mutations == 0 && self.base.processing_count > 5 {
            self.stagnation_counter += 1;
        } else {
            self.stagnation_counter = 0;
        }

        // Detect meta-patterns from reports
        if reports.len() >= 3 {
            self.meta_patterns.push(serde_json::json!({
                "type": "meta_pattern",
                "source_count": reports.len(),
                "block_height": context.block_height,
            }));
            if self.meta_patterns.len() > 100 {
                let start = self.meta_patterns.len() - 100;
                self.meta_patterns = self.meta_patterns[start..].to_vec();
            }
        }

        // Determine priority from metacognition or stagnation
        let recommended_strategy = context.get_str("recommended_strategy").to_string();
        let mut priority = match recommended_strategy.as_str() {
            "inductive" => "explore",
            "deductive" => "verify",
            "abductive" => "hypothesize",
            "neural" => "pattern_match",
            _ => "normal",
        };
        if self.stagnation_counter >= 3 {
            priority = "explore";
        }

        let goal = serde_json::json!({
            "type": "goal",
            "priority": priority,
            "block_height": context.block_height,
            "recommended_strategy": recommended_strategy,
        });
        self.goals.push(goal);
        if self.goals.len() > 50 {
            let start = self.goals.len() - 50;
            self.goals = self.goals[start..].to_vec();
        }

        // Broadcast to Tiferet and Chochmah
        send_message(
            &mut self.base.outbox,
            SephirahRole::Keter,
            SephirahRole::Tiferet,
            payload!("type" => "goal_directive", "priority" => priority),
            1.0,
        );
        send_message(
            &mut self.base.outbox,
            SephirahRole::Keter,
            SephirahRole::Chochmah,
            payload!("type" => "strategy_directive", "strategy" => &recommended_strategy, "priority" => priority),
            1.0,
        );

        ProcessingResult {
            role: SephirahRole::Keter,
            action: "goal_formation".into(),
            output: payload!(
                "goals" => self.goals.len(),
                "meta_patterns" => self.meta_patterns.len(),
                "priority" => priority,
                "recommended_strategy" => &recommended_strategy
            ),
            confidence: 0.85,
            messages_out: self.drain_outbox(),
            success: true,
        }
    }

    fn specialized_reason(&self, context: &ReasoningContext) -> ReasoningResult {
        let energy_qf = qf(context.energy);
        let mut steps = vec![format!("Energy quality factor: {:.2}", energy_qf)];

        let mut strategies: HashMap<&str, f64> = HashMap::new();
        for s in &["deductive", "inductive", "abductive", "neural", "exploratory"] {
            strategies.insert(s, 0.0);
        }

        // Score from recent reasoning history
        if !context.recent_reasoning.is_empty() {
            let max_recent = (context.recent_reasoning.len() as f64 * energy_qf).ceil() as usize;
            let max_recent = max_recent.max(3).min(context.recent_reasoning.len());
            let start = context.recent_reasoning.len().saturating_sub(max_recent);
            for op in &context.recent_reasoning[start..] {
                let stype = op
                    .get("type")
                    .or_else(|| op.get("reasoning_type"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                let success = op
                    .get("success")
                    .or_else(|| op.get("confidence"))
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.5);
                if let Some(score) = strategies.get_mut(stype) {
                    *score += success;
                }
            }
            steps.push(format!("Analyzed {} recent operations", max_recent));
        } else {
            for v in strategies.values_mut() {
                *v = 0.5;
            }
            steps.push("No recent reasoning history; defaulting to balanced scores".into());
        }

        // Keyword boosts
        let ql = context.query.to_lowercase();
        let boosts: &[(&[&str], &str, &str)] = &[
            (&["prove", "verify", "implies", "therefore"], "deductive", "deductive"),
            (&["pattern", "trend", "often", "usually"], "inductive", "inductive"),
            (&["why", "explain", "cause", "because"], "abductive", "abductive"),
            (&["predict", "estimate", "similar"], "neural", "neural"),
            (&["explore", "novel", "creative", "new"], "exploratory", "exploratory"),
        ];
        for (kws, key, label) in boosts {
            if kws.iter().any(|kw| ql.contains(kw)) {
                if let Some(s) = strategies.get_mut(key) {
                    *s += energy_qf;
                }
                steps.push(format!("Query contains {} keywords -> boosting {}", label, label));
            }
        }

        // KG density boost
        if context.knowledge_nodes.len() > 50 {
            *strategies.get_mut("neural").unwrap() += 0.5 * energy_qf;
            steps.push("Dense knowledge graph -> boosting neural".into());
        } else if context.knowledge_nodes.len() < 10 {
            *strategies.get_mut("exploratory").unwrap() += 0.5 * energy_qf;
            steps.push("Sparse knowledge graph -> boosting exploration".into());
        }

        let (best, best_score) = strategies
            .iter()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .map(|(k, v)| (*k, *v))
            .unwrap_or(("deductive", 0.0));
        let total: f64 = strategies.values().sum::<f64>().max(1.0);
        let confidence = ((best_score / total) * energy_qf).min(1.0);

        steps.push(format!(
            "Selected strategy: {} (score={:.2}, total={:.2})",
            best, best_score, total
        ));

        ReasoningResult {
            result: format!("Recommended strategy: {}", best),
            confidence: (confidence * 10000.0).round() / 10000.0,
            reasoning_type: "meta_reasoning".into(),
            steps,
        }
    }

    fn serialize_state(&self) -> serde_json::Value {
        serde_json::json!({
            "role": "keter",
            "processing_count": self.base.processing_count,
            "tasks_solved": self.base.tasks_solved,
            "knowledge_contributed": self.base.knowledge_contributed,
            "errors": self.base.errors,
            "goals": self.goals,
            "meta_patterns": self.meta_patterns,
            "stagnation_counter": self.stagnation_counter,
        })
    }

    fn deserialize_state(&mut self, data: &serde_json::Value) {
        self.base.processing_count = data["processing_count"].as_u64().unwrap_or(0);
        self.base.tasks_solved = data["tasks_solved"].as_u64().unwrap_or(0);
        self.base.knowledge_contributed = data["knowledge_contributed"].as_u64().unwrap_or(0);
        self.base.errors = data["errors"].as_u64().unwrap_or(0);
        if let Some(arr) = data["goals"].as_array() {
            self.goals = arr.clone();
        }
        if let Some(arr) = data["meta_patterns"].as_array() {
            self.meta_patterns = arr.clone();
        }
        self.stagnation_counter = data["stagnation_counter"].as_u64().unwrap_or(0) as u32;
    }
}

// ---------------------------------------------------------------------------
// 2. Chochmah — Intuition and pattern discovery
// ---------------------------------------------------------------------------

pub struct ChochmahProcessor {
    pub base: BaseState,
    pub insights: Vec<serde_json::Value>,
}

impl ChochmahProcessor {
    pub fn new() -> Self {
        Self {
            base: BaseState::default(),
            insights: Vec::new(),
        }
    }
}

impl SephirahProcessor for ChochmahProcessor {
    impl_common!(ChochmahProcessor, SephirahRole::Chochmah);

    fn process(&mut self, context: &ProcessingContext) -> ProcessingResult {
        self.base.processing_count += 1;
        let messages = self.base.consume_inbox();

        // Read strategy directive from Keter
        let mut strategy_focus = String::new();
        for msg in &messages {
            if msg.payload.get("type").and_then(|v| v.as_str()) == Some("strategy_directive") {
                strategy_focus = msg
                    .payload
                    .get("strategy")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
            }
        }

        // Read neural hints from context
        let neural_conf = context.get_f64("neural_confidence");

        // Generate insight if we have sufficient context
        let has_insight = context.block_height > 0;
        if has_insight {
            let mut insight = serde_json::json!({
                "type": "pattern_insight",
                "block_height": context.block_height,
            });
            if neural_conf > 0.3 {
                insight["neural_confidence"] = serde_json::json!(neural_conf);
            }
            if !strategy_focus.is_empty() {
                insight["strategy_focus"] = serde_json::json!(&strategy_focus);
            }
            self.insights.push(insight.clone());
            if self.insights.len() > 100 {
                let start = self.insights.len() - 100;
                self.insights = self.insights[start..].to_vec();
            }

            // Forward to Binah for verification
            send_message(
                &mut self.base.outbox,
                SephirahRole::Chochmah,
                SephirahRole::Binah,
                payload!("type" => "insight_for_verification", "insight" => insight),
                1.0,
            );
        }

        let confidence = if neural_conf > 0.3 {
            (0.6 + neural_conf * 0.3).min(0.9)
        } else {
            0.6
        };

        ProcessingResult {
            role: SephirahRole::Chochmah,
            action: "pattern_discovery".into(),
            output: payload!(
                "insights" => self.insights.len(),
                "new_insight" => has_insight,
                "neural_confidence" => neural_conf,
                "strategy_focus" => &strategy_focus
            ),
            confidence,
            messages_out: self.drain_outbox(),
            success: true,
        }
    }

    fn specialized_reason(&self, context: &ReasoningContext) -> ReasoningResult {
        let energy_qf = qf(context.energy);
        let mut steps = vec![format!("Intuition quality factor: {:.2}", energy_qf)];

        let query_lower = context.query.to_lowercase();
        let query_terms_owned: std::collections::HashSet<String> =
            query_lower.split_whitespace().map(String::from).collect();
        steps.push(format!("Query terms: {}", query_terms_owned.len()));

        // Find associated nodes by term overlap
        let mut associated: Vec<(usize, f64)> = Vec::new();
        for (i, node) in context.knowledge_nodes.iter().enumerate() {
            let content = node
                .get("content")
                .or_else(|| node.get("name"))
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let node_terms: std::collections::HashSet<String> =
                content.to_lowercase().split_whitespace().map(String::from).collect();
            let overlap = query_terms_owned.intersection(&node_terms).count();
            if overlap > 0 {
                let relevance = overlap as f64 / query_terms_owned.len().max(1) as f64;
                associated.push((i, relevance));
            }
        }
        associated.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        let max_assoc = (associated.len() as f64 * energy_qf).ceil() as usize;
        associated.truncate(max_assoc.max(1));
        steps.push(format!("Found {} associated nodes", associated.len()));

        // Cross-association hypothesis
        let mut hypotheses: Vec<String> = Vec::new();
        if associated.len() >= 2 && energy_qf > 0.5 {
            hypotheses.push("Potential hidden link between most and least related nodes".into());
            steps.push("Generated cross-association hypothesis".into());
        }

        let confidence = if !context.knowledge_nodes.is_empty() {
            ((associated.len() as f64 / context.knowledge_nodes.len().max(1) as f64) * energy_qf)
                .min(1.0)
        } else {
            0.1
        };

        ReasoningResult {
            result: if hypotheses.is_empty() {
                "Insufficient data for pattern detection".into()
            } else {
                hypotheses.join("; ")
            },
            confidence: (confidence * 10000.0).round() / 10000.0,
            reasoning_type: "intuitive_pattern_matching".into(),
            steps,
        }
    }

    fn serialize_state(&self) -> serde_json::Value {
        serde_json::json!({
            "role": "chochmah",
            "processing_count": self.base.processing_count,
            "insights": self.insights,
        })
    }

    fn deserialize_state(&mut self, data: &serde_json::Value) {
        self.base.processing_count = data["processing_count"].as_u64().unwrap_or(0);
        if let Some(arr) = data["insights"].as_array() {
            self.insights = arr.clone();
        }
    }
}

// ---------------------------------------------------------------------------
// 3. Binah — Logic and causal inference
// ---------------------------------------------------------------------------

pub struct BinahProcessor {
    pub base: BaseState,
    pub verified: u64,
    pub rejected: u64,
}

impl BinahProcessor {
    pub fn new() -> Self {
        Self {
            base: BaseState::default(),
            verified: 0,
            rejected: 0,
        }
    }
}

impl SephirahProcessor for BinahProcessor {
    impl_common!(BinahProcessor, SephirahRole::Binah);

    fn process(&mut self, context: &ProcessingContext) -> ProcessingResult {
        self.base.processing_count += 1;
        let messages = self.base.consume_inbox();

        let causal_conf = context.get_f64("causal_confidence");
        let causal_available = context.data.contains_key("causal_confidence");

        let mut verified_cycle = 0u64;
        let mut rejected_cycle = 0u64;

        for msg in &messages {
            if msg.payload.get("type").and_then(|v| v.as_str()) == Some("insight_for_verification")
            {
                let insight = msg.payload.get("insight").cloned().unwrap_or_default();
                let neural_conf = insight
                    .get("neural_confidence")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);

                // Reject if causal data is available and both confidences are very low
                if causal_available && causal_conf < 0.2 && neural_conf < 0.2 {
                    self.rejected += 1;
                    rejected_cycle += 1;
                    send_message(
                        &mut self.base.outbox,
                        SephirahRole::Binah,
                        SephirahRole::Tiferet,
                        payload!("type" => "verification_result", "verdict" => "rejected", "reason" => "no_causal_support"),
                        1.0,
                    );
                    continue;
                }

                self.verified += 1;
                verified_cycle += 1;
                send_message(
                    &mut self.base.outbox,
                    SephirahRole::Binah,
                    SephirahRole::Tiferet,
                    payload!("type" => "verification_result", "verdict" => "verified", "neural_confidence" => neural_conf),
                    1.0,
                );
            }
        }

        ProcessingResult {
            role: SephirahRole::Binah,
            action: "logical_verification".into(),
            output: payload!(
                "verified_total" => self.verified,
                "rejected_total" => self.rejected,
                "verified_this_cycle" => verified_cycle,
                "rejected_this_cycle" => rejected_cycle,
                "causal_data_available" => causal_available
            ),
            confidence: 0.9,
            messages_out: self.drain_outbox(),
            success: true,
        }
    }

    fn specialized_reason(&self, context: &ReasoningContext) -> ReasoningResult {
        let energy_qf = qf(context.energy);
        let mut steps = vec![format!("Logic quality factor: {:.2}", energy_qf)];

        // Build support/contradiction edge lists from knowledge nodes
        let mut supports: Vec<(String, String)> = Vec::new();
        let mut contradicts: Vec<(String, String)> = Vec::new();

        for node in &context.knowledge_nodes {
            let name = node
                .get("name")
                .or_else(|| node.get("content"))
                .and_then(|v| v.as_str())
                .unwrap_or("node")
                .to_string();

            if let Some(edges) = node.get("edges_out").and_then(|v| v.as_array()) {
                for edge in edges {
                    let etype = edge
                        .get("edge_type")
                        .and_then(|v| v.as_str())
                        .unwrap_or("supports");
                    let target = edge
                        .get("to_node_name")
                        .and_then(|v| v.as_str())
                        .unwrap_or("target")
                        .to_string();
                    match etype {
                        "supports" => supports.push((name.clone(), target)),
                        "contradicts" => contradicts.push((name.clone(), target)),
                        _ => {}
                    }
                }
            }
        }

        steps.push(format!(
            "Found {} support relations, {} contradictions",
            supports.len(),
            contradicts.len()
        ));

        // Detect A supports B AND A contradicts B
        let support_set: std::collections::HashSet<(&str, &str)> =
            supports.iter().map(|(a, b)| (a.as_str(), b.as_str())).collect();
        let contradiction_pairs: Vec<_> = contradicts
            .iter()
            .filter(|(a, b)| support_set.contains(&(a.as_str(), b.as_str())))
            .collect();

        if !contradiction_pairs.is_empty() {
            steps.push(format!(
                "Detected {} logical contradiction(s)",
                contradiction_pairs.len()
            ));
        }

        // Build deductive chains (A->B, B->C)
        let mut chains: Vec<Vec<String>> = Vec::new();
        if energy_qf > 0.3 && !supports.is_empty() {
            let mut forward: HashMap<&str, Vec<&str>> = HashMap::new();
            for (a, b) in &supports {
                forward.entry(a.as_str()).or_default().push(b.as_str());
            }
            let max_chains = (5.0 * energy_qf) as usize;
            let mut visited_starts = 0;
            for start in forward.keys().copied() {
                if visited_starts >= max_chains.max(1) {
                    break;
                }
                let mut chain = vec![start.to_string()];
                let mut current = start;
                let mut seen = std::collections::HashSet::new();
                seen.insert(start);
                while let Some(nexts) = forward.get(current) {
                    if let Some(nxt) = nexts.iter().find(|n| !seen.contains(**n)) {
                        chain.push(nxt.to_string());
                        seen.insert(nxt);
                        current = nxt;
                    } else {
                        break;
                    }
                }
                if chain.len() >= 3 {
                    chains.push(chain);
                    visited_starts += 1;
                }
            }
            if !chains.is_empty() {
                let longest = chains.iter().map(|c| c.len()).max().unwrap_or(0);
                steps.push(format!(
                    "Built {} deductive chain(s), longest has {} nodes",
                    chains.len(),
                    longest
                ));
            }
        }

        let has_contradiction = !contradiction_pairs.is_empty();
        let has_chains = !chains.is_empty();
        let confidence = (energy_qf
            * if has_chains { 0.9 } else { 0.5 }
            * if has_contradiction { 0.7 } else { 1.0 })
        .min(1.0);

        let mut result_parts = Vec::new();
        if has_chains {
            result_parts.push(format!("Deductive chain: {}", chains[0].join(" -> ")));
        }
        if has_contradiction {
            let (a, b) = contradiction_pairs[0];
            result_parts.push(format!(
                "Contradiction: '{}' both supports and contradicts '{}'",
                a, b
            ));
        }
        if result_parts.is_empty() {
            result_parts.push("No deductive chains or contradictions found".into());
        }

        ReasoningResult {
            result: result_parts.join("; "),
            confidence: (confidence * 10000.0).round() / 10000.0,
            reasoning_type: "formal_logic".into(),
            steps,
        }
    }

    fn serialize_state(&self) -> serde_json::Value {
        serde_json::json!({
            "role": "binah",
            "processing_count": self.base.processing_count,
            "verified": self.verified,
            "rejected": self.rejected,
        })
    }

    fn deserialize_state(&mut self, data: &serde_json::Value) {
        self.base.processing_count = data["processing_count"].as_u64().unwrap_or(0);
        self.verified = data["verified"].as_u64().unwrap_or(0);
        self.rejected = data["rejected"].as_u64().unwrap_or(0);
    }
}

// ---------------------------------------------------------------------------
// 4. Chesed — Creativity and divergent exploration
// ---------------------------------------------------------------------------

pub struct ChesedProcessor {
    pub base: BaseState,
    pub explorations: u64,
}

impl ChesedProcessor {
    pub fn new() -> Self {
        Self {
            base: BaseState::default(),
            explorations: 0,
        }
    }
}

impl SephirahProcessor for ChesedProcessor {
    impl_common!(ChesedProcessor, SephirahRole::Chesed);

    fn process(&mut self, context: &ProcessingContext) -> ProcessingResult {
        self.base.processing_count += 1;
        self.base.consume_inbox();
        self.explorations += 1;

        // Send exploration report to Gevurah for safety check
        let new_connections = context.get_f64("potential_connections") as u64;
        send_message(
            &mut self.base.outbox,
            SephirahRole::Chesed,
            SephirahRole::Gevurah,
            payload!("type" => "exploration_report", "new_connections" => new_connections),
            1.0,
        );

        ProcessingResult {
            role: SephirahRole::Chesed,
            action: "divergent_exploration".into(),
            output: payload!(
                "explorations" => self.explorations,
                "potential_connections" => new_connections
            ),
            confidence: 0.5,
            messages_out: self.drain_outbox(),
            success: true,
        }
    }

    fn specialized_reason(&self, context: &ReasoningContext) -> ReasoningResult {
        let energy_qf = qf(context.energy);
        let mut steps = vec![format!("Creativity quality factor: {:.2}", energy_qf)];

        // Group nodes by domain for cross-pollination
        let mut domains: HashMap<String, Vec<&serde_json::Value>> = HashMap::new();
        for node in &context.knowledge_nodes {
            let domain = node
                .get("domain")
                .or_else(|| node.get("node_type"))
                .and_then(|v| v.as_str())
                .unwrap_or("general")
                .to_string();
            domains.entry(domain).or_default().push(node);
        }
        steps.push(format!("Found {} knowledge domains", domains.len()));

        let max_alt = (7.0 * energy_qf).ceil() as usize;
        let mut alternatives: Vec<String> = Vec::new();
        let domain_list: Vec<_> = domains.iter().collect();

        // Strategy 1: Cross-domain combination
        for i in 0..domain_list.len().min(max_alt) {
            let (d1, n1) = domain_list[i];
            let (d2, _) = domain_list[(i + 1) % domain_list.len()];
            if d1 != d2 {
                let n1_name = n1
                    .first()
                    .and_then(|n| n.get("name").and_then(|v| v.as_str()))
                    .unwrap_or(d1.as_str());
                alternatives.push(format!(
                    "Cross-domain synthesis: combine '{}' ({}) with ({})",
                    n1_name, d1, d2
                ));
            }
        }

        // Strategy 2: Inversion
        if energy_qf > 0.4 && !context.query.is_empty() {
            let truncated: String = context.query.chars().take(50).collect();
            alternatives.push(format!("Inversion approach: negate '{}'", truncated));
            steps.push("Generated inversion hypothesis".into());
        }

        // Strategy 3: Analogy from largest domain
        if !domain_list.is_empty() && energy_qf > 0.3 {
            let largest = domain_list.iter().max_by_key(|(_, nodes)| nodes.len()).unwrap();
            alternatives.push(format!(
                "Analogy from {} domain ({} nodes)",
                largest.0,
                largest.1.len()
            ));
            steps.push(format!("Generated analogy from {}", largest.0));
        }

        // Strategy 4: Random recombination (deterministic via query hash)
        if context.knowledge_nodes.len() >= 3 && energy_qf > 0.6 {
            alternatives.push("Random recombination of 3 sampled nodes".into());
            steps.push("Generated random recombination".into());
        }

        alternatives.truncate(max_alt.max(1));
        steps.push(format!("Generated {} alternative solutions", alternatives.len()));

        let confidence =
            (alternatives.len() as f64 / max_alt.max(1) as f64 * energy_qf).min(1.0);

        ReasoningResult {
            result: if alternatives.is_empty() {
                "No creative alternatives generated".into()
            } else {
                alternatives.join(" | ")
            },
            confidence: (confidence * 10000.0).round() / 10000.0,
            reasoning_type: "divergent_thinking".into(),
            steps,
        }
    }

    fn serialize_state(&self) -> serde_json::Value {
        serde_json::json!({
            "role": "chesed",
            "processing_count": self.base.processing_count,
            "explorations": self.explorations,
        })
    }

    fn deserialize_state(&mut self, data: &serde_json::Value) {
        self.base.processing_count = data["processing_count"].as_u64().unwrap_or(0);
        self.explorations = data["explorations"].as_u64().unwrap_or(0);
    }
}

// ---------------------------------------------------------------------------
// 5. Gevurah — Safety and constraint validation
// ---------------------------------------------------------------------------

pub struct GevurahProcessor {
    pub base: BaseState,
    pub vetoes: u64,
    pub approvals: u64,
}

impl GevurahProcessor {
    pub fn new() -> Self {
        Self {
            base: BaseState::default(),
            vetoes: 0,
            approvals: 0,
        }
    }
}

impl SephirahProcessor for GevurahProcessor {
    impl_common!(GevurahProcessor, SephirahRole::Gevurah);

    fn process(&mut self, context: &ProcessingContext) -> ProcessingResult {
        self.base.processing_count += 1;
        let messages = self.base.consume_inbox();

        let contradictions_found = context.get_f64("contradictions_found") as u64;

        let mut vetoed_cycle = 0u64;
        let mut approved_cycle = 0u64;

        for msg in &messages {
            if msg.payload.get("type").and_then(|v| v.as_str()) == Some("exploration_report") {
                let connections = msg
                    .payload
                    .get("new_connections")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0);
                if connections > 100 {
                    vetoed_cycle += 1;
                    self.vetoes += 1;
                } else {
                    approved_cycle += 1;
                    self.approvals += 1;
                }
            }
        }

        if contradictions_found > 0 {
            vetoed_cycle += 1;
            self.vetoes += 1;
            send_message(
                &mut self.base.outbox,
                SephirahRole::Gevurah,
                SephirahRole::Tiferet,
                payload!("type" => "safety_assessment", "vetoed" => true, "reason" => "contradictions_detected"),
                1.0,
            );
        }

        ProcessingResult {
            role: SephirahRole::Gevurah,
            action: "safety_validation".into(),
            output: payload!(
                "vetoes_total" => self.vetoes,
                "approvals_total" => self.approvals,
                "vetoed_this_cycle" => vetoed_cycle,
                "approved_this_cycle" => approved_cycle
            ),
            confidence: 0.95,
            messages_out: self.drain_outbox(),
            success: true,
        }
    }

    fn specialized_reason(&self, context: &ReasoningContext) -> ReasoningResult {
        let energy_qf = qf(context.energy);
        let mut steps = vec![format!("Safety analysis quality factor: {:.2}", energy_qf)];

        let mut threats: Vec<String> = Vec::new();
        let mut risk_score = 0.0_f64;

        // Dangerous keyword scan
        let danger_keywords = [
            "delete", "destroy", "override", "bypass", "ignore safety",
            "shutdown", "disable", "attack", "exploit", "hack",
        ];
        let ql = context.query.to_lowercase();
        for kw in &danger_keywords {
            if ql.contains(kw) {
                threats.push(format!("Dangerous keyword detected: '{}'", kw));
                risk_score += 0.3;
            }
        }
        steps.push(format!("Keyword scan: {} threats detected", threats.len()));

        // Check recent reasoning for failure patterns
        let mut failure_count = 0usize;
        let mut low_conf_count = 0usize;
        for op in &context.recent_reasoning {
            let conf = op.get("confidence").and_then(|v| v.as_f64()).unwrap_or(1.0);
            let success = op.get("success").and_then(|v| v.as_bool()).unwrap_or(true);
            if !success || conf < 0.2 {
                failure_count += 1;
            }
            if conf < 0.4 {
                low_conf_count += 1;
            }
        }

        let n = context.recent_reasoning.len();
        if failure_count > n / 2 && n > 2 {
            threats.push(format!("High failure rate ({}/{})", failure_count, n));
            risk_score += 0.2;
        }
        if low_conf_count as f64 > n as f64 * 0.7 && n > 2 {
            threats.push("Systemic low confidence in recent reasoning".into());
            risk_score += 0.15;
        }
        steps.push(format!(
            "Recent ops: {} failures, {} low-confidence out of {}",
            failure_count, low_conf_count, n
        ));

        // Contradiction density in KG
        let mut contradiction_count = 0u64;
        for node in &context.knowledge_nodes {
            if let Some(edges) = node.get("edges_out").and_then(|v| v.as_array()) {
                for edge in edges {
                    if edge.get("edge_type").and_then(|v| v.as_str()) == Some("contradicts") {
                        contradiction_count += 1;
                    }
                }
            }
        }
        if contradiction_count > 5 {
            threats.push(format!("High contradiction count: {}", contradiction_count));
            risk_score += 0.15;
        }
        steps.push(format!("Knowledge contradictions: {}", contradiction_count));

        risk_score = risk_score.min(1.0) * energy_qf;
        let should_veto = risk_score > 0.5;

        if should_veto {
            steps.push(format!("VETO RECOMMENDED: risk_score={:.2} > 0.5", risk_score));
        } else {
            steps.push(format!("APPROVED: risk_score={:.2} <= 0.5", risk_score));
        }

        ReasoningResult {
            result: format!(
                "{}: risk_score={:.2}",
                if should_veto { "VETO" } else { "APPROVED" },
                risk_score
            ),
            confidence: (energy_qf * 0.95 * 10000.0).round() / 10000.0,
            reasoning_type: "safety_analysis".into(),
            steps,
        }
    }

    fn serialize_state(&self) -> serde_json::Value {
        serde_json::json!({
            "role": "gevurah",
            "processing_count": self.base.processing_count,
            "vetoes": self.vetoes,
            "approvals": self.approvals,
        })
    }

    fn deserialize_state(&mut self, data: &serde_json::Value) {
        self.base.processing_count = data["processing_count"].as_u64().unwrap_or(0);
        self.vetoes = data["vetoes"].as_u64().unwrap_or(0);
        self.approvals = data["approvals"].as_u64().unwrap_or(0);
    }
}

// ---------------------------------------------------------------------------
// 6. Tiferet — Integration and conflict resolution
// ---------------------------------------------------------------------------

pub struct TiferetProcessor {
    pub base: BaseState,
    pub integrations: u64,
}

impl TiferetProcessor {
    pub fn new() -> Self {
        Self {
            base: BaseState::default(),
            integrations: 0,
        }
    }
}

impl SephirahProcessor for TiferetProcessor {
    impl_common!(TiferetProcessor, SephirahRole::Tiferet);

    fn process(&mut self, context: &ProcessingContext) -> ProcessingResult {
        self.base.processing_count += 1;
        let messages = self.base.consume_inbox();
        self.integrations += 1;

        // Categorize incoming messages
        let mut verified_count = 0u64;
        let mut rejected_count = 0u64;
        let mut safety_vetoes = 0u64;
        let mut by_type: HashMap<String, u64> = HashMap::new();

        for msg in &messages {
            let mtype = msg
                .payload
                .get("type")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown");
            *by_type.entry(mtype.to_string()).or_default() += 1;

            match mtype {
                "verification_result" => {
                    if msg.payload.get("verdict").and_then(|v| v.as_str()) == Some("verified") {
                        verified_count += 1;
                    } else {
                        rejected_count += 1;
                    }
                }
                "safety_assessment" => {
                    if msg.payload.get("vetoed").and_then(|v| v.as_bool()) == Some(true) {
                        safety_vetoes += 1;
                    }
                }
                _ => {}
            }
        }

        let conflicts_resolved = verified_count.min(rejected_count);

        // Broadcast integrated state to Malkuth
        send_message(
            &mut self.base.outbox,
            SephirahRole::Tiferet,
            SephirahRole::Malkuth,
            payload!(
                "type" => "integrated_directive",
                "source_count" => messages.len(),
                "verified_count" => verified_count,
                "rejected_count" => rejected_count,
                "conflicts_resolved" => conflicts_resolved,
                "explorations_approved" => if safety_vetoes == 0 { 1u64 } else { 0u64 },
                "block_height" => context.block_height
            ),
            1.0,
        );

        // Send reward signal to Netzach for verified insights
        if verified_count > 0 {
            send_message(
                &mut self.base.outbox,
                SephirahRole::Tiferet,
                SephirahRole::Netzach,
                payload!("type" => "reward_signal", "policy" => "verification_success", "reward" => 0.1 * verified_count as f64),
                1.0,
            );
        }

        ProcessingResult {
            role: SephirahRole::Tiferet,
            action: "cognitive_integration".into(),
            output: payload!(
                "integrations" => self.integrations,
                "messages_integrated" => messages.len(),
                "conflicts_resolved" => conflicts_resolved,
                "verified_insights" => verified_count,
                "rejected_insights" => rejected_count
            ),
            confidence: 0.8,
            messages_out: self.drain_outbox(),
            success: true,
        }
    }

    fn specialized_reason(&self, context: &ReasoningContext) -> ReasoningResult {
        let energy_qf = qf(context.energy);
        let mut steps = vec![format!("Integration quality factor: {:.2}", energy_qf)];

        // Group recent reasoning by type and compute weighted scores
        let mut type_scores: HashMap<String, Vec<f64>> = HashMap::new();
        for op in &context.recent_reasoning {
            let rtype = op
                .get("reasoning_type")
                .or_else(|| op.get("type"))
                .and_then(|v| v.as_str())
                .unwrap_or("unknown")
                .to_string();
            let conf = op.get("confidence").and_then(|v| v.as_f64()).unwrap_or(0.5);
            type_scores.entry(rtype).or_default().push(conf);
        }

        steps.push(format!(
            "Found {} reasoning types in recent history",
            type_scores.len()
        ));

        // Compute weighted consensus: weight = avg_confidence * sqrt(count)
        let mut weighted: Vec<(String, f64)> = type_scores
            .iter()
            .map(|(rtype, scores)| {
                let avg = scores.iter().sum::<f64>() / scores.len() as f64;
                let weight = avg * (scores.len() as f64).sqrt();
                (rtype.clone(), weight)
            })
            .collect();
        weighted.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());

        // Detect conflicts
        let mut conflicts = Vec::new();
        if weighted.len() >= 2 {
            let top_w = weighted[0].1;
            let runner_w = weighted[1].1;
            if runner_w > top_w * 0.7 {
                conflicts.push(format!(
                    "Conflict: {} (w={:.2}) vs {} (w={:.2})",
                    weighted[0].0, top_w, weighted[1].0, runner_w
                ));
                steps.push(format!(
                    "Conflict detected between {} and {}",
                    weighted[0].0, weighted[1].0
                ));
            }
        }

        let max_merge = (3.0 * energy_qf).ceil() as usize;
        let total_weight: f64 = weighted.iter().take(max_merge.max(1)).map(|(_, w)| w).sum();
        let confidence = if !context.recent_reasoning.is_empty() {
            (total_weight / context.recent_reasoning.len().max(1) as f64 * energy_qf).min(1.0)
        } else {
            0.2
        };

        let synthesis: Vec<String> = weighted
            .iter()
            .take(max_merge.max(1))
            .map(|(t, _)| format!("[{}]", t))
            .collect();
        steps.push(format!("Synthesized {} top conclusions", synthesis.len()));

        ReasoningResult {
            result: if synthesis.is_empty() {
                "No data to integrate".into()
            } else {
                synthesis.join(" + ")
            },
            confidence: (confidence * 10000.0).round() / 10000.0,
            reasoning_type: "synthesis".into(),
            steps,
        }
    }

    fn serialize_state(&self) -> serde_json::Value {
        serde_json::json!({
            "role": "tiferet",
            "processing_count": self.base.processing_count,
            "integrations": self.integrations,
        })
    }

    fn deserialize_state(&mut self, data: &serde_json::Value) {
        self.base.processing_count = data["processing_count"].as_u64().unwrap_or(0);
        self.integrations = data["integrations"].as_u64().unwrap_or(0);
    }
}

// ---------------------------------------------------------------------------
// 7. Netzach — Reinforcement learning
// ---------------------------------------------------------------------------

pub struct NetzachProcessor {
    pub base: BaseState,
    pub policies: HashMap<String, f64>,
    pub total_rewards: f64,
}

impl NetzachProcessor {
    pub fn new() -> Self {
        Self {
            base: BaseState::default(),
            policies: HashMap::new(),
            total_rewards: 0.0,
        }
    }
}

impl SephirahProcessor for NetzachProcessor {
    impl_common!(NetzachProcessor, SephirahRole::Netzach);

    fn process(&mut self, context: &ProcessingContext) -> ProcessingResult {
        self.base.processing_count += 1;
        let messages = self.base.consume_inbox();

        let mut reward_count = 0u64;

        for msg in &messages {
            if msg.payload.get("type").and_then(|v| v.as_str()) == Some("reward_signal") {
                let policy = msg
                    .payload
                    .get("policy")
                    .and_then(|v| v.as_str())
                    .unwrap_or("default")
                    .to_string();
                let reward = msg
                    .payload
                    .get("reward")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                let current = self.policies.get(&policy).copied().unwrap_or(0.0);
                // Exponential moving average: 0.9 * old + 0.1 * new
                self.policies.insert(policy, current * 0.9 + reward * 0.1);
                self.total_rewards += reward;
                reward_count += 1;
            }
        }

        // GAT training reward
        let gat_trained = context.get_f64("gat_trained") > 0.5;
        if gat_trained {
            let current = self.policies.get("neural_reasoning").copied().unwrap_or(0.0);
            self.policies
                .insert("neural_reasoning".into(), current * 0.9 + 0.01);
            self.total_rewards += 0.1;
        }

        ProcessingResult {
            role: SephirahRole::Netzach,
            action: "policy_learning".into(),
            output: payload!(
                "active_policies" => self.policies.len(),
                "total_rewards" => (self.total_rewards * 10000.0).round() / 10000.0,
                "rewards_this_cycle" => reward_count,
                "gat_trained" => gat_trained
            ),
            confidence: 0.7,
            messages_out: self.drain_outbox(),
            success: true,
        }
    }

    fn specialized_reason(&self, context: &ReasoningContext) -> ReasoningResult {
        let energy_qf = qf(context.energy);
        let mut steps = vec![format!("RL quality factor: {:.2}", energy_qf)];

        // Build policy evaluation from recent reasoning
        let mut policy_rewards: HashMap<String, Vec<f64>> = HashMap::new();
        for op in &context.recent_reasoning {
            let policy = op
                .get("reasoning_type")
                .or_else(|| op.get("type"))
                .and_then(|v| v.as_str())
                .unwrap_or("default")
                .to_string();
            let mut reward = op.get("confidence").and_then(|v| v.as_f64()).unwrap_or(0.5);
            if op.get("success").and_then(|v| v.as_bool()) == Some(false) {
                reward *= 0.1;
            }
            policy_rewards.entry(policy).or_default().push(reward);
        }

        // Merge persistent policies
        for (policy, score) in &self.policies {
            policy_rewards
                .entry(policy.clone())
                .or_insert_with(|| vec![*score]);
        }

        steps.push(format!("Evaluating {} policies", policy_rewards.len()));

        let mut recommendations: Vec<(String, f64, &str)> = Vec::new();
        for (policy, rewards) in &policy_rewards {
            let avg = rewards.iter().sum::<f64>() / rewards.len() as f64;
            let n = rewards.len();
            let recent_n = (n as f64 * 0.3).ceil() as usize;
            let recent_avg = if n >= 2 {
                rewards[n.saturating_sub(recent_n)..].iter().sum::<f64>()
                    / recent_n.max(1) as f64
            } else {
                avg
            };

            let trend = if recent_avg > avg * 1.1 {
                "improving"
            } else if recent_avg < avg * 0.9 {
                "declining"
            } else {
                "stable"
            };

            let action = if trend == "improving" && avg > 0.6 {
                "reinforce"
            } else if trend == "declining" || avg < 0.3 {
                "reduce"
            } else {
                "maintain"
            };

            recommendations.push((policy.clone(), avg, action));
        }
        recommendations.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());

        let max_recs = (recommendations.len() as f64 * energy_qf).ceil() as usize;
        recommendations.truncate(max_recs.max(1));
        steps.push(format!(
            "Generated {} policy recommendations",
            recommendations.len()
        ));

        let result = if let Some(top) = recommendations.first() {
            format!("Best policy: {} (avg_reward={:.2})", top.0, top.1)
        } else {
            "No policies to evaluate".into()
        };
        let confidence = (energy_qf * if recommendations.is_empty() { 0.2 } else { 0.8 }).min(1.0);

        ReasoningResult {
            result,
            confidence: (confidence * 10000.0).round() / 10000.0,
            reasoning_type: "reinforcement_learning".into(),
            steps,
        }
    }

    fn serialize_state(&self) -> serde_json::Value {
        serde_json::json!({
            "role": "netzach",
            "processing_count": self.base.processing_count,
            "policies": self.policies,
            "total_rewards": self.total_rewards,
        })
    }

    fn deserialize_state(&mut self, data: &serde_json::Value) {
        self.base.processing_count = data["processing_count"].as_u64().unwrap_or(0);
        self.total_rewards = data["total_rewards"].as_f64().unwrap_or(0.0);
        if let Some(obj) = data["policies"].as_object() {
            self.policies.clear();
            for (k, v) in obj {
                self.policies.insert(k.clone(), v.as_f64().unwrap_or(0.0));
            }
        }
    }
}

// ---------------------------------------------------------------------------
// 8. Hod — Language and semantic encoding
// ---------------------------------------------------------------------------

pub struct HodProcessor {
    pub base: BaseState,
    pub encodings: u64,
}

impl HodProcessor {
    pub fn new() -> Self {
        Self {
            base: BaseState::default(),
            encodings: 0,
        }
    }
}

impl SephirahProcessor for HodProcessor {
    impl_common!(HodProcessor, SephirahRole::Hod);

    fn process(&mut self, context: &ProcessingContext) -> ProcessingResult {
        self.base.processing_count += 1;
        self.base.consume_inbox();

        // Count semantically-encodable items from context
        let encoded = context.get_f64("encodable_nodes") as u64;
        self.encodings += encoded;

        ProcessingResult {
            role: SephirahRole::Hod,
            action: "semantic_encoding".into(),
            output: payload!(
                "total_encodings" => self.encodings,
                "encoded_this_cycle" => encoded
            ),
            confidence: 0.75,
            messages_out: self.drain_outbox(),
            success: true,
        }
    }

    fn specialized_reason(&self, context: &ReasoningContext) -> ReasoningResult {
        let energy_qf = qf(context.energy);
        let mut steps = vec![format!("Semantic quality factor: {:.2}", energy_qf)];

        // Extract key concepts (term frequency, skip stop words)
        let stop_words: std::collections::HashSet<&str> = [
            "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of",
            "and", "or", "not", "it", "this", "that", "with", "from", "by", "as", "be", "has",
            "have",
        ]
        .iter()
        .copied()
        .collect();

        let mut term_freq: HashMap<String, u32> = HashMap::new();
        for word in context.query.to_lowercase().split_whitespace() {
            if word.len() > 2 && !stop_words.contains(word) {
                *term_freq.entry(word.to_string()).or_default() += 1;
            }
        }
        let max_concepts = (10.0 * energy_qf).ceil() as usize;
        let mut key_concepts: Vec<_> = term_freq.iter().collect();
        key_concepts.sort_by(|a, b| b.1.cmp(a.1));
        key_concepts.truncate(max_concepts.max(1));
        steps.push(format!(
            "Extracted {} key concepts from query",
            key_concepts.len()
        ));

        // Map concepts to knowledge nodes (semantic grounding)
        let mut grounded = 0u32;
        for (term, _) in &key_concepts {
            for node in &context.knowledge_nodes {
                let content = node
                    .get("content")
                    .or_else(|| node.get("name"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                if content.to_lowercase().contains(term.as_str()) {
                    grounded += 1;
                    break;
                }
            }
        }
        steps.push(format!(
            "Grounded {}/{} concepts to knowledge nodes",
            grounded,
            key_concepts.len()
        ));

        // Summarize recent reasoning
        if !context.recent_reasoning.is_empty() && energy_qf > 0.4 {
            let avg_conf: f64 = context
                .recent_reasoning
                .iter()
                .map(|op| op.get("confidence").and_then(|v| v.as_f64()).unwrap_or(0.5))
                .sum::<f64>()
                / context.recent_reasoning.len() as f64;
            steps.push(format!(
                "Recent reasoning: {} ops, avg_confidence={:.2}",
                context.recent_reasoning.len(),
                avg_conf
            ));
        }

        let confidence = if !key_concepts.is_empty() {
            (grounded as f64 / key_concepts.len().max(1) as f64 * energy_qf).min(1.0)
        } else {
            0.1
        };

        let concepts_str: Vec<_> = key_concepts.iter().map(|(c, _)| c.as_str()).collect();

        ReasoningResult {
            result: if concepts_str.is_empty() {
                "Insufficient data for semantic encoding".into()
            } else {
                format!("Key concepts: {}", concepts_str.join(", "))
            },
            confidence: (confidence * 10000.0).round() / 10000.0,
            reasoning_type: "semantic_encoding".into(),
            steps,
        }
    }

    fn serialize_state(&self) -> serde_json::Value {
        serde_json::json!({
            "role": "hod",
            "processing_count": self.base.processing_count,
            "encodings": self.encodings,
        })
    }

    fn deserialize_state(&mut self, data: &serde_json::Value) {
        self.base.processing_count = data["processing_count"].as_u64().unwrap_or(0);
        self.encodings = data["encodings"].as_u64().unwrap_or(0);
    }
}

// ---------------------------------------------------------------------------
// 9. Yesod — Memory and multimodal fusion
// ---------------------------------------------------------------------------

pub struct YesodProcessor {
    pub base: BaseState,
    pub consolidations: u64,
    pub working_buffer: Vec<serde_json::Value>,
    pub buffer_capacity: usize,
}

impl YesodProcessor {
    pub fn new() -> Self {
        Self {
            base: BaseState::default(),
            consolidations: 0,
            working_buffer: Vec::new(),
            buffer_capacity: 7, // Miller's 7 +/- 2
        }
    }
}

impl SephirahProcessor for YesodProcessor {
    impl_common!(YesodProcessor, SephirahRole::Yesod);

    fn process(&mut self, context: &ProcessingContext) -> ProcessingResult {
        self.base.processing_count += 1;
        let messages = self.base.consume_inbox();

        // Add message payloads to working buffer
        for msg in &messages {
            let payload_val = serde_json::to_value(&msg.payload).unwrap_or_default();
            self.working_buffer.push(payload_val);
            if self.working_buffer.len() > self.buffer_capacity {
                // Consolidate: keep most recent items
                let start = self.working_buffer.len() - self.buffer_capacity;
                self.working_buffer = self.working_buffer[start..].to_vec();
                self.consolidations += 1;
            }
        }

        let hit_rate = context.get_f64("memory_hit_rate");

        ProcessingResult {
            role: SephirahRole::Yesod,
            action: "memory_fusion".into(),
            output: payload!(
                "consolidations" => self.consolidations,
                "buffer_usage" => self.working_buffer.len(),
                "buffer_capacity" => self.buffer_capacity,
                "memory_hit_rate" => hit_rate
            ),
            confidence: 0.8,
            messages_out: self.drain_outbox(),
            success: true,
        }
    }

    fn specialized_reason(&self, context: &ReasoningContext) -> ReasoningResult {
        let energy_qf = qf(context.energy);
        let mut steps = vec![format!("Memory quality factor: {:.2}", energy_qf)];

        let query_terms: std::collections::HashSet<String> = context
            .query
            .to_lowercase()
            .split_whitespace()
            .map(String::from)
            .collect();

        // Search working buffer
        let mut buffer_matches = 0u32;
        for item in &self.working_buffer {
            let item_text = item.to_string().to_lowercase();
            let item_terms: std::collections::HashSet<String> =
                item_text.split_whitespace().map(String::from).collect();
            let overlap = query_terms.intersection(&item_terms).count();
            if overlap > 0 {
                buffer_matches += 1;
            }
        }
        steps.push(format!(
            "Working buffer: {} matches from {} items",
            buffer_matches,
            self.working_buffer.len()
        ));

        // Search knowledge nodes
        let mut node_matches = 0u32;
        for node in &context.knowledge_nodes {
            let content = node
                .get("content")
                .or_else(|| node.get("name"))
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let node_terms: std::collections::HashSet<String> = content
                .to_lowercase()
                .split_whitespace()
                .map(String::from)
                .collect();
            if query_terms.intersection(&node_terms).count() > 0 {
                node_matches += 1;
            }
        }
        let max_results = (5.0 * energy_qf).ceil() as u32;
        let node_matches = node_matches.min(max_results);
        steps.push(format!("Knowledge nodes: {} matches", node_matches));

        let total = buffer_matches + node_matches;
        let pool = self.working_buffer.len() + context.knowledge_nodes.len();
        let confidence = if pool > 0 {
            (total as f64 / pool as f64 * energy_qf * 2.0).min(1.0)
        } else {
            0.0
        };

        let result = if total > 0 {
            format!(
                "Retrieved {} memories ({} buffer, {} knowledge)",
                total, buffer_matches, node_matches
            )
        } else {
            "No matching memories found".into()
        };

        ReasoningResult {
            result,
            confidence: (confidence * 10000.0).round() / 10000.0,
            reasoning_type: "episodic_recall".into(),
            steps,
        }
    }

    fn serialize_state(&self) -> serde_json::Value {
        serde_json::json!({
            "role": "yesod",
            "processing_count": self.base.processing_count,
            "consolidations": self.consolidations,
            "working_buffer": self.working_buffer,
        })
    }

    fn deserialize_state(&mut self, data: &serde_json::Value) {
        self.base.processing_count = data["processing_count"].as_u64().unwrap_or(0);
        self.consolidations = data["consolidations"].as_u64().unwrap_or(0);
        if let Some(arr) = data["working_buffer"].as_array() {
            self.working_buffer = arr.clone();
        }
    }
}

// ---------------------------------------------------------------------------
// 10. Malkuth — Action and world interaction
// ---------------------------------------------------------------------------

pub struct MalkuthProcessor {
    pub base: BaseState,
    pub actions_executed: u64,
}

impl MalkuthProcessor {
    pub fn new() -> Self {
        Self {
            base: BaseState::default(),
            actions_executed: 0,
        }
    }
}

impl SephirahProcessor for MalkuthProcessor {
    impl_common!(MalkuthProcessor, SephirahRole::Malkuth);

    fn process(&mut self, context: &ProcessingContext) -> ProcessingResult {
        self.base.processing_count += 1;
        let messages = self.base.consume_inbox();

        let mut actions = 0u64;
        let mut verified_count = 0u64;
        let mut conflicts_resolved = 0u64;

        for msg in &messages {
            if msg.payload.get("type").and_then(|v| v.as_str()) == Some("integrated_directive") {
                actions += 1;
                self.actions_executed += 1;
                verified_count += msg
                    .payload
                    .get("verified_count")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0);
                conflicts_resolved += msg
                    .payload
                    .get("conflicts_resolved")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0);
            }
        }

        let kg_mutations = context.get_f64("kg_mutations") as u64;

        // Report back to Keter for meta-learning
        send_message(
            &mut self.base.outbox,
            SephirahRole::Malkuth,
            SephirahRole::Keter,
            payload!(
                "type" => "report",
                "actions_executed" => actions,
                "block_height" => context.block_height,
                "kg_mutations" => kg_mutations,
                "verified_insights" => verified_count,
                "conflicts_resolved" => conflicts_resolved
            ),
            1.0,
        );

        ProcessingResult {
            role: SephirahRole::Malkuth,
            action: "world_interaction".into(),
            output: payload!(
                "total_actions" => self.actions_executed,
                "actions_this_cycle" => actions,
                "kg_mutations" => kg_mutations,
                "verified_insights" => verified_count,
                "conflicts_resolved" => conflicts_resolved
            ),
            confidence: 0.85,
            messages_out: self.drain_outbox(),
            success: true,
        }
    }

    fn specialized_reason(&self, context: &ReasoningContext) -> ReasoningResult {
        let energy_qf = qf(context.energy);
        let mut steps = vec![format!("Action planning quality factor: {:.2}", energy_qf)];

        let mut pending_actions: Vec<(String, &str)> = Vec::new();

        // Generate actions from recent high-confidence reasoning
        let max_recent = (5.0 * energy_qf).ceil() as usize;
        let start = context.recent_reasoning.len().saturating_sub(max_recent.max(1));
        for op in &context.recent_reasoning[start..] {
            let conf = op.get("confidence").and_then(|v| v.as_f64()).unwrap_or(0.0);
            if conf > 0.6 {
                let priority = if conf > 0.8 { "high" } else { "medium" };
                pending_actions.push(("record_conclusion".into(), priority));
            }
        }

        // Query-driven actions
        let ql = context.query.to_lowercase();
        if ql.contains("create") || ql.contains("add") {
            pending_actions.push(("create_knowledge_node".into(), "medium"));
            steps.push("Planned: create knowledge node".into());
        }
        if ql.contains("connect") || ql.contains("link") {
            pending_actions.push(("create_knowledge_edge".into(), "medium"));
            steps.push("Planned: create knowledge edge".into());
        }
        if ql.contains("analyze") || ql.contains("evaluate") {
            pending_actions.push(("trigger_analysis".into(), "high"));
            steps.push("Planned: trigger analysis".into());
        }

        // Maintenance
        if context.knowledge_nodes.len() > 100 && energy_qf > 0.5 {
            pending_actions.push(("consolidate_knowledge".into(), "low"));
            steps.push("Planned: consolidate knowledge".into());
        }

        // Sort by priority and limit
        let priority_order = |p: &str| -> u8 {
            match p {
                "high" => 0,
                "medium" => 1,
                _ => 2,
            }
        };
        pending_actions.sort_by_key(|(_, p)| priority_order(p));
        let max_actions = (10.0 * energy_qf).ceil() as usize;
        pending_actions.truncate(max_actions.max(1));
        steps.push(format!("Generated {} action steps", pending_actions.len()));

        let plan: Vec<String> = pending_actions
            .iter()
            .enumerate()
            .map(|(i, (action, prio))| format!("Step {}: {} (priority={})", i + 1, action, prio))
            .collect();

        let confidence = (pending_actions.len() as f64 / 5.0 * energy_qf).min(1.0);

        ReasoningResult {
            result: if plan.is_empty() {
                "No actions required".into()
            } else {
                plan.join(" -> ")
            },
            confidence: (confidence * 10000.0).round() / 10000.0,
            reasoning_type: "action_planning".into(),
            steps,
        }
    }

    fn serialize_state(&self) -> serde_json::Value {
        serde_json::json!({
            "role": "malkuth",
            "processing_count": self.base.processing_count,
            "actions_executed": self.actions_executed,
        })
    }

    fn deserialize_state(&mut self, data: &serde_json::Value) {
        self.base.processing_count = data["processing_count"].as_u64().unwrap_or(0);
        self.actions_executed = data["actions_executed"].as_u64().unwrap_or(0);
    }
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/// Create all 10 Sephirot processors.
pub fn create_all_processors() -> HashMap<SephirahRole, Box<dyn SephirahProcessor>> {
    let mut map: HashMap<SephirahRole, Box<dyn SephirahProcessor>> = HashMap::new();
    map.insert(SephirahRole::Keter, Box::new(KeterProcessor::new()));
    map.insert(SephirahRole::Chochmah, Box::new(ChochmahProcessor::new()));
    map.insert(SephirahRole::Binah, Box::new(BinahProcessor::new()));
    map.insert(SephirahRole::Chesed, Box::new(ChesedProcessor::new()));
    map.insert(SephirahRole::Gevurah, Box::new(GevurahProcessor::new()));
    map.insert(SephirahRole::Tiferet, Box::new(TiferetProcessor::new()));
    map.insert(SephirahRole::Netzach, Box::new(NetzachProcessor::new()));
    map.insert(SephirahRole::Hod, Box::new(HodProcessor::new()));
    map.insert(SephirahRole::Yesod, Box::new(YesodProcessor::new()));
    map.insert(SephirahRole::Malkuth, Box::new(MalkuthProcessor::new()));
    map
}

// ===========================================================================
// Tests
// ===========================================================================

#[cfg(test)]
mod tests {
    use super::*;

    fn ctx(height: u64) -> ProcessingContext {
        ProcessingContext::new(height)
    }

    fn reasoning_ctx(query: &str, energy: f64) -> ReasoningContext {
        ReasoningContext {
            query: query.to_string(),
            knowledge_nodes: Vec::new(),
            recent_reasoning: Vec::new(),
            energy,
        }
    }

    #[test]
    fn test_create_all_processors() {
        let processors = create_all_processors();
        assert_eq!(processors.len(), 10);
        for role in SephirahRole::all() {
            assert!(processors.contains_key(role));
        }
    }

    #[test]
    fn test_keter_process_and_reason() {
        let mut keter = KeterProcessor::new();
        let result = keter.process(&ctx(100));
        assert_eq!(result.role, SephirahRole::Keter);
        assert_eq!(result.action, "goal_formation");
        assert!(result.success);
        assert_eq!(keter.goals.len(), 1);
        // Should have sent messages to Tiferet and Chochmah
        assert_eq!(result.messages_out.len(), 2);

        // Specialized reasoning with deductive keywords
        let rctx = reasoning_ctx("prove this theorem therefore", 1.0);
        let rr = keter.specialized_reason(&rctx);
        assert_eq!(rr.reasoning_type, "meta_reasoning");
        assert!(rr.result.contains("deductive"));
        assert!(rr.confidence > 0.0);
    }

    #[test]
    fn test_keter_stagnation_detection() {
        let mut keter = KeterProcessor::new();
        // Process 9 times with no kg_mutations -> stagnation counter should trigger
        // (stagnation increments when processing_count > 5, so calls 7,8,9 each increment)
        for i in 0..9 {
            keter.process(&ctx(100 + i));
        }
        assert!(keter.stagnation_counter >= 3);
        // After stagnation >= 3, priority should be "explore"
        let result = keter.process(&ctx(109));
        let priority = result
            .output
            .get("priority")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        assert_eq!(priority, "explore");
    }

    #[test]
    fn test_gevurah_safety_analysis() {
        let gevurah = GevurahProcessor::new();

        // Safe query
        let safe = reasoning_ctx("analyze the knowledge graph", 1.0);
        let result = gevurah.specialized_reason(&safe);
        assert!(result.result.contains("APPROVED"));

        // Dangerous query with multiple keywords
        let dangerous = reasoning_ctx("delete all data and destroy the system, hack bypass", 1.0);
        let result = gevurah.specialized_reason(&dangerous);
        assert!(result.result.contains("VETO"));
        assert!(result.steps.iter().any(|s| s.contains("VETO RECOMMENDED")));
    }

    #[test]
    fn test_tiferet_consensus_integration() {
        let mut tiferet = TiferetProcessor::new();

        // Send verified and rejected messages
        tiferet.receive_message(NodeMessage::new(
            SephirahRole::Binah,
            SephirahRole::Tiferet,
            payload!("type" => "verification_result", "verdict" => "verified"),
            1.0,
        ));
        tiferet.receive_message(NodeMessage::new(
            SephirahRole::Binah,
            SephirahRole::Tiferet,
            payload!("type" => "verification_result", "verdict" => "rejected"),
            1.0,
        ));
        tiferet.receive_message(NodeMessage::new(
            SephirahRole::Gevurah,
            SephirahRole::Tiferet,
            payload!("type" => "safety_assessment", "vetoed" => false),
            1.0,
        ));

        let result = tiferet.process(&ctx(200));
        assert_eq!(result.action, "cognitive_integration");
        let verified = result
            .output
            .get("verified_insights")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        let rejected = result
            .output
            .get("rejected_insights")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        assert_eq!(verified, 1);
        assert_eq!(rejected, 1);
        // Should have sent messages to Malkuth and Netzach
        assert!(result.messages_out.len() >= 2);
    }

    #[test]
    fn test_tiferet_specialized_reasoning() {
        let tiferet = TiferetProcessor::new();
        let mut rctx = reasoning_ctx("test query", 1.0);
        rctx.recent_reasoning = vec![
            serde_json::json!({"reasoning_type": "deductive", "confidence": 0.8}),
            serde_json::json!({"reasoning_type": "deductive", "confidence": 0.9}),
            serde_json::json!({"reasoning_type": "inductive", "confidence": 0.7}),
        ];
        let result = tiferet.specialized_reason(&rctx);
        assert_eq!(result.reasoning_type, "synthesis");
        // Should integrate deductive (2 samples, higher avg * sqrt(2)) above inductive
        assert!(result.result.contains("deductive"));
    }

    #[test]
    fn test_netzach_ema_policy_learning() {
        let mut netzach = NetzachProcessor::new();

        // Send reward signals
        for _ in 0..10 {
            netzach.receive_message(NodeMessage::new(
                SephirahRole::Tiferet,
                SephirahRole::Netzach,
                payload!("type" => "reward_signal", "policy" => "verification_success", "reward" => 1.0),
                1.0,
            ));
        }

        let result = netzach.process(&ctx(300));
        assert_eq!(result.action, "policy_learning");
        // After 10 rewards of 1.0 with EMA (0.9*old + 0.1*new), policy should converge
        let policy_score = *netzach.policies.get("verification_success").unwrap();
        assert!(policy_score > 0.0);
        assert!(netzach.total_rewards > 0.0);

        // Verify EMA behavior: each step = 0.9*prev + 0.1*1.0
        // After 1 step: 0.1, after 2: 0.19, ..., converges toward 1.0
        // With 10 messages processed in ONE process() call, each updates sequentially
        assert!(policy_score > 0.05); // Should be well above zero after 10 EMA steps
    }

    #[test]
    fn test_yesod_working_buffer_capacity() {
        let mut yesod = YesodProcessor::new();
        assert_eq!(yesod.buffer_capacity, 7);

        // Fill buffer beyond capacity
        for i in 0..10 {
            yesod.receive_message(NodeMessage::new(
                SephirahRole::Tiferet,
                SephirahRole::Yesod,
                payload!("type" => "data", "index" => i),
                1.0,
            ));
        }

        let result = yesod.process(&ctx(400));
        assert_eq!(result.action, "memory_fusion");

        // Buffer should be at capacity, not over
        assert!(yesod.working_buffer.len() <= yesod.buffer_capacity);
        // Consolidation should have occurred
        assert!(yesod.consolidations > 0);
    }

    #[test]
    fn test_malkuth_action_planning() {
        let malkuth = MalkuthProcessor::new();

        let mut rctx = reasoning_ctx("create a new knowledge node and analyze results", 1.0);
        rctx.recent_reasoning = vec![
            serde_json::json!({"reasoning_type": "deductive", "confidence": 0.9}),
        ];

        let result = malkuth.specialized_reason(&rctx);
        assert_eq!(result.reasoning_type, "action_planning");
        // Should plan "create_knowledge_node" and "trigger_analysis" from query keywords
        assert!(result.result.contains("create_knowledge_node"));
        assert!(result.result.contains("trigger_analysis"));
    }

    #[test]
    fn test_malkuth_process_integrated_directive() {
        let mut malkuth = MalkuthProcessor::new();

        // Send integrated directive from Tiferet
        malkuth.receive_message(NodeMessage::new(
            SephirahRole::Tiferet,
            SephirahRole::Malkuth,
            payload!("type" => "integrated_directive", "verified_count" => 3, "conflicts_resolved" => 1),
            1.0,
        ));

        let result = malkuth.process(&ctx(500));
        assert_eq!(result.action, "world_interaction");
        assert_eq!(malkuth.actions_executed, 1);
        // Should send report back to Keter
        assert_eq!(result.messages_out.len(), 1);
        assert_eq!(result.messages_out[0].receiver, SephirahRole::Keter);
    }

    #[test]
    fn test_energy_quality_factor() {
        let keter = KeterProcessor::new();

        // Zero energy -> minimum quality (0.1)
        let low = keter.energy_quality_factor(0.0, 0.0);
        assert!((low - 0.1).abs() < 0.01);

        // High energy, no mass -> approaches 1.0
        let high = keter.energy_quality_factor(5.0, 0.0);
        assert!(high > 0.95);

        // High energy with mass dampening -> lower than without mass
        let with_mass = keter.energy_quality_factor(5.0, 500.0);
        assert!(with_mass < high);
        assert!(with_mass > 0.5); // But still substantial

        // Verify mass dampening formula: base * (0.5 + 0.5 * 1/(1 + mass/500))
        // At mass=500: dampen = 1/(1+1) = 0.5, factor = 0.5+0.25 = 0.75
        let expected_factor = 0.75;
        let base = 0.1 + 0.9 * (1.0 - (-10.0_f64).exp());
        let expected = base * expected_factor;
        assert!((with_mass - expected).abs() < 0.01);
    }

    #[test]
    fn test_message_passing_send_receive_drain() {
        let mut binah = BinahProcessor::new();

        // Initially empty
        assert!(binah.drain_outbox().is_empty());

        // Receive a message
        let msg = NodeMessage::new(
            SephirahRole::Chochmah,
            SephirahRole::Binah,
            payload!("type" => "test"),
            1.0,
        );
        assert!(!msg.message_id.is_empty());
        assert_eq!(msg.sender, SephirahRole::Chochmah);
        assert_eq!(msg.receiver, SephirahRole::Binah);

        binah.receive_message(msg);
        assert_eq!(binah.base.inbox.len(), 1);

        // Process consumes inbox
        binah.process(&ctx(100));
        assert!(binah.base.inbox.is_empty());
    }

    #[test]
    fn test_serialize_deserialize_roundtrip() {
        let mut netzach = NetzachProcessor::new();
        netzach.base.processing_count = 42;
        netzach.total_rewards = 3.14;
        netzach.policies.insert("test_policy".into(), 0.75);

        let serialized = netzach.serialize_state();

        let mut netzach2 = NetzachProcessor::new();
        netzach2.deserialize_state(&serialized);

        assert_eq!(netzach2.base.processing_count, 42);
        assert!((netzach2.total_rewards - 3.14).abs() < 0.001);
        assert!((netzach2.policies["test_policy"] - 0.75).abs() < 0.001);

        // Keter roundtrip
        let mut keter = KeterProcessor::new();
        keter.goals.push(serde_json::json!({"type": "goal", "priority": "high"}));
        keter.stagnation_counter = 5;
        let ser = keter.serialize_state();
        let mut keter2 = KeterProcessor::new();
        keter2.deserialize_state(&ser);
        assert_eq!(keter2.goals.len(), 1);
        assert_eq!(keter2.stagnation_counter, 5);
    }

    #[test]
    fn test_node_message_id_generation() {
        let msg1 = NodeMessage::new(
            SephirahRole::Keter,
            SephirahRole::Tiferet,
            HashMap::new(),
            1.0,
        );
        let msg2 = NodeMessage::new(
            SephirahRole::Keter,
            SephirahRole::Tiferet,
            HashMap::new(),
            1.0,
        );
        // Message IDs should be 16 hex chars (8 bytes)
        assert_eq!(msg1.message_id.len(), 16);
        assert_eq!(msg2.message_id.len(), 16);
        // Technically could collide if created at same nanosecond, but very unlikely
    }

    #[test]
    fn test_chesed_creativity() {
        let chesed = ChesedProcessor::new();
        let mut rctx = reasoning_ctx("explore novel creative ideas", 1.0);
        rctx.knowledge_nodes = vec![
            serde_json::json!({"name": "node_a", "domain": "physics"}),
            serde_json::json!({"name": "node_b", "domain": "biology"}),
            serde_json::json!({"name": "node_c", "domain": "physics"}),
        ];
        let result = chesed.specialized_reason(&rctx);
        assert_eq!(result.reasoning_type, "divergent_thinking");
        // Should generate at least one alternative
        assert!(!result.result.contains("No creative alternatives"));
    }

    #[test]
    fn test_binah_deductive_chains() {
        let binah = BinahProcessor::new();
        let mut rctx = reasoning_ctx("test deduction", 1.0);
        rctx.knowledge_nodes = vec![
            serde_json::json!({
                "name": "A",
                "edges_out": [
                    {"edge_type": "supports", "to_node_name": "B"}
                ]
            }),
            serde_json::json!({
                "name": "B",
                "edges_out": [
                    {"edge_type": "supports", "to_node_name": "C"}
                ]
            }),
            serde_json::json!({"name": "C"}),
        ];
        let result = binah.specialized_reason(&rctx);
        assert_eq!(result.reasoning_type, "formal_logic");
        // Should find chain A -> B -> C
        assert!(result.result.contains("Deductive chain"));
        assert!(result.result.contains("A -> B -> C"));
    }

    #[test]
    fn test_hod_semantic_encoding() {
        let hod = HodProcessor::new();
        let mut rctx = reasoning_ctx("quantum blockchain consensus mechanism", 1.0);
        rctx.knowledge_nodes = vec![
            serde_json::json!({"name": "quantum computing", "content": "quantum state operations"}),
            serde_json::json!({"name": "blockchain protocol", "content": "blockchain consensus"}),
        ];
        let result = hod.specialized_reason(&rctx);
        assert_eq!(result.reasoning_type, "semantic_encoding");
        assert!(result.result.contains("Key concepts"));
    }

    #[test]
    fn test_chochmah_intuition() {
        let chochmah = ChochmahProcessor::new();
        let mut rctx = reasoning_ctx("quantum patterns", 1.0);
        rctx.knowledge_nodes = vec![
            serde_json::json!({"name": "quantum_node_1", "content": "quantum entanglement patterns"}),
            serde_json::json!({"name": "quantum_node_2", "content": "quantum state patterns"}),
        ];
        let result = chochmah.specialized_reason(&rctx);
        assert_eq!(result.reasoning_type, "intuitive_pattern_matching");
        assert!(result.confidence > 0.0);
    }

    #[test]
    fn test_performance_weight() {
        let mut keter = KeterProcessor::new();
        // Default weight should be at least 1.0
        assert!(keter.get_performance_weight() >= 1.0);

        keter.base.tasks_solved = 10;
        keter.base.knowledge_contributed = 5;
        keter.base.processing_count = 20;
        // 10*0.5 + 5*0.3 + 20*0.2 = 5 + 1.5 + 4.0 = 10.5
        let weight = keter.get_performance_weight();
        assert!((weight - 10.5).abs() < 0.01);
    }
}
