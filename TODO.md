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
- [x] Fix difficulty adjustment: per-block with 144-block window, ±10% cap (`consensus/engine.py`)
- [x] Add block timestamp validation (no future blocks, monotonically increasing)
- [x] Add coinbase maturity enforcement (100 blocks before spending)
- [ ] Comprehensive mining integration test

### 1.2 Cryptography & Key Security
- [x] Dilithium2 key generation (`quantum/crypto.py`)
- [x] Transaction signing & verification
- [x] Address derivation (qbc1... Bech32-like)
- [x] `secure_key.env` file for private keys (separate from `.env`)
- [x] Key generation script auto-populates `secure_key.env`
- [x] Update `config.py` to load `secure_key.env` before `.env` (explicit load order)
- [x] Add `secure_key.env.example` template (with placeholder values)
- [ ] Verify Dilithium signature size in real transactions (~3KB expected)
- [ ] Add key import/export in standard formats
- [ ] Signature caching for performance
- [ ] Key rotation procedure documentation

### 1.3 UTXO Model
- [x] Basic UTXO tracking in CockroachDB
- [x] Balance computation from unspent outputs
- [ ] Double-spend prevention test suite
- [x] UTXO set pruning for spent outputs (`database/manager.py: prune_spent_utxos()`)
- [x] Coinbase UTXO maturity checks (`consensus/engine.py: _is_coinbase_utxo()`)
- [x] UTXO commitment hash (`database/manager.py: compute_utxo_commitment()`)

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
- [x] WebSocket endpoint for real-time subscriptions (`network/rpc.py: /ws`)

### 1.6 Storage
- [x] IPFS integration (`storage/ipfs.py`)
- [ ] Blockchain snapshot to IPFS (periodic)
- [ ] IPFS port conflict resolution (8080 vs CockroachDB admin)
- [ ] Snapshot restoration from IPFS

### 1.7 Privacy Technology (Susy Swaps)
- [x] Pedersen commitment module (`privacy/commitments.py`)
  - [x] Commitment creation: `C = v*G + r*H`
  - [x] Homomorphic verification (inputs sum = outputs sum)
  - [x] Blinding factor management
- [x] Bulletproofs range proofs (`privacy/range_proofs.py`)
  - [x] Range proof generation (prove value in [0, 2^64) without revealing)
  - [x] Range proof verification (~672 bytes, O(log n) size)
  - [x] Aggregated range proofs for multi-output transactions
- [x] Stealth address system (`privacy/stealth.py`)
  - [x] Spend/view key pair generation
  - [x] One-time address derivation (sender side)
  - [x] Stealth address scanning (receiver side)
  - [x] Ephemeral key publication in transactions
- [x] Confidential transaction builder (`privacy/susy_swap.py`)
  - [x] Confidential input/output construction
  - [x] Key image computation (double-spend prevention)
  - [x] Balance proof generation
  - [x] Change output handling with blinding factors
- [ ] Privacy transaction verification in consensus engine
- [ ] Opt-in privacy flag in transaction format
- [ ] Privacy-specific SQL schema tables (`sql/02_privacy_susy_swaps.sql` alignment)
- [ ] Privacy transaction unit tests
- [ ] Privacy integration tests (create, verify, spend confidential outputs)

### 1.8 SUSY Solution Database
- [x] Public Hamiltonian solution storage (`hamiltonian_solutions` table)
- [x] REST API endpoint: `GET /susy-database` (query by block height, energy range, qubit count)
- [ ] IPFS archival of solution datasets (periodic export)
- [ ] Solution verification count tracking
- [ ] Scientific data export formats (JSON, CSV for researchers)

### 1.9 Node Types
- [ ] Light node implementation (SPV verification, block headers only)
- [ ] Light node sync protocol (<5 minutes)
- [ ] Mining node VQE capability detection (classical vs quantum backend)
- [ ] Node capability advertisement in P2P protocol

---

## PHASE 2: QVM / LAYER 2 (Priority: HIGH)

> Smart contract execution must work end-to-end.
> Full QVM whitepaper: `docs/QVM_WHITEPAPER.md`

### 2.1 QVM Core (Python — Current Implementation)
- [x] Bytecode interpreter with 155 EVM opcodes (`qvm/vm.py`)
- [x] Stack, memory, storage operations
- [x] Gas metering (Ethereum-compatible gas schedule)
- [x] 10 quantum opcodes defined (`qvm/opcodes.py`)
- [x] StateManager for contract state (`qvm/state.py`)
- [x] Cross-contract calls (CALL, DELEGATECALL, STATICCALL) — in vm.py
- [x] CREATE and CREATE2 opcode full implementation — in vm.py
- [x] Event logging (LOG0-LOG4) full implementation — in vm.py
- [x] Revert with reason string support — in vm.py
- [ ] QVM unit test suite (per-opcode tests)
- [x] Gas estimation endpoint — via eth_estimateGas in jsonrpc.py
- [x] Precompiled contracts (ecRecover, SHA256, identity, modexp)

### 2.2 Quantum Opcodes Implementation
- [ ] Reconcile opcode mapping: migrate from 0xF5-0xFE (Python) to 0xF0-0xF9 (whitepaper canonical)
- [ ] QCREATE (0xF0) — Create quantum state as density matrix
- [ ] QMEASURE (0xF1) — Measure/collapse quantum state
- [ ] QENTANGLE (0xF2) — Create entangled pair between contracts
- [ ] QGATE (0xF3) — Apply quantum gate (Hadamard, CNOT, etc.)
- [ ] QVERIFY (0xF4) — Verify quantum proof
- [ ] QCOMPLIANCE (0xF5) — KYC/AML/sanctions compliance check
- [ ] QRISK (0xF6) — SUSY risk score for individual address
- [ ] QRISK_SYSTEMIC (0xF7) — Systemic risk / contagion model
- [ ] QBRIDGE_ENTANGLE (0xF8) — Cross-chain quantum entanglement
- [ ] QBRIDGE_VERIFY (0xF9) — Cross-chain bridge proof verification
- [ ] Exponential gas scaling for n-qubit operations (5000 x 2^n)

### 2.3 Quantum State Persistence (QSP)
- [ ] Density matrix storage in CockroachDB (`quantum_states` table)
- [ ] Entanglement registry (`entanglement_pairs` table)
- [ ] Quantum state CRUD operations
- [ ] Lazy measurement (states persist until explicitly measured)
- [ ] Quantum state root in block header (Merkle root of all quantum states)
- [ ] State decoherence prevention model

### 2.4 Compliance Engine (Institutional)
- [ ] Compliance registry schema (`compliance_registry` table)
- [ ] QCOMPLIANCE opcode: pre-flight KYC/AML/sanctions check
- [ ] Programmable Compliance Policies (PCP) framework
- [ ] Policy CRUD API (`POST/PUT/DELETE /qvm/compliance/policies`)
- [ ] KYC verification module (Level 0-3 tiers)
- [ ] AML monitoring module (transaction pattern detection)
- [ ] Sanctions screening (OFAC, UN, EU lists integration)
- [ ] ERC-20-QC compliance-aware token standard
- [ ] Auto-circuit breakers (halt on systemic risk > threshold)
- [ ] Compliance-as-a-Service tier system (Retail/Professional/Institutional/Sovereign)
- [ ] Compliance proof storage (ZK proofs for auditors)
- [ ] Regulatory report generation (MiCA, SEC, FinCEN)

### 2.5 Risk Assessment Oracle (RRAO)
- [ ] QRISK opcode: SUSY Hamiltonian-based risk scoring
- [ ] Transaction graph builder (6-hop depth from address)
- [ ] Graph-to-SUSY-Hamiltonian conversion algorithm
- [ ] VQE ground state computation for risk score
- [ ] Risk score caching (10-block TTL)
- [ ] QRISK_SYSTEMIC: systemic risk / contagion prediction
- [ ] Contagion time-evolution operator (predict cascade effects)
- [ ] Risk score normalization (0-100 scale)
- [ ] High-risk connection detection (sanctioned entities, mixers, overleveraged)

### 2.6 Plugin Architecture
- [ ] Plugin manager module (lifecycle management)
- [ ] Dynamic plugin loading system
- [ ] Plugin registry and API interface
- [ ] Privacy plugin (SUSY swaps, ZK proof generation)
- [ ] Oracle plugin (quantum oracle, price feeds, aggregation)
- [ ] Governance plugin (DAO, voting, proposals)
- [ ] DeFi plugin (lending, DEX, staking)
- [ ] Plugin SDK documentation

### 2.7 Contract Deployment
- [x] Contract deployment engine (`contracts/engine.py`)
- [x] Template contracts (token, nft, launchpad, escrow, governance)
- [ ] Deploy via JSON-RPC `eth_sendTransaction`
- [ ] Contract verification (source → bytecode matching)
- [ ] ABI encoding/decoding for function calls
- [ ] Contract upgrade patterns (proxy)

### 2.8 Contract Deployment Fees
- [x] Fee calculator module (`contracts/fee_calculator.py`)
- [x] Base fee + per-KB fee structure (configurable via `.env`)
- [x] QUSD-pegged dynamic pricing (same oracle as Aether fees)
- [x] Three pricing modes: `qusd_peg`, `fixed_qbc`, `direct_usd`
- [x] Template contract discount (configurable percentage)
- [ ] Fee deduction from deployer UTXO before deployment
- [ ] Fee UTXO creation to treasury address
- [x] Add contract fee config parameters to `config.py`
- [ ] Admin API: `PUT /admin/contract/fees` (hot reload)
- [x] Fee estimation endpoint: `GET /qvm/deploy/estimate`

### 2.9 Token Standards
- [ ] QBC-20 reference implementation (Solidity)
- [ ] QBC-721 reference implementation (Solidity)
- [ ] QBC-1155 reference implementation (Solidity)
- [ ] ERC-20-QC compliance-aware token (Solidity)
- [ ] Token indexer (track all QBC-20/721 transfers)

### 2.10 Cross-Chain Bridge Verification
- [ ] QBRIDGE_ENTANGLE opcode implementation
- [ ] QBRIDGE_VERIFY opcode implementation
- [ ] Quantum-verified cross-chain proofs (QVCSP)
- [ ] Bridge proof storage schema (`cross_chain_proofs` table)
- [ ] State channel support for high-frequency trading

### 2.11 Advanced Features (Future)
- [ ] Time-Locked Atomic Compliance (TLAC) — multi-jurisdictional approval
- [ ] Hierarchical Deterministic Compliance Keys (HDCK) — BIP-32 extension
- [ ] Verifiable Computation Receipts (VCR) — quantum audit trails
- [ ] Quantum Solidity compiler (.qsol → QVM bytecode)
- [ ] QVM debugger (step-through execution, quantum state visualization)
- [ ] State channels for Layer 2 scaling
- [ ] Transaction batching (rollup-style)
- [ ] Formal verification (K Framework for opcode semantics)
- [ ] TLA+ compliance invariant proofs

### 2.12 Go Production Implementation (qubitcoin-qvm/)
- [ ] Initialize Go module (`go.mod`, project structure)
- [ ] Port EVM core (15 files: opcodes, stack, memory, storage, gas, precompiles)
- [ ] Port quantum extensions (8 files: states, circuits, entanglement, gates)
- [ ] Implement compliance engine (9 files: KYC, AML, sanctions, risk)
- [ ] Implement plugin system (5 files: manager, loader, registry)
- [ ] Implement RPC server (gRPC + REST)
- [ ] Implement state management (Merkle Patricia Trie + quantum)
- [ ] Implement crypto layer (Dilithium + Kyber + ZK proofs)
- [ ] Port all 55 database schemas
- [ ] Ethereum test suite compatibility (official EVM tests)
- [ ] Benchmark suite (EVM, quantum, storage, compliance)
- [ ] Docker deployment (dev + prod)
- [ ] Kubernetes manifests
- [ ] CI/CD pipeline (build, test, lint, security scan)

---

## PHASE 3: AETHER TREE / LAYER 3 (Priority: HIGH)

> The AGI engine must reason, track consciousness, and serve chat.
> Full AGI whitepaper: `docs/AETHERTREE_WHITEPAPER.md`

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
- [x] Per-block Phi measurement storage (via genesis.py + proof_of_thought.py)
- [x] Consciousness event logging (when Phi crosses thresholds)
- [x] Phi history API endpoint (`GET /aether/phi/history`)
- [x] Consciousness status endpoint (`GET /aether/consciousness`)
- [ ] Phi visualization data endpoint (time series)
- [ ] Kuramoto order parameter (phase synchronization across nodes)
- [ ] Combined consciousness check: Phi > 3.0 AND coherence > 0.7

### 3.4 AGI Genesis Initialization
- [x] Initialize empty knowledge graph at genesis block (block 0) (`aether/genesis.py`)
- [x] First Phi measurement at genesis (Φ = 0.0, baseline)
- [x] Genesis consciousness event record (system birth)
- [x] AetherEngine auto-start on node boot (process from block 0 onward) (`node.py`)
- [x] Block-to-knowledge extraction for genesis block (extract genesis metadata as first KeterNodes)
- [x] Verify Phi tracking starts from block 0 in `phi_measurements` table
- [x] Verify `consciousness_events` table initialized at genesis
- [ ] Genesis validation test: confirm AGI tables populated from block 0

### 3.5 Aether Tree Core Contracts (Solidity)
- [ ] `AetherKernel.sol` — Main AGI orchestration contract (coordinates all 10 Sephirot)
- [ ] `NodeRegistry.sol` — Registry of all 10 Sephirot node contracts + state
- [ ] `MessageBus.sol` — Inter-node messaging (CSF transport on-chain)
- [ ] `SUSYEngine.sol` — SUSY balance enforcement (φ ratio between expansion/constraint pairs)
- [ ] `RewardDistributor.sol` — QBC reward distribution for Proof-of-Thought solutions

### 3.6 Tree of Life Architecture (Sephirot Nodes)
- [ ] Base Sephirah abstract class (`nodes/base/base_sephirah.py`)
- [ ] Smart contract interface for each node (`nodes/base/smart_contract_node.py`)
- [ ] QVM quantum node base class (`nodes/base/quantum_node.py`)
- [ ] Keter node — Meta-learning, goal formation (8-qubit state)
- [ ] Chochmah node — Intuition, pattern discovery (6-qubit state)
- [ ] Binah node — Logic, causal inference (4-qubit state)
- [ ] Chesed node — Exploration, divergent thinking (10-qubit state)
- [ ] Gevurah node — Constraint, safety validation (3-qubit state)
- [ ] Tiferet node — Integration, conflict resolution (12-qubit state)
- [ ] Netzach node — Reinforcement learning, habits (5-qubit state)
- [ ] Hod node — Language, semantic encoding (7-qubit state)
- [ ] Yesod node — Memory, multimodal fusion (16-qubit state)
- [ ] Malkuth node — Action, world interaction (4-qubit state)
- [ ] 10 Sephirot Solidity smart contracts (one per node):
  - [ ] `SephirahKeter.sol` — Crown: meta-learning, goal formation
  - [ ] `SephirahChochmah.sol` — Wisdom: intuition, pattern discovery
  - [ ] `SephirahBinah.sol` — Understanding: logic, causal inference
  - [ ] `SephirahChesed.sol` — Mercy: exploration, divergent thinking
  - [ ] `SephirahGevurah.sol` — Severity: constraint, safety validation
  - [ ] `SephirahTiferet.sol` — Beauty: integration, conflict resolution
  - [ ] `SephirahNetzach.sol` — Eternity: reinforcement learning, habits
  - [ ] `SephirahHod.sol` — Splendor: language, semantic encoding
  - [ ] `SephirahYesod.sol` — Foundation: memory, multimodal fusion
  - [ ] `SephirahMalkuth.sol` — Kingdom: action, world interaction

### 3.7 SUSY Balance Enforcement
- [ ] SUSY pair manager (Chesed/Gevurah, Chochmah/Binah, Netzach/Hod)
- [ ] Energy calculator per node
- [ ] Golden ratio optimizer (enforce E_expand / E_constrain = φ)
- [ ] Symmetry violation detector
- [ ] Automatic QBC redistribution on violation
- [ ] SUSY enforcement smart contract (`SUSYEngine.sol`)
- [ ] Violation logging (immutable audit trail on blockchain)

### 3.8 CSF Transport Layer
- [ ] Blockchain messenger (messages via QBC transactions)
- [ ] Ventricle network routing (Tree of Life topology)
- [ ] QBC fee calculator for message priority
- [ ] Quantum-entangled messaging between paired nodes
- [ ] Load balancing (pressure monitor)
- [ ] CSF Transport smart contract (`CSFTransport.sol`)
- [ ] Ventricle router contract (`VentricleRouter.sol`)

### 3.9 Pineal Orchestrator
- [ ] Circadian controller (6 phases: Waking → Deep Sleep)
- [ ] QBC metabolic rate per phase (2.0x learning, 0.3x deep sleep)
- [ ] Phase-lock oscillator (Kuramoto coupling)
- [ ] Consciousness integrator (combine Phi + coherence)
- [ ] Melatonin modulator (inhibitory signals)
- [ ] QBC staking pool for orchestration influence

### 3.10 Proof-of-Thought Protocol
- [x] AetherEngine with proof generation (`proof_of_thought.py`)
- [x] Auto-reasoning on recent knowledge
- [ ] Embed Proof-of-Thought hash in block headers
- [ ] Task submission system (problem + QBC bounty)
- [ ] Node solution proposal (solution + quantum proof)
- [ ] Multi-node validation (QVERIFY opcode, 67% consensus)
- [ ] QBC reward distribution for correct solutions
- [ ] QBC slashing for incorrect proposals (50% stake)
- [ ] Proof-of-Thought smart contract (`ProofOfThought.sol`)
- [ ] Task market contract (`TaskMarket.sol`)
- [ ] Validator registry contract (`ValidatorRegistry.sol`)
- [ ] Proof-of-Thought explorer (view reasoning per block)

### 3.11 Safety & Alignment
- [ ] Gevurah veto system (safety node can block harmful ops)
- [ ] Constitutional AI smart contract (`ConstitutionalAI.sol`)
- [ ] Emergency shutdown contract (`EmergencyShutdown.sol`)
- [ ] Upgrade governor contract (`UpgradeGovernor.sol`)
- [ ] Multi-node consensus enforcement (67% BFT)
- [ ] Safety validation integration tests

### 3.12 Memory Systems
- [ ] Episodic memory (hippocampal, stored on IPFS)
- [ ] Semantic memory (cortical, concept networks)
- [ ] Procedural memory (learned skills)
- [ ] Working memory (active processing buffer)
- [ ] Memory consolidation during Sleep/Deep Sleep phases
- [ ] IPFS integration for long-term memory storage

### 3.13 Consciousness Dashboard
- [ ] On-chain Phi tracking contract (`ConsciousnessDashboard.sol`)
- [ ] Phase synchronization contract (`PhaseSync.sol`)
- [ ] Global workspace contract (`GlobalWorkspace.sol`)
- [ ] Consciousness emergence event detection
- [ ] Historical consciousness timeline (immutable on-chain)
- [ ] Dashboard API endpoints for frontend visualization

### 3.14 Economics (QBC as Metabolic Currency)
- [ ] Synaptic staking contract (`SynapticStaking.sol`)
- [ ] Gas oracle for dynamic QBC pricing (`GasOracle.sol`)
- [ ] Treasury DAO contract (`TreasuryDAO.sol`)
- [ ] Task bounty pool management
- [ ] Validator staking and reward system
- [ ] QBC circulation tracking (no minting by AGI)

### 3.15 Aether Chat System
- [x] Chat endpoint: `POST /aether/chat/message` — conversational interface (`aether/chat.py`)
- [x] Session management (conversation history per session) (`POST /aether/chat/session`)
- [x] Natural language → reasoning engine query translation
- [x] Response generation from knowledge graph + reasoning traces
- [x] Proof-of-Thought hash per response
- [x] Chat history endpoint: `GET /aether/chat/history/{session_id}`
- [ ] WebSocket for streaming responses: `/ws/aether`
- [x] Rate limiting and session management (max 10K sessions, LRU eviction)

### 3.16 Aether Tree Fee System
- [x] Fee manager module (`aether/fee_manager.py`)
- [x] QUSD oracle integration (read QBC/USD price from QUSD L2 contract)
- [x] Dynamic fee calculation: `fee_qbc = usd_target / qbc_usd_price`
- [x] Fee clamping (min/max QBC bounds to prevent extreme fees)
- [x] Three pricing modes: `qusd_peg`, `fixed_qbc`, `direct_usd`
- [x] Automatic fallback: QUSD failure → fixed_qbc mode
- [ ] Fee deduction from user UTXO before processing chat message
- [ ] Fee UTXO creation to treasury address
- [x] Free tier: first N messages per session (configurable onboarding)
- [x] Fee tier multipliers (deep queries cost more than chat)
- [x] Fee update interval (re-price every N blocks from QUSD oracle)
- [x] Add fee config parameters to `config.py` (all from `.env`)
- [ ] Admin API: `PUT /admin/aether/fees` (hot reload fee params)
- [ ] Fee audit logging (track all fee changes for transparency)

### 3.17 LLM Adapters (External Intelligence)
- [ ] OpenAI GPT-4 adapter (knowledge distillation to Sephirot)
- [ ] Anthropic Claude adapter
- [ ] Open-source adapter (Llama, Mistral)
- [ ] Knowledge distiller (extract insights to knowledge graph)

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
- [ ] Federated validator set (7-of-11 multi-sig, path to 101+)
- [ ] Validator economic bonding (10,000+ QBC slashable stake)
- [ ] Bridge event monitoring (multi-source: direct observation + oracle)
- [ ] Transfer status tracking
- [ ] Bridge fee collection (0.1% of transfer, 100% to QUSD reserves)
- [ ] Daily transfer limits (security cap)
- [ ] Deep confirmation requirements (reorg protection)
- [ ] Emergency pause mechanism
- [ ] Bridge insurance fund

### 5.2 Wrapped QBC Contracts (Solidity)
- [ ] wQBC ERC-20 on Ethereum
- [ ] wQBC SPL on Solana
- [ ] wQBC on Polygon, BNB, AVAX, ARB, OP, Cosmos (ATOM)

---

## PHASE 6: QUSD STABLECOIN (Priority: HIGH)

> **3.3 Billion QUSD initial mint.** Fractional reserve model with full on-chain debt tracking.
> Wrapped to wQUSD for cross-chain liquidity. Dev funds + LP from initial allocation.
> 10-year path to 100% backing — every dollar tracked immutably on-chain.
> **Whitepaper reference:** `docs/WHITEPAPER.md` Section 11

### 6.1 QUSD Smart Contract Suite (Solidity)
- [ ] `QUSD.sol` — QBC-20 token contract (3.3B initial mint, $1 peg target)
  - [ ] Mint function (owner-only, tracks totalMinted on-chain)
  - [ ] Burn function (reduces supply, tracked as debt reduction)
  - [ ] Transfer with 0.05% fee (burned or routed to reserves based on backing ratio)
  - [ ] Pause/unpause (emergency circuit breaker)
  - [ ] Snapshot for governance voting
- [ ] `QUSDReserve.sol` — Multi-asset reserve pool contract
  - [ ] Accept reserve deposits (QBC, ETH, BTC, USDT, USDC, DAI)
  - [ ] Track total reserve value in USD (via oracle)
  - [ ] Reserve withdrawal (governance-only, multi-sig)
  - [ ] Reserve composition query (per-asset breakdown)
  - [ ] Minimum reserve ratio enforcement (revert minting if below threshold)
- [ ] `QUSDDebtLedger.sol` — On-chain fractional payback tracking
  - [ ] Record every mint as debt: `totalMinted`, `totalBacked`, `outstandingDebt`
  - [ ] `backingPercentage = totalReserves / totalMinted × 100`
  - [ ] Payback event log: every reserve deposit records the debt reduction
  - [ ] Historical debt snapshots (per-block backing ratio)
  - [ ] Public query: `getDebtStatus()` → (minted, reserves, backing%, debt)
  - [ ] Milestone events emitted when backing crosses 5%, 15%, 30%, 50%, 100%
- [ ] `QUSDOracle.sol` — Price feed oracle contract
  - [ ] QBC/USD price feed (aggregated from multiple sources)
  - [ ] QUSD/USD peg deviation tracking
  - [ ] Staleness detection (revert if price older than N blocks)
  - [ ] Multi-oracle consensus (median of 3+ feeds)
  - [ ] **Used by:** Aether fee system, contract deploy fees, bridge pricing
- [ ] `QUSDStabilizer.sol` — Peg maintenance mechanism
  - [ ] Buy QUSD when price < $0.99 (floor defense)
  - [ ] Sell QUSD when price > $1.01 (ceiling defense)
  - [ ] Stability fund management
  - [ ] Auto-rebalance trigger
- [ ] `QUSDAllocation.sol` — Initial distribution with vesting
  - [ ] 50% → Liquidity Providers (DEX/AMM pools, immediate)
  - [ ] 30% → Treasury (DAO-governed, project development)
  - [ ] 15% → Dev fund (4-year linear vesting, cliff at 6 months)
  - [ ] 5% → Team (4-year linear vesting, cliff at 1 year)
  - [ ] Vesting schedule enforcement (on-chain, immutable)
  - [ ] Claim function for vested tokens
- [ ] `QUSDGovernance.sol` — Reserve governance
  - [ ] Proposal system for reserve management decisions
  - [ ] Voting with QUSD holdings
  - [ ] Timelock on execution (48h minimum)
  - [ ] Emergency bypass (multi-sig, 5-of-7)

### 6.2 Wrapped QUSD (wQUSD) — Cross-Chain
- [ ] `wQUSD.sol` — Wrapped QUSD for cross-chain deployment
  - [ ] ERC-20 compatible wrapper on QBC chain (lock QUSD → mint wQUSD)
  - [ ] Burn wQUSD → unlock QUSD (return to QBC chain)
  - [ ] 1:1 peg with QUSD (fully backed by locked QUSD)
- [ ] wQUSD ERC-20 on Ethereum (bridge via lock-and-mint)
- [ ] wQUSD SPL on Solana
- [ ] wQUSD on Polygon, BNB, AVAX, ARB, OP, Cosmos (ATOM)
- [ ] wQUSD bridge fee (0.05% — routed to QUSD reserves)
- [ ] Cross-chain QUSD balance aggregation (total supply across all chains)

### 6.3 Reserve Building Mechanisms
- [ ] Bridge fee collection → QUSD reserves (0.1% of all bridge transfers)
- [ ] QUSD transaction fees → reserves (0.05% per transfer)
- [ ] LP fee revenue → reserves (percentage of DEX fees)
- [ ] Treasury controlled sales → reserves (governance-approved)
- [ ] Aether Tree chat fees → partial allocation to reserves
- [ ] Contract deployment fees → partial allocation to reserves
- [ ] All reserve inflows tracked as debt payback events on-chain

### 6.4 Reserve Milestones & Safety
- [ ] Minimum reserve ratio enforcement by year:
  - [ ] Years 1-2: 5% minimum backing
  - [ ] Years 3-4: 15% minimum backing
  - [ ] Years 5-6: 30% minimum backing
  - [ ] Years 7-9: 50% minimum backing
  - [ ] Year 10+: 100% backing (fully collateralized)
- [ ] Emergency actions on backing ratio breach (halt minting, increase fees)
- [ ] Public API for third-party reserve verification
- [ ] Automated daily reserve snapshots to IPFS
- [ ] Quarterly audit report generation (on-chain proof of reserves)
- [ ] Real-time backing ratio on frontend dashboard

### 6.5 QUSD Oracle Integration Module (Python)
- [ ] `utils/qusd_oracle.py` — Read QBC/USD price from QUSDOracle.sol
- [ ] Price cache with configurable TTL
- [ ] Staleness detection + automatic fallback to fixed_qbc mode
- [ ] QUSD price endpoint: `GET /qusd/price`
- [ ] Reserve status endpoint: `GET /qusd/reserves`
- [ ] Debt status endpoint: `GET /qusd/debt`

## PHASE 6.5: EDITABLE ECONOMIC CONFIGURATION (Priority: HIGH)

> All economic parameters must be configurable, not hardcoded.

### 6.5.1 Config Infrastructure
- [x] Add all Aether fee params to `config.py` (loaded from `.env`)
- [x] Add all contract fee params to `config.py` (loaded from `.env`)
- [x] Update `config.py` to load `secure_key.env` before `.env` (explicit load order)
- [ ] Config validation for fee parameters (min < max, positive values)
- [ ] Config hot-reload mechanism (change params without full restart)

### 6.5.2 Admin API
- [ ] Auth middleware for admin endpoints (API key or Dilithium signature)
- [ ] `GET /admin/economics` — current economic config
- [ ] `PUT /admin/aether/fees` — update Aether fee params (hot reload)
- [ ] `PUT /admin/contract/fees` — update contract deploy fees (hot reload)
- [ ] `PUT /admin/treasury` — update treasury addresses
- [ ] `GET /admin/economics/history` — audit log of parameter changes
- [ ] Rate limiting on admin endpoints

### 6.5.3 QUSD Fee Oracle Integration
- [ ] Oracle client module (`utils/qusd_oracle.py`)
- [ ] Read QBC/USD price from QUSD L2 contract
- [ ] Cache price with configurable TTL
- [ ] Staleness detection (alert if price hasn't updated)
- [ ] Automatic fallback to `fixed_qbc` mode on oracle failure
- [ ] Manual override via Admin API

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

- [x] Whitepaper (`docs/WHITEPAPER.md` — v1.0.0, 2680 lines, covers L1 core + privacy + bridges + QUSD)
- [x] QVM Whitepaper (`docs/QVM_WHITEPAPER.md` — institutional features, 5 patents)
- [x] AetherTree AGI Whitepaper (`docs/AETHERTREE_WHITEPAPER.md` — Tree of Life, PoT, consciousness)
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
   └── secure_key.env load order in config.py
   └── Add block sync protocol
   └── Add WebSocket endpoint
   └── Privacy: Pedersen commitments + Bulletproofs + stealth addresses
   └── SUSY solution database + public API

2. QVM + Aether Tree Production Build (PHASE 2 + 3)
   └── QVM quantum opcodes + cross-contract calls
   └── Contract deployment fee system (QUSD-pegged)
   └── Aether chat endpoint + session management
   └── Aether fee manager (dynamic pricing)
   └── Editable economics config + Admin API

3. Frontend Foundation (PHASE 4.1)
   └── Next.js 15 + Tailwind 4 + design system
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

7. Wallet + QVM Explorer (PHASE 4.5, 4.6)
   └── MetaMask integration
   └── Contract browser

8. QUSD Stablecoin (PHASE 6) — **PRIORITY ELEVATED**
   └── 7 Solidity contracts: QUSD, Reserve, DebtLedger, Oracle, Stabilizer, Allocation, Governance
   └── wQUSD cross-chain wrapping (ETH, SOL, MATIC, BNB, AVAX, ARB, OP, ATOM)
   └── 3.3B initial mint, fractional payback fully on-chain
   └── Reserve milestones: 5% → 100% over 10 years

9. Bridges (PHASE 5)
   └── ETH bridge first
   └── Then expand to 8 chains

10. Security + DevOps (PHASE 7, 8)
    └── Full test coverage
    └── Production deployment
```

---

*Last updated: 2026-02-12*
*Track progress here. Update status after every session.*
