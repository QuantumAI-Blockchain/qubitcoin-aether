"""Unit tests for bridge validator reward tracking."""
import pytest
from unittest.mock import MagicMock


class TestValidatorRewardTrackerInit:
    """Test ValidatorRewardTracker initialization."""

    def test_default_reward(self):
        """Tracker uses Config default reward per verification."""
        from qubitcoin.bridge.validator_rewards import ValidatorRewardTracker
        tracker = ValidatorRewardTracker()
        assert tracker.reward_per_verification == 0.01

    def test_custom_reward(self):
        """Tracker accepts custom reward per verification."""
        from qubitcoin.bridge.validator_rewards import ValidatorRewardTracker
        tracker = ValidatorRewardTracker(reward_per_verification=0.05)
        assert tracker.reward_per_verification == 0.05

    def test_initial_stats_empty(self):
        """Initial stats show zero validators and verifications."""
        from qubitcoin.bridge.validator_rewards import ValidatorRewardTracker
        tracker = ValidatorRewardTracker()
        stats = tracker.get_stats()
        assert stats["total_validators"] == 0
        assert stats["total_verifications"] == 0
        assert stats["total_rewards_qbc"] == 0


class TestRecordVerification:
    """Test recording proof verifications."""

    def _make_tracker(self, reward: float = 0.01):
        from qubitcoin.bridge.validator_rewards import ValidatorRewardTracker
        return ValidatorRewardTracker(reward_per_verification=reward)

    def test_single_verification(self):
        """Record a single verification and check stats."""
        tracker = self._make_tracker()
        tracker.record_verification("0xValidator1", "ethereum", "proof_hash_1")
        stats = tracker.get_stats()
        assert stats["total_validators"] == 1
        assert stats["total_verifications"] == 1
        assert stats["total_rewards_qbc"] == 0.01

    def test_multiple_verifications_same_validator(self):
        """Same validator can verify multiple proofs."""
        tracker = self._make_tracker(reward=0.1)
        tracker.record_verification("0xVal", "ethereum", "proof1")
        tracker.record_verification("0xVal", "polygon", "proof2")
        tracker.record_verification("0xVal", "ethereum", "proof3")
        stats = tracker.get_validator_stats("0xVal")
        assert stats["verification_count"] == 3
        assert stats["total_rewards_qbc"] == pytest.approx(0.3)

    def test_duplicate_proof_ignored(self):
        """Same proof hash cannot be recorded twice."""
        tracker = self._make_tracker()
        tracker.record_verification("0xVal1", "ethereum", "same_proof")
        tracker.record_verification("0xVal2", "ethereum", "same_proof")  # duplicate
        stats = tracker.get_stats()
        assert stats["total_verifications"] == 1
        assert stats["processed_proofs"] == 1

    def test_case_insensitive_validator(self):
        """Validator addresses are normalized to lowercase."""
        tracker = self._make_tracker()
        tracker.record_verification("0xABC", "ethereum", "proof1")
        tracker.record_verification("0xabc", "ethereum", "proof2")
        stats = tracker.get_stats()
        assert stats["total_validators"] == 1
        assert stats["total_verifications"] == 2


class TestCalculateRewards:
    """Test reward calculation."""

    def _make_tracker(self, reward: float = 0.01):
        from qubitcoin.bridge.validator_rewards import ValidatorRewardTracker
        return ValidatorRewardTracker(reward_per_verification=reward)

    def test_rewards_all_bridges(self):
        """Calculate rewards across all bridges."""
        tracker = self._make_tracker(reward=0.1)
        tracker.record_verification("0xA", "ethereum", "p1")
        tracker.record_verification("0xA", "polygon", "p2")
        tracker.record_verification("0xB", "ethereum", "p3")
        rewards = tracker.calculate_rewards()
        assert rewards["0xa"] == pytest.approx(0.2)
        assert rewards["0xb"] == pytest.approx(0.1)

    def test_rewards_filtered_by_bridge(self):
        """Calculate rewards for a specific bridge only."""
        tracker = self._make_tracker(reward=0.1)
        tracker.record_verification("0xA", "ethereum", "p1")
        tracker.record_verification("0xA", "polygon", "p2")
        tracker.record_verification("0xB", "ethereum", "p3")
        rewards = tracker.calculate_rewards(bridge_name="ethereum")
        assert rewards["0xa"] == pytest.approx(0.1)
        assert rewards["0xb"] == pytest.approx(0.1)

    def test_empty_rewards(self):
        """Empty tracker returns empty rewards."""
        tracker = self._make_tracker()
        assert tracker.calculate_rewards() == {}


class TestValidatorStats:
    """Test individual validator statistics."""

    def _make_tracker(self):
        from qubitcoin.bridge.validator_rewards import ValidatorRewardTracker
        return ValidatorRewardTracker(reward_per_verification=0.05)

    def test_validator_stats_detail(self):
        """Validator stats include per-bridge breakdown."""
        tracker = self._make_tracker()
        tracker.record_verification("0xVal", "ethereum", "p1")
        tracker.record_verification("0xVal", "ethereum", "p2")
        tracker.record_verification("0xVal", "polygon", "p3")
        stats = tracker.get_validator_stats("0xVal")
        assert stats["verification_count"] == 3
        assert stats["total_rewards_qbc"] == pytest.approx(0.15)
        assert stats["bridge_breakdown"]["ethereum"] == 2
        assert stats["bridge_breakdown"]["polygon"] == 1
        assert len(stats["recent_verifications"]) == 3

    def test_unknown_validator_stats(self):
        """Stats for unknown validator return zeros."""
        tracker = self._make_tracker()
        stats = tracker.get_validator_stats("0xUnknown")
        assert stats["verification_count"] == 0
        assert stats["total_rewards_qbc"] == 0


class TestTopValidators:
    """Test top validators ranking."""

    def _make_tracker(self):
        from qubitcoin.bridge.validator_rewards import ValidatorRewardTracker
        return ValidatorRewardTracker(reward_per_verification=0.01)

    def test_top_validators_ordered(self):
        """Top validators are sorted by verification count."""
        tracker = self._make_tracker()
        tracker.record_verification("0xA", "eth", "p1")
        tracker.record_verification("0xB", "eth", "p2")
        tracker.record_verification("0xB", "eth", "p3")
        tracker.record_verification("0xC", "eth", "p4")
        tracker.record_verification("0xC", "eth", "p5")
        tracker.record_verification("0xC", "eth", "p6")
        top = tracker.get_top_validators(limit=2)
        assert len(top) == 2
        assert top[0]["validator"] == "0xc"
        assert top[0]["verification_count"] == 3
        assert top[1]["validator"] == "0xb"
        assert top[1]["verification_count"] == 2

    def test_top_validators_empty(self):
        """Empty tracker returns empty list."""
        tracker = self._make_tracker()
        assert tracker.get_top_validators() == []
