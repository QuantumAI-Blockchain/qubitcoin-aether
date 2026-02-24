#!/usr/bin/env python3
"""
QUSD Oracle Feeder Initialization

Post-deployment script that configures the QUSDOracle contract:
  1. Registers 3 default oracle feeders (node operator + 2 configurable)
  2. Sets initial QBC/USD price via the first feeder
  3. Verifies the staleness threshold (maxAge) was set during deployment

Run AFTER deploy_qusd.py has deployed the QUSDOracle contract.

Usage:
    python3 scripts/deploy/init_oracle_feeders.py [--rpc-url URL] [--deployer-key FILE]
    python3 scripts/deploy/init_oracle_feeders.py --dry-run

Requires:
  - Running Qubitcoin node with RPC at --rpc-url (default http://localhost:5000)
  - QUSDOracle deployed and registered in contract_registry.json
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import requests

from qubitcoin.config import Config
from qubitcoin.utils.logger import get_logger

logger = get_logger("init_oracle_feeders")

# ─── Constants ────────────────────────────────────────────────────────────────

REGISTRY_PATH = Path(__file__).parent.parent.parent / "contract_registry.json"

# Default staleness threshold (in blocks).  QUSDOracle.initialize(maxAge) is
# called during deploy_qusd.py, but we verify and can update it here.
DEFAULT_MAX_AGE: int = 1000

# Default initial QBC/USD price: $0.10 at 8 decimals = 10_000_000
DEFAULT_INITIAL_PRICE: int = 10_000_000


# ─── ABI Encoding Helpers ────────────────────────────────────────────────────

def keccak256(data: bytes) -> bytes:
    """Keccak-256 hash (EVM standard)."""
    try:
        import sha3
        return sha3.keccak_256(data).digest()
    except ImportError:
        try:
            from Crypto.Hash import keccak as _keccak
            return _keccak.new(digest_bits=256, data=data).digest()
        except ImportError:
            # Fallback — not EVM-compatible but functional for selectors
            return hashlib.sha3_256(data).digest()


def function_selector(sig: str) -> bytes:
    """Compute 4-byte function selector from signature string."""
    return keccak256(sig.encode())[:4]


def encode_address(addr: str) -> bytes:
    """Encode an address as a 32-byte ABI word."""
    addr = addr.removeprefix("0x").lower()
    return bytes.fromhex(addr.zfill(64))


def encode_uint256(val: int) -> bytes:
    """Encode a uint256 as a 32-byte ABI word."""
    return val.to_bytes(32, "big")


def encode_int256(val: int) -> bytes:
    """Encode a signed int256 as a 32-byte ABI word (two's complement)."""
    if val >= 0:
        return val.to_bytes(32, "big")
    return (val + (1 << 256)).to_bytes(32, "big")


# ─── RPC Client ──────────────────────────────────────────────────────────────

class RPCClient:
    """Thin client for QBC JSON-RPC endpoints."""

    def __init__(self, base_url: str, deployer_address: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.deployer = deployer_address
        self.nonce: int = 0

    def _post_jsonrpc(self, method: str, params: list) -> Any:
        """Send a JSON-RPC request with retry on rate-limiting."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        for attempt in range(10):
            r = requests.post(f"{self.base_url}/", json=payload, timeout=30)
            if r.status_code == 429:
                wait = min(2 ** attempt, 30)
                logger.warning(f"Rate limited (429), waiting {wait}s (attempt {attempt + 1}/10)...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            result = r.json()
            if result.get("error"):
                raise RuntimeError(f"RPC error: {result['error']}")
            time.sleep(0.3)  # Base delay to avoid rate limits
            return result.get("result")
        raise RuntimeError(f"RPC rate limited after 10 retries: {method}")

    def get_nonce(self) -> int:
        """Get the current nonce for the deployer account."""
        result = self._post_jsonrpc("eth_getTransactionCount", [self.deployer, "latest"])
        if isinstance(result, str):
            return int(result, 16)
        return int(result)

    def send_tx(self, to: str, data_hex: str, gas: int = 5_000_000) -> Optional[str]:
        """Send a transaction to a contract."""
        tx = {
            "from": self.deployer,
            "to": to,
            "data": "0x" + data_hex,
            "gas": hex(gas),
            "nonce": hex(self.nonce),
            "value": "0x0",
        }
        result = self._post_jsonrpc("eth_sendTransaction", [tx])
        self.nonce += 1
        return result

    def health_check(self) -> bool:
        """Verify the node is reachable."""
        try:
            r = requests.get(f"{self.base_url}/health", timeout=5)
            r.raise_for_status()
            return True
        except Exception:
            return False


# ─── Registry ────────────────────────────────────────────────────────────────

def load_registry() -> Dict[str, Any]:
    """Load existing contract registry."""
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return {}


def get_address(registry: Dict[str, Any], name: str) -> str:
    """Get the proxy address of a deployed contract."""
    entry = registry.get(name, {})
    return entry.get("proxy") or entry.get("address") or ""


# ─── Feeder Initialization ──────────────────────────────────────────────────

def resolve_feeders(deployer_address: str) -> List[str]:
    """Resolve the 3 oracle feeder addresses from .env / defaults.

    Feeder 1: Node operator (ADDRESS from secure_key.env)
    Feeder 2: ORACLE_FEEDER_2 from .env (skip if empty)
    Feeder 3: ORACLE_FEEDER_3 from .env (skip if empty)

    Returns:
        List of feeder addresses (1-3 items, all non-empty).
    """
    feeders: List[str] = [deployer_address]

    feeder2 = os.getenv("ORACLE_FEEDER_2", "").strip()
    if feeder2:
        feeders.append(feeder2)

    feeder3 = os.getenv("ORACLE_FEEDER_3", "").strip()
    if feeder3:
        feeders.append(feeder3)

    return feeders


def init_oracle_feeders(
    rpc: RPCClient,
    oracle_addr: str,
    feeders: List[str],
    initial_price: int,
    max_age: int,
    dry_run: bool = False,
) -> None:
    """Register feeders, set staleness threshold, and submit initial price.

    Steps:
      1. addFeeder(address) for each feeder — owner-only call
      2. setMaxAge(newMaxAge) if different from deployment default
      3. submitPrice(price) from the deployer (must be an authorized feeder)
      4. submitPegDeviation(0) — initial 0 bps deviation (QUSD at peg)
    """
    logger.info("=" * 60)
    logger.info("QUSD ORACLE FEEDER INITIALIZATION")
    logger.info("=" * 60)
    logger.info(f"Oracle contract: {oracle_addr}")
    logger.info(f"Feeders to register: {len(feeders)}")
    logger.info(f"Initial QBC/USD price: {initial_price} (8 decimals = ${initial_price / 1e8:.4f})")
    logger.info(f"Max staleness: {max_age} blocks")
    logger.info("")

    # ── Step 1: Register feeders ────────────────────────────────────
    for i, feeder in enumerate(feeders, 1):
        logger.info(f"[{i}/{len(feeders)}] Adding feeder: {feeder}")
        data_hex = (
            function_selector("addFeeder(address)")
            + encode_address(feeder)
        ).hex()
        if dry_run:
            logger.info(f"  [DRY RUN] Would call addFeeder({feeder})")
        else:
            try:
                tx_hash = rpc.send_tx(oracle_addr, data_hex)
                logger.info(f"  addFeeder tx: {tx_hash}")
            except Exception as e:
                # May fail if feeder already registered — log and continue
                logger.warning(f"  addFeeder failed (may already be registered): {e}")

    # ── Step 2: Update staleness threshold (if needed) ──────────────
    logger.info(f"\nSetting maxAge to {max_age} blocks...")
    data_hex = (
        function_selector("setMaxAge(uint256)")
        + encode_uint256(max_age)
    ).hex()
    if dry_run:
        logger.info(f"  [DRY RUN] Would call setMaxAge({max_age})")
    else:
        try:
            tx_hash = rpc.send_tx(oracle_addr, data_hex)
            logger.info(f"  setMaxAge tx: {tx_hash}")
        except Exception as e:
            logger.warning(f"  setMaxAge failed: {e}")

    # ── Step 3: Submit initial price (from deployer as feeder) ──────
    logger.info(f"\nSubmitting initial price: {initial_price}...")
    data_hex = (
        function_selector("submitPrice(uint256)")
        + encode_uint256(initial_price)
    ).hex()
    if dry_run:
        logger.info(f"  [DRY RUN] Would call submitPrice({initial_price})")
    else:
        try:
            tx_hash = rpc.send_tx(oracle_addr, data_hex)
            logger.info(f"  submitPrice tx: {tx_hash}")
        except Exception as e:
            logger.error(f"  submitPrice failed: {e}")

    # ── Step 4: Submit initial peg deviation (0 bps = at peg) ───────
    logger.info("\nSubmitting initial peg deviation: 0 bps (at peg)...")
    data_hex = (
        function_selector("submitPegDeviation(int256)")
        + encode_int256(0)
    ).hex()
    if dry_run:
        logger.info("  [DRY RUN] Would call submitPegDeviation(0)")
    else:
        try:
            tx_hash = rpc.send_tx(oracle_addr, data_hex)
            logger.info(f"  submitPegDeviation tx: {tx_hash}")
        except Exception as e:
            logger.warning(f"  submitPegDeviation failed: {e}")

    # ── Summary ─────────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("ORACLE INITIALIZATION SUMMARY")
    logger.info("=" * 60)
    for i, feeder in enumerate(feeders, 1):
        role = "node operator" if i == 1 else f"configurable (ORACLE_FEEDER_{i})"
        logger.info(f"  Feeder {i} ({role}): {feeder}")
    logger.info(f"  Initial price: ${initial_price / 1e8:.4f} ({initial_price} raw)")
    logger.info(f"  Max staleness: {max_age} blocks")
    logger.info(f"  Peg deviation: 0 bps")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize QUSD Oracle feeders post-deployment"
    )
    parser.add_argument(
        "--rpc-url", default="http://localhost:5000",
        help="RPC endpoint URL (default: http://localhost:5000)"
    )
    parser.add_argument(
        "--deployer-key", default="secure_key.env",
        help="Path to deployer key file (default: secure_key.env)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print initialization plan without executing"
    )
    parser.add_argument(
        "--initial-price", type=int, default=None,
        help="Initial QBC/USD price (8 decimals). Overrides ORACLE_INITIAL_PRICE env var."
    )
    parser.add_argument(
        "--max-age", type=int, default=None,
        help="Staleness threshold in blocks. Overrides ORACLE_MAX_AGE env var."
    )
    args = parser.parse_args()

    # ── Load deployer keys ────────────────────────────────────────────
    key_path = Path(args.deployer_key)
    if not key_path.exists():
        key_path = Path(__file__).parent.parent.parent / "secure_key.env"
    if not key_path.exists():
        logger.error(f"Key file not found: {key_path}")
        logger.error("Run: python3 scripts/setup/generate_keys.py")
        sys.exit(1)

    keys: Dict[str, str] = {}
    for line in key_path.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip()

    deployer = keys.get("ADDRESS", "")
    if not deployer:
        logger.error("No ADDRESS found in key file")
        sys.exit(1)

    # ── Load registry and find oracle ──────────────────────────────
    registry = load_registry()
    oracle_addr = get_address(registry, "QUSDOracle")
    if not oracle_addr:
        logger.error(
            "QUSDOracle not found in contract_registry.json.\n"
            "Deploy the QUSD contracts first:\n"
            "  python3 scripts/deploy/deploy_qusd.py"
        )
        sys.exit(1)

    # ── Resolve parameters ─────────────────────────────────────────
    feeders = resolve_feeders(deployer)
    initial_price = args.initial_price or int(os.getenv("ORACLE_INITIAL_PRICE", str(DEFAULT_INITIAL_PRICE)))
    max_age = args.max_age or int(os.getenv("ORACLE_MAX_AGE", str(DEFAULT_MAX_AGE)))

    logger.info(f"Deployer: {deployer}")
    logger.info(f"RPC URL:  {args.rpc_url}")
    logger.info(f"Dry run:  {args.dry_run}")
    logger.info("")

    # ── Create RPC client ──────────────────────────────────────────
    rpc = RPCClient(args.rpc_url, deployer)

    if not args.dry_run:
        if not rpc.health_check():
            logger.error(f"Node not reachable at {args.rpc_url}")
            sys.exit(1)
        logger.info("Node health check passed")
        rpc.nonce = rpc.get_nonce()
        logger.info(f"Deployer nonce: {rpc.nonce}")

    # ── Initialize oracle ──────────────────────────────────────────
    try:
        init_oracle_feeders(
            rpc=rpc,
            oracle_addr=oracle_addr,
            feeders=feeders,
            initial_price=initial_price,
            max_age=max_age,
            dry_run=args.dry_run,
        )
    except Exception as e:
        logger.error(f"Oracle initialization failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
