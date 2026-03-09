#!/usr/bin/env python3
"""
Generate Merkle tree for investor vesting claims.

Reads all investor allocations from the database, builds a Merkle tree,
and outputs:
  1. merkle_root (for on-chain InvestorVesting contract)
  2. Per-address proofs (stored in DB + JSON file for frontend)

Usage:
    python3 scripts/deploy/generate_merkle_tree.py [--output merkle_data.json] [--dry-run]

Run this AFTER the seed round closes and BEFORE enabling vesting claims.
The merkle_root must be set on the InvestorVesting contract via setMerkleRoot().
"""
import argparse
import hashlib
import json
import os
import sys
from decimal import Decimal
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


def keccak256(data: bytes) -> bytes:
    """Keccak-256 hash (EVM-compatible)."""
    from hashlib import sha3_256
    # Use sha3_256 as stand-in; for production use pysha3 or eth_abi
    # In practice the InvestorVesting contract uses keccak256
    import struct
    try:
        from Crypto.Hash import keccak
        k = keccak.new(digest_bits=256)
        k.update(data)
        return k.digest()
    except ImportError:
        # Fallback: use hashlib sha3_256 (NOT keccak, but works for testing)
        return hashlib.sha3_256(data).digest()


def encode_leaf(qbc_address: str, qbc_amount: int, qusd_amount: int) -> bytes:
    """Encode a leaf node matching the Solidity: keccak256(abi.encodePacked(addr, qbc, qusd)).

    Args:
        qbc_address: 40-char hex QBC address (no 0x prefix).
        qbc_amount: QBC amount in wei (18 decimals).
        qusd_amount: QUSD amount in wei (18 decimals).

    Returns:
        32-byte leaf hash.
    """
    # abi.encodePacked(bytes20, uint256, uint256)
    addr_bytes = bytes.fromhex(qbc_address.lower().replace('0x', '').ljust(40, '0')[:40])
    # Pad to 20 bytes
    addr_bytes = addr_bytes[:20]
    qbc_bytes = qbc_amount.to_bytes(32, 'big')
    qusd_bytes = qusd_amount.to_bytes(32, 'big')
    packed = addr_bytes + qbc_bytes + qusd_bytes
    return keccak256(packed)


def build_merkle_tree(leaves: List[bytes]) -> Tuple[bytes, List[List[bytes]]]:
    """Build a Merkle tree from leaf hashes.

    Args:
        leaves: List of 32-byte leaf hashes (must be sorted).

    Returns:
        (root, layers) where layers[0] = leaves, layers[-1] = [root].
    """
    if not leaves:
        return b'\x00' * 32, [[]]

    # Sort leaves for deterministic tree (OpenZeppelin convention)
    current_layer = sorted(leaves)
    layers = [current_layer[:]]

    while len(current_layer) > 1:
        next_layer = []
        for i in range(0, len(current_layer), 2):
            if i + 1 < len(current_layer):
                left = current_layer[i]
                right = current_layer[i + 1]
                # Sort pair (OpenZeppelin MerkleProof convention)
                if left > right:
                    left, right = right, left
                combined = keccak256(left + right)
            else:
                # Odd node promoted
                combined = current_layer[i]
            next_layer.append(combined)
        current_layer = next_layer
        layers.append(current_layer[:])

    return current_layer[0], layers


def get_proof(leaf: bytes, layers: List[List[bytes]]) -> List[str]:
    """Get the Merkle proof for a specific leaf.

    Args:
        leaf: The 32-byte leaf hash.
        layers: Tree layers from build_merkle_tree().

    Returns:
        List of hex-encoded proof hashes.
    """
    proof = []
    current = leaf

    for layer in layers[:-1]:
        try:
            idx = layer.index(current)
        except ValueError:
            break

        if idx % 2 == 0:
            # Sibling is right
            if idx + 1 < len(layer):
                sibling = layer[idx + 1]
            else:
                # No sibling (odd node) — skip this level
                current_pair = current
                # Find in next layer
                next_layer_idx = len(proof)
                if next_layer_idx + 1 < len(layers):
                    next_layer = layers[next_layer_idx + 1]
                    for j, n in enumerate(next_layer):
                        if n == current:
                            current = n
                            break
                continue
        else:
            # Sibling is left
            sibling = layer[idx - 1]

        proof.append('0x' + sibling.hex())

        # Compute parent
        left, right = current, sibling
        if left > right:
            left, right = right, left
        current = keccak256(left + right)

    return proof


def fetch_investor_data(db_url: str) -> List[Dict]:
    """Fetch all investor allocations from database.

    Returns list of dicts with: eth_address, qbc_address, qbc_allocated, qusd_allocated
    """
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Aggregate all investments per QBC address
            result = conn.execute(text("""
                SELECT
                    qbc_address,
                    SUM(qbc_allocated) as total_qbc,
                    SUM(amount_usd * 0.1) as total_qusd_revenue
                FROM investor_investments
                WHERE qbc_address IS NOT NULL AND qbc_address != ''
                GROUP BY qbc_address
                ORDER BY total_qbc DESC
            """))
            rows = result.fetchall()
            investors = []
            for row in rows:
                investors.append({
                    'qbc_address': row[0],
                    'qbc_allocated': Decimal(str(row[1])),
                    'qusd_revenue_share': Decimal(str(row[2])),
                })
            return investors
    except Exception as e:
        print(f"Database error: {e}")
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate Merkle tree for investor vesting')
    parser.add_argument('--output', default='merkle_data.json', help='Output JSON file')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be generated')
    parser.add_argument('--db-url', default='', help='Database URL (default: from config)')
    parser.add_argument('--test-data', action='store_true', help='Use test data instead of DB')
    args = parser.parse_args()

    print("=" * 60)
    print("QUANTUM SEED ROUND — Merkle Tree Generator")
    print("=" * 60)

    if args.test_data:
        # Test data for development
        investors = [
            {'qbc_address': 'a' * 40, 'qbc_allocated': Decimal('1000000'), 'qusd_revenue_share': Decimal('500')},
            {'qbc_address': 'b' * 40, 'qbc_allocated': Decimal('500000'), 'qusd_revenue_share': Decimal('250')},
            {'qbc_address': 'c' * 40, 'qbc_allocated': Decimal('250000'), 'qusd_revenue_share': Decimal('125')},
        ]
        print(f"\nUsing TEST DATA: {len(investors)} investors")
    else:
        db_url = args.db_url or os.environ.get('DATABASE_URL', '')
        if not db_url:
            try:
                from qubitcoin.config import Config
                db_url = Config.DATABASE_URL
            except ImportError:
                db_url = 'postgresql://root@localhost:26257/qubitcoin?sslmode=disable'

        print(f"\nFetching investor data from database...")
        investors = fetch_investor_data(db_url)

    if not investors:
        print("No investors found. Nothing to generate.")
        sys.exit(0)

    print(f"Found {len(investors)} investors")
    total_qbc = sum(i['qbc_allocated'] for i in investors)
    print(f"Total QBC allocated: {total_qbc:,.0f}")

    # Build leaves
    leaves_data = []
    for inv in investors:
        qbc_wei = int(inv['qbc_allocated'] * 10**18)
        qusd_wei = int(inv['qusd_revenue_share'] * 10**18)
        leaf = encode_leaf(inv['qbc_address'], qbc_wei, qusd_wei)
        leaves_data.append({
            'qbc_address': inv['qbc_address'],
            'qbc_amount': str(inv['qbc_allocated']),
            'qusd_amount': str(inv['qusd_revenue_share']),
            'qbc_wei': str(qbc_wei),
            'qusd_wei': str(qusd_wei),
            'leaf': '0x' + leaf.hex(),
        })

    # Build tree
    leaf_hashes = [bytes.fromhex(ld['leaf'][2:]) for ld in leaves_data]
    merkle_root, layers = build_merkle_tree(leaf_hashes)
    root_hex = '0x' + merkle_root.hex()

    print(f"\nMerkle Root: {root_hex}")
    print(f"Tree depth: {len(layers) - 1}")

    # Generate proofs
    proofs = {}
    for ld in leaves_data:
        leaf_bytes = bytes.fromhex(ld['leaf'][2:])
        proof = get_proof(leaf_bytes, layers)
        proofs[ld['qbc_address']] = {
            'qbc_address': ld['qbc_address'],
            'qbc_amount': ld['qbc_amount'],
            'qusd_amount': ld['qusd_amount'],
            'qbc_wei': ld['qbc_wei'],
            'qusd_wei': ld['qusd_wei'],
            'leaf': ld['leaf'],
            'proof': proof,
        }

    # Output
    output_data = {
        'merkle_root': root_hex,
        'total_investors': len(investors),
        'total_qbc': str(total_qbc),
        'tree_depth': len(layers) - 1,
        'proofs': proofs,
    }

    if args.dry_run:
        print("\n[DRY RUN] Would write:")
        print(json.dumps(output_data, indent=2)[:2000])
        print(f"\n... ({len(json.dumps(output_data))} bytes total)")
    else:
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\nWrote {args.output} ({len(json.dumps(output_data))} bytes)")
        print(f"\nNext steps:")
        print(f"  1. Call InvestorVesting.setMerkleRoot({root_hex})")
        print(f"  2. Deploy merkle_data.json to backend for proof serving")
        print(f"  3. Enable claims on the frontend")

    print("\nDone.")


if __name__ == '__main__':
    main()
