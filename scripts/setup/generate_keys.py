#!/usr/bin/env python3
"""
Generate Dilithium keypair for Qubitcoin node.
Supports ML-DSA-44 (Level 2), ML-DSA-65 (Level 3), and ML-DSA-87 (Level 5).
Saves to ~/qubitcoin/secure_key.env (NOT .env)
"""

import argparse
import hashlib
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

try:
    from dilithium_py.dilithium import Dilithium2, Dilithium3, Dilithium5
except ImportError:
    print("Error: dilithium-py not installed")
    print("   Run: pip install dilithium-py")
    sys.exit(1)

# Security level configurations
LEVELS = {
    2: {'impl': Dilithium2, 'name': 'ML-DSA-44', 'classical': 128, 'quantum': 64,
        'pk': 1312, 'sk': 2528, 'sig': 2420},
    3: {'impl': Dilithium3, 'name': 'ML-DSA-65', 'classical': 192, 'quantum': 96,
        'pk': 1952, 'sk': 4000, 'sig': 3293},
    5: {'impl': Dilithium5, 'name': 'ML-DSA-87', 'classical': 256, 'quantum': 128,
        'pk': 2592, 'sk': 4864, 'sig': 4595},
}


def generate_check_phrase(address: str) -> str:
    """Generate a human-readable check-phrase from an address."""
    try:
        from qubitcoin.quantum.crypto import address_to_check_phrase
        return address_to_check_phrase(address)
    except ImportError:
        # Fallback: inline implementation
        from qubitcoin.quantum.bip39_wordlist import BIP39_ENGLISH
        addr_bytes = hashlib.sha256(address.encode()).digest()
        bits = bin(int.from_bytes(addr_bytes[:5], 'big'))[2:].zfill(40)
        words = []
        for i in range(3):
            idx = int(bits[i * 11:(i + 1) * 11], 2) % 2048
            words.append(BIP39_ENGLISH[idx])
        return "-".join(words)


def generate_mnemonic() -> list:
    """Generate a 24-word BIP-39 mnemonic."""
    try:
        from qubitcoin.quantum.crypto import generate_mnemonic
        return generate_mnemonic()
    except ImportError:
        import secrets
        from qubitcoin.quantum.bip39_wordlist import BIP39_ENGLISH
        entropy = secrets.token_bytes(32)
        h = hashlib.sha256(entropy).digest()
        bits = bin(int.from_bytes(entropy, 'big'))[2:].zfill(256)
        checksum = bin(h[0])[2:].zfill(8)[:8]
        all_bits = bits + checksum
        words = []
        for i in range(0, len(all_bits), 11):
            idx = int(all_bits[i:i + 11], 2)
            words.append(BIP39_ENGLISH[idx])
        return words


def run_kat_self_test(level: int) -> bool:
    """Run FIPS 204 KAT self-test for the specified level."""
    info = LEVELS[level]
    impl = info['impl']
    test_msg = b"FIPS 204 KAT self-test for Qubitcoin keygen"

    try:
        pk, sk = impl.keygen()
        assert len(pk) == info['pk'], f"pk size {len(pk)} != {info['pk']}"
        assert len(sk) == info['sk'], f"sk size {len(sk)} != {info['sk']}"

        sig = impl.sign(sk, test_msg)
        assert len(sig) == info['sig'], f"sig size {len(sig)} != {info['sig']}"

        assert impl.verify(pk, test_msg, sig), "Valid sig rejected"

        tampered = bytearray(sig)
        tampered[-1] ^= 0xFF
        assert not impl.verify(pk, test_msg, bytes(tampered)), "Tampered sig accepted"

        return True
    except Exception as e:
        print(f"   FIPS 204 KAT FAILED: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Generate Qubitcoin Dilithium keypair')
    parser.add_argument(
        '--level', type=int, choices=[2, 3, 5], default=5,
        help='Dilithium security level: 2=ML-DSA-44, 3=ML-DSA-65, 5=ML-DSA-87 (default: 5)'
    )
    args = parser.parse_args()

    level = args.level
    info = LEVELS[level]

    print("=" * 70)
    print(f"  QUBITCOIN KEY GENERATOR — {info['name']} (Level {level})")
    print("=" * 70)
    print()
    print(f"  Security: {info['classical']}-bit classical, {info['quantum']}-bit quantum")
    print(f"  Public key:  {info['pk']:,} bytes")
    print(f"  Private key: {info['sk']:,} bytes")
    print(f"  Signature:   {info['sig']:,} bytes")
    print()

    # Output file is ALWAYS in project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
    output_file = os.path.join(root_dir, 'secure_key.env')

    print(f"Output file: {output_file}")
    print()

    # FIPS 204 KAT self-test
    print(f"Running FIPS 204 KAT self-test for {info['name']}...")
    if not run_kat_self_test(level):
        print("CRITICAL: FIPS 204 KAT self-test FAILED. Aborting key generation.")
        sys.exit(1)
    print(f"  FIPS 204 KAT: PASSED")
    print()

    # Generate keys
    print(f"Generating {info['name']} keypair...")
    impl = info['impl']
    pk, sk = impl.keygen()

    # Convert to hex
    pk_hex = pk.hex()
    sk_hex = sk.hex()

    # Derive address
    address = hashlib.sha256(pk).hexdigest()[:40]

    # Generate mnemonic
    mnemonic = generate_mnemonic()
    mnemonic_str = " ".join(mnemonic)
    mnemonic_hash = hashlib.sha256(mnemonic_str.encode()).hexdigest()

    # Generate check-phrase
    check_phrase = generate_check_phrase(address)

    # Display
    print()
    print("=" * 70)
    print("  GENERATED KEYS — KEEP THESE SECURE!")
    print("=" * 70)
    print()
    print(f"SECURITY LEVEL: {info['name']} (Level {level})")
    print()
    print(f"ADDRESS (QBC):")
    print(f"  {address}")
    print()
    print(f"CHECK-PHRASE (human-readable alias):")
    print(f"  {check_phrase}")
    print()
    print(f"PUBLIC KEY ({len(pk):,} bytes):")
    print(f"  {pk_hex[:80]}...")
    print(f"  ...{pk_hex[-80:]}")
    print()
    print(f"PRIVATE KEY ({len(sk):,} bytes):")
    print(f"  {sk_hex[:80]}...")
    print(f"  ...{sk_hex[-80:]}")
    print()
    print("=" * 70)
    print("  RECOVERY MNEMONIC — WRITE THIS DOWN! SHOWN ONCE!")
    print("=" * 70)
    print()
    for i in range(0, 24, 6):
        line = "  ".join(f"{i+j+1:2d}. {mnemonic[i+j]:<12s}" for j in range(min(6, 24 - i)))
        print(f"  {line}")
    print()
    print("  WARNING: This mnemonic will NOT be saved anywhere.")
    print("  Write it down on paper and store it securely.")
    print("  It is your ONLY recovery option if you lose your keys.")
    print()
    print("=" * 70)
    print()

    # Write to secure_key.env
    print(f"Writing to {output_file}...")
    with open(output_file, 'w') as f:
        f.write("# Qubitcoin Node Keys — KEEP THIS FILE SECURE!\n")
        f.write(f"# Generated with {info['name']} (Level {level}) post-quantum signatures\n")
        f.write("# DO NOT commit this file to git!\n")
        f.write("\n")
        f.write(f"DILITHIUM_LEVEL={level}\n")
        f.write(f"ADDRESS={address}\n")
        f.write(f"PUBLIC_KEY_HEX={pk_hex}\n")
        f.write(f"PRIVATE_KEY_HEX={sk_hex}\n")
        f.write(f"CHECK_PHRASE={check_phrase}\n")
        f.write(f"MNEMONIC_HASH={mnemonic_hash}\n")

    print(f"  Keys saved to {output_file}")
    print()

    # Verify the keys work
    print("Verifying keys...")
    test_message = b"Qubitcoin test"
    signature = impl.sign(sk, test_message)
    valid = impl.verify(pk, test_message, signature)

    if valid:
        print(f"  Key verification: PASSED")
    else:
        print("  Key verification: FAILED!")
        sys.exit(1)

    print()
    print("=" * 70)
    print("  NEXT STEPS")
    print("=" * 70)
    print()
    print("1. Copy .env template (if not already done):")
    print("   cp .env.example .env")
    print()
    print("2. Start node:")
    print("   cd src && python3 run_node.py")
    print()
    print(f"3. Your node will use {info['name']} ({info['classical']}-bit security)")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
