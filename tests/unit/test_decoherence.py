"""Tests for quantum state decoherence prevention model (Batch 16.4)."""
import pytest

from qubitcoin.qvm.decoherence import (
    DecoherenceManager, CoherenceRecord,
    DEFAULT_COHERENCE_BUDGET, SHIELD_MULTIPLIER,
)


class TestRegister:
    def test_register_creates_record(self):
        mgr = DecoherenceManager()
        rec = mgr.register(1, block_height=10)
        assert rec.state_id == 1
        assert rec.remaining_budget == DEFAULT_COHERENCE_BUDGET

    def test_register_custom_budget(self):
        mgr = DecoherenceManager()
        rec = mgr.register(2, block_height=0, budget=50)
        assert rec.initial_budget == 50
        assert rec.remaining_budget == 50

    def test_get_record(self):
        mgr = DecoherenceManager()
        mgr.register(3, block_height=0)
        assert mgr.get(3) is not None

    def test_get_missing(self):
        mgr = DecoherenceManager()
        assert mgr.get(999) is None


class TestTick:
    def test_budget_decreases(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0, budget=10)
        mgr.tick(1)
        assert mgr.get(1).remaining_budget == 9

    def test_decoheres_at_zero(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0, budget=3)
        mgr.tick(1)  # 2
        mgr.tick(2)  # 1
        decohered = mgr.tick(3)  # 0 → decohered
        assert 1 in decohered
        assert mgr.get(1).is_decohered is True

    def test_already_decohered_not_ticked(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0, budget=1)
        mgr.tick(1)  # decohered
        assert mgr.get(1).remaining_budget == 0
        mgr.tick(2)  # should not go negative
        assert mgr.get(1).remaining_budget == 0

    def test_frozen_not_ticked(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0, budget=10)
        mgr.freeze(1)
        mgr.tick(1)
        assert mgr.get(1).remaining_budget == 10  # unchanged


class TestRefresh:
    def test_refresh_resets_budget(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0, budget=10)
        mgr.tick(1)  # 9
        mgr.tick(2)  # 8
        mgr.refresh(1)
        assert mgr.get(1).remaining_budget == 10

    def test_refresh_custom_budget(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0, budget=10)
        mgr.refresh(1, budget=50)
        assert mgr.get(1).remaining_budget == 50

    def test_refresh_revives_decohered(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0, budget=1)
        mgr.tick(1)  # decohered
        assert mgr.get(1).is_decohered is True
        mgr.refresh(1)
        assert mgr.get(1).is_decohered is False

    def test_refresh_missing_returns_false(self):
        mgr = DecoherenceManager()
        assert mgr.refresh(999) is False


class TestShield:
    def test_shield_doubles_budget(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0, budget=10)
        mgr.shield(1)
        assert mgr.get(1).remaining_budget == 20

    def test_shield_increments_level(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0)
        mgr.shield(1)
        mgr.shield(1)
        assert mgr.get(1).shield_level == 2

    def test_shield_decohered_fails(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0, budget=1)
        mgr.tick(1)
        assert mgr.shield(1) is False

    def test_shield_missing_fails(self):
        mgr = DecoherenceManager()
        assert mgr.shield(999) is False


class TestFreeze:
    def test_freeze(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0)
        assert mgr.freeze(1) is True
        assert mgr.get(1).is_frozen is True

    def test_unfreeze(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0)
        mgr.freeze(1)
        mgr.unfreeze(1)
        assert mgr.get(1).is_frozen is False

    def test_freeze_decohered_fails(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0, budget=1)
        mgr.tick(1)
        assert mgr.freeze(1) is False

    def test_freeze_missing_fails(self):
        mgr = DecoherenceManager()
        assert mgr.freeze(999) is False


class TestIsCoherent:
    def test_coherent(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0)
        assert mgr.is_coherent(1) is True

    def test_not_coherent(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0, budget=1)
        mgr.tick(1)
        assert mgr.is_coherent(1) is False

    def test_missing_not_coherent(self):
        mgr = DecoherenceManager()
        assert mgr.is_coherent(999) is False


class TestListing:
    def test_list_active(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0, budget=100)
        mgr.register(2, block_height=0, budget=1)
        mgr.tick(1)  # 2 decoheres
        assert len(mgr.list_active()) == 1
        assert mgr.list_active()[0].state_id == 1

    def test_list_decohered(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0, budget=1)
        mgr.tick(1)
        assert len(mgr.list_decohered()) == 1

    def test_remove(self):
        mgr = DecoherenceManager()
        mgr.register(1, block_height=0)
        assert mgr.remove(1) is True
        assert mgr.get(1) is None

    def test_remove_missing(self):
        mgr = DecoherenceManager()
        assert mgr.remove(999) is False


class TestSerialization:
    def test_record_to_dict(self):
        rec = CoherenceRecord(state_id=42, initial_budget=100, remaining_budget=75)
        d = rec.to_dict()
        assert d['state_id'] == 42
        assert d['remaining_budget'] == 75
        assert d['is_decohered'] is False
