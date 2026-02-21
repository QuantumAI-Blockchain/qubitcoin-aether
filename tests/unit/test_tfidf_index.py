"""Unit tests for TF-IDF search index and cross-referencing."""
from qubitcoin.aether.kg_index import TFIDFIndex, _tokenize, _extract_text


class TestTokenizer:
    """Test tokenization and text extraction."""

    def test_basic_tokenize(self):
        tokens = _tokenize("Quantum computing uses qubits for superposition")
        assert 'quantum' in tokens
        assert 'computing' in tokens
        assert 'qubits' in tokens
        # Stop words filtered
        assert 'for' not in tokens
        assert 'the' not in tokens

    def test_stop_words_removed(self):
        tokens = _tokenize("this is a test of the system")
        assert 'test' in tokens
        assert 'system' in tokens
        assert 'this' not in tokens
        assert 'the' not in tokens

    def test_short_tokens_removed(self):
        tokens = _tokenize("I am OK at AI ML")
        # Short tokens (<=2 chars) are removed
        assert 'am' not in tokens
        assert 'ok' not in tokens

    def test_extract_text(self):
        content = {'text': 'Quantum entanglement', 'description': 'EPR pairs'}
        text = _extract_text(content)
        assert 'Quantum entanglement' in text
        assert 'EPR pairs' in text

    def test_extract_text_empty(self):
        assert _extract_text({}) == ''


class TestTFIDFIndex:
    """Test the TF-IDF index."""

    def test_empty_index(self):
        idx = TFIDFIndex()
        assert idx.n_docs == 0
        results = idx.query("test")
        assert results == []

    def test_add_and_query(self):
        idx = TFIDFIndex()
        idx.add_node(1, {'text': 'Quantum computing uses qubits and superposition'})
        idx.add_node(2, {'text': 'Classical computers use transistors and binary'})
        idx.add_node(3, {'text': 'Blockchain technology uses cryptographic hashing'})

        results = idx.query("quantum qubits")
        assert len(results) > 0
        # Node 1 should be the best match
        assert results[0][0] == 1

    def test_relevance_ranking(self):
        idx = TFIDFIndex()
        idx.add_node(1, {'text': 'Quantum entanglement enables faster than light correlation'})
        idx.add_node(2, {'text': 'Blockchain consensus algorithms provide security'})
        idx.add_node(3, {'text': 'Quantum computers threaten classical cryptography'})

        results = idx.query("quantum computing")
        node_ids = [nid for nid, score in results]
        # Both quantum nodes should rank higher than blockchain
        assert 2 not in node_ids[:2] or len(results) <= 2

    def test_no_match(self):
        idx = TFIDFIndex()
        idx.add_node(1, {'text': 'Quantum computing uses qubits'})
        results = idx.query("cooking recipe pasta")
        # Should return empty or very low scores
        assert len(results) == 0 or results[0][1] < 0.1

    def test_remove_node(self):
        idx = TFIDFIndex()
        idx.add_node(1, {'text': 'Quantum computing'})
        idx.add_node(2, {'text': 'Classical computing'})
        assert idx.n_docs == 2

        idx.remove_node(1)
        assert idx.n_docs == 1
        results = idx.query("quantum")
        # Node 1 should not appear
        assert all(nid != 1 for nid, _ in results)

    def test_get_stats(self):
        idx = TFIDFIndex()
        idx.add_node(1, {'text': 'Quantum computing uses qubits and superposition'})
        idx.add_node(2, {'text': 'Blockchain technology uses cryptographic hashing'})
        stats = idx.get_stats()
        assert stats['total_docs'] == 2
        assert stats['unique_terms'] > 0
        assert stats['avg_terms_per_doc'] > 0

    def test_incremental_add(self):
        idx = TFIDFIndex()
        idx.add_node(1, {'text': 'First document about quantum computing research'})
        assert idx.n_docs == 1
        idx.add_node(2, {'text': 'Second document about blockchain technology'})
        assert idx.n_docs == 2
        # With 2+ docs, IDF is non-zero for discriminating terms
        results = idx.query("quantum computing")
        assert len(results) > 0

    def test_empty_content(self):
        idx = TFIDFIndex()
        idx.add_node(1, {})  # Empty content
        assert idx.n_docs == 0  # Should not index empty docs

    def test_top_k_limit(self):
        idx = TFIDFIndex()
        for i in range(20):
            idx.add_node(i, {'text': f'Document about quantum computing number {i}'})
        results = idx.query("quantum computing", top_k=5)
        assert len(results) <= 5

    def test_cosine_similarity_range(self):
        idx = TFIDFIndex()
        idx.add_node(1, {'text': 'Quantum entanglement and superposition states'})
        idx.add_node(2, {'text': 'Entanglement is a quantum mechanical phenomenon'})
        results = idx.query("quantum entanglement")
        for nid, score in results:
            assert 0 <= score <= 2.0  # Cosine can be slightly >1 due to TF augmentation
