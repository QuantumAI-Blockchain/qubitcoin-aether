#!/usr/bin/env python3
"""
Generate Ed25519 key for P2P identity
Appends to ~/qubitcoin/secure_key.env (NOT .env)
"""

import secrets
import os

def main():
    # Output file is ALWAYS in parent directory (root)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    output_file = os.path.join(root_dir, 'secure_key.env')
    
    print("=" * 70)
    print("  Ed25519 P2P Key Generator")
    print("=" * 70)
    print()
    print(f"Appending to: {output_file}")
    print()
    
    # Generate 32-byte Ed25519 secret
    secret_bytes = secrets.token_bytes(32)
    ed25519_hex = secret_bytes.hex()
    
    print(f"PRIVATE_KEY_ED25519={ed25519_hex}")
    print()
    
    # Append to secure_key.env in ROOT directory
    with open(output_file, 'a') as f:
        f.write("\n# P2P Identity (Ed25519)\n")
        f.write(f"PRIVATE_KEY_ED25519={ed25519_hex}\n")
    
    print(f"✅ P2P key appended to {output_file}")
    print()
    print("=" * 70)
    print("  NEXT STEPS")
    print("=" * 70)
    print()
    print("1. Copy all keys to .env:")
    print("   cat ../secure_key.env >> ../.env")
    print()
    print("2. Start node:")
    print("   cd ../src && python3 run_node.py")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
