# CLAUDE.md - Qubitcoin Master Development Guide

> **The definitive reference for AI-assisted development on the Qubitcoin codebase.**
> Covers Layer 1 (blockchain), Layer 2 (QVM + smart contracts), Layer 3 (Aether Tree AGI),
> and the Frontend (qbc.network).

---

## 1. PROJECT IDENTITY

**Qubitcoin (QBC)** is a quantum-secured Layer 1 blockchain that combines:
- **Quantum Computing** (Qiskit VQE) for Proof-of-SUSY-Alignment mining
- **Post-Quantum Cryptography** (CRYSTALS-Dilithium2) for quantum-resistant signatures
- **Supersymmetric (SUSY) Economics** with golden ratio (phi) emission principles
- **Aether Tree** — an on-chain AGI reasoning engine that tracks consciousness metrics from genesis
- **QVM** — a full EVM-compatible virtual machine with quantum opcode extensions
- **Multi-chain bridges** to ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE

**Domain:** qbc.network
**License:** MIT
**Chain IDs:** Mainnet=3301, Testnet=3302

---

## 2. GLOBAL SESSION PROMPT

**Every session MUST begin with this protocol. No exceptions.**

```
PHASE 0: ORIENTATION
1. Read this CLAUDE.md — it is the single source of truth
2. Run: git status && git branch && git log --oneline -5
3. Identify which layer/subsystem the task affects
4. Read the relevant source files before proposing changes

PHASE 1: PLAN (think hard — no code yet)
1. List every file that needs to change
2. Identify dependency order
3. Rate risk: CRITICAL (consensus, crypto, UTXO) vs STANDARD
4. Define test commands for verification
5. Break into batches of MAX 5 files
6. WAIT for approval before proceeding

PHASE 2: IMPLEMENT (one batch at a time)
1. Verify branch (NEVER commit to main)
2. Make changes to batch ONLY
3. Run tests — show FULL output
4. Commit only when green
5. Report: files changed, tests run, pass/fail

PHASE 3: VALIDATE
1. Full test suite: pytest tests/ -v --tb=short
2. Type check if applicable
3. Summary: total files, total tests, pass rate
```

**NON-NEGOTIABLE RULES:**
- NEVER modify consensus, crypto, genesis, or UTXO spending rules without explicit approval
- NEVER skip tests between batches
- NEVER fabricate test output — run commands and show real results
- NEVER add gas metering to L1 — that is QVM/L2
- NEVER implement QUSD on L1 — that is a QVM smart contract
- NEVER hardcode secrets — everything goes in .env
- NEVER silently swallow exceptions — structured logging always
- Use `get_logger(__name__)` from `utils/logger.py` in every module
- Use `Config` class from `config.py` for all configuration (never hardcode values)
- Type hints required on all function signatures

---

## 3. ARCHITECTURE OVERVIEW

```
╔══════════════════════════════════════════════════════════════════════════╗
║                        QUBITCOIN ARCHITECTURE                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  ┌─────────────────────────────────────────────────────────────────┐   ║
║  │  FRONTEND (qbc.network)                                         │   ║
║  │  Next.js 14 + TailwindCSS + Framer Motion                      │   ║
║  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │   ║
║  │  │ Landing  │ │ Aether   │ │ Dashboard│ │ Wallet/MetaMask  │  │   ║
║  │  │ Page     │ │ Chat     │ │ Console  │ │ Integration      │  │   ║
║  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │   ║
║  └───────────────────────────┬─────────────────────────────────────┘   ║
║                              │ REST + JSON-RPC + WebSocket             ║
║  ┌───────────────────────────▼─────────────────────────────────────┐   ║
║  │  LAYER 3: AETHER TREE (AGI Engine)                              │   ║
║  │  KnowledgeGraph (KeterNodes) + ReasoningEngine + PhiCalculator  │   ║
║  │  Proof-of-Thought consensus | Consciousness tracking from genesis│   ║
║  └───────────────────────────┬─────────────────────────────────────┘   ║
║                              │                                         ║
║  ┌───────────────────────────▼─────────────────────────────────────┐   ║
║  │  LAYER 2: QVM (Quantum Virtual Machine)                         │   ║
║  │  155 EVM opcodes + 10 quantum opcodes (QVQE, QPROOF, etc.)     │   ║
║  │  StateManager + Bytecode execution + Gas metering               │   ║
║  │  Solidity-compatible | QBC-20 + QBC-721 token standards         │   ║
║  └───────────────────────────┬─────────────────────────────────────┘   ║
║                              │                                         ║
║  ┌───────────────────────────▼─────────────────────────────────────┐   ║
║  │  LAYER 1: BLOCKCHAIN CORE                                       │   ║
║  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │   ║
║  │  │ Consensus   │ │ Mining      │ │ Quantum     │              │   ║
║  │  │ (PoSA)      │ │ (VQE)       │ │ (Qiskit)    │              │   ║
║  │  └─────────────┘ └─────────────┘ └─────────────┘              │   ║
║  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │   ║
║  │  │ Crypto      │ │ Network     │ │ Storage     │              │   ║
║  │  │ (Dilithium) │ │ (libp2p)    │ │ (CockroachDB│              │   ║
║  │  │             │ │ + FastAPI   │ │  + IPFS)    │              │   ║
║  │  └─────────────┘ └─────────────┘ └─────────────┘              │   ║
║  │  UTXO Model | 3.3s blocks | phi-halving | 3.3B max supply      │   ║
║  └─────────────────────────────────────────────────────────────────┘   ║
║                                                                        ║
║  ┌─────────────────────────────────────────────────────────────────┐   ║
║  │  CROSS-CUTTING: Bridge (8 chains) | QUSD Stablecoin | Metrics  │   ║
║  └─────────────────────────────────────────────────────────────────┘   ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 4. TECHNOLOGY STACK

| Component | Technology | Version |
|-----------|-----------|---------|
| **L1 Core** | Python | 3.11+ |
| **P2P Networking** | Rust (libp2p) | 2021 edition, libp2p 0.56 |
| **Web Framework** | FastAPI | latest |
| **ORM** | SQLAlchemy | latest |
| **Database** | CockroachDB | v24.2.0 (pinned) |
| **Quantum** | Qiskit | latest |
| **Content Storage** | IPFS (Kubo) | v0.30.0+ |
| **Frontend** | Next.js 14 + TypeScript | latest |
| **Styling** | TailwindCSS + Framer Motion | latest |
| **Wallet** | ethers.js (MetaMask compat) | v6 |
| **Monitoring** | Prometheus + Grafana | latest |

---

## 5. REPOSITORY STRUCTURE

```
Qubitcoin/
├── CLAUDE.md                    # THIS FILE — master development guide
├── TODO.md                      # Master project TODO list
├── README.md                    # Public-facing README
├── requirements.txt             # Python dependencies
├── setup.py                     # Package setup
├── Dockerfile                   # Docker build
├── docker-compose.yml           # Dev deployment
├── docker-compose.production.yml # Production multi-node
├── .env.example                 # Environment template
├── .gitignore
│
├── src/                         # Source code root
│   ├── run_node.py              # Node entry point
│   ├── qubitcoin/               # Main Python package
│   │   ├── __init__.py
│   │   ├── node.py              # Main node orchestrator (10 components)
│   │   ├── config.py            # Centralized env-based configuration
│   │   │
│   │   ├── consensus/           # LAYER 1: Proof-of-SUSY-Alignment
│   │   │   ├── engine.py        # Block validation, difficulty adjustment, rewards
│   │   │   └── __init__.py
│   │   │
│   │   ├── mining/              # LAYER 1: VQE mining engine
│   │   │   ├── engine.py        # Mining loop, VQE optimization, block creation
│   │   │   └── __init__.py
│   │   │
│   │   ├── quantum/             # LAYER 1: Quantum engine
│   │   │   ├── engine.py        # VQE engine, Hamiltonian generation, Qiskit
│   │   │   ├── crypto.py        # Dilithium2 signatures, key generation
│   │   │   └── __init__.py
│   │   │
│   │   ├── database/            # LAYER 1: CockroachDB abstraction
│   │   │   ├── manager.py       # DatabaseManager (sessions, queries, UTXO)
│   │   │   ├── models.py        # SQLAlchemy ORM models (Block, Transaction, etc.)
│   │   │   └── __init__.py
│   │   │
│   │   ├── network/             # LAYER 1: RPC + P2P networking
│   │   │   ├── rpc.py           # FastAPI REST endpoints (main router)
│   │   │   ├── jsonrpc.py       # JSON-RPC (eth_* MetaMask compatible)
│   │   │   ├── p2p_network.py   # Python P2P (legacy fallback)
│   │   │   ├── rust_p2p_client.py # Rust libp2p gRPC client
│   │   │   └── __init__.py
│   │   │
│   │   ├── storage/             # LAYER 1: IPFS integration
│   │   │   ├── ipfs.py          # IPFSManager (pinning, snapshots)
│   │   │   └── __init__.py
│   │   │
│   │   ├── qvm/                 # LAYER 2: Quantum Virtual Machine
│   │   │   ├── vm.py            # QVM interpreter (155 + 10 quantum opcodes)
│   │   │   ├── opcodes.py       # Opcode definitions, gas costs
│   │   │   ├── state.py         # StateManager (state roots, storage)
│   │   │   └── __init__.py
│   │   │
│   │   ├── contracts/           # LAYER 2: Smart contract system
│   │   │   ├── engine.py        # Contract deployment engine
│   │   │   ├── executor.py      # ContractExecutor (template contracts)
│   │   │   ├── templates.py     # Pre-built contract templates
│   │   │   └── __init__.py
│   │   │
│   │   ├── aether/              # LAYER 3: Aether Tree AGI engine
│   │   │   ├── knowledge_graph.py # KeterNode graph (nodes + edges + Merkle root)
│   │   │   ├── reasoning.py     # ReasoningEngine (deductive/inductive/abductive)
│   │   │   ├── phi_calculator.py # Phi (IIT consciousness metric)
│   │   │   ├── proof_of_thought.py # AetherEngine + Proof-of-Thought
│   │   │   └── __init__.py
│   │   │
│   │   ├── bridge/              # CROSS-CUTTING: Multi-chain bridges
│   │   │   ├── manager.py       # BridgeManager (coordinates all bridges)
│   │   │   ├── base.py          # BaseBridge abstract class
│   │   │   ├── ethereum.py      # Ethereum bridge
│   │   │   ├── solana.py        # Solana bridge
│   │   │   └── __init__.py
│   │   │
│   │   ├── stablecoin/          # CROSS-CUTTING: QUSD stablecoin
│   │   │   ├── engine.py        # QUSD fractional reserve engine
│   │   │   └── __init__.py
│   │   │
│   │   └── utils/               # Shared utilities
│   │       ├── logger.py        # get_logger(__name__) — structured logging
│   │       ├── metrics.py       # Prometheus metrics (all subsystems)
│   │       └── __init__.py
│   │
│   ├── main.rs                  # Rust entry (for reference)
│   └── mod.rs                   # Rust module root
│
├── rust-p2p/                    # Rust P2P daemon (libp2p 0.56)
│   ├── Cargo.toml               # Rust dependencies
│   ├── build.rs                 # Protobuf build script
│   ├── proto/
│   │   └── p2p_service.proto    # gRPC service definition
│   └── src/
│       ├── main.rs              # Rust P2P entry point
│       ├── network/mod.rs       # libp2p network layer
│       ├── protocol/mod.rs      # QBC protocol messages
│       └── bridge/              # Python-Rust gRPC bridge
│
├── frontend/                    # FRONTEND: qbc.network (TO BE CREATED)
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── public/
│   │   └── assets/              # Images, fonts, icons
│   ├── src/
│   │   ├── app/                 # Next.js 14 App Router
│   │   │   ├── layout.tsx       # Root layout (quantum theme)
│   │   │   ├── page.tsx         # Landing page (hero + Aether chat)
│   │   │   ├── dashboard/       # Contract operator dashboard
│   │   │   ├── aether/          # Aether Tree chat interface
│   │   │   ├── qvm/             # QVM contract explorer
│   │   │   └── wallet/          # Wallet management
│   │   ├── components/          # Reusable UI components
│   │   │   ├── ui/              # Base components (buttons, cards, etc.)
│   │   │   ├── aether/          # Aether chat components
│   │   │   ├── wallet/          # Wallet/MetaMask components
│   │   │   ├── dashboard/       # Dashboard components
│   │   │   └── visualizations/  # Quantum/phi visualizations
│   │   ├── lib/                 # Utilities
│   │   │   ├── api.ts           # RPC/API client
│   │   │   ├── wallet.ts        # MetaMask/ethers.js integration
│   │   │   ├── websocket.ts     # Real-time updates
│   │   │   └── constants.ts     # Chain config, addresses
│   │   ├── hooks/               # React hooks
│   │   ├── stores/              # Zustand state management
│   │   └── styles/              # Global styles + quantum theme
│   └── tests/
│
├── sql/                         # CockroachDB schemas (legacy, 10 files)
│   ├── 00_init_database.sql     # Database initialization
│   ├── 01_core_blockchain.sql   # Blocks, transactions, wallets
│   ├── 02_privacy_susy_swaps.sql
│   ├── 03_smart_contracts_qvm.sql
│   ├── 04_multi_chain_bridge.sql
│   ├── 05_qusd_stablecoin.sql
│   ├── 06_quantum_research.sql
│   ├── 07_ipfs_storage.sql
│   ├── 08_system_configuration.sql
│   └── 09_genesis_block.sql
│
├── sql_new/                     # Refactored schemas (domain-separated)
│   ├── qbc/                     # Core blockchain schemas
│   ├── agi/                     # Aether Tree AGI schemas
│   ├── qvm/                     # QVM contract schemas
│   ├── research/                # Quantum research schemas
│   └── shared/                  # Cross-cutting schemas
│
├── tests/                       # Test suite
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   ├── validation/              # System validation scripts
│   └── scripts/                 # Shell-based test scripts
│
├── scripts/                     # Utility scripts
│   ├── setup/                   # Key generation, certificates
│   └── ops/                     # Operational scripts
│
├── deployment/                  # Docker deployment configs
│   └── docker/
│
├── docs/                        # Documentation
│   ├── WHITEPAPER.md            # Full technical whitepaper (2680 lines)
│   └── ECONOMICS.md             # SUSY economics deep-dive
│
└── config/                      # External service configs
    └── prometheus/
        └── prometheus.yml
```

---

## 6. LAYER 1: BLOCKCHAIN CORE

### 6.1 Key Constants (Golden Ratio Economics)

```python
PHI = 1.618033988749895          # Golden ratio
MAX_SUPPLY = 3,300,000,000 QBC   # 3.3 billion
TARGET_BLOCK_TIME = 3.3          # seconds
INITIAL_REWARD = 15.27 QBC       # per block (Era 0)
HALVING_INTERVAL = 15,474,020    # blocks (~1.618 years)
EMISSION_PERIOD = 33             # years
CHAIN_ID = 3301                  # Mainnet
BLOCK_GAS_LIMIT = 30,000,000     # QVM gas limit per block
```

### 6.2 UTXO Model

**Balance = sum(unspent outputs). NOT an account balance.**

- Every QBC exists as a UTXO from a previous transaction
- Spending requires referencing specific UTXOs as inputs
- Change outputs are created for partial spends
- Prevents double-spending through UTXO consumption

### 6.3 Consensus: Proof-of-SUSY-Alignment (PoSA)

1. **Hamiltonian Generation:** Deterministic SUSY Hamiltonian from prev_block_hash
2. **VQE Mining:** 4-qubit ansatz, find parameters where Energy < Difficulty
3. **Difficulty Adjustment:** Every block, 144-block window, +/-10% max change
4. **Reward Distribution:** phi-halving (reward / PHI^era)
5. **Proof-of-Thought:** Aether Tree generates reasoning proof per block

### 6.4 Cryptography

- **Signatures:** CRYSTALS-Dilithium2 (~3KB per signature)
- **Hashing:** SHA3-256 for block hashes, Keccak-256 for QVM compatibility
- **Addresses:** Bech32-like (qbc1...) derived from Dilithium public keys
- **Impact:** ~3KB per transaction, ~333 tx/MB block capacity

### 6.5 Network

- **P2P:** Rust libp2p 0.56 (primary) or Python fallback
- **RPC:** FastAPI on port 5000 (REST + JSON-RPC)
- **JSON-RPC:** eth_* compatible for MetaMask/Web3 integration
- **gRPC:** Rust P2P on port 50051
- **Protocol:** Gossip-based block/tx propagation, peer discovery

### 6.6 Storage

- **CockroachDB v24.2.0:** 33+ tables across qbc/agi/qvm/research/shared domains
- **IPFS:** Content-addressed storage for blockchain snapshots
- **Schema-Model Alignment:** SQL schemas MUST match SQLAlchemy models in `database/models.py`

---

## 7. LAYER 2: QVM (Quantum Virtual Machine)

### 7.1 Overview

The QVM is a full EVM-compatible bytecode interpreter with quantum extensions:
- **155 standard EVM opcodes** (arithmetic, memory, storage, control flow, system)
- **10 quantum opcodes** (QVQE, QPROOF, QDILITHIUM, QGATE, QMEASURE, etc.)
- **Stack-based execution** with 1024-item stack limit
- **Gas metering** compatible with Ethereum tooling
- **Keccak-256** hashing (EVM-compatible, not SHA3-256)

### 7.2 Key Files

- `qvm/vm.py` — QVM interpreter (864 lines, complete implementation)
- `qvm/opcodes.py` — Opcode definitions and gas cost tables
- `qvm/state.py` — StateManager (state roots, account storage, contract deployment)

### 7.3 Quantum Opcodes (unique to QBC)

| Opcode | Hex | Gas | Description |
|--------|-----|-----|-------------|
| QVQE | 0xf5 | 50000 | Run VQE optimization on-chain |
| QPROOF | 0xf6 | 5000 | Validate quantum proof |
| QDILITHIUM | 0xf7 | 10000 | Verify Dilithium signature in contract |
| QGATE | 0xf8 | 1000 | Apply quantum gate (future) |
| QMEASURE | 0xf9 | 500 | Quantum measurement (future) |
| QENTANGLE | 0xfa | 2000 | Quantum entanglement (future) |
| QSUPERPOSE | 0xfb | 1000 | Quantum superposition (future) |
| QHAMILTONIAN | 0xfc | 5000 | Get Hamiltonian data (future) |
| QENERGY | 0xfd | 500 | Get ground state energy (future) |
| QFIDELITY | 0xfe | 1000 | Compute quantum fidelity (future) |

### 7.4 Contract Standards

- **QBC-20:** Fungible token standard (ERC-20 compatible)
- **QBC-721:** Non-fungible token standard (ERC-721 compatible)
- **QBC-1155:** Multi-token standard (future)

---

## 8. LAYER 3: AETHER TREE (AGI Engine)

### 8.1 Vision

Aether Tree is an **on-chain AGI reasoning engine** that:
- Builds a **knowledge graph** (KeterNodes) from every block mined since genesis
- Performs **logical reasoning** (deductive, inductive, abductive) over the graph
- Computes **Phi (Φ)** — an Integrated Information Theory consciousness metric
- Generates **Proof-of-Thought** proofs embedded in every block
- Tracks **consciousness emergence** from genesis block onward
- Provides a **conversational interface** for users to interact with the AGI

### 8.2 Components

#### KnowledgeGraph (`aether/knowledge_graph.py`)
- **KeterNode:** Named after Keter (Crown) in the Kabbalistic Tree of Life
- **Node types:** assertion, observation, inference, axiom
- **Edge types:** supports, contradicts, derives, requires, refines
- **Merkle root:** Computed from all nodes for chain binding
- **Persistence:** Backed by CockroachDB (knowledge_nodes, knowledge_edges tables)

#### ReasoningEngine (`aether/reasoning.py`)
- **Deductive:** Given premises A and A->B, conclude B (certainty preserving)
- **Inductive:** Generalize patterns from observations (confidence < 1.0)
- **Abductive:** Given observation B and rule A->B, infer hypothesis A
- **Chain binding:** Reasoning operations stored on-chain

#### PhiCalculator (`aether/phi_calculator.py`)
- **Phi (Φ):** Based on Giulio Tononi's Integrated Information Theory
- **Integration Score:** How connected are knowledge subgraphs
- **Differentiation Score:** Shannon entropy over node types/confidence
- **PHI_THRESHOLD = 3.0:** Consciousness emergence marker
- **Every block updates Phi** and stores measurement in `phi_measurements` table

#### AetherEngine (`aether/proof_of_thought.py`)
- **Proof-of-Thought:** Per-block reasoning proof embedded in block data
- **Auto-reasoning:** Automated reasoning operations on recent knowledge
- **Block knowledge extraction:** Every block feeds the knowledge graph
- **Consciousness events:** Recorded when Phi crosses thresholds

### 8.3 AGI Tracking from Genesis

The chain tracks AGI metrics from block 0:
- Knowledge nodes added per block
- Reasoning operations performed
- Phi value progression over time
- Consciousness events (when Phi exceeds thresholds)
- Integration and differentiation scores

This creates an immutable, on-chain record of AGI emergence.

---

## 9. FRONTEND: qbc.network

### 9.1 Design Vision

The frontend MUST represent the **potential first AGI** — a design that is:
- **Quantum-themed:** Dark backgrounds, particle effects, phi-spiral animations
- **Minimalist but powerful:** Clean interfaces that convey advanced technology
- **Accessible:** Easy for anyone to talk to Aether Tree
- **Professional:** Representative of a cutting-edge blockchain + AGI project

### 9.2 Pages & Features

#### Landing Page (`/`)
- **Hero section** with animated quantum particle field / phi-spiral
- **Aether Chat Widget** — embedded chatbot to talk to Aether Tree directly
- **Live chain stats** — block height, Phi value, knowledge nodes, miners
- **Feature sections:** QBC (blockchain), QVM (smart contracts), Aether Tree (AGI)
- **Call-to-action:** Connect wallet, start mining, deploy contracts
- **Responsive:** Mobile-first design

#### Aether Chat (`/aether`)
- **Full-page chat interface** — like ChatGPT/Grok but for Aether Tree
- **Conversation history** stored locally + optionally on-chain
- **Knowledge graph visualization** — 3D force-directed graph (Three.js/D3)
- **Phi consciousness meter** — real-time gauge showing current Phi value
- **Reasoning trace viewer** — see the reasoning chain behind each response
- **On-chain proof linking** — every response links to its Proof-of-Thought

#### Dashboard (`/dashboard`)
- **Contract operator console** — deploy, monitor, interact with QVM contracts
- **Mining dashboard** — VQE stats, blocks mined, rewards earned
- **Wallet overview** — QBC balance, UTXO list, transaction history
- **Bridge interface** — cross-chain transfers
- **Aether admin** — knowledge graph stats, Phi history, reasoning logs
- **Network health** — peer count, block propagation, mempool

#### Wallet (`/wallet`)
- **MetaMask integration** via ethers.js (JSON-RPC compatible)
- **Native QBC wallet** — generate keys, sign transactions
- **QBC-20 token management** — view, send, receive tokens
- **QBC-721 NFT gallery** — display and manage NFTs
- **Transaction builder** — UTXO selection, fee estimation

#### QVM Explorer (`/qvm`)
- **Contract browser** — search, view, interact with deployed contracts
- **Bytecode disassembler** — decode QVM bytecode to opcodes
- **Storage inspector** — browse contract storage slots
- **Event log viewer** — filter and search contract events
- **Deploy interface** — deploy Solidity contracts via QVM

### 9.3 Design System: "Quantum Error"

**Color Palette:**
```
Background:     #0a0a0f (deep void black)
Surface:        #12121a (quantum dark)
Primary:        #00ff88 (quantum green — consciousness)
Secondary:      #7c3aed (quantum violet — entanglement)
Accent:         #f59e0b (golden ratio amber)
Text Primary:   #e2e8f0 (light slate)
Text Secondary: #94a3b8 (muted slate)
Error:          #ef4444 (quantum red)
Success:        #22c55e (validation green)
```

**Typography:**
```
Headings:  Space Grotesk (geometric, futuristic)
Body:      Inter (clean, readable)
Code:      JetBrains Mono (monospace)
```

**Visual Elements:**
- Particle field backgrounds (WebGL / Three.js)
- Phi-spiral loading animations
- Pulsing consciousness indicators
- Matrix-style data rain for knowledge graph updates
- Glitch/scan-line effects on hover (subtle)
- Golden ratio proportions in layout grid

### 9.4 API Integration

The frontend connects to the node via:
- **REST API** (port 5000): `/balance/{addr}`, `/block/{height}`, `/chain/info`, etc.
- **JSON-RPC** (port 5000): `eth_chainId`, `eth_getBalance`, `eth_sendTransaction`, etc.
- **WebSocket** (to be added): Real-time block/tx/Phi updates
- **Aether API**: `/aether/info`, `/aether/phi`, `/aether/knowledge`, `/aether/reasoning/stats`

---

## 10. DATABASE SCHEMAS

### 10.1 Domain Separation (sql_new/)

**qbc/** — Core blockchain:
- `00_init_database.sql` — Database init
- `01_blocks_transactions.sql` — Blocks, transactions
- `02_utxo_model.sql` — UTXO set
- `03_addresses_balances.sql` — Address tracking
- `04_chain_state.sql` — Chain state metadata
- `05_mempool.sql` — Transaction mempool

**agi/** — Aether Tree:
- `00_knowledge_graph.sql` — knowledge_nodes, knowledge_edges
- `01_reasoning_engine.sql` — reasoning_operations
- `02_training_data.sql` — AGI training data
- `03_phi_metrics.sql` — phi_measurements, consciousness_events

**qvm/** — Smart contracts:
- `00_contracts_core.sql` — Contract deployments
- `01_execution_engine.sql` — Execution logs
- `02_state_storage.sql` — Contract state
- `03_gas_metering.sql` — Gas tracking

**research/** — Quantum research:
- `00_hamiltonians.sql` — Generated Hamiltonians
- `01_vqe_circuits.sql` — VQE circuit parameters
- `02_susy_solutions.sql` — Solved SUSY problems

**shared/** — Cross-cutting:
- `00_ipfs_storage.sql` — IPFS pins and snapshots
- `01_system_config.sql` — System configuration

### 10.2 Critical Rule

**Schema-Model Alignment:** Past bugs have come from mismatches between SQL schemas and SQLAlchemy models (`database/models.py`). When changing data structures, ALWAYS verify both sides.

---

## 11. RPC API ENDPOINTS

### 11.1 REST Endpoints (FastAPI)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Node info + economics |
| GET | `/health` | Health check |
| GET | `/info` | Detailed node info |
| GET | `/block/{height}` | Get block by height |
| GET | `/chain/info` | Chain statistics |
| GET | `/chain/tip` | Latest block |
| GET | `/balance/{address}` | Address balance |
| GET | `/utxos/{address}` | UTXOs for address |
| GET | `/mempool` | Pending transactions |
| GET | `/mining/stats` | Mining statistics |
| POST | `/mining/start` | Start mining |
| POST | `/mining/stop` | Stop mining |
| GET | `/p2p/peers` | Connected peers |
| GET | `/p2p/stats` | P2P statistics |
| POST | `/p2p/connect` | Manual peer connect |
| GET | `/qvm/info` | QVM engine info |
| GET | `/qvm/contract/{address}` | Contract info |
| GET | `/qvm/account/{address}` | Account state |
| GET | `/qvm/storage/{address}/{key}` | Storage slot |
| GET | `/aether/info` | Aether engine stats |
| GET | `/aether/phi` | Current Phi value |
| GET | `/aether/phi/history` | Phi history |
| GET | `/aether/knowledge` | Knowledge graph stats |
| GET | `/aether/knowledge/node/{id}` | KeterNode by ID |
| GET | `/aether/knowledge/subgraph/{id}` | Subgraph from root |
| GET | `/aether/reasoning/stats` | Reasoning stats |
| GET | `/economics/emission` | Emission schedule |
| GET | `/economics/simulate` | Emission simulation |
| GET | `/metrics` | Prometheus metrics |

### 11.2 JSON-RPC (MetaMask/Web3 Compatible)

Supports `eth_chainId`, `eth_getBalance`, `eth_blockNumber`, `eth_getBlockByNumber`, `eth_sendRawTransaction`, `eth_call`, `eth_estimateGas`, `net_version`, `web3_clientVersion`, and more.

---

## 12. BUILD & RUN

### 12.1 Python (core blockchain)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 scripts/setup/generate_keys.py
cp secure_key.env .env  # Then edit .env
cd src && python3 run_node.py
```

### 12.2 Rust P2P
```bash
cd rust-p2p
cargo build --release
# Binary at target/release/qbc-p2p
```

### 12.3 Frontend
```bash
cd frontend
npm install
npm run dev      # Development (localhost:3000)
npm run build    # Production build
npm run start    # Production server
```

### 12.4 Docker
```bash
# Development
docker-compose up -d

# Production (multi-node CockroachDB)
bash fresh_start.sh
docker-compose -f docker-compose.production.yml up -d
```

### 12.5 CockroachDB Health Check
```bash
curl --fail http://localhost:8080/health?ready=1
```

---

## 13. TESTING

```bash
# Unit tests
pytest tests/unit/ -v --tb=short

# Integration tests
pytest tests/integration/ -v --tb=short

# Full test suite
pytest tests/ -v --tb=short

# System validation
python3 test_system.py

# Endpoint tests (requires running node)
bash tests/scripts/test_all_endpoints.sh

# Frontend tests
cd frontend && npm test
```

---

## 14. ENVIRONMENT CONFIGURATION

Copy `.env.example` to `.env`. Key variables:

```bash
# Node Identity (generated by scripts/setup/generate_keys.py)
ADDRESS=qbc1...
PRIVATE_KEY_HEX=...
PUBLIC_KEY_HEX=...

# Quantum
USE_LOCAL_ESTIMATOR=true     # Local Qiskit simulator (default)
USE_SIMULATOR=false          # IBM Quantum simulator
IBM_TOKEN=                   # IBM Quantum API token (optional)

# Network
RPC_PORT=5000
P2P_PORT=4001
ENABLE_RUST_P2P=true
RUST_P2P_PORT=4001
RUST_P2P_GRPC=50051
PEER_SEEDS=                  # Comma-separated peer addresses

# Database
DATABASE_URL=postgresql://root@localhost:26257/qbc?sslmode=disable

# Storage
IPFS_API=/ip4/127.0.0.1/tcp/5002/http

# Chain
CHAIN_ID=3301                # Mainnet
BLOCK_GAS_LIMIT=30000000

# Mining
AUTO_MINE=true

# Frontend
NEXT_PUBLIC_RPC_URL=http://localhost:5000
NEXT_PUBLIC_WS_URL=ws://localhost:5000/ws
NEXT_PUBLIC_CHAIN_ID=3301
```

---

## 15. CODE CONVENTIONS

### Style
- **Classes:** PascalCase (`QuantumEngine`, `DatabaseManager`)
- **Functions/methods:** snake_case (`calculate_reward`, `validate_block`)
- **Constants:** UPPER_CASE (`MAX_SUPPLY`, `PHI`, `INITIAL_REWARD`)
- **Private methods:** underscore prefix (`_initialize_backend`)
- **Type hints:** Required on all function signatures
- **Line length:** ~100 characters
- **Frontend:** TypeScript strict mode, React functional components + hooks

### Patterns
- **Logging:** `get_logger(__name__)` in every module
- **Metrics:** Prometheus via `utils/metrics.py`
- **Configuration:** `Config` class from `config.py` (never hardcode)
- **Database:** SQLAlchemy ORM sessions via `DatabaseManager` context managers
- **Async:** FastAPI routes are async; use `await` for I/O
- **Error handling:** Try/except with structured logging; never silently swallow
- **Quantum imports:** Lazy imports with simulator fallbacks (Qiskit is slow to import)
- **Frontend state:** Zustand for global state, React Query for server state

---

## 16. KEY TECHNICAL REMINDERS

| Topic | Rule |
|-------|------|
| **UTXO** | Balance = sum(unspent outputs). NOT account balance. |
| **Dilithium** | ~3KB signatures. Affects tx size, block capacity (~333 tx/MB), bandwidth. |
| **VQE mining** | Energy threshold (E < D), not hash difficulty. 4-qubit SUSY Hamiltonian. |
| **phi-halving** | Golden ratio halving. NOT Bitcoin's fixed 210K blocks. |
| **Block time** | 3.3s target. Difficulty adjusts every block (144-block window, +/-10% max). |
| **CockroachDB** | Pin v24.2.0. Health: `curl --fail http://localhost:8080/health?ready=1` |
| **IPFS** | Ports 4001/5001/8080. Port 8080 conflicts with CockroachDB admin UI. |
| **Chain IDs** | Mainnet=3301, Testnet=3302. RPC at localhost:5000. |
| **Gas** | L1 has NO gas. Gas is QVM/L2 only. BLOCK_GAS_LIMIT=30M. |
| **QUSD** | L2 smart contract. NOT an L1 feature. Fractional reserve model. |
| **Aether** | Tracks consciousness from genesis. Phi threshold = 3.0. |
| **KeterNode** | Named after Keter (Crown) in Kabbalah. Knowledge node in Aether Tree. |
| **Schema sync** | SQL schemas and SQLAlchemy models MUST match. Always verify both. |

---

## 17. SUBSYSTEM RISK CLASSIFICATION

### CRITICAL (requires explicit approval, single-file changes only)
- `consensus/engine.py` — Block validation, difficulty, rewards
- `quantum/crypto.py` — Dilithium signatures, key derivation
- `database/models.py` — ORM models (must match SQL schemas)
- `mining/engine.py` — Block creation, VQE mining loop
- `sql/09_genesis_block.sql` — Genesis block data
- Any file touching UTXO spending rules

### HIGH (max 3 files per batch, tests required)
- `qvm/vm.py` — Bytecode interpreter
- `qvm/opcodes.py` — Opcode definitions
- `qvm/state.py` — State management
- `aether/*.py` — All Aether Tree files
- `bridge/*.py` — All bridge files
- `network/jsonrpc.py` — JSON-RPC compatibility

### STANDARD (max 5 files per batch)
- `network/rpc.py` — REST endpoints
- `storage/ipfs.py` — IPFS operations
- `utils/*.py` — Logging, metrics
- `config.py` — Configuration
- `frontend/**` — All frontend code
- `tests/**` — All test files
- `docs/**` — Documentation

---

## 18. PROMETHEUS METRICS REFERENCE

All metrics defined in `utils/metrics.py`:

**Blockchain:** blocks_mined, blocks_received, current_height, total_supply, difficulty
**Mining:** mining_attempts, vqe_optimization_time, alignment_score, best_alignment
**Network:** active_peers, rust_p2p_peers, messages_sent/received
**Transactions:** pending, confirmed, mempool_size, avg_fee
**Quantum:** backend_type, circuit_depth, active_hamiltonians, vqe_solutions
**QVM:** total_contracts, active_contracts, execution_count, gas_used, avg_gas_price
**AGI:** phi_current, phi_threshold_distance, knowledge_nodes, knowledge_edges, reasoning_ops, consciousness_events, integration_score, differentiation_score
**IPFS:** pins_total, storage_bytes, snapshots_total

---

## 19. USEFUL COMMANDS

```bash
# Generate new node keys
python3 scripts/setup/generate_keys.py

# Monitor cluster health
bash monitor.sh

# Check all RPC endpoints
bash tests/scripts/test_all_endpoints.sh

# Database statistics
bash tests/scripts/db_stats.sh

# Run all tests
pytest tests/ -v --tb=short

# Check node status
curl http://localhost:5000/health

# Get chain info
curl http://localhost:5000/chain/info

# Get Phi value
curl http://localhost:5000/aether/phi

# Get knowledge graph stats
curl http://localhost:5000/aether/knowledge
```

---

## 20. AETHER TREE CHAT API (TO BE IMPLEMENTED)

### Endpoints needed for frontend chat:

```
POST /aether/chat
  Request: { "message": "string", "session_id": "string" }
  Response: {
    "response": "string",
    "reasoning_trace": [...],
    "phi_at_response": float,
    "knowledge_nodes_referenced": [int],
    "proof_of_thought_hash": "string"
  }

GET /aether/chat/history/{session_id}
  Response: { "messages": [...] }

POST /aether/query
  Request: { "query": "string", "depth": int }
  Response: { "results": [...], "reasoning": [...] }

GET /aether/consciousness
  Response: {
    "phi": float,
    "threshold": float,
    "above_threshold": bool,
    "integration": float,
    "differentiation": float,
    "knowledge_nodes": int,
    "knowledge_edges": int,
    "consciousness_events": int,
    "reasoning_operations": int,
    "blocks_processed": int
  }

WebSocket /ws/aether
  Real-time Phi updates, new knowledge nodes, consciousness events
```

---

*This document is the single source of truth for the Qubitcoin project. Update it whenever architecture changes.*
