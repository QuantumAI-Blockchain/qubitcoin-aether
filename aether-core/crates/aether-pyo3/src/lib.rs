//! aether_core — PyO3 entry point for the Aether Tree Rust engine.
//!
//! This crate is the single cdylib that Python imports as `aether_core`.
//! It registers all PyO3 classes from every workspace crate.

use pyo3::prelude::*;

/// Python module entry point.
#[pymodule]
fn aether_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Initialize Rust logging -> Python logging bridge
    pyo3_log::init();

    // Types (KeterNode, KeterEdge)
    m.add_class::<aether_types::KeterNode>()?;
    m.add_class::<aether_types::KeterEdge>()?;

    // Knowledge Graph
    m.add_class::<aether_graph::KnowledgeGraph>()?;

    // Phi Calculator
    m.add_class::<aether_phi::PhiCalculator>()?;

    // Vector Index
    m.add_class::<aether_memory::VectorIndex>()?;
    m.add_class::<aether_memory::HNSWIndex>()?;

    // Working Memory
    m.add_class::<aether_memory::WorkingMemoryItem>()?;
    m.add_class::<aether_memory::WorkingMemory>()?;

    // Memory Manager
    m.add_class::<aether_memory::Episode>()?;
    m.add_class::<aether_memory::MemoryManager>()?;

    // Embedder
    m.add_class::<aether_memory::SimpleEmbedder>()?;
    m.add_class::<aether_memory::IDFEmbedder>()?;

    // Long-Term Memory
    m.add_class::<aether_memory::ConsolidatedPattern>()?;
    m.add_class::<aether_memory::ConsolidationResult>()?;
    m.add_class::<aether_memory::LongTermMemory>()?;

    // Neural GAT Reasoner
    m.add_class::<aether_neural::RustGATReasoner>()?;

    // CSF Transport
    m.add_class::<aether_sephirot::CSFMessage>()?;
    m.add_class::<aether_sephirot::CSFTransport>()?;

    Ok(())
}
