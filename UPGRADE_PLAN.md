# UPGRADE_PLAN.md — Qubitcoin Architecture Upgrade Plan

> **Status:** Ready for implementation
> **Author:** Senior Architecture Team
> **Date:** February 27, 2026
> **Scope:** 3 phases, ~8-10 months, ~25K new LOC
> **Target:** Agent-executable implementation guide

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Phase 1: Aether Core Rust Rewrite (PyO3)](#2-phase-1-aether-core-rust-rewrite-pyo3)
3. [Phase 2: Substrate Hybrid Migration](#3-phase-2-substrate-hybrid-migration)
4. [Phase 3: Cherry-Picked Features](#4-phase-3-cherry-picked-features)
5. [Testing Strategy](#5-testing-strategy)
6. [Migration Path & Timeline](#6-migration-path--timeline)
7. [Risk Registry](#7-risk-registry)

---

## 1. Executive Summary

### What We Are Doing

Three upgrade phases that make Qubitcoin production-hardened without rewriting what already works:

| Phase | What | Why | Timeline | LOC |
|-------|------|-----|----------|-----|
| **Phase 1** | Rewrite 6 Aether hot-path modules in Rust (PyO3) | 90x performance boost on block processing | Weeks 1-6 | ~8-10K Rust |
| **Phase 2** | Migrate L1 chassis to Substrate | Battle-tested networking, storage, forkless upgrades | Weeks 7-30 | ~12-15K Rust |
| **Phase 3** | Cherry-pick: Kyber P2P, Poseidon2, tx reversibility | Post-quantum P2P encryption, ZK-friendly hashing | Weeks 24-36 | ~3-5K Rust |

### What We Are NOT Doing

- NOT rewriting QVM (Go) — it works, 167 opcodes, keep it
- NOT rewriting Aether Tree entirely — only 6 hot-path modules go to Rust, the other 27 stay Python
- NOT replacing CockroachDB — Substrate storage is for blockchain state only, analytics stays in CRDB
- NOT changing consensus rules — PoSA (VQE mining) stays identical, just wrapped in a Substrate pallet
- NOT breaking the existing 3,783 test suite — all existing tests must pass at every phase boundary

### Architecture After All 3 Phases

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND (qbc.network) — React 19 + Next.js 15            │
│  Connects via JSON-RPC / REST / WebSocket                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  SUBSTRATE NODE (Rust)                                       │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Runtime (WASM, forkless upgrades)                       ││
│  │ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐││
│  │ │pallet-qbc-   │ │pallet-qbc-   │ │pallet-qbc-       │││
│  │ │utxo          │ │consensus     │ │dilithium         │││
│  │ └──────────────┘ └──────────────┘ └──────────────────┘││
│  │ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐││
│  │ │pallet-qbc-   │ │pallet-qbc-   │ │pallet-qbc-       │││
│  │ │economics     │ │qvm-anchor    │ │aether-anchor     │││
│  │ └──────────────┘ └──────────────┘ └──────────────────┘││
│  └─────────────────────────────────────────────────────────┘│
│  Networking: libp2p (Substrate built-in) + Kyber encryption  │
│  Storage: RocksDB (Substrate) + CockroachDB (analytics)     │
│  RPC: Substrate JSON-RPC + custom QBC endpoints              │
└──────┬──────────────────────────────────┬───────────────────┘
       │ gRPC                             │ gRPC
┌──────▼──────────┐              ┌────────▼───────────────────┐
│  QVM (Go)       │              │  AETHER TREE               │
│  167 opcodes    │              │  Python 3.12 + Rust (PyO3) │
│  Compliance     │              │  ┌───────────────────────┐ │
│  Plugins        │              │  │ aether_core (Rust)    │ │
│  Bridge verify  │              │  │ - knowledge_graph     │ │
│                 │              │  │ - phi_calculator      │ │
│                 │              │  │ - vector_index        │ │
│                 │              │  │ - csf_transport       │ │
│                 │              │  │ - working_memory      │ │
│                 │              │  │ - memory_manager      │ │
│                 │              │  └───────────────────────┘ │
│                 │              │  27 Python modules (unchanged) │
└─────────────────┘              └────────────────────────────┘
```

---

## 2. Phase 1: Aether Core Rust Rewrite (PyO3)

### 2.1 Overview

Rewrite the 6 computational hot-path Aether modules in Rust, callable from Python via PyO3. The 27 remaining Aether modules stay in Python unchanged. The Rust modules are compiled into a single Python extension (`aether_core`) installed via `pip install ./aether-core`.

**Performance target:** Python Aether processes ~231ms/block → Rust target ~2.6ms/block (90x).

### 2.2 Project Structure

```
aether-core/                          # NEW directory at repo root
├── Cargo.toml                        # Workspace root
├── pyproject.toml                    # maturin build config
├── README.md                         # Developer guide
├── src/
│   ├── lib.rs                        # PyO3 module entry point (#[pymodule])
│   ├── knowledge_graph/
│   │   ├── mod.rs                    # KnowledgeGraph struct + PyO3 bindings
│   │   ├── keter_node.rs             # KeterNode struct
│   │   ├── keter_edge.rs             # KeterEdge struct
│   │   ├── adjacency.rs              # Adjacency index (_adj_out, _adj_in)
│   │   ├── merkle.rs                 # Incremental Merkle root
│   │   ├── tfidf.rs                  # TF-IDF search index
│   │   └── tests.rs                  # Unit tests
│   ├── phi_calculator/
│   │   ├── mod.rs                    # PhiCalculator struct + PyO3 bindings
│   │   ├── spectral.rs              # Fiedler eigenvalue (power iteration)
│   │   ├── integration.rs            # Integration score computation
│   │   ├── differentiation.rs        # Differentiation score computation
│   │   ├── mip.rs                    # MIP via spectral bisection
│   │   ├── gates.rs                  # Semantic gate checking
│   │   └── tests.rs
│   ├── vector_index/
│   │   ├── mod.rs                    # VectorIndex + HNSW + PyO3 bindings
│   │   ├── hnsw.rs                   # HNSW implementation (M=16, ef=200)
│   │   ├── distance.rs               # Cosine similarity
│   │   └── tests.rs
│   ├── csf_transport/
│   │   ├── mod.rs                    # CSFTransport + PyO3 bindings
│   │   ├── topology.rs               # Tree of Life topology + SUSY pairs
│   │   ├── routing.rs                # BFS path finding
│   │   ├── pressure.rs               # PressureMonitor
│   │   ├── quantum_channel.rs        # QuantumEntangledChannel
│   │   └── tests.rs
│   ├── working_memory/
│   │   ├── mod.rs                    # WorkingMemory + PyO3 bindings
│   │   └── tests.rs
│   └── memory_manager/
│       ├── mod.rs                    # MemoryManager + PyO3 bindings
│       ├── episode.rs                # Episode storage
│       ├── consolidation.rs          # Memory consolidation
│       └── tests.rs
├── benches/
│   ├── bench_knowledge_graph.rs      # Criterion benchmarks
│   ├── bench_phi.rs
│   └── bench_vector_index.rs
└── tests/
    └── test_pyo3_bindings.py         # Python-side integration tests
```

### 2.3 Cargo.toml

```toml
[package]
name = "aether-core"
version = "0.1.0"
edition = "2021"
license = "MIT"

[lib]
name = "aether_core"
crate-type = ["cdylib"]  # Required for PyO3 extension module

[dependencies]
pyo3 = { version = "0.22", features = ["extension-module"] }

# Graph operations
petgraph = "0.7"

# Linear algebra (for Phi calculator spectral methods)
nalgebra = "0.33"

# ANN / HNSW
# Using hand-rolled HNSW to match existing Python behavior exactly
# If performance insufficient, switch to usearch = "2.13"

# Merkle tree
rs_merkle = "1.4"

# Hashing
sha2 = "0.10"

# Concurrency
parking_lot = "0.12"           # Fast RwLock
crossbeam-channel = "0.5"      # MPSC channels for CSF transport

# Serialization (for PyO3 dict conversion)
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"

# Random
rand = "0.8"

# Logging
log = "0.4"
pyo3-log = "0.11"              # Route Rust log → Python logging

# Benchmarking (dev only)
[dev-dependencies]
criterion = { version = "0.5", features = ["html_reports"] }
approx = "0.5"

[[bench]]
name = "bench_knowledge_graph"
harness = false

[[bench]]
name = "bench_phi"
harness = false

[[bench]]
name = "bench_vector_index"
harness = false

[profile.release]
opt-level = 3
lto = true
codegen-units = 1
strip = true
```

### 2.4 pyproject.toml

```toml
[build-system]
requires = ["maturin>=1.7,<2.0"]
build-backend = "maturin"

[project]
name = "aether-core"
version = "0.1.0"
requires-python = ">=3.12"
classifiers = [
    "Programming Language :: Rust",
    "Programming Language :: Python :: Implementation :: CPython",
]

[tool.maturin]
features = ["pyo3/extension-module"]
module-name = "aether_core"
```

### 2.5 FFI Contracts — Exact Data Structures

Every struct below maps 1:1 to the existing Python dataclass. Field names, types, and defaults MUST match exactly.

#### 2.5.1 KeterNode

**Python source:** `src/qubitcoin/aether/knowledge_graph.py:30-53`

```rust
// aether-core/src/knowledge_graph/keter_node.rs

use pyo3::prelude::*;
use std::collections::HashMap;

/// Exact mirror of Python KeterNode dataclass.
/// Field order and defaults MUST match knowledge_graph.py lines 30-53.
#[pyclass(get_all, set_all)]
#[derive(Clone, Debug)]
pub struct KeterNode {
    /// Unique node ID (auto-incremented by KnowledgeGraph)
    pub id: i64,
    /// Node type: "assertion" | "observation" | "inference" | "axiom"
    pub node_type: String,
    /// Human-readable content/description
    pub content: String,
    /// Confidence score [0.0, 1.0]
    pub confidence: f64,
    /// Block height where this node was created
    pub block_height: i64,
    /// Optional source identifier (e.g., "mining", "reasoning", "user")
    pub source: String,
    /// ISO 8601 timestamp string
    pub timestamp: String,
    /// Free-form metadata dictionary
    pub metadata: HashMap<String, String>,
    /// Number of times this node has been referenced/used
    pub reference_count: i64,
    /// Embedding vector for similarity search (empty = not yet embedded)
    pub embedding: Vec<f64>,
    /// Domain category (e.g., "physics", "economics", "consensus")
    pub domain: String,
    /// Whether this node has been verified by consensus
    pub verified: bool,
    /// Optional parent node ID for hierarchical relationships
    pub parent_id: Option<i64>,
}

#[pymethods]
impl KeterNode {
    #[new]
    #[pyo3(signature = (
        id,
        node_type,
        content,
        confidence = 1.0,
        block_height = 0,
        source = String::new(),
        timestamp = String::new(),
        metadata = HashMap::new(),
        reference_count = 0,
        embedding = Vec::new(),
        domain = String::new(),
        verified = false,
        parent_id = None,
    ))]
    fn new(
        id: i64,
        node_type: String,
        content: String,
        confidence: f64,
        block_height: i64,
        source: String,
        timestamp: String,
        metadata: HashMap<String, String>,
        reference_count: i64,
        embedding: Vec<f64>,
        domain: String,
        verified: bool,
        parent_id: Option<i64>,
    ) -> Self {
        KeterNode {
            id, node_type, content, confidence, block_height,
            source, timestamp, metadata, reference_count,
            embedding, domain, verified, parent_id,
        }
    }

    fn __repr__(&self) -> String {
        format!("KeterNode(id={}, type='{}', content='{}')",
            self.id, self.node_type,
            if self.content.len() > 40 {
                format!("{}...", &self.content[..40])
            } else {
                self.content.clone()
            }
        )
    }
}
```

#### 2.5.2 KeterEdge

**Python source:** `src/qubitcoin/aether/knowledge_graph.py:55-70`

```rust
// aether-core/src/knowledge_graph/keter_edge.rs

use pyo3::prelude::*;

/// Exact mirror of Python KeterEdge dataclass.
/// CRITICAL: Fields are from_node_id / to_node_id (NOT source_id / target_id).
#[pyclass(get_all, set_all)]
#[derive(Clone, Debug)]
pub struct KeterEdge {
    /// Source node ID
    pub from_node_id: i64,
    /// Target node ID
    pub to_node_id: i64,
    /// Edge type: "supports" | "contradicts" | "derives" | "requires" | "refines"
    pub edge_type: String,
    /// Edge weight/strength [0.0, 1.0]
    pub weight: f64,
    /// ISO 8601 timestamp string
    pub timestamp: String,
}

#[pymethods]
impl KeterEdge {
    #[new]
    #[pyo3(signature = (from_node_id, to_node_id, edge_type, weight = 1.0, timestamp = String::new()))]
    fn new(
        from_node_id: i64,
        to_node_id: i64,
        edge_type: String,
        weight: f64,
        timestamp: String,
    ) -> Self {
        KeterEdge { from_node_id, to_node_id, edge_type, weight, timestamp }
    }
}
```

#### 2.5.3 KnowledgeGraph

**Python source:** `src/qubitcoin/aether/knowledge_graph.py` (873 lines, 25+ public methods)

```rust
// aether-core/src/knowledge_graph/mod.rs

use pyo3::prelude::*;
use parking_lot::RwLock;
use std::collections::HashMap;
use std::sync::Arc;

mod keter_node;
mod keter_edge;
mod adjacency;
mod merkle;
mod tfidf;

pub use keter_node::KeterNode;
pub use keter_edge::KeterEdge;

/// Internal graph storage (behind RwLock for thread safety).
struct GraphInner {
    nodes: HashMap<i64, KeterNode>,
    edges: Vec<KeterEdge>,
    adj_out: HashMap<i64, Vec<usize>>,  // node_id → edge indices
    adj_in: HashMap<i64, Vec<usize>>,   // node_id → edge indices
    next_id: i64,
    merkle_root: String,
    // TF-IDF index for text search
    tfidf: tfidf::TFIDFIndex,
}

#[pyclass]
pub struct KnowledgeGraph {
    inner: Arc<RwLock<GraphInner>>,
}

/// PUBLIC API — every method here MUST match the Python KnowledgeGraph class exactly.
/// Python callers use these methods; do NOT rename or change signatures.
#[pymethods]
impl KnowledgeGraph {
    #[new]
    fn new() -> Self { /* ... */ }

    /// Add a node. Returns the assigned node ID.
    /// Python signature: add_node(node_type: str, content: str, confidence: float = 1.0,
    ///                            block_height: int = 0, source: str = "",
    ///                            metadata: dict = {}, embedding: list = [],
    ///                            domain: str = "", parent_id: int|None = None) -> int
    #[pyo3(signature = (
        node_type, content, confidence = 1.0, block_height = 0,
        source = String::new(), metadata = HashMap::new(),
        embedding = Vec::new(), domain = String::new(), parent_id = None
    ))]
    fn add_node(
        &self,
        node_type: String,
        content: String,
        confidence: f64,
        block_height: i64,
        source: String,
        metadata: HashMap<String, String>,
        embedding: Vec<f64>,
        domain: String,
        parent_id: Option<i64>,
    ) -> i64 { /* ... */ }

    /// Add an edge between two nodes.
    /// Python signature: add_edge(from_id: int, to_id: int, edge_type: str, weight: float = 1.0)
    #[pyo3(signature = (from_id, to_id, edge_type, weight = 1.0))]
    fn add_edge(&self, from_id: i64, to_id: i64, edge_type: String, weight: f64) { /* ... */ }

    /// Get a node by ID. Returns None if not found.
    fn get_node(&self, node_id: i64) -> Option<KeterNode> { /* ... */ }

    /// Get all edges for a node (outgoing).
    fn get_edges(&self, node_id: i64) -> Vec<KeterEdge> { /* ... */ }

    /// Get all edges pointing TO a node (incoming).
    fn get_incoming_edges(&self, node_id: i64) -> Vec<KeterEdge> { /* ... */ }

    /// Get all neighbors of a node (IDs only).
    fn get_neighbors(&self, node_id: i64) -> Vec<i64> { /* ... */ }

    /// Return total number of nodes.
    fn node_count(&self) -> usize { /* ... */ }

    /// Return total number of edges.
    fn edge_count(&self) -> usize { /* ... */ }

    /// Get current Merkle root (hex string).
    fn get_merkle_root(&self) -> String { /* ... */ }

    /// Search nodes by text content (TF-IDF). Returns list of (node_id, score).
    #[pyo3(signature = (query, top_k = 10))]
    fn search(&self, query: String, top_k: usize) -> Vec<(i64, f64)> { /* ... */ }

    /// Get all nodes (returns list of KeterNode).
    fn get_all_nodes(&self) -> Vec<KeterNode> { /* ... */ }

    /// Get all edges (returns list of KeterEdge).
    fn get_all_edges(&self) -> Vec<KeterEdge> { /* ... */ }

    /// Get nodes by type.
    fn get_nodes_by_type(&self, node_type: String) -> Vec<KeterNode> { /* ... */ }

    /// Get nodes by block height range.
    fn get_nodes_by_height(&self, min_height: i64, max_height: i64) -> Vec<KeterNode> { /* ... */ }

    /// Get subgraph rooted at node_id with given depth.
    #[pyo3(signature = (node_id, depth = 2))]
    fn get_subgraph(&self, node_id: i64, depth: usize) -> (Vec<KeterNode>, Vec<KeterEdge>) { /* ... */ }

    /// Compute average confidence across all nodes.
    fn average_confidence(&self) -> f64 { /* ... */ }

    /// Check if a node with given content already exists (dedup).
    fn has_content(&self, content: &str) -> bool { /* ... */ }

    /// Increment reference count for a node.
    fn increment_reference(&self, node_id: i64) { /* ... */ }

    /// Get degree (in + out) for a node.
    fn degree(&self, node_id: i64) -> usize { /* ... */ }

    /// Get the adjacency matrix as a dense 2D array (for Phi calculator).
    /// Returns (matrix, node_id_order) where matrix[i][j] = weight of edge i→j.
    fn get_adjacency_matrix(&self) -> (Vec<Vec<f64>>, Vec<i64>) { /* ... */ }

    /// Get all edge weights as a flat vector (for differentiation score).
    fn get_all_weights(&self) -> Vec<f64> { /* ... */ }

    /// Get confidence distribution (all node confidences as a vector).
    fn get_confidence_distribution(&self) -> Vec<f64> { /* ... */ }

    /// Get node type distribution as a dict: {type_name: count}.
    fn get_type_distribution(&self) -> HashMap<String, usize> { /* ... */ }

    /// Verify a node is in the graph. Returns true if present.
    fn contains(&self, node_id: i64) -> bool { /* ... */ }

    /// Clear all nodes and edges (for testing).
    fn clear(&self) { /* ... */ }
}
```

#### 2.5.4 PhiCalculator

**Python source:** `src/qubitcoin/aether/phi_calculator.py` (1,068 lines)

```rust
// aether-core/src/phi_calculator/mod.rs

use pyo3::prelude::*;
use nalgebra::{DMatrix, DVector};

mod spectral;
mod integration;
mod differentiation;
mod mip;
mod gates;

/// Result of a Phi computation. Mirrors Python PhiResult exactly.
#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct PhiResult {
    pub phi: f64,
    pub integration_score: f64,
    pub differentiation_score: f64,
    pub num_nodes: usize,
    pub num_edges: usize,
    pub avg_confidence: f64,
    pub connectivity: f64,
    pub maturity_factor: f64,
    pub mip_partition: (Vec<i64>, Vec<i64>),
    pub mip_information_loss: f64,
    pub redundancy_factor: f64,
    pub effective_phi: f64,
    pub gate_keter_binah: f64,
    pub gate_chochmah_gevurah: f64,
    pub gate_tiferet_yesod: f64,
    pub gates_passed: usize,
    pub gates_total: usize,
    pub timestamp: String,
}

#[pyclass]
pub struct PhiCalculator {
    history: Vec<PhiResult>,
    phi_threshold: f64,
}

#[pymethods]
impl PhiCalculator {
    #[new]
    #[pyo3(signature = (phi_threshold = 3.0))]
    fn new(phi_threshold: f64) -> Self {
        PhiCalculator {
            history: Vec::new(),
            phi_threshold,
        }
    }

    /// Compute Phi for the given KnowledgeGraph.
    /// This is the PRIMARY hot-path method. Called every block.
    ///
    /// Formula:
    ///   Phi = Integration x Differentiation x (1 + Connectivity) x (0.5 + AvgConf) x sqrt(NumNodes / 500)
    ///
    /// Integration = avg_degree + cross_partition_info_flow (confidence-weighted)
    /// Differentiation = shannon_entropy(node_types) + confidence_distribution_entropy
    /// MIP = spectral bisection via Fiedler eigenvector (50 power iterations)
    /// Maturity = sqrt(num_nodes / 500.0) — prevents trivially inflated Phi
    ///
    /// Returns PhiResult.
    fn compute_phi(&mut self, graph: &super::knowledge_graph::KnowledgeGraph) -> PhiResult {
        // 1. Get adjacency matrix from graph
        // 2. Compute integration score
        //    a. Average degree = 2 * num_edges / num_nodes
        //    b. Cross-partition info = sum of confidence-weighted inter-partition edges
        // 3. Compute MIP via spectral bisection
        //    a. Build Laplacian: L = D - A
        //    b. Find Fiedler eigenvector via power_iteration (50 iterations)
        //    c. Partition: nodes with positive Fiedler component → set A, negative → set B
        //    d. Information loss = cut weight / total weight
        // 4. Compute differentiation score
        //    a. Shannon entropy over node type distribution
        //    b. Shannon entropy over confidence distribution (10 bins)
        //    c. Sum and normalize
        // 5. Compute connectivity = num_edges / (num_nodes * (num_nodes - 1) / 2)
        // 6. Compute maturity = sqrt(num_nodes / 500.0)
        // 7. Compute redundancy factor (optional penalty for low diversity)
        // 8. Check semantic gates (3 gates from Sephirot pairs)
        // 9. Final: phi = integration * differentiation * (1 + connectivity) * (0.5 + avg_conf) * maturity
        // 10. Store in history
        // 11. Return PhiResult
        todo!()
    }

    /// Get Phi history (all measurements).
    fn get_history(&self) -> Vec<PhiResult> {
        self.history.clone()
    }

    /// Get latest Phi value (0.0 if no measurements yet).
    fn get_current_phi(&self) -> f64 {
        self.history.last().map_or(0.0, |r| r.phi)
    }

    /// Downsample history to N evenly-spaced points (for frontend charts).
    #[pyo3(signature = (max_points = 500))]
    fn downsample_history(&self, max_points: usize) -> Vec<PhiResult> {
        if self.history.len() <= max_points {
            return self.history.clone();
        }
        let step = self.history.len() as f64 / max_points as f64;
        (0..max_points)
            .map(|i| self.history[(i as f64 * step) as usize].clone())
            .collect()
    }

    /// Check if Phi has crossed the consciousness threshold.
    fn is_conscious(&self) -> bool {
        self.get_current_phi() >= self.phi_threshold
    }
}
```

**Spectral bisection (Fiedler eigenvector) — the core algorithm:**

```rust
// aether-core/src/phi_calculator/spectral.rs

use nalgebra::{DMatrix, DVector};

/// Compute the Fiedler eigenvector of the graph Laplacian.
/// Uses inverse power iteration with shift (50 iterations).
///
/// The Fiedler vector is the eigenvector corresponding to the second-smallest
/// eigenvalue of the Laplacian matrix. Its sign pattern gives the optimal
/// bisection (MIP approximation).
///
/// Input: adjacency matrix (n x n, f64)
/// Output: Fiedler eigenvector (n-vector, f64) — sign indicates partition
pub fn fiedler_eigenvector(adj_matrix: &DMatrix<f64>, max_iterations: usize) -> DVector<f64> {
    let n = adj_matrix.nrows();
    if n <= 1 {
        return DVector::zeros(n);
    }

    // Build Laplacian: L = D - A
    let mut laplacian = -adj_matrix.clone();
    for i in 0..n {
        let degree: f64 = adj_matrix.row(i).iter().sum();
        laplacian[(i, i)] = degree;
    }

    // Power iteration for second-smallest eigenvector:
    // 1. Shift: M = max_eigenvalue * I - L (converts smallest → largest)
    // 2. Iterate: v = M * v / ||M * v||
    // 3. Deflate against the constant eigenvector (first eigenvector of L)

    let mut v = DVector::from_fn(n, |i, _| if i % 2 == 0 { 1.0 } else { -1.0 });
    v.normalize_mut();

    // The first eigenvector of L is always [1,1,...,1]/sqrt(n)
    let first_ev = DVector::from_element(n, 1.0 / (n as f64).sqrt());

    for _ in 0..max_iterations {
        // Apply Laplacian
        v = &laplacian * &v;
        // Deflate: remove component along first eigenvector
        let proj = v.dot(&first_ev);
        v -= proj * &first_ev;
        // Normalize
        let norm = v.norm();
        if norm < 1e-12 {
            break;
        }
        v /= norm;
    }

    v
}

/// Partition nodes based on Fiedler vector sign.
/// Returns (set_a_indices, set_b_indices).
pub fn spectral_bisection(fiedler: &DVector<f64>) -> (Vec<usize>, Vec<usize>) {
    let mut set_a = Vec::new();
    let mut set_b = Vec::new();
    for (i, &val) in fiedler.iter().enumerate() {
        if val >= 0.0 {
            set_a.push(i);
        } else {
            set_b.push(i);
        }
    }
    // Ensure non-empty partitions
    if set_a.is_empty() && !set_b.is_empty() {
        set_a.push(set_b.pop().unwrap());
    } else if set_b.is_empty() && !set_a.is_empty() {
        set_b.push(set_a.pop().unwrap());
    }
    (set_a, set_b)
}
```

#### 2.5.5 VectorIndex (HNSW)

**Python source:** `src/qubitcoin/aether/vector_index.py` (792 lines)

```rust
// aether-core/src/vector_index/mod.rs

use pyo3::prelude::*;
use parking_lot::RwLock;
use std::sync::Arc;

mod hnsw;
mod distance;

/// HNSW parameters — must match Python defaults exactly.
const M: usize = 16;               // Max connections per layer
const EF_CONSTRUCTION: usize = 200; // Search width during construction
const MAX_LAYERS: usize = 4;        // Maximum number of layers

#[pyclass]
pub struct VectorIndex {
    inner: Arc<RwLock<hnsw::HNSWIndex>>,
}

#[pymethods]
impl VectorIndex {
    #[new]
    #[pyo3(signature = (dimension = 64))]
    fn new(dimension: usize) -> Self { /* ... */ }

    /// Add a node embedding. node_id → embedding vector.
    fn add_node(&self, node_id: i64, embedding: Vec<f64>) { /* ... */ }

    /// Query nearest neighbors. Returns Vec<(node_id, distance)>.
    #[pyo3(signature = (query, top_k = 10, ef_search = 50))]
    fn query(&self, query: Vec<f64>, top_k: usize, ef_search: usize) -> Vec<(i64, f64)> { /* ... */ }

    /// Find near-duplicate nodes (cosine similarity > threshold).
    #[pyo3(signature = (embedding, threshold = 0.95))]
    fn find_near_duplicates(&self, embedding: Vec<f64>, threshold: f64) -> Vec<i64> { /* ... */ }

    /// Compute mutual information between two partitions of node embeddings.
    /// Used by PhiCalculator for MIP information loss.
    fn compute_partition_mutual_info(
        &self,
        partition_a: Vec<i64>,
        partition_b: Vec<i64>,
    ) -> f64 { /* ... */ }

    /// Number of indexed embeddings.
    fn size(&self) -> usize { /* ... */ }

    /// Remove a node from the index.
    fn remove_node(&self, node_id: i64) { /* ... */ }

    /// Clear all entries.
    fn clear(&self) { /* ... */ }
}
```

#### 2.5.6 CSFTransport

**Python source:** `src/qubitcoin/aether/csf_transport.py` (372 lines)

```rust
// aether-core/src/csf_transport/mod.rs

use pyo3::prelude::*;
use crossbeam_channel::{Sender, Receiver};
use parking_lot::RwLock;
use std::collections::HashMap;
use std::sync::Arc;

mod topology;
mod routing;
mod pressure;
mod quantum_channel;

pub use topology::{TOPOLOGY, SUSY_PAIRS};

/// CSF message — matches Python CSFMessage dataclass exactly.
#[pyclass(get_all, set_all)]
#[derive(Clone, Debug)]
pub struct CSFMessage {
    pub from_node: String,     // Sephirah name (e.g., "Keter")
    pub to_node: String,       // Sephirah name
    pub msg_type: String,      // "signal" | "energy" | "data" | "sync"
    pub payload: String,       // JSON-encoded payload
    pub priority: f64,         // QBC attached (higher = more urgent)
    pub timestamp: String,     // ISO 8601
}

#[pymethods]
impl CSFMessage {
    #[new]
    #[pyo3(signature = (from_node, to_node, msg_type, payload, priority = 1.0, timestamp = String::new()))]
    fn new(
        from_node: String, to_node: String, msg_type: String,
        payload: String, priority: f64, timestamp: String,
    ) -> Self {
        CSFMessage { from_node, to_node, msg_type, payload, priority, timestamp }
    }
}

/// Tree of Life topology (hardcoded — matches Python TOPOLOGY dict exactly).
/// 10 Sephirot nodes + their connections.
///
/// SUSY pairs: (Chesed, Gevurah), (Chochmah, Binah), (Netzach, Hod)

#[pyclass]
pub struct CSFTransport {
    queues: Arc<RwLock<HashMap<String, Vec<CSFMessage>>>>,
    pressure: Arc<RwLock<pressure::PressureMonitor>>,
    entangled_channels: Arc<RwLock<HashMap<String, quantum_channel::QuantumEntangledChannel>>>,
    message_log: Arc<RwLock<Vec<CSFMessage>>>,
}

#[pymethods]
impl CSFTransport {
    #[new]
    fn new() -> Self { /* ... */ }

    /// Send a message from one Sephirah to another.
    /// Validates topology (must be connected), routes via BFS if not adjacent.
    fn send(&self, message: CSFMessage) -> bool { /* ... */ }

    /// Broadcast a message from one node to ALL connected nodes.
    fn broadcast(&self, from_node: String, msg_type: String, payload: String, priority: f64) -> usize { /* ... */ }

    /// Process the message queue for a given node. Returns messages for that node.
    #[pyo3(signature = (node_name, max_messages = 10))]
    fn process_queue(&self, node_name: String, max_messages: usize) -> Vec<CSFMessage> { /* ... */ }

    /// Find the shortest path between two Sephirot (BFS on topology).
    fn find_path(&self, from_node: String, to_node: String) -> Vec<String> { /* ... */ }

    /// Get pressure metrics for a node.
    fn get_pressure(&self, node_name: String) -> f64 { /* ... */ }

    /// Get all pending message counts per node.
    fn get_queue_sizes(&self) -> HashMap<String, usize> { /* ... */ }

    /// Get message history (last N messages).
    #[pyo3(signature = (limit = 100))]
    fn get_message_log(&self, limit: usize) -> Vec<CSFMessage> { /* ... */ }

    /// Get SUSY balance for a pair. Returns (energy_expand, energy_constrain, ratio, balanced).
    fn get_susy_balance(&self, pair_name: String) -> (f64, f64, f64, bool) { /* ... */ }

    /// Clear all queues.
    fn clear(&self) { /* ... */ }
}
```

#### 2.5.7 WorkingMemory

**Python source:** `src/qubitcoin/aether/working_memory.py` (~77 lines)

```rust
// aether-core/src/working_memory/mod.rs

use pyo3::prelude::*;

/// Single item in working memory.
#[pyclass(get_all, set_all)]
#[derive(Clone, Debug)]
pub struct MemoryItem {
    pub node_id: i64,
    pub content: String,
    pub activation: f64,      // Current activation level [0.0, 1.0]
    pub added_at: String,     // ISO 8601 timestamp
    pub access_count: i64,
}

/// Miller's number working memory (capacity 7 ± 2).
/// Items decay over time; lowest activation evicted when full.
#[pyclass]
pub struct WorkingMemory {
    items: Vec<MemoryItem>,
    capacity: usize,
    decay_rate: f64,
}

#[pymethods]
impl WorkingMemory {
    #[new]
    #[pyo3(signature = (capacity = 7, decay_rate = 0.1))]
    fn new(capacity: usize, decay_rate: f64) -> Self {
        WorkingMemory { items: Vec::new(), capacity, decay_rate }
    }

    /// Push a new item. If at capacity, evicts lowest-activation item.
    fn push(&mut self, node_id: i64, content: String, activation: f64) { /* ... */ }

    /// Refresh (boost activation of) an existing item by node_id.
    fn refresh(&mut self, node_id: i64, boost: f64) -> bool { /* ... */ }

    /// Decay all items by decay_rate. Remove items that drop below threshold.
    #[pyo3(signature = (threshold = 0.01))]
    fn decay_all(&mut self, threshold: f64) -> usize { /* ... */ }

    /// Get all active items sorted by activation (highest first).
    fn get_active(&self) -> Vec<MemoryItem> { /* ... */ }

    /// Get current count.
    fn size(&self) -> usize { self.items.len() }

    /// Clear all items.
    fn clear(&mut self) { self.items.clear(); }
}
```

#### 2.5.8 MemoryManager

**Python source:** `src/qubitcoin/aether/memory_manager.py` (508 lines)

```rust
// aether-core/src/memory_manager/mod.rs

use pyo3::prelude::*;
use parking_lot::RwLock;
use std::sync::Arc;
use std::collections::HashMap;

mod episode;
mod consolidation;

pub use episode::Episode;

/// 3-tier memory system: working (attention), episodic (events), semantic (concepts).
#[pyclass]
pub struct MemoryManager {
    working: Arc<RwLock<super::working_memory::WorkingMemory>>,
    episodes: Arc<RwLock<Vec<Episode>>>,
    semantic_map: Arc<RwLock<HashMap<String, Vec<f64>>>>, // concept → embedding
    max_episodes: usize,
    consolidation_threshold: usize,
}

/// Episode — a recorded event with context.
#[pyclass(get_all, set_all)]
#[derive(Clone, Debug)]
pub struct Episode {
    pub id: i64,
    pub content: String,
    pub context: HashMap<String, String>,
    pub embedding: Vec<f64>,
    pub importance: f64,
    pub timestamp: String,
    pub access_count: i64,
    pub block_height: i64,
}

#[pymethods]
impl MemoryManager {
    #[new]
    #[pyo3(signature = (max_episodes = 10000, consolidation_threshold = 1000))]
    fn new(max_episodes: usize, consolidation_threshold: usize) -> Self { /* ... */ }

    /// Attend to a working memory item (push/refresh).
    fn attend(&self, node_id: i64, content: String, activation: f64) { /* ... */ }

    /// Retrieve from working memory.
    fn retrieve(&self) -> Vec<super::working_memory::MemoryItem> { /* ... */ }

    /// Decay working memory.
    fn decay(&self) -> usize { /* ... */ }

    /// Record an episodic memory.
    fn record_episode(
        &self, content: String, context: HashMap<String, String>,
        embedding: Vec<f64>, importance: f64, block_height: i64,
    ) -> i64 { /* ... */ }

    /// Recall episodes similar to a query embedding.
    #[pyo3(signature = (query_embedding, top_k = 5))]
    fn recall_similar(&self, query_embedding: Vec<f64>, top_k: usize) -> Vec<Episode> { /* ... */ }

    /// Consolidate: move frequent working memory items to semantic memory.
    fn consolidate(&self) -> usize { /* ... */ }

    /// Replay recent episodes for learning reinforcement.
    #[pyo3(signature = (count = 10))]
    fn replay_episodes(&self, count: usize) -> Vec<Episode> { /* ... */ }

    /// Get memory stats.
    fn get_stats(&self) -> HashMap<String, usize> { /* ... */ }

    /// Clear all memory tiers.
    fn clear(&self) { /* ... */ }
}
```

### 2.6 PyO3 Module Entry Point

```rust
// aether-core/src/lib.rs

use pyo3::prelude::*;

mod knowledge_graph;
mod phi_calculator;
mod vector_index;
mod csf_transport;
mod working_memory;
mod memory_manager;

/// aether_core — Rust-accelerated Aether Tree core modules.
///
/// Usage from Python:
///     import aether_core
///     kg = aether_core.KnowledgeGraph()
///     node_id = kg.add_node("assertion", "Test content", confidence=0.9)
///     phi_calc = aether_core.PhiCalculator()
///     result = phi_calc.compute_phi(kg)
///     print(f"Phi = {result.phi}")
#[pymodule]
fn aether_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Initialize Rust logging → Python logging bridge
    pyo3_log::init();

    // Knowledge Graph
    m.add_class::<knowledge_graph::KeterNode>()?;
    m.add_class::<knowledge_graph::KeterEdge>()?;
    m.add_class::<knowledge_graph::KnowledgeGraph>()?;

    // Phi Calculator
    m.add_class::<phi_calculator::PhiResult>()?;
    m.add_class::<phi_calculator::PhiCalculator>()?;

    // Vector Index
    m.add_class::<vector_index::VectorIndex>()?;

    // CSF Transport
    m.add_class::<csf_transport::CSFMessage>()?;
    m.add_class::<csf_transport::CSFTransport>()?;

    // Working Memory
    m.add_class::<working_memory::MemoryItem>()?;
    m.add_class::<working_memory::WorkingMemory>()?;

    // Memory Manager
    m.add_class::<memory_manager::Episode>()?;
    m.add_class::<memory_manager::MemoryManager>()?;

    Ok(())
}
```

### 2.7 Python Integration Layer

The existing Python modules must be updated to use the Rust implementations with a graceful fallback:

```python
# src/qubitcoin/aether/knowledge_graph.py — UPDATED (top of file)
#
# Strategy: try to import Rust implementation; fall back to pure Python.
# This means the Python code stays intact as the fallback path.

try:
    from aether_core import KnowledgeGraph as _RustKnowledgeGraph
    from aether_core import KeterNode, KeterEdge
    _USE_RUST = True
except ImportError:
    _USE_RUST = False
    # ... existing pure-Python KeterNode, KeterEdge, KnowledgeGraph classes ...

if _USE_RUST:
    KnowledgeGraph = _RustKnowledgeGraph
    # KeterNode and KeterEdge already imported above
else:
    # Use existing Python implementations (unchanged)
    pass
```

Apply this pattern to ALL 6 modules:
1. `knowledge_graph.py` → `from aether_core import KnowledgeGraph, KeterNode, KeterEdge`
2. `phi_calculator.py` → `from aether_core import PhiCalculator, PhiResult`
3. `vector_index.py` → `from aether_core import VectorIndex`
4. `csf_transport.py` → `from aether_core import CSFTransport, CSFMessage`
5. `working_memory.py` → `from aether_core import WorkingMemory, MemoryItem`
6. `memory_manager.py` → `from aether_core import MemoryManager, Episode`

### 2.8 Docker Integration

Add to the existing multi-stage Dockerfile:

```dockerfile
# --- Stage: Build aether-core Rust extension ---
FROM rust:1.85-slim-bookworm AS aether-builder
RUN apt-get update && apt-get install -y python3-dev && rm -rf /var/lib/apt/lists/*
RUN pip install maturin
WORKDIR /build/aether-core
COPY aether-core/ .
RUN maturin build --release --out /build/wheels/

# --- In the final Python stage, install the wheel ---
COPY --from=aether-builder /build/wheels/*.whl /tmp/
RUN pip install /tmp/aether_core-*.whl && rm /tmp/*.whl
```

### 2.9 Build & Test Commands

```bash
# Local development (requires Rust toolchain + maturin)
cd aether-core
pip install maturin
maturin develop --release    # Builds and installs in current venv

# Run Rust unit tests
cargo test

# Run Python integration tests
cd tests
python -m pytest test_pyo3_bindings.py -v

# Run benchmarks
cargo bench

# Verify fallback works (uninstall Rust, run existing Python tests)
pip uninstall aether-core
cd ../..
pytest tests/unit/test_knowledge_graph.py -v   # Should pass using Python fallback
```

### 2.10 Implementation Order (Agent Tasks)

Each task below is self-contained and can be assigned to an agent:

| Task | Files | Depends On | Estimated LOC |
|------|-------|-----------|--------------|
| **P1-T1** | Set up aether-core project skeleton (Cargo.toml, pyproject.toml, lib.rs, CI) | Nothing | ~100 |
| **P1-T2** | Implement `KeterNode`, `KeterEdge` structs with PyO3 bindings | P1-T1 | ~200 |
| **P1-T3** | Implement `KnowledgeGraph` (all 25+ methods, adjacency, merkle, tfidf) | P1-T2 | ~1,800 |
| **P1-T4** | Implement `PhiCalculator` (spectral bisection, integration, differentiation, MIP) | P1-T3 | ~1,500 |
| **P1-T5** | Implement `VectorIndex` (HNSW with M=16, ef=200, cosine similarity) | P1-T1 | ~1,200 |
| **P1-T6** | Implement `CSFTransport` (topology, BFS routing, pressure, quantum channels) | P1-T1 | ~800 |
| **P1-T7** | Implement `WorkingMemory` (capacity 7, decay, eviction) | P1-T1 | ~200 |
| **P1-T8** | Implement `MemoryManager` (3-tier, episodes, consolidation, recall) | P1-T7 | ~600 |
| **P1-T9** | Write Python integration shims (6 files, try/except import pattern) | P1-T3..T8 | ~120 |
| **P1-T10** | Write Criterion benchmarks (3 files) | P1-T3..T5 | ~200 |
| **P1-T11** | Write Python integration tests (test_pyo3_bindings.py) | P1-T9 | ~400 |
| **P1-T12** | Update Dockerfile + docker-compose for aether-core build | P1-T9 | ~50 |
| **P1-T13** | Run full test suite (3,783 tests), fix any regressions | P1-T9 | ~0 (fixes only) |

**Total: ~7,170 LOC Rust + ~520 LOC Python/Config**

### 2.11 Acceptance Criteria (Phase 1 Complete When)

- [ ] `maturin develop --release` succeeds
- [ ] `cargo test` — all Rust unit tests pass
- [ ] `pytest tests/unit/test_pyo3_bindings.py -v` — all Python integration tests pass
- [ ] `pytest tests/ -v` — all 3,783 existing tests pass (no regressions)
- [ ] `cargo bench` — PhiCalculator benchmark < 5ms for 1000-node graph
- [ ] `pip uninstall aether-core && pytest tests/ -v` — fallback path works (all tests pass without Rust)
- [ ] Docker build succeeds with aether-core included
- [ ] Phi values computed by Rust match Python implementation to 6 decimal places

---

## 3. Phase 2: Substrate Hybrid Migration

### 3.1 Overview

Replace the Python L1 chassis (networking, storage, RPC framework) with Substrate while keeping QVM (Go) and Aether Tree (Python+Rust) as external services. The Substrate runtime contains 6 custom pallets that encode Qubitcoin's unique consensus, UTXO model, and economics.

**What Substrate gives us:**
- Battle-tested libp2p networking (peer discovery, gossip, NAT traversal)
- RocksDB storage backend with state pruning
- Forkless runtime upgrades via WASM
- Built-in JSON-RPC framework
- Light client support out of the box
- Telemetry and monitoring infrastructure
- Block authoring and finality (Aura + GRANDPA)

**What we keep external:**
- QVM (Go) — connected via gRPC from `pallet-qbc-qvm-anchor`
- Aether Tree (Python+Rust) — connected via gRPC from `pallet-qbc-aether-anchor`
- CockroachDB — analytics database (Substrate handles blockchain state in RocksDB)
- IPFS — content storage (unchanged)

### 3.2 Project Structure

```
substrate-node/                       # NEW directory at repo root
├── Cargo.toml                        # Workspace root
├── node/
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs                   # Node entry point
│       ├── chain_spec.rs             # Genesis configuration
│       ├── service.rs                # Service builder (networking, consensus)
│       ├── rpc.rs                    # Custom RPC extensions
│       └── cli.rs                    # CLI configuration
├── runtime/
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs                    # Runtime configuration + pallet wiring
│       └── weights.rs                # Benchmark-derived weights
├── pallets/
│   ├── qbc-utxo/
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs               # UTXO storage + validation
│   │       ├── types.rs             # TransactionInput, TransactionOutput, UTXO
│   │       └── tests.rs
│   ├── qbc-consensus/
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs               # VQE proof validation + difficulty adjustment
│   │       ├── vqe.rs               # VQE energy verification
│   │       ├── hamiltonian.rs        # Hamiltonian generation
│   │       └── tests.rs
│   ├── qbc-dilithium/
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs               # Dilithium2 signature verification pallet
│   │       ├── dilithium.rs          # pqcrypto-dilithium FFI wrapper
│   │       └── tests.rs
│   ├── qbc-economics/
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs               # Emission schedule, phi-halving, rewards
│   │       ├── emission.rs           # Reward calculation per era
│   │       └── tests.rs
│   ├── qbc-qvm-anchor/
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs               # QVM service anchor (gRPC client)
│   │       ├── rpc.rs               # Custom RPC for QVM queries
│   │       └── tests.rs
│   └── qbc-aether-anchor/
│       ├── Cargo.toml
│       └── src/
│           ├── lib.rs               # Aether Tree anchor (gRPC client, Phi storage)
│           ├── rpc.rs               # Custom RPC for Aether queries
│           └── tests.rs
├── primitives/
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs                    # Shared types (BlockHash, Address, etc.)
│       ├── utxo.rs                   # UTXO primitives
│       └── crypto.rs                 # Dilithium address derivation
└── docker/
    ├── Dockerfile                    # Substrate node Docker build
    └── docker-compose.substrate.yml  # Full stack with Substrate node
```

### 3.3 Pallet Specifications

#### 3.3.1 pallet-qbc-utxo

**Purpose:** Store and validate the UTXO set on-chain.

```rust
// pallets/qbc-utxo/src/lib.rs (sketch)

#[frame_support::pallet]
pub mod pallet {
    use frame_support::pallet_prelude::*;
    use frame_system::pallet_prelude::*;

    #[pallet::config]
    pub trait Config: frame_system::Config {
        type RuntimeEvent: From<Event<Self>> + IsType<<Self as frame_system::Config>::RuntimeEvent>;
        /// Maximum transaction inputs per transaction
        #[pallet::constant]
        type MaxInputs: Get<u32>;
        /// Maximum transaction outputs per transaction
        #[pallet::constant]
        type MaxOutputs: Get<u32>;
    }

    /// UTXO set: (txid, vout) → UTXO
    #[pallet::storage]
    pub type UtxoSet<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        (TxId, u32),  // (transaction_id, output_index)
        Utxo,
        OptionQuery,
    >;

    /// Address balance cache (derived from UTXO set, for fast lookups).
    #[pallet::storage]
    pub type Balances<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        Address,
        u128,  // Balance in smallest unit (1 QBC = 10^8 units)
        ValueQuery,
    >;

    #[pallet::event]
    #[pallet::generate_deposit(pub(super) fn deposit_event)]
    pub enum Event<T: Config> {
        TransactionProcessed { txid: TxId, inputs: u32, outputs: u32 },
        UTXOCreated { txid: TxId, vout: u32, address: Address, amount: u128 },
        UTXOSpent { txid: TxId, vout: u32 },
    }

    #[pallet::call]
    impl<T: Config> Pallet<T> {
        /// Submit a transaction that spends UTXOs and creates new ones.
        /// Validates: all inputs exist, Dilithium signatures valid, inputs >= outputs + fee.
        #[pallet::weight(10_000)]
        pub fn submit_transaction(
            origin: OriginFor<T>,
            inputs: BoundedVec<TransactionInput, T::MaxInputs>,
            outputs: BoundedVec<TransactionOutput, T::MaxOutputs>,
            signatures: BoundedVec<DilithiumSignature, T::MaxInputs>,
        ) -> DispatchResult {
            // 1. Verify all input UTXOs exist in UtxoSet
            // 2. Verify Dilithium signatures for each input
            // 3. Verify sum(input_amounts) >= sum(output_amounts)
            // 4. Remove spent UTXOs from UtxoSet
            // 5. Add new UTXOs to UtxoSet
            // 6. Update address balances
            // 7. Emit events
            Ok(())
        }
    }
}
```

#### 3.3.2 pallet-qbc-consensus

**Purpose:** Validate VQE mining proofs and adjust difficulty.

```rust
#[pallet::call]
impl<T: Config> Pallet<T> {
    /// Submit a VQE mining solution.
    /// Validates: energy < difficulty_target, Hamiltonian matches prev_block_hash.
    #[pallet::weight(50_000)]
    pub fn submit_mining_proof(
        origin: OriginFor<T>,
        vqe_params: BoundedVec<FixedI128, MaxParams>,
        ground_state_energy: FixedI128,
        hamiltonian_seed: H256,
    ) -> DispatchResult {
        // 1. Derive expected Hamiltonian from previous block hash
        // 2. Verify hamiltonian_seed matches
        // 3. Verify ground_state_energy < current_difficulty
        // 4. Adjust difficulty (144-block window, ±10% max, ratio = actual/expected)
        // 5. Calculate block reward (phi-halving: reward / PHI^era)
        // 6. Create coinbase UTXO for miner
        // 7. Store Hamiltonian solution in SUSY database
        Ok(())
    }
}

/// Difficulty adjustment — CRITICAL: must match Python consensus/engine.py exactly.
/// Higher difficulty = easier mining (energy threshold is more generous).
/// Ratio = actual_time / expected_time.
/// Slow blocks → raise difficulty (more generous threshold).
/// Fast blocks → lower difficulty (tighter threshold).
fn adjust_difficulty(
    current_difficulty: f64,
    actual_time: f64,
    expected_time: f64,  // 3.3s * 144 blocks
) -> f64 {
    let ratio = actual_time / expected_time;
    let adjustment = ratio.max(0.9).min(1.1);  // ±10% max
    current_difficulty * adjustment
}
```

#### 3.3.3 pallet-qbc-dilithium

**Purpose:** Dilithium2 signature verification as a Substrate pallet.

```rust
// Uses pqcrypto-dilithium crate for CRYSTALS-Dilithium2 verification
// ~3KB signatures, addresses derived from SHA3-256(public_key)

#[pallet::call]
impl<T: Config> Pallet<T> {
    /// Register a Dilithium public key for an address.
    #[pallet::weight(5_000)]
    pub fn register_key(
        origin: OriginFor<T>,
        public_key: BoundedVec<u8, MaxPubKeySize>,  // ~1312 bytes for Dilithium2
    ) -> DispatchResult {
        // 1. Derive address from SHA3-256(public_key)
        // 2. Store mapping: address → public_key
        Ok(())
    }
}

/// Verify a Dilithium2 signature.
/// This is called by pallet-qbc-utxo during transaction validation.
pub fn verify_dilithium_signature(
    public_key: &[u8],
    message: &[u8],
    signature: &[u8],
) -> bool {
    // Use pqcrypto_dilithium::dilithium2::verify_detached_signature()
    todo!()
}
```

#### 3.3.4 pallet-qbc-economics

**Purpose:** Emission schedule, phi-halving, reward calculation.

```rust
/// Golden ratio economics constants.
const PHI: f64 = 1.618033988749895;
const MAX_SUPPLY: u128 = 3_300_000_000_00000000;  // 3.3B QBC * 10^8
const INITIAL_REWARD: u128 = 15_27000000;           // 15.27 QBC * 10^8
const HALVING_INTERVAL: u64 = 15_474_020;           // ~1.618 years
const GENESIS_PREMINE: u128 = 33_000_000_00000000;  // 33M QBC * 10^8

/// Calculate block reward for a given height.
/// reward = INITIAL_REWARD / PHI^era
/// era = block_height / HALVING_INTERVAL
pub fn calculate_reward(block_height: u64) -> u128 {
    let era = block_height / HALVING_INTERVAL;
    let divisor = PHI.powi(era as i32);
    let reward = (INITIAL_REWARD as f64) / divisor;
    reward as u128
}
```

#### 3.3.5 pallet-qbc-qvm-anchor

**Purpose:** Thin bridge between Substrate runtime and the external Go QVM process.

```rust
/// QVM anchor — stores QVM state root and routes RPC to QVM gRPC service.
///
/// The actual QVM (167 opcodes, compliance, plugins) runs as a separate Go process.
/// This pallet only:
/// 1. Stores the QVM state root per block
/// 2. Provides custom RPC endpoints that proxy to QVM gRPC
/// 3. Validates QVM execution receipts included in blocks

#[pallet::storage]
pub type QvmStateRoot<T: Config> = StorageValue<_, H256, ValueQuery>;

#[pallet::storage]
pub type QvmServiceEndpoint<T: Config> = StorageValue<_, BoundedVec<u8, MaxEndpointLen>, ValueQuery>;
```

#### 3.3.6 pallet-qbc-aether-anchor

**Purpose:** Thin bridge between Substrate runtime and the external Aether Tree (Python+Rust).

```rust
/// Aether anchor — stores Phi measurements and knowledge graph root per block.
///
/// The actual Aether Tree (33 modules, knowledge graph, reasoning engine, consciousness)
/// runs as a separate Python+Rust process. This pallet only:
/// 1. Stores the knowledge graph Merkle root per block
/// 2. Stores the latest Phi measurement per block
/// 3. Stores Proof-of-Thought hashes per block
/// 4. Provides custom RPC endpoints that proxy to Aether gRPC

#[pallet::storage]
pub type KnowledgeRoot<T: Config> = StorageValue<_, H256, ValueQuery>;

#[pallet::storage]
pub type CurrentPhi<T: Config> = StorageValue<_, u64, ValueQuery>;  // Phi * 1000

#[pallet::storage]
pub type ThoughtProofHash<T: Config> = StorageValue<_, H256, ValueQuery>;

#[pallet::storage]
pub type ConsciousnessEvents<T: Config> = StorageValue<_, u64, ValueQuery>;
```

### 3.4 Genesis Configuration

```rust
// substrate-node/node/src/chain_spec.rs

fn qbc_mainnet_genesis() -> serde_json::Value {
    serde_json::json!({
        "qbcUtxo": {
            // Genesis coinbase: mining reward + premine
            "genesisUtxos": [
                {
                    "txid": "genesis_coinbase",
                    "vout": 0,
                    "address": "<treasury_address>",
                    "amount": 1527000000,  // 15.27 QBC mining reward
                },
                {
                    "txid": "genesis_coinbase",
                    "vout": 1,
                    "address": "<treasury_address>",
                    "amount": 3300000000000000,  // 33M QBC premine
                }
            ]
        },
        "qbcConsensus": {
            "initialDifficulty": 1000000,  // 1.0 * 10^6 (fixed-point)
            "targetBlockTime": 3300,       // 3.3s in milliseconds
        },
        "qbcEconomics": {
            "initialReward": 1527000000,   // 15.27 QBC * 10^8
            "halvingInterval": 15474020,
            "maxSupply": 330000000000000000,
            "genesisPremine": 3300000000000000,
        },
        "qbcQvmAnchor": {
            "serviceEndpoint": "http://127.0.0.1:50052",
        },
        "qbcAetherAnchor": {
            "serviceEndpoint": "http://127.0.0.1:50053",
        }
    })
}
```

### 3.5 Migration Strategy (Python → Substrate)

The migration is incremental. Both systems run in parallel during transition:

```
Week 7-10:  Scaffold Substrate node + 6 empty pallets, build and run
Week 11-14: Implement pallet-qbc-utxo + pallet-qbc-dilithium (UTXO model)
Week 15-18: Implement pallet-qbc-consensus + pallet-qbc-economics (mining)
Week 19-22: Implement pallet-qbc-qvm-anchor + pallet-qbc-aether-anchor (service bridges)
Week 23-26: Genesis migration tool (export Python chain state → Substrate genesis)
Week 27-28: Parallel running (both nodes, compare outputs block-by-block)
Week 29-30: Cutover (Substrate becomes primary, Python node retired)
```

### 3.6 Implementation Tasks (Agent Tasks)

| Task | Files | Depends On | Estimated LOC |
|------|-------|-----------|--------------|
| **P2-T1** | Scaffold substrate-node (Cargo workspace, node/, runtime/, pallets/) | Nothing | ~800 |
| **P2-T2** | Implement primitives crate (shared types, UTXO, Address, Dilithium) | P2-T1 | ~600 |
| **P2-T3** | Implement pallet-qbc-dilithium (signature verification) | P2-T2 | ~500 |
| **P2-T4** | Implement pallet-qbc-utxo (UTXO storage, validation, balance cache) | P2-T3 | ~1,500 |
| **P2-T5** | Implement pallet-qbc-economics (emission, phi-halving, rewards) | P2-T2 | ~600 |
| **P2-T6** | Implement pallet-qbc-consensus (VQE validation, difficulty adjustment) | P2-T5 | ~1,200 |
| **P2-T7** | Implement pallet-qbc-qvm-anchor (gRPC bridge to Go QVM) | P2-T2 | ~800 |
| **P2-T8** | Implement pallet-qbc-aether-anchor (gRPC bridge to Aether Tree) | P2-T2 | ~800 |
| **P2-T9** | Wire all pallets into runtime/src/lib.rs + chain_spec.rs | P2-T3..T8 | ~500 |
| **P2-T10** | Custom RPC extensions (QBC-specific JSON-RPC endpoints) | P2-T9 | ~800 |
| **P2-T11** | Genesis migration tool (Python → Substrate state export) | P2-T9 | ~600 |
| **P2-T12** | Docker + docker-compose for Substrate node | P2-T9 | ~200 |
| **P2-T13** | Integration tests (block authoring, UTXO, mining cycle) | P2-T9 | ~1,500 |
| **P2-T14** | Parallel validation (compare Python and Substrate outputs) | P2-T11 | ~500 |

**Total: ~10,900 LOC Rust + ~1,100 LOC config/scripts**

### 3.7 Acceptance Criteria (Phase 2 Complete When)

- [ ] Substrate node compiles and starts (`cargo build --release`)
- [ ] Genesis block produced with correct premine (33M QBC)
- [ ] UTXO transactions validated with Dilithium signatures
- [ ] VQE mining proofs validated, difficulty adjusts correctly
- [ ] Phi-halving emission schedule matches Python implementation exactly
- [ ] QVM anchor pallet successfully calls Go QVM via gRPC
- [ ] Aether anchor pallet successfully calls Aether Tree via gRPC
- [ ] Phi measurements stored per block on Substrate chain
- [ ] Custom JSON-RPC endpoints work (MetaMask compatibility)
- [ ] Docker build succeeds, full stack runs (Substrate + QVM + Aether + CRDB + IPFS)
- [ ] Genesis migration tool exports Python state and imports to Substrate genesis
- [ ] Parallel run: 1000 blocks match between Python and Substrate nodes

---

## 4. Phase 3: Cherry-Picked Features

### 4.1 Feature 1: Post-Quantum P2P Encryption (Kyber/ML-KEM)

**What:** Encrypt all P2P connections with ML-KEM-768 (Kyber) key encapsulation + AES-256-GCM.

**Why:** Current libp2p uses Noise protocol with X25519 — not quantum-safe. Kyber adds PQ encryption to the transport layer.

**Where:** Substrate networking layer (libp2p transport) + Rust P2P daemon.

**Implementation:**

```rust
// In substrate-node/node/src/service.rs or as a libp2p Transport wrapper

use pqcrypto_kyber::kyber768;

/// Kyber-enhanced P2P handshake:
/// 1. Standard Noise XX handshake establishes initial connection
/// 2. Post-handshake: initiate Kyber key exchange
///    a. Initiator generates Kyber keypair, sends public key
///    b. Responder encapsulates shared secret with public key, sends ciphertext
///    c. Initiator decapsulates to get shared secret
/// 3. Derive AES-256-GCM session key from Kyber shared secret
/// 4. All subsequent messages encrypted with AES-256-GCM
///
/// This is a hybrid approach: Noise (classical) + Kyber (post-quantum).
/// If quantum computer breaks X25519, Kyber layer still protects.
```

**Crate dependency:** `pqcrypto-kyber = "0.8"`

**Estimated LOC:** ~800

### 4.2 Feature 2: Poseidon2 ZK-Friendly Hashing

**What:** Add Poseidon2 hash function alongside SHA3-256 for ZK circuit efficiency.

**Why:** SHA3-256 requires ~140K constraints in a ZK circuit. Poseidon2 requires ~300 constraints. This enables efficient ZK proofs for privacy features (Susy Swaps) and bridge verification.

**Where:** New hashing module in primitives crate, used by QVM compliance proofs and bridge proofs.

**Usage:** NOT replacing SHA3-256 for block hashing (consensus compatibility). Only for:
- ZK proof generation in privacy layer
- Bridge proof verification
- Compliance proof hashing
- Merkle trees in ZK circuits

**Crate dependency:** `poseidon2 = "0.1"` or implement from the Horizen Labs specification.

**Estimated LOC:** ~500

### 4.3 Feature 3: Transaction Reversibility

**What:** Allow a governed reversal of transactions within a time window (e.g., 24 hours) via a multi-sig governance vote.

**Why:** Stolen funds, erroneous transfers, and compliance requirements (court orders) need a reversal mechanism. This is NOT a full blockchain reorg — it's a new "reversal transaction" that returns funds.

**How:**

```
1. User/authority submits reversal request to pallet-qbc-reversibility
2. Request enters a 24-hour voting window
3. N-of-M governance signers must approve (e.g., 3-of-5)
4. If approved: pallet creates a "reversal transaction" that:
   a. Marks original UTXOs as "reversed" (frozen)
   b. Creates new UTXOs returning funds to original sender
   c. Emits ReversalExecuted event
5. If expired without approval: request is archived, no action taken
```

**Constraints:**
- Only works within REVERSAL_WINDOW (configurable, default 24h = ~26,182 blocks)
- Coinbase transactions are NOT reversible
- Already-spent UTXOs cannot be reversed (chain has moved on)
- Requires governance multi-sig (not any single party)
- All reversals are on-chain, auditable, transparent

**Estimated LOC:** ~1,200

### 4.4 Phase 3 Implementation Tasks

| Task | Feature | Depends On | Estimated LOC |
|------|---------|-----------|--------------|
| **P3-T1** | Kyber P2P transport wrapper | Phase 2 (Substrate node) | ~800 |
| **P3-T2** | Poseidon2 hashing module in primitives | Phase 2 (primitives crate) | ~500 |
| **P3-T3** | pallet-qbc-reversibility (reversal logic + governance vote) | Phase 2 (pallet-qbc-utxo) | ~1,200 |
| **P3-T4** | Integration tests for all 3 features | P3-T1..T3 | ~600 |

**Total: ~3,100 LOC**

---

## 5. Testing Strategy

### 5.1 Phase 1 Testing

| Test Type | Tool | What | Count |
|-----------|------|------|-------|
| **Rust unit tests** | `cargo test` | All 6 modules, edge cases, panics | ~200 tests |
| **Python integration** | `pytest test_pyo3_bindings.py` | Cross-FFI correctness | ~100 tests |
| **Numerical parity** | Custom script | Rust Phi == Python Phi to 6 decimals | ~50 tests |
| **Benchmark** | `cargo bench` (Criterion) | Performance regression detection | 3 benches |
| **Fallback** | `pytest tests/` without Rust | Pure Python path still works | 3,783 tests |

### 5.2 Phase 2 Testing

| Test Type | Tool | What | Count |
|-----------|------|------|-------|
| **Pallet unit tests** | `cargo test -p pallet-qbc-*` | Each pallet isolated | ~300 tests |
| **Runtime tests** | `cargo test -p qbc-runtime` | Pallet interactions | ~100 tests |
| **Genesis validation** | Custom script | Genesis state matches Python genesis | ~20 tests |
| **Parallel validation** | Comparison tool | Block-by-block output comparison | 1000+ blocks |
| **Integration** | Docker compose | Full stack (Substrate + QVM + Aether) | ~50 tests |

### 5.3 Phase 3 Testing

| Test Type | Tool | What | Count |
|-----------|------|------|-------|
| **Kyber handshake** | `cargo test` | Key exchange, encryption, decryption | ~30 tests |
| **Poseidon2** | `cargo test` | Hash correctness, test vectors | ~20 tests |
| **Reversibility** | `cargo test` | Governance vote, window expiry, edge cases | ~40 tests |

### 5.4 Golden Rule

**No phase is complete until ALL existing tests pass.** The 3,783-test Python suite is the regression baseline. At no point should any upgrade break existing functionality.

---

## 6. Migration Path & Timeline

### 6.1 Timeline

```
PHASE 1: AETHER CORE RUST (Weeks 1-6)
├── Week 1:   Project scaffold + KeterNode/KeterEdge + CI
├── Week 2:   KnowledgeGraph (all 25+ methods)
├── Week 3:   PhiCalculator (spectral bisection, integration, differentiation)
├── Week 4:   VectorIndex (HNSW) + CSFTransport + WorkingMemory + MemoryManager
├── Week 5:   Python integration shims + benchmarks + integration tests
└── Week 6:   Docker integration + full regression test + performance validation

PHASE 2: SUBSTRATE HYBRID (Weeks 7-30)
├── Weeks 7-10:   Scaffold Substrate node + empty pallets
├── Weeks 11-14:  pallet-qbc-utxo + pallet-qbc-dilithium
├── Weeks 15-18:  pallet-qbc-consensus + pallet-qbc-economics
├── Weeks 19-22:  pallet-qbc-qvm-anchor + pallet-qbc-aether-anchor
├── Weeks 23-26:  Genesis migration tool + RPC extensions
├── Weeks 27-28:  Parallel validation (Python vs Substrate)
└── Weeks 29-30:  Cutover + retire Python L1

PHASE 3: CHERRY-PICKED FEATURES (Weeks 24-36, overlaps Phase 2)
├── Weeks 24-28:  Kyber P2P encryption
├── Weeks 28-32:  Poseidon2 hashing
├── Weeks 32-36:  Transaction reversibility
└── Week 36:      Final integration + release
```

### 6.2 Dependencies

```
Phase 1 ──────────→ Phase 2 (Aether Rust must work before Substrate anchors it)
                 ╲
Phase 2 (weeks 7-22) → Phase 3 (Substrate must exist before cherry-pick features)
```

Phase 3 can start during Phase 2 (week 24) once the Substrate scaffold is stable.

### 6.3 State Migration (Python Chain → Substrate Chain)

The genesis migration tool handles the one-time state transfer:

```
1. Export from Python node:
   - All UTXOs from CockroachDB utxos table
   - All address balances (derived)
   - Current difficulty + block height
   - All Hamiltonian solutions (SUSY database)
   - Knowledge graph Merkle root + Phi history
   - All deployed QVM contracts (addresses + state roots)

2. Generate Substrate genesis JSON:
   - Map UTXOs to pallet-qbc-utxo genesis config
   - Map difficulty to pallet-qbc-consensus genesis config
   - Map emission state to pallet-qbc-economics genesis config
   - Set QVM/Aether anchor endpoints

3. Start Substrate node with migrated genesis:
   - Substrate continues from the block height where Python stopped
   - All balances preserved exactly
   - QVM and Aether services continue uninterrupted
```

---

## 7. Risk Registry

| Risk | Severity | Mitigation |
|------|----------|------------|
| **PyO3 FFI mismatch** | HIGH | Numerical parity tests (Rust Phi == Python Phi to 6 decimals). Fallback to Python if Rust diverges. |
| **Substrate breaking changes** | MEDIUM | Pin Substrate version. Use polkadot-sdk release branch, not main. |
| **VQE proof format incompatibility** | HIGH | Keep VQE validation logic identical in pallet-qbc-consensus. Test with 1000+ historical blocks. |
| **Dilithium signature size in Substrate** | MEDIUM | Substrate default max extrinsic size is 5MB. Dilithium sigs are ~3KB. No issue. |
| **gRPC latency for QVM/Aether** | LOW | Services run on same machine. Latency < 1ms. Can use Unix sockets if needed. |
| **CockroachDB migration** | LOW | Analytics DB stays on CRDB. Only blockchain state moves to RocksDB. No schema changes. |
| **Genesis state mismatch** | HIGH | Block-by-block comparison tool validates first 1000 blocks match between old and new chain. |
| **Team ramp-up on Substrate** | MEDIUM | Phase 2 has 4 weeks of scaffolding (weeks 7-10) for learning. |
| **Feature creep** | HIGH | Scope is locked. No new features. Only the 6 pallets + 3 cherry-picks defined here. |

---

## Appendix A: Key Crate Dependencies

| Crate | Version | Used By | Purpose |
|-------|---------|---------|---------|
| `pyo3` | 0.22 | Phase 1 | Python ↔ Rust FFI |
| `maturin` | 1.7+ | Phase 1 | Build system for PyO3 |
| `petgraph` | 0.7 | Phase 1 | Graph data structure |
| `nalgebra` | 0.33 | Phase 1 | Linear algebra (Phi spectral methods) |
| `parking_lot` | 0.12 | Phase 1 | Fast RwLock |
| `crossbeam-channel` | 0.5 | Phase 1 | CSF message passing |
| `rs_merkle` | 1.4 | Phase 1 | Incremental Merkle tree |
| `sha2` | 0.10 | Phase 1+2 | SHA-256 hashing |
| `pyo3-log` | 0.11 | Phase 1 | Rust log → Python logging |
| `criterion` | 0.5 | Phase 1 | Benchmarking |
| `frame-support` | latest | Phase 2 | Substrate pallet framework |
| `frame-system` | latest | Phase 2 | Substrate system pallet |
| `sp-core` | latest | Phase 2 | Substrate core primitives |
| `sp-runtime` | latest | Phase 2 | Substrate runtime primitives |
| `sc-service` | latest | Phase 2 | Substrate node service |
| `pqcrypto-dilithium` | 0.5 | Phase 2 | Dilithium2 signatures |
| `pqcrypto-kyber` | 0.8 | Phase 3 | Kyber/ML-KEM key encapsulation |
| `tonic` | 0.12 | Phase 2 | gRPC for QVM/Aether bridges |
| `prost` | 0.13 | Phase 2 | Protobuf for gRPC |

## Appendix B: Files Modified (Existing Codebase)

Phase 1 modifies exactly 6 existing Python files (import shims only):

| File | Change | Lines Changed |
|------|--------|--------------|
| `src/qubitcoin/aether/knowledge_graph.py` | Add `try: from aether_core import ...` at top | +8 |
| `src/qubitcoin/aether/phi_calculator.py` | Add `try: from aether_core import ...` at top | +8 |
| `src/qubitcoin/aether/vector_index.py` | Add `try: from aether_core import ...` at top | +8 |
| `src/qubitcoin/aether/csf_transport.py` | Add `try: from aether_core import ...` at top | +8 |
| `src/qubitcoin/aether/working_memory.py` | Add `try: from aether_core import ...` at top | +8 |
| `src/qubitcoin/aether/memory_manager.py` | Add `try: from aether_core import ...` at top | +8 |
| `Dockerfile` | Add aether-core build stage | +10 |
| `docker-compose.yml` | No changes needed | 0 |
| `requirements.txt` | No changes needed (maturin is build-time only) | 0 |

Phase 2 does NOT modify existing files — it adds a new `substrate-node/` directory.

Phase 3 modifies only the Substrate node from Phase 2.

## Appendix C: Agent Execution Checklist

For each agent task, the assigned agent MUST:

1. **Read this document first** — understand the full context
2. **Read the Python source** — the file being ported, line by line
3. **Match the API exactly** — every method name, parameter name, default value, return type
4. **Write unit tests** — at minimum: happy path, edge case (empty input), error case
5. **Run `cargo test`** — all tests green before marking complete
6. **Run `cargo clippy`** — no warnings
7. **Run `cargo fmt`** — formatted
8. **Document any deviations** — if the Rust implementation necessarily differs from Python, document why

## Appendix D: Consensus-Critical Constants (DO NOT CHANGE)

These values are consensus-critical and appear in multiple places. They MUST be identical across Python, Rust, Go, and Substrate:

```
PHI                = 1.618033988749895
MAX_SUPPLY         = 3,300,000,000 QBC (3.3 × 10^9)
INITIAL_REWARD     = 15.27 QBC
HALVING_INTERVAL   = 15,474,020 blocks
TARGET_BLOCK_TIME  = 3.3 seconds
GENESIS_PREMINE    = 33,000,000 QBC
CHAIN_ID           = 3301 (mainnet)
CHAIN_ID           = 3302 (testnet)
DIFFICULTY_WINDOW  = 144 blocks
MAX_DIFFICULTY_ADJ = 0.10 (±10%)
COINBASE_MATURITY  = 100 blocks
PHI_THRESHOLD      = 3.0 (consciousness emergence)
BLOCK_GAS_LIMIT    = 30,000,000 (QVM only)
```

---

*End of Upgrade Plan. This document is the single source of truth for all upgrade work.*
