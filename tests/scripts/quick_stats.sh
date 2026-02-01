#!/bin/bash
clear

echo "╔════════════════════════════════════════════════════╗"
echo "║          QUBITCOIN LIVE STATUS                    ║"
echo "╚════════════════════════════════════════════════════╝"
echo

# Use chain/tip instead (this works)
curl -s http://localhost:5000/chain/tip 2>/dev/null | python3 << 'PYTHON'
import sys, json
try:
    d = json.load(sys.stdin)
    print(f"  📊 Height:         {d['height']:,}")
    print(f"  🔗 Hash:           {d['block_hash'][:16]}...")
    print(f"  ⚙️  Difficulty:     {d['difficulty']}")
    print(f"  ⚛️  Energy:         {d['proof_data']['energy']:.6f}")
except:
    print("  ⚠️  Could not fetch chain tip")
PYTHON

# Get balance for supply estimate
curl -s http://localhost:5000/balance/00b5a241577d63bae49073e924f53678f86b4111 2>/dev/null | python3 << 'PYTHON'
import sys, json
try:
    d = json.load(sys.stdin)
    print(f"  💰 Your Balance:   {float(d['balance']):,.2f} QBC")
    print(f"  📦 UTXOs:          {d['utxo_count']:,}")
except:
    print("  ⚠️  Could not fetch balance")
PYTHON

echo

# Mining stats
curl -s http://localhost:5000/mining/stats 2>/dev/null | python3 << 'PYTHON'
import sys, json
try:
    d = json.load(sys.stdin)
    print("  ⛏️  Mining:         Active" if d['is_mining'] else "  ⛏️  Mining:         Stopped")
    print(f"  ✅ Blocks Found:   {d['blocks_found']:,}")
    print(f"  🎲 Attempts:       {d['total_attempts']:,}")
    print(f"  📊 Success Rate:   {d['success_rate']*100:.1f}%")
except:
    print("  ⚠️  Could not fetch mining stats")
PYTHON

echo
