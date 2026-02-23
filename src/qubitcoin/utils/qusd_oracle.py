"""
QUSD Oracle Client

Reads QBC/USD price from QUSD L2 oracle contract via QVM.
Provides caching, staleness detection, and automatic fallback.

Used by:
  - Aether Tree fee manager (dynamic chat fees)
  - Contract fee calculator (deploy fees)
  - Bridge pricing
  - Dashboard / API endpoints
"""
import time
from decimal import Decimal
from typing import Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class QUSDOracle:
    """Read QBC/USD price from QUSD L2 oracle contract or external feed."""

    def __init__(self, state_manager: Optional[object] = None) -> None:
        """
        Args:
            state_manager: QVM StateManager for calling QUSDOracle.sol.
                           If None, only external price feeds are available.
        """
        self._state = state_manager
        self._cached_price: Optional[Decimal] = None
        self._cache_ts: float = 0.0
        self._cache_ttl: float = 30.0  # seconds
        self._last_block_update: int = 0
        self._oracle_contract: Optional[str] = None
        self._external_price: Optional[Decimal] = None  # manually set price
        self._stale_threshold: float = 600.0  # 10 minutes

    def set_oracle_contract(self, address: str) -> None:
        """Set the QUSDOracle.sol contract address."""
        self._oracle_contract = address
        logger.info(f"QUSD oracle contract set: {address[:16]}...")

    def set_external_price(self, price: Decimal) -> None:
        """Manually set an external QBC/USD price (for direct_usd mode or testing)."""
        if price <= 0:
            raise ValueError("Price must be positive")
        self._external_price = price
        self._cached_price = price
        self._cache_ts = time.time()
        logger.info(f"External QBC/USD price set: {price}")

    def get_qbc_usd_price(self) -> Optional[Decimal]:
        """Get the current QBC/USD price.

        Priority:
        1. Cached price (if fresh)
        2. On-chain QUSD oracle contract
        3. External price feed
        4. None (stale/unavailable)

        Returns:
            QBC price in USD, or None if unavailable.
        """
        now = time.time()

        # Return cache if fresh
        if self._cached_price and (now - self._cache_ts) < self._cache_ttl:
            return self._cached_price

        # Try on-chain oracle
        price = self._read_onchain_price()
        if price and price > 0:
            self._cached_price = price
            self._cache_ts = now
            return price

        # Try external price
        if self._external_price and self._external_price > 0:
            self._cached_price = self._external_price
            self._cache_ts = now
            return self._external_price

        # Stale check — return cached if exists but flag it
        if self._cached_price:
            age = now - self._cache_ts
            if age < self._stale_threshold:
                logger.debug(f"Using stale cached price (age={age:.0f}s)")
                return self._cached_price
            logger.warning(
                f"QUSD oracle price stale ({age:.0f}s > {self._stale_threshold:.0f}s threshold)"
            )

        return None

    def _read_onchain_price(self) -> Optional[Decimal]:
        """Read price from QUSDOracle.sol via QVM state call."""
        if not self._state or not self._oracle_contract:
            return None

        try:
            # Call getPrice() view function on QUSDOracle.sol
            # ABI: function getPrice() external view returns (uint256 price, uint256 timestamp, uint256 feedCount)
            # Selector: keccak256("getPrice()")[:4] = d61a3b92
            selector = bytes.fromhex("d61a3b92")
            result = self._state.call_view(
                self._oracle_contract, selector.hex()
            )
            if result and isinstance(result, (int, float)):
                # Oracle returns price in 18 decimals (wei-style)
                return Decimal(str(result)) / Decimal(10 ** 18)
        except Exception as e:
            logger.debug(f"On-chain oracle read failed: {e}")

        return None

    def is_price_stale(self) -> bool:
        """Check if the cached price is stale."""
        if not self._cached_price:
            return True
        return (time.time() - self._cache_ts) > self._stale_threshold

    def get_status(self) -> dict:
        """Get oracle status for API/monitoring."""
        now = time.time()
        return {
            "price": str(self._cached_price) if self._cached_price else None,
            "cache_age_seconds": round(now - self._cache_ts, 1) if self._cache_ts else None,
            "stale": self.is_price_stale(),
            "oracle_contract": self._oracle_contract,
            "has_external_price": self._external_price is not None,
            "cache_ttl": self._cache_ttl,
            "stale_threshold": self._stale_threshold,
        }

    def update_from_block(self, block_height: int) -> None:
        """Called per block to refresh price at configurable intervals."""
        interval = Config.AETHER_FEE_UPDATE_INTERVAL
        if block_height - self._last_block_update >= interval:
            # Force refresh on next call
            self._cache_ts = 0.0
            self._last_block_update = block_height
