"""
Memory Manager — Three-Tier Biologically-Inspired Memory System

Working Memory: Fixed-capacity buffer of recently-accessed nodes with attention weights
Episodic Memory: Time-stamped reasoning episodes (input -> chain -> outcome)
Semantic Memory: The existing KnowledgeGraph (long-term conceptual storage)
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WorkingMemoryItem:
    """An item in working memory, tracking a knowledge graph node's relevance."""
    node_id: int
    relevance: float  # 0.0-1.0, decays over time
    last_access: float  # timestamp
    access_count: int = 1


@dataclass
class Episode:
    """A recorded reasoning episode with its context and outcome."""
    episode_id: int
    block_height: int
    input_node_ids: List[int] = field(default_factory=list)
    reasoning_strategy: str = ''
    conclusion_node_id: Optional[int] = None
    success: bool = False
    confidence: float = 0.0
    timestamp: float = 0.0
    replay_count: int = 0


class MemoryManager:
    """
    Three-tier memory system for the Aether Tree AGI engine.

    Tier 1 - Working Memory: Fixed-capacity buffer of KG node IDs with
        relevance scores that decay over time. Provides fast access to
        recently-relevant knowledge nodes.

    Tier 2 - Episodic Memory: Chronological record of reasoning episodes
        (what strategy was used, what inputs, whether it succeeded).
        Enables learning from past reasoning attempts.

    Tier 3 - Semantic Memory: The existing KnowledgeGraph (passed by
        reference). Long-term conceptual storage. Consolidation promotes
        frequently-accessed working memory items by boosting their
        confidence in the KG.
    """

    def __init__(self, knowledge_graph: object, capacity: int = 50) -> None:
        """Initialize the three-tier memory system.

        Args:
            knowledge_graph: Reference to the KnowledgeGraph (semantic memory).
            capacity: Maximum number of items in working memory.
        """
        self._kg = knowledge_graph
        self._capacity: int = capacity

        # Tier 1: Working memory
        self._working_memory: Dict[int, WorkingMemoryItem] = {}
        self._attend_calls: int = 0
        self._attend_hits: int = 0

        # Tier 2: Episodic memory
        self._episodes: List[Episode] = []
        self._max_episodes: int = 1000
        self._next_episode_id: int = 1

        # Tier 2 replay tracking: strategy -> successful replay count
        self._strategy_replay_success: Dict[str, int] = {}

        # Stats
        self._consolidations_total: int = 0
        self._replay_total: int = 0

        logger.info(
            f"MemoryManager initialized (working capacity={capacity}, "
            f"max episodes={self._max_episodes})"
        )

    # --- Working Memory ---

    def attend(self, node_id: int, boost: float = 0.3) -> None:
        """Add or boost a node in working memory.

        If the node is already present, its relevance is boosted and
        access count incremented. If at capacity, the lowest-relevance
        item is evicted to make room.

        Args:
            node_id: Knowledge graph node ID to attend to.
            boost: Amount to increase relevance (clamped to 1.0).
        """
        self._attend_calls += 1
        now = time.time()

        if node_id in self._working_memory:
            # Cache hit — boost existing item
            self._attend_hits += 1
            item = self._working_memory[node_id]
            item.relevance = min(1.0, item.relevance + boost)
            item.last_access = now
            item.access_count += 1
            return

        # New item — evict if at capacity
        if len(self._working_memory) >= self._capacity:
            self._evict_lowest()

        self._working_memory[node_id] = WorkingMemoryItem(
            node_id=node_id,
            relevance=min(1.0, boost),
            last_access=now,
            access_count=1,
        )

    def _evict_lowest(self) -> None:
        """Remove the item with the lowest relevance from working memory."""
        if not self._working_memory:
            return
        lowest_id = min(
            self._working_memory,
            key=lambda nid: self._working_memory[nid].relevance,
        )
        del self._working_memory[lowest_id]

    def retrieve(self, top_k: int = 10,
                 query_node_id: Optional[int] = None) -> List[int]:
        """Return the top-k node IDs sorted by relevance (highest first).

        When ``query_node_id`` is provided and a vector index is available on
        the knowledge graph, retrieval becomes *context-dependent*: each
        item's final score is a weighted combination of its existing relevance
        and its vector similarity to the query node.  This mimics human
        working memory where what is "relevant" depends on what you are
        currently thinking about.

        Args:
            top_k: Number of node IDs to return.
            query_node_id: Optional KG node ID to bias retrieval towards.
                If provided and embeddings are available, scores are
                combined: ``final = relevance * 0.6 + similarity * 0.4``.

        Returns:
            List of node IDs, most relevant first.
        """
        if not self._working_memory:
            return []

        # Attempt context-dependent scoring when a query node is given
        query_embedding: Optional[list] = None
        if query_node_id is not None and self._kg is not None:
            vi = getattr(self._kg, 'vector_index', None)
            if vi is not None and getattr(vi, 'embeddings', None):
                query_embedding = vi.get_embedding(query_node_id)

        if query_embedding is not None:
            from .vector_index import cosine_similarity
            scored: List[tuple] = []
            vi = self._kg.vector_index  # type: ignore[union-attr]
            for item in self._working_memory.values():
                item_emb = vi.get_embedding(item.node_id)
                if item_emb is not None:
                    sim = cosine_similarity(query_embedding, item_emb)
                    # Clamp similarity to [0, 1] (cosine can be slightly negative)
                    sim = max(0.0, sim)
                    final_score = item.relevance * 0.6 + sim * 0.4
                else:
                    final_score = item.relevance
                scored.append((item.node_id, final_score))
            scored.sort(key=lambda x: x[1], reverse=True)
            return [nid for nid, _ in scored[:top_k]]

        # Fallback: sort by relevance only
        sorted_items = sorted(
            self._working_memory.values(),
            key=lambda item: item.relevance,
            reverse=True,
        )
        return [item.node_id for item in sorted_items[:top_k]]

    def decay(self, factor: float = 0.95) -> None:
        """Multiply all relevance scores by a decay factor.

        Items whose relevance falls below 0.01 are removed.

        Args:
            factor: Multiplicative decay factor (0.0-1.0).
        """
        to_remove: List[int] = []
        for node_id, item in self._working_memory.items():
            item.relevance *= factor
            if item.relevance < 0.01:
                to_remove.append(node_id)

        for node_id in to_remove:
            del self._working_memory[node_id]

    def contains(self, node_id: int) -> bool:
        """Check if a node is currently in working memory.

        Args:
            node_id: Knowledge graph node ID.

        Returns:
            True if the node is in working memory.
        """
        return node_id in self._working_memory

    def get_hit_rate(self) -> float:
        """Fraction of attend() calls that found an existing item (cache hit).

        Returns:
            Hit rate as a float between 0.0 and 1.0.
        """
        if self._attend_calls == 0:
            return 0.0
        return self._attend_hits / self._attend_calls

    # --- Episodic Memory ---

    def record_episode(self, block_height: int, input_ids: List[int],
                       strategy: str, conclusion_id: Optional[int],
                       success: bool, confidence: float) -> Episode:
        """Record a reasoning episode.

        Args:
            block_height: Block height when the episode occurred.
            input_ids: Node IDs used as input to the reasoning.
            strategy: Name of the reasoning strategy used.
            conclusion_id: Node ID of the conclusion (if any).
            success: Whether the reasoning was successful.
            confidence: Confidence of the outcome.

        Returns:
            The recorded Episode.
        """
        episode = Episode(
            episode_id=self._next_episode_id,
            block_height=block_height,
            input_node_ids=list(input_ids),
            reasoning_strategy=strategy,
            conclusion_node_id=conclusion_id,
            success=success,
            confidence=confidence,
            timestamp=time.time(),
        )
        self._next_episode_id += 1
        self._episodes.append(episode)

        # FIFO eviction
        while len(self._episodes) > self._max_episodes:
            self._episodes.pop(0)

        return episode

    def recall_similar(self, strategy: str = '', success_only: bool = True,
                       limit: int = 10) -> List[Episode]:
        """Find similar past episodes.

        Args:
            strategy: Filter by reasoning strategy (empty = all strategies).
            success_only: If True, only return successful episodes.
            limit: Maximum number of episodes to return.

        Returns:
            List of matching Episodes, most recent first.
        """
        results: List[Episode] = []
        for episode in reversed(self._episodes):
            if strategy and episode.reasoning_strategy != strategy:
                continue
            if success_only and not episode.success:
                continue
            results.append(episode)
            if len(results) >= limit:
                break
        return results

    def get_success_rate(self, strategy: str = '') -> float:
        """Get the success rate for a strategy (or overall).

        Args:
            strategy: Filter by strategy name (empty = all).

        Returns:
            Success rate as a float between 0.0 and 1.0.
        """
        total = 0
        successes = 0
        for episode in self._episodes:
            if strategy and episode.reasoning_strategy != strategy:
                continue
            total += 1
            if episode.success:
                successes += 1
        if total == 0:
            return 0.0
        return successes / total

    # --- Consolidation ---

    def consolidate(self, block_height: int) -> int:
        """Consolidate working memory and prune episodic memory.

        Called every N blocks (e.g., 100). Performs two operations:

        1. Promotes frequently-accessed working memory items: if a node
           has access_count > 5 AND exists in the knowledge graph, its
           confidence is boosted by 0.05 (capped at 1.0).

        2. Prunes episodic memory: removes episodes older than 10000 blocks.

        Args:
            block_height: Current block height.

        Returns:
            Number of items consolidated (confidence-boosted).
        """
        consolidated = 0

        # Promote frequently-accessed working memory nodes to KG
        if self._kg and hasattr(self._kg, 'nodes'):
            for item in self._working_memory.values():
                if item.access_count > 5 and item.node_id in self._kg.nodes:
                    node = self._kg.nodes[item.node_id]
                    new_conf = min(1.0, node.confidence + 0.05)
                    if new_conf > node.confidence:
                        node.confidence = new_conf
                        consolidated += 1

        # Prune old episodes
        cutoff = block_height - 10000
        original_count = len(self._episodes)
        self._episodes = [
            ep for ep in self._episodes if ep.block_height >= cutoff
        ]
        pruned = original_count - len(self._episodes)

        self._consolidations_total += 1

        if consolidated > 0 or pruned > 0:
            logger.debug(
                f"Memory consolidation at block {block_height}: "
                f"{consolidated} nodes boosted, {pruned} old episodes pruned"
            )

        return consolidated

    # --- Episodic Replay ---

    def replay_episodes(self, block_height: int, top_k: int = 10) -> dict:
        """Replay recent episodic memories to reinforce or suppress patterns.

        Called every N blocks (e.g., 200). Selects the top-k most important
        episodes, reinforces successful ones (boost KG node confidence) and
        suppresses failed ones (reduce KG node confidence). Promotes
        frequently-replayed successful strategies to axiom nodes in the KG,
        mimicking sleep-based memory consolidation.

        Args:
            block_height: Current block height (used for recency weighting).
            top_k: Number of episodes to replay per call.

        Returns:
            Dict with replay statistics: episodes_replayed, reinforced,
            suppressed, promoted_to_axiom.
        """
        stats = {
            'episodes_replayed': 0,
            'reinforced': 0,
            'suppressed': 0,
            'promoted_to_axiom': 0,
        }

        if not self._episodes:
            return stats

        # Step 1: Score episodes by importance = success_weight * recency_weight
        scored: List[tuple] = []
        for episode in self._episodes:
            success_weight = 1.5 if episode.success else 0.5
            recency_weight = 1.0 / (1 + (block_height - episode.block_height) / 1000)
            importance = success_weight * recency_weight
            scored.append((importance, episode))

        # Sort by importance descending and take top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = scored[:top_k]

        has_kg = self._kg is not None and hasattr(self._kg, 'nodes')

        for _importance, episode in selected:
            episode.replay_count += 1
            stats['episodes_replayed'] += 1

            if not has_kg:
                continue

            # Check conclusion node status
            conclusion_exists = False
            conclusion_confident = False
            if episode.conclusion_node_id is not None:
                conclusion_node = self._kg.nodes.get(episode.conclusion_node_id)
                if conclusion_node is not None:
                    conclusion_exists = True
                    conclusion_confident = conclusion_node.confidence > 0.3

            # Step 2a: Reinforce successful episodes with confident conclusions
            if episode.success and conclusion_exists and conclusion_confident:
                # Boost conclusion node confidence by 0.03
                c_node = self._kg.nodes[episode.conclusion_node_id]
                c_node.confidence = min(1.0, c_node.confidence + 0.03)

                # Boost input nodes' confidence by 0.01 each
                for input_id in episode.input_node_ids:
                    input_node = self._kg.nodes.get(input_id)
                    if input_node is not None:
                        input_node.confidence = min(1.0, input_node.confidence + 0.01)

                stats['reinforced'] += 1

                # Track successful replay for this strategy
                strategy = episode.reasoning_strategy
                if strategy:
                    self._strategy_replay_success[strategy] = (
                        self._strategy_replay_success.get(strategy, 0) + 1
                    )

            # Step 2b: Suppress unsuccessful or degraded episodes
            elif not episode.success or not conclusion_exists or (
                conclusion_exists
                and self._kg.nodes[episode.conclusion_node_id].confidence < 0.1
            ):
                # Reduce input nodes' confidence by 0.02 (floored at 0.05)
                for input_id in episode.input_node_ids:
                    input_node = self._kg.nodes.get(input_id)
                    if input_node is not None:
                        input_node.confidence = max(0.05, input_node.confidence - 0.02)

                stats['suppressed'] += 1

        # Step 3: Promote frequently-replayed successful strategies to axioms
        if has_kg and hasattr(self._kg, 'add_node'):
            for strategy, count in self._strategy_replay_success.items():
                if count >= 5:
                    # Create an axiom node for this consolidated pattern
                    self._kg.add_node(
                        node_type='axiom',
                        content={
                            'type': 'consolidated_pattern',
                            'strategy': strategy,
                            'replay_count': count,
                        },
                        confidence=0.8,
                        source_block=block_height,
                    )
                    stats['promoted_to_axiom'] += 1
                    logger.info(
                        f"Promoted strategy '{strategy}' to axiom "
                        f"(replay_count={count})"
                    )
                    # Reset counter after promotion to avoid duplicate axioms
                    self._strategy_replay_success[strategy] = 0

        self._replay_total += 1

        if stats['episodes_replayed'] > 0:
            logger.debug(
                f"Episodic replay at block {block_height}: "
                f"replayed={stats['episodes_replayed']}, "
                f"reinforced={stats['reinforced']}, "
                f"suppressed={stats['suppressed']}, "
                f"promoted={stats['promoted_to_axiom']}"
            )

        return stats

    # --- Stats ---

    def get_stats(self) -> dict:
        """Get memory manager statistics.

        Returns:
            Dict with working memory, episodic, and consolidation stats.
        """
        episodes_successful = sum(1 for ep in self._episodes if ep.success)
        return {
            'working_memory_size': len(self._working_memory),
            'working_memory_capacity': self._capacity,
            'working_memory_hit_rate': round(self.get_hit_rate(), 4),
            'episodes_total': len(self._episodes),
            'episodes_successful': episodes_successful,
            'consolidations_total': self._consolidations_total,
            'replay_total': self._replay_total,
            'strategy_replay_success': dict(self._strategy_replay_success),
        }
