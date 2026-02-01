#!/bin/bash

while true; do
    clear
    date
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Real-time stats
    cockroach sql --insecure --database=qbc --format=csv << 'SQL' | column -t -s','
SELECT 
    'Height' as metric, MAX(height)::STRING as value FROM blocks
UNION ALL
SELECT 'Supply', (SELECT total_minted::STRING FROM supply WHERE id=1)
UNION ALL  
SELECT 'UTXOs', COUNT(*)::STRING FROM utxos WHERE spent=false
UNION ALL
SELECT 'Hamiltonians', COUNT(*)::STRING FROM solved_hamiltonians;
SQL
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Refreshing every 5 seconds... (Ctrl+C to exit)"
    sleep 5
done
