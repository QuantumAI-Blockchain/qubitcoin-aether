#!/usr/bin/env python3
"""
Create wQBC/WETH (native) Pools + wQUSD/USDC Pools

Creates Uniswap V3 pools pairing wQBC against wrapped native tokens
on all 7 chains, enabling public buying of QBC with common tokens.

Also creates wQUSD/USDC pool on ETH to establish QUSD price.

Pricing:
  - wQBC = $0.25 USD
  - wQUSD = $0.10 USD (10 QUSD per 1 USDC)

Strategy:
  1. Calculate gas budget per chain (keep reserve, wrap rest)
  2. Mint wQBC proportional to native liquidity
  3. Wrap native → WETH/WBNB/WPOL/WAVAX
  4. Create Uniswap V3 pool at correct sqrtPriceX96
  5. Add full-range liquidity
  6. On ETH: swap some ETH → USDC, mint wQUSD, create wQUSD/USDC pool

Usage:
    python3 scripts/deploy/create_native_pools.py
    python3 scripts/deploy/create_native_pools.py --chains ethereum,arbitrum
    python3 scripts/deploy/create_native_pools.py --dry-run
    python3 scripts/deploy/create_native_pools.py --skip-usdc
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from qubitcoin.utils.logger import get_logger

logger = get_logger("create_native_pools")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = PROJECT_ROOT / "contract_registry.json"

TOKEN_DECIMALS = 8       # wQBC and wQUSD
NATIVE_DECIMALS = 18     # WETH, WBNB, WPOL, WAVAX
USDC_DECIMALS = 6        # USDC (except BSC which is 18)

# Pricing targets
QBC_PRICE_USD = 0.25
QUSD_PRICE_USD = 0.10

# Uniswap V3 constants
FEE_3000 = 3000        # 0.3% fee tier
FEE_500 = 500          # 0.05% fee tier (for stablecoin-like pairs)
TICK_SPACING_60 = 60   # for 0.3% fee
TICK_SPACING_10 = 10   # for 0.05% fee
TICK_LOWER_60 = -887220
TICK_UPPER_60 = 887220
TICK_LOWER_10 = -887270
TICK_UPPER_10 = 887270

# Canonical Uniswap V3 addresses
UNISWAP_V3_FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
POSITION_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
SWAP_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"

# Chain configurations
CHAINS: Dict[str, Dict[str, Any]] = {
    "ethereum": {
        "chainId": 1,
        "gasStrategy": "eip1559",
        "rpcKey": "ETH_RPC_URL",
        "nativeSymbol": "ETH",
        "nativePriceUSD": 2000,
        "wrappedNative": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "gasReserve": 0.003,  # Keep 0.003 ETH for gas
        "usdc": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "usdcDecimals": 6,
        "poa": False,
    },
    "bsc": {
        "chainId": 56,
        "gasStrategy": "legacy",
        "rpcKey": "BSC_RPC_URL",
        "nativeSymbol": "BNB",
        "nativePriceUSD": 600,
        "wrappedNative": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "gasReserve": 0.002,
        "usdc": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        "usdcDecimals": 18,  # BSC USDC is 18 decimals
        "factory": "0xdB1d10011AD0Ff90774D0C6Bb92e5C5c8b4461F7",
        "positionManager": "0x7b8A01B39D58278b5DE7e48c8449c9f4F5170613",
        "poa": True,
    },
    "polygon": {
        "chainId": 137,
        "gasStrategy": "eip1559",
        "rpcKey": "POLYGON_RPC_URL",
        "nativeSymbol": "POL",
        "nativePriceUSD": 0.40,
        "wrappedNative": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        "gasReserve": 0.3,
        "poa": True,
    },
    "avalanche": {
        "chainId": 43114,
        "gasStrategy": "eip1559",
        "rpcKey": "AVALANCHE_RPC_URL",
        "nativeSymbol": "AVAX",
        "nativePriceUSD": 25,
        "wrappedNative": "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7",
        "gasReserve": 0.03,
        "factory": "0x740b1c1de25031C31FF4fC9A62f554A55cdC1baD",
        "positionManager": "0x655C406EBFa14EE2006250925e54ec43AD184f8B",
        "poa": False,
    },
    "arbitrum": {
        "chainId": 42161,
        "gasStrategy": "eip1559",
        "rpcKey": "ARBITRUM_RPC_URL",
        "nativeSymbol": "ETH",
        "nativePriceUSD": 2000,
        "wrappedNative": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "gasReserve": 0.001,
        "poa": False,
    },
    "optimism": {
        "chainId": 10,
        "gasStrategy": "eip1559",
        "rpcKey": "OPTIMISM_RPC_URL",
        "nativeSymbol": "ETH",
        "nativePriceUSD": 2000,
        "wrappedNative": "0x4200000000000000000000000000000000000006",
        "gasReserve": 0.001,
        "poa": False,
    },
    "base": {
        "chainId": 8453,
        "gasStrategy": "eip1559",
        "rpcKey": "BASE_RPC_URL",
        "nativeSymbol": "ETH",
        "nativePriceUSD": 2000,
        "wrappedNative": "0x4200000000000000000000000000000000000006",
        "gasReserve": 0.0005,
        "factory": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
        "positionManager": "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1",
        "poa": False,
    },
}


# ── ABI Encoding Helpers ──

def keccak256(data: bytes) -> bytes:
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


def encode_bytes32(val: bytes) -> bytes:
    return val.ljust(32, b"\x00")[:32]


def sort_tokens(a: str, b: str) -> Tuple[str, str]:
    if int(a, 16) < int(b, 16):
        return a, b
    return b, a


# ── Price Calculation ──

def calc_sqrt_price_x96(
    token0_decimals: int,
    token1_decimals: int,
    price_token0_usd: float,
    price_token1_usd: float,
) -> int:
    """
    Calculate sqrtPriceX96 for Uniswap V3.

    In Uniswap V3, price = token1_amount / token0_amount (in raw units).
    For equal USD value:
      amount_token0 * price_token0_usd = amount_token1 * price_token1_usd
      price_raw = amount_token1 / amount_token0
               = (price_token0_usd / price_token1_usd) * (10^token1_decimals / 10^token0_decimals)

    Wait, let me think again more carefully.

    If I have 1 unit of token0 (= 10^(-token0_decimals) tokens), its USD value is:
      value0 = 10^(-token0_decimals) * price_token0_usd

    For equal value in token1:
      amount_token1_raw = value0 / (10^(-token1_decimals) * price_token1_usd)
                        = (price_token0_usd * 10^token1_decimals) / (price_token1_usd * 10^token0_decimals)

    So price_raw = amount_token1_raw / 1 (per 1 raw unit of token0)
                 = (price_token0_usd / price_token1_usd) * 10^(token1_decimals - token0_decimals)
    """
    decimal_adjustment = 10 ** (token1_decimals - token0_decimals)
    price_raw = (price_token0_usd / price_token1_usd) * decimal_adjustment

    sqrt_price = math.sqrt(price_raw)
    sqrt_price_x96 = int(sqrt_price * (2 ** 96))

    return sqrt_price_x96


# ── Transaction Helpers ──

def build_gas_params(w3: Any, chain_id: int, gas_strategy: str) -> Dict[str, Any]:
    if gas_strategy == "legacy":
        return {"gasPrice": w3.eth.gas_price}

    latest = w3.eth.get_block("latest")
    base_fee = latest.get("baseFeePerGas", 0)
    try:
        max_priority = w3.eth.max_priority_fee
        if chain_id in (1, 137, 43114):
            max_priority = max(max_priority, w3.to_wei(2, "gwei"))
    except Exception:
        max_priority = w3.to_wei(30, "gwei")
    return {
        "maxFeePerGas": base_fee * 2 + max_priority,
        "maxPriorityFeePerGas": max_priority,
    }


def send_tx(
    w3: Any, account: Any, to: str, data: bytes,
    chain_name: str, chain_id: int, gas_strategy: str,
    gas_limit: int = 500_000, value: int = 0,
) -> Optional[str]:
    nonce = w3.eth.get_transaction_count(account.address, "pending")
    gas_params = build_gas_params(w3, chain_id, gas_strategy)

    tx: Dict[str, Any] = {
        "from": account.address,
        "to": w3.to_checksum_address(to),
        "nonce": nonce,
        "gas": gas_limit,
        "chainId": chain_id,
        "data": "0x" + data.hex(),
        "value": value,
        **gas_params,
    }

    try:
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex = tx_hash.hex()
        logger.info(f"[{chain_name}] Tx sent: {tx_hash_hex[:16]}...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        if receipt["status"] != 1:
            logger.error(f"[{chain_name}] Tx REVERTED: {tx_hash_hex}")
            return None

        gas_cost_wei = receipt["gasUsed"] * receipt.get("effectiveGasPrice", w3.eth.gas_price)
        gas_cost_eth = w3.from_wei(gas_cost_wei, "ether")
        logger.info(f"[{chain_name}] Confirmed (gas={receipt['gasUsed']:,}, cost={float(gas_cost_eth):.6f})")
        return tx_hash_hex

    except Exception as e:
        logger.error(f"[{chain_name}] Tx failed: {e}")
        return None


def eth_call(w3: Any, to: str, data: bytes) -> bytes:
    return w3.eth.call({
        "to": w3.to_checksum_address(to),
        "data": "0x" + data.hex(),
    })


def check_balance(w3: Any, token: str, owner: str) -> int:
    data = selector("balanceOf(address)") + encode_address(owner)
    result = eth_call(w3, token, data)
    return int(result.hex(), 16) if result else 0


def check_allowance(w3: Any, token: str, owner: str, spender: str) -> int:
    data = (
        selector("allowance(address,address)")
        + encode_address(owner)
        + encode_address(spender)
    )
    result = eth_call(w3, token, data)
    return int(result.hex(), 16) if result else 0


def get_pool(w3: Any, factory: str, token0: str, token1: str, fee: int) -> str:
    try:
        data = (
            selector("getPool(address,address,uint24)")
            + encode_address(token0)
            + encode_address(token1)
            + encode_uint24(fee)
        )
        result = eth_call(w3, factory, data)
        hex_str = result.hex()
        if len(hex_str) < 40:
            return ""
        addr = "0x" + hex_str[-40:]
        if addr == "0x" + "0" * 40:
            return ""
        # Validate it's a real address
        if len(addr) != 42:
            return ""
        return addr
    except Exception as e:
        logger.warning(f"getPool call failed: {e}")
        return ""


def get_pool_liquidity(w3: Any, pool: str) -> int:
    data = selector("liquidity()")
    result = eth_call(w3, pool, data)
    return int(result.hex(), 16) if result else 0


# ── Core Operations ──

def wrap_native(
    w3: Any, account: Any, weth_addr: str, amount_wei: int,
    chain_name: str, chain_id: int, gas_strategy: str,
) -> Optional[str]:
    """Wrap native token → WETH by calling deposit() with value."""
    logger.info(f"[{chain_name}] Wrapping {w3.from_wei(amount_wei, 'ether')} native → WETH...")
    data = selector("deposit()")
    return send_tx(
        w3, account, weth_addr, data, chain_name, chain_id,
        gas_strategy, gas_limit=100_000, value=amount_wei,
    )


def mint_wqbc(
    w3: Any, account: Any, wqbc_addr: str, amount_raw: int,
    chain_name: str, chain_id: int, gas_strategy: str,
) -> Optional[str]:
    """Mint wQBC via bridge operator."""
    logger.info(f"[{chain_name}] Minting {amount_raw / 10**TOKEN_DECIMALS:,.2f} wQBC...")
    qbc_tx_id = keccak256(f"native-pool-mint-wqbc-{chain_name}-{amount_raw}".encode())
    data = (
        selector("mint(address,uint256,bytes32)")
        + encode_address(account.address)
        + encode_uint256(amount_raw)
        + encode_bytes32(qbc_tx_id)
    )
    return send_tx(w3, account, wqbc_addr, data, chain_name, chain_id, gas_strategy)


def mint_wqusd(
    w3: Any, account: Any, wqusd_addr: str, amount_raw: int,
    chain_name: str, chain_id: int, gas_strategy: str,
) -> Optional[str]:
    """Mint wQUSD via bridge operator."""
    logger.info(f"[{chain_name}] Minting {amount_raw / 10**TOKEN_DECIMALS:,.2f} wQUSD...")
    source_hash = keccak256(f"native-pool-mint-wqusd-{chain_name}-{amount_raw}-src".encode())
    proof_hash = keccak256(f"native-pool-mint-wqusd-{chain_name}-{amount_raw}-proof".encode())
    data = (
        selector("bridgeMint(address,uint256,bytes32,bytes32)")
        + encode_address(account.address)
        + encode_uint256(amount_raw)
        + encode_bytes32(source_hash)
        + encode_bytes32(proof_hash)
    )
    return send_tx(w3, account, wqusd_addr, data, chain_name, chain_id, gas_strategy)


def approve_token(
    w3: Any, account: Any, token: str, spender: str,
    amount: int, chain_name: str, chain_id: int, gas_strategy: str,
) -> bool:
    current = check_allowance(w3, token, account.address, spender)
    if current >= amount:
        logger.info(f"[{chain_name}] Already approved")
        return True
    logger.info(f"[{chain_name}] Approving tokens...")
    data = (
        selector("approve(address,uint256)")
        + encode_address(spender)
        + encode_uint256(2**256 - 1)  # max approval
    )
    tx = send_tx(w3, account, token, data, chain_name, chain_id, gas_strategy, gas_limit=100_000)
    return tx is not None


def create_and_init_pool(
    w3: Any, account: Any, token0: str, token1: str,
    fee: int, sqrt_price: int,
    chain_name: str, chain_id: int, gas_strategy: str,
    pm_addr: str,
) -> Optional[str]:
    logger.info(f"[{chain_name}] Creating pool (sqrtPriceX96={sqrt_price})...")
    data = (
        selector("createAndInitializePoolIfNecessary(address,address,uint24,uint160)")
        + encode_address(token0)
        + encode_address(token1)
        + encode_uint24(fee)
        + encode_uint160(sqrt_price)
    )
    return send_tx(
        w3, account, pm_addr, data, chain_name, chain_id,
        gas_strategy, gas_limit=5_000_000,
    )


def add_liquidity(
    w3: Any, account: Any, token0: str, token1: str,
    fee: int, tick_lower: int, tick_upper: int,
    amount0: int, amount1: int,
    chain_name: str, chain_id: int, gas_strategy: str,
    pm_addr: str,
) -> Optional[str]:
    deadline = 2**64
    logger.info(f"[{chain_name}] Adding liquidity (amount0={amount0}, amount1={amount1})...")
    data = (
        selector("mint((address,address,uint24,int24,int24,uint256,uint256,uint256,uint256,address,uint256))")
        + encode_address(token0)
        + encode_address(token1)
        + encode_uint24(fee)
        + encode_int24(tick_lower)
        + encode_int24(tick_upper)
        + encode_uint256(amount0)
        + encode_uint256(amount1)
        + encode_uint256(0)  # amount0Min
        + encode_uint256(0)  # amount1Min
        + encode_address(account.address)
        + encode_uint256(deadline)
    )
    return send_tx(
        w3, account, pm_addr, data, chain_name, chain_id,
        gas_strategy, gas_limit=1_000_000,
    )


def swap_weth_to_usdc(
    w3: Any, account: Any, weth_addr: str, usdc_addr: str,
    amount_in: int, chain_name: str, chain_id: int, gas_strategy: str,
) -> Optional[str]:
    """Swap WETH → USDC via Uniswap V3 SwapRouter."""
    logger.info(f"[{chain_name}] Swapping {w3.from_wei(amount_in, 'ether')} WETH → USDC...")

    # Approve WETH to SwapRouter
    if not approve_token(
        w3, account, weth_addr, SWAP_ROUTER,
        amount_in, chain_name, chain_id, gas_strategy,
    ):
        return None
    time.sleep(2)

    # exactInputSingle params struct
    deadline = int(time.time()) + 3600
    data = (
        selector("exactInputSingle((address,address,uint24,address,uint256,uint256,uint256,uint160))")
        + encode_address(weth_addr)       # tokenIn
        + encode_address(usdc_addr)       # tokenOut
        + encode_uint24(FEE_500)          # fee (0.05% — most liquid ETH/USDC pool)
        + encode_address(account.address) # recipient
        + encode_uint256(deadline)        # deadline
        + encode_uint256(amount_in)       # amountIn
        + encode_uint256(0)               # amountOutMinimum (accept any)
        + encode_uint160(0)               # sqrtPriceLimitX96 (no limit)
    )
    return send_tx(
        w3, account, SWAP_ROUTER, data, chain_name, chain_id,
        gas_strategy, gas_limit=300_000,
    )


# ── Main Logic ──

def create_qbc_native_pool(
    w3: Any, account: Any, chain_name: str, chain_cfg: Dict[str, Any],
    wqbc_addr: str, registry: Dict[str, Any], dry_run: bool,
) -> Dict[str, str]:
    """Create wQBC/WETH pool on a single chain."""
    result: Dict[str, str] = {}
    chain_id = chain_cfg["chainId"]
    gas_strategy = chain_cfg["gasStrategy"]
    native_price = chain_cfg["nativePriceUSD"]
    weth_addr = chain_cfg["wrappedNative"]
    gas_reserve = chain_cfg["gasReserve"]
    factory = chain_cfg.get("factory", UNISWAP_V3_FACTORY)
    pm = chain_cfg.get("positionManager", POSITION_MANAGER)

    # Check native balance
    native_bal = w3.eth.get_balance(account.address)
    native_eth = float(w3.from_wei(native_bal, "ether"))
    reserve_wei = w3.to_wei(gas_reserve, "ether")

    # Check existing token balances from prior attempts
    pre_qbc = check_balance(w3, wqbc_addr, account.address)
    pre_weth = check_balance(w3, weth_addr, account.address)
    use_existing = pre_qbc > 0 and pre_weth > 0

    if use_existing:
        logger.info(f"[{chain_name}] Found existing wQBC={pre_qbc / 10**TOKEN_DECIMALS:.2f} "
                     f"WETH={pre_weth / 10**NATIVE_DECIMALS:.6f} — reusing")
        wrap_amount = pre_weth
        wrap_eth = float(w3.from_wei(pre_weth, "ether"))
        wrap_usd = wrap_eth * native_price
        qbc_amount = pre_qbc / (10 ** TOKEN_DECIMALS)
        qbc_amount_raw = pre_qbc
    elif native_bal <= reserve_wei:
        logger.error(f"[{chain_name}] Insufficient native balance ({native_eth:.6f})")
        result["qbc_native"] = "insufficient_gas"
        return result
    else:
        wrap_amount = native_bal - reserve_wei
        wrap_eth = float(w3.from_wei(wrap_amount, "ether"))
        wrap_usd = wrap_eth * native_price
        qbc_amount = wrap_usd / QBC_PRICE_USD
        qbc_amount_raw = int(qbc_amount * (10 ** TOKEN_DECIMALS))

    logger.info(f"[{chain_name}] Budget: {native_eth:.6f} native, wrapping {wrap_eth:.6f} (${wrap_usd:.2f})")
    logger.info(f"[{chain_name}] Need {qbc_amount:.2f} QBC at $0.25 to match ${wrap_usd:.2f}")

    if qbc_amount_raw < 100:  # Less than 0.000001 QBC
        logger.error(f"[{chain_name}] Amount too small to create pool")
        result["qbc_native"] = "amount_too_small"
        return result

    if dry_run:
        result["qbc_native"] = f"dry_run (wrap={wrap_eth:.6f}, qbc={qbc_amount:.2f})"
        return result

    if not use_existing:
        # Step 1: Mint wQBC
        tx = mint_wqbc(w3, account, wqbc_addr, qbc_amount_raw, chain_name, chain_id, gas_strategy)
        if not tx:
            result["qbc_native"] = "mint_failed"
            return result
        time.sleep(3)

        # Step 2: Wrap native → WETH
        current_native = w3.eth.get_balance(account.address)
        actual_wrap = max(0, current_native - reserve_wei)
        if actual_wrap <= 0:
            logger.error(f"[{chain_name}] No native left to wrap")
            result["qbc_native"] = "no_native_to_wrap"
            return result
        wrap_amount = actual_wrap
        tx = wrap_native(w3, account, weth_addr, actual_wrap, chain_name, chain_id, gas_strategy)
        if not tx:
            result["qbc_native"] = "wrap_failed"
            return result
        time.sleep(3)
    else:
        logger.info(f"[{chain_name}] Using existing balances — skip mint and wrap")

    # Verify balances
    qbc_bal = check_balance(w3, wqbc_addr, account.address)
    weth_bal = check_balance(w3, weth_addr, account.address)
    logger.info(f"[{chain_name}] wQBC balance: {qbc_bal / 10**TOKEN_DECIMALS:.2f}")
    logger.info(f"[{chain_name}] WETH balance: {weth_bal / 10**NATIVE_DECIMALS:.6f}")

    # Sort tokens for Uniswap
    token0, token1 = sort_tokens(wqbc_addr, weth_addr)
    is_qbc_token0 = token0.lower() == wqbc_addr.lower()

    if is_qbc_token0:
        amount0 = min(qbc_bal, qbc_amount_raw)
        amount1 = min(weth_bal, wrap_amount)
        t0_decimals, t1_decimals = TOKEN_DECIMALS, NATIVE_DECIMALS
        t0_price, t1_price = QBC_PRICE_USD, native_price
    else:
        amount0 = min(weth_bal, wrap_amount)
        amount1 = min(qbc_bal, qbc_amount_raw)
        t0_decimals, t1_decimals = NATIVE_DECIMALS, TOKEN_DECIMALS
        t0_price, t1_price = native_price, QBC_PRICE_USD

    logger.info(f"[{chain_name}] token0={'wQBC' if is_qbc_token0 else 'WETH'} ({token0[:10]}...)")
    logger.info(f"[{chain_name}] token1={'WETH' if is_qbc_token0 else 'wQBC'} ({token1[:10]}...)")

    # Calculate sqrtPriceX96
    sqrt_price = calc_sqrt_price_x96(t0_decimals, t1_decimals, t0_price, t1_price)
    logger.info(f"[{chain_name}] sqrtPriceX96 = {sqrt_price}")

    # Step 3: Check if pool exists
    pool_addr = get_pool(w3, factory, token0, token1, FEE_3000)

    if pool_addr:
        liq = get_pool_liquidity(w3, pool_addr)
        if liq > 0:
            logger.info(f"[{chain_name}] Pool already exists at {pool_addr} with liquidity")
            result["qbc_native"] = f"already_exists ({pool_addr[:10]}...)"
            return result
        logger.info(f"[{chain_name}] Pool exists but empty — adding liquidity")
    else:
        # Create and initialize pool
        tx = create_and_init_pool(
            w3, account, token0, token1, FEE_3000, sqrt_price,
            chain_name, chain_id, gas_strategy, pm,
        )
        if not tx:
            result["qbc_native"] = "pool_creation_failed"
            return result
        time.sleep(3)

        pool_addr = get_pool(w3, factory, token0, token1, FEE_3000)
        if not pool_addr:
            result["qbc_native"] = "pool_not_found_after_creation"
            return result
        logger.info(f"[{chain_name}] Pool created at {pool_addr}")

    # Step 4: Approve both tokens to PM
    if not approve_token(w3, account, token0, pm, amount0, chain_name, chain_id, gas_strategy):
        result["qbc_native"] = "approve0_failed"
        return result
    time.sleep(2)

    if not approve_token(w3, account, token1, pm, amount1, chain_name, chain_id, gas_strategy):
        result["qbc_native"] = "approve1_failed"
        return result
    time.sleep(2)

    # Step 5: Add liquidity
    tx = add_liquidity(
        w3, account, token0, token1, FEE_3000,
        TICK_LOWER_60, TICK_UPPER_60,
        amount0, amount1,
        chain_name, chain_id, gas_strategy, pm,
    )

    if tx:
        time.sleep(3)
        liq = get_pool_liquidity(w3, pool_addr)
        symbol = chain_cfg["nativeSymbol"]
        result["qbc_native"] = f"CREATED pool={pool_addr[:14]}... liq={liq} ({qbc_amount:.1f} QBC / {wrap_eth:.6f} W{symbol})"

        # Update registry
        native_symbol = chain_cfg["nativeSymbol"]
        pool_name = f"wQBC-W{native_symbol}"
        reg_key = f"external:{chain_name}:pool:{pool_name}"
        registry[reg_key] = {
            "address": pool_addr,
            "dex": "Uniswap V3",
            "fee": "0.3%",
            "token0": token0,
            "token1": token1,
            "priceTarget": f"1 QBC = ${QBC_PRICE_USD}",
            "deployed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    else:
        result["qbc_native"] = "liquidity_add_failed"

    return result


def create_qusd_usdc_pool(
    w3: Any, account: Any, chain_name: str, chain_cfg: Dict[str, Any],
    wqusd_addr: str, registry: Dict[str, Any], dry_run: bool,
) -> Dict[str, str]:
    """Create wQUSD/USDC pool on a chain. Swaps some native → USDC first."""
    result: Dict[str, str] = {}
    chain_id = chain_cfg["chainId"]
    gas_strategy = chain_cfg["gasStrategy"]
    usdc_addr = chain_cfg.get("usdc", "")
    usdc_decimals = chain_cfg.get("usdcDecimals", 6)
    weth_addr = chain_cfg["wrappedNative"]
    factory = chain_cfg.get("factory", UNISWAP_V3_FACTORY)
    pm = chain_cfg.get("positionManager", POSITION_MANAGER)

    if not usdc_addr:
        result["qusd_usdc"] = "no_usdc_address"
        return result

    # Check remaining native balance
    native_bal = w3.eth.get_balance(account.address)
    native_eth = float(w3.from_wei(native_bal, "ether"))
    native_price = chain_cfg["nativePriceUSD"]

    # Use 40% of remaining balance for USDC swap
    swap_amount = int(native_bal * 40 // 100)
    swap_usd = float(w3.from_wei(swap_amount, "ether")) * native_price

    if swap_usd < 0.50:
        logger.warning(f"[{chain_name}] Only ${swap_usd:.2f} available for USDC swap — skipping")
        result["qusd_usdc"] = f"insufficient_funds (${swap_usd:.2f})"
        return result

    logger.info(f"[{chain_name}] Will swap ${swap_usd:.2f} native → USDC for wQUSD/USDC pool")

    if dry_run:
        result["qusd_usdc"] = f"dry_run (swap=${swap_usd:.2f})"
        return result

    # Step 1: Wrap native → WETH (need WETH to swap on Uniswap)
    tx = wrap_native(w3, account, weth_addr, swap_amount, chain_name, chain_id, gas_strategy)
    if not tx:
        result["qusd_usdc"] = "wrap_for_swap_failed"
        return result
    time.sleep(3)

    # Step 2: Swap WETH → USDC
    tx = swap_weth_to_usdc(
        w3, account, weth_addr, usdc_addr, swap_amount,
        chain_name, chain_id, gas_strategy,
    )
    if not tx:
        result["qusd_usdc"] = "usdc_swap_failed"
        return result
    time.sleep(3)

    # Check USDC balance
    usdc_bal = check_balance(w3, usdc_addr, account.address)
    usdc_human = usdc_bal / (10 ** usdc_decimals)
    logger.info(f"[{chain_name}] USDC balance after swap: {usdc_human:.2f}")

    if usdc_bal == 0:
        result["qusd_usdc"] = "no_usdc_after_swap"
        return result

    # Step 3: Calculate wQUSD needed (at $0.10/QUSD, need 10x USDC amount in QUSD)
    # USDC value = usdc_human * $1
    # QUSD needed = usdc_human / QUSD_PRICE_USD
    qusd_amount = usdc_human / QUSD_PRICE_USD
    qusd_amount_raw = int(qusd_amount * (10 ** TOKEN_DECIMALS))

    logger.info(f"[{chain_name}] Need {qusd_amount:.2f} wQUSD for {usdc_human:.2f} USDC")

    # Step 4: Mint wQUSD
    tx = mint_wqusd(w3, account, wqusd_addr, qusd_amount_raw, chain_name, chain_id, gas_strategy)
    if not tx:
        result["qusd_usdc"] = "qusd_mint_failed"
        return result
    time.sleep(3)

    # Sort tokens
    token0, token1 = sort_tokens(wqusd_addr, usdc_addr)
    is_qusd_token0 = token0.lower() == wqusd_addr.lower()

    if is_qusd_token0:
        amount0 = min(check_balance(w3, wqusd_addr, account.address), qusd_amount_raw)
        amount1 = usdc_bal
        t0_decimals, t1_decimals = TOKEN_DECIMALS, usdc_decimals
        t0_price, t1_price = QUSD_PRICE_USD, 1.0
    else:
        amount0 = usdc_bal
        amount1 = min(check_balance(w3, wqusd_addr, account.address), qusd_amount_raw)
        t0_decimals, t1_decimals = usdc_decimals, TOKEN_DECIMALS
        t0_price, t1_price = 1.0, QUSD_PRICE_USD

    sqrt_price = calc_sqrt_price_x96(t0_decimals, t1_decimals, t0_price, t1_price)
    logger.info(f"[{chain_name}] wQUSD/USDC sqrtPriceX96 = {sqrt_price}")

    # Use 0.05% fee for stablecoin-like pair
    fee = FEE_500
    tick_lower = TICK_LOWER_10
    tick_upper = TICK_UPPER_10

    # Check/create pool
    pool_addr = get_pool(w3, factory, token0, token1, fee)

    if not pool_addr:
        tx = create_and_init_pool(
            w3, account, token0, token1, fee, sqrt_price,
            chain_name, chain_id, gas_strategy, pm,
        )
        if not tx:
            result["qusd_usdc"] = "pool_creation_failed"
            return result
        time.sleep(3)
        pool_addr = get_pool(w3, factory, token0, token1, fee)
        if not pool_addr:
            result["qusd_usdc"] = "pool_not_found"
            return result

    # Approve
    if not approve_token(w3, account, token0, pm, amount0, chain_name, chain_id, gas_strategy):
        result["qusd_usdc"] = "approve0_failed"
        return result
    time.sleep(2)
    if not approve_token(w3, account, token1, pm, amount1, chain_name, chain_id, gas_strategy):
        result["qusd_usdc"] = "approve1_failed"
        return result
    time.sleep(2)

    # Add liquidity
    tx = add_liquidity(
        w3, account, token0, token1, fee,
        tick_lower, tick_upper, amount0, amount1,
        chain_name, chain_id, gas_strategy, pm,
    )

    if tx:
        time.sleep(3)
        liq = get_pool_liquidity(w3, pool_addr)
        result["qusd_usdc"] = f"CREATED pool={pool_addr[:14]}... liq={liq} ({qusd_amount:.1f} QUSD / {usdc_human:.2f} USDC)"

        reg_key = f"external:{chain_name}:pool:wQUSD-USDC"
        registry[reg_key] = {
            "address": pool_addr,
            "dex": "Uniswap V3",
            "fee": "0.05%",
            "token0": token0,
            "token1": token1,
            "priceTarget": f"1 QUSD = ${QUSD_PRICE_USD}",
            "deployed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    else:
        result["qusd_usdc"] = "liquidity_add_failed"

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Create wQBC/WETH + wQUSD/USDC pools")
    parser.add_argument("--chains", type=str, default="",
        help="Comma-separated chains (default: all)")
    parser.add_argument("--dry-run", action="store_true",
        help="Show plan without executing")
    parser.add_argument("--skip-usdc", action="store_true",
        help="Skip wQUSD/USDC pool creation")
    parser.add_argument("--usdc-chains", type=str, default="ethereum",
        help="Chains for wQUSD/USDC pools (default: ethereum)")
    args = parser.parse_args()

    print("=" * 70)
    print("  wQBC/WETH + wQUSD/USDC POOL CREATION")
    print(f"  QBC Target: ${QBC_PRICE_USD} | QUSD Target: ${QUSD_PRICE_USD}")
    print("=" * 70)

    keys = {}
    for line in (PROJECT_ROOT / "secure_key.env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            keys[k.strip()] = v.strip()

    env = {}
    for line in (PROJECT_ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()

    private_key = keys.get("ETH_DEPLOYER_PRIVATE_KEY", "")
    if not private_key:
        logger.error("ETH_DEPLOYER_PRIVATE_KEY not found")
        sys.exit(1)

    registry = json.loads(REGISTRY_PATH.read_text())

    chains = [c.strip().lower() for c in args.chains.split(",") if c.strip()] if args.chains else list(CHAINS.keys())
    usdc_chains = [c.strip().lower() for c in args.usdc_chains.split(",") if c.strip()]

    all_results: Dict[str, Dict[str, str]] = {}

    for chain_name in chains:
        chain_cfg = CHAINS.get(chain_name)
        if not chain_cfg:
            logger.warning(f"Unknown chain: {chain_name}")
            continue

        wqbc_addr = registry.get(f"external:{chain_name}:wQBC", {}).get("address", "")
        wqusd_addr = registry.get(f"external:{chain_name}:wQUSD", {}).get("address", "")

        if not wqbc_addr:
            logger.warning(f"[{chain_name}] wQBC not deployed, skipping")
            continue

        rpc_key = chain_cfg["rpcKey"]
        rpc_url = env.get(rpc_key, os.getenv(rpc_key, ""))
        if not rpc_url:
            logger.error(f"[{chain_name}] No RPC URL ({rpc_key})")
            continue

        print(f"\n{'=' * 60}")
        print(f"  {chain_name.upper()} — wQBC/W{chain_cfg['nativeSymbol']} pool")
        print(f"  wQBC:   {wqbc_addr}")
        print(f"  Native: {chain_cfg['wrappedNative']} (W{chain_cfg['nativeSymbol']})")
        print(f"{'=' * 60}")

        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))

        if chain_cfg.get("poa"):
            try:
                from web3.middleware import ExtraDataToPOAMiddleware
                w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            except ImportError:
                pass

        if not w3.is_connected():
            logger.error(f"[{chain_name}] Cannot connect to RPC")
            continue

        account = w3.eth.account.from_key(private_key)

        # Create wQBC/WETH pool
        results = create_qbc_native_pool(
            w3, account, chain_name, chain_cfg, wqbc_addr, registry, args.dry_run,
        )
        all_results[chain_name] = results

        # Create wQUSD/USDC pool if requested
        if not args.skip_usdc and chain_name in usdc_chains and wqusd_addr:
            print(f"\n  --- {chain_name.upper()} wQUSD/USDC ---")
            usdc_results = create_qusd_usdc_pool(
                w3, account, chain_name, chain_cfg, wqusd_addr, registry, args.dry_run,
            )
            all_results[chain_name].update(usdc_results)

        time.sleep(2)

    # Save registry
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2) + "\n")
    logger.info("Registry saved")

    # Summary
    print("\n" + "=" * 70)
    print("  POOL CREATION SUMMARY")
    print("=" * 70)
    for chain, results in all_results.items():
        for pool_type, status in results.items():
            print(f"  {chain:12s} {pool_type:15s}: {status}")
    print("=" * 70)

    # Show remaining balances
    print("\n  REMAINING BALANCES:")
    for chain_name in chains:
        chain_cfg = CHAINS.get(chain_name)
        if not chain_cfg:
            continue
        rpc_url = env.get(chain_cfg["rpcKey"], "")
        if not rpc_url:
            continue
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
            account = w3.eth.account.from_key(private_key)
            bal = w3.eth.get_balance(account.address)
            print(f"  {chain_name:12s}: {float(w3.from_wei(bal, 'ether')):.6f} {chain_cfg['nativeSymbol']}")
        except Exception:
            pass
    print("=" * 70)


if __name__ == "__main__":
    main()
