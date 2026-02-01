#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║          QUBITCOIN PRODUCTION PROJECTIONS             ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

# Get current stats
BLOCKS=$(cockroach sql --insecure --database=qbc -e "SELECT COUNT(*) FROM blocks;" --format=csv 2>/dev/null | tail -1)
SUPPLY=$(cockroach sql --insecure --database=qbc -e "SELECT total_minted FROM supply WHERE id=1;" --format=csv 2>/dev/null | tail -1)
AVG_TIME=$(cockroach sql --insecure --database=qbc --format=csv << 'SQL' 2>/dev/null | tail -1
SELECT ROUND(AVG(EXTRACT(EPOCH FROM (created_at - LAG(created_at) OVER (ORDER BY height))))::NUMERIC, 2)
FROM blocks WHERE height > 0;
SQL
)

# Current era reward
ERA_0_REWARD=15.27

# Calculations
BLOCKS_PER_DAY=$(echo "86400 / $AVG_TIME" | bc)
QBC_PER_DAY=$(echo "$BLOCKS_PER_DAY * $ERA_0_REWARD" | bc)
BLOCKS_TO_ERA_1=$((15474020 - BLOCKS))
DAYS_TO_ERA_1=$(echo "$BLOCKS_TO_ERA_1 / $BLOCKS_PER_DAY" | bc)
YEAR_1_EMISSION=$(echo "$BLOCKS_PER_DAY * 365 * $ERA_0_REWARD" | bc)

echo "📊 CURRENT STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Blocks Mined:        $BLOCKS"
echo "  Current Supply:      $SUPPLY QBC"
echo "  Avg Block Time:      ${AVG_TIME}s"
echo

echo "⚡ PRODUCTION RATE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Blocks/Day:          $(printf "%'d" $BLOCKS_PER_DAY)"
echo "  QBC/Day:             $(printf "%'d" $QBC_PER_DAY | cut -d. -f1) QBC"
echo "  Blocks/Year:         $(printf "%'d" $((BLOCKS_PER_DAY * 365)))"
echo

echo "🎯 ERA 1 PROJECTIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Blocks to Era 1:     $(printf "%'d" $BLOCKS_TO_ERA_1)"
echo "  Days to Era 1:       $(printf "%'d" $DAYS_TO_ERA_1)"
echo "  Era 1 Starts:        $(date -d "+${DAYS_TO_ERA_1} days" '+%Y-%m-%d' 2>/dev/null || echo 'N/A')"
echo

echo "💎 YEAR 1 EMISSION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Total Year 1:        $(printf "%'d" $YEAR_1_EMISSION | cut -d. -f1) QBC"
echo "  % of Max Supply:     $(echo "scale=4; $YEAR_1_EMISSION / 3300000000 * 100" | bc)%"
echo "  Halving Impact:      Next halving: $(echo "$ERA_0_REWARD / 1.618" | bc -l | xargs printf "%.2f") QBC/block"
echo
