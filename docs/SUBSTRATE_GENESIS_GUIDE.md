# Qubitcoin Substrate Genesis Guide

> Complete reference for launching Qubitcoin in hybrid Substrate + Python mode.

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│              SUBSTRATE NODE (L1)                  │
│  Aura (3.3s blocks) + GRANDPA (finality)         │
│  7 pallets: UTXO, Consensus, Dilithium,          │
│  Economics, QVM Anchor, Aether Anchor,            │
│  Reversibility                                    │
│  Ports: 9944 (WS/RPC), 30333 (P2P), 9615 (Prom) │
└──────────────────┬───────────────────────────────┘
                   │ WebSocket (chain_subscribeFinalizedHeads)
                   │ + Extrinsic submission (author_submitExtrinsic)
                   ▼
┌──────────────────────────────────────────────────┐
│          PYTHON EXECUTION SERVICE                 │
│  SubstrateBridge: subscribes to finalized blocks  │
│  QVM (167 opcodes), Aether Tree (34 modules)      │
│  QUSD, Bridge, Compliance, Exchange, AIKGS        │
│  Mining: generates VQE proofs → submits to        │
│    Substrate via submit_mining_proof extrinsic    │
│  Anchoring: submits Phi/state roots via           │
│    Sudo.sudo() wrapped extrinsics                 │
│  RPC Gateway: 315+ endpoints for frontend         │
│  Port: 5000 (REST + JSON-RPC)                     │
└──────────────────┬───────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────┐
│         CockroachDB + IPFS + Redis                │
│  55+ tables (blocks, UTXOs, knowledge, contracts) │
│  IPFS for content storage, Redis for caching      │
└──────────────────────────────────────────────────┘
```

**Key principle:** Substrate handles consensus (block production, UTXO, P2P, finality).
Python handles execution (QVM, Aether Tree, QUSD, bridges, RPC). Both share infrastructure.

---

## Prerequisites

### 1. Docker & Docker Compose

```bash
docker --version   # v24+ required
docker compose version  # v2.20+ required
```

### 2. Generate Node Keys

```bash
python3 scripts/setup/generate_keys.py
```

This creates `secure_key.env` with Dilithium2 key material. **Never commit this file.**

### 3. Create Environment File

```bash
cp .env.example .env
```

Edit `.env` and set required values:
- `REDIS_PASSWORD` — strong password for Redis
- `GRAFANA_ADMIN_PASSWORD` — if using monitoring profile
- `GEVURAH_SECRET` — HMAC secret for safety veto (generate with `openssl rand -hex 32`)
- `AIKGS_AUTH_TOKEN` — gRPC auth token (generate with `openssl rand -hex 32`)

### 4. Substrate Build (if building locally)

```bash
cd substrate-node
SKIP_WASM_BUILD=1 cargo build --release
# Binary: target/release/qbc-node
```

For Docker deployments, the build happens inside the container.

---

## Quick Start

### Full Stack (one command)

```bash
docker compose -f docker-compose.substrate.yml up -d
```

This starts all 7 services in dependency order:
1. CockroachDB → waits for healthy
2. db-init → loads SQL schemas, waits for completion
3. IPFS + Redis → wait for healthy
4. Substrate node → waits for healthy (producing blocks)
5. Python execution service → connects to Substrate via WebSocket
6. AIKGS sidecar → connects to Python execution service

### Verify Genesis

```bash
bash scripts/setup/substrate_genesis_init.sh
```

This verifies:
- Substrate is producing blocks
- Python is processing finalized blocks
- Aether Tree is initialized
- CockroachDB is healthy
- All health endpoints respond

### Start Frontend

```bash
cd frontend && pnpm install && pnpm dev
# Opens http://localhost:3000
```

---

## Service Reference

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| CockroachDB | qbc-cockroachdb | 26257 (SQL), 8080 (UI) | Shared database |
| IPFS (Kubo) | qbc-ipfs | 4001 (P2P), 5002 (API), 8081 (GW) | Content storage |
| Redis | qbc-redis | 6379 | Caching, rate limiting |
| Substrate | qbc-substrate | 9944 (RPC/WS), 30333 (P2P), 9615 (Prom) | L1 consensus |
| Python | qbc-execution | 5000 | L2/L3 execution + RPC gateway |
| AIKGS Sidecar | qbc-aikgs-sidecar | 50052 (gRPC) | Knowledge rewards |
| Prometheus | qbc-prometheus | 9090 | Metrics (monitoring profile) |
| Grafana | qbc-grafana | 3001 | Dashboards (monitoring profile) |

### Enable Monitoring

```bash
docker compose -f docker-compose.substrate.yml --profile monitoring up -d
```

---

## How It Works

### Block Production

1. Substrate produces blocks via Aura consensus (~3.3s intervals)
2. GRANDPA finalizes blocks (single-node: instant finality)
3. Python subscribes to `chain_subscribeFinalizedHeads` via WebSocket
4. On each finalized block, Python:
   - Fetches full block data via `chain_getBlock`
   - Converts Substrate SCALE format to Python dict
   - Stores block in CockroachDB
   - Processes QVM transactions
   - Updates Aether Tree (knowledge graph, Phi, reasoning)
   - Anchors Aether state back to Substrate every 10 blocks

### Mining (VQE Proof Submission)

1. Python mining engine generates VQE proofs (same as standalone mode)
2. Instead of creating a local block, proof is submitted as a Substrate extrinsic:
   ```
   pallet_qbc_consensus::submit_mining_proof(origin, vqe_proof)
   ```
3. Substrate validates the proof (energy < difficulty threshold)
4. If valid, proof is included in the next block
5. Miner receives block reward via UTXO coinbase

### State Anchoring

Python periodically anchors L2/L3 state to Substrate (every 10 blocks):

- **Aether state**: `Sudo.sudo(QbcAetherAnchor.record_block_state(height, phi, knowledge_root, pot_hash))`
- **QVM state**: `Sudo.sudo(QbcQvmAnchor.update_state_root(height, state_root))`

Both use `ensure_root` origin, so they're wrapped in `Sudo.sudo()` extrinsics signed by the sudo key (`//Alice` in dev mode).

### Frontend Connection

The frontend connects to Python (port 5000), not Substrate directly. Python serves:
- L1 queries: proxied from CockroachDB (populated by SubstrateBridge)
- L2/L3 queries: handled directly (QVM, Aether, QUSD, contracts)
- All 315+ RPC endpoints remain identical

---

## Configuration

### Substrate Mode Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SUBSTRATE_MODE` | `false` | Enable hybrid Substrate mode |
| `SUBSTRATE_WS_URL` | `ws://localhost:9944` | Substrate WebSocket URL |
| `SUBSTRATE_HTTP_URL` | `http://localhost:9944` | Substrate HTTP RPC URL |
| `SUBSTRATE_SUDO_SEED` | `//Alice` | Sudo key seed for state anchoring |

When `SUBSTRATE_MODE=false` (default), the Python node runs standalone — identical to pre-migration behavior.

### Docker Override

In `docker-compose.substrate.yml`, the Python execution service has:
```yaml
environment:
  - SUBSTRATE_MODE=true
  - SUBSTRATE_WS_URL=ws://qbc-substrate:9944
  - ENABLE_RUST_P2P=false  # Substrate handles P2P
```

---

## Health Checks

### Substrate Node

```bash
curl -sf -H 'Content-Type: application/json' \
  -d '{"id":1,"jsonrpc":"2.0","method":"system_health","params":[]}' \
  http://localhost:9944
```

### Python Execution Service

```bash
curl http://localhost:5000/health
```

Returns JSON with `substrate_mode: true` and `substrate_connected: true` when healthy.

### CockroachDB

```bash
curl http://localhost:8080/health?ready=1
```

### Full Status

```bash
bash scripts/setup/substrate_genesis_init.sh
```

---

## Troubleshooting

### Substrate not producing blocks

```bash
docker logs qbc-substrate --tail 50
```

Common causes:
- Port 9944 already in use
- Insufficient memory (needs ~2GB)
- Volume corruption → `docker volume rm qbc-substrate-data`

### Python can't connect to Substrate

```bash
docker logs qbc-execution --tail 50 | grep -i substrate
```

Common causes:
- Substrate not yet healthy (Python waits and retries with backoff)
- Wrong WS URL (check `SUBSTRATE_WS_URL` env var)
- Network isolation (both must be on `qbc-net` Docker network)

### Database schema errors

```bash
docker logs qbc-db-init
```

The db-init container runs SQL migrations. If it fails, check:
- CockroachDB is healthy before db-init starts
- SQL files exist in `sql/` and `sql_new/` directories

### Mining proofs not accepted

Check Substrate logs for proof validation errors:
```bash
docker logs qbc-substrate 2>&1 | grep -i mining
```

Common causes:
- Energy above difficulty threshold
- Invalid VQE proof format
- Extrinsic encoding mismatch

---

## Production Deployment

### Multi-Validator Setup

1. Generate unique keys for each validator
2. Add validator keys to Substrate chain spec
3. Update `--chain` flag from `dev` to custom chain spec
4. Replace `//Alice` sudo seed with a secure key
5. Enable mutual TLS between services

### Security Checklist

- [ ] Replace `--rpc-methods unsafe` with `safe` (disable sudo RPC)
- [ ] Set strong `REDIS_PASSWORD`
- [ ] Set `GEVURAH_SECRET` for safety veto authentication
- [ ] Set `AIKGS_AUTH_TOKEN` for gRPC authentication
- [ ] Use dedicated treasury addresses (not dev addresses)
- [ ] Enable TLS on CockroachDB (`--certs-dir` instead of `--insecure`)
- [ ] Restrict RPC access (remove `--rpc-external` or add firewall rules)
- [ ] Use Docker secrets or a vault for sensitive env vars

### Monitoring

Enable the monitoring profile for Prometheus + Grafana:
```bash
docker compose -f docker-compose.substrate.yml --profile monitoring up -d
```

Grafana dashboard: http://localhost:3001 (admin / `GRAFANA_ADMIN_PASSWORD`)

---

## Backward Compatibility

| Mode | Behavior |
|------|----------|
| `SUBSTRATE_MODE=false` | Python node runs standalone (original behavior) |
| `SUBSTRATE_MODE=true` | Python runs as execution service alongside Substrate |

All 3,907 existing tests pass in both modes. The frontend API shape is identical.

---

## Key Files

| File | Purpose |
|------|---------|
| `src/qubitcoin/substrate_bridge.py` | WebSocket connection to Substrate, block subscription, extrinsic submission |
| `src/qubitcoin/substrate_codec.py` | SCALE encoding/decoding utilities |
| `src/qubitcoin/config.py` | SUBSTRATE_MODE, WS_URL, HTTP_URL, SUDO_SEED |
| `src/qubitcoin/node.py` | Substrate initialization path (Component 3), block callback |
| `src/qubitcoin/mining/engine.py` | Substrate mining proof submission |
| `src/qubitcoin/network/rpc.py` | Substrate-aware health/chain endpoints |
| `docker-compose.substrate.yml` | Full hybrid stack orchestration |
| `scripts/setup/substrate_genesis_init.sh` | Post-genesis verification |
| `substrate-node/` | Substrate node source (7 crates, 6 pallets) |
