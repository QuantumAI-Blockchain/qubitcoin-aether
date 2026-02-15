"""
Blockchain snapshot scheduler for periodic IPFS archival.

Extends the IPFSManager with a background scheduler that automatically
creates blockchain snapshots at configurable intervals and tracks
snapshot history with metadata.
"""
import time
import threading
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SnapshotRecord:
    """Metadata record for a completed snapshot."""
    snapshot_id: str
    block_height: int
    cid: Optional[str]          # IPFS CID (None if IPFS unavailable)
    chain_hash: Optional[str]   # Hash of the chain tip at snapshot time
    block_count: int
    utxo_count: int
    tx_count: int
    size_estimate_bytes: int
    duration_s: float
    success: bool
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            'snapshot_id': self.snapshot_id,
            'block_height': self.block_height,
            'cid': self.cid,
            'chain_hash': self.chain_hash,
            'block_count': self.block_count,
            'utxo_count': self.utxo_count,
            'tx_count': self.tx_count,
            'size_estimate_bytes': self.size_estimate_bytes,
            'duration_s': round(self.duration_s, 3),
            'success': self.success,
            'error': self.error,
            'created_at': self.created_at,
        }


class SnapshotScheduler:
    """Manages periodic blockchain snapshots to IPFS.

    Works with or without a live IPFS daemon — when IPFS is unavailable,
    snapshots are built in-memory and recorded locally without upload.

    Usage:
        scheduler = SnapshotScheduler(interval_blocks=1000)
        # Called from the mining loop after each block:
        scheduler.on_new_block(height=100, db_manager=db, ipfs_manager=ipfs)

        # Or manually trigger:
        record = scheduler.take_snapshot(height=500, db_manager=db, ipfs_manager=ipfs)
    """

    def __init__(
        self,
        interval_blocks: int = 1000,
        max_history: int = 200,
    ):
        self._interval = interval_blocks
        self._max_history = max_history
        self._lock = threading.Lock()
        self._history: List[SnapshotRecord] = []
        self._last_snapshot_height: int = -1
        self._total_snapshots: int = 0
        self._total_failures: int = 0
        logger.info(f"Snapshot scheduler initialized (interval={interval_blocks} blocks)")

    @property
    def interval_blocks(self) -> int:
        return self._interval

    def should_snapshot(self, current_height: int) -> bool:
        """Check if a snapshot is due at this block height."""
        if current_height <= 0:
            return False
        if current_height <= self._last_snapshot_height:
            return False
        return current_height % self._interval == 0

    def on_new_block(
        self,
        height: int,
        db_manager: object,
        ipfs_manager: Optional[object] = None,
    ) -> Optional[SnapshotRecord]:
        """Called after each new block. Takes snapshot if interval is met.

        Args:
            height: The new block height.
            db_manager: DatabaseManager instance.
            ipfs_manager: Optional IPFSManager instance.

        Returns:
            SnapshotRecord if a snapshot was taken, else None.
        """
        if not self.should_snapshot(height):
            return None
        return self.take_snapshot(height, db_manager, ipfs_manager)

    def take_snapshot(
        self,
        height: int,
        db_manager: object,
        ipfs_manager: Optional[object] = None,
    ) -> SnapshotRecord:
        """Take a blockchain snapshot and optionally upload to IPFS.

        Args:
            height: Block height to snapshot at.
            db_manager: DatabaseManager instance.
            ipfs_manager: Optional IPFSManager instance.

        Returns:
            SnapshotRecord with result metadata.
        """
        start = time.monotonic()
        snapshot_id = hashlib.sha256(
            f"snapshot:{height}:{time.time()}".encode()
        ).hexdigest()[:16]

        logger.info(f"Taking blockchain snapshot at height {height}")

        try:
            # Build snapshot data
            snapshot_data = self._build_snapshot(height, db_manager)
            block_count = len(snapshot_data.get('blocks', []))
            utxo_count = len(snapshot_data.get('utxos', []))
            tx_count = len(snapshot_data.get('transactions', []))
            size_est = self._estimate_size(snapshot_data)
            chain_hash = snapshot_data.get('chain_hash')

            # Upload to IPFS if available
            cid = None
            if ipfs_manager is not None:
                cid = self._upload_to_ipfs(ipfs_manager, snapshot_data, db_manager, height, chain_hash)

            duration = time.monotonic() - start
            record = SnapshotRecord(
                snapshot_id=snapshot_id,
                block_height=height,
                cid=cid,
                chain_hash=chain_hash,
                block_count=block_count,
                utxo_count=utxo_count,
                tx_count=tx_count,
                size_estimate_bytes=size_est,
                duration_s=duration,
                success=True,
            )

            with self._lock:
                self._history.append(record)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]
                self._last_snapshot_height = height
                self._total_snapshots += 1

            logger.info(
                f"Snapshot complete: height={height}, blocks={block_count}, "
                f"utxos={utxo_count}, txs={tx_count}, cid={cid}, "
                f"duration={duration:.2f}s"
            )
            return record

        except Exception as e:
            duration = time.monotonic() - start
            record = SnapshotRecord(
                snapshot_id=snapshot_id,
                block_height=height,
                cid=None,
                chain_hash=None,
                block_count=0,
                utxo_count=0,
                tx_count=0,
                size_estimate_bytes=0,
                duration_s=duration,
                success=False,
                error=str(e),
            )
            with self._lock:
                self._history.append(record)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]
                self._total_failures += 1

            logger.error(f"Snapshot failed at height {height}: {e}")
            return record

    def _build_snapshot(self, height: int, db_manager: object) -> dict:
        """Build snapshot data dict from database state."""
        import json
        from sqlalchemy import text as sa_text

        blocks = []
        utxos = []
        transactions = []
        chain_hash = None

        with db_manager.get_session() as session:  # type: ignore[attr-defined]
            # Blocks
            rows = session.execute(
                sa_text(
                    "SELECT height, prev_hash, difficulty, block_hash, created_at "
                    "FROM blocks WHERE height <= :h ORDER BY height"
                ),
                {'h': height},
            ).fetchall()
            for r in rows:
                blocks.append({
                    'height': r[0], 'prev_hash': r[1],
                    'difficulty': float(r[2]) if r[2] else 0.0,
                    'block_hash': r[3],
                    'created_at': str(r[4]),
                })

            # UTXOs (unspent only)
            rows = session.execute(
                sa_text(
                    "SELECT txid, vout, amount, address, block_height "
                    "FROM utxos WHERE spent = false AND block_height <= :h"
                ),
                {'h': height},
            ).fetchall()
            for r in rows:
                utxos.append({
                    'txid': r[0], 'vout': r[1],
                    'amount': str(r[2]), 'address': r[3],
                    'block_height': r[4],
                })

            # Confirmed transactions
            rows = session.execute(
                sa_text(
                    "SELECT txid, block_height, fee "
                    "FROM transactions WHERE status = 'confirmed' AND block_height <= :h"
                ),
                {'h': height},
            ).fetchall()
            for r in rows:
                transactions.append({
                    'txid': r[0], 'block_height': r[1],
                    'fee': str(r[2]) if r[2] else '0',
                })

        # Chain hash from tip
        try:
            block = db_manager.get_block(height)  # type: ignore[attr-defined]
            if block:
                chain_hash = getattr(block, 'block_hash', None)
        except Exception:
            pass

        return {
            'version': '2.0',
            'timestamp': time.time(),
            'height': height,
            'blocks': blocks,
            'utxos': utxos,
            'transactions': transactions,
            'chain_hash': chain_hash,
        }

    def _upload_to_ipfs(
        self,
        ipfs_manager: object,
        snapshot_data: dict,
        db_manager: object,
        height: int,
        chain_hash: Optional[str],
    ) -> Optional[str]:
        """Upload snapshot to IPFS via IPFSManager."""
        try:
            client = getattr(ipfs_manager, 'client', None)
            if client is None:
                logger.debug("IPFS client not available, skipping upload")
                return None
            import json
            cid = client.add_json(snapshot_data)
            # Store record in DB
            store_fn = getattr(ipfs_manager, '_store_snapshot_record', None)
            if store_fn:
                store_fn(db_manager, cid, height, chain_hash)
            return cid
        except Exception as e:
            logger.warning(f"IPFS upload failed: {e}")
            return None

    @staticmethod
    def _estimate_size(data: dict) -> int:
        """Rough estimate of snapshot size in bytes."""
        import json
        try:
            return len(json.dumps(data, default=str).encode())
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 20) -> List[dict]:
        """Get recent snapshot history."""
        with self._lock:
            recent = self._history[-limit:]
        return [r.to_dict() for r in recent]

    def get_latest(self) -> Optional[SnapshotRecord]:
        """Get the most recent snapshot record."""
        with self._lock:
            return self._history[-1] if self._history else None

    def get_stats(self) -> dict:
        """Aggregate snapshot statistics."""
        with self._lock:
            return {
                'total_snapshots': self._total_snapshots,
                'total_failures': self._total_failures,
                'last_snapshot_height': self._last_snapshot_height,
                'interval_blocks': self._interval,
                'history_size': len(self._history),
                'success_rate': round(
                    self._total_snapshots / max(self._total_snapshots + self._total_failures, 1), 4
                ),
            }
