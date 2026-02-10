#!/bin/bash
cd ~/qubitcoin

# Stop everything
docker compose -f deployment/docker/docker-compose.production.yml down
sleep 3

# Clean temp files only
sudo rm -rf data/cockroach-1/cockroach-temp*
sudo rm -rf data/cockroach-2/*
sudo rm -rf data/cockroach-3/*

# Start node 1
echo "=== STARTING NODE 1 ==="
docker compose -f deployment/docker/docker-compose.production.yml up -d cockroach-1
sleep 20

# Start nodes 2 & 3
echo "=== STARTING NODES 2 & 3 ==="
docker compose -f deployment/docker/docker-compose.production.yml up -d cockroach-2 cockroach-3
sleep 20

# Initialize cluster
echo "=== INITIALIZING CLUSTER ==="
docker exec qbc-cockroach-1 ./cockroach init \
  --certs-dir=/certs \
  --host=cockroach-1:26257
sleep 5

# Check cluster
echo "=== CLUSTER STATUS ==="
docker exec qbc-cockroach-1 ./cockroach node status \
  --certs-dir=/certs \
  --host=cockroach-1:26257

# Check data
echo "=== BLOCKCHAIN HEIGHT ==="
docker exec qbc-cockroach-1 ./cockroach sql \
  --certs-dir=/certs \
  --host=cockroach-1:26257 \
  --database=qubitcoin \
  --execute="SELECT MAX(height) FROM blocks;"

# Start qubitcoin node
echo "=== STARTING QUBITCOIN NODE ==="
docker compose -f deployment/docker/docker-compose.production.yml up -d qubitcoin-node
sleep 5

docker logs qbc-node --tail 40
