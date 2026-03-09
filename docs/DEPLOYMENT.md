# Quantum Blockchain Deployment Guide

Production deployment for Quantum Blockchain nodes, from single-node development to multi-node mainnet.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Docker Deployment](#docker-deployment)
  - [Rust Services in the Docker Build](#rust-services-in-the-docker-build)
  - [Stratum Mining Server](#stratum-mining-server)
  - [Competitive Features Configuration](#competitive-features-configuration)
- [Production Deployment (Digital Ocean)](#production-deployment-digital-ocean)
- [2-Node Peer Setup](#2-node-peer-setup)
- [Frontend Deployment (Vercel)](#frontend-deployment-vercel)
- [Bare-Metal Deployment](#bare-metal-deployment)
- [Monitoring](#monitoring)
- [Backup & Restore](#backup--restore)
- [Security Checklist](#security-checklist)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Minimum Requirements

| Component | Development | Production (Seed Node) |
|-----------|-------------|------------------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| Storage | 20 GB | 320+ GB SSD |
| Network | Any | 10 Gbps (DO included) |
| Python | 3.12+ | 3.12+ (in Docker) |
| Docker | 24+ | 24+ |

### One-Command Local Dev

```bash
git clone https://github.com/BlockArtica/Qubitcoin.git && cd Qubitcoin
pip install -r requirements.txt
python3 scripts/setup/generate_keys.py
cp .env.example .env
docker compose up -d
# Mining starts automatically — genesis block in ~2 minutes
```

### One-Command Production

```bash
git clone https://github.com/BlockArtica/Qubitcoin.git && cd Qubitcoin
pip install -r requirements.txt
python3 scripts/setup/generate_keys.py
cp .env.production.example .env
# Edit .env (set treasury addresses, Grafana password)
docker compose -f docker-compose.production.yml up -d --build
```

---

## Architecture

```
PRODUCTION ARCHITECTURE
═══════════════════════════════════════════════════════════════

                    ┌──────────────┐
                    │   Vercel     │  ← Frontend (qbc.network)
                    │   (CDN)      │
                    └──────┬───────┘
                           │ HTTPS
                    ┌──────▼───────┐
                    │  Nginx       │  ← SSL termination + rate limiting
                    │  :80 / :443  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼────┐ ┌────▼─────┐ ┌───▼────┐
        │ RPC API  │ │ P2P Node │ │ gRPC   │
        │ :5000    │ │ :4001    │ │ :50051 │
        │ (FastAPI)│ │ (libp2p) │ │ (P2P)  │
        └─────┬────┘ └────┬─────┘ └───┬────┘
              │            │            │
        ┌─────▼──────┐ ┌──▼──┐ ┌──────▼──────┐
        │ CockroachDB│ │IPFS │ │    Redis     │
        │ :26257     │ │:5001│ │    :6379     │
        │ (internal) │ │(int)│ │  (internal)  │
        └────────────┘ └─────┘ └──────────────┘

 Monitoring (internal):
   Prometheus :9090 → Grafana :3001 (localhost)
   Promtail → Loki :3100
```

### Port Map

| Port | Service | Dev Compose | Prod Compose | Protocol |
|------|---------|-------------|--------------|----------|
| 80 | Nginx | profile: production | Exposed | HTTP |
| 443 | Nginx | profile: production | Exposed | HTTPS |
| 3000 | Frontend | External (pnpm dev) | Vercel | HTTP |
| 4001 | QBC P2P | Mapped to host 4001 | Exposed | TCP/QUIC |
| 5000 | QBC RPC | Exposed | Exposed (proxied) | HTTP |
| 5001 | IPFS API | Mapped to host 5002 | Internal only | HTTP |
| 6379 | Redis | Exposed | Internal only | TCP |
| 8080 | CRDB Admin | Exposed | Internal only | HTTP |
| 9090 | Prometheus | profile: monitoring | Internal only | HTTP |
| 3001 | Grafana | profile: monitoring | 127.0.0.1 only | HTTP |
| 3100 | Loki | profile: monitoring | Internal only | HTTP |
| 26257 | CRDB SQL | Exposed | Internal only | PostgreSQL |
| 50051 | gRPC P2P | Exposed | Exposed | gRPC |
| 3333 | Stratum Mining Server | Exposed | Exposed | WebSocket |
| 50053 | Stratum gRPC Bridge | Exposed | Internal only | gRPC |

---

## Docker Deployment

### Development (all ports exposed, monitoring optional)

```bash
# Core services only (CockroachDB, IPFS, Redis, QBC Node)
docker compose up -d

# With monitoring (adds Prometheus, Grafana, Loki, Promtail)
docker compose --profile monitoring up -d

# With SSL proxy (adds Nginx, Certbot)
docker compose --profile production up -d

# Everything
docker compose --profile monitoring --profile production up -d
```

### Production (internal-only services, monitoring inline)

```bash
# All services inline — no profiles needed
docker compose -f docker-compose.production.yml up -d --build
```

Production compose differences from dev:
- CockroachDB, Redis, IPFS: **no exposed ports** (internal network only)
- Grafana: bound to `127.0.0.1:3001` (SSH tunnel access only)
- Prometheus retention: 90 days (vs 30 in dev)
- Redis: 256MB memory limit with LRU eviction
- Nginx + Certbot: inline (not behind profile)
- `DEBUG=false` hardcoded in environment
- No Portainer (security risk in production)

### Rust Services in the Docker Build

The Dockerfile uses a multi-stage build with two Rust build stages that produce
distinct artifacts:

**aether-builder stage (security-core PyO3 extension)**

The `aether-builder` stage compiles the `security-core` Rust crate via maturin.
This produces a Python-importable PyO3 extension module (`.so` / `.pyd`) that
provides native-speed implementations of inheritance protocols, security policies,
deniable transactions, and fast-finality verification. The resulting wheel is
installed into the Python virtual environment in the final production image.

```
Stage: aether-builder
  Build tool: maturin (PyO3 extension)
  Output: security_core-*.whl → installed via pip in production image
  Usage: import security_core (transparent fallback to Python if unavailable)
```

**rust-builder stage (stratum-server binary)**

The `rust-builder` stage compiles the `stratum-server` crate as a standalone
binary. This binary provides a Stratum V1/V2 compatible mining server that
bridges external mining pool workers to the Qubitcoin node via gRPC. The
binary is copied into the final production image and launched alongside the
Python node when `STRATUM_ENABLED=true`.

```
Stage: rust-builder
  Build tool: cargo build --release
  Output: stratum-server binary → /usr/local/bin/stratum-server
  Ports: 3333 (WebSocket, Stratum protocol), 50053 (gRPC bridge to node)
  Launch: auto-started by node.py when STRATUM_ENABLED=true
```

Both Rust build stages use `rust:1.85-bookworm` as the base image. The final
production image (`python:3.12-slim-bookworm`) contains only the compiled
artifacts, keeping the image size minimal.

### Build the Node Image Separately

```bash
docker build -t qubitcoin-node .
docker run -p 5000:5000 -p 4001:4001 -p 50051:50051 -p 3333:3333 \
  --env-file .env --env-file secure_key.env \
  qubitcoin-node
```

### Substrate Node (Optional — Future Migration)

The Substrate hybrid node provides a future Rust-native runtime. Not required for initial launch.

```bash
cd substrate-node
SKIP_WASM_BUILD=1 cargo build --release
# Binary at target/release/qubitcoin-node
```

Docker setup for the Substrate node:

```bash
cd substrate-node
docker build -t qubitcoin-substrate .
docker run -p 9944:9944 -p 9933:9933 -p 30333:30333 qubitcoin-substrate
```

> **Note:** Use `SKIP_WASM_BUILD=1` due to an upstream `serde_core` conflict in WASM builds.

### Higgs Cognitive Field Configuration

The Higgs Cognitive Field assigns mass to Sephirot nodes via a mechanism analogous to
the Standard Model Higgs boson. Add these to your `.env`:

```bash
# Higgs Cognitive Field
HIGGS_ENABLE_MASS_REBALANCING=true    # Enable Higgs field mass assignments
HIGGS_VEV=246.0                       # Vacuum expectation value
HIGGS_LAMBDA=0.129                    # Quartic coupling constant
HIGGS_MU_SQUARED=-8000.0              # Mu^2 parameter (negative for SSB)
HIGGS_YUKAWA_SCALE=1.0                # Global Yukawa coupling scale
```

When enabled, the Higgs field initializes automatically at genesis and assigns cognitive
masses to all 10 Sephirot nodes via Yukawa couplings. Expansion nodes couple to H_u,
constraint nodes couple to H_d, and masses follow a golden ratio cascade.

### QUSD Peg Keeper Configuration

The QUSD Peg Keeper daemon monitors wQUSD prices across 8 chains and executes automated
stabilization actions. Add these to your `.env`:

```bash
# QUSD Peg Keeper
KEEPER_ENABLED=true                  # Enable keeper daemon
KEEPER_DEFAULT_MODE=scan             # off | scan | periodic | continuous | aggressive
KEEPER_CHECK_INTERVAL=10             # Blocks between peg checks
KEEPER_MAX_TRADE_SIZE=1000000        # Max QBC per stabilization trade
KEEPER_FLOOR_PRICE=0.99              # Depeg floor trigger ($)
KEEPER_CEILING_PRICE=1.01            # Depeg ceiling trigger ($)
KEEPER_COOLDOWN_BLOCKS=10            # Min blocks between actions
```

**Production recommendation:** Start with `scan` mode (default) to observe market behavior.
Upgrade to `periodic` or `continuous` once QUSD liquidity is established on external DEXs.
Use `aggressive` only during active depeg events. The keeper reads live bridge fees from
`BridgeVault.feeBps()` (default 10 bps) for accurate cross-chain arb profitability calculations.

**Verification:**
```bash
curl http://localhost:5000/keeper/status     # Check daemon status
curl http://localhost:5000/keeper/prices     # View multi-chain DEX prices
curl http://localhost:5000/keeper/arb/summary # Check arbitrage opportunities
```

### Stratum Mining Server

The Stratum Mining Server enables pool mining by providing a standard Stratum V1/V2
endpoint that external miners (ASICs, GPUs, or VQE workers) can connect to. The server
translates Stratum protocol messages into Qubitcoin VQE mining tasks via a gRPC bridge
to the node.

To enable pool mining, add these variables to your `.env`:

```bash
# Stratum Mining Server
STRATUM_ENABLED=true             # Enable the Stratum server (default: false)
STRATUM_PORT=3333                # WebSocket port for miner connections
STRATUM_HOST=0.0.0.0             # Bind address (0.0.0.0 for external access)
STRATUM_MAX_WORKERS=100          # Maximum concurrent mining workers
STRATUM_GRPC_PORT=50053          # gRPC bridge port (node <-> stratum communication)
```

When `STRATUM_ENABLED=true`, the node process auto-launches the `stratum-server` binary
on startup. Miners connect via WebSocket to `ws://<node-ip>:3333` using standard Stratum
credentials. The gRPC bridge on port 50053 handles internal communication between the
stratum-server and the Qubitcoin node -- it should not be exposed to external miners.

**Firewall configuration for pool mining:**
```bash
ufw allow 3333/tcp      # Stratum (miners connect here)
# Do NOT expose 50053 — internal gRPC bridge only
```

**Verification:**
```bash
# Check stratum server status
curl http://localhost:5000/stratum/status

# View connected workers
curl http://localhost:5000/stratum/workers
```

### Competitive Features Configuration

Qubitcoin includes several competitive features implemented in the `security-core` Rust
extension. Each feature is independently configurable via environment variables in `.env`:

**Inheritance Protocol** -- automated QBC transfer to designated heirs after a
configurable inactivity period:

```bash
INHERITANCE_ENABLED=true                 # Enable inheritance protocol (default: false)
INHERITANCE_DEFAULT_INACTIVITY=15780000  # Inactivity threshold in seconds (~6 months)
INHERITANCE_GRACE_PERIOD=2592000         # Grace period after trigger in seconds (~30 days)
```

**Security Policy Engine** -- per-address spending limits, whitelisted destinations,
and time-locked withdrawal policies:

```bash
SECURITY_POLICY_ENABLED=true             # Enable security policies (default: false)
SECURITY_DAILY_LIMIT_WINDOW=86400        # Rolling window for daily limits in seconds
SECURITY_MAX_WHITELIST_SIZE=256          # Maximum whitelist entries per address
```

**Deniable Transactions** -- plausible deniability layer allowing construction of
transactions that appear valid under multiple interpretations:

```bash
DENIABLE_RPC_ENABLED=true                # Enable deniable transaction RPC (default: false)
DENIABLE_RPC_MAX_BATCH=10                # Maximum deniable outputs per transaction
```

**Fast Finality** -- stake-weighted finality gadget providing sub-second economic
finality on top of PoSA consensus:

```bash
FINALITY_ENABLED=true                    # Enable fast-finality gadget (default: false)
FINALITY_MIN_STAKE=1000                  # Minimum QBC stake for finality voting
FINALITY_THRESHOLD=0.67                  # Supermajority threshold (67% of staked QBC)
```

All competitive features default to disabled. Enable them individually based on your
deployment requirements. When the `security-core` Rust extension is not installed, the
node falls back to Python implementations with equivalent functionality.

---

## Production Deployment (Digital Ocean)

### Recommended Droplet

| Setting | Value |
|---------|-------|
| **Plan** | General Purpose |
| **Size** | g-4vcpu-16gb ($96/mo) or g-8vcpu-32gb ($192/mo) |
| **Region** | NYC1, SFO3, or closest to your users |
| **OS** | Ubuntu 24.04 LTS |
| **Features** | Monitoring enabled, SSH key auth |

### Step-by-Step

```bash
# 1. Create droplet
doctl compute droplet create qbc-seed-1 \
  --size g-4vcpu-16gb \
  --image ubuntu-24-04-x64 \
  --region nyc1 \
  --ssh-keys $(doctl compute ssh-key list --format ID --no-header | head -1) \
  --enable-monitoring

# 2. SSH in and set up
ssh root@<droplet-ip>
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
systemctl enable docker
apt install -y python3-pip python3-venv git

# 3. Add swap
fallocate -l 4G /swapfile && chmod 600 /swapfile
mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# 4. Firewall
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp
ufw allow 4001/tcp && ufw allow 50051/tcp
ufw enable

# 5. Clone and configure
git clone https://github.com/BlockArtica/Qubitcoin.git && cd Qubitcoin
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 scripts/setup/generate_keys.py
deactivate
cp .env.production.example .env
# Edit .env: set treasury addresses, Grafana password

# 6. Launch
docker compose -f docker-compose.production.yml up -d --build

# 7. Verify
curl http://localhost:5000/health
docker compose -f docker-compose.production.yml logs -f qbc-node
```

### DNS Setup

| Record | Type | Value | Purpose |
|--------|------|-------|---------|
| `api.qbc.network` | A | `<droplet-ip>` | Backend RPC API |
| `seed1.qbc.network` | A | `<droplet-ip>` | P2P seed address |
| `qbc.network` | CNAME | `cname.vercel-dns.com` | Frontend |
| `www.qbc.network` | CNAME | `cname.vercel-dns.com` | WWW redirect |

### SSL Certificate

After DNS propagates (check with `dig api.qbc.network`):

```bash
# Option A: Via Docker certbot
docker compose -f docker-compose.production.yml exec certbot \
  certbot certonly --webroot -w /var/www/certbot \
  -d api.qbc.network --email info@qbc.network \
  --agree-tos --no-eff-email

docker compose -f docker-compose.production.yml restart nginx

# Option B: Host-level certbot (simpler for initial setup)
apt install -y certbot
certbot certonly --standalone -d api.qbc.network --email info@qbc.network --agree-tos
# Then mount cert paths into the nginx container
```

---

## 2-Node Peer Setup

### Configure the Mining Node to Connect to Seed

On the second node (e.g., your local machine), set `PEER_SEEDS` in `.env`:

```bash
# .env on the mining node
PEER_SEEDS=<seed-node-ip>:4001
# Or use DNS:
PEER_SEEDS=seed1.qbc.network:4001
```

### Verify Peer Connection

```bash
# On the connecting node
curl http://localhost:5000/p2p/peers
# Expected: [{"peer_id": "...", "address": "<seed-ip>:4001", ...}]

curl http://localhost:5000/p2p/stats
# Expected: {"connected_peers": 1, ...}
```

### Firewall Requirements

The **seed node** must allow inbound connections:

```bash
# On the seed node (DO droplet)
ufw allow 4001/tcp     # P2P
ufw allow 50051/tcp    # gRPC bridge
```

The **mining node** (local) needs no special firewall rules — it initiates the outbound connection.

### Multiple Peers

For 3+ node networks, each node should know about multiple seeds:

```bash
PEER_SEEDS=seed1.qbc.network:4001,seed2.qbc.network:4001
```

Nodes discover additional peers via gossip after connecting to any seed.

---

## Frontend Deployment (Vercel)

### Environment Variables (Vercel Dashboard)

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_RPC_URL` | `https://api.qbc.network` |
| `NEXT_PUBLIC_WS_URL` | `wss://api.qbc.network/ws` |
| `NEXT_PUBLIC_CHAIN_ID` | `3303` |
| `NEXT_PUBLIC_CHAIN_NAME` | `Quantum Blockchain` |
| `NEXT_PUBLIC_CHAIN_SYMBOL` | `QBC` |

### Deploy

1. Connect the GitHub repo to Vercel
2. Set root directory to `frontend`
3. Add environment variables above
4. Push to `main` → auto-deploy

Or via CLI:
```bash
cd frontend && pnpm install && npx vercel --prod
```

---

## Bare-Metal Deployment

For deployments without Docker.

### systemd Service File

```ini
# /etc/systemd/system/qubitcoin.service
[Unit]
Description=Qubitcoin Node
After=network.target cockroachdb.service
Wants=cockroachdb.service

[Service]
Type=simple
User=qbc
Group=qbc
WorkingDirectory=/opt/qubitcoin/src
ExecStart=/opt/qubitcoin/venv/bin/python3 run_node.py
Restart=always
RestartSec=5
EnvironmentFile=/opt/qubitcoin/.env
EnvironmentFile=/opt/qubitcoin/secure_key.env

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/qubitcoin/data /opt/qubitcoin/logs
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
# Install
sudo cp qubitcoin.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable qubitcoin
sudo systemctl start qubitcoin

# Check status
sudo systemctl status qubitcoin
sudo journalctl -u qubitcoin -f
```

### Bare-Metal Prerequisites

```bash
# CockroachDB
curl https://binaries.cockroachdb.com/cockroach-v25.2.12.linux-amd64.tgz | tar xz
sudo mv cockroach-v25.2.12.linux-amd64/cockroach /usr/local/bin/
cockroach start-single-node --insecure --store=/var/lib/cockroach --background

# IPFS
wget https://dist.ipfs.tech/kubo/v0.30.0/kubo_v0.30.0_linux-amd64.tar.gz
tar xzf kubo_v0.30.0_linux-amd64.tar.gz
sudo mv kubo/ipfs /usr/local/bin/
ipfs init && ipfs daemon &

# Redis
sudo apt install redis-server
sudo systemctl enable redis-server

# Python app
cd /opt/qubitcoin
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

---

## Monitoring

### Prometheus Metrics

The node exposes 77 Prometheus metrics at `/metrics`:

```bash
curl http://localhost:5000/metrics
```

Key metrics:
- `qbc_blocks_mined_total` — blocks mined by this node
- `qbc_current_height` — current chain height
- `qbc_active_peers` — connected peer count
- `qbc_phi_current` — Aether Tree Phi value
- `qbc_total_contracts` — deployed QVM contracts
- `qbc_total_supply` — total QBC in circulation

### Grafana Access

**Development:** http://localhost:3001 (admin / qbc_grafana_change_me)

**Production:** SSH tunnel required (Grafana only listens on 127.0.0.1):
```bash
ssh -L 3001:localhost:3001 root@<droplet-ip>
# Then open http://localhost:3001 in your browser
```

### Health Checks

```bash
curl http://localhost:5000/health         # Node health
curl http://localhost:5000/chain/info     # Chain status
curl http://localhost:5000/mining/stats   # Mining status
curl http://localhost:5000/p2p/stats      # P2P status
curl http://localhost:5000/aether/phi     # AGI consciousness
```

---

## Backup & Restore

### CockroachDB Backup

```bash
# Create backup (development — port exposed)
docker exec qbc-cockroachdb ./cockroach dump qbc --insecure \
  --host=localhost:26257 > backup_$(date +%Y%m%d).sql

# Create backup (production — port not exposed)
docker exec qbc-cockroachdb ./cockroach dump qbc --insecure > backup_$(date +%Y%m%d).sql

# Automated daily backup via cron
echo '0 3 * * * docker exec qbc-cockroachdb ./cockroach dump qbc --insecure > /backups/qbc_$(date +\%Y\%m\%d).sql' | crontab -
```

### Volume Backup

```bash
# Stop services
docker compose -f docker-compose.production.yml stop

# Backup all volumes
for vol in cockroach-data ipfs-data redis-data node-data node-logs; do
  docker run --rm -v qubitcoin_${vol}:/data -v /backups:/backup alpine \
    tar czf /backup/${vol}_$(date +%Y%m%d).tar.gz -C /data .
done

# Restart services
docker compose -f docker-compose.production.yml start
```

### Restore from Backup

```bash
# Stop and remove volumes
docker compose -f docker-compose.production.yml down -v

# Restore volumes
for vol in cockroach-data ipfs-data redis-data node-data node-logs; do
  docker volume create qubitcoin_${vol}
  docker run --rm -v qubitcoin_${vol}:/data -v /backups:/backup alpine \
    tar xzf /backup/${vol}_YYYYMMDD.tar.gz -C /data
done

# Restart
docker compose -f docker-compose.production.yml up -d
```

---

## Security Checklist

### Production Hardening

- [ ] `secure_key.env` permissions: `chmod 600 secure_key.env`
- [ ] `.env` has `DEBUG=false`
- [ ] Firewall allows ONLY: 22 (SSH), 80 (HTTP), 443 (HTTPS), 4001 (P2P), 50051 (gRPC), 3333 (Stratum, if pool mining enabled)
- [ ] CockroachDB NOT exposed to public internet
- [ ] Redis NOT exposed to public internet
- [ ] IPFS API NOT exposed to public internet
- [ ] Grafana password changed from default
- [ ] Grafana bound to 127.0.0.1 only (SSH tunnel access)
- [ ] SSL certificate installed and auto-renewing
- [ ] CORS restricted to `qbc.network` domain
- [ ] Rate limiting active in Nginx (60 req/s API, 30 req/s RPC)
- [ ] `/metrics` and `/admin/` restricted to internal IPs
- [ ] SSH key-only auth (password auth disabled)
- [ ] Automatic security updates enabled (`unattended-upgrades`)
- [ ] Backup strategy configured and tested

### Node Types

| Type | Use Case | Hardware | Config |
|------|----------|----------|--------|
| **Seed Node** | Genesis miner, public RPC, peer hub | 16GB RAM, 320GB SSD | `AUTO_MINE=true` |
| **Mining Node** | Block production, chain validation | 8-16GB RAM, 50GB+ SSD | `AUTO_MINE=true`, `PEER_SEEDS=seed:4001` |
| **Full Node** | RPC only, no mining | 8GB RAM, 50GB+ SSD | `AUTO_MINE=false`, `PEER_SEEDS=seed:4001` |
| **Light Node** | SPV verification, mobile/embedded | 2GB RAM, 1GB | SPV mode |

---

## Bridge Confirmation Thresholds

### Why 20 Confirmations for Bridge Finality

Standard QBC transactions are considered final after **6 confirmations** (~20 seconds at 3.3s/block). Bridge transfers, however, require **20 confirmations** (~66 seconds) on the QBC side before the bridge operator mints wQBC on the destination chain.

The higher threshold exists because bridge operations involve cross-chain state: once wQBC is minted on an external chain, reversing the operation (e.g., due to a QBC reorg) would require burning already-distributed tokens on a chain outside QBC's control. The 20-confirmation requirement reduces reorg risk to near zero, protecting both the bridge operator and liquidity providers.

### Per-Chain Confirmation Requirements

Each external chain has its own confirmation requirement before the bridge operator considers a burn/lock event final on that chain. These are set based on each chain's block time, finality mechanism, and historical reorg depth:

| Chain | Confirmations | Approximate Time | Finality Model |
|-------|---------------|-------------------|----------------|
| **QBC (source)** | 20 | ~66 seconds | PoSA (VQE mining) |
| **Ethereum** | 12 | ~2.5 minutes | PoS (Casper FFG) |
| **BNB Smart Chain** | 15 | ~45 seconds | PoSA (21 validators) |
| **Polygon** | 128 | ~4.3 minutes | PoS + Heimdall checkpoints |
| **Avalanche** | 1 | ~2 seconds | Snowman consensus (instant finality) |
| **Arbitrum** | 1 | ~250ms | L2 sequencer (L1 finality via challenge) |
| **Optimism** | 1 | ~2 seconds | L2 sequencer (L1 finality via challenge) |
| **Base** | 1 | ~2 seconds | L2 sequencer (L1 finality via challenge) |
| **Solana** | 32 slots | ~13 seconds | Tower BFT (slot-based) |

**Notes:**
- L2 chains (Arbitrum, Optimism, Base) have fast sequencer confirmations but full L1 finality takes ~7 days via the challenge period. The bridge uses sequencer confirmations for speed, accepting the small risk.
- Avalanche achieves sub-second finality via its Snowman consensus protocol, so 1 confirmation is sufficient.
- Polygon requires more confirmations because its PoS chain has experienced reorgs. Full security comes from Heimdall checkpoints to Ethereum L1.
- Solana uses slot-based finality; 32 slots provides a strong guarantee under its Tower BFT model.

### Configuration

Bridge confirmation thresholds are set in the bridge operator configuration and are not user-adjustable. They are defined per-chain in the bridge manager:

```python
BRIDGE_CONFIRMATIONS = {
    "qbc": 20,       # QBC source chain
    "ethereum": 12,
    "bsc": 15,
    "polygon": 128,
    "avalanche": 1,
    "arbitrum": 1,
    "optimism": 1,
    "base": 1,
    "solana": 32,
}
```

The bridge operator monitors events on each chain and only processes bridge operations after the required number of confirmations have passed. If a reorg occurs before confirmation, the operation is requeued automatically.

---

## Troubleshooting

### Node won't start
```bash
docker compose logs qbc-node --tail 100
# "secure_key.env not found" → Run: python3 scripts/setup/generate_keys.py
# "Connection refused: cockroachdb" → DB not ready, wait 30s
# "IPFS connection failed" → Check: docker compose logs ipfs
```

### No blocks being mined
```bash
curl http://localhost:5000/mining/stats
grep AUTO_MINE .env  # Must be AUTO_MINE=true
curl -X POST http://localhost:5000/mining/start  # Manual start
```

### Peer connection failures
```bash
curl http://localhost:5000/p2p/stats
nc -zv <seed-ip> 4001  # Test port connectivity
# Check: ufw status on seed node
# Check: PEER_SEEDS in .env on connecting node
```

### Port conflicts
```
CockroachDB admin (8080) and IPFS gateway (8080) — resolved in Docker compose (IPFS mapped to 8081).
IPFS swarm (4001) and QBC P2P (4001) — in dev compose, QBC P2P mapped to host 4002.
In production, IPFS ports are internal only, no conflict.
```

### SSL certificate issues
```bash
# Check cert status
docker exec qbc-certbot certbot certificates

# Force renewal
docker exec qbc-certbot certbot renew --force-renewal
docker compose -f docker-compose.production.yml restart nginx
```

---

**Website:** [qbc.network](https://qbc.network) | **Contact:** info@qbc.network | **GitHub:** [BlockArtica/Qubitcoin](https://github.com/BlockArtica/Qubitcoin)

*For the complete launch checklist, see `LAUNCHTODO.md`. For architecture details, see `CLAUDE.md`.*
