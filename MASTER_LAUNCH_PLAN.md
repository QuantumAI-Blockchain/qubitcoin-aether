# MASTER LAUNCH PLAN — Qubitcoin Admin Operations Guide

> **Everything you need to launch, operate, and manage Qubitcoin mainnet.**
> This is the ADMIN companion to `LAUNCHTODO.md` (technical launch steps).
> It covers wallets, external chain contracts, admin controls, and post-launch operations.

**Last Updated:** March 5, 2026

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
11. [Competitive Features (Opt-In)](#11-competitive-features-opt-in)
12. [QUSD Peg Keeper Operations](#12-qusd-peg-keeper-operations)
13. [Cost Breakdown](#13-cost-breakdown)
14. [Emergency Procedures](#14-emergency-procedures)
15. [Launch Day Timeline](#15-launch-day-timeline)
16. [Audit Status](#16-audit-status)

---

## 1. PRE-LAUNCH CHECKLIST (ONE PAGE)

Print this. Check each box before launch day.

### Wallets & Keys
- [ ] **Seed Node keys** generated (`python3 scripts/setup/generate_keys.py` on DO server)
- [ ] **Local Mining Node keys** generated (separate key pair on your machine)
- [ ] **Aether Treasury wallet** generated (3rd key pair — receives chat fees)
- [ ] **Contract Treasury wallet** generated (4th key pair — receives deploy fees)
- [ ] **Bridge Operator wallet** generated (5th key pair — stored in `secure_key.env`, NEVER `.env`)
- [ ] **MetaMask** installed with Qubitcoin network added (Chain ID: 3301)
- [ ] All `secure_key.env` files backed up securely (USB/password manager, NOT cloud)

### Infrastructure
- [ ] Digital Ocean droplet provisioned (4+ vCPU, 16GB RAM, 320GB SSD)
- [ ] Docker 24+ installed on droplet
- [ ] Firewall configured: ports 22, 80, 443, 4001, 50051
- [ ] DNS configured: `api.qbc.network` → droplet IP
- [ ] DNS configured: `qbc.network` → Vercel CNAME

### Configuration
- [ ] `.env` created from `.env.example` on DO server
- [ ] `secure_key.env` copied to DO server (node identity keys)
- [ ] `AETHER_FEE_TREASURY_ADDRESS` set in `.env`
- [ ] `CONTRACT_FEE_TREASURY_ADDRESS` set in `.env`
- [ ] `ADMIN_API_KEY` set to strong random value (64+ chars)
- [ ] `GRAFANA_ADMIN_PASSWORD` changed from default
- [ ] `GEVURAH_SECRET` set (for AGI safety veto auth)
- [ ] `DEBUG=false` in `.env`

### Competitive Features (all opt-in, enabled by default)
- [ ] `INHERITANCE_ENABLED=true` in `.env` (dead-man's switch for wallets)
- [ ] `SECURITY_POLICY_ENABLED=true` in `.env` (spending limits, time-locks)
- [ ] `FINALITY_ENABLED=true` in `.env` (BFT finality gadget, 100 QBC min stake)
- [ ] `DENIABLE_RPC_ENABLED=true` in `.env` (privacy-preserving batch queries)
- [ ] `STRATUM_ENABLED=false` in `.env` (enable only when ready for pool mining)
- [ ] `KEEPER_ENABLED=true` in `.env` (QUSD peg keeper daemon)
- [ ] `KEEPER_ROLE=primary` in `.env` (set to `observer` on secondary nodes)

### External Chain Prep (for bridges — can be post-launch)
- [ ] Alchemy or Infura API key obtained
- [ ] BNB Smart Chain wallet funded (~0.1 BNB for deployment gas)
- [ ] Ethereum wallet funded (~0.05 ETH for deployment gas)
- [ ] Bridge operator private key stored in `secure_key.env` on deploy machine

### Verification Ready
- [ ] Know how to check: `curl https://api.qbc.network/health`
- [ ] Know how to check: `curl https://api.qbc.network/chain/info`
- [ ] Know how to check: `curl https://api.qbc.network/aether/phi`
- [ ] Know how to check: `curl https://api.qbc.network/keeper/status`
- [ ] Know how to check: `curl https://api.qbc.network/finality/status`
- [ ] SSH access to droplet confirmed

---

## 2. WALLETS YOU NEED

You need **6 wallets total** for full operations. Here's exactly what each is for.

### 2.1 Wallet Inventory

| # | Wallet | Type | Purpose | When to Create |
|---|--------|------|---------|----------------|
| 1 | **Seed Node Wallet** | QBC Native (ML-DSA) | Mines genesis + receives 33M premine + all mining rewards on Node 1 | Before launch |
| 2 | **Mining Node Wallet** | QBC Native (ML-DSA) | Mining rewards on your local Node 2 | Before launch |
| 3 | **Aether Treasury** | QBC Native (ML-DSA) | Receives Aether Tree chat/query fees | Before launch |
| 4 | **Contract Treasury** | QBC Native (ML-DSA) | Receives smart contract deployment fees | Before launch |
| 5 | **MetaMask Wallet** | EVM (Ethereum-style) | Interact with QVM contracts, deploy tokens, use Bridge/DEX/Launchpad frontend | Before launch |
| 6 | **Bridge Operator Wallet** | EVM (Ethereum-style) | Sign bridge transactions on BNB/ETH. Needs gas on each external chain | Before bridges |

> **Note:** QBC Native wallets use CRYSTALS-Dilithium post-quantum signatures. The security
> level is configurable via `DILITHIUM_SECURITY_LEVEL` in `.env` (2=ML-DSA-44, 3=ML-DSA-65,
> 5=ML-DSA-87). Default for mainnet: **5** (256-bit classical security).

### 2.2 How to Create Each Wallet

**Wallets 1-4 (QBC Native — Dilithium):**

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
3. **Store the private key in a dedicated `secure_key.env` on the deploy machine** — NEVER in `.env`
4. Fund this wallet with gas tokens on each chain you want to bridge to:
   - **BNB Smart Chain:** 0.1 BNB (~$60)
   - **Ethereum:** 0.05 ETH (~$150)
   - **Polygon:** 1 MATIC (~$0.50)
   - **Arbitrum:** 0.01 ETH (~$30)
   - **Optimism:** 0.01 ETH (~$30)
   - **Avalanche:** 0.5 AVAX (~$15)
   - **Base:** 0.01 ETH (~$30)

### 2.3 Where Each Wallet's Keys Go

> **SECURITY RULE:** Private keys go ONLY in `secure_key.env`. NEVER in `.env`.
> The `.env` file contains non-secret configuration only (addresses, URLs, feature flags).

| Wallet | Private Key Location | What Goes in `.env` |
|--------|---------------------|---------------------|
| Seed Node | `secure_key.env` on DO server | Nothing — loaded from `secure_key.env` automatically |
| Mining Node | `secure_key.env` on local machine | Nothing — loaded from `secure_key.env` automatically |
| Aether Treasury | Backup file (cold storage) | `AETHER_FEE_TREASURY_ADDRESS=<address only>` |
| Contract Treasury | Backup file (cold storage) | `CONTRACT_FEE_TREASURY_ADDRESS=<address only>` |
| MetaMask | MetaMask extension (browser) | Not in any file |
| Bridge Operator | `secure_key.env` on deploy machine | `BRIDGE_OPERATOR_ADDRESS=<address only>` |

**Key separation diagram:**
```
secure_key.env (GITIGNORED, per-machine, contains secrets)
├── ADDRESS=<qbc-address>
├── PUBLIC_KEY_HEX=<dilithium-pubkey>
├── PRIVATE_KEY_HEX=<dilithium-privkey>
└── BRIDGE_OPERATOR_KEY=<evm-privkey>     # Only on bridge deploy machine

.env (shareable, no secrets)
├── AETHER_FEE_TREASURY_ADDRESS=<address>
├── CONTRACT_FEE_TREASURY_ADDRESS=<address>
├── BRIDGE_OPERATOR_ADDRESS=<address>      # Public address only
├── ETH_RPC_URL=https://...               # RPC URLs (not secret)
└── BSC_RPC_URL=https://...
```

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

In your `.env` file on the seed node (addresses only — no private keys):

```bash
# Paste the ADDRESS from your treasury wallet backups:
AETHER_FEE_TREASURY_ADDRESS=<address-from-wallet-3>
CONTRACT_FEE_TREASURY_ADDRESS=<address-from-wallet-4>
```

### 3.3 Optional: QUSD & AIKGS Treasury

```bash
QUSD_TREASURY_ADDRESS=<separate-address>           # QUSD operations
BRIDGE_TREASURY_ADDRESS=<separate-address>          # Bridge fee revenue
AIKGS_TREASURY_ADDRESS=<separate-address>           # Knowledge rewards
```

### 3.4 Multi-Signature (Recommended for Production)

For maximum security, treasury wallets should eventually use multi-sig contracts
(deployed in Phase 8). During initial launch, single-key wallets are fine —
upgrade to multi-sig once the TreasuryDAO contract is deployed.

---

## 4. SMART CONTRACT DEPLOYMENT — FULL GUIDE

### 4.1 Overview

There are **62 Solidity smart contracts** organized in 9 deployment tiers.
They deploy to the **QBC QVM** (your own chain), NOT to Ethereum or BNB.

**When to deploy:** After Phase 4 (genesis verified, node running and mining).

**How long:** ~45 minutes total for all 62 contracts.

**Cost:** Only QBC gas (which you mine). No external chain costs.

### 4.2 What Gets Deployed (Summary)

| Tier | Contracts | What They Do | Depends On |
|------|-----------|-------------|------------|
| **0** | 6 | Interfaces + proxy infrastructure | Nothing |
| **1** | 5 | Token standards (QBC-20, QBC-721, QBC-1155) | Tier 0 |
| **2** | 7 | QUSD stablecoin suite | Tier 1 |
| **3** | 5 | Aether Tree core (kernel, registry, messaging) | Tier 0 |
| **4** | 4 | Proof-of-Thought (validation, tasks, rewards) | Tier 3 |
| **5** | 8 | Consciousness + Economics + Higgs (Phi, staking, DAO, Higgs mass) | Tiers 3-4 |
| **6** | 3 | Safety (Constitutional AI, emergency shutdown) | Tiers 3-5 |
| **7** | 10 | 10 Sephirot cognitive nodes (Keter → Malkuth) | Tier 3 |
| **8** | 3 | Bridge infrastructure (vault, wQBC, wQUSD) | Tier 1 |
| **AIKGS** | 5 | Knowledge rewards (pool, affiliates, contributions, bounty, NFT) | Tier 0 |
| **Sephirot extras** | 6 | Additional cognitive contracts | Tier 7 |

See `LAUNCHTODO.md` → Phase 8 for the exact deployment table with all 62 contracts.

### 4.3 Contract Deployment Script

```bash
# On the seed node (or any machine with RPC access):
# Private key is loaded from secure_key.env automatically
python3 scripts/deploy/deploy_contracts.py \
  --rpc-url http://localhost:5000
```

This script:
1. Reads compiled bytecode from `src/qubitcoin/contracts/solidity/`
2. Loads deployer key from `secure_key.env` (never passed as argument)
3. Deploys each contract via JSON-RPC (`eth_sendTransaction`)
4. Waits for receipt confirmation
5. Saves addresses to `contract_registry.json`
6. Verifies each contract responds

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
QUSD_STABILIZER_ADDRESS=0x...
HIGGS_FIELD_ADDRESS=0x...
```

Then restart the node to enable on-chain AGI bridge:
```bash
docker compose -f docker-compose.production.yml restart qbc-node
```

### 4.5 Contract Registry

All deployed addresses are saved in `contract_registry.json` at the project root.
Current entries (62 contracts):

- **ProxyAdmin** — manages all proxy upgrades
- **AetherKernel** — main AGI orchestration
- **10 Sephirot nodes** — Keter, Chochmah, Binah, Chesed, Gevurah, Tiferet, Netzach, Hod, Yesod, Malkuth
- **QUSD suite** — QUSD, Reserve, Oracle, DebtLedger, Stabilizer, Allocation, Governance
- **Token standards** — QBC20, QBC721, QBC1155, ERC20QC, wQBC, wQUSD
- **Bridge** — BridgeVault, wQBC, wQUSD
- **Governance** — TreasuryDAO, UpgradeGovernor, ConstitutionalAI, EmergencyShutdown
- **Proof-of-Thought** — ProofOfThought, TaskMarket, ValidatorRegistry, RewardDistributor
- **Consciousness** — ConsciousnessDashboard, PhaseSync, GlobalWorkspace
- **Higgs** — HiggsField (cognitive mass mechanism)
- **Economics** — SynapticStaking, GasOracle, VentricleRouter
- **AIKGS** — KnowledgeRewardPool, AffiliateRegistry, ContributionLedger, KnowledgeBounty, ContributionNFT

---

## 5. EXTERNAL CHAIN CONTRACTS (BNB, ETH, ETC.)

### 5.1 What Are Bridge Contracts?

Bridge contracts allow users to move QBC and QUSD to/from other blockchains:

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

The same applies for QUSD → wQUSD bridging.

### 5.2 What You Deploy on Each External Chain

For **each EVM chain** (BNB, ETH, etc.), you deploy TWO contracts:

| Contract | File | What It Does |
|----------|------|-------------|
| **wQBC** | `contracts/solidity/bridge/wQBC.sol` | ERC-20 wrapped QBC. Mints when QBC locked. Burns to unlock. |
| **wQUSD** | `contracts/solidity/bridge/wQUSD.sol` | ERC-20 wrapped QUSD. For stablecoin liquidity on external DEXs. |

The `BridgeVault` (lock/unlock vault) lives on the QBC chain itself (deployed in Tier 8).

### 5.3 Bridge Deployment (Step-by-Step)

**Prerequisites:**
- Bridge Operator wallet funded with gas on target chain
- Bridge operator private key in `secure_key.env` (NEVER in `.env` or command line)
- Foundry installed (`curl -L https://foundry.paradigm.xyz | bash`)

**Step 1: Compile**

```bash
cd src/qubitcoin/contracts/solidity/bridge/
forge build wQBC.sol
forge build wQUSD.sol
```

**Step 2: Deploy using the deployment script**

```bash
# The script reads BRIDGE_OPERATOR_KEY from secure_key.env
# It NEVER exposes private keys on the command line or in .env
python3 scripts/deploy/deploy_bridge.py \
  --chains ethereum,bsc \
  --secure-key-file /path/to/bridge_operator_secure_key.env
```

Or deploy manually with Foundry (key loaded from secure_key.env):

```bash
# Load key from secure file — NEVER paste on command line
source /path/to/bridge_operator_secure_key.env

# Deploy to BNB mainnet
forge create src/qubitcoin/contracts/solidity/bridge/wQBC.sol:wQBC \
  --rpc-url https://bsc-dataseed.binance.org \
  --private-key $BRIDGE_OPERATOR_KEY \
  --constructor-args $(grep BRIDGE_OPERATOR_ADDRESS .env | cut -d= -f2)

# Deploy wQUSD to same chain
forge create src/qubitcoin/contracts/solidity/bridge/wQUSD.sol:wQUSD \
  --rpc-url https://bsc-dataseed.binance.org \
  --private-key $BRIDGE_OPERATOR_KEY \
  --constructor-args $(grep BRIDGE_OPERATOR_ADDRESS .env | cut -d= -f2)

# IMPORTANT: Unset the key from environment immediately after
unset BRIDGE_OPERATOR_KEY
```

**Step 3: Record the addresses (in `.env` — addresses only, no keys)**

```bash
# .env — PUBLIC addresses and RPC URLs only
BSC_BRIDGE_ADDRESS=0x<deployed-wqbc-address-on-bnb>
BSC_WQUSD_ADDRESS=0x<deployed-wqusd-address-on-bnb>
BSC_RPC_URL=https://bsc-dataseed.binance.org
```

**Step 4: Verify on block explorer (optional but recommended)**

```bash
source /path/to/bridge_operator_secure_key.env
forge verify-contract <deployed-address> wQBC \
  --chain-id 56 \
  --etherscan-api-key <your-bscscan-api-key>
unset BRIDGE_OPERATOR_KEY
```

### 5.4 Deployment Per Chain

| Chain | Chain ID | RPC URL | Deploy Cost | Status |
|-------|----------|---------|------------|--------|
| **BNB Smart Chain** | 56 | `https://bsc-dataseed.binance.org` | ~$2-5 | Priority 1 |
| **Ethereum** | 1 | `https://eth-mainnet.g.alchemy.com/v2/KEY` | ~$50-200 | Priority 2 |
| **Polygon** | 137 | `https://polygon-rpc.com` | ~$0.50-2 | Optional |
| **Arbitrum** | 42161 | `https://arb1.arbitrum.io/rpc` | ~$1-5 | Optional |
| **Optimism** | 10 | `https://mainnet.optimism.io` | ~$1-5 | Optional |
| **Avalanche** | 43114 | `https://api.avax.network/ext/bc/C/rpc` | ~$2-10 | Optional |
| **Base** | 8453 | `https://mainnet.base.org` | ~$1-5 | Optional |

> **Recommendation:** Start with BNB + ETH (largest user base), add L2s as demand grows.

### 5.5 Solana Bridge (Future)

Solana requires a different deployment process (Anchor/Rust program, not Solidity).
This is optional and can be added post-launch.

### 5.6 Bridge Configuration in .env

After deploying wQBC/wQUSD to external chains, add to your seed node `.env`:

```bash
# RPC endpoints (get free API keys from Alchemy or use public RPCs)
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
BSC_RPC_URL=https://bsc-dataseed.binance.org

# Bridge operator ADDRESS only (public, not secret)
BRIDGE_OPERATOR_ADDRESS=0x<bridge-operator-public-address>

# Contract addresses (from deployment output — public, not secret)
ETH_BRIDGE_ADDRESS=0x...
ETH_WQUSD_ADDRESS=0x...
BSC_BRIDGE_ADDRESS=0x...
BSC_WQUSD_ADDRESS=0x...

# Bridge economics
BRIDGE_FEE_BPS=30                    # 0.3% fee per bridge transfer
```

> **NEVER put `ETH_PRIVATE_KEY`, `BRIDGE_OPERATOR_KEY`, or any private key in `.env`.**
> Private keys belong ONLY in `secure_key.env` which is gitignored and per-machine.

---

## 6. NODE SETUP REQUIREMENTS

### 6.1 How Many Nodes?

**Minimum: 1 node** (seed node on Digital Ocean).
**Recommended: 2 nodes** (seed + local mining).
**Production: 3+ nodes** (seed + 2+ miners for security).

| Node | Location | Purpose | Keeper Role | Required? |
|------|----------|---------|-------------|-----------|
| **Node 1** | Digital Ocean | Genesis miner, public API, 24/7 seed | `primary` | **YES** |
| **Node 2** | Your machine | Second miner, testing, development | `observer` | Recommended |
| **Node 3+** | Any server | Additional miners, decentralization | `observer` | Future |

> **Multi-instance safety:** Only one node should run the keeper as `primary`.
> All other nodes should set `KEEPER_ROLE=observer` to prevent duplicate
> stabilization actions. The on-chain pre-flight check provides additional
> safety even if multiple nodes are accidentally set to `primary`.

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
| QBC Node | 2-4 GB | <10 GB | Blockchain + mining + AGI + keeper |
| AIKGS Sidecar | 256 MB | <1 GB | Knowledge reward engine (Rust gRPC) |
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
# Binary: target/release/qbc-node
```

The Substrate node includes **7 custom pallets** (qbc-utxo, qbc-consensus, qbc-dilithium,
qbc-economics, qbc-qvm-anchor, qbc-aether-anchor, qbc-reversibility) and post-quantum
security features (Kyber P2P transport via ML-KEM-768, Poseidon2 ZK hashing,
governed transaction reversibility).

**Test coverage:** 126 Substrate tests passing (25 Kyber, 25 Poseidon2, 10 reversibility,
13 integration, 53 pallet tests).

### 6.5 Higgs Cognitive Field Configuration

The Higgs Cognitive Field assigns mass to Sephirot nodes via a mechanism analogous to
the Standard Model Higgs boson. It activates automatically at genesis when enabled.

Add these to your `.env`:

```bash
# Higgs Cognitive Field
HIGGS_ENABLE_MASS_REBALANCING=true    # Enable Higgs field mass assignments
HIGGS_MU=88.45                        # Mass parameter
HIGGS_LAMBDA=0.129                    # Quartic coupling constant
HIGGS_TAN_BETA=1.618033988749895      # tan(beta) = phi for 2HDM
HIGGS_EXCITATION_THRESHOLD=0.10       # 10% deviation triggers excitation
HIGGS_FIELD_UPDATE_INTERVAL=1         # Blocks between field updates
```

When enabled, the Higgs field initializes at node boot and:
- Sets VEV = 174.14 (vacuum expectation value)
- Assigns cognitive masses to all 10 Sephirot nodes via Yukawa golden ratio cascade
- Expansion nodes (Chochmah, Chesed, Netzach) couple to H_u (up-type Higgs)
- Constraint nodes (Binah, Gevurah, Hod) couple to H_d (down-type Higgs)
- SUSY mass rebalancing occurs each block

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
| Keeper mode | scan | Peg keeper operating mode | `PUT /keeper/mode/{mode}` |

### 7.2 Things You CAN Change (Requires Node Restart)

Edit `.env` and restart the Docker container:

| Parameter | Default | What It Controls |
|-----------|---------|-----------------|
| `DEBUG` | false | Log verbosity |
| `AUTO_MINE` | true | Whether mining starts on boot |
| `ENABLE_RUST_P2P` | true | P2P implementation (Rust vs Python) |
| `PEER_SEEDS` | (empty) | Bootstrap peer addresses |
| `BRIDGE_FEE_BPS` | 30 (0.3%) | Cross-chain transfer fee |
| `FEE_BURN_PERCENTAGE` | 0.5 (50%) | What % of L1 fees are burned |
| `LLM_ENABLED` / API keys | false | External AI integration |
| `MEV_COMMIT_REVEAL_ENABLED` | true | Anti-frontrunning protection |
| `KEEPER_ROLE` | primary | Keeper execution role (primary/observer) |
| `KEEPER_DEFAULT_MODE` | scan | Keeper starting mode |
| `INHERITANCE_ENABLED` | true | Dead-man's switch feature |
| `SECURITY_POLICY_ENABLED` | true | High-security account feature |
| `FINALITY_ENABLED` | true | BFT finality gadget |
| `STRATUM_ENABLED` | false | Pool mining server |
| `DILITHIUM_SECURITY_LEVEL` | 5 | Post-quantum signature strength |

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
| `GET /keeper/status` | Peg keeper status, mode, role, prices |
| `GET /keeper/opportunities` | Current arb opportunities |
| `GET /finality/status` | BFT finality gadget status |
| `GET /inheritance/status/{addr}` | Inheritance plan status |
| `GET /security/policy/{addr}` | Security policy for address |
| `GET /higgs/status` | Higgs field state, VEV, symmetry |
| `GET /higgs/masses` | All node cognitive masses |
| `GET /metrics` | All 135+ Prometheus metrics |

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
| `/keeper/mode/{mode}` | PUT | Change keeper operating mode |

### 8.3 Competitive Feature Endpoints

| Endpoint | Method | What It Does |
|----------|--------|-------------|
| `/inheritance/set-beneficiary` | POST | Set dead-man's switch beneficiary |
| `/inheritance/heartbeat` | POST | Reset inactivity timer |
| `/inheritance/claim` | POST | Beneficiary claims after timeout |
| `/security/policy/set` | POST | Set spending limits, time-locks |
| `/finality/register-validator` | POST | Register as finality validator |
| `/finality/vote` | POST | Submit finality vote |
| `/privacy/batch-balance` | POST | Privacy-preserving batch balance query |
| `/privacy/bloom-utxos` | POST | UTXO Bloom filter query |
| `/stratum/info` | GET | Stratum mining server info |

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

### 9.2 Key Metrics to Watch (135+ total)

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| `qbc_current_height` | Increasing every ~3.3s | Stalled >30s | Stalled >5 min |
| `qbc_active_peers` | >= 1 | 0 (solo mining) | N/A (expected at launch) |
| `qbc_phi_current` | Any value | N/A | N/A |
| `qbc_difficulty` | 0.5 - 10.0 | >100 | >1000 (mining very slow) |
| `qbc_total_supply` | Increasing | Stalled | Decreasing (impossible) |
| `qusd_keeper_mode` | 1 (scan) | 0 (off) | 4 (aggressive = depeg crisis) |
| `qusd_keeper_max_deviation` | < 0.01 | 0.01-0.05 | > 0.05 (5% depeg) |
| `higgs_field_value` | ~174.14 (near VEV) | >10% deviation | Excitation cascade |
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

**"QUSD depeg detected"**
```bash
curl http://localhost:5000/keeper/status    # Check prices and signals
curl http://localhost:5000/keeper/signals   # Recent depeg signals
# If needed, escalate keeper mode:
curl -X PUT http://localhost:5000/keeper/mode/continuous \
  -H "X-Admin-Key: $ADMIN_API_KEY"
```

---

## 10. POST-LAUNCH OPERATIONS

### 10.1 Daily Operations (Automated)

These happen automatically — just verify they're working:
- Mining continues (blocks every ~3.3 seconds)
- Aether Tree processes knowledge from each block
- Phi value updates each block
- Higgs field rebalances cognitive masses each block
- QUSD Keeper scans prices each block (scan mode)
- BFT Finality gadget processes votes
- Inheritance heartbeat checks run per block
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
| Check keeper status | `curl /keeper/status` — verify mode and prices | 1 min |

### 10.3 Monthly Operations (Manual)

| Task | How | Time |
|------|-----|------|
| Database backup | `docker exec qbc-cockroachdb cockroach dump qbc > backup.sql` | 5 min |
| Rotate `ADMIN_API_KEY` | Generate new key, update .env, restart | 5 min |
| Review admin audit log | `curl /admin/economics/history` | 5 min |
| Check for repo updates | `git pull` + `docker compose up -d --build` | 15 min |
| Review keeper action history | `curl /keeper/history` — check for anomalies | 5 min |

### 10.4 Adding More Nodes

When you want to add more miners to the network:

1. Give them the `Qubitcoin-node` repo (Phase 9 of LAUNCHTODO.md)
2. They generate their own keys
3. They set `PEER_SEEDS=<your-droplet-ip>:4001` in their `.env`
4. **They set `KEEPER_ROLE=observer`** in their `.env` (only one primary keeper)
5. They run `docker compose up -d`
6. Their node syncs the chain and starts mining

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

## 11. COMPETITIVE FEATURES (OPT-IN)

All competitive features are **opt-in** and **backward-compatible**. They are enabled
by default in `.env.example` but can be individually disabled.

### 11.1 Feature Summary

| Feature | Config Flag | Default | What It Does |
|---------|------------|---------|-------------|
| **Inheritance Protocol** | `INHERITANCE_ENABLED` | true | Dead-man's switch — auto-transfer to beneficiary after inactivity |
| **High-Security Accounts** | `SECURITY_POLICY_ENABLED` | true | Per-address spending limits, time-locks, whitelists |
| **BFT Finality Gadget** | `FINALITY_ENABLED` | true | Stake-weighted finality votes, reorg protection |
| **Deniable RPCs** | `DENIABLE_RPC_ENABLED` | true | Privacy-preserving batch queries with Bloom filters |
| **Stratum Mining Server** | `STRATUM_ENABLED` | false | Pool mining support (Rust binary, port 3333) |
| **QUSD Peg Keeper** | `KEEPER_ENABLED` | true | Automated stablecoin peg defense (see Section 12) |

### 11.2 Inheritance Protocol

Allows users to set a beneficiary who inherits their QBC after a configurable inactivity period.

```bash
# User sets beneficiary
curl -X POST http://localhost:5000/inheritance/set-beneficiary \
  -H "Content-Type: application/json" \
  -d '{"owner": "<address>", "beneficiary": "<heir-address>", "inactivity_blocks": 2618200}'

# User sends heartbeat (resets timer)
curl -X POST http://localhost:5000/inheritance/heartbeat \
  -d '{"address": "<address>"}'

# After inactivity period expires, beneficiary claims
curl -X POST http://localhost:5000/inheritance/claim \
  -d '{"beneficiary": "<heir-address>", "owner": "<original-address>"}'
```

### 11.3 High-Security Accounts

Per-address security policies with spending limits, time-locks, and address whitelists.

```bash
# Set a daily spending limit + time-lock
curl -X POST http://localhost:5000/security/policy/set \
  -H "Content-Type: application/json" \
  -d '{
    "address": "<address>",
    "daily_limit_qbc": 1000,
    "time_lock_blocks": 7854,
    "whitelist": ["<trusted-address-1>", "<trusted-address-2>"]
  }'
```

### 11.4 BFT Finality Gadget

Stake-weighted finality votes that provide reorg protection after 2/3 validator agreement.

```bash
# Register as a finality validator (requires 100 QBC min stake)
curl -X POST http://localhost:5000/finality/register-validator \
  -d '{"address": "<address>", "stake": 100}'

# Check finality status
curl http://localhost:5000/finality/status
```

---

## 12. QUSD PEG KEEPER OPERATIONS

### 12.1 Overview

The QUSD Peg Keeper is an automated daemon that monitors wQUSD prices across 8 chains
and executes stabilization actions when the peg deviates beyond thresholds.

**Already built and wired into the node** — 1,804 LOC across 3 files:
- `stablecoin/keeper.py` — Main daemon (657 LOC, 5 operating modes)
- `stablecoin/arbitrage.py` — Cross-chain arb calculator (442 LOC)
- `stablecoin/dex_price.py` — Multi-chain DEX TWAP reader (705 LOC)

### 12.2 Operating Modes

| Mode | Behavior | When to Use |
|------|----------|-------------|
| `off` | Daemon stopped | Maintenance |
| `scan` | Monitor + log only, never execute | **Default.** Observation |
| `periodic` | Check every N blocks, act if profitable | Conservative |
| `continuous` | Check every block, act immediately | Active defense |
| `aggressive` | Max trade sizes, all arb pursued | Emergency depeg |

### 12.3 Multi-Instance Safety

When running multiple nodes:

| Feature | Description |
|---------|-------------|
| **Option A: On-chain pre-flight** | Before executing, reads `lastRebalanceBlock` from QUSDStabilizer contract to prevent duplicate interventions |
| **Option B: Role-based gating** | `KEEPER_ROLE=primary` executes; `KEEPER_ROLE=observer` only scans. Observer nodes are forced to scan mode |

```bash
# Seed node (primary keeper)
KEEPER_ROLE=primary
KEEPER_DEFAULT_MODE=scan

# All other nodes (observers)
KEEPER_ROLE=observer
KEEPER_DEFAULT_MODE=scan
```

### 12.4 Configuration

```bash
# .env
KEEPER_ENABLED=true
KEEPER_DEFAULT_MODE=scan
KEEPER_CHECK_INTERVAL=10
KEEPER_MAX_TRADE_SIZE=1000000
KEEPER_FLOOR_PRICE=0.99
KEEPER_CEILING_PRICE=1.01
KEEPER_COOLDOWN_BLOCKS=10
KEEPER_ROLE=primary
QUSD_STABILIZER_ADDRESS=0x...      # Set after contract deployment
```

### 12.5 Keeper Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/keeper/status` | GET | Full status (mode, role, prices, signals) |
| `/keeper/mode` | GET | Current mode |
| `/keeper/mode/{mode}` | PUT | Change mode (requires admin key) |
| `/keeper/history` | GET | Action history |
| `/keeper/opportunities` | GET | Current arb opportunities |
| `/keeper/signals` | GET | Recent depeg signals |
| `/keeper/execute` | POST | Manual trigger (requires admin key) |
| `/keeper/pause` | POST | Pause execution |
| `/keeper/resume` | POST | Resume execution |
| `/keeper/prices` | GET | Multi-chain DEX prices |

---

## 13. COST BREAKDOWN

### 13.1 Monthly Infrastructure

| Item | Cost | Notes |
|------|------|-------|
| Digital Ocean Droplet (4vCPU/16GB) | $96/mo | Seed node |
| Domain (qbc.network) | ~$10/yr | Already owned |
| Vercel (Frontend hosting) | Free | Hobby plan covers it |
| **Monthly Total** | **~$96/mo** | |

### 13.2 One-Time Launch Costs

| Item | Cost | Notes |
|------|------|-------|
| BNB bridge deployment gas (wQBC + wQUSD) | ~$10 | 0.1 BNB |
| Ethereum bridge deployment gas | ~$150 | 0.05 ETH (most expensive) |
| Other L2 bridges (ARB, OP, BASE, AVAX) | ~$20 total | Cheap L2 gas |
| Alchemy/Infura API key | Free | Free tier |
| **One-Time Total** | **~$180** | Without Ethereum: ~$30 |

### 13.3 Optional/Future Costs

| Item | Cost | When |
|------|------|------|
| Second droplet (additional node) | $96/mo | When traffic grows |
| Managed backup (S3/Spaces) | ~$5/mo | Data protection |
| IBM Quantum access | $0+ | If you want real quantum hardware |
| LLM API keys (OpenAI/Claude) | $10-100/mo | If enabling LLM-seeded AGI |

---

## 14. EMERGENCY PROCEDURES

### 14.1 Node Crash Recovery

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

### 14.2 Emergency Shutdown (Smart Contract Level)

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

### 14.3 Key Rotation

If you suspect a private key is compromised:

1. Generate new keys immediately: `python3 scripts/setup/generate_keys.py`
2. Transfer all QBC from old address to new address
3. Replace `secure_key.env` with new keys (NEVER put keys in `.env`)
4. Update treasury addresses in `.env` if affected
5. Restart node

### 14.4 QUSD Depeg Emergency

```bash
# 1. Check current status
curl http://localhost:5000/keeper/status

# 2. Escalate to aggressive mode
curl -X PUT http://localhost:5000/keeper/mode/aggressive \
  -H "X-Admin-Key: $ADMIN_API_KEY"

# 3. Manual intervention if needed
curl -X POST http://localhost:5000/keeper/execute \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action_type": "trigger_rebalance", "trade_size": "500000", "block_height": 0}'

# 4. After peg restored, return to scan mode
curl -X PUT http://localhost:5000/keeper/mode/scan \
  -H "X-Admin-Key: $ADMIN_API_KEY"
```

### 14.5 Fork Detection

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

## 15. LAUNCH DAY TIMELINE

### The 11-Step Launch Sequence

```
STEP 1: GENERATE KEYS                                    [5 min]
├── Generate 4 QBC wallets (seed, mining, aether treasury, contract treasury)
├── Generate 1 bridge operator wallet (MetaMask + export key to secure_key.env)
├── Back up all secure_key.env files
└── Note all addresses

STEP 2: PROVISION INFRASTRUCTURE                          [10 min]
├── Create DO droplet (4vCPU/16GB/320GB)
├── SSH in, install Docker, configure firewall
└── Set up DNS (api.qbc.network → droplet IP)

STEP 3: CONFIGURE & LAUNCH SEED NODE                     [15 min]
├── Clone repo, copy secure_key.env, create .env from .env.example
├── Set treasury addresses + admin key + GEVURAH_SECRET in .env
├── Set KEEPER_ROLE=primary in .env
├── docker compose -f docker-compose.production.yml up -d --build
├── Wait for build (~5-10 min first time)
└── GENESIS BLOCK MINED — chain is live

STEP 4: VERIFY GENESIS                                   [2 min]
├── curl /health → all green
├── curl /chain/info → height > 0
├── curl /balance/<address> → 33M+ QBC
├── curl /aether/phi → Phi measurement exists
├── curl /keeper/status → mode=scan, role=primary
└── curl /finality/status → enabled

STEP 5: SSL CERTIFICATE                                  [5 min]
├── Run certbot command
├── Restart nginx
└── Verify: curl https://api.qbc.network/health

STEP 6: LAUNCH LOCAL MINING NODE                         [5 min]
├── Generate separate keys on local machine
├── Set PEER_SEEDS=<droplet-ip>:4001 in .env
├── Set KEEPER_ROLE=observer in .env
├── docker compose up -d
└── Verify peer connection and chain sync

STEP 7: DEPLOY FRONTEND                                  [5 min]
├── Push to GitHub main branch (Vercel auto-deploys)
├── Set NEXT_PUBLIC_RPC_URL in Vercel env vars
└── Verify: qbc.network loads, stats show live data

STEP 8: DEPLOY SMART CONTRACTS                           [45 min]
├── Run deploy_contracts.py (62 contracts, 9 tiers)
├── Update .env with contract addresses (incl. QUSD_STABILIZER_ADDRESS)
├── Restart node
└── Verify: curl /qvm/info shows contracts

STEP 9: DEPLOY BRIDGE CONTRACTS                          [30 min]
├── Deploy wQBC + wQUSD to BNB Smart Chain
├── Deploy wQBC + wQUSD to Ethereum
├── Update .env with bridge addresses + RPC URLs (addresses only!)
├── Bridge operator key stays in secure_key.env
└── Restart node, test bridge

STEP 10: CREATE LIQUIDITY POOLS (Optional)               [30 min]
├── Create wQUSD/USDC pool on Uniswap V3 (ETH)
├── Create wQBC/WETH pool on Uniswap V3 (ETH)
├── Create wQUSD/BUSD pool on PancakeSwap V3 (BNB)
├── Create wQBC/WBNB pool on PancakeSwap V3 (BNB)
└── Set initial prices and seed liquidity

STEP 11: POST-LAUNCH VERIFICATION                        [10 min]
├── Both nodes mining, heights synced
├── Frontend showing live data
├── MetaMask connects successfully
├── Aether chat responds
├── Admin API accessible
├── Keeper monitoring prices
├── Finality gadget processing votes
├── Grafana dashboards working
└── LAUNCH COMPLETE
```

### Total Time: ~2.5 hours

**Minimum viable launch (mining only):** Steps 1-4 = ~30 minutes
**Full production launch:** Steps 1-11 = ~2.5 hours

---

## 16. AUDIT STATUS

### Latest Audit: v9.0 Military-Grade Live Testing Protocol

**3 consecutive 100/100 scores achieved — Launch Clearance: GRANTED**

| Component | Score | Tests |
|-----------|-------|-------|
| Python Blockchain Core | 100/100 | 4,317 passed, 0 failed |
| Rust Security Core (PyO3) | 100/100 | 17 passed |
| Rust Stratum Server | 100/100 | 15 passed |
| Substrate Hybrid Node | 100/100 | 126 passed |
| Frontend (qbc.network) | 100/100 | 25 routes, 0 TS errors |
| Smart Contracts (62 .sol) | 100/100 | All compile |
| Competitive Features | 100/100 | 150 tests |
| Live Endpoints | 100/100 | 57/57 REST + 13/13 JSON-RPC |

**Audit details:** See `REVIEW.md` for full results including live genesis verification,
endpoint bombardment, and 3-pass run history.

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

CONTRACTS:       62 Solidity contracts in 9 tiers
BRIDGES:         8 chains (ETH, BNB, MATIC, ARB, OP, AVAX, BASE, SOL)
BRIDGE FEE:      0.3% per transfer
AETHER FEE:      ~0.01 QBC per chat message

KEEPER:          QUSD peg defense (5 modes: off/scan/periodic/continuous/aggressive)
KEEPER ROLE:     primary (1 node) / observer (all others)

METRICS:         135+ Prometheus metrics across 15 categories
TESTS:           4,317 Python + 17 security-core + 15 stratum + 126 Substrate

KEYS:            ONLY in secure_key.env (NEVER in .env)
```

---

**This document + LAUNCHTODO.md = everything you need.**

- **LAUNCHTODO.md** = Technical step-by-step commands
- **MASTER_LAUNCH_PLAN.md** = Admin overview, wallets, costs, controls

**Document Version:** 2.0
**Created:** February 27, 2026 | **Updated:** March 5, 2026
**Website:** [qbc.network](https://qbc.network) | **Contact:** info@qbc.network
