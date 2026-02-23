#!/usr/bin/env python3
"""Simple Dilithium2 key generator - writes directly"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dilithium_py.dilithium import Dilithium2
import hashlib

print("Generating Dilithium2 keypair...")

# Generate keys
pk, sk = Dilithium2.keygen()

# Convert to hex
pk_hex = pk.hex()
sk_hex = sk.hex()

# Derive address
address = hashlib.sha256(pk).hexdigest()[:40]

print(f"\nADDRESS={address}")
print(f"\nKeys generated. Writing to secure_key.env...")

# Write to file - simple and direct
with open('secure_key.env', 'w') as f:
    f.write(f"ADDRESS={address}\n")
    f.write(f"PUBLIC_KEY_HEX={pk_hex}\n")
    f.write(f"PRIVATE_KEY_HEX={sk_hex}\n")

print("✅ Done!")

# Verify file was written
with open('secure_key.env', 'r') as f:
    content = f.read()
    print(f"\nFile size: {len(content)} bytes")
    print("First 100 chars:")
    print(content[:100])
