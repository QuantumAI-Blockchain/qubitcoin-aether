# QUBITCOIN PROJECT REVIEW
# Military-Grade Production Audit — v7.0 Protocol
# Date: 2026-03-02 | Run #10

---

## EXECUTIVE SUMMARY

- **Overall Readiness Score: 68/100** (down from 100/100 in Run #9 due to expanded audit scope)
- **Launch-Blocking Issues: 23 CRITICAL**
- **Total Files Audited: 330+** (added AIKGS sidecar: 18 Rust + 4 Python files)
- **Total LOC Audited: ~185,000+**
- **Test Suite: 3,847 passed, 4 failed (need running node), 4 skipped (Python) + 63 passed (Go QVM) + 73 passed (Substrate)**
- **Audit Protocol: v7.0 — Includes AIKGS Rust sidecar (Component #11)**

### What Changed Since Run #9 (100/100 → 68/100)

**Run #10 is NOT a regression.** The score drop reflects:
1. **New component added:** AIKGS Rust sidecar (4,500 LOC) audited for the first time — 29 findings
2. **Deeper audit methodology:** Line-by-line review of 11 core files (L1), 23 Aether files, 18 QVM/Solidity files, 17 Substrate/Rust files, 30+ frontend/infra files
3. **Previously undetected issues** in existing code surfaced by more thorough analysis
4. **New code changes** from AIKGS migration (node.py, rpc.py, mining/engine.py, consensus/engine.py modified)

### Finding Summary (All 11 Components)

| Severity | Count | Launch Blocking? |
|----------|-------|-----------------|
| CRITICAL | 23 | YES — must fix before launch |
| HIGH | 46 | YES — must fix before launch |
| MEDIUM | 49 | Should fix, not blocking |
| LOW | 34 | Nice to fix |
| INFO | 23 | Observations only |
| **TOTAL** | **175** | **69 blocking** |

---

## COMPONENT READINESS MATRIX (11 Components)

| # | Component | Score | Launch Ready | CRITICAL | HIGH | MEDIUM | LOW | INFO |
|---|-----------|-------|-------------|----------|------|--------|-----|------|
| 1 | Frontend (qbc.network) | 55/100 | NO | 3 | 7 | 8 | 6 | 5 |
| 2 | Blockchain Core (Python L1) | 72/100 | NO | 6 | 10 | 10 | 6 | 5 |
| 3 | Substrate Hybrid Node (Rust L1) | 70/100 | TESTNET | 4 | 8 | 12 | 7 | 5 |
| 4 | QVM Python + Go (L2) | 68/100 | NO | 5 | 9 | 8 | 5 | 4 |
| 5 | Aether Tree (Python L3) | 60/100 | NO | 5 | 10 | 12 | 8 | 7 |
| 6 | QBC Economics & Bridges | 85/100 | YES* | 0 | 0 | 0 | 0 | 0 |
| 7 | QUSD Stablecoin | 85/100 | YES* | 0 | 1 | 1 | 1 | 0 |
| 8 | Exchange | 90/100 | YES* | 0 | 0 | 0 | 0 | 0 |
| 9 | Launchpad | 90/100 | YES* | 0 | 0 | 0 | 0 | 0 |
| 10 | Smart Contracts (57 .sol) | 75/100 | NO | 0 | 5 | 4 | 1 | 2 |
| 11 | **AIKGS Rust Sidecar** (NEW) | 40/100 | NO | 4 | 8 | 9 | 8 | 7 |

*Components 6-9 scored 100/100 in Run #9 and were not deeply re-audited in Run #10. Scores adjusted slightly as dependent components (L1, QVM) have issues that affect their operation.

---

## TOP 10 CRITICAL FINDINGS (Immediate Fix Required)

### 1. [AIKGS-C1] No Authentication on Any gRPC Endpoint
**Files:** `aikgs-sidecar/src/main.rs`, `aikgs-sidecar/src/service.rs`
All 35 AIKGS gRPC RPCs callable by anyone on the network. `Disburse` allows unauthorized fund transfers. `StoreApiKey`/`GetApiKey` expose plaintext LLM API keys.
**Fix:** mTLS between node and sidecar + remove host port binding from docker-compose.yml.

### 2. [L1-C2] eth_sendRawTransaction Executes Transfers Before Block Inclusion
**File:** `src/qubitcoin/network/jsonrpc.py:384-508`
Value transfers applied to account balances immediately, bypassing consensus. Double-execution risk if the tx is also included in a mined block.
**Fix:** Store as pending only. Let miners include in blocks through consensus.

### 3. [FE-C1] Private Key Generated on Server, Returned Over HTTP
**File:** `src/qubitcoin/network/rpc.py:2365-2376`, `frontend/src/lib/api.ts:442-446`
Dilithium2 private key (~5KB) generated on backend and transmitted to client.
**Fix:** Client-side WASM key generation. Remove `/wallet/create` endpoint.

### 4. [FE-C3] HMAC-SHA256 Placeholder Signing — No Cryptographic Security
**File:** `frontend/src/lib/dilithium.ts:29-66`
Uses HMAC-SHA256 with the PUBLIC KEY as secret. Anyone who knows the public key can forge signatures.
**Fix:** Implement actual Dilithium2 WASM signing.

### 5. [AIKGS-C2] Disburse RPC — No Auth, No Limits, No Rate Limiting
**File:** `aikgs-sidecar/src/service.rs:816-831`
Anyone can trigger unlimited treasury disbursements to arbitrary addresses.
**Fix:** Add auth, amount validation, rate limiting, maximum caps.

### 6. [AETHER-C1] SUSY Balance Enforcement is Dead Code
**File:** `src/qubitcoin/aether/proof_of_thought.py:596-612`
`_sephirot_manager` never assigned — golden ratio enforcement never runs.
**Fix:** Wire `self._sephirot_manager` from `node.py` or use `self.pineal.sephirot`.

### 7. [AETHER-C2] Proof-of-Thought Validation Accepts Null Proofs Forever
**File:** `src/qubitcoin/aether/proof_of_thought.py:260-261`
No block height cutoff. PoT is "optional during transition" with no end date.
**Fix:** Add `MANDATORY_POT_HEIGHT` config and enforce after that height.

### 8. [AETHER-C4] Gevurah Safety Veto Uses Hardcoded Secret
**File:** `src/qubitcoin/aether/safety.py:136-150`
Fallback to `sha256(b"gevurah-veto-default-secret")` — derivable from source code.
**Fix:** Refuse to start without `GEVURAH_SECRET` environment variable.

### 9. [QVM-C1] Keccak-256 Silent Fallback to SHA-256
**File:** `src/qubitcoin/qvm/vm.py:17-40`
Missing library causes silent hash algorithm switch — consensus-breaking.
**Fix:** Remove SHA-256 fallback. Fail loudly if keccak library is missing.

### 10. [SUBSTRATE-C3] Anyone Can Submit Mining Proofs for Any Miner Address
**File:** `substrate-node/pallets/qbc-consensus/src/lib.rs:181`
`miner_address` is a free parameter, not tied to `origin`. Front-running attacks possible.
**Fix:** Derive `miner_address` from transaction signer or require Dilithium signature.

---

## ALL CRITICAL FINDINGS (23 Total)

### L1 Blockchain Core (6 CRITICAL)

| ID | File | Issue |
|----|------|-------|
| L1-C1 | mining/engine.py:402 | `pk_bytes` misleading name for private key, no length validation |
| L1-C2 | jsonrpc.py:384-508 | eth_sendRawTransaction executes transfers before block inclusion |
| L1-C3 | jsonrpc.py:510-585 | eth_sendTransaction allows unsigned contract deployment from "localhost" |
| L1-C4 | rpc.py:1570 | DD Report JSON injection via string interpolation |
| L1-C5 | consensus/engine.py:404-413 | Coinbase maturity off-by-one |
| L1-C6 | mining/engine.py:204-230 | Race condition in mining block storage |

### AIKGS Rust Sidecar (4 CRITICAL)

| ID | File | Issue |
|----|------|-------|
| AIKGS-C1 | main.rs, service.rs | No authentication on any gRPC endpoint |
| AIKGS-C2 | service.rs:816-831 | Disburse RPC: no auth, no limits, no rate limiting |
| AIKGS-C3 | db.rs:193-199, contributions.rs:289 | TOCTOU race on contribution ID (MAX+1) |
| AIKGS-C4 | service.rs:225-240 | Treasury disbursement fire-and-forget, no idempotency |

### L3 Aether Tree (5 CRITICAL)

| ID | File | Issue |
|----|------|-------|
| AETHER-C1 | proof_of_thought.py:596-612 | SUSY balance enforcement is dead code |
| AETHER-C2 | proof_of_thought.py:260-261 | PoT validation accepts null proofs forever |
| AETHER-C3 | proof_of_thought.py:269 | Phi threshold (3.0) not enforced in block validation |
| AETHER-C4 | safety.py:136-150 | Gevurah veto uses hardcoded default secret |
| AETHER-C5 | safety.py:591-601 | Emergency shutdown resume has no authentication |

### L2 QVM (5 CRITICAL)

| ID | File | Issue |
|----|------|-------|
| QVM-C1 | qvm/vm.py:17-40 | Keccak-256 silent fallback to SHA-256 |
| QVM-C2 | qvm/opcodes.py:300 | Unknown opcodes charged zero gas |
| QVM-C3 | qvm/vm.py:1878-1887 | QCOMPLIANCE returns "pass" when engine unavailable |
| QVM-C4 | Go interpreter.go:44-75 | mustPop returns zero on underflow, continues executing |
| QVM-C5 | qvm/vm.py (entire) | Missing EIP-2929 warm/cold access tracking |

### Substrate Node (4 CRITICAL)

| ID | File | Issue |
|----|------|-------|
| SUB-C1 | qbc-dilithium/lib.rs:54-123 | WASM Dilithium bypass: any valid-sized signature passes |
| SUB-C2 | qbc-consensus/lib.rs:207-211 | Replay prevention checks only last proof hash |
| SUB-C3 | qbc-consensus/lib.rs:181 | Anyone can submit mining proof for any miner address |
| SUB-C4 | qbc-utxo/lib.rs:162-314 | Frozen UTXOs from reversibility pallet not checked |

### Frontend (3 CRITICAL)

| ID | File | Issue |
|----|------|-------|
| FE-C1 | rpc.py:2365-2376, api.ts:442-446 | Private key generated server-side, returned over HTTP |
| FE-C2 | twa/onboard/page.tsx:56 | Private key stored in sessionStorage (XSS exfiltration) |
| FE-C3 | dilithium.ts:29-66 | HMAC-SHA256 placeholder signing with public key as secret |

---

## ALL HIGH FINDINGS (46 Total)

### L1 Blockchain Core (10 HIGH)

| ID | Issue |
|----|-------|
| L1-H1 | `_is_coinbase_utxo` returns False on DB error (unsafe default) |
| L1-H2 | Difficulty cache unbounded growth + fork invalidation gaps |
| L1-H3 | Tx signature verification uses non-deterministic `str()` of dict |
| L1-H4 | `validate_block` allows blocks with no proof signature |
| L1-H5 | Fork resolution has no MAX_REORG_DEPTH enforcement |
| L1-H6 | `_pending_commits` dict grows without bound |
| L1-H7 | IPFS snapshot exports all data without pagination |
| L1-H8 | Config validation failure only emits warning, node starts anyway |
| L1-H9 | Mining stats access without lock (data race) |
| L1-H10 | `knowledge_prune` endpoint has no authentication |

### AIKGS Sidecar (8 HIGH)

| ID | Issue |
|----|-------|
| AIKGS-H1 | GetApiKey returns decrypted keys without owner verification |
| AIKGS-H2 | No input validation on addresses, content length, string fields |
| AIKGS-H3 | Reward amount includes bounty but reward record doesn't (accounting mismatch) |
| AIKGS-H4 | Bounty fulfillment race condition (double-fulfill) |
| AIKGS-H5 | Affiliate commissions not deducted from pool balance |
| AIKGS-H6 | Dynamic SQL construction pattern in increment_affiliate_commission |
| AIKGS-H7 | No transaction wrapping for multi-step operations |
| AIKGS-H8 | Unbounded query results in multiple endpoints |

### L3 Aether Tree (10 HIGH)

| ID | Issue |
|----|-------|
| AETHER-H1 | Coherence metric degenerate when energies equal (reports 1.0 at genesis) |
| AETHER-H2 | `_delivered` list in CSF transport grows unbounded |
| AETHER-H3 | `violations` list in SephirotManager grows unbounded |
| AETHER-H4 | `_consciousness_events` in PinealOrchestrator grows unbounded |
| AETHER-H5 | `_events` in ConsciousnessDashboard grows unbounded |
| AETHER-H6 | Chat memory persists to world-readable `/tmp` path |
| AETHER-H7 | Nonce eviction in VetoAuthenticator is non-deterministic |
| AETHER-H8 | Thread safety gaps in KnowledgeGraph (3 methods unlocked) |
| AETHER-H9 | Task protocol allows self-voting (validator = solver) |
| AETHER-H10 | `get_status()` returns zero corrections (dead code: `sum(1 for _ in [])`) |

### L2 QVM + Solidity (9 HIGH)

| ID | Issue |
|----|-------|
| QVM-H1 | QBC20 approve() front-running vulnerability |
| QVM-H2 | RewardDistributor.distributeReward missing reentrancy guard |
| QVM-H3 | SynapticStaking.userStake missing reentrancy guard |
| QVM-H4 | HiggsField unbounded excitations array (storage gas bomb) |
| QVM-H5 | Python QVM SSTORE missing original value tracking (EIP-2200) |
| QVM-H6 | Python QVM DELEGATECALL does not preserve msg.value |
| QVM-H7 | Go QVM CALL value transfer without balance check |
| QVM-H8 | Gas refund: porting risk from Python to fixed-width integers |
| QVM-H9 | ProofOfThought partial unstake leaves request open (bypass 7-day delay) |

### Substrate + Rust (8 HIGH)

| ID | Issue |
|----|-------|
| SUB-H1 | Kyber nonce overflow check uses wrong threshold (u64::MAX vs 2^32) |
| SUB-H2 | Same key for send/receive ciphers — AES-GCM nonce reuse |
| SUB-H4 | Economics pallet: loop-based phi division can overflow at high eras |
| SUB-H5 | P2P gossipsub messages not size-limited (OOM) |
| SUB-H6 | P2P `expect()` in spawned tasks causes silent panics |
| SUB-H7 | Reversibility pallet iterates entire storage map for expired entries |
| SUB-H8 | Poseidon2 round constants generated via LCG (weak PRNG) |

### Frontend + Infra (7 HIGH)

| ID | Issue |
|----|-------|
| FE-H1 | Grafana default password in docker-compose.yml |
| FE-H2 | CockroachDB insecure mode in dev docker-compose |
| FE-H3 | Redis has no authentication in either docker-compose |
| FE-H4 | API_KEY_VAULT_SECRET has weak default |
| FE-H5 | AIKGS vault master key passed as environment variable |
| FE-H6 | Mock data can leak into production (no build-time guard) |
| FE-H7 | Private key derivative used as spending key for Susy Swaps |

---

## RUN HISTORY

| Run | Date | Protocol | Score | CRITICAL | HIGH | MEDIUM | LOW | Notes |
|-----|------|----------|-------|----------|------|--------|-----|-------|
| 1-6 | Feb 2026 | v1-v5 | 75-95 | Various | — | — | — | Initial development + audits |
| 7 | 2026-02-28 | v6.0 | 92/100 | 3 | 9 | 15 | 14 | First military-grade audit |
| 8 | 2026-02-28 | v6.0 | 97/100 | 0 | 0 | 0 | 12 | Re-audit after fixes |
| 9 | 2026-03-01 | v6.2 | 100/100 | 0 | 0 | 0 | 0 | All findings resolved |
| **10** | **2026-03-02** | **v7.0** | **68/100** | **23** | **46** | **49** | **34** | **AIKGS sidecar added + deeper audit across all 11 components** |

### Run #10 Notes

- Protocol upgraded from v6.2 to v7.0 to include AIKGS Rust sidecar (Component #11)
- AIKGS sidecar committed in `97bc1c5` — first audit of new ~4,500 LOC Rust binary
- Audit methodology deepened: 6 parallel audit agents, line-by-line review of all critical files
- Score drop from 100→68 is NOT a regression — reflects expanded scope and deeper analysis
- Components 6-9 (Economics, QUSD, Exchange, Launchpad) not re-audited in depth — retain prior scores with minor adjustment

---

## PRIORITY REMEDIATION ROADMAP

### Phase 1: Pre-Launch Blockers (23 CRITICAL + top HIGH — ~2-3 days)

**Authentication & Authorization (Day 1):**
1. AIKGS-C1/C2: Add mTLS to gRPC sidecar, remove host port binding
2. FE-C1/C3: Implement Dilithium2 WASM client-side key generation and signing
3. AETHER-C4/C5: Remove hardcoded Gevurah secret, add auth to resume()
4. L1-C3: Tighten `_is_localhost()` default to False

**Consensus Safety (Day 1-2):**
5. L1-C2: Fix eth_sendRawTransaction to store pending only
6. QVM-C1: Remove SHA-256 fallback for Keccak
7. QVM-C3: QCOMPLIANCE default to deny when engine unavailable
8. SUB-C3: Derive miner_address from transaction signer

**AGI Enforcement (Day 2):**
9. AETHER-C1: Wire `_sephirot_manager` for SUSY enforcement
10. AETHER-C2/C3: Add mandatory PoT height + Phi threshold check

**Data Integrity (Day 2-3):**
11. AIKGS-C3: Use DB sequences for contribution IDs
12. AIKGS-C4: Add disbursement tracking and idempotency
13. AIKGS-H3/H5: Fix pool balance accounting (include bounties + commissions)

### Phase 2: HIGH Findings (~1 week)

**Memory Safety:** Fix all unbounded list growth (AETHER-H2/H3/H4/H5, AIKGS-H8)
**Thread Safety:** Fix KnowledgeGraph lock gaps (AETHER-H8)
**Crypto:** Fix Kyber nonce reuse (SUB-H2), Poseidon2 round constants (SUB-H8)
**Solidity:** Add reentrancy guards (QVM-H2/H3), fix unstake bypass (QVM-H9)
**Input Validation:** AIKGS-H2 (all endpoints), L1-H10 (knowledge_prune auth)

### Phase 3: MEDIUM + LOW (~1-2 weeks)

Remaining findings by component. See full finding tables above.

---

*This review was generated by running AUDIT_PROTOCOL.md v7.0 with 6 parallel audit agents.*
*Protocol covers 11 components, ~185,000+ LOC across Python, Rust, Go, TypeScript, and Solidity.*
