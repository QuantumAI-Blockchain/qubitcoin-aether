#!/usr/bin/env python3
"""Generate Ed25519 key for P2P identity"""
import secrets

def main():
    # Generate 32-byte Ed25519 secret
    secret_bytes = secrets.token_bytes(32)
    ed25519_hex = secret_bytes.hex()
    
    print("\n" + "="*60)
    print("Ed25519 P2P Key")
    print("="*60)
    print(f"\nPRIVATE_KEY_ED25519={ed25519_hex}")
    print("\n" + "="*60)
    
    # Append to secure_key.env
    with open('secure_key.env', 'a') as f:
        f.write(f"PRIVATE_KEY_ED25519={ed25519_hex}\n")
    
    print("\n✓ P2P key appended to secure_key.env")

if __name__ == "__main__":
    main()
