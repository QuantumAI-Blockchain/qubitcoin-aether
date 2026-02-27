"""
Knowledge Graph - KeterNode System
Manages the decentralized knowledge graph that forms the foundation of the Aether Tree.
Each node (KeterNode) represents a piece of verified knowledge; edges represent relationships.
"""
import hashlib
import json
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class KeterNode:
    """
    A knowledge node in the Aether Tree.
    Named after Keter (Crown) in Kabbalistic Tree of Life — the highest sephira.
    """
    node_id: int = 0
    node_type: str = 'assertion'  # assertion, observation, inference, axiom, prediction, meta_observation
    content_hash: str = ''
    content: dict = field(default_factory=dict)
    confidence: float = 0.5  # [0.0, 1.0]
    source_block: int = 0
    timestamp: float = 0.0
    domain: str = ''  # Auto-assigned domain (quantum_physics, mathematics, etc.)
    last_referenced_block: int = 0  # Last block where this node was used in reasoning
    reference_count: int = 0  # How many times this node has been used in reasoning
    grounding_source: str = ''  # '', 'block_oracle', 'prediction_verified', 'qusd_oracle'
    # In-memory graph links
    edges_out: List[int] = field(default_factory=list)
    edges_in: List[int] = field(default_factory=list)

    def effective_confidence(self, current_block: int = 0) -> float:
        """Return confidence adjusted for time-decay.

        Decay is based on blocks since last reference (or creation if never
        referenced).  Axioms never decay.  Floor is configurable
        (default 0.3) so old knowledge never fully vanishes.
        """
        if self.node_type == 'axiom' or current_block <= 0:
            return self.confidence
        from ..config import Config
        halflife = Config.CONFIDENCE_DECAY_HALFLIFE
        floor = Config.CONFIDENCE_DECAY_FLOOR
        ref_block = self.last_referenced_block or self.source_block
        age = max(0, current_block - ref_block)
        decay = max(floor, 1.0 - (age / halflife))
        return self.confidence * decay

    def calculate_hash(self) -> str:
        data = json.dumps({
            'type': self.node_type,
            'content': self.content,
            'source_block': self.source_block,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop('edges_out', None)
        d.pop('edges_in', None)
        return d


@dataclass
class KeterEdge:
    """Directed edge between two KeterNodes"""
    from_node_id: int
    to_node_id: int
    edge_type: str = 'supports'  # supports, contradicts, derives, requires, refines, causes, abstracts, analogous_to
    weight: float = 1.0
    timestamp: float = 0.0


# Domain keyword mapping for auto-classification
DOMAIN_KEYWORDS: Dict[str, Set[str]] = {
    'quantum_physics': {'qubit', 'quantum', 'superposition', 'entanglement', 'decoherence',
                        'hamiltonian', 'vqe', 'qiskit', 'photon', 'wave', 'particle'},
    'mathematics': {'theorem', 'proof', 'algebra', 'topology', 'geometry', 'calculus',
                    'prime', 'fibonacci', 'equation', 'integral', 'matrix', 'vector'},
    'computer_science': {'algorithm', 'compiler', 'database', 'hash', 'binary',
                         'complexity', 'turing', 'sorting', 'graph_theory', 'recursion'},
    'blockchain': {'block', 'transaction', 'consensus', 'mining', 'utxo', 'merkle',
                   'ledger', 'token', 'smart_contract', 'defi', 'bridge', 'staking'},
    'cryptography': {'encryption', 'signature', 'dilithium', 'lattice', 'zero_knowledge',
                     'zkp', 'aes', 'rsa', 'cipher', 'post_quantum'},
    'philosophy': {'consciousness', 'qualia', 'epistemology', 'ethics', 'ontology',
                   'kabbalah', 'sephirot', 'phenomenology', 'mind', 'metaphysics'},
    'biology': {'neuron', 'dna', 'gene', 'evolution', 'cell', 'protein',
                'ecology', 'organism', 'neural', 'brain', 'synapse'},
    'physics': {'relativity', 'gravity', 'thermodynamics', 'entropy', 'energy',
                'electromagnetism', 'nuclear', 'optics', 'cosmology', 'dark_matter'},
    'economics': {'market', 'inflation', 'monetary', 'gdp', 'trade',
                  'supply_demand', 'fiscal', 'currency', 'game_theory'},
    'ai_ml': {'transformer', 'neural_network', 'reinforcement', 'gradient',
              'backpropagation', 'llm', 'attention', 'embedding', 'training', 'inference'},
}


def classify_domain(content: dict) -> str:
    """Classify a knowledge node's domain from its content.

    Scans all text fields in the content dict against keyword sets.
    Returns the best-matching domain or 'general' if no strong match.
    """
    text = ' '.join(str(v) for v in content.values()).lower()
    # Normalize separators
    text = text.replace('-', '_').replace('.', ' ')
    words = set(text.split())

    best_domain = 'general'
    best_score = 0
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = len(words & keywords)
        if score > best_score:
            best_score = score
            best_domain = domain
    return best_domain


class KnowledgeGraph:
    """
    In-memory knowledge graph backed by database persistence.
    Supports CRUD operations, graph traversal, and root hash computation.
    Includes a TF-IDF index for semantic search.
    """

    def __init__(self, db_manager):
        self.db = db_manager
        self._lock = threading.Lock()
        self.nodes: Dict[int, KeterNode] = {}
        self.edges: List[KeterEdge] = []
        # O(1) edge adjacency index — avoids O(n) scans of self.edges
        self._adj_out: Dict[int, List[KeterEdge]] = {}  # node_id -> outgoing edges
        self._adj_in: Dict[int, List[KeterEdge]] = {}   # node_id -> incoming edges
        self._next_id = 1
        # Merkle root cache — avoids O(n) recomputation per call
        self._merkle_dirty: bool = True
        self._merkle_cache: str = ''
        # TF-IDF semantic search index
        from .kg_index import TFIDFIndex
        self.search_index = TFIDFIndex()
        # Dense embedding vector index (semantic similarity)
        from .vector_index import VectorIndex
        self.vector_index = VectorIndex()
        self._load_from_db()

    def _load_from_db(self):
        """Load knowledge graph from database into memory"""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                rows = session.execute(
                    text("SELECT id, node_type, content_hash, content, confidence, source_block FROM knowledge_nodes ORDER BY id")
                )
                for r in rows:
                    node = KeterNode(
                        node_id=r[0],
                        node_type=r[1],
                        content_hash=r[2],
                        content=json.loads(r[3]) if isinstance(r[3], str) else (r[3] or {}),
                        confidence=float(r[4] or 0.5),
                        source_block=r[5] or 0,
                    )
                    self.nodes[node.node_id] = node
                    self._next_id = max(self._next_id, node.node_id + 1)

                edge_rows = session.execute(
                    text("SELECT from_node_id, to_node_id, edge_type, weight FROM knowledge_edges ORDER BY id")
                )
                for r in edge_rows:
                    edge = KeterEdge(
                        from_node_id=r[0], to_node_id=r[1],
                        edge_type=r[2], weight=float(r[3] or 1.0)
                    )
                    self.edges.append(edge)
                    self._adj_out.setdefault(r[0], []).append(edge)
                    self._adj_in.setdefault(r[1], []).append(edge)
                    if r[0] in self.nodes:
                        self.nodes[r[0]].edges_out.append(r[1])
                    if r[1] in self.nodes:
                        self.nodes[r[1]].edges_in.append(r[0])

            # Build TF-IDF index and auto-classify domains for loaded nodes
            unclassified = 0
            for nid, node in self.nodes.items():
                self.search_index.add_node(nid, node.content)
                if not node.domain:
                    node.domain = classify_domain(node.content)
                    unclassified += 1

            # Batch-build vector embeddings for loaded nodes
            if self.nodes:
                batch = {nid: node.content for nid, node in self.nodes.items()}
                embedded = self.vector_index.add_nodes_batch(batch)
                if embedded:
                    logger.info(f"Vector index: embedded {embedded} nodes")

            domain_counts = {}
            for node in self.nodes.values():
                d = node.domain or 'general'
                domain_counts[d] = domain_counts.get(d, 0) + 1

            logger.info(f"Knowledge graph loaded: {len(self.nodes)} nodes, {len(self.edges)} edges, "
                         f"{self.search_index.get_stats()['unique_terms']} indexed terms, "
                         f"{len(domain_counts)} domains"
                         + (f" ({unclassified} auto-classified)" if unclassified else ''))
        except Exception as e:
            logger.debug(f"Knowledge graph load: {e}")

    def add_node(self, node_type: str, content: dict, confidence: float,
                 source_block: int, domain: str = '') -> KeterNode:
        """Add a new knowledge node"""
        with self._lock:
            node = KeterNode(
                node_id=self._next_id,
                node_type=node_type,
                content=content,
                confidence=max(0.0, min(1.0, confidence)),
                source_block=source_block,
                timestamp=time.time(),
                domain=domain or classify_domain(content),
                last_referenced_block=source_block,
            )
            node.content_hash = node.calculate_hash()
            self._next_id += 1
            self.nodes[node.node_id] = node
            self._merkle_dirty = True

        # Update search indices (outside lock — no shared state mutation)
        self.search_index.add_node(node.node_id, content)
        self.vector_index.add_node(node.node_id, content)

        # Persist
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(
                    text("""
                        INSERT INTO knowledge_nodes (id, node_type, content_hash, content, confidence, source_block)
                        VALUES (:id, :ntype, :chash, CAST(:content AS jsonb), :conf, :sb)
                    """),
                    {
                        'id': node.node_id, 'ntype': node.node_type,
                        'chash': node.content_hash,
                        'content': json.dumps(node.content),
                        'conf': node.confidence, 'sb': source_block,
                    }
                )
                session.commit()
        except Exception as e:
            logger.error(f"Failed to persist knowledge node: {e}")

        return node

    def add_edge(self, from_id: int, to_id: int, edge_type: str = 'supports',
                 weight: float = 1.0) -> Optional[KeterEdge]:
        """Add a directed edge between two nodes"""
        with self._lock:
            if from_id not in self.nodes or to_id not in self.nodes:
                logger.warning(f"Cannot add edge: node {from_id} or {to_id} not found")
                return None

            edge = KeterEdge(
                from_node_id=from_id, to_node_id=to_id,
                edge_type=edge_type, weight=weight,
                timestamp=time.time()
            )
            self.edges.append(edge)
            self._adj_out.setdefault(from_id, []).append(edge)
            self._adj_in.setdefault(to_id, []).append(edge)
            self._merkle_dirty = True
            self.nodes[from_id].edges_out.append(to_id)
            self.nodes[to_id].edges_in.append(from_id)

        # Persist
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(
                    text("""
                        INSERT INTO knowledge_edges (from_node_id, to_node_id, edge_type, weight)
                        VALUES (:fid, :tid, :etype, :w)
                        ON CONFLICT (from_node_id, to_node_id, edge_type) DO UPDATE SET weight = :w
                    """),
                    {'fid': from_id, 'tid': to_id, 'etype': edge_type, 'w': weight}
                )
                session.commit()
        except Exception as e:
            logger.error(f"Failed to persist knowledge edge: {e}")

        return edge

    def get_node(self, node_id: int) -> Optional[KeterNode]:
        return self.nodes.get(node_id)

    def get_neighbors(self, node_id: int, direction: str = 'out') -> List[KeterNode]:
        """Get neighboring nodes"""
        node = self.nodes.get(node_id)
        if not node:
            return []
        ids = node.edges_out if direction == 'out' else node.edges_in
        return [self.nodes[nid] for nid in ids if nid in self.nodes]

    def get_subgraph(self, root_id: int, depth: int = 3) -> Dict[int, KeterNode]:
        """BFS to get subgraph up to given depth"""
        visited: Dict[int, KeterNode] = {}
        queue = deque([(root_id, 0)])

        while queue:
            nid, d = queue.popleft()
            if nid in visited or d > depth:
                continue
            node = self.nodes.get(nid)
            if not node:
                continue
            visited[nid] = node
            for neighbor_id in node.edges_out + node.edges_in:
                if neighbor_id not in visited:
                    queue.append((neighbor_id, d + 1))

        return visited

    def find_paths(self, from_id: int, to_id: int, max_depth: int = 5) -> List[List[int]]:
        """Find all paths between two nodes up to max_depth"""
        paths = []

        def _dfs(current: int, target: int, path: List[int], visited: Set[int]):
            if len(path) > max_depth:
                return
            if current == target:
                paths.append(list(path))
                return
            node = self.nodes.get(current)
            if not node:
                return
            for nid in node.edges_out:
                if nid not in visited:
                    visited.add(nid)
                    path.append(nid)
                    _dfs(nid, target, path, visited)
                    path.pop()
                    visited.remove(nid)

        _dfs(from_id, to_id, [from_id], {from_id})
        return paths

    def propagate_confidence(self, node_id: int, iterations: int = 3):
        """
        Propagate confidence scores through the graph.
        Nodes supported by high-confidence parents gain confidence;
        nodes contradicted by high-confidence parents lose it.
        """
        for _ in range(iterations):
            updates = {}
            for nid, node in self.nodes.items():
                if not node.edges_in:
                    continue
                support_sum = 0.0
                contradict_sum = 0.0
                count = 0
                for edge in self._adj_in.get(nid, []):
                    parent = self.nodes.get(edge.from_node_id)
                    if not parent:
                        continue
                    if edge.edge_type in ('supports', 'derives'):
                        support_sum += parent.confidence * edge.weight
                    elif edge.edge_type == 'contradicts':
                        contradict_sum += parent.confidence * edge.weight
                    count += 1

                if count > 0:
                    # Weighted update: support raises confidence, contradiction lowers it
                    delta = (support_sum - contradict_sum) / count * 0.1
                    new_conf = max(0.0, min(1.0, node.confidence + delta))
                    updates[nid] = new_conf

            for nid, conf in updates.items():
                self.nodes[nid].confidence = conf

    def compute_knowledge_root(self) -> str:
        """
        Compute Merkle root hash of the entire knowledge graph.
        Used in Proof-of-Thought for chain binding.
        Cached — only recomputes when graph is mutated.
        """
        if not self.nodes:
            return hashlib.sha256(b'empty_knowledge').hexdigest()

        if not self._merkle_dirty and self._merkle_cache:
            return self._merkle_cache

        leaves = []
        for nid in sorted(self.nodes.keys()):
            node = self.nodes[nid]
            leaf = hashlib.sha256(
                f"{nid}:{node.content_hash}:{node.confidence:.6f}".encode()
            ).hexdigest()
            leaves.append(leaf)

        # Merkle tree
        while len(leaves) > 1:
            if len(leaves) % 2 == 1:
                leaves.append(leaves[-1])
            new_leaves = []
            for i in range(0, len(leaves), 2):
                combined = hashlib.sha256(
                    (leaves[i] + leaves[i + 1]).encode()
                ).hexdigest()
                new_leaves.append(combined)
            leaves = new_leaves

        self._merkle_cache = leaves[0]
        self._merkle_dirty = False
        return self._merkle_cache

    def prune_low_confidence(self, threshold: float = 0.1, protect_types: Optional[Set[str]] = None) -> int:
        """
        Remove nodes with confidence below threshold from memory AND database.

        Nodes of protected types (e.g. 'axiom') are never pruned.
        Edges referencing pruned nodes are also removed.

        Args:
            threshold: Minimum confidence to keep a node
            protect_types: Node types that are never pruned

        Returns:
            Number of nodes removed
        """
        protect = protect_types or {'axiom'}
        to_remove = [
            nid for nid, node in self.nodes.items()
            if node.confidence < threshold and node.node_type not in protect
        ]

        if not to_remove:
            return 0

        # Remove from in-memory graph
        for nid in to_remove:
            self.edges = [
                e for e in self.edges
                if e.from_node_id != nid and e.to_node_id != nid
            ]
            # Clean adjacency index
            for edge in self._adj_out.get(nid, []):
                adj_list = self._adj_in.get(edge.to_node_id, [])
                self._adj_in[edge.to_node_id] = [e for e in adj_list if e.from_node_id != nid]
            for edge in self._adj_in.get(nid, []):
                adj_list = self._adj_out.get(edge.from_node_id, [])
                self._adj_out[edge.from_node_id] = [e for e in adj_list if e.to_node_id != nid]
            self._adj_out.pop(nid, None)
            self._adj_in.pop(nid, None)
            for other_node in self.nodes.values():
                if nid in other_node.edges_out:
                    other_node.edges_out.remove(nid)
                if nid in other_node.edges_in:
                    other_node.edges_in.remove(nid)
            del self.nodes[nid]
        self._merkle_dirty = True

        # Delete from database
        db_deleted_nodes = 0
        db_deleted_edges = 0
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                # Delete edges first (referential integrity)
                result = session.execute(
                    text("""
                        DELETE FROM knowledge_edges
                        WHERE from_node_id = ANY(:ids) OR to_node_id = ANY(:ids)
                    """),
                    {"ids": to_remove}
                )
                db_deleted_edges = result.rowcount

                # Delete nodes
                result = session.execute(
                    text("DELETE FROM knowledge_nodes WHERE id = ANY(:ids)"),
                    {"ids": to_remove}
                )
                db_deleted_nodes = result.rowcount

                session.commit()
        except Exception as e:
            logger.error(f"Failed to delete pruned nodes from DB: {e}")

        logger.info(
            f"Pruned {len(to_remove)} low-confidence nodes (threshold={threshold}), "
            f"DB: {db_deleted_nodes} nodes + {db_deleted_edges} edges deleted"
        )
        return len(to_remove)

    def persist_confidence_updates(self) -> int:
        """
        Write changed confidence values back to the database.

        Called periodically (e.g. every 100 blocks) to ensure that
        confidence adjustments from reasoning/propagation survive restarts.

        Returns:
            Number of rows updated.
        """
        if not self.nodes:
            return 0

        try:
            from sqlalchemy import text
            updated = 0
            with self.db.get_session() as session:
                # Batch update — send all current confidences
                for nid, node in self.nodes.items():
                    result = session.execute(
                        text("""
                            UPDATE knowledge_nodes SET confidence = :conf
                            WHERE id = :id AND confidence != :conf
                        """),
                        {'conf': node.confidence, 'id': nid}
                    )
                    updated += result.rowcount
                session.commit()

            if updated > 0:
                logger.info(f"Persisted confidence updates for {updated} nodes")
            return updated
        except Exception as e:
            logger.error(f"Failed to persist confidence updates: {e}")
            return 0

    def search(self, query: str, top_k: int = 10) -> List[Tuple[KeterNode, float]]:
        """
        Semantic search blending TF-IDF keyword match + dense vector similarity.

        Args:
            query: Natural language search query
            top_k: Maximum results to return

        Returns:
            List of (KeterNode, similarity_score) tuples, best match first.
        """
        # TF-IDF results (keyword match)
        tfidf_results = self.search_index.query(query, top_k=top_k * 2)
        # Vector results (semantic similarity)
        vector_results = self.vector_index.query(query, top_k=top_k * 2)

        # Blend scores: 0.4 * tfidf + 0.6 * vector (semantic weighs more)
        scores: Dict[int, float] = {}
        for nid, score in tfidf_results:
            scores[nid] = scores.get(nid, 0.0) + 0.4 * score
        for nid, score in vector_results:
            scores[nid] = scores.get(nid, 0.0) + 0.6 * score

        # Sort by blended score, return top_k
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            (self.nodes[nid], score)
            for nid, score in ranked
            if nid in self.nodes
        ]

    def find_by_type(self, node_type: str, limit: int = 100) -> List[KeterNode]:
        """Find nodes by type, sorted by confidence descending."""
        matching = [
            n for n in self.nodes.values()
            if n.node_type == node_type
        ]
        matching.sort(key=lambda n: n.confidence, reverse=True)
        return matching[:limit]

    def find_by_content(self, key: str, value: str, limit: int = 50) -> List[KeterNode]:
        """Find nodes whose content dict contains a matching key-value."""
        matching = [
            n for n in self.nodes.values()
            if str(n.content.get(key, '')) == str(value)
        ]
        matching.sort(key=lambda n: n.source_block, reverse=True)
        return matching[:limit]

    def find_recent(self, count: int = 20) -> List[KeterNode]:
        """Get the most recently added nodes by source block."""
        nodes = sorted(
            self.nodes.values(),
            key=lambda n: n.source_block,
            reverse=True,
        )
        return nodes[:count]

    def get_edge_types_for_node(self, node_id: int) -> Dict[str, List[int]]:
        """Get all edges grouped by type for a specific node. O(degree) via adjacency index."""
        result: Dict[str, List[int]] = {}
        for edge in self._adj_out.get(node_id, []):
            result.setdefault(f"out_{edge.edge_type}", []).append(edge.to_node_id)
        for edge in self._adj_in.get(node_id, []):
            result.setdefault(f"in_{edge.edge_type}", []).append(edge.from_node_id)
        return result

    def get_edges_from(self, node_id: int) -> List[KeterEdge]:
        """Get all outgoing edges from a node. O(1) lookup."""
        return self._adj_out.get(node_id, [])

    def get_edges_to(self, node_id: int) -> List[KeterEdge]:
        """Get all incoming edges to a node. O(1) lookup."""
        return self._adj_in.get(node_id, [])

    def export_json_ld(self, limit: int = 0) -> dict:
        """Export the knowledge graph in JSON-LD format.

        Args:
            limit: Maximum number of nodes to export (0 = all).

        Returns:
            JSON-LD document with @context, @graph nodes, and edges.
        """
        context = {
            "@vocab": "https://qbc.network/ontology#",
            "qbc": "https://qbc.network/ontology#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "node_type": "qbc:nodeType",
            "confidence": {"@id": "qbc:confidence", "@type": "xsd:float"},
            "source_block": {"@id": "qbc:sourceBlock", "@type": "xsd:integer"},
            "content_hash": "qbc:contentHash",
            "supports": "qbc:supports",
            "contradicts": "qbc:contradicts",
            "derives": "qbc:derives",
            "requires": "qbc:requires",
            "refines": "qbc:refines",
        }

        nodes_list = sorted(self.nodes.values(), key=lambda n: n.node_id)
        if limit > 0:
            nodes_list = nodes_list[:limit]
        exported_ids = {n.node_id for n in nodes_list}

        graph = []
        for node in nodes_list:
            entry: dict = {
                "@id": f"qbc:node/{node.node_id}",
                "@type": "qbc:KeterNode",
                "node_type": node.node_type,
                "confidence": round(node.confidence, 6),
                "source_block": node.source_block,
                "content_hash": node.content_hash,
            }
            if node.content:
                entry["qbc:content"] = node.content
            graph.append(entry)

        # Add edges that connect exported nodes
        for edge in self.edges:
            if edge.from_node_id in exported_ids and edge.to_node_id in exported_ids:
                graph.append({
                    "@id": f"qbc:edge/{edge.from_node_id}-{edge.to_node_id}",
                    "@type": "qbc:KeterEdge",
                    "qbc:from": {"@id": f"qbc:node/{edge.from_node_id}"},
                    "qbc:to": {"@id": f"qbc:node/{edge.to_node_id}"},
                    "qbc:edgeType": edge.edge_type,
                    "qbc:weight": round(edge.weight, 6),
                })

        return {
            "@context": context,
            "@graph": graph,
            "qbc:stats": {
                "exported_nodes": len(nodes_list),
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
            },
        }

    def touch_node(self, node_id: int, current_block: int) -> None:
        """Update a node's last_referenced_block and increment reference count.

        Called when a node is used in reasoning or referenced in a query.
        Resets the decay clock and builds evidence for the node.
        """
        node = self.nodes.get(node_id)
        if node:
            node.last_referenced_block = current_block
            node.reference_count += 1

    def boost_referenced_nodes(self, min_references: int = 5, boost_per_ref: float = 0.01,
                               max_boost: float = 0.15) -> int:
        """Boost confidence of frequently-referenced nodes.

        Nodes that have been used in reasoning multiple times get a small
        confidence increase, creating natural selection pressure: useful
        knowledge rises, unused knowledge fades (via decay).

        Args:
            min_references: Minimum references before boost applies.
            boost_per_ref: Confidence increase per log(references).
            max_boost: Maximum total boost per call.

        Returns:
            Number of nodes boosted.
        """
        boosted = 0
        for node in self.nodes.values():
            if node.reference_count >= min_references:
                boost = min(max_boost, boost_per_ref * math.log(node.reference_count))
                new_conf = min(1.0, node.confidence + boost)
                if new_conf > node.confidence:
                    node.confidence = new_conf
                    boosted += 1
        if boosted:
            logger.info(f"Boosted confidence for {boosted} frequently-referenced nodes")
        return boosted

    def get_domain_stats(self) -> Dict[str, dict]:
        """Get node counts and average confidence per domain."""
        domains: Dict[str, dict] = {}
        for node in self.nodes.values():
            d = node.domain or 'general'
            if d not in domains:
                domains[d] = {'count': 0, 'total_confidence': 0.0}
            domains[d]['count'] += 1
            domains[d]['total_confidence'] += node.confidence

        result: Dict[str, dict] = {}
        for d, info in sorted(domains.items(), key=lambda x: x[1]['count'], reverse=True):
            result[d] = {
                'count': info['count'],
                'avg_confidence': round(info['total_confidence'] / info['count'], 4) if info['count'] else 0.0,
            }
        return result

    def reclassify_domains(self) -> int:
        """Reclassify domains for all nodes that have no domain set.

        Returns:
            Number of nodes reclassified.
        """
        count = 0
        for node in self.nodes.values():
            if not node.domain:
                node.domain = classify_domain(node.content)
                count += 1
        if count:
            logger.info(f"Reclassified domains for {count} nodes")
        return count

    def detect_contradictions(self, new_node_id: int, max_checks: int = 20) -> int:
        """Scan for potential contradictions between a new node and existing ones.

        Checks for numeric value conflicts and opposing assertions
        in nodes of the same domain.

        Args:
            new_node_id: The newly-added node to check.
            max_checks: Max existing nodes to compare against.

        Returns:
            Number of contradiction edges created.
        """
        new_node = self.nodes.get(new_node_id)
        if not new_node or new_node.node_type not in ('assertion', 'inference'):
            return 0

        new_text = str(new_node.content.get('text', '')).lower()
        if not new_text:
            return 0

        created = 0
        # Find nodes in the same domain to compare
        candidates = [
            n for n in self.nodes.values()
            if n.node_id != new_node_id
            and n.node_type in ('assertion', 'inference')
            and (n.domain == new_node.domain or not new_node.domain)
            and n.content.get('text')
        ]
        # Sort by most recent first
        candidates.sort(key=lambda n: n.source_block, reverse=True)
        candidates = candidates[:max_checks]

        for existing in candidates:
            existing_text = str(existing.content.get('text', '')).lower()
            if not existing_text:
                continue

            # Check for numeric value conflicts
            import re
            new_numbers = set(re.findall(r'\b\d+\.?\d*\b', new_text))
            existing_numbers = set(re.findall(r'\b\d+\.?\d*\b', existing_text))

            # Same subject (high word overlap) but different numbers
            new_words = set(new_text.split())
            existing_words = set(existing_text.split())
            overlap = len(new_words & existing_words)
            total = len(new_words | existing_words)
            word_similarity = overlap / total if total > 0 else 0

            if (word_similarity > 0.4
                    and new_numbers and existing_numbers
                    and new_numbers != existing_numbers
                    and len(new_numbers & existing_numbers) == 0):
                # Likely contradiction: same subject, different numeric values
                edge = self.add_edge(
                    new_node_id, existing.node_id, 'contradicts', weight=0.7
                )
                if edge:
                    created += 1
                if created >= 3:
                    break

        if created:
            logger.info(
                f"Detected {created} potential contradictions for node {new_node_id}"
            )
        return created

    def get_stats(self) -> dict:
        """Get knowledge graph statistics"""
        type_counts = {}
        for node in self.nodes.values():
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1

        edge_type_counts = {}
        for edge in self.edges:
            edge_type_counts[edge.edge_type] = edge_type_counts.get(edge.edge_type, 0) + 1

        avg_confidence = (
            sum(n.confidence for n in self.nodes.values()) / len(self.nodes)
            if self.nodes else 0.0
        )

        domain_counts = {}
        for node in self.nodes.values():
            d = node.domain or 'general'
            domain_counts[d] = domain_counts.get(d, 0) + 1

        return {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'node_types': type_counts,
            'edge_types': edge_type_counts,
            'avg_confidence': round(avg_confidence, 4),
            'domains': domain_counts,
            'knowledge_root': self.compute_knowledge_root()[:16] + '...',
        }

    def get_grounding_stats(self) -> dict:
        """Get statistics on grounded vs ungrounded knowledge nodes.

        Returns:
            Dict with total_nodes, grounded_nodes, grounding_ratio,
            and by_source breakdown.
        """
        total = len(self.nodes)
        by_source: Dict[str, int] = {}
        grounded = 0
        for node in self.nodes.values():
            if node.grounding_source:
                grounded += 1
                by_source[node.grounding_source] = by_source.get(node.grounding_source, 0) + 1

        return {
            'total_nodes': total,
            'grounded_nodes': grounded,
            'grounding_ratio': round(grounded / total, 4) if total > 0 else 0.0,
            'by_source': by_source,
        }


# --- Rust acceleration shim ---
# If aether_core (Rust/PyO3) is installed, transparently replace Python classes
# with the Rust equivalents for 10-50x speedup on hot-path operations.
try:
    from aether_core import KeterNode as _RustKeterNode  # noqa: F811
    from aether_core import KeterEdge as _RustKeterEdge  # noqa: F811
    from aether_core import KnowledgeGraph as _RustKnowledgeGraph  # noqa: F811
    KeterNode = _RustKeterNode  # type: ignore[misc]
    KeterEdge = _RustKeterEdge  # type: ignore[misc]
    KnowledgeGraph = _RustKnowledgeGraph  # type: ignore[misc]
    logger.info("KnowledgeGraph: using Rust-accelerated aether_core backend")
except ImportError:
    logger.debug("aether_core not installed — using pure-Python KnowledgeGraph")
