#!/usr/bin/env python3
"""
Bulk-load existing KG nodes into the Aether Graph Shard Service.

Runs inside the qbc-node container (or anywhere with access to both
the node RPC and shard gRPC). Reads all nodes from the KG via the
internal Python API, then streams them to the shard service in batches.

Usage (inside container):
    python3 /app/scripts/bulk_load_shards.py

Usage (from host):
    docker exec qbc-node python3 /app/scripts/bulk_load_shards.py
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time

# Add src to path when running inside container
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from qubitcoin.utils.logger import get_logger

logger = get_logger("bulk_load_shards")

SHARD_ADDR = os.environ.get("GRAPH_SHARD_ADDR", "graph-shard:50053")
BATCH_SIZE = 500


async def main():
    """Load all KG nodes into the shard service."""
    # Import shard client
    from qubitcoin.aether.shard_client import GraphShardClient

    client = GraphShardClient(SHARD_ADDR, timeout=30.0)
    connected = await client.connect()
    if not connected:
        logger.error("Cannot connect to shard service at %s", SHARD_ADDR)
        sys.exit(1)

    # Get current shard stats
    stats = await client.get_stats()
    logger.info("Shard service stats before load: %s", stats)

    # Connect to the node's RPC to get KG data
    import aiohttp

    node_url = os.environ.get("NODE_RPC_URL", "http://localhost:5000")

    async with aiohttp.ClientSession() as session:
        # Get all knowledge nodes via the dump endpoint
        logger.info("Fetching knowledge graph from %s...", node_url)
        async with session.get(f"{node_url}/aether/knowledge/dump", timeout=aiohttp.ClientTimeout(total=300)) as resp:
            if resp.status != 200:
                logger.error("Failed to get KG dump: %s", resp.status)
                # Fallback: use internal Python API directly
                await _load_from_internal_api(client)
                return
            data = await resp.json()

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    logger.info("Got %d nodes and %d edges from KG dump", len(nodes), len(edges))

    if not nodes:
        logger.info("No nodes to load. Done.")
        return

    # Bulk load nodes in batches
    total_loaded = 0
    t0 = time.time()

    for i in range(0, len(nodes), BATCH_SIZE):
        batch = nodes[i:i + BATCH_SIZE]
        batch_records = []
        for n in batch:
            content = n.get("content", {})
            if isinstance(content, str):
                content = {"text": content}
            batch_records.append({
                "node_id": n.get("node_id", 0),
                "node_type": n.get("node_type", "observation"),
                "content": {str(k): str(v) for k, v in content.items()},
                "confidence": n.get("confidence", 0.5),
                "source_block": n.get("source_block", 0),
                "domain": n.get("domain", "general"),
                "grounding_source": n.get("grounding_source", ""),
            })

        result = await client.bulk_put_nodes(batch_records)
        if result:
            total_loaded += result.get("nodes_written", 0)
            elapsed = time.time() - t0
            rate = total_loaded / elapsed if elapsed > 0 else 0
            logger.info(
                "Loaded %d/%d nodes (%.0f nodes/sec, %d errors)",
                total_loaded, len(nodes), rate, result.get("errors", 0)
            )
        else:
            logger.warning("Batch %d-%d failed", i, i + BATCH_SIZE)

    # Load edges
    logger.info("Loading %d edges...", len(edges))
    edge_count = 0
    for e in edges:
        ok = await client.put_edge(
            from_id=e.get("from_id", e.get("from_node_id", 0)),
            to_id=e.get("to_id", e.get("to_node_id", 0)),
            edge_type=e.get("edge_type", "supports"),
            weight=e.get("weight", 1.0),
        )
        if ok:
            edge_count += 1
        if edge_count % 1000 == 0 and edge_count > 0:
            logger.info("Loaded %d/%d edges", edge_count, len(edges))

    elapsed = time.time() - t0
    logger.info(
        "Bulk load complete: %d nodes, %d edges in %.1fs",
        total_loaded, edge_count, elapsed
    )

    # Final stats
    stats = await client.get_stats()
    logger.info("Shard stats after load: %s", stats)
    await client.close()


async def _load_from_internal_api(client):
    """Fallback: load directly from the Python KG if RPC dump isn't available."""
    logger.info("Using internal Python API to load nodes...")

    try:
        from qubitcoin.aether.knowledge_graph import KnowledgeGraph
    except ImportError:
        logger.error("Cannot import KnowledgeGraph. Run inside the node container.")
        return

    # Can't instantiate a new KG here — we'd need the running instance.
    # Instead, use the database directly.
    from qubitcoin.database.manager import DatabaseManager
    from qubitcoin.config import Config

    config = Config()
    db = DatabaseManager(config)

    logger.info("Loading nodes from CockroachDB...")
    nodes = []
    async with db.session() as session:
        from sqlalchemy import text
        result = await session.execute(text(
            "SELECT node_id, node_type, content_hash, content, confidence, "
            "source_block, timestamp, domain, last_referenced_block, "
            "reference_count, grounding_source "
            "FROM agi.knowledge_nodes ORDER BY node_id"
        ))
        for row in result:
            nodes.append({
                "node_id": row[0],
                "node_type": row[1],
                "content": json.loads(row[3]) if isinstance(row[3], str) else row[3],
                "confidence": float(row[4]),
                "source_block": row[5],
                "domain": row[7] or "general",
                "grounding_source": row[10] or "",
            })

    logger.info("Got %d nodes from DB, starting bulk load...", len(nodes))

    t0 = time.time()
    total = 0
    for i in range(0, len(nodes), BATCH_SIZE):
        batch = nodes[i:i + BATCH_SIZE]
        result = await client.bulk_put_nodes(batch)
        if result:
            total += result.get("nodes_written", 0)
            logger.info("Loaded %d/%d", total, len(nodes))

    logger.info("DB load complete: %d nodes in %.1fs", total, time.time() - t0)
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
