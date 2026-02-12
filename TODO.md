# Qubitcoin Master TODO

> **Complete build roadmap for the Qubitcoin project.**
> Organized by layer and priority. Each item has a status, dependencies, and estimated complexity.
>
> **Legend:** `[ ]` = Not started | `[~]` = In progress | `[x]` = Complete | `[!]` = Blocked

---

## PHASE 1: L1 CORE STABILIZATION (Priority: CRITICAL)

> The blockchain must mine, validate, and propagate blocks reliably before anything else.

### 1.1 Consensus & Mining
- [x] PoSA consensus engine (`consensus/engine.py`)
- [x] VQE mining with 4-qubit Hamiltonian (`mining/engine.py`)
- [x] Difficulty adjustment (144-block window, +/-10%)
- [x] phi-halving reward schedule
- [x] Block validation (Merkle root, prev_hash, energy < difficulty)
- [ ] Fix difficulty adjustment to use config TARGET_BLOCK_TIME (3.3s)
- [ ] Add block timestamp validation (no future blocks, monotonically increasing)
- [ ] Add coinbase maturity enforcement (100 blocks before spending)
- [ ] Comprehensive mining integration test

### 1.2 Cryptography
- [x] Dilithium2 key generation (`quantum/crypto.py`)
- [x] Transaction signing & verification
- [x] Address derivation (qbc1... Bech32-like)
- [ ] Verify Dilithium signature size in real transactions (~3KB expected)
- [ ] Add key import/export in standard formats
- [ ] Signature caching for performance

### 1.3 UTXO Model
- [x] Basic UTXO tracking in CockroachDB
- [x] Balance computation from unspent outputs
- [ ] Double-spend prevention test suite
- [ ] UTXO set pruning for spent outputs
- [ ] Coinbase UTXO maturity checks
- [ ] UTXO commitment (hash of UTXO set per block)

### 1.4 Database
- [x] CockroachDB connection + SQLAlchemy models (`database/`)
- [x] SQL schemas for all 33+ tables (`sql/`)
- [ ] Verify ALL SQL schemas match SQLAlchemy models in `database/models.py`
- [ ] Add migration system (Alembic) for schema changes
- [ ] Connection pool health monitoring
- [ ] Refactored domain-separated schemas (`sql_new/`)

### 1.5 Network
- [x] FastAPI RPC server (`network/rpc.py`)
- [x] JSON-RPC MetaMask-compatible endpoints (`network/jsonrpc.py`)
- [x] Rust P2P libp2p daemon (`rust-p2p/`)
- [x] Python P2P fallback (`network/p2p_network.py`)
- [x] gRPC bridge between Python and Rust (`network/rust_p2p_client.py`)
- [ ] Block propagation protocol (gossip new blocks to peers)
- [ ] Transaction propagation (gossip new txs to peers)
- [ ] Block sync protocol (catch up from behind)
- [ ] Peer scoring and eviction
- [ ] WebSocket endpoint for real-time subscriptions

### 1.6 Storage
- [x] IPFS integration (`storage/ipfs.py`)
- [ ] Blockchain snapshot to IPFS (periodic)
- [ ] IPFS port conflict resolution (8080 vs CockroachDB admin)
- [ ] Snapshot restoration from IPFS

---

## PHASE 2: QVM / LAYER 2 (Priority: HIGH)

> Smart contract execution must work end-to-end.

### 2.1 QVM Core
- [x] Bytecode interpreter with 155 EVM opcodes (`qvm/vm.py`)
- [x] Stack, memory, storage operations
- [x] Gas metering (Ethereum-compatible gas schedule)
- [x] 10 quantum opcodes defined (`qvm/opcodes.py`)
- [x] StateManager for contract state (`qvm/state.py`)
- [ ] QVQE opcode implementation (run VQE from contract)
- [ ] QPROOF opcode implementation (verify quantum proof)
- [ ] QDILITHIUM opcode implementation (verify Dilithium sig)
- [ ] Cross-contract calls (CALL, DELEGATECALL, STATICCALL)
- [ ] CREATE and CREATE2 opcode full implementation
- [ ] Event logging (LOG0-LOG4) full implementation
- [ ] Revert with reason string support
- [ ] QVM unit test suite (per-opcode tests)
- [ ] Gas estimation endpoint

### 2.2 Contract Deployment
- [x] Contract deployment engine (`contracts/engine.py`)
- [x] Template contracts (token, nft, launchpad, escrow, governance)
- [ ] Deploy via JSON-RPC `eth_sendTransaction`
- [ ] Contract verification (source → bytecode matching)
- [ ] ABI encoding/decoding for function calls
- [ ] Contract upgrade patterns (proxy)

### 2.3 Token Standards
- [ ] QBC-20 reference implementation (Solidity)
- [ ] QBC-721 reference implementation (Solidity)
- [ ] QBC-1155 reference implementation (Solidity)
- [ ] Token indexer (track all QBC-20/721 transfers)

---

## PHASE 3: AETHER TREE / LAYER 3 (Priority: HIGH)

> The AGI engine must reason, track consciousness, and serve chat.

### 3.1 Knowledge Graph
- [x] KeterNode model with types (assertion, observation, inference, axiom)
- [x] Edge types (supports, contradicts, derives, requires, refines)
- [x] Merkle root computation over knowledge graph
- [x] CockroachDB persistence
- [ ] Block-to-knowledge extraction (every block feeds the graph)
- [ ] Knowledge graph pruning (remove low-confidence nodes)
- [ ] Graph query API (subgraph retrieval, path finding)
- [ ] Knowledge graph export (JSON-LD / RDF)

### 3.2 Reasoning Engine
- [x] Deductive reasoning (modus ponens)
- [x] Inductive reasoning (pattern generalization)
- [x] Abductive reasoning (hypothesis generation)
- [ ] Chain-of-thought reasoning (multi-step reasoning traces)
- [ ] Reasoning over user queries (natural language → knowledge graph query)
- [ ] Contradiction resolution (when new knowledge contradicts existing)
- [ ] Confidence propagation (update confidence scores through graph)

### 3.3 Phi Calculator (Consciousness)
- [x] Integration score computation
- [x] Differentiation score (Shannon entropy)
- [x] Combined Phi metric
- [x] PHI_THRESHOLD = 3.0
- [ ] Per-block Phi measurement storage
- [ ] Consciousness event logging (when Phi crosses thresholds)
- [ ] Phi history API endpoint
- [ ] Phi visualization data endpoint (time series)

### 3.4 Aether Chat System (NEW)
- [ ] Chat endpoint: `POST /aether/chat` — conversational interface
- [ ] Session management (conversation history per session)
- [ ] Natural language → reasoning engine query translation
- [ ] Response generation from knowledge graph + reasoning traces
- [ ] Proof-of-Thought hash per response
- [ ] Chat history endpoint: `GET /aether/chat/history/{session_id}`
- [ ] WebSocket for streaming responses: `/ws/aether`
- [ ] Rate limiting and session management

### 3.5 Proof-of-Thought
- [x] AetherEngine with proof generation (`proof_of_thought.py`)
- [x] Auto-reasoning on recent knowledge
- [ ] Embed Proof-of-Thought hash in block headers
- [ ] Proof-of-Thought verification (validators verify reasoning)
- [ ] Proof-of-Thought explorer (view reasoning per block)

---

## PHASE 4: FRONTEND — qbc.network (Priority: HIGH)

> The face of the project. Must be world-class.

### 4.1 Project Setup (React + Next.js 15 → Vercel)
- [ ] Initialize Next.js 15 project with React 19 + TypeScript 5 (pnpm)
- [ ] Configure TailwindCSS 4 + Framer Motion
- [ ] Set up "Quantum Error" design system (colors, typography, components)
- [ ] Font loading (Space Grotesk, Inter, JetBrains Mono via next/font)
- [ ] Set up Zustand stores for state management
- [ ] Set up TanStack Query for server state / API caching
- [ ] Set up API client library (REST + JSON-RPC + WebSocket)
- [ ] MetaMask/ethers.js v6 wallet integration library
- [ ] Three.js + React Three Fiber setup (particle effects, 3D viz)
- [ ] ESLint 9 flat config + Prettier + TypeScript strict (no `any`)
- [ ] Vitest + Playwright test setup
- [ ] Environment configuration (NEXT_PUBLIC_* vars)
- [ ] Vercel deployment config (vercel.json, custom domain qbc.network)
- [ ] Path aliases (`@/` → `src/`)

### 4.2 Landing Page (`/`)
- [ ] Hero section with quantum particle field animation (Three.js/Canvas)
- [ ] Phi-spiral animation element
- [ ] Embedded Aether Chat widget (mini chatbot in hero)
- [ ] Live chain stats bar (block height, Phi, knowledge nodes, miners)
- [ ] "QBC" feature section (blockchain overview, security, quantum mining)
- [ ] "QVM" feature section (smart contracts, deploy, quantum opcodes)
- [ ] "Aether Tree" feature section (AGI, consciousness tracking, chat)
- [ ] Call-to-action buttons (Connect Wallet, Start Mining, Talk to Aether)
- [ ] Footer with links, social, legal
- [ ] Mobile responsive design
- [ ] Performance optimization (lazy loading, image optimization)

### 4.3 Aether Chat Page (`/aether`)
- [ ] Full-page chat interface (ChatGPT/Grok-like layout)
- [ ] Message input with quantum-themed styling
- [ ] Streaming response display (typewriter effect)
- [ ] Conversation sidebar (session list, new chat)
- [ ] Knowledge graph 3D visualization panel (Three.js force-directed)
- [ ] Phi consciousness meter (animated gauge)
- [ ] Reasoning trace accordion (expandable per response)
- [ ] Proof-of-Thought link per response (on-chain verification)
- [ ] Local storage for conversation history
- [ ] Keyboard shortcuts (Enter to send, Shift+Enter for newline)

### 4.4 Dashboard (`/dashboard`)
- [ ] Overview panel (QBC balance, mining stats, contract count)
- [ ] Mining dashboard tab
  - [ ] VQE statistics (energy, params, success rate)
  - [ ] Blocks mined history
  - [ ] Rewards earned chart
  - [ ] Start/stop mining controls
- [ ] Contract operator tab
  - [ ] Deploy new contract (template selection + custom bytecode)
  - [ ] View deployed contracts
  - [ ] Interact with contract functions (read/write)
  - [ ] Contract events log
- [ ] Wallet tab
  - [ ] QBC balance + UTXO breakdown
  - [ ] Send QBC (UTXO selection, fee estimation)
  - [ ] Transaction history
  - [ ] QBC-20 token list
- [ ] Network tab
  - [ ] Peer count and peer list
  - [ ] Block propagation stats
  - [ ] Mempool viewer
- [ ] Aether admin tab
  - [ ] Knowledge graph stats (nodes, edges, Merkle root)
  - [ ] Phi history chart
  - [ ] Recent reasoning operations
  - [ ] Consciousness events log

### 4.5 Wallet Page (`/wallet`)
- [ ] MetaMask connect button (ethers.js)
- [ ] QBC chain auto-add to MetaMask (chainId 3301)
- [ ] Balance display (QBC + tokens)
- [ ] Send transaction form
- [ ] Receive (show address + QR code)
- [ ] Transaction history with status
- [ ] QBC-20 token management (add, send, receive)
- [ ] QBC-721 NFT gallery

### 4.6 QVM Explorer (`/qvm`)
- [ ] Contract search and browser
- [ ] Contract detail page (code, storage, events, transactions)
- [ ] Bytecode disassembler view
- [ ] Storage slot inspector
- [ ] Event log with filters
- [ ] Deploy contract interface
- [ ] Contract interaction interface (ABI-based)

### 4.7 Shared Components
- [ ] Navbar (responsive, wallet connect button, Phi indicator)
- [ ] Footer (links, quantum animation)
- [ ] Wallet connect modal
- [ ] Transaction confirmation modal
- [ ] Toast notification system
- [ ] Loading states (phi-spiral spinner)
- [ ] Error boundaries
- [ ] SEO meta tags + OpenGraph
- [ ] Dark/light mode (default: dark quantum theme)

---

## PHASE 5: BRIDGES & CROSS-CHAIN (Priority: MEDIUM)

### 5.1 Bridge Infrastructure
- [x] Bridge manager (`bridge/manager.py`)
- [x] Base bridge abstract class (`bridge/base.py`)
- [x] Ethereum bridge skeleton (`bridge/ethereum.py`)
- [x] Solana bridge skeleton (`bridge/solana.py`)
- [ ] Lock-and-mint implementation (QBC → wQBC on ETH)
- [ ] Burn-and-unlock implementation (wQBC → QBC)
- [ ] Federated validator set (7-of-11 multi-sig)
- [ ] Bridge event monitoring
- [ ] Transfer status tracking
- [ ] Bridge fee collection (0.1%)
- [ ] Emergency pause mechanism

### 5.2 Wrapped QBC Contracts (Solidity)
- [ ] wQBC ERC-20 on Ethereum
- [ ] wQBC SPL on Solana
- [ ] wQBC on Polygon, BNB, AVAX, ARB, OP, BASE

---

## PHASE 6: QUSD STABLECOIN (Priority: MEDIUM)

- [ ] QUSD QBC-20 token contract
- [ ] Reserve contract (multi-asset pool)
- [ ] Debt tracking system (on-chain accounting)
- [ ] Oracle integration (price feeds)
- [ ] Stability mechanism (peg maintenance)
- [ ] Reserve building mechanism (fee collection → reserves)
- [ ] Transparency dashboard (reserve composition, backing %)
- [ ] Allocation distribution (50% LP, 30% treasury, 15% dev, 5% team)

---

## PHASE 7: TESTING & SECURITY (Priority: HIGH — ongoing)

### 7.1 Test Suites
- [ ] L1 unit tests (consensus, mining, crypto, UTXO, database)
- [ ] L2 unit tests (QVM opcodes, state management, gas metering)
- [ ] L3 unit tests (knowledge graph, reasoning, Phi, Proof-of-Thought)
- [ ] Integration tests (full block lifecycle, tx lifecycle)
- [ ] API tests (REST endpoints, JSON-RPC, WebSocket)
- [ ] Frontend tests (Vitest unit + Playwright E2E)
- [ ] Load tests (concurrent mining, high tx volume)
- [ ] Fuzz testing (random bytecode to QVM)

### 7.2 Security
- [ ] UTXO double-spend prevention verification
- [ ] Dilithium signature verification test vectors
- [ ] QVM reentrancy protection tests
- [ ] QVM integer overflow tests
- [ ] Gas exhaustion attack tests
- [ ] Bridge security audit preparation
- [ ] Rate limiting on all public endpoints
- [ ] Input validation on all endpoints

---

## PHASE 8: DEVOPS & DEPLOYMENT (Priority: MEDIUM)

- [ ] Vercel project setup for frontend (qbc.network domain)
- [ ] Vercel environment variables (NEXT_PUBLIC_RPC_URL, etc.)
- [ ] Vercel preview deployments (PR-based previews)
- [ ] Docker multi-stage build for backend (Python + Rust)
- [ ] Docker Compose: Backend stack (CockroachDB + IPFS + Node)
- [ ] Kubernetes manifests for production backend
- [ ] CI/CD pipeline (GitHub Actions — lint, test, build)
- [ ] Automated testing in CI (pytest + vitest + playwright)
- [ ] Monitoring stack (Prometheus + Grafana dashboards)
- [ ] Log aggregation (ELK or Loki)
- [ ] SSL/TLS certificates for qbc.network
- [ ] CDN setup for frontend assets
- [ ] DNS configuration for qbc.network

---

## PHASE 9: DOCUMENTATION (Priority: MEDIUM)

- [x] Whitepaper (`docs/WHITEPAPER.md` — 2680 lines)
- [x] Economics documentation (`docs/ECONOMICS.md`)
- [x] CLAUDE.md master development guide
- [ ] API documentation (OpenAPI/Swagger auto-generated from FastAPI)
- [ ] Developer SDK documentation
- [ ] Smart contract developer guide
- [ ] Aether Tree integration guide
- [ ] Deployment guide
- [ ] Contributing guidelines

---

## BUILD ORDER (Recommended Execution Sequence)

```
1. L1 Core Stabilization (PHASE 1)
   └── Fix remaining consensus/mining issues
   └── Add block sync protocol
   └── Add WebSocket endpoint

2. Aether Chat Backend (PHASE 3.4)
   └── POST /aether/chat endpoint
   └── Session management
   └── WebSocket streaming

3. Frontend Foundation (PHASE 4.1)
   └── Next.js 14 + Tailwind + design system
   └── API client + wallet integration

4. Landing Page (PHASE 4.2)
   └── Hero + particle effects
   └── Aether chat widget
   └── Feature sections

5. Aether Chat Page (PHASE 4.3)
   └── Full chat interface
   └── Knowledge graph viz
   └── Phi meter

6. Dashboard (PHASE 4.4)
   └── Mining + contracts + wallet tabs

7. QVM Hardening (PHASE 2)
   └── Quantum opcodes
   └── Cross-contract calls
   └── Test suite

8. Wallet + QVM Explorer (PHASE 4.5, 4.6)
   └── MetaMask integration
   └── Contract browser

9. Bridges (PHASE 5)
   └── ETH bridge first
   └── Then expand

10. QUSD (PHASE 6)
    └── Token + Reserve + Dashboard

11. Security + DevOps (PHASE 7, 8)
    └── Full test coverage
    └── Production deployment
```

---

*Last updated: 2026-02-12*
*Track progress here. Update status after every session.*
