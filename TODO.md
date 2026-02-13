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
- [x] Comprehensive mining integration test (`test_mining_and_utxo.py` — block model, coinbase, reward, validation)

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
- [x] Double-spend prevention test suite (`test_mining_and_utxo.py: TestDoubleSpendPrevention` — 6 tests)
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
- [x] Privacy transaction unit tests (`test_privacy_advanced.py` — 18 tests: commitments, stealth, range proofs, susy swap)
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
- [x] QVM unit test suite (per-opcode tests) — 52 tests in test_qvm.py
- [x] Gas estimation endpoint — via eth_estimateGas in jsonrpc.py
- [x] Precompiled contracts (ecRecover, SHA256, identity, modexp)

### 2.2 Quantum Opcodes Implementation
- [ ] Reconcile opcode mapping: migrate from 0xD0-0xD9 (Python) to 0xF0-0xF9 (whitepaper canonical)
- [ ] QCREATE (0xF0) — Create quantum state as density matrix
- [x] QMEASURE (0xD1/0xF1) — Measure/collapse quantum state (deterministic from block context)
- [x] QENTANGLE (0xD2/0xF2) — Create entangled pair between contracts
- [x] QGATE (0xD0/0xF3) — Apply quantum gate (H,X,Y,Z,CNOT,RX,RY,RZ)
- [ ] QVERIFY (0xF4) — Verify quantum proof
- [ ] QCOMPLIANCE (0xF5) — KYC/AML/sanctions compliance check
- [ ] QRISK (0xF6) — SUSY risk score for individual address
- [ ] QRISK_SYSTEMIC (0xF7) — Systemic risk / contagion model
- [ ] QBRIDGE_ENTANGLE (0xF8) — Cross-chain quantum entanglement
- [ ] QBRIDGE_VERIFY (0xF9) — Cross-chain bridge proof verification
- [x] QSUPERPOSE (0xD3) — Hadamard superposition
- [x] QVQE (0xD4) — Execute VQE optimization
- [x] QHAMILTONIAN (0xD5) — Generate SUSY Hamiltonian from seed
- [x] QENERGY (0xD6) — Compute energy expectation value
- [x] QPROOF (0xD7) — Validate quantum proof (energy vs difficulty)
- [x] QFIDELITY (0xD8) — Compute state fidelity between quantum states
- [x] QDILITHIUM (0xD9) — Verify Dilithium signature
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
- [x] QBC-20 reference implementation (`tokens/QBC20.sol`)
- [x] QBC-721 reference implementation (`tokens/QBC721.sol`)
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
- [x] Block-to-knowledge extraction (`knowledge_extractor.py` — block metadata, tx patterns, mining, temporal, difficulty trends)
- [x] Knowledge graph pruning (`knowledge_graph.py: prune_low_confidence()` — threshold-based, axiom protection)
- [x] Graph query API (`knowledge_graph.py: find_by_type/content/recent, get_edge_types_for_node` + REST endpoints)
- [x] Knowledge graph export (`knowledge_graph.py: export_json_ld()` — JSON-LD with @context, @graph, stats + REST endpoint)

### 3.2 Reasoning Engine
- [x] Deductive reasoning (modus ponens)
- [x] Inductive reasoning (pattern generalization)
- [x] Abductive reasoning (hypothesis generation)
- [x] Chain-of-thought reasoning (`reasoning.py: chain_of_thought()` — multi-step iterative traces)
- [ ] Reasoning over user queries (natural language → knowledge graph query)
- [x] Contradiction resolution (`reasoning.py: resolve_contradiction()` — evidence-weighted, loser penalized)
- [x] Confidence propagation (`knowledge_graph.py: propagate_confidence()` — iterative support/contradict)

### 3.3 Phi Calculator (Consciousness)
- [x] Integration score computation
- [x] Differentiation score (Shannon entropy)
- [x] Combined Phi metric
- [x] PHI_THRESHOLD = 3.0
- [x] Per-block Phi measurement storage (via genesis.py + proof_of_thought.py)
- [x] Consciousness event logging (when Phi crosses thresholds)
- [x] Phi history API endpoint (`GET /aether/phi/history`)
- [x] Consciousness status endpoint (`GET /aether/consciousness`)
- [x] Phi visualization data endpoint (`rpc.py: GET /aether/phi/timeseries` — blocks, phi_values, is_conscious arrays)
- [x] Kuramoto order parameter (phase synchronization across nodes) — `sephirot.py: get_coherence()`
- [x] Combined consciousness check: Phi > 3.0 AND coherence > 0.7 — `pineal.py: _check_consciousness()`

### 3.4 AGI Genesis Initialization
- [x] Initialize empty knowledge graph at genesis block (block 0) (`aether/genesis.py`)
- [x] First Phi measurement at genesis (Φ = 0.0, baseline)
- [x] Genesis consciousness event record (system birth)
- [x] AetherEngine auto-start on node boot (process from block 0 onward) (`node.py`)
- [x] Block-to-knowledge extraction for genesis block (extract genesis metadata as first KeterNodes)
- [x] Verify Phi tracking starts from block 0 in `phi_measurements` table
- [x] Verify `consciousness_events` table initialized at genesis
- [x] Genesis validation test (`test_genesis_validation.py` — 11 tests: axioms, confidence, edges, content types, Phi baseline)

### 3.5 Aether Tree Core Contracts (Solidity)
- [x] `AetherKernel.sol` — Main AGI orchestration contract (coordinates all 10 Sephirot)
- [x] `NodeRegistry.sol` — Registry of all 10 Sephirot node contracts + state
- [x] `MessageBus.sol` — Inter-node messaging (CSF transport on-chain)
- [x] `SUSYEngine.sol` — SUSY balance enforcement (φ ratio between expansion/constraint pairs)
- [x] `RewardDistributor.sol` — QBC reward distribution for Proof-of-Thought solutions

### 3.6 Tree of Life Architecture (Sephirot Nodes)
- [x] Base Sephirah abstract class (`sephirot_nodes.py: BaseSephirah` — ABC with process/message/status)
- [x] Smart contract interface for each node (`sephirot_nodes.py` — role-based with CSF messaging)
- [x] QVM quantum node base class (`sephirot_nodes.py: BaseSephirah` — quantum state placeholder per node)
- [x] Keter node — Meta-learning, goal formation (8-qubit state) — `sephirot_nodes.py: KeterNode`
- [x] Chochmah node — Intuition, pattern discovery (6-qubit state) — `sephirot_nodes.py: ChochmahNode`
- [x] Binah node — Logic, causal inference (4-qubit state) — `sephirot_nodes.py: BinahNode`
- [x] Chesed node — Exploration, divergent thinking (10-qubit state) — `sephirot_nodes.py: ChesedNode`
- [x] Gevurah node — Constraint, safety validation (3-qubit state) — `sephirot_nodes.py: GevurahNode`
- [x] Tiferet node — Integration, conflict resolution (12-qubit state) — `sephirot_nodes.py: TiferetNode`
- [x] Netzach node — Reinforcement learning, habits (5-qubit state) — `sephirot_nodes.py: NetzachNode`
- [x] Hod node — Language, semantic encoding (7-qubit state) — `sephirot_nodes.py: HodNode`
- [x] Yesod node — Memory, multimodal fusion (16-qubit state) — `sephirot_nodes.py: YesodNode`
- [x] Malkuth node — Action, world interaction (4-qubit state) — `sephirot_nodes.py: MalkuthNode`
- [x] 10 Sephirot Solidity smart contracts (one per node):
  - [x] `SephirahKeter.sol` — Crown: meta-learning, goal formation
  - [x] `SephirahChochmah.sol` — Wisdom: intuition, pattern discovery
  - [x] `SephirahBinah.sol` — Understanding: logic, causal inference
  - [x] `SephirahChesed.sol` — Mercy: exploration, divergent thinking
  - [x] `SephirahGevurah.sol` — Severity: constraint, safety validation
  - [x] `SephirahTiferet.sol` — Beauty: integration, conflict resolution
  - [x] `SephirahNetzach.sol` — Eternity: reinforcement learning, habits
  - [x] `SephirahHod.sol` — Splendor: language, semantic encoding
  - [x] `SephirahYesod.sol` — Foundation: memory, multimodal fusion
  - [x] `SephirahMalkuth.sol` — Kingdom: action, world interaction

### 3.7 SUSY Balance Enforcement
- [x] SUSY pair manager (Chesed/Gevurah, Chochmah/Binah, Netzach/Hod) — `sephirot.py: SUSY_PAIRS`
- [x] Energy calculator per node — `sephirot.py: SephirahState.energy`
- [x] Golden ratio optimizer (enforce E_expand / E_constrain = φ) — `sephirot.py: enforce_susy_balance()`
- [x] Symmetry violation detector — `sephirot.py: check_susy_balance()`
- [x] Automatic QBC redistribution on violation — `sephirot.py: enforce_susy_balance()`
- [x] SUSY enforcement smart contract (`SUSYEngine.sol`)
- [x] Violation logging (immutable audit trail on blockchain) — `sephirot.py: SUSYViolation dataclass`

### 3.8 CSF Transport Layer
- [x] Blockchain messenger (messages via QBC transactions) — `csf_transport.py: CSFMessage`
- [x] Ventricle network routing (Tree of Life topology) — `csf_transport.py: TOPOLOGY + BFS routing`
- [x] QBC fee calculator for message priority — `csf_transport.py: priority_qbc ordering`
- [ ] Quantum-entangled messaging between paired nodes
- [ ] Load balancing (pressure monitor)
- [x] CSF Transport smart contract (`MessageBus.sol` — covers CSF transport on-chain)
- [ ] Ventricle router contract (`VentricleRouter.sol`)

### 3.9 Pineal Orchestrator
- [x] Circadian controller (6 phases: Waking → Deep Sleep) — `pineal.py: CircadianPhase + PHASE_CYCLE`
- [x] QBC metabolic rate per phase (2.0x learning, 0.3x deep sleep) — `pineal.py: METABOLIC_RATES`
- [x] Phase-lock oscillator (Kuramoto coupling) — `sephirot.py: get_coherence()`
- [x] Consciousness integrator (combine Phi + coherence) — `pineal.py: _check_consciousness()`
- [ ] Melatonin modulator (inhibitory signals)
- [ ] QBC staking pool for orchestration influence

### 3.10 Proof-of-Thought Protocol
- [x] AetherEngine with proof generation (`proof_of_thought.py`)
- [x] Auto-reasoning on recent knowledge
- [ ] Embed Proof-of-Thought hash in block headers
- [x] Task submission system (`task_protocol.py: TaskMarket` — submit with QBC bounty, claim, solve)
- [x] Node solution proposal (`task_protocol.py: submit_solution()` — solution + hash)
- [x] Multi-node validation (`task_protocol.py: ProofOfThoughtProtocol.validate_solution()` — stake-weighted 67% BFT)
- [x] QBC reward distribution for correct solutions (`task_protocol.py: finalize_task()`)
- [x] QBC slashing for incorrect proposals (`task_protocol.py: ValidatorRegistry.slash()` — 50% stake)
- [x] Proof-of-Thought smart contract (`ProofOfThought.sol`)
- [x] Task market contract (`TaskMarket.sol`)
- [x] Validator registry contract (`ValidatorRegistry.sol`)
- [x] Validator registry Python module (`task_protocol.py: ValidatorRegistry` — stake/unstake/slash/reward)
- [ ] Proof-of-Thought explorer (view reasoning per block)

### 3.11 Safety & Alignment
- [x] Gevurah veto system (`safety.py: GevurahVeto` — threat evaluation, constitutional principles, veto records)
- [x] Constitutional AI smart contract (`ConstitutionalAI.sol`)
- [x] Emergency shutdown contract (`EmergencyShutdown.sol`)
- [x] Upgrade governor contract (`UpgradeGovernor.sol`)
- [x] Multi-node consensus enforcement (`safety.py: MultiNodeConsensus` — 67% BFT, stake-weighted voting)
- [x] Safety Manager (`safety.py: SafetyManager` — Gevurah + consensus + emergency shutdown)
- [x] Safety validation integration tests (`test_integration.py: TestSafetyIntegration` — veto, consensus, shutdown)

### 3.12 Memory Systems
- [x] Episodic memory (hippocampal, stored on IPFS) — `memory.py: EpisodicMemory`
- [x] Semantic memory (cortical, concept networks) — `memory.py: SemanticMemory` with Hebbian associations
- [x] Procedural memory (learned skills) — `memory.py: ProceduralMemory` with proficiency tracking
- [x] Working memory (active processing buffer) — `memory.py: WorkingMemory` (Miller's 7±2 capacity)
- [x] Memory consolidation during Sleep/Deep Sleep phases — `memory.py: MemoryManager.consolidate()`
- [ ] IPFS integration for long-term memory storage

### 3.13 Consciousness Dashboard
- [x] On-chain Phi tracking contract (`ConsciousnessDashboard.sol`)
- [x] Phase synchronization contract (`PhaseSync.sol`)
- [x] Global workspace contract (`GlobalWorkspace.sol`)
- [x] Consciousness emergence event detection (`consciousness.py: ConsciousnessDashboard` — emergence/loss events)
- [x] Historical consciousness timeline (`consciousness.py: get_phi_history() + get_events()`)
- [x] Dashboard API data provider (`consciousness.py: get_dashboard_data() + get_consciousness_status()`)
- [x] Dashboard REST API endpoints (`rpc.py: /aether/consciousness/dashboard`, `/trend`, `/events`, `/sephirot`)

### 3.14 Economics (QBC as Metabolic Currency)
- [x] Synaptic staking contract (`SynapticStaking.sol`)
- [x] Gas oracle for dynamic QBC pricing (`GasOracle.sol`)
- [x] Treasury DAO contract (`TreasuryDAO.sol`)
- [x] Task bounty pool management (`task_protocol.py: TaskMarket` — bounty lifecycle)
- [x] Validator staking and reward system (`task_protocol.py: ValidatorRegistry` — stake/unstake/slash/reward)
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
- [x] Initialize Next.js 16 project with React 19 + TypeScript 5.9 (pnpm)
- [x] Configure TailwindCSS 4 + Framer Motion
- [x] Set up "Quantum Error" design system (colors, typography, components)
- [x] Font loading (Space Grotesk, Inter, JetBrains Mono via Google Fonts CDN)
- [x] Set up Zustand stores for state management (`stores/chain-store.ts`, `wallet-store.ts`)
- [x] Set up TanStack Query for server state / API caching (`app/providers.tsx`)
- [x] Set up API client library (REST + WebSocket) (`lib/api.ts`, `lib/websocket.ts`)
- [x] MetaMask/ethers.js v6 wallet integration library (`lib/wallet.ts`)
- [x] Three.js + React Three Fiber setup (particle effects) (`components/visualizations/`)
- [x] ESLint + Prettier + TypeScript strict
- [ ] Vitest + Playwright test setup
- [x] Environment configuration (NEXT_PUBLIC_* vars) (`.env.local`)
- [ ] Vercel deployment config (vercel.json, custom domain qbc.network)
- [x] Path aliases (`@/` → `src/`) (`tsconfig.json`)

### 4.2 Landing Page (`/`)
- [x] Hero section with quantum particle field animation (Three.js/R3F)
- [x] Phi-spiral particle distribution
- [x] Embedded Aether Chat widget (floating chatbot)
- [x] Live chain stats bar (block height, Phi, knowledge nodes, difficulty, peers)
- [x] "Quantum Blockchain" feature section
- [x] "Quantum Virtual Machine" feature section
- [x] "Aether Tree AGI" feature section
- [x] Call-to-action buttons (Talk to Aether, Open Dashboard, Connect Wallet)
- [ ] Footer with links, social, legal
- [x] Mobile responsive design
- [ ] Performance optimization (lazy loading, image optimization)

### 4.3 Aether Chat Page (`/aether`)
- [x] Full-page chat interface (ChatGPT/Grok-like layout)
- [x] Message input with quantum-themed styling
- [ ] Streaming response display (typewriter effect)
- [ ] Conversation sidebar (session list, new chat)
- [ ] Knowledge graph 3D visualization panel (Three.js force-directed)
- [x] Phi consciousness meter (animated gauge) — sidebar panel
- [x] Reasoning trace accordion (expandable per response)
- [x] Proof-of-Thought hash per response
- [ ] Local storage for conversation history
- [x] Keyboard shortcuts (Enter to send)

### 4.4 Dashboard (`/dashboard`)
- [x] Overview tab (QBC balance, block height, supply, difficulty, Phi, knowledge)
- [x] Mining tab (status, blocks mined, VQE energy, alignment score)
- [x] Aether tab (consciousness gauge, knowledge nodes/edges, integration, differentiation)
- [x] Network tab (peers, mempool, chain ID, block height)
- [ ] Contract operator tab (deploy, view, interact)
- [ ] Wallet tab with UTXO breakdown
- [ ] Start/stop mining controls
- [ ] Phi history chart (time series visualization)

### 4.5 Wallet Page (`/wallet`)
- [x] MetaMask connect button (ethers.js v6)
- [x] QBC chain auto-add to MetaMask (chainId 3301)
- [x] Balance display (QBC)
- [x] Send transaction form (UI)
- [x] Receive (show address)
- [ ] QR code for receiving
- [ ] Transaction history with status
- [ ] QBC-20 token management
- [ ] QBC-721 NFT gallery

### 4.6 QVM Explorer (`/qvm`)
- [ ] Contract search and browser
- [ ] Contract detail page (code, storage, events, transactions)
- [ ] Bytecode disassembler view
- [ ] Storage slot inspector
- [ ] Event log with filters
- [x] Deploy contract interface (template selection + bytecode input)
- [ ] Contract interaction interface (ABI-based)
- [x] Quantum opcodes reference table (all 10 opcodes with gas costs)

### 4.7 Shared Components
- [x] Navbar (responsive, wallet connect button, Phi indicator)
- [ ] Footer (links, quantum animation)
- [x] Wallet connect/disconnect button
- [ ] Transaction confirmation modal
- [ ] Toast notification system
- [x] Loading states (phi-spiral spinner, skeleton)
- [x] Card component with quantum glow variants
- [ ] Error boundaries
- [x] SEO meta tags
- [ ] Dark/light mode (default: dark quantum theme)

---

## PHASE 5: BRIDGES & CROSS-CHAIN (Priority: MEDIUM)

### 5.1 Bridge Infrastructure
- [x] Bridge manager (`bridge/manager.py`)
- [x] Base bridge abstract class (`bridge/base.py`)
- [x] Ethereum bridge skeleton (`bridge/ethereum.py`)
- [x] Solana bridge skeleton (`bridge/solana.py`)
- [x] Lock-and-mint implementation (QBC → wQBC on ETH) — `BridgeVault.sol: deposit()`
- [x] Burn-and-unlock implementation (wQBC → QBC) — `BridgeVault.sol: processWithdrawal()`
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
- [x] wQBC ERC-20 on Ethereum — `bridge/wQBC.sol` (mint/burn by bridge, pausable)
- [ ] wQBC SPL on Solana
- [ ] wQBC on Polygon, BNB, AVAX, ARB, OP, Cosmos (ATOM)

---

## PHASE 6: QUSD STABLECOIN (Priority: HIGH)

> **3.3 Billion QUSD initial mint.** Fractional reserve model with full on-chain debt tracking.
> Wrapped to wQUSD for cross-chain liquidity. Dev funds + LP from initial allocation.
> 10-year path to 100% backing — every dollar tracked immutably on-chain.
> **Whitepaper reference:** `docs/WHITEPAPER.md` Section 11

### 6.1 QUSD Smart Contract Suite (Solidity)
- [x] `QUSD.sol` — QBC-20 token contract (3.3B initial mint, $1 peg target)
  - [x] Mint function (owner-only, tracks totalMinted on-chain)
  - [x] Burn function (reduces supply, tracked as debt reduction)
  - [x] Transfer with 0.05% fee (burned or routed to reserves based on backing ratio)
  - [x] Pause/unpause (emergency circuit breaker)
  - [x] Snapshot for governance voting
- [x] `QUSDReserve.sol` — Multi-asset reserve pool contract
  - [x] Accept reserve deposits (QBC, ETH, BTC, USDT, USDC, DAI)
  - [x] Track total reserve value in USD (via oracle)
  - [x] Reserve withdrawal (governance-only, multi-sig)
  - [x] Reserve composition query (per-asset breakdown)
  - [x] Minimum reserve ratio enforcement (revert minting if below threshold)
- [x] `QUSDDebtLedger.sol` — On-chain fractional payback tracking
  - [x] Record every mint as debt: `totalMinted`, `totalBacked`, `outstandingDebt`
  - [x] `backingPercentage = totalReserves / totalMinted × 100`
  - [x] Payback event log: every reserve deposit records the debt reduction
  - [x] Historical debt snapshots (per-block backing ratio)
  - [x] Public query: `getDebtStatus()` → (minted, reserves, backing%, debt)
  - [x] Milestone events emitted when backing crosses 5%, 15%, 30%, 50%, 100%
- [x] `QUSDOracle.sol` — Price feed oracle contract
  - [x] QBC/USD price feed (aggregated from multiple sources)
  - [x] QUSD/USD peg deviation tracking
  - [x] Staleness detection (revert if price older than N blocks)
  - [x] Multi-oracle consensus (median of 3+ feeds)
  - [x] **Used by:** Aether fee system, contract deploy fees, bridge pricing
- [x] `QUSDStabilizer.sol` — Peg maintenance mechanism
  - [x] Buy QUSD when price < $0.99 (floor defense)
  - [x] Sell QUSD when price > $1.01 (ceiling defense)
  - [x] Stability fund management
  - [x] Auto-rebalance trigger
- [x] `QUSDAllocation.sol` — Initial distribution with vesting
  - [x] 50% → Liquidity Providers (DEX/AMM pools, immediate)
  - [x] 30% → Treasury (DAO-governed, project development)
  - [x] 15% → Dev fund (4-year linear vesting, cliff at 6 months)
  - [x] 5% → Team (4-year linear vesting, cliff at 1 year)
  - [x] Vesting schedule enforcement (on-chain, immutable)
  - [x] Claim function for vested tokens
- [x] `QUSDGovernance.sol` — Reserve governance
  - [x] Proposal system for reserve management decisions
  - [x] Voting with QUSD holdings
  - [x] Timelock on execution (48h minimum)
  - [x] Emergency bypass (multi-sig, 5-of-7)

### 6.2 Wrapped QUSD (wQUSD) — Cross-Chain
- [x] `wQUSD.sol` — Wrapped QUSD for cross-chain deployment
  - [x] ERC-20 compatible wrapper on QBC chain (lock QUSD → mint wQUSD)
  - [x] Burn wQUSD → unlock QUSD (return to QBC chain)
  - [x] 1:1 peg with QUSD (fully backed by locked QUSD)
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
- [x] `utils/qusd_oracle.py` — Read QBC/USD price from QUSDOracle.sol
- [x] Price cache with configurable TTL
- [x] Staleness detection + automatic fallback to fixed_qbc mode
- [x] QUSD price endpoint: `GET /qusd/price`
- [x] Reserve status endpoint: `GET /qusd/reserves`
- [x] Debt status endpoint: `GET /qusd/debt`

## PHASE 6.5: EDITABLE ECONOMIC CONFIGURATION (Priority: HIGH)

> All economic parameters must be configurable, not hardcoded.

### 6.5.1 Config Infrastructure
- [x] Add all Aether fee params to `config.py` (loaded from `.env`)
- [x] Add all contract fee params to `config.py` (loaded from `.env`)
- [x] Update `config.py` to load `secure_key.env` before `.env` (explicit load order)
- [x] Config validation for fee parameters (min < max in validate())
- [x] Config hot-reload mechanism (Admin API mutates Config class attrs at runtime)

### 6.5.2 Admin API
- [x] Auth middleware for admin endpoints (API key via `ADMIN_API_KEY` env)
- [x] `GET /admin/economics` — current economic config
- [x] `PUT /admin/aether/fees` — update Aether fee params (hot reload)
- [x] `PUT /admin/contract/fees` — update contract deploy fees (hot reload)
- [x] `PUT /admin/treasury` — update treasury addresses
- [x] `GET /admin/economics/history` — audit log of parameter changes
- [ ] Rate limiting on admin endpoints

### 6.5.3 QUSD Fee Oracle Integration
- [x] Oracle client module (`utils/qusd_oracle.py`)
- [x] Read QBC/USD price from QUSD L2 contract (via QVM state call)
- [x] Cache price with configurable TTL (30s default)
- [x] Staleness detection (10-min threshold, warning on stale)
- [x] Automatic fallback to cached/external price on oracle failure
- [x] Manual override via `set_external_price()` method
- [x] QUSD API endpoints: `GET /qusd/price`, `GET /qusd/reserves`, `GET /qusd/debt`

---

## PHASE 7: TESTING & SECURITY (Priority: HIGH — ongoing)

### 7.1 Test Suites
- [x] L1 unit tests (consensus, mining, crypto, UTXO, database) — 57 tests (test_consensus, test_database, test_quantum, test_mining_and_utxo, test_genesis_validation)
- [x] L2 unit tests (QVM opcodes, state management, gas metering) — 52 tests (test_qvm: opcodes, execution, precompiles, quantum opcodes)
- [x] L3 unit tests (knowledge graph, reasoning, Phi, Proof-of-Thought) — 139 tests (test_knowledge_graph, test_aether, test_sephirot, test_consciousness, test_memory, test_knowledge_extractor, test_reasoning_advanced, test_sephirot_nodes, test_knowledge_graph_advanced, test_task_protocol)
- [x] Integration tests (`test_integration.py` — 13 tests: KG+reasoning, Phi+KG, consciousness, extractor, sephirot, safety)
- [x] API tests (REST endpoints, JSON-RPC, WebSocket) — 9 tests (test_network: admin API, auth, models)
- [ ] Frontend tests (Vitest unit + Playwright E2E)
- [ ] Load tests (concurrent mining, high tx volume)
- [ ] Fuzz testing (random bytecode to QVM)
- [x] Privacy unit tests — 33 tests (test_privacy + test_privacy_advanced: commitments, stealth, range proofs, susy swap)
- [x] Config unit tests — 8 tests (test_config: economics, chain IDs, fee params)
- [x] Test infrastructure — conftest.py with dependency stubs (Qiskit, gRPC, IPFS, etc.)

### 7.2 Security
- [x] UTXO double-spend prevention verification (`test_mining_and_utxo.py: TestDoubleSpendPrevention`)
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
- [x] CI/CD pipeline (GitHub Actions — lint, test, build) — `.github/workflows/ci.yml`
- [x] Automated testing in CI (pytest + vitest + playwright) — backend-test, backend-lint, frontend-build jobs
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
