"""
Tests for BridgeLPRewards (Item E17 — lp_rewards.py).

Verifies:
  - add_liquidity / remove_liquidity via the rewards wrapper
  - calculate_rewards aggregation across chains
  - claim_rewards with cooldown enforcement
  - update_rewards per-block distribution
  - get_provider_stats / get_pool_stats reporting
  - Edge cases (cooldown, empty providers, chain filtering)
"""

import time
from unittest.mock import patch, MagicMock

import pytest


# ============================================================================
# Fixtures
# ============================================================================

class FakeConfig:
    """Test configuration with fast reward rates."""
    BRIDGE_LP_REWARD_RATE = 0.5
    BRIDGE_LP_REWARD_RATE_BPS = 10000  # 100% APY for easier math
    BRIDGE_LP_MIN_LIQUIDITY = 10.0
    BRIDGE_LP_MIN_DEPOSIT = 10.0
    BRIDGE_LP_REWARD_COOLDOWN_BLOCKS = 10


@pytest.fixture
def rewards():
    """Create a BridgeLPRewards with test-friendly defaults."""
    with patch('qubitcoin.bridge.liquidity_pool.Config') as MockConfig:
        MockConfig.BRIDGE_LP_REWARD_RATE_BPS = 10000
        MockConfig.BRIDGE_LP_MIN_DEPOSIT = 10.0

        from qubitcoin.bridge.lp_rewards import BridgeLPRewards
        return BridgeLPRewards(config=FakeConfig)


@pytest.fixture
def rewards_no_cooldown():
    """Create a BridgeLPRewards with zero cooldown."""

    class NoCooldownConfig(FakeConfig):
        BRIDGE_LP_REWARD_COOLDOWN_BLOCKS = 0

    with patch('qubitcoin.bridge.liquidity_pool.Config') as MockConfig:
        MockConfig.BRIDGE_LP_REWARD_RATE_BPS = 10000
        MockConfig.BRIDGE_LP_MIN_DEPOSIT = 10.0

        from qubitcoin.bridge.lp_rewards import BridgeLPRewards
        return BridgeLPRewards(config=NoCooldownConfig)


# ============================================================================
# Tests: add_liquidity
# ============================================================================

class TestAddLiquidity:
    """Tests for adding liquidity through the rewards wrapper."""

    def test_add_creates_position(self, rewards):
        """Should create a new LP position and update total_liquidity."""
        pos = rewards.add_liquidity('provider1', 'ethereum', 100.0)
        assert pos.provider == 'provider1'
        assert pos.chain == 'ethereum'
        assert pos.amount == 100.0
        assert rewards.total_liquidity == 100.0

    def test_add_multiple_chains_tracks_total(self, rewards):
        """Total liquidity should aggregate across chains."""
        rewards.add_liquidity('p1', 'ethereum', 100.0)
        rewards.add_liquidity('p1', 'polygon', 50.0)
        assert rewards.total_liquidity == 150.0

    def test_add_below_minimum_rejected(self, rewards):
        """Should reject deposits below the minimum liquidity."""
        with pytest.raises(ValueError, match="below minimum"):
            rewards.add_liquidity('p1', 'ethereum', 5.0)

    def test_add_to_existing_position(self, rewards):
        """Adding to existing position should accumulate."""
        rewards.add_liquidity('p1', 'ethereum', 100.0)
        pos = rewards.add_liquidity('p1', 'ethereum', 50.0)
        assert pos.amount == 150.0
        assert rewards.total_liquidity == 150.0


# ============================================================================
# Tests: remove_liquidity
# ============================================================================

class TestRemoveLiquidity:
    """Tests for removing liquidity."""

    def test_remove_full(self, rewards):
        """Full removal should return withdrawn amount."""
        rewards.add_liquidity('p1', 'ethereum', 100.0)
        withdrawn = rewards.remove_liquidity('p1', 'ethereum', 100.0)
        assert withdrawn == 100.0
        assert rewards.total_liquidity == 0.0

    def test_remove_partial(self, rewards):
        """Partial removal should leave remaining position."""
        rewards.add_liquidity('p1', 'ethereum', 100.0)
        withdrawn = rewards.remove_liquidity('p1', 'ethereum', 40.0)
        assert withdrawn == 40.0
        assert rewards.total_liquidity == 60.0

    def test_remove_nonexistent_rejected(self, rewards):
        """Should reject removal from nonexistent position."""
        with pytest.raises(ValueError, match="No LP position"):
            rewards.remove_liquidity('p1', 'ethereum', 50.0)


# ============================================================================
# Tests: calculate_rewards
# ============================================================================

class TestCalculateRewards:
    """Tests for reward calculation."""

    def test_rewards_near_zero_initially(self, rewards):
        """Rewards should be near zero right after deposit."""
        rewards.add_liquidity('p1', 'ethereum', 100.0)
        total = rewards.calculate_rewards('p1')
        assert total < 0.01

    def test_rewards_accumulate_over_time(self, rewards):
        """Rewards should accumulate with time elapsed."""
        from qubitcoin.bridge.liquidity_pool import SECONDS_PER_YEAR

        rewards.add_liquidity('p1', 'ethereum', 1000.0)

        # Manually set last_reward_timestamp to 1 year ago
        key = ('p1', 'ethereum')
        pos = rewards._pool._positions[key]
        pos.last_reward_timestamp = time.time() - SECONDS_PER_YEAR

        total = rewards.calculate_rewards('p1')
        # 100% APY on 1000 QBC for 1 year = ~1000 QBC
        assert total > 900.0
        assert total < 1100.0

    def test_rewards_aggregate_chains(self, rewards):
        """Should aggregate rewards across multiple chains."""
        from qubitcoin.bridge.liquidity_pool import SECONDS_PER_YEAR

        rewards.add_liquidity('p1', 'ethereum', 1000.0)
        rewards.add_liquidity('p1', 'polygon', 500.0)

        # Set both positions to 1 day ago
        now = time.time()
        for key, pos in rewards._pool._positions.items():
            pos.last_reward_timestamp = now - 86400

        total = rewards.calculate_rewards('p1')
        # Should be > 0 combining both chains
        assert total > 0


# ============================================================================
# Tests: claim_rewards
# ============================================================================

class TestClaimRewards:
    """Tests for claiming rewards."""

    def test_claim_collects_accumulated(self, rewards_no_cooldown):
        """Claim should collect all accumulated rewards."""
        from qubitcoin.bridge.liquidity_pool import SECONDS_PER_YEAR

        r = rewards_no_cooldown
        r.add_liquidity('p1', 'ethereum', 1000.0)

        # Set time 1 day ago to accrue rewards
        key = ('p1', 'ethereum')
        pos = r._pool._positions[key]
        pos.last_reward_timestamp = time.time() - 86400

        claimed = r.claim_rewards('p1')
        assert claimed > 0

    def test_claim_enforces_cooldown(self, rewards):
        """Should reject claim if within cooldown period."""
        rewards.add_liquidity('p1', 'ethereum', 100.0)

        # First claim at block 100 should succeed
        rewards.claim_rewards('p1', block_height=100)

        # Second claim at block 105 (within 10-block cooldown) should fail
        with pytest.raises(ValueError, match="cooldown"):
            rewards.claim_rewards('p1', block_height=105)

    def test_claim_after_cooldown_succeeds(self, rewards):
        """Should allow claim after cooldown expires."""
        from qubitcoin.bridge.liquidity_pool import SECONDS_PER_YEAR

        rewards.add_liquidity('p1', 'ethereum', 1000.0)

        # First claim
        key = ('p1', 'ethereum')
        pos = rewards._pool._positions[key]
        pos.last_reward_timestamp = time.time() - 86400
        rewards.claim_rewards('p1', block_height=100)

        # Set more time for rewards to accrue
        pos.last_reward_timestamp = time.time() - 86400

        # Claim after cooldown (100 + 10 = 110)
        claimed = rewards.claim_rewards('p1', block_height=111)
        assert claimed >= 0  # May be 0 if no time passed

    def test_claim_no_positions_rejected(self, rewards):
        """Should reject claim for provider with no positions."""
        with pytest.raises(ValueError, match="No LP positions"):
            rewards.claim_rewards('nonexistent', block_height=100)

    def test_claim_records_history(self, rewards_no_cooldown):
        """Claims should be recorded in claim history."""
        r = rewards_no_cooldown
        r.add_liquidity('p1', 'ethereum', 100.0)

        key = ('p1', 'ethereum')
        pos = r._pool._positions[key]
        pos.last_reward_timestamp = time.time() - 86400

        r.claim_rewards('p1', block_height=50)
        assert len(r._claims) == 1
        assert r._claims[0].provider == 'p1'
        assert r._claims[0].block_height == 50


# ============================================================================
# Tests: update_rewards
# ============================================================================

class TestUpdateRewards:
    """Tests for per-block reward updates."""

    def test_update_processes_positions(self, rewards):
        """update_rewards should distribute to positions with accrued time."""
        rewards.add_liquidity('p1', 'ethereum', 100.0)

        key = ('p1', 'ethereum')
        pos = rewards._pool._positions[key]
        pos.last_reward_timestamp = time.time() - 3600  # 1 hour ago

        rewards.update_rewards(block_height=1)
        assert pos.accumulated_rewards > 0

    def test_update_idempotent_same_block(self, rewards):
        """Calling update_rewards twice on same block should be a no-op."""
        rewards.add_liquidity('p1', 'ethereum', 100.0)

        key = ('p1', 'ethereum')
        pos = rewards._pool._positions[key]
        pos.last_reward_timestamp = time.time() - 3600

        rewards.update_rewards(block_height=1)
        first_rewards = pos.accumulated_rewards

        rewards.update_rewards(block_height=1)  # Same block
        assert pos.accumulated_rewards == first_rewards

    def test_update_tracks_last_block(self, rewards):
        """Should track the last processed block height."""
        rewards.update_rewards(block_height=42)
        assert rewards._last_update_block == 42


# ============================================================================
# Tests: get_provider_stats
# ============================================================================

class TestProviderStats:
    """Tests for provider statistics."""

    def test_stats_returns_positions(self, rewards):
        """Should return all positions for the provider."""
        rewards.add_liquidity('p1', 'ethereum', 100.0)
        rewards.add_liquidity('p1', 'polygon', 50.0)

        stats = rewards.get_provider_stats('p1')
        assert stats['provider'] == 'p1'
        assert len(stats['positions']) == 2
        assert stats['total_staked'] == 150.0
        assert stats['cooldown_blocks'] == 10

    def test_stats_empty_provider(self, rewards):
        """Should return empty positions for unknown provider."""
        stats = rewards.get_provider_stats('unknown')
        assert stats['total_staked'] == 0.0
        assert len(stats['positions']) == 0


# ============================================================================
# Tests: get_pool_stats
# ============================================================================

class TestPoolStats:
    """Tests for pool statistics."""

    def test_stats_empty_pool(self, rewards):
        """Empty pool should return zero stats."""
        stats = rewards.get_pool_stats()
        assert stats['total_liquidity'] == 0.0
        assert stats['total_providers'] == 0
        assert stats['cooldown_blocks'] == 10
        assert stats['reward_rate_per_block'] == 0.5

    def test_stats_with_deposits(self, rewards):
        """Stats should reflect deposited amounts."""
        rewards.add_liquidity('p1', 'ethereum', 100.0)
        rewards.add_liquidity('p2', 'polygon', 200.0)

        stats = rewards.get_pool_stats()
        assert stats['total_liquidity'] == 300.0
        assert stats['total_providers'] == 2
        assert 'ethereum' in stats['chains']
        assert 'polygon' in stats['chains']

    def test_stats_chain_filter(self, rewards):
        """Should filter stats to a specific chain."""
        rewards.add_liquidity('p1', 'ethereum', 100.0)
        rewards.add_liquidity('p2', 'polygon', 200.0)

        eth_stats = rewards.get_pool_stats(chain='ethereum')
        assert eth_stats['chain'] == 'ethereum'
        assert eth_stats['total_liquidity'] == 100.0
