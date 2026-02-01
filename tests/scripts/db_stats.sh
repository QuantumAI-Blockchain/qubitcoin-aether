#!/bin/bash
clear
cockroach sql --insecure --database=qbc << 'SQL'
SELECT 
    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' as line
UNION ALL
SELECT 'QUBITCOIN STATUS - ' || NOW()::STRING
UNION ALL
SELECT '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
UNION ALL
SELECT ''
UNION ALL
SELECT '📊 Height:       ' || MAX(height)::STRING FROM blocks
UNION ALL
SELECT '📦 Total Blocks: ' || COUNT(*)::STRING FROM blocks
UNION ALL
SELECT '💰 Supply:       ' || (SELECT total_minted::STRING FROM supply WHERE id=1) || ' QBC'
UNION ALL
SELECT '📍 UTXOs:        ' || (SELECT COUNT(*)::STRING FROM utxos WHERE spent=false)
UNION ALL
SELECT '⚛️  Hamiltonians: ' || (SELECT COUNT(*)::STRING FROM solved_hamiltonians)
UNION ALL
SELECT ''
UNION ALL
SELECT '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
SQL
