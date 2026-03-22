"""
KGQA — Knowledge Graph Question Answering for Aether Tree

Item #48: Parse questions, classify type, query KG, traverse graph,
and generate natural language answers.
"""
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class KGQAResult:
    """Result of a KGQA query."""
    answer_text: str
    confidence: float           # 0.0–1.0
    sources: List[int] = field(default_factory=list)   # KG node IDs used
    reasoning_path: List[str] = field(default_factory=list)
    question_type: str = "unknown"


# ---------------------------------------------------------------------------
# Question classification patterns
# ---------------------------------------------------------------------------

_FACTOID_PATTERNS = [
    re.compile(r"^what (?:is|are|was|were) ", re.I),
    re.compile(r"^who (?:is|are|was|were) ", re.I),
    re.compile(r"^where (?:is|are|was|were) ", re.I),
    re.compile(r"^tell me about ", re.I),
    re.compile(r"^describe ", re.I),
    re.compile(r"^define ", re.I),
]

_COUNT_PATTERNS = [
    re.compile(r"^how many ", re.I),
    re.compile(r"^how much ", re.I),
    re.compile(r"^count ", re.I),
    re.compile(r"^total (?:number of )?", re.I),
]

_TEMPORAL_PATTERNS = [
    re.compile(r"^when (?:did|was|were|is|will) ", re.I),
    re.compile(r"what happened (?:at|on|in|during) ", re.I),
    re.compile(r"what (?:was|is) (?:the )?\w+ at block ", re.I),
    re.compile(r"block (?:#?\d+|number \d+)", re.I),
]

_CAUSAL_PATTERNS = [
    re.compile(r"^why (?:did|does|do|is|are|was|were) ", re.I),
    re.compile(r"what (?:caused|causes|led to) ", re.I),
    re.compile(r"^how (?:did|does|do) ", re.I),
    re.compile(r"reason for ", re.I),
]

_COMPARISON_PATTERNS = [
    re.compile(r"compare ", re.I),
    re.compile(r"difference between ", re.I),
    re.compile(r"(?:which|what) is (?:better|worse|higher|lower|faster|slower)", re.I),
    re.compile(r" vs\.? ", re.I),
    re.compile(r" versus ", re.I),
    re.compile(r"compared to ", re.I),
]

_AGGREGATE_PATTERNS = [
    re.compile(r"^(?:what is the )?(?:average|mean|median|max|min|sum|total)", re.I),
    re.compile(r"^(?:list|show|give me) (?:all|every) ", re.I),
    re.compile(r"^summarize ", re.I),
    re.compile(r"^overview of ", re.I),
]

# Block number extraction
_BLOCK_NUM_RE = re.compile(r'block\s*#?\s*(\d+)', re.I)
# Amount extraction
_AMOUNT_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:QBC|QUSD|qbc|qusd)', re.I)
# Address extraction
_ADDR_RE = re.compile(r'(0x[0-9a-fA-F]{40}|qbc1[0-9a-z]{38,62})')


def _classify_question(text: str) -> str:
    """Classify a question into a type category."""
    for pattern in _COMPARISON_PATTERNS:
        if pattern.search(text):
            return "comparison"
    for pattern in _CAUSAL_PATTERNS:
        if pattern.search(text):
            return "causal"
    for pattern in _TEMPORAL_PATTERNS:
        if pattern.search(text):
            return "temporal"
    for pattern in _COUNT_PATTERNS:
        if pattern.search(text):
            return "aggregate"
    for pattern in _AGGREGATE_PATTERNS:
        if pattern.search(text):
            return "aggregate"
    for pattern in _FACTOID_PATTERNS:
        if pattern.search(text):
            return "factoid"
    # Default: factoid if it ends with '?' else unknown
    if text.strip().endswith("?"):
        return "factoid"
    return "unknown"


def _extract_keywords(text: str) -> List[str]:
    """Extract search keywords from a question."""
    # Remove common question words
    stop = {
        "what", "is", "are", "was", "were", "the", "a", "an", "of", "in",
        "on", "at", "to", "for", "with", "from", "by", "about", "how",
        "many", "much", "who", "where", "when", "why", "did", "does",
        "do", "can", "could", "will", "would", "should", "tell", "me",
        "and", "or", "but", "this", "that", "these", "those", "it",
        "has", "have", "had", "be", "been", "being", "not", "no",
        "compare", "between", "difference", "vs", "versus", "show",
        "list", "give", "all", "every", "describe", "define",
    }
    tokens = re.findall(r'[a-zA-Z0-9]+', text.lower())
    return [t for t in tokens if t not in stop and len(t) > 1]


class KGQA:
    """Knowledge Graph Question Answering engine.

    Parses questions, queries the knowledge graph, traverses multi-hop
    paths, and generates natural language answers.
    """

    def __init__(self, knowledge_graph: Optional[Any] = None) -> None:
        self._kg = knowledge_graph
        self._calls: int = 0
        self._total_time: float = 0.0
        self._questions_by_type: Dict[str, int] = {}
        self._avg_confidence: float = 0.0
        self._total_confidence: float = 0.0

    def set_knowledge_graph(self, kg: Any) -> None:
        """Update the knowledge graph reference."""
        self._kg = kg

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def answer(self, question: str,
               knowledge_graph: Optional[Any] = None) -> KGQAResult:
        """Answer a question using the knowledge graph.

        Args:
            question: Natural language question.
            knowledge_graph: Optional KG override.

        Returns:
            KGQAResult with answer, confidence, sources, reasoning path.
        """
        t0 = time.time()
        self._calls += 1
        kg = knowledge_graph or self._kg

        if not kg or not hasattr(kg, 'nodes') or not kg.nodes:
            self._total_time += time.time() - t0
            return KGQAResult(
                answer_text="I don't have enough knowledge to answer that yet.",
                confidence=0.0,
                question_type="unknown",
            )

        q_type = _classify_question(question)
        self._questions_by_type[q_type] = self._questions_by_type.get(q_type, 0) + 1

        reasoning_path: List[str] = [f"Question type: {q_type}"]

        # Route to handler
        if q_type == "factoid":
            result = self._handle_factoid(question, kg, reasoning_path)
        elif q_type == "aggregate":
            result = self._handle_aggregate(question, kg, reasoning_path)
        elif q_type == "temporal":
            result = self._handle_temporal(question, kg, reasoning_path)
        elif q_type == "causal":
            result = self._handle_causal(question, kg, reasoning_path)
        elif q_type == "comparison":
            result = self._handle_comparison(question, kg, reasoning_path)
        else:
            result = self._handle_factoid(question, kg, reasoning_path)

        result.question_type = q_type

        self._total_confidence += result.confidence
        self._avg_confidence = self._total_confidence / self._calls
        self._total_time += time.time() - t0
        return result

    # ------------------------------------------------------------------
    # Question handlers
    # ------------------------------------------------------------------

    def _handle_factoid(self, question: str, kg: Any,
                        path: List[str]) -> KGQAResult:
        """Handle factoid questions: 'What is X?'"""
        keywords = _extract_keywords(question)
        path.append(f"Search keywords: {keywords}")

        matched_nodes = self._search_nodes(kg, keywords)
        if not matched_nodes:
            return KGQAResult(
                answer_text="I couldn't find relevant information in my knowledge graph.",
                confidence=0.1,
                reasoning_path=path,
            )

        path.append(f"Found {len(matched_nodes)} matching nodes")

        # Build answer from top matches
        top_nodes = matched_nodes[:5]
        answer_parts: List[str] = []
        sources: List[int] = []

        for node, score in top_nodes:
            nid = getattr(node, 'node_id', None)
            if nid is not None:
                sources.append(nid)
            content = getattr(node, 'content', {})
            if isinstance(content, dict):
                desc = (content.get('description') or content.get('text')
                        or content.get('explanation'))
                if desc:
                    answer_parts.append(str(desc))
                else:
                    # Summarize content fields
                    ntype = content.get('type', '')
                    summary = self._summarize_content(content)
                    if summary:
                        answer_parts.append(summary)
            elif isinstance(content, str):
                answer_parts.append(content)

        # Multi-hop: follow edges from matched nodes (2-3 hops)
        hop_answers, hop_sources = self._multi_hop(kg, sources, max_hops=2)
        answer_parts.extend(hop_answers)
        sources.extend(hop_sources)

        if answer_parts:
            answer = " ".join(answer_parts[:5])
            confidence = min(0.9, 0.3 + 0.12 * len(answer_parts))
        else:
            answer = "I found related knowledge nodes but couldn't extract a clear answer."
            confidence = 0.2

        path.append(f"Answer assembled from {len(answer_parts)} fragments")
        return KGQAResult(
            answer_text=answer,
            confidence=round(confidence, 3),
            sources=list(dict.fromkeys(sources))[:20],
            reasoning_path=path,
        )

    def _handle_aggregate(self, question: str, kg: Any,
                          path: List[str]) -> KGQAResult:
        """Handle aggregate questions: 'How many X?'"""
        keywords = _extract_keywords(question)
        path.append(f"Aggregate query with keywords: {keywords}")

        matched_nodes = self._search_nodes(kg, keywords)
        count = len(matched_nodes)
        sources = [
            getattr(n, 'node_id', 0) for n, _ in matched_nodes[:20]
            if getattr(n, 'node_id', None) is not None
        ]

        # Check for specific aggregation keywords
        q_lower = question.lower()
        if "average" in q_lower or "mean" in q_lower:
            # Try to compute average of numeric content
            values = self._extract_numeric_values(matched_nodes, keywords)
            if values:
                avg = sum(values) / len(values)
                answer = (
                    f"Based on {len(values)} data points, the average is {avg:.4f}."
                )
                confidence = min(0.85, 0.3 + 0.1 * len(values))
                path.append(f"Computed average from {len(values)} values")
                return KGQAResult(
                    answer_text=answer, confidence=round(confidence, 3),
                    sources=sources, reasoning_path=path,
                )

        if count > 0:
            keyword_str = " ".join(keywords) if keywords else "that topic"
            answer = (
                f"I found {count} knowledge node(s) related to {keyword_str} "
                f"in my knowledge graph."
            )
            confidence = min(0.8, 0.3 + 0.05 * count)
        else:
            answer = "I don't have any knowledge nodes matching that query."
            confidence = 0.2

        path.append(f"Count result: {count}")
        return KGQAResult(
            answer_text=answer, confidence=round(confidence, 3),
            sources=sources, reasoning_path=path,
        )

    def _handle_temporal(self, question: str, kg: Any,
                         path: List[str]) -> KGQAResult:
        """Handle temporal questions: 'What happened at block N?'"""
        # Extract block number
        block_match = _BLOCK_NUM_RE.search(question)
        if block_match:
            block_num = int(block_match.group(1))
            path.append(f"Looking up block {block_num}")

            # Find nodes at this block height
            block_nodes = []
            for nid, node in kg.nodes.items():
                source_block = getattr(node, 'source_block', None)
                content = getattr(node, 'content', {})
                height = content.get('height') if isinstance(content, dict) else None
                if source_block == block_num or height == block_num:
                    block_nodes.append(node)

            if block_nodes:
                sources = [
                    getattr(n, 'node_id', 0) for n in block_nodes
                    if getattr(n, 'node_id', None) is not None
                ]
                answer_parts = []
                for node in block_nodes[:5]:
                    content = getattr(node, 'content', {})
                    if isinstance(content, dict):
                        summary = self._summarize_content(content)
                        if summary:
                            answer_parts.append(summary)

                answer = (
                    f"At block {block_num}: " + " ".join(answer_parts)
                    if answer_parts
                    else f"Block {block_num} is recorded in my knowledge graph with {len(block_nodes)} node(s)."
                )
                confidence = min(0.85, 0.4 + 0.1 * len(block_nodes))
                path.append(f"Found {len(block_nodes)} nodes at block {block_num}")
                return KGQAResult(
                    answer_text=answer, confidence=round(confidence, 3),
                    sources=sources, reasoning_path=path,
                )

        # Fallback to keyword search
        return self._handle_factoid(question, kg, path)

    def _handle_causal(self, question: str, kg: Any,
                       path: List[str]) -> KGQAResult:
        """Handle causal questions: 'Why did X change?'"""
        keywords = _extract_keywords(question)
        path.append(f"Causal query with keywords: {keywords}")

        matched_nodes = self._search_nodes(kg, keywords)
        if not matched_nodes:
            return KGQAResult(
                answer_text="I don't have enough causal knowledge to answer that.",
                confidence=0.1,
                reasoning_path=path,
            )

        # Look for causal edges
        causal_chains: List[str] = []
        sources: List[int] = []

        for node, score in matched_nodes[:5]:
            nid = getattr(node, 'node_id', None)
            if nid is None:
                continue
            sources.append(nid)

            # Follow causal edges
            if hasattr(kg, 'edges'):
                for edge_key, edge_type in kg.edges.items():
                    if not isinstance(edge_key, tuple) or len(edge_key) < 2:
                        continue
                    src_id, tgt_id = edge_key[0], edge_key[1]
                    etype = edge_type if isinstance(edge_type, str) else getattr(edge_type, 'edge_type', '')
                    if etype in ('causes', 'derives', 'supports') and src_id == nid:
                        target_node = kg.nodes.get(tgt_id)
                        if target_node:
                            src_text = self._node_brief(node)
                            tgt_text = self._node_brief(target_node)
                            causal_chains.append(f"{src_text} → {tgt_text}")
                            sources.append(tgt_id)

        if causal_chains:
            answer = "Causal chain: " + "; ".join(causal_chains[:3]) + "."
            confidence = min(0.8, 0.3 + 0.15 * len(causal_chains))
        else:
            # Fallback: describe what we know
            node_descs = []
            for node, _ in matched_nodes[:3]:
                desc = self._node_brief(node)
                if desc:
                    node_descs.append(desc)
            if node_descs:
                answer = (
                    "I found related knowledge but no direct causal links: "
                    + "; ".join(node_descs) + "."
                )
                confidence = 0.3
            else:
                answer = "I don't have causal information about that topic."
                confidence = 0.15

        path.append(f"Found {len(causal_chains)} causal chains")
        return KGQAResult(
            answer_text=answer, confidence=round(confidence, 3),
            sources=list(dict.fromkeys(sources))[:20],
            reasoning_path=path,
        )

    def _handle_comparison(self, question: str, kg: Any,
                           path: List[str]) -> KGQAResult:
        """Handle comparison questions: 'Compare X and Y'."""
        keywords = _extract_keywords(question)
        path.append(f"Comparison query with keywords: {keywords}")

        # Try to split into two entity groups
        q_lower = question.lower()
        split_words = [" and ", " vs ", " versus ", " compared to ", " or "]
        entity_a_kw: List[str] = []
        entity_b_kw: List[str] = []

        for sw in split_words:
            if sw in q_lower:
                parts = q_lower.split(sw, 1)
                entity_a_kw = _extract_keywords(parts[0])
                entity_b_kw = _extract_keywords(parts[1])
                break

        if not entity_a_kw and not entity_b_kw:
            # Fall back to general keyword search
            entity_a_kw = keywords[:len(keywords)//2] or keywords
            entity_b_kw = keywords[len(keywords)//2:] or keywords

        nodes_a = self._search_nodes(kg, entity_a_kw)
        nodes_b = self._search_nodes(kg, entity_b_kw)

        sources: List[int] = []
        parts_list: List[str] = []

        # Describe entity A
        if nodes_a:
            a_desc = self._node_brief(nodes_a[0][0])
            parts_list.append(f"About {' '.join(entity_a_kw)}: {a_desc}")
            for n, _ in nodes_a[:3]:
                nid = getattr(n, 'node_id', None)
                if nid is not None:
                    sources.append(nid)

        # Describe entity B
        if nodes_b:
            b_desc = self._node_brief(nodes_b[0][0])
            parts_list.append(f"About {' '.join(entity_b_kw)}: {b_desc}")
            for n, _ in nodes_b[:3]:
                nid = getattr(n, 'node_id', None)
                if nid is not None:
                    sources.append(nid)

        if parts_list:
            answer = " | ".join(parts_list)
            confidence = min(0.75, 0.2 + 0.1 * (len(nodes_a) + len(nodes_b)))
        else:
            answer = "I don't have enough information to compare those topics."
            confidence = 0.15

        path.append(f"Compared {len(nodes_a)} vs {len(nodes_b)} nodes")
        return KGQAResult(
            answer_text=answer, confidence=round(confidence, 3),
            sources=list(dict.fromkeys(sources))[:20],
            reasoning_path=path,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _search_nodes(self, kg: Any, keywords: List[str]) -> List[Tuple[Any, float]]:
        """Search KG nodes by keyword matching. Returns (node, score) pairs."""
        if not keywords or not hasattr(kg, 'nodes'):
            return []

        results: List[Tuple[Any, float]] = []

        for nid, node in kg.nodes.items():
            content = getattr(node, 'content', None)
            domain = getattr(node, 'domain', '')
            confidence = getattr(node, 'confidence', 0)

            # Build searchable text
            searchable = ""
            if isinstance(content, dict):
                for val in content.values():
                    if isinstance(val, str):
                        searchable += " " + val.lower()
                    elif isinstance(val, (int, float)):
                        searchable += " " + str(val)
            elif isinstance(content, str):
                searchable = content.lower()

            searchable += " " + domain.lower()

            # Score by keyword match count
            score = 0.0
            for kw in keywords:
                if kw in searchable:
                    score += 1.0

            if score > 0:
                # Boost by confidence
                score *= (0.5 + 0.5 * confidence)
                results.append((node, score))

        # Sort by score descending
        results.sort(key=lambda x: -x[1])
        return results[:50]

    def _multi_hop(self, kg: Any, source_ids: List[int],
                   max_hops: int = 2) -> Tuple[List[str], List[int]]:
        """Follow edges from source nodes up to max_hops."""
        if not hasattr(kg, 'edges') or not source_ids:
            return [], []

        answers: List[str] = []
        extra_sources: List[int] = []
        visited = set(source_ids)

        current_ids = list(source_ids)

        for hop in range(max_hops):
            next_ids: List[int] = []
            for nid in current_ids:
                for edge_key in kg.edges:
                    if not isinstance(edge_key, tuple) or len(edge_key) < 2:
                        continue
                    src_id, tgt_id = edge_key[0], edge_key[1]
                    if src_id == nid and tgt_id not in visited:
                        visited.add(tgt_id)
                        next_ids.append(tgt_id)
                        target = kg.nodes.get(tgt_id)
                        if target:
                            brief = self._node_brief(target)
                            if brief:
                                answers.append(brief)
                                extra_sources.append(tgt_id)

                    if len(next_ids) > 10:
                        break
                if len(next_ids) > 10:
                    break

            current_ids = next_ids
            if not current_ids:
                break

        return answers[:5], extra_sources[:10]

    @staticmethod
    def _node_brief(node: Any) -> str:
        """Get a brief description of a node."""
        content = getattr(node, 'content', None)
        if isinstance(content, dict):
            desc = (content.get('description') or content.get('text')
                    or content.get('explanation'))
            if desc:
                return str(desc)[:200]
            ntype = content.get('type', '')
            height = content.get('height') or content.get('block_height')
            if height:
                return f"{ntype} at block {height}"
            return str(ntype) if ntype else ""
        elif isinstance(content, str):
            return content[:200]
        return ""

    @staticmethod
    def _summarize_content(content: dict) -> str:
        """Summarize a node content dict into a sentence."""
        parts: List[str] = []
        ntype = content.get('type', '')
        if ntype:
            parts.append(ntype.replace('_', ' '))

        for key in ('height', 'block_height', 'difficulty', 'tx_count',
                     'energy', 'metric', 'predicted_value'):
            val = content.get(key)
            if val is not None:
                parts.append(f"{key}={val}")

        desc = content.get('description') or content.get('explanation')
        if desc:
            parts.append(str(desc)[:100])

        return ", ".join(parts) if parts else ""

    def _extract_numeric_values(self, matched_nodes: List[Tuple[Any, float]],
                                keywords: List[str]) -> List[float]:
        """Extract numeric values from matched nodes."""
        values: List[float] = []
        for node, _ in matched_nodes:
            content = getattr(node, 'content', {})
            if not isinstance(content, dict):
                continue
            for key, val in content.items():
                if isinstance(val, (int, float)):
                    # Prefer keys that match a keyword
                    if any(kw in key.lower() for kw in keywords):
                        values.append(float(val))
                    elif key in ('value', 'amount', 'difficulty', 'energy'):
                        values.append(float(val))
        return values

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return KGQA statistics."""
        return {
            "calls": self._calls,
            "total_time_s": round(self._total_time, 4),
            "avg_confidence": round(self._avg_confidence, 4),
            "questions_by_type": dict(self._questions_by_type),
            "avg_time_per_call_ms": (
                round(self._total_time / self._calls * 1000, 2)
                if self._calls else 0.0
            ),
        }
