#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "════════════════════════════════════════════════════════════"
echo "  STEP 1: INITIALIZE CLUSTER + CREATE DATABASE"
echo "════════════════════════════════════════════════════════════"

# Cleanup
echo "[1/6] Cleaning up..."
docker compose -f deployment/docker/docker-compose.production.yml down 2>/dev/null || true
sudo rm -rf data/cockroach-* data/ipfs 2>/dev/null || true

# Data directories
echo "[2/6] Creating data directories..."
mkdir -p data/{cockroach-1,cockroach-2,cockroach-3,ipfs}
sudo chown -R $USER:$USER data/

# Start cluster
echo "[3/6] Starting 3-node cluster..."
docker compose -f deployment/docker/docker-compose.production.yml up -d cockroach-1 cockroach-2 cockroach-3

echo "Waiting 45 seconds for nodes to start..."
sleep 45

# Initialize
echo "[4/6] Initializing cluster..."
docker run --rm --network docker_qbc-network \
  -v "$PROJECT_ROOT/certs/client:/certs:ro" \
  cockroachdb/cockroach:v24.2.0 init \
  --certs-dir=/certs \
  --host=cockroach-1:26257

echo "Waiting 10 seconds..."
sleep 10

# Create database (using client certs mounted inside container)
echo "[5/6] Creating qubitcoin database..."
docker run --rm --network docker_qbc-network \
  -v "$PROJECT_ROOT/certs/client:/certs:ro" \
  cockroachdb/cockroach:v24.2.0 sql \
  --certs-dir=/certs \
  --host=cockroach-1:26257 \
  --execute="CREATE DATABASE IF NOT EXISTS qubitcoin;"

# Set password
echo "[6/6] Setting admin password..."
docker run --rm --network docker_qbc-network \
  -v "$PROJECT_ROOT/certs/client:/certs:ro" \
  cockroachdb/cockroach:v24.2.0 sql \
  --certs-dir=/certs \
  --host=cockroach-1:26257 \
  --execute="ALTER USER root WITH PASSWORD 'qubitcoin2026';"

# Verify database exists
echo ""
echo "Verifying database..."
docker run --rm --network docker_qbc-network \
  -v "$PROJECT_ROOT/certs/client:/certs:ro" \
  cockroachdb/cockroach:v24.2.0 sql \
  --certs-dir=/certs \
  --host=cockroach-1:26257 \
  --execute="SHOW DATABASES;"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ CLUSTER INITIALIZED"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Database: qubitcoin (created, empty)"
echo ""
echo "Web UI:   https://localhost:8080"
echo "Username: root"
echo "Password: qubitcoin2026"
echo ""
echo "Nodes:"
echo "  • Node 1: localhost:26257 (UI: 8080)"
echo "  • Node 2: localhost:26258 (UI: 8081)"
echo "  • Node 3: localhost:26259 (UI: 8082)"
echo ""
echo "✓ Ready for table creation!"
echo ""
