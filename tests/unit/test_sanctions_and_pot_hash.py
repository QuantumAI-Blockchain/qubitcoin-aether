"""Tests for Sanctions Screening + Proof-of-Thought hash in block headers (Batch 20)."""
import pytest

from qubitcoin.qvm.compliance import (
    ComplianceEngine,
    SanctionsEntry,
    SanctionsList,
    SanctionsSource,
    AMLStatus,
    KYCLevel,
)
from qubitcoin.database.models import Block, Transaction


# ===========================================================================
# Batch 20.1 — Sanctions Screening
# ===========================================================================


class TestSanctionsList:
    def test_add_address(self):
        sl = SanctionsList()
        entry = sl.add_address("0xBad", SanctionsSource.OFAC, "SDN listed")
        assert entry.source == SanctionsSource.OFAC
        assert entry.address == "0xbad"  # normalised to lower

    def test_is_sanctioned(self):
        sl = SanctionsList()
        sl.add_address("0xBad", SanctionsSource.OFAC)
        assert sl.is_sanctioned("0xbad") is True
        assert sl.is_sanctioned("0xBad") is True  # case-insensitive
        assert sl.is_sanctioned("0xGood") is False

    def test_remove_address(self):
        sl = SanctionsList()
        sl.add_address("0xBad", SanctionsSource.UN)
        assert sl.remove_address("0xbad") is True
        assert sl.is_sanctioned("0xbad") is False

    def test_remove_nonexistent(self):
        sl = SanctionsList()
        assert sl.remove_address("0xNope") is False

    def test_screen_address_clean(self):
        sl = SanctionsList()
        result = sl.screen_address("0xClean")
        assert result["sanctioned"] is False
        assert result["sources"] == []

    def test_screen_address_hit(self):
        sl = SanctionsList()
        sl.add_address("0xBad", SanctionsSource.OFAC, "Terror financing")
        result = sl.screen_address("0xBad")
        assert result["sanctioned"] is True
        assert "ofac" in result["sources"]
        assert result["reason"] == "Terror financing"

    def test_list_by_source(self):
        sl = SanctionsList()
        sl.add_address("0xA", SanctionsSource.OFAC)
        sl.add_address("0xB", SanctionsSource.OFAC)
        sl.add_address("0xC", SanctionsSource.EU)
        assert len(sl.list_by_source(SanctionsSource.OFAC)) == 2
        assert len(sl.list_by_source(SanctionsSource.EU)) == 1
        assert len(sl.list_by_source(SanctionsSource.UN)) == 0

    def test_bulk_add(self):
        sl = SanctionsList()
        count = sl.bulk_add(
            ["0xA", "0xB", "0xC"],
            SanctionsSource.UN,
            "Batch import",
        )
        assert count == 3
        assert sl.is_sanctioned("0xa") is True

    def test_get_entry(self):
        sl = SanctionsList()
        sl.add_address("0xBad", SanctionsSource.EU, "Arms embargo")
        entry = sl.get_entry("0xBad")
        assert entry is not None
        assert entry.reason == "Arms embargo"

    def test_get_entry_missing(self):
        sl = SanctionsList()
        assert sl.get_entry("0xNone") is None

    def test_stats(self):
        sl = SanctionsList()
        sl.add_address("0xA", SanctionsSource.OFAC)
        sl.add_address("0xB", SanctionsSource.EU)
        stats = sl.get_stats()
        assert stats["total_entries"] == 2
        assert stats["by_source"]["ofac"] == 1
        assert stats["by_source"]["eu"] == 1

    def test_entry_to_dict(self):
        entry = SanctionsEntry(
            address="0xbad",
            source=SanctionsSource.OFAC,
            reason="SDN",
        )
        d = entry.to_dict()
        assert d["source"] == "ofac"
        assert d["address"] == "0xbad"


class TestComplianceEngineSanctions:
    """Integration: sanctions list wired into ComplianceEngine."""

    def test_sanctioned_address_blocked(self):
        engine = ComplianceEngine()
        engine.sanctions.add_address("0xEvil", SanctionsSource.OFAC)
        assert engine.is_address_blocked("0xEvil") is True

    def test_clean_address_not_blocked(self):
        engine = ComplianceEngine()
        assert engine.is_address_blocked("0xGood") is False

    def test_sanctions_override_policy(self):
        """Sanctions block even if policy says not blocked."""
        engine = ComplianceEngine()
        engine.create_policy("0xevil", is_blocked=False)
        engine.sanctions.add_address("0xEvil", SanctionsSource.UN)
        assert engine.is_address_blocked("0xEvil") is True

    def test_screen_sanctions_via_engine(self):
        engine = ComplianceEngine()
        engine.sanctions.add_address("0xBad", SanctionsSource.EU, "Listed")
        result = engine.screen_sanctions("0xBad")
        assert result["sanctioned"] is True

    def test_aml_blocked_still_works(self):
        """AML BLOCKED status still blocks even without sanctions."""
        engine = ComplianceEngine()
        engine.create_policy("0xSus", aml_status=AMLStatus.BLOCKED)
        assert engine.is_address_blocked("0xSus") is True


# ===========================================================================
# Batch 20.2 — Proof-of-Thought hash in block headers
# ===========================================================================


def _make_block(thought_proof: dict = None, **kwargs) -> Block:
    """Helper to create a minimal block for testing."""
    defaults = {
        "height": 1,
        "prev_hash": "0" * 64,
        "proof_data": {"energy": 0.5},
        "transactions": [],
        "timestamp": 1700000000.0,
        "difficulty": 1.0,
    }
    defaults.update(kwargs)
    return Block(thought_proof=thought_proof, **defaults)


class TestProofOfThoughtHash:
    def test_hash_empty_without_pot(self):
        block = _make_block()
        assert block.proof_of_thought_hash == ''
        block.calculate_hash()
        assert block.proof_of_thought_hash == ''

    def test_hash_populated_with_pot(self):
        pot = {
            "thought_hash": "abc123",
            "reasoning_steps": 5,
            "phi_value": 2.5,
            "knowledge_root": "def456",
        }
        block = _make_block(thought_proof=pot)
        block.calculate_hash()
        assert block.proof_of_thought_hash != ''
        assert len(block.proof_of_thought_hash) == 64  # SHA-256 hex

    def test_hash_deterministic(self):
        pot = {"phi_value": 3.1, "steps": 10}
        b1 = _make_block(thought_proof=pot)
        b2 = _make_block(thought_proof=pot)
        b1.calculate_hash()
        b2.calculate_hash()
        assert b1.proof_of_thought_hash == b2.proof_of_thought_hash

    def test_different_pot_different_hash(self):
        b1 = _make_block(thought_proof={"phi": 1.0})
        b2 = _make_block(thought_proof={"phi": 2.0})
        b1.calculate_hash()
        b2.calculate_hash()
        assert b1.proof_of_thought_hash != b2.proof_of_thought_hash

    def test_pot_hash_in_to_dict(self):
        pot = {"thought_hash": "xyz"}
        block = _make_block(thought_proof=pot)
        d = block.to_dict()
        assert "proof_of_thought_hash" in d
        assert d["proof_of_thought_hash"] != ''

    def test_pot_hash_in_block_hash(self):
        """Changing PoT must change the block hash."""
        b1 = _make_block(thought_proof={"phi": 1.0})
        b2 = _make_block(thought_proof={"phi": 2.0})
        h1 = b1.calculate_hash()
        h2 = b2.calculate_hash()
        assert h1 != h2

    def test_from_dict_preserves_pot_hash(self):
        pot = {"thought_hash": "test"}
        block = _make_block(thought_proof=pot)
        block.calculate_hash()
        d = block.to_dict()
        restored = Block.from_dict(d)
        assert restored.proof_of_thought_hash == block.proof_of_thought_hash

    def test_from_dict_without_pot_hash(self):
        """Older blocks without the field should still deserialise."""
        d = {
            "height": 1,
            "prev_hash": "0" * 64,
            "proof_data": {},
            "transactions": [],
            "timestamp": 1700000000.0,
            "difficulty": 1.0,
        }
        block = Block.from_dict(d)
        assert block.proof_of_thought_hash == ''

    def test_compute_thought_proof_hash_helper(self):
        block = _make_block(thought_proof={"data": "value"})
        h = block._compute_thought_proof_hash()
        assert len(h) == 64
        # Same input → same hash
        assert h == block._compute_thought_proof_hash()

    def test_no_thought_proof_gives_empty_hash(self):
        block = _make_block()
        assert block._compute_thought_proof_hash() == ''
