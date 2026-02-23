#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║          QUBITCOIN PRODUCTION PROJECTIONS             ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

# Get current stats from RPC (more reliable)
CHAIN_INFO=$(curl -s http://localhost:5000/chain/info 2>/dev/null)

if [ -z "$CHAIN_INFO" ]; then
    echo "Error: Cannot reach node"
    exit 1
fi

HEIGHT=$(echo "$CHAIN_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['height'])" 2>/dev/null)
SUPPLY=$(echo "$CHAIN_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_supply'])" 2>/dev/null)
DIFFICULTY=$(echo "$CHAIN_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['difficulty'])" 2>/dev/null)

# Get avg block time from database
AVG_TIME=$(cockroach sql --insecure --database=qbc --format=tsv << 'SQL' 2>/dev/null | tail -1
SELECT ROUND(AVG(EXTRACT(EPOCH FROM (created_at - LAG(created_at) OVER (ORDER BY height))))::NUMERIC, 2)
FROM blocks WHERE height > 0 LIMIT 100;
SQL
)

# Fallback if query fails
if [ -z "$AVG_TIME" ] || [ "$AVG_TIME" = "NULL" ]; then
    AVG_TIME=1.76
fi

ERA_0_REWARD=15.27
BLOCKS_PER_DAY=$(python3 -c "print(int(86400 / $AVG_TIME))")
QBC_PER_DAY=$(python3 -c "print(int($BLOCKS_PER_DAY * $ERA_0_REWARD))")
BLOCKS_TO_ERA_1=$((15474020 - HEIGHT))
DAYS_TO_ERA_1=$(python3 -c "print(int($BLOCKS_TO_ERA_1 / $BLOCKS_PER_DAY))")
YEAR_1_EMISSION=$(python3 -c "print(int($BLOCKS_PER_DAY * 365 * $ERA_0_REWARD))")

echo "📊 CURRENT STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "  Blocks Mined:        %'d\n" $HEIGHT
echo "  Current Supply:      $SUPPLY QBC"
echo "  Avg Block Time:      ${AVG_TIME}s"
printf "  Difficulty:          %.2f\n" $DIFFICULTY
echo

echo "⚡ PRODUCTION RATE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "  Blocks/Day:          %'d\n" $BLOCKS_PER_DAY
printf "  QBC/Day:             %'d QBC\n" $QBC_PER_DAY
printf "  Blocks/Year:         %'d\n" $((BLOCKS_PER_DAY * 365))
echo

echo "🎯 ERA 1 PROJECTIONS (φ Halving)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "  Blocks to Era 1:     %'d\n" $BLOCKS_TO_ERA_1
printf "  Days to Era 1:       %'d days\n" $DAYS_TO_ERA_1
printf "  Years to Era 1:      %.1f years\n" $(python3 -c "print($DAYS_TO_ERA_1 / 365)")
echo "  Era 1 Reward:        $(python3 -c "print(round($ERA_0_REWARD / 1.618034, 2))") QBC/block"
echo

echo "💎 YEAR 1 EMISSION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "  Total Year 1:        %'d QBC\n" $YEAR_1_EMISSION
printf "  %% of Max Supply:     %.4f%%\n" $(python3 -c "print($YEAR_1_EMISSION / 3300000000 * 100)")
printf "  At Current Rate:     %'d QBC mined/hour\n" $(($QBC_PER_DAY / 24))
echo

echo "🏆 MILESTONES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
BLOCKS_TO_1K=$((1000 - HEIGHT))
if [ $BLOCKS_TO_1K -gt 0 ]; then
    MINS_TO_1K=$(python3 -c "print(int($BLOCKS_TO_1K * $AVG_TIME / 60))")
    echo "  Block 1,000:         $BLOCKS_TO_1K blocks away (~$MINS_TO_1K minutes)"
else
    echo "  Block 1,000:         ✅ PASSED!"
fi

BLOCKS_TO_10K=$((10000 - HEIGHT))
if [ $BLOCKS_TO_10K -gt 0 ]; then
    HOURS_TO_10K=$(python3 -c "print(int($BLOCKS_TO_10K * $AVG_TIME / 3600))")
    echo "  Block 10,000:        $BLOCKS_TO_10K blocks away (~$HOURS_TO_10K hours)"
fi

BLOCKS_TO_100K=$((100000 - HEIGHT))
DAYS_TO_100K=$(python3 -c "print(int($BLOCKS_TO_100K * $AVG_TIME / 86400))")
echo "  Block 100,000:       $BLOCKS_TO_100K blocks away (~$DAYS_TO_100K days)"
echo
