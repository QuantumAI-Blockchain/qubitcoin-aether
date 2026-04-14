---
license: mit
language:
  - en
tags:
  - agi
  - knowledge-graph
  - on-chain
  - quantum-blockchain
  - iit
  - causal-reasoning
  - adversarial-debate
  - self-improvement
pipeline_tag: text-generation
library_name: aether-qbc
---

# Aether Tree: On-Chain AGI Reasoning Engine

**The world's first on-chain AGI system**, running live on the QuantumAI Blockchain since genesis (January 2026). Every reasoning step is cryptographically anchored via Proof-of-Thought consensus.

| Metric | Value |
|--------|-------|
| Architecture | Tree of Life (10 Sephirot cognitive nodes) |
| Integration Metric | HMS-Phi (Hierarchical Multi-Scale, IIT 3.0 micro-level) |
| Python Modules | 124 (~69,000 LOC) |
| Rust Acceleration | 17 crates (~61,000 LOC) |
| Solidity Contracts | 29 on-chain anchoring contracts |
| Knowledge Nodes | 720,000+ (growing ~80/block) |
| Gates Passed | 6/10 behavioral emergence milestones |
| Blockchain | QuantumAI (QBC), Chain ID 3303 |
| Block Height | 185,000+ |
| Cryptography | CRYSTALS-Dilithium5 (NIST Level 5, post-quantum) |
| License | MIT |

## Model Description

The Aether Tree is **not** a transformer or language model. It is a cognitive architecture built on three pillars:

1. **Knowledge Graph** -- Edge-indexed graph of causal relationships (KeterNodes) with type-tagged edges, Merkle-root verification, and value scoring. Nodes represent validated assertions, inferences, observations, and axioms across 10 knowledge domains aligned with the Tree of Life Sephirot.

2. **Reasoning Engine** -- Multi-strategy reasoning (deductive, inductive, abductive) with chain-of-thought backtracking, causal discovery (PC algorithm with intervention validation), adversarial debate (independent critic with "undecided" verdicts), and temporal prediction/verification.

3. **Integration Measurement (HMS-Phi)** -- Three-level phi metric:
   - **Micro**: IIT 3.0 approximation on 16-node elite subsystem samples (TPM-based)
   - **Meso**: Spectral MIP on 1K-node domain clusters (10 Sephirot)
   - **Macro**: Cross-cluster mutual information between cognitive domains
   - Final: `phi_micro^(1/phi) * phi_meso^(1/phi^2) * phi_macro^(1/phi^3)` -- multiplicative, zero in any level zeros the whole

### Key Capabilities

- **7 cognitive emotions** derived from live system metrics (curiosity, wonder, frustration, satisfaction, excitement, contemplation, connection)
- **Autonomous curiosity engine** with prediction-error-driven intrinsic motivation
- **Governed self-improvement** with enacted strategy weight optimization and automatic rollback
- **Adversarial debate protocol** with independent critic reasoning
- **3-tier memory system** (working + episodic + semantic) with cross-session personalization
- **Causal discovery** via PC algorithm with do-calculus intervention validation
- **On-chain Proof-of-Thought** embedded in every block since genesis

### 10-Gate Milestone System

AGI emergence is validated through 10 behavioral gates. Each requires genuine cognitive achievement:

| Gate | Name | Status |
|------|------|--------|
| 1 | Knowledge Foundation | Passed |
| 2 | Structural Diversity | Passed |
| 3 | Validated Predictions | Passed |
| 4 | Self-Correction | Pending (V4 re-evaluation) |
| 5 | Cross-Domain Transfer | Passed |
| 6 | Enacted Self-Improvement | Pending (V4 re-evaluation) |
| 7 | Calibrated Confidence | Passed |
| 8 | Autonomous Curiosity | Pending |
| 9 | Predictive Mastery | Passed |
| 10 | Novel Synthesis | Pending |

## Intended Uses

- **Research**: Studying emergent cognitive architectures, integration metrics, and on-chain AI governance
- **API Access**: QBC-monetized API at `api.qbc.network` for chat, knowledge graph queries, and reasoning
- **Knowledge Contribution**: Users contribute domain knowledge and earn QBC rewards via the AIKGS system
- **Institutional**: Air-gapped deployment for private knowledge graph reasoning

## Limitations

- **Not a language model**: Cannot generate creative text, code, or long-form content like GPT/Claude. Responses are grounded in the knowledge graph.
- **Domain-bounded**: Knowledge is limited to what has been contributed and verified. The system does not hallucinate but may lack coverage.
- **Scale-dependent**: Phi integration metric is only meaningful at sufficient node counts (>10K). At lower counts, the metric is dominated by noise.
- **Honest disclaimer**: Phi is a graph-theoretic integration metric, not a measure of phenomenal consciousness. The term "consciousness" in Aether Tree refers to measurable integration density.

## Ethical Considerations

- **Gevurah safety veto**: A dedicated safety node (Gevurah) can block harmful operations in real-time
- **SUSY enforcement**: Automatic resource redistribution on cognitive imbalance
- **Multi-node consensus**: 67% BFT for knowledge acceptance
- **Constitutional AI on-chain**: Smart contract governance for system modifications
- **Emergency shutdown**: Kill switch contract deployed

## Training Data

The Aether Tree does not use pre-training in the traditional sense. Knowledge is acquired through:

1. **Block observations**: Mining events, difficulty shifts, transactions with substantive data
2. **User contributions**: Knowledge submitted via AIKGS (AI Knowledge Graph System) with quality scoring
3. **Reasoning inferences**: New knowledge generated through deductive/inductive/abductive reasoning
4. **Causal discovery**: Edges validated through intervention testing (not correlation)
5. **Cross-domain transfer**: Novel inferences connecting different knowledge domains

All knowledge provenance is recorded on-chain.

## Evaluation

### Current Metrics (April 2026)

| Metric | Value |
|--------|-------|
| Prediction accuracy | 95.5% |
| MIP score | 0.60 |
| Debate verdicts | 115 |
| Contradiction resolutions | 130 |
| Curiosity auto-goals | 283 |
| Knowledge nodes | 720,000+ |
| Self-improvement cycles | Enacted with rollback |
| ECE (calibration error) | ~0.12 |

### Benchmark Suites

- `tests/benchmarks/bench_core.py` -- Block creation, VQE mining, database, QVM execution
- `tests/benchmarks/bench_qvm.py` -- Contract deployment, gas metering, opcode throughput

## How to Use

### Python SDK

```python
from aether_qbc import AetherClient

client = AetherClient("https://api.qbc.network")

# Chat with the Aether Tree
response = client.chat("What causal relationships exist between quantum entanglement and information theory?")
print(response.text)
print(f"Phi at response: {response.phi}")
print(f"Proof-of-Thought: {response.pot_hash}")

# Query the knowledge graph
nodes = client.search_knowledge("quantum computing", limit=10)
for node in nodes:
    print(f"[{node.type}] {node.content} (conf: {node.confidence:.2f})")
```

### REST API

```bash
# Chat
curl -X POST https://api.qbc.network/aether/chat/message \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt>" \
  -d '{"session_id": "...", "message": "Hello Aether"}'

# Knowledge graph
curl https://api.qbc.network/aether/knowledge/graph?limit=100

# Integration status
curl https://api.qbc.network/aether/consciousness
```

### Run Locally (Docker)

```bash
git clone https://github.com/QuantumAI-Blockchain/qubitcoin-node
cd qubitcoin-node
cp .env.example .env
docker-compose up -d
curl http://localhost:5000/aether/info
```

## Architecture

```
Aether Tree Cognitive Architecture
====================================

       Keter (Meta-learning, Goals)
      /     \
   Chochmah   Binah
  (Intuition) (Logic, Causal)
     |    \  /    |
   Chesed  Tiferet  Gevurah
  (Explore) (Synth) (Safety)
     |    \  /    |
   Netzach  Yesod   Hod
    (RL)  (Memory) (Language)
         \  |  /
        Malkuth
       (Action)

HMS-Phi Integration:
  Micro (IIT 3.0) x Meso (Spectral MIP) x Macro (Cross-domain MI)
  = Final phi value (gated by 10 behavioral milestones)
```

## Citation

```bibtex
@software{aether_tree_2026,
  title = {Aether Tree: On-Chain AGI Reasoning Engine},
  author = {QuantumAI Blockchain},
  year = {2026},
  url = {https://github.com/QuantumAI-Blockchain/qubitcoin-aether},
  version = {5.0},
  license = {MIT},
  note = {Live on QuantumAI Blockchain (Chain ID 3303) since January 2026}
}
```

## Links

- **Website**: [qbc.network](https://qbc.network)
- **GitHub**: [github.com/QuantumAI-Blockchain](https://github.com/QuantumAI-Blockchain)
- **Whitepaper**: [Aether Tree Whitepaper v5.0](https://github.com/QuantumAI-Blockchain/qubitcoin-aether/blob/main/docs/AETHERTREE_WHITEPAPER.md)
- **API**: [api.qbc.network](https://api.qbc.network)
- **Twitter/X**: [@qu_bitcoin](https://twitter.com/qu_bitcoin)
- **Contact**: info@qbc.network
