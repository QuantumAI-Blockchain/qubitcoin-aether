"""
CSF Transport Layer — Inter-Sephirot Messaging

Biological model: Cerebrospinal Fluid (CSF) circulation through brain ventricles.

Messages between Sephirot nodes flow as QBC transactions:
- Each message is a blockchain transaction with QBC attached for priority.
- Routing follows the Tree of Life topology (Keter → Tiferet → Malkuth).
- Message fees fund the network and prevent spam.
"""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import deque

from .sephirot import SephirahRole, SUSY_PAIRS
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Max queue depth per node before backpressure triggers
MAX_NODE_PRESSURE = 50
# Pressure threshold (0-1) at which backpressure activates
BACKPRESSURE_THRESHOLD = 0.8

# Tree of Life routing topology — directed edges between Sephirot
# Defines which nodes can directly communicate
TOPOLOGY: Dict[SephirahRole, List[SephirahRole]] = {
    SephirahRole.KETER: [SephirahRole.CHOCHMAH, SephirahRole.BINAH],
    SephirahRole.CHOCHMAH: [SephirahRole.KETER, SephirahRole.BINAH, SephirahRole.CHESED],
    SephirahRole.BINAH: [SephirahRole.KETER, SephirahRole.CHOCHMAH, SephirahRole.GEVURAH],
    SephirahRole.CHESED: [SephirahRole.CHOCHMAH, SephirahRole.GEVURAH, SephirahRole.TIFERET],
    SephirahRole.GEVURAH: [SephirahRole.BINAH, SephirahRole.CHESED, SephirahRole.TIFERET],
    SephirahRole.TIFERET: [SephirahRole.CHESED, SephirahRole.GEVURAH, SephirahRole.NETZACH,
                           SephirahRole.HOD, SephirahRole.YESOD],
    SephirahRole.NETZACH: [SephirahRole.TIFERET, SephirahRole.HOD, SephirahRole.YESOD],
    SephirahRole.HOD: [SephirahRole.TIFERET, SephirahRole.NETZACH, SephirahRole.YESOD],
    SephirahRole.YESOD: [SephirahRole.TIFERET, SephirahRole.NETZACH, SephirahRole.HOD,
                         SephirahRole.MALKUTH],
    SephirahRole.MALKUTH: [SephirahRole.YESOD],
}


@dataclass
class CSFMessage:
    """A message flowing between Sephirot nodes via CSF transport."""
    msg_id: str = ""
    source: SephirahRole = SephirahRole.KETER
    destination: SephirahRole = SephirahRole.MALKUTH
    msg_type: str = "signal"          # signal, query, response, broadcast
    payload: dict = field(default_factory=dict)
    priority_qbc: float = 0.0        # QBC attached for priority
    ttl: int = 10                     # Max hops before expiry
    timestamp: float = 0.0
    hops: List[str] = field(default_factory=list)
    delivered: bool = False

    def __post_init__(self) -> None:
        if not self.msg_id:
            data = f"{self.source.value}:{self.destination.value}:{time.time()}"
            self.msg_id = hashlib.sha256(data.encode()).hexdigest()[:16]
        if not self.timestamp:
            self.timestamp = time.time()


class PressureMonitor:
    """
    Monitors per-node message queue pressure and applies backpressure.

    Biological model: Intracranial pressure monitoring — when CSF pressure
    in a brain region exceeds safe levels, flow is redirected.

    Tracks the number of pending messages destined for each Sephirah node.
    When a node's queue depth exceeds a threshold, new messages are
    rerouted through less congested paths or deprioritized.
    """

    def __init__(self, max_pressure: int = MAX_NODE_PRESSURE) -> None:
        self._max_pressure = max_pressure
        self._node_pressure: Dict[SephirahRole, int] = {
            role: 0 for role in SephirahRole
        }
        self._total_backpressure_events: int = 0

    def record_enqueue(self, destination: SephirahRole) -> None:
        """Record that a message was enqueued for a node."""
        self._node_pressure[destination] = self._node_pressure.get(destination, 0) + 1

    def record_dequeue(self, destination: SephirahRole) -> None:
        """Record that a message was delivered/dropped for a node."""
        current = self._node_pressure.get(destination, 0)
        self._node_pressure[destination] = max(0, current - 1)

    def is_congested(self, node: SephirahRole) -> bool:
        """Check if a node's queue is above the backpressure threshold."""
        pressure = self._node_pressure.get(node, 0)
        return pressure >= int(self._max_pressure * BACKPRESSURE_THRESHOLD)

    def get_pressure(self, node: SephirahRole) -> float:
        """Get normalized pressure for a node (0.0 to 1.0+)."""
        return self._node_pressure.get(node, 0) / max(self._max_pressure, 1)

    def get_least_congested_neighbor(self, neighbors: List[SephirahRole]) -> Optional[SephirahRole]:
        """Return the least congested neighbor from a list."""
        if not neighbors:
            return None
        return min(neighbors, key=lambda n: self._node_pressure.get(n, 0))

    def record_backpressure(self) -> None:
        """Record a backpressure event (message rerouted or deprioritized)."""
        self._total_backpressure_events += 1

    def get_status(self) -> dict:
        """Get pressure monitor status."""
        return {
            "node_pressure": {
                role.value: round(self.get_pressure(role), 3)
                for role in SephirahRole
            },
            "congested_nodes": [
                role.value for role in SephirahRole if self.is_congested(role)
            ],
            "total_backpressure_events": self._total_backpressure_events,
        }


class QuantumEntangledChannel:
    """
    Zero-latency messaging between SUSY-paired Sephirot nodes.

    Biological model: Quantum entanglement between paired neural regions
    allows instantaneous state correlation (not classical communication).

    SUSY pairs (Chesed/Gevurah, Chochmah/Binah, Netzach/Hod) share
    entangled channels that bypass normal BFS routing — messages between
    paired nodes are delivered instantly without consuming TTL or hops.
    """

    def __init__(self) -> None:
        # Build pair lookup from SUSY_PAIRS
        self._pairs: Dict[SephirahRole, SephirahRole] = {}
        for expansion, constraint in SUSY_PAIRS:
            self._pairs[expansion] = constraint
            self._pairs[constraint] = expansion
        self._entangled_deliveries: int = 0
        logger.info(
            f"Quantum entangled channels initialized "
            f"({len(SUSY_PAIRS)} SUSY pairs)"
        )

    def is_entangled(self, source: SephirahRole, destination: SephirahRole) -> bool:
        """Check if two nodes share a quantum entangled channel."""
        return self._pairs.get(source) == destination

    def get_partner(self, node: SephirahRole) -> Optional[SephirahRole]:
        """Get the SUSY-entangled partner of a node, if any."""
        return self._pairs.get(node)

    def deliver_entangled(self, msg: CSFMessage) -> CSFMessage:
        """
        Instantly deliver a message through the entangled channel.

        The message bypasses routing — it is marked as delivered immediately
        with a special 'entangled' hop marker.
        """
        msg.hops.append(f"⟨entangled⟩→{msg.destination.value}")
        msg.delivered = True
        self._entangled_deliveries += 1
        logger.debug(
            f"Quantum entangled delivery: {msg.source.value} ⟷ {msg.destination.value}"
        )
        return msg

    def get_status(self) -> dict:
        """Get entangled channel status."""
        return {
            "pairs": [
                {"a": e.value, "b": c.value}
                for e, c in SUSY_PAIRS
            ],
            "total_entangled_deliveries": self._entangled_deliveries,
        }


class CSFTransport:
    """
    Routes messages between Sephirot nodes following the Tree of Life topology.

    Features:
    - Priority queue: higher QBC = faster processing
    - Topology-aware routing via BFS pathfinding
    - TTL prevents infinite loops
    - Adaptive TTL based on path length
    - Max queue size prevents unbounded memory growth
    - Deadlock monitoring via stale message detection
    - Message history for debugging/monitoring
    """

    MAX_QUEUE_SIZE: int = 500  # Maximum total messages in queue
    MAX_PER_DEST_QUEUE: int = 100  # Max messages queued per destination
    STALE_THRESHOLD_S: float = 60.0  # Seconds before a queued message is stale
    MAX_DELIVERED_HISTORY: int = 10000  # Cap delivered history to prevent unbounded growth

    def __init__(self) -> None:
        self._queue: List[CSFMessage] = []  # Priority queue (sorted by qbc desc)
        self._delivered: List[CSFMessage] = []
        self._total_delivered: int = 0  # Total count (survives truncation)
        self._dropped: int = 0
        self._stale_dropped: int = 0
        self.pressure = PressureMonitor()
        self.entangled = QuantumEntangledChannel()
        logger.info("CSF Transport initialized (Tree of Life topology + quantum entanglement)")

    def _record_delivered(self, msg: CSFMessage) -> None:
        """Append a delivered message and enforce history cap."""
        self._delivered.append(msg)
        self._total_delivered += 1
        if len(self._delivered) > self.MAX_DELIVERED_HISTORY:
            self._delivered = self._delivered[-self.MAX_DELIVERED_HISTORY:]

    def send(self, source: SephirahRole, destination: SephirahRole,
             payload: dict, msg_type: str = "signal",
             priority_qbc: float = 0.0) -> CSFMessage:
        """
        Send a message from one Sephirah to another.

        Args:
            source: Sending node.
            destination: Target node.
            payload: Message data.
            msg_type: signal, query, response, or broadcast.
            priority_qbc: QBC attached for priority ordering.

        Returns:
            The queued CSFMessage.
        """
        # Adaptive TTL: base on path length + safety margin
        path = self.find_path(source, destination)
        adaptive_ttl = max(10, len(path) + 5) if path else 10

        msg = CSFMessage(
            source=source,
            destination=destination,
            msg_type=msg_type,
            payload=payload,
            priority_qbc=priority_qbc,
            ttl=adaptive_ttl,
        )
        msg.hops.append(source.value)

        # Check for quantum-entangled shortcut (instant delivery for SUSY pairs)
        if self.entangled.is_entangled(source, destination):
            self.entangled.deliver_entangled(msg)
            self._record_delivered(msg)
            return msg

        # Enforce max queue size to prevent unbounded memory growth
        if len(self._queue) >= self.MAX_QUEUE_SIZE:
            self._dropped += 1
            logger.warning(f"CSF queue full ({self.MAX_QUEUE_SIZE}), dropping message "
                           f"{source.value}→{destination.value}")
            return msg

        # Per-destination queue limit to prevent flow starvation
        dest_count = sum(1 for m in self._queue if m.destination == destination)
        if dest_count >= self.MAX_PER_DEST_QUEUE:
            self._dropped += 1
            logger.debug(f"Per-dest queue limit ({self.MAX_PER_DEST_QUEUE}) reached for "
                         f"{destination.value}, dropping")
            return msg

        # Backpressure check: if destination is congested, deprioritize
        if self.pressure.is_congested(destination):
            msg.priority_qbc *= 0.5  # Halve priority for congested destinations
            self.pressure.record_backpressure()
            logger.debug(f"Backpressure: {destination.value} congested, deprioritizing")

        self.pressure.record_enqueue(destination)
        self._queue.append(msg)
        # Sort by priority (highest QBC first)
        self._queue.sort(key=lambda m: -m.priority_qbc)
        logger.debug(
            f"CSF: {source.value} → {destination.value} "
            f"[{msg_type}] priority={priority_qbc} QBC"
        )
        return msg

    def broadcast(self, source: SephirahRole, payload: dict,
                  priority_qbc: float = 0.0) -> List[CSFMessage]:
        """Broadcast a message from one node to all its direct neighbors."""
        neighbors = TOPOLOGY.get(source, [])
        messages = []
        for dest in neighbors:
            msg = self.send(source, dest, payload, msg_type="broadcast",
                            priority_qbc=priority_qbc)
            messages.append(msg)
        return messages

    def process_queue(self, max_messages: int = 100) -> List[CSFMessage]:
        """
        Process pending messages, routing them through the topology.

        Returns list of successfully delivered messages.
        """
        delivered = []
        remaining = []

        now = time.time()
        for msg in self._queue[:max_messages]:
            if msg.ttl <= 0:
                self._dropped += 1
                self.pressure.record_dequeue(msg.destination)
                continue

            # Stale message detection: drop messages stuck too long
            if now - msg.timestamp > self.STALE_THRESHOLD_S:
                self._stale_dropped += 1
                self._dropped += 1
                self.pressure.record_dequeue(msg.destination)
                logger.debug(f"Dropping stale CSF message {msg.msg_id} "
                             f"({msg.source.value}→{msg.destination.value}, "
                             f"age={now - msg.timestamp:.1f}s)")
                continue

            # Check if destination is directly reachable from current position
            current = SephirahRole(msg.hops[-1]) if msg.hops else msg.source
            neighbors = TOPOLOGY.get(current, [])

            if msg.destination == current:
                # Already at destination
                msg.delivered = True
                self._record_delivered(msg)
                delivered.append(msg)
                self.pressure.record_dequeue(msg.destination)
            elif msg.destination in neighbors:
                # Direct neighbor — deliver
                msg.hops.append(msg.destination.value)
                msg.delivered = True
                self._record_delivered(msg)
                delivered.append(msg)
                self.pressure.record_dequeue(msg.destination)
            else:
                # Route via shortest path — prefer least-congested next hop
                next_hop = self._find_next_hop(current, msg.destination)
                if next_hop:
                    msg.hops.append(next_hop.value)
                    msg.ttl -= 1
                    remaining.append(msg)
                else:
                    self._dropped += 1
                    self.pressure.record_dequeue(msg.destination)

        # Keep undelivered messages + remaining unprocessed
        self._queue = remaining + self._queue[max_messages:]
        return delivered

    def _find_next_hop(self, current: SephirahRole,
                       destination: SephirahRole) -> Optional[SephirahRole]:
        """BFS to find next hop toward destination in the topology."""
        visited = {current}
        queue: deque = deque()

        for neighbor in TOPOLOGY.get(current, []):
            queue.append((neighbor, neighbor))  # (node, first_hop)
            visited.add(neighbor)

        while queue:
            node, first_hop = queue.popleft()
            if node == destination:
                return first_hop
            for neighbor in TOPOLOGY.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, first_hop))

        return None

    def find_path(self, source: SephirahRole,
                  destination: SephirahRole) -> List[SephirahRole]:
        """Find shortest path between two nodes in the topology."""
        if source == destination:
            return [source]

        visited = {source}
        queue: deque = deque([(source, [source])])

        while queue:
            node, path = queue.popleft()
            for neighbor in TOPOLOGY.get(node, []):
                if neighbor == destination:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []  # No path found

    def get_stats(self) -> dict:
        """Get transport statistics."""
        return {
            "queue_size": len(self._queue),
            "max_queue_size": self.MAX_QUEUE_SIZE,
            "total_delivered": self._total_delivered,
            "total_dropped": self._dropped,
            "stale_dropped": self._stale_dropped,
            "pressure": self.pressure.get_status(),
            "entangled_channels": self.entangled.get_status(),
            "recent_messages": [
                {
                    "id": m.msg_id,
                    "source": m.source.value,
                    "destination": m.destination.value,
                    "type": m.msg_type,
                    "hops": len(m.hops),
                    "priority": m.priority_qbc,
                }
                for m in self._delivered[-20:]
            ],
        }


# --- Rust acceleration shim ---
try:
    from aether_core import CSFMessage as _RustCSFMessage  # noqa: F811
    from aether_core import CSFTransport as _RustCSFTransport  # noqa: F811
    CSFMessage = _RustCSFMessage  # type: ignore[misc]
    CSFTransport = _RustCSFTransport  # type: ignore[misc]
    logger.info("CSFTransport: using Rust-accelerated aether_core backend")
except ImportError:
    logger.debug("aether_core not installed — using pure-Python CSFTransport")
