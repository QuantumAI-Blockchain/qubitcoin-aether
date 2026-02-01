#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║          ADVANCED DIAGNOSTIC CHECKS                   ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

# Check block production rate
echo "1️⃣  Block Production Rate"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cockroach sql --insecure --database=qbc << 'SQL'
WITH block_times AS (
    SELECT 
        height,
        created_at,
        EXTRACT(EPOCH FROM (created_at - LAG(created_at) OVER (ORDER BY height))) as block_time
    FROM blocks
    WHERE height > 0
)
SELECT 
    ROUND(AVG(block_time)::NUMERIC, 2)::STRING || 's' as avg_block_time,
    ROUND(MIN(block_time)::NUMERIC, 2)::STRING || 's' as min_block_time,
    ROUND(MAX(block_time)::NUMERIC, 2)::STRING || 's' as max_block_time
FROM block_times;
SQL
echo

# Check for orphaned blocks
echo "2️⃣  Orphaned Blocks Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cockroach sql --insecure --database=qbc << 'SQL'
SELECT COUNT(*) as orphaned_blocks
FROM blocks b1
WHERE NOT EXISTS (
    SELECT 1 FROM blocks b2 
    WHERE b2.prev_hash = b1.block_hash
) AND height < (SELECT MAX(height) FROM blocks);
SQL
echo

# Check transaction distribution
echo "3️⃣  Transaction Distribution"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cockroach sql --insecure --database=qbc << 'SQL'
SELECT 
    status,
    COUNT(*) as count,
    ROUND(AVG(CAST(fee AS DECIMAL))::NUMERIC, 8)::STRING as avg_fee
FROM transactions
GROUP BY status;
SQL
echo

# Top energy solutions
echo "4️⃣  Best Quantum Solutions (Top 5)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cockroach sql --insecure --database=qbc << 'SQL'
SELECT 
    block_height,
    ROUND(energy::NUMERIC, 8) as energy,
    created_at
FROM solved_hamiltonians
ORDER BY energy ASC
LIMIT 5;
SQL
echo

