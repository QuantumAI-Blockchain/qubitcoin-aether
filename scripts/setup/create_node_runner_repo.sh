#!/usr/bin/env bash
# ============================================================================
# Create Qubitcoin Node Runner Repo
# Builds a clean directory with only the files needed to run a QBC node.
# No frontend, no tests, no docs, no AI dev files, no git history.
#
# Usage:
#   bash scripts/setup/create_node_runner_repo.sh /path/to/qubitcoin-node
#   bash scripts/setup/create_node_runner_repo.sh  # defaults to ../qubitcoin-node
# ============================================================================

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TARGET_DIR="${1:-$(dirname "$PROJECT_ROOT")/qubitcoin-node}"

echo "=== Qubitcoin Node Runner Repo Builder ==="
echo "Source:  $PROJECT_ROOT"
echo "Target:  $TARGET_DIR"
echo ""

# ── Safety check ──────────────────────────────────────────────────────────
if [ -d "$TARGET_DIR" ]; then
    echo "ERROR: Target directory already exists: $TARGET_DIR"
    echo "Remove it first or choose a different path."
    exit 1
fi

# ── Create directory structure ────────────────────────────────────────────
echo "Creating directory structure..."
mkdir -p "$TARGET_DIR"

# ── Copy node files ───────────────────────────────────────────────────────
echo "Copying source files..."

# Core source code
cp -r "$PROJECT_ROOT/src" "$TARGET_DIR/src"

# SQL schemas
cp -r "$PROJECT_ROOT/sql" "$TARGET_DIR/sql"
cp -r "$PROJECT_ROOT/sql_new" "$TARGET_DIR/sql_new"

# Service configuration (prometheus, grafana, nginx, loki, redis)
cp -r "$PROJECT_ROOT/config" "$TARGET_DIR/config"

# Rust P2P daemon
cp -r "$PROJECT_ROOT/rust-p2p" "$TARGET_DIR/rust-p2p"
# Remove build artifacts if present
rm -rf "$TARGET_DIR/rust-p2p/target"

# Setup scripts (key generation)
mkdir -p "$TARGET_DIR/scripts/setup"
cp "$PROJECT_ROOT/scripts/setup/generate_keys.py" "$TARGET_DIR/scripts/setup/"
cp "$PROJECT_ROOT/scripts/setup/generate_keys_simple.py" "$TARGET_DIR/scripts/setup/" 2>/dev/null || true

# Docker files
cp "$PROJECT_ROOT/Dockerfile" "$TARGET_DIR/"
cp "$PROJECT_ROOT/docker-compose.yml" "$TARGET_DIR/"
cp "$PROJECT_ROOT/docker-compose.production.yml" "$TARGET_DIR/"
cp "$PROJECT_ROOT/.dockerignore" "$TARGET_DIR/"

# Dependencies
cp "$PROJECT_ROOT/requirements.txt" "$TARGET_DIR/"

# Environment templates
cp "$PROJECT_ROOT/.env.example" "$TARGET_DIR/"
cp "$PROJECT_ROOT/.env.production.example" "$TARGET_DIR/" 2>/dev/null || true

# Contract registry (deployed addresses)
cp "$PROJECT_ROOT/contract_registry.json" "$TARGET_DIR/" 2>/dev/null || true

echo "Creating .gitignore..."
cat > "$TARGET_DIR/.gitignore" << 'GITIGNORE'
# Keys and secrets — NEVER commit
secure_key.env
.env

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
*.egg-info/
venv/
.venv/

# Rust build artifacts
rust-p2p/target/

# Node.js (shouldn't be here, but just in case)
node_modules/

# Docker data
data/
logs/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Claude Code
.claude/
GITIGNORE

# ── Generate README ───────────────────────────────────────────────────────
echo "Generating README.md..."
cat > "$TARGET_DIR/README.md" << 'README'
# Qubitcoin Node Runner

Run a Qubitcoin (QBC) node — mine blocks, validate transactions, and participate in the
quantum-secured blockchain network with on-chain AGI.

**Chain ID:** 3303 | **Block Time:** 3.3s | **Consensus:** Proof-of-SUSY-Alignment

## Quick Start (Docker)

```bash
# 1. Install Python dependencies (for key generation only)
pip install pycryptodome cryptography python-dotenv

# 2. Generate your node's cryptographic identity
python3 scripts/setup/generate_keys.py

# 3. Configure environment
cp .env.example .env
# Edit .env — set PEER_SEEDS to connect to existing network:
#   PEER_SEEDS=seed1.qbc.network:4001

# 4. Start all services
docker compose up -d

# 5. Verify
curl http://localhost:5000/health
curl http://localhost:5000/chain/info
```

Mining starts automatically. Your node will:
- Connect to seed peers and sync the blockchain
- Start mining new blocks (VQE quantum mining)
- Serve RPC API on port 5000
- Track Aether Tree consciousness metrics

## Production Deployment

For production (Digital Ocean, bare metal, etc.), use the production compose:

```bash
cp .env.production.example .env
# Edit .env — set treasury addresses, Grafana password, peer seeds
docker compose -f docker-compose.production.yml up -d --build
```

This includes Nginx (SSL), Prometheus, Grafana, Loki for monitoring.

## Configuration

Edit `.env` to configure your node:

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTO_MINE` | `true` | Start mining on boot |
| `PEER_SEEDS` | (empty) | Comma-separated seed peer addresses |
| `CHAIN_ID` | `3303` | Mainnet (3304 for testnet) |
| `ENABLE_RUST_P2P` | `true` | Use Rust libp2p for P2P networking |
| `RPC_PORT` | `5000` | RPC API port |

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Disk | 20 GB | 320 GB SSD |

## Ports

| Port | Service | Purpose |
|------|---------|---------|
| 5000 | RPC API | REST + JSON-RPC |
| 4001 | P2P | Peer connections |
| 50051 | gRPC | P2P bridge |

## API

```bash
curl http://localhost:5000/health         # Node health
curl http://localhost:5000/chain/info     # Chain status
curl http://localhost:5000/balance/<addr> # Address balance
curl http://localhost:5000/mining/stats   # Mining stats
curl http://localhost:5000/p2p/peers      # Connected peers
curl http://localhost:5000/aether/phi     # AGI consciousness metric
```

## Troubleshooting

```bash
# View node logs
docker compose logs -f qbc-node

# Check service status
docker compose ps

# Reset everything (deletes all data)
docker compose down -v && docker compose up -d --build
```

## Links

- **Website:** [qbc.network](https://qbc.network)
- **Full Documentation:** [github.com/BlockArtica/Qubitcoin](https://github.com/BlockArtica/Qubitcoin)
- **Contact:** info@qbc.network

**License:** MIT
README

# ── Summary ───────────────────────────────────────────────────────────────
echo ""
echo "=== Done! ==="
echo ""
echo "Node runner repo created at: $TARGET_DIR"
echo ""
echo "Contents:"
find "$TARGET_DIR" -maxdepth 1 -not -name "." | sort | while read -r f; do
    if [ -d "$f" ]; then
        echo "  $(basename "$f")/"
    else
        echo "  $(basename "$f")"
    fi
done
echo ""
echo "Next steps:"
echo "  cd $TARGET_DIR"
echo "  git init && git add . && git commit -m 'Initial: QBC node runner package'"
echo "  gh repo create BlockArtica/Qubitcoin-node --public --source=. --push"
