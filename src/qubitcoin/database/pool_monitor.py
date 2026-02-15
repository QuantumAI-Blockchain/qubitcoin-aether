"""
Connection pool health monitoring for CockroachDB.

Tracks pool utilization, checkout latency, overflow events,
and connection errors to detect resource exhaustion before it
causes outages.
"""
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PoolSnapshot:
    """Point-in-time snapshot of pool health."""
    timestamp: float
    pool_size: int
    checked_in: int
    checked_out: int
    overflow: int
    checkedout_pct: float
    avg_checkout_ms: float
    total_checkouts: int
    total_errors: int
    total_timeouts: int
    status: str  # healthy | degraded | critical

    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'pool_size': self.pool_size,
            'checked_in': self.checked_in,
            'checked_out': self.checked_out,
            'overflow': self.overflow,
            'checkedout_pct': round(self.checkedout_pct, 2),
            'avg_checkout_ms': round(self.avg_checkout_ms, 3),
            'total_checkouts': self.total_checkouts,
            'total_errors': self.total_errors,
            'total_timeouts': self.total_timeouts,
            'status': self.status,
        }


class PoolHealthMonitor:
    """Monitors SQLAlchemy connection pool health metrics.

    Attach to a DatabaseManager's engine to track connection usage
    patterns and detect problems early.

    Usage:
        monitor = PoolHealthMonitor(engine)
        snapshot = monitor.get_snapshot()
        history  = monitor.get_history(limit=10)
    """

    # Thresholds for health status
    DEGRADED_UTILIZATION = 0.75   # >75% checked out
    CRITICAL_UTILIZATION = 0.90   # >90% checked out
    DEGRADED_LATENCY_MS = 100.0   # avg checkout > 100ms
    CRITICAL_LATENCY_MS = 500.0   # avg checkout > 500ms

    def __init__(self, engine: Optional[object] = None, max_history: int = 500):
        self._engine = engine
        self._max_history = max_history
        self._lock = threading.Lock()

        # Counters
        self._total_checkouts: int = 0
        self._total_checkins: int = 0
        self._total_errors: int = 0
        self._total_timeouts: int = 0
        self._total_invalidated: int = 0

        # Latency tracking (rolling window)
        self._checkout_latencies: List[float] = []
        self._max_latency_samples = 200
        self._pending_checkouts: Dict[int, float] = {}  # conn_id -> start_time

        # History
        self._snapshots: List[PoolSnapshot] = []

        # Attach listeners if engine provided
        if engine is not None:
            self._attach_listeners(engine)

        logger.info("Pool health monitor initialized")

    def _attach_listeners(self, engine: object) -> None:
        """Attach SQLAlchemy pool event listeners."""
        try:
            from sqlalchemy import event as sa_event
            pool = engine.pool  # type: ignore[attr-defined]
            sa_event.listen(pool, 'checkout', self._on_checkout)
            sa_event.listen(pool, 'checkin', self._on_checkin)
            sa_event.listen(pool, 'invalidate', self._on_invalidate)
            logger.info("Pool event listeners attached")
        except Exception as e:
            logger.warning(f"Could not attach pool listeners: {e}")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_checkout(self, dbapi_conn: object, connection_record: object,
                     connection_proxy: object) -> None:
        """Called when a connection is checked out from the pool."""
        conn_id = id(dbapi_conn)
        with self._lock:
            self._total_checkouts += 1
            self._pending_checkouts[conn_id] = time.monotonic()

    def _on_checkin(self, dbapi_conn: object, connection_record: object) -> None:
        """Called when a connection is returned to the pool."""
        conn_id = id(dbapi_conn)
        with self._lock:
            self._total_checkins += 1
            start = self._pending_checkouts.pop(conn_id, None)
            if start is not None:
                latency_ms = (time.monotonic() - start) * 1000.0
                self._checkout_latencies.append(latency_ms)
                if len(self._checkout_latencies) > self._max_latency_samples:
                    self._checkout_latencies = self._checkout_latencies[
                        -self._max_latency_samples:
                    ]

    def _on_invalidate(self, dbapi_conn: object,
                       connection_record: object, exception: object) -> None:
        """Called when a connection is invalidated (error)."""
        with self._lock:
            self._total_invalidated += 1
            self._total_errors += 1

    # ------------------------------------------------------------------
    # Manual event recording (for non-engine usage or testing)
    # ------------------------------------------------------------------

    def record_checkout(self) -> None:
        """Manually record a connection checkout."""
        with self._lock:
            self._total_checkouts += 1

    def record_checkin(self, latency_ms: float = 0.0) -> None:
        """Manually record a connection checkin with optional latency."""
        with self._lock:
            self._total_checkins += 1
            if latency_ms > 0:
                self._checkout_latencies.append(latency_ms)
                if len(self._checkout_latencies) > self._max_latency_samples:
                    self._checkout_latencies = self._checkout_latencies[
                        -self._max_latency_samples:
                    ]

    def record_error(self) -> None:
        """Manually record a connection error."""
        with self._lock:
            self._total_errors += 1

    def record_timeout(self) -> None:
        """Manually record a checkout timeout."""
        with self._lock:
            self._total_timeouts += 1

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def _get_pool_stats(self) -> dict:
        """Read live pool stats from engine (if available)."""
        if self._engine is None:
            return {'pool_size': 0, 'checked_in': 0, 'checked_out': 0, 'overflow': 0}
        try:
            pool = self._engine.pool  # type: ignore[attr-defined]
            return {
                'pool_size': pool.size(),
                'checked_in': pool.checkedin(),
                'checked_out': pool.checkedout(),
                'overflow': pool.overflow(),
            }
        except Exception:
            return {'pool_size': 0, 'checked_in': 0, 'checked_out': 0, 'overflow': 0}

    def _compute_status(self, utilization: float, avg_latency_ms: float) -> str:
        """Determine health status from utilization and latency."""
        if utilization >= self.CRITICAL_UTILIZATION or avg_latency_ms >= self.CRITICAL_LATENCY_MS:
            return 'critical'
        if utilization >= self.DEGRADED_UTILIZATION or avg_latency_ms >= self.DEGRADED_LATENCY_MS:
            return 'degraded'
        return 'healthy'

    def get_snapshot(self) -> PoolSnapshot:
        """Take a current health snapshot and store in history."""
        pool = self._get_pool_stats()
        with self._lock:
            total_capacity = pool['pool_size'] + pool['overflow'] if pool['pool_size'] > 0 else 1
            utilization = pool['checked_out'] / total_capacity if total_capacity > 0 else 0.0
            avg_lat = (
                sum(self._checkout_latencies) / len(self._checkout_latencies)
                if self._checkout_latencies else 0.0
            )
            status = self._compute_status(utilization, avg_lat)

            snap = PoolSnapshot(
                timestamp=time.time(),
                pool_size=pool['pool_size'],
                checked_in=pool['checked_in'],
                checked_out=pool['checked_out'],
                overflow=pool['overflow'],
                checkedout_pct=utilization * 100,
                avg_checkout_ms=avg_lat,
                total_checkouts=self._total_checkouts,
                total_errors=self._total_errors,
                total_timeouts=self._total_timeouts,
                status=status,
            )
            self._snapshots.append(snap)
            if len(self._snapshots) > self._max_history:
                self._snapshots = self._snapshots[-self._max_history:]
            return snap

    def get_history(self, limit: int = 20) -> List[dict]:
        """Return recent snapshots as dicts."""
        with self._lock:
            recent = self._snapshots[-limit:]
        return [s.to_dict() for s in recent]

    def get_stats(self) -> dict:
        """Aggregate statistics."""
        with self._lock:
            avg_lat = (
                sum(self._checkout_latencies) / len(self._checkout_latencies)
                if self._checkout_latencies else 0.0
            )
            max_lat = max(self._checkout_latencies) if self._checkout_latencies else 0.0
            return {
                'total_checkouts': self._total_checkouts,
                'total_checkins': self._total_checkins,
                'total_errors': self._total_errors,
                'total_timeouts': self._total_timeouts,
                'total_invalidated': self._total_invalidated,
                'avg_checkout_latency_ms': round(avg_lat, 3),
                'max_checkout_latency_ms': round(max_lat, 3),
                'latency_samples': len(self._checkout_latencies),
                'history_size': len(self._snapshots),
            }

    def is_healthy(self) -> bool:
        """Quick boolean health check."""
        snap = self.get_snapshot()
        return snap.status == 'healthy'
