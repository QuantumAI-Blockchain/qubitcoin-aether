#!/usr/bin/env python3
"""
send_test_tx.py — First user-initiated QBC transfer on the Substrate chain.

Steps:
1. Scan UTXOs to find a mature coinbase UTXO
2. Register the Dilithium5 public key for that UTXO's address (via sudo)
3. Build inputs/outputs matching the Substrate signing_message format
4. Sign with Dilithium5
5. Submit via QbcUtxo.submit_transaction extrinsic

Requires: substrate-interface, pqcrypto
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


def find_mature_utxo(ws, current_height):
    """Find ANY mature coinbase UTXO (age >= 100). Returns (utxo_dict, address_hex)."""
    print("  Scanning UTXOs (max 500)...")
    keys = ws.query_map('QbcUtxo', 'UtxoSet', max_results=500)

    mature_utxos = []
    scanned = 0
    for key, utxo in keys:
        scanned += 1
        if utxo is None:
            continue
        utxo_val = utxo.value if hasattr(utxo, 'value') else utxo
        if not isinstance(utxo_val, dict):
            continue

        address = str(utxo_val.get('address', ''))
        block_height = utxo_val.get('block_height', 0)
        amount = utxo_val.get('amount', 0)
        txid = str(utxo_val.get('txid', ''))
        vout = utxo_val.get('vout', 0)
        is_coinbase = utxo_val.get('is_coinbase', False)

        if not address or amount <= 0:
            continue

        age = current_height - block_height
        if age >= 100:
            mature_utxos.append({
                'txid': txid,
                'vout': vout,
                'amount': amount,
                'block_height': block_height,
                'is_coinbase': is_coinbase,
                'age': age,
                'address': address,
            })

    print(f"  Scanned {scanned} UTXOs, found {len(mature_utxos)} mature (age >= 100)")

    # Sort by age descending (oldest first)
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


def sign_dilithium5(private_key_bytes, message):
    """Sign a message with ML-DSA-87 (Dilithium5) and return the 4627-byte signature."""
    from pqcrypto.sign.ml_dsa_87 import sign as dilithium_sign

    signature = dilithium_sign(private_key_bytes, message)
    assert len(signature) == 4627, f"Expected 4627-byte signature, got {len(signature)}"
    return signature


def main():
    print("=== Qubitcoin Test Transaction ===\n")

    # Connect to Substrate
    ws_url = os.environ.get('SUBSTRATE_WS', 'ws://localhost:9944')
    print(f"Connecting to {ws_url}...")
    ws = SubstrateInterface(url=ws_url)
    ws.init_runtime()

    # Generate fresh ML-DSA-87 (Dilithium5) keys for this transaction.
    # We generate fresh keys because the secure_key.env keys use the original
    # Dilithium5 format (sk=4864) which is incompatible with the pqcrypto
    # ML-DSA-87 signer (sk=4896). Both produce 2592-byte PKs and 4627-byte sigs.
    from pqcrypto.sign.ml_dsa_87 import generate_keypair
    dilithium_pk, dilithium_sk = generate_keypair()
    print(f"Generated ML-DSA-87 keypair: PK={len(dilithium_pk)} bytes, SK={len(dilithium_sk)} bytes")

    # Get chain state
    current_height = ws.query('QbcUtxo', 'CurrentHeight').value
    utxo_count = ws.query('QbcUtxo', 'UtxoCount').value
    tx_count = ws.query('QbcUtxo', 'TxCount').value

    print(f"\nChain state:")
    print(f"  Height: {current_height}")
    print(f"  UTXOs: {utxo_count}")
    print(f"  Transactions: {tx_count}")

    # Step 1: Find a mature coinbase UTXO
    print(f"\n--- Step 1: Find mature coinbase UTXO ---")
    mature_utxos = find_mature_utxo(ws, current_height)

    if not mature_utxos:
        print("  ERROR: No mature UTXOs found")
        print(f"  Current height: {current_height}")
        print("  Need coinbase UTXOs with age >= 100 blocks")
        sys.exit(1)

    utxo = mature_utxos[0]
    utxo_address = utxo['address']
    print(f"  Using UTXO: txid={utxo['txid'][:16]}..., vout={utxo['vout']}, "
          f"amount={utxo['amount']}, age={utxo['age']}")
    print(f"  UTXO address: {utxo_address}")

    # Step 2: Register Dilithium key for the UTXO's address via sudo
    print(f"\n--- Step 2: Register Dilithium5 key for UTXO address ---")

    existing_key = ws.query('QbcDilithium', 'PublicKeys', params=[utxo_address])
    if existing_key and existing_key.value:
        print(f"  Key already registered for {utxo_address[:18]}... (different key, need fresh UTXO)")
        # Find a UTXO with an address that has NO key registered
        found = False
        for u in mature_utxos:
            addr = u['address']
            ek = ws.query('QbcDilithium', 'PublicKeys', params=[addr])
            if not ek or not ek.value:
                utxo = u
                utxo_address = addr
                utxo_addr_hex = utxo_address.replace('0x', '')
                print(f"  Switched to UTXO: txid={utxo['txid'][:16]}..., address={utxo_address[:18]}...")
                found = True
                break
        if not found:
            print("  ERROR: All UTXO addresses already have keys registered (from different keys)")
            print("  Cannot proceed — would need to clear old keys first")
            sys.exit(1)

    existing_key2 = ws.query('QbcDilithium', 'PublicKeys', params=[utxo_address])
    if existing_key2 and existing_key2.value:
        print(f"  Key already registered for {utxo_address[:18]}...")
    else:
        print(f"  Registering Dilithium5 key for {utxo_address[:18]}...")
        alice = Keypair.create_from_uri('//Alice')

        pk_bytes = dilithium_pk
        addr_hex = utxo_address.replace('0x', '')

        call = ws.compose_call(
            call_module='Sudo',
            call_function='sudo',
            call_params={
                'call': ws.compose_call(
                    call_module='QbcDilithium',
                    call_function='sudo_register_key_for_address',
                    call_params={
                        'address': f'0x{addr_hex}',
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
    utxo_addr_hex = utxo_address.replace('0x', '')
    if change_amount > 0:
        outputs.append({
            'address': utxo_addr_hex,
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

    signature = sign_dilithium5(dilithium_sk, signing_msg)
    print(f"  Signature: {len(signature)} bytes")

    # Step 5: Submit transaction via raw SCALE-encoded call
    # (substrate-interface can't encode BoundedVec<BoundedVec<u8, N>>)
    print(f"\n--- Step 5: Submit transaction ---")

    alice = Keypair.create_from_uri('//Alice')

    def encode_compact(val):
        if val <= 0x3f:
            return bytes([val << 2])
        elif val <= 0x3fff:
            return struct.pack('<H', (val << 2) | 0b01)
        elif val <= 0x3fffffff:
            return struct.pack('<I', (val << 2) | 0b10)
        else:
            bts = val.to_bytes((val.bit_length() + 7) // 8, 'little')
            return bytes([((len(bts) - 4) << 2) | 0b11]) + bts

    # Build raw SCALE call bytes for QbcUtxo(8).submit_transaction(0)
    txid_bytes = bytes.fromhex(utxo['txid'].replace('0x', ''))
    bob_addr_bytes = bob_address
    change_addr_bytes = bytes.fromhex(utxo_addr_hex)

    # Encode inputs: compact_len + (txid(32) + vout_le(4)) per input
    inputs_enc = encode_compact(1)  # 1 input
    inputs_enc += txid_bytes + struct.pack('<I', utxo['vout'])

    # Encode outputs: compact_len + (address(32) + amount_le(16)) per output
    num_outputs = 2 if change_amount > 0 else 1
    outputs_enc = encode_compact(num_outputs)
    outputs_enc += bob_addr_bytes + struct.pack('<QQ', send_amount & 0xFFFFFFFFFFFFFFFF, send_amount >> 64)
    if change_amount > 0:
        outputs_enc += change_addr_bytes + struct.pack('<QQ', change_amount & 0xFFFFFFFFFFFFFFFF, change_amount >> 64)

    # Encode signatures: compact_len(1) + (compact_len(sig_size) + sig_bytes)
    sigs_enc = encode_compact(1)  # 1 signature
    sigs_enc += encode_compact(len(signature)) + signature

    # Full call: pallet_idx(8) + call_idx(0) + inputs + outputs + signatures
    raw_call = bytes([8, 0]) + inputs_enc + outputs_enc + sigs_enc
    print(f"  Raw call: {len(raw_call)} bytes")

    # Sign and submit via manual extrinsic construction
    from hashlib import blake2b

    nonce_result = ws.rpc_request('system_accountNextIndex', [alice.ss58_address])
    nonce = nonce_result['result']
    genesis = ws.get_block_hash(0)
    genesis_bytes = bytes.fromhex(genesis.replace('0x', ''))

    # Extra: era(immortal) + nonce(compact) + tip(compact 0)
    extra = bytes([0x00]) + encode_compact(nonce) + encode_compact(0)

    # Additional signed: (), spec_version(u32), tx_version(u32), genesis, genesis, (), (), ()
    additional = struct.pack('<II', 104, 1) + genesis_bytes + genesis_bytes

    # Signing payload
    payload = raw_call + extra + additional
    if len(payload) > 256:
        sig_input = blake2b(payload, digest_size=32).digest()
    else:
        sig_input = payload

    sr25519_sig = alice.sign(sig_input)

    # Build full extrinsic
    ext_body = bytes([0x84])  # signed, v4
    ext_body += bytes([0x00]) + alice.public_key  # MultiAddress::Id
    ext_body += bytes([0x01]) + sr25519_sig  # MultiSignature::Sr25519
    ext_body += extra
    ext_body += raw_call

    full_ext = encode_compact(len(ext_body)) + ext_body
    print(f"  Extrinsic: {len(full_ext)} bytes, nonce={nonce}")

    try:
        result = ws.rpc_request('author_submitExtrinsic', ['0x' + full_ext.hex()])
        print(f"\n  SUCCESS! First user transaction on Qubitcoin!")
        print(f"  Extrinsic hash: {result['result']}")
    except SubstrateRequestException as e:
        err = str(e)
        print(f"\n  FAILED: {err[:200]}")
        if 'InvalidSignature' in err:
            print("  NOTE: ML-DSA-87 signatures may be incompatible with pqcrypto-dilithium verifier")
        sys.exit(1)

    print(f"\n=== Done ===")


if __name__ == '__main__':
    main()
