#!/usr/bin/env python3
"""
send_test_tx.py — First user-initiated QBC transfer on the Substrate chain.

Steps:
1. Register the Dilithium5 public key for the miner's coinbase address (via sudo)
2. Find a mature coinbase UTXO (age >= 100 blocks)
3. Build inputs/outputs matching the Substrate signing_message format
4. Sign with Dilithium5
5. Submit via QbcUtxo.submit_transaction extrinsic

Requires: substrateinterface, pqcrypto
"""

import hashlib
import os
import struct
import sys

from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException


def load_dilithium_keys():
    """Load Dilithium5 keys from secure_key.env."""
    env_path = os.path.join(os.path.dirname(__file__), '..', 'secure_key.env')
    keys = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                keys[k.strip()] = v.strip().strip('"').strip("'")
    return keys


def get_miner_address(ws):
    """Get the last miner address from Substrate storage."""
    result = ws.query('QbcConsensus', 'LastMiner')
    if result is None:
        raise RuntimeError("No miner address found — chain may not be mining")
    addr_hex = str(result)
    return addr_hex


def find_mature_utxo(ws, miner_address_hex, current_height):
    """Find a coinbase UTXO for the miner address that's mature (age >= 100)."""
    # Query all storage keys for UtxoSet
    # The key format is: twox128("QbcUtxo") + twox128("UtxoSet") + Blake2_128Concat(txid, vout)
    prefix = ws.get_metadata_module_prefix("QbcUtxo", "UtxoSet")

    # Use state_getKeys to enumerate UTXOs
    keys = ws.query_map('QbcUtxo', 'UtxoSet', max_results=500)

    mature_utxos = []
    for key, utxo in keys:
        if utxo is None:
            continue
        utxo_val = utxo.value if hasattr(utxo, 'value') else utxo

        # Extract address from UTXO
        utxo_address = utxo_val.get('address', '') if isinstance(utxo_val, dict) else ''
        if not utxo_address:
            continue

        # Normalize addresses for comparison
        utxo_addr_clean = str(utxo_address).lower().replace('0x', '')
        miner_clean = miner_address_hex.lower().replace('0x', '')

        if utxo_addr_clean != miner_clean:
            continue

        block_height = utxo_val.get('block_height', 0) if isinstance(utxo_val, dict) else 0
        is_coinbase = utxo_val.get('is_coinbase', False) if isinstance(utxo_val, dict) else False
        amount = utxo_val.get('amount', 0) if isinstance(utxo_val, dict) else 0
        txid = utxo_val.get('txid', '') if isinstance(utxo_val, dict) else ''
        vout = utxo_val.get('vout', 0) if isinstance(utxo_val, dict) else 0

        age = current_height - block_height
        if age >= 100 and amount > 0:
            mature_utxos.append({
                'txid': txid,
                'vout': vout,
                'amount': amount,
                'block_height': block_height,
                'is_coinbase': is_coinbase,
                'age': age,
            })

    # Sort by age (oldest first) to use most mature UTXOs
    mature_utxos.sort(key=lambda u: u['age'], reverse=True)
    return mature_utxos


def build_signing_message(inputs, outputs):
    """
    Build the Substrate signing message format:
      msg = prev_txid_bytes(32) || prev_vout_le(4) || ... || addr_bytes(32) || amount_le(16) || ...
    """
    msg = b''
    for inp in inputs:
        txid_bytes = bytes.fromhex(inp['txid'].replace('0x', ''))
        assert len(txid_bytes) == 32, f"txid must be 32 bytes, got {len(txid_bytes)}"
        msg += txid_bytes
        msg += struct.pack('<I', inp['vout'])  # u32 little-endian

    for out in outputs:
        addr_bytes = bytes.fromhex(out['address'].replace('0x', ''))
        assert len(addr_bytes) == 32, f"address must be 32 bytes, got {len(addr_bytes)}"
        msg += addr_bytes
        msg += struct.pack('<QQ', out['amount'] & 0xFFFFFFFFFFFFFFFF, out['amount'] >> 64)  # u128 little-endian

    return msg


def sign_dilithium5(private_key_hex, message):
    """Sign a message with Dilithium5 and return the signature bytes."""
    from pqcrypto.sign.dilithium5 import sign as dilithium_sign

    private_key_bytes = bytes.fromhex(private_key_hex)
    # pqcrypto.sign.dilithium5.sign returns (signed_message, )
    # We need detached signature, so use the low-level API
    signed_msg = dilithium_sign(message, private_key_bytes)
    # The signed message = signature || message
    # Dilithium5 signature size = 4627 bytes
    SIG_SIZE = 4627
    signature = signed_msg[:SIG_SIZE]
    return signature


def main():
    print("=== Qubitcoin Test Transaction ===\n")

    # Connect to Substrate
    ws_url = os.environ.get('SUBSTRATE_WS', 'ws://localhost:9944')
    print(f"Connecting to {ws_url}...")
    ws = SubstrateInterface(url=ws_url)

    # Load keys
    keys = load_dilithium_keys()
    dilithium_pk_hex = keys.get('PUBLIC_KEY_HEX', '')
    dilithium_sk_hex = keys.get('PRIVATE_KEY_HEX', '')
    miner_addr_20 = keys.get('ADDRESS', '')

    if not dilithium_pk_hex or not dilithium_sk_hex:
        print("ERROR: Missing Dilithium keys in secure_key.env")
        sys.exit(1)

    print(f"Dilithium5 PK: {dilithium_pk_hex[:16]}... ({len(dilithium_pk_hex)//2} bytes)")
    print(f"Python address: {miner_addr_20}")

    # Get chain state
    current_height = ws.query('QbcUtxo', 'CurrentHeight').value
    utxo_count = ws.query('QbcUtxo', 'UtxoCount').value
    tx_count = ws.query('QbcUtxo', 'TxCount').value
    miner_address = get_miner_address(ws)

    print(f"\nChain state:")
    print(f"  Height: {current_height}")
    print(f"  UTXOs: {utxo_count}")
    print(f"  Transactions: {tx_count}")
    print(f"  Last miner: {miner_address}")

    # Step 1: Register Dilithium key for miner address via sudo
    print(f"\n--- Step 1: Register Dilithium5 key for miner address ---")

    # Check if key already registered
    existing_key = ws.query('QbcDilithium', 'PublicKeys', params=[miner_address])
    if existing_key and existing_key.value:
        print(f"  Key already registered for {miner_address[:16]}...")
    else:
        print(f"  Registering Dilithium5 key for {miner_address[:16]}...")
        alice = Keypair.create_from_uri('//Alice')

        pk_bytes = bytes.fromhex(dilithium_pk_hex)
        addr_bytes = bytes.fromhex(miner_address.replace('0x', ''))

        call = ws.compose_call(
            call_module='Sudo',
            call_function='sudo',
            call_params={
                'call': ws.compose_call(
                    call_module='QbcDilithium',
                    call_function='sudo_register_key_for_address',
                    call_params={
                        'address': f'0x{addr_bytes.hex()}',
                        'public_key': f'0x{pk_bytes.hex()}',
                    }
                )
            }
        )

        try:
            extrinsic = ws.create_signed_extrinsic(call=call, keypair=alice)
            receipt = ws.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            if receipt.is_success:
                print(f"  SUCCESS: Dilithium key registered (tx: {receipt.extrinsic_hash})")
            else:
                print(f"  FAILED: {receipt.error_message}")
                sys.exit(1)
        except SubstrateRequestException as e:
            print(f"  FAILED: {e}")
            sys.exit(1)

    # Step 2: Find a mature coinbase UTXO
    print(f"\n--- Step 2: Find mature coinbase UTXO ---")
    mature_utxos = find_mature_utxo(ws, miner_address, current_height)

    if not mature_utxos:
        print("  ERROR: No mature UTXOs found for miner address")
        print(f"  Miner address: {miner_address}")
        print(f"  Current height: {current_height}")
        print("  Need coinbase UTXOs with age >= 100 blocks")
        sys.exit(1)

    utxo = mature_utxos[0]
    print(f"  Found UTXO: txid={utxo['txid'][:16]}..., vout={utxo['vout']}, amount={utxo['amount']}, age={utxo['age']}")

    # Step 3: Build transaction
    print(f"\n--- Step 3: Build transaction ---")

    # Send 1 QBC (100_000_000 smallest units) to Bob's address
    # Bob's address = SHA-256(Bob's Ed25519 public key)
    bob_keypair = Keypair.create_from_uri('//Bob')
    bob_ed25519_pk = bob_keypair.public_key
    bob_address = hashlib.sha256(bob_ed25519_pk).digest()

    send_amount = 100_000_000  # 1 QBC
    fee_amount = 1_000_000     # 0.01 QBC fee
    change_amount = utxo['amount'] - send_amount - fee_amount

    if change_amount < 0:
        print(f"  ERROR: UTXO amount ({utxo['amount']}) too small for 1 QBC + fee")
        sys.exit(1)

    inputs = [{'txid': utxo['txid'], 'vout': utxo['vout']}]
    outputs = [
        {'address': bob_address.hex(), 'amount': send_amount},
    ]
    if change_amount > 0:
        outputs.append({
            'address': miner_address.replace('0x', ''),
            'amount': change_amount,
        })

    print(f"  Input: {utxo['amount']} from {utxo['txid'][:16]}...")
    print(f"  Output 0: {send_amount} to Bob ({bob_address.hex()[:16]}...)")
    if change_amount > 0:
        print(f"  Output 1: {change_amount} change to miner")
    print(f"  Fee: {fee_amount}")

    # Step 4: Sign with Dilithium5
    print(f"\n--- Step 4: Sign with Dilithium5 ---")
    signing_msg = build_signing_message(inputs, outputs)
    print(f"  Signing message: {len(signing_msg)} bytes")

    signature = sign_dilithium5(dilithium_sk_hex, signing_msg)
    print(f"  Signature: {len(signature)} bytes")

    # Step 5: Submit transaction
    print(f"\n--- Step 5: Submit transaction ---")

    alice = Keypair.create_from_uri('//Alice')

    txid_hex = utxo['txid'].replace('0x', '')
    bob_addr_hex = bob_address.hex()
    miner_addr_hex = miner_address.replace('0x', '')

    call_inputs = [{'prev_txid': f'0x{txid_hex}', 'prev_vout': utxo['vout']}]
    call_outputs = [{'address': f'0x{bob_addr_hex}', 'amount': send_amount}]
    if change_amount > 0:
        call_outputs.append({'address': f'0x{miner_addr_hex}', 'amount': change_amount})

    call = ws.compose_call(
        call_module='QbcUtxo',
        call_function='submit_transaction',
        call_params={
            'inputs': call_inputs,
            'outputs': call_outputs,
            'signatures': [f'0x{signature.hex()}'],
        }
    )

    try:
        extrinsic = ws.create_signed_extrinsic(call=call, keypair=alice)
        receipt = ws.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        if receipt.is_success:
            print(f"\n  SUCCESS! First user transaction on Qubitcoin!")
            print(f"  Extrinsic hash: {receipt.extrinsic_hash}")
            print(f"  Block hash: {receipt.block_hash}")

            # Verify Bob's balance
            bob_balance = ws.query('QbcUtxo', 'Balances', params=[f'0x{bob_addr_hex}'])
            print(f"\n  Bob's balance: {bob_balance} (expected: {send_amount})")
        else:
            print(f"\n  FAILED: {receipt.error_message}")
            # Print events for debugging
            for event in receipt.triggered_events:
                print(f"    Event: {event}")
    except SubstrateRequestException as e:
        print(f"\n  FAILED: {e}")
        sys.exit(1)

    print(f"\n=== Done ===")


if __name__ == '__main__':
    main()
