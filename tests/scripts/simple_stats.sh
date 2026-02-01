#!/bin/bash
clear
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "QUBITCOIN STATUS - $(date)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# Database stats (most reliable)
cockroach sql --insecure --database=qbc -e "
SELECT 
    'Height: ' || MAX(height)::STRING as status FROM blocks
UNION ALL
SELECT 'Blocks: ' || COUNT(*)::STRING FROM blocks
UNION ALL  
SELECT 'Supply: ' || (SELECT total_minted::STRING FROM supply WHERE id=1) || ' QBC'
UNION ALL
SELECT 'UTXOs: ' || COUNT(*)::STRING FROM utxos WHERE spent=false;
" 2>/dev/null

echo
curl -s http://localhost:5000/mining/stats | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Mining:  {\"✅ Active\" if d[\"is_mining\"] else \"❌ Stopped\"}')
print(f'Found:   {d[\"blocks_found\"]:,} blocks')
print(f'Success: {d[\"success_rate\"]*100:.1f}%')
" 2>/dev/null || echo "Mining: Cannot fetch stats"

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
