"""
Comprehensive tests for QUSD multi-chain liquidity components:
  - DEXPriceReader (stablecoin/dex_price.py)
  - ArbitrageCalculator (stablecoin/arbitrage.py)
  - QUSDKeeper (stablecoin/keeper.py)
  - BridgeVault.sol fee configurability
  - Keeper Prometheus metrics
  - Keeper RPC endpoints
"""

import time
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock


# ============================================================================
# DEXPriceReader Tests
# ============================================================================

class TestDEXPriceReader:
    """Test external DEX price reader."""

    def test_import(self):
        from qubitcoin.stablecoin.dex_price import DEXPriceReader
        reader = DEXPriceReader()
        assert reader is not None

    def test_enum_types(self):
        from qubitcoin.stablecoin.dex_price import DEXType, PriceSource
        assert DEXType.UNISWAP_V3 is not None
        assert DEXType.PANCAKESWAP_V3 is not None
        assert DEXType.ORCA_WHIRLPOOL is not None
        assert DEXType.AERODROME is not None
        assert DEXType.CAMELOT is not None
        assert PriceSource.TWAP is not None
        assert PriceSource.SPOT is not None
        assert PriceSource.CACHED is not None
        assert PriceSource.MANUAL is not None

    def test_dataclass_price_reading(self):
        from qubitcoin.stablecoin.dex_price import DEXPriceReading, DEXType, PriceSource
        reading = DEXPriceReading(
            chain_id=1,
            chain_name="Ethereum",
            dex=DEXType.UNISWAP_V3,
            pool_address="0xabc",
            token_pair="wQUSD/USDC",
            price=Decimal("1.002"),
            price_usd=Decimal("1.002"),
            source=PriceSource.TWAP,
            timestamp=time.time(),
            block_number=1000,
        )
        assert reading.chain_id == 1
        assert reading.price == Decimal("1.002")
        assert reading.dex == DEXType.UNISWAP_V3

    def test_dataclass_chain_price_state(self):
        from qubitcoin.stablecoin.dex_price import ChainPriceState
        state = ChainPriceState(
            chain_id=1,
            chain_name="Ethereum",
            wqusd_usd=Decimal("0.998"),
        )
        assert state.chain_name == "Ethereum"
        assert state.wqusd_usd == Decimal("0.998")

    def test_get_wqusd_prices_empty(self):
        """With no RPC providers, returns empty prices."""
        from qubitcoin.stablecoin.dex_price import DEXPriceReader
        reader = DEXPriceReader()
        prices = reader.get_wqusd_prices()
        assert isinstance(prices, dict)

    def test_get_max_wqusd_deviation_no_data(self):
        """Deviation is 0 when no price data available."""
        from qubitcoin.stablecoin.dex_price import DEXPriceReader
        reader = DEXPriceReader()
        dev, chain, price = reader.get_max_wqusd_deviation()
        assert dev == Decimal("0")

    def test_get_price_spread_no_data(self):
        """Spread is 0 when no data."""
        from qubitcoin.stablecoin.dex_price import DEXPriceReader
        reader = DEXPriceReader()
        spread_info = reader.get_price_spread()
        assert isinstance(spread_info, dict)
        assert spread_info["spread"] == Decimal("0")

    def test_get_status(self):
        """Status returns valid structure."""
        from qubitcoin.stablecoin.dex_price import DEXPriceReader
        reader = DEXPriceReader()
        status = reader.get_status()
        assert "chains" in status
        assert "max_deviation" in status
        assert "spread" in status

    def test_decode_sqrtPriceX96(self):
        """Test sqrtPriceX96 decoding helper."""
        from qubitcoin.stablecoin.dex_price import _decode_sqrtPriceX96
        # sqrt(1.0) * 2^96 = 2^96 when decimals are same
        sqrt_price = 2**96
        price = _decode_sqrtPriceX96(sqrt_price, 18, 18)
        assert abs(price - Decimal("1.0")) < Decimal("0.001")

    def test_decode_sqrtPriceX96_different_decimals(self):
        """Test with different decimal places (USDC has 6 decimals)."""
        from qubitcoin.stablecoin.dex_price import _decode_sqrtPriceX96
        # When token0 has 18 decimals and token1 has 6 decimals
        # price scales by 10^(18-6) = 10^12
        sqrt_price = 2**96  # Raw 1.0
        price = _decode_sqrtPriceX96(sqrt_price, 18, 6)
        assert price > 0

    def test_compute_twap(self):
        """Test TWAP computation from tick cumulatives."""
        from qubitcoin.stablecoin.dex_price import _compute_twap_from_ticks
        # If tick is 0, price = 1.0001^0 = 1.0
        tick_cum_end = 0
        tick_cum_start = 0
        elapsed = 600  # 10 min
        price = _compute_twap_from_ticks(tick_cum_end, tick_cum_start, elapsed, 18, 6)
        assert price is not None

    def test_decode_orca_sqrt_price(self):
        """Test Orca Q64.64 sqrt price decoding."""
        from qubitcoin.stablecoin.dex_price import _decode_orca_sqrt_price
        # sqrt(1.0) in Q64.64 = 2^64
        sqrt_q64 = 2**64
        price = _decode_orca_sqrt_price(sqrt_q64, 9, 6)
        assert price > 0

    def test_manual_price_setting(self):
        """Test manual price injection for testing."""
        from qubitcoin.stablecoin.dex_price import DEXPriceReader
        reader = DEXPriceReader()
        # Manual key format: "{chain_id}:{pair_key}_usd" where pair_key
        # comes from pool config (e.g. "wqusd_usdc")
        reader.set_manual_price("1:wqusd_usdc_usd", Decimal("0.985"))
        reader.set_manual_price("56:wqusd_usdt_usd", Decimal("1.015"))
        prices = reader.get_wqusd_prices()
        assert prices.get(1) == Decimal("0.985")
        assert prices.get(56) == Decimal("1.015")

    def test_cache_ttl(self):
        """Verify cache TTL constant."""
        from qubitcoin.stablecoin.dex_price import DEXPriceReader
        assert DEXPriceReader.CACHE_TTL > 0


# ============================================================================
# ArbitrageCalculator Tests
# ============================================================================

class TestArbitrageCalculator:
    """Test cross-chain arbitrage profitability calculator."""

    def test_import(self):
        from qubitcoin.stablecoin.arbitrage import ArbitrageCalculator
        calc = ArbitrageCalculator()
        assert calc is not None

    def test_enum_types(self):
        from qubitcoin.stablecoin.arbitrage import ArbType, ArbAction
        assert ArbType.PEG_FLOOR is not None
        assert ArbType.PEG_CEILING is not None
        assert ArbType.CROSS_CHAIN is not None
        assert ArbAction.BUY_WQUSD is not None
        assert ArbAction.SELL_WQUSD is not None

    def test_gas_estimate_dataclass(self):
        from qubitcoin.stablecoin.arbitrage import GasEstimate
        est = GasEstimate(chain_id=1, chain_name="Ethereum",
                          gas_units=200_000, gas_price_gwei=Decimal("30"),
                          cost_native=Decimal("0.006"), cost_usd=Decimal("15.0"),
                          native_token="ETH")
        assert est.chain_id == 1
        assert est.cost_usd == Decimal("15.0")

    def test_arb_opportunity_dataclass(self):
        from qubitcoin.stablecoin.arbitrage import ArbOpportunity, ArbType, ArbAction
        opp = ArbOpportunity(
            id="test_1",
            arb_type=ArbType.PEG_FLOOR,
            action=ArbAction.BUY_WQUSD,
            chain_id=1, chain_name="Ethereum",
            current_price=Decimal("0.98"),
            target_price=Decimal("1.00"),
            spread_bps=200,
            trade_size_usd=Decimal("10000"),
            gross_profit_usd=Decimal("200"),
            gas_cost_usd=Decimal("15.0"),
            bridge_fee_usd=Decimal("10"),
            net_profit_usd=Decimal("175"),
            roi_pct=Decimal("1.75"),
            profitable=True,
            confidence=0.9,
            timestamp=time.time(),
        )
        assert opp.profitable is True
        assert opp.spread_bps == 200

    def test_analyze_peg_floor(self):
        """Detect peg floor opportunity."""
        from qubitcoin.stablecoin.arbitrage import ArbitrageCalculator
        calc = ArbitrageCalculator()
        prices = {1: Decimal("0.97"), 56: Decimal("0.995")}
        opps = calc.analyze_peg_opportunities(prices)
        # Should detect ETH floor depeg
        floor_opps = [o for o in opps if o.arb_type.name == "PEG_FLOOR"]
        assert len(floor_opps) >= 1
        assert floor_opps[0].chain_id == 1

    def test_analyze_peg_ceiling(self):
        """Detect peg ceiling opportunity."""
        from qubitcoin.stablecoin.arbitrage import ArbitrageCalculator
        calc = ArbitrageCalculator()
        prices = {1: Decimal("1.03"), 56: Decimal("1.001")}
        opps = calc.analyze_peg_opportunities(prices)
        ceiling_opps = [o for o in opps if o.arb_type.name == "PEG_CEILING"]
        assert len(ceiling_opps) >= 1

    def test_analyze_no_depeg(self):
        """No opportunities when price is within band."""
        from qubitcoin.stablecoin.arbitrage import ArbitrageCalculator
        calc = ArbitrageCalculator()
        prices = {1: Decimal("0.998"), 56: Decimal("1.001")}
        opps = calc.analyze_peg_opportunities(prices)
        assert len(opps) == 0

    def test_analyze_cross_chain(self):
        """Detect cross-chain spread opportunities."""
        from qubitcoin.stablecoin.arbitrage import ArbitrageCalculator
        calc = ArbitrageCalculator()
        prices = {1: Decimal("0.97"), 42161: Decimal("1.02")}
        opps = calc.analyze_cross_chain_opportunities(prices)
        assert len(opps) >= 1

    def test_analyze_all(self):
        """analyze_all combines both opportunity types."""
        from qubitcoin.stablecoin.arbitrage import ArbitrageCalculator
        calc = ArbitrageCalculator()
        prices = {1: Decimal("0.96"), 56: Decimal("1.04")}
        all_opps = calc.analyze_all(prices)
        assert isinstance(all_opps, list)
        assert len(all_opps) >= 2  # At least floor + ceiling

    def test_get_current_opportunities(self):
        """After analyze, can retrieve results."""
        from qubitcoin.stablecoin.arbitrage import ArbitrageCalculator
        calc = ArbitrageCalculator()
        prices = {1: Decimal("0.96"), 42161: Decimal("1.03")}
        calc.analyze_all(prices)
        opps = calc.get_current_opportunities(profitable_only=False)
        assert isinstance(opps, list)

    def test_get_summary(self):
        """Summary returns valid structure."""
        from qubitcoin.stablecoin.arbitrage import ArbitrageCalculator
        calc = ArbitrageCalculator()
        summary = calc.get_summary()
        assert "total_opportunities" in summary
        assert "profitable_opportunities" in summary

    def test_opp_to_dict(self):
        """Verify serialization helper."""
        from qubitcoin.stablecoin.arbitrage import (
            ArbOpportunity, ArbType, ArbAction, _opp_to_dict,
        )
        opp = ArbOpportunity(
            id="test_1",
            arb_type=ArbType.PEG_FLOOR, action=ArbAction.BUY_WQUSD,
            chain_id=1, chain_name="Ethereum",
            current_price=Decimal("0.98"), target_price=Decimal("1.0"),
            spread_bps=200, trade_size_usd=Decimal("10000"),
            gross_profit_usd=Decimal("200"),
            gas_cost_usd=Decimal("15"), bridge_fee_usd=Decimal("10"),
            net_profit_usd=Decimal("175"), roi_pct=Decimal("1.75"),
            profitable=True, confidence=0.9, timestamp=time.time(),
        )
        d = _opp_to_dict(opp)
        assert d["chain_id"] == 1
        assert d["type"] == ArbType.PEG_FLOOR.value
        assert d["profitable"] is True

    def test_gas_estimates_all_chains(self):
        """Each supported chain has a gas estimate."""
        from qubitcoin.stablecoin.arbitrage import _GAS_ESTIMATES
        for chain_id in [1, 56, 42161, 10]:
            assert chain_id in _GAS_ESTIMATES
            assert _GAS_ESTIMATES[chain_id].cost_usd > 0

    def test_empty_prices(self):
        """Empty dict returns no opps."""
        from qubitcoin.stablecoin.arbitrage import ArbitrageCalculator
        calc = ArbitrageCalculator()
        assert calc.analyze_peg_opportunities({}) == []
        assert calc.analyze_cross_chain_opportunities({}) == []

    def test_none_prices_filtered(self):
        """None prices are filtered out."""
        from qubitcoin.stablecoin.arbitrage import ArbitrageCalculator
        calc = ArbitrageCalculator()
        prices = {1: None, 56: Decimal("0.99")}
        opps = calc.analyze_peg_opportunities(prices)
        # Only BSC matters — no depeg at 0.99 (within band)
        assert isinstance(opps, list)


# ============================================================================
# QUSDKeeper Tests
# ============================================================================

class TestQUSDKeeper:
    """Test QUSD peg keeper daemon."""

    def _make_keeper(self, **kwargs):
        from qubitcoin.stablecoin.keeper import QUSDKeeper
        return QUSDKeeper(**kwargs)

    def test_import(self):
        from qubitcoin.stablecoin.keeper import QUSDKeeper, KeeperMode, KeeperConfig
        keeper = QUSDKeeper()
        assert keeper is not None

    def test_keeper_mode_enum(self):
        from qubitcoin.stablecoin.keeper import KeeperMode
        assert KeeperMode.OFF == 0
        assert KeeperMode.SCAN == 1
        assert KeeperMode.PERIODIC == 2
        assert KeeperMode.CONTINUOUS == 3
        assert KeeperMode.AGGRESSIVE == 4

    def test_signal_types(self):
        from qubitcoin.stablecoin.keeper import SignalType
        assert SignalType.DEPEG_FLOOR == "depeg_floor"
        assert SignalType.DEPEG_CEILING == "depeg_ceiling"
        assert SignalType.CROSS_CHAIN_ARB == "cross_chain_arb"
        assert SignalType.HEALTHY == "healthy"

    def test_lifecycle_start_stop(self):
        from qubitcoin.stablecoin.keeper import KeeperMode
        keeper = self._make_keeper()
        assert not keeper.is_running
        keeper.start(KeeperMode.SCAN)
        assert keeper.is_running
        assert keeper.config.mode == KeeperMode.SCAN
        keeper.stop()
        assert not keeper.is_running
        assert keeper.config.mode == KeeperMode.OFF

    def test_pause_resume(self):
        from qubitcoin.stablecoin.keeper import KeeperMode
        keeper = self._make_keeper()
        keeper.start(KeeperMode.CONTINUOUS)
        assert not keeper._paused
        keeper.pause()
        assert keeper._paused
        keeper.resume()
        assert not keeper._paused

    def test_set_mode(self):
        from qubitcoin.stablecoin.keeper import KeeperMode
        keeper = self._make_keeper()
        keeper.start(KeeperMode.SCAN)
        keeper.set_mode(KeeperMode.AGGRESSIVE)
        assert keeper.config.mode == KeeperMode.AGGRESSIVE

    def test_update_config(self):
        keeper = self._make_keeper()
        keeper.update_config(check_interval_blocks=5, cooldown_blocks=20)
        assert keeper.config.check_interval_blocks == 5
        assert keeper.config.cooldown_blocks == 20

    def test_on_block_off_mode_noop(self):
        """Block tick when OFF mode does nothing."""
        from qubitcoin.stablecoin.keeper import KeeperMode
        keeper = self._make_keeper()
        keeper.config.mode = KeeperMode.OFF
        keeper.on_block(100)  # Should not crash
        assert keeper._last_check_block == 0

    def test_on_block_scan_mode(self):
        """Scan mode checks every block but never executes."""
        from qubitcoin.stablecoin.keeper import KeeperMode
        mock_dex = MagicMock()
        mock_dex.get_wqusd_prices.return_value = {1: Decimal("0.95")}
        keeper = self._make_keeper(dex_reader=mock_dex)
        keeper.start(KeeperMode.SCAN)
        keeper.on_block(10)
        assert keeper._last_check_block == 10
        # Scan mode should detect signal but NOT execute
        assert keeper._total_depeg_events >= 1
        assert keeper._total_actions == 0

    def test_on_block_periodic_interval(self):
        """Periodic mode respects check interval."""
        from qubitcoin.stablecoin.keeper import KeeperMode
        keeper = self._make_keeper()
        keeper.start(KeeperMode.PERIODIC)
        keeper.config.check_interval_blocks = 10
        keeper._last_check_block = 100
        keeper.on_block(105)  # Should skip (only 5 blocks since last)
        assert keeper._last_check_block == 100

    def test_on_block_periodic_triggers(self):
        """Periodic mode triggers when interval reached."""
        from qubitcoin.stablecoin.keeper import KeeperMode
        keeper = self._make_keeper()
        keeper.start(KeeperMode.PERIODIC)
        keeper.config.check_interval_blocks = 10
        keeper._last_check_block = 100
        keeper.on_block(111)  # Should trigger (11 blocks since last)
        assert keeper._last_check_block == 111

    def test_on_block_continuous_checks_every_block(self):
        """Continuous mode checks every block."""
        from qubitcoin.stablecoin.keeper import KeeperMode
        keeper = self._make_keeper()
        keeper.start(KeeperMode.CONTINUOUS)
        keeper.on_block(100)
        assert keeper._last_check_block == 100
        keeper.on_block(101)
        assert keeper._last_check_block == 101

    def test_signal_detection_floor_depeg(self):
        """Floor depeg signal detected when price < 0.99."""
        from qubitcoin.stablecoin.keeper import KeeperMode, SignalType
        mock_dex = MagicMock()
        mock_dex.get_wqusd_prices.return_value = {
            1: Decimal("0.97"),
            42161: Decimal("1.00"),
        }
        keeper = self._make_keeper(dex_reader=mock_dex)
        keeper.start(KeeperMode.SCAN)
        keeper.on_block(10)
        signals = keeper.get_signals(100)
        floor_sigs = [s for s in signals if s["type"] == SignalType.DEPEG_FLOOR]
        assert len(floor_sigs) >= 1
        assert floor_sigs[0]["chain_id"] == 1

    def test_signal_detection_ceiling_depeg(self):
        """Ceiling depeg signal detected when price > 1.01."""
        from qubitcoin.stablecoin.keeper import KeeperMode, SignalType
        mock_dex = MagicMock()
        mock_dex.get_wqusd_prices.return_value = {56: Decimal("1.03")}
        keeper = self._make_keeper(dex_reader=mock_dex)
        keeper.start(KeeperMode.SCAN)
        keeper.on_block(10)
        signals = keeper.get_signals(100)
        ceil_sigs = [s for s in signals if s["type"] == SignalType.DEPEG_CEILING]
        assert len(ceil_sigs) >= 1

    def test_signal_detection_cross_chain_spread(self):
        """Cross-chain spread signal when spread > 1%."""
        from qubitcoin.stablecoin.keeper import KeeperMode, SignalType
        mock_dex = MagicMock()
        mock_dex.get_wqusd_prices.return_value = {
            1: Decimal("0.97"),
            42161: Decimal("1.02"),
        }
        keeper = self._make_keeper(dex_reader=mock_dex)
        keeper.start(KeeperMode.SCAN)
        keeper.on_block(10)
        signals = keeper.get_signals(100)
        cross = [s for s in signals if s["type"] == SignalType.CROSS_CHAIN_ARB]
        assert len(cross) >= 1

    def test_signal_detection_fund_depleted(self):
        """Fund depletion warning when below threshold."""
        from qubitcoin.stablecoin.keeper import KeeperMode, SignalType
        keeper = self._make_keeper()
        keeper.start(KeeperMode.SCAN)
        keeper._stability_fund_qbc = Decimal("5000")  # Below min_fund_warning (100k)
        keeper.on_block(10)
        signals = keeper.get_signals(100)
        fund_sigs = [s for s in signals if s["type"] == SignalType.FUND_DEPLETED]
        assert len(fund_sigs) >= 1

    def test_action_execution_continuous(self):
        """Continuous mode executes actions on depeg."""
        from qubitcoin.stablecoin.keeper import KeeperMode
        mock_dex = MagicMock()
        mock_dex.get_wqusd_prices.return_value = {1: Decimal("0.97")}
        keeper = self._make_keeper(dex_reader=mock_dex)
        keeper.start(KeeperMode.CONTINUOUS)
        keeper._stability_fund_qbc = Decimal("500000")
        keeper.on_block(100)
        # In continuous mode, should execute (dry run since no QVM)
        assert keeper._total_actions >= 1

    def test_action_cooldown(self):
        """Cooldown prevents rapid-fire actions."""
        from qubitcoin.stablecoin.keeper import KeeperMode
        mock_dex = MagicMock()
        mock_dex.get_wqusd_prices.return_value = {1: Decimal("0.97")}
        keeper = self._make_keeper(dex_reader=mock_dex)
        keeper.start(KeeperMode.CONTINUOUS)
        keeper._stability_fund_qbc = Decimal("500000")
        keeper.config.cooldown_blocks = 10
        keeper.on_block(100)
        first_actions = keeper._total_actions
        keeper.on_block(105)  # Within cooldown
        assert keeper._total_actions == first_actions  # No new action

    def test_action_no_fund(self):
        """No action executed when fund is empty."""
        from qubitcoin.stablecoin.keeper import KeeperMode
        mock_dex = MagicMock()
        mock_dex.get_wqusd_prices.return_value = {1: Decimal("0.97")}
        keeper = self._make_keeper(dex_reader=mock_dex)
        keeper.start(KeeperMode.CONTINUOUS)
        keeper._stability_fund_qbc = Decimal("0")
        keeper.on_block(100)
        assert keeper._total_actions == 0

    def test_aggressive_mode_larger_trades(self):
        """Aggressive mode uses larger trade sizes."""
        from qubitcoin.stablecoin.keeper import KeeperMode
        mock_dex = MagicMock()
        mock_dex.get_wqusd_prices.return_value = {1: Decimal("0.95")}
        keeper = self._make_keeper(dex_reader=mock_dex)
        keeper.start(KeeperMode.AGGRESSIVE)
        keeper._stability_fund_qbc = Decimal("1000000")
        keeper.on_block(100)
        assert keeper._total_actions >= 1
        # Aggressive mode should use buy_qusd instead of trigger_rebalance
        actions = keeper.get_history(10)
        if actions:
            assert actions[0]["action_type"] == "buy_qusd"

    def test_ceiling_depeg_action(self):
        """Ceiling depeg triggers sell action."""
        from qubitcoin.stablecoin.keeper import KeeperMode
        mock_dex = MagicMock()
        mock_dex.get_wqusd_prices.return_value = {1: Decimal("1.05")}
        keeper = self._make_keeper(dex_reader=mock_dex)
        keeper.start(KeeperMode.CONTINUOUS)
        keeper._qusd_held = Decimal("500000")
        keeper.on_block(100)
        assert keeper._total_actions >= 1

    def test_get_status(self):
        """Status endpoint returns valid structure."""
        keeper = self._make_keeper()
        keeper.start()
        status = keeper.get_status()
        assert "mode" in status
        assert "running" in status
        assert "paused" in status
        assert "config" in status
        assert "prices" in status
        assert "recent_signals" in status

    def test_get_history(self):
        """History returns list of actions."""
        keeper = self._make_keeper()
        history = keeper.get_history(10)
        assert isinstance(history, list)

    def test_get_opportunities_no_arb(self):
        """Opportunities without arb calculator."""
        keeper = self._make_keeper()
        opps = keeper.get_opportunities()
        assert "opportunities" in opps
        assert opps["opportunities"] == []

    def test_get_opportunities_with_arb(self):
        """Opportunities with arb calculator."""
        from qubitcoin.stablecoin.arbitrage import ArbitrageCalculator
        calc = ArbitrageCalculator()
        keeper = self._make_keeper(arb_calc=calc)
        opps = keeper.get_opportunities()
        assert "opportunities" in opps

    def test_get_signals_empty(self):
        """Signals returns empty list initially."""
        keeper = self._make_keeper()
        signals = keeper.get_signals(10)
        assert signals == []

    def test_execute_manual(self):
        """Manual execution returns result."""
        keeper = self._make_keeper()
        result = keeper.execute_manual("trigger_rebalance", Decimal("1000"), 100)
        assert "success" in result

    def test_execute_manual_invalid_action(self):
        """Manual execution with invalid action type."""
        keeper = self._make_keeper()
        result = keeper.execute_manual("invalid_action", Decimal("1000"), 100)
        assert result["success"] is False
        assert "Unknown action" in result["error"]

    def test_max_history_cap(self):
        """History list is capped at MAX_HISTORY."""
        from qubitcoin.stablecoin.keeper import QUSDKeeper, KeeperAction
        keeper = QUSDKeeper()
        for i in range(1100):
            action = KeeperAction(
                action_id=f"test_{i}", action_type="trigger_rebalance",
                block_height=i, price=Decimal("0.98"),
                trade_size=Decimal("1000"), tx_hash=None,
                success=True, timestamp=time.time(),
            )
            keeper._record_action(action)
        assert len(keeper._actions) <= keeper.MAX_HISTORY

    def test_max_signals_cap(self):
        """Signals list is capped at MAX_SIGNALS."""
        from qubitcoin.stablecoin.keeper import QUSDKeeper, KeeperMode
        mock_dex = MagicMock()
        mock_dex.get_wqusd_prices.return_value = {1: Decimal("0.97")}
        keeper = QUSDKeeper(dex_reader=mock_dex)
        keeper.start(KeeperMode.SCAN)
        for i in range(600):
            keeper.on_block(i * 100)
        assert len(keeper._signals) <= keeper.MAX_SIGNALS

    def test_set_stabilizer_state(self):
        """Test manual stabilizer state injection."""
        keeper = self._make_keeper()
        keeper.set_stabilizer_state(
            Decimal("50000"), Decimal("25000"), True
        )
        assert keeper._stability_fund_qbc == Decimal("50000")
        assert keeper._qusd_held == Decimal("25000")
        assert keeper._auto_rebalance_enabled is True

    def test_paused_skips_execution(self):
        """Paused keeper skips execution but detects signals."""
        from qubitcoin.stablecoin.keeper import KeeperMode
        mock_dex = MagicMock()
        mock_dex.get_wqusd_prices.return_value = {1: Decimal("0.97")}
        keeper = self._make_keeper(dex_reader=mock_dex)
        keeper.start(KeeperMode.CONTINUOUS)
        keeper._stability_fund_qbc = Decimal("500000")
        keeper.pause()
        keeper.on_block(100)
        # Signals detected but actions NOT executed
        assert keeper._total_depeg_events >= 1
        assert keeper._total_actions == 0

    def test_severity_critical(self):
        """Critical severity when price < 0.95."""
        from qubitcoin.stablecoin.keeper import KeeperMode
        mock_dex = MagicMock()
        mock_dex.get_wqusd_prices.return_value = {1: Decimal("0.93")}
        keeper = self._make_keeper(dex_reader=mock_dex)
        keeper.start(KeeperMode.SCAN)
        keeper.on_block(10)
        signals = keeper.get_signals(10)
        depeg = [s for s in signals if s["type"] == "depeg_floor"]
        assert depeg[0]["severity"] == "critical"


# ============================================================================
# KeeperConfig Tests
# ============================================================================

class TestKeeperConfig:
    """Test keeper configuration loading from Config."""

    def test_config_vars_exist(self):
        """Keeper config vars are defined in Config."""
        from qubitcoin.config import Config
        assert hasattr(Config, 'KEEPER_ENABLED')
        assert hasattr(Config, 'KEEPER_DEFAULT_MODE')
        assert hasattr(Config, 'KEEPER_CHECK_INTERVAL')
        assert hasattr(Config, 'KEEPER_MAX_TRADE_SIZE')
        assert hasattr(Config, 'KEEPER_FLOOR_PRICE')
        assert hasattr(Config, 'KEEPER_CEILING_PRICE')
        assert hasattr(Config, 'KEEPER_COOLDOWN_BLOCKS')
        assert hasattr(Config, 'QUSD_STABILIZER_ADDRESS')

    def test_config_defaults(self):
        """Keeper config defaults are reasonable."""
        from qubitcoin.config import Config
        assert Config.KEEPER_ENABLED is True
        assert Config.KEEPER_DEFAULT_MODE == 'scan'
        assert Config.KEEPER_CHECK_INTERVAL == 10
        assert Config.KEEPER_FLOOR_PRICE == 0.99
        assert Config.KEEPER_CEILING_PRICE == 1.01
        assert Config.KEEPER_COOLDOWN_BLOCKS == 10


# ============================================================================
# Prometheus Metrics Tests
# ============================================================================

class TestKeeperMetrics:
    """Test keeper Prometheus metrics exist."""

    def test_metrics_defined(self):
        """All keeper metrics are defined."""
        from qubitcoin.utils.metrics import (
            qusd_keeper_mode, qusd_keeper_last_check_block,
            qusd_keeper_actions_total, qusd_keeper_depeg_events_total,
            qusd_keeper_stability_fund, qusd_keeper_max_deviation,
            qusd_keeper_paused, qusd_keeper_arb_opportunities,
        )
        assert qusd_keeper_mode is not None
        assert qusd_keeper_last_check_block is not None
        assert qusd_keeper_actions_total is not None
        assert qusd_keeper_depeg_events_total is not None
        assert qusd_keeper_stability_fund is not None
        assert qusd_keeper_max_deviation is not None
        assert qusd_keeper_paused is not None
        assert qusd_keeper_arb_opportunities is not None

    def test_metrics_exportable(self):
        """Keeper metrics are in __all__."""
        from qubitcoin.utils import metrics
        all_exports = metrics.__all__
        assert 'qusd_keeper_mode' in all_exports
        assert 'qusd_keeper_stability_fund' in all_exports


# ============================================================================
# BridgeVault.sol Fee Configurability Tests
# ============================================================================

class TestBridgeVaultFee:
    """Test BridgeVault.sol fee configurability changes."""

    def test_bridgevault_sol_exists(self):
        """BridgeVault.sol file exists."""
        import os
        path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'src', 'qubitcoin',
            'contracts', 'solidity', 'bridge', 'BridgeVault.sol'
        )
        assert os.path.exists(os.path.normpath(path))

    def test_fee_is_state_variable(self):
        """feeBps is a state variable, not a constant."""
        import os
        path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), '..', '..', 'src', 'qubitcoin',
            'contracts', 'solidity', 'bridge', 'BridgeVault.sol'
        ))
        with open(path, 'r') as f:
            content = f.read()
        # Should NOT be a constant
        assert 'uint256 public constant feeBps' not in content
        # Should be a state variable
        assert 'uint256 public feeBps' in content

    def test_max_fee_bps_constant(self):
        """MAX_FEE_BPS constant exists at 1000 (10%)."""
        import os
        path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), '..', '..', 'src', 'qubitcoin',
            'contracts', 'solidity', 'bridge', 'BridgeVault.sol'
        ))
        with open(path, 'r') as f:
            content = f.read()
        assert 'MAX_FEE_BPS' in content
        assert '1000' in content

    def test_set_fee_bps_function(self):
        """setFeeBps function exists."""
        import os
        path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), '..', '..', 'src', 'qubitcoin',
            'contracts', 'solidity', 'bridge', 'BridgeVault.sol'
        ))
        with open(path, 'r') as f:
            content = f.read()
        assert 'function setFeeBps' in content
        assert 'onlyOwner' in content

    def test_fee_bps_updated_event(self):
        """FeeBpsUpdated event exists."""
        import os
        path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), '..', '..', 'src', 'qubitcoin',
            'contracts', 'solidity', 'bridge', 'BridgeVault.sol'
        ))
        with open(path, 'r') as f:
            content = f.read()
        assert 'event FeeBpsUpdated' in content

    def test_fee_initialized_in_initialize(self):
        """feeBps is set to 10 in initialize()."""
        import os
        path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), '..', '..', 'src', 'qubitcoin',
            'contracts', 'solidity', 'bridge', 'BridgeVault.sol'
        ))
        with open(path, 'r') as f:
            content = f.read()
        assert 'feeBps = 10' in content


# ============================================================================
# RPC Endpoint Integration Tests (lightweight, no running server)
# ============================================================================

class TestKeeperRPCEndpoints:
    """Test that keeper RPC endpoints are registered."""

    def _get_app_routes(self):
        """Get route list from a test app."""
        from qubitcoin.network.rpc import create_rpc_app
        db = MagicMock()
        db.get_current_height.return_value = 0
        db.get_total_supply.return_value = 0
        db.get_balance.return_value = 0
        db.query_one.return_value = None
        db.get_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)
        consensus = MagicMock()
        mining = MagicMock()
        quantum = MagicMock()
        ipfs = MagicMock()
        app = create_rpc_app(db, consensus, mining, quantum, ipfs)
        return [route.path for route in app.routes]

    def test_keeper_status_route(self):
        routes = self._get_app_routes()
        assert "/keeper/status" in routes

    def test_keeper_mode_route(self):
        routes = self._get_app_routes()
        assert "/keeper/mode" in routes

    def test_keeper_config_route(self):
        routes = self._get_app_routes()
        assert "/keeper/config" in routes

    def test_keeper_history_route(self):
        routes = self._get_app_routes()
        assert "/keeper/history" in routes

    def test_keeper_opportunities_route(self):
        routes = self._get_app_routes()
        assert "/keeper/opportunities" in routes

    def test_keeper_signals_route(self):
        routes = self._get_app_routes()
        assert "/keeper/signals" in routes

    def test_keeper_execute_route(self):
        routes = self._get_app_routes()
        assert "/keeper/execute" in routes

    def test_keeper_pause_route(self):
        routes = self._get_app_routes()
        assert "/keeper/pause" in routes

    def test_keeper_resume_route(self):
        routes = self._get_app_routes()
        assert "/keeper/resume" in routes

    def test_keeper_prices_route(self):
        routes = self._get_app_routes()
        assert "/keeper/prices" in routes

    def test_keeper_arb_summary_route(self):
        routes = self._get_app_routes()
        assert "/keeper/arb/summary" in routes

    def test_keeper_set_mode_route(self):
        routes = self._get_app_routes()
        assert "/keeper/mode/{mode_name}" in routes
