"""
QVM Event Log Index — In-memory + DB-backed event storage with topic-based filtering

Provides the ``EventIndex`` class that:
  * Stores events emitted by LOG0-LOG4 opcodes during QVM execution.
  * Supports efficient filtering by contract address, topic[0]-topic[3],
    and block range — matching the ``eth_getLogs`` JSON-RPC interface.
  * Persists events to CockroachDB ``event_logs`` table when a database
    manager is available.
  * Keeps a bounded in-memory cache of recent events for fast queries.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Maximum events retained in the in-memory cache.
_DEFAULT_CACHE_SIZE = 50_000


@dataclass
class EventLog:
    """Single event log entry emitted by a LOG0-LOG4 opcode."""

    address: str               # Contract address that emitted the event
    data: str                  # Hex-encoded event data payload
    topics: List[str]          # 0-4 hex-encoded 32-byte topics
    block_height: int          # Block in which the event was emitted
    block_hash: str = ''       # Hash of the containing block
    tx_hash: str = ''          # Transaction hash
    tx_index: int = 0          # Transaction index within the block
    log_index: int = 0         # Log index within the transaction

    def to_eth_log(self) -> Dict[str, Any]:
        """Return the event in ``eth_getLogs`` response format."""
        return {
            'address': '0x' + self.address,
            'data': '0x' + (self.data or ''),
            'topics': ['0x' + t for t in self.topics],
            'blockNumber': hex(self.block_height),
            'blockHash': '0x' + self.block_hash,
            'transactionHash': '0x' + self.tx_hash,
            'transactionIndex': hex(self.tx_index),
            'logIndex': hex(self.log_index),
            'removed': False,
        }


class EventIndex:
    """In-memory event log index with optional CockroachDB persistence.

    Events are indexed by contract address and topic[0] for fast lookups.
    Older events are evicted from memory once the cache exceeds
    *max_cache_size*; they remain accessible via the database fallback.
    """

    def __init__(self, db_manager=None, max_cache_size: int = _DEFAULT_CACHE_SIZE) -> None:
        self.db = db_manager
        self._max_cache_size = max_cache_size

        # Primary storage: ordered list of all cached events
        self._events: List[EventLog] = []

        # Secondary indices — map to positions in ``_events``
        self._by_address: Dict[str, List[int]] = {}
        self._by_topic0: Dict[str, List[int]] = {}

    # ── Insertion ─────────────────────────────────────────────────────

    def add_event(
        self,
        address: str,
        data: str,
        topics: List[str],
        block_height: int,
        block_hash: str = '',
        tx_hash: str = '',
        tx_index: int = 0,
        log_index: int = 0,
    ) -> EventLog:
        """Index a new event log entry.

        Args:
            address: Contract address (hex, no 0x prefix).
            data: Hex-encoded event data.
            topics: List of 0-4 hex-encoded topic strings (no 0x prefix).
            block_height: Block number.
            block_hash: Block hash (hex, no 0x prefix).
            tx_hash: Transaction hash (hex, no 0x prefix).
            tx_index: Transaction index in block.
            log_index: Log index within the transaction.

        Returns:
            The stored ``EventLog`` instance.
        """
        event = EventLog(
            address=address,
            data=data,
            topics=list(topics),
            block_height=block_height,
            block_hash=block_hash,
            tx_hash=tx_hash,
            tx_index=tx_index,
            log_index=log_index,
        )

        idx = len(self._events)
        self._events.append(event)

        # Build secondary indices
        addr_lower = address.lower()
        self._by_address.setdefault(addr_lower, []).append(idx)
        if topics:
            self._by_topic0.setdefault(topics[0].lower(), []).append(idx)

        # Persist to DB
        self._persist(event)

        # Evict oldest entries when cache is full
        if len(self._events) > self._max_cache_size:
            self._evict()

        return event

    def add_from_log_dict(
        self,
        log: Dict[str, Any],
        block_height: int,
        block_hash: str = '',
        tx_hash: str = '',
        tx_index: int = 0,
        log_index: int = 0,
    ) -> EventLog:
        """Convenience: add an event from the dict format produced by QVM LOG opcodes.

        Expected keys: ``address``, ``data``, ``topic0``..``topic3``.
        """
        topics: List[str] = []
        for i in range(4):
            t = log.get(f'topic{i}')
            if t:
                topics.append(t)

        return self.add_event(
            address=log.get('address', ''),
            data=log.get('data', ''),
            topics=topics,
            block_height=block_height,
            block_hash=block_hash,
            tx_hash=tx_hash,
            tx_index=tx_index,
            log_index=log_index,
        )

    # ── Querying ──────────────────────────────────────────────────────

    def get_logs(
        self,
        from_block: int = 0,
        to_block: Optional[int] = None,
        address: Optional[str] = None,
        topics: Optional[List[Optional[str]]] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Query events matching the given filter, compatible with eth_getLogs.

        Args:
            from_block: Start of block range (inclusive).
            to_block: End of block range (inclusive). None = latest.
            address: Filter by contract address (hex, no 0x prefix).
            topics: List of up to 4 topic filters.  Each element is either
                a hex string (exact match), or None (match any).
                ``topics[0]`` is the event signature hash.
            limit: Maximum number of results.

        Returns:
            List of log dicts in eth_getLogs format.
        """
        # Try memory-first query
        results = self._query_memory(from_block, to_block, address, topics, limit)

        # If memory has no results covering the range, fall back to DB
        if not results and self.db:
            results = self._query_db(from_block, to_block, address, topics, limit)

        return results

    def _query_memory(
        self,
        from_block: int,
        to_block: Optional[int],
        address: Optional[str],
        topics: Optional[List[Optional[str]]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Filter events from the in-memory cache."""
        # Narrow candidate set using indices
        candidates: Optional[List[int]] = None

        if address:
            addr_lower = address.lower()
            addr_indices = self._by_address.get(addr_lower)
            if addr_indices is None:
                return []
            candidates = set(addr_indices)

        if topics and topics[0]:
            t0_lower = topics[0].lower()
            t0_indices = self._by_topic0.get(t0_lower)
            if t0_indices is None:
                return []
            t0_set = set(t0_indices)
            candidates = t0_set if candidates is None else candidates & t0_set

        results: List[Dict[str, Any]] = []
        indices = sorted(candidates) if candidates is not None else range(len(self._events))

        for idx in indices:
            if idx >= len(self._events):
                continue
            ev = self._events[idx]

            # Block range filter
            if ev.block_height < from_block:
                continue
            if to_block is not None and ev.block_height > to_block:
                continue

            # Topic matching (positions 1-3 if specified)
            if topics and not self._match_topics(ev.topics, topics):
                continue

            results.append(ev.to_eth_log())
            if len(results) >= limit:
                break

        return results

    def _query_db(
        self,
        from_block: int,
        to_block: Optional[int],
        address: Optional[str],
        topics: Optional[List[Optional[str]]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Fall back to querying the ``event_logs`` table in CockroachDB."""
        if not self.db:
            return []

        try:
            with self.db.get_session() as session:
                from sqlalchemy import text as sql_text

                query = (
                    "SELECT txid, log_index, contract_address, "
                    "topic0, topic1, topic2, topic3, data, block_height "
                    "FROM event_logs WHERE block_height >= :from_b"
                )
                params: Dict[str, Any] = {'from_b': from_block}

                if to_block is not None:
                    query += " AND block_height <= :to_b"
                    params['to_b'] = to_block

                if address:
                    query += " AND contract_address = :addr"
                    params['addr'] = address.lower()

                if topics:
                    for i, t in enumerate(topics):
                        if t:
                            col = f'topic{i}'
                            key = f't{i}'
                            query += f" AND {col} = :{key}"
                            params[key] = t.replace('0x', '').lower()

                query += f" ORDER BY block_height, log_index LIMIT {limit}"

                rows = session.execute(sql_text(query), params)
                results: List[Dict[str, Any]] = []
                for r in rows:
                    t_list = []
                    for t in [r[3], r[4], r[5], r[6]]:
                        if t:
                            t_list.append('0x' + t)
                    results.append({
                        'transactionHash': '0x' + r[0],
                        'logIndex': hex(r[1]),
                        'address': '0x' + r[2],
                        'data': '0x' + (r[7] or ''),
                        'topics': t_list,
                        'blockNumber': hex(r[8]),
                        'blockHash': '0x',
                        'transactionIndex': '0x0',
                        'removed': False,
                    })
                return results
        except Exception as e:
            logger.debug(f"EventIndex DB query failed: {e}")
            return []

    @staticmethod
    def _match_topics(event_topics: List[str], filter_topics: List[Optional[str]]) -> bool:
        """Check if event topics satisfy a filter.

        Each position in *filter_topics* is either a hex string (must match
        exactly, case-insensitive) or ``None`` (wildcard / match any).
        If the event has fewer topics than the filter specifies, non-None
        filter positions beyond the event's topics cause a mismatch.
        """
        for i, ft in enumerate(filter_topics):
            if ft is None:
                continue
            if i >= len(event_topics):
                return False
            if event_topics[i].lower() != ft.lower():
                return False
        return True

    # ── Persistence ───────────────────────────────────────────────────

    def _persist(self, event: EventLog) -> None:
        """Write an event to the ``event_logs`` table if DB is available."""
        if not self.db:
            return
        try:
            with self.db.get_session() as session:
                from sqlalchemy import text as sql_text
                session.execute(
                    sql_text("""
                        INSERT INTO event_logs
                            (txid, log_index, contract_address,
                             topic0, topic1, topic2, topic3,
                             data, block_height)
                        VALUES (:txid, :li, :ca, :t0, :t1, :t2, :t3, :data, :bh)
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        'txid': event.tx_hash,
                        'li': event.log_index,
                        'ca': event.address,
                        't0': event.topics[0] if len(event.topics) > 0 else None,
                        't1': event.topics[1] if len(event.topics) > 1 else None,
                        't2': event.topics[2] if len(event.topics) > 2 else None,
                        't3': event.topics[3] if len(event.topics) > 3 else None,
                        'data': event.data,
                        'bh': event.block_height,
                    },
                )
                session.commit()
        except Exception as e:
            logger.debug(f"EventIndex persist skipped: {e}")

    # ── Cache maintenance ─────────────────────────────────────────────

    def _evict(self) -> None:
        """Remove the oldest 25% of cached events and rebuild indices."""
        cutoff = len(self._events) // 4
        self._events = self._events[cutoff:]
        self._rebuild_indices()

    def _rebuild_indices(self) -> None:
        """Rebuild secondary indices from the current events list."""
        self._by_address.clear()
        self._by_topic0.clear()
        for idx, ev in enumerate(self._events):
            addr_lower = ev.address.lower()
            self._by_address.setdefault(addr_lower, []).append(idx)
            if ev.topics:
                self._by_topic0.setdefault(ev.topics[0].lower(), []).append(idx)

    # ── Stats ─────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Return index statistics."""
        return {
            'cached_events': len(self._events),
            'indexed_addresses': len(self._by_address),
            'indexed_topic0s': len(self._by_topic0),
            'max_cache_size': self._max_cache_size,
        }
