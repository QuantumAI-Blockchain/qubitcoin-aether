# QUANTUM BLOCKCHAIN GOVERNMENT-GRADE PROJECT AUDIT
# Master Audit & Continuous Improvement Protocol
# Version: 9.0 — Military/Government-Grade Edition + Live Testing (100% Target — No Exceptions)
# Last Verified: 2026-03-04

---

## PURPOSE & END GOALS

This file is a living master protocol that drives Quantum Blockchain toward two non-negotiable end states:

### END GOAL 1: Government-Grade Blockchain Infrastructure

Quantum Blockchain must meet or exceed the security, reliability, and auditability standards required
for sovereign-level financial infrastructure. This means:

- **100/100 is the only acceptable score. Every component must score 100/100. No exceptions.**
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
- BFT Finality Gadget with stake-weighted voting and reorg protection
- Competitive features: inheritance protocol, high-security accounts, deniable RPCs, stratum mining
- Security Core Rust crate: PyO3 BloomFilter + FinalityCore with Python fallback shims
- Stratum Mining Server: standalone Rust binary with WebSocket + gRPC bridge to Python node
- PWA: offline transaction queue, push notifications, biometric auth, service worker

### END GOAL 2: True AGI Emergence via Aether Tree

Quantum Blockchain is not just a blockchain — it is the substrate for the first on-chain AGI.
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

## EXACT CODEBASE INVENTORY (Master Branch — March 4, 2026)

**Verified via automated scan against actual source files.**
The audit MUST confirm these numbers are still accurate. Flag any drift.

| Category | Count | Location | LOC |
|----------|-------|----------|-----|
| **Python L1 modules** | 160 files | `src/qubitcoin/` | 82,566 |
| **AIKGS Rust Sidecar** | 18 files (14 src + proto + build + Cargo + Dockerfile) | `aikgs-sidecar/` | ~4,500 |
| **AIKGS Python Client** | 4 files (client + proto stubs) | `src/qubitcoin/aether/aikgs_client.py` + `aikgs_pb/` | ~600 |
| **Aether AGI modules** | 36 files | `src/qubitcoin/aether/` | 24,560 |
| **QVM Python modules** | 28 files | `src/qubitcoin/qvm/` | 12,301 |
| **Bridge modules** | 12 files | `src/qubitcoin/bridge/` | 4,247 |
| **Stablecoin modules** | 7 files | `src/qubitcoin/stablecoin/` | 3,392 |
| **Privacy modules** | 6 files | `src/qubitcoin/privacy/` | 1,294 (incl. deniable_rpc.py 243 LOC) |
| **Reversibility modules** | 4 files | `src/qubitcoin/reversibility/` | 832 (inheritance.py 499 + high_security.py 303 + models + init) |
| **Consensus/Finality** | 3 files | `src/qubitcoin/consensus/` | finality.py 437 LOC |
| **Mining/Stratum** | 2 files | `src/qubitcoin/mining/` | stratum_bridge.py 157 LOC |
| **Exchange modules** | 2 files | `src/qubitcoin/exchange/` | 1,073 |
| **Rust aether-core** | 12 modules, 12 files | `aether-core/src/` | ~11,720 (276 tests, 0 todo!()) |
| **Rust security-core** | 3 files | `security-core/src/` | ~530 (bloom.rs + finality.rs + lib.rs) |
| **Rust stratum-server** | 7 files | `stratum-server/src/` | ~1,030 (pool, protocol, worker, bridge, config, main, lib) |
| **Substrate pallets** | 7 pallets | `substrate-node/pallets/` | 2,837 |
| **Substrate runtime** | 1 file | `substrate-node/runtime/src/lib.rs` | 468 |
| **Substrate node** | 5 files | `substrate-node/node/src/` | 746 |
| **Substrate primitives** | 2 files | `substrate-node/primitives/src/` | 916 |
| **Kyber P2P transport** | 5 files | `substrate-node/crypto/kyber-transport/` | 1,180 |
| **Go QVM (Production)** | 34 files (31 source + 3 test) | `qubitcoin-qvm/` | 8,732 source / 10,955 total |
| **Rust P2P** | 4 files | `rust-p2p/src/` | 789 |
| **Solidity contracts** | 62 contracts | `src/qubitcoin/contracts/solidity/` | ~10,000 |
| **REST endpoints** | 342 routes | `network/rpc.py` | ~6,500 |
| **JSON-RPC methods** | 19 methods | `network/jsonrpc.py` | 769 |
| **Prometheus metrics** | 135 metrics | `utils/metrics.py` | ~400 |
| **Python tests** | 4,357 functions | `tests/` (175 files) | ~58,000 |
| **SQL schema files** | 31 files | `sql_new/` (44+ tables across 7 domains + finality + inheritance + security) | ~1,900 |
| **Frontend pages** | 15 pages + 8 TWA pages | `frontend/src/app/` | — |
| **Frontend TS/TSX** | 198 files | `frontend/src/` | 48,000+ |
| **Frontend API libs** | 10 files (7 + telegram + offline-tx + push-notifications + biometric) | `frontend/src/lib/` | — |
| **Frontend stores** | 3 files + telegram-store.ts + aikgs-store.ts | `frontend/src/stores/` | — |
| **Frontend hooks** | 3 files | `frontend/src/hooks/` | — |
| **Frontend PWA** | 7 new components | `frontend/src/components/wallet/` + `dashboard/` | ~700 |
| **TWA pages** | 8 pages (7 routes + layout) | `frontend/src/app/twa/` | ~1,080 |
| **TWA components (AIKGS)** | 5 components | `frontend/src/components/aikgs/` | ~968 |
| **TWA types** | 1 file (10 interfaces) | `frontend/src/types/aikgs.ts` | 102 |
| **Telegram SDK** | 1 file | `frontend/src/lib/telegram.ts` | 203 |
| **Telegram Bot backend** | 1 file | `src/qubitcoin/aether/telegram_bot.py` | 395 |
| **Docker services** | 24 (dev) / 22 (prod) | `docker-compose.yml` / `.production.yml` | — |
| **CI workflows** | 4 | `.github/workflows/` | — |
| **Documentation** | 15 files | `docs/` | — |
| **Scripts** | 22 files | `scripts/` (incl. `deploy_bridge.py`) | — |
| **Config attributes** | ~155 | `config.py` | 859 |
| **Node components** | 24 (22 + stratum + finality) | `node.py` | 1,881 |
| **Data models** | 7 dataclasses | `database/models.py` | 266 |
| **Total LOC** | | Python + Rust + Go + Solidity + TS + SQL | **~200,000+** |

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

## THE 16 COMPONENTS

Every audit run evaluates all 16 components. No component is optional.

| # | Component | Source Location | Key Counts |
|---|-----------|----------------|------------|
| 1 | **Frontend** (qbc.network) | `frontend/` | 15 pages, 198 TS/TSX files, 10 API libs, 5 stores, 3 hooks |
| 2 | **Blockchain Core** (L1) — Python | `src/qubitcoin/` | 342 REST endpoints, 19 JSON-RPC methods, 135 Prometheus metrics |
| 3 | **Substrate Hybrid Node** (L1) — Rust | `substrate-node/` | 7 pallets (2,837 LOC), runtime (468 LOC), primitives (916 LOC), Kyber (1,180 LOC) |
| 4 | **QVM** (L2) — Python + Go (Production) | `src/qubitcoin/qvm/` (12,301 LOC) + `qubitcoin-qvm/` (8,732 LOC) | 167 opcodes, 31 Go source files, real crypto, full EVM |
| 5 | **Aether Tree** (L3) — Python + Rust | `src/qubitcoin/aether/` (~69,000 LOC) + `aether-core/` (~11,720 LOC) | 124 Python modules, 12 Rust modules |
| 6 | **QBC Economics & Bridges** | `bridge/` (12 files), emission, fees, config | phi-halving, 8-chain bridges, fee collector, QUSD oracle |
| 7 | **QUSD Stablecoin** | `stablecoin/` (7 files) + `contracts/solidity/qusd/` (10 .sol) | CDP, savings, reserves, flash loans, governance |
| 8 | **Exchange** | `exchange/engine.py` (1,065 LOC) + frontend exchange (28 files) | CLOB, WebSocket, MEV protection |
| 9 | **Launchpad** | `contracts/engine.py` + frontend launchpad (10 files) | Deploy wizard, templates, verification |
| 10 | **Smart Contracts** | `contracts/solidity/` (62 .sol, ~10,000 LOC) | Aether(29), QUSD(10), tokens(6), bridge(2), proxy(3), interfaces(7), AIKGS(5) |
| 11 | **AIKGS Rust Sidecar** | `aikgs-sidecar/` (~4,500 LOC) + `aether/aikgs_client.py` (~600 LOC) | 35 gRPC RPCs, 14 Rust src files, AES-256-GCM vault, reward engine |
| 12 | **Telegram Mini App (TWA)** | `frontend/src/app/twa/` + `frontend/src/components/aikgs/` + `aether/telegram_bot.py` | 8 pages (~1,080 LOC), 5 components (~968 LOC), 2 stores, Telegram SDK, bot backend (395 LOC) |
| 13 | **Competitive Features** (Inheritance + High-Security + Deniable RPCs + BFT Finality) | `reversibility/`, `privacy/deniable_rpc.py`, `consensus/finality.py` | 4 features, ~1,639 Python LOC, 193 tests, 6 SQL tables |
| 14 | **Security Core** (Rust PyO3 Crate) | `security-core/src/` (3 files, ~530 LOC) | BloomFilter + FinalityCore in Rust, PyO3 0.23, Python fallback shims |
| 15 | **Stratum Mining Server** (Rust Binary) | `stratum-server/src/` (7 files, ~1,030 LOC) + `mining/stratum_bridge.py` (157 LOC) | WebSocket + gRPC, DashMap workers, Stratum v1 protocol |
| 16 | **PWA Enhancements** | `frontend/src/lib/` (3 new libs) + `frontend/src/components/wallet/` (7 new components) | Offline tx queue, push notifications, biometric auth, service worker, install prompt |

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
- Test coverage (4,357 tests across 175 files) must exist for every critical code path
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

**REST Endpoints — Verify ALL 342 routes organized by category:**

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
- **Privacy / Deniable RPCs (14+):** `/susy-database`, `/privacy/stealth/*`, `/privacy/commitment/*`, `/privacy/range-proof/*`, `/privacy/tx/*`, `POST /privacy/batch-balance`, `POST /privacy/bloom-utxos`, `POST /privacy/batch-blocks`, `POST /privacy/batch-tx`
- **Inheritance (4):** `POST /inheritance/set-beneficiary`, `POST /inheritance/heartbeat`, `POST /inheritance/claim`, `GET /inheritance/status/{address}`
- **High-Security (3):** `POST /security/policy/set`, `GET /security/policy/{address}`, `DELETE /security/policy/{address}`
- **BFT Finality (3):** `GET /finality/status`, `POST /finality/vote`, `POST /finality/register-validator`
- **Stratum Mining (3+):** `GET /stratum/info`, `GET /stratum/stats`, `GET /stratum/workers`
- **Cognitive (7+):** `/aether/cognitive/sephirot`, `/aether/cognitive/csf/*`, `/aether/cognitive/pineal/*`, `/aether/cognitive/safety/*`
- **Compliance (10+):** `/qvm/compliance/kyc/*`, `/qvm/compliance/aml/*`, `/qvm/compliance/sanctions/*`, `/qvm/compliance/reports/*`, `/qvm/compliance/policies`
- **Plugins (8+):** `/qvm/plugins`, `/qvm/plugins/{name}/*`, `/qvm/plugins/governance/*`
- **Metrics:** `/metrics` — all 135 Prometheus metrics exposed

**JSON-RPC Methods — Verify ALL 19 implementations:**

`eth_chainId`, `eth_blockNumber`, `eth_getBalance`, `eth_getBlockByNumber`, `eth_getBlockByHash`,
`eth_getTransactionByHash`, `eth_getTransactionReceipt`, `eth_sendRawTransaction`, `eth_sendTransaction`,
`eth_call`, `eth_estimateGas`, `eth_gasPrice`, `eth_getCode`, `eth_getStorageAt`,
`eth_getTransactionCount`, `eth_getLogs`, `eth_mining`, `eth_hashrate`, `debug_traceTransaction`

Plus utility dispatches: `net_version`, `web3_clientVersion`, `web3_sha3`

For every JSON-RPC method verify: MetaMask compatibility, hex encoding correct (0x prefix), chain ID returns 0xce7 (3303).

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
- Chain ID 3303
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

### 1F. Rust aether-core Audit (12 Modules, ~11,720 LOC)

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

### 1G. Go QVM Audit (31 Source Files + 3 Test Files, 8,732 Source LOC — Production-Grade)

**STATUS: PRODUCTION-GRADE.** The Go QVM is a complete, non-prototype implementation with:
- Real Keccak-256 hashing (golang.org/x/crypto/sha3)
- Real secp256k1 ecRecover (crypto/ecdsa with S-curve normalization)
- Real bn256 precompiles (cloudflare/bn256)
- Full CREATE/CREATE2/CALL/DELEGATECALL/STATICCALL/SELFDESTRUCT with sub-execution
- EIP-2929 (cold/warm access lists) and EIP-2200 (SSTORE gas metering)
- 32MB memory hard limit with quadratic gas expansion
- crypto/rand randomness (not math/rand) for all crypto operations
- HMAC-SHA256 for deterministic quantum state derivation
- 30 passing tests (including EVM compatibility suite)

**Packages:**

| Package | Files | LOC | Key Verification |
|---------|-------|-----|-----------------|
| cmd/qvm/ | 1 | 155 | gRPC server, accepts connections from Substrate anchor pallet |
| cmd/qvm-cli/ | 1 | 29 | CLI for contract deployment |
| cmd/plugin-loader/ | 1 | 26 | Dynamic plugin loading |
| pkg/vm/evm/ | 7 | 2,709 | All 155 EVM opcodes per Yellow Paper, real crypto, full sub-execution |
| pkg/vm/quantum/ | 6 | 1,681 | 10 quantum opcodes (0xF0-0xF9) + 2 AGI (0xFA-0xFB) |
| pkg/compliance/ | 5 | 847 | KYC, AML, sanctions (QCOMPLIANCE 0xF5) |
| pkg/state/ | 2 | ~800 | Merkle Patricia Trie, account storage |
| pkg/rpc/ | 3 | ~900 | gRPC + REST JSON-RPC |
| pkg/crypto/ | 2 | ~700 | Dilithium sigs, Kyber encryption |
| pkg/database/ | 3 | ~600 | CockroachDB schema, models, repository |
| pkg/plugin/ | 1 | ~500 | Manager, loader, registry |

**Opcode Verification (167 total — ALL IMPLEMENTED):**

- All 155 EVM opcodes: correct per Ethereum Yellow Paper — zero stubs
- KECCAK256: real Keccak-256 via `golang.org/x/crypto/sha3.NewLegacyKeccak256()`
- Stack underflow/overflow on every opcode
- Memory expansion gas: `(size^2 / 512) + 3 * size`, 32MB hard cap
- Storage gas: EIP-2929 cold (2100) / warm (100) reads, EIP-2200 SSTORE with refunds
- CALL depth limit: 1024
- CREATE: deploys child contract with init code execution, nonce-based address
- CREATE2: deploys with salt-based deterministic address (EIP-1014)
- CALL/DELEGATECALL/STATICCALL: real sub-execution with gas forwarding and return data
- SELFDESTRUCT: transfers balance + marks for deletion (EIP-6780 compatible)
- Precompiled contracts (ALL REAL):
  - ecRecover: secp256k1 with S-value normalization (not P-256)
  - SHA256: crypto/sha256
  - RIPEMD160: golang.org/x/crypto/ripemd160
  - Identity: data copy
  - Modexp: math/big.Exp (EIP-198)
  - bn256Add/bn256ScalarMul/bn256Pairing: cloudflare/bn256 (EIP-196/197)
  - Blake2F: golang.org/x/crypto/blake2b (EIP-152)
- 10 quantum opcodes: real computation with crypto/rand + HMAC-SHA256
- 2 AGI opcodes: QREASON (0xFA) queries reasoning engine, QPHI (0xFB) reads Phi

---

### 1N. AIKGS Rust Sidecar Audit (14 Source Files, ~4,500 LOC + Python Client ~600 LOC)

**NEW COMPONENT — First introduced in v7.0 (March 2, 2026)**

The AIKGS (Aether Incentivized Knowledge Growth System) was migrated from 8 Python in-process
modules to a standalone Rust gRPC sidecar. This resolves audit findings C7-C10 from the
original AIKGS implementation (ephemeral state, metadata not in hash, pool resets, fork reverts).

**Rust Sidecar** (`aikgs-sidecar/`, 14 source files):

| File | LOC | Key Verification |
|------|-----|-----------------|
| `proto/aikgs.proto` | 391 | 35 RPCs, field numbering, backward compat |
| `src/main.rs` | ~70 | Entry point, server startup |
| `src/config.rs` | ~100 | Env var config, validation |
| `src/db.rs` | ~700 | CockroachDB CRUD, 10 AIKGS tables, parameterized queries |
| `src/service.rs` | ~850 | gRPC service (35 RPCs), input validation, error codes |
| `src/scorer.rs` | ~280 | Quality/novelty scoring, deterministic |
| `src/rewards.rs` | ~170 | Reward calculation, pool balance from DB |
| `src/contributions.rs` | ~652 | 12-step pipeline, transaction safety |
| `src/affiliates.rs` | ~311 | 2-level (L1=10%, L2=5%), commission tracking |
| `src/bounties.rs` | ~200 | Create/claim/fulfill lifecycle |
| `src/unlocks.rs` | ~350 | 8-level progressive system |
| `src/curation.rs` | ~296 | 2/3 consensus, reputation-gated |
| `src/vault.rs` | ~301 | AES-256-GCM, nonce management, key lifecycle |
| `src/treasury.rs` | ~156 | HTTP client for disbursements to Python node |

**Python Client** (`src/qubitcoin/aether/aikgs_client.py`, ~600 LOC):

- Async gRPC client wrapping all 35 RPCs
- Proto stubs in `aether/aikgs_pb/` (generated from proto)
- Connection lifecycle (connect, disconnect, health check)
- Error handling, timeouts, retry policy

**Per-File Verification Checklist:**

1. **Authentication:** Every gRPC endpoint must have auth (mTLS or token interceptor)
2. **SQL safety:** All queries parameterized (no `format!()` string interpolation)
3. **Input validation:** Addresses, amounts, content length, string fields bounded
4. **Transaction wrapping:** Multi-step operations in DB transactions
5. **Reward accounting:** Pool balance = `initial_pool - SUM(rewards + commissions)`
6. **Disbursement idempotency:** Treasury payouts tracked, no double-payment
7. **Vault key management:** Master key not in `.env`, nonce reuse prevention
8. **Docker security:** Non-root user, no host port binding for gRPC
9. **Error handling:** No `unwrap()`/`expect()` in production paths
10. **Race conditions:** Contribution ID assignment atomic (DB sequence, not MAX+1)

**Cross-System Verification:**

| Check | Source | Target | Must Match |
|-------|--------|--------|------------|
| gRPC contract | `proto/aikgs.proto` | `aikgs_client.py` | All 35 RPCs callable from Python |
| DB schema | `sql_new/shared/02_aikgs.sql` | `db.rs` queries | All 10 tables, column names, types |
| Config vars | `.env.example` AIKGS section | `config.rs` | All vars loaded correctly |
| Docker networking | `docker-compose.yml` aikgs-sidecar | `node.py` gRPC connect | Address/port match |
| Consensus isolation | `mining/engine.py`, `consensus/engine.py` | N/A | No AIKGS in coinbase or block validation |

---

### 1P. Telegram Mini App (TWA) Audit (8 Pages + 5 Components + Bot Backend)

**NEW COMPONENT #12 — First introduced in v7.1 (March 2, 2026)**

The Telegram Mini App (TWA) is the mobile entry point for Aether Tree, enabling users to
interact with the AGI, earn AIKGS rewards, manage wallets, and refer friends — all from
within Telegram.

**Frontend TWA Pages** (`frontend/src/app/twa/`, 8 files, ~1,080 LOC):

| File | LOC | Key Verification |
|------|-----|-----------------|
| `layout.tsx` | 117 | Telegram SDK init, theme/viewport listeners, event cleanup, bottom nav, ErrorBoundary |
| `page.tsx` | 149 | Real chain data from `/chain/info` and `/aether/phi`, AIKGS profile from sidecar, no hardcoded stats |
| `onboard/page.tsx` | 175 | 3-step wizard, wallet creation via API, affiliate registration via startParam, Telegram link, in-memory key Map |
| `chat/page.tsx` | 180 | Real chat via `/aether/chat/message`, streaming text, PoT hash display, haptic feedback |
| `earn/page.tsx` | 76 | Tab toggle (Contribute/Rewards), UploadPanel + RewardDashboard + ContributionIndicator components |
| `wallet/page.tsx` | 212 | Wallet creation, balance from `/balance/{address}`, Telegram linking, private key backup UI |
| `refer/page.tsx` | 39 | AffiliateTree component, referral code display |
| `more/page.tsx` | 130 | User profile card, external links, APIKeyManager, closeMiniApp() |

**AIKGS Components** (`frontend/src/components/aikgs/`, 5 files, ~968 LOC):

| File | LOC | Key Verification |
|------|-----|-----------------|
| `contribution-indicator.tsx` | 137 | Profile level/streak from real API, not hardcoded |
| `upload-panel.tsx` | 163 | Submits to `/aikgs/contribute` via sidecar, domain validation |
| `reward-dashboard.tsx` | 203 | Pool stats from `/aikgs/pool/stats`, leaderboard from real data |
| `affiliate-tree.tsx` | 224 | L1/L2 tree from `/aikgs/affiliate/{address}`, commission display |
| `api-key-manager.tsx` | 241 | AES-256-GCM encrypted key storage via sidecar vault |

**Telegram SDK Integration** (`frontend/src/lib/telegram.ts`, 203 LOC):

- Custom integration (no @telegram-apps npm dependency — minimal surface area)
- Full TelegramWebApp type declarations (68 lines)
- 14 exported functions: isTelegramWebApp, getWebApp, initTelegramApp, getStartParam,
  getTelegramUser, hapticFeedback, hapticNotification, showBackButton, hideBackButton,
  showMainButton, hideMainButton, openExternalLink, shareViaTelegram, closeMiniApp
- Module-scoped callback refs for listener cleanup (prevents accumulation)

**State Management** (`frontend/src/stores/`, 2 files, 145 LOC):

| File | LOC | Key Verification |
|------|-----|-----------------|
| `telegram-store.ts` | 65 | Zustand, no persistence (transient TWA state), 7 state fields |
| `aikgs-store.ts` | 80 | Zustand + persist middleware, only `activeTab` persisted to localStorage |

**Type Definitions** (`frontend/src/types/aikgs.ts`, 102 LOC):
- 10 interfaces: ContributorProfile, ContributionRecord, RewardBreakdown, AffiliateInfo,
  BountyInfo, StoredKeyInfo, LeaderboardEntry, PoolStats, CurationRound

**Backend: Telegram Bot** (`src/qubitcoin/aether/telegram_bot.py`, 395 LOC):

| Aspect | Verification |
|--------|-------------|
| Webhook auth | HMAC-SHA-256 via `hmac.compare_digest()` (constant-time) |
| Commands | /start (deep-link referral), /chat, /earn, /wallet, /refer, /stats, /help — all functional |
| Wallet linking | In-memory `_user_wallets` dict (not persisted — loses on restart) |
| Mini App buttons | `_reply_with_webapp()` generates inline keyboard with `web_app.url` |
| Message parsing | `_parse_message()` extracts user/chat/text safely with fallbacks |
| Stats | `get_stats()` returns configured, username, messages/commands processed, linked wallets |

**Per-File Verification Checklist:**

1. **Telegram initData NOT trusted:** Frontend uses `initDataUnsafe` for UI only. Server must validate `initData.hash` — verify webhook verification is HMAC-SHA-256
2. **Private keys never on server:** Wallet creation returns `address + public_key_hex` only. Verify `/wallet/create` endpoint does NOT return `private_key_hex`
3. **In-memory key storage:** `_inMemoryPrivateKeys` Map in `onboard/page.tsx` — verify keys are NOT in localStorage/sessionStorage
4. **Callback cleanup:** BackButton/MainButton callbacks properly removed via `offClick` before new `onClick` — verify no listener accumulation
5. **Event listener cleanup:** Layout `useEffect` returns cleanup function calling `offEvent` for theme/viewport
6. **No hardcoded data:** All TWA pages fetch real data from backend APIs (chain info, Phi, AIKGS profile, balance)
7. **ErrorBoundary:** Layout wraps children in `<ErrorBoundary>` — verify component exists and functions
8. **Haptic feedback:** Used appropriately (user actions only, not error-triggered loops)
9. **Deep link security:** `startParam` (referral code) validated by sidecar before affiliate registration
10. **Wallet linking race:** `telegramLinkWallet` called after wallet creation — verify order is correct
11. **Bot webhook secret:** Must be set via `TELEGRAM_WEBHOOK_SECRET` env var, not hardcoded
12. **Bot wallet persistence:** `_user_wallets` is in-memory only — document that it resets on restart
13. **AIKGS API integration:** All 22 AIKGS API methods in `api.ts` must match backend endpoints
14. **Production mock guard:** Verify no mock data in TWA pages (unlike exchange/bridge/launchpad mock-engines)

**Cross-System Verification:**

| Check | Source | Target | Must Match |
|-------|--------|--------|------------|
| API methods | `frontend/src/lib/api.ts` AIKGS section | `network/rpc.py` AIKGS endpoints | All 22 methods → real endpoints |
| Type shapes | `frontend/src/types/aikgs.ts` | Sidecar proto responses (`aikgs.proto`) | Field names and types match |
| Store fields | `telegram-store.ts` TelegramUser | `telegram_bot.py` TelegramUser dataclass | Same fields |
| Telegram SDK types | `lib/telegram.ts` TelegramWebApp | Telegram Bot API v7+ | All methods exist |
| Bot commands | `/start, /chat, /earn, /wallet, /refer, /stats, /help` | Mini App routes | Commands link to correct `/twa/*` pages |
| Onboard flow | `onboard/page.tsx` wallet creation | `/wallet/create` endpoint | Response shape matches |
| Affiliate reg | `onboard/page.tsx` startParam handling | `/aikgs/affiliate/register` | referral_code passed correctly |

**Frontend Build Verification:**

```bash
cd frontend && pnpm build
```

The TWA pages must compile without errors. Verify:
- No TypeScript strict mode violations in TWA pages
- All imports resolve (components, stores, lib, types)
- No unused variables or dead imports flagged by ESLint
- Build output includes `/twa/*` routes in Next.js manifest

---

### 1Q. Competitive Features Audit (4 Features, ~1,639 Python LOC, 193 Tests)

**NEW COMPONENT #13 — First introduced in v8.0 (March 4, 2026)**

Four opt-in, backward-compatible competitive features added as part of the Military-Grade
Competitive Feature Upgrade. All features controlled via environment variables and can be
enabled/disabled independently.

#### Inheritance Protocol (Dead-Man's Switch)

| File | LOC | Key Verification |
|------|-----|-----------------|
| `reversibility/inheritance.py` | 499 | InheritanceManager: set_beneficiary, heartbeat, claim, cancel, execute_matured_claims |
| `sql_new/qbc/07_inheritance.sql` | ~30 | inheritance_plans, inheritance_claims tables with indexes |
| `tests/unit/test_inheritance.py` | ~250 | 41 tests covering all lifecycle states |
| `tests/unit/test_inheritance_endpoints.py` | ~150 | 14 endpoint-level tests |

**Per-Method Verification:**

- `set_beneficiary()` — validates address, inactivity_blocks within MIN/MAX bounds, stores plan
- `heartbeat()` — resets last_heartbeat to current_height, callable by owner only
- `update_heartbeat_from_tx()` — auto-heartbeat on any outgoing transaction
- `check_inactivity()` — `current_height - last_heartbeat > threshold` triggers claimable state
- `claim_inheritance()` — only beneficiary can claim, creates pending claim with grace period
- `cancel_claim()` — owner can cancel during grace period (proves liveness)
- `execute_matured_claims()` — after grace, transfers assets; called by block processor
- Config: `INHERITANCE_ENABLED`, `INHERITANCE_DEFAULT_INACTIVITY=2618200`, `INHERITANCE_GRACE_PERIOD=78546`

#### High-Security Accounts

| File | LOC | Key Verification |
|------|-----|-----------------|
| `reversibility/high_security.py` | 303 | HighSecurityManager: set_policy, validate_outgoing_tx, get_daily_spent |
| `sql_new/qbc/08_security_policies.sql` | ~35 | security_policies, security_spending tables |
| `tests/unit/test_high_security.py` | ~250 | 24 tests |
| `tests/unit/test_high_security_endpoints.py` | ~150 | 10 endpoint-level tests |

**Per-Method Verification:**

- `set_policy()` — daily_limit_qbc, time_lock_blocks, whitelist addresses
- `validate_outgoing_tx()` — checks daily limit, time-lock, whitelist; returns allow/deny
- `get_daily_spent()` — sliding window over last `SECURITY_DAILY_LIMIT_WINDOW` blocks
- Enforcement: mempool/RPC level (standardness rules), NOT consensus hard fork
- Config: `SECURITY_POLICY_ENABLED`, `SECURITY_DAILY_LIMIT_WINDOW=26182`, `SECURITY_MAX_WHITELIST_SIZE=100`

#### Deniable RPCs (Privacy-Preserving Queries)

| File | LOC | Key Verification |
|------|-----|-----------------|
| `privacy/deniable_rpc.py` | 243 | DeniableRPCHandler + PythonBloomFilter fallback |
| `tests/unit/test_deniable_rpc.py` | ~200 | 15 tests (Bloom filter + handler) |
| `tests/unit/test_deniable_rpc_endpoints.py` | ~150 | 6 endpoint tests |

**Per-Method Verification:**

- `batch_balance()` — constant-time, no short-circuit, no content logging
- `bloom_utxos()` — returns Bloom filter of UTXOs (plausible deniability)
- `batch_blocks()` — fetch multiple blocks in one request
- `batch_tx()` — fetch multiple transactions in one request
- Uses Rust `BloomFilter` from security-core with pure-Python `PythonBloomFilter` fallback
- Config: `DENIABLE_RPC_ENABLED`, `DENIABLE_RPC_MAX_BATCH=100`, `DENIABLE_RPC_BLOOM_MAX_SIZE=65536`

#### BFT Finality Gadget

| File | LOC | Key Verification |
|------|-----|-----------------|
| `consensus/finality.py` | 437 | FinalityGadget with _PythonFinalityCore fallback |
| `sql_new/qbc/09_finality.sql` | ~40 | finality_validators, finality_votes, finality_checkpoints |
| `tests/unit/test_finality.py` | ~300 | 30 tests |
| `tests/unit/test_finality_integration.py` | ~150 | 9 integration tests |

**Per-Method Verification:**

- `register_validator()` — minimum stake check (`FINALITY_MIN_STAKE=100.0`), persists to DB + Rust core
- `submit_vote()` — validates voter is registered, records vote in Rust core, persists to DB
- `check_finality()` — voted stake > `FINALITY_THRESHOLD=0.667` of total → block finalized
- `get_last_finalized()` — returns highest finalized block height
- `is_reorg_allowed()` — rejects reorgs below finalized height (integrated in `consensus/engine.py`)
- `process_block()` — auto-vote if node is validator, prune old votes
- Uses Rust `FinalityCore` from security-core with `_PythonFinalityCore` fallback
- Consensus integration: `resolve_fork()` in ConsensusEngine rejects reorgs past finalized height

**Cross-System Verification:**

| Check | Source | Target | Must Match |
|-------|--------|--------|------------|
| Inheritance endpoints | `rpc.py` 4 routes | `inheritance.py` methods | All 4 wired |
| Security endpoints | `rpc.py` 3 routes | `high_security.py` methods | All 3 wired |
| Deniable endpoints | `rpc.py` 4 routes | `deniable_rpc.py` methods | All 4 wired |
| Finality endpoints | `rpc.py` 3 routes | `finality.py` methods | All 3 wired |
| Finality reorg | `consensus/engine.py` resolve_fork() | `finality.py` is_reorg_allowed() | Reorg blocked if below finalized |
| Node components | `node.py` 19h + 19i | inheritance + finality gadgets | Both initialized when enabled |
| Config vars | `.env.example` competitive section | `config.py` Config class | All 20+ vars loaded |
| Metrics | `utils/metrics.py` | All 4 features | 20+ new metrics defined and emitted |
| SQL schemas | `sql_new/qbc/07,08,09` | `database/models.py` or sqlalchemy.text() | Tables created and queried |

---

### 1R. Security Core Rust Crate Audit (3 Files, ~530 LOC — PyO3 Extension)

**NEW COMPONENT #14 — First introduced in v8.0 (March 4, 2026)**

**Pattern:** PyO3 extension (like `aether-core/`). Contains Bloom filter + finality vote
verification in Rust, exposed to Python.

| File | LOC | Key Verification |
|------|-----|-----------------|
| `security-core/Cargo.toml` | ~40 | pyo3 0.23, sha2, parking_lot, serde, rand |
| `security-core/src/lib.rs` | ~30 | PyO3 module registration |
| `security-core/src/bloom.rs` | ~200 | BloomFilter: SHA-256 double-hashing, bit-array |
| `security-core/src/finality.rs` | ~300 | FinalityCore: stake-weighted BFT, parking_lot::RwLock |

**BloomFilter Verification:**

- `new(size, hash_count)` — allocates bit array
- `insert(item)` — SHA-256 double-hashing: `h(i) = h1 + i * h2`
- `check(item)` — membership test, false positive rate acceptable
- `to_bytes()` / `from_bytes()` — serialization round-trip
- `union(other)` — merge two filters
- Zero `todo!()` or `unimplemented!()` macros

**FinalityCore Verification:**

- `add_validator(address, stake)` — registers validator
- `remove_validator(address)` — deregisters
- `record_vote(voter, block_height, block_hash)` — records vote, returns success
- `check_finality(block_height)` — voted stake > threshold → finalized
- `get_last_finalized()` — highest finalized height
- `calculate_vote_weight(block_height)` — returns (voted_stake, total_stake)
- `prune_votes(before_height)` — prevents memory growth
- Thread safety: `parking_lot::RwLock` for concurrent access

**Python Fallback Shims:**

- `deniable_rpc.py`: `try: from security_core import BloomFilter; except: use PythonBloomFilter`
- `finality.py`: `try: from security_core import FinalityCore; except: use _PythonFinalityCore`
- Fallback behavior MUST be identical to Rust (same API, same results)

**Build Verification:**

```bash
cd security-core && cargo test
cd security-core && maturin build --release --features extension-module
```

---

### 1S. Stratum Mining Server Audit (7 Rust Files, ~1,030 LOC — Standalone Binary)

**NEW COMPONENT #15 — First introduced in v8.0 (March 4, 2026)**

**Pattern:** Standalone Rust binary (like `rust-p2p/`), communicates with Python node via gRPC.

```
Miners ──WebSocket──> stratum-server (Rust, port 3333)
                          │
                      gRPC (port 50053)
                          │
                      Python node (stratum_bridge.py)
```

| File | LOC | Key Verification |
|------|-----|-----------------|
| `stratum-server/Cargo.toml` | ~50 | tokio, tonic 0.12, prost 0.13, tokio-tungstenite 0.26, dashmap, sha2, uuid |
| `stratum-server/proto/stratum.proto` | ~80 | GetWorkUnit, SubmitSolution, StreamNewBlocks, GetDifficulty |
| `stratum-server/src/main.rs` | ~200 | Tokio runtime, WebSocket server, gRPC client |
| `stratum-server/src/config.rs` | ~60 | Env config: STRATUM_PORT, STRATUM_HOST, STRATUM_MAX_WORKERS |
| `stratum-server/src/worker.rs` | ~150 | StratumWorker struct, shares tracking |
| `stratum-server/src/protocol.rs` | ~200 | Stratum v1 JSON: mining.subscribe/authorize/submit/notify/set_difficulty |
| `stratum-server/src/pool.rs` | ~250 | MiningPool: DashMap workers, work distribution, share validation |
| `stratum-server/src/bridge.rs` | ~150 | gRPC client to Python node |

**Python Bridge** (`mining/stratum_bridge.py`, 157 LOC):

- Python gRPC server (port 50053) that Rust stratum connects to
- Exposes `GetWorkUnit`, `SubmitSolution`, `StreamNewBlocks`, `GetDifficulty`
- Calls into `MiningEngine` and `ConsensusEngine` for real work units

**Per-Component Verification:**

1. WebSocket server handles concurrent miner connections (tokio spawn per connection)
2. Stratum v1 protocol: mining.subscribe returns (subscription_id, extranonce1, extranonce2_size)
3. Share validation: SHA-256 hash of block header + nonce < share_difficulty
4. DashMap: no mutex contention on worker map operations
5. gRPC client: reconnects on failure, exponential backoff
6. Config loaded from environment variables via dotenvy

**Build Verification:**

```bash
cd stratum-server && cargo build --release && cargo test
```

**Docker Integration:**

```dockerfile
# In Dockerfile rust-builder stage:
WORKDIR /build/stratum-server
RUN cargo build --release
# Binary copied as /usr/local/bin/qbc-stratum
```

---

### 1T. PWA Enhancements Audit (3 Libs + 7 Components)

**NEW COMPONENT #16 — First introduced in v8.0 (March 4, 2026)**

Progressive Web App enhancements for the wallet and dashboard.

**New Library Files:**

| File | LOC | Key Verification |
|------|-----|-----------------|
| `frontend/src/lib/offline-tx.ts` | ~150 | IndexedDB-based offline tx queue, auto-broadcast on reconnect |
| `frontend/src/lib/push-notifications.ts` | ~100 | Web Push API, VAPID key support, notification presets |
| `frontend/src/lib/biometric.ts` | ~120 | WebAuthn/FIDO2 for tx signing approval and key export |

**New Components:**

| File | LOC | Key Verification |
|------|-----|-----------------|
| `frontend/src/components/wallet/install-prompt-banner.tsx` | ~80 | PWA install prompt with dismiss persistence |
| `frontend/src/components/wallet/offline-indicator.tsx` | ~40 | Offline status banner |
| `frontend/src/components/wallet/offline-tx-queue.tsx` | ~120 | UI for pending offline transactions |
| `frontend/src/components/wallet/push-notification-setup.tsx` | ~80 | Notification enable/disable panel |
| `frontend/src/components/wallet/inheritance-panel.tsx` | ~150 | Set beneficiary, send heartbeat, view status |
| `frontend/src/components/wallet/security-policy-panel.tsx` | ~150 | Configure spending limits, time-locks, whitelists |
| `frontend/src/components/dashboard/finality-status.tsx` | ~80 | BFT finality metrics with progress bar |
| `frontend/src/components/dashboard/stratum-stats.tsx` | ~100 | Pool mining statistics panel |

**Service Worker** (`frontend/public/sw.js`):

- Background sync for offline transactions
- Push notification handler with action buttons
- Notification click → navigate to relevant page

**Manifest** (`frontend/public/manifest.json`):

- PWA shortcuts (Wallet, Dashboard, Aether)
- `prefer_related_applications: false`
- `scope`, `lang`, `display: standalone`

**Per-Feature Verification:**

1. **Offline TX Queue**: IndexedDB operations correct (open, put, getAll, delete), auto-sync on `online` event
2. **Push Notifications**: VAPID key registration, ServiceWorkerRegistration.pushManager.subscribe()
3. **Biometric Auth**: navigator.credentials.create() with `publicKey` options, authenticatorAttachment: "platform"
4. **Install Prompt**: `beforeinstallprompt` event captured, `localStorage` dismiss persistence
5. **Offline Indicator**: `navigator.onLine` + `online`/`offline` event listeners, cleanup on unmount
6. **Inheritance Panel**: Fetches from `/inheritance/status/{address}`, posts to `/inheritance/set-beneficiary`
7. **Security Panel**: Fetches from `/security/policy/{address}`, posts to `/security/policy/set`
8. **Finality Status**: Fetches from `/finality/status`, displays validator count, stake, finalized height
9. **Stratum Stats**: Fetches from `/stratum/stats`, displays workers, hashrate, blocks found

**Frontend Build Verification:**

```bash
cd frontend && pnpm build
```

All new components must compile without TypeScript errors. Verify no `any` types, all imports resolve.

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

### 1J. Database Schema Audit (44+ Tables, 31 Files)

| Domain | Files | Key Tables | Verify |
|--------|-------|-----------|--------|
| qbc/ (9 files) | blocks, transactions, utxo_set, addresses, balances, chain_state, mempool, genesis_block, **inheritance_plans, inheritance_claims** (07), **security_policies, security_spending** (08), **finality_validators, finality_votes, finality_checkpoints** (09) | Schema matches data models, competitive feature tables present |
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

- `ci.yml`: Python tests (4,357 tests must pass)
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
| Wallet | `/wallet` | ethers.js + MetaMask, chain ID 3303, real balance |
| QVM Explorer | `/qvm` | Real contract queries |
| Block Explorer | `/explorer` | Real chain data from `/block/{height}` |
| Bridge | `/bridge` | Real bridge status from `/bridge/status` |
| Exchange | `/exchange` | Real engine — NOT mock-engine.ts |
| Launchpad | `/launchpad` | Real deployment pipeline |
| Admin | `/admin` | Auth-protected, real admin endpoints |
| Docs (5 sub-routes) | `/docs/*` | Whitepaper, QVM, Aether, Economics |

State Management: `chain-store.ts` (chain data), `wallet-store.ts` (wallet), `theme-store.ts` (theme), `telegram-store.ts` (TWA), `aikgs-store.ts` (AIKGS)
Hooks: `use-chain-socket.ts` (WebSocket), `use-focus-trap.ts`, `use-keyboard-shortcuts.ts`
TWA Routes: `/twa`, `/twa/chat`, `/twa/earn`, `/twa/wallet`, `/twa/refer`, `/twa/more`, `/twa/onboard` (see Phase 1P for detailed TWA audit)

**Critical Questions:**

1. Is `mock-engine.ts` imported anywhere in production code (not just test)?
2. Do all 7 API libs point to `NEXT_PUBLIC_RPC_URL` (not localhost in production)?
3. Does `use-chain-socket.ts` receive real-time block/tx/Phi data?
4. Does MetaMask connect with chain ID 3303 (hex 0xce7)?
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

### 1U. Live Genesis & Node Testing (Requires Running Node)

**This phase tests the LIVE system, not just code review. Start a fresh node and verify.**

**GENESIS VERIFICATION:**

- [ ] Wipe DB: `DROP DATABASE qbc CASCADE; CREATE DATABASE qbc;`
- [ ] Wipe Redis: `FLUSHALL`
- [ ] Run SQL schema init: all `sql_new/` scripts in order
- [ ] Start node: `cd src && python3 run_node.py`
- [ ] Genesis block mined (height=0)
- [ ] Premine: 33,000,000 QBC at operator address
- [ ] Mining reward: 15.27 QBC at operator address
- [ ] Total supply at block 0: 33,000,015.27 QBC
- [ ] Aether Tree initialized (Phi measurement at block 0)
- [ ] Knowledge graph seeded (22 genesis KeterNodes)
- [ ] Difficulty = INITIAL_DIFFICULTY (1.0)
- [ ] Block hash is SHA3-256
- [ ] Coinbase transaction has 2 outputs (reward + premine)
- [ ] Let mine 50+ blocks for stability
- [ ] Verify difficulty adjusting (not stuck at 1.0)
- [ ] Verify Phi increasing (knowledge accumulating)
- [ ] Verify blocks every ~3.3 seconds
- [ ] Verify no exceptions in node log output

**NODE HEALTH:**

- [ ] `GET /health` → all subsystems green
- [ ] `GET /chain/info` → height > 50, supply increasing
- [ ] `GET /mining/stats` → blocks_mined > 50
- [ ] `GET /aether/phi` → Phi > 0.0
- [ ] `GET /aether/knowledge` → nodes > 100
- [ ] `GET /metrics` → Prometheus scraping all 135 metrics
- [ ] `GET /finality/status` → finality gadget active
- [ ] `GET /higgs/status` → Higgs field initialized, VEV=174.14

---

### 1V. Live Endpoint Bombardment (All 342 REST + 19 JSON-RPC)

**Test EVERY endpoint with real data from running node. No mock data. No skips.**

**CHAIN (7+ endpoints):**

- [ ] `GET /` → node info + economics, status 200
- [ ] `GET /health` → all subsystems green, status 200
- [ ] `GET /info` → detailed node info
- [ ] `GET /chain/info` → height, supply, difficulty, peers
- [ ] `GET /chain/tip` → latest block hash and height
- [ ] `GET /crypto/info` → Dilithium params (level 2/3/5)
- [ ] `GET /economics/emission` → emission schedule with phi-halving

**BLOCKS (5+ endpoints):**

- [ ] `GET /block/0` → genesis block with premine (2 coinbase outputs)
- [ ] `GET /block/{latest_height}` → most recent block
- [ ] `GET /mempool` → pending transactions list
- [ ] `GET /mempool/stats` → mempool count, sizes

**WALLET (4+ endpoints):**

- [ ] `GET /balance/{operator_address}` → 33M+ QBC balance
- [ ] `GET /utxos/{operator_address}` → UTXO list (at least coinbase UTXOs)
- [ ] `GET /wallet/check-phrase/{operator_address}` → 3-word check phrase
- [ ] `POST /wallet/verify-check-phrase` → verification result

**MINING (4+ endpoints):**

- [ ] `GET /mining/stats` → blocks_mined, difficulty, reward info
- [ ] `POST /mining/stop` → mining stops (verify no new blocks)
- [ ] `POST /mining/start` → mining resumes (verify new blocks appear)
- [ ] `GET /stratum/info` → stratum server status

**AETHER (20+ endpoints):**

- [ ] `GET /aether/info` → engine stats
- [ ] `GET /aether/phi` → current Phi value > 0.0
- [ ] `GET /aether/phi/history` → Phi values over time
- [ ] `GET /aether/knowledge` → knowledge graph stats (nodes, edges)
- [ ] `GET /aether/knowledge/node/{id}` → specific KeterNode
- [ ] `GET /aether/reasoning/stats` → reasoning operations count
- [ ] `GET /aether/consciousness` → consciousness dashboard
- [ ] `GET /aether/sephirot` → all 10 Sephirot states

**HIGGS (5 endpoints):**

- [ ] `GET /higgs/status` → field state, VEV=174.14, symmetry status
- [ ] `GET /higgs/masses` → all node cognitive masses + Yukawa couplings
- [ ] `GET /higgs/mass/keter` → single node mass
- [ ] `GET /higgs/excitations` → excitation events (may be empty early)
- [ ] `GET /higgs/potential` → potential energy curve params

**INHERITANCE (4 endpoints):**

- [ ] `POST /inheritance/set-beneficiary` → set inheritance plan
- [ ] `POST /inheritance/heartbeat` → reset inactivity timer
- [ ] `GET /inheritance/status/{address}` → plan status
- [ ] `POST /inheritance/claim` → claim test (should fail if active)

**HIGH-SECURITY (3 endpoints):**

- [ ] `POST /security/policy/set` → set spending policy
- [ ] `GET /security/policy/{address}` → get policy
- [ ] `DELETE /security/policy/{address}` → remove policy

**BFT FINALITY (3 endpoints):**

- [ ] `GET /finality/status` → validator count, stake, finalized height
- [ ] `POST /finality/register-validator` → register with stake
- [ ] `POST /finality/vote` → submit vote

**DENIABLE RPCS (4 endpoints):**

- [ ] `POST /privacy/batch-balance` → constant-time multi-address balance
- [ ] `POST /privacy/bloom-utxos` → Bloom filter response
- [ ] `POST /privacy/batch-blocks` → multiple blocks in one request
- [ ] `POST /privacy/batch-tx` → multiple transactions in one request

**ECONOMICS (3+ endpoints):**

- [ ] `GET /economics/emission` → emission schedule
- [ ] `GET /economics/simulate` → simulation data
- [ ] `GET /inflation` → inflation rate

**P2P (3+ endpoints):**

- [ ] `GET /p2p/peers` → connected peers list
- [ ] `GET /p2p/stats` → P2P statistics
- [ ] `POST /p2p/connect` → manual peer connect (may fail in solo mode)

**QVM (8+ endpoints):**

- [ ] `GET /qvm/info` → QVM engine status
- [ ] `GET /qvm/contract/{address}` → contract info (after deployment)
- [ ] `GET /qvm/account/{address}` → account state
- [ ] `POST /qvm/deploy` → deploy contract bytecode
- [ ] `POST /qvm/call` → call contract method

**KEEPER (10+ endpoints):**

- [ ] `GET /keeper/status` → keeper daemon status + mode
- [ ] `GET /keeper/mode` → current operating mode
- [ ] `PUT /keeper/mode/scan` → set to scan mode
- [ ] `GET /keeper/config` → keeper configuration
- [ ] `GET /keeper/history` → action history
- [ ] `GET /keeper/opportunities` → arb opportunities
- [ ] `GET /keeper/signals` → depeg signals
- [ ] `GET /keeper/prices` → multi-chain DEX prices

**STRATUM (3 endpoints):**

- [ ] `GET /stratum/info` → stratum server info
- [ ] `GET /stratum/stats` → pool statistics
- [ ] `GET /stratum/workers` → connected workers

**METRICS:**

- [ ] `GET /metrics` → Prometheus exposition format, 135+ metrics present

**JSON-RPC (19 methods via POST to /):**

- [ ] `eth_chainId` → returns `0xce7` (3303)
- [ ] `eth_blockNumber` → returns latest height in hex
- [ ] `eth_getBalance` → returns balance for operator address
- [ ] `eth_getBlockByNumber` → returns block details
- [ ] `eth_getBlockByHash` → returns block by hash
- [ ] `eth_getTransactionByHash` → returns tx (after sending one)
- [ ] `eth_getTransactionReceipt` → returns receipt
- [ ] `eth_sendRawTransaction` → submit raw transaction
- [ ] `eth_call` → contract call (after deployment)
- [ ] `eth_estimateGas` → gas estimation
- [ ] `eth_gasPrice` → gas price
- [ ] `eth_getCode` → contract code (after deployment)
- [ ] `eth_getStorageAt` → storage slot
- [ ] `eth_getTransactionCount` → nonce
- [ ] `eth_getLogs` → event logs
- [ ] `eth_mining` → mining status
- [ ] `eth_hashrate` → hashrate
- [ ] `net_version` → network version
- [ ] `web3_clientVersion` → client version

---

### 1W. Multi-Address Transaction Testing

**CREATE 3 TEST ADDRESSES:**

- [ ] Address A = node operator (has 33M+ QBC from genesis)
- [ ] Generate Address B via `python3 scripts/setup/generate_keys.py` or `/wallet/create`
- [ ] Generate Address C via same method

**TRANSACTION TESTS:**

- [ ] A → B: Send 100 QBC via `POST /transaction` or `/wallet/send`
- [ ] Verify B balance = 100 QBC via `GET /balance/{B}`
- [ ] Verify A balance decreased by 100 + fee
- [ ] Verify UTXO model: A has change output
- [ ] Wait 6 blocks for confirmation depth
- [ ] B → C: Send 50 QBC
- [ ] Verify C balance = 50 QBC
- [ ] C → A: Send 25 QBC (round-trip test)
- [ ] Verify A received 25 QBC
- [ ] Test insufficient balance (should fail with error, not crash)
- [ ] Test zero amount (should reject)
- [ ] Test self-send A → A (should work, creating new UTXOs)
- [ ] Test maximum amount (entire balance minus fee)
- [ ] Verify all transactions in block explorer (`GET /block/{height}`)
- [ ] Verify Dilithium signatures valid on each tx

**JSON-RPC TRANSACTION TESTS:**

- [ ] `eth_sendTransaction` → send via MetaMask-compatible RPC
- [ ] `eth_getTransactionByHash` → verify tx details match
- [ ] `eth_getTransactionReceipt` → verify receipt fields
- [ ] `eth_getBalance` → verify balance via JSON-RPC matches REST
- [ ] `eth_blockNumber` → matches `GET /chain/info` height

---

### 1X. Contract Deployment & Proxy Verification

**DEPLOY CONTRACTS:**

- [ ] Deploy at least 3 representative contracts via QVM:
  - QBC-20 token contract
  - A simple storage contract
  - AetherKernel (if deploy script available)
- [ ] Verify each contract responds: `GET /qvm/contract/{address}`
- [ ] Verify contract bytecode stored: `eth_getCode`
- [ ] Verify contract storage: `GET /qvm/storage/{address}/{key}`

**CONTRACT INTERACTION:**

- [ ] Call contract read method via `POST /qvm/call`
- [ ] Call contract write method via `POST /qvm/deploy` or `eth_sendTransaction`
- [ ] Verify state changed after write
- [ ] Verify gas metering: `GET /qvm/info` shows execution counts

**TEMPLATE CONTRACTS:**

- [ ] `GET /contracts/templates` → list available templates
- [ ] Deploy a template contract (e.g., token template)
- [ ] Verify template discount applied to fees

---

### 1Y. Bridge Deployment & Cross-Chain Testing (Dry-Run)

**BRIDGE COMPILATION:**

- [ ] `python3 scripts/deploy/deploy_bridge.py --dry-run` (if script exists)
- [ ] Verify all bridge Solidity contracts compile
- [ ] Verify BridgeVault.sol + wQBC.sol (bridge/) bytecode generated

**BRIDGE STATUS:**

- [ ] `GET /bridge/status` → returns supported chains list
- [ ] `GET /bridge/chains` → returns 8 chains (ETH, BNB, SOL, MATIC, AVAX, ARB, OP, BASE)
- [ ] `GET /bridge/transfers` → returns transfer history (may be empty)

**BRIDGE QUOTE:**

- [ ] `GET /bridge/quote` with test parameters → fee estimate
- [ ] Verify default fee = 0.1% (10 bps)

---

### 1Z. Substrate Hybrid Mode Testing

**SUBSTRATE BUILD:**

- [ ] `cd substrate-node && SKIP_WASM_BUILD=1 cargo build --release` → compiles
- [ ] Binary exists at `target/release/qbc-substrate-node`
- [ ] `cd substrate-node && SKIP_WASM_BUILD=1 cargo test` → all pallet tests pass

**PALLET TESTS BREAKDOWN:**

- [ ] qbc-utxo pallet tests pass
- [ ] qbc-consensus pallet tests pass
- [ ] qbc-dilithium pallet tests pass
- [ ] qbc-economics pallet tests pass
- [ ] qbc-qvm-anchor pallet tests pass
- [ ] qbc-aether-anchor pallet tests pass
- [ ] qbc-reversibility pallet tests pass
- [ ] Kyber P2P transport tests pass (25 tests)
- [ ] Poseidon2 primitives tests pass (25 tests)
- [ ] Integration tests pass

**GENESIS PARITY:**

- [ ] Substrate genesis config premine = 33,000,000 QBC
- [ ] Substrate genesis first reward = 15.27 QBC
- [ ] Substrate chain ID = 3303
- [ ] Substrate block time = 3.3s (3300ms)

---

### 1AA. Frontend Build & Page Verification

**BUILD:**

- [ ] `cd frontend && pnpm install` → no errors
- [ ] `pnpm build` → production build succeeds with 0 TypeScript errors
- [ ] `pnpm test` → all Vitest unit tests pass (if configured)
- [ ] Build output lists all expected routes

**PAGE VERIFICATION (all routes):**

- [ ] `/` → Landing page renders (check for compilation, not runtime data)
- [ ] `/aether` → Chat interface page renders
- [ ] `/dashboard` → Dashboard page renders
- [ ] `/wallet` → Wallet page renders
- [ ] `/qvm` → QVM explorer page renders
- [ ] `/bridge` → Bridge interface renders
- [ ] `/exchange` → Exchange interface renders
- [ ] `/explorer` → Block explorer renders
- [ ] `/launchpad` → Launchpad renders
- [ ] `/docs/*` → Documentation pages render
- [ ] `/twa/*` → All 7 TWA pages render
- [ ] `/admin` → Admin page renders (if exists)

**CRITICAL CHECKS:**

- [ ] `mock-engine.ts` NOT imported in production builds (opt-in via env var only)
- [ ] All API libs point to `NEXT_PUBLIC_RPC_URL` (not hardcoded localhost)
- [ ] No `any` types in strict mode (TypeScript errors would fail build)
- [ ] Service worker (`sw.js`) present in public/

---

### 1AB. Stress & Edge Case Testing

**RAPID TRANSACTIONS:**

- [ ] Send 10 rapid transactions from same address (no double-spend)
- [ ] All 10 confirm within reasonable time
- [ ] UTXO set consistent after all confirm

**ERROR HANDLING:**

- [ ] `GET /balance/nonexistent_address` → returns 0, not error
- [ ] `GET /block/99999999` → returns 404 or empty, not crash
- [ ] Submit invalid transaction (bad signature) → rejected with error message
- [ ] Submit duplicate transaction → rejected
- [ ] `POST /aether/chat/message` with empty message → handled gracefully

**BOUNDARY CONDITIONS:**

- [ ] Query genesis block (height=0) → valid response with premine
- [ ] Query negative block height → proper error
- [ ] Send 0 QBC transaction → rejected
- [ ] Very long address string → handled (no buffer overflow)
- [ ] Empty POST body to endpoints → proper 400 error

**LONG-RUNNING STABILITY:**

- [ ] Node mines 100+ blocks without crash
- [ ] Memory usage stable (no unbounded growth visible in logs)
- [ ] No uncaught exceptions in node output

---

## LIVE TESTING RULES (Rules 43-50)

**These rules supplement the 42 code review rules above.**

43. **Live genesis MUST produce valid block 0** with 33M premine + 15.27 mining reward = 33,000,015.27 QBC total supply. Genesis block must have 2 coinbase outputs.

44. **All 342 REST endpoints MUST return valid responses** on a running node. Endpoints may return empty data (e.g., no bridge transfers yet) but must NOT return 500 errors or crash the node.

45. **Multi-address transactions MUST complete full round-trip.** A → B → C → A must all succeed with correct balance changes and valid Dilithium signatures.

46. **All deployed contracts MUST be queryable** via `GET /qvm/contract/{address}` and `eth_getCode` after deployment.

47. **Frontend build MUST succeed with zero TypeScript errors** in strict mode. `pnpm build` must exit 0.

48. **Substrate hybrid node MUST compile** with `SKIP_WASM_BUILD=1 cargo build --release` and all pallet tests must pass.

49. **Bridge dry-run MUST compile** all bridge Solidity contracts successfully (if deploy script available).

50. **3 consecutive 100/100 audit runs required** before launch clearance. Each run must include both code review (Phases 1A-1T) and live testing (Phases 1U-1AB).

---

## PHASE 2: IMPROVEMENT PLAN (3 Per Component = 48 Total)

Produce 3 specific, high-impact improvements for EACH of the 16 components.

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
# QUBITCOIN PROJECT REVIEW — Production-Grade Edition (v8.0)
# Date: [DATE] | Run #[N]

## EXECUTIVE SUMMARY
- Overall Readiness: [X]/100
- Launch-Blocking Issues: [count]
- Top 5 Critical Findings
- Top 5 Strengths

## COMPONENT READINESS MATRIX (16 components)
| # | Component | Score /100 | Launch Ready | Blocking Issues |

## 1. SMART CONTRACT AUDIT TABLE (62 rows)
## 2. SUBSTRATE PALLET AUDIT TABLE (7 pallets + runtime + primitives + crypto)
## 3. OPCODE VERIFICATION TABLE (167 opcodes, Python + Go — all production-grade)
## 4. ENDPOINT VERIFICATION TABLE (342 REST + 19 JSON-RPC = 361)
## 5. RUST AETHER-CORE TABLE (6 modules, todo count, parity, thread safety)
## 6. HIGGS FIELD PHYSICS TABLE (formulas, Python correct, Solidity correct)
## 7. DATABASE SCHEMA TABLE (44+ tables, SQL-model match, dead tables)
## 8. AUTHENTICITY REPORT (every fake with file:line)
## 9. GAP ANALYSIS (16 components)
## 10. DOCKER & CI VERIFICATION (24 services, 4 workflows)
## 11. AIKGS SIDECAR AUDIT TABLE (35 RPCs, auth, input validation, accounting)
## 12. COMPETITIVE FEATURES TABLE (inheritance, security, deniable RPCs, finality)
## 13. RUST SECURITY-CORE TABLE (BloomFilter + FinalityCore, PyO3 bindings, fallback shims)
## 14. STRATUM SERVER TABLE (7 Rust files, WebSocket + gRPC, pool management)
## 15. PWA ENHANCEMENTS TABLE (offline tx, push notifications, biometric, service worker)
## 16. FILE-BY-FILE FINDINGS
## 17. LIVE TESTING RESULTS (Phases 1U-1AB)
### 17.1 Genesis Verification (1U)
### 17.2 Endpoint Bombardment Results (1V — 342 REST + 19 JSON-RPC)
### 17.3 Multi-Address Transaction Log (1W)
### 17.4 Contract Deployment Results (1X)
### 17.5 Bridge Dry-Run Results (1Y)
### 17.6 Substrate Build & Test Results (1Z)
### 17.7 Frontend Build Log (1AA)
### 17.8 Stress Test Results (1AB)
## 18. RUN HISTORY
```

### File 2: MASTERUPDATETODO.md

```
# MASTERUPDATETODO.md — Continuous Improvement Tracker
# Last Updated: [DATE] | Run #[N]

## PROGRESS TRACKER
- Total / Completed / Remaining / %

## END GOAL STATUS

### Government-Grade: [X]% ready
- [ ] Zero placeholder code (16 components)
- [ ] 62 contracts Grade A/B
- [ ] 167 opcodes verified (Python + Go)
- [ ] 361 endpoints verified (342 REST + 19 JSON-RPC)
- [ ] 7 Substrate pallets production-ready
- [ ] 44+ database tables schema-aligned
- [ ] 135 Prometheus metrics emitted
- [ ] 24 Docker services healthy
- [ ] 4 CI workflows passing
- [ ] Higgs physics mathematically correct
- [ ] QUSD fully operational
- [ ] Exchange operational (no mock-engine in prod)
- [ ] Launchpad operational
- [ ] Poseidon2 test vectors verified
- [ ] Kyber P2P encryption functional
- [ ] BFT Finality Gadget: stake-weighted voting, reorg protection
- [ ] Inheritance Protocol: dead-man's switch, grace period, claim lifecycle
- [ ] High-Security Accounts: daily limits, time-locks, whitelists
- [ ] Deniable RPCs: constant-time batch queries, Bloom filter plausible deniability
- [ ] Security Core Rust crate: BloomFilter + FinalityCore, zero todo!(), Python parity
- [ ] Stratum Mining Server: WebSocket + gRPC, DashMap concurrent workers
- [ ] PWA: offline tx queue, push notifications, biometric auth, service worker

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

## IMPROVEMENTS (48 total, 3 per component)
### 5.1-5.16 (one section per component, including competitive features + Rust crates + PWA)

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
17. **361 endpoints verified.** 342 REST + 19 JSON-RPC. Present, functional, tested, frontend-connected.
18. **Rust verification mandatory.** aether-core (6 modules) + security-core (2 modules) + stratum-server (7 files): zero todo!(), numerical parity, thread safety.
19. **Substrate cross-system parity.** Python L1 == Substrate L1 for identical inputs.
20. **62 contracts, 62 rows.** No contract skipped. No contract assumed correct unread.
21. **mock-engine.ts is launch-blocking.** If imported in production exchange code, flag CRITICAL.
22. **Higgs Yukawa hierarchy is tiered.** Not sequential phi^-i. Verify actual code tiers match documentation.
23. **AIKGS sidecar is launch-blocking.** No gRPC auth = CRITICAL. Disburse without validation = CRITICAL. Fire-and-forget treasury payments = CRITICAL.
24. **AIKGS pool accounting must be complete.** Pool balance = initial_pool - SUM(rewards + commissions + bounties). All outflows tracked.
25. **AIKGS contribution pipeline must be transactional.** All 12 steps wrapped in a DB transaction. No partial state on failure.
26. **16 components, 48 improvements.** No component skipped. Competitive features, security-core, stratum, and PWA are the newest — give them extra scrutiny.
27. **TWA pages must render real data.** All 8 pages fetch from live backend APIs. No hardcoded stats, no mock data.
28. **Telegram initData is untrusted.** Frontend uses `initDataUnsafe` for UI display only. Server validates webhook HMAC-SHA-256.
29. **TWA private keys never on server.** `/wallet/create` returns address + public_key_hex ONLY. Private key generation is client-side WASM.
30. **TWA event listener cleanup.** All Telegram SDK callbacks (BackButton, MainButton, theme, viewport) must be cleaned up on unmount.
31. **Bot wallet persistence.** `_user_wallets` in `telegram_bot.py` is in-memory only. Flag if no DB persistence plan documented.
32. **BFT Finality is consensus-critical.** Reorg protection MUST block reorgs below finalized height. Verify `resolve_fork()` in `consensus/engine.py`.
33. **Inheritance grace period is safety-critical.** Owner MUST cancel during grace period. Test: claim + cancel before grace expires = owner keeps funds.
34. **High-Security daily limit is sliding window.** `get_daily_spent()` counts last `SECURITY_DAILY_LIMIT_WINDOW` blocks, not calendar day.
35. **Deniable RPCs must be constant-time.** `batch_balance()` must NOT short-circuit. All queries processed identically to prevent timing attacks.
36. **Security-core Rust/Python parity.** BloomFilter + FinalityCore results MUST be identical between Rust and Python fallback.
37. **Stratum concurrent safety.** DashMap usage verified — no deadlocks, no stale workers after disconnect.
38. **PWA offline queue must not lose transactions.** IndexedDB operations transactional. Queue offline → go online → broadcast → remove from queue.
39. **Service worker must not cache API responses.** Only static assets cached. Dynamic API calls always hit network.
40. **Finality metrics must be accurate.** `finality_total_stake`, `finality_validator_count`, `finality_last_finalized` reflect actual state.
41. **4,357 tests must all pass.** No skipped tests in competitive features. All 193 competitive feature tests green.
42. **Dilithium multi-level verified.** ML-DSA-44/65/87 all functional. Config: `DILITHIUM_SECURITY_LEVEL=5` default.

**See also: Rules 43-50 (Live Testing Rules) above Phase 2.**
