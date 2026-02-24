"""
Tests for bridge relayer incentive system (E13).

Covers: RelayerIncentive class — stake management, relay recording,
reward calculation, claim flow, deduplication, and statistics.
"""
import pytest
from decimal import Decimal

from qubitcoin.bridge.relayer_incentive import RelayerIncentive, RelayEvent


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def incentive() -> RelayerIncentive:
    """Create a RelayerIncentive with known test parameters."""
    return RelayerIncentive(
        reward_per_relay=0.05,
        min_stake=100.0,
        value_bonus_bps=5,
    )


@pytest.fixture
def staked_incentive(incentive: RelayerIncentive) -> RelayerIncentive:
    """Create a RelayerIncentive with a pre-staked relayer."""
    incentive.register_stake("0xrelayer1", Decimal("500"))
    return incentive


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================

class TestRelayerIncentiveInit:
    def test_default_params(self, incentive: RelayerIncentive) -> None:
        assert incentive.reward_per_relay == Decimal("0.05")
        assert incentive.min_stake == Decimal("100.0")
        assert incentive.value_bonus_bps == 5

    def test_custom_params(self) -> None:
        ri = RelayerIncentive(reward_per_relay=0.10, min_stake=50.0, value_bonus_bps=10)
        assert ri.reward_per_relay == Decimal("0.1")
        assert ri.min_stake == Decimal("50.0")
        assert ri.value_bonus_bps == 10

    def test_empty_state(self, incentive: RelayerIncentive) -> None:
        stats = incentive.get_stats()
        assert stats["total_relayers"] == 0
        assert stats["total_relays"] == 0
        assert stats["processed_messages"] == 0


# ============================================================================
# STAKE MANAGEMENT TESTS
# ============================================================================

class TestStakeManagement:
    def test_register_stake_meets_minimum(self, incentive: RelayerIncentive) -> None:
        result = incentive.register_stake("0xrelayer1", Decimal("100"))
        assert result is True
        assert incentive.get_stake("0xrelayer1") == Decimal("100")

    def test_register_stake_below_minimum(self, incentive: RelayerIncentive) -> None:
        result = incentive.register_stake("0xrelayer1", Decimal("50"))
        assert result is False
        assert incentive.get_stake("0xrelayer1") == Decimal("50")

    def test_register_stake_negative_rejected(self, incentive: RelayerIncentive) -> None:
        result = incentive.register_stake("0xrelayer1", Decimal("-10"))
        assert result is False

    def test_get_stake_unknown_relayer(self, incentive: RelayerIncentive) -> None:
        assert incentive.get_stake("0xunknown") == Decimal(0)

    def test_is_eligible(self, incentive: RelayerIncentive) -> None:
        incentive.register_stake("0xrelayer1", Decimal("200"))
        assert incentive.is_eligible("0xrelayer1") is True

    def test_is_not_eligible(self, incentive: RelayerIncentive) -> None:
        incentive.register_stake("0xrelayer1", Decimal("50"))
        assert incentive.is_eligible("0xrelayer1") is False

    def test_case_insensitive_address(self, incentive: RelayerIncentive) -> None:
        incentive.register_stake("0xRelayer1", Decimal("100"))
        assert incentive.get_stake("0xrelayer1") == Decimal("100")
        assert incentive.is_eligible("0XRELAYER1") is True


# ============================================================================
# REWARD CALCULATION TESTS
# ============================================================================

class TestRewardCalculation:
    def test_base_reward_only(self, incentive: RelayerIncentive) -> None:
        reward = incentive.calculate_reward(Decimal(0))
        assert reward == Decimal("0.05")

    def test_reward_with_value_bonus(self, incentive: RelayerIncentive) -> None:
        # base=0.05, bonus = 1000 * 5 / 10000 = 0.5
        reward = incentive.calculate_reward(Decimal("1000"))
        assert reward == Decimal("0.55")

    def test_reward_with_small_value(self, incentive: RelayerIncentive) -> None:
        # base=0.05, bonus = 10 * 5 / 10000 = 0.005
        reward = incentive.calculate_reward(Decimal("10"))
        assert reward == Decimal("0.055")

    def test_reward_zero_bonus_bps(self) -> None:
        ri = RelayerIncentive(reward_per_relay=0.05, min_stake=100.0, value_bonus_bps=0)
        reward = ri.calculate_reward(Decimal("1000"))
        assert reward == Decimal("0.05")


# ============================================================================
# RELAY RECORDING TESTS
# ============================================================================

class TestRecordRelay:
    def test_record_relay_returns_event(self, staked_incentive: RelayerIncentive) -> None:
        event = staked_incentive.record_relay(
            relayer="0xrelayer1",
            source_chain="ethereum",
            dest_chain="polygon",
            message_hash="0xabc123",
            message_value=Decimal("100"),
        )
        assert event is not None
        assert isinstance(event, RelayEvent)
        assert event.relayer == "0xrelayer1"
        assert event.source_chain == "ethereum"
        assert event.dest_chain == "polygon"
        assert event.claimed is False

    def test_duplicate_message_ignored(self, staked_incentive: RelayerIncentive) -> None:
        staked_incentive.record_relay(
            "0xrelayer1", "ethereum", "polygon", "0xdup", Decimal("50")
        )
        result = staked_incentive.record_relay(
            "0xrelayer1", "ethereum", "polygon", "0xdup", Decimal("50")
        )
        assert result is None
        stats = staked_incentive.get_stats()
        assert stats["total_relays"] == 1

    def test_record_relay_tracks_chain_counts(
        self, staked_incentive: RelayerIncentive
    ) -> None:
        staked_incentive.record_relay(
            "0xrelayer1", "ethereum", "polygon", "0xmsg1", Decimal("10")
        )
        staked_incentive.record_relay(
            "0xrelayer1", "ethereum", "polygon", "0xmsg2", Decimal("20")
        )
        staked_incentive.record_relay(
            "0xrelayer1", "bsc", "ethereum", "0xmsg3", Decimal("30")
        )
        stats = staked_incentive.get_stats()
        assert stats["route_counts"]["ethereum->polygon"] == 2
        assert stats["route_counts"]["bsc->ethereum"] == 1

    def test_record_relay_unstaked_still_records(
        self, incentive: RelayerIncentive
    ) -> None:
        # Unstaked relayer can still relay, rewards just not claimable
        event = incentive.record_relay(
            "0xunstaked", "ethereum", "polygon", "0xmsg1", Decimal("10")
        )
        assert event is not None
        stats = incentive.get_stats()
        assert stats["total_relays"] == 1


# ============================================================================
# REWARD CLAIM TESTS
# ============================================================================

class TestRewardClaims:
    def test_pending_rewards_eligible(self, staked_incentive: RelayerIncentive) -> None:
        staked_incentive.record_relay(
            "0xrelayer1", "ethereum", "polygon", "0xmsg1", Decimal("100")
        )
        pending = staked_incentive.get_pending_rewards("0xrelayer1")
        expected = staked_incentive.calculate_reward(Decimal("100"))
        assert pending == expected

    def test_pending_rewards_ineligible(self, incentive: RelayerIncentive) -> None:
        # Record relay without stake
        incentive.record_relay(
            "0xrelayer1", "ethereum", "polygon", "0xmsg1", Decimal("100")
        )
        pending = incentive.get_pending_rewards("0xrelayer1")
        assert pending == Decimal(0)

    def test_claim_rewards_eligible(self, staked_incentive: RelayerIncentive) -> None:
        staked_incentive.record_relay(
            "0xrelayer1", "ethereum", "polygon", "0xmsg1", Decimal("100")
        )
        staked_incentive.record_relay(
            "0xrelayer1", "bsc", "polygon", "0xmsg2", Decimal("200")
        )
        claimed = staked_incentive.claim_rewards("0xrelayer1")
        expected = (
            staked_incentive.calculate_reward(Decimal("100"))
            + staked_incentive.calculate_reward(Decimal("200"))
        )
        assert claimed == expected
        # After claiming, pending should be zero
        assert staked_incentive.get_pending_rewards("0xrelayer1") == Decimal(0)

    def test_claim_rewards_ineligible(self, incentive: RelayerIncentive) -> None:
        incentive.record_relay(
            "0xrelayer1", "ethereum", "polygon", "0xmsg1", Decimal("100")
        )
        claimed = incentive.claim_rewards("0xrelayer1")
        assert claimed == Decimal(0)

    def test_double_claim_returns_zero(
        self, staked_incentive: RelayerIncentive
    ) -> None:
        staked_incentive.record_relay(
            "0xrelayer1", "ethereum", "polygon", "0xmsg1", Decimal("100")
        )
        first_claim = staked_incentive.claim_rewards("0xrelayer1")
        assert first_claim > 0
        second_claim = staked_incentive.claim_rewards("0xrelayer1")
        assert second_claim == Decimal(0)

    def test_claim_after_additional_relays(
        self, staked_incentive: RelayerIncentive
    ) -> None:
        staked_incentive.record_relay(
            "0xrelayer1", "ethereum", "polygon", "0xmsg1", Decimal("100")
        )
        staked_incentive.claim_rewards("0xrelayer1")
        staked_incentive.record_relay(
            "0xrelayer1", "ethereum", "bsc", "0xmsg2", Decimal("200")
        )
        pending = staked_incentive.get_pending_rewards("0xrelayer1")
        expected = staked_incentive.calculate_reward(Decimal("200"))
        assert pending == expected


# ============================================================================
# STATISTICS TESTS
# ============================================================================

class TestStatistics:
    def test_get_relayer_stats(self, staked_incentive: RelayerIncentive) -> None:
        staked_incentive.record_relay(
            "0xrelayer1", "ethereum", "polygon", "0xmsg1", Decimal("100")
        )
        stats = staked_incentive.get_relayer_stats("0xrelayer1")
        assert stats["relay_count"] == 1
        assert stats["eligible"] is True
        assert Decimal(stats["total_rewards_qbc"]) > 0
        assert stats["route_breakdown"]["ethereum->polygon"] == 1

    def test_get_relayer_stats_unknown(self, incentive: RelayerIncentive) -> None:
        stats = incentive.get_relayer_stats("0xunknown")
        assert stats["relay_count"] == 0
        assert stats["eligible"] is False

    def test_get_top_relayers(self, staked_incentive: RelayerIncentive) -> None:
        staked_incentive.register_stake("0xrelayer2", Decimal("200"))
        for i in range(3):
            staked_incentive.record_relay(
                "0xrelayer1", "ethereum", "polygon", f"0xmsg1_{i}", Decimal("10")
            )
        for i in range(5):
            staked_incentive.record_relay(
                "0xrelayer2", "bsc", "ethereum", f"0xmsg2_{i}", Decimal("10")
            )
        top = staked_incentive.get_top_relayers(limit=2)
        assert len(top) == 2
        assert top[0]["relayer"] == "0xrelayer2"
        assert top[0]["relay_count"] == 5
        assert top[1]["relayer"] == "0xrelayer1"
        assert top[1]["relay_count"] == 3

    def test_get_stats_aggregate(self, staked_incentive: RelayerIncentive) -> None:
        staked_incentive.record_relay(
            "0xrelayer1", "ethereum", "polygon", "0xmsg1", Decimal("100")
        )
        staked_incentive.record_relay(
            "0xrelayer1", "bsc", "polygon", "0xmsg2", Decimal("200")
        )
        stats = staked_incentive.get_stats()
        assert stats["total_relayers"] == 1
        assert stats["total_relays"] == 2
        assert stats["eligible_relayers"] == 1
        assert stats["processed_messages"] == 2
        assert Decimal(stats["total_rewards_qbc"]) > 0
        assert Decimal(stats["total_value_relayed"]) == Decimal("300")
