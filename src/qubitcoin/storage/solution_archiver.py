"""
IPFS archival of SUSY Hamiltonian solution datasets.

Periodically exports solved Hamiltonians from the `solved_hamiltonians`
table to JSON, uploads to IPFS, and stores CIDs for retrieval by
researchers and external systems.
"""
import time
import hashlib
import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ArchiveRecord:
    """Record of a completed solution archive upload."""
    archive_id: str
    from_height: int
    to_height: int
    solution_count: int
    cid: Optional[str]      # IPFS CID (None if IPFS unavailable)
    size_bytes: int
    duration_s: float
    success: bool
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            'archive_id': self.archive_id,
            'from_height': self.from_height,
            'to_height': self.to_height,
            'solution_count': self.solution_count,
            'cid': self.cid,
            'size_bytes': self.size_bytes,
            'duration_s': round(self.duration_s, 3),
            'success': self.success,
            'error': self.error,
            'created_at': self.created_at,
        }


class SolutionArchiver:
    """Archives SUSY Hamiltonian solutions to IPFS.

    Provides both periodic (interval-based) and on-demand archival
    of solved Hamiltonians for the public scientific database.

    Usage:
        archiver = SolutionArchiver(interval_blocks=1000)

        # Periodic check (called from mining loop):
        archiver.on_new_block(height=1000, db_manager=db, ipfs_manager=ipfs)

        # On-demand export:
        record = archiver.archive_range(0, 500, db_manager=db, ipfs_manager=ipfs)

        # Query history:
        records = archiver.get_history()
    """

    def __init__(
        self,
        interval_blocks: int = 1000,
        max_history: int = 200,
    ):
        self._interval = interval_blocks
        self._max_history = max_history
        self._lock = threading.Lock()
        self._history: List[ArchiveRecord] = []
        self._last_archive_height: int = -1
        self._total_archives: int = 0
        self._total_solutions_archived: int = 0
        logger.info(f"Solution archiver initialized (interval={interval_blocks} blocks)")

    def should_archive(self, current_height: int) -> bool:
        """Check if an archive is due at this height."""
        if current_height <= 0:
            return False
        if current_height <= self._last_archive_height:
            return False
        return current_height % self._interval == 0

    def on_new_block(
        self,
        height: int,
        db_manager: object,
        ipfs_manager: Optional[object] = None,
    ) -> Optional[ArchiveRecord]:
        """Called after each new block. Archives if interval is met.

        Archives solutions from last_archive_height+1 to current height.
        """
        if not self.should_archive(height):
            return None
        from_h = max(self._last_archive_height + 1, 0)
        return self.archive_range(from_h, height, db_manager, ipfs_manager)

    def archive_range(
        self,
        from_height: int,
        to_height: int,
        db_manager: object,
        ipfs_manager: Optional[object] = None,
    ) -> ArchiveRecord:
        """Archive solutions in a block height range.

        Args:
            from_height: Start block height (inclusive).
            to_height: End block height (inclusive).
            db_manager: DatabaseManager instance.
            ipfs_manager: Optional IPFSManager instance.

        Returns:
            ArchiveRecord with result metadata.
        """
        start = time.monotonic()
        archive_id = hashlib.sha256(
            f"archive:{from_height}:{to_height}:{time.time()}".encode()
        ).hexdigest()[:16]

        logger.info(f"Archiving solutions from height {from_height} to {to_height}")

        try:
            # Query solutions
            solutions = self._query_solutions(db_manager, from_height, to_height)
            solution_count = len(solutions)

            if solution_count == 0:
                logger.info(f"No solutions in range [{from_height}, {to_height}]")

            # Build archive payload
            payload = {
                'version': '1.0',
                'type': 'susy_solution_archive',
                'timestamp': time.time(),
                'from_height': from_height,
                'to_height': to_height,
                'solution_count': solution_count,
                'solutions': solutions,
            }

            size_bytes = self._estimate_size(payload)

            # Upload to IPFS
            cid = None
            if ipfs_manager is not None and solution_count > 0:
                cid = self._upload(ipfs_manager, payload)

            duration = time.monotonic() - start
            record = ArchiveRecord(
                archive_id=archive_id,
                from_height=from_height,
                to_height=to_height,
                solution_count=solution_count,
                cid=cid,
                size_bytes=size_bytes,
                duration_s=duration,
                success=True,
            )

            with self._lock:
                self._history.append(record)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]
                self._last_archive_height = to_height
                self._total_archives += 1
                self._total_solutions_archived += solution_count

            logger.info(
                f"Archive complete: {solution_count} solutions, "
                f"cid={cid}, {size_bytes} bytes, {duration:.2f}s"
            )
            return record

        except Exception as e:
            duration = time.monotonic() - start
            record = ArchiveRecord(
                archive_id=archive_id,
                from_height=from_height,
                to_height=to_height,
                solution_count=0,
                cid=None,
                size_bytes=0,
                duration_s=duration,
                success=False,
                error=str(e),
            )
            with self._lock:
                self._history.append(record)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]

            logger.error(f"Archive failed: {e}")
            return record

    def _query_solutions(
        self, db_manager: object, from_height: int, to_height: int
    ) -> List[dict]:
        """Query solved Hamiltonians from the database."""
        from sqlalchemy import text as sa_text

        solutions = []
        try:
            with db_manager.get_session() as session:  # type: ignore[attr-defined]
                rows = session.execute(
                    sa_text(
                        "SELECT id, hamiltonian, params, energy, miner_address, block_height "
                        "FROM solved_hamiltonians "
                        "WHERE block_height >= :from_h AND block_height <= :to_h "
                        "ORDER BY block_height"
                    ),
                    {'from_h': from_height, 'to_h': to_height},
                ).fetchall()
                for r in rows:
                    solutions.append({
                        'id': r[0],
                        'hamiltonian': r[1],
                        'params': r[2],
                        'energy': float(r[3]) if r[3] is not None else None,
                        'miner_address': r[4],
                        'block_height': r[5],
                    })
        except Exception as e:
            logger.warning(f"Solution query failed (may not have DB): {e}")
        return solutions

    def _upload(self, ipfs_manager: object, payload: dict) -> Optional[str]:
        """Upload archive payload to IPFS."""
        try:
            client = getattr(ipfs_manager, 'client', None)
            if client is None:
                return None
            cid = client.add_json(payload)
            logger.info(f"Archive uploaded to IPFS: {cid}")
            return cid
        except Exception as e:
            logger.warning(f"IPFS upload failed: {e}")
            return None

    @staticmethod
    def _estimate_size(data: dict) -> int:
        """Estimate payload size in bytes."""
        import json
        try:
            return len(json.dumps(data, default=str).encode())
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 20) -> List[dict]:
        """Get recent archive history."""
        with self._lock:
            recent = self._history[-limit:]
        return [r.to_dict() for r in recent]

    def get_latest(self) -> Optional[ArchiveRecord]:
        """Get the most recent archive record."""
        with self._lock:
            return self._history[-1] if self._history else None

    def get_all_cids(self) -> List[str]:
        """Get all IPFS CIDs from successful archives."""
        with self._lock:
            return [r.cid for r in self._history if r.cid is not None]

    def get_stats(self) -> dict:
        """Aggregate archive statistics."""
        with self._lock:
            return {
                'total_archives': self._total_archives,
                'total_solutions_archived': self._total_solutions_archived,
                'last_archive_height': self._last_archive_height,
                'interval_blocks': self._interval,
                'history_size': len(self._history),
                'cids_stored': sum(1 for r in self._history if r.cid is not None),
            }
