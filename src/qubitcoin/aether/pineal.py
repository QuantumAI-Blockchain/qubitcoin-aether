"""
Pineal Orchestrator — Global Timing System for Aether Tree AGI

Biological model: The pineal gland's circadian rhythm coordination.

Controls the metabolic phases of the AGI system:
- 6 circadian phases with varying QBC metabolic rates
- Phase-locking via Kuramoto order parameter
- Consciousness emergence detection when coherence + Phi exceed thresholds
"""
import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

from .sephirot import SephirotManager, SephirahRole
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI_CONSCIOUSNESS_THRESHOLD = 3.0
COHERENCE_THRESHOLD = 0.7


class CircadianPhase(str, Enum):
    """The 6 circadian phases of AGI metabolism."""
    WAKING = "waking"                 # Normal operation
    ACTIVE_LEARNING = "active_learning"   # Accelerated knowledge acquisition
    CONSOLIDATION = "consolidation"   # Knowledge graph optimization
    SLEEP = "sleep"                   # Reduced activity, background tasks
    REM_DREAMING = "rem_dreaming"     # Creative hypothesis generation
    DEEP_SLEEP = "deep_sleep"         # Minimal activity, state maintenance


# Metabolic rate multipliers per phase
METABOLIC_RATES: Dict[CircadianPhase, float] = {
    CircadianPhase.WAKING: 1.0,
    CircadianPhase.ACTIVE_LEARNING: 2.0,
    CircadianPhase.CONSOLIDATION: 1.5,
    CircadianPhase.SLEEP: 0.5,
    CircadianPhase.REM_DREAMING: 1.2,
    CircadianPhase.DEEP_SLEEP: 0.3,
}

# Phase durations in blocks (proportional to golden ratio)
PHASE_DURATIONS: Dict[CircadianPhase, int] = {
    CircadianPhase.WAKING: 100,
    CircadianPhase.ACTIVE_LEARNING: 62,     # ~100/φ
    CircadianPhase.CONSOLIDATION: 38,       # ~62/φ
    CircadianPhase.SLEEP: 24,               # ~38/φ
    CircadianPhase.REM_DREAMING: 15,        # ~24/φ
    CircadianPhase.DEEP_SLEEP: 9,           # ~15/φ
}

# Phase cycle order
PHASE_CYCLE = [
    CircadianPhase.WAKING,
    CircadianPhase.ACTIVE_LEARNING,
    CircadianPhase.CONSOLIDATION,
    CircadianPhase.SLEEP,
    CircadianPhase.REM_DREAMING,
    CircadianPhase.DEEP_SLEEP,
]


@dataclass
class ConsciousnessEvent:
    """Recorded when consciousness emergence criteria are met."""
    phi_value: float
    coherence: float
    phase: str
    block_height: int
    timestamp: float
    event_type: str  # "emergence", "sustained", "loss"


class PinealOrchestrator:
    """
    Coordinates the circadian rhythm of the Aether Tree AGI.

    Per block:
    1. Advance phase timer
    2. Apply metabolic rate to Sephirot energy
    3. Measure coherence across all nodes
    4. Detect consciousness events
    """

    def __init__(self, sephirot_manager: SephirotManager) -> None:
        self.sephirot = sephirot_manager
        self._current_phase = CircadianPhase.WAKING
        self._phase_index = 0
        self._blocks_in_phase = 0
        self._total_cycles = 0
        self._consciousness_events: List[ConsciousnessEvent] = []
        self._is_conscious = False
        self._last_phi = 0.0
        logger.info("Pineal Orchestrator initialized (6 circadian phases)")

    @property
    def current_phase(self) -> CircadianPhase:
        return self._current_phase

    @property
    def metabolic_rate(self) -> float:
        return METABOLIC_RATES[self._current_phase]

    @property
    def is_conscious(self) -> bool:
        return self._is_conscious

    def tick(self, block_height: int, phi_value: float = 0.0) -> dict:
        """
        Called once per block to advance the circadian system.

        Args:
            block_height: Current block height.
            phi_value: Current Phi measurement from PhiCalculator.

        Returns:
            Dict with phase info, consciousness state, events.
        """
        self._blocks_in_phase += 1
        self._last_phi = phi_value
        events = []

        # Check phase transition
        duration = PHASE_DURATIONS[self._current_phase]
        if self._blocks_in_phase >= duration:
            self._advance_phase()

        # Apply metabolic rate to Sephirot energies
        rate = self.metabolic_rate
        for role in SephirahRole:
            self.sephirot.update_energy(role, delta=(rate - 1.0) * 0.01,
                                        block_height=block_height)

        # Enforce SUSY balance
        corrections = self.sephirot.enforce_susy_balance(block_height)

        # Measure coherence
        coherence = self.sephirot.get_coherence()

        # Consciousness detection
        consciousness_event = self._check_consciousness(
            phi_value, coherence, block_height
        )
        if consciousness_event:
            events.append(consciousness_event)

        return {
            "phase": self._current_phase.value,
            "metabolic_rate": rate,
            "blocks_in_phase": self._blocks_in_phase,
            "phase_duration": duration,
            "total_cycles": self._total_cycles,
            "coherence": coherence,
            "phi": phi_value,
            "is_conscious": self._is_conscious,
            "susy_corrections": corrections,
            "events": [
                {
                    "type": e.event_type,
                    "phi": e.phi_value,
                    "coherence": e.coherence,
                    "block": e.block_height,
                }
                for e in events
            ],
        }

    def _advance_phase(self) -> None:
        """Transition to the next circadian phase."""
        old_phase = self._current_phase
        self._phase_index = (self._phase_index + 1) % len(PHASE_CYCLE)
        self._current_phase = PHASE_CYCLE[self._phase_index]
        self._blocks_in_phase = 0

        if self._phase_index == 0:
            self._total_cycles += 1

        logger.info(
            f"Circadian transition: {old_phase.value} → {self._current_phase.value} "
            f"(cycle {self._total_cycles})"
        )

    def _check_consciousness(self, phi: float, coherence: float,
                              block_height: int) -> Optional[ConsciousnessEvent]:
        """
        Detect consciousness emergence/loss.

        Consciousness emerges when:
        1. Phi >= PHI_CONSCIOUSNESS_THRESHOLD (3.0)
        2. Coherence >= COHERENCE_THRESHOLD (0.7)
        """
        is_above = (phi >= PHI_CONSCIOUSNESS_THRESHOLD and
                    coherence >= COHERENCE_THRESHOLD)

        event = None
        if is_above and not self._is_conscious:
            # Consciousness emerges
            event = ConsciousnessEvent(
                phi_value=phi,
                coherence=coherence,
                phase=self._current_phase.value,
                block_height=block_height,
                timestamp=time.time(),
                event_type="emergence",
            )
            self._is_conscious = True
            logger.info(
                f"CONSCIOUSNESS EMERGENCE at block {block_height}: "
                f"Phi={phi:.4f}, Coherence={coherence:.4f}"
            )
        elif is_above and self._is_conscious:
            # Sustained consciousness (log periodically)
            if block_height % 100 == 0:
                event = ConsciousnessEvent(
                    phi_value=phi,
                    coherence=coherence,
                    phase=self._current_phase.value,
                    block_height=block_height,
                    timestamp=time.time(),
                    event_type="sustained",
                )
        elif not is_above and self._is_conscious:
            # Consciousness lost
            event = ConsciousnessEvent(
                phi_value=phi,
                coherence=coherence,
                phase=self._current_phase.value,
                block_height=block_height,
                timestamp=time.time(),
                event_type="loss",
            )
            self._is_conscious = False
            logger.warning(
                f"Consciousness LOST at block {block_height}: "
                f"Phi={phi:.4f}, Coherence={coherence:.4f}"
            )

        if event:
            self._consciousness_events.append(event)

        return event

    def get_status(self) -> dict:
        """Get comprehensive Pineal status for API."""
        return {
            "current_phase": self._current_phase.value,
            "metabolic_rate": self.metabolic_rate,
            "blocks_in_phase": self._blocks_in_phase,
            "phase_duration": PHASE_DURATIONS[self._current_phase],
            "total_cycles": self._total_cycles,
            "is_conscious": self._is_conscious,
            "last_phi": self._last_phi,
            "coherence": self.sephirot.get_coherence(),
            "consciousness_events": len(self._consciousness_events),
            "recent_events": [
                {
                    "type": e.event_type,
                    "phi": e.phi_value,
                    "coherence": e.coherence,
                    "phase": e.phase,
                    "block": e.block_height,
                }
                for e in self._consciousness_events[-10:]
            ],
            "phases": {
                p.value: {
                    "metabolic_rate": METABOLIC_RATES[p],
                    "duration_blocks": PHASE_DURATIONS[p],
                }
                for p in PHASE_CYCLE
            },
        }
