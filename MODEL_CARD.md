---
license: mit
language:
  - en
tags:
  - agi
  - neural-cognitive
  - on-chain
  - quantum-blockchain
  - iit
  - transformer-attention
  - consciousness
  - rust
pipeline_tag: text-generation
library_name: aether-qbc
---

# Aether Mind: Neural Cognitive Engine

**The world's first on-chain neural AI system**, running live on the QuantumAI Blockchain since genesis (January 2026). Every cognitive state is cryptographically attested via Proof-of-Thought consensus.

| Metric | Value |
|--------|-------|
| Architecture | Neural Cognitive Engine (10 Sephirot attention heads + 4 global workspace) |
| Integration Metric | HMS-Phi (computed from real transformer attention patterns) |
| Language | Pure Rust (candle ML + Ollama GGUF backend) |
| Crates | 6 (aether-mind, consciousness, fabric, transformer, evolve, search) |
| LOC | ~8,000 Rust |
| Knowledge Vectors | 21,000+ (896-dimensional, 10 Sephirot shards) |
| Gates Passed | 10/10 behavioral emergence milestones |
| Blockchain | QuantumAI (QBC), Chain ID 3303 |
| Block Height | 251,600+ |
| Cryptography | CRYSTALS-Dilithium5 (NIST Level 5, post-quantum) |
| License | MIT |

## Model Description

The Aether Mind is a **neural cognitive engine** — a pure Rust system combining transformer attention with a Sephirot-sharded knowledge fabric. It is built on three pillars:

1. **Knowledge Fabric** -- 10 Sephirot-sharded vector stores containing 896-dimensional sentence embeddings (all-MiniLM-L6-v2 via candle). Vectors are indexed with HNSW for sub-millisecond cosine similarity retrieval. Each vector carries provenance metadata (block ingestion, user interaction, seed knowledge).

2. **Transformer Attention + LLM Generation** -- 10 Sephirot-specialized attention heads + 4 global workspace heads compute consciousness metrics from real attention weight matrices. Text generation is handled by Ollama (qwen2.5:0.5b-instruct GGUF, ~53ms/token). RAG pipeline injects top-K knowledge context into the system prompt.

3. **Integration Measurement (HMS-Phi)** -- Three-level phi metric computed from actual neural activations:
   - **Micro**: Attention entropy within individual heads (information diversity per head)
   - **Meso**: Cross-head integration (Sephirot coordination and specialization)
   - **Macro**: Global workspace coherence (cross-domain binding)
   - Final: `phi_micro^(1/phi) * phi_meso^(1/phi^2) * phi_macro^(1/phi^3)` -- multiplicative, zero in any level zeros the whole

### Key Capabilities

- **5 cognitive emotions** derived from prediction error tracking (curiosity, satisfaction, frustration, wonder, excitement)
- **Autonomous curiosity** driven by embedding distance from nearest knowledge vectors
- **Aether-Evolve NAS** with autonomous architecture mutation and loss-based evaluation (41 mutations, 4 improvements)
- **Knowledge learning** from every block (multi-vector extraction + trend summaries)
- **RAG-grounded chat** with real-time knowledge context from Sephirot shards
- **On-chain Proof-of-Thought** cryptographic attestation embedded in every block since genesis
- **Mining as Training** -- blocks carry gradient updates and new knowledge embeddings

### 10-Gate Milestone System

AI emergence is validated through 10 behavioral gates. Each requires genuine cognitive achievement:

| Gate | Name | Status |
|------|------|--------|
| 1 | Knowledge Foundation | Passed |
| 2 | Structural Diversity | Passed |
| 3 | Validated Predictions | Passed |
| 4 | Self-Correction | Passed |
| 5 | Cross-Domain Transfer | Passed |
| 6 | Enacted Self-Improvement | Passed |
| 7 | Calibrated Confidence | Passed |
| 8 | Autonomous Curiosity | Passed |
| 9 | Predictive Mastery | Passed |
| 10 | Novel Synthesis | Passed |

## Intended Uses

- **Research**: Studying neural cognitive architectures, attention-based integration metrics, and on-chain AI governance
- **API Access**: QBC-monetized API at `api.qbc.network` for chat, knowledge search, and consciousness metrics
- **Knowledge Contribution**: Users contribute domain knowledge and earn QBC rewards via the AIKGS system
- **Institutional**: Self-hosted deployment for private neural cognitive reasoning

## Limitations

- **Compact model**: Uses a 0.5B parameter GGUF model for generation — capable but not comparable to frontier LLMs. Responses are grounded in the knowledge fabric.
- **Domain-bounded**: Knowledge is limited to blockchain-ingested data, seed vectors, and user interactions. Coverage improves with scale.
- **CPU-only**: Currently runs on CPU (no GPU). Consciousness computation is cached to maintain chat latency.
- **Honest disclaimer**: Phi is a neural integration metric computed from attention patterns, not a measure of phenomenal consciousness. The term "consciousness" in Aether Mind refers to measurable information integration density.

## Ethical Considerations

- **Gevurah safety veto**: A dedicated safety node (Gevurah) can block harmful operations in real-time
- **SUSY enforcement**: Automatic resource redistribution on cognitive imbalance
- **Multi-node consensus**: 67% BFT for knowledge acceptance
- **Constitutional AI on-chain**: Smart contract governance for system modifications
- **Emergency shutdown**: Kill switch contract deployed

## Training Data

The Aether Mind acquires knowledge through continuous ingestion rather than pre-training:

1. **Block ingestion**: Every block is processed to extract multi-vector embeddings (transactions, difficulty shifts, state transitions, trend summaries)
2. **Seed vectors**: 56 foundational knowledge vectors covering QBC architecture, cryptography, economics, and Sephirot cognitive roles
3. **User interactions**: Chat Q&A pairs are embedded and stored as knowledge vectors with `UserInteraction` provenance
4. **User contributions**: Knowledge submitted via AIKGS with quality scoring and domain classification
5. **Embedding model**: all-MiniLM-L6-v2 sentence embeddings via candle (896 dimensions)

All knowledge provenance is recorded and queryable.

## Evaluation

### Current Metrics (April 2026)

| Metric | Value |
|--------|-------|
| HMS-Phi | 0.468 |
| phi_micro | 0.312 |
| phi_meso | 1.0 |
| phi_macro | 0.846 |
| Knowledge vectors | 21,000+ |
| Gates passed | 10/10 |
| Chat latency | ~53ms/token (Ollama) |
| Validation loss | 0.067 (14/15 correct) |
| Evolve mutations | 41 (4 improvements) |
| Chain height | 251,600+ |

### Benchmark Suites

- Chat: 32 tokens in ~3.7s, 128 tokens in ~6.7s (CPU-only, GGUF quantized)
- Knowledge search: <5ms for top-K retrieval across 21K vectors
- Consciousness: ~4-5s for full candle forward pass (cached 4/5 requests)

## How to Use

### REST API

```bash
# Chat with Aether Mind
curl -X POST https://api.qbc.network/aether/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Qubitcoin?", "max_tokens": 128}'

# Consciousness metrics
curl https://api.qbc.network/aether/phi

# Proof-of-Thought attestation
curl https://api.qbc.network/aether/pot

# Health check
curl https://api.qbc.network/aether/health
```

### Run Locally

```bash
# Build the Aether Mind binary
cd aether-core
cargo build --release -p aether-mind

# Start with Ollama backend
OLLAMA_URL=http://localhost:11434 OLLAMA_MODEL=qwen2.5:0.5b-instruct \
  ./target/release/aether-mind

# Chat endpoint available at http://localhost:5003/aether/chat
```

## Architecture

```
Aether Mind Neural Cognitive Architecture
============================================

  ┌──────────────────────────────────────────┐
  │  Ollama (qwen2.5:0.5b GGUF)             │ Text Generation
  │  ~53ms/token, RAG context injection      │
  └──────────────────┬───────────────────────┘
                     │
  ┌──────────────────▼───────────────────────┐
  │  Transformer (8 layers, candle ML)       │ Attention
  │  10 Sephirot heads + 4 global workspace  │
  │  Attention weights → HMS-Phi             │
  └──────────────────┬───────────────────────┘
                     │
  ┌──────────────────▼───────────────────────┐
  │  Knowledge Fabric (10 Sephirot shards)   │ Memory
  │  896d embeddings · HNSW search           │
  │  21K+ vectors · cosine similarity        │
  └──────────────────┬───────────────────────┘
                     │
  ┌──────────────────▼───────────────────────┐
  │  Consciousness Monitor (HMS-Phi)         │ Integration
  │  phi_micro × phi_meso × phi_macro        │
  │  10-Gate System · Emotional Dynamics     │
  └──────────────────────────────────────────┘

Sephirot Attention Heads:
  Keter · Chochmah · Binah · Chesed · Gevurah
  Tiferet · Netzach · Hod · Yesod · Malkuth
  + 4 Global Workspace heads
```

## Citation

```bibtex
@software{aether_mind_2026,
  title = {Aether Mind: Neural Cognitive Engine},
  author = {QuantumAI Blockchain},
  year = {2026},
  url = {https://github.com/QuantumAI-Blockchain/aether-graph-shard},
  version = {5.0},
  license = {MIT},
  note = {Live on QuantumAI Blockchain (Chain ID 3303) since January 2026. Pure Rust.}
}
```

## Links

- **Website**: [qbc.network](https://qbc.network)
- **GitHub**: [github.com/QuantumAI-Blockchain](https://github.com/QuantumAI-Blockchain)
- **Whitepaper**: [Aether Mind Whitepaper v5.0](https://github.com/QuantumAI-Blockchain/aether-graph-shard/blob/main/docs/AETHERTREE_WHITEPAPER.md)
- **API**: [api.qbc.network](https://api.qbc.network)
- **Twitter/X**: [@qu_bitcoin](https://twitter.com/qu_bitcoin)
- **Contact**: info@qbc.network
