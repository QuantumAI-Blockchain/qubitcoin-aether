"""
IPFS Integration for Aether Tree Long-Term Memory

Provides persistence for episodic and semantic memories on IPFS.
Memories are serialized as JSON, pinned on IPFS, and the resulting
CID is stored in the MemoryItem's ipfs_hash field.

This enables:
  - Durable, content-addressed memory storage
  - Cross-node memory sharing (any node can retrieve by CID)
  - Archival of old memories that exceed local capacity
  - Tamper-proof memory provenance via CID verification
"""
import hashlib
import json
import time
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class IPFSMemoryStore:
    """Store and retrieve Aether memories on IPFS.

    Wraps the IPFSManager to provide memory-specific operations.
    When IPFS is unavailable, falls back to local-only storage
    without raising errors.
    """

    def __init__(self, ipfs_manager: object = None) -> None:
        """
        Args:
            ipfs_manager: An IPFSManager instance (from storage/ipfs.py).
                          If None, operates in local-only fallback mode.
        """
        self._ipfs = ipfs_manager
        self._local_cache: Dict[str, dict] = {}  # cid -> memory_data
        self._max_cache = 5000
        self._store_count: int = 0
        self._retrieve_count: int = 0

    @property
    def ipfs_available(self) -> bool:
        """Check if IPFS client is connected."""
        if self._ipfs and hasattr(self._ipfs, 'client') and self._ipfs.client:
            return True
        return False

    def store_memory(self, memory_id: str, memory_type: str,
                     content: str, source_block: int,
                     confidence: float = 1.0,
                     metadata: Optional[dict] = None) -> str:
        """Store a memory item on IPFS.

        Args:
            memory_id: Unique memory identifier.
            memory_type: Type of memory (episodic, semantic, etc.).
            content: Memory content text.
            source_block: Block height where memory originated.
            confidence: Confidence score.
            metadata: Additional metadata.

        Returns:
            CID (content identifier) string. If IPFS is unavailable,
            returns a local hash that can be used for cache lookup.
        """
        memory_data = {
            'memory_id': memory_id,
            'memory_type': memory_type,
            'content': content,
            'source_block': source_block,
            'confidence': confidence,
            'metadata': metadata or {},
            'stored_at': time.time(),
            'chain_id': Config.CHAIN_ID,
        }

        serialized = json.dumps(memory_data, sort_keys=True)

        # Try IPFS first
        if self.ipfs_available:
            try:
                result = self._ipfs.client.add_json(memory_data)
                cid = result if isinstance(result, str) else str(result)
                self._cache_locally(cid, memory_data)
                self._store_count += 1
                logger.debug(f"Memory stored on IPFS: {cid[:12]}... ({memory_type})")
                return cid
            except Exception as e:
                logger.warning(f"IPFS store failed, using local fallback: {e}")

        # Fallback: generate local CID from content hash
        local_cid = 'local:' + hashlib.sha256(serialized.encode()).hexdigest()[:32]
        self._cache_locally(local_cid, memory_data)
        self._store_count += 1
        return local_cid

    def retrieve_memory(self, cid: str) -> Optional[dict]:
        """Retrieve a memory item by its CID.

        Args:
            cid: Content identifier (IPFS CID or local hash).

        Returns:
            Memory data dict or None if not found.
        """
        # Check local cache first
        if cid in self._local_cache:
            self._retrieve_count += 1
            return self._local_cache[cid]

        # Try IPFS if it's a real CID (not local)
        if self.ipfs_available and not cid.startswith('local:'):
            try:
                data = self._ipfs.client.get_json(cid)
                if data:
                    self._cache_locally(cid, data)
                    self._retrieve_count += 1
                    return data
            except Exception as e:
                logger.debug(f"IPFS retrieve failed for {cid[:12]}...: {e}")

        return None

    def store_batch(self, memories: List[dict]) -> List[str]:
        """Store multiple memories at once.

        Args:
            memories: List of dicts with keys: memory_id, memory_type,
                      content, source_block, confidence, metadata.

        Returns:
            List of CIDs for stored memories.
        """
        cids: List[str] = []
        for mem in memories:
            cid = self.store_memory(
                memory_id=mem.get('memory_id', ''),
                memory_type=mem.get('memory_type', 'episodic'),
                content=mem.get('content', ''),
                source_block=mem.get('source_block', 0),
                confidence=mem.get('confidence', 1.0),
                metadata=mem.get('metadata'),
            )
            cids.append(cid)
        return cids

    def pin_memory(self, cid: str) -> bool:
        """Pin a memory on IPFS to prevent garbage collection.

        Args:
            cid: The IPFS CID to pin.

        Returns:
            True if pinned successfully.
        """
        if not self.ipfs_available or cid.startswith('local:'):
            return False

        try:
            self._ipfs.client.pin.add(cid)
            logger.debug(f"Memory pinned on IPFS: {cid[:12]}...")
            return True
        except Exception as e:
            logger.debug(f"IPFS pin failed for {cid[:12]}...: {e}")
            return False

    def _cache_locally(self, cid: str, data: dict) -> None:
        """Add to local cache with eviction."""
        self._local_cache[cid] = data
        if len(self._local_cache) > self._max_cache:
            # Evict oldest entry
            oldest = next(iter(self._local_cache))
            del self._local_cache[oldest]

    def list_cached(self, limit: int = 100) -> List[dict]:
        """List locally cached memories.

        Returns:
            List of dicts with cid and memory_type.
        """
        items = list(self._local_cache.items())[-limit:]
        return [
            {
                'cid': cid,
                'memory_id': data.get('memory_id', ''),
                'memory_type': data.get('memory_type', ''),
                'source_block': data.get('source_block', 0),
            }
            for cid, data in reversed(items)
        ]

    def get_stats(self) -> dict:
        """Get IPFS memory store statistics."""
        return {
            'ipfs_available': self.ipfs_available,
            'local_cache_size': len(self._local_cache),
            'max_cache': self._max_cache,
            'total_stored': self._store_count,
            'total_retrieved': self._retrieve_count,
        }
