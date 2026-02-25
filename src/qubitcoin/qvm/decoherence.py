"""
Quantum State Decoherence Prevention Model

Tracks coherence lifetime of on-chain quantum states.  Each state has a
``coherence_budget`` (measured in blocks) that decreases by 1 per block.
When the budget reaches zero the state is marked as "decohered" and can
no longer be used for quantum operations (entanglement, gates).

Prevention mechanisms:
    - Refresh: reset the budget by re-staking QBC
    - Shield: apply error-correction that multiplies budget by a factor
    - Freeze: pause decoherence countdown (costs gas)
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_COHERENCE_BUDGET: int = 100      # blocks
SHIELD_MULTIPLIER: float = 2.0          # doubles budget
MIN_BUDGET: int = 1


@dataclass
class CoherenceRecord:
    """Per-state coherence tracking."""
    state_id: int
    initial_budget: int = DEFAULT_COHERENCE_BUDGET
    remaining_budget: int = DEFAULT_COHERENCE_BUDGET
    created_at_block: int = 0
    last_refresh_block: int = 0
    is_frozen: bool = False
    is_decohered: bool = False
    shield_level: int = 0        # Number of shields applied

    def to_dict(self) -> dict:
        return {
            'state_id': self.state_id,
            'initial_budget': self.initial_budget,
            'remaining_budget': self.remaining_budget,
            'created_at_block': self.created_at_block,
            'is_frozen': self.is_frozen,
            'is_decohered': self.is_decohered,
            'shield_level': self.shield_level,
        }


class DecoherenceManager:
    """Manages coherence lifetimes for all quantum states.

    Call ``tick(block_height)`` once per block to advance decoherence.
    """

    def __init__(self) -> None:
        self._records: Dict[int, CoherenceRecord] = {}
        self._current_block: int = 0

    def register(self, state_id: int, block_height: int,
                 budget: int = DEFAULT_COHERENCE_BUDGET) -> CoherenceRecord:
        """Register a new quantum state with a coherence budget."""
        record = CoherenceRecord(
            state_id=state_id,
            initial_budget=budget,
            remaining_budget=budget,
            created_at_block=block_height,
            last_refresh_block=block_height,
        )
        self._records[state_id] = record
        return record

    def get(self, state_id: int) -> Optional[CoherenceRecord]:
        return self._records.get(state_id)

    def tick(self, block_height: int) -> List[int]:
        """Advance one block.  Decrements budgets and marks decohered states.

        Returns list of state_ids that decohered this tick.
        """
        self._current_block = block_height
        newly_decohered: List[int] = []

        for sid, rec in self._records.items():
            if rec.is_decohered or rec.is_frozen:
                continue
            rec.remaining_budget -= 1
            if rec.remaining_budget <= 0:
                rec.remaining_budget = 0
                rec.is_decohered = True
                newly_decohered.append(sid)
                logger.info(f"Quantum state {sid} decohered at block {block_height}")

        return newly_decohered

    def refresh(self, state_id: int, budget: Optional[int] = None) -> bool:
        """Refresh the coherence budget (requires re-staking QBC)."""
        rec = self._records.get(state_id)
        if not rec:
            return False
        new_budget = budget if budget is not None else rec.initial_budget
        rec.remaining_budget = max(new_budget, MIN_BUDGET)
        rec.is_decohered = False
        rec.last_refresh_block = self._current_block
        return True

    def shield(self, state_id: int) -> bool:
        """Apply error-correction shield (doubles remaining budget)."""
        rec = self._records.get(state_id)
        if not rec or rec.is_decohered:
            return False
        rec.remaining_budget = int(rec.remaining_budget * SHIELD_MULTIPLIER)
        rec.shield_level += 1
        return True

    def freeze(self, state_id: int) -> bool:
        """Freeze decoherence countdown (pauses budget consumption)."""
        rec = self._records.get(state_id)
        if not rec or rec.is_decohered:
            return False
        rec.is_frozen = True
        return True

    def unfreeze(self, state_id: int) -> bool:
        """Resume decoherence countdown."""
        rec = self._records.get(state_id)
        if not rec:
            return False
        rec.is_frozen = False
        return True

    def is_coherent(self, state_id: int) -> bool:
        """Check if a state is still coherent (usable)."""
        rec = self._records.get(state_id)
        if not rec:
            return False
        return not rec.is_decohered

    def list_active(self) -> List[CoherenceRecord]:
        """Return all non-decohered states."""
        return [r for r in self._records.values() if not r.is_decohered]

    def list_decohered(self) -> List[CoherenceRecord]:
        """Return all decohered states."""
        return [r for r in self._records.values() if r.is_decohered]

    def remove(self, state_id: int) -> bool:
        """Remove a state from tracking."""
        return self._records.pop(state_id, None) is not None

    def get_stats(self) -> dict:
        """Return summary statistics for all tracked quantum states."""
        active = self.list_active()
        decohered = self.list_decohered()
        return {
            'total_states': len(self._records),
            'active': len(active),
            'decohered': len(decohered),
            'frozen': sum(1 for r in active if r.is_frozen),
            'current_block': self._current_block,
            'states': [r.to_dict() for r in self._records.values()],
        }
