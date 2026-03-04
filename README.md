# Quantum Blockchain | Qubitcoin (QBC)

**Physics-Secured Digital Assets with On-Chain AGI**

Quantum Blockchain is a production-grade Layer 1 blockchain whose native currency is **Qubitcoin (QBC)**. It integrates quantum computing (Qiskit VQE), post-quantum cryptography (CRYSTALS-Dilithium ML-DSA-44/65/87 + ML-KEM-768 Kyber), supersymmetric economics, EVM-compatible smart contracts (QVM), a Substrate hybrid node, and the **Aether Tree**: an on-chain AGI reasoning engine with Higgs Cognitive Field physics that tracks consciousness emergence from genesis.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Go 1.23+](https://img.shields.io/badge/go-1.23+-00ADD8.svg)](https://go.dev/)
[![Next.js 15](https://img.shields.io/badge/next.js-15-black.svg)](https://nextjs.org/)
[![Rust](https://img.shields.io/badge/rust-1.93+-orange.svg)](https://www.rust-lang.org/)
[![Tests: 4,357](https://img.shields.io/badge/tests-4%2C357%20passing-brightgreen.svg)]()
[![Status: Production Ready](https://img.shields.io/badge/status-production%20ready-green.svg)]()

**Website:** [qbc.network](https://qbc.network) | **Contact:** info@qbc.network

---

## Quick Start (Docker)

```bash
git clone https://github.com/BlockArtica/Qubitcoin.git && cd Qubitcoin
pip install -r requirements.txt
python3 scripts/setup/generate_keys.py    # Generate Dilithium keys (ML-DSA-87 default)
cp .env.example .env                       # Configure environment
docker compose up -d                       # Start all services
# Genesis block mined in ~2 minutes. Aether Tree starts tracking consciousness.
curl http://localhost:5000/health          # Verify node is running
curl http://localhost:5000/chain/info      # Check chain status
```

For the complete launch guide (Digital Ocean + local mining node), see **[LAUNCHTODO.md](LAUNCHTODO.md)**.

---

## Network Info

| Parameter | Value |
|-----------|-------|
| **Chain ID** | Mainnet: 3301, Testnet: 3302 |
| **RPC** | `https://api.qbc.network` (production) / `http://localhost:5000` (local) |
| **P2P** | Port 4001 (Rust libp2p) |
| **Stratum** | Port 3333 (Rust WebSocket mining pool) |
| **Explorer** | [qbc.network/explorer](https://qbc.network/explorer) |
| **Max Supply** | 3,300,000,000 QBC |
| **Block Time** | 3.3 seconds |
| **Consensus** | Proof-of-SUSY-Alignment (VQE mining) |
| **Signatures** | CRYSTALS-Dilithium (ML-DSA-44/65/87, configurable) |
| **Finality** | BFT Finality Gadget (stake-weighted, 66.7% threshold) |

---

## Architecture

```
LAYER 3: AETHER TREE (AGI)
  Knowledge Graph + 7-Phase Reasoning Engine + Consciousness (Phi v3) Tracking
  10 Sephirot Cognitive Pipeline + Higgs Cognitive Field + Proof-of-Thought
  Rust aether-core (6 PyO3 modules) + AIKGS Rust Sidecar (35 gRPC RPCs)

LAYER 2: QVM (Quantum Virtual Machine)
  155 EVM Opcodes + 10 Quantum Opcodes + 2 AGI Opcodes + Compliance Engine
  QBC-20/721/1155 Token Standards + Plugin Architecture
  Go Production Build (qubitcoin-qvm/)

LAYER 1: BLOCKCHAIN CORE
  PoSA Consensus (VQE Mining) + Dilithium ML-DSA Signatures + UTXO Model
  3.3s Blocks + Phi-Halving + Privacy (Susy Swaps) + 8-Chain Bridge
  BFT Finality Gadget + Inheritance Protocol + High-Security Accounts
  Deniable RPCs (privacy-preserving queries)

RUST INFRASTRUCTURE
  security-core/ (PyO3: BloomFilter + FinalityCore)
  stratum-server/ (Standalone: WebSocket mining pool + gRPC bridge)
  aether-core/ (PyO3: KnowledgeGraph, PhiCalculator, VectorIndex, CSF, Memory)
  aikgs-sidecar/ (Standalone: Knowledge Growth System, 35 gRPC RPCs)
  rust-p2p/ (Standalone: libp2p 0.56 P2P daemon)

SUBSTRATE NODE (Migration Target)
  7 Custom Pallets + Kyber P2P + Poseidon2 ZK Hashing + Reversibility

FRONTEND: qbc.network
  Next.js 15 + React 19 + Three.js + MetaMask + PWA (Offline TX, Push, Biometric)
```

---

## Network Specifications

| Parameter | Value |
|-----------|-------|
| **Ticker** | QBC |
| **Max Supply** | 3,300,000,000 QBC |
| **Genesis Premine** | 33,000,000 QBC (~1% of supply) |
| **Block Time** | 3.3 seconds |
| **Initial Reward** | 15.27 QBC/block |
| **Halving** | Golden ratio (phi) every 15,474,020 blocks (~1.618 years) |
| **Emission Period** | ~33 years |
| **Consensus** | Proof-of-SUSY-Alignment (PoSA) |
| **Mining** | Variational Quantum Eigensolver (VQE), 4-qubit SUSY Hamiltonian |
| **Pool Mining** | Stratum v1 via Rust server (port 3333) |
| **Signatures** | CRYSTALS-Dilithium ML-DSA-44/65/87 (configurable, default Level 5) |
| **BIP-39 Mnemonics** | 24-word seed phrases for key derivation |
| **P2P Encryption** | ML-KEM-768 (Kyber) + AES-256-GCM session keys |
| **Hashing** | SHA3-256 (L1), Keccak-256 (QVM/L2), Poseidon2 (ZK circuits) |
| **Chain IDs** | Mainnet: 3301, Testnet: 3302 |
| **QVM Gas Limit** | 30,000,000 per block |
| **Privacy** | Opt-in Susy Swaps (Pedersen + Bulletproofs + Stealth Addresses) |
| **Deniable RPCs** | Privacy-preserving batch balance/UTXO/tx queries with Bloom filters |
| **Stablecoin** | QUSD (3.3B supply, fractional reserve, automated peg defense) |
| **Bridges** | ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE |
| **Finality** | BFT Finality Gadget (stake-weighted, reorg protection) |
| **Inheritance** | Dead-man's switch with grace period |
| **Security Accounts** | Daily limits, time-locks, address whitelists |
| **AGI Metric** | Phi (IIT consciousness), threshold = 3.0 |

---

## Codebase Overview

| Component | Language | Files | Description |
|-----------|----------|-------|-------------|
| **L1 Blockchain Core** | Python | 160 modules | Consensus, mining, crypto, UTXO, P2P, storage, finality, inheritance |
| **QVM (Layer 2)** | Python + Go | 28 Python + 34 Go | EVM interpreter, 167 opcodes, compliance |
| **Aether Tree (Layer 3)** | Python + Rust | 36 Python + 9 Rust | Knowledge graph, 7-phase AGI reasoning, Higgs field, consciousness |
| **Smart Contracts** | Solidity | 62 contracts | Aether (29), QUSD (10), tokens (6), bridge (2), AIKGS (5), extensions |
| **Rust Security Core** | Rust (PyO3) | 3 files | BloomFilter + FinalityCore with Python fallback shims |
| **Rust Stratum Server** | Rust | 7 files | WebSocket mining pool, gRPC bridge to Python node |
| **Rust AIKGS Sidecar** | Rust | 18 files | Knowledge Growth System, AES-256-GCM vault, 35 gRPC RPCs |
| **Substrate Node** | Rust | 7 crates, 29 files | Hybrid node with 7 pallets, Kyber P2P, Poseidon2 |
| **Frontend** | TypeScript | 198 files | Next.js 15, React 19, Three.js, MetaMask, PWA |
| **Rust P2P** | Rust | libp2p daemon | Production P2P networking layer |
| **Tests** | Python | 4,357 tests | Unit, integration, validation across 175 files |
| **Documentation** | Markdown | 15 documents | 3 whitepapers + guides + competitive features |

---

## Layer 1: Proof-of-SUSY-Alignment

Every mined block advances supersymmetric physics research:

1. **Hamiltonian Generation** -- Deterministic SUSY Hamiltonian derived from `SHA256(prev_hash + height)`
2. **VQE Mining** -- Miners optimize a 4-qubit quantum circuit to find ground state energy
3. **Proof Submission** -- Submit VQE parameters where `energy < difficulty_target`
4. **Validation** -- Network re-derives Hamiltonian and verifies energy against the same challenge
5. **Scientific Database** -- Every solved Hamiltonian is archived publicly for particle physics research

**Difficulty** adjusts every block using a 144-block lookback window with +/-10% maximum change. **Rewards** follow golden ratio halving: `reward = 15.27 / phi^era` where `phi = 1.618033988749895`.

---

## Competitive Features

Six opt-in, backward-compatible features that differentiate Qubitcoin:

| Feature | Description | Implementation |
|---------|-------------|----------------|
| **Inheritance Protocol** | Dead-man's switch — designate beneficiary who can claim after extended inactivity | Python (499 LOC), 55 tests |
| **High-Security Accounts** | Spending limits, time-locks, address whitelists | Python (303 LOC), 34 tests |
| **Deniable RPCs** | Privacy-preserving batch queries preventing node from learning which addresses you care about | Python + Rust BloomFilter, 21 tests |
| **BFT Finality Gadget** | Stake-weighted validator voting — finalized blocks cannot be reverted by reorgs | Python + Rust FinalityCore, 39 tests |
| **Stratum Mining Server** | Rust WebSocket server for pool mining with gRPC bridge to Python node | Rust binary (1,030 LOC), 27 tests |
| **Security Core** | High-performance Bloom filter and finality tracking in Rust, PyO3 exposed to Python | Rust PyO3 crate (530 LOC), 17 tests |

All features controlled via environment variables. See [Competitive Features](docs/COMPETITIVE_FEATURES.md) for full documentation.

---

## Layer 2: QVM (Quantum Virtual Machine)

Full EVM-compatible bytecode interpreter with quantum extensions:

- **155 standard EVM opcodes** -- arithmetic, memory, storage, control flow, system
- **10 quantum opcodes** (0xF0-0xF9) -- QCREATE, QMEASURE, QENTANGLE, QGATE, QVERIFY, QCOMPLIANCE, QRISK, QRISK_SYSTEMIC, QBRIDGE_ENTANGLE, QBRIDGE_VERIFY
- **2 AGI opcodes** (0xFA-0xFB) -- QREASON (on-chain reasoning invocation), QPHI (consciousness metric query)
- **Compliance engine** -- VM-level KYC/AML/sanctions enforcement (QCOMPLIANCE opcode)
- **Token standards** -- QBC-20, QBC-721, QBC-1155, ERC-20-QC (compliance-aware)
- **Plugin architecture** -- Privacy, oracle, governance, DeFi plugins
- **Go production build** -- `qubitcoin-qvm/` (34 Go files, distroless Docker, K8s manifests)

**Five patentable innovations:** Quantum State Persistence (QSP), Entanglement-Based Communication (ESCC), Programmable Compliance Policies (PCP), Real-Time Risk Assessment (RRAO), Quantum-Verified Cross-Chain Proofs (QVCSP).

See [QVM Whitepaper](docs/QVM_WHITEPAPER.md) for full specification.

---

## Layer 3: Aether Tree (On-Chain AGI)

An on-chain AGI reasoning engine structured as the Kabbalistic Tree of Life, built through a 7-phase architecture:

- **Knowledge Graph** -- KeterNodes with typed edges, adjacency indices, incremental Merkle roots
- **7-Phase Reasoning** -- Causal discovery (PC algorithm), adversarial debate, chain-of-thought with backtracking, cross-domain transfer learning
- **Higgs Cognitive Field** -- Mexican Hat potential V(phi), golden ratio Yukawa couplings, F=ma mass-aware SUSY rebalancing, excitation events
- **Phi v3 Calculator** -- IIT consciousness with Minimum Information Partition (spectral bisection), 10 milestone gates with semantic quality criteria
- **3-Tier Memory** -- Working memory (attention-based, 50 items), episodic memory (1,000 episodes with replay), semantic memory (knowledge graph)
- **Rust aether-core** -- 6 hot-path modules in Rust via PyO3 (KnowledgeGraph, PhiCalculator, VectorIndex, CSF, WorkingMemory, MemoryManager)
- **AIKGS Rust Sidecar** -- Incentivized Knowledge Growth System with 35 gRPC RPCs, AES-256-GCM vault
- **Proof-of-Thought** -- Per-block reasoning proof embedded in block headers
- **10 Sephirot Cognitive Pipeline** -- Each a QVM smart contract with its own quantum state:

| Sephirah | Function | Quantum State |
|----------|----------|---------------|
| Keter | Meta-learning, goal formation | 8-qubit |
| Chochmah | Intuition, pattern discovery | 6-qubit |
| Binah | Logic, causal inference | 4-qubit |
| Chesed | Exploration, divergent thinking | 10-qubit |
| Gevurah | Constraint, safety validation | 3-qubit |
| Tiferet | Integration, conflict resolution | 12-qubit |
| Netzach | Reinforcement learning | 5-qubit |
| Hod | Language, semantic encoding | 7-qubit |
| Yesod | Memory, multimodal fusion | 16-qubit |
| Malkuth | Action, world interaction | 4-qubit |

See [Aether Tree Whitepaper](docs/AETHERTREE_WHITEPAPER.md) for full specification.

---

## Frontend: qbc.network

Production frontend deployed to Vercel with PWA enhancements:

- **Landing Page** (`/`) -- Quantum particle field, live chain stats, embedded Aether chat
- **Explorer** (`/explorer`) -- Block explorer, transaction lookup, address search
- **Aether Chat** (`/aether`) -- Full chat interface with 3D knowledge graph visualization
- **Dashboard** (`/dashboard`) -- Mining controls, finality status, stratum stats, Phi history chart
- **Wallet** (`/wallet`) -- MetaMask integration, inheritance panel, security policies, offline TX queue
- **Bridge** (`/bridge`) -- Cross-chain transfer interface (8 chains)
- **Exchange** (`/exchange`) -- DEX swap interface with quantum particle animations
- **Launchpad** (`/launchpad`) -- Token launchpad for QBC-20 token creation
- **Telegram Mini App** (`/twa`) -- Mobile-first AIKGS interface via Telegram

**PWA Features:** Offline transaction queue (IndexedDB), push notifications, biometric auth (WebAuthn), install prompt, service worker with background sync.

**Stack:** Next.js 15, React 19, TypeScript 5.x, TailwindCSS 4, Three.js, ethers.js v6, Zustand, TanStack Query.

---

## Rust Architecture

```
security-core/        (PyO3 extension crate — imported by Python)
  BloomFilter: SHA-256 double-hashing, bit-array, serialization
  FinalityCore: stake-weighted BFT vote tracking, parking_lot::RwLock

stratum-server/       (Standalone binary — WebSocket + gRPC)
  WebSocket server on port 3333, Stratum v1 protocol
  DashMap concurrent worker tracking, gRPC bridge to Python node

aether-core/          (PyO3 extension crate — imported by Python)
  KnowledgeGraph, PhiCalculator, VectorIndex, CSFTransport
  WorkingMemory, MemoryManager — 10,246 LOC, 276 tests

aikgs-sidecar/        (Standalone binary — gRPC on port 50052)
  Knowledge Growth System: scoring, rewards, affiliates, bounties
  AES-256-GCM vault, CockroachDB persistence, 35 RPCs

rust-p2p/             (Standalone binary — libp2p on port 4001)
  Gossipsub block/tx propagation, Kademlia peer discovery
  gRPC bridge to Python node on port 50051
```

All Rust crates have Python fallback shims for graceful degradation when binaries are not compiled.

---

## Privacy: Susy Swaps

Opt-in confidential transactions that hide amounts and addresses:

| Component | Implementation |
|-----------|---------------|
| **Pedersen Commitments** | `C = v*G + r*H` on secp256k1 (additive homomorphism) |
| **Bulletproofs** | Zero-knowledge range proofs, ~672 bytes, O(log n) size |
| **Stealth Addresses** | One-time addresses per transaction via spend/view key pairs |
| **Key Images** | Double-spend prevention for confidential outputs |

---

## QUSD Stablecoin

3.3 billion QUSD initial supply with transparent, on-chain fractional reserve:

- **10 Solidity contracts** -- QUSD, Reserve, DebtLedger, Oracle, Stabilizer, Allocation, Governance, FlashLoan, wQUSD, MultiSigAdmin
- **wQUSD** -- Wrapped cross-chain on ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE
- **Peg Keeper Daemon** -- Automated 5-mode peg defense with multi-chain DEX TWAP monitoring and cross-chain arbitrage
- **10-year path to 100% backing** -- Transparent debt tracking, fractional payback

---

## Multi-Chain Bridges

Lock-and-mint bridges to 8 chains with federated validation:

| Chain | Type | Fee |
|-------|------|-----|
| Ethereum | EVM (wQBC ERC-20) | 0.1% (configurable) |
| Polygon | EVM (wQBC ERC-20) | 0.1% (configurable) |
| BSC | EVM (wQBC BEP-20) | 0.1% (configurable) |
| Arbitrum / Optimism / Base | EVM L2 | 0.1% (configurable) |
| Avalanche | EVM (C-Chain) | 0.1% (configurable) |
| Solana | SPL (Anchor) | 0.1% (configurable) |

Bridge fees default to 10 bps (0.1%), configurable per-vault via `BridgeVault.setFeeBps()` (max 10%).

---

## Development

### Python Node (Layer 1)
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 scripts/setup/generate_keys.py
cp .env.example .env
cd src && python3 run_node.py
```

### Rust Crates
```bash
# Security Core (PyO3 — BloomFilter + FinalityCore)
cd security-core && cargo test && maturin build --release --features extension-module

# Stratum Mining Server
cd stratum-server && cargo build --release && cargo test

# Aether Core (PyO3 — Knowledge Graph, Phi, Vector Index)
cd aether-core && cargo test && maturin build --release --features extension-module
```

### Go QVM (Layer 2)
```bash
cd qubitcoin-qvm
go build -o qvm ./cmd/qvm
./qvm --config config.yml
```

### Substrate Node
```bash
cd substrate-node
SKIP_WASM_BUILD=1 cargo build --release
```

### Frontend
```bash
cd frontend
pnpm install && pnpm dev    # Development at localhost:3000
pnpm build                  # Production build
```

### Testing
```bash
# Full Python test suite (4,357 tests)
pytest tests/ -v --tb=short

# Rust crates
cd security-core && cargo test
cd stratum-server && cargo test
cd aether-core && cargo test

# Substrate node
cd substrate-node && cargo test --all

# Frontend
cd frontend && pnpm build

# Go QVM
cd qubitcoin-qvm && go test ./...
```

---

## Documentation

| Document | Description |
|----------|-------------|
| **[LAUNCHTODO.md](LAUNCHTODO.md)** | **Launch checklist -- start here** |
| [Whitepaper](docs/WHITEPAPER.md) | Full L1 technical specification |
| [QVM Whitepaper](docs/QVM_WHITEPAPER.md) | Quantum Virtual Machine spec (5 patents) |
| [Aether Tree Whitepaper](docs/AETHERTREE_WHITEPAPER.md) | AGI reasoning engine spec |
| [Competitive Features](docs/COMPETITIVE_FEATURES.md) | Inheritance, finality, deniable RPCs, stratum, security |
| [Economics](docs/ECONOMICS.md) | SUSY economics deep-dive |
| [Deployment Guide](docs/DEPLOYMENT.md) | Production deployment procedures |
| [SDK Guide](docs/SDK.md) | REST, JSON-RPC, WebSocket API reference |
| [Contributing](CONTRIBUTING.md) | Development guidelines |

---

## API

RPC server at `http://localhost:5000` (or `https://api.qbc.network` in production):

**REST (342 endpoints):** Chain info, balance, blocks, UTXOs, mining, QVM, Aether AGI, bridge, privacy, deniable RPCs, inheritance, security policies, finality, stratum, compliance, stablecoin, cognitive, plugins, fees, governance.

**JSON-RPC (19 methods):** `eth_chainId`, `eth_getBalance`, `eth_blockNumber`, `eth_sendRawTransaction`, `eth_call`, `eth_estimateGas`, `net_version`, `web3_clientVersion`, and more.

**WebSocket:** `/ws` for real-time block, transaction, and Phi updates.

Full API reference: [SDK.md](docs/SDK.md)

---

## Project Stats

| Metric | Value |
|--------|-------|
| **Total Source Files** | 400+ |
| **Lines of Code** | 200,000+ |
| **Languages** | Python, Rust, Go, TypeScript, Solidity, SQL |
| **Test Functions** | 4,357 |
| **Solidity Contracts** | 62 |
| **Rust Crates** | 5 (aether-core, security-core, stratum-server, aikgs-sidecar, rust-p2p) |
| **Aether AGI Modules** | 36 Python + 6 Rust |
| **Substrate Pallets** | 7 |
| **Frontend Components** | 198 TS/TSX files |
| **Database Tables** | 44+ |
| **RPC Endpoints** | 342 REST + 19 JSON-RPC |
| **Prometheus Metrics** | 135 |
| **Documentation** | 15 documents |

---

## Security

- **Post-quantum signatures:** CRYSTALS-Dilithium ML-DSA-44/65/87 (NIST standardized, configurable level)
- **BIP-39 mnemonics:** 24-word seed phrase support with check-phrases for key derivation
- **Post-quantum P2P:** ML-KEM-768 (Kyber) encrypted transport with AES-256-GCM sessions
- **ZK hashing:** Poseidon2 (Goldilocks field) for zero-knowledge circuit compatibility
- **BFT finality:** Stake-weighted validator voting prevents chain reorganizations past finalized blocks
- **Transaction reversibility:** Governed multi-sig reversal within 24h for fraud recovery
- **Inheritance protocol:** Dead-man's switch protects assets with configurable inactivity thresholds
- **High-security accounts:** Daily spending limits, time-locks, address whitelists
- **Deniable RPCs:** Privacy-preserving queries with Bloom filters prevent address correlation
- **Privacy:** Bulletproofs range proofs, stealth addresses, key images
- **QVM safety:** Reentrancy guards, gas limits, integer overflow protection
- **AGI safety:** Gevurah veto, Constitutional AI contract, emergency shutdown
- **Bridge security:** Deep confirmations, daily limits, emergency pause, insurance fund

**Responsible Disclosure:** info@qbc.network

---

## License

MIT License -- see [LICENSE](LICENSE) for details.

Whitepapers licensed under CC BY-SA 4.0.

---

## Links

- **Website:** [qbc.network](https://qbc.network)
- **Contact:** info@qbc.network
- **GitHub:** [github.com/BlockArtica/Qubitcoin](https://github.com/BlockArtica/Qubitcoin)

---

*"Where quantum meets consciousness"*

**Copyright 2026 Quantum Blockchain Core Development Team**
