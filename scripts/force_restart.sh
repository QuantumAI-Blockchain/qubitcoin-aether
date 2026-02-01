#!/bin/bash

echo "🔥 NUCLEAR CLEANUP..."

# Kill everything
sudo killall -9 cockroach 2>/dev/null
pkill -9 -f "python3 -m qubitcoin" 2>/dev/null

# Free all ports
for port in {8080..8095} 26257; do
    sudo kill -9 $(sudo lsof -t -i:$port) 2>/dev/null
done

sleep 5

echo "✅ Everything killed"
ps aux | grep cockroach

echo ""
echo "🚀 Starting CockroachDB on port 8090..."

cockroach start-single-node \
  --certs-dir=/home/ash/qubitcoin/data/certs \
  --listen-addr=localhost:26257 \
  --http-addr=localhost:8090 \
  --store=/home/ash/qubitcoin/data/cockroach
