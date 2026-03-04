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
// "0xce5" (3301 mainnet) or "0xce6" (3302 testnet)
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
| Chain ID | 3301 (`0xce5`) | 3302 (`0xce6`) |
| RPC URL | `https://rpc.qbc.network` | `https://testnet-rpc.qbc.network` |
| Block Time | 3.3 seconds | 3.3 seconds |
| Currency Symbol | QBC | tQBC |
| Decimals | 8 | 8 |

### Add to MetaMask Programmatically

```typescript
await window.ethereum.request({
  method: "wallet_addEthereumChain",
  params: [{
    chainId: "0xce5",
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

### 3.4 WebSocket (Real-time Updates)

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
**Deployed on:** QBC L1 chain (Chain ID 3301)
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
