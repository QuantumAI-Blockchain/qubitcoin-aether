#!/usr/bin/env python3
"""Export current Python chain state for Substrate fork genesis.

Queries CockroachDB for all unspent UTXOs and chain parameters,
outputs a JSON file that chain_spec.rs can load for the forked genesis.

Usage:
    python3 scripts/export_fork_state.py > substrate-node/fork_state.json
"""

import hashlib
import json
import sys
from collections import defaultdict
from decimal import Decimal

import psycopg2


DB_URL = "postgresql://root@localhost:26257/qubitcoin?sslmode=disable"


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Get current chain state
    # Get chain state from REST API (chain_state table not reliably updated)
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:5000/chain/info", timeout=5) as resp:
            chain_info = json.loads(resp.read())
        fork_height = int(chain_info["height"])
        total_supply = float(chain_info["total_supply"])
        difficulty = float(chain_info["difficulty"])
    except Exception as e:
        print(f"ERROR: Cannot reach node API: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Fork height: {fork_height}", file=sys.stderr)
    print(f"Total supply: {total_supply} QBC", file=sys.stderr)
    print(f"Difficulty: {difficulty}", file=sys.stderr)

    # Get all unspent UTXOs, consolidated per address (lowercase)
    cur.execute("""
        SELECT LOWER(address) as addr,
               SUM(amount) as total_amount,
               COUNT(*) as utxo_count
        FROM utxos
        WHERE spent = false
        GROUP BY LOWER(address)
        ORDER BY total_amount DESC
    """)

    balances = []
    total_in_utxos = Decimal('0')

    for addr, amount, count in cur.fetchall():
        # amount is in QBC (float from DB), convert to smallest units (10^8)
        amount_dec = Decimal(str(amount))
        amount_units = int(amount_dec * Decimal('100000000'))
        if amount_units <= 0:
            continue  # Skip zero-balance addresses

        total_in_utxos += amount_dec
        balances.append({
            "address": addr,
            "amount_qbc": float(amount_dec),
            "amount_units": amount_units,
            "utxo_count": count,
        })

    print(f"Addresses with balance: {len(balances)}", file=sys.stderr)
    print(f"Total in UTXOs: {total_in_utxos} QBC", file=sys.stderr)

    # Generate deterministic txids for each fork genesis UTXO
    # SHA256("fork_genesis_<fork_height>_<address>")
    genesis_utxos = []
    for i, bal in enumerate(balances):
        seed = f"fork_genesis_{fork_height}_{bal['address']}"
        txid = hashlib.sha256(seed.encode()).hexdigest()
        genesis_utxos.append({
            "txid": txid,
            "vout": 0,
            "address_hex": bal["address"],
            "amount": bal["amount_units"],
            "address_label": bal["address"][:12] + "...",
            "amount_qbc": bal["amount_qbc"],
        })

    # Difficulty: Python uses float, Substrate uses u64 scaled by 10^6
    difficulty_scaled = int(difficulty * 1_000_000)

    # Total emitted in smallest units
    total_emitted_units = int(Decimal(str(total_supply)) * Decimal('100000000'))

    fork_state = {
        "fork_height": fork_height,
        "total_supply_qbc": total_supply,
        "total_supply_units": total_emitted_units,
        "total_in_utxos_qbc": float(total_in_utxos),
        "difficulty": difficulty,
        "difficulty_scaled": difficulty_scaled,
        "era": 0,
        "addresses": len(balances),
        "genesis_utxos": genesis_utxos,
    }

    json.dump(fork_state, sys.stdout, indent=2)
    print("", file=sys.stdout)  # trailing newline

    cur.close()
    conn.close()

    print(f"\nFork state exported successfully.", file=sys.stderr)
    print(f"Genesis will have {len(genesis_utxos)} UTXOs preserving all balances.", file=sys.stderr)


if __name__ == "__main__":
    main()
