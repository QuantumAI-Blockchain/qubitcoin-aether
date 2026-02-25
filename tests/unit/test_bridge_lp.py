"""
Tests for bridge liquidity pool LP rewards (Item E17).

Verifies:
  - add_liquidity validation and position tracking
  - remove_liquidity with proportional rewards
  - calculate_rewards time-weighted calculation
  - distribute_rewards batch processing
  - get_pool_stats reporting
  - Edge cases (minimum deposit, over-withdrawal, etc.)
"""

import time
from unittest.mock import patch

import pytest


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def pool():
    """Create a BridgeLiquidityPool with test-friendly defaults."""
    with patch('qubitcoin.bridge.liquidity_pool.Config') as MockConfig:
        MockConfig.BRIDGE_LP_REWARD_RATE_BPS = 500  # 5% APY
        MockConfig.BRIDGE_LP_MIN_DEPOSIT = 10.0

        from qubitcoin.bridge.liquidity_pool import BridgeLiquidityPool
        return BridgeLiquidityPool(reward_rate_bps=500, min_deposit=10.0)


@pytest.fixture
def pool_high_rate():
    """Create a pool with very high reward rate for testing (100% APY)."""
    with patch('qubitcoin.bridge.liquidity_pool.Config') as MockConfig:
        MockConfig.BRIDGE_LP_REWARD_RATE_BPS = 10000  # 100% APY
        MockConfig.BRIDGE_LP_MIN_DEPOSIT = 1.0

        from qubitcoin.bridge.liquidity_pool import BridgeLiquidityPool
        return BridgeLiquidityPool(reward_rate_bps=10000, min_deposit=1.0)


# ============================================================================
# Tests: add_liquidity
# ============================================================================

class TestAddLiquidity:
    """Tests for adding liquidity to bridge pools."""

    def test_add_basic(self, pool):
        """Should create a new LP position."""
        pos = pool.add_liquidity('provider1', 'ethereum', 100.0)
        assert pos.provider == 'provider1'
        assert pos.chain == 'ethereum'
        assert pos.amount == 100.0
        assert pos.accumulated_rewards == 0.0

    def test_add_updates_pool_total(self, pool):
        """Pool total should reflect deposited amount."""
        pool.add_liquidity('p1', 'ethereum', 100.0)
        pool.add_liquidity('p2', 'ethereum', 50.0)
        assert pool._pool_totals['ethereum'] == 150.0

    def test_add_below_minimum_rejected(self, pool):
        """Should reject deposits below minimum."""
        with pytest.raises(ValueError, match="below minimum"):
            pool.add_liquidity('p1', 'ethereum', 5.0)

    def test_add_zero_rejected(self, pool):
        """Should reject zero deposit."""
        with pytest.raises(ValueError, match="positive"):
            pool.add_liquidity('p1', 'ethereum', 0.0)

    def test_add_negative_rejected(self, pool):
        """Should reject negative deposit."""
        with pytest.raises(ValueError, match="positive"):
            pool.add_liquidity('p1', 'ethereum', -10.0)

    def test_add_to_existing_position(self, pool):
        """Adding to existing position should accumulate amount."""
        pool.add_liquidity('p1', 'ethereum', 100.0)
        pos = pool.add_liquidity('p1', 'ethereum', 50.0)
        assert pos.amount == 150.0
        assert pool._pool_totals['ethereum'] == 150.0

    def test_add_different_chains(self, pool):
        """Positions on different chains should be separate."""
        pool.add_liquidity('p1', 'ethereum', 100.0)
        pool.add_liquidity('p1', 'polygon', 50.0)
        assert pool._pool_totals['ethereum'] == 100.0
        assert pool._pool_totals['polygon'] == 50.0

    def test_add_normalizes_provider(self, pool):
        """Provider address should be normalized (lowercase, stripped)."""
        pos = pool.add_liquidity(' Provider1 ', 'ethereum', 100.0)
        assert pos.provider == 'provider1'


# ============================================================================
# Tests: remove_liquidity
# ============================================================================

class TestRemoveLiquidity:
    """Tests for removing liquidity from bridge pools."""

    def test_remove_full_position(self, pool):
        """Removing full amount should delete the position."""
        pool.add_liquidity('p1', 'ethereum', 100.0)
        withdrawn, rewards = pool.remove_liquidity('p1', 'ethereum', 100.0)
        assert withdrawn == 100.0
        stats = pool.get_pool_stats()
        assert stats['total_positions'] == 0

    def test_remove_partial(self, pool):
        """Partial removal should leave remaining position."""
        pool.add_liquidity('p1', 'ethereum', 100.0)
        withdrawn, rewards = pool.remove_liquidity('p1', 'ethereum', 40.0)
        assert withdrawn == 40.0
        positions = pool.get_provider_positions('p1')
        assert len(positions) == 1
        assert positions[0]['amount'] == 60.0

    def test_remove_over_balance_rejected(self, pool):
        """Should reject withdrawal exceeding position balance."""
        pool.add_liquidity('p1', 'ethereum', 100.0)
        with pytest.raises(ValueError, match="exceeds position"):
            pool.remove_liquidity('p1', 'ethereum', 200.0)

    def test_remove_nonexistent_rejected(self, pool):
        """Should reject withdrawal from nonexistent position."""
        with pytest.raises(ValueError, match="No LP position"):
            pool.remove_liquidity('p1', 'ethereum', 50.0)

    def test_remove_zero_rejected(self, pool):
        """Should reject zero withdrawal."""
        pool.add_liquidity('p1', 'ethereum', 100.0)
        with pytest.raises(ValueError, match="positive"):
            pool.remove_liquidity('p1', 'ethereum', 0.0)

    def test_remove_updates_pool_total(self, pool):
        """Pool total should decrease on withdrawal."""
        pool.add_liquidity('p1', 'ethereum', 100.0)
        pool.remove_liquidity('p1', 'ethereum', 40.0)
        assert pool._pool_totals['ethereum'] == 60.0


# ============================================================================
# Tests: calculate_rewards
# ============================================================================

class TestCalculateRewards:
    """Tests for reward calculation."""

    def test_rewards_zero_at_start(self, pool):
        """Rewards should be zero immediately after deposit."""
        pool.add_liquidity('p1', 'ethereum', 100.0)
        # Since time hasn't passed, rewards should be near zero
        rewards = pool.calculate_rewards('p1')
        # Might be a tiny value due to time between add and calculate
        assert 'ethereum' not in rewards or rewards.get('ethereum', 0) < 0.01

    def test_rewards_accumulate_with_time(self, pool_high_rate):
        """Rewards should accumulate proportionally to time elapsed."""
        from qubitcoin.bridge.liquidity_pool import LPPosition, SECONDS_PER_YEAR

        pool_high_rate.add_liquidity('p1', 'ethereum', 1000.0)

        # Manually set last_reward_timestamp to 1 year ago
        key = ('p1', 'ethereum')
        pos = pool_high_rate._positions[key]
        pos.last_reward_timestamp = time.time() - SECONDS_PER_YEAR

        rewards = pool_high_rate.calculate_rewards('p1')
        # 100% APY on 1000 QBC for 1 year = ~1000 QBC
        assert rewards['ethereum'] > 900.0
        assert rewards['ethereum'] < 1100.0

    def test_rewards_proportional_to_amount(self, pool_high_rate):
        """Larger positions should earn more rewards."""
        from qubitcoin.bridge.liquidity_pool import SECONDS_PER_YEAR

        pool_high_rate.add_liquidity('p1', 'ethereum', 1000.0)
        pool_high_rate.add_liquidity('p2', 'ethereum', 500.0)

        # Set both to 1 day ago
        one_day = 86400
        now = time.time()
        for key, pos in pool_high_rate._positions.items():
            pos.last_reward_timestamp = now - one_day

        r1 = pool_high_rate.calculate_rewards('p1')
        r2 = pool_high_rate.calculate_rewards('p2')

        # p1 has 2x the amount of p2, so rewards should be ~2x
        assert abs(r1['ethereum'] / r2['ethereum'] - 2.0) < 0.01


# ============================================================================
# Tests: distribute_rewards
# ============================================================================

class TestDistributeRewards:
    """Tests for batch reward distribution."""

    def test_distribute_accrues_to_positions(self, pool_high_rate):
        """distribute_rewards should add pending rewards to accumulated_rewards."""
        from qubitcoin.bridge.liquidity_pool import SECONDS_PER_YEAR

        pool_high_rate.add_liquidity('p1', 'ethereum', 1000.0)

        key = ('p1', 'ethereum')
        pos = pool_high_rate._positions[key]
        pos.last_reward_timestamp = time.time() - 86400  # 1 day ago

        count = pool_high_rate.distribute_rewards()
        assert count == 1
        assert pos.accumulated_rewards > 0

    def test_distribute_records_events(self, pool_high_rate):
        """distribute_rewards should record distribution events."""
        pool_high_rate.add_liquidity('p1', 'ethereum', 100.0)

        key = ('p1', 'ethereum')
        pos = pool_high_rate._positions[key]
        pos.last_reward_timestamp = time.time() - 86400

        pool_high_rate.distribute_rewards()
        assert len(pool_high_rate._distributions) == 1
        assert pool_high_rate._distributions[0].provider == 'p1'


# ============================================================================
# Tests: get_pool_stats
# ============================================================================

class TestPoolStats:
    """Tests for pool statistics."""

    def test_stats_empty(self, pool):
        """Stats should be correct with empty pool."""
        stats = pool.get_pool_stats()
        assert stats['total_liquidity'] == 0.0
        assert stats['total_providers'] == 0
        assert stats['total_positions'] == 0
        assert stats['reward_rate_bps'] == 500
        assert stats['apy_percent'] == 5.0
        assert stats['min_deposit'] == 10.0

    def test_stats_with_deposits(self, pool):
        """Stats should reflect deposits correctly."""
        pool.add_liquidity('p1', 'ethereum', 100.0)
        pool.add_liquidity('p2', 'polygon', 200.0)
        stats = pool.get_pool_stats()
        assert stats['total_liquidity'] == 300.0
        assert stats['total_providers'] == 2
        assert stats['total_positions'] == 2
        assert 'ethereum' in stats['chains']
        assert 'polygon' in stats['chains']
        assert stats['chains']['ethereum']['total_liquidity'] == 100.0
        assert stats['chains']['polygon']['total_liquidity'] == 200.0

    def test_stats_recent_distributions(self, pool_high_rate):
        """Stats should include recent distribution events."""
        pool_high_rate.add_liquidity('p1', 'ethereum', 100.0)
        key = ('p1', 'ethereum')
        pool_high_rate._positions[key].last_reward_timestamp = time.time() - 86400
        pool_high_rate.distribute_rewards()

        stats = pool_high_rate.get_pool_stats()
        assert len(stats['recent_distributions']) == 1


# ============================================================================
# Tests: get_provider_positions
# ============================================================================

class TestProviderPositions:
    """Tests for querying provider positions."""

    def test_positions_empty(self, pool):
        """Should return empty list for unknown provider."""
        positions = pool.get_provider_positions('unknown')
        assert positions == []

    def test_positions_multiple_chains(self, pool):
        """Should return positions across all chains."""
        pool.add_liquidity('p1', 'ethereum', 100.0)
        pool.add_liquidity('p1', 'polygon', 50.0)
        positions = pool.get_provider_positions('p1')
        assert len(positions) == 2
        chains = {p['chain'] for p in positions}
        assert chains == {'ethereum', 'polygon'}

    def test_positions_include_pool_share(self, pool):
        """Positions should include pool share calculation."""
        pool.add_liquidity('p1', 'ethereum', 100.0)
        pool.add_liquidity('p2', 'ethereum', 100.0)
        positions = pool.get_provider_positions('p1')
        assert len(positions) == 1
        assert abs(positions[0]['pool_share'] - 0.5) < 0.01
