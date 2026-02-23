# Qubitcoin Deployment Guide

This guide covers deploying Qubitcoin in development, staging, and production environments.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Backend Deployment](#backend-deployment)
- [Frontend Deployment](#frontend-deployment)
- [Docker Deployment](#docker-deployment)
- [Production Deployment](#production-deployment)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Minimum Requirements

| Component | Development | Production |
|-----------|-------------|------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| Storage | 50 GB | 500+ GB |
| Network | 10 Mbps | 100+ Mbps |
| Python | 3.12+ | 3.12+ |
| Node.js | 20+ | 20+ (build only) |

### One-Command Dev Setup

```bash
# Clone and setup
git clone https://github.com/BlockArtica/Qubitcoin.git
cd Qubitcoin

# Backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 scripts/setup/generate_keys.py
cp .env.example .env

# Frontend
cd frontend && pnpm install && cd ..

# Start
cd src && python3 run_node.py
```

---

## Architecture

```
                    ┌──────────────┐
                    │   Vercel     │  ← Frontend (qbc.network)
                    │   (CDN)      │
                    └──────┬───────┘
                           │ HTTPS
                    ┌──────▼───────┐
                    │  Reverse     │  ← Nginx/Caddy
                    │  Proxy       │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼────┐ ┌────▼─────┐ ┌───▼────┐
        │ RPC API  │ │ P2P Node │ │ IPFS   │
        │ :5000    │ │ :4001    │ │ :5002  │
        │ (FastAPI)│ │ (libp2p) │ │ (Kubo) │
        └─────┬────┘ └────┬─────┘ └───┬────┘
              │            │            │
        ┌─────▼────────────▼────────────▼────┐
        │         CockroachDB v24.2.0        │
        │         :26257 (SQL)               │
        │         :8080  (Admin UI)          │
        └────────────────────────────────────┘
```

### Ports

| Service | Port | Protocol |
|---------|------|----------|
| RPC API | 5000 | HTTP (REST + JSON-RPC) |
| P2P (Rust libp2p) | 4001 | TCP/QUIC |
| P2P gRPC | 50051 | gRPC |
| CockroachDB SQL | 26257 | PostgreSQL wire |
| CockroachDB Admin | 8080 | HTTP |
| IPFS API | 5002 | HTTP |
| IPFS Gateway | 8080 | HTTP (conflict with CRDB) |
| IPFS Swarm | 4001 | TCP (conflict with P2P) |

**Port Conflicts:** IPFS gateway (8080) conflicts with CockroachDB admin UI. IPFS swarm (4001) conflicts with libp2p. Remap IPFS ports in production.

---

## Backend Deployment

### 1. Key Generation

```bash
python3 scripts/setup/generate_keys.py
```

This creates `secure_key.env` containing:
- Dilithium2 private key
- Dilithium2 public key
- QBC address (SHA-256 derived)

**IMPORTANT:** Never share or commit `secure_key.env`. Each node needs its own keys.

### 2. Environment Configuration

Copy and edit the config template:

```bash
cp .env.example .env
```

Key settings:

```bash
# Network
RPC_PORT=5000
P2P_PORT=4001
ENABLE_RUST_P2P=false          # Rust P2P not production-ready; Python P2P fallback is active
PEER_SEEDS=peer1.qbc.network:4001,peer2.qbc.network:4001

# Database
DATABASE_URL=postgresql://root@localhost:26257/qbc?sslmode=disable

# Mining
AUTO_MINE=true          # Set false for non-mining nodes

# Chain
CHAIN_ID=3301           # Mainnet (3302 for testnet)

# Quantum
USE_LOCAL_ESTIMATOR=true  # Local Qiskit simulator
```

### 3. Database Setup

```bash
# Start CockroachDB
cockroach start-single-node --insecure --store=cockroach-data

# Verify health
curl --fail http://localhost:8080/health?ready=1

# Initialize schema (run SQL files in order)
cockroach sql --insecure < sql/00_init_database.sql
cockroach sql --insecure < sql/01_core_blockchain.sql
# ... through 09_genesis_block.sql
```

### 4. Run the Node

```bash
cd src
python3 run_node.py
```

Verify:
```bash
curl http://localhost:5000/health
curl http://localhost:5000/chain/info
```

---

## Frontend Deployment

### Vercel (Recommended)

The frontend deploys to Vercel automatically:

1. Connect the repository to Vercel
2. Set the root directory to `frontend/`
3. Set environment variables:

```bash
NEXT_PUBLIC_RPC_URL=https://api.qbc.network
NEXT_PUBLIC_WS_URL=wss://api.qbc.network/ws
NEXT_PUBLIC_CHAIN_ID=3301
```

4. Push to `main` for production deploy
5. Push to any branch for preview deploys

### Self-Hosted

```bash
cd frontend
pnpm install
pnpm build
pnpm start    # Starts on port 3000
```

Use a reverse proxy (Nginx/Caddy) to serve on port 443 with TLS.

---

## Docker Deployment

### Development

```bash
docker-compose up -d
```

Services started:
- CockroachDB cluster (3 nodes)
- Qubitcoin node
- IPFS daemon

### Production

```bash
# Fresh start (initializes database)
bash fresh_start.sh

# Start production stack
docker-compose -f docker-compose.production.yml up -d
```

### Docker Build

```bash
docker build -t qubitcoin-node .
docker run -p 5000:5000 -p 4001:4001 \
  --env-file .env \
  --env-file secure_key.env \
  qubitcoin-node
```

---

## Production Deployment

### Node Types

| Type | Description | Hardware |
|------|-------------|----------|
| **Full Node** | Validates all blocks, serves RPC | 16GB RAM, 500GB SSD, 100Mbps |
| **Mining Node** | Full node + VQE mining | 16GB+ RAM, quantum access optional |
| **Light Node** | SPV verification only | 2GB RAM, 1GB storage |

### Security Checklist

- [ ] TLS/SSL on all external-facing ports
- [ ] Firewall: only expose ports 5000 (RPC) and 4001 (P2P)
- [ ] CockroachDB: NOT exposed to public internet
- [ ] IPFS: API port (5002) NOT exposed to public internet
- [ ] `secure_key.env` permissions: `chmod 600 secure_key.env`
- [ ] Rate limiting enabled (default: 120 req/min per IP)
- [ ] CORS origins restricted to your domain
- [ ] No debug mode in production
- [ ] Automated backups of CockroachDB data

### Reverse Proxy (Nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name api.qbc.network;

    ssl_certificate     /etc/ssl/certs/qbc.network.pem;
    ssl_certificate_key /etc/ssl/private/qbc.network.key;

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
    }
}
```

### Systemd Service

```ini
[Unit]
Description=Qubitcoin Node
After=network.target cockroachdb.service

[Service]
Type=simple
User=qbc
WorkingDirectory=/opt/qubitcoin/src
ExecStart=/opt/qubitcoin/venv/bin/python3 run_node.py
Restart=always
RestartSec=5
EnvironmentFile=/opt/qubitcoin/.env
EnvironmentFile=/opt/qubitcoin/secure_key.env

[Install]
WantedBy=multi-user.target
```

### Peer Discovery

For mainnet, configure seed peers:

```bash
# .env
PEER_SEEDS=seed1.qbc.network:4001,seed2.qbc.network:4001,seed3.qbc.network:4001
```

---

## Monitoring

### Prometheus Metrics

The node exposes Prometheus metrics at `/metrics`:

```bash
curl http://localhost:5000/metrics
```

Key metrics:
- `qbc_blocks_mined_total` -- blocks mined by this node
- `qbc_current_height` -- current chain height
- `qbc_active_peers` -- connected peer count
- `qbc_mempool_size` -- pending transaction count
- `qbc_phi_current` -- current Aether Tree Phi value
- `qbc_total_contracts` -- deployed QVM contracts

### Grafana Dashboard

Import the Prometheus config from `config/prometheus/prometheus.yml`.

### Health Checks

```bash
# Node health
curl http://localhost:5000/health

# CockroachDB health
curl --fail http://localhost:8080/health?ready=1

# Chain status
curl http://localhost:5000/chain/info

# Mining status
curl http://localhost:5000/mining/stats

# P2P status
curl http://localhost:5000/p2p/stats
```

---

## Troubleshooting

### Common Issues

**Node won't start: "Missing required configuration"**
```
Run: python3 scripts/setup/generate_keys.py
Ensure secure_key.env exists in the project root.
```

**CockroachDB connection refused**
```bash
# Check if CockroachDB is running
curl --fail http://localhost:8080/health?ready=1

# If using Docker
docker-compose ps
docker-compose logs cockroachdb
```

**Port conflict on 8080**
```
CockroachDB admin UI and IPFS gateway both default to 8080.
Remap IPFS gateway: ipfs config Addresses.Gateway /ip4/127.0.0.1/tcp/9090
```

**Mining not producing blocks**
```bash
# Check mining status
curl http://localhost:5000/mining/stats

# Ensure AUTO_MINE=true in .env
# Check quantum engine is initialized
curl http://localhost:5000/info | jq .quantum
```

**Frontend can't connect to backend**
```
Verify NEXT_PUBLIC_RPC_URL matches the node's RPC address.
Check CORS settings: QBC_CORS_ORIGINS in .env
```

**Peer connection failures**
```bash
# Check P2P status
curl http://localhost:5000/p2p/stats

# Ensure firewall allows port 4001 (TCP)
# Verify PEER_SEEDS in .env
```

---

**Website:** [qbc.network](https://qbc.network) | **Contact:** info@qbc.network | **GitHub:** [BlockArtica/Qubitcoin](https://github.com/BlockArtica/Qubitcoin)

*For more details, see `CLAUDE.md` (master development guide) and `docs/WHITEPAPER.md`.*
