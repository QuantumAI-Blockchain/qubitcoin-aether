# Aether Core

Rust acceleration library for the Aether Tree AI engine, exposed to Python via PyO3 bindings. Implements performance-critical modules — knowledge graph operations, integrated information (Phi) calculation, vector similarity search, CSF message transport, and memory management — as native Rust crates. Provides 10-100x speedup over pure Python on hot-path AI computations.

The Aether Tree is Qubitcoin's on-chain AI reasoning engine. Long-term, the project aspires toward AGSI (Artificial General Super Intelligence) through genuine cognitive integration and causal reasoning.

## Key Features

- **Knowledge Graph** — Lock-free concurrent graph with KeterNode storage, edge adjacency, and Merkle root computation.
- **Phi Calculator** — Hierarchical Multi-Scale Phi (HMS-Phi) computation with spectral MIP bisection for measuring cognitive integration.
- **Vector Index** — Approximate nearest neighbor search for semantic similarity across knowledge nodes.
- **CSF Transport** — Cerebrospinal Fluid message routing between Sephirot cognitive nodes with priority queuing.
- **Working Memory** — Attention-gated working memory with capacity limits and decay.
- **Memory Manager** — Three-tier memory lifecycle: short-term, long-term, and archival with consolidation.

## Quick Start

```bash
# Build all crates
cargo build --release

# Build Python extension (via maturin)
pip install maturin
maturin develop --release

# Use from Python
from aether_core import KnowledgeGraph, PhiCalculator, VectorIndex
```

## Architecture

```
aether-core/
├── crates/
│   ├── aether-graph/        # Knowledge graph: nodes, edges, Merkle roots
│   ├── aether-phi/          # HMS-Phi: IIT integration metrics, spectral MIP
│   ├── aether-knowledge/    # Knowledge scoring, extraction, seeding
│   ├── aether-memory/       # Working memory, attention gating
│   ├── aether-persistence/  # Memory consolidation, 3-tier lifecycle
│   ├── aether-reasoning/    # Deductive, inductive, abductive inference
│   ├── aether-logic/        # Causal engine, formal logic
│   ├── aether-neural/       # Graph attention networks, online training
│   ├── aether-nlp/          # Natural language processing utilities
│   ├── aether-temporal/     # Temporal reasoning, prediction verification
│   ├── aether-sephirot/     # 10 Sephirot cognitive node implementations
│   ├── aether-cognitive/    # Consciousness tracking, metacognition
│   ├── aether-chat/         # Chat interface logic
│   ├── aether-engine/       # Core engine orchestration
│   ├── aether-protocol/     # Proof-of-Thought protocol
│   ├── aether-safety/       # Gevurah safety veto, alignment checks
│   ├── aether-infra/        # CSF transport, infrastructure
│   ├── aether-types/        # Shared type definitions
│   └── aether-pyo3/         # PyO3 Python bindings
├── benches/                 # Criterion benchmarks
├── Cargo.toml               # Workspace manifest
└── pyproject.toml           # Python package configuration
```

### Integration

The Rust crates accelerate corresponding Python modules in `src/qubitcoin/aether/`:

| Rust Crate          | Python Module             | Speedup   |
|---------------------|---------------------------|-----------|
| `aether-graph`      | `knowledge_graph.py`      | ~50x      |
| `aether-phi`        | `phi_calculator.py`       | ~100x     |
| `aether-knowledge`  | `knowledge_scorer.py`     | ~20x      |
| `aether-infra`      | `csf_transport.py`        | ~30x      |
| `aether-memory`     | `working_memory.py`       | ~40x      |

Python falls back to pure-Python implementations when the Rust extension is unavailable.

## Testing

```bash
# Rust tests
cargo test --workspace

# Benchmarks
cargo bench

# Python integration
pytest tests/ -k aether
```

## License

MIT. See [LICENSE](../LICENSE).

## Links

- [Main Repository](https://github.com/QuantumAI-Blockchain/qubitcoin-node)
- [Aether Core Repo](https://github.com/QuantumAI-Blockchain/aether-graph-shard)
- [Aether Tree Whitepaper](../docs/AETHERTREE_WHITEPAPER.md)
