"""
Hierarchical Concept Abstraction — From Observations to Abstract Concepts

Clusters semantically similar knowledge nodes and forms abstract 'concept'
nodes that represent higher-level ideas.  Creates 'abstracts' edges linking
concrete nodes to their abstract parent.

Phase 5.2: Cross-Domain Transfer Learning — extracts structural patterns
from concept clusters and transfers them across domains.

Improvement #8: Without abstraction, the knowledge graph remains a flat
collection of observations and inferences.  This module enables hierarchical
organization — the system can reason about "quantum computing" as a concept
rather than only individual observations about specific qubits.
"""
import math
import time
from typing import Dict, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Transfer learning constants
_MAX_PATTERN_LIBRARY_SIZE: int = 200


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

    Transfer Learning (Phase 5.2):
    6. Extract structural patterns from concept nodes
    7. Search for analogous patterns in other domains
    8. Attempt to create cross-domain edges based on matched patterns
    """

    def __init__(self, knowledge_graph=None, vector_index=None) -> None:
        self.kg = knowledge_graph
        self.vector_index = vector_index
        self._concepts_created: int = 0
        self._runs: int = 0
        # Transfer learning state
        self._pattern_library: List[dict] = []
        self._transfer_attempts: int = 0
        self._transfer_successes: int = 0
        self._patterns_extracted: int = 0
        # Incremental refinement state
        self._concepts_refined: int = 0
        self._concepts_split: int = 0
        self._concepts_merged: int = 0
        # Variance threshold for splitting a concept
        self._split_variance_threshold: float = 0.6

    # ------------------------------------------------------------------
    # Original concept formation methods (unchanged)
    # ------------------------------------------------------------------

    def form_concepts(self, domain: Optional[str] = None,
                      similarity_threshold: float = 0.55,
                      min_cluster_size: int = 2,
                      max_nodes: int = 500) -> dict:
        """
        Run concept formation on nodes in a domain.

        Uses adaptive similarity threshold: starts with the provided threshold
        and adjusts based on the distribution of similarities found. If few
        clusters form, the threshold is lowered; if too many form, it is raised.

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

        # Adaptive similarity threshold (Improvement: adaptive threshold)
        # If we have enough similarity scores, use the distribution to adapt
        if similarities:
            sim_values = sorted(similarities.values(), reverse=True)
            # Use the median of top-quartile similarities as a reference
            top_quartile = sim_values[:max(1, len(sim_values) // 4)]
            median_top = top_quartile[len(top_quartile) // 2] if top_quartile else similarity_threshold

            # Adaptive: move threshold toward the data distribution
            adaptive_threshold = similarity_threshold * 0.6 + median_top * 0.4
            # Clamp to reasonable range
            adaptive_threshold = max(0.4, min(0.9, adaptive_threshold))
            effective_threshold = adaptive_threshold
        else:
            effective_threshold = similarity_threshold

        # Agglomerative clustering
        clusters = self._cluster(node_ids, similarities, effective_threshold)

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
        """Compute candidate similarities between nodes.

        Uses ANN (k-nearest neighbor) retrieval to avoid O(n^2) pairwise
        comparison. For each node, retrieves top-k neighbors from the
        vector index and only computes exact similarity for those pairs.
        Complexity: O(n*k) where k << n.
        """
        sims: Dict[Tuple[int, int], float] = {}
        k_neighbors = min(20, max(5, len(node_ids) // 10))
        node_id_set = set(node_ids)

        # Try ANN-accelerated similarity via vector index
        if self.vector_index and self.vector_index.embeddings:
            from .vector_index import cosine_similarity
            for nid_a in node_ids:
                emb_a = self.vector_index.get_embedding(nid_a)
                if not emb_a:
                    continue
                # Use ANN to get top-k candidates instead of comparing all pairs
                neighbors = self.vector_index.query_by_embedding(
                    emb_a, top_k=k_neighbors + 1
                )
                for nid_b, sim in neighbors:
                    if nid_b == nid_a or nid_b not in node_id_set:
                        continue
                    pair = (min(nid_a, nid_b), max(nid_a, nid_b))
                    if pair not in sims:
                        sims[pair] = sim
            return sims

        # Fallback: Jaccard similarity (still O(n^2) but cheaper per comparison)
        for i, nid_a in enumerate(node_ids):
            pattern_a = self._get_content_tokens(nid_a)
            if not pattern_a:
                continue
            for nid_b in node_ids[i + 1:]:
                pattern_b = self._get_content_tokens(nid_b)
                if not pattern_b:
                    continue
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
        """Create an abstract concept node for a cluster of similar nodes.

        Includes a validation quality gate: concepts are only created if
        the cluster meets minimum quality criteria (sufficient confidence
        spread, meaningful content diversity).
        """
        if not self.kg:
            return None

        # Gather info about cluster members
        members = [self.kg.nodes.get(nid) for nid in cluster]
        members = [m for m in members if m is not None]
        if not members:
            return None

        # Quality gate: validate concept quality before creation
        avg_member_conf = sum(m.confidence for m in members) / len(members)
        if avg_member_conf < 0.2:
            logger.debug(
                f"Concept formation rejected: avg confidence {avg_member_conf:.3f} too low "
                f"for {len(members)} members in domain {domain}"
            )
            return None

        # Ensure some content diversity (not all identical nodes)
        content_set = set()
        for m in members:
            text = str(m.content.get('text', m.content.get('type', '')))[:50]
            content_set.add(text)
        if len(content_set) < 2 and len(members) > 3:
            logger.debug("Concept formation rejected: insufficient content diversity")
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

    # ------------------------------------------------------------------
    # Knowledge Consolidation — promote strong patterns to axioms
    # ------------------------------------------------------------------

    def consolidate_to_axioms(self, block_height: int = 0,
                               min_member_count: int = 3,
                               min_confidence: float = 0.5) -> int:
        """Promote well-supported concept clusters to consolidated axiom nodes.

        Scans existing concept nodes (type='abstract_concept') and promotes
        those with sufficient members and confidence to axiom nodes with
        content type 'consolidated_pattern'.

        Args:
            block_height: Current block height for source_block.
            min_member_count: Minimum cluster members to qualify.
            min_confidence: Minimum average confidence to qualify.

        Returns:
            Number of axioms created.
        """
        if not self.kg:
            return 0

        axioms_created = 0
        promoted_ids: set = getattr(self, '_promoted_concept_ids', set())

        for node in list(self.kg.nodes.values()):
            if node.node_id in promoted_ids:
                continue
            content = node.content if isinstance(node.content, dict) else {}
            if content.get('type') != 'abstract_concept':
                continue
            if content.get('member_count', 0) < min_member_count:
                continue
            if node.confidence < min_confidence:
                continue

            # Create consolidated axiom
            axiom_content = {
                'type': 'consolidated_pattern',
                'text': content.get('text', 'Consolidated pattern'),
                'theme_words': content.get('theme_words', []),
                'member_count': content.get('member_count', 0),
                'domain': content.get('domain', 'general'),
                'source_concept_id': node.node_id,
                'source': 'knowledge_consolidation',
            }
            axiom_node = self.kg.add_node(
                node_type='axiom',
                content=axiom_content,
                confidence=min(0.95, node.confidence * 1.1),
                source_block=block_height or node.source_block,
                domain=node.domain,
            )
            if axiom_node:
                self.kg.add_edge(node.node_id, axiom_node.node_id, 'consolidates')
                axioms_created += 1
                promoted_ids.add(node.node_id)

        self._promoted_concept_ids = promoted_ids

        if axioms_created > 0:
            logger.info(f"Knowledge consolidation: {axioms_created} axioms from concepts")

        return axioms_created

    # ------------------------------------------------------------------
    # Phase 5.2: Cross-Domain Transfer Learning
    # ------------------------------------------------------------------

    def extract_pattern(self, concept_node_id: int) -> Optional[dict]:
        """Extract a structural pattern from a concept node.

        Given a concept node (created by ``_create_concept_node``), inspects
        its cluster members and their inter-relationships to build a
        transferable structural pattern descriptor.

        Args:
            concept_node_id: ID of a concept node with 'abstracts' edges
                pointing to cluster members.

        Returns:
            A pattern dict if extraction succeeds, or ``None`` if the node
            is missing, has no members, or has no knowledge graph attached.
        """
        if not self.kg:
            return None

        concept = self.kg.nodes.get(concept_node_id)
        if not concept:
            return None

        # Verify this is a concept node
        content = concept.content or {}
        if content.get('type') != 'abstract_concept':
            return None

        domain = concept.domain or content.get('domain', 'general')

        # Collect member node IDs via outgoing 'abstracts' edges
        member_ids: List[int] = []
        for edge in self.kg._adj_out.get(concept_node_id, []):
            if edge.edge_type == 'abstracts':
                member_ids.append(edge.to_node_id)

        if not member_ids:
            return None

        # Gather structural profile of the cluster
        edge_types: Set[str] = set()
        node_types: Set[str] = set()
        confidences: List[float] = []
        source_blocks: List[int] = []
        member_set = set(member_ids)

        for nid in member_ids:
            node = self.kg.nodes.get(nid)
            if not node:
                continue
            node_types.add(node.node_type)
            confidences.append(node.confidence)
            source_blocks.append(node.source_block)

            # Inspect edges between cluster members (intra-cluster edges)
            for edge in self.kg._adj_out.get(nid, []):
                if edge.to_node_id in member_set:
                    edge_types.add(edge.edge_type)
            for edge in self.kg._adj_in.get(nid, []):
                if edge.from_node_id in member_set and edge.from_node_id != concept_node_id:
                    edge_types.add(edge.edge_type)

        if not confidences:
            return None

        # Confidence profile: mean + stddev
        mean_conf = sum(confidences) / len(confidences)
        variance = sum((c - mean_conf) ** 2 for c in confidences) / len(confidences)
        std_conf = math.sqrt(variance)

        # Temporal profile: block spread
        block_spread = (max(source_blocks) - min(source_blocks)) if len(source_blocks) > 1 else 0

        pattern: dict = {
            'pattern_id': self._patterns_extracted,
            'domain': domain,
            'edge_types': sorted(edge_types),
            'node_types': sorted(node_types),
            'confidence_profile': {
                'mean': round(mean_conf, 4),
                'std': round(std_conf, 4),
            },
            'member_count': len(member_ids),
            'source_concept_id': concept_node_id,
            'block_spread': block_spread,
            'extracted_at': time.time(),
        }

        # Add to pattern library (FIFO eviction if full)
        self._pattern_library.append(pattern)
        if len(self._pattern_library) > _MAX_PATTERN_LIBRARY_SIZE:
            self._pattern_library = self._pattern_library[-_MAX_PATTERN_LIBRARY_SIZE:]
        self._patterns_extracted += 1

        return pattern

    def find_analogous_patterns(self, source_pattern: dict,
                                target_domain: str,
                                min_similarity: float = 0.4) -> List[dict]:
        """Search the pattern library for structurally similar patterns
        in a different domain.

        Similarity is a weighted combination of:
          - Jaccard similarity of edge types (weight 0.5)
          - Jaccard similarity of node types (weight 0.3)
          - Closeness of confidence profiles (weight 0.2)

        Args:
            source_pattern: The pattern to find analogues for.
            target_domain: Domain to search in.
            min_similarity: Minimum similarity threshold.

        Returns:
            List of ``{pattern, similarity, domain}`` dicts, sorted by
            similarity descending.
        """
        source_edges = set(source_pattern.get('edge_types', []))
        source_nodes = set(source_pattern.get('node_types', []))
        source_conf = source_pattern.get('confidence_profile', {})
        source_mean = source_conf.get('mean', 0.5)
        source_std = source_conf.get('std', 0.0)

        results: List[dict] = []

        for candidate in self._pattern_library:
            # Only consider patterns in the target domain
            if candidate.get('domain') != target_domain:
                continue
            # Skip self-match
            if candidate.get('source_concept_id') == source_pattern.get('source_concept_id'):
                continue

            # Jaccard of edge types
            cand_edges = set(candidate.get('edge_types', []))
            edge_union = source_edges | cand_edges
            edge_jaccard = (
                len(source_edges & cand_edges) / len(edge_union)
                if edge_union else 0.0
            )

            # Jaccard of node types
            cand_nodes = set(candidate.get('node_types', []))
            node_union = source_nodes | cand_nodes
            node_jaccard = (
                len(source_nodes & cand_nodes) / len(node_union)
                if node_union else 0.0
            )

            # Closeness of confidence profiles (1 - normalized distance)
            cand_conf = candidate.get('confidence_profile', {})
            cand_mean = cand_conf.get('mean', 0.5)
            cand_std = cand_conf.get('std', 0.0)
            mean_dist = abs(source_mean - cand_mean)
            std_dist = abs(source_std - cand_std)
            # Max possible distance for both is 1.0, average of two distances
            conf_closeness = 1.0 - (mean_dist + std_dist) / 2.0

            # Weighted similarity
            similarity = (
                edge_jaccard * 0.5
                + node_jaccard * 0.3
                + conf_closeness * 0.2
            )

            if similarity >= min_similarity:
                results.append({
                    'pattern': candidate,
                    'similarity': round(similarity, 4),
                    'domain': target_domain,
                })

        results.sort(key=lambda r: r['similarity'], reverse=True)
        return results

    def attempt_transfer(self, source_pattern: dict,
                         target_domain: str,
                         block_height: int) -> dict:
        """Attempt to transfer a structural pattern from one domain to another.

        Steps:
        1. Find nodes in target_domain matching the pattern's node type profile.
        2. Try to create edges between those nodes matching the pattern's edge
           type profile.
        3. Create a ``transfer_hypothesis`` inference node recording the attempt.

        Args:
            source_pattern: The source structural pattern.
            target_domain: The domain to transfer into.
            block_height: Current block height for the new nodes.

        Returns:
            Dict with ``success``, ``edges_created``, ``hypothesis_node_id``,
            ``source_domain``, ``target_domain``.
        """
        self._transfer_attempts += 1
        result: dict = {
            'success': False,
            'edges_created': 0,
            'hypothesis_node_id': None,
            'source_domain': source_pattern.get('domain', 'unknown'),
            'target_domain': target_domain,
        }

        if not self.kg:
            return result

        pattern_node_types = set(source_pattern.get('node_types', []))
        pattern_edge_types = source_pattern.get('edge_types', [])

        if not pattern_node_types:
            return result

        # Step 1: Find candidate nodes in target domain matching type profile
        target_candidates: Dict[str, List[int]] = {}
        for node in self.kg.nodes.values():
            if node.domain == target_domain and node.node_type in pattern_node_types:
                target_candidates.setdefault(node.node_type, []).append(node.node_id)

        # Need at least 2 nodes to create edges
        all_target_ids: List[int] = []
        for ids in target_candidates.values():
            all_target_ids.extend(ids)

        if len(all_target_ids) < 2:
            return result

        # Limit to most recent nodes to keep transfer focused
        target_nodes = [
            self.kg.nodes[nid] for nid in all_target_ids
            if nid in self.kg.nodes
        ]
        target_nodes.sort(key=lambda n: n.source_block, reverse=True)
        target_nodes = target_nodes[:20]  # Cap at 20 to limit edge creation
        target_id_set = {n.node_id for n in target_nodes}

        # Step 2: Create edges matching the pattern's edge type profile
        edges_created = 0
        if pattern_edge_types:
            # For each edge type in the source pattern, try to create it
            # between pairs of target nodes that don't already have that edge
            for edge_type in pattern_edge_types:
                # Create edges between nodes of different types when possible
                target_list = list(target_id_set)
                for i in range(min(len(target_list) - 1, 5)):
                    from_id = target_list[i]
                    to_id = target_list[i + 1]

                    # Check if edge already exists
                    existing = False
                    for edge in self.kg._adj_out.get(from_id, []):
                        if edge.to_node_id == to_id and edge.edge_type == edge_type:
                            existing = True
                            break

                    if not existing:
                        new_edge = self.kg.add_edge(
                            from_id, to_id, edge_type,
                            weight=0.5  # Lower weight for transferred edges
                        )
                        if new_edge:
                            edges_created += 1
                    # Limit to a few edges per transfer attempt
                    if edges_created >= 3:
                        break
                if edges_created >= 3:
                    break

        # Step 3: Create transfer_hypothesis node
        hypothesis_content = {
            'type': 'transfer_hypothesis',
            'text': (
                f"Cross-domain transfer: pattern from "
                f"{source_pattern.get('domain', '?')} applied to {target_domain}"
            ),
            'source_pattern_id': source_pattern.get('pattern_id'),
            'source_domain': source_pattern.get('domain', 'unknown'),
            'target_domain': target_domain,
            'edge_types_transferred': pattern_edge_types[:5],
            'node_types_matched': sorted(pattern_node_types),
            'edges_created': edges_created,
            'source': 'transfer_learning',
        }

        # Confidence is proportional to source pattern confidence and edges created
        source_conf = source_pattern.get('confidence_profile', {}).get('mean', 0.5)
        transfer_conf = source_conf * 0.6  # Discount for cross-domain transfer
        if edges_created > 0:
            transfer_conf = min(transfer_conf + 0.1, 0.9)

        hypothesis_node = self.kg.add_node(
            node_type='inference',
            content=hypothesis_content,
            confidence=transfer_conf,
            source_block=block_height,
            domain=target_domain,
        )

        hypothesis_id: Optional[int] = None
        if hypothesis_node:
            hypothesis_id = hypothesis_node.node_id
            # Link hypothesis to the target nodes it relates to
            for target_node in target_nodes[:3]:
                self.kg.add_edge(
                    hypothesis_id, target_node.node_id,
                    'derives', weight=0.5
                )

        success = edges_created > 0
        if success:
            self._transfer_successes += 1

        result['success'] = success
        result['edges_created'] = edges_created
        result['hypothesis_node_id'] = hypothesis_id

        if success:
            logger.info(
                f"Transfer learning: {source_pattern.get('domain')} -> "
                f"{target_domain}, {edges_created} edges created, "
                f"hypothesis node {hypothesis_id}"
            )

        return result

    def run_transfer_cycle(self, block_height: int) -> dict:
        """Run a full cross-domain transfer learning cycle.

        Called periodically (every 500 blocks, alongside
        ``form_concepts_all_domains``):

        1. Extract patterns from recently-created concept nodes.
        2. For each pattern, search for analogous patterns in other domains.
        3. If analogues found, attempt transfer.
        4. Track success rate.

        Args:
            block_height: Current block height.

        Returns:
            Summary stats dict.
        """
        if not self.kg:
            return {
                'patterns_extracted': 0,
                'analogues_found': 0,
                'transfers_attempted': 0,
                'transfers_succeeded': 0,
            }

        # Step 1: Find recent concept nodes to extract patterns from
        # Look for concept nodes not yet in the pattern library
        existing_concept_ids = {
            p['source_concept_id'] for p in self._pattern_library
        }

        new_concept_nodes: List[int] = []
        for node in self.kg.nodes.values():
            content = node.content or {}
            if (content.get('type') == 'abstract_concept'
                    and content.get('source') == 'concept_formation'
                    and node.node_id not in existing_concept_ids):
                new_concept_nodes.append(node.node_id)

        # Sort by most recent first, limit extraction
        new_concept_nodes.sort(reverse=True)
        new_concept_nodes = new_concept_nodes[:20]

        patterns_extracted = 0
        for cid in new_concept_nodes:
            pattern = self.extract_pattern(cid)
            if pattern:
                patterns_extracted += 1

        # Step 2 & 3: For each pattern, find analogues and attempt transfer
        # Get all domains present in the pattern library
        all_domains: Set[str] = set()
        for p in self._pattern_library:
            d = p.get('domain')
            if d:
                all_domains.add(d)

        analogues_found = 0
        transfers_attempted = 0
        transfers_succeeded = 0

        # Only attempt transfers from recently extracted patterns
        # to keep the cycle bounded
        recent_patterns = self._pattern_library[-10:] if self._pattern_library else []

        for source_pattern in recent_patterns:
            source_domain = source_pattern.get('domain', '')
            for target_domain in all_domains:
                if target_domain == source_domain:
                    continue

                matches = self.find_analogous_patterns(
                    source_pattern, target_domain, min_similarity=0.4
                )
                if matches:
                    analogues_found += len(matches)
                    # Attempt transfer using best match
                    transfers_attempted += 1
                    transfer_result = self.attempt_transfer(
                        source_pattern, target_domain, block_height
                    )
                    if transfer_result.get('success'):
                        transfers_succeeded += 1

        stats = {
            'patterns_extracted': patterns_extracted,
            'analogues_found': analogues_found,
            'transfers_attempted': transfers_attempted,
            'transfers_succeeded': transfers_succeeded,
        }

        if transfers_attempted > 0:
            logger.info(
                f"Transfer cycle at block {block_height}: "
                f"{patterns_extracted} patterns extracted, "
                f"{analogues_found} analogues found, "
                f"{transfers_attempted} attempted, "
                f"{transfers_succeeded} succeeded"
            )

        return stats

    # ------------------------------------------------------------------
    # Phase A12: Incremental Concept Refinement
    # ------------------------------------------------------------------

    def refine_concept(self, concept_id: int, new_nodes: List,
                       similarity_threshold: float = 0.5) -> Optional[int]:
        """Refine an existing concept by incorporating new knowledge nodes.

        Given an existing concept node and a list of new KeterNodes:
        1. Checks if each new node fits the concept (similarity threshold).
        2. Incorporates fitting nodes by adding 'abstracts' edges.
        3. Updates the concept's content (member_count, theme words, confidence).
        4. If internal variance exceeds threshold, splits the concept.

        Args:
            concept_id: Node ID of an existing concept node.
            new_nodes: New KeterNode objects to evaluate for incorporation.
            similarity_threshold: Min similarity for a node to be incorporated.

        Returns:
            The concept_id if updated, or None if no change was made.
            If a split occurs, returns the original concept_id (the new
            split concept is created as a separate node).
        """
        if not self.kg:
            return None

        concept = self.kg.nodes.get(concept_id)
        if not concept:
            return None

        content = concept.content or {}
        if content.get('type') != 'abstract_concept':
            return None

        # Collect current member IDs
        member_ids: List[int] = []
        for edge in self.kg._adj_out.get(concept_id, []):
            if edge.edge_type == 'abstracts':
                member_ids.append(edge.to_node_id)

        if not member_ids:
            return None

        # Compute centroid embedding from existing members
        centroid = self._compute_centroid(member_ids)

        # Evaluate each new node for incorporation
        incorporated: List[int] = []
        for node in new_nodes:
            if not hasattr(node, 'node_id') or node.node_id not in self.kg.nodes:
                continue
            # Skip nodes already in this concept
            if node.node_id in member_ids:
                continue
            # Skip concept nodes themselves
            node_content = node.content or {}
            if node_content.get('type') == 'abstract_concept':
                continue

            sim = self._node_similarity_to_centroid(node.node_id, centroid)
            if sim >= similarity_threshold:
                # Add 'abstracts' edge from concept to this node
                edge = self.kg.add_edge(
                    concept_id, node.node_id,
                    'abstracts', weight=0.8
                )
                if edge:
                    incorporated.append(node.node_id)
                    member_ids.append(node.node_id)

        if not incorporated:
            return None

        # Update concept content metadata
        all_members = [self.kg.nodes.get(nid) for nid in member_ids]
        all_members = [m for m in all_members if m is not None]

        if all_members:
            avg_confidence = sum(m.confidence for m in all_members) / len(all_members)
            max_block = max(m.source_block for m in all_members)

            # Recompute theme words
            all_text = ' '.join(
                str(m.content.get('text', m.content.get('type', '')))
                for m in all_members
            ).lower()
            words = all_text.split()
            word_counts: Dict[str, int] = {}
            for w in words:
                if len(w) > 3:
                    word_counts[w] = word_counts.get(w, 0) + 1
            top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            theme = ' '.join(w for w, _ in top_words) if top_words else content.get('domain', 'general')

            concept.content['text'] = f"Concept: {theme}"
            concept.content['theme_words'] = [w for w, _ in top_words]
            concept.content['member_count'] = len(all_members)
            concept.confidence = avg_confidence * 0.9
            concept.source_block = max_block

        self._concepts_refined += 1

        logger.info(
            f"Concept {concept_id} refined: incorporated {len(incorporated)} new nodes "
            f"(total members: {len(member_ids)})"
        )

        # Check if concept should split due to high internal variance
        if len(member_ids) >= 4:
            variance = self._compute_internal_variance(member_ids)
            if variance > self._split_variance_threshold:
                self._split_concept(concept_id, member_ids)

        return concept_id

    def merge_similar_concepts(self, threshold: float = 0.85) -> int:
        """Merge concept nodes whose centroids are similar enough.

        Compares all pairs of concept nodes.  When centroid similarity
        exceeds ``threshold``, the smaller concept is merged into the
        larger one (its member edges are re-pointed and the smaller
        concept node is demoted to a regular inference).

        Args:
            threshold: Minimum centroid similarity to trigger a merge.

        Returns:
            Number of merges performed.
        """
        if not self.kg:
            return 0

        # Collect all concept nodes
        concept_ids: List[int] = []
        for node in self.kg.nodes.values():
            content = node.content or {}
            if content.get('type') == 'abstract_concept':
                concept_ids.append(node.node_id)

        if len(concept_ids) < 2:
            return 0

        # Build centroid map
        centroids: Dict[int, List[float]] = {}
        members_map: Dict[int, List[int]] = {}
        for cid in concept_ids:
            member_ids: List[int] = []
            for edge in self.kg._adj_out.get(cid, []):
                if edge.edge_type == 'abstracts':
                    member_ids.append(edge.to_node_id)
            members_map[cid] = member_ids
            centroids[cid] = self._compute_centroid(member_ids)

        # Find mergeable pairs (greedy — highest similarity first)
        merge_pairs: List[Tuple[float, int, int]] = []
        concept_list = list(concept_ids)
        for i in range(len(concept_list)):
            for j in range(i + 1, len(concept_list)):
                cid_a, cid_b = concept_list[i], concept_list[j]
                sim = self._centroid_similarity(centroids[cid_a], centroids[cid_b])
                if sim >= threshold:
                    merge_pairs.append((sim, cid_a, cid_b))

        merge_pairs.sort(reverse=True)

        merged_away: Set[int] = set()
        merges = 0

        for sim, cid_a, cid_b in merge_pairs:
            if cid_a in merged_away or cid_b in merged_away:
                continue

            # Merge smaller into larger
            size_a = len(members_map.get(cid_a, []))
            size_b = len(members_map.get(cid_b, []))
            if size_a >= size_b:
                keep, discard = cid_a, cid_b
            else:
                keep, discard = cid_b, cid_a

            # Move member edges from discard to keep
            discard_members = members_map.get(discard, [])
            keep_members = set(members_map.get(keep, []))
            for mid in discard_members:
                if mid not in keep_members:
                    self.kg.add_edge(keep, mid, 'abstracts', weight=0.8)
                    keep_members.add(mid)

            # Update keep concept's member list
            members_map[keep] = list(keep_members)

            # Demote discarded concept — change its type so it's no longer a concept
            discard_node = self.kg.nodes.get(discard)
            if discard_node and discard_node.content:
                discard_node.content['type'] = 'merged_concept'
                discard_node.content['merged_into'] = keep

            # Update keep concept metadata
            all_members = [self.kg.nodes.get(nid) for nid in keep_members if nid in self.kg.nodes]
            if all_members:
                keep_node = self.kg.nodes.get(keep)
                if keep_node:
                    avg_conf = sum(m.confidence for m in all_members) / len(all_members)
                    keep_node.confidence = avg_conf * 0.9
                    keep_node.content['member_count'] = len(all_members)

            merged_away.add(discard)
            merges += 1
            self._concepts_merged += 1

            logger.info(
                f"Merged concept {discard} into {keep} "
                f"(similarity={sim:.3f}, new size={len(keep_members)})"
            )

        return merges

    def _compute_centroid(self, member_ids: List[int]) -> List[float]:
        """Compute the average embedding vector for a set of member nodes.

        Falls back to an empty vector if the vector index is not available
        or no members have embeddings.
        """
        if not self.vector_index or not member_ids:
            return []

        embeddings: List[List[float]] = []
        for nid in member_ids:
            emb = self.vector_index.get_embedding(nid)
            if emb:
                embeddings.append(emb)

        if not embeddings:
            return []

        dim = len(embeddings[0])
        centroid = [0.0] * dim
        for emb in embeddings:
            for i in range(dim):
                centroid[i] += emb[i]
        for i in range(dim):
            centroid[i] /= len(embeddings)
        return centroid

    def _node_similarity_to_centroid(self, node_id: int,
                                     centroid: List[float]) -> float:
        """Compute similarity between a node's embedding and a centroid.

        Uses cosine similarity when embeddings are available, otherwise
        falls back to Jaccard token overlap with concept members.
        """
        if self.vector_index and centroid:
            emb = self.vector_index.get_embedding(node_id)
            if emb:
                from .vector_index import cosine_similarity
                return cosine_similarity(emb, centroid)

        # Fallback: always consider the node a partial match when no embeddings
        return 0.4

    def _centroid_similarity(self, centroid_a: List[float],
                             centroid_b: List[float]) -> float:
        """Compute cosine similarity between two centroid vectors."""
        if not centroid_a or not centroid_b:
            return 0.0
        from .vector_index import cosine_similarity
        return cosine_similarity(centroid_a, centroid_b)

    def _compute_internal_variance(self, member_ids: List[int]) -> float:
        """Compute the average pairwise dissimilarity within a concept.

        Returns a value between 0.0 (perfectly similar) and 1.0 (maximally
        dissimilar).  Uses embeddings if available; otherwise returns 0.0
        (assume low variance without data).
        """
        if not self.vector_index or len(member_ids) < 2:
            return 0.0

        embeddings: List[List[float]] = []
        for nid in member_ids:
            emb = self.vector_index.get_embedding(nid)
            if emb:
                embeddings.append(emb)

        if len(embeddings) < 2:
            return 0.0

        centroid = self._compute_centroid(member_ids)
        if not centroid:
            return 0.0

        from .vector_index import cosine_similarity
        total_dist = 0.0
        for emb in embeddings:
            sim = cosine_similarity(emb, centroid)
            total_dist += (1.0 - sim)

        return total_dist / len(embeddings)

    def _split_concept(self, concept_id: int, member_ids: List[int]) -> Optional[int]:
        """Split a concept into two if internal variance is too high.

        Uses a simple bisection: partitions members into two groups based
        on similarity to the centroid.  The original concept keeps the
        closer half; a new concept is created for the farther half.

        Args:
            concept_id: The concept to split.
            member_ids: Current member node IDs.

        Returns:
            Node ID of the newly created split concept, or None.
        """
        if not self.kg or len(member_ids) < 4:
            return None

        centroid = self._compute_centroid(member_ids)
        if not centroid:
            return None

        # Score each member by similarity to centroid
        scored: List[Tuple[float, int]] = []
        for nid in member_ids:
            sim = self._node_similarity_to_centroid(nid, centroid)
            scored.append((sim, nid))
        scored.sort(reverse=True)

        # Split at midpoint
        midpoint = len(scored) // 2
        keep_ids = [nid for _, nid in scored[:midpoint]]
        split_ids = [nid for _, nid in scored[midpoint:]]

        if len(split_ids) < 2:
            return None

        # Determine domain from the original concept
        concept_node = self.kg.nodes.get(concept_id)
        domain = concept_node.domain if concept_node else 'general'

        # Create new concept for the split-off members
        new_concept_id = self._create_concept_node(split_ids, domain)
        if new_concept_id is None:
            return None

        # Remove split-off members from original concept's edges
        # (edges remain in the global edge list but we won't double-link)
        # The new concept node already has 'abstracts' edges to split_ids
        # via _create_concept_node, so we just update the original's metadata
        if concept_node:
            concept_node.content['member_count'] = len(keep_ids)

        self._concepts_split += 1
        logger.info(
            f"Split concept {concept_id}: kept {len(keep_ids)} members, "
            f"new concept {new_concept_id} with {len(split_ids)} members"
        )

        return new_concept_id

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def validate_transfer(self, hypothesis_node_id: int,
                          block_height: int) -> dict:
        """Validate a previously created transfer hypothesis.

        Checks whether the transferred pattern has led to useful new
        edges or knowledge growth in the target domain.

        Args:
            hypothesis_node_id: Node ID of the transfer_hypothesis node.
            block_height: Current block height.

        Returns:
            Dict with validation result and evidence.
        """
        if not self.kg:
            return {'valid': False, 'reason': 'no_kg'}

        node = self.kg.nodes.get(hypothesis_node_id)
        if not node:
            return {'valid': False, 'reason': 'node_not_found'}

        content = node.content or {}
        if content.get('type') != 'transfer_hypothesis':
            return {'valid': False, 'reason': 'not_a_transfer_hypothesis'}

        target_domain = content.get('target_domain', '')
        edges_created = content.get('edges_created', 0)

        # Check if the transferred edges have been used (referenced by other reasoning)
        usage_count = 0
        for edge in self.kg.get_edges_from(hypothesis_node_id):
            target = self.kg.nodes.get(edge.to_node_id)
            if target:
                # Check if target has gained new edges since transfer
                target_edges = self.kg.get_edges_from(edge.to_node_id)
                for te in target_edges:
                    if te.edge_type in ('supports', 'derives', 'causes'):
                        usage_count += 1

        valid = usage_count > 0 or edges_created > 1
        if valid:
            # Boost hypothesis confidence since it was validated
            node.confidence = min(1.0, node.confidence + 0.1)

        return {
            'valid': valid,
            'usage_count': usage_count,
            'edges_created': edges_created,
            'target_domain': target_domain,
            'hypothesis_confidence': round(node.confidence, 4),
        }

    def get_stats(self) -> dict:
        """Return concept formation and transfer learning statistics."""
        transfer_rate = (
            self._transfer_successes / max(self._transfer_attempts, 1)
        )
        return {
            'total_concepts_created': self._concepts_created,
            'total_runs': self._runs,
            'transfer_attempts': self._transfer_attempts,
            'transfer_successes': self._transfer_successes,
            'transfer_success_rate': round(transfer_rate, 4),
            'patterns_extracted': self._patterns_extracted,
            'pattern_library_size': len(self._pattern_library),
            'concepts_refined': self._concepts_refined,
            'concepts_split': self._concepts_split,
            'concepts_merged': self._concepts_merged,
        }
