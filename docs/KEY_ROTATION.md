# Key Rotation Procedure

> **Best practices for rotating Dilithium2 cryptographic keys on Qubitcoin nodes.**

---

## 1. Overview

Qubitcoin uses **CRYSTALS-Dilithium2** post-quantum signatures for all node identity
and transaction signing. Keys are stored in `secure_key.env` (never in `.env`).

Key rotation is the process of replacing your node's cryptographic keys while
maintaining operational continuity. You should rotate keys:

- **Periodically** — every 6-12 months as a security best practice
- **After a compromise** — immediately if you suspect key material was leaked
- **Before decommissioning** — transfer funds before taking a node offline
- **After personnel changes** — when operators who had access leave

---

## 2. Key Files

| File | Purpose | Security |
|------|---------|----------|
| `secure_key.env` | Dilithium2 private key, public key, address | **NEVER committed.** Git-ignored. |
| `.env` | Node configuration (no secrets) | Safe to share. |
| `scripts/setup/generate_keys.py` | Key generation script | Part of codebase. |

---

## 3. Pre-Rotation Checklist

Before rotating keys, verify:

- [ ] You have a backup of the current `secure_key.env`
- [ ] All pending transactions from the current address are confirmed
- [ ] No mining rewards are pending maturity (wait 100 blocks after last block mined)
- [ ] You know the current UTXO balance: `curl http://localhost:5000/balance/<your_address>`
- [ ] Node is synced to chain tip: `curl http://localhost:5000/chain/tip`
- [ ] You have secure storage for the new keys (encrypted drive, HSM, etc.)

---

## 4. Rotation Procedure

### Step 1: Stop Mining

```bash
curl -X POST http://localhost:5000/mining/stop
```

Wait for any in-progress block to complete. Verify mining has stopped:

```bash
curl http://localhost:5000/mining/stats
# Confirm "is_mining": false
```

### Step 2: Backup Current Keys

```bash
# Create encrypted backup of current keys
cp secure_key.env secure_key.env.backup.$(date +%Y%m%d)
chmod 400 secure_key.env.backup.*

# Record current address and balance
OLD_ADDRESS=$(grep ADDRESS secure_key.env | cut -d= -f2)
echo "Old address: $OLD_ADDRESS"
curl http://localhost:5000/balance/$OLD_ADDRESS
```

### Step 3: Generate New Keys

```bash
# Generate new Dilithium2 keypair
python3 scripts/setup/generate_keys.py

# This overwrites secure_key.env with:
# - New ADDRESS
# - New PUBLIC_KEY_HEX
# - New PRIVATE_KEY_HEX
```

### Step 4: Record New Address

```bash
NEW_ADDRESS=$(grep ADDRESS secure_key.env | cut -d= -f2)
echo "New address: $NEW_ADDRESS"
```

### Step 5: Transfer Funds

Transfer all UTXOs from the old address to the new address. This requires
signing with the **old** private key, so you need to temporarily use the backup:

```bash
# Restore old keys temporarily for signing
cp secure_key.env secure_key.env.new
cp secure_key.env.backup.* secure_key.env

# Restart node to load old keys
# (restart procedure depends on your deployment)

# Transfer all funds to new address
# Use the REST API or build a transaction manually
# The exact mechanism depends on your wallet tooling

# After transfer is confirmed (6+ confirmations):
cp secure_key.env.new secure_key.env
# Restart node to load new keys
```

### Step 6: Verify

```bash
# Check balance on new address
curl http://localhost:5000/balance/$NEW_ADDRESS

# Check old address is empty
curl http://localhost:5000/balance/$OLD_ADDRESS

# Verify node identity
curl http://localhost:5000/info
```

### Step 7: Resume Mining

```bash
curl -X POST http://localhost:5000/mining/start
```

### Step 8: Secure Cleanup

```bash
# Shred the backup after verifying all funds transferred
shred -u secure_key.env.backup.*
shred -u secure_key.env.new

# Verify only secure_key.env remains
ls secure_key.*
```

---

## 5. Emergency Rotation (Key Compromise)

If you suspect your private key has been compromised:

1. **Immediately stop mining** — prevent the attacker from mining on your behalf
2. **Generate new keys** — `python3 scripts/setup/generate_keys.py`
3. **Transfer all funds** from the old address to the new one using the old keys
4. **Monitor the old address** — watch for unauthorized transactions
5. **Alert the network** — if the compromised key was a bridge validator or staking key
6. **Rotate all related credentials** — API keys, passwords, SSH keys on the same machine

**Time is critical.** The attacker can sign transactions with your key immediately.

---

## 6. Multi-Node Rotation

For operators running multiple nodes:

1. Rotate one node at a time
2. Verify each node's new identity before proceeding
3. Update peer seed lists if node addresses are used for discovery
4. Update any bridge validator registrations
5. Update Proof-of-Thought validator stakes

---

## 7. Key Export/Import

Qubitcoin supports exporting and importing keys in hex and PEM formats:

```python
from qubitcoin.quantum.crypto import Dilithium2

# Export current keypair
keypair = Dilithium2.export_keypair(public_key, private_key, format="hex")
# Returns: {"public_key": "hex...", "private_key": "hex...", "format": "hex"}

# Import keypair
pub, priv = Dilithium2.import_keypair(keypair)
```

**Supported formats:** `hex` (default), `pem`

---

## 8. Hardware Security Module (HSM) Integration

For production deployments, consider storing keys in an HSM:

- **AWS CloudHSM** — PKCS#11 interface
- **Azure Dedicated HSM** — FIPS 140-2 Level 3
- **YubiHSM 2** — Affordable hardware security

The HSM stores the Dilithium2 private key and performs signing operations
without exposing the key material to the host system.

**Note:** HSM integration requires a custom signing adapter (not yet implemented
in the reference node). The `quantum/crypto.py` module can be extended to support
HSM-backed signing.

---

## 9. Security Reminders

- **NEVER** commit `secure_key.env` to git (it is `.gitignored`)
- **NEVER** store private keys in `.env` — use `secure_key.env` exclusively
- **NEVER** transmit private keys over unencrypted channels
- **NEVER** reuse keys across different nodes
- **ALWAYS** verify the new address has received funds before deleting old keys
- **ALWAYS** wait for sufficient confirmations (6+) before considering a transfer final
- **ALWAYS** shred old key files after rotation (use `shred -u`, not `rm`)

---

**Responsible Disclosure:** info@qbc.network | **Website:** [qbc.network](https://qbc.network)
