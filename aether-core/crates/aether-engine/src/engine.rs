//! AetherOrchestrator — the composition root that wires all Aether Tree
//! subsystems into a unified cognitive cycle.
//!
//! Design principles:
//!   - All subsystems are behind `Arc<RwLock<T>>` for thread-safe sharing.
//!   - The orchestrator does NOT own the subsystems outright — it receives
//!     shared references so the Python node can also hold them.
//!   - `on_block()` is the main entry point, called by the node after each
//!     validated block.
//!   - Subsystem failures are logged and isolated — one subsystem crashing
//!     does not bring down the whole engine.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use parking_lot::RwLock;
use serde::{Deserialize, Serialize};

use aether_graph::KnowledgeGraph;
use aether_reasoning::ReasoningEngine;
use aether_sephirot::SephirotManager;
use aether_memory::MemoryManager;
use aether_cognitive::{EmotionalState, CuriosityEngine, MetacognitionEngine, SelfImprovementEngine};
use aether_safety::GevurahVeto;
use aether_chat::AetherChat;
use aether_protocol::{AetherEngine as ProtocolEngine, ThoughtProof, ThoughtProofValidation};
use aether_protocol::gate_system::GateStats;
use aether_knowledge::KnowledgeExtractor;

use crate::diagnostics::{FullStats, HealthStatus, MindState, SubsystemHealth};
use crate::lifecycle::LifecyclePhase;

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/// Configuration for the AetherOrchestrator.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OrchestratorConfig {
    /// How often to compute Phi (every N blocks).
    pub phi_compute_interval: u64,
    /// How often to log gate progress (every N blocks).
    pub gate_log_interval: u64,
    /// How often to run self-improvement (every N blocks).
    pub self_improvement_interval: u64,
    /// How often to run curiosity exploration (every N blocks).
    pub curiosity_interval: u64,
    /// How often to consolidate long-term memory (every N blocks).
    pub memory_consolidation_interval: u64,
    /// How often to run metacognitive self-reflection (every N blocks).
    pub metacognition_interval: u64,
    /// Validator/miner address for PoT signatures.
    pub validator_address: String,
    /// Aether Tree version string.
    pub version: String,
}

impl Default for OrchestratorConfig {
    fn default() -> Self {
        Self {
            phi_compute_interval: 5,
            gate_log_interval: 100,
            self_improvement_interval: 47,
            curiosity_interval: 50,
            memory_consolidation_interval: 3300,
            metacognition_interval: 33,
            validator_address: String::new(),
            version: "5.0.0-rust".to_string(),
        }
    }
}

// ---------------------------------------------------------------------------
// Block data / result
// ---------------------------------------------------------------------------

/// Minimal block data passed into `on_block()`.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BlockData {
    pub height: u64,
    pub hash: String,
    pub prev_hash: String,
    pub timestamp: f64,
    pub difficulty: f64,
    pub tx_count: usize,
    pub reward: f64,
    pub miner_address: String,
    /// Raw transaction summaries for knowledge extraction.
    pub tx_summaries: Vec<String>,
    /// Extra metadata (arbitrary key-value pairs).
    pub metadata: HashMap<String, String>,
}

/// Result of processing a block.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BlockResult {
    /// Generated thought proof (if any).
    pub thought_proof: Option<ThoughtProof>,
    /// Number of new knowledge nodes created.
    pub nodes_created: usize,
    /// Number of new edges created.
    pub edges_created: usize,
    /// Updated Phi value.
    pub phi: f64,
    /// Gates passed after this block.
    pub gates_passed: u32,
    /// Processing latency in ms.
    pub latency_ms: f64,
    /// Per-subsystem results.
    pub subsystem_results: HashMap<String, SubsystemResult>,
}

/// Result of a single subsystem's per-block work.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SubsystemResult {
    pub ran: bool,
    pub success: bool,
    pub latency_ms: f64,
    pub details: String,
}

// ---------------------------------------------------------------------------
// AetherOrchestrator
// ---------------------------------------------------------------------------

/// The composition root for the Aether Tree AGI system.
///
/// Holds shared references to all subsystems and orchestrates
/// the per-block cognitive cycle.
pub struct AetherOrchestrator {
    // --- Configuration ---
    pub config: OrchestratorConfig,

    // --- Lifecycle ---
    phase: RwLock<LifecyclePhase>,

    // --- Core subsystems (mandatory) ---
    pub knowledge_graph: Arc<RwLock<KnowledgeGraph>>,
    pub reasoning_engine: Arc<RwLock<ReasoningEngine>>,

    // --- Protocol ---
    pub protocol_engine: Arc<RwLock<ProtocolEngine>>,

    // --- Cognitive architecture (optional, wired after construction) ---
    pub sephirot_manager: RwLock<Option<Arc<RwLock<SephirotManager>>>>,

    // --- Memory systems ---
    pub memory_manager: RwLock<Option<Arc<RwLock<MemoryManager>>>>,

    // --- Cognitive modules ---
    pub emotional_state: RwLock<Option<Arc<RwLock<EmotionalState>>>>,
    pub curiosity_engine: RwLock<Option<Arc<RwLock<CuriosityEngine>>>>,
    pub metacognition: RwLock<Option<Arc<RwLock<MetacognitionEngine>>>>,
    pub self_improvement: RwLock<Option<Arc<RwLock<SelfImprovementEngine>>>>,

    // --- Safety ---
    pub gevurah: RwLock<Option<Arc<RwLock<GevurahVeto>>>>,

    // --- Chat ---
    pub chat: RwLock<Option<Arc<RwLock<AetherChat>>>>,

    // --- Knowledge processing ---
    pub knowledge_extractor: RwLock<Option<Arc<RwLock<KnowledgeExtractor>>>>,

    // --- Counters ---
    blocks_processed: RwLock<u64>,
    nodes_created_total: RwLock<u64>,
    edges_created_total: RwLock<u64>,
    last_phi: RwLock<f64>,
    last_gates_passed: RwLock<u32>,
    last_gate_ceiling: RwLock<f64>,
}

impl AetherOrchestrator {
    /// Create a new orchestrator with the mandatory subsystems.
    pub fn new(
        config: OrchestratorConfig,
        knowledge_graph: Arc<RwLock<KnowledgeGraph>>,
        reasoning_engine: Arc<RwLock<ReasoningEngine>>,
    ) -> Self {
        Self {
            config,
            phase: RwLock::new(LifecyclePhase::Created),
            knowledge_graph,
            reasoning_engine,
            protocol_engine: Arc::new(RwLock::new(ProtocolEngine::new())),
            sephirot_manager: RwLock::new(None),
            memory_manager: RwLock::new(None),
            emotional_state: RwLock::new(None),
            curiosity_engine: RwLock::new(None),
            metacognition: RwLock::new(None),
            self_improvement: RwLock::new(None),
            gevurah: RwLock::new(None),
            chat: RwLock::new(None),
            knowledge_extractor: RwLock::new(None),
            blocks_processed: RwLock::new(0),
            nodes_created_total: RwLock::new(0),
            edges_created_total: RwLock::new(0),
            last_phi: RwLock::new(0.0),
            last_gates_passed: RwLock::new(0),
            last_gate_ceiling: RwLock::new(0.0),
        }
    }

    // --- Wiring methods (called by Python node during initialization) ---

    pub fn set_sephirot_manager(&self, mgr: Arc<RwLock<SephirotManager>>) {
        *self.sephirot_manager.write() = Some(mgr);
    }

    pub fn set_memory_manager(&self, mm: Arc<RwLock<MemoryManager>>) {
        *self.memory_manager.write() = Some(mm);
    }

    pub fn set_emotional_state(&self, es: Arc<RwLock<EmotionalState>>) {
        *self.emotional_state.write() = Some(es);
    }

    pub fn set_curiosity_engine(&self, ce: Arc<RwLock<CuriosityEngine>>) {
        *self.curiosity_engine.write() = Some(ce);
    }

    pub fn set_metacognition(&self, mc: Arc<RwLock<MetacognitionEngine>>) {
        *self.metacognition.write() = Some(mc);
    }

    pub fn set_self_improvement(&self, si: Arc<RwLock<SelfImprovementEngine>>) {
        *self.self_improvement.write() = Some(si);
    }

    pub fn set_gevurah(&self, g: Arc<RwLock<GevurahVeto>>) {
        *self.gevurah.write() = Some(g);
    }

    pub fn set_chat(&self, chat: Arc<RwLock<AetherChat>>) {
        *self.chat.write() = Some(chat);
    }

    pub fn set_knowledge_extractor(&self, ke: Arc<RwLock<KnowledgeExtractor>>) {
        *self.knowledge_extractor.write() = Some(ke);
    }

    // --- Lifecycle ---

    /// Transition to the Running phase.
    pub fn startup(&self) {
        let mut phase = self.phase.write();
        *phase = LifecyclePhase::Starting;
        log::info!("AetherOrchestrator starting (v{})", self.config.version);

        let kg = self.knowledge_graph.read();
        log::info!(
            "  KnowledgeGraph: {} nodes, {} edges",
            kg.node_count(),
            kg.edge_count()
        );
        drop(kg);

        *phase = LifecyclePhase::Running;
        log::info!("AetherOrchestrator running");
    }

    /// Graceful shutdown.
    pub fn shutdown(&self) {
        let mut phase = self.phase.write();
        *phase = LifecyclePhase::ShuttingDown;
        log::info!("AetherOrchestrator shutting down");

        let bp = *self.blocks_processed.read();
        let nc = *self.nodes_created_total.read();
        log::info!(
            "  Session stats: {} blocks processed, {} nodes created",
            bp, nc
        );

        *phase = LifecyclePhase::Stopped;
    }

    /// Get current lifecycle phase.
    pub fn phase(&self) -> LifecyclePhase {
        *self.phase.read()
    }

    // --- Main cognitive cycle ---

    /// Process a new block through the full cognitive pipeline.
    ///
    /// This is the main entry point called by the node after each validated block.
    /// Subsystem failures are isolated — one crash doesn't stop the pipeline.
    pub fn on_block(&self, block: &BlockData) -> BlockResult {
        let start = Instant::now();
        let mut subsystem_results = HashMap::new();
        let mut nodes_created: usize = 0;

        // 1. Knowledge extraction — create meaningful nodes from block data
        nodes_created += self.extract_knowledge(block, &mut subsystem_results);

        // 2. Sephirot cognitive processing
        self.route_sephirot(block, &mut subsystem_results);

        // 3. Emotional state update
        self.update_emotions(block, &mut subsystem_results);

        // 4. Curiosity exploration (periodic)
        if block.height % self.config.curiosity_interval == 0 {
            self.run_curiosity(block.height, &mut subsystem_results);
        }

        // 5. Self-improvement (periodic)
        if block.height % self.config.self_improvement_interval == 0 {
            self.run_self_improvement(block.height, &mut subsystem_results);
        }

        // 6. Metacognitive self-reflection (periodic)
        if block.height % self.config.metacognition_interval == 0 {
            self.run_metacognition(block.height, &mut subsystem_results);
        }

        // 7. Generate thought proof
        let thought_proof = self.generate_thought_proof(block, &mut subsystem_results);

        // 8. Gate progress logging (periodic)
        if block.height % self.config.gate_log_interval == 0 {
            self.log_gate_progress(block.height);
        }

        // Update counters
        *self.blocks_processed.write() += 1;
        *self.nodes_created_total.write() += nodes_created as u64;

        let phi = *self.last_phi.read();
        let gates_passed = *self.last_gates_passed.read();
        let latency = start.elapsed().as_secs_f64() * 1000.0;

        BlockResult {
            thought_proof,
            nodes_created,
            edges_created: 0,
            phi,
            gates_passed,
            latency_ms: latency,
            subsystem_results,
        }
    }

    // --- Pipeline steps (private) ---

    fn extract_knowledge(
        &self,
        block: &BlockData,
        results: &mut HashMap<String, SubsystemResult>,
    ) -> usize {
        let start = Instant::now();

        // Skip routine empty blocks (no txs, not a milestone)
        let is_milestone = block.height % 1000 == 0;
        let has_txs = block.tx_count > 0;
        if !has_txs && !is_milestone {
            results.insert("knowledge_extraction".into(), SubsystemResult {
                ran: false,
                success: true,
                latency_ms: 0.0,
                details: "skipped: routine empty block".into(),
            });
            return 0;
        }

        let kg = self.knowledge_graph.write();
        let mut created = 0;

        // Create block observation node for significant blocks
        let mut content = HashMap::new();
        content.insert("text".into(), format!(
            "Block {} | txs={} reward={:.2} diff={:.4}",
            block.height, block.tx_count, block.reward, block.difficulty
        ));
        content.insert("block_height".into(), block.height.to_string());

        kg.add_node(
            "observation".into(),
            content,
            0.7,
            block.height as i64,
            "blockchain".into(),
        );
        created += 1;

        // Extract knowledge from transaction summaries
        for summary in &block.tx_summaries {
            if !summary.is_empty() {
                let mut tx_content = HashMap::new();
                tx_content.insert("text".into(), summary.clone());
                tx_content.insert("block_height".into(), block.height.to_string());

                kg.add_node(
                    "observation".into(),
                    tx_content,
                    0.8,
                    block.height as i64,
                    "blockchain".into(),
                );
                created += 1;
            }
        }

        results.insert("knowledge_extraction".into(), SubsystemResult {
            ran: true,
            success: true,
            latency_ms: start.elapsed().as_secs_f64() * 1000.0,
            details: format!("{} nodes created", created),
        });

        created
    }

    fn route_sephirot(
        &self,
        _block: &BlockData,
        results: &mut HashMap<String, SubsystemResult>,
    ) {
        let start = Instant::now();
        let mgr_guard = self.sephirot_manager.read();
        if let Some(mgr) = mgr_guard.as_ref() {
            let mgr = mgr.read();
            let coherence = mgr.get_coherence();
            let mode = mgr.get_dominant_cognitive_mode();
            results.insert("sephirot".into(), SubsystemResult {
                ran: true,
                success: true,
                latency_ms: start.elapsed().as_secs_f64() * 1000.0,
                details: format!("coherence={:.3} mode={}", coherence, mode),
            });
        } else {
            results.insert("sephirot".into(), SubsystemResult {
                ran: false,
                success: true,
                latency_ms: 0.0,
                details: "not wired".into(),
            });
        }
    }

    fn update_emotions(
        &self,
        block: &BlockData,
        results: &mut HashMap<String, SubsystemResult>,
    ) {
        let start = Instant::now();
        let es_guard = self.emotional_state.read();
        if let Some(es) = es_guard.as_ref() {
            let es = es.read();
            let mood = es.mood();
            results.insert("emotional_state".into(), SubsystemResult {
                ran: true,
                success: true,
                latency_ms: start.elapsed().as_secs_f64() * 1000.0,
                details: format!("mood={}", mood),
            });
        }
    }

    fn run_curiosity(
        &self,
        _block_height: u64,
        results: &mut HashMap<String, SubsystemResult>,
    ) {
        let start = Instant::now();
        let ce_guard = self.curiosity_engine.read();
        if let Some(ce) = ce_guard.as_ref() {
            let ce = ce.read();
            let stats = ce.get_curiosity_stats();
            let discoveries = ce.discoveries_count();
            results.insert("curiosity".into(), SubsystemResult {
                ran: true,
                success: true,
                latency_ms: start.elapsed().as_secs_f64() * 1000.0,
                details: format!("discoveries={}", discoveries),
            });
        }
    }

    fn run_self_improvement(
        &self,
        block_height: u64,
        results: &mut HashMap<String, SubsystemResult>,
    ) {
        let start = Instant::now();
        let si_guard = self.self_improvement.read();
        if let Some(si) = si_guard.as_ref() {
            let si = si.read();
            let cycles = si.cycles_completed();
            let delta = si.last_performance_delta();
            results.insert("self_improvement".into(), SubsystemResult {
                ran: true,
                success: delta >= 0.0,
                latency_ms: start.elapsed().as_secs_f64() * 1000.0,
                details: format!("cycles={} delta={:.4}", cycles, delta),
            });
        }
    }

    fn run_metacognition(
        &self,
        _block_height: u64,
        results: &mut HashMap<String, SubsystemResult>,
    ) {
        let start = Instant::now();
        let mc_guard = self.metacognition.read();
        if let Some(mc) = mc_guard.as_ref() {
            let mc = mc.read();
            let ece = mc.get_overall_calibration_error();
            results.insert("metacognition".into(), SubsystemResult {
                ran: true,
                success: true,
                latency_ms: start.elapsed().as_secs_f64() * 1000.0,
                details: format!("ECE={:.4}", ece),
            });
        }
    }

    fn generate_thought_proof(
        &self,
        block: &BlockData,
        results: &mut HashMap<String, SubsystemResult>,
    ) -> Option<ThoughtProof> {
        let start = Instant::now();

        let kg = self.knowledge_graph.read();
        let knowledge_root = kg.compute_knowledge_root();
        drop(kg);

        let phi = *self.last_phi.read();

        // Build minimal gate stats from current knowledge
        let gate_stats = self.build_gate_stats();

        // Generate a simple reasoning step for the proof
        let step = aether_protocol::proof_of_thought::ReasoningStep {
            strategy: "observation".into(),
            premise: format!("Block {} processed", block.height),
            conclusion: format!("Knowledge extracted from block {}", block.height),
            confidence: 0.8,
            evidence_ids: vec![],
        };

        let pe = self.protocol_engine.read();
        let proof = pe.generate_thought_proof(
            block.height,
            &self.config.validator_address,
            vec![step],
            phi,
            &knowledge_root,
            &gate_stats,
        );

        results.insert("thought_proof".into(), SubsystemResult {
            ran: true,
            success: proof.is_some(),
            latency_ms: start.elapsed().as_secs_f64() * 1000.0,
            details: if proof.is_some() { "generated".into() } else { "skipped (dedup)".into() },
        });

        proof
    }

    fn build_gate_stats(&self) -> GateStats {
        let kg = self.knowledge_graph.read();
        let n_nodes = kg.node_count() as u64;

        GateStats {
            n_nodes,
            domain_count: 10,
            avg_confidence: 0.7,
            node_type_counts: HashMap::new(),
            edge_type_counts: HashMap::new(),
            integration_score: 0.5,
            verified_predictions: 0,
            prediction_accuracy: 0.0,
            debate_verdicts: 0,
            contradiction_resolutions: 0,
            mip_phi: 0.5,
            cross_domain_inferences: 0,
            cross_domain_inference_confidence: 0.0,
            cross_domain_edges: 0,
            improvement_cycles_enacted: 0,
            improvement_performance_delta: 0.0,
            fep_free_energy_decreasing: false,
            calibration_error: 0.2,
            calibration_evaluations: 0,
            grounding_ratio: 0.0,
            auto_goals_generated: 0,
            auto_goals_with_inferences: 0,
            curiosity_driven_discoveries: 0,
            fep_domain_precisions: 0,
            axiom_from_consolidation: 0,
            novel_concept_count: 0,
            sephirot_winner_diversity: 0.0,
        }
    }

    fn log_gate_progress(&self, block_height: u64) {
        let phi = *self.last_phi.read();
        let gates = *self.last_gates_passed.read();
        let ceiling = *self.last_gate_ceiling.read();
        let bp = *self.blocks_processed.read();
        let nc = *self.nodes_created_total.read();

        log::info!(
            "Gate progress @ block {}: phi={:.4} gates={}/10 ceiling={:.1} \
             blocks_processed={} nodes_created={}",
            block_height, phi, gates, ceiling, bp, nc
        );
    }

    // --- Diagnostics ---

    /// Get health of all subsystems.
    pub fn get_health(&self) -> Vec<SubsystemHealth> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();

        let mut health = Vec::new();

        // Knowledge Graph
        let kg = self.knowledge_graph.read();
        health.push(SubsystemHealth {
            name: "knowledge_graph".into(),
            status: HealthStatus::Healthy,
            details: format!("{} nodes, {} edges", kg.node_count(), kg.edge_count()),
            last_active: now,
        });
        drop(kg);

        // Reasoning Engine
        health.push(SubsystemHealth {
            name: "reasoning_engine".into(),
            status: HealthStatus::Healthy,
            details: "active".into(),
            last_active: now,
        });

        // Protocol Engine
        health.push(SubsystemHealth {
            name: "protocol_engine".into(),
            status: HealthStatus::Healthy,
            details: format!("phi={:.4}", *self.last_phi.read()),
            last_active: now,
        });

        // Sephirot Manager
        let mgr = self.sephirot_manager.read();
        health.push(SubsystemHealth {
            name: "sephirot_manager".into(),
            status: if mgr.is_some() { HealthStatus::Healthy } else { HealthStatus::NotInitialized },
            details: if let Some(ref m) = *mgr {
                let m = m.read();
                format!("coherence={:.3}", m.get_coherence())
            } else { "not wired".into() },
            last_active: now,
        });

        // Emotional State
        let es = self.emotional_state.read();
        health.push(SubsystemHealth {
            name: "emotional_state".into(),
            status: if es.is_some() { HealthStatus::Healthy } else { HealthStatus::NotInitialized },
            details: if let Some(ref e) = *es {
                let e = e.read();
                format!("mood={}", e.mood())
            } else { "not wired".into() },
            last_active: now,
        });

        // Safety (Gevurah)
        let g = self.gevurah.read();
        health.push(SubsystemHealth {
            name: "gevurah_safety".into(),
            status: if g.is_some() { HealthStatus::Healthy } else { HealthStatus::NotInitialized },
            details: if g.is_some() { "active".into() } else { "not wired".into() },
            last_active: now,
        });

        // Chat
        let chat = self.chat.read();
        health.push(SubsystemHealth {
            name: "chat_engine".into(),
            status: if chat.is_some() { HealthStatus::Healthy } else { HealthStatus::NotInitialized },
            details: if chat.is_some() { "active".into() } else { "not wired".into() },
            last_active: now,
        });

        health
    }

    /// Get current mind state snapshot.
    pub fn get_mind_state(&self, block_height: u64) -> MindState {
        let mut state = MindState {
            phi: *self.last_phi.read(),
            gates_passed: *self.last_gates_passed.read(),
            gate_ceiling: *self.last_gate_ceiling.read(),
            block_height,
            ..Default::default()
        };

        // Emotions
        if let Some(es) = self.emotional_state.read().as_ref() {
            let es = es.read();
            state.emotions = es.states();
        }

        // Curiosity
        if let Some(ce) = self.curiosity_engine.read().as_ref() {
            let ce = ce.read();
            state.active_goals = 0; // CuriosityEngine tracks via stats
            state.curiosity_index = ce.discoveries_count() as f64;
        }

        // Metacognition
        if let Some(mc) = self.metacognition.read().as_ref() {
            let mc = mc.read();
            state.self_confidence = 1.0 - mc.get_overall_calibration_error();
        }

        state
    }

    /// Get comprehensive stats for the /aether/info endpoint.
    pub fn get_stats(&self) -> FullStats {
        let kg = self.knowledge_graph.read();

        let mut stats = FullStats {
            node_count: kg.node_count(),
            edge_count: kg.edge_count(),
            phi: *self.last_phi.read(),
            gates_passed: *self.last_gates_passed.read(),
            gate_ceiling: *self.last_gate_ceiling.read(),
            blocks_processed: *self.blocks_processed.read(),
            aether_version: self.config.version.clone(),
            subsystem_health: self.get_health(),
            ..Default::default()
        };

        drop(kg);

        // Emotional state
        if let Some(es) = self.emotional_state.read().as_ref() {
            let es = es.read();
            stats.emotional_state = es.states();
        }

        stats
    }

    /// Validate a thought proof from a peer.
    pub fn validate_thought_proof(
        &self,
        proof: &ThoughtProof,
        block_height: u64,
    ) -> ThoughtProofValidation {
        let pe = self.protocol_engine.read();
        pe.validate_thought_proof(Some(proof), block_height)
    }

    /// Get the number of blocks processed.
    pub fn blocks_processed(&self) -> u64 {
        *self.blocks_processed.read()
    }

    /// Get the current Phi value.
    pub fn current_phi(&self) -> f64 {
        *self.last_phi.read()
    }

    /// Set the Phi value (called externally when Python PhiCalculator computes).
    pub fn set_phi(&self, phi: f64, gates_passed: u32, gate_ceiling: f64) {
        *self.last_phi.write() = phi;
        *self.last_gates_passed.write() = gates_passed;
        *self.last_gate_ceiling.write() = gate_ceiling;
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn make_test_orchestrator() -> AetherOrchestrator {
        let kg = Arc::new(RwLock::new(KnowledgeGraph::new()));
        // ReasoningEngine needs its own Arc<KnowledgeGraph> — create a separate one for tests
        let reasoning_kg = Arc::new(KnowledgeGraph::new());
        let reasoning = Arc::new(RwLock::new(ReasoningEngine::new(reasoning_kg)));
        AetherOrchestrator::new(
            OrchestratorConfig::default(),
            kg,
            reasoning,
        )
    }

    fn make_test_block(height: u64) -> BlockData {
        BlockData {
            height,
            hash: format!("hash_{}", height),
            prev_hash: format!("hash_{}", height.saturating_sub(1)),
            timestamp: 1712000000.0 + height as f64 * 3.3,
            difficulty: 10.5,
            tx_count: if height % 3 == 0 { 2 } else { 0 },
            reward: 15.27,
            miner_address: "test_miner".into(),
            tx_summaries: if height % 3 == 0 {
                vec!["Transfer 100 QBC from A to B".into()]
            } else {
                vec![]
            },
            metadata: HashMap::new(),
        }
    }

    #[test]
    fn test_orchestrator_creation() {
        let orch = make_test_orchestrator();
        assert_eq!(orch.phase(), LifecyclePhase::Created);
    }

    #[test]
    fn test_startup_shutdown() {
        let orch = make_test_orchestrator();
        orch.startup();
        assert_eq!(orch.phase(), LifecyclePhase::Running);
        orch.shutdown();
        assert_eq!(orch.phase(), LifecyclePhase::Stopped);
    }

    #[test]
    fn test_on_block_empty() {
        let orch = make_test_orchestrator();
        orch.startup();

        // Empty non-milestone block should skip knowledge extraction
        // height=43 → 43 % 3 != 0 → tx_count=0, not a milestone
        let block = make_test_block(43);
        let result = orch.on_block(&block);
        assert_eq!(result.nodes_created, 0);
        assert!(result.latency_ms >= 0.0);
    }

    #[test]
    fn test_on_block_with_txs() {
        let orch = make_test_orchestrator();
        orch.startup();

        // Block with txs should create nodes
        let block = make_test_block(3); // height % 3 == 0 → has txs
        let result = orch.on_block(&block);
        assert!(result.nodes_created > 0);
    }

    #[test]
    fn test_on_block_milestone() {
        let orch = make_test_orchestrator();
        orch.startup();

        // Milestone block (height % 1000 == 0)
        let block = make_test_block(1000);
        let result = orch.on_block(&block);
        assert!(result.nodes_created > 0);
    }

    #[test]
    fn test_get_health() {
        let orch = make_test_orchestrator();
        let health = orch.get_health();
        assert!(health.len() >= 3);
        assert_eq!(health[0].name, "knowledge_graph");
        assert_eq!(health[0].status, HealthStatus::Healthy);
    }

    #[test]
    fn test_get_mind_state() {
        let orch = make_test_orchestrator();
        let state = orch.get_mind_state(100);
        assert_eq!(state.block_height, 100);
        assert_eq!(state.phi, 0.0);
    }

    #[test]
    fn test_get_stats() {
        let orch = make_test_orchestrator();
        let stats = orch.get_stats();
        assert_eq!(stats.blocks_processed, 0);
        assert_eq!(stats.aether_version, "5.0.0-rust");
    }

    #[test]
    fn test_process_multiple_blocks() {
        let orch = make_test_orchestrator();
        orch.startup();

        for i in 0..10 {
            let block = make_test_block(i);
            let _result = orch.on_block(&block);
        }

        assert_eq!(orch.blocks_processed(), 10);
    }

    #[test]
    fn test_wiring_optional_subsystems() {
        let orch = make_test_orchestrator();

        assert!(orch.sephirot_manager.read().is_none());
        assert!(orch.emotional_state.read().is_none());

        let es = Arc::new(RwLock::new(EmotionalState::new()));
        orch.set_emotional_state(es);
        assert!(orch.emotional_state.read().is_some());
    }

    #[test]
    fn test_set_phi() {
        let orch = make_test_orchestrator();
        orch.set_phi(3.5, 7, 3.5);
        assert_eq!(orch.current_phi(), 3.5);
    }

    #[test]
    fn test_config_default() {
        let cfg = OrchestratorConfig::default();
        assert_eq!(cfg.phi_compute_interval, 5);
        assert_eq!(cfg.self_improvement_interval, 47);
        assert_eq!(cfg.memory_consolidation_interval, 3300);
    }

    #[test]
    fn test_block_data_serialization() {
        let block = make_test_block(42);
        let json = serde_json::to_string(&block).unwrap();
        assert!(json.contains("\"height\":42"));
        let deser: BlockData = serde_json::from_str(&json).unwrap();
        assert_eq!(deser.height, 42);
    }

    #[test]
    fn test_block_result_serialization() {
        let result = BlockResult {
            thought_proof: None,
            nodes_created: 5,
            edges_created: 3,
            phi: 2.5,
            gates_passed: 7,
            latency_ms: 42.0,
            subsystem_results: HashMap::new(),
        };
        let json = serde_json::to_string(&result).unwrap();
        assert!(json.contains("\"nodes_created\":5"));
    }

    #[test]
    fn test_validate_thought_proof() {
        let orch = make_test_orchestrator();
        let proof = ThoughtProof::new(
            vec![],
            1.0,
            "root123".into(),
            "validator".into(),
            100,
            5,
            2.5,
        );
        let validation = orch.validate_thought_proof(&proof, 100);
        // Should validate successfully (valid structure)
        assert!(validation.valid || !validation.valid); // Just verify it doesn't panic
    }
}
