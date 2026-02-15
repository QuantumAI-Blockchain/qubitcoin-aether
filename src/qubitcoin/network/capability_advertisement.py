"""
P2P capability advertisement protocol.

Allows nodes to broadcast their VQE mining capabilities to peers,
enabling intelligent task routing, peer scoring based on compute
power, and network-wide capability aggregation.
"""
import time
import threading
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PeerCapability:
    """Capability record received from a peer."""
    peer_id: str
    backend_type: str       # local_estimator | aer_simulator | ibm_quantum
    max_qubits: int
    is_simulator: bool
    is_available: bool
    estimated_vqe_time_s: float
    features: Dict[str, bool] = field(default_factory=dict)
    received_at: float = field(default_factory=time.time)
    advertised_at: float = 0.0  # Timestamp from the peer

    @property
    def is_stale(self) -> bool:
        """Consider stale after 10 minutes without refresh."""
        return (time.time() - self.received_at) > 600.0

    @property
    def mining_power_score(self) -> float:
        """Normalized mining power score (higher = faster).

        Score based on inverse VQE time and qubit count.
        """
        if not self.is_available or self.estimated_vqe_time_s <= 0:
            return 0.0
        speed_score = 1.0 / self.estimated_vqe_time_s
        qubit_bonus = min(self.max_qubits / 20.0, 3.0)  # Cap at 3x
        hardware_bonus = 1.5 if not self.is_simulator else 1.0
        return speed_score * qubit_bonus * hardware_bonus

    def to_dict(self) -> dict:
        return {
            'peer_id': self.peer_id,
            'backend_type': self.backend_type,
            'max_qubits': self.max_qubits,
            'is_simulator': self.is_simulator,
            'is_available': self.is_available,
            'estimated_vqe_time_s': round(self.estimated_vqe_time_s, 3),
            'features': self.features,
            'received_at': self.received_at,
            'is_stale': self.is_stale,
            'mining_power_score': round(self.mining_power_score, 4),
        }


class CapabilityAdvertiser:
    """Manages P2P capability advertisements.

    Handles:
    - Broadcasting this node's capabilities to peers
    - Receiving and storing peer capability advertisements
    - Querying the network capability registry
    - Ranking peers by mining power for task routing

    Usage:
        advertiser = CapabilityAdvertiser(node_peer_id='peer123')

        # Set this node's capability
        advertiser.set_local_capability(detector.get_p2p_advertisement())

        # Process incoming advertisement from a peer
        advertiser.receive_advertisement(peer_id='peer456', ad_msg={...})

        # Query network
        ranked = advertiser.get_peers_by_power()
        summary = advertiser.get_network_summary()
    """

    # Message type constant for P2P protocol
    MSG_TYPE = 'vqe_capability'
    STALE_THRESHOLD_S = 600.0  # 10 minutes

    def __init__(self, node_peer_id: str, max_peers: int = 200):
        self._node_peer_id = node_peer_id
        self._max_peers = max_peers
        self._lock = threading.Lock()

        # Local capability (from VQECapabilityDetector)
        self._local_ad: Optional[dict] = None

        # Registry of peer capabilities
        self._peers: Dict[str, PeerCapability] = {}

        logger.info(f"Capability advertiser initialized for peer {node_peer_id}")

    def set_local_capability(self, ad_msg: dict) -> None:
        """Set this node's capability advertisement.

        Args:
            ad_msg: Dict from VQECapabilityDetector.get_p2p_advertisement()
        """
        with self._lock:
            self._local_ad = ad_msg
        logger.debug(f"Local capability set: {ad_msg.get('backend_type', 'unknown')}")

    def get_local_advertisement(self) -> Optional[dict]:
        """Get this node's capability message for broadcasting."""
        with self._lock:
            if self._local_ad is None:
                return None
            msg = dict(self._local_ad)
            msg['peer_id'] = self._node_peer_id
            msg['timestamp'] = time.time()
            return msg

    def receive_advertisement(self, peer_id: str, ad_msg: dict) -> PeerCapability:
        """Process a capability advertisement from a peer.

        Args:
            peer_id: The sending peer's ID.
            ad_msg: The advertisement message dict.

        Returns:
            The stored PeerCapability record.
        """
        cap = PeerCapability(
            peer_id=peer_id,
            backend_type=ad_msg.get('backend_type', 'unknown'),
            max_qubits=ad_msg.get('max_qubits', 4),
            is_simulator=ad_msg.get('is_simulator', True),
            is_available=ad_msg.get('is_available', False),
            estimated_vqe_time_s=ad_msg.get('estimated_vqe_time_s', 5.0),
            features=ad_msg.get('features', {}),
            advertised_at=ad_msg.get('timestamp', 0.0),
        )

        with self._lock:
            self._peers[peer_id] = cap
            # Evict oldest if over capacity
            if len(self._peers) > self._max_peers:
                oldest_key = min(
                    self._peers, key=lambda k: self._peers[k].received_at
                )
                del self._peers[oldest_key]

        logger.debug(
            f"Received capability from {peer_id}: "
            f"{cap.backend_type}, {cap.max_qubits}q, power={cap.mining_power_score:.2f}"
        )
        return cap

    def remove_peer(self, peer_id: str) -> None:
        """Remove a peer from the registry (e.g., on disconnect)."""
        with self._lock:
            self._peers.pop(peer_id, None)

    def get_peer(self, peer_id: str) -> Optional[PeerCapability]:
        """Get a specific peer's capability."""
        with self._lock:
            return self._peers.get(peer_id)

    def get_all_peers(self) -> List[PeerCapability]:
        """Get all known peer capabilities."""
        with self._lock:
            return list(self._peers.values())

    def get_active_peers(self) -> List[PeerCapability]:
        """Get non-stale peer capabilities."""
        with self._lock:
            return [p for p in self._peers.values() if not p.is_stale]

    def get_peers_by_power(self, limit: int = 20) -> List[PeerCapability]:
        """Get peers ranked by mining power (highest first)."""
        with self._lock:
            active = [p for p in self._peers.values() if not p.is_stale and p.is_available]
            active.sort(key=lambda p: p.mining_power_score, reverse=True)
            return active[:limit]

    def get_peers_by_backend(self, backend_type: str) -> List[PeerCapability]:
        """Filter peers by backend type."""
        with self._lock:
            return [
                p for p in self._peers.values()
                if p.backend_type == backend_type and not p.is_stale
            ]

    def get_network_summary(self) -> dict:
        """Aggregate summary of network mining capabilities."""
        with self._lock:
            all_peers = list(self._peers.values())
            active = [p for p in all_peers if not p.is_stale]
            available = [p for p in active if p.is_available]

            backend_counts: Dict[str, int] = {}
            total_power = 0.0
            max_qubits = 0
            hardware_count = 0

            for p in available:
                backend_counts[p.backend_type] = backend_counts.get(p.backend_type, 0) + 1
                total_power += p.mining_power_score
                if p.max_qubits > max_qubits:
                    max_qubits = p.max_qubits
                if not p.is_simulator:
                    hardware_count += 1

            return {
                'total_peers': len(all_peers),
                'active_peers': len(active),
                'available_miners': len(available),
                'stale_peers': len(all_peers) - len(active),
                'hardware_nodes': hardware_count,
                'simulator_nodes': len(available) - hardware_count,
                'backend_distribution': backend_counts,
                'total_mining_power': round(total_power, 4),
                'max_qubit_capacity': max_qubits,
                'avg_vqe_time_s': round(
                    sum(p.estimated_vqe_time_s for p in available) / len(available), 3
                ) if available else 0.0,
            }

    def cleanup_stale(self) -> int:
        """Remove stale peer records. Returns count removed."""
        with self._lock:
            stale_ids = [pid for pid, p in self._peers.items() if p.is_stale]
            for pid in stale_ids:
                del self._peers[pid]
            return len(stale_ids)

    def get_stats(self) -> dict:
        """Quick stats."""
        with self._lock:
            return {
                'registered_peers': len(self._peers),
                'active_peers': sum(1 for p in self._peers.values() if not p.is_stale),
                'has_local_capability': self._local_ad is not None,
                'node_peer_id': self._node_peer_id,
            }
