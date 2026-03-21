"""
External Knowledge Connector — Ground Aether Tree in Real-World Facts

Fetches structured knowledge from Wikidata (SPARQL) and ConceptNet (REST API)
and injects grounded facts into the knowledge graph with provenance tracking.

Called during the 'active_learning' circadian phase by the Pineal orchestrator,
or on-demand when chat queries require external grounding.
"""
import hashlib
import time
from typing import Any, Dict, List, Optional

import httpx

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Rate limiting: max requests per source per minute
_RATE_LIMIT = 10
_request_timestamps: Dict[str, List[float]] = {'wikidata': [], 'conceptnet': []}


def _rate_ok(source: str) -> bool:
    """Check if we can make another request to this source."""
    now = time.time()
    _request_timestamps[source] = [t for t in _request_timestamps[source] if now - t < 60]
    return len(_request_timestamps[source]) < _RATE_LIMIT


def _record_request(source: str) -> None:
    """Record a request timestamp for rate limiting."""
    _request_timestamps[source].append(time.time())


class ExternalKnowledgeConnector:
    """Fetches and injects external knowledge into the Aether Tree KG.

    Sources:
        - Wikidata: Structured facts via SPARQL (entities, properties, descriptions)
        - ConceptNet: Commonsense relations (IsA, HasProperty, UsedFor, etc.)

    All injected nodes carry a 'grounding_source' field for provenance tracking.
    Confidence is set lower than internally-derived knowledge (0.6 vs 0.8+)
    since external facts haven't been verified by the reasoning engine.
    """

    WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
    CONCEPTNET_ENDPOINT = "https://api.conceptnet.io"

    def __init__(self, knowledge_graph: Any = None, timeout: float = 10.0) -> None:
        self.kg = knowledge_graph
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)
        self._stats = {
            'wikidata_queries': 0,
            'conceptnet_queries': 0,
            'facts_injected': 0,
            'errors': 0,
        }

    def query_wikidata(self, concept: str, limit: int = 5) -> List[dict]:
        """Query Wikidata for facts about a concept.

        Args:
            concept: Search term (e.g., 'quantum computing', 'blockchain').
            limit: Max results to return.

        Returns:
            List of fact dicts with 'label', 'description', 'uri'.
        """
        if not _rate_ok('wikidata'):
            logger.debug("Wikidata rate limit reached, skipping")
            return []

        sparql = f"""
        SELECT ?item ?itemLabel ?itemDescription WHERE {{
          ?item rdfs:label "{concept}"@en.
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """

        try:
            _record_request('wikidata')
            self._stats['wikidata_queries'] += 1
            resp = self._client.get(
                self.WIKIDATA_ENDPOINT,
                params={'query': sparql, 'format': 'json'},
                headers={'User-Agent': 'QubitcoinAetherTree/1.0 (https://qbc.network)'},
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for binding in data.get('results', {}).get('bindings', []):
                results.append({
                    'label': binding.get('itemLabel', {}).get('value', ''),
                    'description': binding.get('itemDescription', {}).get('value', ''),
                    'uri': binding.get('item', {}).get('value', ''),
                    'source': 'wikidata',
                })
            return results

        except Exception as e:
            self._stats['errors'] += 1
            logger.debug("Wikidata query failed for '%s': %s", concept, e)
            return []

    def search_wikidata(self, query: str, limit: int = 5) -> List[dict]:
        """Search Wikidata entities by text (uses wbsearchentities API).

        More flexible than exact SPARQL match — handles partial matches.
        """
        if not _rate_ok('wikidata'):
            return []

        try:
            _record_request('wikidata')
            self._stats['wikidata_queries'] += 1
            resp = self._client.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    'action': 'wbsearchentities',
                    'search': query,
                    'language': 'en',
                    'limit': limit,
                    'format': 'json',
                },
                headers={'User-Agent': 'QubitcoinAetherTree/1.0 (https://qbc.network)'},
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for entity in data.get('search', []):
                results.append({
                    'label': entity.get('label', ''),
                    'description': entity.get('description', ''),
                    'uri': entity.get('concepturi', ''),
                    'qid': entity.get('id', ''),
                    'source': 'wikidata',
                })
            return results

        except Exception as e:
            self._stats['errors'] += 1
            logger.debug("Wikidata search failed for '%s': %s", query, e)
            return []

    def query_conceptnet(self, concept: str, limit: int = 10) -> List[dict]:
        """Query ConceptNet for commonsense relations about a concept.

        Args:
            concept: Concept term (e.g., 'blockchain', 'encryption').
            limit: Max relations to return.

        Returns:
            List of relation dicts with 'start', 'end', 'relation', 'weight'.
        """
        if not _rate_ok('conceptnet'):
            logger.debug("ConceptNet rate limit reached, skipping")
            return []

        # Normalize concept for ConceptNet URI format
        concept_uri = concept.lower().replace(' ', '_')

        try:
            _record_request('conceptnet')
            self._stats['conceptnet_queries'] += 1
            resp = self._client.get(
                f"{self.CONCEPTNET_ENDPOINT}/c/en/{concept_uri}",
                params={'limit': limit},
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for edge in data.get('edges', []):
                start_label = edge.get('start', {}).get('label', '')
                end_label = edge.get('end', {}).get('label', '')
                rel = edge.get('rel', {}).get('label', '')
                weight = edge.get('weight', 1.0)

                if start_label and end_label and rel:
                    results.append({
                        'start': start_label,
                        'end': end_label,
                        'relation': rel,
                        'weight': weight,
                        'source': 'conceptnet',
                        'text': f"{start_label} {rel} {end_label}",
                    })

            return results

        except Exception as e:
            self._stats['errors'] += 1
            logger.debug("ConceptNet query failed for '%s': %s", concept, e)
            return []

    def ground_concept(self, concept: str, block_height: int = 0) -> List[int]:
        """Fetch external knowledge about a concept and inject into KG.

        Queries both Wikidata and ConceptNet, deduplicates, and creates
        knowledge nodes with grounding_source provenance.

        Args:
            concept: The concept to ground (e.g., 'quantum entanglement').
            block_height: Current block height for provenance.

        Returns:
            List of created knowledge node IDs.
        """
        if not self.kg or not hasattr(self.kg, 'add_node'):
            return []

        created_ids: List[int] = []
        seen_hashes: set = set()

        # Wikidata search
        wiki_results = self.search_wikidata(concept, limit=3)
        for result in wiki_results:
            desc = result.get('description', '')
            if not desc:
                continue

            # Deduplicate by content hash
            content_hash = hashlib.sha256(desc.encode()).hexdigest()[:16]
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)

            text = f"{result['label']}: {desc}"
            node = self.kg.add_node(
                node_type='external_fact',
                content={
                    'type': 'external_fact',
                    'text': text,
                    'description': desc,
                    'grounding_source': 'wikidata',
                    'source_uri': result.get('uri', ''),
                    'concept': concept,
                },
                confidence=0.6,  # Lower than internal knowledge
                source_block=block_height,
            )
            if node:
                created_ids.append(node.node_id)
                self._stats['facts_injected'] += 1

        # ConceptNet relations
        cn_results = self.query_conceptnet(concept, limit=5)
        for result in cn_results:
            text = result.get('text', '')
            if not text:
                continue

            content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)

            node = self.kg.add_node(
                node_type='external_fact',
                content={
                    'type': 'external_fact',
                    'text': text,
                    'grounding_source': 'conceptnet',
                    'relation': result.get('relation', ''),
                    'concept': concept,
                    'weight': result.get('weight', 1.0),
                },
                confidence=0.55,  # ConceptNet slightly lower than Wikidata
                source_block=block_height,
            )
            if node:
                created_ids.append(node.node_id)
                self._stats['facts_injected'] += 1

        if created_ids:
            logger.info(
                "Grounded concept '%s': %d facts injected (wiki=%d, cn=%d)",
                concept, len(created_ids),
                len(wiki_results), len(cn_results),
            )

        return created_ids

    def enrich_query(self, query: str) -> List[dict]:
        """Get external knowledge relevant to a chat query without injecting into KG.

        Used by chat.py to provide grounded context for response synthesis.

        Args:
            query: User's query text.

        Returns:
            List of external fact dicts for context enrichment.
        """
        # Extract key concepts from query (simple noun phrase extraction)
        words = query.lower().split()
        # Filter stop words and short words
        stop_words = {'what', 'is', 'the', 'how', 'does', 'can', 'a', 'an', 'in',
                      'of', 'for', 'to', 'and', 'or', 'it', 'this', 'that', 'are',
                      'was', 'be', 'with', 'on', 'at', 'by', 'about', 'tell', 'me',
                      'explain', 'describe', 'do', 'you', 'your', 'my', 'i'}
        concepts = [w for w in words if w not in stop_words and len(w) > 3]

        if not concepts:
            return []

        # Query ConceptNet for the most specific concept (longest word)
        best_concept = max(concepts, key=len)
        return self.query_conceptnet(best_concept, limit=3)

    def periodic_ingestion(self, domains: Optional[List[str]] = None,
                           block_height: int = 0) -> dict:
        """Periodic knowledge ingestion — called during active_learning phase.

        Fetches external facts for a list of domains relevant to the blockchain.

        Args:
            domains: List of domain concepts to ground. Defaults to core domains.
            block_height: Current block height.

        Returns:
            Dict with ingestion statistics.
        """
        if domains is None:
            domains = [
                'quantum computing', 'blockchain consensus',
                'post-quantum cryptography', 'golden ratio mathematics',
                'knowledge graph', 'artificial general intelligence',
            ]

        total_injected = 0
        for domain in domains:
            ids = self.ground_concept(domain, block_height)
            total_injected += len(ids)

        return {
            'domains_processed': len(domains),
            'facts_injected': total_injected,
            'block_height': block_height,
        }

    def get_stats(self) -> dict:
        """Return external knowledge connector statistics."""
        return dict(self._stats)

    def close(self) -> None:
        """Close the HTTP client."""
        try:
            self._client.close()
        except Exception:
            pass
