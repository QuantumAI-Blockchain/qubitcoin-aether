# Competitive Features — Qubitcoin

## Overview

Six competitive features added as opt-in, backward-compatible upgrades. All features
are controlled via environment variables and can be enabled/disabled independently.

---

## 1. Inheritance Protocol (Dead-Man's Switch)

**What:** Designate a beneficiary who can claim assets after extended inactivity.

**How it works:**
1. Owner sets a beneficiary + inactivity threshold (blocks)
2. Every outgoing transaction resets the heartbeat counter
3. If heartbeat goes stale (current_height - last_heartbeat > threshold), the beneficiary can claim
4. Grace period allows the owner to cancel (prove they are alive)
5. After grace expires, claim is executed (assets transferred)

**Config:**
```
INHERITANCE_ENABLED=true
INHERITANCE_DEFAULT_INACTIVITY=2618200   # ~100 days at 3.3s blocks
INHERITANCE_GRACE_PERIOD=78546           # ~3 days
```

**Endpoints:**
- `POST /inheritance/set-beneficiary`
- `POST /inheritance/heartbeat`
- `POST /inheritance/claim`
- `GET /inheritance/status/{address}`

**Key files:**
- `src/qubitcoin/reversibility/inheritance.py` — InheritanceManager
- `sql_new/qbc/07_inheritance.sql` — DB schema
- `tests/unit/test_inheritance.py` — 41 tests

---

## 2. High-Security Accounts

**What:** Spending limits, time-locks, and address whitelists for accounts.

**How it works:**
- Set a daily spending limit (QBC)
- Require time-lock for transactions above a threshold
- Restrict outgoing transactions to whitelisted addresses
- Enforcement at mempool/RPC level (not consensus hard fork)

**Config:**
```
SECURITY_POLICY_ENABLED=true
SECURITY_DAILY_LIMIT_WINDOW=26182     # ~24h in blocks
SECURITY_DEFAULT_TIME_LOCK=7854       # ~7.2h in blocks
SECURITY_MAX_WHITELIST_SIZE=100
```

**Endpoints:**
- `POST /security/policy/set`
- `GET /security/policy/{address}`
- `DELETE /security/policy/{address}`

**Key files:**
- `src/qubitcoin/reversibility/high_security.py` — HighSecurityManager
- `sql_new/qbc/08_security_policies.sql` — DB schema
- `tests/unit/test_high_security.py` — 24 tests

---

## 3. Stratum Mining Server (Rust)

**What:** Standalone Rust binary for pool mining via WebSocket/JSON protocol.

**Architecture:**
```
Miners ──WebSocket──> stratum-server (Rust, port 3333)
                          │
                      gRPC (port 50053)
                          │
                      Python node (stratum_bridge.py)
```

**Features:**
- Standard Stratum v1 protocol (mining.subscribe, authorize, submit)
- DashMap-based concurrent worker tracking
- Work unit distribution from Python node via gRPC
- Share validation and block assembly

**Config:**
```
STRATUM_ENABLED=false
STRATUM_PORT=3333
STRATUM_HOST=0.0.0.0
STRATUM_MAX_WORKERS=100
STRATUM_GRPC_PORT=50053
```

**Key files:**
- `stratum-server/` — Rust crate (main.rs, pool.rs, protocol.rs, worker.rs, bridge.rs)
- `src/qubitcoin/mining/stratum_bridge.py` — Python gRPC bridge
- `stratum-server/proto/stratum.proto` — gRPC service definition

---

## 4. Security Core (Rust PyO3 Crate)

**What:** High-performance Bloom filter and finality vote tracking in Rust, exposed to Python via PyO3.

**Components:**
- **BloomFilter** — SHA-256 double-hashing, bit-array based
  - Methods: `new()`, `insert()`, `check()`, `to_bytes()`, `from_bytes()`, `union()`
- **FinalityCore** — Stake-weighted BFT vote tracking
  - Thread-safe via `parking_lot::RwLock`
  - Methods: `add_validator()`, `record_vote()`, `check_finality()`, `prune_votes()`

**Python fallback:** Both components have pure-Python implementations that activate when the Rust crate is not installed.

**Key files:**
- `security-core/src/bloom.rs` — BloomFilter PyO3 class
- `security-core/src/finality.rs` — FinalityCore PyO3 class
- `security-core/Cargo.toml` — pyo3 0.23, parking_lot, sha2

---

## 5. Deniable RPCs (Privacy-Preserving Queries)

**What:** Batch query endpoints that prevent the node from learning which specific addresses/transactions the client cares about.

**Methods:**
- `batch_balance()` — Query multiple addresses at once (constant-time, no short-circuit)
- `bloom_utxos()` — Return UTXOs as a Bloom filter (plausible deniability)
- `batch_blocks()` — Fetch multiple blocks in one request
- `batch_tx()` — Fetch multiple transactions in one request

**Config:**
```
DENIABLE_RPC_ENABLED=true
DENIABLE_RPC_MAX_BATCH=100
DENIABLE_RPC_BLOOM_MAX_SIZE=65536
```

**Endpoints:**
- `POST /privacy/batch-balance`
- `POST /privacy/bloom-utxos`
- `POST /privacy/batch-blocks`
- `POST /privacy/batch-tx`

**Key files:**
- `src/qubitcoin/privacy/deniable_rpc.py` — DeniableRPCHandler
- Uses Rust BloomFilter from security-core (with Python fallback)

---

## 6. BFT Finality Gadget

**What:** Stake-weighted validator voting for probabilistic finality. Once a block is finalized, it cannot be reverted by chain reorgs.

**How it works:**
1. Validators register with a minimum stake (100 QBC default)
2. After accepting a block, validators vote for it
3. When voted stake exceeds threshold (66.7% of total), block is finalized
4. Reorgs past the finalized height are rejected by consensus engine
5. Old votes are pruned to prevent memory growth

**Config:**
```
FINALITY_ENABLED=true
FINALITY_MIN_STAKE=100.0
FINALITY_THRESHOLD=0.667
FINALITY_VOTE_EXPIRY_BLOCKS=1000
```

**Endpoints:**
- `GET /finality/status`
- `POST /finality/vote`
- `POST /finality/register-validator`

**Consensus integration:** `resolve_fork()` in ConsensusEngine rejects reorgs past finalized height.

**Key files:**
- `src/qubitcoin/consensus/finality.py` — FinalityGadget (Python wrapper)
- `security-core/src/finality.rs` — FinalityCore (Rust computation)
- `sql_new/qbc/09_finality.sql` — DB schema

---

## PWA Enhancements

In addition to the 6 core features, the frontend received PWA upgrades:

- **Offline Transaction Queue** — Store signed transactions in IndexedDB when offline, auto-broadcast on reconnection
- **Push Notifications** — Web Push API alerts for new blocks, incoming transactions, mining rewards, finality checkpoints
- **Biometric Auth** — WebAuthn/FIDO2 for transaction signing approval and wallet key export
- **Install Prompt Banner** — PWA install prompt with dismiss persistence
- **Offline Indicator** — Banner displayed when connectivity is lost
- **Service Worker** — Background sync for offline transactions, push notification handling

## Frontend Panels

- **Inheritance Panel** — Set beneficiary, send heartbeat, view status
- **Security Policy Panel** — Configure spending limits, time-locks, whitelists
- **Finality Status** — Dashboard panel showing BFT finality metrics
- **Stratum Stats** — Dashboard panel showing pool mining statistics

---

## Rust Architecture

```
stratum-server/        (standalone Rust binary)
├── WebSocket server on port 3333
├── JSON mining protocol (subscribe/authorize/submit)
├── gRPC client → Python node (port 50053)
└── Pattern: like rust-p2p/ (tokio + tonic + channels)

security-core/         (PyO3 extension crate)
├── BloomFilter: SHA-256 double-hashing, bit-array
├── FinalityCore: stake-weighted BFT vote tracking
├── parking_lot::RwLock for thread-safe access
└── Pattern: like aether-core/ (pyo3 0.23 + maturin)

Python shims (graceful fallback if Rust not installed)
├── deniable_rpc.py: try import security_core.BloomFilter
├── finality.py: try import security_core.FinalityCore
└── stratum_bridge.py: gRPC bridge to Rust stratum server
```

## Test Summary

| Feature | Tests | Status |
|---------|-------|--------|
| Inheritance Protocol | 55 | All passing |
| High-Security Accounts | 34 | All passing |
| Stratum Mining Server | 27 (15 Rust + 12 Python) | All passing |
| Security Core | 17 Rust | All passing |
| Deniable RPCs | 21 | All passing |
| BFT Finality Gadget | 39 | All passing |
| **Total** | **193** | **All passing** |
