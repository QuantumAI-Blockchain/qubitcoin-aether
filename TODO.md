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
- [x] Verify Dilithium signature size in real transactions (~3KB expected) — `test_dilithium.py` (26 tests: keygen, signing, verification, size, addresses, CryptoManager)
- [x] Add key import/export in standard formats — `crypto.py: Dilithium2.export_keypair()/import_keypair()` (hex + PEM formats)
- [x] Signature caching for performance — `crypto.py: _cached_verify()` LRU cache (4096 entries, SHA-256 keyed)
- [x] Key rotation procedure documentation — `docs/KEY_ROTATION.md` (pre-rotation checklist, step-by-step procedure, emergency rotation, multi-node, HSM integration)

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
- [x] Verify ALL SQL schemas match SQLAlchemy models in `database/models.py` — Audited: models.py uses dataclasses (7 classes) not ORM; SQL has 55+ tables. Gap documented, validation tests added (test_schema_validation: 14 tests)
- [x] Add migration system (Alembic) for schema changes — `alembic.ini` + `migrations/` (env.py loads DATABASE_URL from .env, manual migration scripts, offline/online modes)
- [x] Connection pool health monitoring — `database/pool_monitor.py: PoolHealthMonitor` (SQLAlchemy event listeners, checkout/checkin latency, utilization %, health status: healthy/degraded/critical, snapshot history)
- [x] Refactored domain-separated schemas (`sql_new/`) — 5 domains: qbc/ (6 files), agi/ (4 files), qvm/ (4 files), research/ (3 files), shared/ (2 files) + deploy.sh

### 1.5 Network
- [x] FastAPI RPC server (`network/rpc.py`)
- [x] JSON-RPC MetaMask-compatible endpoints (`network/jsonrpc.py`)
- [x] Rust P2P libp2p daemon (`rust-p2p/`)
- [x] Python P2P fallback (`network/p2p_network.py`)
- [x] gRPC bridge between Python and Rust (`network/rust_p2p_client.py`)
- [x] Block propagation protocol (`p2p_network.py: propagate_block()` — serialize, broadcast, gossip on receive, stats tracking)
- [x] Transaction propagation (`p2p_network.py: propagate_transaction()` — broadcast to all peers, gossip relay, stats)
- [x] Block sync protocol (`p2p_network.py: request_block_range(), sync_to_peer(), get_sync_status()` — 500-block cap, height-driven, stats tracking)
- [x] Peer scoring and eviction (`p2p_network.py: adjust_peer_score, penalize_peer, reward_peer, evict_low_score_peers, get_peers_by_score`)
- [x] WebSocket endpoint for real-time subscriptions (`network/rpc.py: /ws`)

### 1.6 Storage
- [x] IPFS integration (`storage/ipfs.py`)
- [x] Blockchain snapshot to IPFS (periodic) — `storage/snapshot_scheduler.py: SnapshotScheduler` (interval-based scheduling, IPFS upload, snapshot history, failure tracking, manual trigger)
- [x] IPFS port conflict resolution (8080 vs CockroachDB admin) — `config.py: IPFS_GATEWAY_PORT=8081`, `.env.example` updated, `ipfs.py: gateway_url` property
- [x] Snapshot restoration from IPFS — `snapshot_scheduler.py: restore_from_snapshot()` (download from IPFS, validate, replay blocks/UTXOs/txs into DB)

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
- [x] Privacy transaction verification in consensus engine (`consensus/engine.py: _validate_private_transaction()` — key image check, range proof, fee validation)
- [x] Opt-in privacy flag in transaction format (`models.py: is_private: bool = False`)
- [x] Privacy-specific SQL schema tables (`sql/02_privacy_susy_swaps.sql` — key_images, range_proof_cache tables)
- [x] Privacy transaction unit tests (`test_privacy_advanced.py` — 18 tests: commitments, stealth, range proofs, susy swap)
- [x] Privacy integration tests (create, verify, spend confidential outputs) — `test_privacy_integration.py` (17 tests: commitments, stealth, susy swap, key images, tx size)

### 1.8 SUSY Solution Database
- [x] Public Hamiltonian solution storage (`hamiltonian_solutions` table)
- [x] REST API endpoint: `GET /susy-database` (query by block height, energy range, qubit count)
- [x] IPFS archival of solution datasets (periodic export) — `storage/solution_archiver.py: SolutionArchiver` (block-range export, IPFS upload, CID tracking, archive history, graceful DB error handling)
- [x] Solution verification count tracking — `mining/solution_tracker.py: SolutionVerificationTracker` (per-solution verification records, confidence scoring, duplicate verifier prevention, by-block/by-miner queries)
- [x] Scientific data export formats (JSON, CSV for researchers) — `rpc.py: GET /susy-database/export?format=json|csv`

### 1.9 Node Types
- [x] Light node implementation (SPV verification, block headers only) — `network/light_node.py: SPVVerifier + LightNode` (Merkle proof verification, confirmation depth check, header store)
- [x] Light node sync protocol (<5 minutes) — `network/light_node.py: LightNodeSync` (batched header download, chain linkage validation, checkpoint verification, eviction)
- [x] Mining node VQE capability detection (classical vs quantum backend) — `mining/capability_detector.py: VQECapabilityDetector` (detect local/Aer/IBM backends, qubit count, P2P advertisement, config-based fallback)
- [x] Node capability advertisement in P2P protocol — `network/capability_advertisement.py: CapabilityAdvertiser` (peer registry, mining power scoring, P2P broadcast/receive, network summary, stale cleanup, backend filtering)

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
- [x] Reconcile opcode mapping: 0xD0-0xDE (Python) with canonical 0xF0-0xF9 (whitepaper) via CANONICAL_OPCODE_MAP + docs
- [x] QCREATE (0xDA/WP:0xF0) — Create quantum state as density matrix (`vm.py` + `opcodes.py`)
- [x] QMEASURE (0xD1/0xF1) — Measure/collapse quantum state (deterministic from block context)
- [x] QENTANGLE (0xD2/0xF2) — Create entangled pair between contracts
- [x] QGATE (0xD0/0xF3) — Apply quantum gate (H,X,Y,Z,CNOT,RX,RY,RZ)
- [x] QVERIFY (0xDB/WP:0xF4) — Verify quantum ZK proof (`vm.py` + `opcodes.py`)
- [x] QCOMPLIANCE (0xDC/WP:0xF5) — KYC/AML/sanctions compliance check (stub, returns level 1)
- [x] QRISK (0xDD/WP:0xF6) — SUSY risk score for individual address (stub, returns 10/100)
- [x] QRISK_SYSTEMIC (0xDE/WP:0xF7) — Systemic risk / contagion model (stub, returns 5/100)
- [x] QBRIDGE_ENTANGLE (0xF8) — Cross-chain quantum entanglement
- [x] QBRIDGE_VERIFY (0xF9) — Cross-chain bridge proof verification
- [x] QSUPERPOSE (0xD3) — Hadamard superposition
- [x] QVQE (0xD4) — Execute VQE optimization
- [x] QHAMILTONIAN (0xD5) — Generate SUSY Hamiltonian from seed
- [x] QENERGY (0xD6) — Compute energy expectation value
- [x] QPROOF (0xD7) — Validate quantum proof (energy vs difficulty)
- [x] QFIDELITY (0xD8) — Compute state fidelity between quantum states
- [x] QDILITHIUM (0xD9) — Verify Dilithium signature
- [x] Exponential gas scaling for n-qubit operations (`opcodes.py: get_quantum_gas_cost()` — base + 5000*2^n, capped at 32 qubits)

### 2.3 Quantum State Persistence (QSP)
- [x] Density matrix storage in CockroachDB (`quantum_states` table)
- [x] Entanglement registry (`entanglement_pairs` table)
- [x] Quantum state CRUD operations
- [x] Lazy measurement (states persist until explicitly measured)
- [x] Quantum state root in block header (Merkle root of all quantum states)
- [x] State decoherence prevention model

### 2.4 Compliance Engine (Institutional)
- [x] Compliance registry schema (`compliance_registry` table)
- [x] QCOMPLIANCE opcode: pre-flight KYC/AML/sanctions check
- [x] Programmable Compliance Policies (PCP) framework
- [x] Policy CRUD API (`POST/PUT/DELETE /qvm/compliance/policies`)
- [x] KYC verification module (Level 0-3 tiers)
- [x] AML monitoring module (transaction pattern detection)
- [x] Sanctions screening (OFAC, UN, EU lists integration) — `compliance.py: SanctionsList` (add/remove/screen/bulk_add, 3 sources, wired into ComplianceEngine)
- [x] ERC-20-QC compliance-aware token standard — `contracts/solidity/tokens/ERC20QC.sol`
- [x] Auto-circuit breakers (halt on systemic risk > threshold)
- [x] Compliance-as-a-Service tier system (Retail/Professional/Institutional/Sovereign)
- [x] Compliance proof storage (ZK proofs for auditors) — `qvm/compliance_proofs.py: ComplianceProofStore` (hash-chain linkage, per-address audit trails, integrity verification, expiry)
- [x] Regulatory report generation (MiCA, SEC, FinCEN) — `qvm/regulatory_reports.py: RegulatoryReportGenerator` (4 frameworks, integrity hash, period/block-range scoping)

### 2.5 Risk Assessment Oracle (RRAO)
- [x] QRISK opcode: SUSY Hamiltonian-based risk scoring
- [x] Transaction graph builder (6-hop depth from address)
- [x] Graph-to-SUSY-Hamiltonian conversion algorithm
- [x] VQE ground state computation for risk score
- [x] Risk score caching (10-block TTL)
- [x] QRISK_SYSTEMIC: systemic risk / contagion prediction
- [x] Contagion time-evolution operator (predict cascade effects)
- [x] Risk score normalization (0-100 scale)
- [x] High-risk connection detection (sanctioned entities, mixers, overleveraged)

### 2.6 Plugin Architecture
- [x] Plugin manager module (lifecycle management)
- [x] Dynamic plugin loading system
- [x] Plugin registry and API interface
- [x] Privacy plugin (SUSY swaps, ZK proof generation)
- [x] Oracle plugin (quantum oracle, price feeds, aggregation)
- [x] Governance plugin (DAO, voting, proposals)
- [x] DeFi plugin (lending, DEX, staking)
- [x] Plugin SDK documentation — `docs/PLUGIN_SDK.md` (plugin architecture, hook types, lifecycle, built-in plugins, testing guide, security considerations)

### 2.7 Contract Deployment
- [x] Contract deployment engine (`contracts/engine.py`)
- [x] Template contracts (token, nft, launchpad, escrow, governance)
- [x] Deploy via JSON-RPC `eth_sendTransaction`
- [x] Contract verification (source → bytecode matching)
- [x] ABI encoding/decoding for function calls
- [x] Contract upgrade patterns (proxy) — `contracts/proxy.py: ProxyRegistry` (EIP-1967 slots, admin-only upgrade, audit trail)

### 2.8 Contract Deployment Fees
- [x] Fee calculator module (`contracts/fee_calculator.py`)
- [x] Base fee + per-KB fee structure (configurable via `.env`)
- [x] QUSD-pegged dynamic pricing (same oracle as Aether fees)
- [x] Three pricing modes: `qusd_peg`, `fixed_qbc`, `direct_usd`
- [x] Template contract discount (configurable percentage)
- [x] Fee deduction from deployer UTXO before deployment — `contracts/engine.py` integrates `FeeCollector`
- [x] Fee UTXO creation to treasury address — `utils/fee_collector.py: collect_fee()` (UTXO spend → treasury + change)
- [x] Add contract fee config parameters to `config.py`
- [x] Admin API: `PUT /admin/contract/fees` (hot reload) — `network/admin_api.py` (already implemented in Phase 6.5.2)
- [x] Fee estimation endpoint: `GET /qvm/deploy/estimate`

### 2.9 Token Standards
- [x] QBC-20 reference implementation (`tokens/QBC20.sol`)
- [x] QBC-721 reference implementation (`tokens/QBC721.sol`)
- [x] QBC-1155 reference implementation — `contracts/solidity/tokens/QBC1155.sol` (ERC-1155 compatible, single/batch mint/burn/transfer, per-token URI, totalSupply tracking)
- [x] ERC-20-QC compliance-aware token — `contracts/solidity/tokens/ERC20QC.sol` (KYC level requirement, address freezing, compliance officer role, pause/unpause, QCOMPLIANCE opcode hook)
- [x] Token indexer (track all QBC-20/721 transfers) — `qvm/token_indexer.py: TokenIndexer` (Transfer event parsing, balance tracking, holder ranking, mint/burn detection, REST API endpoints)

### 2.10 Cross-Chain Bridge Verification
- [x] QBRIDGE_ENTANGLE opcode implementation (vm.py 0xF8 — deterministic entanglement ID)
- [x] QBRIDGE_VERIFY opcode implementation (vm.py 0xF9 — proof validation stub)
- [x] Quantum-verified cross-chain proofs (QVCSP) — `bridge/proof_store.py: verify_qvcsp()` (entanglement correlation)
- [x] Bridge proof storage schema — `bridge/proof_store.py: ProofStore` (submit, verify, execute, replay protection, Merkle proofs)
- [x] State channel support for high-frequency trading — `qvm/state_channels.py: StateChannelManager` (open/update/close/dispute/finalize lifecycle, balance conservation, challenge window)

### 2.11 Advanced Features (Future)
- [x] Time-Locked Atomic Compliance (TLAC) — `qvm/compliance_advanced.py: TLACManager` (multi-jurisdiction approval, deadline enforcement, auto-expiry)
- [x] Hierarchical Deterministic Compliance Keys (HDCK) — `qvm/compliance_advanced.py: HDCKManager` (BIP-32 path m/44'/689'/{org}'/role/index, role-based permissions, key revocation)
- [x] Verifiable Computation Receipts (VCR) — `qvm/compliance_advanced.py: VCRStore` (Merkle-rooted execution traces, multi-verifier support, 100x faster audit)
- [x] Quantum Solidity compiler — `qvm/qsol_compiler.py` (QSolLexer + QSolParser + QSolCodeGenerator + QSolCompiler, .qsol → AST → QVM bytecode, quantum keywords: qstate/qregister/measure/entangle/apply_gate/superpose/q_verify, ABI generation, 41 tests)
- [x] QVM debugger — `qvm/debugger.py: QVMDebugger` (step-through execution, breakpoints by PC/opcode/gas/stack_depth, state snapshots, execution trace, disassembly, gas profiling, 81 tests)
- [x] State channels for Layer 2 scaling — `qvm/state_channels.py: StateChannelManager` (off-chain updates, dispute resolution, CHALLENGE_WINDOW=100 blocks)
- [x] Transaction batching (rollup-style) — `qvm/transaction_batcher.py: TransactionBatcher` (MAX_BATCH_SIZE=100, MAX_BATCH_GAS=15M, Merkle root proofs, BatchReceipt)
- [x] Formal verification (K Framework) — `docs/formal_verification/qvm_opcodes.k` (executable semantics for EVM arithmetic, memory, storage, flow control + quantum opcodes QGATE/QMEASURE/QENTANGLE/QCREATE/QVERIFY with gas accounting)
- [x] TLA+ compliance invariant proofs — `docs/formal_verification/compliance_invariants.tla` (6 safety invariants: SanctionsEnforced, KYCBeforeTransfer, CircuitBreakerBlocks, RiskScoresBounded, SystemicRiskBounded, CircuitBreakerConsistency + 2 liveness properties)

### 2.12 Go Production Implementation (qubitcoin-qvm/)
- [x] Initialize Go module (`go.mod`, project structure) — `qubitcoin-qvm/go.mod` (Go 1.23, go-ethereum, circl, grpc-gateway, prometheus, cobra, viper, testify, cockroach-go, pgx, zap)
- [x] Port EVM core (6/15 files: opcodes, stack, memory, gas, interpreter, context, precompiles) — `pkg/vm/evm/stack.go` (1024-item bounded stack, big.Int, signed/unsigned helpers), `pkg/vm/evm/memory.go` (word-aligned, EVM expansion cost), `pkg/vm/evm/context.go` (BlockContext, TxContext, CallContext, ExecutionContext, JUMPDEST analysis), `pkg/vm/evm/gas.go` (Berlin/Shanghai constants, EIP-2200 SSTORE, dynamic cost functions), `pkg/vm/evm/interpreter.go` (full opcode dispatch: arithmetic, bitwise, keccak256, environment, block info, stack/memory/storage, push/dup/swap, log, return/revert, CREATE/CALL stubs)
- [x] Port quantum extensions (3/8 files: state, gates, interpreter) — `pkg/vm/quantum/state.go` (StateManager: density matrix creation, measurement with deterministic collapse, entanglement registry, fidelity computation, state verification), `pkg/vm/quantum/gates.go` (10 gate types: H/X/Y/Z/CNOT/RX/RY/RZ/S/T, density matrix transformation ρ'=UρU†, CNOT permutation), `pkg/vm/quantum/interpreter.go` (Handler dispatching all 10 quantum opcodes 0xF0-0xF9: QCREATE, QMEASURE, QENTANGLE, QGATE, QVERIFY, QCOMPLIANCE, QRISK, QRISK_SYSTEMIC, QBRIDGE_ENTANGLE, QBRIDGE_VERIFY)
- [x] Implement compliance engine (4/9 files: KYC, AML, sanctions, risk) — `pkg/compliance/kyc.go` (KYCRegistry: tier-based limits Retail/$10K/Professional/$1M/Institutional+Sovereign/unlimited, verification with expiration, transaction pre-flight check), `pkg/compliance/aml.go` (AMLMonitor: velocity detection, structuring detection, volume spike alerts, configurable thresholds, per-address tx history, severity levels), `pkg/compliance/sanctions.go` (SanctionsChecker: multi-source sanctions list OFAC/EU/UN, sender+receiver checks, add/remove with audit trail), `pkg/compliance/risk.go` (RiskScorer: SUSY-inspired risk 0-10000 scale, sigmoid velocity scoring, log volume scoring, age decay, tier bonus, systemic risk contagion model, auto circuit breaker with cooldown)
- [x] Implement plugin system (1/5 files: manager) — `pkg/plugin/manager.go` (PluginManager: Plugin interface with Name/Version/Initialize/Shutdown/Capabilities, registration/init/shutdown lifecycle, capability-based lookup CapOpcodeHandler/CapPrecompile/CapHook/CapService/CapStorageBackend, deterministic reverse-order shutdown, FindByCapability search)
- [x] Implement RPC server (gRPC + REST) — `pkg/rpc/server.go` (dual gRPC+HTTP server, CORS middleware, request size limiter, graceful shutdown, ServiceRegistry), `pkg/rpc/handlers.go` (REST endpoints: /health, /ready, /info, /chain/info, /qvm/info, /metrics Prometheus), `pkg/rpc/jsonrpc.go` (JSON-RPC 2.0 handler: eth_chainId, eth_blockNumber, eth_getBalance, eth_call, eth_estimateGas, eth_gasPrice, eth_getBlockByNumber, web3_clientVersion, net_version, 25+ methods, batch support)
- [x] Implement state management (StateDB) — `pkg/state/statedb.go` (in-memory StateDB implementing evm.StateAccessor: account/balance/nonce/code/storage management, snapshot/revert for tx atomicity, journal-based undo, Merkle state root computation, block hash storage for BLOCKHASH)
- [x] Implement crypto layer (Keccak-256 + Dilithium) — `pkg/crypto/signatures.go` (Keccak256/Keccak256Multi for EVM compat, SHA256Hash for L1 block hashes, GenerateKeyPair/Sign/Verify Dilithium placeholder with circl interface, AddressFromPublicKey derivation)
- [ ] Port all 55 database schemas
- [ ] Ethereum test suite compatibility (official EVM tests)
- [ ] Benchmark suite (EVM, quantum, storage, compliance)
- [x] Docker deployment (dev + prod) — `qubitcoin-qvm/deployments/docker/Dockerfile` (multi-stage: golang:1.23-bookworm builder → distroless/static-debian12:nonroot runtime, CGO_ENABLED=0, trimpath)
- [x] Kubernetes manifests — `qubitcoin-qvm/deployments/kubernetes/qvm-deployment.yml` (Namespace, ConfigMap, Service+headless, StatefulSet 3 replicas, ServiceAccount, HPA 3-12 pods CPU/memory scaling, PodDisruptionBudget minAvailable=2, NetworkPolicy ingress/egress, PVC 50Gi fast-ssd, readiness+liveness probes, Prometheus annotations)
- [x] CI/CD pipeline (build, test, lint, security scan) — `.github/workflows/qvm-ci.yml` (5 jobs: build, test, lint w/ golangci-lint, benchmark on main, security scan w/ govulncheck, Docker build)

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
- [x] Reasoning over user queries (natural language → knowledge graph query) — `aether/query_translator.py: QueryTranslator` (intent classification, keyword extraction, KG node matching, reasoning strategy dispatch)
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
- [x] Quantum-entangled messaging between paired nodes — `csf_transport.py: QuantumEntangledChannel` (SUSY pair instant delivery, bypasses BFS routing)
- [x] Load balancing (pressure monitor) — `csf_transport.py: PressureMonitor` (per-node queue depth, backpressure, congestion detection)
- [x] CSF Transport smart contract (`MessageBus.sol` — covers CSF transport on-chain)
- [x] Ventricle router contract (`VentricleRouter.sol`) — on-chain CSF routing with backpressure detection, SUSY entangled pair shortcuts, pressure management, routing table

### 3.9 Pineal Orchestrator
- [x] Circadian controller (6 phases: Waking → Deep Sleep) — `pineal.py: CircadianPhase + PHASE_CYCLE`
- [x] QBC metabolic rate per phase (2.0x learning, 0.3x deep sleep) — `pineal.py: METABOLIC_RATES`
- [x] Phase-lock oscillator (Kuramoto coupling) — `sephirot.py: get_coherence()`
- [x] Consciousness integrator (combine Phi + coherence) — `pineal.py: _check_consciousness()`
- [x] Melatonin modulator (inhibitory signals) — `pineal.py: MelatoninModulator` (phase-dependent melatonin levels, inhibition factor dampens metabolic rate, cycle reset)
- [x] QBC staking pool for orchestration influence — `pineal.py: OrchestrationStakingPool` (stake QBC on phases, phase duration extension, 7-day unstaking delay, proportional voting weight)

### 3.10 Proof-of-Thought Protocol
- [x] AetherEngine with proof generation (`proof_of_thought.py`)
- [x] Auto-reasoning on recent knowledge
- [x] Embed Proof-of-Thought hash in block headers — `models.py: Block.proof_of_thought_hash` (SHA-256, auto-computed, in to_dict/from_dict, included in block hash)
- [x] Task submission system (`task_protocol.py: TaskMarket` — submit with QBC bounty, claim, solve)
- [x] Node solution proposal (`task_protocol.py: submit_solution()` — solution + hash)
- [x] Multi-node validation (`task_protocol.py: ProofOfThoughtProtocol.validate_solution()` — stake-weighted 67% BFT)
- [x] QBC reward distribution for correct solutions (`task_protocol.py: finalize_task()`)
- [x] QBC slashing for incorrect proposals (`task_protocol.py: ValidatorRegistry.slash()` — 50% stake)
- [x] Proof-of-Thought smart contract (`ProofOfThought.sol`)
- [x] Task market contract (`TaskMarket.sol`)
- [x] Validator registry contract (`ValidatorRegistry.sol`)
- [x] Validator registry Python module (`task_protocol.py: ValidatorRegistry` — stake/unstake/slash/reward)
- [x] Proof-of-Thought explorer (view reasoning per block) — `aether/pot_explorer.py: ProofOfThoughtExplorer` (block thought data, Phi progression, consciousness events, reasoning summary, phi-range search)

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
- [x] IPFS integration for long-term memory storage — `aether/ipfs_memory.py: IPFSMemoryStore` (store/retrieve/pin memories on IPFS, local cache fallback)

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
- [x] QBC circulation tracking (no minting by AGI) — `aether/circulation.py: CirculationTracker` (era/reward computation, phi-halving detection, emission schedule, REST API endpoints)

### 3.15 Aether Chat System
- [x] Chat endpoint: `POST /aether/chat/message` — conversational interface (`aether/chat.py`)
- [x] Session management (conversation history per session) (`POST /aether/chat/session`)
- [x] Natural language → reasoning engine query translation
- [x] Response generation from knowledge graph + reasoning traces
- [x] Proof-of-Thought hash per response
- [x] Chat history endpoint: `GET /aether/chat/history/{session_id}`
- [x] WebSocket for streaming responses: `/ws/aether` — `aether/ws_streaming.py: AetherWSManager` (session-scoped events, subscription filtering, capacity management, REST stats endpoint)
- [x] Rate limiting and session management (max 10K sessions, LRU eviction)

### 3.16 Aether Tree Fee System
- [x] Fee manager module (`aether/fee_manager.py`)
- [x] QUSD oracle integration (read QBC/USD price from QUSD L2 contract)
- [x] Dynamic fee calculation: `fee_qbc = usd_target / qbc_usd_price`
- [x] Fee clamping (min/max QBC bounds to prevent extreme fees)
- [x] Three pricing modes: `qusd_peg`, `fixed_qbc`, `direct_usd`
- [x] Automatic fallback: QUSD failure → fixed_qbc mode
- [x] Fee deduction from user UTXO before processing chat message — `aether/chat.py` integrates `FeeCollector`
- [x] Fee UTXO creation to treasury address — `utils/fee_collector.py: collect_fee()` (UTXO spend → treasury + change)
- [x] Free tier: first N messages per session (configurable onboarding)
- [x] Fee tier multipliers (deep queries cost more than chat)
- [x] Fee update interval (re-price every N blocks from QUSD oracle)
- [x] Add fee config parameters to `config.py` (all from `.env`)
- [x] Admin API: `PUT /admin/aether/fees` (hot reload fee params) — `network/admin_api.py` (already implemented in Phase 6.5.2)
- [x] Fee audit logging (track all fee changes for transparency) — `utils/fee_collector.py: get_audit_log()` (in-memory, filterable by fee_type)

### 3.17 LLM Adapters (External Intelligence)
- [x] OpenAI GPT-4 adapter (knowledge distillation to Sephirot) — `aether/llm_adapter.py: OpenAIAdapter`
- [x] Anthropic Claude adapter — `aether/llm_adapter.py: ClaudeAdapter`
- [x] Open-source adapter (Llama, Mistral) — `aether/llm_adapter.py: LocalAdapter` (OpenAI-compatible local API)
- [x] Knowledge distiller (extract insights to knowledge graph) — `aether/llm_adapter.py: KnowledgeDistiller` (sentence splitting, classification, KG node creation)

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
- [x] Vitest + Playwright test setup — `vitest.config.ts` + `playwright.config.ts` (jsdom env, path aliases, setup file, 3 browser projects, test scripts in package.json, sample unit tests passing)
- [x] Environment configuration (NEXT_PUBLIC_* vars) (`.env.local`)
- [x] Vercel deployment config (vercel.json, custom domain qbc.network) — `vercel.json` (security headers, static asset caching, API proxy rewrites, iad1 region)
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
- [x] Footer with links, social, legal — `components/ui/footer.tsx` (nav links, resources, social icons, chain info, copyright)
- [x] Mobile responsive design
- [x] Performance optimization (lazy loading, image optimization) — `next.config.ts` (optimizePackageImports for framer-motion/three/ethers, AVIF+WebP images, remote patterns, dynamic imports for heavy components)

### 4.3 Aether Chat Page (`/aether`)
- [x] Full-page chat interface (ChatGPT/Grok-like layout)
- [x] Message input with quantum-themed styling
- [x] Streaming response display (typewriter effect) — `components/aether/streaming-text.tsx` (character-by-character reveal, blinking cursor, configurable speed, onComplete callback)
- [x] Conversation sidebar (session list, new chat) — `components/aether/conversation-sidebar.tsx` (sorted by recency, new/delete/select, mobile fallback)
- [x] Knowledge graph 3D visualization panel (Three.js force-directed) — `components/aether/knowledge-graph-3d.tsx` (R3F Canvas, force-directed layout, node types color-coded, edge rendering, orbit controls, hover labels, dynamic import SSR-safe)
- [x] Phi consciousness meter (animated gauge) — sidebar panel
- [x] Reasoning trace accordion (expandable per response)
- [x] Proof-of-Thought hash per response
- [x] Local storage for conversation history — `conversation-sidebar.tsx` (loadSessions/saveSessions/saveSessionMessages/loadSessionMessages per-session persistence)
- [x] Keyboard shortcuts (Enter to send)

### 4.4 Dashboard (`/dashboard`)
- [x] Overview tab (QBC balance, block height, supply, difficulty, Phi, knowledge)
- [x] Mining tab (status, blocks mined, VQE energy, alignment score)
- [x] Aether tab (consciousness gauge, knowledge nodes/edges, integration, differentiation)
- [x] Network tab (peers, mempool, chain ID, block height)
- [x] Contract operator tab (deploy, view, interact) — inline ContractsTab in dashboard (deploy form, contract lookup, link to QVM explorer)
- [x] Wallet tab with UTXO breakdown — inline WalletTab in dashboard (balance summary, UTXO table with txid/vout/amount/confirmations)
- [x] Start/stop mining controls — `components/dashboard/mining-controls.tsx` (start/stop buttons, confirmation modal, toast feedback)
- [x] Phi history chart (time series visualization) — `components/dashboard/phi-chart.tsx` (SVG chart, threshold line, gradient fill, auto-refetch)

### 4.5 Wallet Page (`/wallet`)
- [x] MetaMask connect button (ethers.js v6)
- [x] QBC chain auto-add to MetaMask (chainId 3301)
- [x] Balance display (QBC)
- [x] Send transaction form (UI)
- [x] Receive (show address)
- [x] QR code for receiving — `components/ui/qr-code.tsx` (SVG-based deterministic QR pattern, finder patterns, timing, data area)
- [x] Transaction history with status — `components/wallet/transaction-history.tsx` (UTXO list, pending mempool txs, confirmations, send/recv indicators)
- [x] QBC-20 token management — `components/wallet/token-manager.tsx` (balance list, send panel, token lookup, format amounts, symbol/decimals display)
- [x] QBC-721 NFT gallery — `components/wallet/nft-gallery.tsx` (responsive grid, image cards, detail modal, collection name, token ID, metadata URI)

### 4.6 QVM Explorer (`/qvm`)
- [x] Contract search and browser — `components/qvm/contract-browser.tsx` (address lookup, active/inactive status badge)
- [x] Contract detail page (code, storage, events, transactions) — inline detail view in contract-browser.tsx (creator, type, storage slots, bytecode hash, deploy date)
- [x] Bytecode disassembler view — `components/qvm/bytecode-disassembler.tsx` (80+ EVM opcodes + 10 quantum opcodes, PUSH inline data, quantum highlight, 500-op safety cap)
- [x] Storage slot inspector — `components/qvm/storage-inspector.tsx` (address + key lookup, preset slot buttons, formatted result display)
- [x] Event log with filters — `components/qvm/event-log.tsx` (contract event lookup, topic filter dropdown, known event decoding, paginated table)
- [x] Deploy contract interface (template selection + bytecode input)
- [x] Contract interaction interface (ABI-based) — `components/qvm/contract-interact.tsx` (ABI JSON parser, function selector, dynamic inputs, read/write call support)
- [x] Quantum opcodes reference table (all 10 opcodes with gas costs)

### 4.7 Shared Components
- [x] Navbar (responsive, wallet connect button, Phi indicator)
- [x] Footer (links, quantum animation) — `components/ui/footer.tsx` (added to root layout)
- [x] Wallet connect/disconnect button
- [x] Transaction confirmation modal — `components/ui/confirm-modal.tsx` (animated backdrop, default/danger variants, loading state)
- [x] Toast notification system — `components/ui/toast.tsx` (ToastProvider context, success/error/info variants, auto-dismiss, animated)
- [x] Loading states (phi-spiral spinner, skeleton)
- [x] Card component with quantum glow variants
- [x] Error boundaries — `components/ui/error-boundary.tsx` (class component, retry button, custom fallback support)
- [x] SEO meta tags
- [x] Dark/light mode (default: dark quantum theme) — `stores/theme-store.ts` (Zustand persist, localStorage), `components/ui/theme-toggle.tsx` (sun/moon icons in navbar), light mode CSS overrides in `globals.css`

---

## PHASE 5: BRIDGES & CROSS-CHAIN (Priority: MEDIUM)

### 5.1 Bridge Infrastructure
- [x] Bridge manager (`bridge/manager.py`)
- [x] Base bridge abstract class (`bridge/base.py`)
- [x] Ethereum bridge skeleton (`bridge/ethereum.py`)
- [x] Solana bridge skeleton (`bridge/solana.py`)
- [x] Lock-and-mint implementation (QBC → wQBC on ETH) — `BridgeVault.sol: deposit()`
- [x] Burn-and-unlock implementation (wQBC → QBC) — `BridgeVault.sol: processWithdrawal()`
- [x] Federated validator set (7-of-11 multi-sig, path to 101+) — `bridge/validators.py: FederatedValidatorSet` (registration, bonding, quorum, attestation aggregation)
- [x] Validator economic bonding (10,000+ QBC slashable stake) — `bridge/validators.py: ValidatorBond` (MIN_BOND=10K, slash 5-50%, unbonding delay 181K blocks)
- [x] Bridge event monitoring (multi-source: direct observation + oracle) — `bridge/monitoring.py: BridgeEventMonitor` (multi-source verification, dedup, chain-specific confirmation depths)
- [x] Transfer status tracking — `bridge/monitoring.py: TransferTracker` (INITIATED→CONFIRMING→VALIDATED→EXECUTING→COMPLETED lifecycle)
- [x] Bridge fee collection (0.1% of transfer, 100% to QUSD reserves) — `bridge/monitoring.py: TransferTracker` (10bps fee, auto-collection on initiation)
- [x] Daily transfer limits (security cap) — `bridge/monitoring.py: TransferTracker` (1M QBC/chain/day default, 100K per-tx limit)
- [x] Deep confirmation requirements (reorg protection) — `bridge/monitoring.py: CONFIRMATION_DEPTHS` (ETH=20, Polygon=64, Solana=32, QBC=6)
- [x] Emergency pause mechanism — `bridge/monitoring.py: TransferTracker.pause()/unpause()` (blocks all new transfers)
- [x] Bridge insurance fund — `bridge/monitoring.py: TransferTracker.contribute_to_insurance()` (dedicated fund for bridge losses)

### 5.2 Wrapped QBC Contracts (Solidity)
- [x] wQBC ERC-20 on Ethereum — `bridge/wQBC.sol` (mint/burn by bridge, pausable)
- [x] wQBC SPL on Solana — `deployment/solana/wqbc/` (Anchor 0.30 program, PDA bridge state, 10bps fee, replay protection via TxReceipt, pause/unpause, events)
- [x] wQBC on Polygon, BNB, AVAX, ARB, OP, Base — `tokens/wQBC.sol` + `deployment/crosschain/deploy.json` (chain-agnostic ERC-20, 0.1% bridge fee, replay protection, emergency pause, deploy configs for 7 chains)

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
- [x] wQUSD ERC-20 on Ethereum (bridge via lock-and-mint) — `qusd/wQUSD.sol` already chain-agnostic ERC-20
- [x] wQUSD SPL on Solana — `deployment/solana/wqusd/` (Anchor 0.30 program, PDA bridge state, 5bps fee to QUSD reserves, replay protection, pause/unpause, events)
- [x] wQUSD on Polygon, BNB, AVAX, ARB, OP, Base — `qusd/wQUSD.sol` + `deployment/crosschain/deploy.json` (same Solidity deploys on all EVM chains, deploy configs included)
- [x] wQUSD bridge fee (0.05% — routed to QUSD reserves) — `stablecoin/reserve_manager.py: CrossChainQUSDAggregator` (5bps fee on every wQUSD bridge transfer)
- [x] Cross-chain QUSD balance aggregation (total supply across all chains) — `stablecoin/reserve_manager.py: CrossChainQUSDAggregator` (per-chain supply tracking, total supply computation)

### 6.3 Reserve Building Mechanisms
- [x] Bridge fee collection → QUSD reserves (0.1% of all bridge transfers) — `stablecoin/reserve_manager.py: ReserveFeeRouter` (BRIDGE_FEE source, 100% allocation)
- [x] QUSD transaction fees → reserves (0.05% per transfer) — `stablecoin/reserve_manager.py: ReserveFeeRouter` (QUSD_TX_FEE source, 100% allocation)
- [x] LP fee revenue → reserves (percentage of DEX fees) — `stablecoin/reserve_manager.py: ReserveFeeRouter` (LP_FEE source, 50% default allocation)
- [x] Treasury controlled sales → reserves (governance-approved) — `stablecoin/reserve_manager.py: ReserveFeeRouter` (TREASURY_SALE source, 100% allocation)
- [x] Aether Tree chat fees → partial allocation to reserves — `stablecoin/reserve_manager.py: ReserveFeeRouter` (AETHER_CHAT_FEE source, 10% default allocation)
- [x] Contract deployment fees → partial allocation to reserves — `stablecoin/reserve_manager.py: ReserveFeeRouter` (CONTRACT_DEPLOY_FEE source, 10% default allocation)
- [x] All reserve inflows tracked as debt payback events on-chain — `stablecoin/reserve_manager.py: ReserveInflow` (deterministic IDs, Merkle-committable)

### 6.4 Reserve Milestones & Safety
- [x] Minimum reserve ratio enforcement by year — `stablecoin/reserve_manager.py: ReserveMilestoneEnforcer`:
  - [x] Years 1-2: 5% minimum backing
  - [x] Years 3-4: 15% minimum backing
  - [x] Years 5-6: 30% minimum backing
  - [x] Years 7-9: 50% minimum backing
  - [x] Year 10+: 100% backing (fully collateralized)
- [x] Emergency actions on backing ratio breach (halt minting, increase fees) — `ReserveMilestoneEnforcer._determine_emergency_actions()` (relative thresholds: 50% deficit → halt, 20% → fee increase)
- [x] Public API for third-party reserve verification — `stablecoin/reserve_verification.py: ReserveVerifier.get_reserve_status()` (no-auth public endpoint)
- [x] Automated daily reserve snapshots to IPFS — `stablecoin/reserve_verification.py: ReserveVerifier.create_snapshot()` (26K block interval, Merkle root, IPFS CID attachment)
- [x] Quarterly audit report generation (on-chain proof of reserves) — `stablecoin/reserve_verification.py: ReserveVerifier.generate_audit_report()` (quarter identifier, inflow summary, violation count)
- [x] Real-time backing ratio on frontend dashboard — `components/dashboard/qusd-reserve.tsx` (QUSDReserveGauge donut chart + QUSDMilestoneTimeline progress bars, polls /qusd/reserves every 15s, color-coded status, 10-year milestone roadmap)

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
- [x] Rate limiting on admin endpoints — `network/admin_api.py: _check_admin_rate_limit()` (30 req/min per IP, 429 on excess)

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
- [x] L1 unit tests (consensus, mining, crypto, UTXO, database, Dilithium) — 83 tests (test_consensus, test_database, test_quantum, test_mining_and_utxo, test_genesis_validation, test_dilithium: 26)
- [x] Batch 35 unit tests — 51 tests (test_mining: 14, test_contracts: 11, test_bridge: 14, test_stablecoin: 12 — engine init, deployment, validation, oracle, aggregation, bridge types/detection/deposit/shutdown)
- [x] P2P network tests — 43 tests (test_peer_scoring: 16, test_block_propagation: 15, test_block_sync: 12 — propagation, dedup, sync, stats)
- [x] L2 unit tests (QVM opcodes, state management, gas metering) — 147 tests (test_qvm: 52, test_qvm_reentrancy: 21, test_qvm_overflow: 28, test_qvm_gas_attacks: 15, test_qvm_quantum_opcodes: 31)
- [x] L3 unit tests (knowledge graph, reasoning, Phi, Proof-of-Thought) — 139 tests (test_knowledge_graph, test_aether, test_sephirot, test_consciousness, test_memory, test_knowledge_extractor, test_reasoning_advanced, test_sephirot_nodes, test_knowledge_graph_advanced, test_task_protocol)
- [x] Integration tests (`test_integration.py` — 13 tests: KG+reasoning, Phi+KG, consciousness, extractor, sephirot, safety)
- [x] API tests (REST endpoints, JSON-RPC, WebSocket) — 9 tests (test_network: admin API, auth, models)
- [x] Frontend tests (Vitest unit + Playwright E2E) — 5 tests (api.test: 3, theme-store.test: 2), Vitest 4 + Playwright 1.58 configured
- [x] Load tests (concurrent mining, high tx volume) — 9 tests (test_load: rapid coinbase 100x, start/stop cycling, concurrent reads, 1000 pending txs, 1000 UTXOs, 500 txs, 333-tx block, rapid difficulty, rapid rewards)
- [x] Fuzz testing (random bytecode to QVM) — 19 tests (test_fuzz_qvm: 100 random runs, all 256 single-byte opcodes, stack overflow/underflow, OOG, invalid JUMP, deep memory, arithmetic edge cases, mixed valid/invalid, REVERT, zero gas)
- [x] Privacy unit tests — 50 tests (test_privacy: 15, test_privacy_advanced: 18, test_privacy_integration: 17 — commitments, stealth, range proofs, susy swap, key images)
- [x] Config unit tests — 8 tests (test_config: economics, chain IDs, fee params)
- [x] Fee collector unit tests — 21 tests (test_fee_collector: UTXO selection, fee deduction, change, audit log, chat/contract integration)
- [x] Batch 23 unit tests — 63 tests (test_batch23: AetherWSManager 14, CirculationTracker 20, TokenIndexer 22, helpers 7)
- [x] Batch 24 unit tests — 50 tests (test_batch24: LLM adapters 15, KnowledgeDistiller 8, LLMAdapterManager 6, IPFSMemoryStore 14, key import/export 6, system prompt 1)
- [x] Test infrastructure — conftest.py with dependency stubs (Qiskit, gRPC, IPFS, etc.)

### 7.2 Security
- [x] UTXO double-spend prevention verification (`test_mining_and_utxo.py: TestDoubleSpendPrevention`)
- [x] Dilithium signature verification test vectors (`test_dilithium.py` — 26 tests: keygen sizes, signing, verification, tampered sig, wrong key/size, address derivation, CryptoManager)
- [x] QVM reentrancy protection tests (`test_qvm_reentrancy.py` — 21 tests: depth limits, static call protection, gas forwarding, storage isolation, CALL value in static, CREATE2 static, revert behavior)
- [x] QVM integer overflow tests (`test_qvm_overflow.py` — 28 tests: ADD/SUB/MUL overflow wrap, DIV/MOD by zero, EXP overflow, ADDMOD/MULMOD, signed arithmetic, SHL/SHR/SAR extremes)
- [x] Gas exhaustion attack tests (`test_qvm_gas_attacks.py` — 15 tests: infinite loops, memory expansion, stack overflow, keccak/exp/calldatacopy gas scaling, SSTORE gas, GAS opcode)
- [x] Bridge security audit preparation — `docs/BRIDGE_SECURITY_AUDIT.md` (threat model, 10 attack vectors, security checklist, confirmation depth analysis, known issues, pre-audit tasks)
- [x] Rate limiting on all public endpoints (`rpc.py: rate_limit_middleware` — per-IP, 120/min configurable via RPC_RATE_LIMIT)
- [x] Input validation on all endpoints (query param bounds checking on all /aether/* endpoints)

---

## PHASE 8: DEVOPS & DEPLOYMENT (Priority: MEDIUM)

- [x] Vercel project setup for frontend — `frontend/vercel.json` (Next.js framework, security headers incl. HSTS + CSP, image caching, API rewrites, /chat→/aether redirect)
- [x] Vercel environment variables — `vercel.json` rewrites use `${NEXT_PUBLIC_RPC_URL}` and `${NEXT_PUBLIC_WS_URL}` env vars
- [x] Vercel preview deployments (PR-based previews) — configured via vercel.json regions + standard Vercel git integration
- [x] Docker multi-stage build for backend (Python + Rust) — `Dockerfile` (Rust builder stage + Python production stage, non-root user, health check, multi-stage)
- [x] Docker Compose: Backend stack (CockroachDB + IPFS + Node) — `docker-compose.yml` (full stack: CockroachDB + IPFS + Redis + QBC Node + Prometheus + Grafana + Portainer, health checks, named volumes)
- [x] Kubernetes manifests for production backend — `deployment/kubernetes/` (namespace, qbc-node Deployment+Service+PVC, CockroachDB StatefulSet, IPFS, Prometheus+Grafana, ConfigMap+Secrets)
- [x] CI/CD pipeline (GitHub Actions — lint, test, build) — `.github/workflows/ci.yml`
- [x] Automated testing in CI (pytest + vitest + playwright) — backend-test, backend-lint, frontend-build jobs
- [x] Monitoring stack (Prometheus + Grafana dashboards) — `config/prometheus/prometheus.yml` (QBC node, CockroachDB, IPFS scraping) + `config/grafana/` (auto-provisioned Prometheus datasource, Qubitcoin Overview dashboard with 14 panels)
- [x] Log aggregation (Loki + Promtail) — `config/loki/loki-config.yml` (TSDB storage, 30-day retention, compactor, embedded cache) + `config/loki/promtail-config.yml` (Docker SD, JSON/regex log parsing, health check noise filtering) + Loki/Promtail services in `docker-compose.yml` + Loki datasource in Grafana provisioning
- [x] SSL/TLS certificates for qbc.network — `config/nginx/nginx.conf` (TLS 1.2/1.3, OCSP stapling, HSTS, security headers, rate limiting, WebSocket proxy, admin/metrics access restriction) + `config/nginx/certbot-renew.sh` (init/renew/status commands) + Nginx/Certbot services in `docker-compose.yml` (production profile)
- [x] CDN setup for frontend assets — `config/cloudflare/cloudflare-config.json` (full_strict SSL, aggressive caching, static asset edge TTL 30d, API bypass, WAF, rate limiting, bot management, Brotli, HTTP/3, image optimization, firewall rules for admin/metrics)
- [x] DNS configuration for qbc.network — `config/dns/zone.conf` (Vercel CNAME at root, api/rpc subdomains, seed node A records, P2P SRV records, MX/SPF/DMARC for email, CAA cert restriction, monitoring subdomains)

---

## PHASE 9: DOCUMENTATION (Priority: MEDIUM)

- [x] Whitepaper (`docs/WHITEPAPER.md` — v1.0.0, 2680 lines, covers L1 core + privacy + bridges + QUSD)
- [x] QVM Whitepaper (`docs/QVM_WHITEPAPER.md` — institutional features, 5 patents)
- [x] AetherTree AGI Whitepaper (`docs/AETHERTREE_WHITEPAPER.md` — Tree of Life, PoT, consciousness)
- [x] Economics documentation (`docs/ECONOMICS.md`)
- [x] CLAUDE.md master development guide
- [x] API documentation (OpenAPI/Swagger auto-generated from FastAPI) — FastAPI app configured with title/version/description; Swagger UI at /docs, ReDoc at /redoc
- [x] Developer SDK documentation — `docs/SDK.md` (REST, JSON-RPC, WebSocket, L1/L2/L3 integration, admin API, rate limits)
- [x] Smart contract developer guide — `docs/SMART_CONTRACTS.md` (QVM deployment, token standards, quantum opcodes, Hardhat/Foundry config, fee estimation)
- [x] Aether Tree integration guide — `docs/AETHER_INTEGRATION.md` (chat API, consciousness metrics, knowledge graph, PoT, Sephirot, WebSocket streaming, integration patterns)
- [x] Deployment guide (`docs/DEPLOYMENT.md` — backend setup, frontend Vercel, Docker, production config, monitoring, troubleshooting)
- [x] Contributing guidelines (`CONTRIBUTING.md` — dev setup, code conventions, testing, risk classification, security)

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

*Last updated: 2026-02-20*
*Track progress here. Update status after every session.*
