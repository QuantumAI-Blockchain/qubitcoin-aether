#!/bin/bash
set -e

cd ~/qubitcoin

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         QUBITCOIN PRODUCTION STARTUP v2.0                  ║"
echo "╚════════════════════════════════════════════════════════════╝"

# STEP 1: Stop everything cleanly
echo ""
echo "=== STEP 1: STOPPING ALL SERVICES ==="
docker compose -f deployment/docker/docker-compose.production.yml down 2>/dev/null || true
sleep 3

# STEP 2: Clean temp files and locks (preserve blockchain data)
echo ""
echo "=== STEP 2: CLEANING TEMPORARY FILES ==="
echo "Removing temp directories and lock files..."
sudo rm -rf data/cockroach-1/cockroach-temp* 2>/dev/null || true
sudo rm -rf data/cockroach-2/cockroach-temp* 2>/dev/null || true
sudo rm -rf data/cockroach-3/cockroach-temp* 2>/dev/null || true

# Remove any stale lock files
sudo find data/cockroach-1 -name "*.lock" -type f -delete 2>/dev/null || true
sudo find data/cockroach-2 -name "*.lock" -type f -delete 2>/dev/null || true
sudo find data/cockroach-3 -name "*.lock" -type f -delete 2>/dev/null || true

echo "✅ Cleanup complete"

# STEP 3: Check if this is first run
FIRST_RUN=false
if [ ! -d "data/cockroach-1/auxiliary" ]; then
    echo ""
    echo "=== FIRST RUN DETECTED ==="
    FIRST_RUN=true
    
    # Ensure directories exist
    mkdir -p data/cockroach-1 data/cockroach-2 data/cockroach-3
    sudo chown -R $USER:$USER data/
fi

# STEP 4: Start CockroachDB cluster
echo ""
echo "=== STEP 3: STARTING COCKROACHDB CLUSTER ==="
echo "Starting node 1..."
docker compose -f deployment/docker/docker-compose.production.yml up -d cockroach-1
sleep 15

echo "Starting nodes 2 & 3..."
docker compose -f deployment/docker/docker-compose.production.yml up -d cockroach-2 cockroach-3
sleep 15

# STEP 5: Initialize cluster (only on first run)
if [ "$FIRST_RUN" = true ]; then
    echo ""
    echo "=== STEP 4: INITIALIZING NEW CLUSTER ==="
    docker exec qbc-cockroach-1 ./cockroach init \
      --certs-dir=/certs \
      --host=cockroach-1:26257
    
    sleep 5
    
    echo ""
    echo "=== STEP 5: CREATING DATABASE ==="
    docker exec qbc-cockroach-1 ./cockroach sql \
      --certs-dir=/certs \
      --host=cockroach-1:26257 \
      --execute="CREATE DATABASE IF NOT EXISTS qubitcoin;"
    
    echo "✅ Database initialized"
else
    echo ""
    echo "=== EXISTING CLUSTER DETECTED - SKIPPING INIT ==="
fi

# STEP 6: Verify cluster health
echo ""
echo "=== STEP 6: VERIFYING CLUSTER HEALTH ==="
RETRIES=5
while [ $RETRIES -gt 0 ]; do
    if docker exec qbc-cockroach-1 ./cockroach node status \
       --certs-dir=/certs \
       --host=cockroach-1:26257 2>&1 | grep -q "id"; then
        echo "✅ Cluster is healthy"
        break
    fi
    RETRIES=$((RETRIES-1))
    if [ $RETRIES -eq 0 ]; then
        echo "❌ Cluster health check failed"
        exit 1
    fi
    echo "Waiting for cluster... ($RETRIES retries left)"
    sleep 5
done

# STEP 7: Check blockchain data
if [ "$FIRST_RUN" = false ]; then
    echo ""
    echo "=== STEP 7: CHECKING BLOCKCHAIN DATA ==="
    BLOCK_HEIGHT=$(docker exec qbc-cockroach-1 ./cockroach sql \
      --certs-dir=/certs \
      --host=cockroach-1:26257 \
      --database=qubitcoin \
      --execute="SELECT COALESCE(MAX(height), 0) FROM blocks;" \
      --format=tsv 2>/dev/null | tail -1 || echo "0")
    
    echo "📊 Current blockchain height: $BLOCK_HEIGHT blocks"
fi

# STEP 8: Start Qubitcoin node
echo ""
echo "=== STEP 8: STARTING QUBITCOIN MINING NODE ==="
docker compose -f deployment/docker/docker-compose.production.yml up -d qubitcoin-node

sleep 10

# STEP 9: Verify node is mining
echo ""
echo "=== STEP 9: VERIFYING NODE STATUS ==="
docker logs qbc-node --tail 30

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  ✅ STARTUP COMPLETE                        ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║  Resource Limits:                                          ║"
echo "║    CockroachDB: 2 CPU, 2GB RAM per node                   ║"
echo "║    Qubitcoin:   4 CPU, 4GB RAM                             ║"
echo "║                                                            ║"
echo "║  Auto-Restart:  Enabled (unless-stopped)                   ║"
echo "║  Health Checks: 30s intervals, 5 retries                   ║"
echo "║                                                            ║"
echo "║  Services:                                                 ║"
echo "║    Node 1: http://localhost:8080  (CockroachDB UI)         ║"
echo "║    Node 2: http://localhost:8081  (CockroachDB UI)         ║"
echo "║    Node 3: http://localhost:8082  (CockroachDB UI)         ║"
echo "║    Mining: http://localhost:5000/info (API)                ║"
echo "║                                                            ║"
echo "║  Next Steps:                                               ║"
echo "║    Terminal 1: python3 dashboard_server.py                 ║"
echo "║    Terminal 2: ngrok http 8090                             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
