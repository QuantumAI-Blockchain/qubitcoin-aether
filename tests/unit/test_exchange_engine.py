"""
Unit tests for the DEX exchange engine (CLOB order matching).
"""

import pytest
from decimal import Decimal
from qubitcoin.exchange.engine import (
    ExchangeEngine, OrderBook, Side, OrderType, OrderStatus,
    SettlementCallback, UTXOSettlement, Fill,
    OrderPersistence, InMemoryPersistence,
)


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
        order, fills = book.place_limit_order("buy", 0.28, 100, "addr1xxx")
        assert order.side == Side.BUY
        assert order.price == Decimal("0.28")
        assert order.size == Decimal("100")
        assert order.status == OrderStatus.OPEN
        assert len(fills) == 0
        assert len(book.bids) == 1
        assert len(book.asks) == 0

    def test_place_limit_sell(self):
        book = OrderBook("QBC_QUSD")
        order, fills = book.place_limit_order("sell", 0.30, 50, "addr2xxx")
        assert order.side == Side.SELL
        assert order.status == OrderStatus.OPEN
        assert len(fills) == 0
        assert len(book.asks) == 1

    def test_limit_order_price_must_be_positive(self):
        book = OrderBook("QBC_QUSD")
        with pytest.raises(ValueError, match="price must be positive"):
            book.place_limit_order("buy", 0, 100, "addr1xxx")

    def test_order_size_must_be_positive(self):
        book = OrderBook("QBC_QUSD")
        with pytest.raises(ValueError, match="size must be positive"):
            book.place_limit_order("buy", 1.0, 0, "addr1xxx")

    # ── Matching tests ─────────────────────────────────────────────────

    def test_exact_match(self):
        book = OrderBook("QBC_QUSD")
        # Resting sell at 0.30
        book.place_limit_order("sell", 0.30, 100, "sellerxx")
        # Incoming buy at 0.30 -> should match
        order, fills = book.place_limit_order("buy", 0.30, 100, "buyerxxx")

        assert order.status == OrderStatus.FILLED
        assert order.filled == Decimal("100")
        assert len(fills) == 1
        assert fills[0].price == Decimal("0.30")
        assert fills[0].size == Decimal("100")
        assert fills[0].side == Side.BUY  # taker side
        assert fills[0].maker_address == "sellerxx"
        assert fills[0].taker_address == "buyerxxx"
        # Book should be empty
        assert len(book.bids) == 0
        assert len(book.asks) == 0

    def test_partial_match_taker_larger(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 50, "sellerxx")
        order, fills = book.place_limit_order("buy", 0.30, 100, "buyerxxx")

        assert order.status == OrderStatus.PARTIAL
        assert order.filled == 50
        assert order.remaining == 50
        assert len(fills) == 1
        # Remaining should rest as a bid
        assert len(book.bids) == 1
        assert len(book.asks) == 0

    def test_partial_match_maker_larger(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 200, "sellerxx")
        order, fills = book.place_limit_order("buy", 0.30, 50, "buyerxxx")

        assert order.status == OrderStatus.FILLED
        assert order.filled == 50
        assert len(fills) == 1
        # Remaining ask should stay in book
        assert len(book.asks) == 1
        assert len(book.bids) == 0

    def test_no_match_when_prices_dont_cross(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.35, 100, "sellerxx")
        order, fills = book.place_limit_order("buy", 0.30, 100, "buyerxxx")

        assert order.status == OrderStatus.OPEN
        assert len(fills) == 0
        assert len(book.bids) == 1
        assert len(book.asks) == 1

    def test_price_time_priority(self):
        """Earlier orders at the same price should fill first."""
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 50, "seller1")
        book.place_limit_order("sell", 0.30, 50, "seller2")

        order, fills = book.place_limit_order("buy", 0.30, 50, "buyerxxx")
        assert len(fills) == 1
        assert fills[0].maker_address == "seller1"

    def test_price_priority_better_price_first(self):
        """Lower-priced asks should fill before higher-priced asks."""
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.32, 50, "expensive")
        book.place_limit_order("sell", 0.30, 50, "cheap")

        order, fills = book.place_limit_order("buy", 0.35, 50, "buyerxxx")
        assert len(fills) == 1
        assert fills[0].maker_address == "cheap"
        assert fills[0].price == Decimal("0.30")

    def test_multi_level_fill(self):
        """Taker consumes multiple price levels."""
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 30, "s1")
        book.place_limit_order("sell", 0.31, 30, "s2")
        book.place_limit_order("sell", 0.32, 30, "s3")

        order, fills = book.place_limit_order("buy", 0.32, 80, "buyerxxx")
        assert order.filled == Decimal("80")
        assert len(fills) == 3
        assert fills[0].price == Decimal("0.30")
        assert fills[1].price == Decimal("0.31")
        assert fills[2].price == Decimal("0.32")
        assert fills[2].size == Decimal("20")  # partial fill on s3

    # ── Market orders ────────────────────────────────────────────────────

    def test_market_buy_fills_against_asks(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 100, "sellerxx")
        order, fills = book.place_market_order("buy", 50, "buyerxxx")

        assert order.status == OrderStatus.FILLED
        assert order.filled == 50
        assert len(fills) == 1
        assert fills[0].price == Decimal("0.30")

    def test_market_order_no_liquidity(self):
        book = OrderBook("QBC_QUSD")
        order, fills = book.place_market_order("buy", 100, "buyerxxx")

        assert order.status == OrderStatus.CANCELLED
        assert order.filled == 0
        assert len(fills) == 0

    def test_market_order_partial_liquidity(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 30, "sellerxx")
        order, fills = book.place_market_order("buy", 100, "buyerxxx")

        assert order.status == OrderStatus.PARTIAL
        assert order.filled == 30
        assert len(fills) == 1

    # ── Self-trade prevention ─────────────────────────────────────────

    def test_self_trade_prevention(self):
        """Self-trade prevention: cancel-oldest mode cancels the resting own
        order instead of matching, then the taker rests in the book."""
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 100, "aliceaaa")
        order, fills = book.place_limit_order("buy", 0.30, 100, "aliceaaa")
        assert len(fills) == 0
        assert order.status == OrderStatus.OPEN
        # Cancel-oldest: alice's sell is cancelled, buy rests
        assert len(book.bids) == 1
        assert len(book.asks) == 0

    def test_self_trade_does_not_block_others(self):
        """Self-trade prevention cancels own resting order then matches
        against other addresses."""
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 100, "aliceaaa")
        book.place_limit_order("sell", 0.30, 100, "bob12345")
        # alice's buy should cancel alice's sell (cancel-oldest) then match bob's sell
        order, fills = book.place_limit_order("buy", 0.30, 100, "aliceaaa")
        assert len(fills) == 1
        assert fills[0].maker_address == "bob12345"
        assert order.status == OrderStatus.FILLED

    def test_no_address_allows_match(self):
        """Orders without addresses (empty string) can match normally."""
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 100, "")
        order, fills = book.place_limit_order("buy", 0.30, 100, "")
        # Both empty addresses — self-trade check skipped
        assert len(fills) == 1
        assert order.status == OrderStatus.FILLED

    # ── Cancel ───────────────────────────────────────────────────────────

    def test_cancel_order(self):
        book = OrderBook("QBC_QUSD")
        order, _ = book.place_limit_order("buy", 0.28, 100, "addr1xxx")
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
        book.place_limit_order("sell", 0.30, 100, "sellerxx")
        book.place_limit_order("buy", 0.30, 50, "buyerxxx")

        trades = book.get_recent_trades(limit=10)
        assert len(trades) == 1
        assert trades[0]["price"] == "0.3"
        assert trades[0]["size"] == "50"

    def test_get_open_orders_by_address(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("buy", 0.28, 100, "aliceaaa")
        book.place_limit_order("sell", 0.32, 50, "bob12345")
        book.place_limit_order("buy", 0.27, 200, "aliceaaa")

        alice_orders = book.get_open_orders("aliceaaa")
        assert len(alice_orders) == 2
        bob_orders = book.get_open_orders("bob12345")
        assert len(bob_orders) == 1

    def test_get_stats(self):
        book = OrderBook("QBC_QUSD")
        book.place_limit_order("sell", 0.30, 100, "sellerxx")
        book.place_limit_order("buy", 0.30, 50, "buyerxxx")  # partial match

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
        engine.deposit("addr1xxx", "QUSD", 100000)
        result = engine.place_order("QBC_QUSD", "buy", "limit", 0.28, 100, "addr1xxx")
        assert result["order"]["pair"] == "QBC_QUSD"
        assert result["order"]["side"] == "buy"
        assert result["order"]["status"] == "open"
        assert result["fillCount"] == 0

    def test_place_order_market(self):
        engine = ExchangeEngine()
        engine.deposit("sellerxx", "QBC", 100000)
        engine.deposit("buyerxxx", "QUSD", 100000)
        # Place a resting sell, then market buy
        engine.place_order("QBC_QUSD", "sell", "limit", 0.30, 100, "sellerxx")
        result = engine.place_order("QBC_QUSD", "buy", "market", 0, 50, "buyerxxx")
        assert result["order"]["status"] == "filled"
        assert result["fillCount"] == 1

    def test_cancel_order(self):
        engine = ExchangeEngine()
        engine.deposit("addr1xxx", "QUSD", 100000)
        result = engine.place_order("QBC_QUSD", "buy", "limit", 0.28, 100, "addr1xxx")
        order_id = result["order"]["id"]

        success = engine.cancel_order("QBC_QUSD", order_id)
        assert success is True

    def test_cancel_order_any_pair(self):
        engine = ExchangeEngine()
        engine.deposit("addr1xxx", "QUSD", 100000)
        result = engine.place_order("WETH_QUSD", "buy", "limit", 3400, 1.0, "addr1xxx")
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
        engine.deposit("aliceaaa", "QUSD", 100000)
        engine.deposit("aliceaaa", "WETH", 100000)
        engine.deposit("bob12345", "QUSD", 100000)
        engine.place_order("QBC_QUSD", "buy", "limit", 0.28, 100, "aliceaaa")
        engine.place_order("WETH_QUSD", "sell", "limit", 3500, 0.5, "aliceaaa")
        engine.place_order("QBC_QUSD", "buy", "limit", 0.27, 200, "bob12345")

        alice_orders = engine.get_user_orders("aliceaaa")
        assert len(alice_orders) == 2
        bob_orders = engine.get_user_orders("bob12345")
        assert len(bob_orders) == 1

    def test_deposit_and_balance(self):
        engine = ExchangeEngine()
        result = engine.deposit("alice1234", "QBC", 1000.0)
        assert result["address"] == "alice1234"
        balances = {b["asset"]: b for b in result["balances"]}
        assert Decimal(balances["QBC"]["total"]) == Decimal("1000")
        assert Decimal(balances["QBC"]["available"]) == Decimal("1000")

    def test_withdraw(self):
        engine = ExchangeEngine()
        engine.deposit("alice1234", "QBC", 1000.0)
        result = engine.withdraw("alice1234", "QBC", 300.0)
        balances = {b["asset"]: b for b in result["balances"]}
        assert Decimal(balances["QBC"]["total"]) == Decimal("700")

    def test_withdraw_insufficient(self):
        engine = ExchangeEngine()
        engine.deposit("alice1234", "QBC", 100.0)
        with pytest.raises(ValueError, match="Insufficient"):
            engine.withdraw("alice1234", "QBC", 200.0)

    def test_get_engine_stats(self):
        engine = ExchangeEngine()
        engine.deposit("addr1xxx", "QUSD", 100000)
        engine.place_order("QBC_QUSD", "buy", "limit", 0.28, 100, "addr1xxx")
        stats = engine.get_engine_stats()
        assert stats["pairs"] == len(ExchangeEngine.DEFAULT_PAIRS)
        assert stats["total_bid_orders"] >= 1

    def test_unsupported_order_type(self):
        engine = ExchangeEngine()
        engine.deposit("addr1xxx", "QUSD", 100000)
        with pytest.raises(ValueError, match="Unsupported order type"):
            engine.place_order("QBC_QUSD", "buy", "iceberg", 0.28, 100, "addr1xxx")


# ---------------------------------------------------------------------------
# Stop Orders
# ---------------------------------------------------------------------------

class TestStopOrders:

    def test_stop_loss_sell_triggers_on_price_drop(self):
        """Stop-loss sell triggers when price falls to trigger level."""
        book = OrderBook("QBC_QUSD")
        # Place a stop-loss to sell if price drops to 0.25
        stop = book.place_stop_loss_order("sell", 0.25, 100, "aliceaaa")
        assert stop.order_type == OrderType.STOP_LOSS
        assert stop.trigger_price == Decimal("0.25")
        assert len(book._stop_orders) == 1

        # Place a resting bid that will absorb the market order
        book.place_limit_order("buy", 0.24, 200, "bob12345")

        # Trigger: price drops to 0.24
        triggered = book.check_triggers(Decimal("0.24"))
        assert len(triggered) == 1
        order, fills = triggered[0]
        assert len(fills) == 1
        assert len(book._stop_orders) == 0

    def test_stop_loss_buy_triggers_on_price_rise(self):
        """Stop-loss buy triggers when price rises to trigger level."""
        book = OrderBook("QBC_QUSD")
        stop = book.place_stop_loss_order("buy", 0.35, 50, "aliceaaa")
        book.place_limit_order("sell", 0.36, 100, "bob12345")

        triggered = book.check_triggers(Decimal("0.36"))
        assert len(triggered) == 1
        _, fills = triggered[0]
        assert len(fills) == 1

    def test_stop_loss_does_not_trigger_prematurely(self):
        """Stop order should not trigger if price hasn't reached trigger."""
        book = OrderBook("QBC_QUSD")
        book.place_stop_loss_order("sell", 0.25, 100, "aliceaaa")
        triggered = book.check_triggers(Decimal("0.30"))
        assert len(triggered) == 0
        assert len(book._stop_orders) == 1

    def test_stop_limit_converts_to_limit(self):
        """Stop-limit converts to a limit order (not market) when triggered."""
        book = OrderBook("QBC_QUSD")
        stop = book.place_stop_limit_order("sell", 0.25, 0.24, 100, "aliceaaa")
        assert stop.order_type == OrderType.STOP_LIMIT
        assert stop.price == Decimal("0.24")

        # No bids — trigger the stop, limit rests in book
        triggered = book.check_triggers(Decimal("0.20"))
        assert len(triggered) == 1
        _, fills = triggered[0]
        assert len(fills) == 0  # no matching bid
        # The limit order should now be resting in asks
        assert len(book.asks) == 1

    def test_cancel_stop_order(self):
        book = OrderBook("QBC_QUSD")
        stop = book.place_stop_loss_order("sell", 0.25, 100, "aliceaaa")
        assert book.cancel_order(stop.id) is True
        assert len(book._stop_orders) == 0
        assert stop.status == OrderStatus.CANCELLED

    def test_stop_order_via_engine(self):
        """Stop orders can be placed through ExchangeEngine.place_order()."""
        engine = ExchangeEngine()
        engine.deposit("aliceaaa", "QBC", 100000)
        result = engine.place_order(
            "QBC_QUSD", "sell", "stop_loss", 0, 100, "aliceaaa", trigger_price=0.25
        )
        assert result["order"]["type"] == "stop_loss"
        assert result["order"]["trigger_price"] == "0.25"
        assert result["fillCount"] == 0

    def test_stop_limit_via_engine(self):
        engine = ExchangeEngine()
        engine.deposit("aliceaaa", "QBC", 100000)
        result = engine.place_order(
            "QBC_QUSD", "sell", "stop_limit", 0.24, 100, "aliceaaa", trigger_price=0.25
        )
        assert result["order"]["type"] == "stop_limit"
        assert result["order"]["trigger_price"] == "0.25"
        assert result["order"]["price"] == "0.24"


# ---------------------------------------------------------------------------
# Settlement
# ---------------------------------------------------------------------------

class TestSettlement:

    def test_settlement_callback_invoked_on_fill(self):
        """Settlement callback is called for each matched fill."""
        settled_fills = []

        class MockSettlement(SettlementCallback):
            def settle_fill(self, fill):
                settled_fills.append(fill.id)
                return True

        engine = ExchangeEngine(settlement=MockSettlement())
        engine.deposit("sellerxx", "QBC", 100000)
        engine.deposit("buyerxxx", "QUSD", 100000)
        engine.place_order("QBC_QUSD", "sell", "limit", 0.30, 100, "sellerxx")
        engine.place_order("QBC_QUSD", "buy", "limit", 0.30, 50, "buyerxxx")
        assert len(settled_fills) == 1

    def test_utxo_settlement_records_fills(self):
        """UTXOSettlement records fill details even without a create_tx backend."""
        settlement = UTXOSettlement()  # no create_transaction_fn
        engine = ExchangeEngine(settlement=settlement)
        engine.deposit("sellerxx", "QBC", 100000)
        engine.deposit("buyerxxx", "QUSD", 100000)
        engine.place_order("QBC_QUSD", "sell", "limit", 0.30, 100, "sellerxx")
        engine.place_order("QBC_QUSD", "buy", "limit", 0.30, 50, "buyerxxx")

        records = settlement.get_pending_settlements()
        assert len(records) == 1
        assert records[0]["settled"] is False  # no backend
        assert records[0]["maker"] == "sellerxx"
        assert records[0]["taker"] == "buyerxxx"

    def test_utxo_settlement_with_backend(self):
        """UTXOSettlement calls create_transaction_fn when provided."""
        tx_log = []

        def mock_create_tx(from_addr, to_addr, amount, asset):
            tx_log.append({"from": from_addr, "to": to_addr, "amount": amount, "asset": asset})

        settlement = UTXOSettlement(create_transaction_fn=mock_create_tx)
        engine = ExchangeEngine(settlement=settlement)
        engine.deposit("sellerxx", "QBC", 100000)
        engine.deposit("buyerxxx", "QUSD", 100000)
        engine.place_order("QBC_QUSD", "sell", "limit", 0.30, 100, "sellerxx")
        engine.place_order("QBC_QUSD", "buy", "limit", 0.30, 100, "buyerxxx")

        # Buy side: taker sends QUSD to maker, maker sends QBC to taker
        assert len(tx_log) == 2
        assert tx_log[0]["asset"] == "QUSD"  # buyer pays quote
        assert tx_log[1]["asset"] == "QBC"    # seller sends base

        records = settlement.get_pending_settlements()
        assert records[0]["settled"] is True

    def test_no_settlement_when_no_callback(self):
        """Engine without settlement callback works normally (backward compatible)."""
        engine = ExchangeEngine()  # no settlement
        engine.deposit("sellerxx", "QBC", 100000)
        engine.deposit("buyerxxx", "QUSD", 100000)
        engine.place_order("QBC_QUSD", "sell", "limit", 0.30, 100, "sellerxx")
        result = engine.place_order("QBC_QUSD", "buy", "limit", 0.30, 50, "buyerxxx")
        assert result["fillCount"] == 1


# ---------------------------------------------------------------------------
# Order Persistence
# ---------------------------------------------------------------------------

class TestPersistence:

    def test_orders_persisted_on_placement(self):
        persistence = InMemoryPersistence()
        engine = ExchangeEngine(persistence=persistence)
        engine.deposit("aliceaaa", "QUSD", 100000)
        engine.place_order("QBC_QUSD", "buy", "limit", 0.28, 100, "aliceaaa")

        saved = persistence.get_saved_orders("QBC_QUSD")
        assert len(saved) == 1
        assert saved[0]["side"] == "buy"
        assert saved[0]["address"] == "aliceaaa"

    def test_fills_persisted_on_match(self):
        persistence = InMemoryPersistence()
        engine = ExchangeEngine(persistence=persistence)
        engine.deposit("sellerxx", "QBC", 100000)
        engine.deposit("buyerxxx", "QUSD", 100000)
        engine.place_order("QBC_QUSD", "sell", "limit", 0.30, 100, "sellerxx")
        engine.place_order("QBC_QUSD", "buy", "limit", 0.30, 50, "buyerxxx")

        fills = persistence.get_saved_fills("QBC_QUSD")
        assert len(fills) == 1
        assert fills[0]["maker_address"] == "sellerxx"
        assert fills[0]["taker_address"] == "buyerxxx"


# ---------------------------------------------------------------------------
# MEV Protection
# ---------------------------------------------------------------------------

class TestMEVProtection:

    def test_commit_reveal_flow(self):
        """Orders can be committed then revealed."""
        engine = ExchangeEngine(mev_protection=True)
        engine.deposit("aliceaaa", "QUSD", 100000)
        order_dict = {
            "pair": "QBC_QUSD",
            "side": "buy",
            "type": "limit",
            "price": "0.28",
            "size": "100",
            "address": "aliceaaa",
        }
        commit_hash = engine.commit_order(order_dict)
        assert commit_hash is not None
        assert len(commit_hash) == 64  # SHA-256 hex
        assert engine.get_engine_stats()["pending_commits"] == 1

        # Reveal and place
        result = engine.reveal_and_place(commit_hash)
        assert result is not None
        assert result["order"]["side"] == "buy"
        assert engine.get_engine_stats()["pending_commits"] == 0

    def test_reveal_unknown_hash_returns_none(self):
        engine = ExchangeEngine(mev_protection=True)
        result = engine.reveal_and_place("deadbeef" * 8)
        assert result is None

    def test_commit_disabled_when_no_mev(self):
        engine = ExchangeEngine(mev_protection=False)
        commit_hash = engine.commit_order({"pair": "QBC_QUSD", "side": "buy"})
        assert commit_hash is None


# ---------------------------------------------------------------------------
# Audit Run #15 — regression tests for H1, H2, M3
# ---------------------------------------------------------------------------

class TestAuditRun15:
    """Tests for findings from audit Run #15 (Exchange + Bridge)."""

    def test_h1_triggered_stop_fills_use_correct_addresses(self):
        """H1: Triggered stop-order fills must debit/credit the stop order
        owner's address, not the original order's address."""
        engine = ExchangeEngine()
        # Alice places a resting sell at 0.30
        engine.deposit("aliceaaa", "QBC", 10000)
        engine.place_order("QBC_QUSD", "sell", "limit", 0.30, 100, "aliceaaa")

        # Bob places a stop-loss sell that triggers at 0.29
        engine.deposit("bob12345", "QBC", 10000)
        engine.place_order(
            "QBC_QUSD", "sell", "stop_loss", 0, 100, "bob12345",
            trigger_price=0.29,
        )

        # Charlie places a resting bid at 0.28 (to absorb Bob's stop-loss sell)
        engine.deposit("charlie1", "QUSD", 10000)
        engine.place_order("QBC_QUSD", "buy", "limit", 0.28, 200, "charlie1")

        # Dave buys at market — fills Alice's ask at 0.30, which triggers
        # Bob's stop-loss sell (price 0.30 >= 0.29 is wrong direction for
        # sell-stop... but 0.30 crosses 0.29 for buy-stops).
        #
        # Actually sell-stop triggers when price <= trigger. Let's set it up
        # so a sell trade pushes price down.

        # Reset and try a simpler scenario:
        engine2 = ExchangeEngine()
        # Maker: resting ask at 0.30
        engine2.deposit("maker123", "QBC", 10000)
        engine2.place_order("QBC_QUSD", "sell", "limit", 0.30, 100, "maker123")

        # Stop owner: stop-loss sell triggers at price <= 0.30
        engine2.deposit("stopowner", "QBC", 10000)
        engine2.place_order(
            "QBC_QUSD", "sell", "stop_loss", 0, 50, "stopowner",
            trigger_price=0.30,
        )

        # Buyer: resting bid at 0.29 (to catch stop-loss market sell)
        engine2.deposit("buyeraaa", "QUSD", 10000)
        engine2.place_order("QBC_QUSD", "buy", "limit", 0.29, 200, "buyeraaa")

        # Taker buy triggers a trade at 0.30, which triggers stop-loss
        engine2.deposit("takerxxx", "QUSD", 10000)
        result = engine2.place_order("QBC_QUSD", "buy", "market", 0, 100, "takerxxx")

        # The taker's direct fill was against maker123 at 0.30
        # The triggered stop-loss sell from stopowner should fill against buyeraaa at 0.29
        fills = result["fills"]
        assert len(fills) >= 1  # At least the direct fill

        # Verify stopowner's QBC balance decreased (they sold via stop-loss)
        stop_bal = engine2.get_user_balance("stopowner")
        stop_qbc = {b["asset"]: Decimal(b["total"]) for b in stop_bal["balances"]}
        # stopowner deposited 10000 QBC, sold 50 via stop-loss
        assert stop_qbc.get("QBC", Decimal(0)) < Decimal("10000"), \
            "Stop-loss owner should have sold QBC"

        # Verify takerxxx got credited base asset (QBC) for their buy
        taker_bal = engine2.get_user_balance("takerxxx")
        taker_qbc = {b["asset"]: Decimal(b["total"]) for b in taker_bal["balances"]}
        assert taker_qbc.get("QBC", Decimal(0)) > Decimal(0), \
            "Taker should have received QBC from their buy"

    def test_h2_market_buy_multilevel_balance_check(self):
        """H2: Market buy across multiple ask levels should require the actual
        total cost, not just best_ask * size."""
        engine = ExchangeEngine()
        # Place asks at ascending prices
        engine.deposit("seller_1", "QBC", 10000)
        engine.deposit("seller_2", "QBC", 10000)
        engine.place_order("QBC_QUSD", "sell", "limit", 0.30, 50, "seller_1")
        engine.place_order("QBC_QUSD", "sell", "limit", 0.50, 50, "seller_2")

        # Actual cost to buy 100: 50*0.30 + 50*0.50 = 15 + 25 = 40 QUSD
        # Old code estimated: 100 * 0.30 = 30 QUSD (underfunded)
        # Deposit only 35 QUSD — should be rejected with the fixed estimator
        engine.deposit("buyerxxx", "QUSD", 35)
        with pytest.raises(ValueError, match="Insufficient"):
            engine.place_order("QBC_QUSD", "buy", "market", 0, 100, "buyerxxx")

        # Deposit enough (40 QUSD) — should succeed
        engine.deposit("buyerxxx", "QUSD", 5)  # now has 35+5=40 total
        result = engine.place_order("QBC_QUSD", "buy", "market", 0, 100, "buyerxxx")
        assert result["fillCount"] == 2
        assert result["order"]["status"] == "filled"

    def test_m3_debit_overdraft_caps_at_zero(self):
        """M3: _debit_balance caps balance at zero on overdraft (no negative)."""
        engine = ExchangeEngine()
        engine.deposit("testaddr", "QBC", 10)

        # Debit more than available — should NOT go negative
        engine._debit_balance("testaddr", "QBC", Decimal("20"))
        bal = engine._user_balances["testaddr"]["QBC"]
        assert bal == Decimal("0"), "Balance should be capped at zero, not negative"

    def test_m3_debit_unknown_address_is_noop(self):
        """M3: _debit_balance for unknown address is a no-op."""
        engine = ExchangeEngine()
        # Address not in _user_balances — debit should silently do nothing
        engine._debit_balance("unknown1", "QBC", Decimal("100"))
        assert "unknown1" not in engine._user_balances

    def test_balance_check_not_bypassed_when_user_balances_empty(self):
        """Verify balance check runs correctly when _user_balances is empty."""
        engine = ExchangeEngine()
        # Don't deposit — user has no entry in _user_balances
        with pytest.raises(ValueError, match="Insufficient"):
            engine.place_order("QBC_QUSD", "buy", "limit", 0.28, 100, "nobalance")

    def test_market_buy_rejected_when_no_asks(self):
        """Market buy on empty book is rejected."""
        engine = ExchangeEngine()
        engine.deposit("buyerxxx", "QUSD", 100000)
        with pytest.raises(ValueError, match="No asks available"):
            engine.place_order("QBC_QUSD", "buy", "market", 0, 100, "buyerxxx")
