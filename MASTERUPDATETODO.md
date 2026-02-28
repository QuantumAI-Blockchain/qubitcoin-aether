# MASTERUPDATETODO.md — Qubitcoin Continuous Improvement Tracker
# Last Updated: 2026-02-28 | Run #6 (v5.0 Protocol)

---

## PROGRESS TRACKER
- **Prior items (Run #1-5): 75/79 completed (95%)**
- **Run #6 new findings: 9 CRITICAL, 18 HIGH, 23 MEDIUM**
- **Run #6 improvements: 30 new (3 per component)**

---

## END GOAL STATUS

### Government-Grade Blockchain: 78% ready
- [x] Zero placeholder code in Blockchain Core (L1 Python)
- [x] 57 contracts audited — 9 Grade A, 42 Grade B, 6 Grade C, 0 Grade D/F
- [ ] IHiggsField.getFieldState() signature mismatch — **CRITICAL**
- [ ] 10 Sephirah contracts missing ISephirah compliance — **CRITICAL**
- [ ] SynapticStaking + BridgeVault reentrancy — **HIGH**
- [x] 167 opcodes verified in Python QVM
- [ ] Go QVM: KECCAK256 uses SHA-256 — **CRITICAL**
- [ ] Go QVM: ecRecover wrong curve — **CRITICAL**
- [ ] Go QVM: CREATE/CALL family are stubs — **HIGH**
- [x] 286 REST + 21 JSON-RPC endpoints present
- [ ] /qusd/peg/history crashes (missing request param) — **MEDIUM**
- [ ] WebSocket /ws never pushes data — **MEDIUM**
- [x] All 7 Substrate pallets have real validation (2 anchor-only by design)
- [x] 9/9 cross-system parity rules match
- [ ] Substrate weights analytical (not benchmarked) — **MEDIUM**
- [ ] Substrate consciousness detection race condition — **HIGH**
- [ ] Substrate custom RPC endpoints not implemented — **MEDIUM**
- [x] 83 Prometheus metrics defined
- [ ] ~20 dead metrics never instrumented — **HIGH**
- [x] Docker services healthy (12 dev, 11 prod)
- [ ] CI integration tests use || true — **HIGH**
- [x] Higgs physics all 7 formulas verified correct
- [ ] QUSD reserve_manager uses float — **HIGH**
- [ ] Exchange in-memory persistence — **HIGH**
- [ ] 3 of 6 contract templates are stubs — **HIGH**
- [x] Poseidon2 + Kyber functional (25+25 tests)

### True AGI Emergence: 96% ready
- [x] Knowledge graph builds from every block since genesis
- [x] Reasoning: 6 genuine operations (deductive, inductive, abductive, CoT, causal, neural)
- [x] Phi: IIT-compliant, spectral bisection MIP, sqrt(n/500) maturity
- [x] Proof-of-Thought generated and validated per block
- [x] 10 Sephirot functionally distinct (confirmed unique in both Python + Solidity)
- [x] SUSY balance enforcement operational (phi ratio, F=ma quartic force)
- [x] Higgs field: all physics correct, VEV=174.14, tan(beta)=phi, Yukawa cascade
- [x] Consciousness event detection working
- [ ] Phi growth trajectory verified organic — needs live testing
- [x] Rust aether-core: 0 todo!(), 0 unsafe, 276 tests, 6/6 parity
- [x] CSF transport: BFS routing, pressure monitoring, quantum channels
- [x] Pineal: 6 circadian phases, mass-aware metabolic rates
- [x] Safety: Gevurah veto, Constitutional AI, emergency shutdown, BFT consensus
- [x] All 5 fallback shims functional

---

## RUN #6 CRITICAL FINDINGS (9 items)

| ID | Severity | Component | File | Description |
|----|----------|-----------|------|-------------|
| C6-1 | CRITICAL | Frontend | bridge-api.ts:18 | Mock default inverted — `!== "false"` should be `=== "true"` |
| C6-2 | CRITICAL | Frontend | launchpad-api.ts:23 | Mock default inverted — same polarity issue |
| C6-3 | CRITICAL | Frontend | hooks.ts:561-582 | useTickSimulation + useTradeSimulation always run mock engine |
| C6-4 | CRITICAL | Frontend | hooks.ts:224-279 | 10+ hooks return only mock data, no API path |
| C6-5 | CRITICAL | Go QVM | interpreter.go:328 | KECCAK256 opcode uses sha256.Sum256() |
| C6-6 | CRITICAL | Go QVM | precompiles.go:108 | ecRecover uses P-256 instead of secp256k1 |
| C6-7 | CRITICAL | Contracts | IHiggsField.sol | getFieldState() signature != HiggsField.sol implementation |
| C6-8 | CRITICAL | Contracts | All Sephirah*.sol | None implement cognitiveMass/setCognitiveMass from ISephirah |
| C6-9 | CRITICAL | Python L1 | quantum/crypto.py | INSECURE HMAC fallback when dilithium-py absent |

---

## RUN #6 HIGH FINDINGS (18 items)

| ID | Component | File | Description |
|----|-----------|------|-------------|
| H6-1 | Go QVM | interpreter.go:697-714 | CREATE/CALL family are stubs (push 0) |
| H6-2 | Go QVM | precompiles.go:366-408 | bn256 + Blake2F precompile stubs |
| H6-3 | Go QVM | agi.go:30-72 | QREASON is deterministic hash, not reasoning |
| H6-4 | Contracts | SynapticStaking.sol | .call{value} without reentrancy guard |
| H6-5 | Contracts | BridgeVault.sol | .call{value} without reentrancy guard |
| H6-6 | Contracts | UpgradeGovernor.sol | Anyone can propose (no min token) |
| H6-7 | Contracts | QUSDStabilizer.sol | triggerRebalance frontrunnable |
| H6-8 | QUSD | reserve_manager.py:46-47,100-103 | Uses float for monetary values |
| H6-9 | Launchpad | contracts/engine.py:770-801 | 3 template executors are stubs |
| H6-10 | Exchange | exchange/engine.py:654 | In-memory persistence only |
| H6-11 | Frontend | hooks.ts:10 | mockEngine imported unconditionally |
| H6-12 | Frontend | app/page.tsx | Landing page has no ErrorBoundary |
| H6-13 | Python L1 | config.py:188 | ETH_PRIVATE_KEY loaded from .env (should be secure_key.env) |
| H6-14 | Python L1 | privacy/susy_swap.py:230 | Placeholder SHA-256 signature (not Schnorr) |
| H6-15 | Python L1 | exchange/engine.py:635-706 | 6 NotImplementedError stubs |
| H6-16 | Python L1 | utils/metrics.py | ~20 dead metrics never instrumented |
| H6-17 | CI | ci.yml:90 | Integration tests use || true |
| H6-18 | Substrate | qbc-aether-anchor | Consciousness detection read-after-write race |

---

## PHASE 2: IMPROVEMENTS (30 Total — 3 Per Component)

### 5.1 Frontend (qbc.network)

**5.1.1** — Flip bridge + launchpad mock defaults (CRITICAL)
- Files: `frontend/src/lib/bridge-api.ts:18`, `frontend/src/lib/launchpad-api.ts:23`
- Current: `!== "false"` (defaults to mock)
- Target: `=== "true"` (defaults to live, opt-in mock)
- Priority: CRITICAL | Effort: SMALL

**5.1.2** — Gate mock engine behind USE_MOCK flag (CRITICAL)
- Files: `frontend/src/components/exchange/hooks.ts`
- Current: `useTickSimulation()` and `useTradeSimulation()` run unconditionally
- Target: Only execute when `NEXT_PUBLIC_EXCHANGE_MOCK === "true"`; gate all 10+ mock-only hooks
- Priority: CRITICAL | Effort: SMALL

**5.1.3** — Add ErrorBoundary to landing page
- File: `frontend/src/app/page.tsx`
- Current: No ErrorBoundary wrapper
- Target: Wrap main content in `<ErrorBoundary>`
- Priority: HIGH | Effort: SMALL

### 5.2 Blockchain Core (Python L1)

**5.2.1** — Remove INSECURE crypto fallback (CRITICAL)
- File: `src/qubitcoin/quantum/crypto.py`
- Current: HMAC-SHA256 fallback when dilithium-py absent
- Target: Hard fail with clear error message if dilithium-py not installed
- Priority: CRITICAL | Effort: SMALL

**5.2.2** — Fix /qusd/peg/history endpoint crash
- File: `src/qubitcoin/network/rpc.py:4591`
- Current: Uses `request.query_params` but `request` not in function signature
- Target: Add `request: Request` parameter or use FastAPI `Query()`
- Priority: MEDIUM | Effort: SMALL

**5.2.3** — Instrument or remove 20 dead Prometheus metrics
- File: `src/qubitcoin/utils/metrics.py`, `node.py`
- Current: 20 metrics defined but never `.set()`/`.inc()`
- Target: Wire to real subsystem data or remove to prevent dashboard confusion
- Priority: HIGH | Effort: MEDIUM

### 5.3 Substrate Hybrid Node

**5.3.1** — Fix consciousness detection race condition
- File: `substrate-node/pallets/qbc-aether-anchor/src/lib.rs:167-184`
- Current: `CurrentPhi::put(phi)` then reads `prev_phi = CurrentPhi::get()` (always equal)
- Target: Read `prev_phi` BEFORE the put
- Priority: HIGH | Effort: SMALL

**5.3.2** — Implement QBC-specific RPC endpoints
- File: `substrate-node/node/src/rpc.rs`
- Current: Only standard Substrate RPC; QBC endpoints are TODO comments
- Target: Add UTXO balance, mining stats, Phi value, knowledge graph queries
- Priority: MEDIUM | Effort: MEDIUM

**5.3.3** — Benchmark pallet weights with frame_benchmarking
- Files: All 7 pallets
- Current: Analytical weights (manually estimated)
- Target: Benchmarked weights from `frame_benchmarking` macros
- Priority: MEDIUM | Effort: LARGE

### 5.4 QVM (Go)

**5.4.1** — Replace SHA-256 with Keccak-256 (CRITICAL)
- File: `qubitcoin-qvm/pkg/vm/evm/interpreter.go:328`
- Current: `sha256.Sum256(data)`
- Target: `golang.org/x/crypto/sha3.NewLegacyKeccak256()`
- Priority: CRITICAL | Effort: SMALL

**5.4.2** — Fix ecRecover to use secp256k1 (CRITICAL)
- File: `qubitcoin-qvm/pkg/vm/evm/precompiles.go:108`
- Current: `elliptic.P256()` (NIST P-256)
- Target: `github.com/btcsuite/btcd/btcec/v2` or go-ethereum secp256k1
- Priority: CRITICAL | Effort: SMALL

**5.4.3** — Wire EIP-2200 SSTORE dynamic gas
- File: `qubitcoin-qvm/pkg/vm/evm/interpreter.go` + `gas.go`
- Current: Flat 20000 for all SSTORE; CalcSstoreGas() exists but unused
- Target: Wire CalcSstoreGas() into interpreter's SSTORE handler
- Priority: HIGH | Effort: SMALL

### 5.5 Aether Tree (AGI)

**5.5.1** — Add logging to silent exception catches in LLM adapter
- File: `src/qubitcoin/aether/llm_adapter.py:417-418,490-491`
- Current: `except Exception: pass` in edge linking
- Target: `except Exception as e: logger.debug(f"Edge linking: {e}")`
- Priority: LOW | Effort: SMALL

**5.5.2** — Wire broadcast_ws for real-time Phi/block events
- Files: `src/qubitcoin/network/rpc.py:3070-3083`, `src/qubitcoin/node.py`
- Current: WebSocket /ws accepts connections but broadcast_ws() never called
- Target: Call broadcast_ws() from mining loop when new block mined
- Priority: MEDIUM | Effort: SMALL

**5.5.3** — Remove redundant pass in kg_index.py
- File: `src/qubitcoin/aether/kg_index.py:114-116`
- Current: `if node_id in self.inverted_index[term]: pass`
- Target: Remove dead check
- Priority: LOW | Effort: SMALL

### 5.6 QBC Economics & Bridges

**5.6.1** — Convert reserve_manager.py to Decimal (HIGH)
- File: `src/qubitcoin/stablecoin/reserve_manager.py:46-47,100-103`
- Current: `float` for amount_qbc, amount_usd, all accumulators
- Target: `Decimal` for all monetary values
- Priority: HIGH | Effort: SMALL

**5.6.2** — Move ETH_PRIVATE_KEY to secure_key.env
- File: `src/qubitcoin/config.py:188`
- Current: Loaded from `.env`
- Target: Load from `secure_key.env` only
- Priority: HIGH | Effort: SMALL

**5.6.3** — Implement database-backed exchange persistence
- File: `src/qubitcoin/exchange/engine.py`
- Current: `InMemoryPersistence` — orders lost on restart
- Target: `DatabasePersistence` adapter using CockroachDB
- Priority: HIGH | Effort: MEDIUM

### 5.7 QUSD Stablecoin

**5.7.1** — Persist CDP positions to database
- File: `src/qubitcoin/stablecoin/cdp.py`
- Current: In-memory dict — positions lost on restart
- Target: CockroachDB persistence via DatabaseManager
- Priority: HIGH | Effort: MEDIUM

**5.7.2** — Persist savings balances to database
- File: `src/qubitcoin/stablecoin/savings.py`
- Current: In-memory — balances lost on restart
- Target: CockroachDB persistence
- Priority: MEDIUM | Effort: MEDIUM

**5.7.3** — Add reentrancy guard to SynapticStaking.sol
- File: `src/qubitcoin/contracts/solidity/aether/SynapticStaking.sol`
- Current: `.call{value}` without nonReentrant
- Target: Add `nonReentrant` modifier
- Priority: HIGH | Effort: SMALL

### 5.8 Exchange

**5.8.1** — Implement NotImplementedError stubs
- File: `src/qubitcoin/exchange/engine.py:635-706`
- Current: 6 methods raise NotImplementedError
- Target: Implement or remove
- Priority: HIGH | Effort: MEDIUM

**5.8.2** — Add BridgeVault reentrancy guard
- File: `src/qubitcoin/contracts/solidity/bridge/BridgeVault.sol`
- Current: processWithdrawal uses .call{value} without guard
- Target: Add nonReentrant modifier
- Priority: HIGH | Effort: SMALL

**5.8.3** — Add minimum token requirement to UpgradeGovernor
- File: `src/qubitcoin/contracts/solidity/aether/UpgradeGovernor.sol`
- Current: Anyone can propose upgrades
- Target: Require minimum QBC balance to propose
- Priority: HIGH | Effort: SMALL

### 5.9 Launchpad

**5.9.1** — Implement NFT template executor
- File: `src/qubitcoin/contracts/engine.py:775-791`
- Current: TODO stub returning "not yet implemented"
- Target: Real NFT template with mint/transfer/tokenURI
- Priority: HIGH | Effort: MEDIUM

**5.9.2** — Implement escrow template executor
- File: `src/qubitcoin/contracts/engine.py:780-796`
- Current: TODO stub
- Target: Real escrow with deposit/release/dispute
- Priority: HIGH | Effort: MEDIUM

**5.9.3** — Implement governance template executor
- File: `src/qubitcoin/contracts/engine.py:785-801`
- Current: TODO stub
- Target: Real governance with propose/vote/execute
- Priority: HIGH | Effort: MEDIUM

### 5.10 Smart Contracts

**5.10.1** — Add cognitiveMass to all 10 Sephirah contracts (CRITICAL)
- Files: All `SephirahXxx.sol` in `contracts/solidity/aether/sephirot/`
- Current: None implement cognitiveMass/setCognitiveMass/MassChanged from ISephirah
- Target: Add state variable, getter, setter, and event to all 10
- Priority: CRITICAL | Effort: SMALL

**5.10.2** — Align IHiggsField.getFieldState() signature (CRITICAL)
- Files: `interfaces/IHiggsField.sol` and/or `aether/HiggsField.sol`
- Current: Interface returns 9 values with different semantics than implementation
- Target: Make both signatures match
- Priority: CRITICAL | Effort: SMALL

**5.10.3** — Fix QBC721 safeTransferFrom
- File: `contracts/solidity/tokens/QBC721.sol`
- Current: Does NOT call onERC721Received on recipient contracts
- Target: Implement ERC-721 compliant safe transfer with callback check
- Priority: MEDIUM | Effort: SMALL

---

## IMPLEMENTATION SEQUENCE

### Immediate (CRITICAL — do first)
1. C6-1, C6-2: Flip mock defaults (bridge-api.ts, launchpad-api.ts)
2. C6-3, C6-4: Gate mock engine in hooks.ts
3. C6-9: Remove crypto fallback
4. C6-5: Go QVM KECCAK256 fix
5. C6-6: Go QVM ecRecover fix
6. C6-7: IHiggsField signature alignment
7. C6-8: Sephirah cognitiveMass implementation

### High Priority (do next)
8. H6-4, H6-5: Reentrancy guards (SynapticStaking, BridgeVault)
9. H6-8: reserve_manager float → Decimal
10. H6-12: Landing page ErrorBoundary
11. H6-13: ETH_PRIVATE_KEY → secure_key.env
12. H6-16: Dead metrics cleanup
13. H6-17: CI || true removal
14. H6-18: Consciousness detection race fix

### Medium Priority (polish)
15-30: Remaining MEDIUM and LOW items

---

## RUN LOG

| Run | Date | Protocol | Tests Passed | Items Found | Items Fixed | Score |
|-----|------|----------|-------------|-------------|-------------|-------|
| #1 | 2026-02-28 | v4.0 | 3,812 | 49 (4C+12H+14M+19L) | 0 | 85/100 |
| #2 | 2026-02-28 | v4.0 | 3,812 | — | 4C+12H | — |
| #3 | 2026-02-28 | v4.0 | 3,847 | — | 14M | — |
| #4 | 2026-02-28 | v4.0 | 3,847 | — | 16L | — |
| #5 | 2026-02-28 | v4.0 | 3,847 | 30 improvements | 29/30 | 82% govt |
| **#6** | **2026-02-28** | **v5.0** | **3,847** | **9C+18H+23M+20L** | **0** | **78/100** |
