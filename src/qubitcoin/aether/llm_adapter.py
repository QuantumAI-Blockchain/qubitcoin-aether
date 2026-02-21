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
                    confidence=0.7,  # LLM-derived knowledge starts at lower confidence
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
            except Exception:
                pass

        self._distilled_count += len(node_ids)
        if node_ids:
            logger.info(
                f"Distilled {len(node_ids)} knowledge nodes from "
                f"{llm_response.adapter_type}:{llm_response.model}"
            )
        return node_ids

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
