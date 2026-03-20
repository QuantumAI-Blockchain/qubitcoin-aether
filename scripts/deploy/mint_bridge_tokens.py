#!/usr/bin/env python3
"""
Mint Bridge Tokens on Deployed Chains

Mints 100K wQBC and 100K wQUSD on each chain where contracts are deployed.
The deployer is the bridge operator with mint authority.

Usage:
    python3 scripts/deploy/mint_bridge_tokens.py
    python3 scripts/deploy/mint_bridge_tokens.py --chains polygon,arbitrum
    python3 scripts/deploy/mint_bridge_tokens.py --amount 50000
    python3 scripts/deploy/mint_bridge_tokens.py --dry-run

Prerequisites:
    pip install web3
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from qubitcoin.utils.logger import get_logger

logger = get_logger("mint_bridge_tokens")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = PROJECT_ROOT / "contract_registry.json"

TOKEN_DECIMALS = 8

# Chain configs
EVM_CHAINS: Dict[str, Dict[str, Any]] = {
    "ethereum": {"chainId": 1, "gasStrategy": "eip1559"},
    "bsc": {"chainId": 56, "gasStrategy": "legacy"},
    "polygon": {"chainId": 137, "gasStrategy": "eip1559"},
    "avalanche": {"chainId": 43114, "gasStrategy": "eip1559"},
    "arbitrum": {"chainId": 42161, "gasStrategy": "eip1559"},
    "optimism": {"chainId": 10, "gasStrategy": "eip1559"},
    "base": {"chainId": 8453, "gasStrategy": "eip1559"},
}


def parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a .env file into a dict."""
    result: Dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def keccak256(data: bytes) -> bytes:
    """Keccak-256 hash."""
    try:
        import sha3
        return sha3.keccak_256(data).digest()
    except ImportError:
        try:
            from Crypto.Hash import keccak as _keccak
            return _keccak.new(digest_bits=256, data=data).digest()
        except ImportError:
            logger.warning("No Keccak library — using hashlib.sha3_256 (NOT Keccak)")
            return hashlib.sha3_256(data).digest()


def function_selector(sig: str) -> bytes:
    """4-byte function selector."""
    return keccak256(sig.encode())[:4]


def encode_address(addr: str) -> bytes:
    """Encode address as 32-byte ABI word."""
    return bytes.fromhex(addr.removeprefix("0x").lower().zfill(64))


def encode_uint256(val: int) -> bytes:
    """Encode uint256 as 32-byte ABI word."""
    return val.to_bytes(32, "big")


def encode_bytes32(val: bytes) -> bytes:
    """Encode bytes32."""
    return val.ljust(32, b"\x00")[:32]


def send_tx(
    w3: Any,
    account: Any,
    to: str,
    data: bytes,
    chain_name: str,
    chain_id: int,
    gas_strategy: str,
    gas_limit: int = 300_000,
) -> Optional[str]:
    """Build, sign, and send a transaction. Returns tx hash or None."""
    nonce = w3.eth.get_transaction_count(account.address, "pending")

    tx: Dict[str, Any] = {
        "from": account.address,
        "to": w3.to_checksum_address(to),
        "nonce": nonce,
        "gas": gas_limit,
        "chainId": chain_id,
        "data": "0x" + data.hex(),
    }

    if gas_strategy == "eip1559":
        latest = w3.eth.get_block("latest")
        base_fee = latest.get("baseFeePerGas", 0)
        try:
            max_priority = w3.eth.max_priority_fee
            # Only enforce 2 gwei min on L1 chains
            if chain_id in (1, 56, 137, 43114):
                max_priority = max(max_priority, w3.to_wei(2, "gwei"))
        except Exception:
            max_priority = w3.to_wei(30, "gwei")
        tx["maxFeePerGas"] = base_fee * 2 + max_priority
        tx["maxPriorityFeePerGas"] = max_priority
    else:
        tx["gasPrice"] = w3.eth.gas_price

    try:
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex = tx_hash.hex()
        logger.info(f"[{chain_name}] Tx sent: {tx_hash_hex[:16]}...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        if receipt["status"] != 1:
            logger.error(f"[{chain_name}] Tx FAILED: {tx_hash_hex}")
            return None

        logger.info(f"[{chain_name}] Tx confirmed (gas={receipt['gasUsed']:,})")
        return tx_hash_hex

    except Exception as e:
        logger.error(f"[{chain_name}] Tx failed: {e}")
        return None


def check_token_balance(
    w3: Any, token_address: str, holder: str
) -> int:
    """Read ERC-20 balanceOf via eth_call."""
    sel = function_selector("balanceOf(address)")
    data = "0x" + (sel + encode_address(holder)).hex()
    result = w3.eth.call({
        "to": w3.to_checksum_address(token_address),
        "data": data,
    })
    return int(result.hex(), 16) if result else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mint 100K wQBC + 100K wQUSD on deployed chains",
    )
    parser.add_argument(
        "--chains", type=str, default="",
        help="Comma-separated chains (default: all deployed chains)",
    )
    parser.add_argument(
        "--amount", type=int, default=100_000,
        help="Amount of each token to mint (default: 100000)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be minted without sending transactions",
    )
    parser.add_argument(
        "--skip-minted", action="store_true", default=True,
        help="Skip tokens that already have the target balance (default: true)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  BRIDGE TOKEN MINTING")
    print(f"  Minting {args.amount:,} wQBC + {args.amount:,} wQUSD per chain")
    print("=" * 60)

    keys = parse_env_file(PROJECT_ROOT / "secure_key.env")
    env_vars = parse_env_file(PROJECT_ROOT / ".env")

    private_key = keys.get("ETH_DEPLOYER_PRIVATE_KEY", "")
    if not private_key:
        logger.error("ETH_DEPLOYER_PRIVATE_KEY not found in secure_key.env")
        sys.exit(1)

    if not REGISTRY_PATH.exists():
        logger.error("contract_registry.json not found")
        sys.exit(1)

    registry = json.loads(REGISTRY_PATH.read_text())

    # Determine chains
    if args.chains:
        chains = [c.strip().lower() for c in args.chains.split(",") if c.strip()]
    else:
        chains = []
        for key in registry:
            if key.startswith("external:") and key.endswith(":wQBC"):
                chain = key.split(":")[1]
                if chain in EVM_CHAINS:
                    chains.append(chain)
        chains = sorted(set(chains))

    raw_amount = args.amount * (10 ** TOKEN_DECIMALS)

    # QBC tx ID for mint — use a deterministic hash based on chain + amount
    base_tx_id = keccak256(f"qbc-bridge-initial-mint-{args.amount}".encode())

    results: Dict[str, Dict[str, str]] = {}

    for chain in chains:
        chain_cfg = EVM_CHAINS.get(chain)
        if not chain_cfg:
            logger.warning(f"Unknown chain: {chain}, skipping")
            continue

        wqbc_entry = registry.get(f"external:{chain}:wQBC", {})
        wqusd_entry = registry.get(f"external:{chain}:wQUSD", {})

        wqbc_addr = wqbc_entry.get("address", "")
        wqusd_addr = wqusd_entry.get("address", "")

        if not wqbc_addr or not wqusd_addr:
            logger.warning(f"[{chain}] Contracts not deployed, skipping")
            continue

        rpc_key = f"{chain.upper()}_RPC_URL"
        rpc_url = env_vars.get(rpc_key, os.getenv(rpc_key, ""))
        if not rpc_url:
            logger.error(f"[{chain}] No RPC URL ({rpc_key}), skipping")
            continue

        print(f"\n--- {chain.upper()} ---")

        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(rpc_url))

        if chain in ("bsc", "polygon"):
            try:
                from web3.middleware import ExtraDataToPOAMiddleware
                w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            except ImportError:
                pass

        if not w3.is_connected():
            logger.error(f"[{chain}] Cannot connect to {rpc_url}")
            results[chain] = {"wQBC": "rpc_failed", "wQUSD": "rpc_failed"}
            continue

        account = w3.eth.account.from_key(private_key)
        chain_id = chain_cfg["chainId"]
        gas_strategy = chain_cfg["gasStrategy"]

        # Check native balance
        native_bal = w3.eth.get_balance(account.address)
        logger.info(f"[{chain}] Native balance: {native_bal / 10**18:.6f}")

        if native_bal == 0:
            logger.error(f"[{chain}] Zero native balance — cannot send txs")
            results[chain] = {"wQBC": "no_gas", "wQUSD": "no_gas"}
            continue

        results[chain] = {}

        # ── Mint wQBC ──
        # wQBC.mint(address to, uint256 amount, bytes32 qbcTxId)
        existing_wqbc = check_token_balance(w3, wqbc_addr, account.address)
        if args.skip_minted and existing_wqbc >= raw_amount:
            logger.info(
                f"[{chain}] wQBC already minted: {existing_wqbc / 10**TOKEN_DECIMALS:,.0f}"
            )
            results[chain]["wQBC"] = f"already_minted ({existing_wqbc / 10**TOKEN_DECIMALS:,.0f})"
        else:
            qbc_tx_id = keccak256(f"initial-mint-wqbc-{chain}".encode())
            mint_data = (
                function_selector("mint(address,uint256,bytes32)")
                + encode_address(account.address)
                + encode_uint256(raw_amount)
                + encode_bytes32(qbc_tx_id)
            )

            if args.dry_run:
                logger.info(f"[{chain}] [DRY RUN] Would mint {args.amount:,} wQBC")
                results[chain]["wQBC"] = "dry_run"
            else:
                tx = send_tx(w3, account, wqbc_addr, mint_data, chain, chain_id, gas_strategy)
                if tx:
                    results[chain]["wQBC"] = f"minted (tx={tx[:16]}...)"
                else:
                    results[chain]["wQBC"] = "failed"

            time.sleep(2)

        # ── Mint wQUSD ──
        # wQUSD.bridgeMint(address recipient, uint256 amount, bytes32 sourceTxHash, bytes32 proofHash)
        existing_wqusd = check_token_balance(w3, wqusd_addr, account.address)
        if args.skip_minted and existing_wqusd >= raw_amount:
            logger.info(
                f"[{chain}] wQUSD already minted: {existing_wqusd / 10**TOKEN_DECIMALS:,.0f}"
            )
            results[chain]["wQUSD"] = f"already_minted ({existing_wqusd / 10**TOKEN_DECIMALS:,.0f})"
        else:
            source_tx_hash = keccak256(f"initial-mint-wqusd-{chain}-source".encode())
            proof_hash = keccak256(f"initial-mint-wqusd-{chain}-proof".encode())
            mint_data = (
                function_selector("bridgeMint(address,uint256,bytes32,bytes32)")
                + encode_address(account.address)
                + encode_uint256(raw_amount)
                + encode_bytes32(source_tx_hash)
                + encode_bytes32(proof_hash)
            )

            if args.dry_run:
                logger.info(f"[{chain}] [DRY RUN] Would mint {args.amount:,} wQUSD")
                results[chain]["wQUSD"] = "dry_run"
            else:
                tx = send_tx(w3, account, wqusd_addr, mint_data, chain, chain_id, gas_strategy)
                if tx:
                    results[chain]["wQUSD"] = f"minted (tx={tx[:16]}...)"
                else:
                    results[chain]["wQUSD"] = "failed"

            time.sleep(2)

    # Summary
    print("\n" + "=" * 60)
    print("  MINTING SUMMARY")
    print("=" * 60)
    for chain, tokens in results.items():
        for token, status in tokens.items():
            print(f"  {chain:12s} {token:6s}: {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
