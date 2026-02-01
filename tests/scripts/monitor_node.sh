#!/bin/bash

while true; do
    clear
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║         QUBITCOIN NODE LIVE DASHBOARD                 ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo
    
    # Get stats
    STATS=$(curl -s http://localhost:5000/mining/stats 2>/dev/null)
    TIP=$(curl -s http://localhost:5000/chain/tip 2>/dev/null)
    HEALTH=$(curl -s http://localhost:5000/health 2>/dev/null)
    
    if [ -n "$STATS" ]; then
        echo "⛏️  MINING STATUS"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "$STATS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  Active: {'✅ YES' if data['is_mining'] else '❌ NO'}\")
print(f\"  Blocks Found: {data['blocks_found']}\")
print(f\"  Total Attempts: {data['total_attempts']}\")
print(f\"  Success Rate: {data['success_rate']*100:.1f}%\")
print(f\"  Difficulty: {data['current_difficulty']:.4f}\")
" 2>/dev/null || echo "  Error reading stats"
    fi
    
    echo
    echo "⛓️  BLOCKCHAIN STATUS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ -n "$TIP" ]; then
        echo "$TIP" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  Height: {data['height']}\")
print(f\"  Hash: {data['block_hash'][:32]}...\")
print(f\"  Difficulty: {data['difficulty']:.4f}\")
print(f\"  Energy: {data['proof_data']['energy']:.6f}\")
" 2>/dev/null || echo "  Error reading tip"
    fi
    
    echo
    echo "🏥 HEALTH STATUS"  
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ -n "$HEALTH" ]; then
        echo "$HEALTH" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  Database: {'✅' if data['database'] else '❌'}\")
print(f\"  Mining: {'✅' if data['mining'] else '❌'}\")
print(f\"  Quantum: {'✅' if data['quantum'] else '❌'}\")
print(f\"  IPFS: {'✅' if data['ipfs'] else '❌'}\")
" 2>/dev/null || echo "  Error reading health"
    fi
    
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')  |  Press Ctrl+C to exit"
    echo
    
    sleep 5
done
