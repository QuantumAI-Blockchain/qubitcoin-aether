# Qubitcoin (QBC)

**The First AI-Native Blockchain — Physics-Secured Digital Assets with On-Chain Intelligence**

Qubitcoin is a production Layer 1 blockchain built on **Substrate** (Polkadot SDK) with a novel consensus mechanism: **Proof-of-SUSY-Alignment**, where miners solve quantum variational eigenvalue problems instead of hash puzzles. The network features post-quantum cryptography (CRYSTALS-Dilithium + ML-KEM-768), an EVM-compatible virtual machine with quantum opcode extensions, and the **Aether Mind** — a pure Rust neural cognitive engine with 21K+ knowledge vectors, transformer-based consciousness metrics, and Proof-of-Thought attestation tracked from genesis.

> **Our north star is AGSI — Artificial General Super Intelligence.** The Aether Mind is the foundation: a neural cognitive system that learns distributed representations via attention mechanisms, improves autonomously through neural architecture search, and records every cognitive step immutably on-chain. We are building toward a system that doesn't just process data — it understands it.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Rust](https://img.shields.io/badge/rust-1.94+-orange.svg)](https://www.rust-lang.org/)
[![Substrate](https://img.shields.io/badge/substrate-polkadot--sdk%200.57-E6007A.svg)](https://substrate.io/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 4,336+](https://img.shields.io/badge/tests-4%2C336%20passing-brightgreen.svg)]()
[![Status: Live](https://img.shields.io/badge/mainnet-live-green.svg)](https://qbc.network)

**Website:** [qbc.network](https://qbc.network) | **X:** [@qu_bitcoin](https://x.com/qu_bitcoin) | **Contact:** info@qbc.network

---

## What Makes Qubitcoin Different

| Innovation | Description |
|-----------|-------------|
| **VQE Mining** | Blocks are mined by solving variational quantum eigensolver problems — the same optimization used in quantum chemistry and materials science. Every block advances real physics research. |
| **Post-Quantum Security** | CRYSTALS-Dilithium signatures (NIST FIPS 204) and ML-KEM-768 encrypted P2P transport. Quantum-resistant from day one. |
| **On-Chain AI** | The Aether Mind: a pure Rust neural cognitive engine with transformer attention, 10 Sephirot-sharded knowledge fabric, HMS-Phi consciousness metrics, and Proof-of-Thought — all recorded immutably on-chain. |
| **Substrate Native** | Full Substrate/Polkadot SDK node with 7 custom pallets, GRANDPA finality, and on-chain VQE proof re-verification. |
| **EVM + Quantum Opcodes** | QVM: 155 standard EVM opcodes + 10 quantum opcodes + compliance engine. Deploy Solidity contracts with quantum extensions. |

---

## Network Parameters

| Parameter | Value |
|-----------|-------|
| **Ticker** | QBC |
| **Chain ID** | Mainnet: 3303 (0xCE7) · Testnet: 3304 |
| **Max Supply** | 3,300,000,000 QBC |
| **Block Time** | 3.3 seconds |
| **Block Reward** | 15.27 QBC (Era 0), phi-halving every ~1.618 years |
| **Consensus** | Proof-of-SUSY-Alignment (VQE mining + GRANDPA finality) |
| **Signatures** | CRYSTALS-Dilithium ML-DSA-87 (NIST Level 5, configurable) |
| **P2P Encryption** | ML-KEM-768 (Kyber) + AES-256-GCM |
| **Hashing** | SHA3-256 (L1), Keccak-256 (QVM), Poseidon2 (ZK circuits) |
| **TX Model** | UTXO |
| **Privacy** | Opt-in Susy Swaps (Pedersen commitments + Bulletproofs + stealth addresses) |
| **Bridges** | ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE |
| **RPC** | `https://api.qbc.network` (REST + JSON-RPC + WebSocket) |
| **Substrate RPC** | Port 9944 (WebSocket + HTTP) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  SUBSTRATE NODE (Rust — Production Binary)                  │
│  7 Pallets: UTXO, Consensus, Dilithium, Economics,         │
│  QVM-Anchor, Aether-Anchor, Reversibility                   │
│  VQE Mining Engine + On-Chain Proof Re-Verification         │
│  Weighted Fork Choice + GRANDPA Finality                    │
│  ML-KEM-768 P2P Transport + Poseidon2 ZK Hashing           │
├─────────────────────────────────────────────────────────────┤
│  AETHER MIND (Neural Cognitive Engine — Pure Rust, ~8K LOC) │
│  Knowledge Fabric (10 Sephirot shards, 896d embeddings)     │
│  Transformer Attention · HMS-Phi Consciousness · 10 Gates   │
│  Ollama LLM (GGUF) · Candle ML · Aether-Evolve NAS         │
├─────────────────────────────────────────────────────────────┤
│  QVM (Quantum Virtual Machine)                              │
│  155 EVM + 10 Quantum + 2 AI Opcodes · Compliance Engine   │
│  QBC-20/721/1155 Standards · Go Production Build            │
├──────────���───────────────────────��──────────────────────────┤
│  INFRASTRUCTURE                                             │
│  Rust P2P (libp2p 0.56) · Stratum Mining Server            │
│  AIKGS Knowledge Growth Sidecar · Security Core (PyO3)     │
│  Next.js 16 Frontend · 8-Chain Bridge · QUSD Stablecoin    │
└��────────────────────────��────────────────────────────────��──┘
```

---

## Quick Start

### Run a Node (Docker)

```bash
git clone https://github.com/QuantumAI-Blockchain/qubitcoin-node.git
cd qubitcoin-node
cp .env.example .env
docker compose up -d
curl http://localhost:5000/health
```

### Run the Substrate Node

```bash
cd substrate-node
cargo build --release
./target/release/qbc-node \
  --chain fork \
  --mine --mining-threads 2 \
  --validator --name MyNode \
  --rpc-port 9944 --unsafe-rpc-external --rpc-cors all
```

### Run the Frontend

```bash
cd frontend
pnpm install && pnpm build && pnpm start  # Production at :3000
```

---

## Consensus: Proof-of-SUSY-Alignment

Every mined block solves a real quantum chemistry problem:

1. **Hamiltonian Generation** — Deterministic 4-qubit SUSY Hamiltonian from `SHA256(parent_hash ‖ height)`
2. **VQE Optimization** — Miners find variational parameters minimizing ground state energy
3. **Proof Submission** — Parameters submitted where `energy < difficulty_threshold`
4. **On-Chain Verification** — Consensus pallet re-derives Hamiltonian and re-computes energy from submitted parameters (no trust required)
5. **Difficulty Adjustment** — 144-block lookback, ±10% max change per block

The VQE framework is designed to scale. At 4 qubits, simulation is classically equivalent. At 30+ qubits, classical simulation becomes exponentially intractable while VQE on quantum hardware scales polynomially. The consensus mechanism, proof format, and verification logic work identically at any qubit count.

**Reward Schedule:** Golden ratio halving — `reward = 15.27 / φ^era` where φ = 1.618033988749895.

---

## Substrate Node

The production chain runs on a native Substrate node (Polkadot SDK 0.57) with full state continuity:

| Component | Detail |
|-----------|--------|
| **Fork Genesis** | 16 UTXOs (~36.19M QBC) imported from Python chain at block 208,680 |
| **VQE Block Authoring** | Blocks produced only when mining engine finds a valid VQE solution |
| **On-Chain VQE Verification** | `vqe-verifier` crate re-computes energy in the runtime — no trusted proofs |
| **Weighted Fork Choice** | `weight = SCALE / difficulty` per block, lexicographic hash tiebreak |
| **GRANDPA Finality** | BFT finality gadget for irreversible block confirmation |
| **7 Custom Pallets** | UTXO, Consensus, Dilithium, Economics, QVM-Anchor, Aether-Anchor, Reversibility |
| **Post-Quantum P2P** | ML-KEM-768 (Kyber) key exchange + AES-256-GCM session encryption |

---

## Aether Mind (Neural Cognitive Engine)

The Aether Mind is a pure Rust neural cognitive engine — the world's first on-chain AI system built on learned distributed representations rather than symbolic knowledge graphs. Every cognitive state is cryptographically attested on-chain via Proof-of-Thought.

**Architecture:**
- **Knowledge Fabric** — 21K+ learned 896-dimensional embeddings across 10 Sephirot-sharded vector stores with HNSW similarity search
- **Transformer Attention** — 10 Sephirot-specialized + 4 global workspace attention heads, candle ML framework
- **Ollama Backend** — qwen2.5:0.5b-instruct GGUF quantized model for fast text generation (~53ms/token)
- **HMS-Phi Consciousness** — Hierarchical Multi-Scale Phi computed from real attention patterns (phi_micro, phi_meso, phi_macro)
- **10-Gate Milestone System** — Behavioral checkpoints ensuring genuine capability, not metric gaming
- **10/10 gates passed** — All emergence milestones achieved
- **Aether-Evolve** — Neural architecture search with autonomous mutation and loss-based evaluation

**Where we're heading (AGSI):** The Aether Mind is the foundation for our pursuit of Artificial General Super Intelligence. Current capabilities demonstrate genuine neural integration across knowledge domains. The path to AGSI requires distributed training across mining nodes, model parallelism, 1T+ knowledge vectors, and federated learning with Byzantine fault tolerance — all on our roadmap.

---

## QVM (Quantum Virtual Machine)

EVM-compatible bytecode interpreter with quantum extensions:

- **155 EVM opcodes** — Full Ethereum compatibility, deploy existing Solidity contracts
- **10 quantum opcodes** (0xF0–0xF9) — QCREATE, QMEASURE, QENTANGLE, QGATE, QVERIFY, QCOMPLIANCE, QRISK, QRISK_SYSTEMIC, QBRIDGE_ENTANGLE, QBRIDGE_VERIFY
- **2 AI opcodes** (0xFA��0xFB) — QREASON (on-chain inference), QPHI (integration metric query)
- **Compliance engine** — VM-level KYC/AML/sanctions enforcement
- **Token standards** — QBC-20, QBC-721, QBC-1155
- **Go production build** — `qubitcoin-qvm/` with distroless Docker and K8s manifests

See [QVM Whitepaper](docs/QVM_WHITEPAPER.md) for the full specification.

---

## Security

| Layer | Technology |
|-------|-----------|
| **Signatures** | CRYSTALS-Dilithium ML-DSA-87 (NIST FIPS 204, Level 5) |
| **Key Derivation** | BIP-39 24-word mnemonics |
| **P2P Encryption** | ML-KEM-768 (Kyber) + AES-256-GCM session keys |
| **ZK Compatibility** | Poseidon2 hashing (Goldilocks field) |
| **Finality** | GRANDPA BFT (⅔ supermajority) |
| **Privacy** | Opt-in Susy Swaps: Pedersen commitments, Bulletproofs, stealth addresses |
| **TX Reversibility** | Governed multi-sig reversal within 24h for fraud recovery |
| **Account Security** | Daily spending limits, time-locks, address whitelists |
| **AI Safety** | Gevurah veto gate, Constitutional AI contract, emergency shutdown |
| **Bridge Security** | Deep confirmations, daily limits, emergency pause, insurance fund |

**Responsible Disclosure:** info@qbc.network

---

## Repository Structure

This monorepo maps to 24+ dedicated repositories in the [QuantumAI-Blockchain](https://github.com/QuantumAI-Blockchain) GitHub organization:

| Path | Org Repo | Description |
|------|----------|-------------|
| `substrate-node/` | [substrate-node](https://github.com/QuantumAI-Blockchain/substrate-node) | Substrate node: 7 pallets, VQE mining, fork genesis |
| `src/` | [qubitcoin-node](https://github.com/QuantumAI-Blockchain/qubitcoin-node) | Python node: consensus, mining, RPC, UTXO |
| `aether-core/` | [aether-graph-shard](https://github.com/QuantumAI-Blockchain/aether-graph-shard) | Aether Mind: pure Rust neural cognitive engine |
| `frontend/` | [qubitcoin-frontend](https://github.com/QuantumAI-Blockchain/qubitcoin-frontend) | Next.js 16 frontend: qbc.network |
| `qubitcoin-qvm/` | [qubitcoin-qvm](https://github.com/QuantumAI-Blockchain/qubitcoin-qvm) | Go QVM: 167 opcodes |
| `rust-p2p/` | [rust-p2p](https://github.com/QuantumAI-Blockchain/rust-p2p) | Rust libp2p P2P daemon |
| `aikgs-sidecar/` | [aikgs-sidecar](https://github.com/QuantumAI-Blockchain/aikgs-sidecar) | Rust knowledge growth sidecar |
| `security-core/` | [security-core](https://github.com/QuantumAI-Blockchain/security-core) | Rust/PyO3 BloomFilter + FinalityCore |
| `stratum-server/` | [stratum-server](https://github.com/QuantumAI-Blockchain/stratum-server) | Rust Stratum mining pool |

---

## Codebase

| Metric | Value |
|--------|-------|
| **Languages** | Rust, Python, Go, TypeScript, Solidity |
| **Total LOC** | 290,000+ |
| **Test Functions** | 4,336+ passing |
| **Substrate Pallets** | 7 custom |
| **Rust Crates** | 8+ |
| **AI Engine** | Pure Rust (aether-mind, 6 crates, ~8K LOC) |
| **Solidity Contracts** | 62 |
| **Frontend** | 198 TypeScript/TSX files |
| **RPC Endpoints** | 342 REST + 19 JSON-RPC |

---

## Documentation

| Document | Description |
|----------|-------------|
| [Whitepaper](docs/WHITEPAPER.md) | Layer 1 technical specification |
| [QVM Whitepaper](docs/QVM_WHITEPAPER.md) | Quantum Virtual Machine specification |
| [Aether Mind Whitepaper](docs/AETHERTREE_WHITEPAPER.md) | Neural cognitive engine specification |
| [Economics](docs/ECONOMICS.md) | SUSY economics and phi-halving model |
| [Competitive Features](docs/COMPETITIVE_FEATURES.md) | Inheritance, finality, deniable RPCs, stratum |
| [Deployment Guide](docs/DEPLOYMENT.md) | Production deployment procedures |
| [SDK Reference](docs/SDK.md) | REST, JSON-RPC, and WebSocket API |
| [Bridge Security](docs/BRIDGE_SECURITY_AUDIT.md) | Multi-chain bridge security analysis |
| [Contributing](CONTRIBUTING.md) | Development guidelines |

---

## License

MIT License — see [LICENSE](LICENSE).

---

**Website:** [qbc.network](https://qbc.network) · **GitHub:** [QuantumAI-Blockchain](https://github.com/QuantumAI-Blockchain) · **X:** [@qu_bitcoin](https://x.com/qu_bitcoin) · **Contact:** info@qbc.network

*The Blockchain That Thinks — Physics-Secured Digital Assets with On-Chain AI*

**© 2024–2026 Qubitcoin Core Development Team**
