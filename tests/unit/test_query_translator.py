"""Unit tests for NL → Knowledge Graph query translator.

Tests:
  - Intent classification (factual, causal, relational, etc.)
  - Keyword extraction (stop word filtering)
  - Node matching against knowledge graph
  - Reasoning strategy selection per intent
  - Full translate_and_execute pipeline
  - Integration with AetherChat
  - Admin API rate limiting
"""
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from qubitcoin.aether.query_translator import (
    QueryTranslator, QueryIntent, QueryResult,
    INTENT_FACTUAL, INTENT_CAUSAL, INTENT_TEMPORAL,
    INTENT_RELATIONAL, INTENT_EXPLORATORY, INTENT_ANALYTICAL,
)


# ---------------------------------------------------------------------------
# Helpers: fake knowledge graph and reasoning engine
# ---------------------------------------------------------------------------

@dataclass
class FakeKeterNode:
    node_id: int = 0
    node_type: str = 'assertion'
    content_hash: str = ''
    content: dict = field(default_factory=dict)
    confidence: float = 0.5
    source_block: int = 0
    timestamp: float = 0.0
    edges_out: List[int] = field(default_factory=list)
    edges_in: List[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'node_id': self.node_id,
            'node_type': self.node_type,
            'content': self.content,
            'confidence': self.confidence,
            'source_block': self.source_block,
        }


class FakeKG:
    """Minimal knowledge graph for testing."""
    def __init__(self):
        self.nodes: Dict[int, FakeKeterNode] = {}

    def add(self, node_id: int, content: dict, node_type: str = 'assertion',
            confidence: float = 0.8) -> None:
        self.nodes[node_id] = FakeKeterNode(
            node_id=node_id, content=content, node_type=node_type,
            confidence=confidence,
        )

    def get_node(self, node_id: int):
        return self.nodes.get(node_id)


class FakeReasoningResult:
    def __init__(self, success: bool = True, conclusion_id: Optional[int] = None):
        self.success = success
        self.operation_type = 'test'
        self.premise_ids = []
        self.conclusion_node_id = conclusion_id
        self.confidence = 0.8
        self.chain = []
        self.explanation = 'test reasoning'

    def to_dict(self):
        return {
            'operation_type': self.operation_type,
            'premise_ids': self.premise_ids,
            'conclusion_node_id': self.conclusion_node_id,
            'confidence': self.confidence,
            'chain': [],
            'success': self.success,
            'explanation': self.explanation,
        }


class FakeReasoning:
    """Minimal reasoning engine for testing."""
    def deduce(self, premise_ids):
        return FakeReasoningResult(success=True, conclusion_id=999)

    def induce(self, observation_ids):
        return FakeReasoningResult(success=True, conclusion_id=998)

    def abduce(self, observation_id, rule_node_ids=None):
        return FakeReasoningResult(success=True, conclusion_id=997)

    def chain_of_thought(self, query_node_ids, max_depth=5):
        return FakeReasoningResult(success=True, conclusion_id=996)


def _make_populated_kg() -> FakeKG:
    """Create a knowledge graph with test data."""
    kg = FakeKG()
    kg.add(1, {'type': 'block', 'hash': 'abc123', 'height': 100}, 'observation', 0.9)
    kg.add(2, {'type': 'mining', 'energy': -0.5, 'miner': 'qbc1test'}, 'observation', 0.85)
    kg.add(3, {'type': 'difficulty', 'trend': 'increasing'}, 'inference', 0.7)
    kg.add(4, {'type': 'transaction', 'count': 50, 'fee': 0.001}, 'assertion', 0.8)
    kg.add(5, {'type': 'quantum', 'qubits': 4, 'algorithm': 'VQE'}, 'axiom', 0.95)
    return kg


# ---------------------------------------------------------------------------
# Intent classification tests
# ---------------------------------------------------------------------------

class TestIntentClassification:
    """Test NL query intent classification."""

    def _translator(self):
        return QueryTranslator(FakeKG(), FakeReasoning())

    def test_factual_what(self):
        qt = self._translator()
        intent = qt.classify_intent("What is the total supply?")
        assert intent.intent_type == INTENT_FACTUAL

    def test_causal_why(self):
        qt = self._translator()
        intent = qt.classify_intent("Why is the difficulty increasing?")
        assert intent.intent_type == INTENT_CAUSAL

    def test_temporal_when(self):
        qt = self._translator()
        intent = qt.classify_intent("When was the last block mined?")
        assert intent.intent_type == INTENT_TEMPORAL

    def test_relational_how(self):
        qt = self._translator()
        intent = qt.classify_intent("How are mining and difficulty related?")
        assert intent.intent_type == INTENT_RELATIONAL

    def test_analytical_pattern(self):
        qt = self._translator()
        intent = qt.classify_intent("Analyze the patterns in transaction fees")
        assert intent.intent_type == INTENT_ANALYTICAL

    def test_exploratory_default(self):
        qt = self._translator()
        intent = qt.classify_intent("blockchain quantum computing")
        assert intent.intent_type == INTENT_EXPLORATORY

    def test_keyword_extraction(self):
        qt = self._translator()
        intent = qt.classify_intent("What is the current mining difficulty?")
        # Should exclude stop words like 'what', 'is', 'the'
        assert 'current' in intent.keywords
        assert 'mining' in intent.keywords
        assert 'difficulty' in intent.keywords
        assert 'the' not in intent.keywords
        assert 'is' not in intent.keywords

    def test_short_words_excluded(self):
        qt = self._translator()
        intent = qt.classify_intent("Is QBC a good coin?")
        # 'qbc' is 3 chars so included, 'is' and 'a' are stop words
        assert 'qbc' in intent.keywords
        assert 'is' not in intent.keywords
        assert 'a' not in intent.keywords

    def test_confidence_increases_with_signals(self):
        qt = self._translator()
        weak = qt.classify_intent("hello")
        strong = qt.classify_intent("Why does the mining cause difficulty to change?")
        assert strong.confidence > weak.confidence


# ---------------------------------------------------------------------------
# Node matching tests
# ---------------------------------------------------------------------------

class TestNodeMatching:
    """Test keyword → KG node matching."""

    def test_match_by_content(self):
        kg = _make_populated_kg()
        qt = QueryTranslator(kg, FakeReasoning())
        ids = qt._find_matching_nodes(['mining', 'energy'], max_results=5)
        assert 2 in ids  # mining node

    def test_match_multiple_keywords(self):
        kg = _make_populated_kg()
        qt = QueryTranslator(kg, FakeReasoning())
        ids = qt._find_matching_nodes(['block', 'hash'], max_results=5)
        assert 1 in ids  # block node with hash

    def test_no_match_returns_empty(self):
        kg = _make_populated_kg()
        qt = QueryTranslator(kg, FakeReasoning())
        ids = qt._find_matching_nodes(['nonexistent_keyword_xyz'], max_results=5)
        assert ids == []

    def test_empty_kg(self):
        kg = FakeKG()
        qt = QueryTranslator(kg, FakeReasoning())
        ids = qt._find_matching_nodes(['anything'], max_results=5)
        assert ids == []

    def test_results_limited(self):
        kg = _make_populated_kg()
        qt = QueryTranslator(kg, FakeReasoning())
        ids = qt._find_matching_nodes(['type'], max_results=3)
        assert len(ids) <= 3

    def test_higher_confidence_nodes_ranked_first(self):
        kg = FakeKG()
        kg.add(1, {'topic': 'mining'}, confidence=0.3)
        kg.add(2, {'topic': 'mining'}, confidence=0.9)
        qt = QueryTranslator(kg, FakeReasoning())
        ids = qt._find_matching_nodes(['mining'], max_results=5)
        assert ids[0] == 2  # higher confidence first


# ---------------------------------------------------------------------------
# Reasoning strategy tests
# ---------------------------------------------------------------------------

class TestReasoningStrategy:
    """Test that the correct reasoning strategy is applied per intent."""

    def test_causal_uses_abduction(self):
        kg = _make_populated_kg()
        reasoning = MagicMock()
        reasoning.abduce.return_value = FakeReasoningResult(success=True)
        qt = QueryTranslator(kg, reasoning)

        intent = QueryIntent(INTENT_CAUSAL, ['difficulty'], "why difficulty?")
        qt._apply_reasoning(intent, [3], depth=3)
        reasoning.abduce.assert_called()

    def test_relational_uses_deduction(self):
        kg = _make_populated_kg()
        reasoning = MagicMock()
        reasoning.deduce.return_value = FakeReasoningResult(success=True)
        qt = QueryTranslator(kg, reasoning)

        intent = QueryIntent(INTENT_RELATIONAL, ['mining', 'difficulty'], "how related?")
        qt._apply_reasoning(intent, [2, 3], depth=3)
        reasoning.deduce.assert_called()

    def test_analytical_uses_induction(self):
        kg = _make_populated_kg()
        reasoning = MagicMock()
        reasoning.induce.return_value = FakeReasoningResult(success=True)
        qt = QueryTranslator(kg, reasoning)

        intent = QueryIntent(INTENT_ANALYTICAL, ['pattern', 'fees'], "fee patterns?")
        qt._apply_reasoning(intent, [4, 5], depth=3)
        reasoning.induce.assert_called()

    def test_factual_uses_chain_of_thought(self):
        kg = _make_populated_kg()
        reasoning = MagicMock()
        reasoning.chain_of_thought.return_value = FakeReasoningResult(success=True)
        qt = QueryTranslator(kg, reasoning)

        intent = QueryIntent(INTENT_FACTUAL, ['block', 'height'], "what is block height?")
        qt._apply_reasoning(intent, [1], depth=3)
        reasoning.chain_of_thought.assert_called()

    def test_no_reasoning_engine(self):
        kg = _make_populated_kg()
        qt = QueryTranslator(kg, None)
        intent = QueryIntent(INTENT_FACTUAL, ['block'], "what?")
        results = qt._apply_reasoning(intent, [1], depth=3)
        assert results == []


# ---------------------------------------------------------------------------
# Full pipeline tests
# ---------------------------------------------------------------------------

class TestTranslateAndExecute:
    """Test the full NL→KG→Reasoning pipeline."""

    def test_full_pipeline_success(self):
        kg = _make_populated_kg()
        qt = QueryTranslator(kg, FakeReasoning())
        result = qt.translate_and_execute("What is the mining energy?")
        assert result.success
        assert len(result.matched_node_ids) > 0
        assert len(result.answer_nodes) > 0
        assert 'mining' in result.intent.keywords or 'energy' in result.intent.keywords

    def test_full_pipeline_no_matches(self):
        kg = _make_populated_kg()
        qt = QueryTranslator(kg, FakeReasoning())
        result = qt.translate_and_execute("xyzzy plugh foobar")
        assert not result.success
        assert len(result.matched_node_ids) == 0

    def test_explanation_generated(self):
        kg = _make_populated_kg()
        qt = QueryTranslator(kg, FakeReasoning())
        result = qt.translate_and_execute("Tell me about quantum VQE")
        assert result.success
        assert len(result.explanation) > 0

    def test_reasoning_depth_respected(self):
        kg = _make_populated_kg()
        reasoning = MagicMock()
        reasoning.chain_of_thought.return_value = FakeReasoningResult(success=True)
        qt = QueryTranslator(kg, reasoning)

        qt.translate_and_execute("What is block height?", reasoning_depth=7)
        call_args = reasoning.chain_of_thought.call_args
        assert call_args[1]['max_depth'] == 7 or call_args[0][1] == 7

    def test_query_result_serializable(self):
        kg = _make_populated_kg()
        qt = QueryTranslator(kg, FakeReasoning())
        result = qt.translate_and_execute("mining difficulty trend")
        d = result.to_dict()
        assert 'intent' in d
        assert 'matched_nodes' in d
        assert 'success' in d


# ---------------------------------------------------------------------------
# AetherChat integration tests
# ---------------------------------------------------------------------------

class TestChatQueryTranslatorIntegration:
    """Test that AetherChat uses the QueryTranslator when available."""

    def test_chat_initializes_translator(self):
        from qubitcoin.aether.chat import AetherChat
        engine = MagicMock()
        engine.kg = _make_populated_kg()
        engine.reasoning = FakeReasoning()
        engine.phi = None
        chat = AetherChat(engine, MagicMock())
        assert chat._query_translator is not None

    def test_chat_uses_translator_for_messages(self):
        from qubitcoin.aether.chat import AetherChat
        engine = MagicMock()
        engine.kg = _make_populated_kg()
        engine.reasoning = FakeReasoning()
        engine.phi = None
        chat = AetherChat(engine, MagicMock())
        session = chat.create_session()
        result = chat.process_message(session.session_id, "What is mining energy?")
        assert 'error' not in result
        assert 'response' in result
        # Response should mention the intent or matched nodes
        assert len(result['response']) > 0

    def test_chat_falls_back_without_translator(self):
        from qubitcoin.aether.chat import AetherChat
        engine = MagicMock()
        engine.kg = None
        engine.reasoning = None
        engine.phi = None
        chat = AetherChat(engine, MagicMock())
        assert chat._query_translator is None
        session = chat.create_session()
        result = chat.process_message(session.session_id, "hello world")
        assert 'error' not in result
        assert 'response' in result


# ---------------------------------------------------------------------------
# Admin rate limiting tests
# ---------------------------------------------------------------------------

class TestAdminRateLimiting:
    """Test rate limiting on admin API endpoints."""

    def test_rate_limit_function_exists(self):
        from qubitcoin.network.admin_api import _check_admin_rate_limit
        assert callable(_check_admin_rate_limit)

    def test_rate_limit_allows_normal_usage(self):
        from qubitcoin.network.admin_api import _check_admin_rate_limit, _admin_rate_limit
        # Reset state
        _admin_rate_limit['requests'].clear()

        request = MagicMock()
        request.client.host = '10.0.0.1'
        # Should not raise for first call
        _check_admin_rate_limit(request)

    def test_rate_limit_blocks_excess(self):
        from qubitcoin.network.admin_api import _check_admin_rate_limit, _admin_rate_limit
        import time

        # Reset state
        _admin_rate_limit['requests'].clear()

        request = MagicMock()
        request.client.host = '10.0.0.2'

        # Fill up to limit
        now = time.time()
        _admin_rate_limit['requests']['10.0.0.2'] = [now] * 30

        # Next call should raise 429
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _check_admin_rate_limit(request)
        assert exc_info.value.status_code == 429

    def test_rate_limit_separate_per_ip(self):
        from qubitcoin.network.admin_api import _check_admin_rate_limit, _admin_rate_limit
        import time

        _admin_rate_limit['requests'].clear()

        request_a = MagicMock()
        request_a.client.host = '10.0.0.3'
        request_b = MagicMock()
        request_b.client.host = '10.0.0.4'

        # Fill A to limit
        now = time.time()
        _admin_rate_limit['requests']['10.0.0.3'] = [now] * 30

        # B should still work
        _check_admin_rate_limit(request_b)  # should not raise

        # A should fail
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _check_admin_rate_limit(request_a)
