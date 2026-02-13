"""
Aether Tree Memory Systems — Biologically-Inspired Memory Hierarchy

Four memory types modeled after human cognition:
  - Episodic: Event-based memories (hippocampal), stored on IPFS
  - Semantic: Concept networks, linked knowledge (cortical)
  - Procedural: Learned skills and procedures (basal ganglia)
  - Working: Active processing buffer, limited capacity (prefrontal)

Memory consolidation happens during Sleep/Deep Sleep circadian phases.
"""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from collections import OrderedDict

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MemoryType(str, Enum):
    """Types of memory in the Aether cognitive architecture."""
    EPISODIC = "episodic"       # Event-based (hippocampal)
    SEMANTIC = "semantic"       # Concept networks (cortical)
    PROCEDURAL = "procedural"   # Learned skills (basal ganglia)
    WORKING = "working"         # Active buffer (prefrontal)


@dataclass
class MemoryItem:
    """A single memory entry in the Aether memory system."""
    memory_id: str = ""
    memory_type: MemoryType = MemoryType.SEMANTIC
    content: str = ""
    source_block: int = 0
    timestamp: float = 0.0
    confidence: float = 1.0
    access_count: int = 0
    last_accessed: float = 0.0
    associations: List[str] = field(default_factory=list)  # IDs of related memories
    metadata: dict = field(default_factory=dict)
    ipfs_hash: str = ""  # For episodic memories stored on IPFS
    consolidated: bool = False  # Has been consolidated from working → long-term

    def __post_init__(self) -> None:
        if not self.memory_id:
            data = f"{self.memory_type.value}:{self.content}:{time.time()}"
            self.memory_id = hashlib.sha256(data.encode()).hexdigest()[:16]
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.last_accessed:
            self.last_accessed = self.timestamp

    @property
    def age_blocks(self) -> int:
        """Blocks since creation (relative to current)."""
        return 0  # Updated by the memory manager

    def access(self) -> None:
        """Record an access to this memory."""
        self.access_count += 1
        self.last_accessed = time.time()

    def decay_confidence(self, factor: float = 0.995) -> None:
        """Apply confidence decay (forgetting curve)."""
        self.confidence = max(0.01, self.confidence * factor)


# Working memory capacity — Miller's magic number 7 ± 2
WORKING_MEMORY_CAPACITY = 7


class EpisodicMemory:
    """
    Event-based memory (hippocampal analog).

    Stores discrete events with temporal context.
    Long-term storage on IPFS, indexed locally.
    """

    def __init__(self) -> None:
        self._memories: OrderedDict[str, MemoryItem] = OrderedDict()
        self._max_local = 10000  # Keep recent 10K locally

    def store(self, content: str, block_height: int,
              metadata: Optional[dict] = None) -> MemoryItem:
        """Store a new episodic memory."""
        item = MemoryItem(
            memory_type=MemoryType.EPISODIC,
            content=content,
            source_block=block_height,
            metadata=metadata or {},
        )
        self._memories[item.memory_id] = item

        # Evict oldest if over capacity
        while len(self._memories) > self._max_local:
            self._memories.popitem(last=False)

        logger.debug(f"Episodic memory stored: {item.memory_id} (block {block_height})")
        return item

    def recall(self, memory_id: str) -> Optional[MemoryItem]:
        """Recall a specific episodic memory."""
        item = self._memories.get(memory_id)
        if item:
            item.access()
        return item

    def recall_by_block_range(self, start: int, end: int) -> List[MemoryItem]:
        """Recall all episodic memories from a block range."""
        return [
            m for m in self._memories.values()
            if start <= m.source_block <= end
        ]

    def search(self, keyword: str, limit: int = 10) -> List[MemoryItem]:
        """Search episodic memories by content keyword."""
        results = [
            m for m in self._memories.values()
            if keyword.lower() in m.content.lower()
        ]
        return sorted(results, key=lambda m: -m.last_accessed)[:limit]

    @property
    def count(self) -> int:
        return len(self._memories)


class SemanticMemory:
    """
    Concept network memory (cortical analog).

    Stores knowledge as interconnected concepts with weighted associations.
    Integrates with the KnowledgeGraph (KeterNodes).
    """

    def __init__(self) -> None:
        self._concepts: Dict[str, MemoryItem] = {}
        self._associations: Dict[str, Dict[str, float]] = {}  # id -> {id: weight}

    def store(self, content: str, block_height: int,
              associations: Optional[List[str]] = None) -> MemoryItem:
        """Store a semantic concept."""
        item = MemoryItem(
            memory_type=MemoryType.SEMANTIC,
            content=content,
            source_block=block_height,
            associations=associations or [],
        )
        self._concepts[item.memory_id] = item

        # Create bidirectional associations
        for assoc_id in item.associations:
            self._add_association(item.memory_id, assoc_id, weight=1.0)

        return item

    def _add_association(self, id_a: str, id_b: str, weight: float) -> None:
        """Add weighted association between two concepts."""
        if id_a not in self._associations:
            self._associations[id_a] = {}
        if id_b not in self._associations:
            self._associations[id_b] = {}
        self._associations[id_a][id_b] = weight
        self._associations[id_b][id_a] = weight

    def strengthen_association(self, id_a: str, id_b: str,
                                delta: float = 0.1) -> float:
        """Strengthen association between two concepts (Hebbian learning)."""
        if id_a in self._associations and id_b in self._associations[id_a]:
            new_weight = min(10.0, self._associations[id_a][id_b] + delta)
            self._associations[id_a][id_b] = new_weight
            self._associations[id_b][id_a] = new_weight
            return new_weight
        return 0.0

    def get_associated(self, memory_id: str,
                       min_weight: float = 0.5) -> List[Tuple[str, float]]:
        """Get concepts associated with a given memory, sorted by weight."""
        assocs = self._associations.get(memory_id, {})
        filtered = [(k, v) for k, v in assocs.items() if v >= min_weight]
        return sorted(filtered, key=lambda x: -x[1])

    def recall(self, memory_id: str) -> Optional[MemoryItem]:
        item = self._concepts.get(memory_id)
        if item:
            item.access()
        return item

    def search(self, keyword: str, limit: int = 10) -> List[MemoryItem]:
        results = [
            m for m in self._concepts.values()
            if keyword.lower() in m.content.lower()
        ]
        return sorted(results, key=lambda m: -m.confidence)[:limit]

    @property
    def count(self) -> int:
        return len(self._concepts)

    @property
    def association_count(self) -> int:
        return sum(len(v) for v in self._associations.values()) // 2


class ProceduralMemory:
    """
    Learned skills and procedures (basal ganglia analog).

    Stores action sequences that can be recalled and executed.
    Skills improve with practice (access_count).
    """

    def __init__(self) -> None:
        self._procedures: Dict[str, MemoryItem] = {}

    def store(self, name: str, steps: List[str], block_height: int) -> MemoryItem:
        """Store a new procedure (skill)."""
        item = MemoryItem(
            memory_type=MemoryType.PROCEDURAL,
            content=name,
            source_block=block_height,
            metadata={"steps": steps, "proficiency": 0.0},
        )
        self._procedures[item.memory_id] = item
        return item

    def practice(self, memory_id: str) -> Optional[float]:
        """Practice a procedure, increasing proficiency."""
        item = self._procedures.get(memory_id)
        if not item:
            return None

        item.access()
        # Proficiency increases with logarithmic learning curve
        import math
        proficiency = min(1.0, math.log1p(item.access_count) / 10.0)
        item.metadata["proficiency"] = round(proficiency, 4)
        return proficiency

    def recall(self, memory_id: str) -> Optional[MemoryItem]:
        item = self._procedures.get(memory_id)
        if item:
            item.access()
        return item

    def get_skills(self) -> List[dict]:
        """Get all learned procedures with proficiency."""
        return [
            {
                "id": m.memory_id,
                "name": m.content,
                "proficiency": m.metadata.get("proficiency", 0.0),
                "practice_count": m.access_count,
                "steps": len(m.metadata.get("steps", [])),
            }
            for m in sorted(
                self._procedures.values(),
                key=lambda x: -x.metadata.get("proficiency", 0.0),
            )
        ]

    @property
    def count(self) -> int:
        return len(self._procedures)


class WorkingMemory:
    """
    Active processing buffer (prefrontal cortex analog).

    Limited capacity (Miller's 7 ± 2). Items compete by attention score.
    Items decay rapidly if not refreshed.
    """

    def __init__(self, capacity: int = WORKING_MEMORY_CAPACITY) -> None:
        self._buffer: OrderedDict[str, MemoryItem] = OrderedDict()
        self._capacity = capacity

    def push(self, content: str, block_height: int,
             attention: float = 1.0) -> MemoryItem:
        """Push an item into working memory."""
        item = MemoryItem(
            memory_type=MemoryType.WORKING,
            content=content,
            source_block=block_height,
            confidence=attention,  # Use confidence as attention score
        )
        self._buffer[item.memory_id] = item

        # Evict lowest-attention item if over capacity
        while len(self._buffer) > self._capacity:
            self._evict_lowest()

        return item

    def _evict_lowest(self) -> Optional[MemoryItem]:
        """Evict the item with lowest attention (confidence)."""
        if not self._buffer:
            return None
        lowest_id = min(self._buffer, key=lambda k: self._buffer[k].confidence)
        return self._buffer.pop(lowest_id)

    def refresh(self, memory_id: str, attention_boost: float = 0.5) -> bool:
        """Refresh an item in working memory (keep it active)."""
        item = self._buffer.get(memory_id)
        if not item:
            return False
        item.confidence = min(10.0, item.confidence + attention_boost)
        item.access()
        return True

    def decay_all(self, rate: float = 0.9) -> int:
        """Apply attention decay to all items. Returns number of items evicted."""
        evicted = 0
        to_remove = []
        for mid, item in self._buffer.items():
            item.confidence *= rate
            if item.confidence < 0.1:
                to_remove.append(mid)
        for mid in to_remove:
            del self._buffer[mid]
            evicted += 1
        return evicted

    def get_active(self) -> List[MemoryItem]:
        """Get all active working memory items, sorted by attention."""
        return sorted(self._buffer.values(), key=lambda m: -m.confidence)

    def clear(self) -> int:
        """Clear working memory. Returns number of items cleared."""
        count = len(self._buffer)
        self._buffer.clear()
        return count

    @property
    def count(self) -> int:
        return len(self._buffer)

    @property
    def utilization(self) -> float:
        """How full is working memory (0.0 to 1.0)."""
        return len(self._buffer) / self._capacity


class MemoryManager:
    """
    Orchestrates all four memory systems.

    Handles memory consolidation (working → long-term) during sleep phases.
    Provides unified search across all memory types.
    """

    def __init__(self) -> None:
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()
        self.working = WorkingMemory()
        self._consolidation_count = 0
        logger.info("Memory Manager initialized (4 memory systems)")

    def consolidate(self, block_height: int) -> int:
        """
        Consolidate working memory into long-term stores.

        Called during Sleep/Deep Sleep circadian phases.
        Items with high attention go to semantic memory.
        Items with temporal context go to episodic memory.

        Returns number of items consolidated.
        """
        consolidated = 0
        items = self.working.get_active()

        for item in items:
            if item.confidence < 0.3:
                continue  # Too weak to consolidate

            if item.metadata.get("temporal", False):
                # Temporal context → episodic
                new_item = self.episodic.store(
                    content=item.content,
                    block_height=item.source_block,
                    metadata=item.metadata,
                )
                new_item.consolidated = True
            else:
                # General knowledge → semantic
                new_item = self.semantic.store(
                    content=item.content,
                    block_height=item.source_block,
                    associations=item.associations,
                )
                new_item.consolidated = True

            consolidated += 1

        # Clear consolidated items from working memory
        if consolidated > 0:
            self.working.decay_all(rate=0.5)  # Aggressive decay post-consolidation
            self._consolidation_count += consolidated
            logger.info(
                f"Memory consolidation: {consolidated} items moved to long-term "
                f"(block {block_height})"
            )

        return consolidated

    def search_all(self, keyword: str, limit: int = 10) -> List[dict]:
        """Search across all memory systems."""
        results = []

        for item in self.episodic.search(keyword, limit):
            results.append({"type": "episodic", "item": item})
        for item in self.semantic.search(keyword, limit):
            results.append({"type": "semantic", "item": item})

        # Sort by confidence, take top N
        results.sort(key=lambda r: -r["item"].confidence)
        return results[:limit]

    def apply_decay(self, phase_rate: float = 1.0) -> None:
        """Apply forgetting curve to all long-term memories."""
        decay = 0.999 * phase_rate  # Slower decay during sleep
        for item in list(self.episodic._memories.values()):
            item.decay_confidence(decay)
        for item in list(self.semantic._concepts.values()):
            item.decay_confidence(decay)
        self.working.decay_all(rate=0.95)

    def get_stats(self) -> dict:
        """Get memory system statistics."""
        return {
            "episodic_count": self.episodic.count,
            "semantic_count": self.semantic.count,
            "semantic_associations": self.semantic.association_count,
            "procedural_count": self.procedural.count,
            "procedural_skills": self.procedural.get_skills()[:5],
            "working_count": self.working.count,
            "working_capacity": WORKING_MEMORY_CAPACITY,
            "working_utilization": round(self.working.utilization, 2),
            "total_consolidations": self._consolidation_count,
        }
