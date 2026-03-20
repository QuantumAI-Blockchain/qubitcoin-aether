#!/usr/bin/env python3
"""
Create Uniswap V3 Liquidity Pools for wQBC/wQUSD

Creates wQBC/wQUSD pools on Uniswap V3 (0.3% fee tier, 1:1 price)
and adds 100K liquidity on each chain.

Uniswap V3 canonical addresses (same on all chains):
  Factory:          0x1F98431c8aD98523631AE4a59f267346ea31F984
  PositionManager:  0xC36442b4a4522E871399CD717aBDD847Ab11FE88

Usage:
    python3 scripts/deploy/create_pools.py
    python3 scripts/deploy/create_pools.py --chains polygon,arbitrum
    python3 scripts/deploy/create_pools.py --amount 50000
    python3 scripts/deploy/create_pools.py --dry-run

Prerequisites:
    pip install web3
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from qubitcoin.utils.logger import get_logger

logger = get_logger("create_pools")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = PROJECT_ROOT / "contract_registry.json"

TOKEN_DECIMALS = 8

# Uniswap V3 canonical addresses (same on all supported chains)
UNISWAP_V3_FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
POSITION_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"

# Fee tier: 3000 = 0.3%, tick spacing = 60
FEE = 3000
TICK_SPACING = 60
# Full-range ticks (nearest multiples of 60 to min/max tick ±887272)
TICK_LOWER = -887220
TICK_UPPER = 887220

# sqrtPriceX96 for 1:1 price = 2^96
SQRT_PRICE_X96_1_TO_1 = 79228162514264337593543950336

EVM_CHAINS: Dict[str, Dict[str, Any]] = {
    "polygon": {"chainId": 137, "gasStrategy": "eip1559"},
    "avalanche": {
        "chainId": 43114,
        "gasStrategy": "eip1559",
        # Avalanche uses a different Uniswap V3 deployment
        "factory": "0x740b1c1de25031C31FF4fC9A62f554A55cdC1baD",
        "positionManager": "0x655C406EBFa14EE2006250925e54ec43AD184f8B",
    },
    "arbitrum": {"chainId": 42161, "gasStrategy": "eip1559"},
    "optimism": {"chainId": 10, "gasStrategy": "eip1559"},
    "base": {
        "chainId": 8453,
        "gasStrategy": "eip1559",
        # Base uses a different Uniswap V3 deployment
        "factory": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
        "positionManager": "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1",
    },
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
            raise ImportError("Need pysha3 or pycryptodome for keccak256")


def selector(sig: str) -> bytes:
    return keccak256(sig.encode())[:4]


def encode_address(addr: str) -> bytes:
    return bytes.fromhex(addr.removeprefix("0x").lower().zfill(64))


def encode_uint256(val: int) -> bytes:
    return val.to_bytes(32, "big")


def encode_uint24(val: int) -> bytes:
    return val.to_bytes(32, "big")


def encode_int24(val: int) -> bytes:
    if val < 0:
        val = (1 << 256) + val
    return val.to_bytes(32, "big")


def encode_uint160(val: int) -> bytes:
    return val.to_bytes(32, "big")


def sort_tokens(a: str, b: str) -> Tuple[str, str]:
    """Sort token addresses (Uniswap requires token0 < token1)."""
    if int(a, 16) < int(b, 16):
        return a, b
    return b, a


def build_gas_params(w3: Any, chain_id: int) -> Dict[str, Any]:
    """Build gas price parameters."""
    latest = w3.eth.get_block("latest")
    base_fee = latest.get("baseFeePerGas", 0)
    try:
        max_priority = w3.eth.max_priority_fee
        if chain_id in (137, 43114):
            max_priority = max(max_priority, w3.to_wei(2, "gwei"))
    except Exception:
        max_priority = w3.to_wei(30, "gwei")
    return {
        "maxFeePerGas": base_fee * 2 + max_priority,
        "maxPriorityFeePerGas": max_priority,
    }


def send_tx(
    w3: Any,
    account: Any,
    to: str,
    data: bytes,
    chain_name: str,
    chain_id: int,
    gas_limit: int = 500_000,
) -> Optional[str]:
    """Build, sign, and send a transaction."""
    nonce = w3.eth.get_transaction_count(account.address, "pending")
    gas_params = build_gas_params(w3, chain_id)

    tx: Dict[str, Any] = {
        "from": account.address,
        "to": w3.to_checksum_address(to),
        "nonce": nonce,
        "gas": gas_limit,
        "chainId": chain_id,
        "data": "0x" + data.hex(),
        **gas_params,
    }

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


def eth_call(w3: Any, to: str, data: bytes) -> bytes:
    return w3.eth.call({
        "to": w3.to_checksum_address(to),
        "data": "0x" + data.hex(),
    })


def get_pool_on(w3: Any, factory: str, token0: str, token1: str, fee: int) -> str:
    """Check if Uniswap V3 pool exists. Returns pool address or zero address."""
    data = (
        selector("getPool(address,address,uint24)")
        + encode_address(token0)
        + encode_address(token1)
        + encode_uint24(fee)
    )
    result = eth_call(w3, factory, data)
    return "0x" + result.hex()[-40:]


def check_allowance(w3: Any, token: str, owner: str, spender: str) -> int:
    """Check ERC-20 allowance."""
    data = (
        selector("allowance(address,address)")
        + encode_address(owner)
        + encode_address(spender)
    )
    result = eth_call(w3, token, data)
    return int(result.hex(), 16) if result else 0


def check_balance(w3: Any, token: str, owner: str) -> int:
    """Check ERC-20 balance."""
    data = selector("balanceOf(address)") + encode_address(owner)
    result = eth_call(w3, token, data)
    return int(result.hex(), 16) if result else 0


def approve_token(
    w3: Any, account: Any, token: str, spender: str,
    amount: int, chain_name: str, chain_id: int,
) -> bool:
    """Approve ERC-20 spending."""
    current = check_allowance(w3, token, account.address, spender)
    if current >= amount:
        logger.info(f"[{chain_name}] Already approved (allowance={current / 10**TOKEN_DECIMALS:,.0f})")
        return True

    data = (
        selector("approve(address,uint256)")
        + encode_address(spender)
        + encode_uint256(amount)
    )
    tx = send_tx(w3, account, token, data, chain_name, chain_id, gas_limit=100_000)
    return tx is not None


def create_and_initialize_pool(
    w3: Any, account: Any, token0: str, token1: str,
    fee: int, sqrt_price: int, chain_name: str, chain_id: int,
    pm_addr: str = POSITION_MANAGER,
) -> Optional[str]:
    """Create and initialize a Uniswap V3 pool."""
    # createAndInitializePoolIfNecessary(address,address,uint24,uint160)
    data = (
        selector("createAndInitializePoolIfNecessary(address,address,uint24,uint160)")
        + encode_address(token0)
        + encode_address(token1)
        + encode_uint24(fee)
        + encode_uint160(sqrt_price)
    )
    return send_tx(w3, account, pm_addr, data, chain_name, chain_id, gas_limit=5_000_000)


def mint_position(
    w3: Any, account: Any, token0: str, token1: str,
    fee: int, tick_lower: int, tick_upper: int,
    amount0: int, amount1: int, chain_name: str, chain_id: int,
    pm_addr: str = POSITION_MANAGER,
) -> Optional[str]:
    """Add liquidity by minting a Uniswap V3 position.

    mint((address,address,uint24,int24,int24,uint256,uint256,uint256,uint256,address,uint256))
    """
    # The mint function takes a struct as a tuple — we ABI-encode it as sequential params
    deadline = 2**64  # far future

    data = (
        selector("mint((address,address,uint24,int24,int24,uint256,uint256,uint256,uint256,address,uint256))")
        + encode_address(token0)
        + encode_address(token1)
        + encode_uint24(fee)
        + encode_int24(tick_lower)
        + encode_int24(tick_upper)
        + encode_uint256(amount0)   # amount0Desired
        + encode_uint256(amount1)   # amount1Desired
        + encode_uint256(0)         # amount0Min
        + encode_uint256(0)         # amount1Min
        + encode_address(account.address)  # recipient
        + encode_uint256(deadline)
    )
    return send_tx(w3, account, pm_addr, data, chain_name, chain_id, gas_limit=1_000_000)


def get_pool_liquidity(w3: Any, pool_addr: str) -> int:
    """Read pool liquidity."""
    data = selector("liquidity()")
    result = eth_call(w3, pool_addr, data)
    return int(result.hex(), 16) if result else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Uniswap V3 wQBC/wQUSD pools on deployed chains",
    )
    parser.add_argument(
        "--chains", type=str, default="",
        help="Comma-separated chains (default: polygon,avalanche,arbitrum,optimism,base)",
    )
    parser.add_argument(
        "--amount", type=int, default=100_000,
        help="Amount of each token to add as liquidity (default: 100000)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without sending transactions",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  UNISWAP V3 POOL CREATION")
    print(f"  wQBC/wQUSD · 0.3% fee · 1:1 price · {args.amount:,} liquidity")
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

    if args.chains:
        chains = [c.strip().lower() for c in args.chains.split(",") if c.strip()]
    else:
        chains = list(EVM_CHAINS.keys())

    raw_amount = args.amount * (10 ** TOKEN_DECIMALS)
    results: Dict[str, str] = {}

    for chain in chains:
        chain_cfg = EVM_CHAINS.get(chain)
        if not chain_cfg:
            logger.warning(f"Unknown chain: {chain}")
            continue

        wqbc_addr = registry.get(f"external:{chain}:wQBC", {}).get("address", "")
        wqusd_addr = registry.get(f"external:{chain}:wQUSD", {}).get("address", "")

        if not wqbc_addr or not wqusd_addr:
            logger.warning(f"[{chain}] Tokens not deployed, skipping")
            results[chain] = "not_deployed"
            continue

        rpc_key = f"{chain.upper()}_RPC_URL"
        rpc_url = env_vars.get(rpc_key, os.getenv(rpc_key, ""))
        if not rpc_url:
            logger.error(f"[{chain}] No RPC URL ({rpc_key})")
            results[chain] = "no_rpc"
            continue

        print(f"\n{'=' * 50}")
        print(f"  {chain.upper()}")
        print(f"  wQBC:  {wqbc_addr}")
        print(f"  wQUSD: {wqusd_addr}")
        print(f"{'=' * 50}")

        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(rpc_url))

        if chain in ("polygon",):
            try:
                from web3.middleware import ExtraDataToPOAMiddleware
                w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            except ImportError:
                pass

        if not w3.is_connected():
            logger.error(f"[{chain}] Cannot connect to RPC")
            results[chain] = "rpc_failed"
            continue

        account = w3.eth.account.from_key(private_key)
        chain_id = chain_cfg["chainId"]

        # Use chain-specific or canonical Uniswap V3 addresses
        factory_addr = chain_cfg.get("factory", UNISWAP_V3_FACTORY)
        pm_addr = chain_cfg.get("positionManager", POSITION_MANAGER)

        # Verify Uniswap V3 Factory exists on this chain
        factory_code = w3.eth.get_code(w3.to_checksum_address(factory_addr))
        if len(factory_code) <= 2:
            logger.error(f"[{chain}] Uniswap V3 Factory not found at {factory_addr}")
            results[chain] = "no_uniswap"
            continue

        # Sort tokens (Uniswap requires token0 < token1)
        token0, token1 = sort_tokens(wqbc_addr, wqusd_addr)
        is_wqbc_token0 = token0.lower() == wqbc_addr.lower()
        logger.info(f"[{chain}] token0={token0[:10]}... ({'wQBC' if is_wqbc_token0 else 'wQUSD'})")
        logger.info(f"[{chain}] token1={token1[:10]}... ({'wQUSD' if is_wqbc_token0 else 'wQBC'})")

        # Check if pool already exists
        pool_addr = get_pool_on(w3, factory_addr, token0, token1, FEE)
        zero_addr = "0x" + "0" * 40

        if len(pool_addr) < 42 or pool_addr == zero_addr:
            pool_addr = zero_addr

        if pool_addr != zero_addr:
            liq = get_pool_liquidity(w3, pool_addr)
            if liq > 0:
                logger.info(f"[{chain}] Pool already exists at {pool_addr} with liquidity={liq}")
                results[chain] = f"already_exists ({pool_addr[:10]}...)"
                continue
            else:
                logger.info(f"[{chain}] Pool exists at {pool_addr} but empty — adding liquidity")
        else:
            logger.info(f"[{chain}] No pool found — creating...")

        if args.dry_run:
            logger.info(f"[{chain}] [DRY RUN] Would create pool and add {args.amount:,} liquidity")
            results[chain] = "dry_run"
            continue

        # Check balances
        bal0 = check_balance(w3, token0, account.address)
        bal1 = check_balance(w3, token1, account.address)
        logger.info(f"[{chain}] Balance token0: {bal0 / 10**TOKEN_DECIMALS:,.0f}")
        logger.info(f"[{chain}] Balance token1: {bal1 / 10**TOKEN_DECIMALS:,.0f}")

        if bal0 < raw_amount or bal1 < raw_amount:
            logger.error(f"[{chain}] Insufficient balance for {args.amount:,} liquidity")
            results[chain] = "insufficient_balance"
            continue

        # Step 1: Create and initialize pool if needed
        if pool_addr == zero_addr:
            logger.info(f"[{chain}] Creating pool (1:1 price, 0.3% fee)...")
            # For 1:1 price, sqrtPriceX96 = 2^96 regardless of token order
            # since both tokens have same decimals (8)
            tx = create_and_initialize_pool(
                w3, account, token0, token1, FEE,
                SQRT_PRICE_X96_1_TO_1, chain, chain_id, pm_addr,
            )
            if not tx:
                results[chain] = "pool_creation_failed"
                continue
            time.sleep(3)

            # Verify pool was created
            pool_addr = get_pool_on(w3, factory_addr, token0, token1, FEE)
            if pool_addr == zero_addr:
                logger.error(f"[{chain}] Pool not found after creation tx")
                results[chain] = "pool_not_created"
                continue
            logger.info(f"[{chain}] Pool created at {pool_addr}")

        # Step 2: Approve tokens to PositionManager
        logger.info(f"[{chain}] Approving token0 to PositionManager...")
        if not approve_token(w3, account, token0, pm_addr, raw_amount, chain, chain_id):
            results[chain] = "approve0_failed"
            continue
        time.sleep(2)

        logger.info(f"[{chain}] Approving token1 to PositionManager...")
        if not approve_token(w3, account, token1, pm_addr, raw_amount, chain, chain_id):
            results[chain] = "approve1_failed"
            continue
        time.sleep(2)

        # Step 3: Mint position (add liquidity)
        logger.info(f"[{chain}] Adding {args.amount:,} liquidity (full range)...")
        tx = mint_position(
            w3, account, token0, token1, FEE,
            TICK_LOWER, TICK_UPPER,
            raw_amount, raw_amount,
            chain, chain_id, pm_addr,
        )

        if tx:
            # Verify liquidity
            time.sleep(3)
            liq = get_pool_liquidity(w3, pool_addr)
            logger.info(f"[{chain}] Pool liquidity: {liq}")
            results[chain] = f"created ({pool_addr[:10]}..., tx={tx[:12]}...)"

            # Update registry with pool address
            reg_key = f"external:{chain}:pool:wQBC-wQUSD"
            registry[reg_key] = {
                "address": pool_addr,
                "dex": "Uniswap V3",
                "fee": "0.3%",
                "token0": token0,
                "token1": token1,
                "deployed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        else:
            results[chain] = "mint_failed"

        time.sleep(2)

    # Save updated registry
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2) + "\n")
    logger.info("Registry updated")

    # Summary
    print("\n" + "=" * 60)
    print("  POOL CREATION SUMMARY")
    print("=" * 60)
    for chain, status in results.items():
        print(f"  {chain:12s}: {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
