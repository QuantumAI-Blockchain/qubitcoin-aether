# Quantum Blockchain Developer SDK Guide

> **Complete reference for integrating with Quantum Blockchain's L1, L2 (QVM), and L3 (Aether Tree) layers.**

---

## 1. Quick Start

### Prerequisites

- Python 3.12+ (backend integration)
- Node.js 20+ / pnpm (frontend / ethers.js)
- A running Qubitcoin node (default: `http://localhost:5000`)

### Install ethers.js (recommended for JS/TS)

```bash
pnpm add ethers@6
```

### Connect to a Qubitcoin Node

```typescript
import { JsonRpcProvider } from "ethers";

const provider = new JsonRpcProvider("http://localhost:5000/jsonrpc");
const chainId = await provider.send("eth_chainId", []);
// "0xce7" (3303 mainnet) or "0xce8" (3304 testnet)
```

### Connect via Python

```python
import httpx

BASE = "http://localhost:5000"

# REST API
info = httpx.get(f"{BASE}/chain/info").json()
print(f"Block height: {info['height']}")

# JSON-RPC
resp = httpx.post(f"{BASE}/jsonrpc", json={
    "jsonrpc": "2.0",
    "method": "eth_blockNumber",
    "params": [],
    "id": 1,
}).json()
print(f"Block number: {int(resp['result'], 16)}")
```

---

## 2. Chain Configuration

| Parameter | Mainnet | Testnet |
|-----------|---------|---------|
| Chain ID | 3303 (`0xce7`) | 3304 (`0xce8`) |
| RPC URL | `https://rpc.qbc.network` | `https://testnet-rpc.qbc.network` |
| Block Time | 3.3 seconds | 3.3 seconds |
| Currency Symbol | QBC | tQBC |
| Decimals | 8 | 8 |

### Add to MetaMask Programmatically

```typescript
await window.ethereum.request({
  method: "wallet_addEthereumChain",
  params: [{
    chainId: "0xce7",
    chainName: "Qubitcoin Mainnet",
    nativeCurrency: { name: "Qubitcoin", symbol: "QBC", decimals: 8 },
    rpcUrls: ["https://rpc.qbc.network"],
    blockExplorerUrls: ["https://explorer.qbc.network"],
  }],
});
```

---

## 3. Layer 1: Blockchain API

### 3.1 REST Endpoints

#### Get Chain Info

```bash
curl http://localhost:5000/chain/info
```

```json
{
  "height": 42000,
  "difficulty": 0.85,
  "total_supply": 642750.0,
  "pending_transactions": 3,
  "peers": 12
}
```

#### Get Block by Height

```bash
curl http://localhost:5000/block/100
```

#### Get Address Balance

```bash
curl http://localhost:5000/balance/qbc1abc123...
```

#### Get UTXOs for Address

```bash
curl http://localhost:5000/utxos/qbc1abc123...
```

Returns all unspent transaction outputs. **Balance = sum of UTXO amounts.**

#### Submit Transaction (REST)

Transactions are submitted via JSON-RPC (see Section 3.2).

### 3.2 JSON-RPC (Ethereum-Compatible)

All JSON-RPC requests go to `POST /jsonrpc`.

#### Get Balance

```typescript
const balance = await provider.getBalance("0xYourAddress");
// Returns BigInt in wei-equivalent (8 decimal places)
```

#### Send Transaction

```typescript
import { Wallet } from "ethers";

const wallet = new Wallet(privateKey, provider);
const tx = await wallet.sendTransaction({
  to: "0xRecipientAddress",
  value: parseUnits("10.0", 8), // 10 QBC
});
const receipt = await tx.wait();
console.log(`TX Hash: ${receipt.hash}`);
```

#### Deploy Contract

```typescript
const tx = await provider.send("eth_sendTransaction", [{
  from: "0xYourAddress",
  data: "0x6080604052...", // Contract bytecode
  gas: "0x7a120",          // 500000 gas
}]);
```

#### Supported JSON-RPC Methods

| Method | Description |
|--------|-------------|
| `eth_chainId` | Chain ID (hex) |
| `eth_blockNumber` | Latest block number |
| `eth_getBalance` | Address balance |
| `eth_getTransactionCount` | Address nonce |
| `eth_getBlockByNumber` | Block data |
| `eth_getBlockByHash` | Block by hash |
| `eth_getTransactionByHash` | Transaction data |
| `eth_getTransactionReceipt` | Receipt with logs |
| `eth_sendRawTransaction` | Submit signed tx |
| `eth_sendTransaction` | Submit tx object |
| `eth_call` | Read-only contract call |
| `eth_estimateGas` | Estimate gas cost |
| `eth_gasPrice` | Current gas price |
| `eth_getLogs` | Query event logs |
| `eth_getCode` | Contract bytecode |
| `eth_getStorageAt` | Storage slot value |
| `eth_mining` | Mining status |
| `eth_hashrate` | Current hashrate |
| `net_version` | Network ID |
| `web3_clientVersion` | Client version |

### 3.3 Mining Control

```bash
# Start mining
curl -X POST http://localhost:5000/mining/start

# Stop mining
curl -X POST http://localhost:5000/mining/stop

# Get mining stats
curl http://localhost:5000/mining/stats
```

### 3.4 Inheritance Protocol (Dead-Man's Switch)

Qubitcoin supports on-chain inheritance planning via a dead-man's switch mechanism.
Account holders designate a beneficiary and must send periodic heartbeats. If the
inactivity threshold is exceeded, the beneficiary can claim the funds.

#### Set Beneficiary

```bash
curl -X POST http://localhost:5000/inheritance/set-beneficiary \
  -H "Content-Type: application/json" \
  -d '{
    "owner_address": "qbc1...",
    "beneficiary_address": "qbc1...",
    "inactivity_threshold_days": 365,
    "signature": "0x..."
  }'
```

```json
{
  "status": "active",
  "owner": "qbc1...",
  "beneficiary": "qbc1...",
  "threshold_days": 365,
  "last_heartbeat": 1709500000,
  "expires_at": 1741036000
}
```

#### Send Heartbeat

```bash
curl -X POST http://localhost:5000/inheritance/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"owner_address": "qbc1...", "signature": "0x..."}'
```

#### Claim Inheritance

```bash
curl -X POST http://localhost:5000/inheritance/claim \
  -H "Content-Type: application/json" \
  -d '{"beneficiary_address": "qbc1...", "owner_address": "qbc1...", "signature": "0x..."}'
```

Returns an error if the inactivity threshold has not yet been exceeded.

#### Get Inheritance Status

```bash
curl http://localhost:5000/inheritance/status/qbc1abc123...
```

```json
{
  "owner": "qbc1...",
  "beneficiary": "qbc1...",
  "threshold_days": 365,
  "last_heartbeat": 1709500000,
  "days_since_heartbeat": 42,
  "claimable": false,
  "balance_qbc": 15000.0
}
```

### 3.5 High-Security Accounts

High-security accounts allow address owners to enforce spending limits, time-locks,
and address whitelists at the protocol level. Once a security policy is set, all
outgoing transactions from the address must comply with the policy constraints.

#### Set Security Policy

```bash
curl -X POST http://localhost:5000/security/policy/set \
  -H "Content-Type: application/json" \
  -d '{
    "address": "qbc1...",
    "daily_spending_limit_qbc": 1000.0,
    "per_tx_limit_qbc": 500.0,
    "time_lock_hours": 24,
    "whitelist_addresses": ["qbc1aaa...", "qbc1bbb..."],
    "require_multi_sig": false,
    "signature": "0x..."
  }'
```

```json
{
  "address": "qbc1...",
  "policy_active": true,
  "daily_limit_qbc": 1000.0,
  "per_tx_limit_qbc": 500.0,
  "time_lock_hours": 24,
  "whitelisted": 2,
  "created_block": 42500
}
```

#### Get Security Policy

```bash
curl http://localhost:5000/security/policy/qbc1abc123...
```

```json
{
  "address": "qbc1...",
  "policy_active": true,
  "daily_limit_qbc": 1000.0,
  "per_tx_limit_qbc": 500.0,
  "time_lock_hours": 24,
  "whitelist_addresses": ["qbc1aaa...", "qbc1bbb..."],
  "spent_today_qbc": 250.0,
  "remaining_daily_qbc": 750.0,
  "require_multi_sig": false,
  "created_block": 42500
}
```

#### Remove Security Policy

```bash
curl -X DELETE http://localhost:5000/security/policy/qbc1abc123... \
  -H "Content-Type: application/json" \
  -d '{"signature": "0x..."}'
```

Removing a policy is subject to the existing time-lock (if set). The deletion
request enters a pending state and executes after the time-lock period elapses.

### 3.6 Deniable RPCs (Privacy)

Deniable RPC endpoints provide privacy-preserving query mechanisms. These endpoints
are designed to prevent timing attacks and metadata leakage by using constant-time
operations and batch queries that provide plausible deniability about which specific
data the caller is interested in.

#### Batch Balance Query

Query multiple addresses in a single constant-time request. The server processes all
addresses without short-circuiting, preventing timing-based inference about which
address the caller actually cares about.

```bash
curl -X POST http://localhost:5000/privacy/batch-balance \
  -H "Content-Type: application/json" \
  -d '{
    "addresses": ["qbc1aaa...", "qbc1bbb...", "qbc1ccc..."],
    "include_decoys": true
  }'
```

```json
{
  "balances": {
    "qbc1aaa...": 1500.0,
    "qbc1bbb...": 0.0,
    "qbc1ccc...": 42.5
  },
  "query_time_ms": 12,
  "constant_time": true
}
```

#### Bloom Filter UTXOs

Returns UTXOs as a Bloom filter rather than an explicit list. The caller can test
membership locally without revealing which specific UTXOs they own.

```bash
curl -X POST http://localhost:5000/privacy/bloom-utxos \
  -H "Content-Type: application/json" \
  -d '{
    "addresses": ["qbc1aaa...", "qbc1bbb..."],
    "false_positive_rate": 0.01
  }'
```

```json
{
  "bloom_filter": "base64-encoded-filter...",
  "filter_size_bytes": 4096,
  "hash_count": 7,
  "element_count": 42,
  "false_positive_rate": 0.01
}
```

#### Batch Block Fetch

Fetch multiple blocks in a single request, preventing observers from knowing which
specific block height the caller is interested in.

```bash
curl -X POST http://localhost:5000/privacy/batch-blocks \
  -H "Content-Type: application/json" \
  -d '{"block_heights": [1000, 1001, 1002, 1003, 1004]}'
```

#### Batch Transaction Fetch

Fetch multiple transactions by hash in a single request with constant-time processing.

```bash
curl -X POST http://localhost:5000/privacy/batch-tx \
  -H "Content-Type: application/json" \
  -d '{"tx_hashes": ["0xabc...", "0xdef...", "0x123..."]}'
```

### 3.7 BFT Finality Gadget

Qubitcoin uses a BFT finality gadget layered on top of the Proof-of-SUSY-Alignment
consensus. Validators stake QBC and vote on blocks to achieve deterministic finality.
Once a block is finalized, it cannot be reverted.

#### Get Finality Status

```bash
curl http://localhost:5000/finality/status
```

```json
{
  "finality_enabled": true,
  "validator_count": 21,
  "total_stake_qbc": 210000.0,
  "min_stake_qbc": 100.0,
  "finalized_height": 41980,
  "current_height": 42000,
  "finality_lag_blocks": 20,
  "quorum_threshold": 0.67,
  "epoch": 420
}
```

#### Submit Finality Vote

```bash
curl -X POST http://localhost:5000/finality/vote \
  -H "Content-Type: application/json" \
  -d '{
    "validator_address": "qbc1...",
    "block_height": 42000,
    "block_hash": "0xabc123...",
    "signature": "0x..."
  }'
```

```json
{
  "accepted": true,
  "block_height": 42000,
  "votes_received": 15,
  "votes_required": 14,
  "finalized": true
}
```

#### Register as Finality Validator

Minimum stake: 100 QBC. Validators earn a share of block rewards proportional to their
stake. Misbehaving validators (double-voting, inactivity) are slashed.

```bash
curl -X POST http://localhost:5000/finality/register-validator \
  -H "Content-Type: application/json" \
  -d '{
    "address": "qbc1...",
    "stake_qbc": 1000.0,
    "signature": "0x..."
  }'
```

```json
{
  "registered": true,
  "validator_address": "qbc1...",
  "stake_qbc": 1000.0,
  "validator_index": 22,
  "activation_block": 42100,
  "message": "Validator will be active after 1 epoch (~100 blocks)"
}
```

### 3.8 Stratum Mining Protocol

Qubitcoin supports the Stratum mining protocol for pool mining. The Stratum server
runs alongside the node and distributes VQE mining work to connected workers.

#### Get Stratum Server Info

```bash
curl http://localhost:5000/stratum/info
```

```json
{
  "stratum_enabled": true,
  "stratum_port": 3333,
  "protocol_version": "stratum+tcp",
  "difficulty": 1.0,
  "block_height": 42000,
  "connected_workers": 8,
  "pool_hashrate": "4.2 TH/s",
  "reward_method": "PPLNS"
}
```

#### Get Mining Pool Statistics

```bash
curl http://localhost:5000/stratum/stats
```

```json
{
  "pool_blocks_found": 156,
  "pool_efficiency": 0.98,
  "total_workers_ever": 42,
  "active_workers": 8,
  "average_share_time_ms": 3300,
  "last_block_found": 41950,
  "payout_threshold_qbc": 1.0,
  "total_paid_qbc": 2380.0
}
```

#### Get Connected Workers

```bash
curl http://localhost:5000/stratum/workers
```

```json
{
  "workers": [
    {
      "worker_id": "worker01",
      "address": "qbc1...",
      "connected_since": 1709400000,
      "shares_submitted": 1200,
      "shares_accepted": 1195,
      "shares_rejected": 5,
      "hashrate": "0.5 TH/s",
      "last_share": 1709500000
    }
  ],
  "total_workers": 8
}
```

### 3.9 WebSocket (Real-time Updates)

```typescript
const ws = new WebSocket("ws://localhost:5000/ws");
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("New event:", data);
};
```

---

## 4. Layer 2: QVM (Smart Contracts)

### 4.1 Deploy a Contract

#### Estimate Fees

```bash
curl "http://localhost:5000/qvm/deploy/estimate?bytecode_size_kb=5.0&contract_type=token"
```

```json
{
  "base_fee_qbc": 1.0,
  "per_kb_fee_qbc": 0.5,
  "total_fee_qbc": 1.5,
  "pricing_mode": "qusd_peg",
  "template_discount_applied": true
}
```

#### Deploy via JSON-RPC

```typescript
const deployTx = await provider.send("eth_sendTransaction", [{
  from: deployer,
  data: contractBytecode,
  gas: "0xF4240", // 1,000,000
}]);
```

### 4.2 Interact with Contracts

#### Read Contract Storage

```bash
curl http://localhost:5000/qvm/storage/0xContractAddr/0x0
```

#### Call Contract Method (Read-Only)

```typescript
const result = await provider.send("eth_call", [{
  to: contractAddress,
  data: encodedFunctionCall,
}, "latest"]);
```

### 4.3 Token Standards

| Standard | Description | Solidity File |
|----------|-------------|---------------|
| QBC-20 | Fungible tokens (ERC-20 compatible) | `contracts/solidity/tokens/QBC20.sol` |
| QBC-721 | NFTs (ERC-721 compatible) | `contracts/solidity/tokens/QBC721.sol` |
| QBC-1155 | Multi-tokens (ERC-1155 compatible) | `contracts/solidity/tokens/QBC1155.sol` |
| ERC-20-QC | Compliance-aware fungible token | `contracts/solidity/tokens/ERC20QC.sol` |

### 4.4 Quantum Opcodes

The QVM supports 10 quantum extension opcodes:

| Opcode | Hex | Gas | Use Case |
|--------|-----|-----|----------|
| QCREATE | 0xF0 | 5,000 + 5,000*2^n | Create quantum state |
| QMEASURE | 0xF1 | 3,000 | Measure/collapse state |
| QENTANGLE | 0xF2 | 10,000 | Entangle contract states |
| QGATE | 0xF3 | 2,000 | Apply quantum gate |
| QVERIFY | 0xF4 | 8,000 | Verify quantum proof |
| QCOMPLIANCE | 0xF5 | 15,000 | KYC/AML check |
| QRISK | 0xF6 | 5,000 | Risk score query |
| QRISK_SYSTEMIC | 0xF7 | 10,000 | Systemic risk query |
| QBRIDGE_ENTANGLE | 0xF8 | 20,000 | Cross-chain entanglement |
| QBRIDGE_VERIFY | 0xF9 | 15,000 | Bridge proof verification |

### 4.5 Compliance API

```bash
# Check address compliance
curl http://localhost:5000/qvm/compliance/check/0xAddress

# Create compliance policy
curl -X POST http://localhost:5000/qvm/compliance/policies \
  -H "Content-Type: application/json" \
  -d '{"address": "0x...", "kyc_level": 2, "daily_limit": 100000}'

# Circuit breaker status
curl http://localhost:5000/qvm/compliance/circuit-breaker
```

### 4.6 Token Tracking

```bash
# List all tokens
curl http://localhost:5000/tokens

# Token holders
curl http://localhost:5000/tokens/0xContractAddr/holders

# Token transfers
curl http://localhost:5000/tokens/0xContractAddr/transfers

# Balance of holder
curl http://localhost:5000/tokens/0xContractAddr/balance/0xHolder
```

---

## 5. Layer 3: Aether Tree (AGI)

### 5.1 Chat with Aether

#### Create Session

```bash
curl -X POST http://localhost:5000/aether/chat/session
```

```json
{
  "session_id": "sess_abc123",
  "created_at": 1708300000,
  "free_messages_remaining": 5
}
```

#### Send Message

```bash
curl -X POST http://localhost:5000/aether/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_abc123",
    "message": "What is the current state of the knowledge graph?",
    "sender_address": "qbc1..."
  }'
```

```json
{
  "response": "The knowledge graph currently contains...",
  "reasoning_trace": [
    {"step": 1, "type": "deductive", "content": "..."},
    {"step": 2, "type": "inductive", "content": "..."}
  ],
  "phi_at_response": 2.45,
  "knowledge_nodes_referenced": [12, 45, 78],
  "proof_of_thought_hash": "0xabc123...",
  "fee_charged_qbc": 0.01
}
```

#### Chat History

```bash
curl http://localhost:5000/aether/chat/history/sess_abc123
```

#### Current Chat Fee

```bash
curl http://localhost:5000/aether/chat/fee
```

### 5.2 Consciousness Metrics

```bash
# Current Phi value
curl http://localhost:5000/aether/phi

# Full consciousness status
curl http://localhost:5000/aether/consciousness

# Phi time series (for charts)
curl http://localhost:5000/aether/phi/timeseries?limit=100

# Consciousness events
curl http://localhost:5000/aether/consciousness/events?limit=20
```

### 5.3 Knowledge Graph

```bash
# Graph statistics
curl http://localhost:5000/aether/knowledge

# Get specific node
curl http://localhost:5000/aether/knowledge/node/42

# Search nodes by content
curl "http://localhost:5000/aether/knowledge/search?query=quantum&limit=10"

# Recent nodes
curl "http://localhost:5000/aether/knowledge/recent?limit=20"

# Find paths between nodes
curl http://localhost:5000/aether/knowledge/paths/10/50

# Export as JSON-LD
curl http://localhost:5000/aether/knowledge/export
```

### 5.4 Sephirot Nodes

```bash
# Status of all 10 Sephirot nodes
curl http://localhost:5000/aether/sephirot
```

Returns state (energy, phase, SUSY balance) of all Tree of Life cognitive nodes.

### 5.5 Proof-of-Thought

```bash
# PoT data for specific block
curl http://localhost:5000/aether/pot/1000

# PoT range
curl http://localhost:5000/aether/pot/range/1000/1100

# Phi progression
curl http://localhost:5000/aether/pot/phi-progression

# PoT statistics
curl http://localhost:5000/aether/pot/stats
```

### 5.6 Higgs Cognitive Field

```bash
# Field status (value, VEV, masses, excitations, potential energy)
curl http://localhost:5000/higgs/status

# All 10 node cognitive masses
curl http://localhost:5000/higgs/masses

# Single node mass + Yukawa coupling
curl http://localhost:5000/higgs/mass/Keter

# Recent excitation events (Higgs boson analogs)
curl http://localhost:5000/higgs/excitations

# Current potential energy V(phi) and field gradient
curl http://localhost:5000/higgs/potential
```

### 5.7 WebSocket Streaming

```typescript
const ws = new WebSocket("ws://localhost:5000/ws/aether");

// Subscribe to events
ws.send(JSON.stringify({
  type: "subscribe",
  events: ["phi_update", "consciousness_event", "aether_response"]
}));

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch (data.type) {
    case "phi_update":
      console.log(`Phi: ${data.value}`);
      break;
    case "consciousness_event":
      console.log(`Consciousness: ${data.event}`);
      break;
  }
};
```

---

## 6. Wrapped QBC (wQBC) -- Dual Contract Pattern

Qubitcoin has **two** separate wQBC contracts serving different purposes. Understanding the distinction is critical for integrators.

### 6.1 tokens/wQBC.sol -- Wrapped QBC on the QBC Chain

**Location:** `contracts/solidity/tokens/wQBC.sol`
**Deployed on:** QBC L1 chain (Chain ID 3303)
**Purpose:** DeFi protocol composability on the QBC chain itself.

This is analogous to WETH on Ethereum. Native QBC cannot be used directly in QVM smart contracts that expect QBC-20 tokens (e.g., DEX liquidity pools, lending protocols, NFT marketplaces). `tokens/wQBC.sol` wraps native QBC into a QBC-20 token so it can interact with the QVM contract ecosystem.

**Key features:**
- 0.1% bridge fee (10 bps) on mint/burn operations
- Replay protection via `processedTxHashes` mapping
- Reentrancy guard on all bridge operations
- Cumulative accounting: `totalLocked`, `totalMinted`, `totalBurned`, `totalFeesCollected`
- Fee recipient configurable by owner
- Bridge operator role for authorized mint/burn

**When to use:** You are building a DeFi protocol on the QBC chain and need QBC in QBC-20 form. For example, a DEX pool pairing QBC with QUSD needs wrapped QBC since native QBC is not a QBC-20 token.

```solidity
// User wraps QBC for DeFi usage on QBC chain
tokensWQBC.bridgeMint(recipient, amount, sourceTxHash, sourceChainId);
```

### 6.2 bridge/wQBC.sol -- Wrapped QBC on External Chains

**Location:** `contracts/solidity/bridge/wQBC.sol`
**Deployed on:** Ethereum, Polygon, BSC, Avalanche, Arbitrum, Optimism, Base, Solana
**Purpose:** Cross-chain representation of QBC on external blockchains.

This is the contract deployed on every external chain where QBC needs to exist. When a user bridges QBC from the QBC chain to Ethereum, the bridge operator locks QBC on L1 and mints `bridge/wQBC` tokens on Ethereum.

**Key features:**
- Simplified mint/burn interface (no fees or replay tracking in the contract itself -- the bridge operator handles those concerns on the external chain)
- Standard ERC-20 implementation compatible with Uniswap, Aave, and other DeFi protocols
- Bridge-only mint/burn access control
- Pause mechanism for emergencies

**When to use:** You are integrating QBC on an external chain. If you are building a DEX pool on Ethereum that includes QBC, you interact with this contract.

```solidity
// Bridge operator mints wQBC on Ethereum after QBC is locked on L1
bridgeWQBC.mint(recipient, amount, qbcTxId);

// User burns wQBC on Ethereum to unlock QBC on L1
bridgeWQBC.burn(user, amount, qbcDestAddress);
```

### 6.3 Comparison

| Feature | tokens/wQBC.sol | bridge/wQBC.sol |
|---------|-----------------|-----------------|
| **Deployed on** | QBC L1 chain | External chains (ETH, BNB, etc.) |
| **Purpose** | DeFi composability on QBC | Cross-chain QBC representation |
| **Bridge fee** | 0.1% (10 bps) | None (handled by bridge operator) |
| **Replay protection** | processedTxHashes | None (bridge operator tracks) |
| **Reentrancy guard** | Yes | No (simplified) |
| **Cumulative accounting** | totalLocked/Minted/Burned/Fees | totalSupply only |
| **Interface** | IQBC20 (full QBC-20) | ERC-20 standard |
| **Admin** | Owner + bridge operator | Owner + bridge |

### 6.4 Flow Diagram

```
QBC L1 Chain                              External Chain (e.g., Ethereum)
-----------------                         ----------------------------

User sends QBC
  |
  v
tokens/wQBC.sol
  (lock QBC, mint wQBC
   on QBC chain for DeFi)

        -- OR --

User sends QBC to bridge
  |
  v
Bridge locks QBC on L1
  |
  |  (bridge operator observes)
  |
  +-------------------------------------> bridge/wQBC.sol
                                            (mint wQBC on Ethereum)
                                            |
                                            v
                                          User trades wQBC on Uniswap
```

---

## 7. QUSD Stablecoin

```bash
# QBC/USD price from oracle
curl http://localhost:5000/qusd/price

# Reserve composition
curl http://localhost:5000/qusd/reserves

# Debt tracking (backing ratio)
curl http://localhost:5000/qusd/debt
```

### 7.1 QUSD Peg Keeper API

The peg keeper daemon monitors wQUSD prices across 8 chains and executes stabilization actions.

#### Get Keeper Status

```bash
curl http://localhost:5000/keeper/status
```

```json
{
  "enabled": true,
  "mode": "scan",
  "paused": false,
  "last_check_block": 42100,
  "total_actions": 0,
  "depeg_events": 0,
  "stability_fund_qbc": 1000000.0,
  "max_deviation": 0.003
}
```

#### Get Multi-Chain DEX Prices

```bash
curl http://localhost:5000/keeper/prices
```

```json
{
  "prices": {
    "ethereum": {"price": 1.002, "dex": "uniswap_v3", "liquidity": 5000000, "twap_window": 300},
    "solana": {"price": 0.998, "dex": "raydium", "liquidity": 2000000, "twap_window": 300},
    "bnb": {"price": 1.001, "dex": "pancakeswap_v3", "liquidity": 3000000, "twap_window": 300}
  },
  "weighted_average": 1.0003,
  "max_deviation": 0.003,
  "timestamp": 1709500000
}
```

#### Change Operating Mode

```bash
# Set to continuous monitoring
curl -X PUT http://localhost:5000/keeper/mode/continuous

# Available modes: off, scan, periodic, continuous, aggressive
```

```json
{
  "previous_mode": "scan",
  "new_mode": "continuous",
  "message": "Keeper mode changed to continuous"
}
```

#### Get Arbitrage Opportunities

```bash
curl http://localhost:5000/keeper/opportunities
```

```json
{
  "opportunities": [
    {
      "type": "floor_arb",
      "chain": "solana",
      "buy_price": 0.985,
      "sell_price": 1.0,
      "spread_bps": 150,
      "max_size": 100000,
      "estimated_profit_qbc": 1500.0,
      "gas_cost_estimate": 0.5,
      "bridge_fee_bps": 10,
      "net_profitable": true
    }
  ],
  "total_opportunities": 1
}
```

#### Execute Keeper Action

```bash
curl -X POST http://localhost:5000/keeper/execute \
  -H "Content-Type: application/json" \
  -d '{"action": "floor_arb", "chain": "solana", "amount": 50000}'
```

#### Pause / Resume Keeper

```bash
# Pause the keeper daemon
curl -X POST http://localhost:5000/keeper/pause

# Resume the keeper daemon
curl -X POST http://localhost:5000/keeper/resume
```

#### Get Keeper Configuration

```bash
curl http://localhost:5000/keeper/config
```

```json
{
  "enabled": true,
  "default_mode": "scan",
  "check_interval_blocks": 10,
  "max_trade_size": 1000000,
  "floor_price": 0.99,
  "ceiling_price": 1.01,
  "cooldown_blocks": 10
}
```

#### Update Keeper Configuration

```bash
curl -X PUT http://localhost:5000/keeper/config \
  -H "Content-Type: application/json" \
  -d '{"floor_price": 0.995, "ceiling_price": 1.005, "max_trade_size": 500000}'
```

#### Get Depeg Signals

```bash
curl http://localhost:5000/keeper/signals
```

#### Get Action History

```bash
curl http://localhost:5000/keeper/history
```

#### Get Arbitrage Summary

```bash
curl http://localhost:5000/keeper/arb/summary
```

```json
{
  "floor_opportunities": 1,
  "ceiling_opportunities": 0,
  "cross_chain_opportunities": 2,
  "total_estimated_profit_qbc": 3200.0,
  "chains_with_depeg": ["solana"],
  "weighted_avg_price": 1.0003
}
```

---

## 8. SUSY Scientific Database

Every mined block contributes a solved SUSY Hamiltonian to a public database.

```bash
# Query solutions
curl "http://localhost:5000/susy-database?min_energy=-5.0&max_energy=0.0&n_qubits=4"

# Export as JSON or CSV
curl "http://localhost:5000/susy-database/export?format=csv"

# Submit verification
curl -X POST http://localhost:5000/susy-database/verifications/42/verify \
  -d '{"verifier_address": "qbc1...", "verified_energy": -3.14}'

# Top verified solutions
curl http://localhost:5000/susy-database/verifications/top
```

---

## 9. Admin API (Authenticated)

Admin endpoints require the `X-Admin-Key` header matching `ADMIN_API_KEY` in `.env`.

```bash
# View economic config
curl -H "X-Admin-Key: $KEY" http://localhost:5000/admin/economics

# Update Aether fees
curl -X PUT -H "X-Admin-Key: $KEY" \
  -H "Content-Type: application/json" \
  http://localhost:5000/admin/aether/fees \
  -d '{"chat_fee_qbc": 0.02, "pricing_mode": "fixed_qbc"}'

# Update contract fees
curl -X PUT -H "X-Admin-Key: $KEY" \
  -H "Content-Type: application/json" \
  http://localhost:5000/admin/contract/fees \
  -d '{"base_fee_qbc": 2.0, "per_kb_fee_qbc": 0.2}'

# Update treasury addresses
curl -X PUT -H "X-Admin-Key: $KEY" \
  -H "Content-Type: application/json" \
  http://localhost:5000/admin/treasury \
  -d '{"aether_treasury": "qbc1...", "contract_treasury": "qbc1..."}'

# Audit log
curl -H "X-Admin-Key: $KEY" http://localhost:5000/admin/economics/history
```

---

## 10. Database & Monitoring

```bash
# Connection pool health
curl http://localhost:5000/db/pool/health

# Prometheus metrics
curl http://localhost:5000/metrics

# Node health check
curl http://localhost:5000/health
```

---

## 11. Error Handling

All REST endpoints return standard HTTP status codes:

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 404 | Resource not found |
| 429 | Rate limited (120 req/min default) |
| 500 | Internal server error |

JSON-RPC errors follow the JSON-RPC 2.0 spec:

```json
{
  "jsonrpc": "2.0",
  "error": {"code": -32601, "message": "Method not found"},
  "id": 1
}
```

---

## 12. Rate Limits

| Endpoint Type | Default Limit | Config |
|---------------|---------------|--------|
| Public REST | 120 req/min per IP | `RPC_RATE_LIMIT` |
| Admin API | 30 req/min per IP | Hardcoded |
| JSON-RPC | Same as REST | `RPC_RATE_LIMIT` |

---

*For smart contract development, see [Smart Contract Developer Guide](SMART_CONTRACTS.md).*
*For Aether Tree integration, see [Aether Integration Guide](AETHER_INTEGRATION.md).*

**Website:** [qbc.network](https://qbc.network) | **Contact:** info@qbc.network | **GitHub:** [BlockArtica/Qubitcoin](https://github.com/BlockArtica/Qubitcoin)
*For Aether Tree integration, see [Aether Integration Guide](AETHER_INTEGRATION.md).*
