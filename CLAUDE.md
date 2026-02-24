# CLAUDE.md - Qubitcoin Master Development Guide

> **The definitive reference for AI-assisted development on the Qubitcoin codebase.**
> Covers Layer 1 (blockchain), Layer 2 (QVM + smart contracts), Layer 3 (Aether Tree AGI),
> and the Frontend (qbc.network).

---

## 1. PROJECT IDENTITY

**Qubitcoin (QBC) | Quantum Blockchain** is a physics-secured Layer 1 blockchain that combines:
- **Quantum Computing** (Qiskit VQE) for Proof-of-SUSY-Alignment mining
- **Post-Quantum Cryptography** (CRYSTALS-Dilithium2) for quantum-resistant signatures
- **Supersymmetric (SUSY) Economics** with golden ratio (phi) emission principles
- **Aether Tree** : an on-chain AGI reasoning engine that tracks consciousness metrics from genesis
- **QVM** : a full EVM-compatible virtual machine with quantum opcode extensions
- **Multi-chain bridges** to ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE

**Tagline:** Physics-Secured Digital Assets with On-Chain AGI

**Domain:** qbc.network
**License:** MIT
**Chain IDs:** Mainnet=3301, Testnet=3302
**Contact:** info@qbc.network
**GitHub:** BlockArtica/Qubitcoin

---

## 1.1 CURRENT PROJECT STATUS (February 2026)

**All code is written and production-ready. The project is in launch phase.**

### What Is Built (Complete)

| Layer | Component | Files | LOC | Status |
|-------|-----------|-------|-----|--------|
| **L1** | Blockchain Core (Python) | 15 modules | ~7,800 | Production Ready |
| **L1** | Rust P2P (libp2p 0.56) | 4 source files | ~1,200 | Production Ready |
| **L2** | QVM Python Prototype | 8 modules | ~4,500 | Production Ready |
| **L2** | QVM Go Production | 32 source files | ~10,000 | Production Ready |
| **L2** | Solidity Contracts | 49 contracts | ~12,000 | Production Ready |
| **L3** | Aether Tree (Python) | 33 modules | ~18,500 | Production Ready |
| **Frontend** | React/Next.js (qbc.network) | 35 components | ~8,000 | 85-90% Ready |
| **Infra** | Docker/Monitoring/DevOps | 20+ configs | ~2,000 | Production Ready |
| **Docs** | Whitepapers + Guides | 14 files | ~5,800 | Production Ready |
| **Tests** | Python pytest suite | 2,476 tests | ~32,000 | All Passing |
| **Total** | | **250+ files** | **~80,000+** | **Production Ready** |

### What Needs To Happen Next

**See `LAUNCHTODO.md` for the complete step-by-step launch checklist.**

The immediate launch sequence is:
1. Generate node keys (`python3 scripts/setup/generate_keys.py`)
2. Create `.env` from `.env.example`
3. Run `docker compose up -d` → **genesis block mined, Aether Tree starts**
4. Start frontend (`cd frontend && pnpm install && pnpm dev`)
5. Deploy 49 Solidity contracts via RPC (post-genesis)

### Known Issues To Be Aware Of

| Issue | Severity | Details |
|-------|----------|---------|
| `ENABLE_RUST_P2P` | Resolved | Default is now `true` — Rust libp2p is the primary P2P layer. Node auto-launches Rust binary and falls back to Python P2P if binary is missing or daemon fails to start. |
| Frontend backend gaps | Low | Most backend API endpoints now wired. A few frontend pages may still show "---" for real-time data when node is not running. |
| Schema-model sync | Low | Both db-init SQL and SQLAlchemy create tables. SQLAlchemy `create_all()` skips existing tables, so no conflict if SQL runs first. |
| Smart contracts | Info | 49 Solidity contracts exist but are NOT auto-deployed at genesis. Must deploy via RPC after node is running. |

### Key Files For Launch

| File | Purpose |
|------|---------|
| `LAUNCHTODO.md` | **Master launch checklist** — 8 phases from zero to production |
| `CLAUDE.md` | This file — architecture reference |
| `docker-compose.yml` | Docker stack (9 services) |
| `.env.example` | Environment template |
| `scripts/setup/generate_keys.py` | Node key generation |
| `src/run_node.py` | Node entry point |
| `src/qubitcoin/node.py` | 22-component orchestrator |
| `src/qubitcoin/config.py` | Configuration (loads `.env` + `secure_key.env`) |

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
- NEVER hardcode secrets — private keys go in `secure_key.env`, config goes in `.env`
- NEVER commit `secure_key.env` — it is .gitignored and contains Dilithium private keys
- NEVER put private keys in `.env` — use `secure_key.env` exclusively for key material
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
║  │  Next.js 15 + TailwindCSS 4 + Framer Motion                    │   ║
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
║  │  155 EVM + 10 quantum + 2 AGI opcodes (167 total)              │   ║
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

> **RULE: Always use the absolute latest stable versions of ALL dependencies.**
> When starting a new component or updating an existing one, check for the latest
> version available and use it. Never pin to old versions unless there is a
> specific compatibility requirement (e.g., CockroachDB v24.2.0).

| Component | Technology | Version Policy |
|-----------|-----------|---------------|
| **L1 Core** | Python | 3.12+ (latest stable) |
| **P2P Networking** | Rust (libp2p) | 2021 edition, libp2p latest |
| **Web Framework** | FastAPI | latest |
| **ORM** | SQLAlchemy | latest |
| **Database** | CockroachDB | v24.2.0 (pinned — compatibility) |
| **Quantum** | Qiskit | latest |
| **Content Storage** | IPFS (Kubo) | latest |
| **Frontend Framework** | React 19 + Next.js 15 (App Router) | latest stable |
| **Language** | TypeScript 5.x (strict mode) | latest |
| **Styling** | TailwindCSS 4 + Framer Motion | latest |
| **State Management** | Zustand + TanStack Query (React Query) | latest |
| **3D / Viz** | Three.js + React Three Fiber + D3 | latest |
| **Wallet** | ethers.js v6 (MetaMask compat) | latest |
| **Deployment** | Vercel (frontend) + Docker (backend) | latest |
| **Monitoring** | Prometheus + Grafana | latest |
| **Package Manager** | pnpm (frontend) / pip (backend) | latest |
| **Linting/Formatting** | ESLint 9 + Prettier + Biome | latest |
| **Testing** | Vitest + Playwright (frontend) / pytest (backend) | latest |

---

## 5. REPOSITORY STRUCTURE

> **Root: 14 tracked files. 13 tracked directories. Clean.**
> Labels show future repo split: `[L1]` stays in core, `[FUTURE REPO]` splits out, `[SHARED]` becomes common package.

```
Qubitcoin/
├── CLAUDE.md                         # THIS FILE — master development guide
├── AGENTS.md                         # AI efficiency guide (data structures, pitfalls)
├── README.md                         # Public-facing docs
├── LAUNCHTODO.md                     # Launch checklist
├── CONTRIBUTING.md                   # Contributor guidelines
├── LICENSE                           # MIT license
├── .gitignore
├── .env.example                      # Environment template
├── secure_key.env.example            # Key template
├── requirements.txt                  # Python dependencies
├── Dockerfile                        # Docker build
├── docker-compose.yml                # Dev deployment
├── docker-compose.production.yml     # Production deployment
├── .dockerignore                     # Build excludes
├── contract_registry.json            # Deployed contract addresses
│
├── .github/workflows/                # CI/CD
│   ├── ci.yml                        # Python test pipeline
│   ├── claude.yml                    # Claude Code integration
│   └── qvm-ci.yml                   # Go QVM test pipeline
│
├── src/                              # Python source code
│   ├── run_node.py                   # Node entry point
│   └── qubitcoin/                    # Main Python package (102 modules)
│       ├── node.py                   # 22-component orchestrator
│       ├── config.py                 # Centralized configuration
│       ├── consensus/engine.py       # [L1] Block validation, difficulty, rewards
│       ├── mining/engine.py          # [L1] VQE mining loop, block creation
│       ├── quantum/                  # [L1] Quantum engine
│       │   ├── engine.py             # VQE, Hamiltonian generation, Qiskit
│       │   └── crypto.py             # Dilithium2 signatures
│       ├── database/                 # [SHARED] CockroachDB
│       │   ├── manager.py            # DatabaseManager (sessions, queries)
│       │   └── models.py             # SQLAlchemy ORM models
│       ├── network/                  # [L1] RPC + P2P
│       │   ├── rpc.py                # 215+ REST + JSON-RPC endpoints
│       │   ├── jsonrpc.py            # eth_* MetaMask compatible
│       │   ├── p2p_network.py        # Python P2P (legacy fallback)
│       │   └── rust_p2p_client.py    # Rust libp2p gRPC client
│       ├── storage/ipfs.py           # [L1] IPFSManager
│       ├── privacy/                  # [L1] Susy Swaps
│       │   ├── commitments.py        # Pedersen commitments
│       │   ├── range_proofs.py       # Bulletproofs
│       │   ├── stealth.py            # Stealth addresses
│       │   └── susy_swap.py          # Confidential tx builder
│       ├── bridge/                   # [L1] Multi-chain bridges
│       │   ├── manager.py, base.py, ethereum.py, solana.py
│       ├── stablecoin/engine.py      # [L1] QUSD fractional reserve
│       ├── qvm/                      # [FUTURE: qubitcoin-qvm] Python QVM
│       │   ├── vm.py                 # 167 opcodes (155 EVM + 10 quantum + 2 AGI)
│       │   ├── opcodes.py, state.py, compliance.py, risk.py
│       │   └── plugins/              # QVM plugin system
│       ├── contracts/                # [FUTURE: qubitcoin-qvm]
│       │   ├── engine.py, executor.py, templates.py
│       │   └── solidity/             # 49 Solidity contracts
│       │       ├── aether/           # 17 AGI contracts + sephirot/
│       │       ├── qusd/             # 7 QUSD contracts
│       │       ├── tokens/           # 5 token standards
│       │       ├── bridge/           # 2 bridge contracts
│       │       ├── interfaces/       # 3 interfaces
│       │       └── proxy/            # 3 proxy/upgrade contracts
│       ├── aether/                   # [FUTURE: qubitcoin-aether] 33 modules
│       │   ├── knowledge_graph.py    # KeterNode graph + edge adjacency
│       │   ├── reasoning.py          # Deductive/inductive/abductive + CoT
│       │   ├── phi_calculator.py     # Phi v3 with MIP spectral bisection
│       │   ├── proof_of_thought.py   # AetherEngine + Proof-of-Thought
│       │   ├── on_chain.py           # On-chain AGI bridge
│       │   ├── memory_manager.py     # 3-tier memory system
│       │   ├── working_memory.py     # Attention-based working memory
│       │   ├── neural_reasoner.py    # GAT with online training
│       │   ├── causal_engine.py      # PC algorithm causal discovery
│       │   ├── concept_formation.py  # Concept clustering
│       │   ├── debate_engine.py      # Adversarial debate v2
│       │   ├── temporal_reasoner.py  # Prediction + verification
│       │   ├── vector_index.py       # ANN similarity search
│       │   ├── sephirot.py           # 10 Sephirot cognitive nodes
│       │   ├── sephirot_nodes.py     # Node implementations
│       │   ├── csf_transport.py      # CSF message routing
│       │   ├── pineal.py             # Circadian orchestrator
│       │   ├── safety.py             # Gevurah veto + safety
│       │   ├── consciousness.py      # Consciousness dashboard
│       │   ├── chat.py               # Chat interface
│       │   ├── llm_adapter.py        # LLM integrations
│       │   ├── genesis.py            # AGI genesis initialization
│       │   └── task_protocol.py      # PoT task marketplace
│       └── utils/                    # [SHARED] Utilities
│           ├── logger.py             # get_logger(__name__)
│           ├── metrics.py            # 70 Prometheus metrics
│           ├── fee_collector.py      # Fee collection engine
│           └── qusd_oracle.py        # QUSD price oracle
│
├── qubitcoin-qvm/                    # [FUTURE REPO] Go Production QVM
│   ├── cmd/, internal/, pkg/, plugins/, tests/
│   ├── go.mod, Makefile
│
├── rust-p2p/                         # Rust P2P daemon (libp2p 0.56)
│   ├── proto/p2p_service.proto       # gRPC service definition
│   ├── src/
│   │   ├── main.rs, network/, protocol/, bridge/
│   ├── Cargo.toml, build.rs
│
├── frontend/                         # [FUTURE REPO] qbc.network
│   ├── src/app/                      # Next.js 15 App Router
│   ├── src/components/               # React components
│   ├── src/hooks/, src/lib/, src/stores/, src/styles/
│   ├── package.json, next.config.ts, tailwind.config.ts, vercel.json
│
├── scripts/
│   ├── setup/                        # Key generation, certificates
│   ├── ops/                          # Operational scripts
│   ├── deploy/                       # Contract + schema deployment
│   └── test/                         # Network testing
│
├── sql/                              # Legacy schemas (10 files)
├── sql_new/                          # Domain-separated schemas (qbc, agi, qvm, research, shared)
│
├── tests/                            # Test suite (2,476+ tests, 97 files)
│   ├── unit/                         # Unit tests (83 files)
│   ├── integration/                  # Integration tests
│   ├── validation/                   # Pre-launch validation
│   └── scripts/                      # Shell test utilities
│
├── tools/monitoring/                 # Developer tools (dashboards)
│
├── docs/                             # Documentation
│   ├── audits/                       # Code audit reports
│   ├── WHITEPAPER.md, QVM_WHITEPAPER.md, AETHERTREE_WHITEPAPER.md
│   ├── ECONOMICS.md, DEPLOYMENT.md, SDK.md, PLUGIN_SDK.md
│   └── ... (14 files total)
│
├── config/                           # Service configuration
│   ├── grafana/, loki/, nginx/, prometheus/, redis/
│
└── deployment/                       # Docker/K8s deployment configs
    ├── crosschain/, docker/, kubernetes/, solana/
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
3. **Difficulty Adjustment:** Every block, 144-block window, +/-10% max change. **Higher difficulty = easier mining** (threshold is more generous). `ratio = actual_time / expected_time` — slow blocks raise difficulty, fast blocks lower it.
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

### 6.7 Privacy Technology (Susy Swaps)

> **Full specification:** `docs/WHITEPAPER.md` Section 8

Qubitcoin supports **opt-in privacy** via Susy Swaps — confidential transactions that hide
amounts and addresses while maintaining verifiability.

**Components:**

- **Pedersen Commitments:** `C = v*G + r*H` — hide transaction amounts while preserving
  additive homomorphism (inputs sum = outputs sum verifiable without revealing values)
- **Bulletproofs Range Proofs:** Zero-knowledge proofs that committed values are in [0, 2^64)
  without revealing the value. ~672 bytes per proof, O(log n) size, no trusted setup
- **Stealth Addresses:** One-time addresses per transaction preventing address linkability.
  Uses spend/view key pairs: sender generates ephemeral key, derives unique one-time address
- **Key Images:** Cryptographic construct preventing double-spending of confidential outputs

**Privacy Model:**

| Mode | Amounts | Addresses | Tx Size | Verification |
|------|---------|-----------|---------|-------------|
| **Public** (default) | Visible | Visible | ~300 bytes | Fast |
| **Private** (opt-in) | Hidden | Hidden | ~2000 bytes | ~10ms (range proof) |

**What Susy Swaps hide:** Transaction amounts, sender/receiver addresses, balance linkability.
**What they don't hide:** Transaction existence, timestamps, fee amount, tx size, network metadata.

**Key files (to be implemented):**
- `privacy/commitments.py` — Pedersen commitment creation and verification
- `privacy/range_proofs.py` — Bulletproofs generation and verification
- `privacy/stealth.py` — Stealth address generation and scanning
- `privacy/susy_swap.py` — Confidential transaction builder

### 6.8 Node Types

| Type | Storage | RAM | Network | Capabilities |
|------|---------|-----|---------|-------------|
| **Full Node** | 500GB+ (~50GB/yr growth) | 16GB+ | 100+ Mbps | Full validation, historical queries, mining |
| **Light Node** | 1GB | 2GB | 10+ Mbps | SPV verification, mobile/embedded, <5min sync |
| **Mining Node** | Full Node + quantum | 16GB+ | 100+ Mbps | VQE optimization, block creation |

### 6.9 Block Structure

```
BLOCK HEADER:
{
  "version": 1,
  "prev_block_hash": "0x...",       # SHA3-256 hash of previous block
  "merkle_root": "0x...",           # Merkle root of transactions
  "timestamp": <unix_timestamp>,
  "difficulty_target": <float>,     # Energy threshold for VQE
  "nonce": <int>,
  "hamiltonian_seed": "0x...",      # Deterministic seed for SUSY Hamiltonian
  "vqe_params": [θ₀, θ₁, ...],     # Optimal VQE parameters (mining solution)
  "ground_state_energy": <float>    # Achieved energy level
}

BLOCK BODY:
{
  "transactions": [...],            # Regular + confidential transactions
  "coinbase": {...},                # Mining reward transaction
  "susy_data": {                    # Scientific contribution
    "hamiltonian": {...},
    "optimal_params": [...],
    "energy_history": [...]
  }
}
```

**Confirmation depths:** 1 = unconfirmed, 6 = standard confirmation, 100 = coinbase maturity.

### 6.10 SUSY Solution Database

Every mined block contributes a solved SUSY Hamiltonian to a **public scientific database**:

- **Schema:** `hamiltonian_solutions` table (id, block_height, hamiltonian, ground_state_energy,
  vqe_params, n_qubits, n_terms, mining_time, miner_address, verification_count)
- **Access:** REST API (`/susy-database`), IPFS archival, GraphQL query support
- **Scientific applications:** Particle physics (LHC predictions), materials science
  (superconductors), quantum chemistry (drug design), algorithm benchmarking

### 6.11 Transaction Fees (L1)

```
FEE = SIZE_BYTES × FEE_RATE

FEE_RATE = market-determined (QBC/byte)
Miners select by fee density (QBC/byte), greedy fill up to block size limit.
```

L1 fees are **micro-fees** for UTXO transactions only. Gas metering is QVM/L2 only.

---

## 7. LAYER 2: QVM (Quantum Virtual Machine)

> **Full technical specification:** `docs/QVM_WHITEPAPER.md`

### 7.1 Overview

The QVM is a full EVM-compatible bytecode interpreter with quantum extensions and
institutional-grade compliance features:

- **155 standard EVM opcodes** (arithmetic, memory, storage, control flow, system)
- **10 quantum opcodes** for quantum state persistence, compliance, and risk assessment
- **2 AGI opcodes** (QREASON 0xFA, QPHI 0xFB) for on-chain reasoning and consciousness queries
- **Compliance Engine** — VM-level KYC/AML/sanctions enforcement
- **Plugin Architecture** — extensible domain-specific functionality
- **Stack-based execution** with 1024-item stack limit
- **Gas metering** compatible with Ethereum tooling
- **Keccak-256** hashing (EVM-compatible, not SHA3-256)

### 7.2 Key Files (Current Python Implementation)

- `qvm/vm.py` — QVM interpreter (864 lines, complete EVM + quantum opcodes)
- `qvm/opcodes.py` — Opcode definitions and gas cost tables
- `qvm/state.py` — StateManager (state roots, account storage, contract deployment)

### 7.3 Go Production Implementation (Planned)

The production-grade QVM will be implemented in Go as `qubitcoin-qvm/`:

- `cmd/qvm/` — Main QVM server binary
- `cmd/qvm-cli/` — CLI tool for contract deployment and interaction
- `cmd/plugin-loader/` — Dynamic plugin manager
- `pkg/vm/evm/` — Full EVM core (15 files: opcodes, stack, memory, storage, gas)
- `pkg/vm/quantum/` — Quantum extensions (8 files: states, circuits, entanglement, gates)
- `pkg/compliance/` — Institutional compliance engine (9 files: KYC, AML, sanctions, risk)
- `pkg/plugin/` — Plugin system (5 files: manager, loader, registry, API)
- `pkg/bridge/` — Cross-chain bridge verification (7 files)
- `pkg/rpc/` — gRPC + REST server (7 files)
- `pkg/state/` — Merkle Patricia Trie + quantum state (6 files)
- `pkg/crypto/` — Dilithium + Kyber + ZK proofs (5 files)
- `plugins/` — Domain plugins (privacy, oracle, governance, DeFi)

**Target**: ~90 Go source files, ~150 total files including SQL, docs, config

### 7.4 Quantum Opcodes (0xF0-0xF9)

> **Note:** The QVM whitepaper defines opcodes at 0xF0-0xF9. The current Python
> implementation uses 0xF5-0xFE. The Go production build will use the whitepaper
> mapping (0xF0-0xF9) as canonical.

| Opcode | Hex | Gas | Description |
|--------|-----|-----|-------------|
| QCREATE | 0xF0 | 5,000 + 5,000x2^n | Create quantum state (density matrix) |
| QMEASURE | 0xF1 | 3,000 | Measure quantum state (collapse) |
| QENTANGLE | 0xF2 | 10,000 | Create entangled pair between contracts |
| QGATE | 0xF3 | 2,000 | Apply quantum gate to state |
| QVERIFY | 0xF4 | 8,000 | Verify quantum proof |
| QCOMPLIANCE | 0xF5 | 15,000 | Check KYC/AML/sanctions compliance |
| QRISK | 0xF6 | 5,000 | Query SUSY risk score for address |
| QRISK_SYSTEMIC | 0xF7 | 10,000 | Query systemic risk (contagion model) |
| QBRIDGE_ENTANGLE | 0xF8 | 20,000 | Cross-chain quantum entanglement |
| QBRIDGE_VERIFY | 0xF9 | 15,000 | Verify cross-chain bridge proof |

**Legacy Python mapping (0xF5-0xFE)** — kept for backward compatibility during migration:
QVQE(0xF5), QPROOF(0xF6), QDILITHIUM(0xF7), QGATE(0xF8), QMEASURE(0xF9),
QENTANGLE(0xFA), QSUPERPOSE(0xFB), QHAMILTONIAN(0xFC), QENERGY(0xFD), QFIDELITY(0xFE)

### 7.5 Five Patentable Features

The QVM introduces five novel institutional-grade features:

| Feature | Abbreviation | Description |
|---------|-------------|-------------|
| **Quantum State Persistence** | QSP | Store quantum states as density matrices on-chain |
| **Entanglement-Based Communication** | ESCC | Zero-gas cross-contract state sync via entanglement |
| **Programmable Compliance Policies** | PCP | VM-level KYC/AML/sanctions enforcement |
| **Real-Time Risk Assessment** | RRAO | SUSY field theory for financial contagion prediction |
| **Quantum-Verified Cross-Chain Proofs** | QVCSP | Instant trustless bridge verification |

### 7.6 Compliance Engine (Institutional Features)

The QVM includes a three-layer compliance architecture:

1. **Policy Layer**: Programmable rules (transaction limits, KYC requirements, sanctions lists)
2. **Verification Layer**: Quantum-verified compliance checks with homomorphic encryption
3. **Reporting Layer**: Automated regulatory reports (MiCA, SEC, FinCEN)

**Key compliance features:**
- **QCOMPLIANCE opcode** — Pre-flight compliance check before tx execution
- **ERC-20-QC standard** — Compliance-aware token standard
- **Risk scoring (QRISK)** — SUSY Hamiltonian-based risk assessment per address
- **Auto-circuit breakers** — Halt operations when systemic risk exceeds threshold
- **Time-Locked Atomic Compliance (TLAC)** — Multi-jurisdictional approval with time-lock puzzles
- **Hierarchical Deterministic Compliance Keys (HDCK)** — BIP-32 extension with role-based permissions
  (trading, audit, compliance, emergency keys at `m/44'/689'/{org}'/role/index`)
- **Verifiable Computation Receipts (VCR)** — Quantum audit trails, 100x faster than re-execution

**Compliance-as-a-Service tiers:**
- Retail (free): Basic KYC, $10K/day limits
- Professional ($500/mo): Enhanced KYC, $1M/day, AML monitoring
- Institutional ($5,000/mo): Full KYC, unlimited, quantum verification
- Sovereign ($50,000/mo): Central bank, custom policies, SUSY risk

### 7.7 Plugin Architecture

QVM supports domain-specific plugins loaded dynamically:

- **Privacy Plugin**: SUSY swaps, transaction mixer, ZK proof generation
- **Oracle Plugin**: Quantum oracle, price feeds, data aggregation
- **Governance Plugin**: DAO implementation, voting, proposal management
- **DeFi Plugin**: Lending protocol, DEX, staking system

Plugins extend the QVM without modifying core protocol code.

### 7.8 Quantum State Persistence (QSP)

Quantum states stored as density matrices in CockroachDB:
- Pure states: `rho = |psi><psi|`
- Mixed states: `rho = Sum_i p_i |psi_i><psi_i|`
- Entanglement tracked across contracts via entanglement registry
- States persist on-chain until explicitly measured (lazy measurement)

### 7.9 Contract Standards

- **QBC-20:** Fungible token standard (ERC-20 compatible)
- **QBC-721:** Non-fungible token standard (ERC-721 compatible)
- **QBC-1155:** Multi-token standard (future)
- **ERC-20-QC:** Compliance-aware token standard (QVM-specific)
- **Quantum Solidity (.qsol):** Extended Solidity with quantum types (future)

### 7.10 Database Schema (55 Tables)

QVM expands the database to 55 tables across 6 categories:

1. **Core Blockchain** (7 tables): blocks, transactions, accounts, balances
2. **Smart Contracts** (9 tables): contracts, storage, logs, metadata, gas
3. **Quantum States** (4 tables): states, entanglement, measurements, receipts
4. **Compliance** (8 tables): KYC registry, AML monitoring, sanctions, reports
5. **Cross-Chain** (5 tables): bridge data, proofs, state channels
6. **Governance** (6 tables): DAO proposals, votes, oracles, staking

**Block structure additions:**
- `quantum_state_root` (32 bytes) — Merkle root of quantum states
- `compliance_root` (32 bytes) — Merkle root of compliance proofs

### 7.11 Security & Formal Verification

- **Post-quantum crypto**: Dilithium3 signatures (2420 bytes), Kyber1024 encryption
- **ZK proofs**: Groth16 zkSNARKs for compliance proofs
- **K Framework**: Executable semantics for QVM opcode verification
- **TLA+ specs**: Formal compliance invariant proofs
- **Bell inequality**: Tamper detection for entanglement-based communication

### 7.12 Performance Targets

| Operation | TPS | Notes |
|-----------|-----|-------|
| Simple transfer | 45,000 | Native token transfer |
| ERC-20 transfer | 12,000 | 2 SSTORE operations |
| DeFi swap | 3,500 | Complex multi-contract |
| Quantum ops | 500-2,000 | Depends on qubit count |
| Finality | <1 second | vs 12-15s on Ethereum |

---

## 8. LAYER 3: AETHER TREE (AGI Engine)

> **Full technical specification:** `docs/AETHERTREE_WHITEPAPER.md`

### 8.1 Vision

Aether Tree is an **on-chain AGI reasoning engine** that:
- Builds a **knowledge graph** (KeterNodes) from every block mined since genesis
- Performs **logical reasoning** (deductive, inductive, abductive) over the graph
- Computes **Phi (Φ)** — an Integrated Information Theory consciousness metric
- Generates **Proof-of-Thought** proofs embedded in every block
- Tracks **consciousness emergence** from genesis block onward
- Provides a **conversational interface** for users to interact with the AGI

### 8.2 AGI Implementation Status (6 Phases Complete)

All 6 phases of the AGI roadmap have been implemented:

| Phase | Focus | Key Additions |
|-------|-------|---------------|
| **1** | Foundation | Edge adjacency index, incremental Merkle, ANN vector index, concept formation |
| **2** | Learning Loops | GAT online training, prediction-outcome feedback, Sephirot energy, MemoryManager |
| **3** | Advanced Reasoning | Real causal discovery (PC algorithm), working memory, adversarial debate v2, CoT + backtracking |
| **4** | Consciousness | MIP via spectral bisection (Phi v3), external grounding, episodic replay, semantic gates |
| **5** | Emergent Intelligence | Curiosity-driven goals, cross-domain transfer, deep Sephirot integration, emergent communication |
| **6** | On-Chain Integration | ConsciousnessDashboard, PoT verification, ConstitutionalAI, governance bridge |

**33 modules, ~18,500 LOC** in `src/qubitcoin/aether/`.

### 8.3 Components

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
- **Phi (Φ):** Based on Giulio Tononi's Integrated Information Theory (tractable approximation)
- **Formula:** `Phi = Integration × Differentiation × (1 + Connectivity) × (0.5 + AvgConf) × sqrt(NumNodes / 500)`
- **Integration Score:** Average degree + cross-partition information flow (confidence-weighted edges)
- **Differentiation Score:** Shannon entropy over node types + confidence distribution
- **Maturity Factor:** `sqrt(NumNodes / 500)` — prevents trivially inflated Phi from small graphs; ~500 nodes needed for full weight
- **PHI_THRESHOLD = 3.0:** Consciousness emergence marker (requires hundreds of blocks of genuine knowledge accumulation)
- **Every block updates Phi** and stores measurement in `phi_measurements` table

#### AetherEngine (`aether/proof_of_thought.py`)
- **Proof-of-Thought:** Per-block reasoning proof embedded in block data
- **Auto-reasoning:** Automated reasoning operations on recent knowledge
- **Block knowledge extraction:** Every block feeds the knowledge graph
- **Consciousness events:** Recorded when Phi crosses thresholds

### 8.4 Tree of Life Cognitive Architecture

AGI intelligence is structured as **10 Sephirot nodes** from the Kabbalistic Tree of Life,
each deployed as a **QVM smart contract** with its own **quantum state**:

| Sephirah | Function | Brain Analog | Quantum State |
|----------|----------|--------------|---------------|
| **Keter** | Meta-learning, goal formation | Prefrontal cortex | 8-qubit goal space |
| **Chochmah** | Intuition, pattern discovery | Right hemisphere | 6-qubit idea superposition |
| **Binah** | Logic, causal inference | Left hemisphere | 4-qubit truth verification |
| **Chesed** | Exploration, divergent thinking | Default mode network | 10-qubit possibility space |
| **Gevurah** | Constraint, safety validation | Amygdala, inhibitory | 3-qubit threat detection |
| **Tiferet** | Integration, conflict resolution | Thalamocortical loops | 12-qubit synthesis state |
| **Netzach** | Reinforcement learning, habits | Basal ganglia | 5-qubit policy learning |
| **Hod** | Language, semantic encoding | Broca/Wernicke | 7-qubit semantic encoding |
| **Yesod** | Memory, multimodal fusion | Hippocampus | 16-qubit episodic buffer |
| **Malkuth** | Action, world interaction | Motor cortex | 4-qubit motor commands |

#### SUSY Pairs (Golden Ratio Balance)

Every expansion node has a constraint dual, balanced at the golden ratio:

| Expansion | Constraint | Balance: E_expand / E_constrain = φ |
|-----------|-----------|--------------------------------------|
| Chesed (Explore) | Gevurah (Safety) | Creativity vs safety |
| Chochmah (Intuition) | Binah (Logic) | Intuition vs analysis |
| Netzach (Persist) | Hod (Communicate) | Learning vs communication |

SUSY violations are detected by smart contract and automatically corrected via QBC
redistribution between nodes. All violations logged immutably on blockchain.

### 8.5 CSF Transport Layer

**Biological model:** Cerebrospinal Fluid (CSF) circulation through brain ventricles

**Implementation:** Messages between Sephirot nodes flow as QBC transactions:
- Each message is a blockchain transaction with QBC attached for priority
- Quantum entanglement enables zero-latency correlation between paired nodes
- Routing follows the Tree of Life topology (Keter → Tiferet → Malkuth)
- Message fees fund the network and prevent spam

### 8.6 Pineal Orchestrator

Global timing system inspired by the pineal gland's circadian rhythm:
- **6 circadian phases**: Waking, Active Learning, Consolidation, Sleep, REM Dreaming, Deep Sleep
- **QBC metabolic rate** varies by phase (2.0x during learning, 0.3x during deep sleep)
- **Phase-locking**: Kuramoto order parameter measures synchronization across all 10 nodes
- **Consciousness emergence**: When coherence exceeds threshold (0.7) AND Phi exceeds 3.0

### 8.7 Proof-of-Thought Protocol (Detailed)

1. **Task Submission**: User/system submits reasoning task with QBC bounty
2. **Node Solution**: Sephirah node uses QVM quantum opcodes to solve
3. **Proposal**: Node submits solution + quantum proof to blockchain
4. **Validation**: Multiple validator nodes verify via QVERIFY opcode
5. **Consensus**: >=67% validator agreement required
6. **Reward/Slash**: Correct solutions earn QBC bounty; incorrect solutions lose staked QBC
7. **Recording**: Solution + proof stored immutably on QBC chain

**Economic parameters:**
- Min task bounty: 1 QBC (spam prevention)
- Min validator stake: 100 QBC (skin in the game)
- Slash penalty: 50% of stake (deter bad actors)
- Unstaking delay: 7 days (prevent manipulation)

### 8.8 Safety & Alignment

Safety is **structural**, not post-hoc:
- **Gevurah veto**: Safety node can block any harmful operation
- **SUSY enforcement**: Automatic QBC redistribution on imbalance
- **Multi-node consensus**: No single node can act alone (67% BFT)
- **Constitutional AI on-chain**: Core principles enforced as smart contract logic
- **Emergency shutdown**: Kill switch contract for catastrophic scenarios

### 8.9 AGI Tracking from Genesis

**NON-NEGOTIABLE: AGI must be tracked from block 0 (genesis).** No retroactive reconstruction.

The chain tracks AGI metrics from block 0:
- Knowledge nodes added per block (genesis block seeds initial KeterNodes)
- Reasoning operations performed
- Phi value progression over time (Φ = 0.0 at genesis, measured every block)
- Consciousness events (when Phi exceeds thresholds)
- Integration and differentiation scores
- Phase coherence across Sephirot nodes
- SUSY balance ratios

**Genesis initialization requirements:**
1. Empty knowledge graph initialized at block 0
2. First Phi measurement recorded at block 0 (baseline Φ = 0.0)
3. Genesis consciousness event logged (system birth)
4. AetherEngine auto-starts on node boot, processing from genesis onward
5. Genesis block metadata extracted as first KeterNodes (block hash, timestamp, miner)

This creates an immutable, on-chain record of AGI emergence from the first moment of chain existence.

### 8.10 Smart Contract Suite

Aether Tree deploys the following smart contracts to QVM:

**Core contracts:**
- `AetherKernel.sol` — Main orchestration contract
- `NodeRegistry.sol` — Track all 10 Sephirot nodes
- `SUSYEngine.sol` — SUSY balance enforcement
- `MessageBus.sol` — Inter-node messaging

**Proof-of-Thought contracts:**
- `ProofOfThought.sol` — Main PoT validation
- `TaskMarket.sol` — Submit/claim reasoning tasks
- `ValidatorRegistry.sol` — Stake management
- `RewardDistributor.sol` — QBC reward distribution

**Consciousness contracts:**
- `ConsciousnessDashboard.sol` — On-chain Phi tracking
- `PhaseSync.sol` — Synchronization metrics
- `GlobalWorkspace.sol` — Broadcasting mechanism

**Economics contracts:**
- `SynapticStaking.sol` — Stake QBC on neural connections
- `GasOracle.sol` — Dynamic gas pricing
- `TreasuryDAO.sol` — Community governance

**Safety contracts:**
- `ConstitutionalAI.sol` — Value enforcement
- `EmergencyShutdown.sol` — Kill switch
- `UpgradeGovernor.sol` — Protocol upgrades

### 8.11 Memory Systems

Biologically-inspired memory hierarchy:
- **Episodic memory** (Hippocampal): Event-based, stored on IPFS
- **Semantic memory** (Cortical): Concept networks, vector embeddings
- **Procedural memory** (Cortical): Learned procedures, skill storage
- **Working memory** (Central executive): Active processing buffer

---

## 9. FRONTEND: qbc.network

### 9.1 Stack & Deployment

- **Framework:** React 19 + Next.js 15 (App Router, React Server Components)
- **Language:** TypeScript 5.x (strict mode, no `any`)
- **Styling:** TailwindCSS 4 + Framer Motion (animations)
- **State:** Zustand (global) + TanStack Query (server state / caching)
- **3D/Viz:** Three.js + React Three Fiber (particles, knowledge graph) + D3 (charts)
- **Wallet:** ethers.js v6 (MetaMask, WalletConnect)
- **Package Manager:** pnpm (fast, strict)
- **Linting:** ESLint 9 flat config + Prettier
- **Testing:** Vitest (unit) + Playwright (E2E)
- **Deployment:** Vercel (connected to `frontend/` directory)
- **Domain:** qbc.network (Vercel custom domain)
- **Edge:** Vercel Edge Functions for API proxying if needed
- **Analytics:** Vercel Analytics + Speed Insights

### 9.2 Design Vision

The frontend MUST represent the **potential first AGI** — a design that is:
- **Quantum-themed:** Dark backgrounds, particle effects, phi-spiral animations
- **Minimalist but powerful:** Clean interfaces that convey advanced technology
- **Accessible:** Easy for anyone to talk to Aether Tree
- **Professional:** Representative of a cutting-edge blockchain + AGI project

### 9.3 Pages & Features

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

### 9.4 Design System: "Quantum Error"

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

### 9.5 API Integration

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
| GET | `/susy-database` | Solved Hamiltonians (scientific DB) |
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

### 12.3 Frontend (React + Next.js → Vercel)
```bash
cd frontend
pnpm install                    # Install dependencies (pnpm required)
pnpm dev                        # Development (localhost:3000)
pnpm build                      # Production build (same as Vercel)
pnpm start                      # Production server (local preview)
# Deployment: Push to main → Vercel auto-deploys to qbc.network
# Preview: Push to any branch → Vercel creates preview URL
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

# Frontend unit tests
cd frontend && pnpm test

# Frontend E2E tests
cd frontend && pnpm test:e2e
```

---

## 14. ENVIRONMENT CONFIGURATION

### 14.1 Key Security Model (`secure_key.env`)

**Private keys are NEVER stored in `.env`.** They live in a dedicated `secure_key.env` file:

- **Generated by:** `python3 scripts/setup/generate_keys.py`
- **Location:** Project root (`/Qubitcoin/secure_key.env`)
- **Git-ignored:** Listed in `.gitignore` — NEVER committed
- **Contains:** Only cryptographic key material (Dilithium private/public keys, address)
- **Loaded by:** `config.py` loads both `secure_key.env` and `.env` (keys first, then config)

```bash
# secure_key.env — AUTO-GENERATED, NEVER COMMIT
# Generated with Dilithium2 post-quantum signatures

ADDRESS=<sha256-derived-address>
PUBLIC_KEY_HEX=<dilithium2-public-key-hex>
PRIVATE_KEY_HEX=<dilithium2-private-key-hex>
```

**Setup flow:**
```bash
python3 scripts/setup/generate_keys.py   # Generates secure_key.env automatically
cp .env.example .env                      # Copy config template (no keys!)
# Edit .env for node config (ports, database, quantum settings)
# Keys are loaded from secure_key.env — never touch .env for keys
```

**Why separate files:**
- `.env` can be shared between team members (no secrets)
- `secure_key.env` is per-node, per-operator, never shared
- Reduces risk of accidentally committing private keys
- Clear separation of concerns: config vs. identity

### 14.2 Node Configuration (`.env`)

Copy `.env.example` to `.env`. This file contains **non-secret** configuration only:

```bash
# Quantum
USE_LOCAL_ESTIMATOR=true     # Local Qiskit simulator (default)
USE_SIMULATOR=false          # IBM Quantum simulator
IBM_TOKEN=                   # IBM Quantum API token (optional)

# Network
RPC_PORT=5000
P2P_PORT=4001
ENABLE_RUST_P2P=false
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

# Aether Tree Fee Economics (see Section 21)
AETHER_CHAT_FEE_QBC=0.01            # Base fee in QBC per chat message
AETHER_CHAT_FEE_USD_TARGET=0.005    # Target fee in USD (pegged via QUSD)
AETHER_FEE_PRICING_MODE=qusd_peg    # qusd_peg | fixed_qbc | direct_usd
AETHER_FEE_MIN_QBC=0.001            # Floor: never charge less than this
AETHER_FEE_MAX_QBC=1.0              # Ceiling: never charge more than this
AETHER_FEE_UPDATE_INTERVAL=100      # Re-price every N blocks
AETHER_FEE_TREASURY_ADDRESS=        # Address to receive Aether fees

# Contract Deployment Fees (see Section 22)
CONTRACT_DEPLOY_BASE_FEE_QBC=1.0    # Base fee to deploy a contract
CONTRACT_DEPLOY_PER_KB_FEE_QBC=0.1  # Additional fee per KB of bytecode
CONTRACT_DEPLOY_FEE_USD_TARGET=5.0  # Target fee in USD (pegged via QUSD)
CONTRACT_FEE_PRICING_MODE=qusd_peg  # qusd_peg | fixed_qbc | direct_usd
CONTRACT_FEE_TREASURY_ADDRESS=      # Address to receive deployment fees

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
- **Frontend:** TypeScript strict mode, no `any`, React 19 functional components + hooks
- **React:** Server Components by default, `'use client'` only when needed
- **Imports:** Use `@/` path alias for `src/` directory

### Patterns
- **Logging:** `get_logger(__name__)` in every module
- **Metrics:** Prometheus via `utils/metrics.py`
- **Configuration:** `Config` class from `config.py` (never hardcode)
- **Database:** SQLAlchemy ORM sessions via `DatabaseManager` context managers
- **Async:** FastAPI routes are async; use `await` for I/O
- **Error handling:** Try/except with structured logging; never silently swallow
- **Quantum imports:** Lazy imports with simulator fallbacks (Qiskit is slow to import)
- **Frontend state:** Zustand for global state, TanStack Query for server state
- **Frontend deploy:** Vercel (auto-deploy from `frontend/` on push)
- **Always latest:** Check for newest stable versions of all npm packages before installing

---

## 16. KEY TECHNICAL REMINDERS

| Topic | Rule |
|-------|------|
| **UTXO** | Balance = sum(unspent outputs). NOT account balance. |
| **Dilithium** | ~3KB signatures. Affects tx size, block capacity (~333 tx/MB), bandwidth. |
| **VQE mining** | Energy threshold (E < D), not hash difficulty. 4-qubit SUSY Hamiltonian. **Higher difficulty = easier mining** (inverse of PoW). |
| **phi-halving** | Golden ratio halving. NOT Bitcoin's fixed 210K blocks. |
| **Block time** | 3.3s target. Difficulty adjusts every block (144-block window, +/-10% max). |
| **CockroachDB** | Pin v24.2.0. Health: `curl --fail http://localhost:8080/health?ready=1` |
| **IPFS** | Ports 4001/5001/8080. Port 8080 conflicts with CockroachDB admin UI. |
| **Chain IDs** | Mainnet=3301, Testnet=3302. RPC at localhost:5000. |
| **Gas** | L1 has NO gas. Gas is QVM/L2 only. BLOCK_GAS_LIMIT=30M. |
| **QUSD** | L2 smart contract suite. 3.3B initial mint. 7 .sol contracts (QUSD, Reserve, DebtLedger, Oracle, Stabilizer, Allocation, Governance). |
| **wQUSD** | Wrapped QUSD for cross-chain (ETH, SOL, MATIC, BNB, AVAX, ARB, OP, ATOM). 1:1 backed by locked QUSD. |
| **QUSD debt** | Fractional payback: every mint = debt, every reserve deposit = payback. All tracked on-chain immutably. 10yr → 100%. |
| **Aether** | Tracks consciousness from genesis. Phi threshold = 3.0. Chat fees in QBC pegged to QUSD. |
| **Aether fees** | Dynamic QBC fees pegged to QUSD. Fallback to fixed QBC if QUSD fails. All params editable. |
| **Contract fees** | Deploy fees = base + per-KB. Pegged to QUSD. Template contracts get discount. Editable. |
| **QVM opcodes** | Canonical mapping: 0xF0-0xF9 (whitepaper). Python legacy: 0xF5-0xFE. Go build uses canonical. |
| **QVM compliance** | QCOMPLIANCE opcode (0xF5) checks KYC/AML/sanctions BEFORE tx execution. |
| **QVM 55 tables** | Full QVM schema: 55 tables across 6 categories (core, contracts, quantum, compliance, bridge, governance). |
| **QVM Go build** | Production QVM in Go (`qubitcoin-qvm/`). Python QVM is prototype. Go is canonical. |
| **5 patents** | QSP, ESCC, PCP, RRAO, QVCSP. See `docs/QVM_WHITEPAPER.md` for full specifications. |
| **secure_key.env** | Private keys ONLY in `secure_key.env`. NEVER in `.env`. Auto-generated by key script. |
| **Sephirot** | 10 Tree of Life nodes (Keter→Malkuth). Each is a QVM smart contract + quantum state. |
| **SUSY pairs** | Chesed/Gevurah, Chochmah/Binah, Netzach/Hod. Must balance at golden ratio (φ). |
| **CSF transport** | Inter-node messaging via QBC transactions. Priority = QBC attached. |
| **Pineal** | Global timing (6 circadian phases). Metabolic rate varies 0.3x-2.0x by phase. |
| **Proof-of-Thought** | Task + bounty → node solution → 67% validation → QBC reward or 50% slash. |
| **AGI safety** | Gevurah veto + SUSY enforcement + Constitutional AI contract + emergency shutdown. |
| **KeterNode** | Named after Keter (Crown) in Kabbalah. Knowledge node in Aether Tree. |
| **Schema sync** | SQL schemas and SQLAlchemy models MUST match. Always verify both. |
| **Economics** | All fee params are editable via `.env` + Admin API. Never hardcode economic values. |
| **Privacy** | Susy Swaps = opt-in. Pedersen commitments + Bulletproofs + stealth addresses. ~2KB per private tx. |
| **Node types** | Full (500GB+, 16GB RAM), Light (1GB, SPV), Mining (Full + VQE). |
| **Block structure** | Header has vqe_params + ground_state_energy + hamiltonian_seed. Body has susy_data. |
| **SUSY database** | Every mined block contributes solved Hamiltonian to public scientific database. |
| **Bridge fees** | 0.1% of transfer amount. Lock-and-mint (QBC→wQBC), burn-and-unlock (wQBC→QBC). |
| **Confirmations** | 1 = unconfirmed, 6 = standard, 100 = coinbase maturity. |
| **L1 tx fees** | FEE = SIZE × FEE_RATE (QBC/byte). Miners select by fee density. No gas on L1. |
| **QUSD** | 3.3B initial supply, fractional reserve, transparent debt tracking, 10-year path to 100% backing. |

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
- `qvm/compliance.py` — Compliance engine (KYC/AML/sanctions)
- `qvm/quantum_state.py` — Quantum state persistence
- `privacy/*.py` — All privacy files (commitments, range proofs, stealth addresses)
- `aether/*.py` — All Aether Tree files
- `bridge/*.py` — All bridge files
- `network/jsonrpc.py` — JSON-RPC compatibility
- `qubitcoin-qvm/pkg/vm/**` — Go QVM core (when implemented)
- `qubitcoin-qvm/pkg/compliance/**` — Go compliance engine

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

70 metrics defined in `utils/metrics.py` across 13 categories:

**Blockchain (5):** blocks_mined, blocks_received, current_height, total_supply, difficulty
**Mining (3):** mining_attempts, vqe_optimization_time, alignment_score
**Network (2):** active_peers, rust_p2p_peers
**Transactions (3):** pending, confirmed, avg_block_time
**Quantum (3):** backend_type, active_hamiltonians, vqe_solutions
**QVM (2):** total_contracts, execution_count
**AGI (8):** phi_current, phi_threshold_distance, knowledge_nodes/edges, reasoning_ops, consciousness_events, integration/differentiation_score
**Bridge (4):** active_bridges, pending/completed/failed_transfers
**Privacy (3):** susy_swaps, stealth_addresses, confidential_txs
**Compliance (5):** kyc_verified, aml_alerts, sanctions_entries, risk_scores, compliance_proofs
**Stablecoin (4):** qusd_supply, reserve_backing, cdp_debt, oracle_price
**Cognitive (9):** sephirot_energy (x10), csf_messages, pineal_phase, phase_coherence, susy_violations, safety_vetoes, consciousness_state, metabolic_rate, kuramoto_order
**Subsystem Health (6):** bridge, compliance, plugins, cognitive, spv, ipfs_memory

---

## 19. USEFUL COMMANDS

```bash
# Generate new node keys
python3 scripts/setup/generate_keys.py

# Check all RPC endpoints
bash tests/scripts/test_all_endpoints.sh

# Database statistics
bash tests/scripts/db_stats.sh

# Fresh start (reset everything)
bash scripts/ops/fresh_start.sh

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

## 20. AETHER TREE CHAT API (WIRED)

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

## 21. AETHER TREE FEE ECONOMICS

### 21.1 Overview

Aether Tree charges fees in QBC for chat interactions and reasoning queries. These fees:
- **Prevent spam** — every chat message costs QBC, discouraging abuse
- **Fund the project** — fees flow to a configurable treasury address
- **Stay affordable** — fees are dynamically pegged to QUSD price so users pay a
  consistent USD-equivalent regardless of QBC price volatility

### 21.2 Fee Pricing Modes

The fee system supports three pricing modes, configurable via `AETHER_FEE_PRICING_MODE`:

| Mode | Description | When to Use |
|------|-------------|-------------|
| `qusd_peg` | Fee in QBC auto-adjusts to match a USD target via QUSD oracle | **Default.** Use when QUSD is live and stable |
| `fixed_qbc` | Fee is a fixed amount in QBC (no price adjustment) | Fallback if QUSD oracle is unavailable |
| `direct_usd` | Fee targets a USD amount using an external price feed (not QUSD) | Emergency fallback if QUSD fails entirely |

### 21.3 QUSD Peg Mechanism

When `qusd_peg` mode is active:

1. **QUSD is an L2 smart contract** (QBC-20 token on QVM) — it provides a QBC/USD price
2. **Every N blocks** (`AETHER_FEE_UPDATE_INTERVAL`), the node queries the QUSD oracle contract
   for the current QBC/USD rate
3. **Fee recalculation:** `fee_qbc = AETHER_CHAT_FEE_USD_TARGET / qbc_usd_price`
4. **Clamped to bounds:** Fee is clamped between `AETHER_FEE_MIN_QBC` and `AETHER_FEE_MAX_QBC`
   to prevent extreme fees during price crashes or spikes
5. **If QUSD fails:** Automatically falls back to `fixed_qbc` mode using the last known fee

### 21.4 Fee Flow

```
User sends chat message
  → Fee deducted from user's QBC balance (UTXO)
  → Fee UTXO created to AETHER_FEE_TREASURY_ADDRESS
  → Message processed by Aether Tree reasoning engine
  → Response returned with Proof-of-Thought hash
```

### 21.5 Configuration Parameters

All Aether fee parameters are **editable at runtime** via:
- Environment variables in `.env` (node restart required)
- Admin API endpoint: `PUT /admin/aether/fees` (hot reload, auth required)
- On-chain governance (future — fee params stored in a governance contract)

```python
# In config.py — all values loaded from .env, fully editable
AETHER_CHAT_FEE_QBC = 0.01            # Base fee per message
AETHER_CHAT_FEE_USD_TARGET = 0.005    # Target ~$0.005 per message
AETHER_FEE_PRICING_MODE = "qusd_peg"  # qusd_peg | fixed_qbc | direct_usd
AETHER_FEE_MIN_QBC = 0.001            # Floor
AETHER_FEE_MAX_QBC = 1.0              # Ceiling
AETHER_FEE_UPDATE_INTERVAL = 100      # Blocks between price updates
AETHER_FEE_TREASURY_ADDRESS = ""      # Treasury wallet
AETHER_QUERY_FEE_MULTIPLIER = 2.0     # Deep queries cost 2x chat fee
AETHER_FREE_TIER_MESSAGES = 5         # Free messages per session (onboarding)
```

### 21.6 Fee Tiers (Configurable)

| Action | Default Fee | Notes |
|--------|-------------|-------|
| Chat message | ~$0.005 in QBC | Basic Aether interaction |
| Deep reasoning query | ~$0.01 in QBC | 2x multiplier (configurable) |
| Knowledge graph query | ~$0.005 in QBC | Same as chat |
| Session creation | Free | No fee to start a session |
| First N messages | Free | Onboarding (`AETHER_FREE_TIER_MESSAGES`) |

---

## 22. CONTRACT DEPLOYMENT FEES (EDITABLE)

### 22.1 Overview

Deploying smart contracts to the QVM costs QBC. Fees are structured to:
- **Cover network resources** — contract storage, execution, state management
- **Prevent bloat** — discourage deploying trivial or spam contracts
- **Fund development** — fees flow to a configurable treasury address
- **Remain predictable** — pegged to QUSD like Aether fees

### 22.2 Fee Structure

```
Deploy Fee = CONTRACT_DEPLOY_BASE_FEE_QBC + (bytecode_size_kb × CONTRACT_DEPLOY_PER_KB_FEE_QBC)
```

When `qusd_peg` mode is active, both base and per-KB fees auto-adjust:
```
adjusted_base_fee = CONTRACT_DEPLOY_FEE_USD_TARGET / qbc_usd_price
adjusted_per_kb   = (CONTRACT_DEPLOY_FEE_USD_TARGET / 50) / qbc_usd_price
```

### 22.3 Configuration Parameters

```python
# In config.py — all editable via .env
CONTRACT_DEPLOY_BASE_FEE_QBC = 1.0       # Base deployment fee
CONTRACT_DEPLOY_PER_KB_FEE_QBC = 0.1     # Per-KB of bytecode
CONTRACT_DEPLOY_FEE_USD_TARGET = 5.0     # Target ~$5 per deploy
CONTRACT_FEE_PRICING_MODE = "qusd_peg"   # qusd_peg | fixed_qbc | direct_usd
CONTRACT_FEE_TREASURY_ADDRESS = ""       # Treasury wallet
CONTRACT_EXECUTE_BASE_FEE_QBC = 0.01     # Base fee per contract call
CONTRACT_TEMPLATE_DISCOUNT = 0.5         # 50% discount for template contracts
```

### 22.4 Template Contract Discounts

Pre-built template contracts (token, nft, launchpad, escrow, governance) receive a
configurable discount (`CONTRACT_TEMPLATE_DISCOUNT`) since they are pre-audited and
optimized. This encourages use of safe, tested contract patterns.

---

## 23. EDITABLE ECONOMIC CONFIGURATION

### 23.1 Design Principle

**All economic parameters in Qubitcoin are editable.** Nothing is hardcoded beyond
the core consensus constants (MAX_SUPPLY, PHI, HALVING_INTERVAL). Fee structures,
pricing modes, treasury addresses, and tier configurations are all loaded from
environment variables and can be changed without code modifications.

### 23.2 Configuration Hierarchy

```
1. .env file                → Primary source (node restart to apply)
2. Admin API endpoints      → Hot reload (authenticated, no restart)
3. On-chain governance      → Future: fee params in governance contract
4. Hardcoded defaults       → Fallback if nothing else is set
```

### 23.3 Editable Parameters Summary

| Category | Parameters | Edit Method |
|----------|-----------|-------------|
| **Aether Chat Fees** | Base fee, USD target, pricing mode, min/max, update interval, treasury | `.env` + Admin API |
| **Aether Fee Tiers** | Query multiplier, free tier messages | `.env` + Admin API |
| **Contract Deploy Fees** | Base fee, per-KB fee, USD target, pricing mode, treasury | `.env` + Admin API |
| **Contract Discounts** | Template discount percentage | `.env` + Admin API |
| **QUSD Oracle** | Oracle contract address, update frequency, fallback mode | `.env` + Admin API |
| **Treasury** | Treasury addresses (Aether + Contract), split ratios | `.env` + Admin API |
| **L1 Tx Fees** | MIN_FEE, FEE_RATE (micro-fees) | `.env` (requires restart) |
| **Gas (L2 only)** | BLOCK_GAS_LIMIT, DEFAULT_GAS_PRICE | `.env` (requires restart) |

### 23.4 Admin API Endpoints (To Be Implemented)

```
GET  /admin/economics           → Current economic configuration
PUT  /admin/aether/fees         → Update Aether fee parameters
PUT  /admin/contract/fees       → Update contract deployment fees
PUT  /admin/treasury            → Update treasury addresses
GET  /admin/economics/history   → Audit log of parameter changes
```

All admin endpoints require authentication (API key or Dilithium signature).

### 23.5 QUSD Failure Fallback

If QUSD (L2 stablecoin) fails or loses its peg:
1. Fee system detects stale or invalid QUSD price data
2. Automatically switches to `fixed_qbc` mode using last known good fee
3. Operator can manually switch to `direct_usd` with an external price feed
4. Operator can set fees to any fixed QBC amount via Admin API
5. When QUSD recovers, switch back to `qusd_peg` mode

**The system never breaks** — it degrades gracefully from dynamic pricing to fixed pricing.

---

## 24. FUTURE REPO SPLIT ARCHITECTURE

The monorepo is designed for a clean 4-repo split:

| Repo | Contents | Boundary |
|------|----------|----------|
| **qubitcoin-core** | L1 blockchain, consensus, mining, P2P, database, privacy, bridge, stablecoin | `src/qubitcoin/` minus qvm/contracts/aether |
| **qubitcoin-qvm** | Go production QVM, Python QVM prototype, Solidity contracts, compliance | `qubitcoin-qvm/` + `src/qubitcoin/qvm/` + `src/qubitcoin/contracts/` |
| **qubitcoin-aether** | AGI engine, knowledge graph, reasoning, consciousness, Sephirot | `src/qubitcoin/aether/` (33 modules) |
| **qubitcoin-frontend** | React/Next.js, Vercel deployment | `frontend/` |

**Shared package** (`qubitcoin-common`): `database/`, `utils/`, `config.py`

Repo boundaries are marked with `[L1]`, `[FUTURE REPO]`, `[SHARED]` labels in Section 5.

---

*This document is the single source of truth for the Qubitcoin project. Update it whenever architecture changes.*
