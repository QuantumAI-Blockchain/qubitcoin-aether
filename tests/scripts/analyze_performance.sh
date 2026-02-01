#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║      QUBITCOIN MINING PERFORMANCE ANALYSIS            ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

# Get data from database
cockroach sql --insecure --database=qbc --format=csv << 'SQL' | python3 << 'PYTHON'
SELECT 
    height,
    EXTRACT(EPOCH FROM created_at) as timestamp,
    (proof_json->>'energy')::FLOAT as energy
FROM blocks
ORDER BY height;
SQL

import sys
import csv
from datetime import datetime, timedelta

reader = csv.DictReader(sys.stdin)
blocks = list(reader)

if len(blocks) < 2:
    print("Not enough blocks for analysis")
    sys.exit(0)

# Calculate statistics
heights = [int(b['height']) for b in blocks]
timestamps = [float(b['timestamp']) for b in blocks]
energies = [float(b['energy']) for b in blocks]

# Block times
block_times = []
for i in range(1, len(timestamps)):
    block_times.append(timestamps[i] - timestamps[i-1])

# Calculate metrics
total_time = timestamps[-1] - timestamps[0]
avg_block_time = sum(block_times) / len(block_times) if block_times else 0
min_block_time = min(block_times) if block_times else 0
max_block_time = max(block_times) if block_times else 0

avg_energy = sum(energies) / len(energies)
min_energy = min(energies)
max_energy = max(energies)

# Expected rewards
era_0_reward = 15.27
total_rewards = len(blocks) * era_0_reward

print("⛏️  MINING PERFORMANCE")
print("━" * 60)
print(f"  Total Blocks:        {len(blocks)}")
print(f"  Genesis to Now:      {timedelta(seconds=int(total_time))}")
print(f"  Avg Block Time:      {avg_block_time:.2f}s")
print(f"  Min Block Time:      {min_block_time:.2f}s")
print(f"  Max Block Time:      {max_block_time:.2f}s")
print(f"  Blocks per Minute:   {60/avg_block_time:.2f}" if avg_block_time > 0 else "  Blocks per Minute:   N/A")
print()

print("⚛️  QUANTUM PROOF QUALITY")
print("━" * 60)
print(f"  Average Energy:      {avg_energy:.6f}")
print(f"  Best Energy:         {min_energy:.6f}")
print(f"  Worst Energy:        {max_energy:.6f}")
print(f"  Difficulty:          0.500000")
print(f"  All Valid:           {'✅ YES' if max_energy < 0.5 else '❌ NO'}")
print()

print("💰 ECONOMICS")
print("━" * 60)
print(f"  Era 0 Reward:        {era_0_reward} QBC per block")
print(f"  Total Minted:        {total_rewards:.2f} QBC")
print(f"  % of Max Supply:     {(total_rewards / 3_300_000_000) * 100:.8f}%")
print(f"  Blocks to Era 1:     {15_474_020 - len(blocks):,}")
print()

print("🎯 PROJECTIONS")
print("━" * 60)
blocks_per_day = (86400 / avg_block_time) if avg_block_time > 0 else 0
days_to_era_1 = 15_474_020 / blocks_per_day if blocks_per_day > 0 else 0
print(f"  Current Rate:        {blocks_per_day:,.0f} blocks/day")
print(f"  Days to Era 1:       {days_to_era_1:,.1f} days")
print(f"  QBC per Day:         {blocks_per_day * era_0_reward:,.2f}")
print(f"  Year 1 Production:   {blocks_per_day * 365 * era_0_reward:,.2f} QBC")

PYTHON
