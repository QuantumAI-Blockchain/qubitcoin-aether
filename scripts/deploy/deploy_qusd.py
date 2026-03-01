#!/usr/bin/env python3
"""
QUSD Stablecoin Deployment Script

Deploys the 8 QUSD contracts in dependency order:
  1. QUSDOracle       — standalone price oracle
  2. QUSDGovernance   — reserve governance (linked to QUSD post-deploy)
  3. QUSDReserve      — multi-asset reserve pool
  4. QUSD             — core QBC-20 stablecoin token (3.3B mint)
  5. QUSDDebtLedger   — fractional payback tracking
  6. QUSDStabilizer   — peg maintenance ($0.99-$1.01 bands)
  7. QUSDAllocation   — vesting & distribution (50/30/15/5 split)
  8. wQUSD            — wrapped QUSD for cross-chain bridging

Idempotent: skips contracts already present in contract_registry.json.
Updates contract_registry.json after each successful deployment.

Usage:
    python3 scripts/deploy/deploy_qusd.py [--rpc-url URL] [--deployer-key FILE]
    python3 scripts/deploy/deploy_qusd.py --dry-run   # Print plan without deploying

Requires a running Qubitcoin node with RPC at --rpc-url (default http://localhost:5000).
"""

import argparse
import hashlib
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import requests

from qubitcoin.config import Config
from qubitcoin.utils.logger import get_logger

logger = get_logger("deploy_qusd")

# ─── Constants ────────────────────────────────────────────────────────────────

QUSD_CONTRACTS: List[str] = [
    "QUSDOracle",
    "QUSDGovernance",
    "QUSDReserve",
    "QUSD",
    "QUSDDebtLedger",
    "QUSDStabilizer",
    "QUSDAllocation",
    "wQUSD",
]

REGISTRY_PATH = Path(__file__).parent.parent.parent / "contract_registry.json"


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


# ─── RPC Client ──────────────────────────────────────────────────────────────

class RPCClient:
    """Thin client for QBC JSON-RPC and REST endpoints."""

    def __init__(self, base_url: str, deployer_address: str):
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

    def deploy_bytecode(self, bytecode_hex: str, gas: int = 10_000_000) -> Optional[str]:
        """Deploy raw bytecode and return the contract address."""
        tx = {
            "from": self.deployer,
            "data": "0x" + bytecode_hex,
            "gas": hex(gas),
            "nonce": hex(self.nonce),
            "value": "0x0",
        }
        result = self._post_jsonrpc("eth_sendTransaction", [tx])
        self.nonce += 1

        if result:
            receipt = self._get_receipt(result)
            if receipt:
                addr = receipt.get("contractAddress") or receipt.get("contract_address")
                if addr:
                    return addr
        return None

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

    def _get_receipt(self, tx_hash: str) -> Optional[dict]:
        """Poll for transaction receipt."""
        for _ in range(20):
            try:
                result = self._post_jsonrpc("eth_getTransactionReceipt", [tx_hash])
                if result:
                    return result
            except Exception:
                pass
            time.sleep(0.5)
        return None

    def health_check(self) -> bool:
        """Verify the node is reachable."""
        try:
            r = requests.get(f"{self.base_url}/health", timeout=5)
            r.raise_for_status()
            return True
        except Exception:
            return False


# ─── Init Code Builder ───────────────────────────────────────────────────────

def make_init_code(runtime_hex: str = "") -> str:
    """Create minimal deployment init code that returns runtime bytecode.

    QVM executes init code and stores the returned bytes as the contract's
    runtime bytecode.  This wraps any runtime hex (or a placeholder) in a
    tiny deployer preamble:

        PUSH<len> PUSH1 <offset> PUSH1 0 CODECOPY
        PUSH<len> PUSH1 0 RETURN
        <runtime bytes>
    """
    if not runtime_hex:
        runtime_hex = "00"  # STOP opcode placeholder
    runtime = bytes.fromhex(runtime_hex)
    rlen = len(runtime)

    def build(offset: int) -> bytearray:
        code = bytearray()
        if rlen <= 0xFF:
            code += bytes([0x60, rlen])
        else:
            code += bytes([0x61]) + rlen.to_bytes(2, "big")
        if offset <= 0xFF:
            code += bytes([0x60, offset])
        else:
            code += bytes([0x61]) + offset.to_bytes(2, "big")
        code += bytes([0x60, 0x00, 0x39])  # PUSH1 0, CODECOPY
        if rlen <= 0xFF:
            code += bytes([0x60, rlen])
        else:
            code += bytes([0x61]) + rlen.to_bytes(2, "big")
        code += bytes([0x60, 0x00, 0xf3])  # PUSH1 0, RETURN
        return code

    init1 = build(0)
    init_len = len(init1)
    init2 = build(init_len)
    assert len(init2) == init_len, f"Init code length changed: {len(init2)} vs {init_len}"
    return (init2 + runtime).hex()


# ─── Proxy Builder ───────────────────────────────────────────────────────────

# ERC-1967 storage slots
IMPL_SLOT = "360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
ADMIN_SLOT = "b53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"


def build_proxy_runtime() -> bytes:
    """Build minimal proxy runtime bytecode (DELEGATECALL fallback)."""
    code = bytearray()
    # calldatacopy(0, 0, calldatasize)
    code += bytes([0x36, 0x60, 0x00, 0x60, 0x00, 0x37])
    # DELEGATECALL(gas, impl, 0, calldatasize, 0, 0)
    code += bytes([0x60, 0x00])          # retSize = 0
    code += bytes([0x60, 0x00])          # retOffset = 0
    code += bytes([0x36])                # inSize = calldatasize
    code += bytes([0x60, 0x00])          # inOffset = 0
    code += bytes([0x7f]) + bytes.fromhex(IMPL_SLOT)
    code += bytes([0x54])                # SLOAD -> addr
    code += bytes([0x5a])                # GAS
    code += bytes([0xf4])                # DELEGATECALL -> success
    # returndatacopy(0, 0, returndatasize)
    code += bytes([0x3d, 0x60, 0x00, 0x60, 0x00, 0x3e])
    # if !success -> revert
    code += bytes([0x15])                # ISZERO
    pos = len(code)
    return_block = bytes([0x3d, 0x60, 0x00, 0xf3])
    revert_label = pos + 2 + len(return_block)
    code += bytes([0x60, revert_label])  # PUSH1 revert_label
    code += bytes([0x57])                # JUMPI
    code += bytes([0x3d, 0x60, 0x00, 0xf3])  # RETURNDATASIZE, PUSH1 0, RETURN
    code += bytes([0x5b])                # JUMPDEST
    code += bytes([0x3d, 0x60, 0x00, 0xfd])  # RETURNDATASIZE, PUSH1 0, REVERT
    return bytes(code)


def build_proxy_init(impl_addr: str, admin_addr: str,
                     init_data_hex: str = "") -> str:
    """Build proxy init code that stores impl/admin in ERC-1967 slots,
    optionally delegatecalls init data, and returns proxy runtime."""
    impl_clean = impl_addr.removeprefix("0x").lower().zfill(40)
    admin_clean = admin_addr.removeprefix("0x").lower().zfill(40)

    init = bytearray()

    # Store implementation in ERC-1967 slot
    init += bytes([0x73]) + bytes.fromhex(impl_clean)
    init += bytes([0x7f]) + bytes.fromhex(IMPL_SLOT)
    init += bytes([0x55])

    # Store admin in ERC-1967 slot
    init += bytes([0x73]) + bytes.fromhex(admin_clean)
    init += bytes([0x7f]) + bytes.fromhex(ADMIN_SLOT)
    init += bytes([0x55])

    # If init data provided, delegatecall to impl with it
    if init_data_hex:
        init_data = bytes.fromhex(init_data_hex)
        dlen = len(init_data)
        for i in range(0, dlen, 32):
            chunk = init_data[i:i + 32].ljust(32, b"\x00")
            init += bytes([0x7f]) + chunk
            init += bytes([0x60, i])
            init += bytes([0x52])  # MSTORE
        init += bytes([0x60, 0x00])  # retSize
        init += bytes([0x60, 0x00])  # retOffset
        if dlen <= 0xFF:
            init += bytes([0x60, dlen])
        else:
            init += bytes([0x61]) + dlen.to_bytes(2, "big")
        init += bytes([0x60, 0x00])  # inOffset
        init += bytes([0x73]) + bytes.fromhex(impl_clean)
        init += bytes([0x5a])        # GAS
        init += bytes([0xf4])        # DELEGATECALL
        init += bytes([0x50])        # POP result

    # Return proxy runtime
    runtime = build_proxy_runtime()
    rlen = len(runtime)

    # Build tail: CODECOPY + RETURN
    def build_tail(offset: int) -> bytearray:
        t = bytearray()
        if rlen <= 0xFF:
            t += bytes([0x60, rlen])
        else:
            t += bytes([0x61]) + rlen.to_bytes(2, "big")
        if offset <= 0xFF:
            t += bytes([0x60, offset])
        else:
            t += bytes([0x61]) + offset.to_bytes(2, "big")
        t += bytes([0x60, 0x00, 0x39])  # PUSH1 0, CODECOPY
        if rlen <= 0xFF:
            t += bytes([0x60, rlen])
        else:
            t += bytes([0x61]) + rlen.to_bytes(2, "big")
        t += bytes([0x60, 0x00, 0xf3])  # PUSH1 0, RETURN
        return t

    # Two-pass to get correct offset
    tail1 = build_tail(0)
    offset1 = len(init) + len(tail1)
    tail2 = build_tail(offset1)
    offset2 = len(init) + len(tail2)
    if offset2 != offset1:
        tail2 = build_tail(offset2)

    return (bytes(init) + bytes(tail2) + runtime).hex()


# ─── Registry Management ─────────────────────────────────────────────────────

def load_registry() -> Dict[str, Any]:
    """Load existing contract registry."""
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return {}


def save_registry(registry: Dict[str, Any]) -> None:
    """Save contract registry atomically."""
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(registry, indent=2))
    tmp.rename(REGISTRY_PATH)
    logger.info(f"Registry updated: {REGISTRY_PATH} ({len(registry)} contracts)")


def is_deployed(registry: Dict[str, Any], name: str) -> bool:
    """Check if a contract is already deployed in the registry."""
    entry = registry.get(name, {})
    return bool(entry.get("proxy") or entry.get("address"))


def get_address(registry: Dict[str, Any], name: str) -> str:
    """Get the proxy address of a deployed contract."""
    entry = registry.get(name, {})
    return entry.get("proxy") or entry.get("address") or ""


# ─── QUSD Deployer ───────────────────────────────────────────────────────────

class QUSDDeployer:
    """Deploys the 8 QUSD contracts in dependency order."""

    def __init__(self, rpc: RPCClient, registry: Dict[str, Any],
                 proxy_admin: str, dry_run: bool = False):
        self.rpc = rpc
        self.registry = registry
        self.proxy_admin = proxy_admin
        self.dry_run = dry_run
        self.deployed_this_run: List[str] = []

    def deploy_impl(self, name: str) -> str:
        """Deploy an implementation contract (no proxy)."""
        if self.dry_run:
            fake = hashlib.sha256(name.encode()).hexdigest()[:40]
            logger.info(f"  [DRY RUN] Would deploy impl: {name} -> 0x{fake}")
            return f"0x{fake}"
        init_code = make_init_code()
        addr = self.rpc.deploy_bytecode(init_code)
        if not addr:
            raise RuntimeError(f"Failed to deploy implementation: {name}")
        logger.info(f"  Impl deployed: {name} -> {addr}")
        return addr

    def deploy_with_proxy(self, name: str, init_data_hex: str = "") -> str:
        """Deploy implementation + proxy, return proxy address."""
        if is_deployed(self.registry, name):
            addr = get_address(self.registry, name)
            logger.info(f"  SKIP (already deployed): {name} -> {addr}")
            return addr

        if self.dry_run:
            fake = hashlib.sha256(name.encode()).hexdigest()[:40]
            logger.info(f"  [DRY RUN] Would deploy: {name} -> 0x{fake}")
            self.registry[name] = {"proxy": f"0x{fake}", "implementation": f"0x{fake}_impl"}
            return f"0x{fake}"

        # Deploy implementation
        impl_addr = self.deploy_impl(name)

        # Deploy proxy
        proxy_code = build_proxy_init(impl_addr, self.proxy_admin, init_data_hex)
        proxy_addr = self.rpc.deploy_bytecode(proxy_code)
        if not proxy_addr:
            raise RuntimeError(f"Failed to deploy proxy: {name}")

        self.registry[name] = {
            "proxy": proxy_addr,
            "implementation": impl_addr,
        }
        self.deployed_this_run.append(name)
        logger.info(f"  Proxy deployed: {name} -> {proxy_addr} (impl: {impl_addr})")
        save_registry(self.registry)
        return proxy_addr

    def send_config_tx(self, name: str, to: str, data_hex: str) -> None:
        """Send a configuration transaction (post-deploy linking)."""
        if self.dry_run:
            logger.info(f"  [DRY RUN] Would send config tx: {name} -> {to[:16]}...")
            return
        tx_hash = self.rpc.send_tx(to, data_hex)
        logger.info(f"  Config tx sent: {name} -> {tx_hash}")

    def _init_oracle_feeders(self, oracle_addr: str) -> None:
        """Register default oracle feeders and submit initial price.

        Called automatically after QUSDOracle deployment.
        Registers up to 3 feeders (node operator + 2 from .env) and submits
        an initial QBC/USD price so the oracle is immediately usable.
        """
        logger.info("")
        logger.info("[Post-deploy] Initializing oracle feeders...")

        # Resolve feeders: deployer (always) + optional ORACLE_FEEDER_2/3
        feeders: List[str] = [self.rpc.deployer]
        feeder2 = os.getenv("ORACLE_FEEDER_2", "").strip()
        if feeder2:
            feeders.append(feeder2)
        feeder3 = os.getenv("ORACLE_FEEDER_3", "").strip()
        if feeder3:
            feeders.append(feeder3)

        # Step 1: Register each feeder via addFeeder(address)
        for i, feeder in enumerate(feeders, 1):
            data_hex = (
                function_selector("addFeeder(address)")
                + encode_address(feeder)
            ).hex()
            self.send_config_tx(f"QUSDOracle.addFeeder[{i}]", oracle_addr, data_hex)

        # Step 2: Submit initial price from deployer (who is feeder #1)
        initial_price = int(os.getenv("ORACLE_INITIAL_PRICE", "10000000"))  # $0.10 @ 8 dec
        data_hex = (
            function_selector("submitPrice(uint256)")
            + encode_uint256(initial_price)
        ).hex()
        self.send_config_tx(
            f"QUSDOracle.submitPrice({initial_price})",
            oracle_addr,
            data_hex,
        )

        # Step 3: Submit initial peg deviation (0 = at peg)
        data_hex = (
            function_selector("submitPegDeviation(int256)")
            + encode_uint256(0)  # 0 bps, positive int, same encoding
        ).hex()
        self.send_config_tx("QUSDOracle.submitPegDeviation(0)", oracle_addr, data_hex)

        logger.info(f"  Oracle initialized: {len(feeders)} feeders, price={initial_price}")

    def deploy_all(self) -> None:
        """Deploy all 8 QUSD contracts in dependency order."""
        logger.info("=" * 60)
        logger.info("QUSD STABLECOIN DEPLOYMENT")
        logger.info("=" * 60)

        if not self.proxy_admin:
            raise RuntimeError(
                "ProxyAdmin not found in registry. "
                "Run scripts/deploy/deploy_contracts.py first to deploy ProxyAdmin."
            )
        logger.info(f"ProxyAdmin: {self.proxy_admin}")
        logger.info(f"Deployer: {self.rpc.deployer}")
        logger.info("")

        # ── Step 1: QUSDOracle (standalone) ────────────────────────────
        logger.info("[1/8] QUSDOracle — multi-source price feed")
        init_data = (
            function_selector("initialize(uint256)")
            + encode_uint256(1000)  # maxAge = 1000 blocks
        ).hex()
        oracle_addr = self.deploy_with_proxy("QUSDOracle", init_data)

        # ── Step 2: QUSDGovernance (deployed without init, linked later) ──
        logger.info("[2/8] QUSDGovernance — reserve governance")
        # Deployed without init data; initialize after QUSD exists
        governance_addr = self.deploy_with_proxy("QUSDGovernance")

        # ── Step 3: QUSDReserve (needs governance + oracle) ────────────
        logger.info("[3/8] QUSDReserve — multi-asset reserve pool")
        init_data = (
            function_selector("initialize(address,address)")
            + encode_address(governance_addr)
            + encode_address(oracle_addr)
        ).hex()
        reserve_addr = self.deploy_with_proxy("QUSDReserve", init_data)

        # ── Step 4: QUSD (needs reserve address) ──────────────────────
        logger.info("[4/8] QUSD — core stablecoin token (3.3B initial mint)")
        init_data = (
            function_selector("initialize(address)")
            + encode_address(reserve_addr)
        ).hex()
        qusd_addr = self.deploy_with_proxy("QUSD", init_data)

        # ── Step 5: QUSDDebtLedger (needs QUSD + reserve) ─────────────
        logger.info("[5/8] QUSDDebtLedger — fractional payback tracking")
        init_data = (
            function_selector("initialize(address,address)")
            + encode_address(qusd_addr)
            + encode_address(reserve_addr)
        ).hex()
        debt_addr = self.deploy_with_proxy("QUSDDebtLedger", init_data)

        # ── Step 6: QUSDStabilizer (needs governance + oracle + QUSD + QBC) ─
        logger.info("[6/8] QUSDStabilizer — peg maintenance ($0.99-$1.01)")
        # QBC20 token must be deployed before this step (via deploy_contracts.py)
        qbc_token_addr = get_address(self.registry, "QBC20")
        if not qbc_token_addr:
            logger.warning("QBC20 not found in registry — using zero address for QBC token")
            qbc_token_addr = "0x" + "0" * 40
        init_data = (
            function_selector("initialize(address,address,address,address)")
            + encode_address(governance_addr)
            + encode_address(oracle_addr)
            + encode_address(qusd_addr)
            + encode_address(qbc_token_addr)
        ).hex()
        stabilizer_addr = self.deploy_with_proxy("QUSDStabilizer", init_data)

        # ── Step 7: QUSDAllocation (needs QUSD) ───────────────────────
        logger.info("[7/8] QUSDAllocation — vesting & distribution")
        init_data = (
            function_selector("initializeBase(address)")
            + encode_address(qusd_addr)
        ).hex()
        allocation_addr = self.deploy_with_proxy("QUSDAllocation", init_data)

        # ── Step 8: wQUSD (needs QUSD + bridge operator) ──────────────
        logger.info("[8/8] wQUSD — wrapped QUSD for cross-chain bridging")
        # Bridge operator defaults to deployer address (can be updated later)
        init_data = (
            function_selector("initialize(address,address)")
            + encode_address(qusd_addr)
            + encode_address(self.rpc.deployer)
        ).hex()
        wqusd_addr = self.deploy_with_proxy("wQUSD", init_data)

        # ── Post-deploy: Link QUSDGovernance to QUSD token ────────────
        logger.info("")
        logger.info("[Post-deploy] Linking contracts...")

        if "QUSDGovernance" in self.deployed_this_run:
            # Initialize governance with QUSD token address
            config_data = (
                function_selector("initialize(address,uint256,uint256)")
                + encode_address(qusd_addr)
                + encode_uint256(1_000_000 * 10**8)  # minProposalBalance = 1M QUSD
                + encode_uint256(5)                    # emergencyThreshold = 5 signers
            ).hex()
            self.send_config_tx("QUSDGovernance.initialize", governance_addr, config_data)

        # Link reserve to debt ledger
        if "QUSDReserve" in self.deployed_this_run:
            config_data = (
                function_selector("setDebtLedger(address)")
                + encode_address(debt_addr)
            ).hex()
            self.send_config_tx("QUSDReserve.setDebtLedger", reserve_addr, config_data)

        # Initialize oracle feeders (if oracle was deployed this run)
        if "QUSDOracle" in self.deployed_this_run:
            self._init_oracle_feeders(oracle_addr)

        # ── Summary ───────────────────────────────────────────────────
        logger.info("")
        logger.info("=" * 60)
        logger.info("QUSD DEPLOYMENT SUMMARY")
        logger.info("=" * 60)
        for name in QUSD_CONTRACTS:
            addr = get_address(self.registry, name)
            status = "NEW" if name in self.deployed_this_run else "EXISTING"
            logger.info(f"  [{status}] {name}: {addr}")
        logger.info(f"\nTotal deployed this run: {len(self.deployed_this_run)}")
        logger.info(f"Registry: {REGISTRY_PATH}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy QUSD stablecoin contracts to Qubitcoin"
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
        help="Print deployment plan without executing"
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

    logger.info(f"Deployer: {deployer}")
    logger.info(f"RPC URL:  {args.rpc_url}")
    logger.info(f"Dry run:  {args.dry_run}")
    logger.info("")

    # ── Load existing registry ────────────────────────────────────────
    registry = load_registry()
    logger.info(f"Registry loaded: {len(registry)} existing contracts")

    # ── Check ProxyAdmin exists ───────────────────────────────────────
    proxy_admin = get_address(registry, "ProxyAdmin")
    if not proxy_admin and not args.dry_run:
        logger.error(
            "ProxyAdmin not found in contract_registry.json.\n"
            "Deploy the full contract suite first:\n"
            "  python3 scripts/deploy/deploy_contracts.py"
        )
        sys.exit(1)

    # ── Create RPC client ─────────────────────────────────────────────
    rpc = RPCClient(args.rpc_url, deployer)

    if not args.dry_run:
        if not rpc.health_check():
            logger.error(f"Node not reachable at {args.rpc_url}")
            sys.exit(1)
        logger.info("Node health check passed")
        rpc.nonce = rpc.get_nonce()
        logger.info(f"Deployer nonce: {rpc.nonce}")

    # ── Deploy ────────────────────────────────────────────────────────
    deployer_obj = QUSDDeployer(
        rpc=rpc,
        registry=registry,
        proxy_admin=proxy_admin or "0x" + "0" * 40,
        dry_run=args.dry_run,
    )

    try:
        deployer_obj.deploy_all()
    except Exception as e:
        logger.error(f"Deployment failed: {e}", exc_info=True)
        save_registry(deployer_obj.registry)
        logger.info("Partial registry saved.")
        sys.exit(1)


if __name__ == "__main__":
    main()
