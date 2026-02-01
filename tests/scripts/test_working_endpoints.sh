#!/bin/bash

BASE="http://localhost:5000"

echo "========================================="
echo "🧪 TESTING WORKING ENDPOINTS"
echo "========================================="
echo

echo "1️⃣  Health Check..."
curl -s $BASE/health | python3 -m json.tool
echo

echo "2️⃣  Latest Block (Chain Tip)..."
curl -s $BASE/chain/tip | python3 -m json.tool
echo

echo "3️⃣  Genesis Block..."
curl -s $BASE/block/0 | python3 -m json.tool
echo

echo "4️⃣  Block 1..."
curl -s $BASE/block/1 | python3 -m json.tool
echo

echo "5️⃣  Mining Stats..."
curl -s $BASE/mining/stats | python3 -m json.tool
echo

echo "6️⃣  Mempool..."
curl -s $BASE/mempool | python3 -m json.tool
echo

echo "7️⃣  Metrics (Prometheus)..."
curl -s $BASE/metrics | head -30
echo

echo "========================================="
echo "✅ WORKING ENDPOINTS TESTED"
echo "========================================="
