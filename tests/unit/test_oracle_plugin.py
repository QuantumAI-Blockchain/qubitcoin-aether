"""Tests for Oracle Plugin (Batch 17.5)."""
import time
import pytest

from qubitcoin.qvm.oracle_plugin import (
    OraclePlugin,
    PriceFeed,
    AggregatedPrice,
    create_plugin,
)
from qubitcoin.qvm.plugins import PluginManager, HookType


class TestOraclePluginLifecycle:
    """Test plugin lifecycle."""

    def test_name_and_version(self):
        p = OraclePlugin()
        assert p.name() == 'oracle'
        assert p.version() == '0.1.0'

    def test_description(self):
        p = OraclePlugin()
        assert 'oracle' in p.description().lower()

    def test_hooks_registered(self):
        p = OraclePlugin()
        hooks = p.hooks()
        assert HookType.PRE_EXECUTE in hooks

    def test_start_stop(self):
        p = OraclePlugin()
        p.on_load()
        p.on_start()
        assert p._started is True
        p.on_stop()
        assert p._started is False

    def test_create_plugin_factory(self):
        p = create_plugin()
        assert isinstance(p, OraclePlugin)


class TestPriceSubmission:
    """Test price feed submission."""

    def test_submit_single_price(self):
        p = OraclePlugin()
        feed = p.submit_price('QBC/USD', 0.50, source='binance')
        assert feed.pair == 'QBC/USD'
        assert feed.price == 0.50
        assert feed.source == 'binance'

    def test_submit_with_block_height(self):
        p = OraclePlugin()
        feed = p.submit_price('QBC/ETH', 0.001, block_height=1000)
        assert feed.block_height == 1000

    def test_feed_to_dict(self):
        feed = PriceFeed(pair='QBC/USD', price=0.5, timestamp=time.time(), source='test')
        d = feed.to_dict()
        assert d['pair'] == 'QBC/USD'
        assert d['price'] == 0.5

    def test_submit_triggers_aggregation(self):
        p = OraclePlugin()
        p.submit_price('QBC/USD', 0.50)
        agg = p.get_price('QBC/USD')
        assert agg is not None
        assert agg.median_price == 0.50


class TestPriceAggregation:
    """Test multi-source price aggregation."""

    def test_single_source_median(self):
        p = OraclePlugin()
        p.submit_price('QBC/USD', 1.0)
        agg = p.get_price('QBC/USD')
        assert agg.median_price == 1.0
        assert agg.source_count == 1

    def test_two_sources_median(self):
        p = OraclePlugin()
        p.submit_price('QBC/USD', 1.0, source='a')
        p.submit_price('QBC/USD', 3.0, source='b')
        agg = p.get_price('QBC/USD')
        assert agg.median_price == 2.0  # (1+3)/2
        assert agg.source_count == 2

    def test_three_sources_median(self):
        p = OraclePlugin()
        p.submit_price('QBC/USD', 1.0, source='a')
        p.submit_price('QBC/USD', 5.0, source='b')
        p.submit_price('QBC/USD', 3.0, source='c')
        agg = p.get_price('QBC/USD')
        assert agg.median_price == 3.0  # median of [1,3,5]

    def test_mean_and_range(self):
        p = OraclePlugin()
        p.submit_price('QBC/USD', 10.0)
        p.submit_price('QBC/USD', 20.0)
        p.submit_price('QBC/USD', 30.0)
        agg = p.get_price('QBC/USD')
        assert agg.mean_price == 20.0
        assert agg.min_price == 10.0
        assert agg.max_price == 30.0

    def test_aggregated_to_dict(self):
        p = OraclePlugin()
        p.submit_price('QBC/USD', 1.0)
        agg = p.get_price('QBC/USD')
        d = agg.to_dict()
        assert 'median_price' in d
        assert 'source_count' in d
        assert 'is_stale' in d

    def test_multiple_pairs(self):
        p = OraclePlugin()
        p.submit_price('QBC/USD', 1.0)
        p.submit_price('QBC/ETH', 0.001)
        prices = p.get_all_prices()
        assert len(prices) == 2
        assert 'QBC/USD' in prices
        assert 'QBC/ETH' in prices


class TestStaleness:
    """Test staleness detection."""

    def test_not_stale_after_submit(self):
        p = OraclePlugin(staleness_threshold=300.0)
        p.submit_price('QBC/USD', 1.0)
        assert p.is_stale('QBC/USD') is False

    def test_stale_if_no_data(self):
        p = OraclePlugin()
        assert p.is_stale('NONEXISTENT/PAIR') is True

    def test_short_staleness_threshold(self):
        # Use a tiny threshold so data is immediately stale
        p = OraclePlugin(staleness_threshold=0.0)
        p.submit_price('QBC/USD', 1.0)
        # After aggregation with threshold=0, feed should be stale
        assert p.is_stale('QBC/USD') is True


class TestDeviation:
    """Test price deviation checking."""

    def test_single_source_no_deviation(self):
        p = OraclePlugin()
        p.submit_price('QBC/USD', 1.0)
        assert p.check_deviation('QBC/USD') is None  # < 2 sources

    def test_deviation_calculated(self):
        p = OraclePlugin()
        p.submit_price('QBC/USD', 1.0)
        p.submit_price('QBC/USD', 1.1)
        dev = p.check_deviation('QBC/USD')
        assert dev is not None
        assert dev > 0

    def test_no_pair_no_deviation(self):
        p = OraclePlugin()
        assert p.check_deviation('NONE/PAIR') is None


class TestFeedHistory:
    """Test feed history retrieval."""

    def test_empty_history(self):
        p = OraclePlugin()
        history = p.get_feed_history('QBC/USD')
        assert len(history) == 0

    def test_history_records(self):
        p = OraclePlugin()
        p.submit_price('QBC/USD', 1.0)
        p.submit_price('QBC/USD', 2.0)
        p.submit_price('QBC/USD', 3.0)
        history = p.get_feed_history('QBC/USD')
        assert len(history) == 3

    def test_history_limit(self):
        p = OraclePlugin()
        for i in range(100):
            p.submit_price('QBC/USD', float(i))
        history = p.get_feed_history('QBC/USD', limit=10)
        assert len(history) == 10


class TestPreExecuteHook:
    """Test PRE_EXECUTE hook for price injection."""

    def test_no_pair_requested(self):
        p = OraclePlugin()
        result = p._pre_execute_hook({})
        assert result is None

    def test_pair_not_available(self):
        p = OraclePlugin()
        result = p._pre_execute_hook({'oracle_pair': 'QBC/USD'})
        assert result is not None
        assert result['oracle_price'] is None
        assert result['oracle_stale'] is True

    def test_pair_available(self):
        p = OraclePlugin()
        p.submit_price('QBC/USD', 1.5)
        result = p._pre_execute_hook({'oracle_pair': 'QBC/USD'})
        assert result is not None
        assert result['oracle_price'] == 1.5
        assert result['oracle_stale'] is False


class TestPluginManagerIntegration:
    """Test oracle plugin with PluginManager."""

    def test_register_and_start(self):
        mgr = PluginManager()
        plugin = OraclePlugin()
        mgr.register(plugin)
        assert mgr.load('oracle') is True
        assert mgr.start('oracle') is True

    def test_dispatch_pre_execute(self):
        mgr = PluginManager()
        plugin = OraclePlugin()
        plugin.submit_price('QBC/USD', 2.0)
        mgr.register(plugin)
        mgr.load('oracle')
        mgr.start('oracle')

        ctx = mgr.dispatch_hook(HookType.PRE_EXECUTE, {'oracle_pair': 'QBC/USD'})
        assert ctx.get('oracle_price') == 2.0


class TestOracleStats:
    """Test plugin statistics."""

    def test_initial_stats(self):
        p = OraclePlugin()
        stats = p.get_stats()
        assert stats['pairs_tracked'] == 0
        assert stats['total_updates'] == 0

    def test_stats_after_updates(self):
        p = OraclePlugin()
        p.submit_price('QBC/USD', 1.0)
        p.submit_price('QBC/ETH', 0.001)
        stats = p.get_stats()
        assert stats['pairs_tracked'] == 2
        assert stats['total_updates'] == 2
