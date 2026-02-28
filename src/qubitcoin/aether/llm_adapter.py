"""
LLM Adapters for Aether Tree External Intelligence

Provides pluggable adapters for external Large Language Models to augment
Aether Tree's reasoning capabilities. Each adapter implements a common
interface and feeds responses back into the knowledge graph via the
KnowledgeDistiller.

Adapters:
  - OpenAIAdapter: GPT-4 / ChatGPT
  - ClaudeAdapter: Anthropic Claude
  - LocalAdapter: Open-source models (Llama, Mistral) via local HTTP API
  - KnowledgeDistiller: Extract insights from LLM responses into KG
"""
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    """Response from an LLM adapter."""
    content: str
    model: str
    adapter_type: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'content': self.content,
            'model': self.model,
            'adapter_type': self.adapter_type,
            'tokens_used': self.tokens_used,
            'latency_ms': self.latency_ms,
            'metadata': self.metadata,
        }


class LLMAdapter(ABC):
    """Abstract base class for LLM adapters.

    All adapters implement `generate()` which takes a prompt and
    optional context, returning an LLMResponse.
    """

    def __init__(self, model: str = '', api_key: str = '',
                 base_url: str = '', max_tokens: int = 1024,
                 temperature: float = 0.7) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._request_count: int = 0
        self._total_tokens: int = 0

    @property
    @abstractmethod
    def adapter_type(self) -> str:
        """Identifier for this adapter type."""
        ...

    @abstractmethod
    def generate(self, prompt: str,
                 context: Optional[List[dict]] = None,
                 system_prompt: Optional[str] = None) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: The user's query.
            context: Optional list of prior messages for conversation.
            system_prompt: Optional system-level instruction.

        Returns:
            LLMResponse with the generated content.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this adapter is configured and reachable."""
        ...

    def get_stats(self) -> dict:
        """Get adapter usage statistics."""
        return {
            'adapter_type': self.adapter_type,
            'model': self.model,
            'available': self.is_available(),
            'request_count': self._request_count,
            'total_tokens': self._total_tokens,
        }


# Default system prompt for Aether Tree LLM interactions
AETHER_SYSTEM_PROMPT = (
    "You are Aether Tree, the AGI reasoning engine of the Qubitcoin blockchain. "
    "You have access to a knowledge graph of blockchain observations, quantum "
    "computations, and logical inferences. Respond thoughtfully and precisely. "
    "When referencing knowledge, cite the reasoning steps that led to your answer."
)


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI GPT models (GPT-4, etc.)."""

    def __init__(self, api_key: str = '', model: str = 'gpt-4',
                 base_url: str = 'https://api.openai.com/v1',
                 max_tokens: int = 1024, temperature: float = 0.7) -> None:
        super().__init__(model, api_key, base_url, max_tokens, temperature)

    @property
    def adapter_type(self) -> str:
        return 'openai'

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str,
                 context: Optional[List[dict]] = None,
                 system_prompt: Optional[str] = None) -> LLMResponse:
        """Generate via OpenAI Chat Completions API."""
        if not self.is_available():
            return LLMResponse(
                content="OpenAI adapter not configured (no API key).",
                model=self.model, adapter_type=self.adapter_type,
            )

        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        if context:
            messages.extend(context)
        messages.append({'role': 'user', 'content': prompt})

        start = time.time()
        try:
            import urllib.request
            payload = json.dumps({
                'model': self.model,
                'messages': messages,
                'max_tokens': self.max_tokens,
                'temperature': self.temperature,
            }).encode()

            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}',
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())

            content = data['choices'][0]['message']['content']
            tokens = data.get('usage', {}).get('total_tokens', 0)
            latency = (time.time() - start) * 1000

            self._request_count += 1
            self._total_tokens += tokens

            return LLMResponse(
                content=content, model=self.model,
                adapter_type=self.adapter_type,
                tokens_used=tokens, latency_ms=latency,
            )
        except Exception as e:
            logger.warning(f"OpenAI request failed: {e}")
            return LLMResponse(
                content=f"OpenAI request failed: {e}",
                model=self.model, adapter_type=self.adapter_type,
                latency_ms=(time.time() - start) * 1000,
                metadata={'error': str(e)},
            )


class ClaudeAdapter(LLMAdapter):
    """Adapter for Anthropic Claude models."""

    def __init__(self, api_key: str = '', model: str = 'claude-sonnet-4-5-20250929',
                 base_url: str = 'https://api.anthropic.com/v1',
                 max_tokens: int = 1024, temperature: float = 0.7) -> None:
        super().__init__(model, api_key, base_url, max_tokens, temperature)

    @property
    def adapter_type(self) -> str:
        return 'claude'

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str,
                 context: Optional[List[dict]] = None,
                 system_prompt: Optional[str] = None) -> LLMResponse:
        """Generate via Anthropic Messages API."""
        if not self.is_available():
            return LLMResponse(
                content="Claude adapter not configured (no API key).",
                model=self.model, adapter_type=self.adapter_type,
            )

        messages = []
        if context:
            messages.extend(context)
        messages.append({'role': 'user', 'content': prompt})

        start = time.time()
        try:
            import urllib.request
            payload = json.dumps({
                'model': self.model,
                'messages': messages,
                'max_tokens': self.max_tokens,
                'temperature': self.temperature,
                'system': system_prompt or AETHER_SYSTEM_PROMPT,
            }).encode()

            req = urllib.request.Request(
                f"{self.base_url}/messages",
                data=payload,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': self.api_key,
                    'anthropic-version': '2023-06-01',
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())

            content = data['content'][0]['text']
            in_tokens = data.get('usage', {}).get('input_tokens', 0)
            out_tokens = data.get('usage', {}).get('output_tokens', 0)
            tokens = in_tokens + out_tokens
            latency = (time.time() - start) * 1000

            self._request_count += 1
            self._total_tokens += tokens

            return LLMResponse(
                content=content, model=self.model,
                adapter_type=self.adapter_type,
                tokens_used=tokens, latency_ms=latency,
            )
        except Exception as e:
            logger.warning(f"Claude request failed: {e}")
            return LLMResponse(
                content=f"Claude request failed: {e}",
                model=self.model, adapter_type=self.adapter_type,
                latency_ms=(time.time() - start) * 1000,
                metadata={'error': str(e)},
            )


class LocalAdapter(LLMAdapter):
    """Adapter for local/self-hosted models (Llama, Mistral, etc.).

    Connects to any OpenAI-compatible local API endpoint (e.g., llama.cpp,
    vLLM, Ollama, text-generation-webui).
    """

    def __init__(self, model: str = 'local-model',
                 base_url: str = 'http://localhost:8080/v1',
                 max_tokens: int = 1024, temperature: float = 0.7) -> None:
        super().__init__(model, '', base_url, max_tokens, temperature)

    @property
    def adapter_type(self) -> str:
        return 'local'

    def is_available(self) -> bool:
        return bool(self.base_url)

    def generate(self, prompt: str,
                 context: Optional[List[dict]] = None,
                 system_prompt: Optional[str] = None) -> LLMResponse:
        """Generate via OpenAI-compatible local API."""
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        if context:
            messages.extend(context)
        messages.append({'role': 'user', 'content': prompt})

        start = time.time()
        try:
            import urllib.request
            payload = json.dumps({
                'model': self.model,
                'messages': messages,
                'max_tokens': self.max_tokens,
                'temperature': self.temperature,
            }).encode()

            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=payload,
                headers={'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())

            content = data['choices'][0]['message']['content']
            tokens = data.get('usage', {}).get('total_tokens', 0)
            latency = (time.time() - start) * 1000

            self._request_count += 1
            self._total_tokens += tokens

            return LLMResponse(
                content=content, model=self.model,
                adapter_type=self.adapter_type,
                tokens_used=tokens, latency_ms=latency,
            )
        except Exception as e:
            logger.debug(f"Local LLM request failed: {e}")
            return LLMResponse(
                content=f"Local model unavailable: {e}",
                model=self.model, adapter_type=self.adapter_type,
                latency_ms=(time.time() - start) * 1000,
                metadata={'error': str(e)},
            )


class KnowledgeDistiller:
    """Extract structured insights from LLM responses into the knowledge graph.

    The distiller parses LLM output and creates KeterNodes capturing
    assertions, inferences, and observations that the LLM produced.
    This feeds external intelligence back into Aether's knowledge base.
    """

    def __init__(self, knowledge_graph: object = None) -> None:
        """
        Args:
            knowledge_graph: KnowledgeGraph instance to store distilled knowledge.
        """
        self.kg = knowledge_graph
        self._distilled_count: int = 0

    def distill(self, llm_response: LLMResponse, query: str,
                block_height: int = 0) -> List[int]:
        """Extract knowledge from an LLM response and add to the graph.

        Splits the response into sentences, classifies each as an assertion
        or inference, and creates KeterNodes.

        Args:
            llm_response: The LLM response to distill.
            query: The original user query.
            block_height: Current block height for provenance.

        Returns:
            List of created node IDs.
        """
        if not self.kg:
            return []

        content = llm_response.content
        if not content or 'failed' in content.lower():
            return []

        # Score quality before distillation
        quality = self._score_response(content, query)
        if quality < 0.3:
            logger.debug(f"LLM response quality too low ({quality:.2f}), skipping distillation")
            return []

        # Map quality score to confidence: 0.3 -> 0.4, 1.0 -> 0.9
        base_confidence = 0.4 + (quality - 0.3) * (0.5 / 0.7)
        base_confidence = max(0.4, min(0.9, base_confidence))

        node_ids: List[int] = []
        sentences = self._split_sentences(content)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue

            node_type = self._classify_sentence(sentence)
            try:
                node = self.kg.add_node(
                    content={
                        'text': sentence,
                        'source': f"llm:{llm_response.adapter_type}",
                        'model': llm_response.model,
                        'query': query[:100],
                    },
                    node_type=node_type,
                    confidence=base_confidence,
                    source_block=block_height,
                )
                node_ids.append(node.node_id)
            except Exception as e:
                logger.debug(f"Failed to add distilled node: {e}")

        # Connect related distilled nodes
        for i in range(len(node_ids) - 1):
            try:
                self.kg.add_edge(
                    node_ids[i], node_ids[i + 1],
                    edge_type='derives',
                    weight=0.8,
                )
            except Exception as e:
                logger.debug(f"Edge linking (derives): {e}")

        # Cross-reference: link new nodes to existing graph nodes with similar content
        self._cross_reference(node_ids)

        self._distilled_count += len(node_ids)
        if node_ids:
            logger.info(
                f"Distilled {len(node_ids)} knowledge nodes from "
                f"{llm_response.adapter_type}:{llm_response.model}"
            )
        return node_ids

    def _cross_reference(self, new_node_ids: List[int],
                         max_refs_per_node: int = 5) -> int:
        """Link new nodes to existing graph nodes with similar content.

        Uses TF-IDF search to find semantically related existing nodes
        and creates 'supports' or 'refines' edges between them.

        Args:
            new_node_ids: IDs of newly created nodes.
            max_refs_per_node: Max cross-references per new node.

        Returns:
            Total number of cross-reference edges created.
        """
        if not self.kg:
            return 0
        try:
            search_index = getattr(self.kg, 'search_index', None)
            if not search_index or search_index.n_docs < 10:
                return 0  # Not enough data for meaningful cross-references
        except (TypeError, AttributeError):
            return 0

        total_refs = 0
        new_ids_set = set(new_node_ids)

        for nid in new_node_ids:
            node = self.kg.nodes.get(nid)
            if not node:
                continue

            text = node.content.get('text', '')
            if not text:
                continue

            # Find similar existing nodes via TF-IDF
            try:
                matches = self.kg.search(text, top_k=max_refs_per_node + len(new_node_ids))
            except Exception:
                continue

            refs_created = 0
            for match_node, score in matches:
                if refs_created >= max_refs_per_node:
                    break
                # Skip self-references and other new nodes from same batch
                if match_node.node_id == nid or match_node.node_id in new_ids_set:
                    continue
                # Only link if similarity is meaningful
                if score < 0.15:
                    break

                # Choose edge type: 'supports' for same type, 'refines' for inference
                edge_type = 'refines' if node.node_type == 'inference' else 'supports'
                try:
                    self.kg.add_edge(nid, match_node.node_id, edge_type=edge_type,
                                     weight=min(1.0, score))
                    refs_created += 1
                    total_refs += 1
                except Exception as e:
                    logger.debug(f"Edge linking (cross-ref {edge_type}): {e}")

        if total_refs > 0:
            logger.info(f"Created {total_refs} cross-references for {len(new_node_ids)} new nodes")
        return total_refs

    def _score_response(self, content: str, query: str) -> float:
        """Score an LLM response for quality before distillation.

        Checks:
        1. Specificity — contains concrete claims (numbers, names, terms)
        2. Relevance — shares keywords with the query
        3. Consistency — doesn't contradict high-confidence nodes

        Returns:
            Float score 0.0 (very low quality) to 1.0 (excellent).
        """
        score = 0.5  # Baseline

        # 1. Specificity: penalize vague generalities
        specificity_signals = [
            'specifically', 'exactly', 'approximately', 'defined as',
            'measured', 'equals', 'consists of', 'requires',
        ]
        vague_signals = [
            'it depends', 'generally speaking', 'it varies',
            'there are many', 'it is complex', 'broadly',
        ]
        content_lower = content.lower()
        specific_hits = sum(1 for s in specificity_signals if s in content_lower)
        vague_hits = sum(1 for s in vague_signals if s in content_lower)
        score += min(0.2, specific_hits * 0.05)
        score -= min(0.15, vague_hits * 0.05)

        # Bonus for containing numbers (concrete data)
        import re
        numbers = re.findall(r'\d+\.?\d*', content)
        if numbers:
            score += min(0.1, len(numbers) * 0.02)

        # 2. Relevance: check query keyword overlap
        query_words = set(query.lower().split())
        content_words = set(content_lower.split())
        overlap = len(query_words & content_words)
        if query_words:
            relevance = overlap / len(query_words)
            score += min(0.15, relevance * 0.2)

        # 3. Consistency: check for contradictions with high-confidence nodes
        if self.kg and hasattr(self.kg, 'search_index'):
            try:
                search_index = getattr(self.kg, 'search_index', None)
                if search_index and search_index.n_docs > 0:
                    # Find existing nodes on the same topic
                    matches = self.kg.search(query, top_k=3)
                    for match_node, sim_score in matches:
                        if match_node.confidence > 0.8 and sim_score > 0.3:
                            # High-confidence existing knowledge exists — slight boost
                            score += 0.05
                            break
            except (TypeError, AttributeError):
                pass

        # Penalty for very short responses (likely incomplete)
        if len(content) < 50:
            score -= 0.2
        # Penalty for error-like content
        if any(err in content_lower for err in ['error', 'failed', 'unavailable', 'cannot']):
            score -= 0.3

        return max(0.0, min(1.0, score))

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split text into sentences (simple heuristic)."""
        # Split on sentence-ending punctuation followed by space or end
        sentences: List[str] = []
        current: List[str] = []
        for char in text:
            current.append(char)
            if char in '.!?' and len(current) > 10:
                sentences.append(''.join(current))
                current = []
        if current:
            sentences.append(''.join(current))
        return sentences

    @staticmethod
    def _classify_sentence(sentence: str) -> str:
        """Classify a sentence as an assertion, inference, or observation."""
        lower = sentence.lower()
        inference_signals = [
            'therefore', 'thus', 'hence', 'implies', 'suggests',
            'indicates', 'likely', 'probably', 'could', 'might',
        ]
        if any(signal in lower for signal in inference_signals):
            return 'inference'
        return 'assertion'

    def get_stats(self) -> dict:
        """Get distiller statistics."""
        return {
            'distilled_count': self._distilled_count,
            'knowledge_graph_available': self.kg is not None,
        }


class LLMAdapterManager:
    """Manages multiple LLM adapters with fallback chain.

    Tries the primary adapter first; if it fails, falls back to
    the next available adapter in priority order.
    """

    def __init__(self, knowledge_graph: object = None) -> None:
        self._adapters: Dict[str, LLMAdapter] = {}
        self._adapter_priorities: Dict[str, int] = {}
        self._priority: List[str] = []  # Ordered adapter type names
        self._distiller = KnowledgeDistiller(knowledge_graph)

    def register_adapter(self, adapter: LLMAdapter,
                         priority: int = 100) -> None:
        """Register an LLM adapter.

        Args:
            adapter: The adapter instance.
            priority: Lower number = higher priority (tried first).
        """
        self._adapters[adapter.adapter_type] = adapter
        self._adapter_priorities[adapter.adapter_type] = priority
        # Rebuild priority list sorted by stored priority
        items = sorted(
            self._adapters.items(),
            key=lambda x: self._adapter_priorities.get(x[0], 100),
        )
        self._priority = [k for k, _ in items]
        logger.info(f"LLM adapter registered: {adapter.adapter_type} ({adapter.model}) priority={priority}")

    def generate(self, prompt: str, context: Optional[List[dict]] = None,
                 system_prompt: Optional[str] = None,
                 distill: bool = True,
                 block_height: int = 0) -> Optional[LLMResponse]:
        """Generate a response using the best available adapter.

        Tries adapters in priority order. Optionally distills the
        response into the knowledge graph.

        Args:
            prompt: The user query.
            context: Conversation context.
            system_prompt: System prompt override.
            distill: If True, extract knowledge from the response.
            block_height: Current block height for provenance.

        Returns:
            LLMResponse or None if all adapters fail.
        """
        sys_prompt = system_prompt or AETHER_SYSTEM_PROMPT

        for adapter_type in self._priority:
            adapter = self._adapters[adapter_type]
            if not adapter.is_available():
                continue

            response = adapter.generate(prompt, context, sys_prompt)
            if response and not response.metadata.get('error'):
                # Distill knowledge from successful response
                if distill and self._distiller.kg:
                    self._distiller.distill(response, prompt, block_height)
                return response

        return None

    def get_available_adapters(self) -> List[str]:
        """Get list of available adapter types."""
        return [
            k for k, v in self._adapters.items()
            if v.is_available()
        ]

    def get_stats(self) -> dict:
        """Get all adapter statistics."""
        return {
            'adapters': {
                k: v.get_stats() for k, v in self._adapters.items()
            },
            'priority': self._priority,
            'available': self.get_available_adapters(),
            'distiller': self._distiller.get_stats(),
        }
