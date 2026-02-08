#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "════════════════════════════════════════════════════════════"
echo "  QUBITCOIN PRODUCTION CLUSTER SETUP"
echo "  Whitepaper v1.0.0 - Complete Implementation"
echo "════════════════════════════════════════════════════════════"

# Cleanup
echo "[1/8] Cleaning up old cluster..."
docker compose -f deployment/docker/docker-compose.production.yml down 2>/dev/null || true
sudo rm -rf data/cockroach-* data/ipfs 2>/dev/null || true

# Certificates
echo "[2/8] Verifying SSL certificates..."
if [ ! -d "certs/node1" ] || [ ! -d "certs/client" ]; then
    echo "ERROR: Certificates missing. Run scripts/setup/generate_certificates.sh first"
    exit 1
fi

# Data directories
echo "[3/8] Creating data directories..."
mkdir -p data/{cockroach-1,cockroach-2,cockroach-3,ipfs}
sudo chown -R $USER:$USER data/

# Start cluster
echo "[4/8] Starting 3-node cluster..."
docker compose -f deployment/docker/docker-compose.production.yml up -d cockroach-1 cockroach-2 cockroach-3

echo "Waiting 60 seconds for nodes to start..."
sleep 60

# Initialize
echo "[5/8] Initializing cluster..."
docker run --rm --network docker_qbc-network \
  -v "$PROJECT_ROOT/certs/client:/certs:ro" \
  cockroachdb/cockroach:v24.2.0 init \
  --certs-dir=/certs \
  --host=cockroach-1:26257

sleep 15

# Create schemas
echo "[6/8] Creating database schemas (80+ tables)..."

# First file creates the database - run without --database flag
echo "  → 00_init_database.sql (creating database)"
docker exec -i qbc-cockroach-1 /cockroach/cockroach sql \
  --certs-dir=/certs \
  --host=localhost:26257 < sql/00_init_database.sql

# Rest of the files use the qubitcoin database
for sql_file in sql/*.sql; do
    filename=$(basename "$sql_file")
    # Skip the init file (already ran it)
    if [ "$filename" = "00_init_database.sql" ]; then
        continue
    fi
    
    echo "  → $filename"
    docker exec -i qbc-cockroach-1 /cockroach/cockroach sql \
      --certs-dir=/certs \
      --host=localhost:26257 \
      --database=qubitcoin < "$sql_file"
done

# Admin user
echo "[7/8] Creating admin user..."
docker exec qbc-cockroach-1 /cockroach/cockroach sql \
  --certs-dir=/certs \
  --host=localhost:26257 \
  --execute="ALTER USER root WITH PASSWORD 'qubitcoin2026';"

# Start IPFS
echo "[8/8] Starting IPFS..."
docker compose -f deployment/docker/docker-compose.production.yml up -d ipfs

# Get table count
TABLE_COUNT=$(docker exec qbc-cockroach-1 /cockroach/cockroach sql \
  --certs-dir=/certs \
  --host=localhost:26257 \
  --database=qubitcoin \
  --execute="SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" \
  --format=tsv | tail -1)

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ CLUSTER READY"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Database: qubitcoin ($TABLE_COUNT tables)"
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
echo "IPFS:"
echo "  • API:     http://localhost:5001"
echo "  • Gateway: http://localhost:8083"
echo ""
echo "Next: Login to https://localhost:8080 and verify your cluster!"
echo ""
