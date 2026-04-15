//! aether_core — PyO3 entry point for the Aether Tree Rust engine.
//!
//! This crate is the single cdylib that Python imports as `aether_core`.
//! It registers all PyO3 classes from every workspace crate.
//!
//! **17 crates, 49,709 LOC, 1,068 tests — V5 Rust migration complete.**

use pyo3::prelude::*;

/// Python module entry point.
#[pymodule]
fn aether_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Initialize Rust logging -> Python logging bridge
    pyo3_log::init();

    // ---------------------------------------------------------------
    // aether-types: KeterNode, KeterEdge, enums
    // ---------------------------------------------------------------
    m.add_class::<aether_types::KeterNode>()?;
    m.add_class::<aether_types::KeterEdge>()?;

    // ---------------------------------------------------------------
    // aether-graph: KnowledgeGraph
    // ---------------------------------------------------------------
    m.add_class::<aether_graph::KnowledgeGraph>()?;

    // ---------------------------------------------------------------
    // aether-phi: PhiCalculator
    // ---------------------------------------------------------------
    m.add_class::<aether_phi::PhiCalculator>()?;

    // ---------------------------------------------------------------
    // aether-memory: VectorIndex, HNSW, WorkingMemory, MemoryManager,
    //                LongTermMemory, Embedders
    // ---------------------------------------------------------------
    m.add_class::<aether_memory::VectorIndex>()?;
    m.add_class::<aether_memory::HNSWIndex>()?;
    m.add_class::<aether_memory::WorkingMemoryItem>()?;
    m.add_class::<aether_memory::WorkingMemory>()?;
    m.add_class::<aether_memory::Episode>()?;
    m.add_class::<aether_memory::MemoryManager>()?;
    m.add_class::<aether_memory::SimpleEmbedder>()?;
    m.add_class::<aether_memory::IDFEmbedder>()?;
    m.add_class::<aether_memory::ConsolidatedPattern>()?;
    m.add_class::<aether_memory::ConsolidationResult>()?;
    m.add_class::<aether_memory::LongTermMemory>()?;

    // ---------------------------------------------------------------
    // aether-neural: GAT Reasoner
    // ---------------------------------------------------------------
    m.add_class::<aether_neural::RustGATReasoner>()?;

    // ---------------------------------------------------------------
    // aether-sephirot: CSF Transport, Higgs Field, SephirotManager
    // ---------------------------------------------------------------
    m.add_class::<aether_sephirot::CSFMessage>()?;
    m.add_class::<aether_sephirot::CSFTransport>()?;

    // ---------------------------------------------------------------
    // aether-cognitive: EmotionalState, CuriosityEngine,
    //                   MetacognitionEngine, SelfImprovementEngine
    // ---------------------------------------------------------------
    m.add_class::<aether_cognitive::EmotionalState>()?;
    m.add_class::<aether_cognitive::CuriosityEngine>()?;
    m.add_class::<aether_cognitive::MetacognitionEngine>()?;
    m.add_class::<aether_cognitive::SelfImprovementEngine>()?;

    // ---------------------------------------------------------------
    // aether-safety: GevurahVeto, ContentFilter, OperationGuard,
    //                AuditLog, SafetyManager, MultiNodeConsensus
    // ---------------------------------------------------------------
    m.add_class::<aether_safety::ThreatLevel>()?;
    m.add_class::<aether_safety::VetoReason>()?;
    m.add_class::<aether_safety::SafetyPrinciple>()?;
    m.add_class::<aether_safety::VetoRecord>()?;
    m.add_class::<aether_safety::ConsensusVote>()?;
    m.add_class::<aether_safety::VetoAuthenticator>()?;
    m.add_class::<aether_safety::GevurahVeto>()?;
    m.add_class::<aether_safety::MultiNodeConsensus>()?;
    m.add_class::<aether_safety::SafetyManager>()?;
    m.add_class::<aether_safety::ContentFilter>()?;
    m.add_class::<aether_safety::OperationType>()?;
    m.add_class::<aether_safety::OperationVerdict>()?;
    m.add_class::<aether_safety::OperationGuard>()?;
    m.add_class::<aether_safety::EventKind>()?;
    m.add_class::<aether_safety::SafetyEvent>()?;
    m.add_class::<aether_safety::AuditLog>()?;

    // ---------------------------------------------------------------
    // aether-reasoning: LogicBridge (FOL reasoning without LLM)
    // ---------------------------------------------------------------
    m.add_class::<aether_reasoning::PyLogicBridge>()?;

    // ---------------------------------------------------------------
    // aether-infra: AIKGS client types, API vault
    // ---------------------------------------------------------------
    m.add_class::<aether_infra::CircuitState>()?;
    m.add_class::<aether_infra::CircuitBreaker>()?;
    m.add_class::<aether_infra::AikgsClientConfig>()?;
    m.add_class::<aether_infra::AikgsContribution>()?;
    m.add_class::<aether_infra::AikgsAffiliate>()?;
    m.add_class::<aether_infra::AikgsBounty>()?;
    m.add_class::<aether_infra::AikgsProfile>()?;
    m.add_class::<aether_infra::AikgsReview>()?;
    m.add_class::<aether_infra::AikgsCurationRound>()?;
    m.add_class::<aether_infra::AikgsKeyInfo>()?;
    m.add_class::<aether_infra::AikgsRewardStats>()?;
    m.add_class::<aether_infra::AikgsContributionStats>()?;
    m.add_class::<aether_infra::AikgsBountyStats>()?;
    m.add_class::<aether_infra::AikgsCuratorStats>()?;
    m.add_class::<aether_infra::AikgsCurationStats>()?;
    m.add_class::<aether_infra::ApiTier>()?;
    m.add_class::<aether_infra::StoredKey>()?;
    m.add_class::<aether_infra::RateLimitEntry>()?;
    m.add_class::<aether_infra::VaultStats>()?;
    m.add_class::<aether_infra::APIKeyVault>()?;

    Ok(())
}
