#!/usr/bin/env python3
"""Generate Dilithium keypair for Qubitcoin node"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dilithium_simple import Dilithium2
import hashlib

def main():
    print("Generating Dilithium2 keypair...")
    public_key, private_key = Dilithium2.keygen()
    
    public_key_hex = public_key.hex()
    private_key_hex = private_key.hex()
    
    # Derive address from public key
    address = hashlib.sha256(public_key).hexdigest()[:40]
    
    print("\n" + "="*60)
    print("GENERATED KEYS - Add to .env file")
    print("="*60)
    print(f"\nADDRESS={address}")
    print(f"PUBLIC_KEY_HEX={public_key_hex}")
    print(f"PRIVATE_KEY_HEX={private_key_hex}")
    print("\n" + "="*60)
    print("\nSave these values securely!")
    
    # Save to secure_key.env
    with open('secure_key.env', 'w') as f:
        f.write(f"ADDRESS={address}\n")
        f.write(f"PUBLIC_KEY_HEX={public_key_hex}\n")
        f.write(f"PRIVATE_KEY_HEX={private_key_hex}\n")
    
    print("\n✓ Keys saved to secure_key.env")
    print("⚠️  Keep this file secure and never commit to git!")

if __name__ == "__main__":
    main()
