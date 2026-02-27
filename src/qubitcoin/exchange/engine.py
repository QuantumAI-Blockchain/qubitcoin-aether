"""
Qubitcoin DEX — Central Limit Order Book (CLOB) Exchange Engine

Price-time priority matching engine for spot trading pairs.
Supports limit orders, market orders, and cancellation.

Architecture:
  - Each trading pair has its own OrderBook instance.
  - Bids sorted descending by price, then ascending by timestamp (best bid first).
  - Asks sorted ascending by price, then ascending by timestamp (best ask first).
  - Market orders execute immediately against resting orders.
  - Limit orders rest in the book if they cannot be fully matched.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Try sortedcontainers for O(log n) insert/remove; fall back to plain list.
# ---------------------------------------------------------------------------
try:
    from sortedcontainers import SortedList as _SortedList
    _HAS_SORTED = True
except ImportError:
    _HAS_SORTED = False
    logger.debug("sortedcontainers not available; using plain list fallback")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(str, Enum):
    OPEN = "open"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"


@dataclass
class Order:
    """A single order on the book."""
    id: str
    pair: str
    side: Side
    order_type: OrderType
    price: float          # 0.0 for market orders
    size: float           # original requested size
    filled: float = 0.0   # amount already filled
    status: OrderStatus = OrderStatus.OPEN
    address: str = ""     # submitter wallet address
    timestamp: float = field(default_factory=time.time)

    @property
    def remaining(self) -> float:
        return self.size - self.filled

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pair": self.pair,
            "side": self.side.value,
            "type": self.order_type.value,
            "price": self.price,
            "size": self.size,
            "filled": self.filled,
            "remaining": self.remaining,
            "status": self.status.value,
            "address": self.address,
            "timestamp": self.timestamp,
        }


@dataclass
class Fill:
    """A single fill (trade) produced when orders match."""
    id: str
    pair: str
    price: float
    size: float
    side: Side            # taker side
    maker_order_id: str
    taker_order_id: str
    maker_address: str
    taker_address: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pair": self.pair,
            "price": self.price,
            "size": self.size,
            "side": self.side.value,
            "maker_order_id": self.maker_order_id,
            "taker_order_id": self.taker_order_id,
            "maker_address": self.maker_address,
            "taker_address": self.taker_address,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Sorted-list wrappers with key functions for bid/ask ordering
# ---------------------------------------------------------------------------

def _bid_key(order: Order) -> Tuple[float, float]:
    """Bids: highest price first, earliest time first (FIFO at same price)."""
    return (-order.price, order.timestamp)


def _ask_key(order: Order) -> Tuple[float, float]:
    """Asks: lowest price first, earliest time first (FIFO at same price)."""
    return (order.price, order.timestamp)


def _make_sorted_list(key_fn):
    """Create a sorted container (SortedList or fallback wrapper)."""
    if _HAS_SORTED:
        return _SortedList(key=key_fn)
    return _FallbackSortedList(key=key_fn)


class _FallbackSortedList:
    """Naive sorted list fallback when sortedcontainers is not installed."""

    def __init__(self, key=None):
        self._items: List[Order] = []
        self._key = key or (lambda x: x)

    def add(self, item: Order) -> None:
        self._items.append(item)
        self._items.sort(key=self._key)

    def remove(self, item: Order) -> None:
        self._items.remove(item)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __getitem__(self, idx):
        return self._items[idx]

    def __bool__(self) -> bool:
        return bool(self._items)


# ---------------------------------------------------------------------------
# OrderBook — single trading pair
# ---------------------------------------------------------------------------

class OrderBook:
    """Price-time priority order book for a single trading pair."""

    MAX_TRADE_HISTORY = 500

    def __init__(self, pair: str) -> None:
        self.pair: str = pair
        self.bids = _make_sorted_list(_bid_key)   # best bid at index 0
        self.asks = _make_sorted_list(_ask_key)   # best ask at index 0
        self._orders: Dict[str, Order] = {}       # id -> Order (for O(1) lookup)
        self._trades: List[Fill] = []             # recent fills

    # ── Limit order ──────────────────────────────────────────────────────

    def place_limit_order(
        self,
        side: str,
        price: float,
        size: float,
        address: str = "",
    ) -> Tuple[Order, List[Fill]]:
        """Place a limit order.  Returns (order, fills).

        The order is immediately matched against resting orders if it crosses
        the spread, then any remaining size rests in the book.
        """
        if price <= 0:
            raise ValueError("Limit order price must be positive")
        if size <= 0:
            raise ValueError("Order size must be positive")

        order = Order(
            id=uuid.uuid4().hex[:16],
            pair=self.pair,
            side=Side(side),
            order_type=OrderType.LIMIT,
            price=price,
            size=size,
            address=address,
        )

        fills = self._match(order)

        # If remaining size, rest in book
        if order.remaining > 1e-12:
            if order.status == OrderStatus.OPEN or order.status == OrderStatus.PARTIAL:
                self._orders[order.id] = order
                if order.side == Side.BUY:
                    self.bids.add(order)
                else:
                    self.asks.add(order)
        else:
            order.status = OrderStatus.FILLED

        logger.debug(
            "Limit %s %s %.8f @ %.8f => %d fills, status=%s",
            side, self.pair, size, price, len(fills), order.status.value,
        )
        return order, fills

    # ── Market order ─────────────────────────────────────────────────────

    def place_market_order(
        self,
        side: str,
        size: float,
        address: str = "",
    ) -> Tuple[Order, List[Fill]]:
        """Place a market order.  Fills immediately or partially.

        Returns (order, fills).  If there is insufficient liquidity the
        unfilled portion is cancelled (market orders never rest).
        """
        if size <= 0:
            raise ValueError("Order size must be positive")

        order = Order(
            id=uuid.uuid4().hex[:16],
            pair=self.pair,
            side=Side(side),
            order_type=OrderType.MARKET,
            price=0.0,
            size=size,
            address=address,
        )

        fills = self._match(order)

        # Market orders never rest — unfilled portion is cancelled
        if order.remaining > 1e-12:
            if order.filled > 0:
                order.status = OrderStatus.PARTIAL
            else:
                order.status = OrderStatus.CANCELLED
        else:
            order.status = OrderStatus.FILLED

        logger.debug(
            "Market %s %s %.8f => %d fills, filled=%.8f, status=%s",
            side, self.pair, size, len(fills), order.filled, order.status.value,
        )
        return order, fills

    # ── Cancel ───────────────────────────────────────────────────────────

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a resting order. Returns True if found and cancelled."""
        order = self._orders.pop(order_id, None)
        if order is None:
            return False

        try:
            if order.side == Side.BUY:
                self.bids.remove(order)
            else:
                self.asks.remove(order)
        except ValueError:
            pass  # already removed (edge case)

        order.status = OrderStatus.CANCELLED
        logger.debug("Cancelled order %s on %s", order_id, self.pair)
        return True

    # ── Matching engine (private) ────────────────────────────────────────

    def _match(self, taker: Order) -> List[Fill]:
        """Match a taker order against the opposite side of the book.

        Uses price-time priority.  For limit orders, only matches at prices
        that are equal or better than the limit price.  For market orders,
        matches at any available price.
        """
        fills: List[Fill] = []
        opposite = self.asks if taker.side == Side.BUY else self.bids

        while opposite and taker.remaining > 1e-12:
            maker = opposite[0]

            # Price check for limit orders
            if taker.order_type == OrderType.LIMIT:
                if taker.side == Side.BUY and maker.price > taker.price:
                    break  # best ask is above our bid limit
                if taker.side == Side.SELL and maker.price < taker.price:
                    break  # best bid is below our ask limit

            # Determine fill quantity at the maker's (resting) price
            fill_size = min(taker.remaining, maker.remaining)
            fill_price = maker.price

            # Execute fill
            taker.filled += fill_size
            maker.filled += fill_size

            fill = Fill(
                id=uuid.uuid4().hex[:16],
                pair=self.pair,
                price=fill_price,
                size=fill_size,
                side=taker.side,
                maker_order_id=maker.id,
                taker_order_id=taker.id,
                maker_address=maker.address,
                taker_address=taker.address,
            )
            fills.append(fill)
            self._trades.insert(0, fill)

            # Trim trade history
            if len(self._trades) > self.MAX_TRADE_HISTORY:
                self._trades = self._trades[: self.MAX_TRADE_HISTORY]

            # Update maker status
            if maker.remaining <= 1e-12:
                maker.status = OrderStatus.FILLED
                opposite.remove(maker)
                self._orders.pop(maker.id, None)
            else:
                maker.status = OrderStatus.PARTIAL

        # Update taker status
        if taker.filled > 0 and taker.remaining > 1e-12:
            taker.status = OrderStatus.PARTIAL
        elif taker.filled > 0:
            taker.status = OrderStatus.FILLED

        return fills

    # ── Queries ──────────────────────────────────────────────────────────

    def get_orderbook(self, depth: int = 20) -> dict:
        """Return order book snapshot with aggregated levels."""
        bid_levels = self._aggregate_levels(self.bids, depth, is_bid=True)
        ask_levels = self._aggregate_levels(self.asks, depth, is_bid=False)

        best_bid = bid_levels[0]["price"] if bid_levels else 0.0
        best_ask = ask_levels[0]["price"] if ask_levels else 0.0
        spread = best_ask - best_bid if best_bid > 0 and best_ask > 0 else 0.0
        mid = (best_ask + best_bid) / 2 if best_bid > 0 and best_ask > 0 else 0.0

        return {
            "pair": self.pair,
            "bids": bid_levels,
            "asks": ask_levels,
            "spread": round(spread, 10),
            "spreadPct": round((spread / mid) * 100, 6) if mid > 0 else 0.0,
            "midPrice": round(mid, 10),
            "updatedAt": time.time(),
        }

    def _aggregate_levels(
        self, side_list, depth: int, is_bid: bool
    ) -> List[dict]:
        """Aggregate individual orders into price levels."""
        levels: Dict[float, float] = {}
        order_counts: Dict[float, int] = {}

        for order in side_list:
            p = order.price
            levels[p] = levels.get(p, 0.0) + order.remaining
            order_counts[p] = order_counts.get(p, 0) + 1

        # Sort: bids descending, asks ascending
        sorted_prices = sorted(levels.keys(), reverse=is_bid)[:depth]

        result = []
        cumulative = 0.0
        for price in sorted_prices:
            size = levels[price]
            cumulative += size
            result.append({
                "price": price,
                "size": round(size, 8),
                "total": round(cumulative, 8),
                "orderCount": order_counts.get(price, 0),
            })
        return result

    def get_recent_trades(self, limit: int = 50) -> List[dict]:
        """Return recent trades for this pair."""
        return [t.to_dict() for t in self._trades[:limit]]

    def get_open_orders(self, address: Optional[str] = None) -> List[dict]:
        """Return open/partial orders, optionally filtered by address."""
        orders = list(self._orders.values())
        if address:
            orders = [o for o in orders if o.address == address]
        return [o.to_dict() for o in orders]

    def get_stats(self) -> dict:
        """Return pair-level statistics (24h approximation from trade history)."""
        now = time.time()
        cutoff = now - 86400  # 24h

        recent = [t for t in self._trades if t.timestamp >= cutoff]
        if not recent:
            return {
                "pair": self.pair,
                "lastPrice": 0.0,
                "change24h": 0.0,
                "volume24h": 0.0,
                "high24h": 0.0,
                "low24h": 0.0,
                "tradeCount24h": 0,
                "bidCount": len(self.bids),
                "askCount": len(self.asks),
            }

        prices = [t.price for t in recent]
        volumes = [t.size * t.price for t in recent]
        last_price = recent[0].price
        first_price = recent[-1].price
        change = ((last_price - first_price) / first_price * 100) if first_price > 0 else 0.0

        return {
            "pair": self.pair,
            "lastPrice": last_price,
            "change24h": round(change, 4),
            "volume24h": round(sum(volumes), 4),
            "high24h": max(prices),
            "low24h": min(prices),
            "tradeCount24h": len(recent),
            "bidCount": len(self.bids),
            "askCount": len(self.asks),
        }


# ---------------------------------------------------------------------------
# ExchangeEngine — multi-pair orchestrator
# ---------------------------------------------------------------------------

class ExchangeEngine:
    """Multi-pair exchange engine.

    Manages a collection of OrderBook instances, one per trading pair.
    Provides a unified API for placing orders, querying order books,
    and retrieving market data.
    """

    # Default trading pairs seeded at startup
    DEFAULT_PAIRS: List[str] = [
        "QBC_QUSD",
        "WETH_QUSD",
        "WBNB_QUSD",
        "WSOL_QUSD",
        "WQBC_QUSD",
    ]

    def __init__(self) -> None:
        self.books: Dict[str, OrderBook] = {}
        self._user_balances: Dict[str, Dict[str, float]] = {}  # address -> {asset: amount}

        # Pre-create default order books
        for pair in self.DEFAULT_PAIRS:
            self.get_or_create_book(pair)

        logger.info(
            "ExchangeEngine initialized with %d default pairs", len(self.DEFAULT_PAIRS)
        )

    # ── Book management ──────────────────────────────────────────────────

    def get_or_create_book(self, pair: str) -> OrderBook:
        """Get existing order book or create a new one for the pair."""
        if pair not in self.books:
            self.books[pair] = OrderBook(pair)
            logger.info("Created order book for pair %s", pair)
        return self.books[pair]

    # ── Order placement ──────────────────────────────────────────────────

    def place_order(
        self,
        pair: str,
        side: str,
        order_type: str,
        price: float,
        size: float,
        address: str = "",
    ) -> dict:
        """Place an order on the given pair.

        Returns a dict with the order details and any fills produced.
        """
        book = self.get_or_create_book(pair)

        if order_type == "market":
            order, fills = book.place_market_order(side, size, address)
        elif order_type == "limit":
            order, fills = book.place_limit_order(side, price, size, address)
        else:
            raise ValueError(f"Unsupported order type: {order_type}")

        return {
            "order": order.to_dict(),
            "fills": [f.to_dict() for f in fills],
            "fillCount": len(fills),
        }

    # ── Cancel ───────────────────────────────────────────────────────────

    def cancel_order(self, pair: str, order_id: str) -> bool:
        """Cancel an order on the given pair."""
        book = self.books.get(pair)
        if not book:
            return False
        return book.cancel_order(order_id)

    def cancel_order_any_pair(self, order_id: str) -> bool:
        """Search all books for the order and cancel it."""
        for book in self.books.values():
            if book.cancel_order(order_id):
                return True
        return False

    # ── Queries ──────────────────────────────────────────────────────────

    def get_markets(self) -> List[dict]:
        """Return summary stats for all active trading pairs."""
        return [book.get_stats() for book in self.books.values()]

    def get_orderbook(self, pair: str, depth: int = 20) -> dict:
        """Return the order book for a given pair."""
        book = self.books.get(pair)
        if not book:
            return {"pair": pair, "bids": [], "asks": [], "spread": 0, "spreadPct": 0, "midPrice": 0, "updatedAt": time.time()}
        return book.get_orderbook(depth)

    def get_recent_trades(self, pair: str, limit: int = 50) -> List[dict]:
        """Return recent trades for a given pair."""
        book = self.books.get(pair)
        if not book:
            return []
        return book.get_recent_trades(limit)

    def get_user_orders(self, address: str) -> List[dict]:
        """Return all open orders for a user across all pairs."""
        result = []
        for book in self.books.values():
            result.extend(book.get_open_orders(address))
        return result

    # ── Balance management (exchange-internal balances) ───────────────────

    def deposit(self, address: str, asset: str, amount: float) -> dict:
        """Credit exchange balance for a user (called after on-chain deposit confirmation)."""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        if address not in self._user_balances:
            self._user_balances[address] = {}
        current = self._user_balances[address].get(asset, 0.0)
        self._user_balances[address][asset] = current + amount
        logger.info("Deposit %.8f %s for %s", amount, asset, address[:16])
        return self.get_user_balance(address)

    def withdraw(self, address: str, asset: str, amount: float) -> dict:
        """Debit exchange balance for a user (initiates on-chain withdrawal)."""
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        balances = self._user_balances.get(address, {})
        current = balances.get(asset, 0.0)
        if current < amount:
            raise ValueError(f"Insufficient {asset} balance: have {current}, need {amount}")
        self._user_balances[address][asset] = current - amount
        logger.info("Withdraw %.8f %s for %s", amount, asset, address[:16])
        return self.get_user_balance(address)

    def get_user_balance(self, address: str) -> dict:
        """Return exchange balances for a user."""
        balances = self._user_balances.get(address, {})
        result = []
        for asset, total in balances.items():
            # Calculate locked-in-orders amount
            in_orders = 0.0
            for book in self.books.values():
                for order in book.get_open_orders(address):
                    # Buy orders lock quote asset, sell orders lock base asset
                    base, quote = book.pair.split("_", 1) if "_" in book.pair else (book.pair, "QUSD")
                    if order["side"] == "buy" and asset == quote:
                        in_orders += order["remaining"] * order["price"]
                    elif order["side"] == "sell" and asset == base:
                        in_orders += order["remaining"]

            result.append({
                "asset": asset,
                "total": round(total, 8),
                "available": round(total - in_orders, 8),
                "inOrders": round(in_orders, 8),
            })

        return {"address": address, "balances": result}

    def get_engine_stats(self) -> dict:
        """Return overall engine statistics."""
        total_bids = sum(len(b.bids) for b in self.books.values())
        total_asks = sum(len(b.asks) for b in self.books.values())
        total_trades = sum(len(b._trades) for b in self.books.values())
        return {
            "pairs": len(self.books),
            "pair_list": list(self.books.keys()),
            "total_bid_orders": total_bids,
            "total_ask_orders": total_asks,
            "total_trades": total_trades,
            "total_users": len(self._user_balances),
        }
