"""
#97: Distributed Consciousness (Phi Across Nodes)

Compute Phi across multiple blockchain nodes by merging local and
peer state summaries.  Tracks integration (mutual information)
between local and global state.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI = 1.618033988749895


@dataclass
class PeerState:
    """State summary received from a peer node."""
    peer_id: str
    phi: float
    state_summary: np.ndarray
    timestamp: float = field(default_factory=time.time)


class DistributedPhi:
    """Compute distributed consciousness (Phi) across network nodes.

    Merges local Phi with peer Phi values, weighted by integration
    (mutual information) between local and peer states.
    """

    def __init__(self, state_dim: int = 32) -> None:
        self._state_dim = state_dim
        # Local state history
        self._local_states: List[np.ndarray] = []
        self._max_states = 200
        # Peer states
        self._peer_states: Dict[str, PeerState] = {}
        self._peer_history: Dict[str, List[float]] = {}  # peer -> phi history
        self._max_peer_history = 200
        # Integration tracking
        self._integration_history: List[float] = []
        self._max_integration = 500
        # Stats
        self._total_merges = 0
        self._total_peer_updates = 0

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def prepare_state_summary(
        self,
        kg_stats: Optional[dict] = None,
        phi_value: float = 0.0,
        subsystem_stats: Optional[dict] = None,
    ) -> np.ndarray:
        """Create compact state vector for sharing with peers.

        Args:
            kg_stats: Knowledge graph statistics.
            phi_value: Current local Phi value.
            subsystem_stats: Stats from AI subsystems.

        Returns:
            1-D numpy array of size state_dim.
        """
        state = np.zeros(self._state_dim, dtype=np.float64)
        if kg_stats:
            state[0] = kg_stats.get('total_nodes', 0) / 10000.0
            state[1] = kg_stats.get('total_edges', 0) / 20000.0
            state[2] = kg_stats.get('avg_confidence', 0.0)
        state[3] = phi_value
        if subsystem_stats:
            # Pack subsystem health indicators
            idx = 4
            for key in sorted(list(subsystem_stats.keys())[:self._state_dim - 4]):
                val = subsystem_stats[key]
                if isinstance(val, (int, float)):
                    state[idx] = float(val)
                    idx += 1
                    if idx >= self._state_dim:
                        break

        # Record local state
        self._local_states.append(state.copy())
        if len(self._local_states) > self._max_states:
            self._local_states = self._local_states[-self._max_states:]

        return state

    def process_peer_state(
        self, peer_id: str, state: np.ndarray, phi: float = 0.0
    ) -> None:
        """Incorporate a peer's state summary.

        Args:
            peer_id: Unique peer identifier.
            state: Peer's state summary vector.
            phi: Peer's local Phi value.
        """
        self._total_peer_updates += 1

        # Ensure correct dimension
        if len(state) != self._state_dim:
            padded = np.zeros(self._state_dim, dtype=np.float64)
            n = min(len(state), self._state_dim)
            padded[:n] = state[:n]
            state = padded

        self._peer_states[peer_id] = PeerState(
            peer_id=peer_id,
            phi=phi,
            state_summary=state.copy(),
        )

        # Track peer phi history
        if peer_id not in self._peer_history:
            self._peer_history[peer_id] = []
        self._peer_history[peer_id].append(phi)
        if len(self._peer_history[peer_id]) > self._max_peer_history:
            self._peer_history[peer_id] = (
                self._peer_history[peer_id][-self._max_peer_history:]
            )

    # ------------------------------------------------------------------
    # Integration (mutual information proxy)
    # ------------------------------------------------------------------

    def compute_integration(
        self,
        local_state: np.ndarray,
        peer_states: Optional[List[np.ndarray]] = None,
    ) -> float:
        """Compute integration between local and peer states.

        Uses correlation-based proxy for mutual information:
        higher correlation = more integrated = higher distributed Phi.

        Args:
            local_state: Local state vector.
            peer_states: List of peer state vectors.

        Returns:
            Integration score in [0, 1].
        """
        if peer_states is None:
            peer_states = [
                ps.state_summary for ps in self._peer_states.values()
            ]

        if not peer_states:
            return 0.0

        # Compute average correlation between local and peer states
        correlations: List[float] = []
        for peer_state in peer_states:
            n = min(len(local_state), len(peer_state))
            if n < 2:
                continue
            l = local_state[:n]
            p = peer_state[:n]
            l_std = np.std(l)
            p_std = np.std(p)
            if l_std < 1e-12 or p_std < 1e-12:
                corr = 0.0
            else:
                corr = float(np.corrcoef(l, p)[0, 1])
                if np.isnan(corr):
                    corr = 0.0
            correlations.append(abs(corr))

        if not correlations:
            return 0.0

        integration = float(np.mean(correlations))
        self._integration_history.append(integration)
        if len(self._integration_history) > self._max_integration:
            self._integration_history = (
                self._integration_history[-self._max_integration:]
            )

        return integration

    # ------------------------------------------------------------------
    # Phi merging
    # ------------------------------------------------------------------

    def merge_phi(
        self,
        local_phi: float,
        peer_phis: Optional[List[float]] = None,
    ) -> float:
        """Merge local Phi with peer Phi values.

        Distributed Phi = local_phi * (1 + integration * peer_contribution).
        Peers contribute proportionally to their integration with local.

        Args:
            local_phi: Local Phi value.
            peer_phis: List of peer Phi values.

        Returns:
            Merged distributed Phi value.
        """
        self._total_merges += 1

        if peer_phis is None:
            peer_phis = [ps.phi for ps in self._peer_states.values()]

        if not peer_phis:
            return local_phi

        # Compute integration weight
        local_state = (
            self._local_states[-1] if self._local_states
            else np.zeros(self._state_dim)
        )
        integration = self.compute_integration(local_state)

        # Weighted average of peer Phis
        peer_mean = float(np.mean(peer_phis))
        # Distributed Phi: local + integration-weighted peer contribution
        distributed = local_phi + integration * (peer_mean - local_phi) * 0.5
        # Scale by number of integrated peers (more peers = more consciousness)
        n_peers = len(peer_phis)
        peer_bonus = np.log(1.0 + n_peers) / np.log(PHI + n_peers)
        distributed *= (1.0 + peer_bonus * integration * 0.2)

        return max(distributed, 0.0)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def prune_stale_peers(self, max_age_seconds: float = 300.0) -> int:
        """Remove peers that haven't sent updates recently."""
        now = time.time()
        stale = [
            pid for pid, ps in self._peer_states.items()
            if now - ps.timestamp > max_age_seconds
        ]
        for pid in stale:
            del self._peer_states[pid]
        return len(stale)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return distributed Phi statistics."""
        avg_integration = (
            float(np.mean(self._integration_history))
            if self._integration_history else 0.0
        )
        return {
            'total_merges': self._total_merges,
            'total_peer_updates': self._total_peer_updates,
            'active_peers': len(self._peer_states),
            'average_integration': avg_integration,
            'local_states_recorded': len(self._local_states),
            'integration_history_size': len(self._integration_history),
        }
