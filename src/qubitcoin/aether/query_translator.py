"""
Natural Language → Knowledge Graph Query Translator

Translates natural language user queries into structured knowledge graph
operations and reasoning chains. Enables the Aether chat to answer questions
by querying the knowledge graph intelligently.

Query pipeline:
  1. Extract keywords and intent from natural language
  2. Map keywords to knowledge graph nodes via content/type matching
  3. Select appropriate reasoning strategy (deductive, inductive, abductive, CoT)
  4. Execute reasoning over matched nodes
  5. Return structured results with reasoning trace
"""
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


# Intent categories for query classification
INTENT_FACTUAL = 'factual'        # "What is X?"
INTENT_CAUSAL = 'causal'          # "Why does X?"
INTENT_TEMPORAL = 'temporal'      # "When did X?"
INTENT_RELATIONAL = 'relational'  # "How is X related to Y?"
INTENT_EXPLORATORY = 'exploratory'  # "Tell me about X"
INTENT_ANALYTICAL = 'analytical'  # "What patterns exist in X?"

# Keywords that signal query intent
_CAUSAL_SIGNALS = {'why', 'because', 'cause', 'reason', 'due', 'result', 'effect', 'leads'}
_TEMPORAL_SIGNALS = {'when', 'before', 'after', 'during', 'since', 'until', 'time', 'block', 'recent'}
_RELATIONAL_SIGNALS = {'how', 'related', 'between', 'connection', 'link', 'relationship', 'compare'}
_ANALYTICAL_SIGNALS = {'pattern', 'trend', 'analyze', 'statistics', 'average', 'distribution'}
_FACTUAL_SIGNALS = {'what', 'which', 'who', 'where', 'define', 'explain'}

# Stop words to filter from keyword extraction
_STOP_WORDS = {
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'shall', 'can', 'to', 'of', 'in', 'for',
    'on', 'with', 'at', 'by', 'from', 'as', 'into', 'about', 'up',
    'out', 'if', 'or', 'and', 'but', 'not', 'no', 'so', 'than', 'too',
    'very', 'just', 'that', 'this', 'it', 'its', 'my', 'me', 'i',
    'you', 'your', 'we', 'they', 'them', 'he', 'she', 'tell',
}


@dataclass
class QueryIntent:
    """Parsed intent from a natural language query."""
    intent_type: str
    keywords: List[str]
    raw_query: str
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            'intent_type': self.intent_type,
            'keywords': self.keywords,
            'confidence': self.confidence,
        }


@dataclass
class QueryResult:
    """Result of translating and executing a NL query against the KG."""
    intent: QueryIntent
    matched_node_ids: List[int]
    reasoning_results: List[dict] = field(default_factory=list)
    answer_nodes: List[dict] = field(default_factory=list)
    success: bool = False
    explanation: str = ''

    def to_dict(self) -> dict:
        return {
            'intent': self.intent.to_dict(),
            'matched_nodes': self.matched_node_ids,
            'reasoning_results': self.reasoning_results,
            'answer_nodes': self.answer_nodes,
            'success': self.success,
            'explanation': self.explanation,
        }


class QueryTranslator:
    """Translate natural language queries to knowledge graph operations."""

    def __init__(self, knowledge_graph, reasoning_engine) -> None:
        """
        Args:
            knowledge_graph: KnowledgeGraph instance.
            reasoning_engine: ReasoningEngine instance.
        """
        self.kg = knowledge_graph
        self.reasoning = reasoning_engine

    def translate_and_execute(self, query: str, max_results: int = 10,
                              reasoning_depth: int = 3) -> QueryResult:
        """Translate a natural language query and execute it against the KG.

        Args:
            query: Natural language query string.
            max_results: Maximum number of result nodes.
            reasoning_depth: Depth for chain-of-thought reasoning.

        Returns:
            QueryResult with matched nodes, reasoning, and answer.
        """
        # Step 1: Parse intent and extract keywords
        intent = self.classify_intent(query)

        # Step 2: Find matching nodes in the knowledge graph
        matched_ids = self._find_matching_nodes(intent.keywords, max_results)

        if not matched_ids:
            return QueryResult(
                intent=intent,
                matched_node_ids=[],
                success=False,
                explanation="No matching knowledge nodes found for query keywords.",
            )

        # Step 3: Apply reasoning strategy based on intent
        reasoning_results = self._apply_reasoning(
            intent, matched_ids, reasoning_depth
        )

        # Step 4: Collect answer nodes
        answer_nodes = self._collect_answers(matched_ids, reasoning_results)

        return QueryResult(
            intent=intent,
            matched_node_ids=matched_ids,
            reasoning_results=reasoning_results,
            answer_nodes=answer_nodes,
            success=True,
            explanation=self._generate_explanation(intent, answer_nodes),
        )

    def classify_intent(self, query: str) -> QueryIntent:
        """Classify the intent of a natural language query.

        Args:
            query: Raw query string.

        Returns:
            QueryIntent with type, keywords, and confidence.
        """
        query_lower = query.lower().strip()
        words = set(re.findall(r'\b[a-z]+\b', query_lower))

        # Classify by signal word overlap
        scores: Dict[str, int] = {
            INTENT_CAUSAL: len(words & _CAUSAL_SIGNALS),
            INTENT_TEMPORAL: len(words & _TEMPORAL_SIGNALS),
            INTENT_RELATIONAL: len(words & _RELATIONAL_SIGNALS),
            INTENT_ANALYTICAL: len(words & _ANALYTICAL_SIGNALS),
            INTENT_FACTUAL: len(words & _FACTUAL_SIGNALS),
        }

        best_intent = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_intent]

        # Default to exploratory if no strong signal
        if best_score == 0:
            best_intent = INTENT_EXPLORATORY

        # Extract keywords (non-stop words, length > 2)
        keywords = [
            w for w in re.findall(r'\b[a-z0-9]+\b', query_lower)
            if w not in _STOP_WORDS and len(w) > 2
        ]

        # Confidence based on keyword count and signal strength
        total_signals = sum(scores.values())
        confidence = min(0.9, 0.3 + (best_score * 0.2) + (len(keywords) * 0.05))

        return QueryIntent(
            intent_type=best_intent,
            keywords=keywords,
            raw_query=query,
            confidence=confidence,
        )

    def _find_matching_nodes(self, keywords: List[str],
                              max_results: int) -> List[int]:
        """Find knowledge graph nodes matching the query keywords.

        Uses a scoring system: each keyword match in node content increases
        the score. Higher-confidence nodes are preferred.
        """
        if not self.kg or not self.kg.nodes:
            return []

        scored: List[Tuple[int, float]] = []

        for node_id, node in self.kg.nodes.items():
            content_str = json.dumps(node.content).lower()
            node_type_str = node.node_type.lower()

            # Score by keyword matches
            matches = sum(1 for kw in keywords if kw in content_str or kw in node_type_str)
            if matches == 0:
                continue

            # Weight by confidence and match density
            score = matches * node.confidence
            scored.append((node_id, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored[:max_results]]

    def _apply_reasoning(self, intent: QueryIntent, node_ids: List[int],
                          depth: int) -> List[dict]:
        """Apply the appropriate reasoning strategy based on intent type."""
        results: List[dict] = []

        if not self.reasoning:
            return results

        try:
            if intent.intent_type == INTENT_CAUSAL:
                # Causal queries → abductive reasoning (infer causes)
                for nid in node_ids[:3]:
                    result = self.reasoning.abduce(nid)
                    if result.success:
                        results.append(result.to_dict())

            elif intent.intent_type == INTENT_RELATIONAL:
                # Relational queries → deductive reasoning over connected nodes
                if len(node_ids) >= 2:
                    result = self.reasoning.deduce(node_ids[:5])
                    if result.success:
                        results.append(result.to_dict())

            elif intent.intent_type == INTENT_ANALYTICAL:
                # Analytical queries → inductive reasoning (patterns)
                if len(node_ids) >= 2:
                    result = self.reasoning.induce(node_ids[:5])
                    if result.success:
                        results.append(result.to_dict())

            elif intent.intent_type in (INTENT_FACTUAL, INTENT_EXPLORATORY, INTENT_TEMPORAL):
                # General queries → chain-of-thought over matched nodes
                result = self.reasoning.chain_of_thought(node_ids[:5], max_depth=depth)
                if result.success:
                    results.append(result.to_dict())

        except Exception as e:
            logger.debug(f"Reasoning failed for intent {intent.intent_type}: {e}")

        return results

    def _collect_answers(self, matched_ids: List[int],
                          reasoning_results: List[dict]) -> List[dict]:
        """Collect answer nodes from matches and reasoning conclusions."""
        answer_ids: List[int] = list(matched_ids[:5])

        # Add conclusion nodes from reasoning
        for result in reasoning_results:
            cid = result.get('conclusion_node_id')
            if cid and cid not in answer_ids:
                answer_ids.append(cid)

        # Convert to dicts
        answers = []
        for nid in answer_ids:
            node = self.kg.get_node(nid)
            if node:
                answers.append(node.to_dict())

        return answers

    def _generate_explanation(self, intent: QueryIntent,
                               answer_nodes: List[dict]) -> str:
        """Generate a human-readable explanation of the query result."""
        if not answer_nodes:
            return f"No knowledge found for: {intent.raw_query}"

        node_types = {}
        for node in answer_nodes:
            t = node.get('node_type', 'unknown')
            node_types[t] = node_types.get(t, 0) + 1

        type_summary = ", ".join(f"{v} {k}" for k, v in node_types.items())

        return (
            f"Found {len(answer_nodes)} relevant nodes ({type_summary}) "
            f"for {intent.intent_type} query with {len(intent.keywords)} keywords."
        )
