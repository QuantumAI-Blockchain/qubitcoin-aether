# LAUNCHTODO.md — Quantum Blockchain Mainnet Launch Checklist

> **Master document for bringing Quantum Blockchain live: seed node on Digital Ocean + mining node locally.**
> Work through each phase in order. Check boxes as you go.

**Website:** qbc.network | **Contact:** info@qbc.network | **Chain ID:** 3301

---

## 2-NODE QUICK LAUNCH

**The plan:** Launch a seed node on a Digital Ocean droplet (genesis miner + public RPC), then
connect your local machine as a second mining node. Total time: ~30 minutes.

```
┌──────────────────────────┐          ┌──────────────────────────┐
│  NODE 1: SEED NODE       │          │  NODE 2: MINING NODE     │
│  Digital Ocean Droplet   │◄────────►│  Your Local Machine      │
│                          │  P2P     │                          │
│  - Genesis block miner   │  :4001   │  - Connects as peer      │
│  - Public RPC API        │          │  - Mines new blocks      │
│  - SSL via Nginx         │          │  - Syncs chain from DO   │
│  - 24/7 uptime           │          │  - Dev/testing           │
└──────────────────────────┘          └──────────────────────────┘
         │
         ▼
   api.qbc.network (HTTPS)
   qbc.network (Vercel frontend)
```

**What each node does:**
- **Node 1 (DO Seed):** Mines genesis, serves RPC, is the first peer other nodes connect to
- **Node 2 (Local):** Syncs chain from Node 1, mines independently, validates blocks

**Minimum steps to get mining:**
1. Phase 1 (Prerequisites) — ~5 min
2. Phase 2 (Generate Keys) — ~2 min
3. Phase 3 (Launch Seed Node on DO) — ~15 min
4. Phase 5 (Launch Mining Node Locally) — ~5 min

---

## TABLE OF CONTENTS

1. [Quick Answers](#1-quick-answers)
2. [What Happens Automatically](#2-what-happens-automatically)
3. [Phase 1: Prerequisites](#3-phase-1-prerequisites)
4. [Phase 2: Generate Node Identity](#4-phase-2-generate-node-identity)
5. [Phase 3: Launch Seed Node on Digital Ocean](#5-phase-3-launch-seed-node-on-digital-ocean)
6. [Phase 4: Verify Genesis](#6-phase-4-verify-genesis)
7. [Phase 5: Launch Mining Node Locally](#7-phase-5-launch-mining-node-locally)
8. [Phase 6: Verify 2-Node Network](#8-phase-6-verify-2-node-network)
9. [Phase 7: Deploy Frontend to Vercel](#9-phase-7-deploy-frontend-to-vercel)
10. [Phase 8: Deploy Smart Contracts](#10-phase-8-deploy-smart-contracts)
11. [Phase 9: Create Qubitcoin-node Public Repo](#11-phase-9-create-qubitcoin-node-public-repo)
12. [Phase 10: Bridge Contracts (Optional)](#12-phase-10-bridge-contracts-optional)
13. [Wallet Guide](#13-wallet-guide)
14. [Known Limitations at Launch](#14-known-limitations-at-launch)
15. [Port Reference](#15-port-reference)
16. [Troubleshooting](#16-troubleshooting)
17. [Architecture Diagram](#17-architecture-diagram)

---

## 1. QUICK ANSWERS

### Is SSL required for local Docker?
**NO.** SSL is not needed for local development or initial testing. All Docker services
communicate over an internal bridge network (`qbc-net`). The RPC API listens on
`http://localhost:5000` (plain HTTP). SSL is only needed for **production** (the DO droplet).
It is pre-configured via Nginx + Certbot in `docker-compose.production.yml`.

### Will Aether Tree launch at genesis?
**YES — automatically.** Here is what happens on first boot:

1. Node starts → SQLAlchemy auto-creates all 40+ database tables
2. Mining engine starts → mines block 0 (genesis) with 15.27 QBC reward + 33M premine
3. After block 0 exists → `AetherGenesis.initialize_genesis()` runs automatically:
   - Creates **4 genesis knowledge nodes** (root KeterNode + 3 axiom nodes)
   - Records **first Phi measurement** (Phi = 0.0 baseline)
   - Logs **"system_birth" consciousness event** at block 0
4. From block 1 onward, every block updates the Aether Tree knowledge graph

**The Aether Tree Python engine (33 modules: knowledge graph, 6-phase reasoning, Phi v3 with MIP,
3-tier memory, neural reasoner, on-chain AGI bridge, proof-of-thought) is fully integrated
into the node and tracks consciousness from genesis. No manual steps needed.**

### What about smart contracts?
The 50 Solidity contracts are **NOT auto-deployed at genesis**. They are deployed manually
via RPC after the node is running. See [Phase 8](#10-phase-8-deploy-smart-contracts).

### What about bridge contracts?
Bridge contracts must be deployed on each target chain **after** the QBC chain is running.
These require funded wallets on each target chain.
See [Phase 10](#12-phase-10-bridge-contracts-optional).

### What do I need to get mining ASAP?
**Phase 1 + Phase 2 + Phase 3 = mining on DO.** Add Phase 5 for a second local miner. ~30 min total.

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
| 4g2 | **Higgs Cognitive Field** | **Initializes mass assignments for Sephirot nodes (if HIGGS_ENABLE_MASS_REBALANCING=true)** | ~1s |
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
| 7+ | Monitoring | Prometheus + Grafana + Loki start (production compose) | ~15s |

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
- [ ] **Node.js** 20+ and **pnpm** (for frontend, if deploying)
- [ ] **Git** (to clone the repo)
- [ ] **doctl** (Digital Ocean CLI, optional — can use web UI instead)

### 3.2 Hardware Requirements

**Digital Ocean Droplet (Node 1 — Seed Node):**

| Component | Recommended | Minimum |
|-----------|-------------|---------|
| CPU | 8 vCPU (General Purpose) | 4 vCPU |
| RAM | 16 GB | 8 GB |
| Disk | 320 GB SSD | 160 GB SSD |
| Network | 10 Gbps (included) | - |
| Cost | ~$96/mo (g-4vcpu-16gb) | ~$48/mo |

**Local Machine (Node 2 — Mining Node):**

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
git --version             # Any recent version
```

---

## 4. PHASE 2: GENERATE NODE IDENTITY

Every Qubitcoin node needs a unique cryptographic identity (Dilithium2 post-quantum keypair).
You need **separate keys for each node** — generate once for DO, once for local.

### 4.1 Install Python Dependencies

```bash
cd /path/to/Qubitcoin
pip install -r requirements.txt
```

> If you only need key generation: `pip install pycryptodome cryptography python-dotenv`

### 4.2 Generate Keys for Node 1 (Seed Node)

```bash
python3 scripts/setup/generate_keys.py
```

**Output:**
```
Qubitcoin Key Generator (Dilithium2 Post-Quantum)
Keys saved to /path/to/Qubitcoin/secure_key.env
Key verification successful!
```

This creates `secure_key.env`:
```
ADDRESS=<your-seed-node-address>
PUBLIC_KEY_HEX=<dilithium2-public-key>
PRIVATE_KEY_HEX=<dilithium2-private-key>
```

**Save this ADDRESS** — this is your seed node's mining address. The genesis premine (33M QBC)
and all mining rewards go here.

> **CRITICAL:** `secure_key.env` contains your private key. NEVER commit it to git.

### 4.3 Create Environment File

```bash
cp .env.production.example .env    # For production (DO droplet)
# OR
cp .env.example .env               # For local development
```

Key settings for the seed node:
```bash
AUTO_MINE=true              # Start mining immediately
USE_LOCAL_ESTIMATOR=true    # Local Qiskit simulator
CHAIN_ID=3301               # Mainnet
ENABLE_RUST_P2P=true        # Use Rust P2P daemon

# Higgs Cognitive Field (Aether Tree mass mechanism)
HIGGS_ENABLE_MASS_REBALANCING=true    # Enable Higgs field mass assignments
HIGGS_VEV=246.0                       # Vacuum expectation value
HIGGS_LAMBDA=0.129                    # Quartic coupling constant
HIGGS_MU_SQUARED=-8000.0              # Mu^2 parameter (negative for SSB)
HIGGS_YUKAWA_SCALE=1.0                # Global Yukawa coupling scale
```

### 4.4 Verify Files Exist

- [ ] `secure_key.env` exists (generated in step 4.2)
- [ ] `.env` exists (copied in step 4.3)
- [ ] `secure_key.env` is NOT in git (`git status` should not show it)

---

## 5. PHASE 3: LAUNCH SEED NODE ON DIGITAL OCEAN

### 5.1 Provision the Droplet

```bash
# Via doctl CLI
doctl compute droplet create qbc-seed-1 \
  --size g-4vcpu-16gb \
  --image ubuntu-24-04-x64 \
  --region nyc1 \
  --ssh-keys $(doctl compute ssh-key list --format ID --no-header | head -1) \
  --enable-monitoring

# Note the IP address from the output
export SEED_IP=$(doctl compute droplet get qbc-seed-1 --format PublicIPv4 --no-header)
echo "Seed node IP: $SEED_IP"
```

Or use the Digital Ocean web UI: Create Droplet → Ubuntu 24.04 → General Purpose 8 vCPU/16GB.

### 5.2 Initial Server Setup

```bash
ssh root@$SEED_IP

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker

# Install Python (for key generation)
apt install -y python3-pip python3-venv git

# Add swap (recommended for VQE mining memory spikes)
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Configure firewall
ufw allow 22/tcp       # SSH
ufw allow 80/tcp       # HTTP (certbot ACME challenge)
ufw allow 443/tcp      # HTTPS (API via Nginx)
ufw allow 4001/tcp     # P2P networking (peers connect here)
ufw allow 50051/tcp    # gRPC P2P bridge
ufw enable
```

### 5.3 Deploy QBC Stack

```bash
# Clone the repo
git clone https://github.com/BlockArtica/Qubitcoin.git
cd Qubitcoin

# Generate node identity
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 scripts/setup/generate_keys.py
deactivate

# Create production environment
cp .env.production.example .env
# Edit .env — set treasury addresses to your ADDRESS from secure_key.env:
#   AETHER_FEE_TREASURY_ADDRESS=<your-address>
#   CONTRACT_FEE_TREASURY_ADDRESS=<your-address>
#   GRAFANA_ADMIN_PASSWORD=<strong-password>

# Start the production stack
docker compose -f docker-compose.production.yml up -d --build

# Monitor startup (wait for "Block 0 mined!")
docker compose -f docker-compose.production.yml logs -f qbc-node
```

**First build takes 5-10 minutes** (compiles Rust P2P daemon + installs Python deps).

### 5.3a Build Substrate Node (Optional — Future Migration Path)

The Substrate hybrid node provides a future migration path to a Rust-native runtime. To build:

```bash
cd substrate-node
SKIP_WASM_BUILD=1 cargo build --release
# Binary at target/release/qubitcoin-node
```

> **Note:** The WASM build is currently deferred due to an upstream `serde_core` conflict.
> Use `SKIP_WASM_BUILD=1` for native builds. The Substrate node is not required for the
> initial Python-based mainnet launch.

### 5.4 Verify Node Is Running

```bash
# Health check
curl http://localhost:5000/health

# Chain info (should show height >= 0)
curl http://localhost:5000/chain/info

# Check your balance (33M premine + mining rewards)
source secure_key.env
curl http://localhost:5000/balance/$ADDRESS
```

### 5.5 Setup SSL (HTTPS)

**Before this step:** Point `api.qbc.network` DNS A record to your droplet IP.

```bash
# Get initial SSL certificate (Nginx must be running on port 80 first)
# Temporarily use HTTP-only nginx for cert acquisition:
docker compose -f docker-compose.production.yml exec certbot \
  certbot certonly --webroot -w /var/www/certbot \
  -d api.qbc.network --email info@qbc.network \
  --agree-tos --no-eff-email

# Restart Nginx to load the new certificate
docker compose -f docker-compose.production.yml restart nginx

# Verify HTTPS works
curl https://api.qbc.network/health
```

> **Note:** If certbot fails because the HTTPS server block can't find certs yet, you can
> temporarily comment out the HTTPS server block in `config/nginx/nginx.conf`, restart nginx,
> run certbot, then uncomment and restart again. Or install certbot on the host directly
> (see Phase 8 of the original instructions).

### 5.6 DNS Configuration

Point these records to your droplet IP **before** running certbot:

| Record | Type | Value | Purpose |
|--------|------|-------|---------|
| `api.qbc.network` | A | `<droplet-ip>` | Backend RPC API |
| `qbc.network` | CNAME | `cname.vercel-dns.com` | Frontend (Vercel) |
| `www.qbc.network` | CNAME | `cname.vercel-dns.com` | WWW redirect |
| `seed1.qbc.network` | A | `<droplet-ip>` | P2P seed address |

### 5.7 Seed Node Checklist

- [ ] Droplet created and SSH accessible
- [ ] Docker installed and running
- [ ] Firewall configured (22, 80, 443, 4001, 50051)
- [ ] `secure_key.env` generated on the server
- [ ] `.env` configured with production settings
- [ ] `docker compose -f docker-compose.production.yml up -d` running
- [ ] `curl http://localhost:5000/health` returns OK
- [ ] Blocks are being mined (check logs)
- [ ] DNS pointed to droplet IP
- [ ] SSL certificate obtained (HTTPS works)

---

## 6. PHASE 4: VERIFY GENESIS

After the seed node has been running for ~1-2 minutes, verify the complete genesis state.

### 6.1 Verify Genesis Block

```bash
# Get genesis block (height 0)
curl http://localhost:5000/block/0 | python3 -m json.tool
```

**Expected:** Block with height=0, coinbase tx with 2 outputs (15.27 reward + 33,000,000 premine).

### 6.2 Verify Your Balance

```bash
# Use your address from secure_key.env
source secure_key.env
curl http://localhost:5000/balance/$ADDRESS
```

**Expected:** Balance >= 33,000,015.27 QBC (33M premine + 15.27 per block mined).

### 6.3 Verify Aether Tree

```bash
# Current Phi value
curl http://localhost:5000/aether/phi

# Consciousness status
curl http://localhost:5000/aether/info

# Knowledge graph stats
curl http://localhost:5000/aether/knowledge
```

**Expected:** Phi >= 0.0, knowledge_nodes >= 4, consciousness_events >= 1.

### 6.4 Genesis Checklist

- [ ] Genesis block (height 0) exists with coinbase containing 2 outputs
- [ ] Coinbase vout=0 is 15.27 QBC (mining reward)
- [ ] Coinbase vout=1 is 33,000,000 QBC (genesis premine)
- [ ] total_supply = 33,000,015.27 QBC after genesis
- [ ] Your address has balance >= 33,000,015.27 QBC
- [ ] Aether Tree shows knowledge nodes and Phi measurement
- [ ] Mining is producing new blocks every ~3-10 seconds
- [ ] Chain height is increasing

---

## 7. PHASE 5: LAUNCH MINING NODE LOCALLY

Now connect your local machine as a second mining node that syncs from the DO seed node.

### 7.1 Prerequisites (Local Machine)

```bash
cd /path/to/Qubitcoin

# Generate SEPARATE keys for the local node
# (Back up your seed node's secure_key.env first if you're on the same machine!)
python3 scripts/setup/generate_keys.py
```

> **IMPORTANT:** Each node needs its own key pair. If you use the same keys on two nodes,
> both will compete to create the same coinbase outputs, causing conflicts.

### 7.2 Configure Peer Connection

Create or edit `.env` with the seed node's IP:

```bash
cp .env.example .env
```

Edit `.env` and set:
```bash
# Point to your seed node
PEER_SEEDS=<SEED_NODE_IP>:4001

# Mining
AUTO_MINE=true
USE_LOCAL_ESTIMATOR=true
CHAIN_ID=3301

# P2P
ENABLE_RUST_P2P=true
```

Replace `<SEED_NODE_IP>` with your Digital Ocean droplet's public IP address.
If you set up DNS, you can use `seed1.qbc.network:4001` instead.

### 7.3 Start Local Node

```bash
# Using the development compose (exposes all ports for debugging)
docker compose up -d

# Monitor startup
docker compose logs -f qbc-node
```

**Expected log output:**
```
[3/22] Initializing P2P Network...
[3/22] P2P Network initialized
...
Connecting to seed peer: <SEED_IP>:4001
Peer connected: <seed-node-peer-id>
Syncing chain from peer... height=0 → current
Block 0 synced from peer
Block 1 synced from peer
...
Mining started (AUTO_MINE=true)
Block N mined! Reward: 15.27 QBC
```

### 7.4 Verify Peer Connection

```bash
# Check peers on the LOCAL node
curl http://localhost:5000/p2p/peers

# Check P2P stats
curl http://localhost:5000/p2p/stats
```

**Expected:** At least 1 connected peer (the seed node).

You can also verify from the **seed node** side:
```bash
# SSH into DO droplet
curl http://localhost:5000/p2p/peers
# Should show your local node's IP as a connected peer
```

### 7.5 Local Node Checklist

- [ ] Separate `secure_key.env` generated for local node
- [ ] `.env` has `PEER_SEEDS=<seed-ip>:4001`
- [ ] `docker compose up -d` running
- [ ] `curl http://localhost:5000/p2p/peers` shows >= 1 peer
- [ ] Chain is syncing (height matches seed node)
- [ ] Local node is mining new blocks

---

## 8. PHASE 6: VERIFY 2-NODE NETWORK

With both nodes running, verify they are properly synced and propagating blocks.

### 8.1 Compare Chain Heights

```bash
# Seed node (via public API or SSH)
curl https://api.qbc.network/chain/info | python3 -c "import sys,json; print('Seed height:', json.load(sys.stdin)['height'])"

# Local node
curl http://localhost:5000/chain/info | python3 -c "import sys,json; print('Local height:', json.load(sys.stdin)['height'])"
```

Heights should be within 1-2 blocks of each other (small difference due to propagation delay).

### 8.2 Verify Block Propagation

```bash
# Get the latest block from seed
SEED_TIP=$(curl -s https://api.qbc.network/chain/tip | python3 -c "import sys,json; print(json.load(sys.stdin)['height'])")

# Check if local node has it
curl http://localhost:5000/block/$SEED_TIP | python3 -c "import sys,json; d=json.load(sys.stdin); print('Block', d.get('height'), 'hash:', d.get('hash','not found')[:16])"
```

### 8.3 Verify Both Nodes Are Mining

```bash
# Seed node mining stats
curl https://api.qbc.network/mining/stats

# Local node mining stats
curl http://localhost:5000/mining/stats
```

Both should show `blocks_mined > 0` and different miner addresses.

### 8.4 Two-Node Network Checklist

- [ ] Both nodes show >= 1 connected peer
- [ ] Chain heights are within 1-2 blocks of each other
- [ ] Blocks mined by Node 1 appear on Node 2 (and vice versa)
- [ ] Both nodes have different miner addresses
- [ ] No fork detected (same block hash at same height on both nodes)

---

## 9. PHASE 7: DEPLOY FRONTEND TO VERCEL

### 9.1 Configure Frontend Environment

```bash
cd frontend

# Create production env
cat > .env.production << 'EOF'
NEXT_PUBLIC_RPC_URL=https://api.qbc.network
NEXT_PUBLIC_WS_URL=wss://api.qbc.network/ws
NEXT_PUBLIC_CHAIN_ID=3301
NEXT_PUBLIC_CHAIN_NAME=Quantum Blockchain
NEXT_PUBLIC_CHAIN_SYMBOL=QBC
EOF
```

### 9.2 Deploy to Vercel

**Option A: Git-based deployment (recommended)**
1. Push to GitHub `main` branch
2. Connect repo to Vercel dashboard (vercel.com)
3. Set root directory to `frontend`
4. Add the environment variables from `.env.production` in Vercel settings
5. Deploy — Vercel auto-deploys on push to main

**Option B: CLI deployment**
```bash
cd frontend
pnpm install
npx vercel --prod
```

### 9.3 Frontend Pages

| Page | URL | What It Shows |
|------|-----|---------------|
| **Landing** | `/` | Hero animation + live chain stats + Aether chat widget |
| **Explorer** | `/explorer` | Block explorer, transaction lookup, address search |
| **Dashboard** | `/dashboard` | Mining, contracts, wallet, Aether, network overview |
| **Aether Chat** | `/aether` | Full chat interface with Phi meter + knowledge graph 3D |
| **Bridge** | `/bridge` | Cross-chain transfer interface |
| **Exchange** | `/exchange` | DEX swap interface |
| **Launchpad** | `/launchpad` | Token launchpad for new QBC-20 tokens |

### 9.4 Frontend Checklist

- [ ] `qbc.network` loads landing page
- [ ] Stats bar shows live block height from `api.qbc.network`
- [ ] MetaMask can connect (chain ID 3301)
- [ ] Aether chat widget responds

---

## 10. PHASE 8: DEPLOY SMART CONTRACTS

Smart contracts are deployed to the QVM **after** the node is running and mining.
They are NOT part of genesis — they are deployed as normal transactions.

### 10.1 Contract Deployment Order

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

#### Tier 1: Core Token Standards

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 7 | QBC20 | `contracts/solidity/tokens/QBC20.sol` | Fungible token standard |
| 8 | QBC721 | `contracts/solidity/tokens/QBC721.sol` | NFT standard |
| 9 | QBC1155 | `contracts/solidity/tokens/QBC1155.sol` | Multi-token standard |
| 10 | ERC20QC | `contracts/solidity/tokens/ERC20QC.sol` | Compliance-aware ERC-20 |
| 11 | wQBC | `contracts/solidity/tokens/wQBC.sol` | Wrapped QBC (bridging) |

#### Tier 2: QUSD Stablecoin

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 12 | QUSD | `contracts/solidity/qusd/QUSD.sol` | QBC-20 stablecoin (3.3B mint) |
| 13 | QUSDReserve | `contracts/solidity/qusd/QUSDReserve.sol` | Multi-asset reserve pool |
| 14 | QUSDOracle | `contracts/solidity/qusd/QUSDOracle.sol` | Price feed oracle |
| 15 | QUSDDebtLedger | `contracts/solidity/qusd/QUSDDebtLedger.sol` | Fractional payback tracking |
| 16 | QUSDStabilizer | `contracts/solidity/qusd/QUSDStabilizer.sol` | Peg maintenance |
| 17 | QUSDAllocation | `contracts/solidity/qusd/QUSDAllocation.sol` | Vesting + distribution |
| 18 | QUSDGovernance | `contracts/solidity/qusd/QUSDGovernance.sol` | Reserve governance |

#### Tier 3: Aether Tree Core

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 19 | AetherKernel | `contracts/solidity/aether/AetherKernel.sol` | Main AGI orchestration |
| 20 | NodeRegistry | `contracts/solidity/aether/NodeRegistry.sol` | 10 Sephirot registry |
| 21 | MessageBus | `contracts/solidity/aether/MessageBus.sol` | Inter-node messaging |
| 22 | SUSYEngine | `contracts/solidity/aether/SUSYEngine.sol` | SUSY balance enforcement |
| 23 | VentricleRouter | `contracts/solidity/aether/VentricleRouter.sol` | CSF message routing |

#### Tier 4: Proof-of-Thought

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 24 | ProofOfThought | `contracts/solidity/aether/ProofOfThought.sol` | PoT validation |
| 25 | TaskMarket | `contracts/solidity/aether/TaskMarket.sol` | Reasoning task marketplace |
| 26 | ValidatorRegistry | `contracts/solidity/aether/ValidatorRegistry.sol` | Validator staking |
| 27 | RewardDistributor | `contracts/solidity/aether/RewardDistributor.sol` | QBC reward distribution |

#### Tier 5: Consciousness + Economics + Higgs

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 28 | ConsciousnessDashboard | `contracts/solidity/aether/ConsciousnessDashboard.sol` | On-chain Phi tracking |
| 29 | PhaseSync | `contracts/solidity/aether/PhaseSync.sol` | Phase synchronization |
| 30 | GlobalWorkspace | `contracts/solidity/aether/GlobalWorkspace.sol` | Broadcasting mechanism |
| 31 | SynapticStaking | `contracts/solidity/aether/SynapticStaking.sol` | Neural connection staking |
| 32 | GasOracle | `contracts/solidity/aether/GasOracle.sol` | Dynamic gas pricing |
| 33 | TreasuryDAO | `contracts/solidity/aether/TreasuryDAO.sol` | Community governance |
| 34 | HiggsField | `contracts/solidity/aether/HiggsField.sol` | Higgs cognitive mass mechanism |

#### Tier 6: Safety

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 35 | ConstitutionalAI | `contracts/solidity/aether/ConstitutionalAI.sol` | Value enforcement |
| 36 | EmergencyShutdown | `contracts/solidity/aether/EmergencyShutdown.sol` | Kill switch |
| 37 | UpgradeGovernor | `contracts/solidity/aether/UpgradeGovernor.sol` | Protocol upgrades |

#### Tier 7: 10 Sephirot Nodes

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 38 | SephirahKeter | `contracts/solidity/aether/sephirot/SephirahKeter.sol` | Meta-learning, goals |
| 39 | SephirahChochmah | `contracts/solidity/aether/sephirot/SephirahChochmah.sol` | Intuition |
| 40 | SephirahBinah | `contracts/solidity/aether/sephirot/SephirahBinah.sol` | Logic |
| 41 | SephirahChesed | `contracts/solidity/aether/sephirot/SephirahChesed.sol` | Exploration |
| 42 | SephirahGevurah | `contracts/solidity/aether/sephirot/SephirahGevurah.sol` | Safety |
| 43 | SephirahTiferet | `contracts/solidity/aether/sephirot/SephirahTiferet.sol` | Integration |
| 44 | SephirahNetzach | `contracts/solidity/aether/sephirot/SephirahNetzach.sol` | Learning |
| 45 | SephirahHod | `contracts/solidity/aether/sephirot/SephirahHod.sol` | Language |
| 46 | SephirahYesod | `contracts/solidity/aether/sephirot/SephirahYesod.sol` | Memory |
| 47 | SephirahMalkuth | `contracts/solidity/aether/sephirot/SephirahMalkuth.sol` | Action |

#### Tier 8: Bridge Infrastructure

| # | Contract | File | Purpose |
|---|----------|------|---------|
| 48 | BridgeVault | `contracts/solidity/bridge/BridgeVault.sol` | Lock/unlock vault |
| 49 | wQBC (Bridge) | `contracts/solidity/bridge/wQBC.sol` | Wrapped QBC for external chains |
| 50 | wQUSD | `contracts/solidity/qusd/wQUSD.sol` | Wrapped QUSD (cross-chain) |

### 10.2 How to Deploy Contracts

```bash
# Example: Deploy a template contract via REST
curl -X POST http://localhost:5000/contracts/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "type": "token",
    "code": { "name": "QBC20", "symbol": "QBC", "decimals": 18 },
    "deployer": "YOUR_ADDRESS"
  }'
```

### 10.3 Contract Deployment Checklist

- [ ] Tier 0: 3 interfaces + 3 proxy contracts
- [ ] Tier 1: QBC20, QBC721, QBC1155, ERC20QC, wQBC
- [ ] Tier 2: QUSD stablecoin suite (7 contracts)
- [ ] Tier 3: Aether Core (5 contracts)
- [ ] Tier 4: Proof-of-Thought (4 contracts)
- [ ] Tier 5: Consciousness + Economics + Higgs (7 contracts)
- [ ] Tier 6: Safety (3 contracts)
- [ ] Tier 7: 10 Sephirot nodes registered in NodeRegistry
- [ ] Tier 8: Bridge infrastructure (3 contracts)

**Total: 50 contracts across 9 tiers**

---

## 11. PHASE 9: CREATE QUBITCOIN-NODE PUBLIC REPO

> **Goal:** A public `BlockArtica/Qubitcoin-node` repo containing ONLY the files
> needed to run a QBC node. No frontend, no tests, no docs, no git history.

### 11.1 Use the Setup Script

```bash
bash scripts/setup/create_node_runner_repo.sh /path/to/qubitcoin-node
```

This creates a clean directory with:
- `src/` — Full Python source
- `sql/`, `sql_new/` — Database schemas
- `config/` — Service configuration
- `rust-p2p/` — Rust P2P daemon source
- `scripts/setup/` — Key generation
- Docker files, env templates, README

### 11.2 Push to GitHub

```bash
cd /path/to/qubitcoin-node
git init && git add . && git commit -m "Initial: QBC node runner package"
gh repo create BlockArtica/Qubitcoin-node --public --source=. --push
```

### 11.3 Node Runner Repo Checklist

- [ ] Directory created with all node files
- [ ] README.md with quick-start instructions
- [ ] No frontend, test, doc, or Claude files present
- [ ] Pushed to `BlockArtica/Qubitcoin-node`

---

## 12. PHASE 10: BRIDGE CONTRACTS (OPTIONAL)

> **Bridges are NOT required for initial launch.** The QBC chain operates independently.
> This phase deploys **wQBC** and **wQUSD** wrapped tokens to external chains and
> transfers the initial 3.3B QUSD from deployer to a dedicated treasury address.

Bridge contracts enable cross-chain transfers and are deployed on **external chains**
(not on QBC). Each requires a funded wallet on the target chain.

**Launch targets:** Ethereum, BNB Chain, and Solana. Additional chains (Polygon, Avalanche,
Arbitrum, Optimism, Base) are supported by the deployment tooling and can be added later
as demand warrants — the same script and deployer key work for all EVM chains.

### 12.0 Prerequisites

- [ ] QBC node running and mining (Phases 1-6 complete)
- [ ] 50 smart contracts deployed on QBC (Phase 8 complete)
- [ ] `pip install web3 py-solc-x` (bridge deployment dependencies)
- [ ] Funded wallet on each target chain (ETH and BNB for gas, SOL for Solana)
- [ ] EVM deployer private key (secp256k1) — one key works for all EVM chains

### 12.0a QUSD Treasury Transfer

The QUSD contract mints 3.3B QUSD to `msg.sender` (the deployer) at initialization.
Transfer this supply to a dedicated treasury address:

```bash
# Set treasury address in .env
# QUSD_TREASURY_ADDRESS=<your-treasury-address>

# Transfer (requires running QBC node + QUSD deployed in Phase 8)
python3 scripts/deploy/deploy_bridge.py --qusd-treasury-transfer --skip-bridge
```

- [ ] `QUSD_TREASURY_ADDRESS` set in `.env`
- [ ] 3.3B QUSD transferred from deployer to treasury
- [ ] Verify: `curl http://localhost:5000/qvm/account/<treasury-address>`

### 12.1 Configure Bridge Environment Variables

Add external chain RPC URLs and deployer keys:

```bash
# In .env — external chain RPC endpoints
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
BSC_RPC_URL=https://bsc-dataseed1.binance.org
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
# Optional: BRIDGE_OPERATOR_ADDRESS (defaults to deployer)

# In secure_key.env — deployer private keys (NEVER in .env)
ETH_DEPLOYER_PRIVATE_KEY=0x<your-secp256k1-private-key>
SOLANA_DEPLOYER_KEYPAIR_PATH=/path/to/keypair.json
```

- [ ] `ETH_RPC_URL` configured (Alchemy/Infura recommended)
- [ ] `BSC_RPC_URL` configured
- [ ] `ETH_DEPLOYER_PRIVATE_KEY` in `secure_key.env`
- [ ] `SOLANA_DEPLOYER_KEYPAIR_PATH` in `secure_key.env` (if deploying to Solana)
- [ ] Deployer wallet funded on target chains

### 12.2 Dry Run Validation

```bash
# Compile contracts + check balances without spending gas
python3 scripts/deploy/deploy_bridge.py --chains ethereum,bsc --dry-run
```

This will:
1. Install solc 0.8.28 (if not present)
2. Flatten and compile `wQBC.sol` and `wQUSD.sol`
3. Cache artifacts to `deployment/crosschain/artifacts/`
4. Connect to each chain and verify deployer balance
5. Report what would be deployed (no transactions sent)

- [ ] Dry run completes without errors
- [ ] Both contracts compile successfully
- [ ] Deployer has sufficient gas on target chains

### 12.3 Deploy to Ethereum + BNB Chain

```bash
# Deploy wQBC + wQUSD to Ethereum and BSC
python3 scripts/deploy/deploy_bridge.py --chains ethereum,bsc
```

For each chain, the script:
1. Deploys wQBC contract → calls `initialize(bridge_operator)`
2. Deploys wQUSD contract → calls `initialize(address(0), bridge_operator)`
3. Saves addresses to `contract_registry.json` under `external:{chain}:wQBC`

**Estimated deployment costs (launch chains):**

| Chain | Token Standard | Est. Deploy Cost |
|-------|---------------|-----------------|
| Ethereum | wQBC + wQUSD ERC-20 | ~$100-400 |
| BNB Chain | wQBC + wQUSD BEP-20 | ~$10-40 |

- [ ] wQBC deployed on Ethereum (address in registry)
- [ ] wQUSD deployed on Ethereum (address in registry)
- [ ] wQBC deployed on BSC (address in registry)
- [ ] wQUSD deployed on BSC (address in registry)

### 12.4 Deploy to Solana

Requires Anchor CLI (`anchor`) and Solana CLI (`solana`):

```bash
# Generate keypair if needed
solana-keygen new --outfile ~/.config/solana/bridge-deployer.json

# Set in secure_key.env
# SOLANA_DEPLOYER_KEYPAIR_PATH=/home/user/.config/solana/bridge-deployer.json

python3 scripts/deploy/deploy_bridge.py --chains solana
```

> **Note:** Solana deployment requires Anchor project scaffolds in
> `deployment/solana/wqbc/` and `deployment/solana/wqusd/`. These must be created
> separately using `anchor init`.

- [ ] Solana keypair generated and funded (~2 SOL)
- [ ] `SOLANA_DEPLOYER_KEYPAIR_PATH` in `secure_key.env`
- [ ] wQBC SPL program deployed (program ID in registry)
- [ ] wQUSD SPL program deployed (program ID in registry)

### 12.5 Future Chains (Post-Launch)

The following chains are supported by the deployment script and `deploy.json` but
are **not part of the initial launch**. Deploy when there is user demand:

```bash
# Example: add Polygon and Arbitrum later
python3 scripts/deploy/deploy_bridge.py --chains polygon,arbitrum
```

| Chain | Chain ID | Status |
|-------|----------|--------|
| Polygon | 137 | Deploy when needed |
| Avalanche | 43114 | Deploy when needed |
| Arbitrum | 42161 | Deploy when needed |
| Optimism | 10 | Deploy when needed |
| Base | 8453 | Deploy when needed |

The same `ETH_DEPLOYER_PRIVATE_KEY` works for all EVM chains. Just add the
chain's RPC URL to `.env` (e.g. `POLYGON_RPC_URL=...`) and run the script.

### 12.6 Register Bridge Addresses in QBC Node

After external deployment, register the bridge contract addresses so the QBC node's
BridgeManager knows where wrapped tokens live:

```bash
# Update .env with external chain contract addresses
# (addresses are in contract_registry.json under external:* keys)

# Restart node to pick up new config
docker compose restart qbc-node
```

- [ ] External bridge addresses registered in QBC node config
- [ ] BridgeManager shows active bridges: `curl http://localhost:5000/bridge/stats`

### 12.7 Configure Bridge Relayer

The bridge relayer watches for lock events on QBC and mint events on external chains:

```bash
# Fund relayer wallets on each external chain
# Relayer needs gas to call bridgeMint() / bridgeBurn()

# Verify relayer can sign transactions on target chains
# Relayer address should be set as bridge operator or added to BridgeVault
```

- [ ] Relayer wallets funded on all launch chains (ETH, BNB, Solana)
- [ ] Relayer registered in BridgeVault as authorized relayer
- [ ] Relayer process running and monitoring both chains

### 12.8 End-to-End Bridge Test

```bash
# 1. Lock QBC on QBC chain (creates deposit in BridgeVault)
curl -X POST http://localhost:5000/bridge/deposit \
  -H "Content-Type: application/json" \
  -d '{"target_chain": 1, "target_address": "0xYourEthAddress", "amount": 10}'

# 2. Verify wQBC minted on Ethereum
# (relayer picks up deposit event and calls wQBC.mint() on ETH)

# 3. Burn wQBC on Ethereum → Unlock QBC on QBC chain
# (relayer picks up burn event and confirms withdrawal on QBC)

# 4. Verify QBC unlocked
curl http://localhost:5000/balance/<your-address>
```

- [ ] Lock QBC → Mint wQBC on Ethereum works
- [ ] Burn wQBC on Ethereum → Unlock QBC works
- [ ] Round-trip completes within expected time (~5 min for ETH confirmations)

### 12.9 Bridge Deployment Checklist (Complete)

- [ ] **Prerequisites:** web3 + py-solc-x installed, wallets funded
- [ ] **QUSD Treasury:** 3.3B QUSD transferred to dedicated treasury address
- [ ] **Dry Run:** Compilation and balance checks pass
- [ ] **ETH Deploy:** wQBC + wQUSD live on Ethereum
- [ ] **BSC Deploy:** wQBC + wQUSD live on BNB Chain
- [ ] **Solana Deploy:** wQBC + wQUSD Anchor programs deployed
- [ ] **Node Config:** Bridge addresses registered in QBC node
- [ ] **Relayer:** Bridge relayer running and funded
- [ ] **E2E Test:** Lock QBC → Mint wQBC → Burn wQBC → Unlock QBC
- [ ] **contract_registry.json** updated with all `external:*` entries
- [ ] **Future chains:** Polygon, Avalanche, Arbitrum, Optimism, Base — deploy later as needed

---

## 13. WALLET GUIDE

### 13.1 Native Dilithium Wallet (Mining & L1 Transactions)

The native wallet uses Dilithium2 post-quantum signatures. This is what mining rewards go to.

> **Launch Note:** At launch, L1 transactions are sent via the node's RPC endpoints (CLI / curl)
> using server-side Dilithium2 signing. The frontend native wallet page (`/wallet`) can display
> balances and UTXOs but **cannot send transactions from the browser** — see
> [Section 14: Known Limitations](#14-known-limitations-at-launch) for details.

```bash
# Generate a new wallet
python3 scripts/setup/generate_keys.py
# Output: secure_key.env with ADDRESS, PUBLIC_KEY_HEX, PRIVATE_KEY_HEX

# Check balance
curl http://localhost:5000/balance/<YOUR_ADDRESS>

# List UTXOs
curl http://localhost:5000/utxos/<YOUR_ADDRESS>

# Send QBC (via RPC)
curl -X POST http://localhost:5000/transaction/send \
  -H "Content-Type: application/json" \
  -d '{
    "from_address": "<YOUR_ADDRESS>",
    "to_address": "<RECIPIENT_ADDRESS>",
    "amount": 100.0
  }'
```

**When to use:** Mining rewards, L1 UTXO transactions, node operations.

### 13.2 MetaMask / EVM Wallet (QVM & Smart Contracts)

MetaMask connects via the JSON-RPC interface for QVM (Layer 2) interactions.

**Add Qubitcoin Network to MetaMask:**

| Setting | Value |
|---------|-------|
| Network Name | Qubitcoin |
| RPC URL | `https://api.qbc.network` (production) or `http://localhost:5000` (local) |
| Chain ID | 3301 (hex: 0xCE5) |
| Currency Symbol | QBC |
| Block Explorer | `https://qbc.network/explorer` |

Or click "Connect Wallet" on the qbc.network frontend — it auto-prompts MetaMask to add the network.

**When to use:** QVM smart contract interaction, QBC-20 token transfers, DeFi, NFTs.

### 13.3 Which Wallet For What?

| Action | Wallet |
|--------|--------|
| Mining rewards | Native (Dilithium) — automatic |
| Send QBC (L1) | Native (Dilithium) via RPC |
| Deploy contracts | MetaMask (EVM) |
| QBC-20 token transfers | MetaMask (EVM) |
| Aether Tree chat | Either (fees deducted from balance) |
| Bridge to Ethereum | MetaMask (EVM) |

---

## 14. KNOWN LIMITATIONS AT LAUNCH

These are documented architectural items that do not block launch. Each has a clear
post-launch resolution path.

### 14.1 Dilithium2 WASM Signing (Frontend Native Wallet)

**What:** The frontend native wallet page (`/wallet`) cannot send L1 transactions from the
browser. The file `frontend/src/lib/dilithium.ts` contains a placeholder HMAC-SHA256 signing
function instead of real Dilithium2 post-quantum signing.

**Why:** Dilithium2 signing requires a WASM build of liboqs or dilithium-py. No production-ready
Dilithium2 WASM module exists yet for browsers. The placeholder generates a fake "signature" that
fails real Dilithium2 verification on the backend — so no invalid transactions can be created.

**Impact at launch:**

| Feature | Status | Notes |
|---------|--------|-------|
| MetaMask wallet (QVM/L2) | **Works** | Primary user flow. All signing handled by MetaMask. |
| Mining rewards | **Works** | Coinbase transactions require no user signing. |
| L1 send via CLI/curl | **Works** | `POST /wallet/send` with real Dilithium sig from `secure_key.env`. |
| L1 send via RPC (programmatic) | **Works** | `POST /wallet/sign` (localhost only) + `POST /wallet/send`. |
| Frontend `/wallet` — view balance | **Works** | Read-only queries don't need signing. |
| Frontend `/wallet` — send QBC | **Blocked** | Placeholder signature fails backend verification. |
| Frontend Sephirot launcher | **Blocked** | Same placeholder signing issue. |
| Smart contract deployment | **Works** | Done via MetaMask or `scripts/deploy/deploy_contracts.py`. |

**Resolution (post-launch):**
1. Build Dilithium2 as a WASM module (from [liboqs](https://github.com/nicoburniske/pqc-wasm) or
   [dilithium-wasm](https://github.com/nicoburniske/dilithium-wasm))
2. Replace the internals of `placeholderSignTransaction()` in `frontend/src/lib/dilithium.ts`
   — the function signature stays the same, only the signing primitive changes
3. Add client-side key generation so `/wallet/create` can return a full keypair in-browser
4. No backend changes needed — the node already validates real Dilithium2 signatures

**Priority:** Medium. The primary user flow (MetaMask) is unaffected. This only blocks the
native QBC wallet send feature in the browser UI.

### 14.2 WASM Build for Substrate Node

**What:** The Substrate hybrid node (`substrate-node/`) builds natively with
`SKIP_WASM_BUILD=1` but the WASM runtime build is deferred.

**Why:** Upstream `serde_core` v1.0.218+ introduces a duplicate `exchange_malloc` lang item
in WASM targets. This is a known Rust ecosystem issue affecting all Substrate projects.

**Impact at launch:** None. The Python L1 node is the production node. The Substrate node is
the migration target for a future release.

**Resolution:** Wait for upstream serde fix or use `substrate-wasm-builder` workaround.

---

## 15. PORT REFERENCE

### Local Development (docker-compose.yml)

| Port | Service | URL | Purpose |
|------|---------|-----|---------|
| **3000** | Frontend | http://localhost:3000 | Next.js dev server |
| **5000** | QBC Node RPC | http://localhost:5000 | REST + JSON-RPC API |
| **8080** | CockroachDB UI | http://localhost:8080 | Database admin |
| **3001** | Grafana | http://localhost:3001 | Metrics dashboards |
| **9090** | Prometheus | http://localhost:9090 | Raw metrics |
| **4001** | IPFS P2P | - | Content network (swarm) |
| **5002** | IPFS API | http://localhost:5002 | IPFS HTTP API |
| **8081** | IPFS Gateway | http://localhost:8081 | Content retrieval |
| **6379** | Redis | - | Cache (internal) |
| **26257** | CockroachDB SQL | - | Database (internal) |
| **50051** | Rust P2P gRPC | - | P2P bridge (internal) |
| **3100** | Loki | - | Log aggregation |

### Production (docker-compose.production.yml)

| Port | Service | URL | Purpose |
|------|---------|-----|---------|
| **443** | Nginx | https://api.qbc.network | SSL-terminated API |
| **80** | Nginx | http://api.qbc.network | Redirects to HTTPS |
| **4001** | P2P | - | Peer-to-peer networking |
| **50051** | gRPC | - | P2P bridge |

All other ports (CockroachDB, Redis, IPFS, Prometheus, Loki) are **internal only** in production.
Grafana is bound to `127.0.0.1:3001` — access via SSH tunnel: `ssh -L 3001:localhost:3001 root@<ip>`.

---

## 16. TROUBLESHOOTING

### Node won't start

```bash
docker compose logs qbc-node --tail 100

# Common issues:
# "secure_key.env not found" → Run: python3 scripts/setup/generate_keys.py
# "Connection refused: cockroachdb:26257" → DB not ready yet, wait 30s
# "IPFS connection failed" → Check: docker compose logs ipfs
```

### No blocks being mined

```bash
curl http://localhost:5000/mining/stats
grep AUTO_MINE .env  # Should be: AUTO_MINE=true

# Manually start mining
curl -X POST http://localhost:5000/mining/start
```

### Peer won't connect

```bash
# On the CONNECTING node:
curl http://localhost:5000/p2p/peers
curl http://localhost:5000/p2p/stats

# Verify PEER_SEEDS in .env
grep PEER_SEEDS .env  # Should be: PEER_SEEDS=<seed-ip>:4001

# Verify firewall on seed node allows port 4001
# From local machine:
nc -zv <seed-ip> 4001   # Should say "Connection succeeded"

# If connection fails, check seed node firewall:
# ssh root@<seed-ip>
# ufw status  → should show 4001/tcp ALLOW
```

### Chain heights diverging (fork)

```bash
# Compare block hashes at same height
SEED_HASH=$(curl -s https://api.qbc.network/block/100 | python3 -c "import sys,json; print(json.load(sys.stdin).get('hash','')[:16])")
LOCAL_HASH=$(curl -s http://localhost:5000/block/100 | python3 -c "import sys,json; print(json.load(sys.stdin).get('hash','')[:16])")
echo "Seed:  $SEED_HASH"
echo "Local: $LOCAL_HASH"
# If different → fork detected. The shorter chain will reorg to the longer one automatically.
```

### Frontend can't connect to backend

```bash
curl http://localhost:5000/health  # Verify backend is running
# Check NEXT_PUBLIC_RPC_URL in frontend .env
# Check CORS (should allow qbc.network in production)
```

### CockroachDB issues

```bash
# Health check
curl http://localhost:8080/health?ready=1  # Dev only (port exposed)

# In production (port not exposed):
docker exec -it qbc-cockroachdb ./cockroach sql --insecure --host=localhost:26257

# Check tables
docker exec qbc-cockroachdb ./cockroach sql --insecure \
  --host=localhost:26257 --database=qbc -e "SHOW TABLES;"
```

### Reset everything (start fresh)

```bash
# Stop all containers and remove data (DESTRUCTIVE)
docker compose down -v

# Rebuild and restart
docker compose up -d --build
```

---

## 17. ARCHITECTURE DIAGRAM

```
PRODUCTION DEPLOYMENT (2-NODE NETWORK)
═══════════════════════════════════════════════════════════════════

 Users / Web                         Vercel CDN
┌──────────────┐                   ┌──────────────┐
│ Browser      │──── HTTPS ────────│ qbc.network  │
│ MetaMask     │                   │ (Frontend)   │
└──────┬───────┘                   └──────────────┘
       │
       │ HTTPS (api.qbc.network)
       ▼
 NODE 1: DIGITAL OCEAN DROPLET
┌─────────────────────────────────────────────────────────────┐
│  Nginx (:443)                                               │
│    ├─ SSL termination (Let's Encrypt)                       │
│    ├─ Rate limiting (60 req/s)                              │
│    └─ Proxy → QBC Node (:5000)                              │
│                                                             │
│  QBC Node (:5000 RPC, :4001 P2P, :50051 gRPC)              │
│    ├─ 22 components (consensus, mining, QVM, Aether...)     │
│    ├─ Mining: VQE on local Qiskit simulator                 │
│    └─ Genesis block miner + public API                      │
│                                                             │
│  CockroachDB (:26257 internal) — blockchain state           │
│  IPFS (:5001 internal) — content storage                    │
│  Redis (:6379 internal) — caching                           │
│  Prometheus → Grafana (:3001 localhost) — monitoring        │
│  Loki + Promtail — log aggregation                          │
└──────────────────────────┬──────────────────────────────────┘
                           │ P2P (:4001)
                           │ Block/tx propagation
                           ▼
 NODE 2: LOCAL MACHINE
┌─────────────────────────────────────────────────────────────┐
│  QBC Node (:5000, :4001, :50051)                            │
│    ├─ Syncs chain from Node 1                               │
│    ├─ Mines independently                                   │
│    └─ Validates all blocks                                  │
│                                                             │
│  CockroachDB + IPFS + Redis (local Docker)                  │
└─────────────────────────────────────────────────────────────┘

TIMELINE:
  T+0:00   Node 1 starts on Digital Ocean
  T+2:00   Block 0 mined (genesis) — 33M premine + 15.27 reward
  T+2:01   Aether Tree genesis — 4 knowledge nodes, Phi=0.0
  T+5:00   Node 2 connects, syncs chain from Node 1
  T+5:30   Both nodes mining, blocks propagating
  T+10:00  Frontend deployed to Vercel
  T+30:00  Smart contracts deployed (50 contracts in 9 tiers)
```

---

## LAUNCH SEQUENCE SUMMARY

```
PHASE 1:  Prerequisites              [~5 min]   Docker, Python, Git
PHASE 2:  Generate Node Identity     [~2 min]   Keys + .env
PHASE 3:  Launch Seed Node (DO)      [~15 min]  Droplet + Docker + SSL → MINING STARTS
PHASE 4:  Verify Genesis             [~2 min]   Confirm blocks, balance, Aether
PHASE 5:  Launch Local Mining Node   [~5 min]   Connect as peer → 2-NODE NETWORK
PHASE 6:  Verify 2-Node Network      [~2 min]   Sync, propagation, both mining
PHASE 7:  Deploy Frontend (Vercel)   [~5 min]   qbc.network live
PHASE 8:  Deploy Smart Contracts     [~45 min]  50 contracts in 9 tiers
PHASE 9:  Create Node Runner Repo    [~10 min]  BlockArtica/Qubitcoin-node
PHASE 10: Bridge Contracts           [Optional] Deploy wQBC/wQUSD to ETH, BNB, Solana
```

**Minimum viable launch: Phase 1 → Phase 3. ~20 minutes to first block.**

**Full production with 2 nodes: Phase 1 → Phase 6. ~30 minutes.**

**Everything including frontend and contracts: All phases. ~1.5 hours.**

---

**Document Version:** 3.2
**Created:** February 20, 2026
**Updated:** March 2, 2026
**Website:** [qbc.network](https://qbc.network) | **Contact:** info@qbc.network
