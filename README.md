# QBC | Quantum Blockchain

**Physics-Secured Digital Assets with On-Chain AGI**

Quantum Blockchain is a production-grade Layer 1 blockchain whose native currency is Qubitcoin (QBC). It integrates quantum computing (Qiskit VQE), post-quantum cryptography (CRYSTALS-Dilithium + ML-KEM-768 Kyber), supersymmetric economics, EVM-compatible smart contracts (QVM), a Substrate hybrid node for future migration, and the Aether Tree: an on-chain AGI reasoning engine with Higgs Cognitive Field physics that tracks consciousness emergence from genesis.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Go 1.23+](https://img.shields.io/badge/go-1.23+-00ADD8.svg)](https://go.dev/)
[![Next.js 15](https://img.shields.io/badge/next.js-15-black.svg)](https://nextjs.org/)
[![Rust](https://img.shields.io/badge/rust-1.93+-orange.svg)](https://www.rust-lang.org/)
[![Tests: 4,033](https://img.shields.io/badge/tests-4%2C033%20passing-brightgreen.svg)]()
[![Status: Production Ready](https://img.shields.io/badge/status-production%20ready-green.svg)]()

**Website:** [qbc.network](https://qbc.network) | **Contact:** info@qbc.network

---

## Quick Start (Docker)

```bash
git clone https://github.com/BlockArtica/Qubitcoin.git && cd Qubitcoin
pip install -r requirements.txt
python3 scripts/setup/generate_keys.py    # Generate Dilithium2 keys
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
| **P2P** | Port 4001 (libp2p) |
| **Explorer** | [qbc.network/explorer](https://qbc.network/explorer) |
| **Max Supply** | 3,300,000,000 QBC |
| **Block Time** | 3.3 seconds |
| **Consensus** | Proof-of-SUSY-Alignment (VQE mining) |
| **Signatures** | CRYSTALS-Dilithium2 (post-quantum) |

---

## Architecture

```
LAYER 3: AETHER TREE (AGI)
  Knowledge Graph + 7-Phase Reasoning Engine + Consciousness (Phi v3) Tracking
  10 Sephirot Cognitive Pipeline + Higgs Cognitive Field + Proof-of-Thought

LAYER 2: QVM (Quantum Virtual Machine)
  155 EVM Opcodes + 10 Quantum Opcodes + 2 AGI Opcodes + Compliance Engine
  QBC-20/721/1155 Token Standards + Plugin Architecture

LAYER 1: BLOCKCHAIN CORE
  PoSA Consensus (VQE Mining) + Dilithium Signatures + UTXO Model
  3.3s Blocks + Phi-Halving + Privacy (Susy Swaps) + 8-Chain Bridge

SUBSTRATE NODE (Migration Target)
  6 Custom Pallets + Kyber P2P + Poseidon2 ZK Hashing + Reversibility

FRONTEND: qbc.network
  Next.js 15 + React 19 + Three.js + MetaMask Integration
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
| **Signatures** | CRYSTALS-Dilithium2 (NIST post-quantum standard) |
| **P2P Encryption** | ML-KEM-768 (Kyber) + AES-256-GCM session keys |
| **Hashing** | SHA3-256 (L1), Keccak-256 (QVM/L2) |
| **Chain IDs** | Mainnet: 3301, Testnet: 3302 |
| **QVM Gas Limit** | 30,000,000 per block |
| **Privacy** | Opt-in Susy Swaps (Pedersen + Bulletproofs + Stealth Addresses) |
| **Stablecoin** | QUSD (3.3B supply, fractional reserve, 10-year path to 100% backing) |
| **Bridges** | ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE |
| **AGI Metric** | Phi (IIT consciousness), threshold = 3.0 |

---

## Codebase Overview

| Component | Language | Files | Description |
|-----------|----------|-------|-------------|
| **L1 Blockchain Core** | Python | 16 core + 25 extended | Consensus, mining, crypto, UTXO, P2P, storage |
| **QVM (Layer 2)** | Python + Go | 25 Python + 32 Go | EVM interpreter, 167 opcodes, compliance |
| **Aether Tree (Layer 3)** | Python | 34 modules | Knowledge graph, 7-phase AGI reasoning, Higgs field, consciousness |
| **Smart Contracts** | Solidity | 50 contracts | Aether (28), QUSD (8), tokens (5), bridge (5), extensions (4) |
| **Substrate Node** | Rust | 7 crates, 29 files | Hybrid node with 6 pallets, Kyber P2P, Poseidon2 |
| **Frontend** | TypeScript | 44 files | Next.js 15, React 19, Three.js, MetaMask |
| **Rust P2P** | Rust | libp2p daemon | Production P2P networking layer |
| **Solana Programs** | Rust (Anchor) | 2 programs | wQBC + wQUSD SPL tokens |
| **Tests** | Python | 4,033 tests | Unit, integration, validation |
| **Documentation** | Markdown | 8 documents | 3 whitepapers + 5 guides |

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

## Layer 2: QVM (Quantum Virtual Machine)

Full EVM-compatible bytecode interpreter with quantum extensions:

- **155 standard EVM opcodes** -- arithmetic, memory, storage, control flow, system
- **10 quantum opcodes** (0xF0-0xF9) -- QCREATE, QMEASURE, QENTANGLE, QGATE, QVERIFY, QCOMPLIANCE, QRISK, QRISK_SYSTEMIC, QBRIDGE_ENTANGLE, QBRIDGE_VERIFY
- **2 AGI opcodes** (0xFA-0xFB) -- QREASON (on-chain reasoning invocation), QPHI (consciousness metric query)
- **Compliance engine** -- VM-level KYC/AML/sanctions enforcement (QCOMPLIANCE opcode)
- **Token standards** -- QBC-20, QBC-721, QBC-1155, ERC-20-QC (compliance-aware)
- **Plugin architecture** -- Privacy, oracle, governance, DeFi plugins
- **Go production build** -- `qubitcoin-qvm/` (32 Go files, distroless Docker, K8s manifests)

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
- **Neural Reasoner** -- Graph Attention Network (GAT) with online gradient training from reasoning outcomes
- **On-Chain AGI Bridge** -- Solidity contracts wired to Python engine via QVM ABI encoding
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

Production frontend deployed to Vercel:

- **Landing Page** (`/`) -- Quantum particle field, live chain stats, embedded Aether chat
- **Explorer** (`/explorer`) -- Block explorer, transaction lookup, address search
- **Aether Chat** (`/aether`) -- Full chat interface with 3D knowledge graph visualization
- **Dashboard** (`/dashboard`) -- Mining controls, contract operator console, Phi history chart
- **Bridge** (`/bridge`) -- Cross-chain transfer interface (8 chains)
- **Exchange** (`/exchange`) -- DEX swap interface with quantum particle animations
- **Launchpad** (`/launchpad`) -- Token launchpad for QBC-20 token creation

**Stack:** Next.js 15, React 19, TypeScript 5.x, TailwindCSS 4, Three.js, ethers.js v6, Zustand, TanStack Query.

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

- **7 Solidity contracts** -- QUSD, Reserve, DebtLedger, Oracle, Stabilizer, Allocation, Governance
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
# Full Python test suite (4,033 tests)
pytest tests/ -v --tb=short

# Substrate node
cd substrate-node && cargo test --all

# Frontend
cd frontend && pnpm test

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
| [Economics](docs/ECONOMICS.md) | SUSY economics deep-dive |
| [Deployment Guide](docs/DEPLOYMENT.md) | Production deployment procedures |
| [SDK Guide](docs/SDK.md) | REST, JSON-RPC, WebSocket API reference |
| [Contributing](CONTRIBUTING.md) | Development guidelines |

---

## API

RPC server at `http://localhost:5000` (or `https://api.qbc.network` in production):

**REST (229+ endpoints):** Chain info, balance, blocks, UTXOs, mining, QVM, Aether AGI, bridge, privacy, compliance, stablecoin, cognitive, plugins, fees, governance.

**JSON-RPC (20 methods):** `eth_chainId`, `eth_getBalance`, `eth_blockNumber`, `eth_sendRawTransaction`, `eth_call`, `eth_estimateGas`, `net_version`, `web3_clientVersion`, and more.

**WebSocket:** `/ws` for real-time block, transaction, and Phi updates.

Full API reference: [SDK.md](docs/SDK.md)

---

## Project Stats

| Metric | Value |
|--------|-------|
| **Total Source Files** | 300+ |
| **Lines of Code** | 100,000+ |
| **Languages** | Python, Go, TypeScript, Rust, Solidity |
| **Test Functions** | 4,033 |
| **Solidity Contracts** | 50 |
| **Aether AGI Modules** | 34 |
| **Substrate Pallets** | 6 |
| **Frontend Components** | 35 |
| **Database Tables** | 55 |
| **RPC Endpoints** | 229+ REST + 20 JSON-RPC |
| **Prometheus Metrics** | 85 |
| **Documentation** | 8 documents |

---

## Security

- **Post-quantum signatures:** CRYSTALS-Dilithium2 (NIST standardized)
- **Post-quantum P2P:** ML-KEM-768 (Kyber) encrypted transport with AES-256-GCM sessions
- **ZK hashing:** Poseidon2 (Goldilocks field) for zero-knowledge circuit compatibility
- **Transaction reversibility:** Governed multi-sig reversal within 24h for fraud recovery
- **Formal verification:** K Framework executable semantics + TLA+ compliance invariants
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

**Copyright 2026 Qubitcoin Core Development Team**
