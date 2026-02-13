"""Unit tests for Aether Tree safety & alignment systems."""
import pytest


class TestThreatLevel:
    """Test ThreatLevel enum."""

    def test_values(self):
        from qubitcoin.aether.safety import ThreatLevel
        assert ThreatLevel.NONE == "none"
        assert ThreatLevel.LOW == "low"
        assert ThreatLevel.MEDIUM == "medium"
        assert ThreatLevel.HIGH == "high"
        assert ThreatLevel.CRITICAL == "critical"

    def test_all_levels(self):
        from qubitcoin.aether.safety import ThreatLevel
        assert len(ThreatLevel) == 5


class TestVetoReason:
    """Test VetoReason enum."""

    def test_values(self):
        from qubitcoin.aether.safety import VetoReason
        assert VetoReason.SAFETY_VIOLATION == "safety_violation"
        assert VetoReason.SUSY_IMBALANCE == "susy_imbalance"
        assert VetoReason.CONSTITUTIONAL_BREACH == "constitutional_breach"

    def test_all_reasons(self):
        from qubitcoin.aether.safety import VetoReason
        assert len(VetoReason) == 8


class TestSafetyPrinciple:
    """Test SafetyPrinciple dataclass."""

    def test_creation(self):
        from qubitcoin.aether.safety import SafetyPrinciple
        p = SafetyPrinciple(
            principle_id="test",
            description="harm damage attack",
            severity=8,
        )
        assert p.principle_id == "test"
        assert p.severity == 8
        assert p.active is True

    def test_matches_keyword(self):
        from qubitcoin.aether.safety import SafetyPrinciple
        p = SafetyPrinciple(
            principle_id="test",
            description="harm damage attack exploit",
        )
        assert p.matches("attempt to attack the system")
        assert p.matches("cause damage to validators")
        assert not p.matches("normal transaction processing")

    def test_matches_ignores_short_words(self):
        from qubitcoin.aether.safety import SafetyPrinciple
        p = SafetyPrinciple(principle_id="test", description="do bad")
        # "do" and "bad" are 2-3 chars, below the len(kw) > 3 filter
        assert not p.matches("do bad things")


class TestVetoRecord:
    """Test VetoRecord dataclass."""

    def test_auto_id_generation(self):
        from qubitcoin.aether.safety import VetoRecord
        record = VetoRecord(action_description="test action")
        assert len(record.veto_id) == 16

    def test_auto_timestamp(self):
        from qubitcoin.aether.safety import VetoRecord
        record = VetoRecord(action_description="test")
        assert record.timestamp > 0


class TestGevurahVeto:
    """Test Gevurah veto system."""

    def test_init_has_principles(self):
        from qubitcoin.aether.safety import GevurahVeto
        gv = GevurahVeto()
        assert len(gv.principles) >= 6

    def test_evaluate_safe_action(self):
        from qubitcoin.aether.safety import GevurahVeto, ThreatLevel
        gv = GevurahVeto()
        threat, violated = gv.evaluate_action("process normal block")
        assert threat == ThreatLevel.NONE
        assert violated == []

    def test_evaluate_harmful_action(self):
        from qubitcoin.aether.safety import GevurahVeto, ThreatLevel
        gv = GevurahVeto()
        threat, violated = gv.evaluate_action("destroy all validator funds")
        assert threat in (ThreatLevel.HIGH, ThreatLevel.CRITICAL)
        assert len(violated) > 0

    def test_evaluate_fund_drain(self):
        from qubitcoin.aether.safety import GevurahVeto, ThreatLevel
        gv = GevurahVeto()
        threat, violated = gv.evaluate_action("drain all staked QBC")
        assert threat in (ThreatLevel.HIGH, ThreatLevel.CRITICAL)
        assert "protect_funds" in violated

    def test_veto_records(self):
        from qubitcoin.aether.safety import GevurahVeto, VetoReason
        gv = GevurahVeto()
        record = gv.veto(
            action_description="steal validator keys",
            reason=VetoReason.SAFETY_VIOLATION,
            block_height=100,
        )
        assert record.veto_id
        assert gv.veto_count == 1

    def test_check_and_veto_blocks_harmful(self):
        from qubitcoin.aether.safety import GevurahVeto
        gv = GevurahVeto()
        result = gv.check_and_veto("exploit consensus bypass authority")
        assert result is not None
        assert result.veto_id

    def test_check_and_veto_allows_safe(self):
        from qubitcoin.aether.safety import GevurahVeto
        gv = GevurahVeto()
        result = gv.check_and_veto("validate block transactions")
        assert result is None

    def test_get_recent_vetoes(self):
        from qubitcoin.aether.safety import GevurahVeto
        gv = GevurahVeto()
        gv.veto("attack 1", block_height=1)
        gv.veto("attack 2", block_height=2)
        gv.veto("attack 3", block_height=3)
        recent = gv.get_recent_vetoes(2)
        assert len(recent) == 2
        # Most recent first
        assert recent[0].block_height == 3


class TestMultiNodeConsensus:
    """Test BFT consensus system."""

    def test_register_validators(self):
        from qubitcoin.aether.safety import MultiNodeConsensus
        mc = MultiNodeConsensus()
        mc.register_validator("addr_a", stake=100.0)
        mc.register_validator("addr_b", stake=200.0)
        assert mc.validator_count == 2
        assert mc.total_stake == 300.0

    def test_remove_validator(self):
        from qubitcoin.aether.safety import MultiNodeConsensus
        mc = MultiNodeConsensus()
        mc.register_validator("addr_a", stake=100.0)
        assert mc.remove_validator("addr_a") is True
        assert mc.validator_count == 0
        assert mc.remove_validator("nonexistent") is False

    def test_submit_vote(self):
        from qubitcoin.aether.safety import MultiNodeConsensus
        mc = MultiNodeConsensus()
        mc.register_validator("v1", 100.0)
        mc.submit_vote("action_hash_1", "v1", approve=True)
        reached, ratio = mc.check_consensus("action_hash_1")
        assert reached is True  # 100% approval > 67%
        assert ratio == 1.0

    def test_consensus_not_reached(self):
        from qubitcoin.aether.safety import MultiNodeConsensus
        mc = MultiNodeConsensus()
        mc.register_validator("v1", 100.0)
        mc.register_validator("v2", 100.0)
        mc.register_validator("v3", 100.0)
        mc.submit_vote("action_1", "v1", approve=True)
        # Only 33% approval, need 67%
        reached, ratio = mc.check_consensus("action_1")
        assert reached is False

    def test_consensus_reached_with_stake_weight(self):
        from qubitcoin.aether.safety import MultiNodeConsensus
        mc = MultiNodeConsensus()
        mc.register_validator("v1", 100.0)
        mc.register_validator("v2", 100.0)
        mc.register_validator("v3", 100.0)
        mc.submit_vote("action_1", "v1", approve=True)
        mc.submit_vote("action_1", "v2", approve=True)
        # 200/300 = 66.7% — just barely under 67%
        reached, ratio = mc.check_consensus("action_1")
        assert reached is False

        mc.submit_vote("action_1", "v3", approve=True)
        # 300/300 = 100%
        reached, ratio = mc.check_consensus("action_1")
        assert reached is True
        assert ratio == 1.0

    def test_no_double_voting(self):
        from qubitcoin.aether.safety import MultiNodeConsensus
        mc = MultiNodeConsensus()
        mc.register_validator("v1", 100.0)
        mc.submit_vote("action_1", "v1", approve=True)
        mc.submit_vote("action_1", "v1", approve=False)  # Double vote ignored
        reached, ratio = mc.check_consensus("action_1")
        assert ratio == 1.0  # First vote stands

    def test_non_validator_vote_ignored(self):
        from qubitcoin.aether.safety import MultiNodeConsensus
        mc = MultiNodeConsensus()
        mc.register_validator("v1", 100.0)
        mc.submit_vote("action_1", "imposter", approve=True)
        reached, ratio = mc.check_consensus("action_1")
        assert ratio == 0.0

    def test_finalize(self):
        from qubitcoin.aether.safety import MultiNodeConsensus
        mc = MultiNodeConsensus()
        mc.register_validator("v1", 100.0)
        mc.submit_vote("action_1", "v1", approve=True)
        decision = mc.finalize("action_1")
        assert decision is not None
        assert decision["approved"] is True
        assert decision["approval_ratio"] == 1.0

    def test_get_stats(self):
        from qubitcoin.aether.safety import MultiNodeConsensus
        mc = MultiNodeConsensus()
        mc.register_validator("v1", 50.0)
        stats = mc.get_stats()
        assert stats["validators"] == 1
        assert stats["total_stake"] == 50.0
        assert stats["threshold"] == 0.67


class TestSafetyManager:
    """Test top-level safety manager."""

    def test_init(self):
        from qubitcoin.aether.safety import SafetyManager
        sm = SafetyManager()
        assert sm.is_shutdown is False
        assert sm.gevurah is not None
        assert sm.consensus is not None

    def test_evaluate_safe_action(self):
        from qubitcoin.aether.safety import SafetyManager
        sm = SafetyManager()
        allowed, veto = sm.evaluate_and_decide("mine new block", block_height=1)
        assert allowed is True
        assert veto is None

    def test_evaluate_harmful_action(self):
        from qubitcoin.aether.safety import SafetyManager
        sm = SafetyManager()
        allowed, veto = sm.evaluate_and_decide(
            "destroy consensus bypass all authority", block_height=1
        )
        assert allowed is False
        assert veto is not None

    def test_emergency_shutdown(self):
        from qubitcoin.aether.safety import SafetyManager
        sm = SafetyManager()
        sm.emergency_shutdown("critical vulnerability detected", block_height=100)
        assert sm.is_shutdown is True
        # All actions blocked during shutdown
        allowed, veto = sm.evaluate_and_decide("normal operation", block_height=101)
        assert allowed is False

    def test_resume_from_shutdown(self):
        from qubitcoin.aether.safety import SafetyManager
        sm = SafetyManager()
        sm.emergency_shutdown("test", block_height=100)
        assert sm.is_shutdown is True
        assert sm.resume(block_height=110) is True
        assert sm.is_shutdown is False

    def test_resume_when_not_shutdown(self):
        from qubitcoin.aether.safety import SafetyManager
        sm = SafetyManager()
        assert sm.resume(block_height=1) is False

    def test_get_stats(self):
        from qubitcoin.aether.safety import SafetyManager
        sm = SafetyManager()
        sm.gevurah.veto("test attack", block_height=1)
        stats = sm.get_stats()
        assert stats["shutdown"] is False
        assert stats["gevurah"]["veto_count"] == 1
        assert stats["gevurah"]["principles"] >= 6
        assert "consensus" in stats
