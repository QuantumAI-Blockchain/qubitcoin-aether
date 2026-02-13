"""Unit tests for Aether Tree memory systems."""
import pytest


class TestMemoryItem:
    """Test MemoryItem dataclass."""

    def test_auto_id_generation(self):
        from qubitcoin.aether.memory import MemoryItem
        item = MemoryItem(content="test")
        assert len(item.memory_id) == 16

    def test_auto_timestamp(self):
        from qubitcoin.aether.memory import MemoryItem
        item = MemoryItem(content="test")
        assert item.timestamp > 0

    def test_access_increments_count(self):
        from qubitcoin.aether.memory import MemoryItem
        item = MemoryItem(content="test")
        assert item.access_count == 0
        item.access()
        assert item.access_count == 1
        item.access()
        assert item.access_count == 2

    def test_decay_confidence(self):
        from qubitcoin.aether.memory import MemoryItem
        item = MemoryItem(content="test", confidence=1.0)
        item.decay_confidence(factor=0.5)
        assert item.confidence == 0.5
        item.decay_confidence(factor=0.5)
        assert item.confidence == 0.25

    def test_decay_confidence_floor(self):
        from qubitcoin.aether.memory import MemoryItem
        item = MemoryItem(content="test", confidence=0.01)
        item.decay_confidence(factor=0.001)
        assert item.confidence == 0.01  # Floor


class TestEpisodicMemory:
    """Test event-based episodic memory."""

    def test_store_and_recall(self):
        from qubitcoin.aether.memory import EpisodicMemory
        mem = EpisodicMemory()
        item = mem.store("block mined", block_height=100)
        recalled = mem.recall(item.memory_id)
        assert recalled is not None
        assert recalled.content == "block mined"
        assert recalled.access_count == 1

    def test_recall_nonexistent(self):
        from qubitcoin.aether.memory import EpisodicMemory
        mem = EpisodicMemory()
        assert mem.recall("nonexistent") is None

    def test_recall_by_block_range(self):
        from qubitcoin.aether.memory import EpisodicMemory
        mem = EpisodicMemory()
        mem.store("event1", block_height=10)
        mem.store("event2", block_height=20)
        mem.store("event3", block_height=30)
        results = mem.recall_by_block_range(15, 25)
        assert len(results) == 1
        assert results[0].content == "event2"

    def test_search(self):
        from qubitcoin.aether.memory import EpisodicMemory
        mem = EpisodicMemory()
        mem.store("quantum computing breakthrough", block_height=1)
        mem.store("new peer connected", block_height=2)
        mem.store("quantum state collapsed", block_height=3)
        results = mem.search("quantum")
        assert len(results) == 2

    def test_count(self):
        from qubitcoin.aether.memory import EpisodicMemory
        mem = EpisodicMemory()
        assert mem.count == 0
        mem.store("test", block_height=1)
        assert mem.count == 1


class TestSemanticMemory:
    """Test concept network semantic memory."""

    def test_store_and_recall(self):
        from qubitcoin.aether.memory import SemanticMemory
        mem = SemanticMemory()
        item = mem.store("blockchain", block_height=1)
        recalled = mem.recall(item.memory_id)
        assert recalled is not None
        assert recalled.content == "blockchain"

    def test_associations(self):
        from qubitcoin.aether.memory import SemanticMemory
        mem = SemanticMemory()
        a = mem.store("quantum", block_height=1)
        b = mem.store("computing", block_height=2, associations=[a.memory_id])
        assocs = mem.get_associated(b.memory_id)
        assert len(assocs) == 1
        assert assocs[0][0] == a.memory_id

    def test_strengthen_association(self):
        from qubitcoin.aether.memory import SemanticMemory
        mem = SemanticMemory()
        a = mem.store("phi", block_height=1)
        b = mem.store("consciousness", block_height=2, associations=[a.memory_id])
        weight = mem.strengthen_association(a.memory_id, b.memory_id, delta=0.5)
        assert weight == 1.5  # 1.0 initial + 0.5

    def test_search(self):
        from qubitcoin.aether.memory import SemanticMemory
        mem = SemanticMemory()
        mem.store("golden ratio phi", block_height=1)
        mem.store("susy symmetry", block_height=2)
        results = mem.search("golden")
        assert len(results) == 1

    def test_association_count(self):
        from qubitcoin.aether.memory import SemanticMemory
        mem = SemanticMemory()
        a = mem.store("A", block_height=1)
        b = mem.store("B", block_height=2, associations=[a.memory_id])
        assert mem.association_count == 1  # Bidirectional counted once


class TestProceduralMemory:
    """Test skill/procedure memory."""

    def test_store_procedure(self):
        from qubitcoin.aether.memory import ProceduralMemory
        mem = ProceduralMemory()
        item = mem.store("validate_block", ["check_hash", "verify_sig", "check_utxo"], block_height=1)
        assert item.metadata["steps"] == ["check_hash", "verify_sig", "check_utxo"]
        assert item.metadata["proficiency"] == 0.0

    def test_practice_increases_proficiency(self):
        from qubitcoin.aether.memory import ProceduralMemory
        mem = ProceduralMemory()
        item = mem.store("mine_block", ["gen_hamiltonian", "run_vqe"], block_height=1)
        p1 = mem.practice(item.memory_id)
        assert p1 > 0.0
        p2 = mem.practice(item.memory_id)
        assert p2 > p1  # Proficiency increases with practice

    def test_practice_nonexistent(self):
        from qubitcoin.aether.memory import ProceduralMemory
        mem = ProceduralMemory()
        assert mem.practice("nonexistent") is None

    def test_get_skills(self):
        from qubitcoin.aether.memory import ProceduralMemory
        mem = ProceduralMemory()
        mem.store("skill_a", ["step1"], block_height=1)
        mem.store("skill_b", ["step1", "step2"], block_height=2)
        skills = mem.get_skills()
        assert len(skills) == 2
        assert "name" in skills[0]
        assert "proficiency" in skills[0]


class TestWorkingMemory:
    """Test limited-capacity working memory."""

    def test_push_and_get_active(self):
        from qubitcoin.aether.memory import WorkingMemory
        wm = WorkingMemory(capacity=3)
        wm.push("item1", block_height=1, attention=1.0)
        wm.push("item2", block_height=2, attention=2.0)
        active = wm.get_active()
        assert len(active) == 2
        assert active[0].content == "item2"  # Higher attention first

    def test_capacity_limit(self):
        from qubitcoin.aether.memory import WorkingMemory
        wm = WorkingMemory(capacity=3)
        wm.push("a", block_height=1, attention=1.0)
        wm.push("b", block_height=2, attention=2.0)
        wm.push("c", block_height=3, attention=3.0)
        wm.push("d", block_height=4, attention=4.0)
        assert wm.count == 3  # One evicted
        active = wm.get_active()
        # Lowest attention ("a") should be evicted
        contents = [m.content for m in active]
        assert "a" not in contents

    def test_refresh(self):
        from qubitcoin.aether.memory import WorkingMemory
        wm = WorkingMemory()
        item = wm.push("important", block_height=1, attention=1.0)
        assert wm.refresh(item.memory_id, attention_boost=0.5)
        active = wm.get_active()
        assert active[0].confidence == 1.5

    def test_decay_all(self):
        from qubitcoin.aether.memory import WorkingMemory
        wm = WorkingMemory()
        wm.push("item1", block_height=1, attention=0.5)
        wm.push("item2", block_height=2, attention=0.05)
        evicted = wm.decay_all(rate=0.5)
        assert evicted >= 1  # item2 decays below 0.1

    def test_utilization(self):
        from qubitcoin.aether.memory import WorkingMemory
        wm = WorkingMemory(capacity=4)
        assert wm.utilization == 0.0
        wm.push("a", block_height=1)
        wm.push("b", block_height=2)
        assert wm.utilization == 0.5

    def test_clear(self):
        from qubitcoin.aether.memory import WorkingMemory
        wm = WorkingMemory()
        wm.push("a", block_height=1)
        wm.push("b", block_height=2)
        cleared = wm.clear()
        assert cleared == 2
        assert wm.count == 0


class TestMemoryManager:
    """Test orchestrated memory system."""

    def test_init(self):
        from qubitcoin.aether.memory import MemoryManager
        mm = MemoryManager()
        assert mm.episodic.count == 0
        assert mm.semantic.count == 0
        assert mm.procedural.count == 0
        assert mm.working.count == 0

    def test_consolidate_to_semantic(self):
        from qubitcoin.aether.memory import MemoryManager
        mm = MemoryManager()
        mm.working.push("knowledge item", block_height=1, attention=1.0)
        consolidated = mm.consolidate(block_height=10)
        assert consolidated == 1
        assert mm.semantic.count == 1

    def test_consolidate_to_episodic(self):
        from qubitcoin.aether.memory import MemoryManager
        mm = MemoryManager()
        item = mm.working.push("temporal event", block_height=1, attention=1.0)
        item.metadata["temporal"] = True
        consolidated = mm.consolidate(block_height=10)
        assert consolidated == 1
        assert mm.episodic.count == 1

    def test_consolidate_skips_low_attention(self):
        from qubitcoin.aether.memory import MemoryManager
        mm = MemoryManager()
        mm.working.push("weak item", block_height=1, attention=0.1)
        consolidated = mm.consolidate(block_height=10)
        assert consolidated == 0

    def test_search_all(self):
        from qubitcoin.aether.memory import MemoryManager
        mm = MemoryManager()
        mm.episodic.store("quantum mining started", block_height=1)
        mm.semantic.store("quantum physics concept", block_height=2)
        results = mm.search_all("quantum")
        assert len(results) == 2

    def test_get_stats(self):
        from qubitcoin.aether.memory import MemoryManager
        mm = MemoryManager()
        mm.episodic.store("event", block_height=1)
        mm.semantic.store("concept", block_height=2)
        mm.procedural.store("skill", ["step"], block_height=3)
        mm.working.push("active", block_height=4)
        stats = mm.get_stats()
        assert stats["episodic_count"] == 1
        assert stats["semantic_count"] == 1
        assert stats["procedural_count"] == 1
        assert stats["working_count"] == 1
        assert stats["working_capacity"] == 7
