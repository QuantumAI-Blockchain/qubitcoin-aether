"""
External DEX Price Reader for wQUSD / wQBC

Reads real-time prices from DEX pools on external chains:
  - Ethereum / L2: Uniswap V3 TWAP via pool.observe()
  - BSC: PancakeSwap V3 TWAP (same interface as Uniswap V3)
  - Solana: Orca Whirlpool price via getSqrtPrice RPC

Used by the keeper daemon to detect wQUSD depeg events across chains
and calculate cross-chain arbitrage opportunities.

All prices are returned as Decimal with 8-decimal precision to match
QUSDOracle.sol (PRICE_DECIMALS = 8).
"""

import time
import math
import struct
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class DEXType(Enum):
    """Supported DEX protocols."""
    UNISWAP_V3 = "uniswap_v3"
    PANCAKESWAP_V3 = "pancakeswap_v3"
    ORCA_WHIRLPOOL = "orca_whirlpool"
    AERODROME = "aerodrome"
    CAMELOT = "camelot"


class PriceSource(Enum):
    """Where the price came from."""
    TWAP = "twap"        # Time-weighted average (most reliable)
    SPOT = "spot"        # Instantaneous (manipulable)
    CACHED = "cached"    # Stale cached value
    MANUAL = "manual"    # Operator override


@dataclass
class DEXPriceReading:
    """Single price reading from a DEX pool."""
    chain_id: int
    chain_name: str
    dex: DEXType
    pool_address: str
    token_pair: str            # e.g. "wQUSD/USDC", "wQBC/ETH"
    price: Decimal             # Price of token0 in token1 terms
    price_usd: Decimal         # Price in USD terms (best effort)
    source: PriceSource
    timestamp: float
    block_number: int = 0
    liquidity_usd: Decimal = Decimal("0")  # Pool TVL estimate
    confidence: float = 1.0    # 0.0-1.0, lower if stale or low liquidity


@dataclass
class ChainPriceState:
    """Aggregated price state for one external chain."""
    chain_id: int
    chain_name: str
    wqusd_usd: Optional[Decimal] = None
    wqbc_usd: Optional[Decimal] = None
    wqusd_readings: List[DEXPriceReading] = field(default_factory=list)
    wqbc_readings: List[DEXPriceReading] = field(default_factory=list)
    last_update: float = 0.0
    healthy: bool = False
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Uniswap V3 TWAP helpers  (pure math, no web3 dep at import time)
# ---------------------------------------------------------------------------

# Uniswap V3 pool ABI selectors (keccak256 first 4 bytes)
_SLOT0_SELECTOR = "3850c7bd"          # slot0()
_OBSERVE_SELECTOR = "883bdbfd"        # observe(uint32[])
_LIQUIDITY_SELECTOR = "1a686502"      # liquidity()
_TOKEN0_SELECTOR = "0dfe1681"         # token0()
_TOKEN1_SELECTOR = "d21220a7"         # token1()


def _decode_sqrtPriceX96(sqrt_price_x96: int, decimals0: int = 8,
                         decimals1: int = 6) -> Decimal:
    """Convert Uniswap V3 sqrtPriceX96 to a human-readable price.

    sqrtPriceX96 = sqrt(price) * 2^96
    price = (sqrtPriceX96 / 2^96)^2 * 10^(decimals0 - decimals1)

    For wQUSD(8 dec)/USDC(6 dec): price = how many USDC per wQUSD.
    """
    if sqrt_price_x96 == 0:
        return Decimal("0")
    price_raw = (Decimal(sqrt_price_x96) / Decimal(2 ** 96)) ** 2
    decimal_adjustment = Decimal(10 ** (decimals0 - decimals1))
    price = price_raw * decimal_adjustment
    return price.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def _compute_twap_from_ticks(tick_cumulative_start: int,
                             tick_cumulative_end: int,
                             elapsed_seconds: int,
                             decimals0: int = 8,
                             decimals1: int = 6) -> Decimal:
    """Compute TWAP price from Uniswap V3 tick cumulatives.

    TWAP tick = (tickCum_end - tickCum_start) / elapsed
    price = 1.0001^tick * 10^(decimals0 - decimals1)
    """
    if elapsed_seconds <= 0:
        return Decimal("0")
    avg_tick = (tick_cumulative_end - tick_cumulative_start) / elapsed_seconds
    price_raw = Decimal(str(1.0001 ** avg_tick))
    decimal_adjustment = Decimal(10 ** (decimals0 - decimals1))
    price = price_raw * decimal_adjustment
    return price.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Solana price helpers
# ---------------------------------------------------------------------------

def _decode_orca_sqrt_price(sqrt_price: int, decimals_a: int = 8,
                            decimals_b: int = 6) -> Decimal:
    """Decode Orca Whirlpool sqrtPrice (Q64.64 fixed-point) to human price.

    sqrtPrice is in Q64.64 format: value / 2^64 = sqrt(price)
    price = (sqrtPrice / 2^64)^2 * 10^(decimals_a - decimals_b)
    """
    if sqrt_price == 0:
        return Decimal("0")
    sqrt_val = Decimal(sqrt_price) / Decimal(2 ** 64)
    price_raw = sqrt_val ** 2
    decimal_adjustment = Decimal(10 ** (decimals_a - decimals_b))
    price = price_raw * decimal_adjustment
    return price.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Chain configuration
# ---------------------------------------------------------------------------

# Default pool addresses — will be overridden by env vars or config
_DEFAULT_POOLS: Dict[int, Dict[str, dict]] = {
    # Ethereum (chain 1)
    1: {
        "wqusd_usdc": {
            "dex": DEXType.UNISWAP_V3,
            "address": "",  # Set via ETH_WQUSD_USDC_POOL
            "decimals0": 8, "decimals1": 6,  # wQUSD=8, USDC=6
            "fee_tier": 100,  # 0.01% (stable-stable)
        },
        "wqbc_eth": {
            "dex": DEXType.UNISWAP_V3,
            "address": "",  # Set via ETH_WQBC_ETH_POOL
            "decimals0": 8, "decimals1": 18,  # wQBC=8, ETH=18
            "fee_tier": 3000,  # 0.3%
        },
    },
    # BSC (chain 56)
    56: {
        "wqusd_usdt": {
            "dex": DEXType.PANCAKESWAP_V3,
            "address": "",  # Set via BSC_WQUSD_USDT_POOL
            "decimals0": 8, "decimals1": 18,  # wQUSD=8, USDT=18 on BSC
            "fee_tier": 100,
        },
        "wqbc_bnb": {
            "dex": DEXType.PANCAKESWAP_V3,
            "address": "",  # Set via BSC_WQBC_BNB_POOL
            "decimals0": 8, "decimals1": 18,  # wQBC=8, BNB=18
            "fee_tier": 2500,
        },
    },
    # Arbitrum (chain 42161)
    42161: {
        "wqusd_usdc": {
            "dex": DEXType.UNISWAP_V3,
            "address": "",
            "decimals0": 8, "decimals1": 6,
            "fee_tier": 100,
        },
    },
    # Base (chain 8453)
    8453: {
        "wqusd_usdc": {
            "dex": DEXType.AERODROME,
            "address": "",
            "decimals0": 8, "decimals1": 6,
            "fee_tier": 1,  # Stable pool
        },
    },
    # Optimism (chain 10)
    10: {
        "wqusd_usdc": {
            "dex": DEXType.UNISWAP_V3,
            "address": "",
            "decimals0": 8, "decimals1": 6,
            "fee_tier": 100,
        },
    },
}

# Solana is non-EVM, handled separately
_SOLANA_POOLS: Dict[str, dict] = {
    "wqusd_usdc": {
        "dex": DEXType.ORCA_WHIRLPOOL,
        "address": "",  # Set via SOLANA_WQUSD_USDC_POOL
        "decimals_a": 8, "decimals_b": 6,
    },
    "wqbc_sol": {
        "dex": DEXType.ORCA_WHIRLPOOL,
        "address": "",  # Set via SOLANA_WQBC_SOL_POOL
        "decimals_a": 8, "decimals_b": 9,  # wQBC=8, SOL=9
    },
}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class DEXPriceReader:
    """Reads wQUSD and wQBC prices from DEX pools across chains.

    Architecture:
      - One Web3 connection per EVM chain (lazy-initialized)
      - One Solana RPC connection (lazy-initialized)
      - Caches prices with configurable TTL
      - Falls back to spot price if TWAP unavailable
      - Reports confidence based on liquidity and staleness
    """

    # Cache validity (seconds)
    CACHE_TTL: float = 30.0
    # TWAP window for Uniswap V3 observe() calls
    TWAP_WINDOW: int = 600  # 10 minutes

    # Minimum pool TVL (USD) for a reading to be considered reliable
    MIN_TVL_RELIABLE: Decimal = Decimal("1000")

    def __init__(self) -> None:
        # Per-chain state
        self._chain_states: Dict[int, ChainPriceState] = {}
        # Web3 connections (lazy)
        self._web3_clients: Dict[int, object] = {}
        # Solana client (lazy)
        self._solana_client: Optional[object] = None
        # Pool configs (populated from env + defaults)
        self._evm_pools: Dict[int, Dict[str, dict]] = {}
        self._solana_pools: Dict[str, dict] = {}
        # Manual price overrides (for testing / emergency)
        self._manual_prices: Dict[str, Decimal] = {}
        # Load pool addresses from environment
        self._load_pool_config()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _load_pool_config(self) -> None:
        """Load pool addresses from environment variables."""
        import os

        chain_names = {
            1: "Ethereum", 56: "BSC", 42161: "Arbitrum",
            8453: "Base", 10: "Optimism", 137: "Polygon",
            43114: "Avalanche",
        }

        # Load EVM pools
        for chain_id, pools in _DEFAULT_POOLS.items():
            self._evm_pools[chain_id] = {}
            for pair_key, pool_cfg in pools.items():
                cfg = dict(pool_cfg)
                env_key = f"{chain_names.get(chain_id, 'CHAIN')}_" \
                          f"{pair_key.upper()}_POOL"
                env_key = env_key.replace(" ", "_")
                cfg["address"] = os.getenv(env_key, cfg.get("address", ""))
                self._evm_pools[chain_id][pair_key] = cfg

        # Load Solana pools
        for pair_key, pool_cfg in _SOLANA_POOLS.items():
            cfg = dict(pool_cfg)
            env_key = f"SOLANA_{pair_key.upper()}_POOL"
            cfg["address"] = os.getenv(env_key, cfg.get("address", ""))
            self._solana_pools[pair_key] = cfg

        # Initialize chain states
        for chain_id in self._evm_pools:
            self._chain_states[chain_id] = ChainPriceState(
                chain_id=chain_id,
                chain_name=chain_names.get(chain_id, f"Chain-{chain_id}"),
            )
        # Solana uses chain_id = 0
        self._chain_states[0] = ChainPriceState(
            chain_id=0, chain_name="Solana",
        )

    def set_manual_price(self, key: str, price: Decimal) -> None:
        """Set a manual price override (for testing/emergency).

        Args:
            key: e.g. "1:wqusd_usd" for Ethereum wQUSD price
            price: USD price
        """
        self._manual_prices[key] = price

    def clear_manual_prices(self) -> None:
        """Remove all manual price overrides."""
        self._manual_prices.clear()

    # ------------------------------------------------------------------
    # Web3 connection management
    # ------------------------------------------------------------------

    def _get_web3(self, chain_id: int) -> Optional[object]:
        """Get or create Web3 connection for a chain."""
        if chain_id in self._web3_clients:
            return self._web3_clients[chain_id]

        import os
        rpc_env_map = {
            1: "ETH_RPC_URL", 56: "BSC_RPC_URL", 137: "POLYGON_RPC_URL",
            42161: "ARBITRUM_RPC_URL", 10: "OPTIMISM_RPC_URL",
            43114: "AVALANCHE_RPC_URL", 8453: "BASE_RPC_URL",
        }
        env_key = rpc_env_map.get(chain_id)
        if not env_key:
            return None

        rpc_url = os.getenv(env_key, "")
        if not rpc_url:
            return None

        try:
            from web3 import Web3
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
            if w3.is_connected():
                self._web3_clients[chain_id] = w3
                logger.info(f"DEXPriceReader: connected to chain {chain_id}")
                return w3
            else:
                logger.warning(f"DEXPriceReader: failed to connect to chain {chain_id}")
                return None
        except Exception as e:
            logger.warning(f"DEXPriceReader: web3 init failed for chain {chain_id}: {e}")
            return None

    def _get_solana_client(self) -> Optional[object]:
        """Get or create Solana RPC client."""
        if self._solana_client is not None:
            return self._solana_client
        import os
        rpc_url = os.getenv("SOLANA_RPC_URL", "")
        if not rpc_url:
            return None
        try:
            from solana.rpc.api import Client
            client = Client(rpc_url, timeout=10)
            self._solana_client = client
            logger.info("DEXPriceReader: connected to Solana")
            return client
        except Exception as e:
            logger.warning(f"DEXPriceReader: Solana client init failed: {e}")
            return None

    # ------------------------------------------------------------------
    # EVM price reading
    # ------------------------------------------------------------------

    def _read_uniswap_v3_spot(self, w3: object, pool_address: str,
                              decimals0: int, decimals1: int) -> Optional[DEXPriceReading]:
        """Read spot price from Uniswap V3 pool via slot0()."""
        try:
            # Call slot0() — returns (sqrtPriceX96, tick, ...)
            data = bytes.fromhex(_SLOT0_SELECTOR)
            result = w3.eth.call({"to": pool_address, "data": data})  # type: ignore[union-attr]
            if len(result) < 32:
                return None
            sqrt_price_x96 = int.from_bytes(result[:32], "big")
            price = _decode_sqrtPriceX96(sqrt_price_x96, decimals0, decimals1)
            block = w3.eth.block_number  # type: ignore[union-attr]
            return DEXPriceReading(
                chain_id=0, chain_name="", dex=DEXType.UNISWAP_V3,
                pool_address=pool_address, token_pair="",
                price=price, price_usd=price,
                source=PriceSource.SPOT,
                timestamp=time.time(), block_number=block,
            )
        except Exception as e:
            logger.debug(f"slot0 read failed for {pool_address}: {e}")
            return None

    def _read_uniswap_v3_twap(self, w3: object, pool_address: str,
                              decimals0: int, decimals1: int,
                              window: int = 600) -> Optional[DEXPriceReading]:
        """Read TWAP from Uniswap V3 pool via observe()."""
        try:
            # Encode observe([window, 0])
            # ABI: observe(uint32[] calldata secondsAgos)
            # We encode manually: selector + offset(32) + length(2) + [window, 0]
            import eth_abi
            calldata = bytes.fromhex(_OBSERVE_SELECTOR) + eth_abi.encode(
                ["uint32[]"], [[window, 0]]
            )
            result = w3.eth.call({"to": pool_address, "data": calldata})  # type: ignore[union-attr]
            if len(result) < 128:
                # Fallback to spot
                return self._read_uniswap_v3_spot(w3, pool_address, decimals0, decimals1)

            # Decode: (int56[] tickCumulatives, uint160[] secondsPerLiquidityCumulativeX128s)
            decoded = eth_abi.decode(
                ["int56[]", "uint160[]"], result
            )
            tick_cums = decoded[0]
            if len(tick_cums) < 2:
                return self._read_uniswap_v3_spot(w3, pool_address, decimals0, decimals1)

            price = _compute_twap_from_ticks(
                tick_cums[0], tick_cums[1], window, decimals0, decimals1,
            )
            block = w3.eth.block_number  # type: ignore[union-attr]
            return DEXPriceReading(
                chain_id=0, chain_name="", dex=DEXType.UNISWAP_V3,
                pool_address=pool_address, token_pair="",
                price=price, price_usd=price,
                source=PriceSource.TWAP,
                timestamp=time.time(), block_number=block,
                confidence=0.95,  # TWAP is more reliable than spot
            )
        except Exception as e:
            logger.debug(f"TWAP read failed for {pool_address}, falling back to spot: {e}")
            return self._read_uniswap_v3_spot(w3, pool_address, decimals0, decimals1)

    def _read_evm_pool(self, chain_id: int, pair_key: str,
                       pool_cfg: dict) -> Optional[DEXPriceReading]:
        """Read price from a single EVM pool."""
        pool_address = pool_cfg.get("address", "")
        if not pool_address:
            return None

        w3 = self._get_web3(chain_id)
        if w3 is None:
            return None

        dex = pool_cfg.get("dex", DEXType.UNISWAP_V3)
        decimals0 = pool_cfg.get("decimals0", 8)
        decimals1 = pool_cfg.get("decimals1", 6)

        # All V3-compatible DEXes use the same TWAP interface
        if dex in (DEXType.UNISWAP_V3, DEXType.PANCAKESWAP_V3,
                   DEXType.AERODROME, DEXType.CAMELOT):
            reading = self._read_uniswap_v3_twap(
                w3, pool_address, decimals0, decimals1, self.TWAP_WINDOW
            )
        else:
            reading = self._read_uniswap_v3_spot(
                w3, pool_address, decimals0, decimals1
            )

        if reading:
            chain_name = self._chain_states.get(chain_id, ChainPriceState(
                chain_id=chain_id, chain_name=f"Chain-{chain_id}"
            )).chain_name
            reading.chain_id = chain_id
            reading.chain_name = chain_name
            reading.dex = dex
            reading.token_pair = pair_key.replace("_", "/").upper()
        return reading

    # ------------------------------------------------------------------
    # Solana price reading
    # ------------------------------------------------------------------

    def _read_solana_pool(self, pair_key: str,
                          pool_cfg: dict) -> Optional[DEXPriceReading]:
        """Read price from a Solana Orca Whirlpool."""
        pool_address = pool_cfg.get("address", "")
        if not pool_address:
            return None

        client = self._get_solana_client()
        if client is None:
            return None

        try:
            # Read Whirlpool account data — sqrtPrice is at offset 65 (u128, 16 bytes)
            from solders.pubkey import Pubkey  # type: ignore[import-untyped]
            resp = client.get_account_info(Pubkey.from_string(pool_address))
            if resp.value is None or resp.value.data is None:
                return None

            account_data = resp.value.data
            if len(account_data) < 81:
                return None

            # Whirlpool layout: discriminator(8) + ... + sqrtPrice(16) at offset 65
            sqrt_price = int.from_bytes(account_data[65:81], "little")
            decimals_a = pool_cfg.get("decimals_a", 8)
            decimals_b = pool_cfg.get("decimals_b", 6)
            price = _decode_orca_sqrt_price(sqrt_price, decimals_a, decimals_b)

            return DEXPriceReading(
                chain_id=0, chain_name="Solana",
                dex=DEXType.ORCA_WHIRLPOOL,
                pool_address=pool_address,
                token_pair=pair_key.replace("_", "/").upper(),
                price=price, price_usd=price,
                source=PriceSource.SPOT,
                timestamp=time.time(),
                confidence=0.8,  # Spot on Solana, no TWAP
            )
        except Exception as e:
            logger.debug(f"Solana pool read failed for {pool_address}: {e}")
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_all_prices(self) -> Dict[int, ChainPriceState]:
        """Fetch prices from all configured chains.

        Returns:
            Dict mapping chain_id -> ChainPriceState with latest readings.
        """
        now = time.time()

        # EVM chains
        for chain_id, pools in self._evm_pools.items():
            state = self._chain_states.get(chain_id)
            if state is None:
                continue
            # Check cache
            if now - state.last_update < self.CACHE_TTL and state.healthy:
                continue

            state.wqusd_readings.clear()
            state.wqbc_readings.clear()
            state.error = None
            state.healthy = False

            for pair_key, pool_cfg in pools.items():
                # Check manual override first
                manual_key = f"{chain_id}:{pair_key}_usd"
                if manual_key in self._manual_prices:
                    reading = DEXPriceReading(
                        chain_id=chain_id, chain_name=state.chain_name,
                        dex=pool_cfg.get("dex", DEXType.UNISWAP_V3),
                        pool_address="manual", token_pair=pair_key,
                        price=self._manual_prices[manual_key],
                        price_usd=self._manual_prices[manual_key],
                        source=PriceSource.MANUAL, timestamp=now,
                        confidence=1.0,
                    )
                else:
                    reading = self._read_evm_pool(chain_id, pair_key, pool_cfg)

                if reading:
                    if "wqusd" in pair_key:
                        state.wqusd_readings.append(reading)
                        state.wqusd_usd = reading.price_usd
                    elif "wqbc" in pair_key:
                        state.wqbc_readings.append(reading)
                        state.wqbc_usd = reading.price_usd

            if state.wqusd_readings or state.wqbc_readings:
                state.healthy = True
            state.last_update = now

        # Solana
        sol_state = self._chain_states.get(0)
        if sol_state and (now - sol_state.last_update >= self.CACHE_TTL
                          or not sol_state.healthy):
            sol_state.wqusd_readings.clear()
            sol_state.wqbc_readings.clear()
            sol_state.error = None
            sol_state.healthy = False

            for pair_key, pool_cfg in self._solana_pools.items():
                manual_key = f"0:{pair_key}_usd"
                if manual_key in self._manual_prices:
                    reading = DEXPriceReading(
                        chain_id=0, chain_name="Solana",
                        dex=DEXType.ORCA_WHIRLPOOL,
                        pool_address="manual", token_pair=pair_key,
                        price=self._manual_prices[manual_key],
                        price_usd=self._manual_prices[manual_key],
                        source=PriceSource.MANUAL, timestamp=now,
                        confidence=1.0,
                    )
                else:
                    reading = self._read_solana_pool(pair_key, pool_cfg)

                if reading:
                    if "wqusd" in pair_key:
                        sol_state.wqusd_readings.append(reading)
                        sol_state.wqusd_usd = reading.price_usd
                    elif "wqbc" in pair_key:
                        sol_state.wqbc_readings.append(reading)
                        sol_state.wqbc_usd = reading.price_usd

            if sol_state.wqusd_readings or sol_state.wqbc_readings:
                sol_state.healthy = True
            sol_state.last_update = now

        return dict(self._chain_states)

    def get_wqusd_prices(self) -> Dict[int, Optional[Decimal]]:
        """Get wQUSD USD price on every chain.

        Returns:
            Dict mapping chain_id -> wQUSD price (or None if unavailable).
        """
        states = self.fetch_all_prices()
        return {cid: s.wqusd_usd for cid, s in states.items()}

    def get_wqbc_prices(self) -> Dict[int, Optional[Decimal]]:
        """Get wQBC USD price on every chain."""
        states = self.fetch_all_prices()
        return {cid: s.wqbc_usd for cid, s in states.items()}

    def get_max_wqusd_deviation(self) -> Tuple[Decimal, int, str]:
        """Get the maximum wQUSD deviation from $1.00 across all chains.

        Returns:
            (max_deviation, chain_id, chain_name) where deviation = |price - 1.0|
        """
        prices = self.get_wqusd_prices()
        max_dev = Decimal("0")
        max_chain = 0
        max_name = ""
        for cid, price in prices.items():
            if price is None:
                continue
            dev = abs(price - Decimal("1.0"))
            if dev > max_dev:
                max_dev = dev
                max_chain = cid
                state = self._chain_states.get(cid)
                max_name = state.chain_name if state else f"Chain-{cid}"
        return max_dev, max_chain, max_name

    def get_price_spread(self) -> Dict[str, Decimal]:
        """Get price spread (max - min) for wQUSD across all chains.

        Returns:
            Dict with min_price, max_price, spread, spread_pct.
        """
        prices = [p for p in self.get_wqusd_prices().values() if p is not None]
        if not prices:
            return {
                "min_price": Decimal("0"), "max_price": Decimal("0"),
                "spread": Decimal("0"), "spread_pct": Decimal("0"),
            }
        min_p = min(prices)
        max_p = max(prices)
        spread = max_p - min_p
        spread_pct = (spread / min_p * 100) if min_p > 0 else Decimal("0")
        return {
            "min_price": min_p, "max_price": max_p,
            "spread": spread,
            "spread_pct": spread_pct.quantize(Decimal("0.01")),
        }

    def get_status(self) -> Dict[str, object]:
        """Full status for monitoring / RPC endpoint."""
        states = self.fetch_all_prices()
        chains = {}
        for cid, state in states.items():
            chains[state.chain_name] = {
                "chain_id": cid,
                "wqusd_usd": str(state.wqusd_usd) if state.wqusd_usd else None,
                "wqbc_usd": str(state.wqbc_usd) if state.wqbc_usd else None,
                "healthy": state.healthy,
                "error": state.error,
                "last_update": state.last_update,
                "wqusd_readings": len(state.wqusd_readings),
                "wqbc_readings": len(state.wqbc_readings),
            }
        spread = self.get_price_spread()
        dev, dev_chain, dev_name = self.get_max_wqusd_deviation()
        return {
            "chains": chains,
            "spread": {k: str(v) for k, v in spread.items()},
            "max_deviation": str(dev),
            "max_deviation_chain": dev_name,
            "manual_overrides": len(self._manual_prices),
            "cache_ttl": self.CACHE_TTL,
            "twap_window": self.TWAP_WINDOW,
        }
