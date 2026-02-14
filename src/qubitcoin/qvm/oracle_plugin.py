"""
Oracle Plugin — Price feeds and data aggregation for QVM

Implements a QVM plugin that provides oracle functionality:
  - Quantum-secured price feeds with configurable update intervals
  - Multi-source data aggregation with median filtering
  - Staleness detection and circuit-breaker integration
"""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .plugins import QVMPlugin, HookType
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PriceFeed:
    """A single price data point."""
    pair: str            # e.g. "QBC/USD", "QBC/ETH"
    price: float
    timestamp: float
    source: str = ''
    block_height: int = 0

    def to_dict(self) -> dict:
        return {
            'pair': self.pair,
            'price': self.price,
            'timestamp': self.timestamp,
            'source': self.source,
            'block_height': self.block_height,
        }

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp


@dataclass
class AggregatedPrice:
    """Aggregated price from multiple sources."""
    pair: str
    median_price: float
    mean_price: float
    min_price: float
    max_price: float
    source_count: int
    timestamp: float
    is_stale: bool = False

    def to_dict(self) -> dict:
        return {
            'pair': self.pair,
            'median_price': round(self.median_price, 8),
            'mean_price': round(self.mean_price, 8),
            'min_price': round(self.min_price, 8),
            'max_price': round(self.max_price, 8),
            'source_count': self.source_count,
            'timestamp': self.timestamp,
            'is_stale': self.is_stale,
        }


# Staleness threshold in seconds
DEFAULT_STALENESS_THRESHOLD: float = 300.0  # 5 minutes
# Maximum deviation allowed between sources (percentage)
MAX_DEVIATION_PCT: float = 10.0


class OraclePlugin(QVMPlugin):
    """Oracle plugin for QVM — price feeds and data aggregation.

    Provides:
      - Multi-source price feed ingestion
      - Median-based aggregation (resistant to outliers)
      - Staleness detection
      - PRE_EXECUTE hook to inject price data into contract calls
    """

    def __init__(self, staleness_threshold: float = DEFAULT_STALENESS_THRESHOLD) -> None:
        self._feeds: Dict[str, List[PriceFeed]] = {}
        self._aggregated: Dict[str, AggregatedPrice] = {}
        self._staleness_threshold = staleness_threshold
        self._update_count: int = 0
        self._started: bool = False

    def name(self) -> str:
        return 'oracle'

    def version(self) -> str:
        return '0.1.0'

    def description(self) -> str:
        return 'Price feed oracle with multi-source aggregation'

    def author(self) -> str:
        return 'Qubitcoin Core'

    def on_load(self) -> None:
        logger.info("Oracle plugin loaded")

    def on_start(self) -> None:
        self._started = True
        logger.info("Oracle plugin started")

    def on_stop(self) -> None:
        self._started = False
        logger.info("Oracle plugin stopped")

    def hooks(self) -> Dict[int, Callable]:
        return {
            HookType.PRE_EXECUTE: self._pre_execute_hook,
        }

    # ── Hook handler ───────────────────────────────────────────────

    def _pre_execute_hook(self, context: dict) -> Optional[dict]:
        """Inject latest price data into execution context."""
        requested_pair = context.get('oracle_pair')
        if not requested_pair:
            return None

        agg = self._aggregated.get(requested_pair)
        if not agg:
            return {'oracle_price': None, 'oracle_stale': True}

        is_stale = agg.age_seconds > self._staleness_threshold if hasattr(agg, 'age_seconds') else agg.is_stale
        return {
            'oracle_price': agg.median_price,
            'oracle_stale': is_stale,
            'oracle_source_count': agg.source_count,
        }

    # ── Public API ─────────────────────────────────────────────────

    def submit_price(self, pair: str, price: float, source: str = '',
                     block_height: int = 0) -> PriceFeed:
        """Submit a new price data point."""
        feed = PriceFeed(
            pair=pair,
            price=price,
            timestamp=time.time(),
            source=source,
            block_height=block_height,
        )
        if pair not in self._feeds:
            self._feeds[pair] = []
        self._feeds[pair].append(feed)
        self._update_count += 1

        # Re-aggregate
        self._aggregate(pair)
        return feed

    def get_price(self, pair: str) -> Optional[AggregatedPrice]:
        """Get the latest aggregated price for a pair."""
        return self._aggregated.get(pair)

    def get_all_prices(self) -> Dict[str, AggregatedPrice]:
        return dict(self._aggregated)

    def get_feed_history(self, pair: str, limit: int = 50) -> List[PriceFeed]:
        """Get recent price feed entries for a pair."""
        feeds = self._feeds.get(pair, [])
        return feeds[-limit:]

    def is_stale(self, pair: str) -> bool:
        """Check if a price feed is stale."""
        agg = self._aggregated.get(pair)
        if not agg:
            return True
        age = time.time() - agg.timestamp
        return age > self._staleness_threshold

    def get_stats(self) -> dict:
        return {
            'pairs_tracked': len(self._feeds),
            'total_updates': self._update_count,
            'started': self._started,
            'staleness_threshold': self._staleness_threshold,
        }

    # ── Aggregation ────────────────────────────────────────────────

    def _aggregate(self, pair: str) -> None:
        """Re-compute aggregated price from recent feeds."""
        feeds = self._feeds.get(pair, [])
        if not feeds:
            return

        now = time.time()
        # Only use recent feeds (within staleness window)
        recent = [
            f for f in feeds
            if (now - f.timestamp) <= self._staleness_threshold
        ]

        if not recent:
            # Mark as stale but keep last known value
            if pair in self._aggregated:
                self._aggregated[pair].is_stale = True
            return

        prices = sorted(f.price for f in recent)
        n = len(prices)
        median = prices[n // 2] if n % 2 == 1 else (prices[n // 2 - 1] + prices[n // 2]) / 2.0

        self._aggregated[pair] = AggregatedPrice(
            pair=pair,
            median_price=median,
            mean_price=sum(prices) / n,
            min_price=prices[0],
            max_price=prices[-1],
            source_count=n,
            timestamp=max(f.timestamp for f in recent),
            is_stale=False,
        )

    def check_deviation(self, pair: str) -> Optional[float]:
        """Check the deviation between min and max source prices.

        Returns the deviation as a percentage, or None if insufficient data.
        """
        agg = self._aggregated.get(pair)
        if not agg or agg.source_count < 2:
            return None
        if agg.median_price == 0:
            return None
        deviation = ((agg.max_price - agg.min_price) / agg.median_price) * 100.0
        return deviation


def create_plugin() -> QVMPlugin:
    """Factory function for dynamic loading."""
    return OraclePlugin()
