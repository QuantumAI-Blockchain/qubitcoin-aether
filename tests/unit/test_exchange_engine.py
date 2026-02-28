"""
Unit tests for the DEX exchange engine (CLOB order matching).
"""

import pytest
from decimal import Decimal
from qubitcoin.exchange.engine import ExchangeEngine, OrderBook, Side, OrderType, OrderStatus


# ---------------------------------------------------------------------------
# OrderBook basics
# ---------------------------------------------------------------------------

class TestOrderBook:

    def test_create_empty_book(self):
        book = OrderBook("QBC_QUSD")
        assert book.pair == "QBC_QUSD"
        assert len(book.bids) == 0
        assert len(book.asks) == 0

    def test_place_limit_buy(self):
        book = OrderBook("QBC_QUSD")
        order, fills = book.place_limit_order("buy", 0.28, 100, "addr1")
        assert order.side == Side.BUY
        assert order.price == Decimal("0.28")
        assert order.size == Decimal("100")
        assert order.status == OrderStatus.OPEN
        assert len(fills) == 0
        assert len(book.bids) == 1
        assert len(book.asks) == 0

    def test_place_limit_sell(self):
        book = OrderBook("QBC_QUSD")
        order, fills = book.place_limit_order("sell", 0.30, 50, "addr2")
        assert order.side == Side.SELL
        assert order.status == OrderStatus.OPEN
        assert len(fills) == 0
        assert len(book.asks) == 1

    def test_limit_order_price_must_be_positive(self):
        book = OrderBook("QBC_QUSD")
        with pytest.raises(ValueError, match="price must be positive"):
            book.place_limit_order("buy", 0, 100, "addr1")

    def test_order_size_must_be_positive(self):
        book = OrderBook("QBC_QUSD")
        with pytest.raises(ValueError, match="size must be positive"):
            book.place_limit_order("buy", 1.0, 0, "addr1")

    # ── Matching tests ─────────────────────────────────────────────────

    def test_exact_match(self):
        book = OrderBook("QBC_QUSD")
        # Resting sell at 0.30
        book.place_limit_order("sell", 0.30, 100, "seller")
        # Incoming buy at 0.30 -> should match
        order, fills = book.place_limit_order("buy", 0.30, 100, "buyer")

        assert order.status == OrderStatus.FILLED
        assert order.filled == Decimal("100")
        assert len(fills) == 1
        assert fills[0].price == Decimal("0.30")
        assert fills[0].size == Decimal("100")
        assert fills[0].side == Side.BUY  # taker side
        assert fills[0].maker_address == "seller"
        assert fills[0].taker_address == "buyer"
        # Book should be empty
        assert len(book.bids) == 0
        assert len(book.asks) == 0

    def test_partial_match_taker_larger(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 50, "seller")
        order, fills = book.place_limit_order("buy", 0.30, 100, "buyer")

        assert order.status == OrderStatus.PARTIAL
        assert order.filled == 50
        assert order.remaining == 50
        assert len(fills) == 1
        # Remaining should rest as a bid
        assert len(book.bids) == 1
        assert len(book.asks) == 0

    def test_partial_match_maker_larger(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 200, "seller")
        order, fills = book.place_limit_order("buy", 0.30, 50, "buyer")

        assert order.status == OrderStatus.FILLED
        assert order.filled == 50
        assert len(fills) == 1
        # Remaining ask should stay in book
        assert len(book.asks) == 1
        assert len(book.bids) == 0

    def test_no_match_when_prices_dont_cross(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.35, 100, "seller")
        order, fills = book.place_limit_order("buy", 0.30, 100, "buyer")

        assert order.status == OrderStatus.OPEN
        assert len(fills) == 0
        assert len(book.bids) == 1
        assert len(book.asks) == 1

    def test_price_time_priority(self):
        """Earlier orders at the same price should fill first."""
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 50, "seller1")
        book.place_limit_order("sell", 0.30, 50, "seller2")

        order, fills = book.place_limit_order("buy", 0.30, 50, "buyer")
        assert len(fills) == 1
        assert fills[0].maker_address == "seller1"

    def test_price_priority_better_price_first(self):
        """Lower-priced asks should fill before higher-priced asks."""
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.32, 50, "expensive")
        book.place_limit_order("sell", 0.30, 50, "cheap")

        order, fills = book.place_limit_order("buy", 0.35, 50, "buyer")
        assert len(fills) == 1
        assert fills[0].maker_address == "cheap"
        assert fills[0].price == Decimal("0.30")

    def test_multi_level_fill(self):
        """Taker consumes multiple price levels."""
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 30, "s1")
        book.place_limit_order("sell", 0.31, 30, "s2")
        book.place_limit_order("sell", 0.32, 30, "s3")

        order, fills = book.place_limit_order("buy", 0.32, 80, "buyer")
        assert order.filled == Decimal("80")
        assert len(fills) == 3
        assert fills[0].price == Decimal("0.30")
        assert fills[1].price == Decimal("0.31")
        assert fills[2].price == Decimal("0.32")
        assert fills[2].size == Decimal("20")  # partial fill on s3

    # ── Market orders ────────────────────────────────────────────────────

    def test_market_buy_fills_against_asks(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 100, "seller")
        order, fills = book.place_market_order("buy", 50, "buyer")

        assert order.status == OrderStatus.FILLED
        assert order.filled == 50
        assert len(fills) == 1
        assert fills[0].price == Decimal("0.30")

    def test_market_order_no_liquidity(self):
        book = OrderBook("QBC_QUSD")
        order, fills = book.place_market_order("buy", 100, "buyer")

        assert order.status == OrderStatus.CANCELLED
        assert order.filled == 0
        assert len(fills) == 0

    def test_market_order_partial_liquidity(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 30, "seller")
        order, fills = book.place_market_order("buy", 100, "buyer")

        assert order.status == OrderStatus.PARTIAL
        assert order.filled == 30
        assert len(fills) == 1

    # ── Cancel ───────────────────────────────────────────────────────────

    def test_cancel_order(self):
        book = OrderBook("QBC_QUSD")
        order, _ = book.place_limit_order("buy", 0.28, 100, "addr1")
        assert len(book.bids) == 1

        result = book.cancel_order(order.id)
        assert result is True
        assert len(book.bids) == 0
        assert order.status == OrderStatus.CANCELLED

    def test_cancel_nonexistent_order(self):
        book = OrderBook("QBC_QUSD")
        result = book.cancel_order("doesnotexist")
        assert result is False

    # ── Order book query ─────────────────────────────────────────────────

    def test_get_orderbook_snapshot(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("buy", 0.28, 100, "b1")
        book.place_limit_order("buy", 0.27, 200, "b2")
        book.place_limit_order("sell", 0.30, 150, "s1")
        book.place_limit_order("sell", 0.31, 50, "s2")

        snapshot = book.get_orderbook(depth=10)
        assert snapshot["pair"] == "QBC_QUSD"
        assert len(snapshot["bids"]) == 2
        assert len(snapshot["asks"]) == 2
        # Bids: highest price first
        assert snapshot["bids"][0]["price"] == "0.28"
        assert snapshot["bids"][1]["price"] == "0.27"
        # Asks: lowest price first
        assert Decimal(snapshot["asks"][0]["price"]) == Decimal("0.30")
        assert snapshot["asks"][1]["price"] == "0.31"
        # Cumulative totals (quantized strings)
        assert Decimal(snapshot["bids"][0]["total"]) == Decimal("100")
        assert Decimal(snapshot["bids"][1]["total"]) == Decimal("300")
        assert Decimal(snapshot["spread"]) > 0
        assert Decimal(snapshot["midPrice"]) > 0

    def test_get_recent_trades(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 100, "seller")
        book.place_limit_order("buy", 0.30, 50, "buyer")

        trades = book.get_recent_trades(limit=10)
        assert len(trades) == 1
        assert trades[0]["price"] == "0.3"
        assert trades[0]["size"] == "50"

    def test_get_open_orders_by_address(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("buy", 0.28, 100, "alice")
        book.place_limit_order("sell", 0.32, 50, "bob")
        book.place_limit_order("buy", 0.27, 200, "alice")

        alice_orders = book.get_open_orders("alice")
        assert len(alice_orders) == 2
        bob_orders = book.get_open_orders("bob")
        assert len(bob_orders) == 1

    def test_get_stats(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 100, "seller")
        book.place_limit_order("buy", 0.30, 50, "buyer")  # partial match

        stats = book.get_stats()
        assert stats["pair"] == "QBC_QUSD"
        assert stats["bidCount"] == 0  # no resting bids (buyer was fully filled)
        assert stats["askCount"] == 1  # partial ask remains


# ---------------------------------------------------------------------------
# ExchangeEngine (multi-pair)
# ---------------------------------------------------------------------------

class TestExchangeEngine:

    def test_init_creates_default_pairs(self):
        engine = ExchangeEngine()
        assert len(engine.books) == len(ExchangeEngine.DEFAULT_PAIRS)
        for pair in ExchangeEngine.DEFAULT_PAIRS:
            assert pair in engine.books

    def test_get_or_create_book(self):
        engine = ExchangeEngine()
        book = engine.get_or_create_book("NEW_PAIR")
        assert "NEW_PAIR" in engine.books
        assert book.pair == "NEW_PAIR"

    def test_place_order_limit(self):
        engine = ExchangeEngine()
        result = engine.place_order("QBC_QUSD", "buy", "limit", 0.28, 100, "addr1")
        assert result["order"]["pair"] == "QBC_QUSD"
        assert result["order"]["side"] == "buy"
        assert result["order"]["status"] == "open"
        assert result["fillCount"] == 0

    def test_place_order_market(self):
        engine = ExchangeEngine()
        # Place a resting sell, then market buy
        engine.place_order("QBC_QUSD", "sell", "limit", 0.30, 100, "seller")
        result = engine.place_order("QBC_QUSD", "buy", "market", 0, 50, "buyer")
        assert result["order"]["status"] == "filled"
        assert result["fillCount"] == 1

    def test_cancel_order(self):
        engine = ExchangeEngine()
        result = engine.place_order("QBC_QUSD", "buy", "limit", 0.28, 100, "addr1")
        order_id = result["order"]["id"]

        success = engine.cancel_order("QBC_QUSD", order_id)
        assert success is True

    def test_cancel_order_any_pair(self):
        engine = ExchangeEngine()
        result = engine.place_order("WETH_QUSD", "buy", "limit", 3400, 1.0, "addr1")
        order_id = result["order"]["id"]

        success = engine.cancel_order_any_pair(order_id)
        assert success is True

    def test_get_markets(self):
        engine = ExchangeEngine()
        markets = engine.get_markets()
        assert len(markets) == len(ExchangeEngine.DEFAULT_PAIRS)
        for m in markets:
            assert "pair" in m
            assert "lastPrice" in m

    def test_get_user_orders_across_pairs(self):
        engine = ExchangeEngine()
        engine.place_order("QBC_QUSD", "buy", "limit", 0.28, 100, "alice")
        engine.place_order("WETH_QUSD", "sell", "limit", 3500, 0.5, "alice")
        engine.place_order("QBC_QUSD", "buy", "limit", 0.27, 200, "bob")

        alice_orders = engine.get_user_orders("alice")
        assert len(alice_orders) == 2
        bob_orders = engine.get_user_orders("bob")
        assert len(bob_orders) == 1

    def test_deposit_and_balance(self):
        engine = ExchangeEngine()
        result = engine.deposit("alice", "QBC", 1000.0)
        assert result["address"] == "alice"
        balances = {b["asset"]: b for b in result["balances"]}
        assert Decimal(balances["QBC"]["total"]) == Decimal("1000")
        assert Decimal(balances["QBC"]["available"]) == Decimal("1000")

    def test_withdraw(self):
        engine = ExchangeEngine()
        engine.deposit("alice", "QBC", 1000.0)
        result = engine.withdraw("alice", "QBC", 300.0)
        balances = {b["asset"]: b for b in result["balances"]}
        assert Decimal(balances["QBC"]["total"]) == Decimal("700")

    def test_withdraw_insufficient(self):
        engine = ExchangeEngine()
        engine.deposit("alice", "QBC", 100.0)
        with pytest.raises(ValueError, match="Insufficient"):
            engine.withdraw("alice", "QBC", 200.0)

    def test_get_engine_stats(self):
        engine = ExchangeEngine()
        engine.place_order("QBC_QUSD", "buy", "limit", 0.28, 100, "addr1")
        stats = engine.get_engine_stats()
        assert stats["pairs"] == len(ExchangeEngine.DEFAULT_PAIRS)
        assert stats["total_bid_orders"] >= 1

    def test_unsupported_order_type(self):
        engine = ExchangeEngine()
        with pytest.raises(ValueError, match="Unsupported order type"):
            engine.place_order("QBC_QUSD", "buy", "stop_loss", 0.28, 100, "addr1")
