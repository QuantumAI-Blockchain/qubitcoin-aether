# MASTER LAUNCH PLAN — Qubitcoin Admin Operations Guide

> **Everything you need to launch, operate, and manage Qubitcoin mainnet.**
> This is the ADMIN companion to `LAUNCHTODO.md` (technical launch steps).
> It covers wallets, external chain contracts, admin controls, and post-launch operations.

**Last Updated:** February 28, 2026

---

## TABLE OF CONTENTS

1. [Pre-Launch Checklist (One Page)](#1-pre-launch-checklist-one-page)
2. [Wallets You Need](#2-wallets-you-need)
3. [Treasury Address Setup](#3-treasury-address-setup)
4. [Smart Contract Deployment — Full Guide](#4-smart-contract-deployment--full-guide)
5. [External Chain Contracts (BNB, ETH, etc.)](#5-external-chain-contracts-bnb-eth-etc)
6. [Node Setup Requirements](#6-node-setup-requirements)
7. [Admin Controls — What You Can Change](#7-admin-controls--what-you-can-change)
8. [Admin API Reference](#8-admin-api-reference)
9. [Monitoring & Alerts](#9-monitoring--alerts)
10. [Post-Launch Operations](#10-post-launch-operations)
11. [Cost Breakdown](#11-cost-breakdown)
12. [Emergency Procedures](#12-emergency-procedures)
13. [Launch Day Timeline](#13-launch-day-timeline)

---

## 1. PRE-LAUNCH CHECKLIST (ONE PAGE)

Print this. Check each box before launch day.

### Wallets & Keys
- [ ] **Seed Node keys** generated (`python3 scripts/setup/generate_keys.py` on DO server)
- [ ] **Local Mining Node keys** generated (separate key pair on your machine)
- [ ] **Aether Treasury wallet** generated (3rd key pair — receives chat fees)
- [ ] **Contract Treasury wallet** generated (4th key pair — receives deploy fees)
- [ ] **MetaMask** installed with Qubitcoin network added (Chain ID: 3301)
- [ ] **EVM bridge operator wallet** created in MetaMask (for BNB/ETH bridge relaying)
- [ ] All `secure_key.env` files backed up securely (USB/password manager, NOT cloud)

### Infrastructure
- [ ] Digital Ocean droplet provisioned (4+ vCPU, 16GB RAM, 320GB SSD)
- [ ] Docker 24+ installed on droplet
- [ ] Firewall configured: ports 22, 80, 443, 4001, 50051
- [ ] DNS configured: `api.qbc.network` → droplet IP
- [ ] DNS configured: `qbc.network` → Vercel CNAME

### Configuration
- [ ] `.env` created from `.env.production.example` on DO server
- [ ] `AETHER_FEE_TREASURY_ADDRESS` set in `.env`
- [ ] `CONTRACT_FEE_TREASURY_ADDRESS` set in `.env`
- [ ] `ADMIN_API_KEY` set to strong random value (64+ chars)
- [ ] `GRAFANA_ADMIN_PASSWORD` changed from default
- [ ] `DEBUG=false` in `.env`

### External Chain Prep (for bridges — can be post-launch)
- [ ] Alchemy or Infura API key obtained
- [ ] BNB Smart Chain wallet funded (~0.1 BNB for deployment gas)
- [ ] Ethereum wallet funded (~0.05 ETH for deployment gas)
- [ ] Other chain wallets funded as needed (Polygon, Arbitrum, etc.)

### Verification Ready
- [ ] Know how to check: `curl https://api.qbc.network/health`
- [ ] Know how to check: `curl https://api.qbc.network/chain/info`
- [ ] Know how to check: `curl https://api.qbc.network/aether/phi`
- [ ] SSH access to droplet confirmed

---

## 2. WALLETS YOU NEED

You need **6 wallets total** for full operations. Here's exactly what each is for.

### 2.1 Wallet Inventory

| # | Wallet | Type | Purpose | When to Create |
|---|--------|------|---------|----------------|
| 1 | **Seed Node Wallet** | QBC Native (Dilithium2) | Mines genesis + receives 33M premine + all mining rewards on Node 1 | Before launch |
| 2 | **Mining Node Wallet** | QBC Native (Dilithium2) | Mining rewards on your local Node 2 | Before launch |
| 3 | **Aether Treasury** | QBC Native (Dilithium2) | Receives Aether Tree chat/query fees | Before launch |
| 4 | **Contract Treasury** | QBC Native (Dilithium2) | Receives smart contract deployment fees | Before launch |
| 5 | **MetaMask Wallet** | EVM (Ethereum-style) | Interact with QVM contracts, deploy tokens, use Bridge/DEX/Launchpad frontend | Before launch |
| 6 | **Bridge Operator Wallet** | EVM (Ethereum-style) | Sign bridge transactions on BNB/ETH/Polygon etc. Needs gas on each external chain | Before bridges |

### 2.2 How to Create Each Wallet

**Wallets 1-4 (QBC Native — Dilithium2):**

```bash
# Generate wallet 1 (Seed Node) — run on your DO server
cd /path/to/Qubitcoin
python3 scripts/setup/generate_keys.py
cp secure_key.env seed_node_keys.env.backup    # Back up immediately

# Generate wallet 2 (Mining Node) — run on your local machine
python3 scripts/setup/generate_keys.py
cp secure_key.env mining_node_keys.env.backup

# Generate wallet 3 (Aether Treasury) — run anywhere
python3 scripts/setup/generate_keys.py
# Save the ADDRESS from the output — you'll put this in .env
cp secure_key.env aether_treasury_keys.env.backup

# Generate wallet 4 (Contract Treasury) — run anywhere
python3 scripts/setup/generate_keys.py
cp secure_key.env contract_treasury_keys.env.backup
```

> **CRITICAL:** After each generation, the script overwrites `secure_key.env`.
> Back up each one BEFORE generating the next. Store backups in a password
> manager or encrypted USB — these are your private keys.

**Wallet 5 (MetaMask):**

1. Install MetaMask browser extension
2. Create or import an account
3. Add Qubitcoin network:

| Setting | Value |
|---------|-------|
| **Network Name** | Qubitcoin |
| **RPC URL** | `https://api.qbc.network` (or `http://localhost:5000` for local) |
| **Chain ID** | `3301` |
| **Currency Symbol** | `QBC` |
| **Block Explorer** | `https://qbc.network/explorer` |

Or just click "Connect Wallet" on the qbc.network frontend — it auto-prompts.

**Wallet 6 (Bridge Operator — EVM):**

Use a **separate MetaMask account** (not the same as Wallet 5):

1. In MetaMask: Create New Account → "Bridge Operator"
2. Export the private key (Account Settings → Security → Export Private Key)
3. Fund this wallet with gas tokens on each chain you want to bridge to:
   - **BNB Smart Chain:** 0.1 BNB (~$60)
   - **Ethereum:** 0.05 ETH (~$150)
   - **Polygon:** 1 MATIC (~$0.50)
   - **Arbitrum:** 0.01 ETH (~$30)
   - **Optimism:** 0.01 ETH (~$30)
   - **Avalanche:** 0.5 AVAX (~$15)
   - **Base:** 0.01 ETH (~$30)

### 2.3 Where Each Wallet's Keys Go

| Wallet | File | Env Variable |
|--------|------|-------------|
| Seed Node | `secure_key.env` on DO server | `ADDRESS`, `PUBLIC_KEY_HEX`, `PRIVATE_KEY_HEX` |
| Mining Node | `secure_key.env` on local machine | `ADDRESS`, `PUBLIC_KEY_HEX`, `PRIVATE_KEY_HEX` |
| Aether Treasury | Your backup file only | `AETHER_FEE_TREASURY_ADDRESS` (address only, no key in .env) |
| Contract Treasury | Your backup file only | `CONTRACT_FEE_TREASURY_ADDRESS` (address only, no key in .env) |
| MetaMask | MetaMask extension | Not in any .env file |
| Bridge Operator | Your backup file only | `ETH_PRIVATE_KEY` (only when bridges are active) |

---

## 3. TREASURY ADDRESS SETUP

### 3.1 What Treasury Addresses Do

Every fee collected on the network flows to a treasury address:

```
User chats with Aether Tree
  → 0.01 QBC fee deducted
  → Fee sent to AETHER_FEE_TREASURY_ADDRESS

Developer deploys a smart contract
  → 1.0+ QBC fee charged
  → Fee sent to CONTRACT_FEE_TREASURY_ADDRESS
```

### 3.2 Setting Treasury Addresses

In your `.env` file on the seed node:

```bash
# Paste the ADDRESS from your treasury wallet backups:
AETHER_FEE_TREASURY_ADDRESS=<address-from-wallet-3>
CONTRACT_FEE_TREASURY_ADDRESS=<address-from-wallet-4>
```

### 3.3 Optional: Insurance Fund

If you want a QUSD insurance fund (recommended for stablecoin operations):

```bash
QUSD_INSURANCE_FUND_ADDRESS=<separate-address>
```

### 3.4 Multi-Signature (Recommended for Production)

For maximum security, treasury wallets should eventually use multi-sig contracts
(deployed in Phase 8). During initial launch, single-key wallets are fine —
upgrade to multi-sig once the TreasuryDAO contract is deployed.

---

## 4. SMART CONTRACT DEPLOYMENT — FULL GUIDE

### 4.1 Overview

There are **50 Solidity smart contracts** organized in 9 deployment tiers.
They deploy to the **QBC QVM** (your own chain), NOT to Ethereum or BNB.

**When to deploy:** After Phase 4 (genesis verified, node running and mining).

**How long:** ~45 minutes total for all 50 contracts.

**Cost:** Only QBC gas (which you mine). No external chain costs.

### 4.2 What Gets Deployed (Summary)

| Tier | Contracts | What They Do | Depends On |
|------|-----------|-------------|------------|
| **0** | 6 | Interfaces + proxy infrastructure | Nothing |
| **1** | 5 | Token standards (QBC-20, QBC-721, QBC-1155) | Tier 0 |
| **2** | 7 | QUSD stablecoin suite | Tier 1 |
| **3** | 5 | Aether Tree core (kernel, registry, messaging) | Tier 0 |
| **4** | 4 | Proof-of-Thought (validation, tasks, rewards) | Tier 3 |
| **5** | 7 | Consciousness + Economics + Higgs (Phi, staking, DAO, Higgs mass) | Tiers 3-4 |
| **6** | 3 | Safety (Constitutional AI, emergency shutdown) | Tiers 3-5 |
| **7** | 10 | 10 Sephirot cognitive nodes (Keter → Malkuth) | Tiers 3 |
| **8** | 3 | Bridge infrastructure (vault, wQBC, wQUSD) | Tier 1 |

See `LAUNCHTODO.md` → Phase 8 for the exact deployment table with all 50 contracts.

### 4.3 Contract Deployment Script

```bash
# On the seed node (or any machine with RPC access):
python3 scripts/deploy/deploy_contracts.py \
  --rpc-url http://localhost:5000 \
  --deployer-key /path/to/secure_key.env
```

This script:
1. Reads compiled bytecode from `src/qubitcoin/contracts/solidity/`
2. Deploys each contract via JSON-RPC (`eth_sendTransaction`)
3. Waits for receipt confirmation
4. Saves addresses to `contract_registry.json`
5. Verifies each contract responds

### 4.4 After Deployment: Update Config

Once contracts are deployed, update your `.env` with the new addresses:

```bash
# Copy addresses from contract_registry.json into .env:
CONSCIOUSNESS_DASHBOARD_ADDRESS=0x...   # From contract_registry.json
PROOF_OF_THOUGHT_ADDRESS=0x...
CONSTITUTIONAL_AI_ADDRESS=0x...
TREASURY_DAO_ADDRESS=0x...
UPGRADE_GOVERNOR_ADDRESS=0x...
VALIDATOR_REGISTRY_ADDRESS=0x...
AETHER_KERNEL_ADDRESS=0x...
QUSD_TOKEN_ADDRESS=0x...
QUSD_RESERVE_ADDRESS=0x...
```

Then restart the node to enable on-chain AGI bridge:
```bash
docker compose -f docker-compose.production.yml restart qbc-node
```

### 4.5 Contract Registry

All deployed addresses are saved in `contract_registry.json` at the project root.
Current entries (50 contracts):

- **ProxyAdmin** — manages all proxy upgrades
- **AetherKernel** — main AGI orchestration
- **10 Sephirot nodes** — Keter, Chochmah, Binah, Chesed, Gevurah, Tiferet, Netzach, Hod, Yesod, Malkuth
- **QUSD suite** — QUSD token, Reserve, Oracle, DebtLedger, Stabilizer, Allocation, Governance
- **Token standards** — QBC20, QBC721, QBC1155, ERC20QC, wQBC, wQUSD
- **Bridge** — BridgeVault, wQBC (bridge version)
- **Governance** — TreasuryDAO, UpgradeGovernor, ConstitutionalAI, EmergencyShutdown
- **Proof-of-Thought** — ProofOfThought, TaskMarket, ValidatorRegistry, RewardDistributor
- **Consciousness** — ConsciousnessDashboard, PhaseSync, GlobalWorkspace
- **Higgs** — HiggsField (cognitive mass mechanism)
- **Economics** — SynapticStaking, GasOracle, VentricleRouter

---

## 5. EXTERNAL CHAIN CONTRACTS (BNB, ETH, ETC.)

### 5.1 What Are Bridge Contracts?

Bridge contracts allow users to move QBC to/from other blockchains:

```
QBC Chain                              BNB Smart Chain
┌──────────────┐                      ┌──────────────┐
│ User locks   │    Bridge Relayer    │ wQBC minted  │
│ 100 QBC in   │ ──────────────────► │ 100 wQBC to  │
│ BridgeVault  │                      │ user on BNB  │
└──────────────┘                      └──────────────┘
```

**Lock-and-Mint (QBC → external):** Lock QBC in BridgeVault → Mint wQBC on external chain
**Burn-and-Unlock (external → QBC):** Burn wQBC on external chain → Unlock QBC from BridgeVault

### 5.2 What You Deploy on Each External Chain

For **each EVM chain** (BNB, ETH, Polygon, etc.), you deploy ONE contract:

| Contract | File | What It Does |
|----------|------|-------------|
| **wQBC** | `src/qubitcoin/contracts/solidity/bridge/wQBC.sol` | ERC-20 wrapped QBC token. Mints when QBC locked. Burns to unlock. |

**That's it.** One simple ERC-20 contract per chain. The `BridgeVault` (lock/unlock vault)
lives on the QBC chain itself (deployed in Tier 8, Phase 8 of LAUNCHTODO.md).

### 5.3 BNB Smart Chain Deployment (Step-by-Step)

**Prerequisites:**
- MetaMask with BNB chain added (Chain ID: 56, RPC: https://bsc-dataseed.binance.org)
- Bridge Operator wallet funded with ~0.1 BNB for gas
- Hardhat or Foundry installed (`npm i -g hardhat` or `curl -L https://foundry.paradigm.xyz | bash`)

**Step 1: Compile the wQBC contract**

```bash
cd src/qubitcoin/contracts/solidity/bridge/

# Using Foundry (recommended):
forge build wQBC.sol

# Or using solc directly:
solc --optimize --bin --abi wQBC.sol -o build/
```

**Step 2: Deploy to BNB Smart Chain**

Using Foundry Forge:
```bash
# Set your bridge operator private key
export PRIVATE_KEY=0x<your-bridge-operator-private-key>

# Deploy to BNB mainnet
forge create src/qubitcoin/contracts/solidity/bridge/wQBC.sol:wQBC \
  --rpc-url https://bsc-dataseed.binance.org \
  --private-key $PRIVATE_KEY \
  --constructor-args <bridge-operator-address>

# Note the deployed contract address from the output
```

Or using Hardhat:
```javascript
// hardhat.config.js
module.exports = {
  networks: {
    bsc: {
      url: "https://bsc-dataseed.binance.org",
      chainId: 56,
      accounts: [process.env.PRIVATE_KEY]
    }
  },
  solidity: "0.8.24"
};

// Deploy: npx hardhat run scripts/deploy-wqbc.js --network bsc
```

**Step 3: Record the address**

Save the deployed wQBC address. You'll set it in your `.env`:
```bash
BSC_BRIDGE_ADDRESS=0x<deployed-wqbc-address-on-bnb>
BSC_RPC_URL=https://bsc-dataseed.binance.org
BSC_PRIVATE_KEY=0x<bridge-operator-key>
```

**Step 4: Verify on BscScan (optional but recommended)**

```bash
forge verify-contract <deployed-address> wQBC \
  --chain-id 56 \
  --etherscan-api-key <your-bscscan-api-key>
```

### 5.4 Deployment Per Chain

| Chain | Chain ID | RPC URL | Deploy Cost | Token Standard |
|-------|----------|---------|------------|----------------|
| **BNB Smart Chain** | 56 | `https://bsc-dataseed.binance.org` | ~$2-5 | BEP-20 |
| **Ethereum** | 1 | `https://eth-mainnet.g.alchemy.com/v2/KEY` | ~$50-200 | ERC-20 |
| **Polygon** | 137 | `https://polygon-rpc.com` | ~$0.50-2 | ERC-20 |
| **Arbitrum** | 42161 | `https://arb1.arbitrum.io/rpc` | ~$1-5 | ERC-20 |
| **Optimism** | 10 | `https://mainnet.optimism.io` | ~$1-5 | ERC-20 |
| **Avalanche** | 43114 | `https://api.avax.network/ext/bc/C/rpc` | ~$2-10 | ERC-20 |
| **Base** | 8453 | `https://mainnet.base.org` | ~$1-5 | ERC-20 |

**Total to deploy on ALL 7 EVM chains: ~$60-250 USD**

> **Recommendation:** Start with BNB + Polygon (cheapest), add Ethereum last (most expensive).

### 5.5 Solana Bridge (Future)

Solana requires a different deployment process (Anchor/Rust program, not Solidity).
This is optional and can be added post-launch.

### 5.6 Bridge Configuration in .env

After deploying wQBC to external chains, add to your seed node `.env`:

```bash
# RPC endpoints (get free API keys from Alchemy or use public RPCs)
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
BSC_RPC_URL=https://bsc-dataseed.binance.org
POLYGON_RPC_URL=https://polygon-rpc.com
ARBITRUM_RPC_URL=https://arb1.arbitrum.io/rpc
OPTIMISM_RPC_URL=https://mainnet.optimism.io
AVALANCHE_RPC_URL=https://api.avax.network/ext/bc/C/rpc
BASE_RPC_URL=https://mainnet.base.org

# Bridge operator key (same key works for all EVM chains)
ETH_PRIVATE_KEY=0x<your-bridge-operator-private-key>

# Contract addresses (from deployment output)
ETH_BRIDGE_ADDRESS=0x...
BSC_BRIDGE_ADDRESS=0x...
POLYGON_BRIDGE_ADDRESS=0x...
ARBITRUM_BRIDGE_ADDRESS=0x...
OPTIMISM_BRIDGE_ADDRESS=0x...
AVALANCHE_BRIDGE_ADDRESS=0x...
BASE_BRIDGE_ADDRESS=0x...

# Bridge economics
BRIDGE_FEE_BPS=30                    # 0.3% fee per bridge transfer
BRIDGE_VALIDATOR_REWARD_QBC=0.01     # QBC per validator signature
BRIDGE_RELAYER_REWARD_QBC=0.05       # QBC per relayed transaction
```

---

## 6. NODE SETUP REQUIREMENTS

### 6.1 How Many Nodes?

**Minimum: 1 node** (seed node on Digital Ocean).
**Recommended: 2 nodes** (seed + local mining).
**Production: 3+ nodes** (seed + 2+ miners for security).

| Node | Location | Purpose | Required? |
|------|----------|---------|-----------|
| **Node 1** | Digital Ocean | Genesis miner, public API, 24/7 seed | **YES** |
| **Node 2** | Your machine | Second miner, testing, development | Recommended |
| **Node 3+** | Any server | Additional miners, decentralization | Future |

### 6.2 Digital Ocean Droplet Specs

| Spec | Minimum | Recommended |
|------|---------|-------------|
| **Plan** | General Purpose 4vCPU/16GB ($96/mo) | General Purpose 8vCPU/32GB ($192/mo) |
| **Disk** | 160 GB SSD | 320 GB SSD |
| **OS** | Ubuntu 24.04 LTS | Ubuntu 24.04 LTS |
| **Region** | Any (nyc1, sfo3, fra1) | Close to your location |

### 6.3 What Each Node Runs

Every node runs a Docker Compose stack:

| Service | RAM | Disk | Purpose |
|---------|-----|------|---------|
| CockroachDB | 4-8 GB | 500 GB+ (grows ~50 GB/yr) | Blockchain database |
| IPFS (Kubo) | 1-2 GB | 50 GB+ | Content storage |
| Redis | 256 MB | <1 GB | Caching |
| QBC Node | 2-4 GB | <10 GB | Blockchain + mining + AGI |
| Prometheus | 1-2 GB | 50 GB (90-day retention) | Metrics |
| Grafana | 512 MB | <2 GB | Dashboards |
| Nginx + Certbot | <128 MB | <1 GB | SSL proxy (production only) |

**Total: ~10-16 GB RAM, ~650 GB disk initially**

See `LAUNCHTODO.md` → Phases 3 and 5 for exact setup commands.

### 6.4 Substrate Node (Future Migration Path)

The Substrate hybrid node is an optional Rust-native runtime that will eventually replace
the Python node. It is **not required for initial mainnet launch**.

```bash
# Build the Substrate node (native, no WASM)
cd substrate-node
SKIP_WASM_BUILD=1 cargo build --release
# Binary: target/release/qubitcoin-node
```

The Substrate node includes 6 custom pallets (qbc-utxo, qbc-consensus, qbc-dilithium,
qbc-economics, qbc-qvm-anchor, qbc-aether-anchor) and post-quantum security features
(Kyber P2P transport, Poseidon2 ZK hashing, reversibility pallet).

### 6.5 Higgs Cognitive Field Configuration

The Higgs Cognitive Field assigns mass to Sephirot nodes via a mechanism analogous to
the Standard Model Higgs boson. It activates automatically at genesis when enabled.

Add these to your `.env`:

```bash
# Higgs Cognitive Field
HIGGS_ENABLE_MASS_REBALANCING=true    # Enable Higgs field mass assignments
HIGGS_VEV=246.0                       # Vacuum expectation value
HIGGS_LAMBDA=0.129                    # Quartic coupling constant
HIGGS_MU_SQUARED=-8000.0              # Mu^2 parameter (negative for SSB)
HIGGS_YUKAWA_SCALE=1.0                # Global Yukawa coupling scale
```

When `HIGGS_ENABLE_MASS_REBALANCING=true`, the Higgs field initializes at node boot and:
- Assigns cognitive masses to all 10 Sephirot nodes via Yukawa couplings
- Expansion nodes (Chochmah, Chesed, Netzach) couple to H_u (up-type Higgs)
- Constraint nodes (Binah, Gevurah, Hod) couple to H_d (down-type Higgs)
- Masses follow a golden ratio cascade from the VEV
- SUSY mass rebalancing occurs each block when enabled

---

## 7. ADMIN CONTROLS — WHAT YOU CAN CHANGE

### 7.1 Things You CAN Change at Any Time (Hot Reload)

These can be changed via the Admin API **without restarting the node**:

| Parameter | Default | What It Controls | How to Change |
|-----------|---------|-----------------|---------------|
| Aether chat fee | 0.01 QBC | Cost per chat message | `PUT /admin/aether/fees` |
| Aether fee pricing mode | `qusd_peg` | How fees adjust to QBC price | `PUT /admin/aether/fees` |
| Aether fee min/max | 0.001 / 1.0 QBC | Floor and ceiling | `PUT /admin/aether/fees` |
| Free tier messages | 5 per session | Onboarding generosity | `PUT /admin/aether/fees` |
| Query fee multiplier | 2.0x | Deep query cost | `PUT /admin/aether/fees` |
| Contract deploy base fee | 1.0 QBC | Cost to deploy a contract | `PUT /admin/contract/fees` |
| Contract per-KB fee | 0.1 QBC | Additional per KB of code | `PUT /admin/contract/fees` |
| Template discount | 50% | Discount for pre-built templates | `PUT /admin/contract/fees` |
| Treasury addresses | (your addresses) | Where fees go | `PUT /admin/treasury` |

### 7.2 Things You CAN Change (Requires Node Restart)

Edit `.env` and restart the Docker container:

| Parameter | Default | What It Controls |
|-----------|---------|-----------------|
| `DEBUG` | false | Log verbosity |
| `AUTO_MINE` | true | Whether mining starts on boot |
| `ENABLE_RUST_P2P` | true | P2P implementation (Rust vs Python) |
| `PEER_SEEDS` | (empty) | Bootstrap peer addresses |
| `CDP_BASE_INTEREST_RATE` | 0.02 (2%) | QUSD borrowing cost |
| `CDP_LIQUIDATION_RATIO` | 1.2 (120%) | When CDPs get liquidated |
| `QUSD_SAVINGS_RATE` | 0.033 (3.3%) | QUSD savings yield |
| `BRIDGE_FEE_BPS` | 30 (0.3%) | Cross-chain transfer fee |
| `FEE_BURN_PERCENTAGE` | 0.5 (50%) | What % of L1 fees are burned |
| All `AETHER_*_INTERVAL` params | various | How often AGI processes run |
| All `SEPHIROT_*` params | various | Cognitive staking economics |
| `LLM_ENABLED` / API keys | false | External AI integration |
| `MEV_COMMIT_REVEAL_ENABLED` | true | Anti-frontrunning protection |

### 7.3 Things You CANNOT Change (Immutable / Chain-Breaking)

These are consensus-critical. Changing them **breaks the chain** (requires full reset):

| Parameter | Value | Why It's Immutable |
|-----------|-------|-------------------|
| `MAX_SUPPLY` | 3,300,000,000 QBC | Defines total economics |
| `INITIAL_REWARD` | 15.27 QBC/block | Affects all historical block validation |
| `HALVING_INTERVAL` | 15,474,020 blocks | Emission schedule |
| `PHI` | 1.618033988749895 | Golden ratio constant |
| `TARGET_BLOCK_TIME` | 3.3 seconds | Block timing |
| `GENESIS_PREMINE` | 33,000,000 QBC | Genesis block structure |
| `CHAIN_ID` | 3301 (mainnet) | Network identity |
| `INITIAL_DIFFICULTY` | 1.0 | Historical block validation |
| `VQE_REPS` | 2 | Mining proof format |

### 7.4 Admin API Authentication

All write endpoints require the `X-Admin-Key` header:

```bash
# Set your admin key in .env before launch
ADMIN_API_KEY=<64-character-random-string>

# Example: generate a strong key
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Usage:
```bash
curl -X PUT https://api.qbc.network/admin/aether/fees \
  -H "X-Admin-Key: YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"chat_fee_qbc": "0.02"}'
```

---

## 8. ADMIN API REFERENCE

### 8.1 Read-Only Endpoints (No Auth Required)

| Endpoint | What It Returns |
|----------|----------------|
| `GET /health` | Node health status (all subsystems) |
| `GET /chain/info` | Block height, supply, difficulty, peers |
| `GET /balance/<address>` | QBC balance for any address |
| `GET /mining/stats` | Mining performance metrics |
| `GET /aether/phi` | Current consciousness (Phi) value |
| `GET /aether/info` | AGI engine status |
| `GET /p2p/peers` | Connected peer list |
| `GET /qvm/info` | Smart contract engine stats |
| `GET /metrics` | All 77 Prometheus metrics |

### 8.2 Admin Endpoints (Auth Required — `X-Admin-Key`)

| Endpoint | Method | What It Does |
|----------|--------|-------------|
| `/admin/economics` | GET | Current economic configuration |
| `/admin/economics/history` | GET | Audit log of all parameter changes |
| `/admin/aether/fees` | PUT | Update Aether Tree fee parameters |
| `/admin/contract/fees` | PUT | Update contract deployment fees |
| `/admin/treasury` | PUT | Update treasury addresses |
| `/mining/start` | POST | Start mining (if stopped) |
| `/mining/stop` | POST | Stop mining |

### 8.3 Example: Change Aether Chat Fee

```bash
# View current fees
curl https://api.qbc.network/admin/economics

# Double the chat fee (from 0.01 to 0.02 QBC)
curl -X PUT https://api.qbc.network/admin/aether/fees \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_fee_qbc": "0.02",
    "free_tier_messages": 10
  }'
```

### 8.4 Example: Switch Fee Pricing Mode

```bash
# Switch from QUSD-pegged to fixed QBC (if QUSD isn't live yet)
curl -X PUT https://api.qbc.network/admin/aether/fees \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"pricing_mode": "fixed_qbc"}'
```

---

## 9. MONITORING & ALERTS

### 9.1 Accessing Monitoring

**Grafana Dashboard** (metrics visualization):
```bash
# From your local machine, SSH tunnel to the server:
ssh -L 3001:localhost:3001 root@<droplet-ip>

# Then open in browser:
open http://localhost:3001
# Login: admin / <your-GRAFANA_ADMIN_PASSWORD>
```

**Prometheus** (raw metrics):
```bash
ssh -L 9090:localhost:9090 root@<droplet-ip>
open http://localhost:9090
```

### 9.2 Key Metrics to Watch

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| `qbc_current_height` | Increasing every ~3.3s | Stalled >30s | Stalled >5 min |
| `qbc_active_peers` | >= 1 | 0 (solo mining) | N/A (expected at launch) |
| `qbc_phi_current` | Any value | N/A | N/A |
| `qbc_difficulty` | 0.5 - 10.0 | >100 | >1000 (mining very slow) |
| `qbc_total_supply` | Increasing | Stalled | Decreasing (impossible) |
| `qbc_total_contracts` | >= 0 | N/A | N/A |
| Container CPU | <80% | >80% | >95% |
| Container RAM | <80% | >80% | >90% |
| Disk usage | <70% | >70% | >90% |

### 9.3 Common Alert Scenarios

**"No new blocks in 5 minutes"**
```bash
docker logs qbc-node --tail 50         # Check for errors
curl http://localhost:5000/mining/stats # Is mining active?
curl -X POST http://localhost:5000/mining/start  # Restart mining
```

**"Disk usage >80%"**
```bash
docker exec qbc-ipfs ipfs repo gc      # Garbage collect IPFS
docker exec qbc-cockroachdb cockroach sql --insecure -e "SELECT count(*) FROM qbc.blocks;"
```

**"Node unhealthy"**
```bash
curl http://localhost:5000/health       # Check which component failed
docker compose -f docker-compose.production.yml restart qbc-node
```

---

## 10. POST-LAUNCH OPERATIONS

### 10.1 Daily Operations (Automated)

These happen automatically — just verify they're working:
- Mining continues (blocks every ~3.3 seconds)
- Aether Tree processes knowledge from each block
- Phi value updates each block
- Prometheus scrapes metrics every 15 seconds
- SSL certificate auto-renews (certbot checks every 12 hours)
- Redis cache auto-evicts (LRU policy)

### 10.2 Weekly Operations (Manual)

| Task | How | Time |
|------|-----|------|
| Check disk usage | `df -h` on droplet | 1 min |
| Review Grafana dashboards | SSH tunnel + browser | 5 min |
| Check logs for errors | `docker logs qbc-node --tail 200 \| grep ERROR` | 2 min |
| Verify chain is synced | Compare heights on both nodes | 1 min |
| Check SSL expiry | `openssl s_client -connect api.qbc.network:443` | 1 min |

### 10.3 Monthly Operations (Manual)

| Task | How | Time |
|------|-----|------|
| Database backup | `docker exec qbc-cockroachdb cockroach dump qbc > backup.sql` | 5 min |
| Rotate `ADMIN_API_KEY` | Generate new key, update .env, restart | 5 min |
| Review admin audit log | `curl /admin/economics/history` | 5 min |
| Check for repo updates | `git pull` + `docker compose up -d --build` | 15 min |

### 10.4 Adding More Nodes

When you want to add more miners to the network:

1. Give them the `Qubitcoin-node` repo (Phase 9 of LAUNCHTODO.md)
2. They generate their own keys
3. They set `PEER_SEEDS=<your-droplet-ip>:4001` in their `.env`
4. They run `docker compose up -d`
5. Their node syncs the chain and starts mining

### 10.5 Upgrading the Node

```bash
# On the droplet:
cd /path/to/Qubitcoin
git pull origin master

# Rebuild and restart (no downtime for non-consensus changes)
docker compose -f docker-compose.production.yml up -d --build

# Monitor the restart
docker compose -f docker-compose.production.yml logs -f qbc-node
```

---

## 11. COST BREAKDOWN

### 11.1 Monthly Infrastructure

| Item | Cost | Notes |
|------|------|-------|
| Digital Ocean Droplet (4vCPU/16GB) | $96/mo | Seed node |
| Domain (qbc.network) | ~$10/yr | Already owned |
| Vercel (Frontend hosting) | Free | Hobby plan covers it |
| **Monthly Total** | **~$96/mo** | |

### 11.2 One-Time Launch Costs

| Item | Cost | Notes |
|------|------|-------|
| BNB bridge deployment gas | ~$5 | 0.1 BNB |
| Polygon bridge deployment gas | ~$1 | 1 MATIC |
| Ethereum bridge deployment gas | ~$150 | 0.05 ETH (most expensive) |
| Other L2 bridges (ARB, OP, BASE, AVAX) | ~$20 total | Cheap L2 gas |
| Alchemy/Infura API key | Free | Free tier |
| **One-Time Total** | **~$180** | Without Ethereum: ~$30 |

### 11.3 Optional/Future Costs

| Item | Cost | When |
|------|------|------|
| Second droplet (additional node) | $96/mo | When traffic grows |
| Managed backup (S3/Spaces) | ~$5/mo | Data protection |
| IBM Quantum access | $0+ | If you want real quantum hardware |
| LLM API keys (OpenAI/Claude) | $10-100/mo | If enabling LLM-seeded AGI |

---

## 12. EMERGENCY PROCEDURES

### 12.1 Node Crash Recovery

```bash
# Check what's wrong
docker compose -f docker-compose.production.yml logs --tail 200

# Restart just the node (keeps database)
docker compose -f docker-compose.production.yml restart qbc-node

# If database is corrupted — FULL RESET (loses all chain data):
docker compose -f docker-compose.production.yml down -v
docker compose -f docker-compose.production.yml up -d --build
# This re-creates everything from genesis
```

### 12.2 Emergency Shutdown (Smart Contract Level)

If a critical bug is found in smart contracts:

```bash
# Call EmergencyShutdown contract
curl -X POST http://localhost:5000/contracts/execute \
  -H "Content-Type: application/json" \
  -d '{
    "contract": "<EmergencyShutdown-address>",
    "method": "shutdown",
    "args": [],
    "caller": "<your-address>"
  }'
```

### 12.3 Key Rotation

If you suspect a private key is compromised:

1. Generate new keys immediately: `python3 scripts/setup/generate_keys.py`
2. Transfer all QBC from old address to new address
3. Update `.env` with new keys
4. Update treasury addresses if affected
5. Restart node

See `docs/KEY_ROTATION.md` for detailed procedure.

### 12.4 Fork Detection

If two miners produce conflicting blocks:

```bash
# Compare block hashes at the same height
SEED=$(curl -s https://api.qbc.network/block/1000 | python3 -c "import sys,json; print(json.load(sys.stdin).get('hash','')[:16])")
LOCAL=$(curl -s http://localhost:5000/block/1000 | python3 -c "import sys,json; print(json.load(sys.stdin).get('hash','')[:16])")
echo "Seed: $SEED"
echo "Local: $LOCAL"
```

If hashes differ → fork detected. The shorter chain automatically reorgs to the longer one.
No manual intervention needed unless both chains are the same length (extremely rare).

---

## 13. LAUNCH DAY TIMELINE

### The 10-Step Launch Sequence

```
STEP 1: GENERATE KEYS                                    [5 min]
├── Generate 4 QBC wallets (seed, mining, aether treasury, contract treasury)
├── Back up all secure_key.env files
└── Note all 4 addresses

STEP 2: PROVISION INFRASTRUCTURE                          [10 min]
├── Create DO droplet (4vCPU/16GB/320GB)
├── SSH in, install Docker, configure firewall
└── Set up DNS (api.qbc.network → droplet IP)

STEP 3: CONFIGURE & LAUNCH SEED NODE                     [15 min]
├── Clone repo, copy secure_key.env, create .env
├── Set treasury addresses + admin key in .env
├── docker compose -f docker-compose.production.yml up -d --build
├── Wait for build (~5-10 min first time)
└── ⭐ GENESIS BLOCK MINED — chain is live

STEP 4: VERIFY GENESIS                                   [2 min]
├── curl /health → all green
├── curl /chain/info → height > 0
├── curl /balance/<address> → 33M+ QBC
└── curl /aether/phi → Phi measurement exists

STEP 5: SSL CERTIFICATE                                  [5 min]
├── Run certbot command
├── Restart nginx
└── Verify: curl https://api.qbc.network/health

STEP 6: LAUNCH LOCAL MINING NODE                         [5 min]
├── Generate separate keys on local machine
├── Set PEER_SEEDS=<droplet-ip>:4001 in .env
├── docker compose up -d
└── Verify peer connection and chain sync

STEP 7: DEPLOY FRONTEND                                  [5 min]
├── Push to GitHub main branch (Vercel auto-deploys)
├── Set NEXT_PUBLIC_RPC_URL in Vercel env vars
└── Verify: qbc.network loads, stats show live data

STEP 8: DEPLOY SMART CONTRACTS                           [45 min]
├── Run deploy_contracts.py (50 contracts, 9 tiers)
├── Update .env with contract addresses
├── Restart node
└── Verify: curl /qvm/info shows contracts

STEP 9: DEPLOY BRIDGE CONTRACTS (Optional)               [30 min]
├── Deploy wQBC to BNB Smart Chain
├── Deploy wQBC to other chains as desired
├── Update .env with bridge addresses + RPC URLs
└── Restart node, test bridge

STEP 10: POST-LAUNCH VERIFICATION                        [10 min]
├── Both nodes mining, heights synced
├── Frontend showing live data
├── MetaMask connects successfully
├── Aether chat responds
├── Admin API accessible
├── Grafana dashboards working
└── ⭐ LAUNCH COMPLETE
```

### Total Time: ~2 hours

**Minimum viable launch (mining only):** Steps 1-4 = ~30 minutes
**Full production launch:** Steps 1-10 = ~2 hours

---

## QUICK REFERENCE CARD

```
CHAIN ID:        3301 (mainnet) / 3302 (testnet)
BLOCK TIME:      3.3 seconds
MAX SUPPLY:      3,300,000,000 QBC
GENESIS PREMINE: 33,000,000 QBC
BLOCK REWARD:    15.27 QBC (Era 0)
HALVING:         Every 15,474,020 blocks (~1.618 years)

PUBLIC PORTS:    80 (HTTP), 443 (HTTPS), 4001 (P2P), 50051 (gRPC)
RPC URL:         https://api.qbc.network
FRONTEND:        https://qbc.network

ADMIN KEY:       X-Admin-Key header on /admin/* endpoints
TREASURY:        AETHER_FEE_TREASURY_ADDRESS + CONTRACT_FEE_TREASURY_ADDRESS

CONTRACTS:       50 Solidity contracts in 9 tiers
BRIDGES:         8 chains (ETH, BNB, MATIC, ARB, OP, AVAX, BASE, SOL)
BRIDGE FEE:      0.3% per transfer
AETHER FEE:      ~0.01 QBC per chat message
```

---

**This document + LAUNCHTODO.md = everything you need.**

- **LAUNCHTODO.md** = Technical step-by-step commands
- **MASTER_LAUNCH_PLAN.md** = Admin overview, wallets, costs, controls

**Document Version:** 1.0
**Created:** February 27, 2026
**Website:** [qbc.network](https://qbc.network) | **Contact:** info@qbc.network
