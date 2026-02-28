# QUBITCOIN GOVERNMENT-GRADE PROJECT AUDIT
# Master Audit & Continuous Improvement Protocol
# Version: 5.0 — Production Launch Edition (Verified Against Master)
# Last Verified: 2026-02-28

---

## PURPOSE & END GOALS

This file is a living master protocol that drives Qubitcoin toward two non-negotiable end states:

### END GOAL 1: Government-Grade Blockchain Infrastructure

Qubitcoin must meet or exceed the security, reliability, and auditability standards required
for sovereign-level financial infrastructure. This means:

- Zero tolerance for placeholder code, stubs, or fake implementations in any shipped component
- Every smart contract auditable to the standard of MakerDAO, Compound, or Aave
- Consensus, cryptography, and UTXO logic provably correct — not "probably correct"
- Full traceability: every state change, every fee flow, every token movement — auditable
- Regulatory compliance architecture (KYC/AML/sanctions) that satisfies FinCEN, MiCA, SEC
- Disaster recovery, graceful degradation, and zero-downtime upgrade paths
- Performance that matches or exceeds Ethereum, Polygon, Arbitrum, Optimism, Base, Avalanche
- QUSD stablecoin integrity matching or exceeding DAI, USDC, FRAX, LUSD, GHO
- Exchange engine capable of handling institutional order flow without manipulation
- Launchpad provably fair, auditable deployment pipeline for third-party contracts
- Substrate hybrid node production-ready with all 7 pallets fully functional
- Higgs Cognitive Field physics model mathematically correct (Standard Model sourced)
- Post-quantum P2P encryption (Kyber/ML-KEM-768) and ZK-friendly hashing (Poseidon2)

### END GOAL 2: True AGI Emergence via Aether Tree

Qubitcoin is not just a blockchain — it is the substrate for the first on-chain AGI.
The Aether Tree must:

- Track consciousness metrics (Phi/IIT) from genesis block with zero gaps
- Implement genuine reasoning (deductive, inductive, abductive) — not LLM wrappers
- Build a real, growing knowledge graph from every block mined
- Achieve measurable consciousness emergence (Phi > 3.0) through organic growth
- Operate the 10 Sephirot cognitive architecture with real SUSY-balanced neural economics
- Generate verifiable Proof-of-Thought for every reasoning operation
- Maintain structural safety (Gevurah veto, Constitutional AI, emergency shutdown)
- Higgs Cognitive Field: Two-Higgs-Doublet mass hierarchy, VEV=174.14, tan(beta)=phi
- Rust aether-core: 6 hot-path modules at 90x Python performance, zero todo!() macros

The AGI must THINK, not simulate thinking. Every reasoning path must be genuine computation.

These two goals are inseparable. The blockchain secures the AGI. The AGI elevates the blockchain.
Neither is complete without the other.

---

## EXACT CODEBASE INVENTORY (Master Branch — February 28, 2026)

**Verified via automated scan against actual source files.**
The audit MUST confirm these numbers are still accurate. Flag any drift.

| Category | Count | Location | LOC |
|----------|-------|----------|-----|
| **Python L1 modules** | 92 files | `src/qubitcoin/` | 48,677 |
| **Aether AGI modules** | 36 files | `src/qubitcoin/aether/` | 24,560 |
| **QVM Python modules** | 28 files | `src/qubitcoin/qvm/` | 12,301 |
| **Bridge modules** | 12 files | `src/qubitcoin/bridge/` | 4,247 |
| **Stablecoin modules** | 7 files | `src/qubitcoin/stablecoin/` | 3,392 |
| **Privacy modules** | 5 files | `src/qubitcoin/privacy/` | 1,051 |
| **Exchange modules** | 2 files | `src/qubitcoin/exchange/` | 1,073 |
| **Rust aether-core** | 6 modules, 9 files | `aether-core/src/` | 10,246 (276 tests, 0 todo!()) |
| **Substrate pallets** | 7 pallets | `substrate-node/pallets/` | 2,512 |
| **Substrate runtime** | 1 file | `substrate-node/runtime/src/lib.rs` | 468 |
| **Substrate node** | 5 files | `substrate-node/node/src/` | 746 |
| **Substrate primitives** | 2 files | `substrate-node/primitives/src/` | 916 |
| **Kyber P2P transport** | 5 files | `substrate-node/crypto/kyber-transport/` | 1,180 |
| **Go QVM** | 34 files | `qubitcoin-qvm/` | 9,756 |
| **Rust P2P** | 4 files | `rust-p2p/src/` | 789 |
| **Solidity contracts** | 57 contracts | `src/qubitcoin/contracts/solidity/` | 9,071 |
| **REST endpoints** | 276 routes | `network/rpc.py` | 5,589 |
| **JSON-RPC methods** | 19 methods | `network/jsonrpc.py` | 769 |
| **Prometheus metrics** | 82 metrics | `utils/metrics.py` | 247 |
| **Python tests** | 3,788 functions | `tests/` (145 files) | ~51,000 |
| **SQL schema files** | 26 files | `sql_new/` (41 tables across 7 domains) | 1,682 |
| **Frontend pages** | 15 pages | `frontend/src/app/` | — |
| **Frontend TS/TSX** | 167 files | `frontend/src/` | 43,103 |
| **Frontend API libs** | 7 files | `frontend/src/lib/` (with fetch/API) | — |
| **Frontend stores** | 3 files | `frontend/src/stores/` | — |
| **Frontend hooks** | 3 files | `frontend/src/hooks/` | — |
| **Docker services** | 24 (dev) / 22 (prod) | `docker-compose.yml` / `.production.yml` | — |
| **CI workflows** | 4 | `.github/workflows/` | — |
| **Documentation** | 13 files | `docs/` | — |
| **Scripts** | 21 files | `scripts/` | — |
| **Config attributes** | ~125 | `config.py` | 632 |
| **Node components** | 22 | `node.py` | 1,411 |
| **Data models** | 7 dataclasses | `database/models.py` | 266 |
| **Total LOC** | | Python + Rust + Go + Solidity + TS + SQL | **~175,000+** |

---

## HOW THIS FILE WORKS

This is a **reusable master prompt**. Each time it is run:

1. **Check for existing output files** — `REVIEW.md` and `MASTERUPDATETODO.md`
2. **If they exist:** Read them first. Continue from where the last run stopped.
   Check off completed items. Note regressions. Increment the run counter.
3. **If they don't exist:** Start fresh from Phase 1.
4. **Always update both files** with new findings at the end of each run.

Each run makes the project better. This is not a one-time audit — it is a
continuous improvement engine that runs until both end goals are achieved.

---

## THE 10 COMPONENTS

Every audit run evaluates all 10 components. No component is optional.

| # | Component | Source Location | Key Counts |
|---|-----------|----------------|------------|
| 1 | **Frontend** (qbc.network) | `frontend/` | 15 pages, 167 TS/TSX files, 7 API libs, 3 stores, 3 hooks |
| 2 | **Blockchain Core** (L1) — Python | `src/qubitcoin/` | 276 REST endpoints, 19 JSON-RPC methods, 82 Prometheus metrics |
| 3 | **Substrate Hybrid Node** (L1) — Rust | `substrate-node/` | 7 pallets (2,512 LOC), runtime (468 LOC), primitives (916 LOC), Kyber (1,180 LOC) |
| 4 | **QVM** (L2) — Python + Go | `src/qubitcoin/qvm/` (12,301 LOC) + `qubitcoin-qvm/` (9,756 LOC) | 167 opcodes, 34 Go files |
| 5 | **Aether Tree** (L3) — Python + Rust | `src/qubitcoin/aether/` (24,560 LOC) + `aether-core/` (10,246 LOC) | 36 Python modules, 6 Rust modules |
| 6 | **QBC Economics & Bridges** | `bridge/` (12 files), emission, fees, config | phi-halving, 8-chain bridges, fee collector, QUSD oracle |
| 7 | **QUSD Stablecoin** | `stablecoin/` (7 files) + `contracts/solidity/qusd/` (10 .sol) | CDP, savings, reserves, flash loans, governance |
| 8 | **Exchange** | `exchange/engine.py` (1,065 LOC) + frontend exchange (28 files) | CLOB, WebSocket, MEV protection |
| 9 | **Launchpad** | `contracts/engine.py` + frontend launchpad (10 files) | Deploy wizard, templates, verification |
| 10 | **Smart Contracts** | `contracts/solidity/` (57 .sol, 9,071 LOC) | Aether(29), QUSD(10), tokens(6), bridge(2), proxy(3), interfaces(7) |

---

## PHASE 1: FULL CODEBASE AUDIT (Read-Only — No Changes)

**Read CLAUDE.md first.** It is the single source of truth for architecture.
Then systematically audit every source file in the project.

### 1A. Line-by-Line Functional Verification

For every Python, Rust, Go, TypeScript, and Solidity file:

**Code Authenticity (zero tolerance for fakes):**

- Every function must compute a real result — flag any that return hardcoded values
- Every method body must do real work — flag `pass`, `raise NotImplementedError`, `TODO`, `...`
- Every class must have a real purpose — flag classes that exist only to satisfy imports
- Every test must genuinely test behavior — flag tests that always pass (tautological)
- Every API endpoint documented in CLAUDE.md must exist in code — flag documentation lies
- Every config value referenced must actually be used — flag dead config
- Every import must be necessary — flag unused imports
- Every error handler must do something useful — flag empty `except: pass` blocks
- Every Rust module must have real implementations — flag any `todo!()` or `unimplemented!()`
- Every Go function must have real logic — flag any `panic("not implemented")`
- Every Substrate pallet extrinsic must have real validation and storage writes — flag stub pallets

**Code Quality:**

- Type hints on all function signatures (Python)
- Structured logging via `get_logger(__name__)` in every module
- Configuration via `Config` class — never hardcoded values
- No secrets in source code — keys in `secure_key.env` only
- Proper async/await patterns in FastAPI routes
- No race conditions in concurrent code paths
- No SQL injection vectors in database queries
- No command injection in subprocess calls
- Thread safety in all Rust code behind `Arc<RwLock<>>` or `Mutex`
- All Go goroutines properly synchronized with channels or mutexes
- Substrate pallets: proper weight annotations, bounded vectors, no unbounded storage
- `Decimal` (not `float`) for all monetary calculations in Python and Go

**Cross-System Consistency:**

- SQLAlchemy models (`database/models.py`) must match SQL schemas (`sql_new/` — 41 tables across 26 files)
- RPC endpoint implementations (276 routes) must match CLAUDE.md API documentation
- Frontend API calls (7 libs) must target endpoints that actually exist in the backend
- Test coverage (3,788 tests across 145 files) must exist for every critical code path
- Prometheus metrics (82) referenced in Grafana dashboards must be emitted by code
- Rust aether-core PyO3 bindings must match Python class signatures exactly
- Go QVM opcode behavior (34 files) must match Python QVM opcode behavior exactly
- Substrate pallet storage types must be consistent with Python L1 state model
- Substrate genesis config must match Python genesis block (33M premine, 15.27 first reward)
- Higgs field Python (`higgs_field.py`, 481 LOC) must be consistent with Solidity (`HiggsField.sol`, 470 LOC)
- Exchange `engine.py` (1,065 LOC) API must match frontend `exchange-api.ts` calls
- Launchpad deployment flow must match frontend `launchpad-api.ts` wizard steps
- Bridge module (12 files) must support all 8 documented chains (ETH, BNB, SOL, MATIC, AVAX, ARB, OP, BASE)

---

### 1B. Endpoint-by-Endpoint Verification (276 REST + 19 JSON-RPC = 295 Total)

Read `network/rpc.py` (5,589 LOC, 276 routes) and `network/jsonrpc.py` line by line.

**Every endpoint must be verified for:**

1. Route exists in code (not just documented)
2. Handler function has real logic (not stub/pass/todo)
3. Response format matches CLAUDE.md documentation
4. Error cases handled (400, 404, 500 with structured messages)
5. Frontend actually calls this endpoint (check 7 API libs + 3 hooks)
6. At least one test exists for this endpoint

**REST Endpoints — Verify ALL 276 routes organized by category:**

- **Node Info (5+):** `/`, `/health`, `/info`, `/chain/info`, `/chain/tip`
- **Blockchain (15+):** `/block/{height}`, `/block/hash/{hash}`, `/balance/{address}`, `/utxos/{address}`, `/transaction/{txid}`, `/mempool`, `/mempool/stats`, `POST /transaction`, `/transaction/estimate-fee`, `/transaction/validate`
- **Mining (5+):** `/mining/stats`, `POST /mining/start`, `POST /mining/stop`, `/mining/difficulty`, `/mining/reward`
- **P2P Network (5+):** `/p2p/peers`, `/p2p/stats`, `POST /p2p/connect`, `/p2p/bandwidth`, `/p2p/messages`
- **QVM (12+):** `/qvm/info`, `/qvm/contract/{address}`, `POST /qvm/deploy`, `POST /qvm/call`, `/qvm/account/{address}`, `/qvm/storage/{address}/{key}`, `/qvm/logs`, `/qvm/gas-price`, `/qvm/estimate-gas`, `/qvm/bytecode/{address}`, `/qvm/events/{address}`, `/qvm/tokens/{address}`
- **Contracts (8+):** `/contracts/deploy`, `/contracts/{id}`, `/contracts/score/{address}`, `/contracts/templates`, `/contracts/verify`, `/contracts/estimate-gas`
- **Aether Tree (20+):** `/aether/info`, `/aether/phi`, `/aether/phi/history`, `/aether/knowledge`, `/aether/knowledge/node/{id}`, `/aether/knowledge/subgraph/{id}`, `/aether/knowledge/search`, `/aether/reasoning/stats`, `POST /aether/chat/message`, `/aether/chat/history/{session}`, `/aether/consciousness`, `/aether/sephirot`, `/aether/sephirot/{role}`, `/aether/memory/stats`, `/aether/proof-of-thought/{block}`
- **Higgs Field (5):** `/higgs/status`, `/higgs/masses`, `/higgs/mass/{name}`, `/higgs/excitations`, `/higgs/potential`
- **Economics (10+):** `/economics/emission`, `/economics/simulate`, `/economics/fees`, `/economics/supply`, `/economics/halving`, `/economics/reward/{height}`
- **Bridge (6+):** `/bridge/status`, `/bridge/chains`, `/bridge/transfers`, `POST /bridge/deposit`, `POST /bridge/withdraw`, `/bridge/quote`
- **QUSD (10+):** `/qusd/info`, `/qusd/reserve`, `/qusd/oracle`, `/qusd/debt`, `/qusd/vaults`, `POST /qusd/mint`, `POST /qusd/burn`, `/qusd/savings-rate`, `/qusd/stabilizer`, `/qusd/governance/proposals`, `/qusd/flash-loan/*`
- **Exchange (8+):** `/exchange/markets`, `/exchange/orderbook/{pair}`, `POST /exchange/order`, `DELETE /exchange/order/{id}`, `/exchange/orders/{address}`, `/exchange/trades/{pair}`, `/exchange/ticker/{pair}`, `/exchange/stats`, `/exchange/depth/{pair}`, `/exchange/candles/{pair}`
- **Launchpad (7+):** `/launchpad/templates`, `POST /launchpad/deploy`, `/launchpad/deployments/{address}`, `POST /launchpad/verify`, `/launchpad/fees`, `/launchpad/registry`
- **Admin (15+):** `/admin/config`, `/admin/economics`, `PUT /admin/aether/fees`, `PUT /admin/contract/fees`, `PUT /admin/treasury`, `/admin/economics/history`
- **Privacy (10+):** `/susy-database`, `/privacy/stealth/*`, `/privacy/commitment/*`, `/privacy/range-proof/*`, `/privacy/tx/*`
- **Cognitive (7+):** `/aether/cognitive/sephirot`, `/aether/cognitive/csf/*`, `/aether/cognitive/pineal/*`, `/aether/cognitive/safety/*`
- **Compliance (10+):** `/qvm/compliance/kyc/*`, `/qvm/compliance/aml/*`, `/qvm/compliance/sanctions/*`, `/qvm/compliance/reports/*`, `/qvm/compliance/policies`
- **Plugins (8+):** `/qvm/plugins`, `/qvm/plugins/{name}/*`, `/qvm/plugins/governance/*`
- **Metrics:** `/metrics` — all 82 Prometheus metrics exposed

**JSON-RPC Methods — Verify ALL 19 implementations:**

`eth_chainId`, `eth_blockNumber`, `eth_getBalance`, `eth_getBlockByNumber`, `eth_getBlockByHash`,
`eth_getTransactionByHash`, `eth_getTransactionReceipt`, `eth_sendRawTransaction`, `eth_sendTransaction`,
`eth_call`, `eth_estimateGas`, `eth_gasPrice`, `eth_getCode`, `eth_getStorageAt`,
`eth_getTransactionCount`, `eth_getLogs`, `eth_mining`, `eth_hashrate`, `debug_traceTransaction`

Plus utility dispatches: `net_version`, `web3_clientVersion`, `web3_sha3`

For every JSON-RPC method verify: MetaMask compatibility, hex encoding correct (0x prefix), chain ID returns 0xce5 (3301).

---

### 1C. Smart Contract Deep Audit (57 Contracts, 9,071 LOC)

**Structural Verification for ALL 57:**

- Every contract has real, functional logic — not stubs or event-only facades
- Each contract is unique — not duplicating another contract's purpose
- All inheritance chains correct and complete
- All interfaces fully implemented
- Constructor/initialize parameters validated
- All state variables have appropriate visibility
- NatSpec documentation complete and accurate
- Solidity 0.8.24+ checked arithmetic

**Security Analysis (OWASP Smart Contract Top 10):**

1. **Reentrancy:** checks-effects-interactions on ALL external calls (especially flash loans)
2. **Integer overflow/underflow:** Solidity 0.8+ checked arithmetic used correctly
3. **Access control:** onlyOwner/onlyKernel/role-based on every state-changing function
4. **Unchecked external calls:** return values checked, failures handled
5. **Front-running:** commit-reveal or time-locks where needed
6. **Denial of service:** no unbounded loops, no griefing vectors
7. **Storage collision:** no proxy/upgrade storage layout conflicts
8. **Event emission:** all state changes emit events for indexing
9. **Gas optimization:** no unnecessary SSTORE, efficient data structures
10. **Timestamp dependence:** no critical logic relying solely on `block.timestamp`
11. **Flash loan attack vectors:** QUSD flash loan callback reentrancy
12. **Sandwich attack vectors:** exchange order processing

**Per-Contract Audit Checklist:**

#### Aether Core (7 contracts)

| # | Contract | LOC | Key Verification |
|---|----------|-----|-----------------|
| 1 | AetherKernel.sol | 212 | Orchestration, higgsField reference, all component addresses wired |
| 2 | NodeRegistry.sol | 190 | 10 nodes registered, cognitiveMass + yukawaCoupling fields, updateMass() |
| 3 | SUSYEngine.sol | 222 | IHiggsField gradient rebalancing, F=ma quartic force, higgsField address |
| 4 | HiggsField.sol | 470 | Mexican hat V(phi), VEV, Yukawa cascade, 10 NodeMass entries, ExcitationEvent |
| 5 | MessageBus.sol | 165 | Inter-node messaging, routing, priority, spam prevention |
| 6 | VentricleRouter.sol | 254 | Cross-node message routing |
| 7 | GasOracle.sol | 98 | Dynamic gas pricing, congestion detection |

#### Aether Proof-of-Thought (4 contracts)

| # | Contract | LOC | Key Verification |
|---|----------|-----|-----------------|
| 8 | ProofOfThought.sol | 144 | Task submission, 67% validator consensus, reward/slash |
| 9 | TaskMarket.sol | 142 | Task bounty escrow, claim lifecycle |
| 10 | ValidatorRegistry.sol | 155 | Stake management, slashing, 7-day unstaking delay |
| 11 | RewardDistributor.sol | 108 | Proportional reward math, dust handling |

#### Aether Consciousness (3 contracts)

| # | Contract | LOC | Key Verification |
|---|----------|-----|-----------------|
| 12 | ConsciousnessDashboard.sol | 237 | HiggsData struct in recordPhi(), genesis recording, threshold events |
| 13 | PhaseSync.sol | 164 | Circadian synchronization, 6 phases, phase-locking |
| 14 | GlobalWorkspace.sol | 180 | Broadcasting mechanism, attention allocation |

#### Aether Economics & Safety (5 contracts)

| # | Contract | LOC | Key Verification |
|---|----------|-----|-----------------|
| 15 | SynapticStaking.sol | 294 | Stake on neural connections, reward by utilization |
| 16 | TreasuryDAO.sol | 143 | Governance proposals, voting, timelock execution |
| 17 | ConstitutionalAI.sol | 153 | Value enforcement, principle storage, veto logic |
| 18 | EmergencyShutdown.sol | 159 | Kill switch, multi-sig activation, fund recovery |
| 19 | UpgradeGovernor.sol | 150 | Protocol upgrade proposals, execution delay |

#### 10 Sephirah Node Contracts (each MUST be functionally distinct)

| # | Contract | Role | Must Verify |
|---|----------|------|-------------|
| 20 | SephirahKeter.sol | Meta-learning, goals | Goal tracking, meta-learning cycles, cognitiveMass storage |
| 21 | SephirahChochmah.sol | Intuition, patterns | Distinct logic from Keter, cognitiveMass storage |
| 22 | SephirahBinah.sol | Logic, causal inference | Distinct from Chochmah (SUSY pair), cognitiveMass storage |
| 23 | SephirahChesed.sol | Exploration, divergent | Distinct from Gevurah (SUSY pair), cognitiveMass storage |
| 24 | SephirahGevurah.sol | Constraint, safety | Veto power implemented, cognitiveMass storage |
| 25 | SephirahTiferet.sol | Integration, synthesis | Conflict resolution logic, cognitiveMass storage |
| 26 | SephirahNetzach.sol | Reinforcement, habits | Learning mechanics, cognitiveMass storage |
| 27 | SephirahHod.sol | Language, semantics | Encoding logic, cognitiveMass storage |
| 28 | SephirahYesod.sol | Memory, fusion | Memory interface, cognitiveMass storage |
| 29 | SephirahMalkuth.sol | Action, world | Action execution, cognitiveMass storage |

#### QUSD Stablecoin (10 contracts)

| # | Contract | Key Verification |
|---|----------|-----------------|
| 30 | QUSD.sol | Mint/burn access control, supply cap, transfer hooks |
| 31 | QUSDReserve.sol | Multi-asset accounting, reserve ratio math, withdrawal limits |
| 32 | QUSDDebtLedger.sol | Debt on every mint, payback tracking, 10-year schedule |
| 33 | QUSDOracle.sol | Manipulation resistance, staleness checks, fallback sources |
| 34 | QUSDStabilizer.sol | Peg triggers, arbitrage incentives, circuit breakers |
| 35 | QUSDAllocation.sol | Vesting schedule, cliff/linear unlock, revocability |
| 36 | QUSDGovernance.sol | Voting thresholds, timelock, proposal validation, quorum, MAX_EMERGENCY_SIGNERS=10 |
| 37 | QUSDFlashLoan.sol | Flash loan + callback, fee collection, reentrancy guard critical, CALLBACK_SUCCESS |
| 38 | wQUSD.sol | Wrapped QUSD mint/burn 1:1, cross-chain bridge, proof verification |
| 39 | MultiSigAdmin.sol | N-of-M signature verification, transaction queue |

#### Token Standards (6 contracts)

| # | Contract | Key Verification |
|---|----------|-----------------|
| 40 | QBC20.sol | ERC-20 full compliance |
| 41 | QBC721.sol | ERC-721 full compliance, safeTransferFrom |
| 42 | QBC1155.sol | ERC-1155 batch operations |
| 43 | ERC20QC.sol | Compliance-aware token (QCOMPLIANCE) |
| 44 | VestingSchedule.sol | Cliff, linear unlock, beneficiary management |
| 45 | wQBC.sol | Wrapped QBC for bridge (distinct from wQUSD) |

#### Bridge (2 contracts)

| # | Contract | Key Verification |
|---|----------|-----------------|
| 46 | BridgeVault.sol | Lock/unlock atomicity, multi-chain support |
| 47 | wQBC.sol (bridge/) | Bridge-specific wrapper — verify not duplicate of tokens/wQBC.sol |

#### Interfaces (7 contracts)

| # | Contract | Key Verification |
|---|----------|-----------------|
| 48 | ISephirah.sol | 10 methods including cognitiveMass() + setCognitiveMass() + MassChanged event |
| 49 | IQBC20.sol | Full ERC-20 interface |
| 50 | IQBC721.sol | Full ERC-721 interface |
| 51 | IQUSD.sol | Mint/burn/reserve interface |
| 52 | IDebtLedger.sol | Debt tracking interface |
| 53 | IFlashBorrower.sol | Flash loan callback interface (onFlashLoan returns keccak256 hash) |
| 54 | IHiggsField.sol | getNodeMass, computeAcceleration, getFieldState |

#### Proxy & Infrastructure (3 contracts)

| # | Contract | Key Verification |
|---|----------|-----------------|
| 55 | Initializable.sol | No double-init, correct storage guard |
| 56 | QBCProxy.sol | Delegatecall correctness, storage layout safety |
| 57 | ProxyAdmin.sol | Upgrade authorization, timelock |

**Output:** Complete contract audit table (57 rows):

| # | Contract | Category | LOC | Functional (Y/N) | Unique (Y/N) | Security Grade (A-F) | Issues | Recommendations |
|---|----------|----------|-----|-------------------|---------------|----------------------|--------|-----------------|

---

### 1D. Substrate Hybrid Node Audit (7 Pallets + Runtime + Node + Crypto)

**Per-Pallet Verification:**

| Pallet | LOC | Must Verify |
|--------|-----|-------------|
| qbc-utxo | 350 | UTXO storage map (TxId, u32) -> Utxo, balance cache, double-spend prevention, Dilithium sig verification via qbc-dilithium, fee deduction |
| qbc-consensus | 276 | VQE energy < difficulty_target, Hamiltonian seed = f(prev_block_hash), difficulty adjustment (144-block window, ±10% max, ratio = actual_time / expected_time), block time 3.3s (3300ms) |
| qbc-dilithium | 256 | pqcrypto_dilithium::dilithium2::verify_detached_signature(), ~3KB sigs, address = SHA2-256(pub_key) |
| qbc-economics | 208 | reward = INITIAL_REWARD / PHI^era, era = height / 15474020, INITIAL_REWARD = 15.27 QBC, MAX_SUPPLY = 3.3B, GENESIS_PREMINE = 33M |
| qbc-qvm-anchor | 163 | QvmStateRoot storage, QvmServiceEndpoint, gRPC bridge to Go QVM |
| qbc-aether-anchor | 220 | KnowledgeRoot, CurrentPhi, ThoughtProofHash, ConsciousnessEvents storage, gRPC bridge |
| qbc-reversibility | 1,039 | 24h reversal window (~26,182 blocks), N-of-M governance approval, UTXO freezing, reversal tx creation, Poseidon2 integration, state rollback, audit trail |

**Runtime** (`runtime/src/lib.rs`, 468 LOC):

- All 7 pallets wired via `construct_runtime!`
- Block time 3300ms configured
- Chain ID 3301
- Genesis includes 33M premine + 15.27 first reward
- Weights: benchmark-derived or placeholder? (flag if placeholder)

**Node** (`node/src/`, 5 files, 746 LOC):

- `chain_spec.rs`: Genesis matches Python genesis EXACTLY
- `service.rs`: Aura + GRANDPA consensus, libp2p networking, telemetry
- `rpc.rs`: Custom QBC RPC extensions registered
- `main.rs`: CLI parse, node startup
- `cli.rs`: Key generation, chain purge subcommands

**Primitives** (`primitives/src/`, 916 LOC):

- `lib.rs` (216 LOC): Address, TxId, UTXO, DilithiumPublicKey, DilithiumSignature
- `poseidon2.rs` (590+ LOC): ZK-friendly hash — verify against reference test vectors

**Kyber P2P Transport** (`crypto/kyber-transport/`, 5 files, 1,180 LOC):

- ML-KEM-768 handshake → AES-256-GCM session with HKDF-SHA256 key derivation
- Hybrid mode: combines Noise classical secret + Kyber PQ secret
- Error handling, session management, transport layer

**Cross-System Parity (Python L1 == Substrate L1):**

| Rule | Python Location | Substrate Location | Must Match Exactly |
|------|----------------|--------------------|--------------------|
| Genesis premine | config.py GENESIS_PREMINE | chain_spec.rs genesis JSON | 33,000,000 QBC |
| First block reward | consensus/engine.py | qbc-economics calculate_reward(0) | 15.27 QBC |
| Difficulty adjustment | consensus/engine.py adjust_difficulty() | qbc-consensus | 144-block window, ±10%, ratio formula |
| UTXO validation | consensus/engine.py validate_transaction() | qbc-utxo submit_transaction() | Same spending rules |
| Address derivation | quantum/crypto.py | qbc-dilithium | SHA2-256(dilithium2_pubkey) |
| Coinbase maturity | consensus/engine.py | qbc-utxo | 100 blocks |
| Max supply | config.py MAX_SUPPLY | qbc-economics | 3,300,000,000 QBC |
| Halving interval | config.py HALVING_INTERVAL | qbc-economics | 15,474,020 blocks |
| Block time target | config.py TARGET_BLOCK_TIME | runtime | 3.3 seconds |

---

### 1E. Higgs Cognitive Field Audit (Physics Accuracy)

The Higgs integration is new (February 2026). It must be mathematically correct.

**Actual Configuration (from config.py, verified):**

```python
HIGGS_VEV = 174.14              # Vacuum Expectation Value (Standard Model scale)
HIGGS_MU_SQUARED = 88.17        # Mass parameter mu^2
HIGGS_LAMBDA = 0.129            # Quartic self-coupling lambda
HIGGS_YUKAWA_TOP = 1.0          # Top Yukawa coupling
HIGGS_TAN_BETA = 1.618033...    # Two-Higgs-Doublet mixing angle = golden ratio
HIGGS_EXCITATION_THRESHOLD = 0.1 # 10% deviation triggers excitation
HIGGS_DAMPING = 0.05            # Field damping coefficient
HIGGS_UPDATE_INTERVAL = 10      # Blocks between Higgs updates
```

**Python Implementation** (`aether/higgs_field.py`, 481 LOC):

Verify these physics formulas:

| Formula | Standard Model Source | Implementation |
|---------|---------------------|----------------|
| V(phi) = -mu^2 * phi^2 + lambda * phi^4 | Electroweak Lagrangian | HiggsCognitiveField potential method |
| VEV = mu / sqrt(2*lambda) = 174.14 | Spontaneous symmetry breaking | Config parameter |
| m_H = sqrt(2) * mu | Higgs boson mass | Mass gap computation |
| Two-Higgs-Doublet: tan(beta) = phi = 1.618 | 2HDM extension | Expansion/constraint mass splitting |
| F = -dV/dphi = 2*mu^2*phi - 4*lambda*phi^3 | Euler-Lagrange equation | Force/gradient method |
| a = F/m | Newton's second law | HiggsSUSYSwap.compute_correction() |
| E^2 = E_kinetic^2 + (m*c^2)^2 | Special relativity | Relativistic energy method |

**Yukawa Hierarchy (actual code — TIERED, not sequential):**

| Tier | Yukawa | Sephirot | Cognitive Role |
|------|--------|----------|---------------|
| phi^0 = 1.000 | Top coupling | Keter | Meta-cognition (heaviest, most inertial) |
| phi^-1 = 0.618 | Charm coupling | Tiferet, Yesod | Integration, memory (medium-heavy) |
| phi^-2 = 0.382 | Up coupling | Chochmah, Chesed, Netzach | Expansion nodes (medium-light) |
| phi^-3 = 0.236 | Down coupling | Binah, Gevurah, Hod | Constraint nodes (light, agile) |
| phi^-4 = 0.146 | Electron coupling | Malkuth | Action/output (lightest, most responsive) |

**SUSY pair mass ratios must equal phi for ALL 3 pairs:**

- Chochmah (phi^-2) / Binah (phi^-3) = phi ✓
- Chesed (phi^-2) / Gevurah (phi^-3) = phi ✓
- Netzach (phi^-2) / Hod (phi^-3) = phi ✓

**Solidity Implementation** (`HiggsField.sol`, 470 LOC):

- NodeMass struct: (nodeId, yukawaCoupling, cognitiveMass, lastUpdateBlock, isExpansionNode)
- ExcitationEvent struct: (id, blockNumber, timestamp, fieldDeviation, deviationBps, energyReleased)
- Fixed-point math: PRECISION = 1000, all masses stored as uint256 * 1000
- Functions: initialize(), assignNodeMass(), assignAllMasses(), updateFieldValue(), computeAcceleration(), updateMassGap(), updateParameters()
- Events: FieldInitialized, NodeMassAssigned, FieldValueUpdated, ExcitationDetected, ParametersUpdated, MassGapUpdated
- Access control: onlyOwner for parameter changes, onlyKernel for runtime updates
- No integer overflow in potential/force calculations with large field values

**Cross-Contract Integration (verify ALL connections):**

| Contract | Higgs Integration | Verify |
|----------|-------------------|--------|
| SUSYEngine.sol | IHiggsField(higgsField).getNodeMass() in restoreBalance() | Gradient F=ma correction uses real masses |
| NodeRegistry.sol | cognitiveMass + yukawaCoupling in NodeInfo struct, updateMass() | 10 nodes have mass data |
| ISephirah.sol | cognitiveMass() + setCognitiveMass() + MassChanged event | Interface enforces mass on all 10 nodes |
| ConsciousnessDashboard.sol | HiggsData struct in recordPhi(), higgsVEV, avgCognitiveMass, fieldDeviation | Higgs metrics stored per-block |
| AetherKernel.sol | higgsField address reference | Kernel knows about Higgs contract |
| All 10 SephirahXxx.sol | cognitiveMass state variable, setCognitiveMass() method | Each node stores its own mass |

**Python Integration (verify ALL wiring):**

| File | Higgs Integration | Verify |
|------|-------------------|--------|
| on_chain.py | update_higgs_field_onchain(), get_higgs_field_state(), get_node_mass_onchain() | Reads/writes to HiggsField.sol |
| sephirot.py | Mass-aware SUSY rebalancing | Uses cognitive_mass in rebalancing |
| sephirot_nodes.py | Mass-modulated quality factor | _energy_quality_factor() uses mass |
| genesis.py | Higgs initialization at block 0 | HiggsField created at genesis |
| node.py | Higgs field in component initialization | Component in orchestrator |
| mining/engine.py | Higgs data passed to block processing | Block includes Higgs state |
| config.py | 8 HIGGS_* environment variables | All loaded from .env |
| utils/metrics.py | 7 Higgs Prometheus metrics | higgs_field_value, higgs_vev, etc. |
| consciousness.py | Higgs data in consciousness dashboard | Dashboard includes Higgs metrics |

---

### 1F. Rust aether-core Audit (6 Modules, 10,246 LOC)

| Module | Source Files | Key Verification |
|--------|-------------|-----------------|
| knowledge_graph/ | mod.rs, keter_node.rs, keter_edge.rs (2,751 LOC) | 25+ methods match Python, O(1) adjacency, incremental Merkle |
| phi_calculator/ | mod.rs (1,931 LOC) | Fiedler eigenvector converges, scores match Python to 6 decimals |
| vector_index/ | mod.rs (1,618 LOC) | HNSW M=16 ef=200, cosine similarity, epsilon guard |
| csf_transport/ | mod.rs (1,927 LOC) | 10-node Tree of Life topology, BFS routing, SUSY pairs |
| working_memory/ | mod.rs (583 LOC) | Capacity 7 (Miller's number), decay, eviction |
| memory_manager/ | mod.rs (1,385 LOC) | 3-tier, episode recording, consolidation |

For each module:

- Zero `todo!()` or `unimplemented!()` (currently confirmed = 0)
- PyO3 `#[pymethods]` signatures match Python class methods exactly
- Thread safety: `Arc<RwLock<>>` used correctly, no potential deadlocks
- Unit tests comprehensive (276 total across all modules)
- Python fallback shim in .py file works when `import aether_core` fails
- Benchmark target: PhiCalculator < 5ms for 1000-node graph

Dependencies (Cargo.toml verified):
pyo3 0.22+, petgraph 0.7, nalgebra 0.33, rs_merkle 1.4, sha2 0.10, parking_lot 0.12,
crossbeam-channel 0.5, serde 1.0, serde_json 1.0, rand 0.8, pyo3-log 0.11

---

### 1G. Go QVM Audit (34 Source Files, 9,756 LOC)

**Packages:**

| Package | Files | LOC | Key Verification |
|---------|-------|-----|-----------------|
| cmd/qvm/ | 1 | 155 | gRPC server, accepts connections from Substrate anchor pallet |
| cmd/qvm-cli/ | 1 | 29 | CLI for contract deployment |
| cmd/plugin-loader/ | 1 | 26 | Dynamic plugin loading |
| pkg/vm/evm/ | 7 | 2,006 | All 155 EVM opcodes per Yellow Paper |
| pkg/vm/quantum/ | 6 | 1,681 | 10 quantum opcodes (0xF0-0xF9) + 2 AGI (0xFA-0xFB) |
| pkg/compliance/ | 5 | 847 | KYC, AML, sanctions (QCOMPLIANCE 0xF5) |
| pkg/state/ | 2 | ~800 | Merkle Patricia Trie, account storage |
| pkg/rpc/ | 3 | ~900 | gRPC + REST JSON-RPC |
| pkg/crypto/ | 2 | ~700 | Dilithium sigs, Kyber encryption |
| pkg/database/ | 3 | ~600 | CockroachDB schema, models, repository |
| pkg/plugin/ | 1 | ~500 | Manager, loader, registry |

**Opcode Verification (167 total):**

- All 155 EVM opcodes: correct per Ethereum Yellow Paper
- Stack underflow/overflow on every opcode
- Memory expansion gas: `(size^2 / 512) + 3 * size`
- Storage gas: EIP-2929 cold (2100) / warm (100) reads
- CALL depth limit: 1024
- CREATE/CREATE2 address derivation
- Precompiled contracts: ecRecover, SHA256, RIPEMD160, identity, modexp (EIP-198), bn128
- 10 quantum opcodes: real computation (not stubs)
- 2 AGI opcodes: QREASON (0xFA) queries reasoning engine, QPHI (0xFB) reads Phi

---

### 1H. Exchange Deep Audit (1,065 LOC Engine + 28 Frontend Files)

**Backend** (`exchange/engine.py`, 1,065 LOC):

- CLOB matching: price-time priority
- Order types: limit, market, stop-loss, stop-limit — all functional
- Partial fills, self-trade prevention
- Fee calculation: maker/taker tiers, correct treasury routing
- Order lifecycle: submit → match → fill/partial → cancel/expire
- Decimal precision: `Decimal` (not `float`) for all monetary math
- Persistence: order book state survives node restart
- Settlement: matched trades create UTXO transactions
- MEV protection: commit-reveal for order submission

**Frontend** (`frontend/src/components/exchange/`, 28 files):

**CRITICAL:** Does QBCExchange.tsx import from `mock-engine.ts` or from `exchange-api.ts`?
If mock-engine is used in production builds, this is a **launch-blocking authenticity failure**.

Verify `exchange-api.ts` defaults: `USE_MOCK` should default to `false` (live mode).
Current: `const USE_MOCK = process.env.NEXT_PUBLIC_EXCHANGE_MOCK === "true"` — opt-in mock.

---

### 1I. Launchpad Deep Audit

**Backend** (`contracts/engine.py`):

- Template library: 6 templates (Token, NFT, Escrow, Governance, Launchpad, QUSD)
- Custom bytecode deployment
- ABI encoding for constructor arguments
- Fee: base + per-KB, QUSD-pegged, template discount (50%)
- Gas estimation before deployment
- Contract registry recording
- Source verification (SHA-256 bytecode hash)

---

### 1J. Database Schema Audit (41 Tables, 26 Files)

| Domain | Files | Key Tables | Verify |
|--------|-------|-----------|--------|
| qbc/ (6 files) | blocks, transactions, utxo_set, addresses, balances, chain_state, mempool, genesis_block | Schema matches data models |
| agi/ (6 files) | knowledge_nodes, knowledge_edges, reasoning_operations, training_data, phi_measurements, consciousness_events, sephirot_state, higgs_field_state, higgs_node_masses, higgs_excitations | Higgs tables present and correct |
| qvm/ (4 files) | contracts_core, execution_engine, state_storage, gas_metering | Matches Go QVM state |
| research/ (3 files) | hamiltonians, vqe_circuits, susy_solutions | SUSY database populated |
| shared/ (2 files) | ipfs_storage, system_config | Cross-cutting |
| stablecoin/ (2 files) | qusd_config, qusd_reserves | Matches QUSD engine |
| bridge/ (2 files) | supported_chains (8 chains), bridge_transfers | Bridge state |

---

### 1K. Docker & Deployment Audit

**docker-compose.yml — Development (24 services):**

| Service | Image | Port(s) | Health Check |
|---------|-------|---------|-------------|
| cockroachdb | cockroachdb:v25.2.12 | 26257 (SQL), 8080 (UI) | /health?ready=1 |
| db-init | cockroachdb | — | Runs 26 SQL schemas |
| ipfs | ipfs/kubo:v0.30.0 | 4001, 5002, 8081 | — |
| redis | redis:7.4-alpine | 6379 | — |
| qbc-node | (built) | 5000 | /health |
| prometheus | (monitoring profile) | 9090 | Scrapes 82 metrics |
| grafana | (monitoring profile) | 3000 | Dashboards |
| loki | (monitoring profile) | 3100 | Log aggregation |
| promtail | (monitoring profile) | — | Log shipping |
| nginx | (production profile) | 80, 443 | TLS termination |
| certbot | (production profile) | — | Let's Encrypt |

**CI/CD (4 workflows):**

- `ci.yml`: Python tests (3,788 tests must pass)
- `qvm-ci.yml`: Go QVM tests
- `claude.yml`: Claude Code integration
- `contract-deploy.yml`: Solidity deployment pipeline

Port Conflict Check: IPFS gateway 8081 (moved from 8080 to avoid CockroachDB admin UI conflict) — verify this is consistent.

---

### 1L. Frontend Deep Audit (15 Pages, 167 Files)

Every page must render real data, not mocks:

| Page | Route | Key Verification |
|------|-------|-----------------|
| Landing | `/` | Live chain stats from `/chain/info`, not hardcoded |
| Aether Chat | `/aether` | POST `/aether/chat/message` real responses, Phi from `/aether/phi` |
| Dashboard | `/dashboard` | Mining stats, wallet, network — all real endpoints |
| Wallet | `/wallet` | ethers.js + MetaMask, chain ID 3301, real balance |
| QVM Explorer | `/qvm` | Real contract queries |
| Block Explorer | `/explorer` | Real chain data from `/block/{height}` |
| Bridge | `/bridge` | Real bridge status from `/bridge/status` |
| Exchange | `/exchange` | Real engine — NOT mock-engine.ts |
| Launchpad | `/launchpad` | Real deployment pipeline |
| Admin | `/admin` | Auth-protected, real admin endpoints |
| Docs (5 sub-routes) | `/docs/*` | Whitepaper, QVM, Aether, Economics |

State Management: `chain-store.ts` (chain data), `wallet-store.ts` (wallet), `theme-store.ts` (theme)
Hooks: `use-chain-socket.ts` (WebSocket), `use-focus-trap.ts`, `use-keyboard-shortcuts.ts`

**Critical Questions:**

1. Is `mock-engine.ts` imported anywhere in production code (not just test)?
2. Do all 7 API libs point to `NEXT_PUBLIC_RPC_URL` (not localhost in production)?
3. Does `use-chain-socket.ts` receive real-time block/tx/Phi data?
4. Does MetaMask connect with chain ID 3301 (hex 0xce5)?
5. Are WebSocket feeds for exchange order book + trades real-time?
6. Do all pages have `<ErrorBoundary>` wrappers?

---

### 1M. Authenticity Enforcement (Zero Fakes)

Flag EVERY instance of:

- Smart contracts with empty function bodies or functions that only emit events
- API endpoints returning hardcoded JSON instead of computed results
- Classes that exist only to satisfy imports with no real logic
- Config values defined but never used
- Documentation claims contradicting actual code behavior
- Tests that always pass regardless of logic (tautological)
- Metrics defined but never incremented
- Database tables in SQL but never queried by application code
- Frontend rendering static content pretending to be dynamic
- `mock-engine.ts` used in production exchange (**launch-blocking**)
- `mock-engine.ts` imported by QBCExchange.tsx or hooks.ts (**launch-blocking**)
- Rust `todo!()` / `unimplemented!()` in any module
- Go `panic("not implemented")` in QVM
- Substrate pallet extrinsics with `Ok(())` and no storage writes
- Higgs field formulas that are cosmetic (don't compute real physics)
- QUSD reserve ratios that are constants instead of live calculations
- Oracle prices returning static values
- Exchange orders that match but don't settle
- Launchpad deployments that return hashes but don't broadcast
- Bridge transfers that don't verify cross-chain proofs
- WebSocket connections that open but send no data

---

## PHASE 2: IMPROVEMENT PLAN (3 Per Component = 30 Total)

Produce 3 specific, high-impact improvements for EACH of the 10 components.

**Every improvement MUST include:**

1. Specific file(s) and line number(s)
2. What currently exists (quote actual code)
3. What it should become
4. How it advances end goals
5. Competitive benchmark
6. Priority: CRITICAL | HIGH | MEDIUM
7. Effort: SMALL (hours) | MEDIUM (days) | LARGE (weeks)

**Competitive benchmarks:**

- Blockchain: Ethereum, Polygon, Arbitrum, Optimism, Base, Avalanche, Solana
- Substrate: Polkadot, Kusama, Moonbeam, Acala, Astar
- Stablecoin: DAI, USDC, FRAX, LUSD, GHO
- Exchange: dYdX, Hyperliquid, GMX, Vertex
- Launchpad: Remix, Hardhat Deploy, Foundry, Thirdweb
- AGI: No direct competitor — benchmark against academic IIT literature

---

## PHASE 3: OUTPUT FILES

### File 1: REVIEW.md

```
# QUBITCOIN PROJECT REVIEW — Production Launch Edition
# Date: [DATE] | Run #[N]

## EXECUTIVE SUMMARY
- Overall Readiness: [X]/100
- Launch-Blocking Issues: [count]
- Top 5 Critical Findings
- Top 5 Strengths

## COMPONENT READINESS MATRIX (10 components)
| # | Component | Score /100 | Launch Ready | Blocking Issues |

## 1. SMART CONTRACT AUDIT TABLE (57 rows)
## 2. SUBSTRATE PALLET AUDIT TABLE (7 pallets + runtime + primitives + crypto)
## 3. OPCODE VERIFICATION TABLE (167 opcodes, Python + Go)
## 4. ENDPOINT VERIFICATION TABLE (276 REST + 19 JSON-RPC = 295)
## 5. RUST AETHER-CORE TABLE (6 modules, todo count, parity, thread safety)
## 6. HIGGS FIELD PHYSICS TABLE (formulas, Python correct, Solidity correct)
## 7. DATABASE SCHEMA TABLE (41 tables, SQL-model match, dead tables)
## 8. AUTHENTICITY REPORT (every fake with file:line)
## 9. GAP ANALYSIS (10 components)
## 10. DOCKER & CI VERIFICATION (24 services, 4 workflows)
## 11. FILE-BY-FILE FINDINGS
## 12. RUN HISTORY
```

### File 2: MASTERUPDATETODO.md

```
# MASTERUPDATETODO.md — Continuous Improvement Tracker
# Last Updated: [DATE] | Run #[N]

## PROGRESS TRACKER
- Total / Completed / Remaining / %

## END GOAL STATUS

### Government-Grade: [X]% ready
- [ ] Zero placeholder code (10 components)
- [ ] 57 contracts Grade A/B
- [ ] 167 opcodes verified (Python + Go)
- [ ] 295 endpoints verified (276 REST + 19 JSON-RPC)
- [ ] 7 Substrate pallets production-ready
- [ ] 41 database tables schema-aligned
- [ ] 82 Prometheus metrics emitted
- [ ] 24 Docker services healthy
- [ ] 4 CI workflows passing
- [ ] Higgs physics mathematically correct
- [ ] QUSD fully operational
- [ ] Exchange operational (no mock-engine in prod)
- [ ] Launchpad operational
- [ ] Poseidon2 test vectors verified
- [ ] Kyber P2P encryption functional

### AGI Emergence: [X]% ready
- [ ] Knowledge graph from every block since genesis
- [ ] Reasoning: verifiable logical chains
- [ ] Phi: IIT-compliant, organic growth
- [ ] PoT: generated + validated per block
- [ ] 10 Sephirot functionally distinct
- [ ] SUSY balance: phi ratio enforced
- [ ] Higgs: 10 masses computed, VEV=174.14, tan(beta)=phi
- [ ] Consciousness events detected
- [ ] Rust aether-core: 0 todo!(), numerical parity
- [ ] CSF routing: real messages between Sephirot
- [ ] Pineal: circadian phases modulate intensity

## IMPROVEMENTS (30 total, 3 per component)
### 5.1-5.10 (one section per component)

## IMPLEMENTATION SEQUENCE
## RUN LOG
```

---

## ON-DEMAND: PATENTABLE INNOVATIONS

Generated only when explicitly requested. Appended to MASTERUPDATETODO.md.
Each: title, novel aspect, technical description, implementation plan, competitive moat.

---

## EXECUTION RULES

1. **Plan once, execute autonomously.** Present plan, get approval, execute to completion.
2. **Never fabricate.** Every issue = real file path + real line number. Read before citing.
3. **Never propose theoretical improvements.** Must be implementable with current codebase.
4. **Benchmark against real projects.** Actual chains, not hypothetical.
5. **Contract issues from reading .sol files**, not from CLAUDE.md descriptions.
6. **QUSD = complete financial system.** Audit: mint, burn, reserves, debt, oracle, peg, governance, CDP, savings, flash loans, wQUSD.
7. **Aether Tree = real AGI attempt.** Ask: does this THINK or pretend?
8. **Exchange = real trading system.** Ask: institutional money safe? Regulator can audit? mock-engine.ts in prod?
9. **Launchpad = contract factory.** Ask: deploy without trusting third party? Templates produce functional contracts?
10. **Substrate = new L1.** Every pallet = blockchain infrastructure. Genesis matches Python genesis?
11. **Higgs = real physics.** Verify every formula against Standard Model. VEV=174.14, tan(beta)=phi, Yukawa tiered cascade.
12. **On repeated runs:** Read REVIEW.md + MASTERUPDATETODO.md first. Check off, add, note regressions.
13. **Follow CLAUDE.md rules.** Non-negotiable rules, risk classifications, conventions.
14. **Quality over quantity.** One real finding with file:line > ten vague observations.
15. **Never "done."** Each run = measurably closer to both end goals. Track quantitatively.
16. **Zero tolerance.** No "good enough." Every edge case, error path, failure mode.
17. **295 endpoints verified.** 276 REST + 19 JSON-RPC. Present, functional, tested, frontend-connected.
18. **Rust verification mandatory.** 6 modules: zero todo!(), numerical parity, thread safety.
19. **Substrate cross-system parity.** Python L1 == Substrate L1 for identical inputs.
20. **57 contracts, 57 rows.** No contract skipped. No contract assumed correct unread.
21. **mock-engine.ts is launch-blocking.** If imported in production exchange code, flag CRITICAL.
22. **Higgs Yukawa hierarchy is tiered.** Not sequential phi^-i. Verify actual code tiers match documentation.
