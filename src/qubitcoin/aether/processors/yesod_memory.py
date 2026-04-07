"""
Yesod Memory Processor — Memory consolidation and contextual retrieval.

Yesod is the memory Sephirah. It:
1. Retrieves relevant past interactions and knowledge
2. Provides contextual memory that enriches other processors' reasoning
3. Consolidates frequently-accessed knowledge for faster retrieval
4. Manages the transition between working memory and long-term KG storage

Yesod answers: "What do we already know that is relevant to this?"
"""
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from ..cognitive_processor import (
    CognitiveProcessor,
    CognitiveResponse,
    SoulPriors,
    WorkspaceItem,
)
from ...utils.logger import get_logger

logger = get_logger(__name__)

# Maximum number of KG nodes to examine per query
MAX_SEARCH_RESULTS: int = 20

# Maximum working memory items to retrieve
MAX_WORKING_MEMORY: int = 15

# Maximum episodic memories to recall
MAX_EPISODES: int = 10


class YesodMemoryProcessor(CognitiveProcessor):
    """Memory consolidation and contextual retrieval processor.

    Yesod searches working memory, episodic memory, and the knowledge
    graph to assemble a rich context of what is already known about
    the current stimulus. This context feeds into other Sephirot
    so they reason with full access to relevant memories.
    """

    def __init__(self, knowledge_graph: Any = None,
                 soul: Optional[SoulPriors] = None,
                 memory_manager: Any = None) -> None:
        super().__init__(role="yesod", knowledge_graph=knowledge_graph, soul=soul)
        self.memory_manager = memory_manager
        self._retrieval_count: int = 0
        self._cache_hits: int = 0

        if memory_manager is None:
            logger.warning("Yesod initialized without MemoryManager — limited to KG search")

    # ------------------------------------------------------------------
    # CognitiveProcessor interface
    # ------------------------------------------------------------------

    def process(self, stimulus: WorkspaceItem) -> CognitiveResponse:
        """Retrieve relevant memories for the current stimulus."""
        t0 = time.time()
        self._retrieval_count += 1

        memory_fragments: List[Dict[str, Any]] = []
        evidence_nodes: List[int] = []
        trace: List[Dict[str, Any]] = []

        # 1. Working memory — recently accessed relevant nodes
        wm_fragments, wm_evidence = self._search_working_memory(stimulus)
        memory_fragments.extend(wm_fragments)
        evidence_nodes.extend(wm_evidence)
        trace.append({
            "step": "working_memory_search",
            "items_found": len(wm_fragments),
        })

        # 2. Episodic memory — similar past reasoning episodes
        ep_fragments = self._search_episodic_memory(stimulus)
        memory_fragments.extend(ep_fragments)
        trace.append({
            "step": "episodic_memory_search",
            "episodes_found": len(ep_fragments),
        })

        # 3. User memories — what we know about this person
        user_fragments = self._gather_user_memories(stimulus)
        memory_fragments.extend(user_fragments)
        trace.append({
            "step": "user_memory_lookup",
            "items_found": len(user_fragments),
        })

        # 4. Knowledge graph search — semantic retrieval
        kg_fragments, kg_evidence = self._search_knowledge_graph(stimulus)
        memory_fragments.extend(kg_fragments)
        evidence_nodes.extend(kg_evidence)
        trace.append({
            "step": "knowledge_graph_search",
            "nodes_found": len(kg_fragments),
        })

        # 5. Attend to retrieved nodes so they stay in working memory
        self._attend_to_evidence(evidence_nodes)

        # Compose the memory context
        content = self._compose_memory_context(memory_fragments, stimulus)

        # Confidence scales with how much relevant memory we found
        total_items = len(memory_fragments)
        confidence = min(0.9, 0.2 + 0.07 * total_items)

        # Relevance: memory context is always moderately useful
        relevance = min(0.85, 0.3 + 0.05 * total_items)

        latency_ms = (time.time() - t0) * 1000
        self._record_metrics(latency_ms, confidence)

        return self._make_response(
            content=content,
            confidence=confidence,
            relevance=relevance,
            novelty=0.2,  # Memory recall is low novelty by nature
            evidence=evidence_nodes[:10],
            trace=trace,
            metadata={
                "total_memories_retrieved": total_items,
                "working_memory_hits": len(wm_fragments),
                "episodic_hits": len(ep_fragments),
                "kg_hits": len(kg_fragments),
                "user_memory_hits": len(user_fragments),
            },
        )

    # ------------------------------------------------------------------
    # Internal: Memory source searches
    # ------------------------------------------------------------------

    def _search_working_memory(
        self, stimulus: WorkspaceItem,
    ) -> tuple[List[Dict[str, Any]], List[int]]:
        """Search working memory for recently-accessed relevant nodes."""
        fragments: List[Dict[str, Any]] = []
        evidence: List[int] = []

        if self.memory_manager is None or self.kg is None:
            return fragments, evidence

        try:
            # Retrieve top nodes from working memory
            node_ids = self.memory_manager.retrieve(top_k=MAX_WORKING_MEMORY)
            for nid in node_ids:
                node = self.kg.nodes.get(nid)
                if node is None:
                    continue
                node_content = getattr(node, "content", {})
                if isinstance(node_content, dict):
                    text = node_content.get("text", node_content.get("title", ""))
                else:
                    text = str(node_content)
                if not text:
                    continue

                # Check relevance to stimulus
                if self._is_relevant(text, stimulus.content):
                    self._cache_hits += 1
                    fragments.append({
                        "source": "working_memory",
                        "node_id": nid,
                        "content": text[:300],
                        "domain": getattr(node, "domain", "unknown"),
                        "confidence": getattr(node, "confidence", 0.5),
                    })
                    evidence.append(nid)
        except Exception as e:
            logger.debug("Yesod working memory search error: %s", e)

        return fragments, evidence

    def _search_episodic_memory(
        self, stimulus: WorkspaceItem,
    ) -> List[Dict[str, Any]]:
        """Search episodic memory for similar past reasoning episodes."""
        fragments: List[Dict[str, Any]] = []

        if self.memory_manager is None:
            return fragments

        try:
            # Recall recent successful episodes
            episodes = self.memory_manager.recall_similar(
                strategy="",
                success_only=False,
                limit=MAX_EPISODES,
            )
            for episode in episodes:
                strategy = getattr(episode, "reasoning_strategy", "")
                success = getattr(episode, "success", False)
                confidence = getattr(episode, "confidence", 0.0)
                fragments.append({
                    "source": "episodic_memory",
                    "strategy": strategy,
                    "success": success,
                    "confidence": confidence,
                    "episode_id": getattr(episode, "episode_id", 0),
                })
        except Exception as e:
            logger.debug("Yesod episodic memory search error: %s", e)

        return fragments

    def _gather_user_memories(
        self, stimulus: WorkspaceItem,
    ) -> List[Dict[str, Any]]:
        """Gather stored user memories from stimulus context."""
        fragments: List[Dict[str, Any]] = []
        user_memories = stimulus.context.get("user_memories", {})

        if not user_memories:
            return fragments

        for key, value in user_memories.items():
            fragments.append({
                "source": "user_memory",
                "key": key,
                "value": str(value)[:200],
            })

        return fragments

    def _search_knowledge_graph(
        self, stimulus: WorkspaceItem,
    ) -> tuple[List[Dict[str, Any]], List[int]]:
        """Search the knowledge graph for relevant nodes."""
        fragments: List[Dict[str, Any]] = []
        evidence: List[int] = []

        if self.kg is None or not stimulus.content:
            return fragments, evidence

        try:
            # Use pre-matched knowledge refs first
            search_ids: List[int] = list(stimulus.knowledge_refs[:10])

            # Supplement with TF-IDF search
            search_results = self.kg.search(stimulus.content, limit=MAX_SEARCH_RESULTS)
            for nid in search_results:
                if nid not in search_ids:
                    search_ids.append(nid)
                if len(search_ids) >= MAX_SEARCH_RESULTS:
                    break

            for nid in search_ids:
                node = self.kg.nodes.get(nid)
                if node is None:
                    continue
                node_content = getattr(node, "content", {})
                if isinstance(node_content, dict):
                    text = node_content.get("text", node_content.get("title", ""))
                else:
                    text = str(node_content)
                if not text:
                    continue

                domain = getattr(node, "domain", "unknown")
                conf = getattr(node, "confidence", 0.5)

                fragments.append({
                    "source": "knowledge_graph",
                    "node_id": nid,
                    "content": text[:300],
                    "domain": domain,
                    "confidence": conf,
                    "node_type": getattr(node, "node_type", "unknown"),
                })
                evidence.append(nid)

        except Exception as e:
            logger.debug("Yesod KG search error: %s", e)

        return fragments, evidence

    # ------------------------------------------------------------------
    # Internal: Helpers
    # ------------------------------------------------------------------

    def _attend_to_evidence(self, evidence_nodes: List[int]) -> None:
        """Boost evidence nodes in working memory so they persist."""
        if self.memory_manager is None:
            return
        for nid in evidence_nodes[:10]:
            try:
                self.memory_manager.attend(nid, boost=0.2)
            except Exception:
                pass

    def _is_relevant(self, text: str, query: str) -> bool:
        """Simple word-overlap relevance check.

        Returns True if the text shares significant tokens with the query.
        This is intentionally simple — deeper relevance is handled by
        the KG search and vector index.
        """
        if not text or not query:
            return False
        text_tokens = set(text.lower().split())
        query_tokens = set(query.lower().split())
        # Remove common stop words
        stop = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
                "to", "for", "of", "and", "or", "but", "it", "this", "that",
                "with", "from", "by", "as", "be", "has", "had", "have", "do",
                "does", "did", "will", "would", "can", "could", "i", "you",
                "we", "they", "what", "how", "why", "when", "where"}
        text_tokens -= stop
        query_tokens -= stop
        if not query_tokens:
            return False
        overlap = text_tokens & query_tokens
        return len(overlap) / len(query_tokens) >= 0.2

    def _compose_memory_context(
        self,
        fragments: List[Dict[str, Any]],
        stimulus: WorkspaceItem,
    ) -> str:
        """Compose retrieved memories into a coherent context string."""
        if not fragments:
            return (
                "No strongly relevant memories found for this query. "
                "Reasoning from general knowledge."
            )

        parts: List[str] = []

        # Group by source
        by_source: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for frag in fragments:
            by_source[frag["source"]].append(frag)

        # User memories first — personal context
        if "user_memory" in by_source:
            user_parts = []
            for frag in by_source["user_memory"]:
                user_parts.append(f"{frag['key']}: {frag['value']}")
            parts.append(
                "What I remember about you: " + "; ".join(user_parts) + "."
            )

        # Knowledge graph hits — domain knowledge
        if "knowledge_graph" in by_source:
            kg_items = by_source["knowledge_graph"][:5]
            knowledge_parts = []
            for frag in kg_items:
                domain = frag.get("domain", "")
                content = frag.get("content", "")
                domain_prefix = f"[{domain}] " if domain and domain != "unknown" else ""
                knowledge_parts.append(f"{domain_prefix}{content}")
            parts.append(
                "Relevant knowledge I have:\n"
                + "\n".join(f"  - {kp}" for kp in knowledge_parts)
            )

        # Working memory — recently active context
        if "working_memory" in by_source:
            wm_items = by_source["working_memory"][:3]
            wm_parts = [frag.get("content", "") for frag in wm_items if frag.get("content")]
            if wm_parts:
                parts.append(
                    "Recently active in my mind: " + "; ".join(wm_parts) + "."
                )

        # Episodic — what reasoning approaches worked before
        if "episodic_memory" in by_source:
            ep_items = by_source["episodic_memory"][:3]
            success_count = sum(1 for e in ep_items if e.get("success"))
            total = len(ep_items)
            strategies = set(e.get("strategy", "") for e in ep_items if e.get("strategy"))
            if strategies:
                parts.append(
                    f"Past reasoning attempts used: {', '.join(strategies)} "
                    f"({success_count}/{total} successful)."
                )

        return " ".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """Extended stats for the memory processor."""
        base = super().get_stats()
        base.update({
            "total_retrievals": self._retrieval_count,
            "working_memory_cache_hits": self._cache_hits,
            "has_memory_manager": self.memory_manager is not None,
        })
        return base
