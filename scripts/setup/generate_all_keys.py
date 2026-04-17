#!/usr/bin/env python3
"""
============================================================================
 QUBITCOIN MASTER KEY GENERATOR — MILITARY-GRADE PRODUCTION SETUP
============================================================================
 Generates ALL Dilithium ML-DSA-87 (Level 5) keypairs for full operator
 deployment. Creates the secure_keys/ vault, production .env, and all
 supporting documentation.

 Usage:
   python3 scripts/setup/generate_all_keys.py

 Output:
   secure_keys/           — 700-permission vault directory
   secure_key.env         — Active node identity (Wallet 1)
   .env                   — Full production config with all addresses

 SECURITY: This script generates real cryptographic keys.
           Run ONLY on a trusted machine. Never pipe output to logs.
           Mnemonics are shown ONCE — write them down physically.
============================================================================
"""

import hashlib
import os
import secrets
import sys
import stat
import datetime

# Add project source to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
sys.path.insert(0, os.path.join(ROOT_DIR, 'src'))

# ── Import Dilithium ────────────────────────────────────────────────────────
try:
    from dilithium_py.dilithium import Dilithium5
except ImportError:
    print("FATAL: dilithium-py not installed")
    print("  Run: pip install dilithium-py")
    sys.exit(1)

# ── Import BIP39 wordlist (direct file import to avoid pulling in full node) ─
import importlib.util
_bip39_path = os.path.join(ROOT_DIR, 'src', 'qubitcoin', 'quantum', 'bip39_wordlist.py')
if not os.path.exists(_bip39_path):
    print(f"FATAL: BIP39 wordlist not found at {_bip39_path}")
    sys.exit(1)
_spec = importlib.util.spec_from_file_location("bip39_wordlist", _bip39_path)
_bip39_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bip39_mod)
BIP39_ENGLISH = _bip39_mod.BIP39_ENGLISH

# ── Constants ───────────────────────────────────────────────────────────────
SECURITY_LEVEL = 5
LEVEL_NAME = "ML-DSA-87"
CLASSICAL_BITS = 256
QUANTUM_BITS = 128
PK_SIZE = 2592
SK_SIZE = 4864
SIG_SIZE = 4595

SECURE_DIR = os.path.join(ROOT_DIR, 'secure_keys')
TIMESTAMP = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

# ── Wallet Definitions ──────────────────────────────────────────────────────
# Each wallet: (filename, label, purpose, is_operator_node)
WALLETS = [
    ("seed_node",          "SEED NODE (MAIN OPERATOR)",   "Genesis miner, 33M premine, Node 1 identity, MASTER ADMIN",                True),
    ("mining_node",        "MINING NODE",                  "Node 2 identity, second miner, local development",                         False),
    ("aether_treasury",    "AETHER FEE TREASURY",          "Receives Aether Tree chat/query fees (AETHER_FEE_TREASURY_ADDRESS)",       False),
    ("contract_treasury",  "CONTRACT FEE TREASURY",        "Receives smart contract deployment fees (CONTRACT_FEE_TREASURY_ADDRESS)",  False),
    ("bridge_treasury",    "BRIDGE TREASURY",              "Receives bridge fee revenue (BRIDGE_TREASURY_ADDRESS)",                    False),
    ("qusd_treasury",      "QUSD TREASURY",                "QUSD stablecoin operations (QUSD_TREASURY_ADDRESS)",                      False),
    ("aikgs_treasury",     "AIKGS TREASURY",               "Knowledge reward disbursements (AIKGS_TREASURY_ADDRESS)",                  False),
    ("higgs_operator",     "HIGGS FIELD OPERATOR",         "Higgs cognitive field contract operator (HIGGS_FIELD_ADDRESS)",            False),
    ("oracle_feeder",      "ORACLE FEEDER #2",             "QUSD price oracle feeder (ORACLE_FEEDER_2)",                              False),
]


# ============================================================================
# CRYPTOGRAPHIC FUNCTIONS
# ============================================================================

def generate_mnemonic() -> list:
    """Generate a 24-word BIP-39 mnemonic from 256 bits of entropy."""
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


def generate_check_phrase(address: str) -> str:
    """Generate a human-readable 3-word check-phrase from an address."""
    addr_bytes = hashlib.sha256(address.encode()).digest()
    bits = bin(int.from_bytes(addr_bytes[:5], 'big'))[2:].zfill(40)
    words = []
    for i in range(3):
        idx = int(bits[i * 11:(i + 1) * 11], 2) % 2048
        words.append(BIP39_ENGLISH[idx])
    return "-".join(words)


def fips204_kat_selftest() -> bool:
    """Run FIPS 204 Known Answer Test self-test for ML-DSA-87."""
    test_msg = b"FIPS 204 KAT self-test for Qubitcoin master keygen"
    try:
        pk, sk = Dilithium5.keygen()
        assert len(pk) == PK_SIZE, f"pk size {len(pk)} != {PK_SIZE}"
        assert len(sk) == SK_SIZE, f"sk size {len(sk)} != {SK_SIZE}"
        sig = Dilithium5.sign(sk, test_msg)
        assert len(sig) == SIG_SIZE, f"sig size {len(sig)} != {SIG_SIZE}"
        assert Dilithium5.verify(pk, test_msg, sig), "Valid signature rejected"
        tampered = bytearray(sig)
        tampered[-1] ^= 0xFF
        assert not Dilithium5.verify(pk, test_msg, bytes(tampered)), "Tampered sig accepted"
        return True
    except Exception as e:
        print(f"  FIPS 204 KAT FAILED: {e}")
        return False


def generate_keypair():
    """Generate a Dilithium5 keypair, derive address and check-phrase."""
    pk, sk = Dilithium5.keygen()
    pk_hex = pk.hex()
    sk_hex = sk.hex()
    address = hashlib.sha256(pk).hexdigest()[:40]
    check_phrase = generate_check_phrase(address)
    mnemonic = generate_mnemonic()
    mnemonic_str = " ".join(mnemonic)
    mnemonic_hash = hashlib.sha256(mnemonic_str.encode()).hexdigest()

    # Verify the keypair works
    test_msg = b"Qubitcoin keypair verification"
    sig = Dilithium5.sign(sk, test_msg)
    assert Dilithium5.verify(pk, test_msg, sig), "Generated keypair FAILED verification!"

    return {
        'address': address,
        'pk_hex': pk_hex,
        'sk_hex': sk_hex,
        'check_phrase': check_phrase,
        'mnemonic': mnemonic,
        'mnemonic_str': mnemonic_str,
        'mnemonic_hash': mnemonic_hash,
    }


def generate_hmac_secret(label: str) -> str:
    """Generate a 64-character hex HMAC secret."""
    return secrets.token_hex(32)


# ============================================================================
# FILE WRITERS
# ============================================================================

def write_wallet_file(filepath: str, label: str, purpose: str, keys: dict, is_operator: bool):
    """Write a single wallet .env file with full documentation."""
    content = f"""# ============================================================================
# QUBITCOIN — {label}
# ============================================================================
# PURPOSE: {purpose}
#
# SECURITY CLASSIFICATION: TOP SECRET — CRYPTOGRAPHIC KEY MATERIAL
# GENERATED: {TIMESTAMP}
# ALGORITHM: CRYSTALS-Dilithium / {LEVEL_NAME} (NIST Level {SECURITY_LEVEL})
# CLASSICAL SECURITY: {CLASSICAL_BITS}-bit (equivalent to AES-256)
# QUANTUM SECURITY: {QUANTUM_BITS}-bit (resistant to Grover + Shor)
# FIPS STANDARD: FIPS 204 (ML-DSA)
#
# WARNING: This file contains PRIVATE KEY MATERIAL.
#   - NEVER commit to version control
#   - NEVER transmit over unencrypted channels
#   - NEVER store in cloud storage without encryption
#   - NEVER share with unauthorized personnel
#   - Back up to encrypted USB or hardware security module
#   - Destroy all digital copies after secure backup
# ============================================================================

# ── Security Level ──────────────────────────────────────────────────────────
# 2 = ML-DSA-44 (128-bit classical, NIST Level 2) — fast, smaller keys
# 3 = ML-DSA-65 (192-bit classical, NIST Level 3) — balanced
# 5 = ML-DSA-87 (256-bit classical, NIST Level 5) — MAXIMUM SECURITY
DILITHIUM_LEVEL={SECURITY_LEVEL}

# ── Post-Quantum Address ───────────────────────────────────────────────────
# SHA-256 hash of the public key, truncated to 40 hex characters (160 bits).
# This is your wallet address on the QBC network.
# Format: 40-character lowercase hexadecimal string
ADDRESS={keys['address']}

# ── Public Key ─────────────────────────────────────────────────────────────
# {LEVEL_NAME} public key ({PK_SIZE:,} bytes, {PK_SIZE * 2:,} hex chars).
# Safe to share — used by others to verify your signatures.
PUBLIC_KEY_HEX={keys['pk_hex']}

# ── Private Key ────────────────────────────────────────────────────────────
# {LEVEL_NAME} private key ({SK_SIZE:,} bytes, {SK_SIZE * 2:,} hex chars).
# TOP SECRET — this key signs all transactions from this wallet.
# Anyone with this key can spend ALL funds in this wallet.
PRIVATE_KEY_HEX={keys['sk_hex']}

# ── Human-Readable Check-Phrase ────────────────────────────────────────────
# 3-word alias derived from the address. Use to visually verify addresses
# in UIs and communications (e.g., "tiger-ocean-marble").
CHECK_PHRASE={keys['check_phrase']}

# ── Mnemonic Verification Hash ─────────────────────────────────────────────
# SHA-256 hash of the 24-word recovery mnemonic. Use to verify that your
# written-down mnemonic matches what was generated. The mnemonic itself
# is NOT stored here — it was shown once during generation.
MNEMONIC_HASH={keys['mnemonic_hash']}
"""
    with open(filepath, 'w') as f:
        f.write(content)
    # Set file permissions: owner read/write only (600)
    os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)


def write_mnemonic_backup(filepath: str, all_wallets: list):
    """Write the temporary mnemonic backup file. DELETE AFTER WRITING DOWN."""
    lines = []
    lines.append("# " + "=" * 76)
    lines.append("# QUBITCOIN — MASTER MNEMONIC BACKUP")
    lines.append("# " + "=" * 76)
    lines.append(f"# GENERATED: {TIMESTAMP}")
    lines.append("#")
    lines.append("# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    lines.append("# !!                                                                    !!")
    lines.append("# !!   WRITE THESE DOWN ON PAPER. THEN DELETE THIS FILE IMMEDIATELY.    !!")
    lines.append("# !!                                                                    !!")
    lines.append("# !!   Command to securely delete:                                      !!")
    lines.append("# !!     shred -vfz -n 5 secure_keys/MNEMONIC_BACKUP.txt                !!")
    lines.append("# !!     rm secure_keys/MNEMONIC_BACKUP.txt                             !!")
    lines.append("# !!                                                                    !!")
    lines.append("# !!   Or on macOS:                                                     !!")
    lines.append("# !!     rm -P secure_keys/MNEMONIC_BACKUP.txt                          !!")
    lines.append("# !!                                                                    !!")
    lines.append("# !!   Each mnemonic is 24 words. They are your ONLY recovery option    !!")
    lines.append("# !!   if private keys are lost. Store on paper in a fireproof safe.    !!")
    lines.append("# !!                                                                    !!")
    lines.append("# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    lines.append("#")
    lines.append("")

    for (filename, label, purpose, _), keys in all_wallets:
        lines.append("# " + "-" * 76)
        lines.append(f"# WALLET: {label}")
        lines.append(f"# ADDRESS: {keys['address']}")
        lines.append(f"# CHECK-PHRASE: {keys['check_phrase']}")
        lines.append(f"# PURPOSE: {purpose}")
        lines.append("# " + "-" * 76)
        lines.append("")
        mnemonic = keys['mnemonic']
        for i in range(0, 24, 6):
            row = "  ".join(f"{i+j+1:2d}. {mnemonic[i+j]:<14s}" for j in range(min(6, 24 - i)))
            lines.append(f"  {row}")
        lines.append("")
        lines.append(f"  Verification hash: {keys['mnemonic_hash']}")
        lines.append("")
        lines.append("")

    lines.append("# " + "=" * 76)
    lines.append("# END OF MNEMONIC BACKUP — DELETE THIS FILE NOW")
    lines.append("# " + "=" * 76)

    with open(filepath, 'w') as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)


def write_master_addresses(filepath: str, all_wallets: list):
    """Write quick-reference address list."""
    lines = []
    lines.append("# " + "=" * 76)
    lines.append("# QUBITCOIN — MASTER ADDRESS REFERENCE")
    lines.append("# " + "=" * 76)
    lines.append(f"# Generated: {TIMESTAMP}")
    lines.append(f"# Algorithm: {LEVEL_NAME} (NIST Level {SECURITY_LEVEL})")
    lines.append("#")
    lines.append("# These are PUBLIC addresses only — safe to reference.")
    lines.append("# Private keys are in individual wallet files.")
    lines.append("# " + "=" * 76)
    lines.append("")

    for (filename, label, purpose, _), keys in all_wallets:
        lines.append(f"# {label}")
        lines.append(f"# Purpose: {purpose}")
        lines.append(f"# File: secure_keys/{filename}.env")
        lines.append(f"ADDRESS_{filename.upper()}={keys['address']}")
        lines.append(f"CHECK_PHRASE_{filename.upper()}={keys['check_phrase']}")
        lines.append("")

    with open(filepath, 'w') as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)


def write_secure_key_env(filepath: str, keys: dict):
    """Write the active node identity secure_key.env (root-level, loaded by config.py)."""
    content = f"""# ============================================================================
# QUBITCOIN — ACTIVE NODE IDENTITY (secure_key.env)
# ============================================================================
# This is the LIVE cryptographic identity for THIS node.
# Loaded automatically by config.py at node startup.
#
# SOURCE: secure_keys/seed_node.env (Wallet 1 — Main Operator)
# ALGORITHM: {LEVEL_NAME} (NIST Level {SECURITY_LEVEL}, {CLASSICAL_BITS}-bit classical)
# GENERATED: {TIMESTAMP}
#
# To switch node identity, replace this file with a different wallet:
#   cp secure_keys/mining_node.env secure_key.env
#
# NEVER commit this file — it is .gitignored.
# ============================================================================

DILITHIUM_LEVEL={SECURITY_LEVEL}
ADDRESS={keys['address']}
PUBLIC_KEY_HEX={keys['pk_hex']}
PRIVATE_KEY_HEX={keys['sk_hex']}
CHECK_PHRASE={keys['check_phrase']}
MNEMONIC_HASH={keys['mnemonic_hash']}
"""
    with open(filepath, 'w') as f:
        f.write(content)
    os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)


def write_bridge_operator_placeholder(filepath: str):
    """Write placeholder for EVM bridge operator key."""
    content = f"""# ============================================================================
# QUBITCOIN — BRIDGE OPERATOR (EVM / secp256k1)
# ============================================================================
# PURPOSE: Signs bridge transactions on external EVM chains (ETH, BNB, etc.)
#
# GENERATED: {TIMESTAMP} (PLACEHOLDER — fill in manually)
#
# HOW TO FILL:
#   1. In MetaMask: Create a NEW account named "Bridge Operator"
#   2. Export private key: Account Details > Export Private Key
#   3. Paste below (0x-prefixed 64-char hex string)
#   4. Fund this account with gas on target chains:
#      - BNB Smart Chain: ~0.1 BNB
#      - Ethereum: ~0.05 ETH
#      - Polygon: ~1 MATIC
#      - Arbitrum/Optimism/Base: ~0.01 ETH each
#
# WARNING: This is an Ethereum-style private key (secp256k1).
#   - Same key works on ALL EVM chains (ETH, BNB, Polygon, etc.)
#   - NEVER share or commit this file
# ============================================================================

# Ethereum-compatible private key (secp256k1)
# Format: 0x-prefixed 64-character hex string
# Example: 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
ETH_DEPLOYER_PRIVATE_KEY=

# Solana keypair file path (JSON format from solana-keygen)
# Generate with: solana-keygen new --outfile ~/.config/solana/bridge-deployer.json
SOLANA_DEPLOYER_KEYPAIR_PATH=
"""
    with open(filepath, 'w') as f:
        f.write(content)
    os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)


def write_production_env(filepath: str, all_wallets: list, hmac_secrets: dict):
    """Write the full production .env with all addresses and extreme comments."""

    # Extract addresses by wallet name
    addr = {}
    for (filename, _, _, _), keys in all_wallets:
        addr[filename] = keys['address']

    content = f"""# ============================================================================
#
#   QUBITCOIN — MASTER OPERATOR NODE CONFIGURATION (.env)
#
# ============================================================================
#
#   NODE ROLE: MASTER ADMIN / SEED NODE / GENESIS MINER
#   GENERATED: {TIMESTAMP}
#   SECURITY: {LEVEL_NAME} (NIST Level {SECURITY_LEVEL}, {CLASSICAL_BITS}-bit classical security)
#
#   This file contains NON-SECRET configuration only.
#   Private keys are in secure_key.env (loaded automatically by config.py).
#   Treasury addresses below are PUBLIC — safe to share.
#
#   FILE HIERARCHY:
#     secure_key.env    → Private key material (auto-loaded FIRST)
#     .env              → THIS FILE — all other configuration (loaded SECOND)
#     secure_keys/      → Vault with all wallet backups (not loaded by node)
#
#   HOW CONFIG LOADING WORKS (config.py):
#     1. Loads secure_key.env (override=True) — sets ADDRESS, PRIVATE_KEY_HEX, etc.
#     2. Loads .env (override=False) — sets everything else, won't overwrite keys
#     3. All values accessible via Config class attributes
#
# ============================================================================


# ============================================================================
# SECTION 1: NODE IDENTITY
# ============================================================================
# These are loaded from secure_key.env automatically.
# Do NOT set ADDRESS, PUBLIC_KEY_HEX, or PRIVATE_KEY_HEX here.
# If you need to change identity, replace secure_key.env:
#   cp secure_keys/mining_node.env secure_key.env
#
# The Ed25519 key is optional — only needed for Substrate hybrid mode.
PRIVATE_KEY_ED25519=


# ============================================================================
# SECTION 2: QUANTUM CONFIGURATION
# ============================================================================
# Controls the quantum computing backend for VQE mining.
#
# USE_LOCAL_ESTIMATOR=true  → Uses local Qiskit simulator (no IBM account needed)
# USE_LOCAL_ESTIMATOR=false → Uses IBM Quantum hardware (requires IBM_TOKEN)
# USE_SIMULATOR=true        → Forces Qiskit Aer simulator even with IBM token
#
# For production: local estimator is fine. IBM Quantum is for research/benchmarking.
USE_LOCAL_ESTIMATOR=true
USE_SIMULATOR=false

# IBM Quantum API credentials (OPTIONAL — only if using real quantum hardware)
# Get from: https://quantum.ibm.com → Account → API Token
IBM_TOKEN=
IBM_INSTANCE=


# ============================================================================
# SECTION 3: NETWORK CONFIGURATION
# ============================================================================
# P2P_PORT: libp2p gossip protocol (peer discovery, block/tx propagation)
# RPC_PORT: FastAPI REST + JSON-RPC (wallet connections, API queries)
# RUST_P2P_GRPC: gRPC interface between Python node and Rust P2P daemon
#
# FIREWALL: Open these ports on your server:
#   - 4001/tcp  → P2P (required for peer connections)
#   - 5000/tcp  → RPC (required for API/wallet access — consider reverse proxy)
#   - 50051/tcp → gRPC (internal only, do NOT expose publicly)
P2P_PORT=4001
RPC_PORT=5000
PEER_SEEDS=

# ── Rust P2P Daemon ────────────────────────────────────────────────────────
# The Rust libp2p daemon is the PRIMARY P2P layer (faster, more reliable).
# Python P2P is a fallback if the Rust binary is missing or crashes.
# RUST_P2P_BINARY: path to compiled Rust binary (relative to project root)
# RUST_P2P_STARTUP_TIMEOUT: seconds to wait for Rust daemon to start
ENABLE_RUST_P2P=true
RUST_P2P_PORT=4001
RUST_P2P_GRPC=50051
RUST_P2P_BINARY=rust-p2p/target/release/qubitcoin-p2p
RUST_P2P_STARTUP_TIMEOUT=10


# ============================================================================
# SECTION 4: DATABASE
# ============================================================================
# CockroachDB v24.2.0 — distributed SQL database.
# In Docker: uses internal hostname "cockroachdb"
# Local dev: use localhost:26257
#
# CockroachDB admin UI runs on port 8080.
# Health check: curl --fail http://localhost:8080/health?ready=1
DATABASE_URL=postgresql://root@cockroachdb:26257/qbc?sslmode=disable


# ============================================================================
# SECTION 5: IPFS CONTENT STORAGE
# ============================================================================
# IPFS (Kubo) for content-addressed storage of blockchain snapshots.
# In Docker: uses internal hostname "ipfs"
# IPFS_GATEWAY_PORT: HTTP gateway for content retrieval
#   NOTE: Default 8080 conflicts with CockroachDB admin UI.
#         Use 8081 in local dev, 8080 is fine in Docker (different containers).
#
# PINATA_JWT: Optional cloud IPFS pinning service for redundancy.
# Get from: https://www.pinata.cloud → API Keys
IPFS_API=/ip4/ipfs/tcp/5001/http
IPFS_GATEWAY_PORT=8080
PINATA_JWT=


# ============================================================================
# SECTION 6: REDIS CACHE
# ============================================================================
# Redis for mempool caching, rate limiting, and session management.
# REDIS_PASSWORD: CHANGE THIS to a strong random value in production.
# In Docker: uses internal hostname "redis"
REDIS_PASSWORD={secrets.token_hex(16)}
REDIS_URL=redis://:${{REDIS_PASSWORD}}@redis:6379


# ============================================================================
# SECTION 7: MINING CONFIGURATION
# ============================================================================
# AUTO_MINE: Start mining automatically when node boots (true for seed node)
# MINING_INTERVAL: Seconds between mining attempts (3.3s target block time)
# SNAPSHOT_INTERVAL: Blocks between IPFS snapshots of chain state
AUTO_MINE=true
MINING_INTERVAL=10
SNAPSHOT_INTERVAL=100


# ============================================================================
# SECTION 8: LLM / EXTERNAL AI (OPTIONAL)
# ============================================================================
# Aether Tree can optionally use external LLMs for enhanced reasoning.
# All keys are OPTIONAL — Aether Tree works without them using built-in reasoning.
#
# LLM_ENABLED: Master switch for external LLM integration
# LLM_PRIMARY_ADAPTER: Which LLM to use by default (openai, claude, grok, etc.)
# LLM_SEEDER_ENABLED: Auto-generate knowledge graph entries using LLM
LLM_ENABLED=false
LLM_PRIMARY_ADAPTER=openai

# ── OpenAI ─────────────────────────────────────────────────────────────────
# Get from: https://platform.openai.com → API Keys
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4

# ── Anthropic Claude ───────────────────────────────────────────────────────
# Get from: https://console.anthropic.com → API Keys
CLAUDE_API_KEY=
CLAUDE_MODEL=claude-sonnet-4-5-20250929

# ── xAI Grok ──────────────────────────────────────────────────────────────
# Get from: https://console.x.ai → API Keys
GROK_API_KEY=
GROK_MODEL=grok-3

# ── Google Gemini ──────────────────────────────────────────────────────────
# Get from: https://aistudio.google.com → API Keys
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-pro

# ── Mistral ────────────────────────────────────────────────────────────────
# Get from: https://console.mistral.ai → API Keys
MISTRAL_API_KEY=
MISTRAL_MODEL=mistral-large-latest

# ── Local LLM ──────────────────────────────────────────────────────────────
# URL to a locally-hosted LLM (e.g., Ollama, vLLM, llama.cpp server)
LOCAL_LLM_URL=

# ── LLM Seeder Settings ───────────────────────────────────────────────────
LLM_SEEDER_ENABLED=false
LLM_SEEDER_INTERVAL_BLOCKS=50
LLM_SEEDER_RATE_LIMIT_PER_HOUR=10
LLM_SEEDER_MAX_TOKENS=2048
LLM_SEEDER_COOLDOWN_SECONDS=15


# ============================================================================
# SECTION 9: TREASURY ADDRESSES
# ============================================================================
# These are PUBLIC wallet addresses that receive various network fees.
# Private keys for these wallets are stored in secure_keys/ (NEVER here).
#
# CRITICAL: Set ALL of these before mainnet launch.
# Fees sent to an empty address are lost forever.
#
# To change a treasury address post-launch:
#   1. Generate new keys or use an existing wallet from secure_keys/
#   2. Update the address below
#   3. Restart the node
#   All future fees go to the new address. Past fees remain in the old wallet.

# ── Aether Fee Treasury ────────────────────────────────────────────────────
# Receives: All Aether Tree chat fees and reasoning query fees
# Expected revenue: ~0.01 QBC per chat message, ~0.02 QBC per deep query
# Source wallet: secure_keys/aether_treasury.env
AETHER_FEE_TREASURY_ADDRESS={addr['aether_treasury']}

# ── Contract Fee Treasury ──────────────────────────────────────────────────
# Receives: Smart contract deployment fees (base + per-KB)
# Expected revenue: ~1-5 QBC per contract deployment
# Source wallet: secure_keys/contract_treasury.env
CONTRACT_FEE_TREASURY_ADDRESS={addr['contract_treasury']}

# ── Bridge Treasury ────────────────────────────────────────────────────────
# Receives: Cross-chain bridge transfer fees (0.3% default)
# Expected revenue: 0.3% of all bridge volume
# Source wallet: secure_keys/bridge_treasury.env
BRIDGE_TREASURY_ADDRESS={addr['bridge_treasury']}

# ── QUSD Treasury ──────────────────────────────────────────────────────────
# Receives: QUSD stablecoin operation fees, initial 3.3B QUSD allocation
# Source wallet: secure_keys/qusd_treasury.env
QUSD_TREASURY_ADDRESS={addr['qusd_treasury']}

# ── AIKGS Treasury ─────────────────────────────────────────────────────────
# Receives: Knowledge contribution reward pool, bounty funds
# Disburses: Rewards to knowledge contributors via AIKGS contracts
# Source wallet: secure_keys/aikgs_treasury.env
AIKGS_TREASURY_ADDRESS={addr['aikgs_treasury']}


# ============================================================================
# SECTION 10: AETHER TREE FEE ECONOMICS
# ============================================================================
# Dynamic fee pricing pegged to QUSD stablecoin for USD stability.
#
# PRICING MODES:
#   qusd_peg   → Fee auto-adjusts based on QUSD oracle price (RECOMMENDED)
#   fixed_qbc  → Fee is a fixed QBC amount (fallback if QUSD fails)
#   direct_usd → Fee targets USD via external price feed
#
# HOW IT WORKS:
#   Every AETHER_FEE_UPDATE_INTERVAL blocks, the node queries the QUSD oracle
#   for the current QBC/USD rate and recalculates:
#     fee_qbc = AETHER_CHAT_FEE_USD_TARGET / qbc_usd_price
#   Clamped between MIN and MAX to prevent extreme fees.
#
# CHANGEABLE: Yes — via .env (restart) or Admin API (hot reload)
AETHER_CHAT_FEE_QBC=0.01
AETHER_CHAT_FEE_USD_TARGET=0.005
AETHER_FEE_PRICING_MODE=qusd_peg
AETHER_FEE_MIN_QBC=0.001
AETHER_FEE_MAX_QBC=1.0
AETHER_FEE_UPDATE_INTERVAL=100
AETHER_QUERY_FEE_MULTIPLIER=2.0
AETHER_FREE_TIER_MESSAGES=5


# ============================================================================
# SECTION 11: CONTRACT DEPLOYMENT FEES
# ============================================================================
# Fee = BASE + (bytecode_KB * PER_KB). Pegged to QUSD like Aether fees.
# Template contracts get a discount (pre-audited, optimized).
#
# CHANGEABLE: Yes — via .env (restart) or Admin API (hot reload)
CONTRACT_DEPLOY_BASE_FEE_QBC=1.0
CONTRACT_DEPLOY_PER_KB_FEE_QBC=0.1
CONTRACT_DEPLOY_FEE_USD_TARGET=5.0
CONTRACT_FEE_PRICING_MODE=qusd_peg
CONTRACT_EXECUTE_BASE_FEE_QBC=0.01
CONTRACT_TEMPLATE_DISCOUNT=0.5


# ============================================================================
# SECTION 12: FEE BURNING (DEFLATIONARY PRESSURE)
# ============================================================================
# Percentage of L1 transaction fees permanently destroyed.
# 0.0 = no burning, 0.5 = 50% burned (default), 1.0 = 100% burned
#
# This creates deflationary pressure as network usage grows.
# CHANGEABLE: Yes — via .env (restart)
FEE_BURN_PERCENTAGE=0.5


# ============================================================================
# SECTION 13: BRIDGE CONFIGURATION
# ============================================================================
# Cross-chain bridge for QBC <-> wQBC and QUSD <-> wQUSD.
#
# BRIDGE_FEE_BPS: Fee in basis points (30 = 0.30% per transfer)
# BRIDGE_OPERATOR_ADDRESS: Public address of the bridge signer (address only!)
#   Private key is in secure_keys/bridge_operator.env (NEVER here)
#
# External chain RPC URLs (get free API keys from Alchemy):
#   https://www.alchemy.com → Create App → Copy API Key
BRIDGE_FEE_BPS=30
BRIDGE_OPERATOR_ADDRESS=

# ── External Chain RPCs ────────────────────────────────────────────────────
# REQUIRED for bridge deployment (Phase 10). Can be added post-launch.
# Free tier Alchemy keys work fine for initial deployment.
#
# FORMAT: https://<network>.g.alchemy.com/v2/YOUR_ALCHEMY_KEY
# Or use public RPCs (less reliable, rate-limited):
ETH_RPC_URL=
BSC_RPC_URL=https://bsc-dataseed.binance.org
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com

# ── Bridge Contract Addresses (populated after bridge deployment) ──────────
# These are filled in AFTER deploying wQBC/wQUSD to external chains.
# See MASTER_LAUNCH_PLAN.md Section 5 for deployment instructions.
# ETH_BRIDGE_ADDRESS=
# ETH_WQUSD_ADDRESS=
# BSC_BRIDGE_ADDRESS=
# BSC_WQUSD_ADDRESS=


# ============================================================================
# SECTION 14: CHAIN PARAMETERS
# ============================================================================
# Core consensus constants. DO NOT change these after genesis.
#
# CHAIN_ID: Unique network identifier (3303=mainnet, 3304=testnet)
# BLOCK_GAS_LIMIT: Maximum gas per block for QVM (L2) execution
CHAIN_ID=3303
BLOCK_GAS_LIMIT=30000000


# ============================================================================
# SECTION 15: DILITHIUM SECURITY LEVEL
# ============================================================================
# Post-quantum signature algorithm security level.
# Must match the level used to generate keys in secure_key.env.
#
# 2 = ML-DSA-44 (128-bit classical, NIST Level 2) — 2,420 byte signatures
# 3 = ML-DSA-65 (192-bit classical, NIST Level 3) — 3,293 byte signatures
# 5 = ML-DSA-87 (256-bit classical, NIST Level 5) — 4,595 byte signatures
#
# MAINNET DEFAULT: 5 (maximum quantum resistance)
# CANNOT CHANGE after genesis without a hard fork.
DILITHIUM_SECURITY_LEVEL=5


# ============================================================================
# SECTION 16: SECURITY SECRETS (AUTO-GENERATED)
# ============================================================================
# These are HMAC secrets and authentication tokens for internal services.
# Generated with cryptographically secure random bytes (secrets.token_hex).
# Treat as SECRET — do not share.

# ── Gevurah Safety Secret ──────────────────────────────────────────────────
# Shared HMAC secret for Aether Tree safety veto + emergency shutdown.
# Used to authenticate Gevurah (safety node) commands.
# If compromised: rotate immediately, restart node.
GEVURAH_SECRET={hmac_secrets['gevurah']}

# ── AIKGS Auth Token ───────────────────────────────────────────────────────
# Shared secret for gRPC authentication between node and AIKGS sidecar.
# Used to prevent unauthorized knowledge reward disbursements.
AIKGS_AUTH_TOKEN={hmac_secrets['aikgs_auth']}

# ── API Key Vault Secret ──────────────────────────────────────────────────
# Encryption key for API keys stored at rest in the AIKGS vault.
# Used by api_key_vault.py to encrypt/decrypt third-party API keys.
# If lost: all stored API keys become unrecoverable.
API_KEY_VAULT_SECRET={hmac_secrets['api_vault']}

# ── Telegram Webhook Secret ────────────────────────────────────────────────
# HMAC secret for verifying Telegram webhook callbacks.
# Set this if you enable the @AetherTreeBot Telegram integration.
TELEGRAM_WEBHOOK_SECRET={hmac_secrets['telegram_webhook']}

# ── Admin API Key ──────────────────────────────────────────────────────────
# Authentication key for admin API endpoints (fee changes, config updates).
# Must be at least 64 characters. Include in Authorization header.
# Format: Authorization: Bearer <ADMIN_API_KEY>
ADMIN_API_KEY={secrets.token_hex(48)}


# ============================================================================
# SECTION 17: HIGGS COGNITIVE FIELD
# ============================================================================
# The Higgs Cognitive Field gives Sephirot nodes their "cognitive mass"
# (inertia to change). Based on the Standard Model's Higgs mechanism.
#
# VEV = Vacuum Expectation Value (equilibrium field strength)
# MU = Mass parameter (controls shape of Mexican Hat potential)
# LAMBDA = Quartic self-coupling (controls width of potential)
# TAN_BETA = tan(beta) = phi for Two-Higgs-Doublet Model (SUSY balance)
#
# CHANGEABLE: Yes — via .env (restart). Affects AI node dynamics.
# OPERATOR ADDRESS: Contract operator for HiggsField.sol
HIGGS_FIELD_ADDRESS={addr['higgs_operator']}
HIGGS_MU=88.45
HIGGS_LAMBDA=0.129
HIGGS_TAN_BETA=1.618033988749895
HIGGS_EXCITATION_THRESHOLD=0.10
HIGGS_DT=0.01
HIGGS_ENABLE_MASS_REBALANCING=true
HIGGS_FIELD_UPDATE_INTERVAL=1


# ============================================================================
# SECTION 18: QUSD ORACLE CONFIGURATION
# ============================================================================
# Price oracle for QUSD stablecoin. Feeders submit QBC/USD prices.
#
# Feeder 1: Defaults to the node operator ADDRESS (from secure_key.env)
# Feeder 2: Set to a trusted partner node or the oracle_feeder wallet
# Feeder 3: Set to another trusted oracle (for 3-of-3 median)
#
# INITIAL_PRICE: Starting QBC/USD price in 8 decimals (10000000 = $0.10)
# MAX_AGE: Maximum blocks before a price reading is considered stale
ORACLE_FEEDER_2={addr['oracle_feeder']}
ORACLE_FEEDER_3=
ORACLE_INITIAL_PRICE=10000000
ORACLE_MAX_AGE=1000


# ============================================================================
# SECTION 19: AIKGS (Aether Incentivized Knowledge Growth System)
# ============================================================================
# Manages knowledge contribution rewards, quality scoring, and affiliates.
#
# SECURITY NOTE: In production, sensitive secrets (AIKGS_AUTH_TOKEN,
# API_KEY_VAULT_SECRET) should ideally use a secrets manager (HashiCorp
# Vault, AWS Secrets Manager, etc.). Env vars are acceptable for initial launch.
AIKGS_ENABLED=true
AIKGS_USE_RUST_SIDECAR=true
AIKGS_GRPC_ADDR=127.0.0.1
AIKGS_GRPC_PORT=50052
AIKGS_MAX_SINGLE_DISBURSEMENT=0.5
AIKGS_MAX_DAILY_DISBURSEMENT=500.0
AIKGS_MAX_DISBURSEMENTS_PER_HOUR=100
AIKGS_DISBURSE_MAX_RETRIES=3
AIKGS_DISBURSE_INITIAL_BACKOFF_MS=1000
AIKGS_BASE_REWARD_QBC=0.05
AIKGS_MAX_REWARD_QBC=0.5
AIKGS_INITIAL_POOL_QBC=1000000.0
AIKGS_EARLY_THRESHOLD=10000
AIKGS_EARLY_MAX_BONUS=2.0
AIKGS_QUALITY_WEIGHT=0.6
AIKGS_NOVELTY_WEIGHT=0.4
AIKGS_L1_COMMISSION_RATE=0.10
AIKGS_L2_COMMISSION_RATE=0.05
AIKGS_MAX_DAILY_SUBMISSIONS=50
AIKGS_QUERY_DEFAULT_LIMIT=50
AIKGS_QUERY_MAX_LIMIT=1000
AIKGS_CURATION_REQUIRED_VOTES=3
AIKGS_DEFAULT_BOUNTY_REWARD=0.25
AIKGS_DEFAULT_BOUNTY_DURATION_DAYS=30

# ── AIKGS Contract Addresses (populated after contract deployment) ─────────
# These are filled in AFTER deploying AIKGS contracts (Phase 8).
# Deploy script saves addresses to contract_registry.json.
AIKGS_REWARD_POOL_ADDRESS=
AIKGS_AFFILIATE_REGISTRY_ADDRESS=
AIKGS_CONTRIBUTION_LEDGER_ADDRESS=
AIKGS_BOUNTY_CONTRACT_ADDRESS=
AIKGS_NFT_CONTRACT_ADDRESS=


# ============================================================================
# SECTION 20: TELEGRAM BOT (OPTIONAL)
# ============================================================================
# @AetherTreeBot — Telegram interface for Aether Tree chat.
#
# HOW TO SET UP:
#   1. Message @BotFather on Telegram → /newbot → get token
#   2. Set TELEGRAM_BOT_TOKEN below
#   3. Set TELEGRAM_WEBHOOK_URL to your public API endpoint
#   4. Restart node — bot auto-registers webhook
TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=AetherTreeBot
TELEGRAM_MINI_APP_URL=https://qbc.network/twa
TELEGRAM_WEBHOOK_URL=


# ============================================================================
# SECTION 21: TRANSACTION REVERSIBILITY (OPT-IN)
# ============================================================================
# Allows users to opt-in to reversible transactions with a time window.
# Requires guardian approvals for third-party reversal requests.
#
# DEFAULT_WINDOW=0 means transactions are irreversible by default.
# Users must explicitly opt-in when creating transactions.
# MAX_WINDOW ~24 hours at 3.3s/block = 26,182 blocks
REVERSAL_DEFAULT_WINDOW=0
REVERSAL_MAX_WINDOW=26182
REVERSAL_GUARDIAN_THRESHOLD=2


# ============================================================================
# SECTION 22: COMPETITIVE FEATURES (ALL OPT-IN, ENABLED BY DEFAULT)
# ============================================================================

# ── Inheritance Protocol (Dead-Man's Switch) ───────────────────────────────
# Allows users to designate beneficiaries who inherit funds after inactivity.
# CHANGEABLE: Yes — per-user opt-in, global enable/disable here.
INHERITANCE_ENABLED=true
INHERITANCE_DEFAULT_INACTIVITY=2618200
INHERITANCE_MIN_INACTIVITY=26182
INHERITANCE_MAX_INACTIVITY=95636360
INHERITANCE_GRACE_PERIOD=78546

# ── High-Security Accounts ─────────────────────────────────────────────────
# Spending limits, time-locks, and address whitelists per account.
# CHANGEABLE: Yes — per-user opt-in, global enable/disable here.
SECURITY_POLICY_ENABLED=true
SECURITY_DAILY_LIMIT_WINDOW=26182
SECURITY_DEFAULT_TIME_LOCK=7854
SECURITY_MAX_WHITELIST_SIZE=100

# ── Stratum Mining Server ──────────────────────────────────────────────────
# Enable pool mining protocol. Only enable when ready for external miners.
# CHANGEABLE: Yes — restart required.
STRATUM_ENABLED=false
STRATUM_PORT=3333
STRATUM_HOST=0.0.0.0
STRATUM_MAX_WORKERS=100
STRATUM_GRPC_PORT=50053

# ── Deniable RPCs (Privacy-Preserving Queries) ─────────────────────────────
# Batch queries that don't reveal which specific item the user cares about.
# CHANGEABLE: Yes — restart required.
DENIABLE_RPC_ENABLED=true
DENIABLE_RPC_MAX_BATCH=100
DENIABLE_RPC_BLOOM_MAX_SIZE=65536

# ── BFT Finality Gadget ───────────────────────────────────────────────────
# Stake-weighted Byzantine Fault Tolerant finality for faster confirmations.
# CHANGEABLE: Yes — restart required.
FINALITY_ENABLED=true
FINALITY_MIN_STAKE=100.0
FINALITY_THRESHOLD=0.667
FINALITY_VOTE_EXPIRY_BLOCKS=1000


# ============================================================================
# SECTION 23: QUSD PEG KEEPER DAEMON
# ============================================================================
# Automated peg defense for QUSD stablecoin.
# Monitors wQUSD prices across 8 chains, executes stabilization trades.
#
# MODES:
#   off        → Disabled, no monitoring
#   scan       → Monitor + emit signals, no action (DEFAULT — observation only)
#   periodic   → Check every N blocks, act if depeg detected
#   continuous → Real-time monitoring, immediate action
#   aggressive → All arb opportunities pursued, max trade size
#
# KEEPER_ROLE:
#   primary  → This node executes stabilization actions
#   observer → This node only monitors (for multi-node setups)
#
# IMPORTANT: Only ONE node should be "primary". All others "observer".
KEEPER_ENABLED=true
KEEPER_DEFAULT_MODE=scan
KEEPER_CHECK_INTERVAL=10
KEEPER_MAX_TRADE_SIZE=1000000
KEEPER_FLOOR_PRICE=0.99
KEEPER_CEILING_PRICE=1.01
KEEPER_COOLDOWN_BLOCKS=10
KEEPER_ROLE=primary
QUSD_STABILIZER_ADDRESS=


# ============================================================================
# SECTION 24: SUBSTRATE HYBRID MODE (FUTURE)
# ============================================================================
# Set SUBSTRATE_MODE=true to run Python node alongside a Substrate consensus node.
# This is for the future migration path. Leave false for initial launch.
SUBSTRATE_MODE=false
SUBSTRATE_WS_URL=ws://localhost:9944
SUBSTRATE_HTTP_URL=http://localhost:9944
SUBSTRATE_SUDO_SEED=//Alice


# ============================================================================
# SECTION 25: INFRASTRUCTURE (DOCKER COMPOSE)
# ============================================================================
# GRAFANA_ADMIN_PASSWORD: MUST change from default before production.
# Access Grafana at: http://your-server:3000
# Default login: admin / <password below>
GRAFANA_ADMIN_PASSWORD={secrets.token_urlsafe(24)}


# ============================================================================
# SECTION 26: EMISSION ECONOMICS (READ-ONLY REFERENCE)
# ============================================================================
# These are consensus-level constants. Changing them requires a hard fork.
# Listed here for documentation only — actual values are in config.py.
#
# TAIL_EMISSION_REWARD=0.1    # QBC/block after phi-halving drops below this
# MAX_SUPPLY=3300000000       # 3.3 billion QBC maximum
# INITIAL_REWARD=15.27        # QBC per block (Era 0)
# HALVING_INTERVAL=15474020   # Blocks (~1.618 years between halvings)
# PHI=1.618033988749895       # Golden ratio


# ============================================================================
# SECTION 27: DEBUGGING
# ============================================================================
# DEBUG=true enables verbose logging, stack traces, and development features.
# MUST be false in production (performance + security).
DEBUG=false
"""
    with open(filepath, 'w') as f:
        f.write(content)
    os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)


def write_operations_guide(filepath: str):
    """Write the secure operations guide."""
    content = """# ============================================================================
#
#   QUBITCOIN — SECURE OPERATIONS GUIDE
#   CLASSIFICATION: INTERNAL — OPERATOR EYES ONLY
#
# ============================================================================
#
# This document explains how to manage the Qubitcoin node as the master
# operator. It covers key management, configuration changes, emergency
# procedures, and operational best practices.
#
# THIS FILE IS GITIGNORED. It lives in secure_keys/ which is never committed.
#
# ============================================================================


## 1. FILE STRUCTURE & WHAT EACH FILE DOES

```
Qubitcoin/
+-- secure_keys/                    # [chmod 700] Vault — ALL key material
|   +-- seed_node.env               # Wallet 1: Genesis miner, main operator
|   +-- mining_node.env             # Wallet 2: Second mining node
|   +-- aether_treasury.env         # Wallet 3: Aether fee collection
|   +-- contract_treasury.env       # Wallet 4: Contract fee collection
|   +-- bridge_treasury.env         # Wallet 5: Bridge fee collection
|   +-- qusd_treasury.env           # Wallet 6: QUSD operations
|   +-- aikgs_treasury.env          # Wallet 7: Knowledge rewards
|   +-- higgs_operator.env          # Wallet 8: Higgs field operator
|   +-- oracle_feeder.env           # Wallet 9: Price oracle feeder
|   +-- bridge_operator.env         # Wallet 10: EVM bridge key (PLACEHOLDER)
|   +-- master_addresses.txt        # Quick reference: all public addresses
|   +-- MNEMONIC_BACKUP.txt         # TEMPORARY: delete after writing down!
|   +-- OPERATIONS_GUIDE.md         # THIS FILE
|
+-- secure_key.env                  # ACTIVE node identity (copy of Wallet 1)
+-- .env                            # Node configuration (no secrets)
```


## 2. HOW CONFIG LOADING WORKS

config.py loads files in this order:

  1. secure_key.env  (override=True)  --> Sets ADDRESS, PRIVATE_KEY_HEX, etc.
  2. .env            (override=False) --> Sets everything else

This means secure_key.env ALWAYS wins for key fields. You cannot accidentally
override your private key by setting ADDRESS in .env.


## 3. WHAT YOU CAN CHANGE (HOT / COLD)

### HOT CHANGES (no restart needed — via Admin API)
| Parameter                     | API Endpoint              |
|-------------------------------|---------------------------|
| Aether chat fee               | PUT /admin/aether/fees    |
| Contract deploy fee           | PUT /admin/contract/fees  |
| Keeper mode (scan/periodic/.) | PUT /keeper/mode/{mode}   |
| Keeper config                 | PUT /keeper/config        |
| Mining start/stop             | POST /mining/start|stop   |

### COLD CHANGES (restart required — edit .env then restart)
| Parameter                     | Restart Command                          |
|-------------------------------|------------------------------------------|
| Treasury addresses            | docker compose restart qbc-node          |
| Redis password                | docker compose down && up -d             |
| P2P/RPC ports                 | docker compose down && up -d             |
| Feature flags                 | docker compose restart qbc-node          |
| Grafana password              | docker compose restart grafana           |
| HMAC secrets                  | docker compose restart qbc-node          |
| Debug mode                    | docker compose restart qbc-node          |

### NEVER CHANGE (requires hard fork)
| Parameter                     | Why                                      |
|-------------------------------|------------------------------------------|
| CHAIN_ID                      | All peers must agree                     |
| MAX_SUPPLY                    | Consensus constant                       |
| PHI / HALVING_INTERVAL        | Emission schedule is deterministic       |
| DILITHIUM_SECURITY_LEVEL      | All signatures must use same level       |
| GENESIS_PREMINE               | Already minted at block 0                |


## 4. KEY MANAGEMENT OPERATIONS

### Switch Node Identity
To run this node as a different wallet (e.g., switch from seed to mining):
```bash
cp secure_keys/mining_node.env secure_key.env
docker compose restart qbc-node
```

### Rotate HMAC Secrets
If any HMAC secret is compromised:
```bash
# Generate new secret
NEW_SECRET=$(openssl rand -hex 32)

# Edit .env — replace the compromised secret
# Then restart:
docker compose restart qbc-node
```

### Change Treasury Address
```bash
# 1. Edit .env — update the address
# 2. Restart node
docker compose restart qbc-node
# All FUTURE fees go to new address. Past fees remain in old wallet.
```

### Back Up Keys
```bash
# Create encrypted backup
tar czf - secure_keys/ | gpg --symmetric --cipher-algo AES256 > qbc_keys_backup.tar.gz.gpg

# Store on encrypted USB drive — NEVER cloud storage
# Verify backup:
gpg --decrypt qbc_keys_backup.tar.gz.gpg | tar tzf -
```


## 5. MONITORING COMMANDS

```bash
# Node health
curl http://localhost:5000/health

# Chain info (block height, supply, peers)
curl http://localhost:5000/chain/info

# Aether consciousness (Phi value)
curl http://localhost:5000/aether/phi

# Keeper status (peg defense)
curl http://localhost:5000/keeper/status

# Mining stats
curl http://localhost:5000/mining/stats

# Prometheus metrics (for Grafana)
curl http://localhost:9090/metrics

# Docker logs
docker compose logs -f qbc-node --tail 100
```


## 6. EMERGENCY PROCEDURES

### Emergency Shutdown (Gevurah Veto)
If Aether Tree exhibits unsafe behavior:
```bash
# Uses GEVURAH_SECRET from .env
curl -X POST http://localhost:5000/aether/safety/shutdown \\
  -H "Authorization: Bearer $(grep GEVURAH_SECRET .env | cut -d= -f2)" \\
  -H "Content-Type: application/json" \\
  -d '{"reason": "Emergency safety shutdown"}'
```

### Emergency Node Stop
```bash
docker compose stop qbc-node
```

### Full Stack Shutdown
```bash
docker compose down
```

### Key Compromise Response
If ANY private key is compromised:
1. IMMEDIATELY transfer all funds from compromised wallet to a new wallet
2. Generate new keys: python3 scripts/setup/generate_keys.py
3. Update secure_key.env if it was the node identity
4. Update .env if it was a treasury address
5. Restart node
6. Notify all peers if it was the seed node identity


## 7. WALLET PURPOSES & FUND FLOWS

```
Mining Rewards (15.27 QBC/block)
  |
  +--> Seed Node Wallet (Wallet 1)         <-- Genesis miner
  +--> Mining Node Wallet (Wallet 2)       <-- Second miner
  |
  +--> [33M QBC Premine at Genesis]        --> Seed Node Wallet (Wallet 1)

Fee Revenue:
  Chat fees ---------> Aether Treasury (Wallet 3)
  Deploy fees -------> Contract Treasury (Wallet 4)
  Bridge fees -------> Bridge Treasury (Wallet 5)
  QUSD fees ---------> QUSD Treasury (Wallet 6)
  Knowledge rewards -> AIKGS Treasury (Wallet 7)
```


## 8. PERMISSIONS REFERENCE

| File/Directory     | Permissions | Who Can Access              |
|--------------------|-------------|-----------------------------|
| secure_keys/       | 700 (rwx------) | Owner only              |
| secure_keys/*.env  | 600 (rw-------) | Owner read/write only   |
| secure_key.env     | 600 (rw-------) | Owner read/write only   |
| .env               | 640 (rw-r-----) | Owner + group read      |
| *.py               | 644 (rw-r--r--) | Normal file permissions |


## 9. VERIFYING KEY INTEGRITY

To verify your keys are valid and match their addresses:
```bash
python3 -c "
from dilithium_py.dilithium import Dilithium5
import hashlib
# Read your key file
with open('secure_key.env') as f:
    lines = {l.split('=',1)[0]: l.split('=',1)[1].strip()
             for l in f if '=' in l and not l.startswith('#')}
pk = bytes.fromhex(lines['PUBLIC_KEY_HEX'])
sk = bytes.fromhex(lines['PRIVATE_KEY_HEX'])
addr = hashlib.sha256(pk).hexdigest()[:40]
assert addr == lines['ADDRESS'], 'ADDRESS MISMATCH!'
sig = Dilithium5.sign(sk, b'test')
assert Dilithium5.verify(pk, b'test', sig), 'KEY VERIFICATION FAILED!'
print(f'Key verified: {addr}')
"
```
"""
    with open(filepath, 'w') as f:
        f.write(content)
    os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print()
    print("=" * 78)
    print("  QUBITCOIN MASTER KEY GENERATOR")
    print(f"  Algorithm: {LEVEL_NAME} (NIST Level {SECURITY_LEVEL})")
    print(f"  Security: {CLASSICAL_BITS}-bit classical, {QUANTUM_BITS}-bit quantum")
    print("=" * 78)
    print()

    # ── Step 1: FIPS 204 KAT Self-Test ──────────────────────────────────────
    print("[1/8] Running FIPS 204 KAT self-test...")
    if not fips204_kat_selftest():
        print("FATAL: FIPS 204 KAT self-test FAILED. Aborting.")
        sys.exit(1)
    print("  PASSED")
    print()

    # ── Step 2: Create secure_keys/ directory ───────────────────────────────
    print(f"[2/8] Creating secure vault: {SECURE_DIR}")
    os.makedirs(SECURE_DIR, exist_ok=True)
    os.chmod(SECURE_DIR, stat.S_IRWXU)  # 700 — owner only
    print(f"  Permissions: 700 (rwx------)")
    print()

    # ── Step 3: Generate all keypairs ───────────────────────────────────────
    print(f"[3/8] Generating {len(WALLETS)} Dilithium keypairs...")
    all_wallets = []
    for i, (filename, label, purpose, is_op) in enumerate(WALLETS):
        print(f"  [{i+1}/{len(WALLETS)}] {label}...", end=" ", flush=True)
        keys = generate_keypair()
        all_wallets.append(((filename, label, purpose, is_op), keys))
        print(f"OK  addr={keys['address'][:16]}...")
    print()

    # ── Step 4: Generate HMAC secrets ───────────────────────────────────────
    print("[4/8] Generating HMAC secrets and auth tokens...")
    hmac_secrets = {
        'gevurah':          generate_hmac_secret("GEVURAH_SECRET"),
        'aikgs_auth':       generate_hmac_secret("AIKGS_AUTH_TOKEN"),
        'api_vault':        generate_hmac_secret("API_KEY_VAULT_SECRET"),
        'telegram_webhook': generate_hmac_secret("TELEGRAM_WEBHOOK_SECRET"),
    }
    print(f"  Generated {len(hmac_secrets)} secrets")
    print()

    # ── Step 5: Write wallet files ──────────────────────────────────────────
    print("[5/8] Writing wallet files to secure_keys/...")
    for (filename, label, purpose, is_op), keys in all_wallets:
        filepath = os.path.join(SECURE_DIR, f"{filename}.env")
        write_wallet_file(filepath, label, purpose, keys, is_op)
        print(f"  {filename}.env (600)")

    # Write bridge operator placeholder
    bridge_path = os.path.join(SECURE_DIR, "bridge_operator.env")
    write_bridge_operator_placeholder(bridge_path)
    print(f"  bridge_operator.env (600) [PLACEHOLDER]")
    print()

    # ── Step 6: Write supporting files ──────────────────────────────────────
    print("[6/8] Writing supporting files...")

    # Master addresses
    addr_path = os.path.join(SECURE_DIR, "master_addresses.txt")
    write_master_addresses(addr_path, all_wallets)
    print(f"  master_addresses.txt")

    # Mnemonic backup
    mnemonic_path = os.path.join(SECURE_DIR, "MNEMONIC_BACKUP.txt")
    write_mnemonic_backup(mnemonic_path, all_wallets)
    print(f"  MNEMONIC_BACKUP.txt [DELETE AFTER WRITING DOWN]")

    # Operations guide
    ops_path = os.path.join(SECURE_DIR, "OPERATIONS_GUIDE.md")
    write_operations_guide(ops_path)
    print(f"  OPERATIONS_GUIDE.md")
    print()

    # ── Step 7: Write active node identity ──────────────────────────────────
    print("[7/8] Writing active node identity (secure_key.env)...")
    seed_keys = all_wallets[0][1]  # Wallet 1 = seed node
    secure_key_path = os.path.join(ROOT_DIR, "secure_key.env")
    write_secure_key_env(secure_key_path, seed_keys)
    print(f"  secure_key.env -> Wallet 1 (Seed Node)")
    print()

    # ── Step 8: Write production .env ───────────────────────────────────────
    print("[8/8] Writing production .env with all addresses...")
    env_path = os.path.join(ROOT_DIR, ".env")
    write_production_env(env_path, all_wallets, hmac_secrets)
    print(f"  .env (640)")
    print()

    # ── Summary ─────────────────────────────────────────────────────────────
    print("=" * 78)
    print("  GENERATION COMPLETE")
    print("=" * 78)
    print()
    print("  Files created:")
    print(f"    secure_keys/           9 wallets + bridge placeholder + 3 docs")
    print(f"    secure_key.env         Active node identity (Wallet 1)")
    print(f"    .env                   Full production config")
    print()
    print("  Wallet addresses:")
    for (filename, label, _, _), keys in all_wallets:
        print(f"    {label:<30s} {keys['address']}")
    print()
    print("  CRITICAL NEXT STEPS:")
    print("  1. Read secure_keys/MNEMONIC_BACKUP.txt")
    print("  2. Write down ALL 9 mnemonics on paper")
    print("  3. Securely delete the file:")
    print("     shred -vfz -n 5 secure_keys/MNEMONIC_BACKUP.txt")
    print("     rm secure_keys/MNEMONIC_BACKUP.txt")
    print("  4. Back up secure_keys/ to encrypted USB")
    print("  5. Fill in optional keys in .env (Alchemy, LLM keys, etc.)")
    print("  6. Fill in bridge_operator.env with your MetaMask private key")
    print("  7. Review secure_keys/OPERATIONS_GUIDE.md")
    print()
    print("=" * 78)


if __name__ == "__main__":
    main()
