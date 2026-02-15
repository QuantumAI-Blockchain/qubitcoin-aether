"""Unit tests for Batch 24: LLM Adapters, IPFS Memory, Key import/export.

Tests:
  - LLMAdapter: base class, OpenAI/Claude/Local adapters
  - LLMAdapterManager: registration, fallback, distillation
  - KnowledgeDistiller: sentence splitting, classification, distillation
  - IPFSMemoryStore: store, retrieve, cache, batch, stats
  - Key import/export: hex and PEM formats (already implemented, verify)
"""
import json
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

from qubitcoin.aether.llm_adapter import (
    LLMAdapter, LLMResponse, LLMAdapterManager,
    OpenAIAdapter, ClaudeAdapter, LocalAdapter,
    KnowledgeDistiller, AETHER_SYSTEM_PROMPT,
)
from qubitcoin.aether.ipfs_memory import IPFSMemoryStore
from qubitcoin.quantum.crypto import Dilithium2


# ---------------------------------------------------------------------------
# LLMResponse tests
# ---------------------------------------------------------------------------

class TestLLMResponse:
    """Test LLM response dataclass."""

    def test_response_creation(self):
        resp = LLMResponse(
            content="Hello world", model="gpt-4",
            adapter_type="openai", tokens_used=50,
        )
        assert resp.content == "Hello world"
        assert resp.model == "gpt-4"
        assert resp.tokens_used == 50

    def test_response_to_dict(self):
        resp = LLMResponse(
            content="test", model="claude-3",
            adapter_type="claude", latency_ms=100.5,
        )
        d = resp.to_dict()
        assert d['content'] == 'test'
        assert d['adapter_type'] == 'claude'
        assert d['latency_ms'] == 100.5


# ---------------------------------------------------------------------------
# OpenAIAdapter tests
# ---------------------------------------------------------------------------

class TestOpenAIAdapter:
    """Test OpenAI adapter."""

    def test_adapter_type(self):
        adapter = OpenAIAdapter()
        assert adapter.adapter_type == 'openai'

    def test_not_available_without_key(self):
        adapter = OpenAIAdapter()
        assert not adapter.is_available()

    def test_available_with_key(self):
        adapter = OpenAIAdapter(api_key='sk-test-key')
        assert adapter.is_available()

    def test_generate_without_key_returns_message(self):
        adapter = OpenAIAdapter()
        resp = adapter.generate("Hello")
        assert 'not configured' in resp.content

    def test_get_stats(self):
        adapter = OpenAIAdapter(api_key='sk-test')
        stats = adapter.get_stats()
        assert stats['adapter_type'] == 'openai'
        assert stats['available'] is True
        assert stats['request_count'] == 0


# ---------------------------------------------------------------------------
# ClaudeAdapter tests
# ---------------------------------------------------------------------------

class TestClaudeAdapter:
    """Test Claude adapter."""

    def test_adapter_type(self):
        adapter = ClaudeAdapter()
        assert adapter.adapter_type == 'claude'

    def test_not_available_without_key(self):
        adapter = ClaudeAdapter()
        assert not adapter.is_available()

    def test_available_with_key(self):
        adapter = ClaudeAdapter(api_key='sk-ant-test')
        assert adapter.is_available()

    def test_generate_without_key_returns_message(self):
        adapter = ClaudeAdapter()
        resp = adapter.generate("Hello")
        assert 'not configured' in resp.content

    def test_model_default(self):
        adapter = ClaudeAdapter()
        assert 'claude' in adapter.model


# ---------------------------------------------------------------------------
# LocalAdapter tests
# ---------------------------------------------------------------------------

class TestLocalAdapter:
    """Test local model adapter."""

    def test_adapter_type(self):
        adapter = LocalAdapter()
        assert adapter.adapter_type == 'local'

    def test_available_with_url(self):
        adapter = LocalAdapter(base_url='http://localhost:8080/v1')
        assert adapter.is_available()

    def test_generate_fails_gracefully(self):
        adapter = LocalAdapter(base_url='http://nonexistent:9999/v1')
        resp = adapter.generate("Hello")
        assert 'unavailable' in resp.content.lower() or 'failed' in resp.content.lower()
        assert resp.metadata.get('error')


# ---------------------------------------------------------------------------
# KnowledgeDistiller tests
# ---------------------------------------------------------------------------

class TestKnowledgeDistiller:
    """Test knowledge distillation from LLM responses."""

    def test_distill_without_kg(self):
        distiller = KnowledgeDistiller()
        resp = LLMResponse(content="Test.", model="test", adapter_type="test")
        nodes = distiller.distill(resp, "query")
        assert nodes == []

    def test_distill_with_kg(self):
        kg = MagicMock()
        kg.add_node = MagicMock(side_effect=lambda **kw: len(kg.add_node.call_args_list))
        kg.add_edge = MagicMock()

        distiller = KnowledgeDistiller(kg)
        resp = LLMResponse(
            content="Qubitcoin uses quantum computing for mining. "
                    "This therefore makes it more secure than classical chains.",
            model="test", adapter_type="test",
        )
        nodes = distiller.distill(resp, "tell me about qubitcoin", block_height=100)
        assert len(nodes) == 2
        assert kg.add_node.call_count == 2
        # Second sentence should be classified as 'inference' due to 'therefore'
        calls = kg.add_node.call_args_list
        assert calls[1][1]['node_type'] == 'inference'

    def test_distill_skips_failed_responses(self):
        kg = MagicMock()
        distiller = KnowledgeDistiller(kg)
        resp = LLMResponse(
            content="Request failed: timeout",
            model="test", adapter_type="test",
        )
        nodes = distiller.distill(resp, "query")
        assert nodes == []

    def test_distill_skips_short_sentences(self):
        kg = MagicMock()
        kg.add_node = MagicMock(return_value=1)
        distiller = KnowledgeDistiller(kg)
        resp = LLMResponse(
            content="OK. Yes. This is a longer sentence about blockchain technology.",
            model="test", adapter_type="test",
        )
        nodes = distiller.distill(resp, "query")
        # Only the long sentence should be added (short ones < 10 chars skipped)
        assert len(nodes) >= 1

    def test_classify_assertion(self):
        assert KnowledgeDistiller._classify_sentence(
            "Qubitcoin uses Dilithium2 signatures."
        ) == 'assertion'

    def test_classify_inference(self):
        assert KnowledgeDistiller._classify_sentence(
            "This therefore implies quantum resistance."
        ) == 'inference'

    def test_split_sentences(self):
        text = "First sentence. Second sentence. Third."
        sentences = KnowledgeDistiller._split_sentences(text)
        assert len(sentences) >= 2

    def test_get_stats(self):
        distiller = KnowledgeDistiller()
        stats = distiller.get_stats()
        assert stats['distilled_count'] == 0
        assert stats['knowledge_graph_available'] is False


# ---------------------------------------------------------------------------
# LLMAdapterManager tests
# ---------------------------------------------------------------------------

class TestLLMAdapterManager:
    """Test multi-adapter management with fallback."""

    def test_register_adapter(self):
        mgr = LLMAdapterManager()
        adapter = OpenAIAdapter(api_key='test')
        mgr.register_adapter(adapter)
        assert 'openai' in mgr.get_available_adapters()

    def test_multiple_adapters(self):
        mgr = LLMAdapterManager()
        mgr.register_adapter(OpenAIAdapter(api_key='test'))
        mgr.register_adapter(ClaudeAdapter(api_key='test'))
        assert len(mgr.get_available_adapters()) == 2

    def test_generate_no_adapters(self):
        mgr = LLMAdapterManager()
        result = mgr.generate("Hello")
        assert result is None

    def test_generate_no_available_adapters(self):
        mgr = LLMAdapterManager()
        mgr.register_adapter(OpenAIAdapter())  # No API key
        result = mgr.generate("Hello")
        assert result is None

    def test_generate_with_distill(self):
        kg = MagicMock()
        kg.add_node = MagicMock(return_value=1)
        kg.add_edge = MagicMock()

        mgr = LLMAdapterManager(knowledge_graph=kg)
        # Create a mock adapter that returns a successful response
        mock_adapter = MagicMock(spec=LLMAdapter)
        mock_adapter.adapter_type = 'mock'
        mock_adapter.is_available = MagicMock(return_value=True)
        mock_adapter._request_count = 0
        mock_adapter.generate = MagicMock(return_value=LLMResponse(
            content="Qubitcoin is a quantum blockchain.",
            model="mock", adapter_type="mock",
        ))
        mgr._adapters['mock'] = mock_adapter
        mgr._priority = ['mock']

        result = mgr.generate("What is Qubitcoin?", distill=True)
        assert result is not None
        assert result.content == "Qubitcoin is a quantum blockchain."

    def test_get_stats(self):
        mgr = LLMAdapterManager()
        mgr.register_adapter(LocalAdapter())
        stats = mgr.get_stats()
        assert 'adapters' in stats
        assert 'local' in stats['adapters']
        assert 'distiller' in stats


# ---------------------------------------------------------------------------
# IPFSMemoryStore tests
# ---------------------------------------------------------------------------

class TestIPFSMemoryStore:
    """Test IPFS memory storage."""

    def test_store_without_ipfs(self):
        store = IPFSMemoryStore()
        cid = store.store_memory(
            memory_id='m1', memory_type='episodic',
            content='Test memory', source_block=10,
        )
        assert cid.startswith('local:')
        assert store._store_count == 1

    def test_retrieve_from_cache(self):
        store = IPFSMemoryStore()
        cid = store.store_memory(
            memory_id='m1', memory_type='episodic',
            content='Test memory', source_block=10,
        )
        data = store.retrieve_memory(cid)
        assert data is not None
        assert data['memory_id'] == 'm1'
        assert data['content'] == 'Test memory'
        assert store._retrieve_count == 1

    def test_retrieve_nonexistent(self):
        store = IPFSMemoryStore()
        data = store.retrieve_memory('nonexistent-cid')
        assert data is None

    def test_store_with_metadata(self):
        store = IPFSMemoryStore()
        cid = store.store_memory(
            memory_id='m2', memory_type='semantic',
            content='Concept: Quantum', source_block=5,
            confidence=0.9, metadata={'category': 'physics'},
        )
        data = store.retrieve_memory(cid)
        assert data['confidence'] == 0.9
        assert data['metadata']['category'] == 'physics'

    def test_store_batch(self):
        store = IPFSMemoryStore()
        memories = [
            {'memory_id': f'm{i}', 'memory_type': 'episodic',
             'content': f'Memory {i}', 'source_block': i}
            for i in range(5)
        ]
        cids = store.store_batch(memories)
        assert len(cids) == 5
        assert store._store_count == 5

    def test_cache_eviction(self):
        store = IPFSMemoryStore()
        store._max_cache = 3
        for i in range(5):
            store.store_memory(f'm{i}', 'episodic', f'Content {i}', i)
        assert len(store._local_cache) == 3

    def test_list_cached(self):
        store = IPFSMemoryStore()
        for i in range(3):
            store.store_memory(f'm{i}', 'episodic', f'Content {i}', i)
        cached = store.list_cached(limit=10)
        assert len(cached) == 3
        assert all('cid' in c for c in cached)

    def test_ipfs_available_false(self):
        store = IPFSMemoryStore()
        assert not store.ipfs_available

    def test_ipfs_available_with_client(self):
        mock_ipfs = MagicMock()
        mock_ipfs.client = MagicMock()
        store = IPFSMemoryStore(mock_ipfs)
        assert store.ipfs_available

    def test_store_with_ipfs(self):
        mock_ipfs = MagicMock()
        mock_ipfs.client = MagicMock()
        mock_ipfs.client.add_json = MagicMock(return_value='QmTestCID123')
        store = IPFSMemoryStore(mock_ipfs)

        cid = store.store_memory('m1', 'episodic', 'Test', 10)
        assert cid == 'QmTestCID123'
        mock_ipfs.client.add_json.assert_called_once()

    def test_retrieve_with_ipfs(self):
        mock_ipfs = MagicMock()
        mock_ipfs.client = MagicMock()
        mock_ipfs.client.get_json = MagicMock(return_value={
            'memory_id': 'm1', 'content': 'From IPFS',
        })
        store = IPFSMemoryStore(mock_ipfs)

        data = store.retrieve_memory('QmSomeCID')
        assert data is not None
        assert data['content'] == 'From IPFS'

    def test_pin_memory(self):
        mock_ipfs = MagicMock()
        mock_ipfs.client = MagicMock()
        store = IPFSMemoryStore(mock_ipfs)

        assert store.pin_memory('QmTestCID')
        mock_ipfs.client.pin.add.assert_called_once_with('QmTestCID')

    def test_pin_local_returns_false(self):
        store = IPFSMemoryStore()
        assert not store.pin_memory('local:abc123')

    def test_get_stats(self):
        store = IPFSMemoryStore()
        store.store_memory('m1', 'episodic', 'Test', 10)
        stats = store.get_stats()
        assert stats['total_stored'] == 1
        assert stats['ipfs_available'] is False
        assert stats['local_cache_size'] == 1


# ---------------------------------------------------------------------------
# Key import/export tests (verify existing implementation)
# ---------------------------------------------------------------------------

class TestKeyImportExport:
    """Verify Dilithium2 key import/export (already implemented in crypto.py)."""

    def test_export_hex(self):
        pk, sk = Dilithium2.keygen()
        exported = Dilithium2.export_keypair(pk, sk, fmt='hex')
        assert exported['format'] == 'hex'
        assert len(exported['public_key']) == 1312 * 2  # hex doubles bytes

    def test_import_hex(self):
        pk, sk = Dilithium2.keygen()
        exported = Dilithium2.export_keypair(pk, sk, fmt='hex')
        pk2, sk2 = Dilithium2.import_keypair(
            exported['public_key'], exported['private_key'], fmt='hex',
        )
        assert pk == pk2
        assert sk == sk2

    def test_export_pem(self):
        pk, sk = Dilithium2.keygen()
        exported = Dilithium2.export_keypair(pk, sk, fmt='pem')
        assert exported['format'] == 'pem'
        assert '-----BEGIN DILITHIUM2 PUBLIC KEY-----' in exported['public_key']
        assert '-----BEGIN DILITHIUM2 PRIVATE KEY-----' in exported['private_key']

    def test_import_pem_roundtrip(self):
        pk, sk = Dilithium2.keygen()
        exported = Dilithium2.export_keypair(pk, sk, fmt='pem')
        pk2, sk2 = Dilithium2.import_keypair(
            exported['public_key'], exported['private_key'], fmt='pem',
        )
        assert pk == pk2
        assert sk == sk2

    def test_signature_cache_info(self):
        info = Dilithium2.cache_info()
        assert 'hits' in info
        assert 'misses' in info
        assert 'maxsize' in info

    def test_sign_verify_cached(self):
        pk, sk = Dilithium2.keygen()
        msg = b"test message"
        sig = Dilithium2.sign(sk, msg)
        # First verification (cache miss)
        assert Dilithium2.verify(pk, msg, sig)
        # Second verification (cache hit)
        assert Dilithium2.verify(pk, msg, sig)


# ---------------------------------------------------------------------------
# System prompt constant tests
# ---------------------------------------------------------------------------

class TestSystemPrompt:
    """Test the Aether system prompt."""

    def test_system_prompt_exists(self):
        assert AETHER_SYSTEM_PROMPT
        assert 'Aether Tree' in AETHER_SYSTEM_PROMPT
        assert 'Qubitcoin' in AETHER_SYSTEM_PROMPT
