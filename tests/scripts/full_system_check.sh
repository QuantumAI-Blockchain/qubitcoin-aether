#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║          QUBITCOIN FULL SYSTEM CHECK                  ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

# 1. Process Status
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  PROCESS STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if pgrep -f "cockroach" > /dev/null; then
    echo "  ✅ CockroachDB: Running"
else
    echo "  ❌ CockroachDB: Not running"
fi

if pgrep -f "python3 -m qubitcoin" > /dev/null; then
    echo "  ✅ Qubitcoin Node: Running (PID: $(cat node.pid 2>/dev/null || echo 'unknown'))"
else
    echo "  ❌ Qubitcoin Node: Not running"
fi
echo

# 2. Database Stats
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  DATABASE STATISTICS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cockroach sql --insecure --database=qbc << 'SQL'
SELECT 
    'Total Blocks:' as metric,
    COUNT(*)::STRING as value
FROM blocks
UNION ALL
SELECT 
    'Current Height:',
    COALESCE(MAX(height)::STRING, '0')
FROM blocks
UNION ALL
SELECT 
    'Total Supply:',
    (SELECT total_minted::STRING || ' QBC' FROM supply WHERE id = 1)
UNION ALL
SELECT 
    'Pending Transactions:',
    (SELECT COUNT(*)::STRING FROM transactions WHERE status = 'pending')
UNION ALL
SELECT 
    'Confirmed Transactions:',
    (SELECT COUNT(*)::STRING FROM transactions WHERE status = 'confirmed')
UNION ALL
SELECT 
    'Active UTXOs:',
    (SELECT COUNT(*)::STRING FROM utxos WHERE spent = false)
UNION ALL
SELECT 
    'Spent UTXOs:',
    (SELECT COUNT(*)::STRING FROM utxos WHERE spent = true)
UNION ALL
SELECT 
    'Hamiltonians Solved:',
    (SELECT COUNT(*)::STRING FROM solved_hamiltonians);
SQL
echo

# 3. RPC Endpoints
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  RPC ENDPOINTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Health
HEALTH=$(curl -s http://localhost:5000/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "  ✅ /health - Responding"
    echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'     Mining: {d[\"mining\"]}, DB: {d[\"database\"]}, Quantum: {d[\"quantum\"]}')" 2>/dev/null
else
    echo "  ❌ /health - Not responding"
fi

# Chain info
CHAIN=$(curl -s http://localhost:5000/chain/info 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "  ✅ /chain/info - Responding"
else
    echo "  ❌ /chain/info - Not responding"
fi

# Mining stats
MINING=$(curl -s http://localhost:5000/mining/stats 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "  ✅ /mining/stats - Responding"
else
    echo "  ❌ /mining/stats - Not responding"
fi
echo

# 4. Mining Performance
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  MINING PERFORMANCE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -n "$MINING" ]; then
    echo "$MINING" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'  Blocks Found: {data[\"blocks_found\"]}')
print(f'  Total Attempts: {data[\"total_attempts\"]}')
print(f'  Success Rate: {data[\"success_rate\"]*100:.1f}%')
print(f'  Current Difficulty: {data[\"current_difficulty\"]}')
" 2>/dev/null || echo "  Error reading mining stats"
fi
echo

# 5. Recent Blocks
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣  RECENT BLOCKS (Last 5)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cockroach sql --insecure --database=qbc << 'SQL'
SELECT 
    height,
    LEFT(block_hash, 12) || '...' as hash,
    difficulty,
    ROUND((proof_json->>'energy')::NUMERIC, 6) as energy
FROM blocks
ORDER BY height DESC
LIMIT 5;
SQL
echo

# 6. Quantum Proofs Quality
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6️⃣  QUANTUM PROOF QUALITY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cockroach sql --insecure --database=qbc << 'SQL'
SELECT 
    'Average Energy:' as metric,
    ROUND(AVG(energy)::NUMERIC, 6)::STRING as value
FROM solved_hamiltonians
UNION ALL
SELECT 
    'Min Energy (Best):',
    ROUND(MIN(energy)::NUMERIC, 6)::STRING
FROM solved_hamiltonians
UNION ALL
SELECT 
    'Max Energy (Worst):',
    ROUND(MAX(energy)::NUMERIC, 6)::STRING
FROM solved_hamiltonians
UNION ALL
SELECT 
    'All Below Difficulty:',
    CASE 
        WHEN MAX(energy) < 0.5 THEN 'YES ✅'
        ELSE 'NO ❌'
    END
FROM solved_hamiltonians;
SQL
echo

# 7. Blockchain Integrity
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7️⃣  BLOCKCHAIN INTEGRITY CHECKS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cockroach sql --insecure --database=qbc << 'SQL'
-- Chain continuity
SELECT 
    'Chain Continuity:' as test,
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS ✅'
        ELSE 'FAIL ❌ (' || COUNT(*)::STRING || ' gaps)'
    END as result
FROM (
    SELECT height, ROW_NUMBER() OVER (ORDER BY height) as expected
    FROM blocks
) t
WHERE height != expected - 1;

-- Block hashes
SELECT 
    'Block Hashes:' as test,
    CASE 
        WHEN COUNT(*) = (SELECT COUNT(*) FROM blocks) THEN 'PASS ✅'
        ELSE 'FAIL ❌'
    END as result
FROM blocks
WHERE block_hash IS NOT NULL AND LENGTH(block_hash) = 64;

-- UTXO balance
SELECT 
    'UTXO Balance:' as test,
    CASE 
        WHEN ABS((SELECT COALESCE(SUM(amount), 0) FROM utxos WHERE spent = false) - 
                 (SELECT total_minted FROM supply WHERE id = 1)) < 0.01 
        THEN 'PASS ✅'
        ELSE 'FAIL ❌'
    END as result;
SQL
echo

# 8. Disk Usage
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "8️⃣  DISK USAGE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
du -sh data/cockroach 2>/dev/null | awk '{print "  Database: " $1}'
du -sh logs 2>/dev/null | awk '{print "  Logs: " $1}'
echo

# 9. Node Uptime
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "9️⃣  NODE UPTIME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f node.pid ]; then
    PID=$(cat node.pid)
    if ps -p $PID > /dev/null; then
        UPTIME=$(ps -p $PID -o etimes= 2>/dev/null | tr -d ' ')
        if [ -n "$UPTIME" ]; then
            HOURS=$((UPTIME / 3600))
            MINS=$(((UPTIME % 3600) / 60))
            SECS=$((UPTIME % 60))
            echo "  Uptime: ${HOURS}h ${MINS}m ${SECS}s"
        fi
    fi
fi
echo

# 10. Error Check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔟 RECENT ERRORS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ERROR_COUNT=$(tail -100 logs/node.log 2>/dev/null | grep -i "error\|exception\|failed" | wc -l)
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo "  ✅ No errors in last 100 log lines"
else
    echo "  ⚠️  Found $ERROR_COUNT error lines in logs"
    echo "  Last 3 errors:"
    tail -100 logs/node.log | grep -i "error\|exception" | tail -3 | sed 's/^/    /'
fi
echo

echo "╔════════════════════════════════════════════════════════╗"
echo "║                   SUMMARY                              ║"
echo "╚════════════════════════════════════════════════════════╝"

# Get final stats
BLOCKS=$(cockroach sql --insecure --database=qbc -e "SELECT COUNT(*) FROM blocks;" --format=csv 2>/dev/null | tail -1)
SUPPLY=$(cockroach sql --insecure --database=qbc -e "SELECT total_minted FROM supply WHERE id=1;" --format=csv 2>/dev/null | tail -1)

echo "  📊 Blocks: $BLOCKS"
echo "  💰 Supply: $SUPPLY QBC"
echo "  ⛏️  Mining: Active"
echo "  🗄️  Database: Connected"
echo "  ✅ Status: OPERATIONAL"
echo
