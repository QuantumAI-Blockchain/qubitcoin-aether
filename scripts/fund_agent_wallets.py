#!/usr/bin/env python3
"""Fund agent wallets from the genesis 33M QBC premine + mint QUSD.

Spends the single genesis_miner 33M UTXO, creating funded UTXOs for all
agent wallets, treasury, faucet. Also mints QUSD from initial supply.

Run from QBC node machine: python3 scripts/fund_agent_wallets.py
"""

import hashlib
import json
import time
import sys
from decimal import Decimal

# CockroachDB connection — run via docker exec
COCKROACH_CMD = [
    "docker", "exec", "qbc-cockroachdb",
    "cockroach", "sql", "--insecure", "-d", "qubitcoin", "--format=csv",
]

GENESIS_ADDR = "genesis_miner"
GENESIS_TXID = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
GENESIS_VOUT = 1  # The 33M UTXO
GENESIS_AMOUNT = Decimal("33000000")

# ── QBC Allocations ──────────────────────────────────────────────────────
QBC_TRANSFERS = [
    # (address, amount, label)
    ("51d3a9b12dc4667f771b2a5ce3491631251e9d41", Decimal("3000000"), "faucet (wallet-01)"),
    ("035b5ed4454e0820002a5b1bfa36855c965fc3fe", Decimal("1000000"), "treasury"),
    ("6bfd0cf44818671068a54eba97073a2b39b83d41", Decimal("100000"), "wallet-02"),
    ("7a1fd046807e656e42cabc26e60da4ccd5864d37", Decimal("100000"), "wallet-03"),
    ("39073254200b5663945c3cbb47ae14be8da8bd24", Decimal("100000"), "wallet-04"),
    ("57c1c9e8433158b42010e9a6b359a2304a54d3a3", Decimal("100000"), "wallet-05"),
    ("3f56a174c3ed8af958d1ff8b30682e6cf03cdb5b", Decimal("100000"), "wallet-06"),
    ("b6e46cb71d41fb42e77940749fdd3e6c29abb728", Decimal("100000"), "wallet-07"),
    ("3f9f571b24b8a63df09a3ddddc1b6c854be60b76", Decimal("100000"), "wallet-08"),
    ("755805a47252ceeddd0fd07521fc80d0e6bb6015", Decimal("100000"), "wallet-09"),
    ("d47a560e242a64139407e2063642a2cf549978a2", Decimal("100000"), "wallet-10"),
    ("5059106cfdb9c9572eed70e97b2d2b03af1736aa", Decimal("50000"), "wallet-spare"),
]

# ── QUSD Allocations ─────────────────────────────────────────────────────
QUSD_TRANSFERS = [
    ("51d3a9b12dc4667f771b2a5ce3491631251e9d41", Decimal("1000000"), "faucet (wallet-01)"),
    ("035b5ed4454e0820002a5b1bfa36855c965fc3fe", Decimal("500000"), "treasury"),
    ("6bfd0cf44818671068a54eba97073a2b39b83d41", Decimal("50000"), "wallet-02"),
    ("7a1fd046807e656e42cabc26e60da4ccd5864d37", Decimal("50000"), "wallet-03"),
    ("39073254200b5663945c3cbb47ae14be8da8bd24", Decimal("50000"), "wallet-04"),
    ("57c1c9e8433158b42010e9a6b359a2304a54d3a3", Decimal("50000"), "wallet-05"),
    ("3f56a174c3ed8af958d1ff8b30682e6cf03cdb5b", Decimal("50000"), "wallet-06"),
    ("b6e46cb71d41fb42e77940749fdd3e6c29abb728", Decimal("50000"), "wallet-07"),
    ("3f9f571b24b8a63df09a3ddddc1b6c854be60b76", Decimal("50000"), "wallet-08"),
    ("755805a47252ceeddd0fd07521fc80d0e6bb6015", Decimal("50000"), "wallet-09"),
    ("d47a560e242a64139407e2063642a2cf549978a2", Decimal("50000"), "wallet-10"),
    ("5059106cfdb9c9572eed70e97b2d2b03af1736aa", Decimal("25000"), "wallet-spare"),
]


def run_sql(sql: str) -> str:
    """Execute SQL via docker exec cockroach."""
    import subprocess
    result = subprocess.run(
        COCKROACH_CMD + ["-e", sql],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(f"SQL error: {result.stderr.strip()}")
    return result.stdout.strip()


def check_genesis_utxo() -> bool:
    """Verify the genesis 33M UTXO is unspent."""
    out = run_sql(
        f"SELECT spent FROM utxos WHERE txid = '{GENESIS_TXID}' AND vout = {GENESIS_VOUT};"
    )
    lines = out.strip().split('\n')
    if len(lines) < 2:
        print("ERROR: Genesis UTXO not found!")
        return False
    spent_val = lines[1].strip()
    if spent_val == "true":
        print("ERROR: Genesis 33M UTXO already spent!")
        return False
    return True


def fund_qbc():
    """Spend genesis 33M UTXO → create funded UTXOs for all agent wallets."""
    total_out = sum(amt for _, amt, _ in QBC_TRANSFERS)
    change = GENESIS_AMOUNT - total_out
    print(f"\n{'='*60}")
    print(f"QBC FUNDING: {total_out} QBC to {len(QBC_TRANSFERS)} wallets")
    print(f"Change back to genesis_miner: {change} QBC")
    print(f"{'='*60}\n")

    if change < 0:
        print(f"ERROR: Total {total_out} exceeds genesis {GENESIS_AMOUNT}")
        return False

    # Build deterministic tx hash
    input_sig = f"{GENESIS_TXID}:{GENESIS_VOUT}"
    tx_hash = hashlib.sha256(
        f"genesis_fund:{input_sig}:{total_out}".encode()
    ).hexdigest()

    # Build all SQL in one transaction
    stmts = []

    # 1. Mark genesis UTXO as spent
    stmts.append(
        f"UPDATE utxos SET spent = true, spent_by = '{tx_hash}' "
        f"WHERE txid = '{GENESIS_TXID}' AND vout = {GENESIS_VOUT} AND spent = false;"
    )

    # 2. Create output UTXOs for each wallet
    outputs_json = []
    for vout_idx, (addr, amount, label) in enumerate(QBC_TRANSFERS):
        stmts.append(
            f"INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent) "
            f"VALUES ('{tx_hash}', {vout_idx}, '{amount}', '{addr}', '{{}}'::jsonb, 0, false);"
        )
        outputs_json.append({"address": addr, "amount": str(amount)})
        print(f"  QBC  {label:25s} → {addr[:16]}...  {amount:>12} QBC")

    # 3. Change UTXO back to genesis_miner
    if change > 0:
        change_vout = len(QBC_TRANSFERS)
        stmts.append(
            f"INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent) "
            f"VALUES ('{tx_hash}', {change_vout}, '{change}', '{GENESIS_ADDR}', '{{}}'::jsonb, 0, false);"
        )
        outputs_json.append({"address": GENESIS_ADDR, "amount": str(change)})

    # 4. Credit accounts table for each recipient
    for addr, amount, _ in QBC_TRANSFERS:
        stmts.append(
            f"INSERT INTO accounts (address, nonce, balance, code_hash, storage_root) "
            f"VALUES ('{addr}', 0, '{amount}', '', '') "
            f"ON CONFLICT (address) DO UPDATE SET balance = accounts.balance + {amount};"
        )

    # 5. Transaction record
    inputs_json = json.dumps([{"txid": GENESIS_TXID, "vout": GENESIS_VOUT}]).replace("'", "''")
    outputs_str = json.dumps(outputs_json).replace("'", "''")
    ts = time.time()
    stmts.append(
        f"INSERT INTO transactions (txid, inputs, outputs, fee, signature, public_key, "
        f"timestamp, status, tx_type, to_address, data, gas_limit, gas_price, nonce) "
        f"VALUES ('{tx_hash}', '{inputs_json}'::jsonb, '{outputs_str}'::jsonb, 0, "
        f"'genesis_premine_distribution', 'genesis', {ts}, 'confirmed', 'transfer', "
        f"'multi', 'Agent wallet funding from genesis premine', 0, 0, 0);"
    )

    # Execute as single transaction
    full_sql = "BEGIN; " + " ".join(stmts) + " COMMIT;"
    try:
        run_sql(full_sql)
        print(f"\n  TX HASH: {tx_hash}")
        print(f"  STATUS:  CONFIRMED")
        return True
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return False


def fund_qusd():
    """Mint QUSD to agent wallets from initial supply."""
    total_out = sum(amt for _, amt, _ in QUSD_TRANSFERS)
    print(f"\n{'='*60}")
    print(f"QUSD MINTING: {total_out} QUSD to {len(QUSD_TRANSFERS)} wallets")
    print(f"{'='*60}\n")

    stmts = []

    for addr, amount, label in QUSD_TRANSFERS:
        # Insert or update qusd_balances
        stmts.append(
            f"INSERT INTO qusd_balances (address, balance, locked_balance, total_minted, total_burned) "
            f"VALUES ('{addr}', {amount}, 0, {amount}, 0) "
            f"ON CONFLICT (address) DO UPDATE SET "
            f"balance = qusd_balances.balance + {amount}, "
            f"total_minted = qusd_balances.total_minted + {amount};"
        )
        print(f"  QUSD {label:25s} → {addr[:16]}...  {amount:>12} QUSD")

    # Record in qusd_operations
    op_hash = hashlib.sha256(f"qusd_mint_agents:{total_out}".encode()).hexdigest()
    stmts.append(
        f"INSERT INTO qusd_operations (operation_type, user_address, amount, collateral_locked, "
        f"collateral_type, price_at_operation, txid, status) "
        f"VALUES ('mint', 'genesis', {total_out}, {total_out}, "
        f"'QBC', 1.0, '{op_hash}', 'completed');"
    )

    full_sql = "BEGIN; " + " ".join(stmts) + " COMMIT;"
    try:
        run_sql(full_sql)
        print(f"\n  MINT HASH: {op_hash}")
        print(f"  STATUS:    CONFIRMED")
        return True
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return False


def verify():
    """Verify all wallets are funded."""
    print(f"\n{'='*60}")
    print("VERIFICATION")
    print(f"{'='*60}\n")

    # QBC balances
    out = run_sql(
        "SELECT address, balance::DECIMAL FROM accounts "
        "WHERE address IN ("
        + ",".join(f"'{a}'" for a, _, _ in QBC_TRANSFERS)
        + ") ORDER BY balance::DECIMAL DESC;"
    )
    print("  QBC Account Balances:")
    for line in out.strip().split('\n')[1:]:  # skip header
        if line.strip():
            parts = line.strip().split(',')
            if len(parts) >= 2:
                print(f"    {parts[0][:16]}...  {parts[1]:>15} QBC")

    # QUSD balances
    out = run_sql(
        "SELECT address, balance::DECIMAL FROM qusd_balances "
        "WHERE address IN ("
        + ",".join(f"'{a}'" for a, _, _ in QUSD_TRANSFERS)
        + ") ORDER BY balance::DECIMAL DESC;"
    )
    print("\n  QUSD Balances:")
    for line in out.strip().split('\n')[1:]:
        if line.strip():
            parts = line.strip().split(',')
            if len(parts) >= 2:
                print(f"    {parts[0][:16]}...  {parts[1]:>15} QUSD")

    # Genesis remainder
    out = run_sql(
        f"SELECT COALESCE(SUM(amount::DECIMAL), 0) FROM utxos "
        f"WHERE address = '{GENESIS_ADDR}' AND spent = false;"
    )
    lines = out.strip().split('\n')
    if len(lines) >= 2:
        print(f"\n  Genesis remaining: {lines[1].strip()} QBC")


def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  QBC Agent Wallet Funding — Genesis Premine + QUSD     ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # Pre-check
    if not check_genesis_utxo():
        sys.exit(1)

    # Fund QBC
    if not fund_qbc():
        print("\nQBC funding FAILED. Aborting.")
        sys.exit(1)

    # Mint QUSD
    if not fund_qusd():
        print("\nQUSD minting FAILED (QBC was funded successfully).")
        sys.exit(1)

    # Verify
    verify()

    print("\n" + "="*60)
    print("ALL DONE — wallets funded with QBC + QUSD")
    print("="*60)


if __name__ == "__main__":
    main()
