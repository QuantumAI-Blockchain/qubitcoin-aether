"""
gRPC client for the distributed Aether Graph Shard Service.

Designed for trillion-node scale with domain-based sharding.
Each shard runs RocksDB + LRU cache + incremental Merkle tree.

Usage:
    client = GraphShardClient("localhost:50053")
    await client.connect()
    shard_id = await client.put_node(node_data)
    node = await client.get_node(node_id)
    results = await client.search("quantum entanglement", top_k=10)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import grpc

from qubitcoin.utils.logger import get_logger

logger = get_logger(__name__)

# Lazy import of generated stubs
_pb2 = None
_pb2_grpc = None
_STUBS_LOADED = False


def _load_stubs():
    global _pb2, _pb2_grpc, _STUBS_LOADED
    if _STUBS_LOADED:
        return
    try:
        from qubitcoin.aether.graph_shard_pb import graph_shard_pb2, graph_shard_pb2_grpc
        _pb2 = graph_shard_pb2
        _pb2_grpc = graph_shard_pb2_grpc
        _STUBS_LOADED = True
    except ImportError as e:
        logger.warning("Graph shard gRPC stubs not available: %s", e)


class GraphShardClient:
    """Async gRPC client for the Aether Graph Shard Service."""

    def __init__(self, address: str = "localhost:50053", timeout: float = 5.0):
        self.address = address
        self.timeout = timeout
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to the shard service."""
        _load_stubs()
        if not _STUBS_LOADED:
            logger.warning("Cannot connect: gRPC stubs not available")
            return False

        try:
            self._channel = grpc.aio.insecure_channel(
                self.address,
                options=[
                    ("grpc.max_send_message_length", 64 * 1024 * 1024),
                    ("grpc.max_receive_message_length", 64 * 1024 * 1024),
                    ("grpc.keepalive_time_ms", 30000),
                    ("grpc.keepalive_timeout_ms", 10000),
                ],
            )
            self._stub = _pb2_grpc.GraphShardServiceStub(self._channel)

            # Health check
            resp = await self._stub.HealthCheck(
                _pb2.HealthRequest(), timeout=self.timeout
            )
            self._connected = resp.healthy
            logger.info(
                "Graph Shard connected at %s: %d shards online",
                self.address,
                resp.shards_online,
            )
            return self._connected
        except Exception as e:
            logger.warning("Graph Shard connection failed: %s", e)
            self._connected = False
            return False

    async def close(self):
        """Close the gRPC channel."""
        if self._channel:
            await self._channel.close()
            self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Node Operations ────────────────────────────────────────────

    async def put_node(
        self,
        node_id: int,
        node_type: str,
        content: dict[str, str],
        confidence: float,
        source_block: int,
        domain: str,
        grounding_source: str = "",
        embedding: Optional[list[float]] = None,
    ) -> Optional[int]:
        """Put a node into the distributed graph. Returns shard_id."""
        if not self._connected:
            return None

        try:
            import hashlib
            import json

            content_hash = hashlib.sha256(
                json.dumps(content, sort_keys=True).encode()
            ).hexdigest()

            record = _pb2.NodeRecord(
                node_id=node_id,
                node_type=node_type,
                content_hash=content_hash,
                content=content,
                confidence=confidence,
                source_block=source_block,
                timestamp=time.time(),
                domain=domain,
                last_referenced_block=source_block,
                reference_count=0,
                grounding_source=grounding_source,
                embedding=embedding or [],
            )

            resp = await self._stub.PutNode(
                _pb2.PutNodeRequest(node=record), timeout=self.timeout
            )
            return resp.shard_id
        except Exception as e:
            logger.warning("put_node failed: %s", e)
            return None

    async def get_node(self, node_id: int) -> Optional[dict[str, Any]]:
        """Get a node by ID from the distributed graph."""
        if not self._connected:
            return None

        try:
            resp = await self._stub.GetNode(
                _pb2.GetNodeRequest(node_id=node_id), timeout=self.timeout
            )
            if resp.found and resp.node:
                return _node_to_dict(resp.node)
            return None
        except Exception as e:
            logger.warning("get_node failed: %s", e)
            return None

    async def get_nodes(self, node_ids: list[int]) -> list[dict[str, Any]]:
        """Get multiple nodes by ID."""
        if not self._connected:
            return []

        try:
            resp = await self._stub.GetNodes(
                _pb2.GetNodesRequest(node_ids=node_ids), timeout=self.timeout
            )
            return [_node_to_dict(n) for n in resp.nodes]
        except Exception as e:
            logger.warning("get_nodes failed: %s", e)
            return []

    async def delete_node(self, node_id: int, cascade: bool = True) -> bool:
        """Delete a node (and optionally its edges)."""
        if not self._connected:
            return False

        try:
            resp = await self._stub.DeleteNode(
                _pb2.DeleteNodeRequest(node_id=node_id, cascade_edges=cascade),
                timeout=self.timeout,
            )
            return resp.deleted
        except Exception as e:
            logger.warning("delete_node failed: %s", e)
            return False

    async def update_confidence(
        self, node_id: int, confidence: float, block_height: int
    ) -> Optional[float]:
        """Update a node's confidence. Returns old confidence."""
        if not self._connected:
            return None

        try:
            resp = await self._stub.UpdateConfidence(
                _pb2.UpdateConfidenceRequest(
                    node_id=node_id,
                    new_confidence=confidence,
                    block_height=block_height,
                ),
                timeout=self.timeout,
            )
            return resp.old_confidence if resp.updated else None
        except Exception as e:
            logger.warning("update_confidence failed: %s", e)
            return None

    # ── Edge Operations ────────────────────────────────────────────

    async def put_edge(
        self,
        from_id: int,
        to_id: int,
        edge_type: str,
        weight: float = 1.0,
    ) -> bool:
        """Add an edge between two nodes."""
        if not self._connected:
            return False

        try:
            record = _pb2.EdgeRecord(
                from_node_id=from_id,
                to_node_id=to_id,
                edge_type=edge_type,
                weight=weight,
                timestamp=time.time(),
            )
            resp = await self._stub.PutEdge(
                _pb2.PutEdgeRequest(edge=record), timeout=self.timeout
            )
            return resp.created
        except Exception as e:
            logger.warning("put_edge failed: %s", e)
            return False

    async def get_edges(
        self,
        node_id: int,
        direction: str = "outgoing",
        edge_type_filter: str = "",
    ) -> list[dict[str, Any]]:
        """Get edges for a node."""
        if not self._connected:
            return []

        try:
            dir_map = {"outgoing": 0, "incoming": 1, "both": 2}
            resp = await self._stub.GetEdges(
                _pb2.GetEdgesRequest(
                    node_id=node_id,
                    direction=dir_map.get(direction, 0),
                    edge_type_filter=edge_type_filter,
                ),
                timeout=self.timeout,
            )
            return [_edge_to_dict(e) for e in resp.edges]
        except Exception as e:
            logger.warning("get_edges failed: %s", e)
            return []

    # ── Search ─────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        top_k: int = 10,
        domain_filter: str = "",
        min_confidence: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search nodes by keyword."""
        if not self._connected:
            return []

        try:
            resp = await self._stub.Search(
                _pb2.SearchRequest(
                    query=query,
                    top_k=top_k,
                    domain_filter=domain_filter,
                    min_confidence=min_confidence,
                ),
                timeout=self.timeout,
            )
            return [
                {"node": _node_to_dict(r.node), "score": r.score, "match_type": r.match_type}
                for r in resp.results
                if r.node
            ]
        except Exception as e:
            logger.warning("search failed: %s", e)
            return []

    async def cross_domain_search(
        self,
        domains: list[str],
        query: str,
        top_k_per_domain: int = 10,
        min_confidence: float = 0.0,
        merge: bool = True,
    ) -> dict[str, Any]:
        """Search across multiple domain shards."""
        if not self._connected:
            return {}

        try:
            resp = await self._stub.CrossDomainSearch(
                _pb2.CrossDomainSearchRequest(
                    domains=domains,
                    query=query,
                    top_k_per_domain=top_k_per_domain,
                    min_confidence=min_confidence,
                    merge_results=merge,
                ),
                timeout=self.timeout * 2,  # Cross-domain takes longer
            )
            result: dict[str, Any] = {
                "latency_ms": resp.total_latency_ms,
                "per_domain": {},
            }
            for domain, dr in resp.per_domain.items():
                result["per_domain"][domain] = [
                    {"node": _node_to_dict(r.node), "score": r.score}
                    for r in dr.results
                    if r.node
                ]
            if merge:
                result["merged"] = [
                    {"node": _node_to_dict(r.node), "score": r.score}
                    for r in resp.merged
                    if r.node
                ]
            return result
        except Exception as e:
            logger.warning("cross_domain_search failed: %s", e)
            return {}

    # ── Merkle & Stats ─────────────────────────────────────────────

    async def get_merkle_root(self) -> Optional[str]:
        """Get the global Merkle root across all shards."""
        if not self._connected:
            return None

        try:
            resp = await self._stub.GetMerkleRoot(
                _pb2.MerkleRootRequest(), timeout=self.timeout
            )
            return resp.global_root
        except Exception as e:
            logger.warning("get_merkle_root failed: %s", e)
            return None

    async def get_stats(self) -> Optional[dict[str, Any]]:
        """Get global graph statistics."""
        if not self._connected:
            return None

        try:
            resp = await self._stub.GetStats(
                _pb2.StatsRequest(), timeout=self.timeout
            )
            return {
                "total_nodes": resp.total_nodes,
                "total_edges": resp.total_edges,
                "nodes_per_domain": dict(resp.nodes_per_domain),
                "active_shards": resp.active_shards,
                "cache_hit_rate": resp.cache_hit_rate,
                "merkle_root": resp.merkle_root,
            }
        except Exception as e:
            logger.warning("get_stats failed: %s", e)
            return None

    async def compact(
        self,
        shard_id: Optional[int] = None,
        min_confidence: float = 0.1,
    ) -> Optional[dict[str, Any]]:
        """Compact shards by removing low-value nodes."""
        if not self._connected:
            return None

        try:
            resp = await self._stub.CompactShard(
                _pb2.CompactRequest(
                    shard_id=shard_id or 0,
                    all_shards=shard_id is None,
                    min_confidence=min_confidence,
                ),
                timeout=60.0,  # Compaction can take time
            )
            return {
                "nodes_pruned": resp.nodes_pruned,
                "bytes_reclaimed": resp.bytes_reclaimed,
                "duration_ms": resp.duration_ms,
            }
        except Exception as e:
            logger.warning("compact failed: %s", e)
            return None

    # ── Bulk Operations ────────────────────────────────────────────

    async def bulk_put_nodes(
        self, nodes: list[dict[str, Any]]
    ) -> Optional[dict[str, Any]]:
        """Bulk insert nodes via streaming RPC."""
        if not self._connected:
            return None

        try:
            import hashlib
            import json

            async def node_stream():
                for n in nodes:
                    content = {str(k): str(v) for k, v in n.get("content", {}).items()}
                    content_hash = hashlib.sha256(
                        json.dumps(content, sort_keys=True).encode()
                    ).hexdigest()

                    record = _pb2.NodeRecord(
                        node_id=n["node_id"],
                        node_type=n.get("node_type", "observation"),
                        content_hash=content_hash,
                        content=content,
                        confidence=n.get("confidence", 0.5),
                        source_block=n.get("source_block", 0),
                        timestamp=time.time(),
                        domain=n.get("domain", "general"),
                        grounding_source=n.get("grounding_source", ""),
                    )
                    yield _pb2.PutNodeRequest(node=record)

            resp = await self._stub.BulkPutNodes(
                node_stream(), timeout=300.0
            )
            return {
                "nodes_written": resp.nodes_written,
                "errors": resp.errors,
                "duration_ms": resp.duration_ms,
            }
        except Exception as e:
            logger.warning("bulk_put_nodes failed: %s", e)
            return None


# ── Helper conversions ─────────────────────────────────────────────

def _node_to_dict(record) -> dict[str, Any]:
    """Convert a proto NodeRecord to a Python dict."""
    return {
        "node_id": record.node_id,
        "node_type": record.node_type,
        "content_hash": record.content_hash,
        "content": dict(record.content),
        "confidence": record.confidence,
        "source_block": record.source_block,
        "timestamp": record.timestamp,
        "domain": record.domain,
        "last_referenced_block": record.last_referenced_block,
        "reference_count": record.reference_count,
        "grounding_source": record.grounding_source,
        "edges_out": list(record.edges_out),
        "edges_in": list(record.edges_in),
    }


def _edge_to_dict(record) -> dict[str, Any]:
    """Convert a proto EdgeRecord to a Python dict."""
    return {
        "from_node_id": record.from_node_id,
        "to_node_id": record.to_node_id,
        "edge_type": record.edge_type,
        "weight": record.weight,
        "timestamp": record.timestamp,
    }
