#!/bin/bash

echo "Testing wallet operations..."

# 1. Check balance
curl -s http://localhost:5000/balance/00b5a241577d63bae49073e924f53678f86b4111 | python3 -m json.tool

# 2. Get UTXOs
curl -s http://localhost:5000/utxos/00b5a241577d63bae49073e924f53678f86b4111 | python3 -m json.tool | head -30

# 3. Check mempool
curl -s http://localhost:5000/mempool | python3 -m json.tool
