"""
Hierarchical Concept Abstraction — From Observations to Abstract Concepts

Clusters semantically similar knowledge nodes and forms abstract 'concept'
nodes that represent higher-level ideas.  Creates 'abstracts' edges linking
concrete nodes to their abstract parent.

Improvement #8: Without abstraction, the knowledge graph remains a flat
collection of observations and inferences.  This module enables hierarchical
organization — the system can reason about "quantum computing" as a concept
rather than only individual observations about specific qubits.
"""
import math
from typing import Dict, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ConceptFormation:
    """
    Discovers abstract concepts by clustering similar knowledge nodes.

    Algorithm:
    1. Group nodes by domain
    2. Within each domain, compute pairwise semantic similarity
       (using VectorIndex embeddings or edge-pattern overlap)
    3. Agglomerative clustering with a similarity threshold
    4. For each cluster of size >= min_cluster, create an abstract
       'concept' node linked to members via 'abstracts' edges
    5. Concept nodes can themselves be clustered for multi-level hierarchy
    """

    def __init__(self, knowledge_graph=None, vector_index=None) -> None:
        self.kg = knowledge_graph
        self.vector_index = vector_index
        self._concepts_created: int = 0
        self._runs: int = 0

    def form_concepts(self, domain: Optional[str] = None,
                      similarity_threshold: float = 0.7,
                      min_cluster_size: int = 3,
                      max_nodes: int = 500) -> dict:
        """
        Run concept formation on nodes in a domain.

        Args:
            domain: Domain to analyze (None = all domains).
            similarity_threshold: Min cosine similarity for clustering.
            min_cluster_size: Min cluster size to create a concept node.
            max_nodes: Max nodes to process (most recent first).

        Returns:
            Dict with concepts created and stats.
        """
        if not self.kg:
            return {'concepts_created': 0, 'nodes_analyzed': 0}

        self._runs += 1

        # Select candidate nodes
        candidates = [
            n for n in self.kg.nodes.values()
            if (not domain or n.domain == domain)
            and n.node_type in ('observation', 'inference', 'assertion')
        ]
        candidates.sort(key=lambda n: n.source_block, reverse=True)
        candidates = candidates[:max_nodes]

        if len(candidates) < min_cluster_size:
            return {'concepts_created': 0, 'nodes_analyzed': len(candidates)}

        # Build similarity matrix
        node_ids = [n.node_id for n in candidates]
        similarities = self._compute_similarities(node_ids)

        # Agglomerative clustering
        clusters = self._cluster(node_ids, similarities, similarity_threshold)

        # Create concept nodes for large enough clusters
        concepts_created = 0
        for cluster in clusters:
            if len(cluster) < min_cluster_size:
                continue

            concept = self._create_concept_node(cluster, domain or 'general')
            if concept:
                concepts_created += 1

        self._concepts_created += concepts_created

        if concepts_created > 0:
            logger.info(
                f"Concept formation ({domain or 'all'}): "
                f"{concepts_created} concepts from {len(candidates)} nodes "
                f"({len(clusters)} clusters)"
            )

        return {
            'concepts_created': concepts_created,
            'nodes_analyzed': len(candidates),
            'clusters_found': len(clusters),
            'domain': domain,
        }

    def form_concepts_all_domains(self, block_height: int = 0,
                                   min_domain_nodes: int = 10) -> int:
        """Run concept formation across all domains with enough nodes."""
        if not self.kg:
            return 0

        total = 0
        domain_stats = self.kg.get_domain_stats()
        for domain, info in domain_stats.items():
            if info['count'] >= min_domain_nodes:
                result = self.form_concepts(domain=domain)
                total += result['concepts_created']

        return total

    def _compute_similarities(self, node_ids: List[int]) -> Dict[Tuple[int, int], float]:
        """Compute pairwise similarities between nodes."""
        sims: Dict[Tuple[int, int], float] = {}

        # Try vector similarity first (better quality)
        if self.vector_index and self.vector_index.embeddings:
            from .vector_index import cosine_similarity
            for i, nid_a in enumerate(node_ids):
                emb_a = self.vector_index.get_embedding(nid_a)
                if not emb_a:
                    continue
                for nid_b in node_ids[i + 1:]:
                    emb_b = self.vector_index.get_embedding(nid_b)
                    if not emb_b:
                        continue
                    sim = cosine_similarity(emb_a, emb_b)
                    sims[(nid_a, nid_b)] = sim
            return sims

        # Fallback: edge-pattern similarity
        for i, nid_a in enumerate(node_ids):
            pattern_a = self._get_content_tokens(nid_a)
            if not pattern_a:
                continue
            for nid_b in node_ids[i + 1:]:
                pattern_b = self._get_content_tokens(nid_b)
                if not pattern_b:
                    continue
                # Jaccard similarity
                intersection = len(pattern_a & pattern_b)
                union = len(pattern_a | pattern_b)
                if union > 0:
                    sims[(nid_a, nid_b)] = intersection / union

        return sims

    def _get_content_tokens(self, node_id: int) -> Set[str]:
        """Extract a set of content tokens from a node."""
        node = self.kg.nodes.get(node_id)
        if not node:
            return set()
        text = ' '.join(str(v) for v in node.content.values()).lower()
        return set(text.split())

    def _cluster(self, node_ids: List[int],
                 similarities: Dict[Tuple[int, int], float],
                 threshold: float) -> List[List[int]]:
        """Simple agglomerative clustering."""
        # Start with each node in its own cluster
        clusters: List[Set[int]] = [{nid} for nid in node_ids]
        id_to_cluster: Dict[int, int] = {nid: i for i, nid in enumerate(node_ids)}

        # Find pairs above threshold and merge
        merge_candidates = [
            (sim, a, b)
            for (a, b), sim in similarities.items()
            if sim >= threshold
        ]
        merge_candidates.sort(reverse=True)  # Highest similarity first

        for sim, a, b in merge_candidates:
            ca = id_to_cluster.get(a)
            cb = id_to_cluster.get(b)
            if ca is None or cb is None or ca == cb:
                continue
            # Merge smaller into larger
            if len(clusters[ca]) < len(clusters[cb]):
                ca, cb = cb, ca
            # Merge
            for nid in clusters[cb]:
                id_to_cluster[nid] = ca
            clusters[ca].update(clusters[cb])
            clusters[cb] = set()

        # Collect non-empty clusters
        return [list(c) for c in clusters if len(c) >= 2]

    def _create_concept_node(self, cluster: List[int], domain: str) -> Optional[int]:
        """Create an abstract concept node for a cluster of similar nodes."""
        if not self.kg:
            return None

        # Gather info about cluster members
        members = [self.kg.nodes.get(nid) for nid in cluster]
        members = [m for m in members if m is not None]
        if not members:
            return None

        # Compute cluster centroid confidence
        avg_confidence = sum(m.confidence for m in members) / len(members)
        max_block = max(m.source_block for m in members)

        # Extract common themes from content
        all_text = ' '.join(
            str(m.content.get('text', m.content.get('type', '')))
            for m in members
        ).lower()
        words = all_text.split()
        word_counts: Dict[str, int] = {}
        for w in words:
            if len(w) > 3:
                word_counts[w] = word_counts.get(w, 0) + 1
        top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        theme = ' '.join(w for w, _ in top_words) if top_words else domain

        content = {
            'type': 'abstract_concept',
            'text': f"Concept: {theme}",
            'theme_words': [w for w, _ in top_words],
            'member_count': len(members),
            'domain': domain,
            'source': 'concept_formation',
        }

        concept_node = self.kg.add_node(
            node_type='inference',
            content=content,
            confidence=avg_confidence * 0.9,  # Slight discount for abstraction
            source_block=max_block,
            domain=domain,
        )

        if concept_node:
            # Link members to concept via 'abstracts' edges
            for member in members:
                self.kg.add_edge(
                    concept_node.node_id, member.node_id,
                    'abstracts', weight=0.8
                )
            return concept_node.node_id

        return None

    def get_stats(self) -> dict:
        return {
            'total_concepts_created': self._concepts_created,
            'total_runs': self._runs,
        }
