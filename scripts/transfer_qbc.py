#!/usr/bin/env python3
"""Transfer QBC between addresses using CockroachDB UTXOs directly.

Usage:
    python3 scripts/transfer_qbc.py --from-addr <addr> --to-addr <addr> --amount <qbc>
"""

import argparse
import hashlib
import time
import uuid
from decimal import Decimal

import psycopg2

DB_DSN = "host=localhost port=26257 dbname=qubitcoin user=root sslmode=disable"


def transfer(from_addr: str, to_addr: str, amount: Decimal) -> dict:
    from_addr = from_addr.replace("0x", "").lower()
    to_addr = to_addr.replace("0x", "").lower()

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Select ALL unspent UTXOs (no FOR UPDATE — single operator, no contention)
        cur.execute(
            """SELECT txid, vout, amount FROM utxos
               WHERE address = %s AND spent = false
               ORDER BY amount DESC""",
            (from_addr,),
        )
        rows = cur.fetchall()

        if not rows:
            raise RuntimeError(f"No UTXOs for {from_addr}")

        # Greedy largest-first selection
        selected = []
        total = Decimal(0)
        for txid, vout, utxo_amount in rows:
            selected.append((txid, vout, Decimal(str(utxo_amount))))
            total += Decimal(str(utxo_amount))
            if total >= amount:
                break

        if total < amount:
            raise RuntimeError(f"Insufficient funds: have {total}, need {amount}")

        change = total - amount

        # Generate transaction ID
        tx_data = f"{from_addr}:{to_addr}:{amount}:{time.time()}:{uuid.uuid4().hex}"
        txid_hash = hashlib.sha256(tx_data.encode()).hexdigest()

        # Mark selected UTXOs as spent in batches
        batch_size = 100
        for i in range(0, len(selected), batch_size):
            batch = selected[i:i + batch_size]
            # Build batch UPDATE with IN clause
            txid_vout_pairs = [(s[0], s[1]) for s in batch]
            placeholders = ",".join(
                [f"(%s, %s)"] * len(txid_vout_pairs)
            )
            params = []
            for t, v in txid_vout_pairs:
                params.extend([t, v])
            cur.execute(
                f"""UPDATE utxos SET spent = true
                    WHERE (txid, vout) IN ({placeholders})""",
                params,
            )

        # Create output UTXO for recipient
        cur.execute(
            """INSERT INTO utxos (txid, vout, address, amount, spent, block_height)
               VALUES (%s, 0, %s, %s, false, 0)""",
            (txid_hash, to_addr, float(amount)),
        )

        # Create change UTXO if needed
        if change > Decimal("0.00000001"):
            cur.execute(
                """INSERT INTO utxos (txid, vout, address, amount, spent, block_height)
                   VALUES (%s, 1, %s, %s, false, 0)""",
                (txid_hash, from_addr, float(change)),
            )

        # Record transaction
        import json
        inputs_json = json.dumps([{"txid": s[0], "vout": s[1]} for s in selected])
        outputs_json = json.dumps([
            {"address": to_addr, "amount": str(amount)},
        ] + ([{"address": from_addr, "amount": str(change)}] if change > Decimal("0.00000001") else []))
        cur.execute(
            """INSERT INTO transactions (txid, block_height, to_address, fee, timestamp, inputs, outputs, status, tx_type)
               VALUES (%s, 0, %s, 0, %s, %s, %s, 'confirmed', 'transfer')""",
            (txid_hash, to_addr, time.time(), inputs_json, outputs_json),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    return {
        "txid": txid_hash,
        "from": from_addr,
        "to": to_addr,
        "amount": str(amount),
        "change": str(change),
        "utxos_consumed": len(selected),
    }


def dry_run(from_addr: str, to_addr: str, amount: Decimal):
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*), SUM(amount) FROM utxos WHERE address = %s AND spent = false",
        (from_addr,),
    )
    count, total = cur.fetchone()
    cur.close()
    conn.close()
    print(f"  Available: {total} QBC across {count} UTXOs")
    if total and total >= amount:
        print(f"  Transfer is FEASIBLE ({amount} <= {total})")
    else:
        print(f"  Transfer IMPOSSIBLE: need {amount}, have {total or 0}")
    print("  [DRY RUN — no changes made]")


def main():
    parser = argparse.ArgumentParser(description="Transfer QBC via CockroachDB UTXOs")
    parser.add_argument("--from-addr", required=True, help="Sender address")
    parser.add_argument("--to-addr", required=True, help="Recipient address")
    parser.add_argument("--amount", required=True, help="Amount of QBC to send")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen")
    args = parser.parse_args()

    amount = Decimal(args.amount)
    from_addr = args.from_addr.replace("0x", "").lower()
    to_addr = args.to_addr.replace("0x", "").lower()

    print(f"Transfer: {amount} QBC")
    print(f"  From: {from_addr}")
    print(f"  To:   {to_addr}")

    if args.dry_run:
        dry_run(from_addr, to_addr, amount)
        return

    result = transfer(from_addr, to_addr, amount)
    print(f"  TX ID: {result['txid']}")
    print(f"  UTXOs consumed: {result['utxos_consumed']}")
    print(f"  Change returned: {result['change']} QBC")
    print("  SUCCESS")


if __name__ == "__main__":
    main()
