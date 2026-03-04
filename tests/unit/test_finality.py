"""Tests for BFT Finality Gadget."""

import pytest
from unittest.mock import MagicMock, patch

from qubitcoin.consensus.finality import (
    FinalityGadget, FinalityStatus, ValidatorInfo,
    _PythonFinalityCore,
)


@pytest.fixture()
def mock_db():
    db = MagicMock()
    db.get_session.side_effect = Exception("no db in unit tests")
    return db


@pytest.fixture()
def gadget(mock_db):
    from qubitcoin.config import Config
    Config.FINALITY_ENABLED = True
    Config.FINALITY_MIN_STAKE = 100.0
    Config.FINALITY_THRESHOLD = 0.667
    Config.FINALITY_VOTE_EXPIRY_BLOCKS = 1000
    return FinalityGadget(mock_db)


# ── Python Fallback Core Tests ────────────────────────────────────────


class TestPythonFinalityCore:
    def test_add_validator(self):
        core = _PythonFinalityCore(0.667, 1000)
        core.add_validator("v1", 100.0)
        assert core.validator_count() == 1
        assert core.total_stake() == 100.0

    def test_remove_validator(self):
        core = _PythonFinalityCore(0.667, 1000)
        core.add_validator("v1", 100.0)
        core.remove_validator("v1")
        assert core.validator_count() == 0

    def test_record_vote(self):
        core = _PythonFinalityCore(0.667, 1000)
        core.add_validator("v1", 100.0)
        assert core.record_vote("v1", 1, "hash1")
        assert core.vote_count(1) == 1

    def test_duplicate_vote_rejected(self):
        core = _PythonFinalityCore(0.667, 1000)
        core.add_validator("v1", 100.0)
        assert core.record_vote("v1", 1, "hash1")
        assert not core.record_vote("v1", 1, "hash1")

    def test_non_validator_rejected(self):
        core = _PythonFinalityCore(0.667, 1000)
        assert not core.record_vote("unknown", 1, "hash1")

    def test_finality_reached(self):
        core = _PythonFinalityCore(0.66, 1000)
        core.add_validator("v1", 100.0)
        core.add_validator("v2", 100.0)
        core.add_validator("v3", 100.0)

        core.record_vote("v1", 10, "hash10")
        assert not core.check_finality(10)

        core.record_vote("v2", 10, "hash10")
        assert core.check_finality(10)  # 2/3 = 0.667 >= 0.66

    def test_finality_unequal_stakes(self):
        core = _PythonFinalityCore(0.667, 1000)
        core.add_validator("whale", 1000.0)
        core.add_validator("small", 10.0)

        core.record_vote("whale", 5, "hash5")
        assert core.check_finality(5)  # 1000/1010 > 0.667

    def test_already_finalized(self):
        core = _PythonFinalityCore(0.667, 1000)
        core.add_validator("v1", 100.0)
        core.record_vote("v1", 10, "hash10")
        core.check_finality(10)
        assert core.check_finality(5)  # Below finalized

    def test_calculate_vote_weight(self):
        core = _PythonFinalityCore(0.667, 1000)
        core.add_validator("v1", 100.0)
        core.add_validator("v2", 200.0)
        core.record_vote("v1", 1, "hash1")
        voted, total = core.calculate_vote_weight(1)
        assert voted == 100.0
        assert total == 300.0

    def test_prune_votes(self):
        core = _PythonFinalityCore(0.667, 100)
        core.add_validator("v1", 100.0)
        core.record_vote("v1", 10, "hash10")
        core.record_vote("v1", 200, "hash200")
        core.prune_votes(200)
        assert core.vote_count(10) == 0
        assert core.vote_count(200) == 1

    def test_last_finalized(self):
        core = _PythonFinalityCore(0.667, 1000)
        core.add_validator("v1", 100.0)
        core.record_vote("v1", 5, "hash5")
        core.check_finality(5)
        assert core.get_last_finalized() == 5

    def test_no_validators_no_finality(self):
        core = _PythonFinalityCore(0.667, 1000)
        assert not core.check_finality(1)


# ── FinalityGadget Tests ──────────────────────────────────────────────


class TestFinalityGadget:
    def test_register_validator(self, gadget):
        assert gadget.register_validator("v1", 200.0, 100)
        assert gadget.get_validator_count() == 1
        assert gadget.get_total_stake() == 200.0

    def test_register_below_min_stake(self, gadget):
        assert not gadget.register_validator("v1", 10.0, 100)
        assert gadget.get_validator_count() == 0

    def test_unregister_validator(self, gadget):
        gadget.register_validator("v1", 200.0, 100)
        assert gadget.unregister_validator("v1")
        assert gadget.get_validator_count() == 0

    def test_submit_vote(self, gadget):
        gadget.register_validator("v1", 200.0, 100)
        assert gadget.submit_vote("v1", 50, "hash50")

    def test_submit_vote_non_validator(self, gadget):
        assert not gadget.submit_vote("unknown", 50, "hash50")

    def test_submit_vote_duplicate(self, gadget):
        gadget.register_validator("v1", 200.0, 100)
        assert gadget.submit_vote("v1", 50, "hash50")
        assert not gadget.submit_vote("v1", 50, "hash50")

    def test_finality_check(self, gadget):
        gadget.register_validator("v1", 200.0, 100)
        gadget.register_validator("v2", 200.0, 100)
        gadget.register_validator("v3", 200.0, 100)

        gadget.submit_vote("v1", 50, "hash50")
        assert not gadget.check_finality(50)

        gadget.submit_vote("v2", 50, "hash50")
        gadget.submit_vote("v3", 50, "hash50")
        assert gadget.check_finality(50)

    def test_get_last_finalized(self, gadget):
        gadget.register_validator("v1", 200.0, 100)
        gadget.submit_vote("v1", 10, "hash10")
        gadget.check_finality(10)
        assert gadget.get_last_finalized() == 10

    def test_finality_status(self, gadget):
        gadget.register_validator("v1", 200.0, 100)
        gadget.submit_vote("v1", 10, "hash10")

        status = gadget.get_finality_status(10)
        assert isinstance(status, FinalityStatus)
        assert status.block_height == 10
        assert status.is_finalized  # Only 1 validator, 100%
        assert status.voted_stake == 200.0
        assert status.total_stake == 200.0
        assert status.vote_ratio == 1.0
        assert status.voter_count == 1

    def test_process_block_prunes(self, gadget):
        gadget.register_validator("v1", 200.0, 100)
        gadget.submit_vote("v1", 10, "hash10")
        gadget.process_block(2000)
        # After pruning, vote at height 10 should be gone
        status = gadget.get_finality_status(10)
        assert status.voter_count == 0

    def test_auto_vote_if_validator(self, gadget):
        gadget.register_validator("v1", 200.0, 100)
        assert gadget.auto_vote_if_validator(50, "hash50", "v1")

    def test_auto_vote_not_validator(self, gadget):
        assert not gadget.auto_vote_if_validator(50, "hash50", "unknown")

    def test_is_reorg_allowed_no_finality(self, gadget):
        assert gadget.is_reorg_allowed(5)

    def test_is_reorg_allowed_above_finalized(self, gadget):
        gadget.register_validator("v1", 200.0, 100)
        gadget.submit_vote("v1", 10, "hash10")
        gadget.check_finality(10)
        assert gadget.is_reorg_allowed(15)

    def test_is_reorg_blocked_below_finalized(self, gadget):
        gadget.register_validator("v1", 200.0, 100)
        gadget.submit_vote("v1", 10, "hash10")
        gadget.check_finality(10)
        assert not gadget.is_reorg_allowed(5)

    def test_multiple_validators_threshold(self, gadget):
        """Test that the 2/3 threshold works correctly."""
        gadget._threshold = 0.667
        gadget.register_validator("v1", 100.0, 100)
        gadget.register_validator("v2", 100.0, 100)
        gadget.register_validator("v3", 100.0, 100)

        gadget.submit_vote("v1", 20, "hash20")
        assert not gadget.check_finality(20)  # 1/3 < 0.667

        gadget.submit_vote("v2", 20, "hash20")
        # 2/3 = 0.6667 < 0.667 — NOT finalized (strict threshold)
        # This is by design: exactly 2/3 is not enough for 0.667 threshold
        assert not gadget.check_finality(20)

        gadget.submit_vote("v3", 20, "hash20")
        assert gadget.check_finality(20)  # 3/3 = 1.0 >= 0.667

    def test_weighted_threshold(self, gadget):
        """Stake-weighted: one large validator can finalize."""
        gadget.register_validator("whale", 1000.0, 100)
        gadget.register_validator("small1", 100.0, 100)
        gadget.register_validator("small2", 100.0, 100)

        gadget.submit_vote("whale", 30, "hash30")
        # whale has 1000/1200 = 83.3% > 66.7%
        assert gadget.check_finality(30)

    def test_get_validators_empty(self, gadget):
        # DB will fail, should return empty list
        validators = gadget.get_validators()
        assert validators == []
