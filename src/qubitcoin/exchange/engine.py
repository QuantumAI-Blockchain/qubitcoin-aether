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
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

# Decimal precision context: 18 digits matches Ethereum wei precision
ZERO = Decimal("0")
EPSILON = Decimal("1E-12")  # minimum meaningful amount

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
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"


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
    price: Decimal        # Decimal("0") for market orders
    size: Decimal         # original requested size
    filled: Decimal = field(default_factory=lambda: ZERO)
    status: OrderStatus = OrderStatus.OPEN
    address: str = ""     # submitter wallet address
    timestamp: float = field(default_factory=time.time)
    trigger_price: Optional[Decimal] = None  # stop orders: activate when market hits this price

    @property
    def remaining(self) -> Decimal:
        return self.size - self.filled

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "pair": self.pair,
            "side": self.side.value,
            "type": self.order_type.value,
            "price": str(self.price),
            "size": str(self.size),
            "filled": str(self.filled),
            "remaining": str(self.remaining),
            "status": self.status.value,
            "address": self.address,
            "timestamp": self.timestamp,
        }
        if self.trigger_price is not None:
            d["trigger_price"] = str(self.trigger_price)
        return d


@dataclass
class Fill:
    """A single fill (trade) produced when orders match."""
    id: str
    pair: str
    price: Decimal
    size: Decimal
    side: Side            # taker side
    maker_order_id: str
    taker_order_id: str
    maker_address: str
    taker_address: str
    timestamp: float = field(default_factory=time.time)
    maker_fee: Decimal = ZERO
    taker_fee: Decimal = ZERO
    fee_asset: str = "QBC"

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "pair": self.pair,
            "price": str(self.price),
            "size": str(self.size),
            "side": self.side.value,
            "maker_order_id": self.maker_order_id,
            "taker_order_id": self.taker_order_id,
            "maker_address": self.maker_address,
            "taker_address": self.taker_address,
            "timestamp": self.timestamp,
        }
        if self.maker_fee > ZERO or self.taker_fee > ZERO:
            d["maker_fee"] = str(self.maker_fee)
            d["taker_fee"] = str(self.taker_fee)
            d["fee_asset"] = self.fee_asset
        return d


# ---------------------------------------------------------------------------
# Sorted-list wrappers with key functions for bid/ask ordering
# ---------------------------------------------------------------------------

def _bid_key(order: Order) -> Tuple[Decimal, float]:
    """Bids: highest price first, earliest time first (FIFO at same price)."""
    return (-order.price, order.timestamp)


def _ask_key(order: Order) -> Tuple[Decimal, float]:
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
        self._stop_orders: Dict[str, Order] = {}  # id -> pending stop orders

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
        d_price = Decimal(str(price))
        d_size = Decimal(str(size))
        if d_price <= ZERO:
            raise ValueError("Limit order price must be positive")
        if d_size <= ZERO:
            raise ValueError("Order size must be positive")

        order = Order(
            id=uuid.uuid4().hex[:16],
            pair=self.pair,
            side=Side(side),
            order_type=OrderType.LIMIT,
            price=d_price,
            size=d_size,
            address=address,
        )

        fills = self._match(order)

        # If remaining size, rest in book
        if order.remaining > EPSILON:
            if order.status == OrderStatus.OPEN or order.status == OrderStatus.PARTIAL:
                self._orders[order.id] = order
                if order.side == Side.BUY:
                    self.bids.add(order)
                else:
                    self.asks.add(order)
        else:
            order.status = OrderStatus.FILLED

        logger.debug(
            "Limit %s %s %s @ %s => %d fills, status=%s",
            side, self.pair, d_size, d_price, len(fills), order.status.value,
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
        d_size = Decimal(str(size))
        if d_size <= ZERO:
            raise ValueError("Order size must be positive")

        order = Order(
            id=uuid.uuid4().hex[:16],
            pair=self.pair,
            side=Side(side),
            order_type=OrderType.MARKET,
            price=ZERO,
            size=d_size,
            address=address,
        )

        fills = self._match(order)

        # Market orders never rest — unfilled portion is cancelled
        if order.remaining > EPSILON:
            if order.filled > ZERO:
                order.status = OrderStatus.PARTIAL
            else:
                order.status = OrderStatus.CANCELLED
        else:
            order.status = OrderStatus.FILLED

        logger.debug(
            "Market %s %s %s => %d fills, filled=%s, status=%s",
            side, self.pair, d_size, len(fills), order.filled, order.status.value,
        )
        return order, fills

    # ── Stop orders ──────────────────────────────────────────────────────

    def place_stop_loss_order(
        self,
        side: str,
        trigger_price: float,
        size: float,
        address: str = "",
    ) -> Order:
        """Place a stop-loss order.

        When the market price crosses the trigger price, the stop order
        converts to a market order and executes immediately.
        Returns the pending stop order (no fills until triggered).
        """
        d_trigger = Decimal(str(trigger_price))
        d_size = Decimal(str(size))
        if d_trigger <= ZERO:
            raise ValueError("Trigger price must be positive")
        if d_size <= ZERO:
            raise ValueError("Order size must be positive")

        order = Order(
            id=uuid.uuid4().hex[:16],
            pair=self.pair,
            side=Side(side),
            order_type=OrderType.STOP_LOSS,
            price=ZERO,
            size=d_size,
            address=address,
            trigger_price=d_trigger,
        )
        self._stop_orders[order.id] = order
        logger.debug(
            "Stop-loss %s %s %s trigger@%s", side, self.pair, d_size, d_trigger
        )
        return order

    def place_stop_limit_order(
        self,
        side: str,
        trigger_price: float,
        limit_price: float,
        size: float,
        address: str = "",
    ) -> Order:
        """Place a stop-limit order.

        When the market price crosses the trigger price, the stop order
        converts to a limit order at the specified limit price.
        Returns the pending stop order (no fills until triggered).
        """
        d_trigger = Decimal(str(trigger_price))
        d_limit = Decimal(str(limit_price))
        d_size = Decimal(str(size))
        if d_trigger <= ZERO:
            raise ValueError("Trigger price must be positive")
        if d_limit <= ZERO:
            raise ValueError("Limit price must be positive")
        if d_size <= ZERO:
            raise ValueError("Order size must be positive")

        order = Order(
            id=uuid.uuid4().hex[:16],
            pair=self.pair,
            side=Side(side),
            order_type=OrderType.STOP_LIMIT,
            price=d_limit,
            size=d_size,
            address=address,
            trigger_price=d_trigger,
        )
        self._stop_orders[order.id] = order
        logger.debug(
            "Stop-limit %s %s %s trigger@%s limit@%s",
            side, self.pair, d_size, d_trigger, d_limit,
        )
        return order

    def check_triggers(self, last_trade_price: Decimal) -> List[Tuple[Order, List[Fill]]]:
        """Check if any stop orders should be triggered by the current market price.

        Call this after every trade. Returns list of (order, fills) for triggered orders.

        Stop-loss sell triggers when price <= trigger_price.
        Stop-loss buy triggers when price >= trigger_price.
        """
        triggered: List[Tuple[Order, List[Fill]]] = []
        to_remove: List[str] = []

        for order_id, order in self._stop_orders.items():
            should_trigger = False

            if order.side == Side.SELL:
                # Sell stop: triggers when price falls to/below trigger
                if last_trade_price <= order.trigger_price:
                    should_trigger = True
            else:
                # Buy stop: triggers when price rises to/above trigger
                if last_trade_price >= order.trigger_price:
                    should_trigger = True

            if should_trigger:
                to_remove.append(order_id)
                if order.order_type == OrderType.STOP_LOSS:
                    # Convert to market order
                    _, fills = self.place_market_order(
                        order.side.value, float(order.size), order.address
                    )
                else:
                    # Convert to limit order at the limit price
                    _, fills = self.place_limit_order(
                        order.side.value, float(order.price), float(order.size), order.address
                    )
                order.status = OrderStatus.FILLED if fills else OrderStatus.OPEN
                triggered.append((order, fills))
                logger.info(
                    "Triggered stop order %s (%s) at price %s",
                    order_id, order.order_type.value, last_trade_price,
                )

        for oid in to_remove:
            del self._stop_orders[oid]

        return triggered

    def cancel_stop_order(self, order_id: str) -> bool:
        """Cancel a pending stop order."""
        order = self._stop_orders.pop(order_id, None)
        if order is None:
            return False
        order.status = OrderStatus.CANCELLED
        return True

    # ── Cancel ───────────────────────────────────────────────────────────

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a resting or stop order. Returns True if found and cancelled."""
        # Check stop orders first
        if order_id in self._stop_orders:
            return self.cancel_stop_order(order_id)

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

        while opposite and taker.remaining > EPSILON:
            maker = opposite[0]

            # Self-trade prevention: skip orders from the same address
            if maker.address and taker.address and maker.address == taker.address:
                break

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
            if maker.remaining <= EPSILON:
                maker.status = OrderStatus.FILLED
                opposite.remove(maker)
                self._orders.pop(maker.id, None)
            else:
                maker.status = OrderStatus.PARTIAL

        # Update taker status
        if taker.filled > ZERO and taker.remaining > EPSILON:
            taker.status = OrderStatus.PARTIAL
        elif taker.filled > ZERO:
            taker.status = OrderStatus.FILLED

        return fills

    # ── Queries ──────────────────────────────────────────────────────────

    def get_orderbook(self, depth: int = 20) -> dict:
        """Return order book snapshot with aggregated levels."""
        bid_levels = self._aggregate_levels(self.bids, depth, is_bid=True)
        ask_levels = self._aggregate_levels(self.asks, depth, is_bid=False)

        best_bid = Decimal(bid_levels[0]["price"]) if bid_levels else ZERO
        best_ask = Decimal(ask_levels[0]["price"]) if ask_levels else ZERO
        spread = best_ask - best_bid if best_bid > ZERO and best_ask > ZERO else ZERO
        mid = (best_ask + best_bid) / 2 if best_bid > ZERO and best_ask > ZERO else ZERO

        return {
            "pair": self.pair,
            "bids": bid_levels,
            "asks": ask_levels,
            "spread": str(spread),
            "spreadPct": str((spread / mid * 100).quantize(Decimal("0.000001"))) if mid > ZERO else "0",
            "midPrice": str(mid),
            "updatedAt": time.time(),
        }

    def _aggregate_levels(
        self, side_list, depth: int, is_bid: bool
    ) -> List[dict]:
        """Aggregate individual orders into price levels."""
        levels: Dict[Decimal, Decimal] = {}
        order_counts: Dict[Decimal, int] = {}

        for order in side_list:
            p = order.price
            levels[p] = levels.get(p, ZERO) + order.remaining
            order_counts[p] = order_counts.get(p, 0) + 1

        # Sort: bids descending, asks ascending
        sorted_prices = sorted(levels.keys(), reverse=is_bid)[:depth]

        result = []
        cumulative = ZERO
        for price in sorted_prices:
            size = levels[price]
            cumulative += size
            result.append({
                "price": str(price),
                "size": str(size.quantize(Decimal("0.00000001"))),
                "total": str(cumulative.quantize(Decimal("0.00000001"))),
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
                "lastPrice": "0",
                "change24h": "0",
                "volume24h": "0",
                "high24h": "0",
                "low24h": "0",
                "tradeCount24h": 0,
                "bidCount": len(self.bids),
                "askCount": len(self.asks),
            }

        prices = [t.price for t in recent]
        volumes = [t.size * t.price for t in recent]
        last_price = recent[0].price
        first_price = recent[-1].price
        change = ((last_price - first_price) / first_price * 100) if first_price > ZERO else ZERO

        return {
            "pair": self.pair,
            "lastPrice": str(last_price),
            "change24h": str(change.quantize(Decimal("0.0001"))),
            "volume24h": str(sum(volumes).quantize(Decimal("0.0001"))),
            "high24h": str(max(prices)),
            "low24h": str(min(prices)),
            "tradeCount24h": len(recent),
            "bidCount": len(self.bids),
            "askCount": len(self.asks),
        }


# ---------------------------------------------------------------------------
# ExchangeEngine — multi-pair orchestrator
# ---------------------------------------------------------------------------

class OrderPersistence:
    """Interface for persisting order book state to a database.

    Subclass this and pass to ExchangeEngine to survive node restarts.
    """

    def save_order(self, pair: str, order: 'Order') -> None:
        """Save or update an order."""
        raise NotImplementedError

    def delete_order(self, pair: str, order_id: str) -> None:
        """Remove an order from persistence."""
        raise NotImplementedError

    def save_fill(self, pair: str, fill: 'Fill') -> None:
        """Persist a fill/trade record."""
        raise NotImplementedError

    def load_orders(self, pair: str) -> List['Order']:
        """Load all open/partial orders for a pair on startup."""
        raise NotImplementedError

    def load_fills(self, pair: str, limit: int = 500) -> List['Fill']:
        """Load recent fills for a pair on startup."""
        raise NotImplementedError


class InMemoryPersistence(OrderPersistence):
    """In-memory persistence for testing — stores data in dicts."""

    def __init__(self) -> None:
        self._orders: Dict[str, Dict[str, dict]] = {}  # pair -> {id -> order_dict}
        self._fills: Dict[str, List[dict]] = {}         # pair -> [fill_dicts]

    def save_order(self, pair: str, order: 'Order') -> None:
        if pair not in self._orders:
            self._orders[pair] = {}
        self._orders[pair][order.id] = order.to_dict()

    def delete_order(self, pair: str, order_id: str) -> None:
        if pair in self._orders:
            self._orders[pair].pop(order_id, None)

    def save_fill(self, pair: str, fill: 'Fill') -> None:
        if pair not in self._fills:
            self._fills[pair] = []
        self._fills[pair].insert(0, fill.to_dict())

    def load_orders(self, pair: str) -> List['Order']:
        return []  # In-memory starts fresh

    def load_fills(self, pair: str, limit: int = 500) -> List['Fill']:
        return []

    def get_saved_orders(self, pair: str) -> List[dict]:
        """Test helper: return saved order dicts."""
        return list(self._orders.get(pair, {}).values())

    def get_saved_fills(self, pair: str) -> List[dict]:
        """Test helper: return saved fill dicts."""
        return list(self._fills.get(pair, []))


class DatabasePersistence(OrderPersistence):
    """Database-backed persistence using SQLAlchemy sessions.

    Persists orders and fills to CockroachDB so the order book
    survives node restarts.
    """

    def __init__(self, db_manager: 'DatabaseManager') -> None:
        self._db = db_manager

    def save_order(self, pair: str, order: 'Order') -> None:
        from sqlalchemy import text
        with self._db.get_session() as session:
            session.execute(
                text("""
                    INSERT INTO exchange_orders (order_id, pair, side, order_type, price, size, filled, status, owner, created_at)
                    VALUES (:oid, :pair, :side, :otype, :price, :size, :filled, :status, :owner, to_timestamp(:ts))
                    ON CONFLICT (order_id) DO UPDATE SET
                        filled = :filled, status = :status
                """),
                {
                    'oid': order.id, 'pair': pair, 'side': order.side.value,
                    'otype': order.order_type.value, 'price': str(order.price),
                    'size': str(order.size), 'filled': str(order.filled),
                    'status': order.status.value, 'owner': order.address,
                    'ts': order.timestamp,
                },
            )
            session.commit()

    def delete_order(self, pair: str, order_id: str) -> None:
        from sqlalchemy import text
        with self._db.get_session() as session:
            session.execute(
                text("DELETE FROM exchange_orders WHERE order_id = :oid"),
                {'oid': order_id},
            )
            session.commit()

    def save_fill(self, pair: str, fill: 'Fill') -> None:
        from sqlalchemy import text
        with self._db.get_session() as session:
            session.execute(
                text("""
                    INSERT INTO exchange_fills (fill_id, pair, price, size, side, maker_order_id, taker_order_id, maker_address, taker_address, timestamp)
                    VALUES (:fid, :pair, :price, :size, :side, :moid, :toid, :maddr, :taddr, to_timestamp(:ts))
                    ON CONFLICT (fill_id) DO NOTHING
                """),
                {
                    'fid': fill.id, 'pair': pair, 'price': str(fill.price),
                    'size': str(fill.size), 'side': fill.side.value,
                    'moid': fill.maker_order_id, 'toid': fill.taker_order_id,
                    'maddr': fill.maker_address, 'taddr': fill.taker_address,
                    'ts': fill.timestamp,
                },
            )
            session.commit()

    def load_orders(self, pair: str) -> List['Order']:
        return []  # Orders are loaded from DB on demand; fresh start

    def load_fills(self, pair: str, limit: int = 500) -> List['Fill']:
        return []  # Fills are loaded from DB on demand; fresh start


class SettlementCallback:
    """Interface for on-chain settlement of matched trades.

    Subclass this and pass to ExchangeEngine to create blockchain
    transactions for every matched fill.
    """

    def settle_fill(self, fill: Fill) -> bool:
        """Called for each matched fill to create an on-chain transaction.

        Args:
            fill: The fill to settle on-chain.

        Returns:
            True if settlement succeeded, False otherwise.
        """
        raise NotImplementedError

    def settle_batch(self, fills: List[Fill]) -> int:
        """Settle multiple fills in a single batch transaction.

        Returns the number of successfully settled fills.
        Default implementation settles one at a time.
        """
        settled = 0
        for fill in fills:
            if self.settle_fill(fill):
                settled += 1
        return settled


class UTXOSettlement(SettlementCallback):
    """Settlement callback that creates UTXO transactions for each trade.

    Requires a reference to the node's transaction creation function.
    """

    def __init__(self, create_transaction_fn=None) -> None:
        self._create_tx = create_transaction_fn
        self._pending: List[dict] = []  # pending settlement records

    def settle_fill(self, fill: Fill) -> bool:
        """Create a UTXO transaction for a matched trade."""
        record = {
            "fill_id": fill.id,
            "pair": fill.pair,
            "price": str(fill.price),
            "size": str(fill.size),
            "side": fill.side.value,
            "maker": fill.maker_address,
            "taker": fill.taker_address,
            "timestamp": fill.timestamp,
            "settled": False,
        }

        if self._create_tx is not None:
            try:
                # Determine transfer: taker pays base asset, receives quote (or vice versa)
                base, quote = fill.pair.split("_", 1) if "_" in fill.pair else (fill.pair, "QUSD")
                notional = fill.price * fill.size  # quote amount

                if fill.side == Side.BUY:
                    # Taker bought base: taker sends quote to maker, maker sends base to taker
                    self._create_tx(fill.taker_address, fill.maker_address, notional, quote)
                    self._create_tx(fill.maker_address, fill.taker_address, fill.size, base)
                else:
                    # Taker sold base: taker sends base to maker, maker sends quote to taker
                    self._create_tx(fill.taker_address, fill.maker_address, fill.size, base)
                    self._create_tx(fill.maker_address, fill.taker_address, notional, quote)

                record["settled"] = True
                logger.info("Settled fill %s on-chain: %s %s @ %s",
                            fill.id, fill.size, base, fill.price)
            except Exception as e:
                logger.error("Settlement failed for fill %s: %s", fill.id, e)
                record["error"] = str(e)
        else:
            logger.debug("No settlement backend — fill %s recorded but not settled", fill.id)

        self._pending.append(record)
        return record["settled"]

    def get_pending_settlements(self) -> List[dict]:
        """Return all settlement records."""
        return list(self._pending)

    def get_unsettled(self) -> List[dict]:
        """Return settlements that failed or have no backend."""
        return [r for r in self._pending if not r["settled"]]


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

    # Default fee rates (configurable)
    DEFAULT_MAKER_FEE: Decimal = Decimal('0.001')   # 0.1%
    DEFAULT_TAKER_FEE: Decimal = Decimal('0.002')   # 0.2%

    def __init__(
        self,
        settlement: Optional[SettlementCallback] = None,
        persistence: Optional[OrderPersistence] = None,
        mev_protection: bool = False,
        commit_reveal_fn=None,
        maker_fee: Optional[Decimal] = None,
        taker_fee: Optional[Decimal] = None,
        fee_treasury: str = "",
    ) -> None:
        self.books: Dict[str, OrderBook] = {}
        self._user_balances: Dict[str, Dict[str, Decimal]] = {}  # address -> {asset: amount}
        self._settlement = settlement
        self._persistence = persistence
        self._mev_protection = mev_protection
        self._commit_reveal_fn = commit_reveal_fn  # callable(order_dict) -> commit_hash
        self._committed_orders: Dict[str, dict] = {}  # commit_hash -> order_dict

        # Fee configuration
        self._maker_fee = maker_fee if maker_fee is not None else self.DEFAULT_MAKER_FEE
        self._taker_fee = taker_fee if taker_fee is not None else self.DEFAULT_TAKER_FEE
        self._fee_treasury = fee_treasury
        self._total_fees_collected: Decimal = ZERO

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
        trigger_price: float = 0,
    ) -> dict:
        """Place an order on the given pair.

        Returns a dict with the order details and any fills produced.
        For stop orders, fills will be empty until the trigger price is hit.
        """
        book = self.get_or_create_book(pair)

        if order_type == "market":
            order, fills = book.place_market_order(side, size, address)
        elif order_type == "limit":
            order, fills = book.place_limit_order(side, price, size, address)
        elif order_type == "stop_loss":
            order = book.place_stop_loss_order(side, trigger_price, size, address)
            fills = []
        elif order_type == "stop_limit":
            order = book.place_stop_limit_order(side, trigger_price, price, size, address)
            fills = []
        else:
            raise ValueError(f"Unsupported order type: {order_type}")

        # Check if any stop orders should trigger after a fill
        if fills:
            last_price = fills[-1].price
            triggered = book.check_triggers(last_price)
            for trig_order, trig_fills in triggered:
                fills.extend(trig_fills)

        # Calculate and apply fees to fills
        if fills and (self._maker_fee > ZERO or self._taker_fee > ZERO):
            for fill in fills:
                notional = fill.price * fill.size
                fill.maker_fee = notional * self._maker_fee
                fill.taker_fee = notional * self._taker_fee
                self._total_fees_collected += fill.maker_fee + fill.taker_fee

        # Settle fills on-chain
        if fills and self._settlement:
            self._settlement.settle_batch(fills)

        # Persist order and fills
        if self._persistence:
            self._persistence.save_order(pair, order)
            for fill in fills:
                self._persistence.save_fill(pair, fill)

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
        d_amount = Decimal(str(amount))
        if d_amount <= ZERO:
            raise ValueError("Deposit amount must be positive")
        if address not in self._user_balances:
            self._user_balances[address] = {}
        current = self._user_balances[address].get(asset, ZERO)
        self._user_balances[address][asset] = current + d_amount
        logger.info("Deposit %s %s for %s", d_amount, asset, address[:16])
        return self.get_user_balance(address)

    def withdraw(self, address: str, asset: str, amount: float) -> dict:
        """Debit exchange balance for a user (initiates on-chain withdrawal)."""
        d_amount = Decimal(str(amount))
        if d_amount <= ZERO:
            raise ValueError("Withdrawal amount must be positive")
        balances = self._user_balances.get(address, {})
        current = balances.get(asset, ZERO)
        if current < d_amount:
            raise ValueError(f"Insufficient {asset} balance: have {current}, need {d_amount}")
        self._user_balances[address][asset] = current - d_amount
        logger.info("Withdraw %s %s for %s", d_amount, asset, address[:16])
        return self.get_user_balance(address)

    def get_user_balance(self, address: str) -> dict:
        """Return exchange balances for a user."""
        balances = self._user_balances.get(address, {})
        result = []
        for asset, total in balances.items():
            # Calculate locked-in-orders amount
            in_orders = ZERO
            for book in self.books.values():
                for order in book.get_open_orders(address):
                    # Buy orders lock quote asset, sell orders lock base asset
                    base, quote = book.pair.split("_", 1) if "_" in book.pair else (book.pair, "QUSD")
                    if order["side"] == "buy" and asset == quote:
                        in_orders += Decimal(order["remaining"]) * Decimal(order["price"])
                    elif order["side"] == "sell" and asset == base:
                        in_orders += Decimal(order["remaining"])

            result.append({
                "asset": asset,
                "total": str(total.quantize(Decimal("0.00000001"))),
                "available": str((total - in_orders).quantize(Decimal("0.00000001"))),
                "inOrders": str(in_orders.quantize(Decimal("0.00000001"))),
            })

        return {"address": address, "balances": result}

    # ── MEV Protection ─────────────────────────────────────────────────

    def commit_order(self, order_dict: dict) -> Optional[str]:
        """Phase 1 of commit-reveal: commit an order hash without revealing details.

        Returns a commit hash that must be revealed within the reveal window.
        Only effective when mev_protection=True and commit_reveal_fn is set.
        """
        if not self._mev_protection:
            return None

        import hashlib
        import json
        order_json = json.dumps(order_dict, sort_keys=True, default=str)
        commit_hash = hashlib.sha256(order_json.encode()).hexdigest()

        self._committed_orders[commit_hash] = order_dict

        if self._commit_reveal_fn:
            self._commit_reveal_fn(commit_hash)

        logger.debug("MEV commit: %s for %s order", commit_hash[:16], order_dict.get("pair"))
        return commit_hash

    def reveal_and_place(self, commit_hash: str) -> Optional[dict]:
        """Phase 2 of commit-reveal: reveal a previously committed order and place it.

        Returns the placement result (same as place_order) or None if hash not found.
        """
        order_dict = self._committed_orders.pop(commit_hash, None)
        if order_dict is None:
            logger.warning("MEV reveal failed: unknown commit %s", commit_hash[:16])
            return None

        return self.place_order(
            pair=order_dict["pair"],
            side=order_dict["side"],
            order_type=order_dict.get("type", "limit"),
            price=float(order_dict.get("price", 0)),
            size=float(order_dict["size"]),
            address=order_dict.get("address", ""),
            trigger_price=float(order_dict.get("trigger_price", 0)),
        )

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
            "mev_protection": self._mev_protection,
            "pending_commits": len(self._committed_orders),
            "fees": {
                "maker_fee_rate": str(self._maker_fee),
                "taker_fee_rate": str(self._taker_fee),
                "total_collected": str(self._total_fees_collected),
                "treasury": self._fee_treasury,
            },
        }
