#!/usr/bin/env python3
"""
Generate Dilithium2 keypair for Qubitcoin node
Saves to ~/qubitcoin/secure_key.env (NOT .env)
"""

import sys
import os
import hashlib

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from dilithium_py.dilithium import Dilithium2
except ImportError:
    print("❌ Error: dilithium-py not installed")
    print("   Run: pip install dilithium-py")
    sys.exit(1)

def main():
    print("=" * 70)
    print("  QUBITCOIN KEY GENERATOR - Dilithium2 Post-Quantum Signatures")
    print("=" * 70)
    print()
    
    # Output file is ALWAYS in parent directory (root)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    output_file = os.path.join(root_dir, 'secure_key.env')
    
    print(f"Output file: {output_file}")
    print()
    
    print("Generating Dilithium2 keypair...")
    
    # Generate keys
    pk, sk = Dilithium2.keygen()
    
    # Convert to hex
    pk_hex = pk.hex()
    sk_hex = sk.hex()
    
    # Derive address
    address = hashlib.sha256(pk).hexdigest()[:40]
    
    # Display keys
    print()
    print("=" * 70)
    print("  GENERATED KEYS - KEEP THESE SECURE!")
    print("=" * 70)
    print()
    print(f"ADDRESS (QBC):")
    print(f"  {address}")
    print()
    print(f"PUBLIC KEY ({len(pk)} bytes):")
    print(f"  {pk_hex[:80]}...")
    print(f"  ...{pk_hex[-80:]}")
    print()
    print(f"PRIVATE KEY ({len(sk)} bytes):")
    print(f"  {sk_hex[:80]}...")
    print(f"  ...{sk_hex[-80:]}")
    print()
    print("=" * 70)
    print()
    
    # Write to secure_key.env in ROOT directory
    print(f"Writing to {output_file}...")
    
    with open(output_file, 'w') as f:
        f.write("# Qubitcoin Node Keys - KEEP THIS FILE SECURE!\n")
        f.write("# Generated with Dilithium2 post-quantum signatures\n")
        f.write("# DO NOT commit this file to git!\n")
        f.write("\n")
        f.write(f"ADDRESS={address}\n")
        f.write(f"PUBLIC_KEY_HEX={pk_hex}\n")
        f.write(f"PRIVATE_KEY_HEX={sk_hex}\n")
    
    print(f"✅ Keys saved to {output_file}")
    print()
    
    # Verify the keys work
    print("Verifying keys...")
    test_message = b"Qubitcoin test"
    signature = Dilithium2.sign(sk, test_message)
    valid = Dilithium2.verify(pk, test_message, signature)
    
    if valid:
        print("✅ Key verification successful!")
    else:
        print("❌ Key verification failed!")
        sys.exit(1)
    
    print()
    print("=" * 70)
    print("  NEXT STEPS")
    print("=" * 70)
    print()
    print("1. Generate P2P key:")
    print("   python3 generate_ed25519.py")
    print()
    print("2. Copy keys to .env:")
    print("   cat ../secure_key.env >> ../.env")
    print()
    print("3. Start node:")
    print("   cd ../src && python3 run_node.py")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
