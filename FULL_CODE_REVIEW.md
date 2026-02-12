# Qubitcoin Full Code Review
## QBC Compatibility with QVM & Aether Tree

**Date:** 2026-02-11
**Scope:** All source files on `master` branch
**Focus:** QBC readiness for QVM (EVM-compatible VM) and Aether Tree (AGI layer)

---

## Executive Summary

QBC has a functional L1 blockchain with quantum proof-of-work, UTXO model, post-quantum cryptography, P2P networking, smart contracts, stablecoin, cross-chain bridge, and IPFS storage. However, the smart contract system is **NOT a bytecode VM** — it's a JSON-config dispatch system. To support the QVM (with 140+ EVM opcodes + quantum opcodes) and Aether Tree (AGI reasoning layer), QBC needs fundamental architectural additions.

**Current state:** QBC works as a standalone L1 chain.
**What's missing:** A bytecode execution engine, EVM opcode interpreter, state trie, gas metering runtime, and the hooks for Aether Tree's Proof-of-Thought consensus.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [File-by-File Review](#2-file-by-file-review)
3. [QVM Compatibility Gap Analysis](#3-qvm-compatibility-gap-analysis)
4. [EVM Opcode Coverage](#4-evm-opcode-coverage)
5. [Aether Tree Integration Points](#5-aether-tree-integration-points)
6. [Critical Issues (Must Fix)](#6-critical-issues)
7. [High Priority Issues](#7-high-priority-issues)
8. [Medium Priority Issues](#8-medium-priority-issues)
9. [Recommended Architecture](#9-recommended-architecture)
10. [Implementation Roadmap](#10-implementation-roadmap)

---

## 1. Architecture Overview

### Current QBC Stack
```
┌─────────────────────────────────────────┐
│           RPC (FastAPI :5000)            │ ← HTTP API
├─────────────────────────────────────────┤
│          Node Orchestrator              │ ← node.py
├──────────┬──────────┬───────────────────┤
│ Mining   │Consensus │ Contract Engine   │ ← Python modules
│ Engine   │ Engine   │ (JSON dispatch)   │
├──────────┴──────────┴───────────────────┤
│        Quantum Engine (Qiskit VQE)      │ ← Proof-of-SUSY
├─────────────────────────────────────────┤
│     Database (CockroachDB/SQLAlchemy)   │ ← State storage
├──────────┬──────────────────────────────┤
│ Python   │  Rust P2P (libp2p + gRPC)   │ ← Networking
│ P2P      │                              │
├──────────┴──────────────────────────────┤
│  Bridge (ETH/Polygon/BSC/SOL/etc.)     │ ← Cross-chain
├─────────────────────────────────────────┤
│  IPFS Storage + Stablecoin (QUSD)      │ ← Extras
└─────────────────────────────────────────┘
```

### What QVM + Aether Need
```
┌─────────────────────────────────────────┐
│     JSON-RPC (eth_* compatible)         │ ← Web3 compatible
├─────────────────────────────────────────┤
│          Node Orchestrator              │
├──────────┬──────────┬───────────────────┤
│ Mining   │Consensus │    QVM Runtime    │ ← BYTECODE VM
│ Engine   │ Engine   │ (140 EVM opcodes  │
│          │ + PoT    │  + quantum ops)   │
├──────────┴──────────┼───────────────────┤
│  Quantum Engine     │  Aether Tree      │ ← AGI Layer
│  (VQE / PoSA)      │  (KeterNode,      │
│                     │   Proof-of-Thought)│
├─────────────────────┴───────────────────┤
│  State Trie (MPT or similar)            │ ← Account model
├─────────────────────────────────────────┤
│     Database + Gas Metering Runtime     │
└─────────────────────────────────────────┘
```

---

## 2. File-by-File Review

### 2.1 `config.py` — Configuration
**Status:** GOOD
- Clean env-var based config with sensible defaults
- SUSY economics parameters well-defined (PHI, halving, emission)
- Rust P2P toggle, bridge settings, quantum settings all present
- **QVM gap:** No QVM-specific config (gas limits, block gas cap, EVM version, opcode toggles)

### 2.2 `node.py` — Node Orchestrator
**Status:** GOOD (after merge fixes)
- Initializes 9 components in order with proper error handling
- Rust P2P / Python P2P dual-mode
- Metrics loop, mining control, block broadcast
- **QVM gap:** No QVM initialization step, no state root tracking, no EVM transaction processor

### 2.3 `quantum/engine.py` — Quantum VQE Engine
**Status:** SOLID
- Deterministic Hamiltonian derivation from `prev_hash + height` — correct design
- VQE optimization with COBYLA optimizer
- Proof validation re-derives Hamiltonian from chain state (prevents forged challenges)
- 4-qubit TwoLocal ansatz with Ry/CZ gates
- **QVM gap:** Need to expose quantum opcodes to QVM:
  - `QGATE` (0xf5) — apply quantum gate
  - `QMEASURE` (0xf6) — measure qubit
  - `QENTANGLE` (0xf7) — entangle qubits
  - `QVQE` (0xf8) — run VQE optimization
  - `QHAMILTONIAN` (0xf9) — generate/load Hamiltonian
  - `QPROOF` (0xfa) — validate quantum proof

### 2.4 `quantum/crypto.py` — Post-Quantum Cryptography
**Status:** GOOD with caveat
- CRYSTALS-Dilithium2 (NIST Level 2) via dilithium-py
- Proper keygen/sign/verify with fallback for dev mode
- Address derivation: SHA256(public_key)[:40]
- **Issue:** Fallback mode is insecure (hash-based mock) — must enforce real Dilithium in production
- **QVM gap:** Need `ECRECOVER`-equivalent opcode that verifies Dilithium signatures, not secp256k1

### 2.5 `consensus/engine.py` — Consensus Engine
**Status:** SOLID
- Golden ratio reward halvings: `reward = INITIAL / (PHI ^ era)`
- Difficulty adjustment every 1000 blocks with 0.25x-4.0x bounds
- Block validation: height, prev_hash, difficulty, quantum proof, coinbase, timestamps
- Transaction validation: UTXO lookup by txid/vout, double-spend detection, signature verify
- Fork resolution with chain reorg
- **QVM gap:** No `stateRoot` validation in blocks. Need to validate world state after executing QVM transactions.
- **Aether gap:** No Proof-of-Thought hooks. Aether's `ProofOfThought.sol` needs a consensus integration point where thought proofs are validated alongside quantum proofs.

### 2.6 `mining/engine.py` — Mining Engine
**Status:** SOLID
- Threaded mining loop with VQE nonce grinding
- Deterministic Hamiltonian from chain state (every miner gets same puzzle)
- Up to 50 attempts per round with different random initial params
- Atomic block storage under lock (prevents race conditions)
- Self-validation before storage
- **QVM gap:** After mining, need to execute all pending QVM transactions and compute `stateRoot` before block finalization.

### 2.7 `contracts/engine.py` — Smart Contract Engine
**Status:** FUNCTIONAL BUT NOT A VM
- **This is the core QVM gap.** Currently a JSON-config dispatch system:
  - `deploy_contract()` stores JSON config in DB
  - `execute_contract()` routes to hardcoded Python methods
  - Supported types: token, nft, launchpad, escrow, governance, quantum_gate
  - Token operations (transfer, approve, transferFrom) work
  - Quantum gate unlock via VQE proof validation works
- **NOT a bytecode interpreter.** No opcodes, no stack machine, no EVM compatibility.
- **What QVM needs:** Replace this with a proper stack-based bytecode VM that interprets EVM opcodes + quantum opcodes.

### 2.8 `contracts/executor.py` — Contract Executor
**Status:** FUNCTIONAL
- Second contract execution path (stablecoin + token focus)
- ERC-20 style `transfer`, `balanceOf` for tokens
- Stablecoin routing to `StablecoinEngine`
- Contract cache for performance
- **Same QVM gap:** Python method dispatch, not bytecode execution.

### 2.9 `contracts/templates.py` — Contract Templates
**Status:** MINIMAL
- Only QUSD stablecoin template defined
- **QVM gap:** Templates won't be needed once QVM compiles Solidity to bytecode.

### 2.10 `database/manager.py` — Database Manager
**Status:** SOLID
- CockroachDB with SQLAlchemy ORM
- Full UTXO operations (get, create, mark spent)
- Block storage with transaction processing
- Supply tracking
- Hamiltonian research data storage
- 20+ SQLAlchemy models covering: blocks, txs, UTXOs, contracts, tokens, stablecoin, bridge, IPFS, launchpad, quantum gates
- **QVM gap:** Missing:
  - `contract_storage` table for key-value state (defined in SQL schemas but not used by Python)
  - `contract_logs` table for events (defined in SQL but unused)
  - Account balance model (currently UTXO-only; QVM needs account model for contract storage)
  - State root computation (Merkle Patricia Trie or similar)

### 2.11 `network/rpc.py` — RPC Server
**Status:** FUNCTIONAL
- FastAPI with CORS, Prometheus metrics
- Endpoints: node info, blocks, chain, economics, balance, UTXOs, mempool, mining, P2P
- **QVM gap — CRITICAL:** No `eth_*` JSON-RPC methods. Web3 tools (MetaMask, Hardhat, Ethers.js) cannot interact with QBC. Need:
  - `eth_blockNumber`, `eth_getBlockByNumber`, `eth_getBlockByHash`
  - `eth_sendTransaction`, `eth_sendRawTransaction`
  - `eth_call` (read-only contract call)
  - `eth_estimateGas`
  - `eth_getTransactionReceipt`, `eth_getTransactionByHash`
  - `eth_getLogs` (event filtering)
  - `eth_getCode`, `eth_getStorageAt`
  - `eth_chainId`, `net_version`
  - `eth_getBalance` (account model, not UTXO)

### 2.12 `network/p2p_network.py` — Python P2P
**Status:** FUNCTIONAL with issues
- Asyncio TCP-based gossip protocol
- Peer management, message deduplication, rate limiting
- **Issues:** No message signing, no TLS, weak peer scoring, memory leak in seen_messages cache
- **QVM gap:** Need to propagate QVM transactions (with bytecode payload) not just UTXO transactions.

### 2.13 `network/rust_p2p_client.py` — Rust P2P Bridge
**Status:** FUNCTIONAL
- gRPC client to Rust libp2p network
- Block broadcasting, peer stats
- **Issue:** Missing `broadcast_transaction()` method
- **QVM gap:** Need to handle QVM transaction types in the protocol.

### 2.14 `rust-p2p/` — Rust P2P Network
**Status:** SCAFFOLDED
- libp2p 0.56 with Kademlia + Gossipsub
- gRPC bridge to Python via tonic
- Protocol definition for Qubitcoin messages
- **Issues:** Event loop only forwards messages to Python, doesn't process them. Missing block/tx validation.

### 2.15 `bridge/` — Cross-Chain Bridge
**Status:** WELL DESIGNED
- Abstract base class with 8 supported chains (ETH, Polygon, BSC, Arbitrum, Optimism, Avalanche, Base, Solana)
- EVM bridge uses Web3.py with proper chain ID validation
- Deposit/withdrawal tracking in DB
- Bridge manager routes across chains
- **QVM gap:** Bridge needs to interact with QVM contracts, not just lock/mint. The wQBC token on target chains should be deployable via QVM bytecode.

### 2.16 `stablecoin/engine.py` — QUSD Stablecoin
**Status:** FUNCTIONAL with issues
- Multi-collateral CDP system (USDT, USDC, DAI, QBC, ETH)
- Oracle price aggregation with median/mean/stddev
- Vault creation, collateral management, health monitoring
- **Issues:** SQL injection risk (string interpolation), vault marks "liquidated" on repay (should be "closed"), no actual liquidation logic
- **QVM gap:** QUSD should eventually be a QVM smart contract (QRC-20), not a hardcoded Python engine.

### 2.17 SQL Schemas (`sql_new/`)
**Status:** WELL DESIGNED — ahead of the Python code
- `qvm/00_contracts_core.sql` — Contract registry with bytecode storage, ERC-20/QRC-20 token standards
- `qvm/01_execution_engine.sql` — Execution tracking with function selectors, gas metering, opcode counts, event logs (topic0-3 + data)
- `qvm/02_state_storage.sql` — Key-value contract storage with state snapshots
- `qvm/03_gas_metering.sql` — Opcode cost table with 9 seed opcodes (STOP, ADD, MUL, SUB, DIV, SLOAD, SSTORE, CALL, CREATE), gas price oracle
- `agi/` — Knowledge graph, reasoning engine, training data, phi metrics for consciousness tracking
- `research/` — Hamiltonians, VQE circuits, SUSY solutions

**Key observation:** The SQL schemas define infrastructure for a proper bytecode VM (opcode costs, function selectors, event logs, storage) that the Python code doesn't use yet. The schemas are QVM-ready; the Python code is not.

---

## 3. QVM Compatibility Gap Analysis

### What QBC Has vs. What QVM Needs

| Component | QBC Current | QVM Required | Gap |
|-----------|-------------|-------------|-----|
| **Transaction Model** | UTXO only | UTXO + Account (dual) | Need account model for contract state |
| **Contract Deployment** | JSON config → DB | Bytecode → DB + state trie | Need bytecode compiler target |
| **Contract Execution** | Python method dispatch | Stack-based bytecode VM | **Complete rewrite needed** |
| **Opcode Set** | None (no VM) | 140 EVM + ~20 quantum | Need full opcode interpreter |
| **Gas Metering** | Fixed per-type fees | Per-opcode metering | DB schema exists, runtime doesn't |
| **State Storage** | JSON blobs in DB | Key-value trie (MPT) | DB schema exists, trie doesn't |
| **Event Logs** | None | LOG0-LOG4 opcodes | DB schema exists, emission doesn't |
| **State Root** | Not computed | Block header field | Critical for validation |
| **RPC** | Custom HTTP | JSON-RPC (eth_*) | Adapter layer needed |
| **ABI Encoding** | JSON params | Solidity ABI (packed) | Need ABI encoder/decoder |
| **Address Format** | SHA256[:40] | Keccak256[:40] (or keep QBC format) | Decide on compatibility |

---

## 4. EVM Opcode Coverage

### Standard EVM Opcodes Needed (140+)

The `sql_new/qvm/03_gas_metering.sql` seeds 9 opcodes. Here's the full set QVM needs:

#### Arithmetic (0x01-0x0b) — 11 opcodes
```
ADD(0x01), MUL(0x02), SUB(0x03), DIV(0x04), SDIV(0x05),
MOD(0x06), SMOD(0x07), ADDMOD(0x08), MULMOD(0x09),
EXP(0x0a), SIGNEXTEND(0x0b)
```
**QBC status:** ADD, MUL, SUB, DIV in gas table. Missing 7.

#### Comparison & Bitwise (0x10-0x1d) — 14 opcodes
```
LT(0x10), GT(0x11), SLT(0x12), SGT(0x13), EQ(0x14),
ISZERO(0x15), AND(0x16), OR(0x17), XOR(0x18), NOT(0x19),
BYTE(0x1a), SHL(0x1b), SHR(0x1c), SAR(0x1d)
```
**QBC status:** None implemented.

#### Keccak (0x20)
```
KECCAK256(0x20)
```
**QBC status:** Not implemented. QBC uses SHA256 — need Keccak for EVM compatibility.

#### Environment (0x30-0x3f) — 16 opcodes
```
ADDRESS(0x30), BALANCE(0x31), ORIGIN(0x32), CALLER(0x33),
CALLVALUE(0x34), CALLDATALOAD(0x35), CALLDATASIZE(0x36),
CALLDATACOPY(0x37), CODESIZE(0x38), CODECOPY(0x39),
GASPRICE(0x3a), EXTCODESIZE(0x3b), EXTCODECOPY(0x3c),
RETURNDATASIZE(0x3d), RETURNDATACOPY(0x3e), EXTCODEHASH(0x3f)
```
**QBC status:** None implemented.

#### Block Info (0x40-0x48) — 9 opcodes
```
BLOCKHASH(0x40), COINBASE(0x41), TIMESTAMP(0x42),
NUMBER(0x43), PREVRANDAO(0x44), GASLIMIT(0x45),
CHAINID(0x46), SELFBALANCE(0x47), BASEFEE(0x48)
```
**QBC status:** None implemented. QBC has the data (height, timestamp, difficulty) but no opcode to expose it.

#### Stack/Memory/Storage (0x50-0x5b) — 12 opcodes
```
POP(0x50), MLOAD(0x51), MSTORE(0x52), MSTORE8(0x53),
SLOAD(0x54), SSTORE(0x55), JUMP(0x56), JUMPI(0x57),
PC(0x58), MSIZE(0x59), GAS(0x5a), JUMPDEST(0x5b)
```
**QBC status:** SLOAD and SSTORE in gas table. Missing 10.

#### Push (0x5f-0x7f) — 33 opcodes
```
PUSH0(0x5f), PUSH1(0x60)...PUSH32(0x7f)
```
**QBC status:** None implemented.

#### Dup (0x80-0x8f) — 16 opcodes
```
DUP1(0x80)...DUP16(0x8f)
```
**QBC status:** None implemented.

#### Swap (0x90-0x9f) — 16 opcodes
```
SWAP1(0x90)...SWAP16(0x9f)
```
**QBC status:** None implemented.

#### Log (0xa0-0xa4) — 5 opcodes
```
LOG0(0xa0), LOG1(0xa1), LOG2(0xa2), LOG3(0xa3), LOG4(0xa4)
```
**QBC status:** DB schema supports topic0-3 + data. Runtime doesn't emit.

#### System (0xf0-0xff) — 9 opcodes
```
CREATE(0xf0), CALL(0xf1), CALLCODE(0xf2), RETURN(0xf3),
DELEGATECALL(0xf4), CREATE2(0xf5 - conflicts with quantum!),
STATICCALL(0xfa), REVERT(0xfd), INVALID(0xfe),
SELFDESTRUCT(0xff)
```
**QBC status:** CALL and CREATE in gas table. Missing 7.

#### QBC Quantum Opcodes (proposed 0xd0-0xdf range)
```
QGATE(0xd0)          — Apply quantum gate to qubit register
QMEASURE(0xd1)       — Measure qubit, collapse to classical
QENTANGLE(0xd2)      — Entangle two qubit registers
QSUPERPOSE(0xd3)     — Put qubit into superposition
QVQE(0xd4)           — Execute VQE optimization
QHAMILTONIAN(0xd5)   — Load/generate Hamiltonian
QENERGY(0xd6)        — Compute energy expectation value
QPROOF(0xd7)         — Validate quantum proof
QFIDELITY(0xd8)      — Compute state fidelity
QDILITHIUM_VERIFY(0xd9) — Verify Dilithium signature (precompile)
```
**QBC status:** The quantum engine has all the math. Need to wrap as opcodes.

**Total: ~145 EVM opcodes + ~10 quantum opcodes = ~155 opcodes for QVM**

---

## 5. Aether Tree Integration Points

### What Aether Tree Needs from QBC

Based on the DB schemas and codebase analysis:

#### 5.1 KeterNode Integration
- **What it is:** Solidity contract representing a knowledge node in the Sephirot tree
- **What QBC needs:** QVM must execute KeterNode.sol bytecode. This requires the full EVM opcode set.
- **Current gap:** QBC's contract engine can't execute Solidity. Need QVM.

#### 5.2 Proof-of-Thought (PoT) Consensus
- **What it is:** Validators submit "thought proofs" — evidence of reasoning/computation
- **What QBC needs:** A consensus hook in `consensus/engine.py` that validates PoT alongside PoSA (quantum proof)
- **Integration point:** `validate_block()` needs an optional PoT validation step
- **Current gap:** `consensus/engine.py` only validates quantum proofs. Need:
```python
# In validate_block():
if block.thought_proof:
    valid, reason = self.validate_thought_proof(block.thought_proof)
    if not valid:
        return False, f"Invalid thought proof: {reason}"
```

#### 5.3 Knowledge Graph Storage
- **What it is:** Graph of knowledge nodes + edges representing AGI reasoning
- **What QBC needs:** Already has SQL schemas (`sql_new/agi/00_knowledge_graph.sql`) with `knowledge_nodes`, `knowledge_edges`, `causal_chains` tables
- **Current gap:** No Python code reads/writes these tables. Need `KnowledgeGraphManager` class.

#### 5.4 Phi (Φ) Consciousness Metrics
- **What it is:** Integrated Information Theory metric tracking system consciousness
- **What QBC needs:** Already has SQL schema (`sql_new/agi/03_phi_metrics.sql`) and Prometheus gauges
- **Current gap:** No code computes Φ. Need `PhiCalculator` class.

#### 5.5 Reasoning Engine
- **What it is:** Deductive/inductive/abductive reasoning tracked in DB
- **What QBC needs:** Already has SQL schema (`sql_new/agi/01_reasoning_engine.sql`)
- **Current gap:** No Python implementation.

---

## 6. Critical Issues (Must Fix Before QVM)

### C1. No Bytecode VM — The Core Gap
**File:** `contracts/engine.py`, `contracts/executor.py`
**Issue:** Smart contracts are JSON configs dispatched to Python methods. This cannot execute Solidity bytecode.
**Fix:** Build or integrate a stack-based bytecode interpreter (the QVM itself).
**Impact:** Blocks QVM, blocks Aether Tree, blocks any Solidity/Vyper contracts.

### C2. No State Root in Block Model
**File:** `database/models.py:84-106`
**Issue:** `Block` dataclass has no `state_root` field. Without this, nodes cannot verify world state.
**Fix:** Add `state_root: str` to Block, compute Merkle root of all account/storage state after executing transactions.

### C3. No Account Model
**File:** `database/manager.py`
**Issue:** QBC is UTXO-only. QVM contracts need account-based state (nonce, balance, storage root, code hash).
**Fix:** Add dual model — keep UTXO for native QBC transfers, add account model for contract interactions:
```sql
CREATE TABLE accounts (
    address BYTES PRIMARY KEY,
    nonce BIGINT DEFAULT 0,
    balance DECIMAL(30, 8) DEFAULT 0,
    code_hash BYTES,
    storage_root BYTES
);
```

### C4. No JSON-RPC (eth_*) Endpoints
**File:** `network/rpc.py`
**Issue:** No Web3-compatible RPC. MetaMask, Hardhat, Ethers.js, Remix cannot connect.
**Fix:** Add JSON-RPC endpoint at `/` or separate port with full eth_* method set.

### C5. SQL Schema / Python Code Mismatch
**Files:** `sql_new/qvm/` vs `contracts/engine.py`
**Issue:** SQL schemas define proper QVM infrastructure (bytecode storage, opcode costs, function selectors, event logs, state storage) but Python code uses a completely different structure (JSON configs, no bytecode).
**Fix:** Python code must align with the SQL schemas when QVM is built.

---

## 7. High Priority Issues

### H1. Contract Engine Gas Not Deducted from Balance
**File:** `contracts/engine.py:98-106`
**Issue:** Gas cost is calculated and checked against balance, but never actually deducted.
**Fix:** After deployment, deduct gas from deployer's UTXO balance.

### H2. Stablecoin SQL Injection Risk
**File:** `stablecoin/engine.py` (multiple lines)
**Issue:** Uses string interpolation in SQL queries instead of parameterized queries.
**Fix:** Replace all `f"..."` SQL with parameterized `text()` queries.

### H3. RPC Unauthenticated
**File:** `network/rpc.py`
**Issue:** All endpoints are public with no authentication. Mining start/stop accessible to anyone.
**Fix:** Add API key or JWT authentication for write endpoints.

### H4. P2P Messages Not Signed
**File:** `network/p2p_network.py`
**Issue:** Any peer can spoof any sender_id. No message authentication.
**Fix:** Sign all P2P messages with node's Dilithium key.

### H5. Vault Repayment Bug
**File:** `stablecoin/engine.py`
**Issue:** When a vault is fully repaid, it's marked `liquidated = true` instead of having a proper `closed` status.
**Fix:** Add `status` field or use `liquidated` only for actual liquidations.

### H6. Missing Keccak256
**Issue:** EVM uses Keccak256 everywhere (address derivation, ABI encoding, storage slots, event topics). QBC uses SHA256.
**Fix:** Add Keccak256 as a precompile and use it in QVM context. Keep SHA256 for native QBC operations.

---

## 8. Medium Priority Issues

### M1. CORS Defaults to Wildcard
**File:** `network/rpc.py:51`
**Fix:** Default to `[]` (no CORS) instead of `["*"]`.

### M2. P2P Message Cache Memory Leak
**File:** `network/p2p_network.py`
**Issue:** seen_messages cache removes only 10% when full, can grow unbounded.
**Fix:** Use LRU cache with fixed size.

### M3. Rust P2P Missing Transaction Broadcast
**File:** `network/rust_p2p_client.py`
**Issue:** Can broadcast blocks but not transactions.
**Fix:** Add `broadcast_transaction()` method.

### M4. No Transaction Receipt Storage
**Issue:** QVM transactions need receipts (status, gas used, logs). Currently no receipt model.
**Fix:** Add `transaction_receipts` table.

### M5. Fallback Dilithium in Production
**File:** `quantum/crypto.py`
**Issue:** If dilithium-py not installed, falls back to insecure hash-based mock.
**Fix:** Fail hard in production if DILITHIUM_AVAILABLE is False.

### M6. Mining Engine Broadcast Race
**File:** `mining/engine.py:188-199`
**Issue:** `asyncio.run_coroutine_threadsafe()` from mining thread may fail if event loop isn't running.
**Impact:** Blocks mine but don't propagate.

---

## 9. Recommended Architecture

### Phase 1: QBC Foundation (Current + Fixes)
Fix critical issues C2-C5 while keeping current contract system working.

```
QBC Node
├── UTXO Model (native transfers) ✅ exists
├── Account Model (contracts)     ← NEW
├── State Trie (MPT)              ← NEW
├── Block.state_root              ← NEW
├── JSON-RPC adapter (eth_*)      ← NEW
└── All current functionality     ✅ exists
```

### Phase 2: QVM Integration
QVM is built as a separate crate/module, QBC calls into it.

```
QBC Node
├── Transaction Router
│   ├── UTXO tx → existing pipeline
│   └── Contract tx → QVM.execute(bytecode, calldata, state)
├── QVM Runtime (separate module)
│   ├── Stack Machine (256-bit words)
│   ├── Memory (byte-addressable)
│   ├── Storage (key-value, Keccak slots)
│   ├── EVM Opcodes (0x00-0xff)
│   └── Quantum Opcodes (0xd0-0xdf) → calls QuantumEngine
├── State Manager
│   ├── Account storage (nonce, balance, code, storage)
│   └── State root computation
└── Gas Metering
    ├── Per-opcode costs (from DB table)
    └── Block gas limit
```

### Phase 3: Aether Tree Integration
Aether Tree runs as a QVM contract + consensus extension.

```
QBC Node + QVM
├── Consensus Engine
│   ├── Proof-of-SUSY-Alignment  ✅ exists
│   └── Proof-of-Thought hook    ← NEW (validates Aether proofs)
├── QVM
│   ├── KeterNode.sol (deployed as QVM bytecode)
│   ├── ProofOfThought.sol
│   └── Sephirot tree contracts
├── Knowledge Graph Manager       ← NEW (uses existing SQL schema)
├── Phi Calculator                ← NEW (uses existing SQL schema)
└── Reasoning Engine              ← NEW (uses existing SQL schema)
```

---

## 10. Implementation Roadmap

### Step 1: QBC Hardening (Do Now)
- [ ] Fix H1: Gas deduction from balance on contract deploy/execute
- [ ] Fix H2: Parameterize all stablecoin SQL queries
- [ ] Fix H5: Vault repayment status
- [ ] Fix M5: Fail hard on missing Dilithium in production
- [ ] Add `state_root` field to Block model
- [ ] Add `accounts` table for dual UTXO/account model
- [ ] Add `transaction_receipts` table

### Step 2: JSON-RPC Adapter (Before QVM)
- [ ] Add `eth_chainId`, `net_version` (trivial)
- [ ] Add `eth_blockNumber`, `eth_getBlockByNumber/Hash`
- [ ] Add `eth_getBalance` (read from accounts table)
- [ ] Add `eth_getTransactionReceipt`
- [ ] Add `eth_call` (read-only contract execution — stub until QVM)

### Step 3: QVM Build (Separate Repo)
- [ ] Stack machine with 256-bit words
- [ ] All 140+ EVM opcodes
- [ ] Quantum opcodes (0xd0-0xdf) calling into QuantumEngine
- [ ] Gas metering per opcode
- [ ] State trie integration
- [ ] Solidity compiler target verification

### Step 4: QVM ↔ QBC Integration
- [ ] Transaction type routing (UTXO vs contract)
- [ ] `eth_sendTransaction` / `eth_sendRawTransaction`
- [ ] Block building with QVM execution
- [ ] State root computation after QVM execution
- [ ] Event log emission and storage

### Step 5: Aether Tree Deployment
- [ ] Deploy KeterNode.sol to QVM
- [ ] Deploy ProofOfThought.sol to QVM
- [ ] Add PoT consensus hook
- [ ] Build KnowledgeGraphManager
- [ ] Build PhiCalculator
- [ ] Build ReasoningEngine

---

## Summary of Findings

| Category | Count |
|----------|-------|
| **Critical (blocks QVM)** | 5 |
| **High (production risk)** | 6 |
| **Medium (should fix)** | 6 |
| **Total files reviewed** | 49 |
| **EVM opcodes needed** | ~145 |
| **Quantum opcodes proposed** | ~10 |
| **SQL schemas QVM-ready** | Yes (ahead of Python) |
| **Python code QVM-ready** | No (JSON dispatch, not bytecode VM) |
| **Aether Tree SQL schemas** | Exist but unused by Python |

**Bottom line:** QBC is a working L1 blockchain. The SQL schemas are already designed for QVM. The Python smart contract code needs to be replaced (not patched) with a proper bytecode VM when QVM is built. The Aether Tree integration is well-scaffolded in the DB but needs Python implementations. Start with QBC hardening (Step 1-2), then build QVM (Step 3), then integrate (Step 4-5).
