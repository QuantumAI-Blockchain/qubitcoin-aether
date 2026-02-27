//! aether_core — Rust-accelerated Aether Tree core modules for Qubitcoin.
//!
//! Provides high-performance implementations of 6 hot-path modules:
//! - KnowledgeGraph: In-memory graph with adjacency index, Merkle root, TF-IDF search
//! - PhiCalculator: IIT consciousness metric with spectral bisection MIP
//! - VectorIndex: HNSW approximate nearest neighbor search
//! - CSFTransport: Tree of Life inter-Sephirot message routing
//! - WorkingMemory: Fixed-capacity attention buffer (Miller's number)
//! - MemoryManager: 3-tier biologically-inspired memory system

use pyo3::prelude::*;

pub mod knowledge_graph;
pub mod phi_calculator;
pub mod vector_index;
pub mod csf_transport;
pub mod working_memory;
pub mod memory_manager;

/// Python module entry point.
#[pymodule]
fn aether_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Initialize Rust logging → Python logging bridge
    pyo3_log::init();

    // Knowledge Graph
    m.add_class::<knowledge_graph::KeterNode>()?;
    m.add_class::<knowledge_graph::KeterEdge>()?;
    m.add_class::<knowledge_graph::KnowledgeGraph>()?;

    // Phi Calculator
    m.add_class::<phi_calculator::PhiCalculator>()?;

    // Vector Index
    m.add_class::<vector_index::VectorIndex>()?;
    m.add_class::<vector_index::HNSWIndex>()?;

    // CSF Transport
    m.add_class::<csf_transport::CSFMessage>()?;
    m.add_class::<csf_transport::CSFTransport>()?;

    // Working Memory
    m.add_class::<working_memory::WorkingMemoryItem>()?;
    m.add_class::<working_memory::WorkingMemory>()?;

    // Memory Manager
    m.add_class::<memory_manager::Episode>()?;
    m.add_class::<memory_manager::MemoryManager>()?;

    Ok(())
}
