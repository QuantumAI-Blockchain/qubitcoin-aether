"""
Transaction Graph Builder — 6-hop depth analysis for risk assessment

Builds a directed graph of transaction relationships from a seed address,
traversing up to ``MAX_HOPS`` hops to identify connected addresses and
their risk characteristics.

Used by the QRISK oracle to compute SUSY Hamiltonian-based risk scores.
"""
import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

MAX_HOPS: int = 6


@dataclass
class TxEdge:
    """A directed edge in the transaction graph."""
    sender: str
    recipient: str
    amount: float
    block_height: int
    txid: str = ''

    def to_dict(self) -> dict:
        return {
            'sender': self.sender,
            'recipient': self.recipient,
            'amount': self.amount,
            'block_height': self.block_height,
            'txid': self.txid,
        }


@dataclass
class GraphNode:
    """A node in the transaction graph with aggregate statistics."""
    address: str
    hop_distance: int = 0
    total_sent: float = 0.0
    total_received: float = 0.0
    tx_count: int = 0

    def to_dict(self) -> dict:
        return {
            'address': self.address,
            'hop_distance': self.hop_distance,
            'total_sent': self.total_sent,
            'total_received': self.total_received,
            'tx_count': self.tx_count,
        }


class TransactionGraph:
    """In-memory transaction graph for risk analysis.

    Records transactions and supports BFS traversal from any seed address
    to discover connected addresses within ``MAX_HOPS``.
    """

    def __init__(self, max_hops: int = MAX_HOPS) -> None:
        self.max_hops = max_hops
        # Adjacency lists: address → list of (peer, edge)
        self._outgoing: Dict[str, List[TxEdge]] = defaultdict(list)
        self._incoming: Dict[str, List[TxEdge]] = defaultdict(list)
        self._addresses: Set[str] = set()

    def add_transaction(self, sender: str, recipient: str,
                        amount: float, block_height: int,
                        txid: str = '') -> TxEdge:
        """Record a transaction between two addresses."""
        edge = TxEdge(
            sender=sender,
            recipient=recipient,
            amount=amount,
            block_height=block_height,
            txid=txid,
        )
        self._outgoing[sender].append(edge)
        self._incoming[recipient].append(edge)
        self._addresses.add(sender)
        self._addresses.add(recipient)
        return edge

    def build_subgraph(self, seed: str, max_hops: Optional[int] = None) -> Dict[str, GraphNode]:
        """BFS from a seed address up to max_hops depth.

        Returns:
            Dict mapping address → GraphNode with hop distance and aggregates.
        """
        hops = max_hops if max_hops is not None else self.max_hops
        visited: Dict[str, GraphNode] = {}
        queue: deque = deque()

        if seed not in self._addresses:
            return visited

        root = GraphNode(address=seed, hop_distance=0)
        visited[seed] = root
        queue.append(seed)

        while queue:
            addr = queue.popleft()
            current_hop = visited[addr].hop_distance

            if current_hop >= hops:
                continue

            # Follow outgoing edges
            for edge in self._outgoing.get(addr, []):
                peer = edge.recipient
                if peer not in visited:
                    node = GraphNode(address=peer, hop_distance=current_hop + 1)
                    visited[peer] = node
                    queue.append(peer)
                visited[peer].total_received += edge.amount
                visited[peer].tx_count += 1

            # Follow incoming edges
            for edge in self._incoming.get(addr, []):
                peer = edge.sender
                if peer not in visited:
                    node = GraphNode(address=peer, hop_distance=current_hop + 1)
                    visited[peer] = node
                    queue.append(peer)
                visited[peer].total_sent += edge.amount
                visited[peer].tx_count += 1

        return visited

    def get_neighbors(self, address: str) -> Set[str]:
        """Return direct neighbors (1-hop) of an address."""
        neighbors: Set[str] = set()
        for edge in self._outgoing.get(address, []):
            neighbors.add(edge.recipient)
        for edge in self._incoming.get(address, []):
            neighbors.add(edge.sender)
        return neighbors

    def get_edge_count(self) -> int:
        """Total number of transaction edges."""
        return sum(len(edges) for edges in self._outgoing.values())

    def get_node_count(self) -> int:
        """Total number of unique addresses."""
        return len(self._addresses)

    def has_address(self, address: str) -> bool:
        return address in self._addresses

    def get_transactions(self, address: str) -> List[TxEdge]:
        """Return all transactions involving an address (sent + received)."""
        sent = self._outgoing.get(address, [])
        received = self._incoming.get(address, [])
        return sent + received
