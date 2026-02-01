#!/bin/bash

BASE="http://localhost:5000"

echo "========================================="
echo "🧪 TESTING ALL RPC ENDPOINTS"
echo "========================================="
echo

echo "1️⃣  Root endpoint..."
curl -s $BASE/ | python3 -m json.tool
echo

echo "2️⃣  Health check..."
curl -s $BASE/health | python3 -m json.tool
echo

echo "3️⃣  Node info..."
curl -s $BASE/info | python3 -m json.tool
echo

echo "4️⃣  Chain info..."
curl -s $BASE/chain/info | python3 -m json.tool
echo

echo "5️⃣  Chain tip (latest block)..."
curl -s $BASE/chain/tip | python3 -m json.tool
echo

echo "6️⃣  Block 0 (genesis)..."
curl -s $BASE/block/0 | python3 -m json.tool
echo

echo "7️⃣  Mining stats..."
curl -s $BASE/mining/stats | python3 -m json.tool
echo

echo "8️⃣  Node balance..."
ADDRESS=$(curl -s $BASE/ | python3 -c "import sys, json; print(json.load(sys.stdin)['address'])")
curl -s $BASE/balance/$ADDRESS | python3 -m json.tool
echo

echo "9️⃣  Mempool..."
curl -s $BASE/mempool | python3 -m json.tool
echo

echo "🔟 Quantum info..."
curl -s $BASE/quantum/info | python3 -m json.tool
echo

echo "1️⃣1️⃣ Research data (Hamiltonians)..."
curl -s $BASE/research/hamiltonians | python3 -m json.tool
echo

echo "1️⃣2️⃣ IPFS snapshots..."
curl -s $BASE/ipfs/snapshots | python3 -m json.tool
echo

echo "========================================="
echo "✅ ALL ENDPOINTS TESTED"
echo "========================================="
