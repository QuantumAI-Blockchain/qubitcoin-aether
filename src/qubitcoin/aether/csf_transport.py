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

from .sephirot import SephirahRole
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

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


class CSFTransport:
    """
    Routes messages between Sephirot nodes following the Tree of Life topology.

    Features:
    - Priority queue: higher QBC = faster processing
    - Topology-aware routing via BFS pathfinding
    - TTL prevents infinite loops
    - Message history for debugging/monitoring
    """

    def __init__(self) -> None:
        self._queue: List[CSFMessage] = []  # Priority queue (sorted by qbc desc)
        self._delivered: List[CSFMessage] = []
        self._dropped: int = 0
        logger.info("CSF Transport initialized (Tree of Life topology)")

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
        msg = CSFMessage(
            source=source,
            destination=destination,
            msg_type=msg_type,
            payload=payload,
            priority_qbc=priority_qbc,
        )
        msg.hops.append(source.value)
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

        for msg in self._queue[:max_messages]:
            if msg.ttl <= 0:
                self._dropped += 1
                continue

            # Check if destination is directly reachable from current position
            current = SephirahRole(msg.hops[-1]) if msg.hops else msg.source
            neighbors = TOPOLOGY.get(current, [])

            if msg.destination == current:
                # Already at destination
                msg.delivered = True
                self._delivered.append(msg)
                delivered.append(msg)
            elif msg.destination in neighbors:
                # Direct neighbor — deliver
                msg.hops.append(msg.destination.value)
                msg.delivered = True
                self._delivered.append(msg)
                delivered.append(msg)
            else:
                # Route via shortest path
                next_hop = self._find_next_hop(current, msg.destination)
                if next_hop:
                    msg.hops.append(next_hop.value)
                    msg.ttl -= 1
                    remaining.append(msg)
                else:
                    self._dropped += 1

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
            "total_delivered": len(self._delivered),
            "total_dropped": self._dropped,
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
