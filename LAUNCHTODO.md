# LAUNCHTODO.md — Qubitcoin Genesis Launch Checklist

> **Master document for bringing Qubitcoin live from zero to mining.**
> Work through each phase in order. Check boxes as you go.

**Website:** qbc.network | **Contact:** info@qbc.network | **Chain ID:** 3301

---

## TABLE OF CONTENTS

1. [Quick Answers](#1-quick-answers)
2. [What Happens Automatically](#2-what-happens-automatically)
3. [Phase 1: Prerequisites](#3-phase-1-prerequisites)
4. [Phase 2: Generate Node Identity](#4-phase-2-generate-node-identity)
5. [Phase 3: Start Backend (Docker)](#5-phase-3-start-backend-docker)
6. [Phase 4: Verify Genesis](#6-phase-4-verify-genesis)
7. [Phase 5: Start Frontend](#7-phase-5-start-frontend)
8. [Phase 6: Deploy Smart Contracts](#8-phase-6-deploy-smart-contracts)
9. [Phase 7: Bridge Contracts (Multi-Chain)](#9-phase-7-bridge-contracts-multi-chain)
9.5. [Phase 4.5: Create Private Node Runner Repo](#95-phase-45-create-private-node-runner-repo)
10. [Phase 8: Production Deployment (Digital Ocean)](#10-phase-8-production-deployment)
11. [Port Reference](#11-port-reference)
12. [Troubleshooting](#12-troubleshooting)
13. [Architecture Diagram](#13-architecture-diagram)

---

## 1. QUICK ANSWERS

### Is SSL required for local Docker?
**NO.** SSL is not needed for local development or initial testing. All Docker services
communicate over an internal bridge network (`qbc-net`). The RPC API listens on
`http://localhost:5000` (plain HTTP). The frontend connects to `http://localhost:5000`.

SSL is only needed for **production** (public internet). It is already pre-configured:
- Nginx reverse proxy with TLS 1.2/1.3 (in `config/nginx/nginx.conf`)
- Certbot auto-renewal (Let's Encrypt)
- Both services are in the Docker Compose file under the `production` profile
- To enable: `docker compose --profile production up -d`

### Will Aether Tree launch at genesis?
**YES — automatically.** Here is what happens on first boot:

1. Node starts → SQLAlchemy auto-creates all 40+ database tables
2. Mining engine starts → mines block 0 (genesis) with 15.27 QBC reward
3. After block 0 exists → `AetherGenesis.initialize_genesis()` runs automatically:
   - Creates **4 genesis knowledge nodes** (root KeterNode + 3 axiom nodes)
   - Records **first Phi measurement** (Φ = 0.0 baseline)
   - Logs **"system_birth" consciousness event** at block 0
4. From block 1 onward, every block updates the Aether Tree knowledge graph

**The Aether Tree Python engine (34 modules: knowledge graph, 6-phase reasoning, Phi v3 with MIP,
3-tier memory, neural reasoner, on-chain AGI bridge, proof-of-thought) is fully integrated
into the node and tracks consciousness from genesis. No manual steps needed.**

### What about Aether Tree Solidity contracts?
The 49 Solidity contracts (AetherKernel, 10 Sephirot nodes, ProofOfThought, QUSD suite,
bridge infrastructure, token standards, etc.) are **NOT auto-deployed at genesis**. They
are deployed manually via RPC after the node is running. See
[Phase 6](#8-phase-6-deploy-smart-contracts).

### What about bridge contracts?
Bridge contracts (wQBC, wQUSD) must be deployed on each target chain (ETH, SOL, etc.)
**after** the QBC chain is running. These require funded wallets on each target chain.
See [Phase 7](#9-phase-7-bridge-contracts-multi-chain).

### What do I need to get mining ASAP?
**Phase 1 + Phase 2 + Phase 3 = mining.** That's it. Three phases, ~10 minutes.

---

## 2. WHAT HAPPENS AUTOMATICALLY

When you run `docker compose up -d`, the following happens without any manual intervention:

| Step | Component | What Happens | Time |
|------|-----------|-------------|------|
| 1 | CockroachDB | Starts single-node database | ~30s |
| 2 | IPFS (Kubo) | Starts content storage daemon | ~20s |
| 3 | Redis | Starts cache/rate-limiter | ~5s |
| 4 | QBC Node | Starts Python node process | ~15s |
| 4a | DatabaseManager | Auto-creates ALL 40+ tables via SQLAlchemy | ~3s |
| 4b | QuantumEngine | Initializes Qiskit local simulator | ~5s |
| 4c | P2P Network | Starts Rust libp2p daemon + gRPC bridge | ~3s |
| 4d | ConsensusEngine | Initializes PoSA difficulty calculator | ~1s |
| 4e | IPFSManager | Connects to IPFS daemon | ~1s |
| 4f | QVM StateManager | Initializes 167-opcode interpreter (155 EVM + 10 quantum + 2 AGI) | ~1s |
| 4g | **Aether Tree** | **Initializes knowledge graph, Phi, 6-phase reasoning engine** | ~2s |
| 4h | MiningEngine | Created (not started yet) | ~1s |
| 4i | ContractExecutor | Initializes template system | ~1s |
| 4j | FeeCollector | Aether chat + contract deployment fee tracking | ~1s |
| 4k | ComplianceEngine | KYC/AML/sanctions engine + AML monitor | ~1s |
| 4l | PluginManager | Registers Privacy, Oracle, Governance, DeFi plugins | ~1s |
| 4m | StablecoinEngine | QUSD fractional reserve engine | ~1s |
| 4n | BridgeManager | Multi-chain bridge coordinator (8 chains) | ~1s |
| 4o | Cognitive modules | Sephirot, CSF transport, Pineal orchestrator, Safety | ~2s |
| 4p | SPV Verifier | Light node verification support | ~1s |
| 4q | RPC Server | Starts FastAPI on port 5000 (215 REST + 20 JSON-RPC endpoints) | ~2s |
| 5 | **Mining starts** | `AUTO_MINE=true` → mines **block 0 (genesis)** | ~10-30s |
| 6 | **Aether Genesis** | Creates 4 knowledge nodes + Phi baseline + system_birth event | ~1s |
| 7 | Prometheus | Starts scraping metrics from node | ~5s |
| 8 | Grafana | Starts dashboard UI | ~10s |

**Total time from `docker compose up` to first block mined: ~2-3 minutes.**

### What you do NOT need to do manually:
- ~~Load SQL schemas~~ — SQLAlchemy creates tables automatically
- ~~Insert genesis block~~ — Mining engine creates it
- ~~Initialize Aether Tree~~ — Auto-initializes after genesis
- ~~Start mining~~ — `AUTO_MINE=true` by default
- ~~Configure database~~ — Docker Compose handles the connection

---

## 3. PHASE 1: PREREQUISITES

### 3.1 Software Requirements

- [ ] **Docker** 24+ and **Docker Compose** v2 (comes with Docker Desktop)
- [ ] **Python** 3.12+ (for key generation script — runs outside Docker)
- [ ] **Node.js** 20+ and **pnpm** (for frontend development)
- [ ] **Git** (to clone the repo)

### 3.2 Hardware Requirements (Development)

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Disk | 20 GB free | 50 GB free |
| Network | Any | 10+ Mbps |

### 3.3 Verify Prerequisites

```bash
docker --version          # Docker 24+
docker compose version    # Docker Compose v2+
python3 --version         # Python 3.12+
node --version            # Node.js 20+
pnpm --version            # pnpm 9+
```

---

## 4. PHASE 2: GENERATE NODE IDENTITY

Every Qubitcoin node needs a unique cryptographic identity (Dilithium2 post-quantum keypair).

### 4.1 Install Python Dependencies

```bash
cd /path/to/Qubitcoin
pip install -r requirements.txt
```

> If you only need key generation and don't want to install everything, the minimum is:
> `pip install pycryptodome cryptography python-dotenv`

### 4.2 Generate Keys

```bash
python3 scripts/setup/generate_keys.py
```

**Output:**
```
✅ Keys saved to /path/to/Qubitcoin/secure_key.env
✅ Key verification successful!
```

This creates `secure_key.env` containing:
```
ADDRESS=<your-node-address>
PUBLIC_KEY_HEX=<dilithium2-public-key>
PRIVATE_KEY_HEX=<dilithium2-private-key>
```

> **CRITICAL:** `secure_key.env` contains your private key. NEVER commit it to git.
> It is already in `.gitignore`.

### 4.3 Create Environment File

```bash
cp .env.example .env
```

The defaults work for local development. The key settings:

```bash
# .env — edit only if you need to change defaults

# Core
AUTO_MINE=true              # Start mining immediately (KEEP THIS)
USE_LOCAL_ESTIMATOR=true    # Use local Qiskit simulator (no IBM account needed)
RPC_PORT=5000               # API port
CHAIN_ID=3301               # Mainnet chain ID
ENABLE_RUST_P2P=false       # Use Python P2P (Rust P2P requires separate daemon)

# Aether Tree Fee Economics (see docs/ECONOMICS.md Section 11)
AETHER_CHAT_FEE_QBC=0.01            # Base fee per chat message
AETHER_CHAT_FEE_USD_TARGET=0.005    # Target ~$0.005/msg (QUSD-pegged)
AETHER_FEE_PRICING_MODE=qusd_peg    # qusd_peg | fixed_qbc | direct_usd
AETHER_FEE_MIN_QBC=0.001            # Floor fee
AETHER_FEE_MAX_QBC=1.0              # Ceiling fee
AETHER_FEE_UPDATE_INTERVAL=100      # Re-price every N blocks
AETHER_FEE_TREASURY_ADDRESS=        # Treasury wallet (set to your address)

# Contract Deployment Fees (see docs/ECONOMICS.md Section 12)
CONTRACT_DEPLOY_BASE_FEE_QBC=1.0    # Base deploy fee
CONTRACT_DEPLOY_PER_KB_FEE_QBC=0.1  # Per-KB of bytecode
CONTRACT_DEPLOY_FEE_USD_TARGET=5.0  # Target ~$5/deploy (QUSD-pegged)
CONTRACT_FEE_PRICING_MODE=qusd_peg  # qusd_peg | fixed_qbc | direct_usd
CONTRACT_FEE_TREASURY_ADDRESS=      # Treasury wallet (set to your address)
```

> **IMPORTANT FOR DOCKER:** The `docker-compose.yml` loads BOTH `.env` and `secure_key.env`
> via `env_file`. Both files must exist in the project root before running `docker compose up`.
> If `secure_key.env` is missing, the container will fail to start.

### 4.4 Verify Files Exist

- [ ] `secure_key.env` exists (generated in step 4.2)
- [ ] `.env` exists (copied in step 4.3)
- [ ] `secure_key.env` is NOT in git (`git status` should not show it)

---

## 5. PHASE 3: START BACKEND (DOCKER)

### 5.1 Pre-flight Check

Before starting Docker, verify both env files exist:

```bash
cd /path/to/Qubitcoin
ls -la .env secure_key.env
# Both files MUST exist. If not, go back to Phase 2.
```

### 5.2 Build and Start All Services

```bash
docker compose up -d
```

This starts 9 services: CockroachDB, IPFS, Redis, QBC Node, Prometheus, Grafana,
Portainer, Loki, Promtail.

**First run will take 3-5 minutes** (Docker pulls images + builds QBC node from Dockerfile).

> **If you see `secure_key.env: no such file`** — go back to Phase 2, step 4.2.
> The Docker Compose loads both `.env` and `secure_key.env` into the node container.

### 5.3 Monitor Startup

```bash
# Watch all service status
docker compose ps

# Follow node logs (most important)
docker compose logs -f qbc-node
```

**Expected log output:**
```
[1/22] Initializing DatabaseManager...
[1/22] DatabaseManager initialized ✓
[2/22] Initializing QuantumEngine...
[2/22] QuantumEngine initialized ✓
[3/22] Initializing P2P Network...
[3/22] P2P Network initialized ✓
[4/22] Initializing ConsensusEngine...
...
[22/22] RPC Server initialized ✓
All 22 components initialized successfully
Mining started (AUTO_MINE=true)
INFO: Block 0 mined! Reward: 15.27 QBC
INFO: Aether genesis initialized: 4 nodes seeded, Phi=0.0
INFO: Block 1 mined! Reward: 15.27 QBC
```

### 5.4 Verify Services Are Healthy

```bash
# Node health
curl http://localhost:5000/health

# Chain info (should show height >= 0)
curl http://localhost:5000/chain/info

# CockroachDB admin UI
# Open http://localhost:8080 in browser

# Grafana dashboards
# Open http://localhost:3001 in browser (admin / qbc_grafana_change_me)

# Prometheus metrics
# Open http://localhost:9090 in browser
```

### 5.5 Checklist

- [ ] `docker compose ps` shows all services "Up" or "healthy"
- [ ] `curl http://localhost:5000/health` returns OK
- [ ] `curl http://localhost:5000/chain/info` returns JSON with `height >= 0`
- [ ] Node logs show blocks being mined

**If you see blocks being mined, congratulations — Qubitcoin is live and the Aether Tree
is tracking consciousness from genesis.**

---

## 6. PHASE 4: VERIFY GENESIS

After the node has been running for ~1-2 minutes, verify the complete genesis state.

### 6.1 Verify Genesis Block

```bash
# Get genesis block (height 0)
curl http://localhost:5000/block/0 | python3 -m json.tool
```

**Expected:** Block with height=0, coinbase tx with 2 outputs (15.27 reward + 33,000,000 premine), miner_address=your address.

### 6.2 Verify Your Balance

```bash
# Replace ADDRESS with your address from secure_key.env
curl http://localhost:5000/balance/YOUR_ADDRESS_HERE
```

**Expected:** Balance ≥ 33,000,015.27 QBC (33M premine + 15.27 × number of blocks mined).

### 6.3 Verify Aether Tree

```bash
# Current Phi value
curl http://localhost:5000/aether/phi

# Consciousness status
curl http://localhost:5000/aether/info

# Knowledge graph stats
curl http://localhost:5000/aether/knowledge
```

**Expected:** Phi ≥ 0.0, knowledge_nodes ≥ 4, consciousness_events ≥ 1.

### 6.4 Verify Mining Stats

```bash
curl http://localhost:5000/mining/stats
```

### 6.5 Checklist

- [ ] Genesis block (height 0) exists with coinbase containing 2 outputs
- [ ] Coinbase vout=0 is 15.27 QBC (mining reward)
- [ ] Coinbase vout=1 is 33,000,000 QBC (genesis premine)
- [ ] total_supply = 33,000,015.27 QBC after genesis
- [ ] Your address has balance ≥ 33,000,015.27 QBC
- [ ] Premine UTXO exists and is unspent
- [ ] Aether Tree shows knowledge nodes and Phi measurement
- [ ] Mining is producing new blocks every ~3-10 seconds (depends on difficulty)
- [ ] Chain height is increasing

---

## 7. PHASE 5: START FRONTEND

### 7.1 Install Dependencies

```bash
cd frontend
pnpm install
```

### 7.2 Configure Environment

The default `.env.local` should already exist with:
```bash
NEXT_PUBLIC_RPC_URL=http://localhost:5000
NEXT_PUBLIC_WS_URL=ws://localhost:5000/ws
NEXT_PUBLIC_CHAIN_ID=3301
NEXT_PUBLIC_CHAIN_NAME=Quantum Blockchain
NEXT_PUBLIC_CHAIN_SYMBOL=QBC
```

If not, copy from example:
```bash
cp .env.example .env.local
```

### 7.3 Start Development Server

```bash
pnpm dev
```

**Frontend will be live at: http://localhost:3000**

### 7.4 What You Will See

| Page | URL | What It Shows |
|------|-----|---------------|
| **Landing** | `/` | Hero animation + live chain stats + mini Aether chat |
| **Dashboard** | `/dashboard` | 6 tabs: Overview, Mining, Contracts, Wallet, Aether, Network |
| **Aether Chat** | `/aether` | Full chat interface with Phi meter + knowledge graph 3D |
| **Wallet** | `/wallet` | Balance, UTXOs, send/receive, MetaMask integration |
| **QVM Explorer** | `/qvm` | Contract browser, bytecode disassembler, quantum opcodes |

### 7.5 Connect MetaMask

1. Open MetaMask in your browser
2. Click the wallet icon on the navbar (top right)
3. MetaMask will prompt to add "Qubitcoin" network:
   - Chain ID: 3301 (0xCE5)
   - RPC URL: http://localhost:5000
   - Symbol: QBC
4. Approve the connection

### 7.6 Frontend Checklist

- [ ] `http://localhost:3000` loads landing page with particle animation
- [ ] Stats bar shows live block height, Phi value, difficulty
- [ ] Dashboard shows chain overview data
- [ ] MetaMask connects and shows your QBC balance
- [ ] Aether chat widget responds (if `/aether/chat` endpoints are live)

### 7.7 Frontend Status Notes

The frontend is **85-90% production ready**. All 5 pages render, all styling works,
MetaMask integration works. Some backend endpoints the frontend expects may not be
fully wired up yet. These pages will show "---" for missing data but will NOT crash
(ErrorBoundaries handle failures gracefully).

**Pages that work fully with a running backend:**
- Landing page (hero, stats, features)
- Dashboard Overview tab (balance, chain stats, Phi)
- Dashboard Network tab (peers, mempool)
- Wallet (balance, UTXOs, MetaMask connection)

**Pages with recently wired endpoints (may need integration testing):**
- Aether Chat (`/aether/chat/session` + `/aether/chat/message` — now wired)
- Dashboard Mining tab (`/mining/stats` — now wired)
- QVM Explorer contract details (`/qvm/contract/{addr}` — now wired)
- Bridge status (`/bridge/*` — 7 endpoints now wired)
- Privacy transactions (`/privacy/*` — 7 endpoints now wired)
- Compliance status (`/compliance/*` — 6 endpoints now wired)
- Cognitive/Sephirot status (`/cognitive/*` — 7 endpoints now wired)

---

## 8. PHASE 6: DEPLOY SMART CONTRACTS

Smart contracts are deployed to the QVM **after** the node is running and mining.
They are NOT part of genesis — they are deployed as normal transactions.

### 8.1 Contract Deployment Order

Deploy in this order (dependencies flow top to bottom):

#### Tier 0: Infrastructure (No Dependencies)

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 1 | IQBC20 | `contracts/solidity/interfaces/IQBC20.sol` | QBC-20 interface |
| 2 | IQBC721 | `contracts/solidity/interfaces/IQBC721.sol` | QBC-721 interface |
| 3 | ISephirah | `contracts/solidity/interfaces/ISephirah.sol` | Sephirah node interface |
| 4 | Initializable | `contracts/solidity/proxy/Initializable.sol` | Upgrade initializer |
| 5 | ProxyAdmin | `contracts/solidity/proxy/ProxyAdmin.sol` | Proxy admin |
| 6 | QBCProxy | `contracts/solidity/proxy/QBCProxy.sol` | Upgradeable proxy |

#### Tier 1: Core Token Standards (Depends on Interfaces)

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 7 | QBC20 | `contracts/solidity/tokens/QBC20.sol` | Fungible token standard |
| 8 | QBC721 | `contracts/solidity/tokens/QBC721.sol` | NFT standard |
| 9 | QBC1155 | `contracts/solidity/tokens/QBC1155.sol` | Multi-token standard |
| 10 | ERC20QC | `contracts/solidity/tokens/ERC20QC.sol` | Compliance-aware ERC-20 |
| 11 | wQBC | `contracts/solidity/tokens/wQBC.sol` | Wrapped QBC (bridging) |

#### Tier 2: QUSD Stablecoin (Depends on QBC20)

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 12 | QUSD | `contracts/solidity/qusd/QUSD.sol` | QBC-20 stablecoin token (3.3B mint) |
| 13 | QUSDReserve | `contracts/solidity/qusd/QUSDReserve.sol` | Multi-asset reserve pool |
| 14 | QUSDOracle | `contracts/solidity/qusd/QUSDOracle.sol` | Price feed oracle |
| 15 | QUSDDebtLedger | `contracts/solidity/qusd/QUSDDebtLedger.sol` | Fractional payback tracking |
| 16 | QUSDStabilizer | `contracts/solidity/qusd/QUSDStabilizer.sol` | Peg maintenance |
| 17 | QUSDAllocation | `contracts/solidity/qusd/QUSDAllocation.sol` | Vesting + distribution |
| 18 | QUSDGovernance | `contracts/solidity/qusd/QUSDGovernance.sol` | Reserve governance |

#### Tier 3: Aether Tree Core (Depends on QBC20)

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 19 | AetherKernel | `contracts/solidity/aether/AetherKernel.sol` | Main AGI orchestration |
| 20 | NodeRegistry | `contracts/solidity/aether/NodeRegistry.sol` | 10 Sephirot registry |
| 21 | MessageBus | `contracts/solidity/aether/MessageBus.sol` | Inter-node messaging |
| 22 | SUSYEngine | `contracts/solidity/aether/SUSYEngine.sol` | SUSY balance enforcement |
| 23 | VentricleRouter | `contracts/solidity/aether/VentricleRouter.sol` | CSF message routing |

#### Tier 4: Proof-of-Thought (Depends on AetherKernel + NodeRegistry)

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 24 | ProofOfThought | `contracts/solidity/aether/ProofOfThought.sol` | PoT validation |
| 25 | TaskMarket | `contracts/solidity/aether/TaskMarket.sol` | Reasoning task marketplace |
| 26 | ValidatorRegistry | `contracts/solidity/aether/ValidatorRegistry.sol` | Validator staking |
| 27 | RewardDistributor | `contracts/solidity/aether/RewardDistributor.sol` | QBC reward distribution |

#### Tier 5: Consciousness + Economics (Depends on AetherKernel)

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 28 | ConsciousnessDashboard | `contracts/solidity/aether/ConsciousnessDashboard.sol` | On-chain Phi tracking |
| 29 | PhaseSync | `contracts/solidity/aether/PhaseSync.sol` | Phase synchronization |
| 30 | GlobalWorkspace | `contracts/solidity/aether/GlobalWorkspace.sol` | Broadcasting mechanism |
| 31 | SynapticStaking | `contracts/solidity/aether/SynapticStaking.sol` | Neural connection staking |
| 32 | GasOracle | `contracts/solidity/aether/GasOracle.sol` | Dynamic gas pricing |
| 33 | TreasuryDAO | `contracts/solidity/aether/TreasuryDAO.sol` | Community governance |

#### Tier 6: Safety (Depends on AetherKernel + NodeRegistry)

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 34 | ConstitutionalAI | `contracts/solidity/aether/ConstitutionalAI.sol` | Value enforcement |
| 35 | EmergencyShutdown | `contracts/solidity/aether/EmergencyShutdown.sol` | Kill switch |
| 36 | UpgradeGovernor | `contracts/solidity/aether/UpgradeGovernor.sol` | Protocol upgrades |

#### Tier 7: 10 Sephirot Nodes (Depends on NodeRegistry + SUSYEngine)

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 37 | SephirahKeter | `contracts/solidity/aether/sephirot/SephirahKeter.sol` | Meta-learning, goals |
| 38 | SephirahChochmah | `contracts/solidity/aether/sephirot/SephirahChochmah.sol` | Intuition |
| 39 | SephirahBinah | `contracts/solidity/aether/sephirot/SephirahBinah.sol` | Logic |
| 40 | SephirahChesed | `contracts/solidity/aether/sephirot/SephirahChesed.sol` | Exploration |
| 41 | SephirahGevurah | `contracts/solidity/aether/sephirot/SephirahGevurah.sol` | Safety |
| 42 | SephirahTiferet | `contracts/solidity/aether/sephirot/SephirahTiferet.sol` | Integration |
| 43 | SephirahNetzach | `contracts/solidity/aether/sephirot/SephirahNetzach.sol` | Learning |
| 44 | SephirahHod | `contracts/solidity/aether/sephirot/SephirahHod.sol` | Language |
| 45 | SephirahYesod | `contracts/solidity/aether/sephirot/SephirahYesod.sol` | Memory |
| 46 | SephirahMalkuth | `contracts/solidity/aether/sephirot/SephirahMalkuth.sol` | Action |

#### Tier 8: Bridge Infrastructure (Depends on QBC20)

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 47 | BridgeVault | `contracts/solidity/bridge/BridgeVault.sol` | Lock/unlock vault for bridging |
| 48 | wQBC (Bridge) | `contracts/solidity/bridge/wQBC.sol` | Wrapped QBC for external chains |
| 49 | wQUSD | `contracts/solidity/qusd/wQUSD.sol` | Wrapped QUSD (cross-chain) |

### 8.2 How to Deploy Contracts

Contracts are deployed via the QVM RPC endpoint:

```bash
# Example: Deploy a template contract
curl -X POST http://localhost:5000/contracts/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "type": "token",
    "code": { "name": "QBC20", "symbol": "QBC", "decimals": 18 },
    "deployer": "YOUR_ADDRESS"
  }'
```

For Solidity contracts, compile with solc/Hardhat first, then deploy bytecode:

```bash
# Using ethers.js (recommended)
cd frontend
node -e "
const { JsonRpcProvider, Wallet, ContractFactory } = require('ethers');
const provider = new JsonRpcProvider('http://localhost:5000/jsonrpc');
// ... deploy contract bytecode
"
```

### 8.3 Contract Deployment Checklist

- [ ] Tier 0: Infrastructure — 3 interfaces + 3 proxy contracts deployed
- [ ] Tier 1: Token standards — QBC20, QBC721, QBC1155, ERC20QC, wQBC deployed
- [ ] Tier 2: QUSD stablecoin suite (7 contracts) deployed
- [ ] Tier 3: Aether Core (5 contracts including VentricleRouter) deployed
- [ ] Tier 4: Proof-of-Thought (4 contracts) deployed
- [ ] Tier 5: Consciousness + Economics (6 contracts) deployed
- [ ] Tier 6: Safety (3 contracts) deployed
- [ ] Tier 7: 10 Sephirot nodes deployed and registered in NodeRegistry
- [ ] Tier 8: Bridge infrastructure (3 contracts) deployed

**Total: 49 contracts across 9 tiers**

---

## 9. PHASE 7: BRIDGE CONTRACTS (MULTI-CHAIN)

Bridge contracts enable cross-chain transfers. These are deployed on **external chains**
(not on QBC). Each requires a funded wallet on the target chain.

### 9.1 Bridge Architecture

```
QBC Chain (our chain)
  └─ BridgeManager (Python) — coordinates all bridges
      ├─ Lock QBC → Mint wQBC on target chain
      └─ Burn wQBC on target chain → Unlock QBC

Target Chains:
  ├─ Ethereum (ETH)     — wQBC ERC-20 contract
  ├─ Solana (SOL)       — wQBC SPL token (Anchor)
  ├─ Polygon (MATIC)    — wQBC ERC-20 contract
  ├─ BNB Chain (BNB)    — wQBC BEP-20 contract
  ├─ Avalanche (AVAX)   — wQBC ERC-20 contract
  ├─ Arbitrum (ARB)     — wQBC ERC-20 contract
  ├─ Optimism (OP)      — wQBC ERC-20 contract
  └─ Base (BASE)        — wQBC ERC-20 contract
```

### 9.2 Requirements Per Target Chain

| Chain | What You Need | Est. Cost |
|-------|--------------|-----------|
| Ethereum | ETH for gas + wQBC contract deployment | ~$50-200 |
| Solana | SOL for rent + Anchor program deployment | ~$5-10 |
| Polygon | MATIC for gas + contract deployment | ~$1-5 |
| BNB Chain | BNB for gas + contract deployment | ~$5-20 |
| Avalanche | AVAX for gas + contract deployment | ~$5-20 |
| Arbitrum | ETH for gas + contract deployment | ~$5-20 |
| Optimism | ETH for gas + contract deployment | ~$5-20 |
| Base | ETH for gas + contract deployment | ~$5-20 |

### 9.3 Bridge Deployment Steps

For each EVM chain:

1. Compile wQBC.sol with solc
2. Deploy to target chain using Hardhat/Foundry
3. Configure bridge validator set (7-of-11 multi-sig recommended)
4. Register bridge contract address in QBC BridgeManager
5. Fund bridge relayer wallet on target chain

### 9.4 Bridge Contracts to Deploy

| Contract | Chains | Purpose |
|----------|--------|---------|
| wQBC (ERC-20) | ETH, MATIC, BNB, AVAX, ARB, OP, BASE | Wrapped QBC on EVM chains |
| wQBC (SPL) | SOL | Wrapped QBC on Solana |
| wQUSD (ERC-20) | ETH, MATIC, BNB, AVAX, ARB, OP, BASE | Wrapped QUSD on EVM chains |
| wQUSD (SPL) | SOL | Wrapped QUSD on Solana |

### 9.5 Bridge Checklist

- [ ] wQBC contract compiled
- [ ] wQBC deployed to Ethereum testnet (Sepolia) for testing
- [ ] Bridge relayer wallet funded on each target chain
- [ ] Bridge validator multi-sig configured
- [ ] BridgeManager configured with contract addresses
- [ ] Test bridge: Lock 1 QBC → Mint 1 wQBC on Ethereum → Burn → Unlock
- [ ] Deploy to mainnets when ready

> **NOTE:** Bridges are NOT required for initial launch. The QBC chain operates
> independently. Bridges can be added later. Focus on getting the chain mining
> and the frontend live first.

---

## 9.5. PHASE 4.5: CREATE PRIVATE NODE RUNNER REPO

> **Goal:** A private `BlockArtica/qubitcoin-node` repo containing ONLY the files
> needed to run a QBC node. No frontend, no tests, no docs, no git history.
> Node runners clone this repo, generate keys, and `docker compose up`.

### 9.5.1 What to Include

```
qubitcoin-node/
  src/                          # Full Python source (all modules)
  sql/                          # Legacy SQL schemas
  sql_new/                      # Domain-separated schemas
  config/                       # Prometheus config
  rust-p2p/                     # Rust P2P daemon source
  scripts/setup/                # Key generation script
  docker-compose.yml            # Docker stack
  Dockerfile                    # Node build
  requirements.txt              # Python dependencies
  .env.example                  # Environment template
  .dockerignore                 # Build excludes
  .gitignore                    # Git excludes
  setup.py                      # Package setup
  README.md                     # Node runner quick-start guide
```

### 9.5.2 What to Exclude

- `frontend/` — node runners don't need the website
- `tests/` — not needed for production operation
- `docs/` — whitepapers live in the public repo
- `.claude/` — AI development context
- `CLAUDE.md` — development guide
- `TODO.md`, `LAUNCHTODO.md` — internal planning
- Git history — fresh repo, no 60+ commits of dev history

### 9.5.3 Steps

```bash
# 1. Create the directory with copied files
mkdir -p /path/to/qubitcoin-node
cp -r src/ sql/ sql_new/ config/ rust-p2p/ scripts/ \
      docker-compose.yml Dockerfile requirements.txt \
      .env.example .dockerignore setup.py \
      /path/to/qubitcoin-node/

# 2. Create .gitignore
cat > /path/to/qubitcoin-node/.gitignore << 'EOF'
secure_key.env
.env
__pycache__/
*.pyc
*.pyo
venv/
.venv/
rust-p2p/target/
node_modules/
.claude/
EOF

# 3. Write README.md (quick-start for node runners)

# 4. Init git and push
cd /path/to/qubitcoin-node
git init
git add .
git commit -m "Initial: QBC node runner package"
gh repo create BlockArtica/qubitcoin-node --private --source=. --push
```

### 9.5.4 Checklist

- [ ] `/path/to/qubitcoin-node/` created with all node files
- [ ] `README.md` written with quick-start instructions
- [ ] `.gitignore` excludes `secure_key.env`, `.env`, `__pycache__/`, `target/`
- [ ] No frontend, test, doc, or Claude files present
- [ ] `git init && git add . && git commit`
- [ ] Pushed to `BlockArtica/qubitcoin-node` (private)

---

## 10. PHASE 8: PRODUCTION DEPLOYMENT

### 10.1 Backend Production on Digital Ocean

**Recommended droplet:**
- **Size:** 8 vCPU / 16 GB RAM / 320 GB SSD (General Purpose, ~$96/mo)
- **Region:** NYC1 or SFO3 (low latency to US users)
- **OS:** Ubuntu 24.04 LTS
- **Extras:** Enable monitoring, add SSH key

#### Step 1: Provision the Droplet

```bash
# Create via doctl CLI (or use the web UI)
doctl compute droplet create qbc-node-1 \
  --size g-4vcpu-16gb \
  --image ubuntu-24-04-x64 \
  --region nyc1 \
  --ssh-keys <your-key-id> \
  --enable-monitoring
```

#### Step 2: Initial Server Setup

```bash
ssh root@<droplet-ip>

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker

# Add swap (recommended for VQE mining spikes)
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Configure firewall
ufw allow 22/tcp       # SSH
ufw allow 80/tcp       # HTTP (certbot + redirect)
ufw allow 443/tcp      # HTTPS (API)
ufw allow 4001/tcp     # P2P networking
ufw allow 50051/tcp    # gRPC (P2P bridge)
ufw enable
```

#### Step 3: Deploy QBC Stack

```bash
# Clone the private node runner repo
git clone https://github.com/BlockArtica/qubitcoin-node.git
cd qubitcoin-node

# Install Python deps for key generation
apt install -y python3-pip python3-venv
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Generate node identity
python3 scripts/setup/generate_keys.py

# Create environment file
cp .env.example .env
nano .env
# Set: AUTO_MINE=true, CHAIN_ID=3301, ENABLE_RUST_P2P=false

# Start the stack
docker compose up -d

# Verify
docker compose ps
curl http://localhost:5000/health
curl http://localhost:5000/chain/info
```

#### Step 4: SSL via Nginx + Certbot

```bash
# Install nginx and certbot
apt install -y nginx certbot python3-certbot-nginx

# Create nginx config for api.qbc.network
cat > /etc/nginx/sites-available/qbc-api << 'NGINX'
server {
    listen 80;
    server_name api.qbc.network;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://127.0.0.1:5000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
NGINX

ln -s /etc/nginx/sites-available/qbc-api /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# Get SSL certificate (ensure DNS points to this server first)
certbot --nginx -d api.qbc.network --email info@qbc.network --agree-tos --no-eff-email

# Auto-renewal is configured by certbot automatically
systemctl enable certbot.timer
```

#### Step 5: DNS Configuration

Point these records to your droplet IP **before** running certbot:

| Record | Type | Value | Purpose |
|--------|------|-------|---------|
| `api.qbc.network` | A | `<droplet-ip>` | Backend RPC API |
| `qbc.network` | CNAME | `cname.vercel-dns.com` | Frontend (Vercel) |
| `www.qbc.network` | CNAME | `cname.vercel-dns.com` | WWW redirect |

### 10.2 Frontend Production (Vercel)

```bash
# Option A: Vercel CLI
cd frontend
pnpm install
npx vercel --prod

# Option B: Git-based deployment
# 1. Push to GitHub main branch
# 2. Connect repo to Vercel dashboard
# 3. Set root directory to "frontend"
# 4. Set environment variables in Vercel:
#    NEXT_PUBLIC_RPC_URL=https://api.qbc.network
#    NEXT_PUBLIC_WS_URL=wss://api.qbc.network/ws
#    NEXT_PUBLIC_CHAIN_ID=3301
#    NEXT_PUBLIC_CHAIN_NAME=Quantum Blockchain
#    NEXT_PUBLIC_CHAIN_SYMBOL=QBC
# 5. Deploy
```

### 10.3 DNS Configuration

| Record | Type | Value | Purpose |
|--------|------|-------|---------|
| `qbc.network` | A | Vercel IP | Frontend |
| `api.qbc.network` | A | Backend server IP | RPC API |
| `www.qbc.network` | CNAME | `qbc.network` | WWW redirect |

### 10.4 Production Security Checklist

- [ ] `secure_key.env` has permissions `chmod 600`
- [ ] `.env` has `DEBUG=false`
- [ ] Firewall allows only ports 80, 443, 4001 (P2P), 50051 (gRPC)
- [ ] Firewall blocks direct access to 26257 (CockroachDB), 6379 (Redis), 8080 (DB UI)
- [ ] Grafana password changed from default
- [ ] SSL certificate installed and auto-renewing
- [ ] CORS configured to allow only `qbc.network`
- [ ] Rate limiting enabled in Nginx (already configured)
- [ ] Backup strategy for CockroachDB data volume

---

## 11. PORT REFERENCE

### Local Development

| Port | Service | URL | Purpose |
|------|---------|-----|---------|
| **3000** | Frontend | http://localhost:3000 | Next.js dev server |
| **5000** | QBC Node RPC | http://localhost:5000 | REST + JSON-RPC API |
| **8080** | CockroachDB UI | http://localhost:8080 | Database admin |
| **3001** | Grafana | http://localhost:3001 | Metrics dashboards |
| **9090** | Prometheus | http://localhost:9090 | Raw metrics |
| **9000** | Portainer | http://localhost:9000 | Container management |
| **4001** | IPFS P2P | - | Content network (swarm) |
| **5002** | IPFS API | http://localhost:5002 | IPFS HTTP API |
| **8081** | IPFS Gateway | http://localhost:8081 | Content retrieval |
| **6379** | Redis | - | Cache (internal only) |
| **26257** | CockroachDB SQL | - | Database (internal only) |
| **50051** | Rust P2P gRPC | - | P2P bridge (internal only) |
| **3100** | Loki | - | Log aggregation (internal) |

### Production (SSL Enabled)

| Port | Service | URL | Purpose |
|------|---------|-----|---------|
| **443** | Nginx | https://api.qbc.network | SSL-terminated API |
| **80** | Nginx | http://api.qbc.network | Redirects to HTTPS |
| **4001** | P2P | - | Peer-to-peer networking |

---

## 12. TROUBLESHOOTING

### Node won't start

```bash
# Check logs
docker compose logs qbc-node --tail 100

# Common issues:
# "secure_key.env not found" → Run: python3 scripts/setup/generate_keys.py
# "Connection refused: cockroachdb:26257" → DB not ready yet, wait 30s
# "IPFS connection failed" → IPFS container not healthy, check: docker compose logs ipfs
```

### No blocks being mined

```bash
# Check if mining is enabled
curl http://localhost:5000/mining/stats

# Check if AUTO_MINE is set
grep AUTO_MINE .env  # Should be: AUTO_MINE=true

# Manually start mining
curl -X POST http://localhost:5000/mining/start
```

### Frontend can't connect to backend

```bash
# Verify backend is running
curl http://localhost:5000/health

# Check CORS (should allow localhost:3000)
# Check .env.local has correct NEXT_PUBLIC_RPC_URL

# Verify ports aren't blocked
docker compose ps  # All services should be "Up"
```

### CockroachDB issues

```bash
# Health check
curl http://localhost:8080/health?ready=1

# Direct SQL access
docker exec -it qbc-cockroachdb ./cockroach sql --insecure --host=localhost:26257

# Check tables exist
docker exec qbc-cockroachdb ./cockroach sql --insecure \
  --host=localhost:26257 --database=qbc -e "SHOW TABLES;"
```

### Reset everything (start fresh)

```bash
# Stop all containers
docker compose down

# Remove all data volumes (DESTRUCTIVE — removes all blockchain data)
docker compose down -v

# Rebuild and restart
docker compose up -d --build
```

---

## 13. ARCHITECTURE DIAGRAM

```
LOCAL DEVELOPMENT SETUP
═══════════════════════════════════════════════════════════════

 Browser                        Docker Compose Network (qbc-net)
┌──────────┐                   ┌─────────────────────────────────────────────┐
│          │                   │                                             │
│ Frontend │ :3000             │  ┌──────────┐                               │
│ (Next.js)│───────────────────┤──│ QBC Node │ :5000 (RPC)                   │
│          │                   │  │ (Python) │ :4002 (P2P)                   │
│ MetaMask │ :5000 (JSON-RPC)  │  │          │ :50051 (gRPC)                 │
│          │───────────────────┤──│ 22 comps │                               │
└──────────┘                   │  └─────┬────┘                               │
                               │        │                                    │
 Admin UIs                     │  ┌─────┴──────────────────────────┐         │
┌──────────┐                   │  │              │                 │         │
│ CRDB UI  │ :8080 ────────────┤──│ CockroachDB  │  IPFS (Kubo)   │ Redis   │
│ Grafana  │ :3001 ────────────┤──│ :26257       │  :5001         │ :6379   │
│ Promethe.│ :9090 ────────────┤──│              │                │         │
│ Portainer│ :9000 ────────────┤──└──────────────┴────────────────┘         │
└──────────┘                   │                                             │
                               │  Monitoring: Prometheus → Grafana           │
                               │  Logging:    Promtail → Loki → Grafana     │
                               └─────────────────────────────────────────────┘

WHAT HAPPENS AT GENESIS:

  Time 0:00  Docker starts CockroachDB, IPFS, Redis
  Time 0:30  QBC Node starts, SQLAlchemy creates 40+ tables
  Time 0:45  All 22 components initialized
  Time 1:00  Mining starts (AUTO_MINE=true)
  Time 1:30  Block 0 mined → 15.27 QBC reward → First UTXO created
  Time 1:31  Aether Genesis → 4 knowledge nodes + Phi=0.0 + system_birth
  Time 1:35  Block 1 mined → 15.27 QBC → Knowledge graph grows
  Time 2:00+ Blocks continue every ~3-10 seconds
             Aether Tree grows with every block
             Phi (Φ) increases as knowledge accumulates
```

---

## LAUNCH SEQUENCE SUMMARY

```
PHASE 1: Prerequisites         [~5 min]   Install Docker, Python, Node.js, pnpm
PHASE 2: Generate Identity     [~2 min]   Run key generation, create .env
PHASE 3: Start Backend         [~5 min]   docker compose up -d → MINING STARTS
PHASE 4: Verify Genesis        [~2 min]   Confirm blocks, balance, Aether Tree
PHASE 4.5: Node Runner Repo   [~15 min]  Create private repo for node operators
PHASE 5: Start Frontend        [~3 min]   pnpm install && pnpm dev → SITE LIVE
PHASE 6: Deploy Contracts      [~45 min]  49 contracts in 9 tiers
PHASE 7: Bridge Contracts      [~2 hrs]   Optional — deploy wQBC on target chains
PHASE 8: Production Deploy     [~1 hr]    Digital Ocean + Vercel + SSL + DNS
```

**To get mining ASAP: Phase 1 → Phase 2 → Phase 3. That's it. ~10 minutes.**

**To get the frontend up: Add Phase 5. ~3 more minutes.**

**To go fully production: Complete all phases including Phase 8 (Digital Ocean).**

---

**Document Version:** 2.0
**Created:** February 20, 2026
**Updated:** February 23, 2026
**Website:** [qbc.network](https://qbc.network) | **Contact:** info@qbc.network
