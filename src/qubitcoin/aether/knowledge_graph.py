"""
Knowledge Graph - KeterNode System
Manages the decentralized knowledge graph that forms the foundation of the Aether Tree.
Each node (KeterNode) represents a piece of verified knowledge; edges represent relationships.
"""
import hashlib
import json
import math
import time
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
    node_type: str = 'assertion'  # assertion, observation, inference, axiom
    content_hash: str = ''
    content: dict = field(default_factory=dict)
    confidence: float = 0.5  # [0.0, 1.0]
    source_block: int = 0
    timestamp: float = 0.0
    # In-memory graph links
    edges_out: List[int] = field(default_factory=list)
    edges_in: List[int] = field(default_factory=list)

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
    edge_type: str = 'supports'  # supports, contradicts, derives, requires, refines
    weight: float = 1.0
    timestamp: float = 0.0


class KnowledgeGraph:
    """
    In-memory knowledge graph backed by database persistence.
    Supports CRUD operations, graph traversal, and root hash computation.
    """

    def __init__(self, db_manager):
        self.db = db_manager
        self.nodes: Dict[int, KeterNode] = {}
        self.edges: List[KeterEdge] = []
        self._next_id = 1
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
                    if r[0] in self.nodes:
                        self.nodes[r[0]].edges_out.append(r[1])
                    if r[1] in self.nodes:
                        self.nodes[r[1]].edges_in.append(r[0])

            logger.info(f"Knowledge graph loaded: {len(self.nodes)} nodes, {len(self.edges)} edges")
        except Exception as e:
            logger.debug(f"Knowledge graph load: {e}")

    def add_node(self, node_type: str, content: dict, confidence: float,
                 source_block: int) -> KeterNode:
        """Add a new knowledge node"""
        node = KeterNode(
            node_id=self._next_id,
            node_type=node_type,
            content=content,
            confidence=max(0.0, min(1.0, confidence)),
            source_block=source_block,
            timestamp=time.time(),
        )
        node.content_hash = node.calculate_hash()
        self._next_id += 1
        self.nodes[node.node_id] = node

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
        if from_id not in self.nodes or to_id not in self.nodes:
            logger.warning(f"Cannot add edge: node {from_id} or {to_id} not found")
            return None

        edge = KeterEdge(
            from_node_id=from_id, to_node_id=to_id,
            edge_type=edge_type, weight=weight,
            timestamp=time.time()
        )
        self.edges.append(edge)
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
        queue = [(root_id, 0)]

        while queue:
            nid, d = queue.pop(0)
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
                for edge in self.edges:
                    if edge.to_node_id != nid:
                        continue
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
        """
        if not self.nodes:
            return hashlib.sha256(b'empty_knowledge').hexdigest()

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

        return leaves[0]

    def prune_low_confidence(self, threshold: float = 0.1, protect_types: Optional[Set[str]] = None) -> int:
        """
        Remove nodes with confidence below threshold.

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

        for nid in to_remove:
            # Remove edges referencing this node
            self.edges = [
                e for e in self.edges
                if e.from_node_id != nid and e.to_node_id != nid
            ]
            # Clean up neighbor references in remaining nodes
            for other_node in self.nodes.values():
                if nid in other_node.edges_out:
                    other_node.edges_out.remove(nid)
                if nid in other_node.edges_in:
                    other_node.edges_in.remove(nid)
            del self.nodes[nid]

        if to_remove:
            logger.info(f"Pruned {len(to_remove)} low-confidence nodes (threshold={threshold})")

        return len(to_remove)

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
        """Get all edges grouped by type for a specific node."""
        result: Dict[str, List[int]] = {}
        for edge in self.edges:
            if edge.from_node_id == node_id:
                result.setdefault(f"out_{edge.edge_type}", []).append(edge.to_node_id)
            if edge.to_node_id == node_id:
                result.setdefault(f"in_{edge.edge_type}", []).append(edge.from_node_id)
        return result

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

        return {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'node_types': type_counts,
            'edge_types': edge_type_counts,
            'avg_confidence': round(avg_confidence, 4),
            'knowledge_root': self.compute_knowledge_root()[:16] + '...',
        }
