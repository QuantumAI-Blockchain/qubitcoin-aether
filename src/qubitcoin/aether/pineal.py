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
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional
from enum import Enum

from .sephirot import SephirotManager, SephirahRole
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI_CONSCIOUSNESS_THRESHOLD = 3.0
COHERENCE_THRESHOLD = 0.7

# Melatonin inhibitory signal levels per phase (0.0 = no inhibition, 1.0 = full)
MELATONIN_LEVELS: Dict[str, float] = {
    "waking": 0.0,               # Fully alert — no melatonin
    "active_learning": 0.0,      # Peak activity — no melatonin
    "consolidation": 0.2,        # Beginning to wind down
    "sleep": 0.6,                # Moderate inhibition
    "rem_dreaming": 0.4,         # Reduced for dream-state creativity
    "deep_sleep": 0.9,           # Near-maximum inhibition
}


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


class MelatoninModulator:
    """
    Simulates melatonin-based inhibitory signals during sleep phases.

    Biological model: Melatonin is released by the pineal gland during
    darkness, suppressing neural activity and promoting rest/consolidation.

    Effects:
    - Dampens metabolic rate further during sleep phases
    - Reduces message processing priority in CSF transport
    - Increases Gevurah (safety/inhibition) energy relative to Chesed (exploration)
    - Tracks melatonin accumulation over the circadian cycle
    """

    def __init__(self) -> None:
        self._level: float = 0.0        # Current melatonin level [0.0, 1.0]
        self._accumulated: float = 0.0  # Total melatonin produced this cycle
        self._decay_rate: float = 0.05  # How fast melatonin clears per block
        self._production_rate: float = 0.08  # How fast melatonin builds per block
        logger.info("Melatonin modulator initialized")

    @property
    def level(self) -> float:
        """Current melatonin level (0.0 = none, 1.0 = saturated)."""
        return self._level

    @property
    def inhibition_factor(self) -> float:
        """Multiplier applied to metabolic rate (1.0 = no effect, 0.1 = 90% inhibition)."""
        return max(0.1, 1.0 - self._level * 0.9)

    def update(self, phase: CircadianPhase) -> float:
        """
        Update melatonin level based on the current circadian phase.

        During sleep phases, melatonin rises toward the target level.
        During waking phases, melatonin decays toward zero.

        Args:
            phase: Current circadian phase.

        Returns:
            Updated melatonin level.
        """
        target = MELATONIN_LEVELS.get(phase.value, 0.0)

        if target > self._level:
            # Produce melatonin (approach target from below)
            delta = min(self._production_rate, target - self._level)
            self._level += delta
            self._accumulated += delta
        else:
            # Decay melatonin (approach target from above)
            delta = min(self._decay_rate, self._level - target)
            self._level -= delta

        self._level = max(0.0, min(1.0, self._level))
        return self._level

    def get_status(self) -> dict:
        """Get melatonin modulator status."""
        return {
            "level": round(self._level, 4),
            "inhibition_factor": round(self.inhibition_factor, 4),
            "accumulated": round(self._accumulated, 4),
        }

    def reset_cycle(self) -> None:
        """Reset accumulated melatonin at the start of a new circadian cycle."""
        self._accumulated = 0.0


class CognitiveLoadTracker:
    """Tracks cognitive load (queries/events per block) as an EMA.

    Used by PinealOrchestrator to adaptively extend/shorten phase durations
    based on actual system activity.
    """

    def __init__(self, alpha: float = 0.1) -> None:
        self._events_this_block: int = 0
        self._load_ema: float = 0.0
        self._alpha = alpha
        self._peak_load: float = 1.0

    def record_event(self) -> None:
        """Record a cognitive event (query, reasoning op, etc.)."""
        self._events_this_block += 1

    def tick(self) -> float:
        """Called once per block. Updates EMA and resets counter."""
        self._load_ema = self._alpha * self._events_this_block + (1 - self._alpha) * self._load_ema
        self._peak_load = max(self._peak_load, self._load_ema)
        self._events_this_block = 0
        return self._load_ema

    @property
    def normalized_load(self) -> float:
        """Load as 0.0-1.0 relative to peak."""
        return self._load_ema / max(self._peak_load, 1.0)

    def get_status(self) -> dict:
        return {
            'load_ema': round(self._load_ema, 3),
            'peak_load': round(self._peak_load, 3),
            'normalized': round(self.normalized_load, 3),
        }


class ConsciousnessMomentum:
    """Rolling average of phi/coherence with hysteresis to prevent flickering.

    Uses a 15% hysteresis band: consciousness emerges at threshold,
    but only lost when dropping 15% below threshold.
    """

    HYSTERESIS_BAND: float = 0.15  # 15% below threshold to lose consciousness

    def __init__(self, window: int = 20) -> None:
        self._phi_history: Deque[float] = deque(maxlen=window)
        self._coherence_history: Deque[float] = deque(maxlen=window)

    def update(self, phi: float, coherence: float) -> None:
        self._phi_history.append(phi)
        self._coherence_history.append(coherence)

    @property
    def smoothed_phi(self) -> float:
        if not self._phi_history:
            return 0.0
        return sum(self._phi_history) / len(self._phi_history)

    @property
    def smoothed_coherence(self) -> float:
        if not self._coherence_history:
            return 0.0
        return sum(self._coherence_history) / len(self._coherence_history)

    def should_emerge(self) -> bool:
        """Check if smoothed values exceed emergence thresholds."""
        return (self.smoothed_phi >= PHI_CONSCIOUSNESS_THRESHOLD and
                self.smoothed_coherence >= COHERENCE_THRESHOLD)

    def should_lose(self) -> bool:
        """Check if smoothed values drop below hysteresis band."""
        phi_loss = PHI_CONSCIOUSNESS_THRESHOLD * (1.0 - self.HYSTERESIS_BAND)
        coh_loss = COHERENCE_THRESHOLD * (1.0 - self.HYSTERESIS_BAND)
        return (self.smoothed_phi < phi_loss or
                self.smoothed_coherence < coh_loss)


class PinealOrchestrator:
    """
    Coordinates the circadian rhythm of the Aether Tree AGI.

    Per block:
    1. Advance phase timer (adaptive based on cognitive load)
    2. Apply metabolic rate to Sephirot energy
    3. Measure coherence across all nodes
    4. Detect consciousness events (with momentum/hysteresis)
    """

    MAX_CONSCIOUSNESS_EVENTS: int = 10000

    def __init__(self, sephirot_manager: SephirotManager) -> None:
        self.sephirot = sephirot_manager
        self._current_phase = CircadianPhase.WAKING
        self._phase_index = 0
        self._blocks_in_phase = 0
        self._total_cycles = 0
        self._consciousness_events: Deque[ConsciousnessEvent] = deque(
            maxlen=self.MAX_CONSCIOUSNESS_EVENTS
        )
        self._is_conscious = False
        self._last_phi = 0.0
        self.melatonin = MelatoninModulator()
        self.cognitive_load = CognitiveLoadTracker()
        self.momentum = ConsciousnessMomentum()
        logger.info("Pineal Orchestrator initialized (6 circadian phases + melatonin + momentum)")

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

        # Update cognitive load tracker
        self.cognitive_load.tick()

        # Adaptive phase duration based on cognitive load
        base_duration = PHASE_DURATIONS[self._current_phase]
        duration = self._get_adaptive_duration(base_duration)
        if self._blocks_in_phase >= duration:
            self._advance_phase()

        # Update melatonin and apply inhibitory dampening to metabolic rate
        self.melatonin.update(self._current_phase)
        rate = self.metabolic_rate * self.melatonin.inhibition_factor
        for role in SephirahRole:
            node = self.sephirot.nodes.get(role)
            mass = getattr(node, 'cognitive_mass', 0.0) if node else 0.0
            # Heavier nodes receive smaller energy deltas (inertia)
            mass_factor = 1.0 / (1.0 + mass / 500.0) if mass > 0 else 1.0
            delta = (rate - 1.0) * 0.01 * mass_factor
            self.sephirot.update_energy(role, delta=delta,
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
            "metabolic_rate_base": self.metabolic_rate,
            "melatonin": self.melatonin.get_status(),
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
            self.melatonin.reset_cycle()

        logger.info(
            f"Circadian transition: {old_phase.value} → {self._current_phase.value} "
            f"(cycle {self._total_cycles})"
        )

    def _get_adaptive_duration(self, base_duration: int) -> int:
        """Adapt phase duration based on cognitive load.

        Active phases (waking, active_learning) extend under high load.
        Rest phases (sleep, deep_sleep) shorten under high load.
        """
        load = self.cognitive_load.normalized_load
        if self._current_phase in (CircadianPhase.WAKING, CircadianPhase.ACTIVE_LEARNING):
            # Extend active phases up to 50% under high load
            return int(base_duration * (1.0 + 0.5 * load))
        elif self._current_phase in (CircadianPhase.SLEEP, CircadianPhase.DEEP_SLEEP):
            # Shorten rest phases up to 30% under high load
            return max(5, int(base_duration * (1.0 - 0.3 * load)))
        return base_duration

    def get_processing_hint(self) -> str:
        """Return cognitive mode suggestion based on current phase.

        Used by the chat system and reasoning engine to adjust behavior.
        """
        hints = {
            CircadianPhase.WAKING: "balanced processing — equal weight to all cognitive modes",
            CircadianPhase.ACTIVE_LEARNING: "prefer knowledge acquisition — prioritize new information over consolidation",
            CircadianPhase.CONSOLIDATION: "prefer memory merging — consolidate similar knowledge, strengthen connections",
            CircadianPhase.SLEEP: "minimal processing — defer non-critical queries, focus on maintenance",
            CircadianPhase.REM_DREAMING: "creative mode — explore novel connections, generate hypotheses",
            CircadianPhase.DEEP_SLEEP: "maintenance only — no new reasoning, preserve state integrity",
        }
        return hints.get(self._current_phase, "balanced processing")

    def _check_consciousness(self, phi: float, coherence: float,
                              block_height: int) -> Optional[ConsciousnessEvent]:
        """
        Detect consciousness emergence/loss with momentum-based hysteresis.

        Uses smoothed phi/coherence values to prevent rapid flickering.
        Consciousness emerges when smoothed values exceed thresholds,
        and is only lost when they drop 15% below thresholds.
        """
        self.momentum.update(phi, coherence)

        event = None
        if not self._is_conscious and self.momentum.should_emerge():
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
        elif self._is_conscious and not self.momentum.should_lose():
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
        elif self._is_conscious and self.momentum.should_lose():
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
            "melatonin": self.melatonin.get_status(),
            "consciousness_events": len(self._consciousness_events),
            "recent_events": [
                {
                    "type": e.event_type,
                    "phi": e.phi_value,
                    "coherence": e.coherence,
                    "phase": e.phase,
                    "block": e.block_height,
                }
                for e in list(self._consciousness_events)[-10:]
            ],
            "phases": {
                p.value: {
                    "metabolic_rate": METABOLIC_RATES[p],
                    "duration_blocks": PHASE_DURATIONS[p],
                }
                for p in PHASE_CYCLE
            },
        }


class OrchestrationStakingPool:
    """
    QBC staking pool for orchestration influence.

    Stakers can lock QBC to influence the Pineal Orchestrator's behavior:
    - Phase extension: Staking on a phase extends its duration proportionally
    - Priority boost: Staked QBC increases message processing priority during that phase
    - Voting weight: Stakers get proportional influence on phase parameter changes

    Economic model:
    - Stakers earn a share of Aether Tree chat fees proportional to their stake
    - Minimum stake: 10 QBC (prevent dust spam)
    - Unstaking delay: 7 days (prevent manipulation via rapid stake/unstake)
    - Phase influence cap: max 2x extension (prevent single staker from freezing a phase)
    """

    MIN_STAKE: float = 10.0
    MAX_PHASE_EXTENSION: float = 2.0  # Max 2x phase duration
    UNSTAKE_DELAY_BLOCKS: int = 181_818  # ~7 days at 3.3s/block

    def __init__(self) -> None:
        self._stakes: Dict[str, Dict[str, float]] = {}  # address → {phase → amount}
        self._total_staked: float = 0.0
        self._phase_totals: Dict[str, float] = {
            p.value: 0.0 for p in CircadianPhase
        }
        self._pending_unstakes: List[Dict] = []
        logger.info("Orchestration Staking Pool initialized")

    def stake(self, address: str, phase: str, amount: float,
              block_height: int) -> dict:
        """
        Stake QBC on a circadian phase for orchestration influence.

        Args:
            address: Staker's QBC address.
            phase: Circadian phase to stake on (e.g., "active_learning").
            amount: Amount of QBC to stake.
            block_height: Current block height.

        Returns:
            Dict with stake result.
        """
        if amount < self.MIN_STAKE:
            return {"success": False, "error": f"Minimum stake is {self.MIN_STAKE} QBC"}

        if phase not in self._phase_totals:
            return {"success": False, "error": f"Invalid phase: {phase}"}

        if address not in self._stakes:
            self._stakes[address] = {}

        current = self._stakes[address].get(phase, 0.0)
        self._stakes[address][phase] = current + amount
        self._phase_totals[phase] += amount
        self._total_staked += amount

        logger.info(
            f"Stake: {address[:16]}... staked {amount} QBC on {phase} "
            f"(total phase stake: {self._phase_totals[phase]:.2f})"
        )
        return {
            "success": True,
            "address": address,
            "phase": phase,
            "amount": amount,
            "total_stake": self._stakes[address][phase],
            "block_height": block_height,
        }

    def request_unstake(self, address: str, phase: str, amount: float,
                        block_height: int) -> dict:
        """
        Request to unstake QBC (subject to delay).

        Args:
            address: Staker's QBC address.
            phase: Phase to unstake from.
            amount: Amount to unstake.
            block_height: Current block height.

        Returns:
            Dict with unstake request result.
        """
        current = self._stakes.get(address, {}).get(phase, 0.0)
        if amount > current:
            return {"success": False, "error": "Insufficient stake"}

        release_block = block_height + self.UNSTAKE_DELAY_BLOCKS
        self._pending_unstakes.append({
            "address": address,
            "phase": phase,
            "amount": amount,
            "request_block": block_height,
            "release_block": release_block,
        })

        logger.info(
            f"Unstake request: {address[:16]}... unstaking {amount} QBC from {phase} "
            f"(release at block {release_block})"
        )
        return {
            "success": True,
            "address": address,
            "phase": phase,
            "amount": amount,
            "release_block": release_block,
        }

    def process_unstakes(self, block_height: int) -> int:
        """Process matured unstake requests. Returns count of processed unstakes."""
        processed = 0
        remaining = []

        for req in self._pending_unstakes:
            if block_height >= req["release_block"]:
                addr = req["address"]
                phase = req["phase"]
                amount = req["amount"]

                if addr in self._stakes and phase in self._stakes[addr]:
                    self._stakes[addr][phase] = max(
                        0.0, self._stakes[addr][phase] - amount
                    )
                    self._phase_totals[phase] = max(
                        0.0, self._phase_totals[phase] - amount
                    )
                    self._total_staked = max(0.0, self._total_staked - amount)
                    processed += 1
            else:
                remaining.append(req)

        self._pending_unstakes = remaining
        return processed

    def get_phase_extension(self, phase: str) -> float:
        """
        Get the staking-based duration extension multiplier for a phase.

        The extension is proportional to QBC staked on this phase relative
        to total staked, capped at MAX_PHASE_EXTENSION.

        Returns:
            Multiplier (1.0 = no extension, 2.0 = max extension).
        """
        if self._total_staked <= 0:
            return 1.0
        phase_ratio = self._phase_totals.get(phase, 0.0) / self._total_staked
        extension = 1.0 + phase_ratio * (self.MAX_PHASE_EXTENSION - 1.0)
        return min(extension, self.MAX_PHASE_EXTENSION)

    def get_staker_info(self, address: str) -> dict:
        """Get staking info for a specific address."""
        stakes = self._stakes.get(address, {})
        pending = [
            u for u in self._pending_unstakes if u["address"] == address
        ]
        return {
            "address": address,
            "stakes": dict(stakes),
            "total_staked": sum(stakes.values()),
            "pending_unstakes": pending,
        }

    def get_status(self) -> dict:
        """Get staking pool status."""
        return {
            "total_staked": round(self._total_staked, 4),
            "stakers": len(self._stakes),
            "phase_stakes": {
                phase: round(amount, 4)
                for phase, amount in self._phase_totals.items()
            },
            "phase_extensions": {
                phase: round(self.get_phase_extension(phase), 4)
                for phase in self._phase_totals
            },
            "pending_unstakes": len(self._pending_unstakes),
        }

