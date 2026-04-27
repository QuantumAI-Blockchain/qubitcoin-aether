"""Unit tests for Aether Tree knowledge extraction pipeline."""
import pytest
import time
from types import SimpleNamespace
from unittest.mock import MagicMock


def _make_mock_kg():
    """Create a mock knowledge graph for testing."""
    _next_id = [1]
    _nodes = {}

    def add_node(node_type, content, confidence, source_block):
        nid = _next_id[0]
        _next_id[0] += 1
        node = SimpleNamespace(
            node_id=nid,
            node_type=node_type,
            content=content,
            confidence=confidence,
            source_block=source_block,
        )
        _nodes[nid] = node
        return node

    kg = MagicMock()
    kg.add_node = MagicMock(side_effect=add_node)
    kg.add_edge = MagicMock()
    kg.nodes = _nodes
    return kg


def _make_block(height, difficulty=1.0, tx_count=0, timestamp=None,
                proof_data=None, tx_type='transfer'):
    """Create a mock block for testing."""
    txs = []
    for i in range(tx_count):
        tx = SimpleNamespace(
            tx_type=tx_type if i == 0 and tx_type != 'transfer' else 'transfer',
            fee=0.001,
        )
        txs.append(tx)

    return SimpleNamespace(
        height=height,
        difficulty=difficulty,
        timestamp=timestamp or time.time(),
        transactions=txs,
        proof_data=proof_data,
        thought_proof=None,
    )


class TestKnowledgeExtractor:
    """Test knowledge extraction from blocks."""

    def test_init(self):
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor
        kg = _make_mock_kg()
        ke = KnowledgeExtractor(kg)
        assert ke._blocks_processed == 0

    def test_extract_empty_block(self):
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor
        kg = _make_mock_kg()
        ke = KnowledgeExtractor(kg)
        nodes = ke.extract_from_block(_make_block(0), 0)
        assert nodes >= 1  # At least block metadata node

    def test_extract_block_metadata(self):
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor
        kg = _make_mock_kg()
        ke = KnowledgeExtractor(kg)
        # Use milestone block (every 1000) to pass observation filter
        block = _make_block(1000, difficulty=0.5)
        ke.extract_from_block(block, 1000)

        # Verify add_node was called with block_observation
        calls = kg.add_node.call_args_list
        assert len(calls) >= 1
        first_call = calls[0]
        assert first_call.kwargs['node_type'] == 'observation'
        assert first_call.kwargs['content']['type'] == 'block_observation'
        assert first_call.kwargs['content']['height'] == 1000

    def test_extract_transaction_patterns(self):
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor
        kg = _make_mock_kg()
        ke = KnowledgeExtractor(kg)
        block = _make_block(1, tx_count=5)
        nodes = ke.extract_from_block(block, 1)
        assert nodes >= 2  # block metadata + tx pattern

    def test_extract_mining_data(self):
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor
        kg = _make_mock_kg()
        ke = KnowledgeExtractor(kg)
        # Use milestone block to pass observation filter
        block = _make_block(1000, proof_data={'energy': -2.5, 'n_qubits': 4})
        nodes = ke.extract_from_block(block, 1000)
        assert nodes >= 2  # block metadata + quantum observation

    def test_extract_contract_activity(self):
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor
        kg = _make_mock_kg()
        ke = KnowledgeExtractor(kg)
        # Create block with many contract txs to trigger inference
        txs = [SimpleNamespace(tx_type='contract_deploy', fee=0.01) for _ in range(5)]
        block = SimpleNamespace(
            height=1, difficulty=1.0, timestamp=time.time(),
            transactions=txs, proof_data=None, thought_proof=None,
        )
        nodes = ke.extract_from_block(block, 1)
        # Should create block obs + tx pattern + high_contract_activity inference
        assert nodes >= 3

    def test_sliding_window_tracking(self):
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor
        kg = _make_mock_kg()
        ke = KnowledgeExtractor(kg)

        for i in range(5):
            block = _make_block(i, difficulty=0.1 * (i + 1))
            ke.extract_from_block(block, i)

        assert len(ke._difficulties) == 5
        assert ke._blocks_processed == 5

    def test_temporal_pattern_detection(self):
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor
        kg = _make_mock_kg()
        ke = KnowledgeExtractor(kg)

        # Simulate 10 blocks with fast block times (well below 3.3s target)
        base_time = time.time()
        for i in range(11):
            block = _make_block(i, timestamp=base_time + i * 1.0)
            ke.extract_from_block(block, i)

        # Block 10 should trigger temporal pattern detection (every 10 blocks)
        # With 1.0s intervals, drift > 20% from 3.3s target
        # Check that an inference node was created
        inference_calls = [
            c for c in kg.add_node.call_args_list
            if c.kwargs.get('node_type') == 'inference'
        ]
        assert len(inference_calls) >= 1

    def test_difficulty_trend_analysis(self):
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor
        kg = _make_mock_kg()
        ke = KnowledgeExtractor(kg)

        # Simulate blocks with rising difficulty
        base_time = time.time()
        for i in range(145):
            difficulty = 1.0 + 0.1 * i  # Rising difficulty
            block = _make_block(i, difficulty=difficulty, timestamp=base_time + i * 3.3)
            ke.extract_from_block(block, i)

        # Block 144 triggers difficulty trend analysis
        inference_calls = [
            c for c in kg.add_node.call_args_list
            if c.kwargs.get('node_type') == 'inference'
            and c.kwargs.get('content', {}).get('type') == 'difficulty_trend'
        ]
        assert len(inference_calls) >= 1
        trend_content = inference_calls[0].kwargs['content']
        assert trend_content['trend'] == 'rising'

    def test_no_kg_returns_zero(self):
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor
        ke = KnowledgeExtractor(None)
        nodes = ke.extract_from_block(_make_block(0), 0)
        assert nodes == 0

    def test_get_stats(self):
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor
        kg = _make_mock_kg()
        ke = KnowledgeExtractor(kg)
        ke.extract_from_block(_make_block(0, difficulty=1.0), 0)
        ke.extract_from_block(_make_block(1, difficulty=2.0), 1)

        stats = ke.get_stats()
        assert stats['blocks_processed'] == 2
        assert stats['difficulty_samples'] == 2
        assert stats['avg_difficulty'] == 1.5

    def test_window_size_limit(self):
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor
        kg = _make_mock_kg()
        ke = KnowledgeExtractor(kg)
        ke._window_size = 10  # Small window for testing

        base_time = time.time()
        for i in range(15):
            block = _make_block(i, difficulty=float(i), timestamp=base_time + i * 3.3)
            ke.extract_from_block(block, i)

        assert len(ke._difficulties) <= 10
        assert len(ke._tx_counts) <= 10

    def test_link_to_previous_block(self):
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor
        kg = _make_mock_kg()
        ke = KnowledgeExtractor(kg)

        # Use genesis (block 0) and milestone (block 1000) to pass observation filter
        ke.extract_from_block(_make_block(0), 0)
        ke.extract_from_block(_make_block(1000), 1000)

        # add_edge should be called to link block 1000 → block 0
        edge_calls = kg.add_edge.call_args_list
        derives_calls = [c for c in edge_calls if 'derives' in str(c)]
        assert len(derives_calls) >= 1
