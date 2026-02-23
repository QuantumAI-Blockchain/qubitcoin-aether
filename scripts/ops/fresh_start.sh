#!/bin/bash
set -e

cd ~/qubitcoin

echo "=== STEP 1: STOPPING EVERYTHING ==="
docker compose -f deployment/docker/docker-compose.production.yml down
sleep 3

echo ""
echo "=== STEP 2: WIPING ALL DATA ==="
sudo rm -rf data/cockroach-1/*
sudo rm -rf data/cockroach-2/*
sudo rm -rf data/cockroach-3/*

# Recreate directories
mkdir -p data/cockroach-1
mkdir -p data/cockroach-2
mkdir -p data/cockroach-3
sudo chown -R $USER:$USER data/

echo "✅ All data wiped clean"

echo ""
echo "=== STEP 3: STARTING NODE 1 ==="
docker compose -f deployment/docker/docker-compose.production.yml up -d cockroach-1
sleep 15

echo ""
echo "=== STEP 4: STARTING NODES 2 & 3 ==="
docker compose -f deployment/docker/docker-compose.production.yml up -d cockroach-2 cockroach-3
sleep 15

echo ""
echo "=== STEP 5: INITIALIZING CLUSTER ==="
docker exec qbc-cockroach-1 ./cockroach init \
  --certs-dir=/certs \
  --host=cockroach-1:26257

sleep 5

echo ""
echo "=== STEP 6: CREATING DATABASE ==="
docker exec qbc-cockroach-1 ./cockroach sql \
  --certs-dir=/certs \
  --host=cockroach-1:26257 \
  --execute="CREATE DATABASE IF NOT EXISTS qubitcoin;"

echo ""
echo "=== STEP 7: VERIFYING CLUSTER ==="
docker exec qbc-cockroach-1 ./cockroach node status \
  --certs-dir=/certs \
  --host=cockroach-1:26257

echo ""
echo "=== STEP 8: STARTING QUBITCOIN NODE ==="
docker compose -f deployment/docker/docker-compose.production.yml up -d qubitcoin-node

sleep 5

echo ""
echo "=== CHECKING NODE STATUS ==="
docker logs qbc-node --tail 40

echo ""
echo "✅ FRESH START COMPLETE!"
echo "🚀 Node should be mining from block 0"
echo ""
echo "Next steps:"
echo "  Terminal 1: python3 dashboard_server.py"
echo "  Terminal 2: ngrok http 8090"
