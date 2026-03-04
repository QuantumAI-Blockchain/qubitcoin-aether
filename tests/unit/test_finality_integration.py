"""Integration tests for BFT Finality Gadget — endpoint + consensus wiring."""

import pytest
from unittest.mock import MagicMock

from qubitcoin.consensus.finality import FinalityGadget


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


class TestFinalityEndpoints:
    def test_finality_status(self, gadget):
        gadget.register_validator("v1", 500.0, 10)
        gadget.submit_vote("v1", 50, "hash50")
        status = gadget.get_finality_status(50)
        assert status.is_finalized
        assert status.last_finalized_height == 50

    def test_register_and_vote(self, gadget):
        assert gadget.register_validator("v1", 200.0, 1)
        assert gadget.register_validator("v2", 200.0, 1)
        assert gadget.register_validator("v3", 200.0, 1)

        # All three vote
        assert gadget.submit_vote("v1", 100, "hash100")
        assert gadget.submit_vote("v2", 100, "hash100")
        assert gadget.submit_vote("v3", 100, "hash100")

        assert gadget.check_finality(100)
        assert gadget.get_last_finalized() == 100


class TestFinalityConsensusIntegration:
    def test_reorg_blocked_past_finalized(self, gadget):
        """Reorgs past finalized height should be blocked."""
        gadget.register_validator("v1", 500.0, 10)
        gadget.submit_vote("v1", 50, "hash50")
        gadget.check_finality(50)

        # Reorg to height 40 (below finalized 50) should be blocked
        assert not gadget.is_reorg_allowed(40)

        # Reorg to height 60 (above finalized 50) is OK
        assert gadget.is_reorg_allowed(60)

    def test_no_finality_allows_all_reorgs(self, gadget):
        """Without finalized blocks, all reorgs are allowed."""
        assert gadget.is_reorg_allowed(0)
        assert gadget.is_reorg_allowed(1000)

    def test_chain_info_finalized_height(self, gadget):
        """Test finalized_height in chain info."""
        gadget.register_validator("v1", 500.0, 10)
        gadget.submit_vote("v1", 100, "hash100")
        gadget.check_finality(100)

        assert gadget.get_last_finalized() == 100

    def test_process_block_prunes_old_votes(self, gadget):
        """process_block should prune expired votes."""
        gadget.register_validator("v1", 500.0, 10)
        gadget.submit_vote("v1", 10, "hash10")

        # After processing block 2000, vote at 10 should be pruned
        gadget.process_block(2000)
        status = gadget.get_finality_status(10)
        assert status.voter_count == 0

    def test_auto_vote_flow(self, gadget):
        """Test auto-voting after block acceptance."""
        gadget.register_validator("my_node", 500.0, 10)
        assert gadget.auto_vote_if_validator(100, "hash100", "my_node")
        assert gadget.check_finality(100)

    def test_multi_block_finalization(self, gadget):
        """Test finalization across multiple blocks."""
        gadget.register_validator("v1", 200.0, 1)
        gadget.register_validator("v2", 200.0, 1)
        gadget.register_validator("v3", 200.0, 1)

        # Finalize blocks 10, 20, 30
        for height in [10, 20, 30]:
            gadget.submit_vote("v1", height, f"hash{height}")
            gadget.submit_vote("v2", height, f"hash{height}")
            gadget.submit_vote("v3", height, f"hash{height}")
            assert gadget.check_finality(height)

        assert gadget.get_last_finalized() == 30
        assert not gadget.is_reorg_allowed(25)
        assert gadget.is_reorg_allowed(35)

    def test_validator_unregistration_affects_finality(self, gadget):
        """Unregistered validator's votes should not count."""
        gadget.register_validator("v1", 100.0, 1)
        gadget.register_validator("v2", 100.0, 1)
        gadget.register_validator("v3", 100.0, 1)

        # v1 votes
        gadget.submit_vote("v1", 50, "hash50")
        assert not gadget.check_finality(50)

        # Unregister v2 and v3 — now v1 is 100% of remaining stake
        gadget.unregister_validator("v2")
        gadget.unregister_validator("v3")
        assert gadget.check_finality(50)  # v1 is 100% now
