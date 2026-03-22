"""
Knowledge-Grounded Response Generation (#55)

Generate responses grounded in knowledge graph evidence:
- Template-based generation with evidence citation
- Response templates for different query types (factoid, explanation, comparison, temporal)
- Evidence integration with citation format
- Confidence-weighted response assembly
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GroundedResponse:
    """A response grounded in KG evidence with citations."""
    text: str
    citations: List[str]      # List of node_ids cited
    confidence: float          # Overall response confidence
    reasoning_path: List[str]  # Steps in reasoning chain

    def to_dict(self) -> dict:
        return {
            'text': self.text,
            'citations': self.citations,
            'confidence': round(self.confidence, 4),
            'reasoning_path': self.reasoning_path,
        }


# Response templates by query type
_FACTOID_TEMPLATES: List[str] = [
    "Based on the knowledge graph, {fact} [source: {citation}].",
    "The current data shows {fact} [source: {citation}].",
    "{fact} according to on-chain data [source: {citation}].",
]

_EXPLANATION_TEMPLATES: List[str] = [
    "{intro} {evidence_chain} This is because {reason} [sources: {citations}].",
    "Here's how it works: {evidence_chain} The key mechanism is {reason} [sources: {citations}].",
    "Let me explain. {evidence_chain} In summary, {reason} [sources: {citations}].",
]

_COMPARISON_TEMPLATES: List[str] = [
    "Comparing {item_a} and {item_b}: {comparison_body} [sources: {citations}].",
    "{item_a} differs from {item_b} in that {comparison_body} [sources: {citations}].",
]

_TEMPORAL_TEMPLATES: List[str] = [
    "At block {block_ref}, {fact}. Since then, {change} [sources: {citations}].",
    "The data from block {block_ref} shows {fact}. The current state is {current} [sources: {citations}].",
    "Over the period from block {start_block} to {end_block}, {trend} [sources: {citations}].",
]

_FALLBACK_TEMPLATE: str = (
    "Based on available evidence: {combined_facts}. "
    "[{num_sources} source(s) consulted]"
)


class GroundedGenerator:
    """Generate knowledge-grounded responses with citations."""

    def __init__(self, min_confidence: float = 0.1) -> None:
        self._min_confidence = min_confidence

        # Stats
        self._generations: int = 0
        self._citations_used: int = 0
        self._avg_confidence: float = 0.0
        self._last_generation: float = 0.0
        self._query_type_counts: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, query: str,
                 evidence_nodes: List[dict],
                 context: str = '') -> GroundedResponse:
        """Generate a grounded response from query and evidence.

        Args:
            query: The user's query.
            evidence_nodes: List of KG node dicts. Each should have:
                - 'node_id' or 'id' (str/int)
                - 'content' (dict or str)
                - 'confidence' (float, optional)
                - 'source_block' (int, optional)
                - 'node_type' (str, optional)
                - 'domain' (str, optional)
            context: Additional context string (e.g., conversation history).

        Returns:
            GroundedResponse with text, citations, confidence, and reasoning path.
        """
        self._generations += 1
        self._last_generation = time.time()

        if not evidence_nodes:
            return GroundedResponse(
                text="I don't have enough evidence to answer that question accurately.",
                citations=[],
                confidence=0.0,
                reasoning_path=['no_evidence'],
            )

        # Filter by minimum confidence
        valid_nodes = [
            n for n in evidence_nodes
            if n.get('confidence', 0.5) >= self._min_confidence
        ]
        if not valid_nodes:
            valid_nodes = evidence_nodes[:3]  # Fall back to top-3

        # Sort by confidence descending
        valid_nodes.sort(key=lambda n: n.get('confidence', 0.5), reverse=True)

        # Determine query type
        query_type = self._classify_query(query)
        self._query_type_counts[query_type] = (
            self._query_type_counts.get(query_type, 0) + 1
        )

        # Extract facts and citations
        facts, citations = self._extract_facts(valid_nodes)
        self._citations_used += len(citations)

        # Build reasoning path
        reasoning_path = self._build_reasoning_path(query_type, valid_nodes)

        # Generate response based on query type
        if query_type == 'factoid':
            text = self._generate_factoid(query, facts, citations)
        elif query_type == 'explanation':
            text = self._generate_explanation(query, facts, citations, context)
        elif query_type == 'comparison':
            text = self._generate_comparison(query, facts, citations)
        elif query_type == 'temporal':
            text = self._generate_temporal(query, facts, citations, valid_nodes)
        else:
            text = self._generate_fallback(facts, citations)

        # Compute overall confidence
        if valid_nodes:
            confidences = [n.get('confidence', 0.5) for n in valid_nodes[:5]]
            avg_conf = sum(confidences) / len(confidences)
        else:
            avg_conf = 0.0

        # Update running average
        total = self._generations
        self._avg_confidence = (
            (self._avg_confidence * (total - 1) + avg_conf) / total
        )

        return GroundedResponse(
            text=text,
            citations=[str(c) for c in citations],
            confidence=avg_conf,
            reasoning_path=reasoning_path,
        )

    def get_stats(self) -> dict:
        """Return runtime statistics."""
        return {
            'generations': self._generations,
            'citations_used': self._citations_used,
            'avg_confidence': round(self._avg_confidence, 4),
            'query_type_counts': dict(self._query_type_counts),
            'last_generation': self._last_generation,
        }

    # ------------------------------------------------------------------
    # Query classification
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_query(query: str) -> str:
        """Classify query into type: factoid, explanation, comparison, temporal."""
        q = query.lower().strip()

        # Temporal patterns
        temporal_words = [
            'when', 'since', 'before', 'after', 'during', 'over time',
            'history', 'trend', 'changed', 'evolved', 'growth',
            'block ago', 'blocks ago', 'last hour', 'last day',
        ]
        if any(w in q for w in temporal_words):
            return 'temporal'

        # Comparison patterns
        comparison_words = [
            'compare', 'vs', 'versus', 'difference', 'different',
            'similar', 'better', 'worse', 'more than', 'less than',
        ]
        if any(w in q for w in comparison_words):
            return 'comparison'

        # Explanation patterns
        explanation_words = [
            'why', 'how does', 'how do', 'explain', 'how is',
            'mechanism', 'process', 'works', 'because',
        ]
        if any(w in q for w in explanation_words):
            return 'explanation'

        # Default: factoid
        return 'factoid'

    # ------------------------------------------------------------------
    # Fact extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_facts(nodes: List[dict]) -> tuple:
        """Extract fact strings and citation IDs from evidence nodes.

        Returns:
            Tuple of (facts_list, citations_list).
        """
        facts: List[str] = []
        citations: List[str] = []

        for node in nodes[:10]:  # Cap at 10 nodes
            node_id = str(node.get('node_id', node.get('id', 'unknown')))
            citations.append(node_id)

            content = node.get('content', {})
            if isinstance(content, str):
                facts.append(content)
                continue

            if not isinstance(content, dict):
                continue

            # Build fact string from content fields
            parts: List[str] = []
            content_type = content.get('type', '')

            if content_type == 'block_observation':
                height = content.get('height', '?')
                diff = content.get('difficulty', '?')
                tx = content.get('tx_count', '?')
                parts.append(f"block {height} has difficulty {diff} and {tx} transactions")
            elif content_type == 'quantum_observation':
                energy = content.get('energy', '?')
                parts.append(f"quantum energy level is {energy}")
            elif content_type == 'contract_activity':
                tx_type = content.get('tx_type', 'activity')
                parts.append(f"contract {tx_type} detected")
            else:
                # Generic: extract string values
                for key, val in content.items():
                    if key == 'type':
                        continue
                    if isinstance(val, (str, int, float)):
                        parts.append(f"{key.replace('_', ' ')}: {val}")

            if parts:
                facts.append("; ".join(parts[:5]))  # Cap per node

        return facts, citations

    # ------------------------------------------------------------------
    # Response generators
    # ------------------------------------------------------------------

    def _generate_factoid(self, query: str, facts: List[str],
                          citations: List[str]) -> str:
        """Generate a factoid response."""
        if not facts:
            return _FALLBACK_TEMPLATE.format(
                combined_facts="no specific data available",
                num_sources=0,
            )

        # Use first (highest confidence) fact
        template = _FACTOID_TEMPLATES[self._generations % len(_FACTOID_TEMPLATES)]
        citation_str = citations[0] if citations else 'N/A'

        return template.format(
            fact=facts[0],
            citation=citation_str,
        )

    def _generate_explanation(self, query: str, facts: List[str],
                              citations: List[str],
                              context: str) -> str:
        """Generate an explanation response."""
        if not facts:
            return _FALLBACK_TEMPLATE.format(
                combined_facts="insufficient data for explanation",
                num_sources=0,
            )

        template = _EXPLANATION_TEMPLATES[
            self._generations % len(_EXPLANATION_TEMPLATES)
        ]
        citation_str = ", ".join(citations[:3])

        # Build evidence chain from multiple facts
        evidence_parts = facts[:3]
        evidence_chain = ". ".join(evidence_parts)

        # Extract a reason from the last fact or context
        reason = facts[-1] if len(facts) > 1 else facts[0]

        intro = ""
        q_lower = query.lower()
        if 'how' in q_lower:
            intro = "Here's how this works."
        elif 'why' in q_lower:
            intro = "The reason is as follows."
        else:
            intro = "Let me explain."

        return template.format(
            intro=intro,
            evidence_chain=evidence_chain,
            reason=reason,
            citations=citation_str,
        )

    def _generate_comparison(self, query: str, facts: List[str],
                             citations: List[str]) -> str:
        """Generate a comparison response."""
        if len(facts) < 2:
            return _FALLBACK_TEMPLATE.format(
                combined_facts=". ".join(facts) if facts else "insufficient data",
                num_sources=len(citations),
            )

        template = _COMPARISON_TEMPLATES[
            self._generations % len(_COMPARISON_TEMPLATES)
        ]
        citation_str = ", ".join(citations[:3])

        return template.format(
            item_a=facts[0].split(";")[0] if ";" in facts[0] else facts[0][:50],
            item_b=facts[1].split(";")[0] if ";" in facts[1] else facts[1][:50],
            comparison_body=f"{facts[0]}; while {facts[1]}",
            citations=citation_str,
        )

    def _generate_temporal(self, query: str, facts: List[str],
                           citations: List[str],
                           nodes: List[dict]) -> str:
        """Generate a temporal response."""
        if not facts:
            return _FALLBACK_TEMPLATE.format(
                combined_facts="no temporal data available",
                num_sources=0,
            )

        template = _TEMPORAL_TEMPLATES[
            self._generations % len(_TEMPORAL_TEMPLATES)
        ]
        citation_str = ", ".join(citations[:3])

        # Extract block references from nodes
        blocks = [
            n.get('source_block', n.get('content', {}).get('height', 0))
            for n in nodes if isinstance(n.get('content'), dict)
        ]
        blocks = [b for b in blocks if b]

        if len(blocks) >= 2:
            return template.format(
                block_ref=blocks[0],
                start_block=min(blocks),
                end_block=max(blocks),
                fact=facts[0],
                change=facts[-1] if len(facts) > 1 else "the trend continues",
                current=facts[-1] if len(facts) > 1 else facts[0],
                trend=". ".join(facts[:3]),
                citations=citation_str,
            )
        elif blocks:
            return _TEMPORAL_TEMPLATES[0].format(
                block_ref=blocks[0],
                fact=facts[0],
                change=facts[-1] if len(facts) > 1 else "the state is stable",
                citations=citation_str,
            )
        else:
            return _FALLBACK_TEMPLATE.format(
                combined_facts=". ".join(facts[:3]),
                num_sources=len(citations),
            )

    @staticmethod
    def _generate_fallback(facts: List[str], citations: List[str]) -> str:
        """Generate a fallback response when no specific template fits."""
        combined = ". ".join(facts[:5]) if facts else "no specific data available"
        return _FALLBACK_TEMPLATE.format(
            combined_facts=combined,
            num_sources=len(citations),
        )

    # ------------------------------------------------------------------
    # Reasoning path
    # ------------------------------------------------------------------

    @staticmethod
    def _build_reasoning_path(query_type: str,
                              nodes: List[dict]) -> List[str]:
        """Build a reasoning path explaining how the response was constructed."""
        path: List[str] = [f"query_type={query_type}"]

        if nodes:
            path.append(f"evidence_nodes={len(nodes)}")
            confidences = [n.get('confidence', 0.5) for n in nodes[:5]]
            path.append(f"avg_confidence={sum(confidences) / len(confidences):.3f}")

            domains = set()
            for n in nodes[:5]:
                d = n.get('domain', '')
                if d:
                    domains.add(d)
            if domains:
                path.append(f"domains={','.join(sorted(domains))}")

            types = set()
            for n in nodes[:5]:
                t = n.get('node_type', '')
                if t:
                    types.add(t)
            if types:
                path.append(f"node_types={','.join(sorted(types))}")

        path.append("response_generated")
        return path
