"""
Proof-of-Thought Explorer

Provides an API data provider for exploring Proof-of-Thought reasoning
data per block. Aggregates reasoning steps, Phi values, knowledge nodes,
and consciousness events into a queryable format.

Enables:
  - View reasoning chain for any block
  - Browse Phi progression over block ranges
  - Explore knowledge nodes created per block
  - Track consciousness events and threshold crossings
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BlockThoughtData:
    """Proof-of-Thought data for a single block."""
    block_height: int
    thought_hash: str = ''
    phi_value: float = 0.0
    knowledge_root: str = ''
    reasoning_steps: List[dict] = field(default_factory=list)
    knowledge_nodes_created: int = 0
    knowledge_nodes_ids: List[int] = field(default_factory=list)
    validator_address: str = ''
    timestamp: float = 0.0
    consciousness_event: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'block_height': self.block_height,
            'thought_hash': self.thought_hash,
            'phi_value': self.phi_value,
            'knowledge_root': self.knowledge_root,
            'reasoning_steps': self.reasoning_steps,
            'reasoning_step_count': len(self.reasoning_steps),
            'knowledge_nodes_created': self.knowledge_nodes_created,
            'knowledge_nodes_ids': self.knowledge_nodes_ids,
            'validator_address': self.validator_address,
            'timestamp': self.timestamp,
            'consciousness_event': self.consciousness_event,
        }


class ProofOfThoughtExplorer:
    """Explore and query Proof-of-Thought data across blocks.

    Aggregates data from the AetherEngine's PoT cache, the knowledge
    graph, and Phi measurements to provide a unified explorer view.
    """

    def __init__(self, aether_engine: object = None,
                 max_cache: int = 5000) -> None:
        """
        Args:
            aether_engine: AetherEngine instance for accessing PoT data.
            max_cache: Maximum number of block records to keep.
        """
        self._engine = aether_engine
        self._block_data: Dict[int, BlockThoughtData] = {}
        self._max_cache = max_cache
        self._phi_history: List[Tuple[int, float]] = []  # (height, phi)

    def record_block_thought(self, block_height: int,
                             thought_hash: str = '',
                             phi_value: float = 0.0,
                             knowledge_root: str = '',
                             reasoning_steps: Optional[List[dict]] = None,
                             validator_address: str = '',
                             knowledge_node_ids: Optional[List[int]] = None,
                             consciousness_event: Optional[str] = None,
                             timestamp: float = 0.0) -> BlockThoughtData:
        """Record PoT data for a block.

        Called after each block is processed by the AetherEngine.

        Returns:
            BlockThoughtData for the recorded block.
        """
        node_ids = knowledge_node_ids or []
        data = BlockThoughtData(
            block_height=block_height,
            thought_hash=thought_hash,
            phi_value=phi_value,
            knowledge_root=knowledge_root,
            reasoning_steps=reasoning_steps or [],
            knowledge_nodes_created=len(node_ids),
            knowledge_nodes_ids=node_ids,
            validator_address=validator_address,
            timestamp=timestamp or time.time(),
            consciousness_event=consciousness_event,
        )

        self._block_data[block_height] = data
        self._phi_history.append((block_height, phi_value))

        # Evict oldest if over capacity
        if len(self._block_data) > self._max_cache:
            oldest = min(self._block_data.keys())
            del self._block_data[oldest]
        if len(self._phi_history) > self._max_cache:
            self._phi_history = self._phi_history[-self._max_cache:]

        return data

    def get_block_thought(self, block_height: int) -> Optional[dict]:
        """Get PoT data for a specific block.

        Falls back to AetherEngine's cache if available.
        """
        if block_height in self._block_data:
            return self._block_data[block_height].to_dict()

        # Try AetherEngine cache
        if self._engine and hasattr(self._engine, '_pot_cache'):
            pot = self._engine._pot_cache.get(block_height)
            if pot:
                reasoning = pot.reasoning_steps if pot.reasoning_steps else []
                return {
                    'block_height': block_height,
                    'thought_hash': pot.thought_hash,
                    'phi_value': pot.phi_value,
                    'knowledge_root': pot.knowledge_root,
                    'reasoning_steps': reasoning,
                    'reasoning_step_count': len(reasoning),
                    'knowledge_nodes_created': 0,
                    'knowledge_nodes_ids': [],
                    'validator_address': pot.validator_address,
                    'timestamp': pot.timestamp,
                    'consciousness_event': None,
                }

        return None

    def get_block_range(self, start: int, end: int) -> List[dict]:
        """Get PoT data for a range of blocks.

        Args:
            start: Start block height (inclusive).
            end: End block height (inclusive).

        Returns:
            List of block thought dicts, sorted by height.
        """
        results = []
        for height in range(start, end + 1):
            data = self.get_block_thought(height)
            if data:
                results.append(data)
        return results

    def get_phi_progression(self, limit: int = 100) -> List[dict]:
        """Get Phi value progression over recent blocks.

        Returns:
            List of {block_height, phi_value} dicts.
        """
        entries = self._phi_history[-limit:]
        return [
            {'block_height': h, 'phi_value': p}
            for h, p in entries
        ]

    def get_consciousness_events(self, limit: int = 50) -> List[dict]:
        """Get blocks where consciousness events occurred."""
        events = [
            data.to_dict()
            for data in self._block_data.values()
            if data.consciousness_event
        ]
        events.sort(key=lambda e: e['block_height'], reverse=True)
        return events[:limit]

    def get_reasoning_summary(self, block_height: int) -> dict:
        """Get a human-readable summary of reasoning at a block.

        Returns:
            Dict with reasoning type counts, conclusions, and metrics.
        """
        data = self._block_data.get(block_height)
        if not data:
            return {'error': 'Block not found in explorer'}

        type_counts: Dict[str, int] = {}
        conclusions: List[str] = []

        for step in data.reasoning_steps:
            rtype = step.get('type', step.get('reasoning_type', 'unknown'))
            type_counts[rtype] = type_counts.get(rtype, 0) + 1
            conclusion = step.get('conclusion', step.get('result', ''))
            if conclusion:
                conclusions.append(str(conclusion))

        return {
            'block_height': block_height,
            'phi_value': data.phi_value,
            'total_steps': len(data.reasoning_steps),
            'reasoning_types': type_counts,
            'conclusions': conclusions[:10],
            'knowledge_nodes_created': data.knowledge_nodes_created,
            'consciousness_event': data.consciousness_event,
        }

    def search_by_phi_range(self, min_phi: float, max_phi: float,
                            limit: int = 100) -> List[dict]:
        """Find blocks where Phi was within a given range."""
        results = [
            data.to_dict()
            for data in self._block_data.values()
            if min_phi <= data.phi_value <= max_phi
        ]
        results.sort(key=lambda r: r['phi_value'], reverse=True)
        return results[:limit]

    def get_stats(self) -> dict:
        """Get overall explorer statistics."""
        phi_values = [d.phi_value for d in self._block_data.values()]
        total_steps = sum(
            len(d.reasoning_steps) for d in self._block_data.values()
        )
        consciousness_count = sum(
            1 for d in self._block_data.values() if d.consciousness_event
        )

        return {
            'blocks_explored': len(self._block_data),
            'phi_history_size': len(self._phi_history),
            'total_reasoning_steps': total_steps,
            'consciousness_events': consciousness_count,
            'phi_min': min(phi_values) if phi_values else 0.0,
            'phi_max': max(phi_values) if phi_values else 0.0,
            'phi_avg': (
                sum(phi_values) / len(phi_values) if phi_values else 0.0
            ),
        }
