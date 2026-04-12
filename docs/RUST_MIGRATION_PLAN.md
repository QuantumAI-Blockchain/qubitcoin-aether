# Aether Tree V5: Full Rust Migration Plan

**Version**: 5.0 (V5 Fork)
**Date**: April 2026
**Goal**: Replace ALL 143 Python modules (~73K LOC) with native Rust (~51K new LOC)
**Scale Target**: MAX — 1B+ nodes, 1M+ concurrent users, sub-millisecond cognitive cycles
**Directive**: 100% migration NOW. No partial upgrades. No future phases. Ship pure Rust.

---

## 1. Architecture: Rust Workspace

```
aether-core/                          # Workspace root
├── Cargo.toml                        # [workspace] with all members
├── crates/
│   ├── aether-types/                 # Shared types: KeterNode, KeterEdge, domains [DONE]
│   ├── aether-graph/                 # KnowledgeGraph: in-memory + DB-backed [DONE]
│   ├── aether-phi/                   # PhiCalculator, IIT, gate system [DONE]
│   ├── aether-memory/                # VectorIndex/HNSW, WorkingMemory, MemoryManager [DONE]
│   ├── aether-neural/                # GATReasoner, trainer [DONE]
│   ├── aether-sephirot/              # CSF transport, Higgs field, 10 processors, manager [DONE]
│   ├── aether-reasoning/             # Deductive/inductive/abductive, causal, debate [DONE]
│   ├── aether-nlp/                   # NLP pipeline, summarizer, entity extraction
│   ├── aether-knowledge/             # Knowledge extractor, seeder, scorer
│   ├── aether-cognitive/             # 50+ small cognitive modules
│   ├── aether-safety/                # Gevurah veto, adversarial defense
│   ├── aether-chat/                  # Chat engine, intent handlers, LLM adapter
│   ├── aether-persistence/           # sqlx + CockroachDB (replaces SQLAlchemy)
│   ├── aether-protocol/              # Proof-of-Thought, on-chain bridge, task protocol
│   ├── aether-infra/                 # WebSocket, AIKGS client, telegram, API vault
│   ├── aether-engine/                # AetherEngine orchestrator (wires everything)
│   └── aether-pyo3/                  # Single cdylib exposing ALL types to Python [DONE]
└── tests/                            # Integration tests
```

## 2. Crate Dependency DAG

```
aether-types          (leaf, no internal deps)
   ^
aether-graph          (types)
aether-memory         (types)
aether-phi            (types, graph)
aether-neural         (types)
aether-nlp            (types)
aether-safety         (types)
aether-persistence    (types, graph)
   ^
aether-reasoning      (types, graph, memory, neural)
aether-sephirot       (types, graph, reasoning)
aether-knowledge      (types, graph, nlp)
aether-cognitive      (types, graph, memory, reasoning)
   ^
aether-chat           (types, graph, reasoning, sephirot, knowledge)
aether-protocol       (types, graph, phi, reasoning, persistence)
aether-infra          (types)
   ^
aether-engine         (ALL crates)
   ^
aether-pyo3           (engine + all, exposes PyO3 bindings)
```

## 3. Migration Batches

| Batch | Week | Target | New Rust LOC | Milestone |
|-------|------|--------|-------------|-----------|
| Batch | Status | Target | New Rust LOC | Tests | Milestone |
|-------|--------|--------|-------------|-------|-----------|
| 0 | **DONE** | Workspace restructure (7 crates) | 0 | 276 | Workspace + CI green |
| 1 | **DONE** | Types + Persistence (sqlx CockroachDB) | ~2,000 | 307 | Rust reads/writes DB |
| 2 | **DONE** | Graph + Phi (DB-backed) | ~2,200 | 316 | KnowledgeGraph live |
| 3 | **DONE** | Reasoning + Causal + Debate | ~6,200 | 421 | Reasoning engine |
| 4 | **DONE** | Sephirot (manager, Higgs, 10 processors) | ~5,035 | 484 | Tree of Life architecture |
| 5 | NEXT | Memory + Vector (ONNX embeddings) | ~3,000 | — | Memory system in Rust |
| 6 | — | NLP + Knowledge processing | ~5,000 | — | Knowledge pipeline |
| 7 | — | Metacognition + Self-Improvement | ~4,000 | — | Self-improvement loop |
| 8 | — | Advanced Cognitive (35+ modules) | ~5,500 | — | All cognitive modules |
| 9 | — | Chat + LLM + Safety | ~6,000 | — | User-facing layer |
| 10 | — | Protocol + Infrastructure | ~5,000 | — | AetherEngine orchestrator |
| 11 | — | Integration + Python removal | ~500 | — | Pure Rust Aether Tree |
| **Total** | **4/11 done** | **143 modules** | **~15,435 done / ~51,000 target** | **484** | **30% complete** |

## 4. Zero-Downtime Strategy

Each module follows this pattern:
1. Write Rust implementation in appropriate crate with `#[pyclass]` / `#[pymethods]`
2. Register in `aether-pyo3/src/lib.rs`
3. Add shim at bottom of Python module: `try: from aether_core import RustFoo`
4. Run existing Python tests against Rust-backed version
5. Write Rust-native tests (`#[cfg(test)]`)
6. Soak on live chain for 1+ week
7. Remove Python module once Rust is proven stable

## 5. Critical Path: Database Migration

The biggest challenge: 6 Python modules use SQLAlchemy. Solution:

- `aether-persistence` crate uses `sqlx` (async Rust PostgreSQL driver)
- Connects to same CockroachDB instance
- Both Python (SQLAlchemy) and Rust (sqlx) access DB during transition
- CockroachDB handles concurrent access safely
- Python shim passes connection string: `RustKnowledgeGraph(db_url="postgresql://...")`

## 6. Key Dependencies

```toml
# Core
pyo3 = "0.23"
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }

# Graph + Math
petgraph = "0.7"
nalgebra = "0.33"
ndarray = "0.16"

# Database
sqlx = { version = "0.8", features = ["runtime-tokio", "postgres", "chrono", "json"] }

# HTTP + gRPC
reqwest = { version = "0.12", features = ["json", "rustls-tls"] }
tonic = "0.12"

# ML/Embeddings
candle-core = "0.8"
tokenizers = "0.21"

# Concurrency
rayon = "1.10"
parking_lot = "0.12"
crossbeam-channel = "0.5"
```

## 7. V5 Gate System

The 10-gate milestone system carries forward unchanged. If gates need re-evaluation
after the Rust migration, that is acceptable. V5 is a performance and architecture
upgrade, not a gate reset.

## 8. Testing Protocol

Per-module:
1. Rust unit tests (`#[cfg(test)]`)
2. Python compatibility tests (existing pytest against Rust-backed shim)
3. Comparison tests (run both Python and Rust for 1000+ blocks, diff outputs)
4. Criterion benchmarks (verify Rust is faster)

Integration:
5. Block cycle test (mine 100 blocks with Rust Aether)
6. Chat regression test (replay 50 saved conversations)
7. Genesis test (fresh DB with Rust genesis, verify node/edge counts match)

CI:
8. `cargo test --workspace`
9. `cargo bench --workspace`
10. `pytest tests/unit/test_aether*.py` (Python compatibility)
11. `cargo clippy -W clippy::all`

---

**Current Status (2026-04-12)**: Batches 0-4 COMPLETE. 9 crates, 484 Rust tests, ~15,435 new LOC.
Core architecture (types, graph, phi, persistence, reasoning, sephirot) fully in Rust.
Ready for Batch 5 (memory + vector index with ONNX embeddings).

### Completed Crate LOC Breakdown

| Crate | Files | LOC | Tests |
|-------|-------|-----|-------|
| aether-types | 6 | ~1,200 | 124 |
| aether-persistence | 6 | ~900 | 13 |
| aether-graph | 5 | ~2,100 | 59 |
| aether-phi | 2 | ~800 | 37 |
| aether-memory | 3 | ~600 | 8 |
| aether-neural | 3 | ~500 | 0 |
| aether-reasoning | 8 | ~4,300 | 123 |
| aether-sephirot | 5 | ~6,984 | 119 |
| aether-pyo3 | 1 | ~100 | 1 |
| **Total** | **39** | **~17,484** | **484** |
