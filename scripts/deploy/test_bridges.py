#!/usr/bin/env python3
"""
Bridge Test Script for Qubitcoin

Comprehensive verification of wQBC and wQUSD deployments on all chains:
1. Check deployer gas balance
2. Check wQBC balance = 100K
3. Check wQUSD balance = 100K
4. Test transfer() of 1 wQBC to test address
5. Verify token metadata (name, symbol, decimals)
6. Verify bridge operator / owner is correctly set
7. Report pass/fail per chain

Usage:
    python3 scripts/deploy/test_bridges.py
    python3 scripts/deploy/test_bridges.py --chains polygon,arbitrum
    python3 scripts/deploy/test_bridges.py --skip-transfer  # skip actual transfer test

Prerequisites:
    pip install web3
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from qubitcoin.utils.logger import get_logger

logger = get_logger("test_bridges")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = PROJECT_ROOT / "contract_registry.json"

TOKEN_DECIMALS = 8
EXPECTED_BALANCE = 100_000 * (10 ** TOKEN_DECIMALS)

# Test address for transfer test (burns to a known safe address)
TEST_RECIPIENT = "0x000000000000000000000000000000000000dEaD"

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


def eth_call(w3: Any, to: str, data: bytes) -> bytes:
    """Execute eth_call and return raw result."""
    result = w3.eth.call({
        "to": w3.to_checksum_address(to),
        "data": "0x" + data.hex(),
    })
    return result


def read_string(w3: Any, contract: str, func_sig: str) -> str:
    """Read a string return value from a contract."""
    sel = function_selector(func_sig)
    result = eth_call(w3, contract, sel)
    if len(result) < 64:
        return ""
    # ABI-encoded string: offset(32) + length(32) + data
    offset = int(result[:32].hex(), 16)
    length = int(result[offset:offset + 32].hex(), 16)
    return result[offset + 32:offset + 32 + length].decode("utf-8", errors="replace")


def read_uint8(w3: Any, contract: str, func_sig: str) -> int:
    """Read a uint8 return value."""
    sel = function_selector(func_sig)
    result = eth_call(w3, contract, sel)
    return int(result.hex(), 16) if result else 0


def read_uint256(w3: Any, contract: str, func_sig: str) -> int:
    """Read a uint256 return value."""
    sel = function_selector(func_sig)
    result = eth_call(w3, contract, sel)
    return int(result.hex(), 16) if result else 0


def read_address(w3: Any, contract: str, func_sig: str) -> str:
    """Read an address return value."""
    sel = function_selector(func_sig)
    result = eth_call(w3, contract, sel)
    return "0x" + result[-20:].hex() if result else ""


def read_balance_of(w3: Any, contract: str, holder: str) -> int:
    """Read balanceOf(address)."""
    sel = function_selector("balanceOf(address)")
    data = sel + encode_address(holder)
    result = eth_call(w3, contract, data)
    return int(result.hex(), 16) if result else 0


class TestResult:
    """Track test pass/fail results."""

    def __init__(self, chain: str, token: str) -> None:
        self.chain = chain
        self.token = token
        self.checks: List[Dict[str, Any]] = []

    def check(self, name: str, passed: bool, detail: str = "") -> bool:
        status = "PASS" if passed else "FAIL"
        self.checks.append({"name": name, "passed": passed, "detail": detail})
        icon = "+" if passed else "X"
        msg = f"  [{icon}] {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)
        return passed

    @property
    def passed(self) -> bool:
        return all(c["passed"] for c in self.checks)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c["passed"])

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if not c["passed"])


def test_token(
    w3: Any,
    account: Any,
    chain: str,
    token_name: str,
    token_addr: str,
    expected_name: str,
    expected_symbol: str,
    chain_cfg: Dict[str, Any],
    skip_transfer: bool,
) -> TestResult:
    """Run all tests for a single token on a chain."""
    result = TestResult(chain, token_name)

    # 1. Token metadata
    try:
        name = read_string(w3, token_addr, "name()")
        result.check("name()", name == expected_name, f"'{name}'")
    except Exception as e:
        result.check("name()", False, str(e))

    try:
        symbol = read_string(w3, token_addr, "symbol()")
        result.check("symbol()", symbol == expected_symbol, f"'{symbol}'")
    except Exception as e:
        result.check("symbol()", False, str(e))

    try:
        decimals = read_uint8(w3, token_addr, "decimals()")
        result.check("decimals()", decimals == TOKEN_DECIMALS, str(decimals))
    except Exception as e:
        result.check("decimals()", False, str(e))

    # 2. Total supply
    try:
        supply = read_uint256(w3, token_addr, "totalSupply()")
        human = supply / 10**TOKEN_DECIMALS
        result.check("totalSupply > 0", supply > 0, f"{human:,.0f}")
    except Exception as e:
        result.check("totalSupply", False, str(e))

    # 3. Deployer balance
    try:
        balance = read_balance_of(w3, token_addr, account.address)
        human = balance / 10**TOKEN_DECIMALS
        result.check(
            "deployer balance >= 100K",
            balance >= EXPECTED_BALANCE,
            f"{human:,.0f}",
        )
    except Exception as e:
        result.check("deployer balance", False, str(e))

    # 4. Owner / bridge operator
    try:
        if token_name == "wQBC":
            owner = read_address(w3, token_addr, "owner()")
            result.check(
                "owner == deployer",
                owner.lower() == account.address.lower(),
                owner,
            )
            bridge = read_address(w3, token_addr, "bridge()")
            result.check(
                "bridge == deployer",
                bridge.lower() == account.address.lower(),
                bridge,
            )
        else:
            owner = read_address(w3, token_addr, "owner()")
            result.check(
                "owner == deployer",
                owner.lower() == account.address.lower(),
                owner,
            )
            bridge_op = read_address(w3, token_addr, "bridgeOperator()")
            result.check(
                "bridgeOperator == deployer",
                bridge_op.lower() == account.address.lower(),
                bridge_op,
            )
    except Exception as e:
        result.check("ownership check", False, str(e))

    # 5. Not paused
    try:
        paused_result = eth_call(w3, token_addr, function_selector("paused()"))
        is_paused = int(paused_result.hex(), 16) != 0
        result.check("not paused", not is_paused, f"paused={is_paused}")
    except Exception as e:
        result.check("pause check", False, str(e))

    # 6. Transfer test (1 token to dead address)
    if not skip_transfer and balance >= 10**TOKEN_DECIMALS:
        try:
            transfer_amount = 1 * 10**TOKEN_DECIMALS  # 1 token
            sel = function_selector("transfer(address,uint256)")
            tx_data = sel + encode_address(TEST_RECIPIENT) + encode_uint256(transfer_amount)

            nonce = w3.eth.get_transaction_count(account.address)
            chain_id = chain_cfg["chainId"]
            gas_strategy = chain_cfg["gasStrategy"]

            tx: Dict[str, Any] = {
                "from": account.address,
                "to": w3.to_checksum_address(token_addr),
                "nonce": nonce,
                "gas": 100_000,
                "chainId": chain_id,
                "data": "0x" + tx_data.hex(),
            }

            if gas_strategy == "eip1559":
                latest = w3.eth.get_block("latest")
                base_fee = latest.get("baseFeePerGas", 0)
                try:
                    max_priority = w3.eth.max_priority_fee
                    if chain_cfg["chainId"] in (1, 56, 137, 43114):
                        max_priority = max(max_priority, w3.to_wei(2, "gwei"))
                except Exception:
                    max_priority = w3.to_wei(30, "gwei")
                tx["maxFeePerGas"] = base_fee * 2 + max_priority
                tx["maxPriorityFeePerGas"] = max_priority
            else:
                tx["gasPrice"] = w3.eth.gas_price

            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            result.check(
                "transfer(1 token)",
                receipt["status"] == 1,
                f"tx={tx_hash.hex()[:16]}... gas={receipt['gasUsed']:,}",
            )
        except Exception as e:
            result.check("transfer test", False, str(e))
    elif skip_transfer:
        print("  [~] transfer test — skipped")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test wQBC/wQUSD bridge deployments on all chains",
    )
    parser.add_argument(
        "--chains", type=str, default="",
        help="Comma-separated chains (default: all deployed)",
    )
    parser.add_argument(
        "--skip-transfer", action="store_true",
        help="Skip the actual token transfer test",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  BRIDGE DEPLOYMENT TESTS")
    print("  Testing wQBC + wQUSD on all deployed chains")
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

    all_results: List[TestResult] = []
    total_pass = 0
    total_fail = 0

    for chain in chains:
        chain_cfg = EVM_CHAINS.get(chain)
        if not chain_cfg:
            continue

        wqbc_addr = registry.get(f"external:{chain}:wQBC", {}).get("address", "")
        wqusd_addr = registry.get(f"external:{chain}:wQUSD", {}).get("address", "")

        if not wqbc_addr or not wqusd_addr:
            logger.warning(f"[{chain}] Not fully deployed, skipping")
            continue

        rpc_key = f"{chain.upper()}_RPC_URL"
        rpc_url = env_vars.get(rpc_key, os.getenv(rpc_key, ""))
        if not rpc_url:
            logger.error(f"[{chain}] No RPC URL, skipping")
            continue

        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(rpc_url))

        if chain in ("bsc", "polygon"):
            try:
                from web3.middleware import ExtraDataToPOAMiddleware
                w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            except ImportError:
                pass

        if not w3.is_connected():
            logger.error(f"[{chain}] Cannot connect to RPC")
            continue

        account = w3.eth.account.from_key(private_key)

        # Native gas check
        native_bal = w3.eth.get_balance(account.address)
        native_eth = native_bal / 10**18

        print(f"\n{'=' * 50}")
        print(f"  {chain.upper()} — Gas: {native_eth:.6f}")
        print(f"  wQBC:  {wqbc_addr}")
        print(f"  wQUSD: {wqusd_addr}")
        print(f"{'=' * 50}")

        # Test wQBC
        print(f"\n  --- wQBC ---")
        r1 = test_token(
            w3, account, chain, "wQBC", wqbc_addr,
            "Wrapped Qubitcoin", "wQBC", chain_cfg, args.skip_transfer,
        )
        all_results.append(r1)
        total_pass += r1.pass_count
        total_fail += r1.fail_count

        # Test wQUSD
        print(f"\n  --- wQUSD ---")
        r2 = test_token(
            w3, account, chain, "wQUSD", wqusd_addr,
            "Wrapped QUSD", "wQUSD", chain_cfg, args.skip_transfer,
        )
        all_results.append(r2)
        total_pass += r2.pass_count
        total_fail += r2.fail_count

    # Final summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)

    for r in all_results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  {r.chain:12s} {r.token:6s}: {status} ({r.pass_count}/{r.pass_count + r.fail_count})")

    print(f"\n  Total: {total_pass} passed, {total_fail} failed")
    overall = "ALL PASSED" if total_fail == 0 else f"{total_fail} FAILURES"
    print(f"  Result: {overall}")
    print("=" * 60)

    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
