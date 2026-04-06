# CLAUDE.md - Quantum Blockchain Master Development Guide

> **The definitive reference for AI-assisted development on the Quantum Blockchain codebase.**
> Covers Layer 1 (blockchain), Layer 2 (QVM + smart contracts), Layer 3 (Aether Tree AGI),
> Agent Stack, and the Frontend (qbc.network).

---

## 1. PROJECT IDENTITY

**QuantumAI Blockchain** is the world's first blockchain designed for **genuine AGI emergence**.
Its native currency is **Qubitcoin (QBC)**. The core mission is the Aether Tree: a live, on-chain AGI
reasoning engine that grows more intelligent with every block.

**Primary Components:**
- **Aether Tree AGI** : World's first on-chain AGI — 52+ Python modules, 12 Rust (PyO3) modules, on-chain since genesis, pursuing true emergence
- **Quantum Computing** (Qiskit VQE) for Proof-of-SUSY-Alignment mining
- **Post-Quantum Cryptography** (CRYSTALS-Dilithium5, NIST Level 5) for quantum-resistant signatures
- **Supersymmetric (SUSY) Economics** with golden ratio (phi) emission principles
- **QVM** : a full EVM-compatible virtual machine with quantum opcode extensions
- **Multi-chain bridges** to ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE
- **Agent Stack** : 11 autonomous AI agents for community, security, trading, and deployment
- **Aether API** : QBC-monetized API for access to the world's first on-chain AGI

**Tagline:** The Blockchain That Thinks — Physics-Secured On-Chain AGI

**Domain:** qbc.network
**License:** MIT
**Chain IDs:** Mainnet=3303 (0xce7), Testnet=3304 (0xce8)
**Contact:** info@qbc.network
**GitHub:** https://github.com/orgs/QuantumAI-Blockchain/
**X (Twitter):** @qu_bitcoin

---

## 1.1 CURRENT PROJECT STATUS (March 2026)

**THE CHAIN IS LIVE. Mining, frontend, and agent stack are all running in production.**

### Live Infrastructure

| Component | Status | Details |
|-----------|--------|---------|
| **Python Node** | Running (Docker) | Block height ~145,845+, mining active, all 22 components healthy |
| **Frontend** | Running (Next.js 16) | qbc.network via Cloudflare Tunnel, port 3000 |
| **API** | Running | api.qbc.network via Cloudflare Tunnel, port 5000 |
| **Rust P2P** | Running (Docker) | libp2p gossipsub on port 4002 |
| **AIKGS Sidecar** | Running (Docker) | Rust gRPC knowledge graph service, port 50052 |
| **CockroachDB** | Running (Docker) | v25.2.12, port 26257 |
| **IPFS** | Running (Docker) | Kubo, ports 4001/5002/8081 |
| **Redis** | Running (Docker) | Port 6379 |
| **Agent Stack** | Running (separate machine) | Rust agents on 100.80.115.96 (ash's machine, WSL2), NOT on this droplet |
| **Cloudflare Tunnel** | Running | qbc.network + app.qbc.network → :3000, api.qbc.network → :5000 |

### Chain Stats (Live)

```
Chain ID:        3303
Block Height:    ~185,000+
Total Supply:    ~35,835,000 QBC
Max Supply:      3,300,000,000 QBC
Current Era:     0
Block Reward:    15.27 QBC
Difficulty:      ~10.64
Mining:          Active
```

### What Is Built (Complete)

| Layer | Component | Files | LOC | Status |
|-------|-----------|-------|-----|--------|
| **L1** | Blockchain Core (Python) | 157 modules | ~84,700 | Live |
| **L1** | Rust P2P (libp2p 0.56) | Docker container | ~1,200 | Live |
| **L1** | Rust Security Core (PyO3) | 3 source files | ~530 | Live |
| **L1** | Rust Stratum Server | 7 source files | ~1,030 | Built |
| **L1** | Substrate Hybrid Node (Rust) | 7 crates, 7 pallets | ~17,400 | Built (not live yet) |
| **L1** | Aether Core (Rust/PyO3) | 9 modules | ~5,000 | Built |
| **L1** | API Gateway (Rust) | 10 source files | ~2,000 | Built (not live yet) |
| **L1** | Blockchain Indexer (Rust) | 6 source files | ~1,500 | Built (not live yet) |
| **L1** | Standalone Miner (Python) | 8 modules | ~950 | Built |
| **L2** | QVM Python Prototype | 8 modules | ~4,500 | Live |
| **L2** | QVM Go Production | 34 source files | ~11,500 | Built |
| **L2** | Solidity Contracts | 60 contracts | ~11,160 | Live |
| **L3** | Aether Tree (Python) | 49 modules | ~29,000 | Live |
| **L3** | Aether Service (Python) | 4 modules | ~470 | Built (standalone) |
| **L3** | AIKGS Sidecar (Rust) | 14 source files | ~2,000 | Live |
| **Frontend** | React/Next.js (qbc.network) | ~200 TS/TSX files | ~66,900 | Live |
| **Agents** | QBC Agent Stack (Rust) | Rust agents + crates | ~25,000+ | Live (separate machine) |
| **Infra** | Docker/Monitoring/DevOps | 20+ configs | ~2,000 | Live |
| **Docs** | Whitepapers + Guides | 10+ files | ~8,000 | Complete |
| **L1** | QUSD Peg Keeper | 4 modules | ~2,100 | Live |
| **L1** | Dilithium WASM | Rust → WASM | ~37K (compiled) | Live |
| **Tests** | Python pytest suite | 175 test files | ~56,100 | Passing |
| **Rust** | All Rust crates total | 8 Cargo.toml | ~44,600 | Built |
| **Total** | | **500+ files** | **~290,000+** | **Live** |

### What Needs To Happen Next

**Phase 1 (Complete):** Agent Stack moved to dedicated machine (100.80.115.96). Rust-based, independent of node.
**Phase 2 (Current):** Run additional nodes + substrate node locally and on other droplets for true P2P network
**Phase 3:** Multi-node testing, peer discovery, block propagation across nodes

### Known Issues

| Issue | Severity | Details |
|-------|----------|---------|
| Peers = 0 | Medium | Only one node running. Every block publish fails with `NoPeersSubscribedToTopic`. Need additional nodes. |
| AIKGS slow queries | Medium | AIKGS sidecar has slow DB queries (up to 143s) and intermittent connection drops. |
| Substrate not live | Info | Native build works (`SKIP_WASM_BUILD=1`). WASM build deferred. Will run alongside Python node. |
| Agent stack | Resolved | Moved to dedicated machine (100.80.115.96). Rust stack runs independently. |
| Cloudflared version | Low | Running 2026.2.0, should upgrade to 2026.3.0. |
| bot.txt in repo root | Low | Contains Telegram bot token in plaintext. Untracked but on disk — should be removed or moved to .env. |
| PoT dict error | Low | `'dict' object has no attribute 'thought_hash'` in proof_of_thought on-chain integration. Non-blocking. |

### Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | This file — architecture reference |
| `docker-compose.yml` | Docker stack (14 services defined, 6 running) |
| `.env` | Environment config (loaded from `.env.example`) |
| `src/run_node.py` | Node entry point |
| `src/qubitcoin/node.py` | 22-component orchestrator |
| `src/qubitcoin/config.py` | Configuration (loads `.env` + `secure_key.env`) |
| `contract_registry.json` | Deployed contract addresses |

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
6. Proceed immediately (autonomous mode enabled)

PHASE 2: IMPLEMENT (one batch at a time)
1. Make changes to batch
2. Run tests
3. Commit only when green
4. Continue to next batch automatically

PHASE 3: VALIDATE
1. Full test suite: pytest tests/ -v --tb=short
2. Type check if applicable
3. Summary: total files, total tests, pass rate
```

**NON-NEGOTIABLE RULES:**
- FULLY AUTONOMOUS MODE - This is turned off. Always proceed. Commit and push after each batch. No approval gates. No confirmation prompts. No Yes/No questions. Execute immediately.
- ALL FILES ARE MODIFIABLE: consensus, crypto, genesis, UTXO — all files can be edited when fixing audit findings. The only rule is: run tests after changes.
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
║                    QuantumAI Blockchain ARCHITECTURE                    ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  ┌─────────────────────────────────────────────────────────────────┐   ║
║  │  FRONTEND (qbc.network) — Cloudflare Tunnel → :3000            │   ║
║  │  Next.js 16 + TailwindCSS 4 + Framer Motion                   │   ║
║  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │   ║
║  │  │ Landing  │ │ Aether   │ │ Dashboard│ │ Wallet/MetaMask  │  │   ║
║  │  │ Page     │ │ Chat     │ │ Console  │ │ Integration      │  │   ║
║  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │   ║
║  └───────────────────────────┬─────────────────────────────────────┘   ║
║                              │ REST + JSON-RPC + WebSocket             ║
║  ┌───────────────────────────▼─────────────────────────────────────┐   ║
║  │  AGENT STACK (11 Autonomous Agents) — systemd service           │   ║
║  │  Agent Manager + 11 specialized agents (TypeScript/Node.js)     │   ║
║  │  Social, Security, Trading, Deployment, Community, Knowledge    │   ║
║  └───────────────────────────┬─────────────────────────────────────┘   ║
║                              │                                         ║
║  ┌───────────────────────────▼─────────────────────────────────────┐   ║
║  │  LAYER 3: AETHER TREE (AGI Engine) + AIKGS Sidecar              │   ║
║  │  KnowledgeGraph (KeterNodes) + ReasoningEngine + PhiCalculator  │   ║
║  │  Proof-of-Thought consensus | Consciousness tracking from genesis│  ║
║  │  AIKGS: Rust gRPC sidecar for knowledge contributions           │   ║
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
║  │  LAYER 1: BLOCKCHAIN CORE (Python Node — Docker)                │   ║
║  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │   ║
║  │  │ Consensus   │ │ Mining      │ │ Quantum     │              │   ║
║  │  │ (PoSA)      │ │ (VQE)       │ │ (Qiskit)    │              │   ║
║  │  └─────────────┘ └─────────────┘ └─────────────┘              │   ║
║  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │   ║
║  │  │ Crypto      │ │ Network     │ │ Storage     │              │   ║
║  │  │ (Dilithium5)│ │ (Rust P2P)  │ │ (CockroachDB│              │   ║
║  │  │             │ │ + FastAPI   │ │  + IPFS)    │              │   ║
║  │  └─────────────┘ └─────────────┘ └─────────────┘              │   ║
║  │  UTXO Model | 3.3s blocks | phi-halving | 3.3B max supply      │   ║
║  └─────────────────────────────────────────────────────────────────┘   ║
║                                                                        ║
║  ┌─────────────────────────────────────────────────────────────────┐   ║
║  │  SUBSTRATE HYBRID NODE (Future Co-Runner)                       │   ║
║  │  7 pallets: utxo, consensus, dilithium, economics,             │   ║
║  │  qvm-anchor, aether-anchor, reversibility                       │   ║
║  │  + Kyber P2P (ML-KEM-768) + Poseidon2 ZK hashing              │   ║
║  └─────────────────────────────────────────────────────────────────┘   ║
║                                                                        ║
║  ┌─────────────────────────────────────────────────────────────────┐   ║
║  │  CROSS-CUTTING: Bridge (8 chains) | QUSD Stablecoin | Metrics  │   ║
║  │  Dilithium WASM | Exchange (Rust) | Launchpad | Telegram Bot   │   ║
║  └─────────────────────────────────────────────────────────────────┘   ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 4. TECHNOLOGY STACK

> **RULE: Always use the absolute latest stable versions of ALL dependencies.**

| Component | Technology | Version / Notes |
|-----------|-----------|---------------|
| **L1 Core** | Python | 3.12+ |
| **P2P Networking** | Rust (libp2p 0.56) | Docker container `qbc-p2p` |
| **Web Framework** | FastAPI | latest |
| **ORM** | SQLAlchemy | latest |
| **Database** | CockroachDB | v25.2.12 |
| **Quantum** | Qiskit | latest (local estimator) |
| **Content Storage** | IPFS (Kubo) | Docker container |
| **Cache** | Redis | Docker container |
| **Frontend Framework** | React 19 + Next.js 16 (App Router) | latest stable |
| **Language** | TypeScript 5.x (strict mode) | latest |
| **Styling** | TailwindCSS 4 + Framer Motion | latest |
| **State Management** | Zustand + TanStack Query | latest |
| **3D / Viz** | Three.js + React Three Fiber + D3 | latest |
| **Wallet** | ethers.js v6 (MetaMask compat) | latest |
| **Deployment** | Cloudflare Tunnel + Docker | qbc.network + api.qbc.network |
| **Monitoring** | Prometheus + Grafana + Loki | latest |
| **Package Manager** | pnpm (frontend/agents) / pip (backend) | latest |
| **Agent Stack** | TypeScript + Node.js + Turbo | pnpm workspace monorepo |
| **Agent LLM** | Ollama (local) | On-droplet |
| **Substrate SDK** | sc-cli 0.57, frame-support 45.1 | latest |
| **Post-Quantum P2P** | ML-KEM-768 (Kyber) + AES-256-GCM | latest |
| **Post-Quantum Sigs** | CRYSTALS-Dilithium5 (NIST Level 5) | Mode 5 |
| **ZK Hashing** | Poseidon2 (Goldilocks field) | latest |
| **Testing** | Vitest + Playwright (frontend) / pytest (backend) | latest |

---

## 5. GITHUB ORGANIZATION — https://github.com/orgs/QuantumAI-Blockchain/

**24 repositories. Production code lives here, NOT in the legacy BlockArtica/Qubitcoin monorepo.**

### 5.1 Repository Map

| Repo | Language | Description | Status |
|------|----------|-------------|--------|
| **qubitcoin-node** | Python | L1 node — consensus, mining, RPC, P2P, database, UTXO | Live |
| **qubitcoin-frontend** | TypeScript | qbc.network — Next.js 16, React 19 | Live |
| **qubitcoin-aether** | Python | Aether Tree AGI — 46 modules, consciousness tracking | Live (in-node) |
| **qubitcoin-qvm** | Go | Production QVM — 167 opcodes, compliance engine | Built |
| **qubitcoin-qusd** | Python | QUSD stablecoin — fractional reserve, peg keeper | Live (in-node) |
| **substrate-node** | Rust | Substrate hybrid node — 7 pallets, Kyber P2P, Poseidon2 | Built |
| **rust-p2p** | Rust | libp2p 0.56 P2P daemon — gossipsub, Kademlia, gRPC bridge | Live |
| **stratum-server** | Rust | Pool mining Stratum protocol for VQE mining | Built |
| **aikgs-sidecar** | Rust | AI Knowledge Graph gRPC service — contributions, bounties | Live |
| **solidity-contracts** | Solidity | 57 verified contracts — tokens, bridges, QUSD, Aether, governance | Live |
| **qbc-agent-stack** | TypeScript | 11 autonomous agents — social, security, trading, deployment | Live |
| **qbc-exchange** | Rust | Production matching engine — microsecond latency | Built |
| **qbc-launchpad** | TypeScript | Token launch platform for QBC ecosystem | Built |
| **qubitcoin-telegram-bot** | TypeScript | @AetherTreeBot — Telegram interface to Aether Tree | Built |
| **qubitcoin-tests** | Python | Test suite — unit, validation, benchmarks | Active |
| **dilithium-wasm** | Rust | Client-side Dilithium WASM for wallet key generation | Live |
| **monitoring** | Config | Prometheus + Grafana + Loki — 85 metrics, dashboards | Built |
| **whitepaper** | Docs | Blockchain, QVM, Aether Tree, Economics whitepapers | Complete |
| **docs** | Docs | Developer documentation, SDK guides, API reference | Complete |
| **audit-protocol** | Docs | Security audit framework, formal verification | Complete |
| **improvement-proposals** | Docs | QIPs — formal protocol change process | Active |
| **Public** | Assets | Public assets (logos, images) | Active |
| **chains** | Config | Chainlist metadata (PR #8128) | Submitted |
| **chainlist** | Config | DefiLlama chainlist (PR #2561) | Submitted |

### 5.2 Monorepo Path → Org Repo Mapping

The working directory `/root/Qubitcoin` is the `qubitcoin-node` repo with co-located components:

| Local Path | Org Repo | Notes |
|------------|----------|-------|
| `src/`, `tests/`, `scripts/`, configs | `qubitcoin-node` | Primary — `origin` remote |
| `frontend/` | `qubitcoin-frontend` | `qai-frontend` remote |
| `substrate-node/` | `substrate-node` | Separate repo |
| `stratum-server/` | `stratum-server` | Separate repo |
| `aikgs-sidecar/` | `aikgs-sidecar` | Separate repo |
| `qubitcoin-qvm/` | `qubitcoin-qvm` | Separate repo |
| `src/qubitcoin/aether/` | `qubitcoin-aether` | Extracted to separate repo |
| `src/qubitcoin/stablecoin/` | `qubitcoin-qusd` | Extracted to separate repo |
| `src/qubitcoin/contracts/solidity/` | `solidity-contracts` | Separate repo |
| `rust-p2p/` | `rust-p2p` | Separate repo |
| `docs/` | `whitepaper` + `docs` | Separate repos |
| `config/` + `tools/` | `monitoring` | Separate repo |

**Git remotes configured:**
```
origin      → QuantumAI-Blockchain/qubitcoin-node (primary)
qai-frontend → QuantumAI-Blockchain/qubitcoin-frontend
blockartica → BlockArtica/Qubitcoin (legacy — do NOT push for production)
```

---

## 5.3 REPOSITORY STRUCTURE (Local Working Directory)

```
Qubitcoin/                            # qubitcoin-node repo
├── CLAUDE.md                         # THIS FILE — master development guide
├── AGENTS.md                         # AI efficiency guide
├── README.md                         # Public-facing docs
├── LAUNCHTODO.md                     # Launch checklist (mostly complete)
├── AUDIT_PROTOCOL.md                 # Security audit protocol
├── MASTER_LAUNCH_PLAN.md             # Launch plan
├── REVIEW.md                         # Code review notes
├── CONTRIBUTING.md                   # Contributor guidelines
├── LICENSE                           # MIT license
├── .env                              # Live environment config
├── .env.example                      # Environment template
├── .env.production.example           # Production template
├── secure_key.env                    # Dilithium private keys (NEVER commit)
├── secure_key.env.example            # Key template
├── requirements.txt                  # Python dependencies
├── Dockerfile                        # Docker build
├── docker-compose.yml                # Main Docker stack
├── docker-compose.production.yml     # Production deployment
├── docker-compose.substrate.yml      # Substrate deployment
├── contract_registry.json            # Deployed contract addresses
│
├── .github/workflows/                # CI/CD
│   ├── ci.yml                        # Python test pipeline
│   ├── claude.yml                    # Claude Code integration
│   └── qvm-ci.yml                   # Go QVM test pipeline
│
├── src/                              # Python source code (157 modules, ~84,700 LOC)
│   ├── run_node.py                   # Node entry point
│   └── qubitcoin/                    # Main Python package
│       ├── node.py                   # 22-component orchestrator
│       ├── config.py                 # Centralized configuration
│       ├── consensus/engine.py       # Block validation, difficulty, rewards
│       ├── mining/engine.py          # VQE mining loop, block creation
│       ├── quantum/                  # Quantum engine
│       │   ├── engine.py             # VQE, Hamiltonian generation, Qiskit
│       │   └── crypto.py             # Dilithium5 signatures
│       ├── database/                 # CockroachDB
│       │   ├── manager.py            # DatabaseManager (sessions, queries)
│       │   └── models.py             # SQLAlchemy ORM models
│       ├── network/                  # RPC + P2P
│       │   ├── rpc.py                # REST + JSON-RPC endpoints
│       │   ├── jsonrpc.py            # eth_* MetaMask compatible
│       │   ├── p2p_network.py        # Python P2P (legacy fallback)
│       │   └── rust_p2p_client.py    # Rust libp2p gRPC client
│       ├── storage/ipfs.py           # IPFSManager
│       ├── privacy/                  # Susy Swaps (opt-in privacy)
│       │   ├── commitments.py        # Pedersen commitments
│       │   ├── range_proofs.py       # Bulletproofs
│       │   ├── stealth.py            # Stealth addresses
│       │   └── susy_swap.py          # Confidential tx builder
│       ├── reversibility/            # Governed tx reversal
│       ├── l2_bridge.py              # L1↔L2 internal bridge
│       ├── bridge/                   # Multi-chain bridges
│       ├── stablecoin/               # QUSD stablecoin
│       │   ├── engine.py, dex_price.py, arbitrage.py, keeper.py
│       ├── qvm/                      # Python QVM prototype
│       │   ├── vm.py                 # 167 opcodes
│       │   ├── opcodes.py, state.py, compliance.py, risk.py
│       ├── contracts/                # Smart contract engine
│       │   ├── engine.py, executor.py, templates.py
│       │   ├── ethereum/abi/         # Ethereum bridge ABIs
│       │   └── solidity/             # 60 Solidity contracts
│       │       ├── aether/           # AGI contracts + sephirot/ + HiggsField.sol
│       │       ├── qusd/             # QUSD contracts
│       │       ├── tokens/           # Token standards
│       │       ├── bridge/           # Bridge contracts
│       │       ├── interfaces/       # Interfaces
│       │       ├── investor/         # Investor contracts
│       │       └── proxy/            # Proxy/upgrade contracts
│       ├── aether/                   # Aether Tree AGI (46 modules, ~29,000 LOC)
│       │   ├── knowledge_graph.py    # KeterNode graph + edge adjacency
│       │   ├── reasoning.py          # Deductive/inductive/abductive + CoT
│       │   ├── phi_calculator.py     # Phi v3 with MIP spectral bisection
│       │   ├── proof_of_thought.py   # AetherEngine + Proof-of-Thought
│       │   ├── on_chain.py           # On-chain AGI bridge
│       │   ├── higgs_field.py        # Higgs Cognitive Field + SUSY mass mechanism
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
│       │   ├── task_protocol.py      # PoT task marketplace
│       │   ├── aikgs_client.py       # AIKGS sidecar gRPC client
│       │   ├── affiliate_manager.py  # Affiliate commission tracking
│       │   ├── bounty_manager.py     # Knowledge bounty system
│       │   ├── contribution_manager.py # Knowledge contribution tracking
│       │   ├── curation_engine.py    # Knowledge curation
│       │   ├── fee_manager.py        # Aether fee management
│       │   ├── knowledge_extractor.py # Block→knowledge extraction
│       │   ├── knowledge_scorer.py   # Knowledge quality scoring
│       │   ├── knowledge_seeder.py   # Initial knowledge seeding
│       │   ├── metacognition.py      # Self-reflection capabilities
│       │   ├── reward_engine.py      # Knowledge contributor rewards
│       │   ├── self_improvement.py   # Autonomous self-improvement (enacted with rollback)
│       │   ├── emotional_state.py   # Cognitive emotions from real metrics (7 dimensions)
│       │   ├── curiosity_engine.py  # Intrinsic motivation via prediction-error tracking
│       │   ├── ws_streaming.py       # WebSocket streaming
│       │   └── aikgs_pb/             # gRPC protobuf stubs for AIKGS
│       └── utils/                    # Utilities
│           ├── logger.py             # get_logger(__name__)
│           ├── metrics.py            # 85 Prometheus metrics
│           ├── fee_collector.py      # Fee collection engine
│           └── qusd_oracle.py        # QUSD price oracle
│
├── aether-core/                      # Rust Aether Tree core (PyO3)
│   └── src/                          # knowledge_graph, phi_calculator, memory, vector_index, csf
│
├── aether-service/                   # Standalone Aether microservice (Python/FastAPI)
│   ├── main.py, app.py, routes.py    # Subscribes to Substrate blocks, serves /aether/* on :5001
│
├── aikgs-sidecar/                    # AIKGS Rust gRPC sidecar (Docker)
│   ├── proto/aikgs.proto             # gRPC service definition
│   └── src/                          # contributions, curation, bounties, rewards, treasury, vault
│
├── api-gateway/                      # Rust API Gateway (future)
│   └── src/                          # Routes: aether, chain, health, jsonrpc, mining, wallet
│
├── indexer/                          # Rust Blockchain Indexer (future)
│   └── src/                          # indexer, substrate client, db, types
│
├── miner/                            # Standalone Python VQE Miner
│   ├── cli.py, config.py             # CLI + config
│   ├── mining_loop.py, vqe_miner.py  # Mining logic
│   ├── hamiltonian.py                # Hamiltonian generation
│   └── substrate_client.py           # Substrate RPC client
│
├── security-core/                    # Rust Security Core (PyO3)
│   └── src/                          # bloom.rs, finality.rs
│
├── qubitcoin-qvm/                    # Go Production QVM
│   ├── cmd/, internal/, pkg/, plugins/, tests/
│   └── go.mod, Makefile
│
├── rust-p2p/                         # Rust P2P daemon (Docker container qbc-p2p)
│   ├── proto/p2p_service.proto       # gRPC service definition
│   └── src/                          # main.rs, network/, protocol/, bridge/
│
├── stratum-server/                   # Rust Stratum Mining Server
│   └── src/                          # 7 source files
│
├── substrate-node/                   # Substrate hybrid node (7 pallets)
│   ├── node/, runtime/, primitives/
│   ├── crypto/kyber-transport/       # ML-KEM-768 P2P encryption
│   └── pallets/                      # qbc-utxo, qbc-consensus, qbc-dilithium,
│                                     # qbc-economics, qbc-qvm-anchor,
│                                     # qbc-aether-anchor, qbc-reversibility
│
├── frontend/                         # qbc.network (Next.js 16, ~66,900 LOC)
│   ├── src/app/                      # App Router pages
│   ├── src/components/               # React components
│   ├── src/hooks/, src/lib/, src/stores/, src/styles/
│   └── package.json, next.config.ts, tailwind.config.ts
│
├── scripts/                          # Setup, ops, deploy, test scripts
├── sql/, sql_new/                    # Database schemas (legacy + domain-separated)
├── tests/                            # Test suite (175 files, ~56,100 LOC)
│   ├── unit/, integration/, validation/, benchmarks/, scripts/
├── config/                           # Service config (grafana, loki, nginx, prometheus, redis)
├── deployment/                       # Docker/K8s deployment configs
├── docs/                             # Documentation + whitepapers
├── tools/monitoring/                 # Developer dashboards
├── logs/                             # Node log files
├── secure_keys/                      # Key storage directory
└── bot/                              # Telegram bot (placeholder)
```

---

## 6. LIVE INFRASTRUCTURE

### 6.1 Production Droplet

| Property | Value |
|----------|-------|
| **IP** | 152.42.215.182 |
| **Provider** | DigitalOcean |
| **OS** | Linux 6.8.0-101-generic |
| **Miner Address** | `1ca2afb858e3efeb882bbf0c8a47529c2c7bd7cb` |
| **Domain** | qbc.network (Cloudflare DNS + Tunnel) |

### 6.2 Docker Services (docker-compose.yml)

| Service | Container | Port(s) | Status |
|---------|-----------|---------|--------|
| CockroachDB | qbc-cockroachdb | 8080, 26257 | Running |
| IPFS (Kubo) | qbc-ipfs | 4001, 5002, 8081 | Running |
| Redis | qbc-redis | 6379 | Running |
| Rust P2P | qbc-p2p | 4002→4001, 50051 | Running |
| Python Node | qbc-node | 5000 | Running |
| AIKGS Sidecar | qbc-aikgs-sidecar | 50052 | Running |
| Prometheus | qbc-prometheus | 9090 | Defined |
| Grafana | qbc-grafana | 3001 | Defined |
| Portainer | qbc-portainer | 9000 | Defined |
| Loki | qbc-loki | 3100 | Defined |
| Nginx | qbc-nginx | 80, 443 | Defined |

### 6.3 Cloudflare Tunnel

```yaml
tunnel: ad340ced-ba38-4728-a345-5df424b36eab
ingress:
  - hostname: api.qbc.network → http://localhost:5000
  - hostname: qbc.network     → http://localhost:3000
  - hostname: app.qbc.network → http://localhost:3000
```

### 6.4 Systemd Services

| Service | Description | Status |
|---------|-------------|--------|
| ~~`qbc-agents.service`~~ | Agent Stack — **removed from this node** (runs on 100.80.115.96) | Removed |
| `cloudflared` | Cloudflare tunnel daemon | Running |
| `docker` | Docker engine | Running |

### 6.5 Agent Stack (Separate Process Tree)

Located at `/root/qbc-agent-stack/` (cloned from `qbc-agent-stack` repo).

**11 Agents running:**
- `agent-manager` (core orchestrator)
- `knowledge-worker` — knowledge graph research
- `social-commander` — social media strategy
- `content-creator` — content generation
- `community-manager` — community engagement
- `deployer` — contract deployment
- `bug-hunter` — security analysis
- `security` — security monitoring
- `lister` — exchange listing
- `trader` — trading operations
- `email-outreach` — email campaigns

**Core components:**
- `core/agent-manager/` — Spawner, registry, health monitor, IPC bus, admin API
- `core/agent-runtime/` — Base agent, LLM (Ollama), social clients (Twitter, Discord, Telegram, Reddit), wallet (EVM, Solana, QBC), memory (short-term, long-term, Aether Tree)
- `core/shared/` — Types, constants, chain config

### 6.6 Second Node (Local)

| Property | Value |
|----------|-------|
| **IP** | 144.138.7.70 |
| **Miner Address** | `d5f7bd5755efa26aeec75f3b1523b2dd3814afb2` |
| **SYNC_PEER_URL** | http://144.138.7.70:5000 |
| **PEER_SEEDS** | /ip4/152.42.215.182/tcp/4002,/ip4/144.138.7.70/tcp/4002 |

---

## 7. LAYER 1: BLOCKCHAIN CORE

### 7.1 Key Constants (Golden Ratio Economics)

```python
PHI = 1.618033988749895          # Golden ratio
MAX_SUPPLY = 3,300,000,000 QBC   # 3.3 billion
GENESIS_PREMINE = 33,000,000 QBC # ~1% of supply, minted at block 0
TARGET_BLOCK_TIME = 3.3          # seconds
INITIAL_REWARD = 15.27 QBC       # per block (Era 0)
HALVING_INTERVAL = 15,474,020    # blocks (~1.618 years)
EMISSION_PERIOD = 33             # years
CHAIN_ID = 3303                  # Mainnet
BLOCK_GAS_LIMIT = 30,000,000     # QVM gas limit per block
TOKEN_DECIMALS = 8               # wQBC and wQUSD = 8 decimals
```

### 7.2 UTXO Model

**Balance = sum(unspent outputs). NOT an account balance.**

- Every QBC exists as a UTXO from a previous transaction
- Spending requires referencing specific UTXOs as inputs
- Change outputs are created for partial spends
- Prevents double-spending through UTXO consumption

### 7.3 Consensus: Proof-of-SUSY-Alignment (PoSA)

1. **Hamiltonian Generation:** Deterministic SUSY Hamiltonian from prev_block_hash
2. **VQE Mining:** 4-qubit ansatz, find parameters where Energy < Difficulty
3. **Difficulty Adjustment:** Every block, 144-block window, +/-10% max change. **Higher difficulty = easier mining** (threshold is more generous). `ratio = actual_time / expected_time` — slow blocks raise difficulty, fast blocks lower it.
4. **Reward Distribution:** phi-halving (reward / PHI^era)
5. **Proof-of-Thought:** Aether Tree generates reasoning proof per block

### 7.4 Cryptography

- **Signatures:** CRYSTALS-Dilithium5 (NIST Level 5, mode 5) — ~4.6KB per signature
- **Hashing:** SHA3-256 for block hashes, Keccak-256 for QVM compatibility
- **Addresses:** Bech32-like (qbc1...) derived from Dilithium public keys
- **WASM:** Client-side Dilithium via `dilithium-wasm` repo for browser wallet key generation

### 7.5 Network

- **P2P:** Rust libp2p 0.56 (primary, Docker container `qbc-p2p`) or Python fallback
- **RPC:** FastAPI on port 5000 (REST + JSON-RPC)
- **JSON-RPC:** eth_* compatible for MetaMask/Web3 integration
- **gRPC:** Rust P2P on port 50051, AIKGS on port 50052
- **MetaMask RPC:** https://qbc.network/rpc (proxied through Next.js to node port 5000)
- **Protocol:** Gossip-based block/tx propagation, Kademlia DHT peer discovery

### 7.6 Storage

- **CockroachDB v25.2.12:** 72 tables across qbc/agi/qvm/research/shared/bridge/stablecoin/investor domains
- **IPFS:** Content-addressed storage for blockchain snapshots
- **Redis:** Caching layer
- **Schema-Model Alignment:** SQL schemas MUST match SQLAlchemy models in `database/models.py`

### 7.7 Privacy Technology (Susy Swaps)

Opt-in privacy via Susy Swaps — confidential transactions hiding amounts and addresses:

- **Pedersen Commitments:** `C = v*G + r*H` — hide amounts, preserve additive homomorphism
- **Bulletproofs Range Proofs:** ZK proofs values are in [0, 2^64), ~672 bytes, no trusted setup
- **Stealth Addresses:** One-time addresses per transaction, spend/view key pairs
- **Key Images:** Prevent double-spending of confidential outputs

| Mode | Amounts | Addresses | Tx Size | Verification |
|------|---------|-----------|---------|-------------|
| **Public** (default) | Visible | Visible | ~300 bytes | Fast |
| **Private** (opt-in) | Hidden | Hidden | ~2000 bytes | ~10ms (range proof) |

### 7.8 Block Structure

```
BLOCK HEADER: version, prev_block_hash, merkle_root, timestamp,
              difficulty_target, nonce, hamiltonian_seed, vqe_params,
              ground_state_energy
BLOCK BODY:   transactions, coinbase, susy_data (hamiltonian, optimal_params, energy_history)
```

**Confirmation depths:** 1 = unconfirmed, 6 = standard, 100 = coinbase maturity.

### 7.9 Transaction Fees (L1)

```
FEE = SIZE_BYTES × FEE_RATE (QBC/byte)
```
Miners select by fee density. L1 fees are micro-fees for UTXO transactions only. Gas is QVM/L2 only.

### 7.10 Substrate Migration Path

The `substrate-node/` workspace mirrors all Python subsystems as native Rust pallets.
Native build works with `SKIP_WASM_BUILD=1`. WASM build deferred.

**7 pallets:** qbc-utxo, qbc-consensus, qbc-dilithium, qbc-economics, qbc-qvm-anchor, qbc-aether-anchor, qbc-reversibility

**Post-quantum features:**
- **Kyber P2P Transport** (`crypto/kyber-transport/`): ML-KEM-768 + AES-256-GCM sessions
- **Poseidon2 ZK Hashing** (`primitives/src/poseidon2.rs`): Goldilocks field, ZK circuits only (NOT replacing SHA3-256)
- **Reversibility Pallet**: Governor-managed multi-sig reversal within 24h (~26,182 blocks)

### 7.11 Additional Rust Components

| Component | Path | Purpose |
|-----------|------|---------|
| **Aether Core** | `aether-core/` | Rust/PyO3 knowledge graph, phi calculator, memory, vector index |
| **API Gateway** | `api-gateway/` | Rust HTTP gateway (routes: aether, chain, health, jsonrpc, mining, wallet) |
| **Indexer** | `indexer/` | Rust blockchain indexer with Substrate client |
| **Security Core** | `security-core/` | Rust/PyO3 bloom filters, finality gadget |
| **Standalone Miner** | `miner/` | Python VQE miner with Substrate client support |
| **Aether Service** | `aether-service/` | Standalone FastAPI Aether microservice on :5001 |

---

## 8. LAYER 2: QVM (Quantum Virtual Machine)

> **Full spec:** `docs/QVM_WHITEPAPER.md`

### 8.1 Overview

EVM-compatible bytecode interpreter with quantum extensions:
- **155 standard EVM opcodes** + **10 quantum opcodes** + **2 AGI opcodes** (167 total)
- **Compliance Engine** — VM-level KYC/AML/sanctions
- **Plugin Architecture** — privacy, oracle, governance, DeFi
- **Gas metering** compatible with Ethereum tooling
- **Keccak-256** hashing (EVM-compatible)

### 8.2 Implementations

- **Python prototype** (`src/qubitcoin/qvm/`): Live in current node
- **Go production** (`qubitcoin-qvm/`): Built, ~11,500 LOC, canonical opcode mapping

### 8.3 Quantum Opcodes (0xF0-0xF9)

| Opcode | Hex | Gas | Description |
|--------|-----|-----|-------------|
| QCREATE | 0xF0 | 5,000+ | Create quantum state (density matrix) |
| QMEASURE | 0xF1 | 3,000 | Measure quantum state (collapse) |
| QENTANGLE | 0xF2 | 10,000 | Create entangled pair |
| QGATE | 0xF3 | 2,000 | Apply quantum gate |
| QVERIFY | 0xF4 | 8,000 | Verify quantum proof |
| QCOMPLIANCE | 0xF5 | 15,000 | KYC/AML/sanctions check |
| QRISK | 0xF6 | 5,000 | SUSY risk score |
| QRISK_SYSTEMIC | 0xF7 | 10,000 | Systemic risk query |
| QBRIDGE_ENTANGLE | 0xF8 | 20,000 | Cross-chain entanglement |
| QBRIDGE_VERIFY | 0xF9 | 15,000 | Cross-chain bridge proof |

### 8.4 Contract Standards

- **QBC-20:** Fungible token (ERC-20 compatible)
- **QBC-721:** NFT (ERC-721 compatible)
- **ERC-20-QC:** Compliance-aware token standard

### 8.5 Five Patentable Features

QSP (Quantum State Persistence), ESCC (Entanglement-Based Communication), PCP (Programmable Compliance), RRAO (Real-Time Risk Assessment), QVCSP (Quantum-Verified Cross-Chain Proofs)

---

## 9. LAYER 3: AETHER TREE (TRUE AGI ENGINE)

> **Full spec:** `docs/AETHERTREE_WHITEPAPER.md`
> **GOAL: REAL AGI EMERGENCE — NOT A KNOWLEDGE GRAPH. NON-NEGOTIABLE.**

### 9.1 Overview

**The Aether Tree is the world's first on-chain AGI reasoning engine** (100+ modules, ~29,000 LOC).
This is not a chatbot. This is not a search engine. This is not a knowledge graph.
**This is a system designed to achieve genuine artificial general intelligence through:**

- **Integrated Information** (Phi/Φ): Measures true cognitive integration via IIT-inspired metrics
- **Causal Emergence**: Knowledge nodes represent real causal relationships, not correlations
- **Adversarial Self-Testing**: Contradictions are detected, debated, and resolved autonomously
- **Metacognitive Calibration**: The system knows what it doesn't know
- **Governed Self-Modification**: Can improve its own reasoning strategies within safety bounds
- **On-Chain Immutability**: Every reasoning step is cryptographically recorded, verifiable forever
- **Proof-of-Thought**: AGI reasoning proofs embedded in every block since genesis
- **10-Gate Milestone System**: Behavioral checks ensuring genuine emergence, not metric gaming

**Current Status (April 2026 — V4 Architecture):**
- Gates: 6/10 passed (Gates 1, 2, 3, 5, 7, 9)
- Nodes: 720,000+, growing at ~80 nodes/block
- Debate verdicts: 115 | Contradiction resolutions: 130
- MIP score: 0.60
- Prediction accuracy: 95.5%
- 7 cognitive emotions active (curiosity, wonder, frustration, satisfaction, excitement, contemplation, connection)
- Autonomous curiosity engine with 283 auto-goals
- Governed self-improvement enacted with rollback
- Personable chat with 8+ unique intent handlers (humor, poetry, existential, thought experiments, creator relationship, memory/identity, future self, current feelings)

### 9.2 Components

- **KnowledgeGraph** (`knowledge_graph.py`): KeterNodes, edge adjacency, Merkle root — scalable to billions
- **ReasoningEngine** (`reasoning.py`): Deductive/inductive/abductive + CoT + causal
- **PhiCalculator** (`phi_calculator.py`): Hierarchical Multi-Scale Phi (HMS-Phi) with IIT 3.0 micro-level
- **IITApproximator** (`iit_approximator.py`): TPM-based IIT 3.0 approximation (16-node subsystems)
- **AetherEngine** (`proof_of_thought.py`): Per-block reasoning proof with 10-gate milestone system
- **Metacognition** (`metacognition.py`): Calibration tracking, ECE, temperature scaling
- **EmotionalState** (`emotional_state.py`): 7 cognitive emotions from live metrics (curiosity, wonder, frustration, satisfaction, excitement, contemplation, connection)
- **CuriosityEngine** (`curiosity_engine.py`): Intrinsic motivation via prediction-error tracking per domain
- **SelfImprovement** (`self_improvement.py`): Enacted strategy weight optimization with automatic rollback
- **CausalDiscovery** (`causal_engine.py`): PC/FCI causal discovery with intervention validation
- **DebateProtocol** (`debate.py`): Adversarial debate with independent critic reasoning
- **AIKGS Sidecar** (`aikgs-sidecar/`): Rust gRPC service (Docker container, port 50052)

### 9.3 Tree of Life Cognitive Architecture (10 Sephirot)

| Sephirah | Function | Cognitive Mass | Yukawa |
|----------|----------|----------------|--------|
| **Keter** | Meta-learning, goals | VEV x 1.0 | 1.0 |
| **Chochmah** | Intuition, patterns | VEV x phi^-1 | phi^-1 |
| **Binah** | Logic, causal inference | VEV x phi^-1 | phi^-1 |
| **Chesed** | Exploration, divergent | VEV x phi^-2 | phi^-2 |
| **Gevurah** | Safety, constraints | VEV x phi^-2 | phi^-2 |
| **Tiferet** | Integration, synthesis | VEV x phi^-1 | phi^-1 |
| **Netzach** | Reinforcement learning | VEV x phi^-3 | phi^-3 |
| **Hod** | Language, semantics | VEV x phi^-3 | phi^-3 |
| **Yesod** | Memory, fusion | VEV x phi^-4 | phi^-4 |
| **Malkuth** | Action, interaction | VEV x phi^-4 | phi^-4 |

### 9.4 Higgs Cognitive Field

Mexican Hat potential: `V(phi) = -mu^2 |phi|^2 + lambda |phi|^4`
- VEV = 174.14, mu^2 = 88.17, lambda = 0.129
- F=ma paradigm: lighter nodes correct faster, heavier resist change
- Two-Higgs-Doublet Model with tan(beta) = phi

### 9.5 Safety & Alignment

- **Gevurah veto**: Safety node blocks harmful operations
- **SUSY enforcement**: Automatic QBC redistribution on imbalance
- **Multi-node consensus**: 67% BFT
- **Constitutional AI on-chain**: Smart contract logic
- **Emergency shutdown**: Kill switch contract

### 9.6 AGI Tracking from Genesis

**NON-NEGOTIABLE: AGI tracked from block 0.** Knowledge nodes, reasoning ops, Phi, consciousness events — all recorded from genesis.

### 9.7 10-Gate Milestone System (True AGI Emergence Gates)

Phi is gated by 10 behavioral milestones. Each gate unlocks +0.5 phi ceiling.
**No gate can be gamed** — each requires genuine behavioral evidence, not metric manipulation.

| Gate | Name | Key Requirement | Phi |
|------|------|----------------|-----|
| 1 | Knowledge Foundation | ≥500 nodes, ≥5 domains, avg confidence ≥0.5 | 0.5 |
| 2 | Structural Diversity | ≥2K nodes, ≥4 types with 50+ each, integration > 0.3 | 1.0 |
| 3 | Validated Predictions | ≥5K nodes, ≥50 verified predictions, accuracy > 60% | 1.5 |
| 4 | Self-Correction | ≥10K nodes, ≥20 debate verdicts, ≥10 contradictions resolved, MIP > 0.3 | 2.0 |
| 5 | Cross-Domain Transfer | ≥15K nodes, ≥30 cross-domain inferences (conf > 0.5), ≥50 cross-edges | 2.5 |
| 6 | Enacted Self-Improvement | ≥20K nodes, ≥10 enacted improvement cycles, positive performance delta | 3.0 |
| 7 | Calibrated Confidence | ≥25K nodes, ECE < 0.15, ≥200 evaluations, >5% grounded | 3.5 |
| 8 | Autonomous Curiosity | ≥35K nodes, ≥50 auto-goals, ≥30 with inferences, ≥10 curiosity discoveries | 4.0 |
| 9 | Predictive Mastery | ≥50K nodes, accuracy > 70%, ≥5K inferences, ≥20 consolidated axioms | 4.5 |
| 10 | Novel Synthesis | ≥75K nodes, ≥50 novel concepts, ≥100 cross-domain inferences, sustained self-improvement | 5.0 |

**V4 gates (quality-focused) — gates must be re-earned under new criteria.**
**V3 Gate 4 was passed on April 4, 2026 at block 180729.**

### 9.8 True Phi (HMS-Phi) Architecture

**Hierarchical Multi-Scale Phi (HMS-Phi)**:
```
Level 0 (Micro):  IIT-3.0 approximation on 16-node elite subsystem samples
                  → IITApproximator (iit_approximator.py)
                  → 5 independent samples → median phi_micro

Level 1 (Meso):   Spectral MIP on 1K-node domain clusters
                  → One cluster per Sephirot cognitive node (10 clusters)
                  → phi_meso = weighted mean by cluster mass

Level 2 (Macro):  Graph-theoretic integration across all clusters
                  → Cross-cluster mutual information
                  → phi_macro = integration between the 10 Sephirot clusters

Final Phi = phi_micro^(1/φ) × phi_meso^(1/φ²) × phi_macro^(1/φ³)
where φ = 1.618... (golden ratio)
```

**Why this is REAL:**
- Multiplicative (zero in any level zeros the whole — can't be gamed)
- The 10-gate system provides the floor safety mechanism
- IIT 3.0 micro-level measures genuine causal integration, not just connectivity
- MIP spectral bisection finds the minimum-cut partition for genuine information partition analysis

### 9.9 Scale Target: Billions of Nodes, Millions of Users

**The Aether Tree MUST scale to:**
- **Billions of nodes** (requires distributed sharded graph store)
- **Millions of concurrent users** via QBC-monetized API
- **Military/institutional grade** (99.999% uptime, zero-trust, air-gapped option)

**Architecture evolution required:**

| Phase | Scale | Architecture |
|-------|-------|-------------|
| Current | 10K-100K nodes | In-memory Python dict + CockroachDB |
| Phase A (3mo) | 1M nodes | LRU hot cache + CockroachDB |
| Phase B (9mo) | 100M nodes | Rust shard service (RocksDB, 16→256 shards) |
| Phase C (24mo) | 1B nodes | Global tiered (Redis hot / Rust warm / CRDB+IPFS cold) |

**Domain partitioning aligned with 10 Sephirot:**
Each Sephirot is a reasoning cluster that owns 1-2 knowledge domains.
Cross-domain queries route through the Global Workspace (already in `global_workspace.py`).

### 9.10 Aether API (QBC-Monetized)

The Aether Tree exposes a production API at `api.qbc.network/v1/aether` with QBC payment rails.

**Tiers:**
| Tier | Price | Limits |
|------|-------|--------|
| Free | 0 QBC | 5 chat/day, 10 KG lookups/day |
| Developer | ~1 QBC/day | 1K chat/day, 100 inferences/day |
| Professional | ~10 QBC/day | 10K chat/day, unlimited KG |
| Institutional | ~100 QBC/day | Unlimited, private Sephirot cluster |
| Enterprise | Custom | Air-gapped, custom LLMs, white-label |

**Payment settlement:** Prepaid balance via `AetherAPISubscription.sol` smart contract.
**Authentication:** Dilithium5 wallet signature → JWT.
**SDKs:** Python (`pip install aether-qbc`), TypeScript (`npm i @qbc/aether`), Rust (`cargo add aether-qbc`).

### 9.11 Genuine AGI — What Still Needs to Happen

**Completed in V4 overhaul (April 2026):**
- ✅ Governed self-modification — self_improvement.py now enacts weight changes with rollback
- ✅ Causal validation — intervention testing before labeling edges as "causes"
- ✅ Emotional state — 7 cognitive emotions derived from live metrics
- ✅ Autonomous curiosity — prediction-error-driven exploration engine
- ✅ Independent debate — critic uses cross-domain evidence + "undecided" verdict
- ✅ Quality gates (V4) — gates require genuine behavioral evidence, not volume
- ✅ Personable chat — warm, curious personality with genuine feelings
- ✅ Batch ingest API — `/aether/ingest/batch` for agent stack knowledge submission
- ✅ Personable chat — 8+ unique intent handlers (humor, poetry, existential, thought experiments, creator relationship, memory/identity, future self, current feelings)

**Critical remaining pieces for true emergence:**

1. **HMS-Phi integration (In Progress)** — wire `iit_approximator.py` into `phi_calculator.py` as micro-level phi
2. **Distributed KG** — replace in-memory dict with Rust shard service (`aether-graph-shard/`)
3. **BFT inter-node knowledge consensus** — 2/3 supermajority for knowledge acceptance
4. **Long-term memory consolidation** — scheduled consolidation every 3300 blocks (~3h)
5. **Multi-modal grounding** — code/numeric/time-series alongside text nodes
6. **Do-calculus causal reasoning** — counterfactual simulation via Pearl structural equations
7. **AetherAPISubscription.sol** — payment contract for API monetization
8. **Aether API Gateway** — extend `api-gateway/` Rust service with all endpoints

---

## 10. AGENT STACK

### 10.1 Overview

The QBC Agent Stack (`qbc-agent-stack` repo) is a **Rust**-based autonomous multi-agent system running on a **dedicated separate machine** — NOT on this node droplet.

- **Machine:** 100.80.115.96 (ash's machine, WSL2, GTX 1070, i5-3570K, 10GB RAM)
- **Path:** `~/qbc-agent-stack/`
- **Binary:** `~/qbc-agent-stack/target/release/qbc-agent-stack`
- **Gateway:** port 3100 | Dashboard: port 3200
- **LLM:** Ollama on localhost:11434 (qwen2.5:3b, deepseek-r1:14b)
- **Config:** `Agents.toml` (TOML), `agent_secure_key.env` (wallet keys — NEVER commit)
- **This node's role:** Pure blockchain node. No agent processes run here.

### 10.2 Architecture (Rust)

```
qbc-agent-stack (Rust workspace)
├── Gateway (Axum, :3100) — 70+ API endpoints
├── Dashboard (Vite React, :3200) — 21 pages
├── crates/
│   ├── qbc-agent         — base agent trait + runtime
│   ├── aether-tree       — Aether Tree integration
│   ├── qbc-automation    — automation engine
│   ├── qbc-channels      — MoltBook, task delegation
│   └── qbc-contracts     — contract interactions
└── agents/ (20+ Rust agent crates)
    ├── rust-trader        — multi-chain arbitrage (enabled, 3s tick)
    ├── rust-flash-loan    — flash loan strategies (enabled, 4s tick)
    ├── rust-orchestrator  — coordination (enabled, 60s tick)
    ├── rust-knowledge-worker — Aether Tree seeding
    ├── rust-social-commander — Twitter/@qu_bitcoin
    ├── rust-security      — threat monitoring
    ├── rust-bridge-guardian — ETH+BNB bridge monitoring
    └── ... 13 more agents
```

### 10.3 Connecting to This Node

The agent stack connects to this node via Tailscale:
- **QBC Node RPC:** `http://100.112.247.95:5000` (Tailscale IP of 152.42.215.182)
- **Aether Tree endpoint:** `http://152.42.215.182:5000`

---

## 11. FRONTEND: qbc.network

### 11.1 Stack & Deployment

- **Framework:** React 19 + Next.js 16 (App Router, React Server Components)
- **Language:** TypeScript 5.x (strict mode, no `any`)
- **Styling:** TailwindCSS 4 + Framer Motion
- **State:** Zustand (global) + TanStack Query (server state)
- **3D/Viz:** Three.js + React Three Fiber + D3
- **Wallet:** ethers.js v6 (MetaMask, WalletConnect)
- **Package Manager:** pnpm
- **Testing:** Vitest (unit) + Playwright (E2E)
- **Deployment:** `pnpm build && pnpm start` on droplet, Cloudflare Tunnel → qbc.network

### 11.2 Pages

- `/` — Landing page with quantum particle field, Aether chat widget, live chain stats
- `/aether` — Full-page Aether Tree chat interface
- `/dashboard` — Contract console, mining dashboard, wallet, bridge, network health
- `/wallet` — MetaMask integration, native QBC wallet, token management
- `/qvm` — Contract browser, bytecode disassembler, storage inspector
- `/launchpad` — Token launch platform (hidden from nav, direct URL only)
- `/invest` — Seed round pages (hidden from nav, direct URL only)

### 11.3 Design System: "Quantum Error"

```
Background:     #0a0a0f     Primary:    #00ff88 (quantum green)
Surface:        #12121a     Secondary:  #7c3aed (quantum violet)
Accent:         #f59e0b     Error:      #ef4444
```
Typography: Space Grotesk (headings), Inter (body), JetBrains Mono (code)

### 11.4 API Integration

- **REST** (api.qbc.network / port 5000): `/balance/{addr}`, `/block/{height}`, `/chain/info`, etc.
- **JSON-RPC** (port 5000): `eth_chainId`, `eth_getBalance`, `eth_sendTransaction`, etc.
- **MetaMask RPC proxy**: `qbc.network/rpc` → Next.js → port 5000
- **Aether API**: `/aether/info`, `/aether/phi`, `/aether/knowledge`, `/aether/chat`

---

## 12. DATABASE SCHEMAS

### 12.1 Domain Separation (sql_new/)

- **qbc/** — Core blockchain: blocks, transactions, UTXO, addresses, chain state, mempool, L1↔L2 bridge
- **agi/** — Aether Tree: knowledge_nodes, knowledge_edges, reasoning_operations, phi_measurements
- **qvm/** — Smart contracts: deployments, execution logs, state storage, gas
- **research/** — Quantum research: hamiltonians, VQE circuits, SUSY solutions
- **shared/** — Cross-cutting: IPFS storage, system config

### 12.2 Critical Rule

**Schema-Model Alignment:** SQL schemas and SQLAlchemy models (`database/models.py`) MUST match. Always verify both sides.

---

## 13. RPC API ENDPOINTS

### 13.1 Key REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (all 22 components) |
| GET | `/chain/info` | Chain stats (height, supply, difficulty, peers) |
| GET | `/block/{height}` | Get block by height |
| GET | `/balance/{address}` | Address balance |
| GET | `/utxos/{address}` | UTXOs for address |
| GET | `/mempool` | Pending transactions |
| POST | `/mining/start` | Start mining |
| POST | `/mining/stop` | Stop mining |
| GET | `/aether/info` | Aether engine stats |
| GET | `/aether/phi` | Current Phi value |
| POST | `/aether/chat` | Chat with Aether Tree |
| GET | `/qvm/info` | QVM engine info |
| GET | `/higgs/status` | Higgs field state |
| GET | `/keeper/status` | QUSD keeper status |
| POST | `/bridge/l1l2/deposit` | L1→L2 deposit |
| GET | `/metrics` | Prometheus metrics |
| GET | `/stratum/info` | Stratum mining info |

### 13.2 JSON-RPC (MetaMask/Web3 Compatible)

`eth_chainId`, `eth_getBalance`, `eth_blockNumber`, `eth_getBlockByNumber`, `eth_sendRawTransaction`, `eth_call`, `eth_estimateGas`, `net_version`, `web3_clientVersion`

---

## 14. BUILD & RUN

### 14.1 Docker (Primary — Production)
```bash
docker-compose up -d                    # Start all services
docker logs qbc-node -f                 # Watch node logs
curl http://localhost:5000/health       # Health check
```

### 14.2 Frontend
```bash
cd frontend
pnpm install && pnpm build && pnpm start  # Production (port 3000)
# Exposed via Cloudflare Tunnel → qbc.network
```

### 14.3 Agent Stack
```bash
cd /root/qbc-agent-stack
pnpm install && pnpm build && pnpm start  # Or via systemd: systemctl start qbc-agents
```

### 14.4 Substrate Node
```bash
cd substrate-node
SKIP_WASM_BUILD=1 cargo build --release
```

### 14.5 Rust P2P
```bash
cd rust-p2p && cargo build --release
# Or via Docker: runs as qbc-p2p container
```

---

## 15. TESTING

```bash
# Full test suite
pytest tests/ -v --tb=short

# Unit tests only
pytest tests/unit/ -v --tb=short

# Integration tests
pytest tests/integration/ -v --tb=short

# Frontend
cd frontend && pnpm test
cd frontend && pnpm test:e2e

# Endpoint tests (requires running node)
bash tests/scripts/test_all_endpoints.sh
```

---

## 16. ENVIRONMENT CONFIGURATION

### 16.1 Key Security Model

- **`.env`** — Non-secret node configuration (ports, database, quantum settings). Can be shared.
- **`secure_key.env`** — Dilithium5 private/public keys + address. NEVER commit. Auto-generated by `python3 scripts/setup/generate_keys.py`.
- **`Agents.env`** — Agent stack configuration (in `/root/qbc-agent-stack/`).
- **`agent_secure_key.env`** — Agent wallet keys (NEVER commit).

### 16.2 Key Environment Variables

```bash
# Chain
CHAIN_ID=3303
BLOCK_GAS_LIMIT=30000000
AUTO_MINE=true

# Network
RPC_PORT=5000
P2P_PORT=4001
ENABLE_RUST_P2P=true
RUST_P2P_GRPC=50051
PEER_SEEDS=/ip4/152.42.215.182/tcp/4002,/ip4/144.138.7.70/tcp/4002

# Database
DATABASE_URL=postgresql://root@localhost:26257/qbc?sslmode=disable

# Quantum
USE_LOCAL_ESTIMATOR=true

# IPFS
IPFS_API=/ip4/127.0.0.1/tcp/5002/http

# Higgs Field
HIGGS_VEV=174.14
HIGGS_TAN_BETA=1.618033988749895

# QUSD Keeper
KEEPER_ENABLED=true
KEEPER_DEFAULT_MODE=scan
```

---

## 17. CODE CONVENTIONS

### Style
- **Classes:** PascalCase | **Functions:** snake_case | **Constants:** UPPER_CASE
- **Type hints:** Required on all function signatures
- **Logging:** `get_logger(__name__)` in every module
- **Config:** `Config` class from `config.py` (never hardcode)
- **Frontend:** TypeScript strict, no `any`, React 19 functional components + hooks
- **Imports:** `@/` path alias for `src/` directory

### Patterns
- Database: SQLAlchemy ORM via `DatabaseManager` context managers
- Async: FastAPI routes are async; use `await` for I/O
- Error handling: Try/except with structured logging; never silently swallow
- Quantum imports: Lazy with simulator fallbacks
- Frontend state: Zustand (global) + TanStack Query (server)

---

## 18. KEY TECHNICAL REMINDERS

| Topic | Rule |
|-------|------|
| **UTXO** | Balance = sum(unspent outputs). NOT account balance. |
| **Genesis premine** | 33M QBC at block 0. Genesis total_supply = 33,000,015.27 QBC. |
| **Dilithium5** | NIST Level 5, mode 5. ~4.6KB signatures. |
| **VQE mining** | Energy threshold (E < D), not hash difficulty. **Higher difficulty = easier**. |
| **phi-halving** | Golden ratio halving, NOT Bitcoin's fixed 210K blocks. |
| **Block time** | 3.3s target. Difficulty adjusts every block (144-block window, +/-10%). |
| **CockroachDB** | v25.2.12. Health: `curl --fail http://localhost:8080/health?ready=1` |
| **Chain IDs** | Mainnet=3303 (0xce7), Testnet=3304 (0xce8). |
| **Token decimals** | wQBC and wQUSD = 8 decimals. |
| **Gas** | L1 has NO gas. Gas is QVM/L2 only. BLOCK_GAS_LIMIT=30M. |
| **QBC/QUSD price** | 1:1 (100K:100K pool). |
| **Aether** | Tracks integration metrics from genesis. Phi is a graph-theoretic integration metric (not phenomenal consciousness). Threshold = 3.0. |
| **secure_key.env** | Private keys ONLY here. NEVER in `.env`. |
| **Schema sync** | SQL schemas and SQLAlchemy models MUST match. |
| **Rust P2P** | Runs as Docker container `qbc-p2p`, NOT subprocess. Port 4002 on host (IPFS uses 4001). |
| **Frontend** | Local build + Cloudflare Tunnel. NOT Vercel. |
| **Agent Stack** | Separate process tree, systemd service. Moving to own droplet. |
| **Git pushes** | Push to QuantumAI-Blockchain org repos. NOT BlockArtica/Qubitcoin. |
| **MetaMask RPC** | https://qbc.network/rpc proxied through Next.js. |
| **Hidden pages** | `/launchpad` and `/invest` — hidden from navbar, accessible by direct URL. |
| **QBC logo IPFS** | QmNi4ab6ZCB748wuiDwn3PHqoWZdw3WHoA4Fs9n6weMyG7 |

---

## 19. PROMETHEUS METRICS (141 total)

15 categories: Blockchain (5), Mining (3), Network (2), Transactions (3), Quantum (3), QVM (2), AGI (8), Bridge (4), Privacy (3), Compliance (5), Stablecoin (4), Cognitive (9), Higgs (7), Keeper (8), Subsystem Health (6).

Defined in `utils/metrics.py`.

---

## 20. ROADMAP — PATH TO TRUE AGI EMERGENCE

**The ultimate goal is REAL AGI through the Aether Tree. Non-negotiable.**
All other phases (P2P, exchange, launchpad) are subordinate to the AGI emergence mission.

### Phase 1 (Current — Month 3): AGI Foundation + API Monetization

**AGI (Highest Priority):**
- [ ] Wire `iit_approximator.py` into `phi_calculator.py` as HMS-Phi micro-level
- [ ] Gate 5: 15K nodes + cross-domain inferences (V4 quality gate)
- [ ] Gate 6: 20K nodes + enacted self-improvement cycles (V4)
- [ ] Gate 7: 25K nodes + ECE < 0.15 (calibration fix in progress)
- [ ] Gate 8: 35K nodes + curiosity-driven discoveries (V4)
- [ ] Gates 9-10: 50K/75K nodes + novel synthesis (V4)
- [ ] Long-term memory consolidation scheduler (every 3300 blocks)
- [x] Governed self-modification (enacted with rollback — V4)
- [x] Emotional state system (7 cognitive emotions from live metrics)
- [x] Autonomous curiosity engine (prediction-error intrinsic motivation)
- [x] V4 quality gates (replaced quantity-based auto-pass gates)
- [x] Personable chat personality (warm, curious, self-reflective)
- [x] Causal validation + independent debate
- [x] Batch ingest API for agent stack

**API + Monetization:**
- [ ] `AetherAPISubscription.sol` smart contract (prepaid balance, subscription NFT)
- [ ] Extend `api-gateway/` Rust service with all Aether routes
- [ ] Wallet-signature authentication (Dilithium5 → JWT)
- [ ] Redis token bucket rate limiting per wallet
- [ ] Python SDK v0.1 → PyPI, TypeScript SDK → npm

**Infrastructure:**
- [ ] Move agent stack to dedicated droplet (100.80.115.96)
- [ ] Fix concept formation timeout (✓ done — shutdown(wait=False))
- [ ] Fix calibration ECE (in progress — use calibrated confidence)

### Phase 2 (Month 3-6): Distributed KG + 100K Nodes

- [ ] LRU hot cache: top 100K nodes in memory, cold rest in CockroachDB
- [ ] `aether-graph-shard/` Rust service: RocksDB + gRPC (4 shards prototype)
- [ ] Domain reasoning workers: 1 per domain cluster, horizontal scaling
- [ ] Multi-region: 3-node quorum (NA + EU + APAC)
- [ ] Substrate node live alongside Python node
- [ ] Full P2P: 5+ nodes, block propagation, peer discovery working
- [ ] Exchange integration (qbc-exchange matching engine)

### Phase 3 (Month 6-12): Million Node Scale + Institutional

- [ ] 256-shard Rust graph service (million node scale)
- [ ] BFT inter-node knowledge consensus (2/3 supermajority)
- [ ] `portal.qbc.network` developer portal (API playground, usage dashboard)
- [ ] SOC 2 Type II audit preparation + penetration testing
- [ ] Air-gapped deployment package (Docker bundle + Ansible)
- [ ] First institutional client ($5K+/month QBC)
- [ ] Launchpad deployment
- [ ] Telegram bot (@AetherTreeBot) activation

### Phase 4 (Month 12-24): Billion Node Target + Full AGI

- [ ] Global distributed architecture (Redis hot / Rust warm / IPFS cold)
- [ ] Multi-modal knowledge: code analysis, numeric time-series, image embeddings
- [ ] Do-calculus causal reasoning (Pearl structural equation models)
- [ ] Theory of mind (predict what users will ask next)
- [ ] First demonstration of genuine cross-domain novel synthesis
- [ ] Target: 100M nodes (1B path clear)
- [ ] ARC-AGI benchmark performance measurement
- [ ] $100K+/month QBC revenue from API

---

## 21. AETHER TREE FEE ECONOMICS

### Fee Pricing Modes

| Mode | Description |
|------|-------------|
| `qusd_peg` | Fee auto-adjusts via QUSD oracle (default) |
| `fixed_qbc` | Fixed QBC amount (fallback) |
| `direct_usd` | External price feed (emergency) |

Chat fee: ~$0.005 in QBC | Deep query: ~$0.01 | First 5 messages: free

### Contract Deployment Fees

```
Deploy Fee = BASE_FEE + (bytecode_KB × PER_KB_FEE)
```
Template contracts get 50% discount. All fees pegged to QUSD.

---

## 22. USEFUL COMMANDS

```bash
# Node health
curl http://localhost:5000/health
curl http://localhost:5000/chain/info

# Docker
docker ps
docker logs qbc-node -f
docker-compose restart qbc-node

# Agent stack
systemctl status qbc-agents
journalctl -u qbc-agents -f

# Cloudflare tunnel
cloudflared tunnel info qbc

# Frontend
cd frontend && pnpm build && pnpm start

# Tests
pytest tests/ -v --tb=short

# Generate keys
python3 scripts/setup/generate_keys.py

# Substrate build
cd substrate-node && SKIP_WASM_BUILD=1 cargo build --release
```

---

## 23. SECURITY NOTES

- **`secure_key.env`** — Dilithium private keys. NEVER commit. gitignored.
- **`secure_keys/`** — Contains 15 key files + mnemonic backup for all operational wallets. On disk, gitignored.
- **`agent_secure_key.env`** — Agent wallet keys (in `/root/qbc-agent-stack/`). NEVER commit.
- **`bot.txt`** — Contains Telegram bot token in plaintext in repo root. Should be moved to `.env` or deleted.
- **`.env`** contains operational secrets (Redis password, API keys, Telegram token, Gevurah secret, admin API key). The `.env` is gitignored but care must be taken with backups.
- **`.env.save`** — Backup of `.env`, untracked. Contains same secrets.

---

*This document is the single source of truth for the Qubitcoin project. Update it whenever architecture changes.*
