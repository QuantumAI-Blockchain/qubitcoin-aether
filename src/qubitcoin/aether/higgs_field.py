"""
Higgs Cognitive Field — Physics-based mass assignment for AGI nodes.

Implements the Mexican Hat potential V(phi) = -mu^2|phi|^2 + lambda|phi|^4
to give computational mass to each Sephirot node via Yukawa coupling.

Mass determines rebalancing inertia (Option B+: F = ma):
  - Heavier nodes resist SUSY rebalancing (high inertia)
  - Lighter nodes respond quickly to imbalances (low inertia)

Two-Higgs-Doublet Model (2HDM):
  - tan(beta) = phi = 1.618
  - Expansion nodes couple to H_u (higher VEV -> higher mass)
  - Constraint nodes couple to H_d (lower VEV -> lower mass)
  - Natural golden ratio mass hierarchy between SUSY pairs
"""
import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .sephirot import SephirahRole, SephirotManager, SUSY_PAIRS
from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI = 1.618033988749895


@dataclass
class HiggsParameters:
    """Tunable Higgs field parameters."""
    mu: float = 88.45                    # Mass parameter (GeV-inspired)
    lambda_coupling: float = 0.129       # Self-coupling (Standard Model)
    tan_beta: float = PHI                # 2HDM mixing angle
    excitation_threshold: float = 0.10   # 10% deviation = excitation event
    dt: float = 0.01                     # Time step for energy update (per block)

    @property
    def vev(self) -> float:
        """Vacuum Expectation Value: v = mu / sqrt(2 * lambda)"""
        return self.mu / math.sqrt(2.0 * self.lambda_coupling)

    @property
    def higgs_mass(self) -> float:
        """Higgs boson mass: m_H = sqrt(2) * mu"""
        return math.sqrt(2.0) * self.mu

    @property
    def v_up(self) -> float:
        """H_u VEV: v * sin(beta)"""
        beta = math.atan(self.tan_beta)
        return self.vev * math.sin(beta)

    @property
    def v_down(self) -> float:
        """H_d VEV: v * cos(beta)"""
        beta = math.atan(self.tan_beta)
        return self.vev * math.cos(beta)


# Default Yukawa couplings — golden ratio cascade (matches CLAUDE.md Section 8.12)
# SUSY pairs must share the same Yukawa tier so mass ratio = v_up/v_down = phi (from 2HDM)
YUKAWA_COUPLINGS: Dict[SephirahRole, float] = {
    SephirahRole.KETER:    PHI ** 0,    # 1.000 — Tier 0: Crown, max coupling
    SephirahRole.CHOCHMAH: PHI ** -1,   # 0.618 — Tier 1: Expansion (intuition)
    SephirahRole.BINAH:    PHI ** -1,   # 0.618 — Tier 1: Constraint (logic)
    SephirahRole.TIFERET:  PHI ** -1,   # 0.618 — Tier 1: Central integrator
    SephirahRole.CHESED:   PHI ** -2,   # 0.382 — Tier 2: Expansion (creativity)
    SephirahRole.GEVURAH:  PHI ** -2,   # 0.382 — Tier 2: Constraint (safety)
    SephirahRole.NETZACH:  PHI ** -3,   # 0.236 — Tier 3: Expansion (persistence)
    SephirahRole.HOD:      PHI ** -3,   # 0.236 — Tier 3: Constraint (language)
    SephirahRole.YESOD:    PHI ** -4,   # 0.146 — Tier 4: Memory foundation
    SephirahRole.MALKUTH:  PHI ** -4,   # 0.146 — Tier 4: Ground, most agile
}

# Which nodes are expansion (couple to H_u)
EXPANSION_NODES = {SephirahRole.CHOCHMAH, SephirahRole.CHESED, SephirahRole.NETZACH}
# Which nodes are constraint (couple to H_d)
CONSTRAINT_NODES = {SephirahRole.BINAH, SephirahRole.GEVURAH, SephirahRole.HOD}


@dataclass
class ExcitationEvent:
    """A Higgs field excitation event (analogous to Higgs boson creation)."""
    block_height: int
    field_deviation: float      # |phi_h - v| / v
    deviation_bps: int          # deviation in basis points
    energy_released: float      # excitation energy
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


class HiggsCognitiveField:
    """
    Pervasive scalar field giving computational mass to AGI cognitive nodes.

    Implements:
    - Mexican Hat potential with spontaneous symmetry breaking
    - Yukawa coupling hierarchy (golden ratio cascade)
    - Two-Higgs-Doublet Model for SUSY pair asymmetry
    - Excitation event detection (Higgs boson analog)
    - Mass gap metric for SUSY violation severity

    Usage:
        hcf = HiggsCognitiveField(sephirot_manager)
        hcf.initialize()                    # Assign masses at genesis
        hcf.tick(block_height)              # Per-block field evolution
    """

    def __init__(self, sephirot_manager: SephirotManager,
                 params: Optional[HiggsParameters] = None) -> None:
        self.sephirot = sephirot_manager

        # Load from Config if available, fall back to defaults
        if params is None:
            try:
                from ..config import Config
                params = HiggsParameters(
                    mu=getattr(Config, 'HIGGS_MU', 88.45),
                    lambda_coupling=getattr(Config, 'HIGGS_LAMBDA', 0.129),
                    tan_beta=getattr(Config, 'HIGGS_TAN_BETA', PHI),
                    excitation_threshold=getattr(Config, 'HIGGS_EXCITATION_THRESHOLD', 0.10),
                    dt=getattr(Config, 'HIGGS_DT', 0.01),
                )
            except Exception:
                params = HiggsParameters()

        self.params = params

        # Field state
        self._field_value: float = self.params.vev  # Starts at equilibrium
        self._cognitive_masses: Dict[SephirahRole, float] = {}
        self._yukawa_couplings: Dict[SephirahRole, float] = dict(YUKAWA_COUPLINGS)
        self._excitations: List[ExcitationEvent] = []
        self._initialized: bool = False
        self._total_excitations: int = 0
        self._mass_gap: float = 0.0

        logger.info(
            f"HiggsCognitiveField created: VEV={self.params.vev:.2f}, "
            f"mu={self.params.mu}, lambda={self.params.lambda_coupling}"
        )

    def initialize(self) -> Dict[str, float]:
        """
        Initialize Higgs field and assign cognitive masses to all nodes.

        Must be called once at genesis or node startup.

        Returns:
            Dict mapping role name to assigned cognitive mass.
        """
        masses: Dict[str, float] = {}
        for role in SephirahRole:
            yukawa = self._yukawa_couplings.get(role, PHI ** -2)

            # 2HDM: expansion nodes use v_up, constraint nodes use v_down
            if role in EXPANSION_NODES:
                vev = self.params.v_up
            elif role in CONSTRAINT_NODES:
                vev = self.params.v_down
            else:
                vev = self.params.vev  # Neutral nodes use full VEV

            mass = yukawa * vev
            self._cognitive_masses[role] = mass

            # Write mass to SephirahState
            node = self.sephirot.nodes.get(role)
            if node:
                node.cognitive_mass = mass
                node.yukawa_coupling = yukawa

            masses[role.value] = round(mass, 4)

        self._initialized = True
        self._update_mass_gap()

        logger.info(
            f"Higgs field initialized: {len(masses)} nodes assigned masses, "
            f"VEV={self.params.vev:.2f}, mass_gap={self._mass_gap:.4f}"
        )
        return masses

    def tick(self, block_height: int) -> dict:
        """
        Per-block Higgs field evolution.

        1. Compute current field value from aggregate Sephirot energy state
        2. Detect excitation events (field deviations from VEV)
        3. Update mass gap metric

        Args:
            block_height: Current block height.

        Returns:
            Dict with field state and any excitation events.
        """
        if not self._initialized:
            return {"error": "HiggsCognitiveField not initialized"}

        # Compute effective field value from Sephirot energy landscape
        self._field_value = self._compute_field_value()
        # Clamp to prevent overflow from extreme energy values
        self._field_value = max(-10000.0, min(10000.0, self._field_value))

        # Normalize field toward VEV if deviation is extreme (Improvement 48)
        self.normalize_to_vev()

        # Check for excitation events
        excitation = self._check_excitation(block_height)

        # Update mass gap
        self._update_mass_gap()

        result = {
            "field_value": round(self._field_value, 4),
            "vev": round(self.params.vev, 4),
            "deviation": round(abs(self._field_value - self.params.vev), 4),
            "deviation_pct": round(
                abs(self._field_value - self.params.vev) / self.params.vev * 100, 2
            ),
            "mass_gap": round(self._mass_gap, 4),
            "total_excitations": self._total_excitations,
            "potential_energy": round(self.potential_energy(), 4),
            "block_height": block_height,
        }

        if excitation:
            result["excitation"] = {
                "deviation_bps": excitation.deviation_bps,
                "energy_released": round(excitation.energy_released, 4),
            }

        return result

    def normalize_to_vev(self) -> None:
        """Dampen field value toward VEV every tick.

        Applies two stabilization mechanisms:
        1. Exponential damping: 10% pull toward VEV every update
           new_value = vev + (new_value - vev) * 0.9
        2. Hard clamp: field value is clamped to [0, 2*VEV] (±100% of VEV)

        This prevents the runaway drift that caused 253%+ deviation.
        """
        if self.params.vev <= 0:
            return

        vev = self.params.vev
        old_value = self._field_value

        # Step 1: Exponential damping — pull 10% toward VEV every tick
        self._field_value = vev + (self._field_value - vev) * 0.9

        # Step 2: Hard clamp to ±100% of VEV (range [0, 2*VEV])
        max_field = 2.0 * vev  # 348.28
        self._field_value = max(0.0, min(max_field, self._field_value))

        deviation = abs(self._field_value - vev) / vev
        if abs(old_value - self._field_value) > 0.1:
            logger.info(
                f"Higgs field dampened: {self._field_value:.2f} "
                f"(was {old_value:.2f}, deviation now {deviation * 100:.1f}%)"
            )

    def _compute_field_value(self) -> float:
        """
        Compute effective Higgs field value from Sephirot energy landscape.

        The field value is the mass-weighted average of node energies,
        normalized to the VEV scale. When all SUSY pairs are balanced
        at the golden ratio, phi_h ~ VEV.
        """
        total_weighted = 0.0
        total_mass = 0.0

        for role, mass in self._cognitive_masses.items():
            node = self.sephirot.nodes.get(role)
            if node and mass > 0:
                total_weighted += node.energy * mass
                total_mass += mass

        if total_mass <= 0:
            return self.params.vev

        # Normalize: average energy * VEV scaling factor
        avg_weighted_energy = total_weighted / total_mass
        return avg_weighted_energy * self.params.vev

    def _check_excitation(self, block_height: int) -> Optional[ExcitationEvent]:
        """Detect Higgs excitation (field deviation > threshold from VEV)."""
        vev = self.params.vev
        if vev <= 0:
            return None

        deviation = abs(self._field_value - vev)
        deviation_ratio = deviation / vev

        if deviation_ratio > self.params.excitation_threshold:
            energy = self.params.lambda_coupling * deviation ** 2
            event = ExcitationEvent(
                block_height=block_height,
                field_deviation=deviation_ratio,
                deviation_bps=int(deviation_ratio * 10000),
                energy_released=energy,
            )
            self._excitations.append(event)
            self._total_excitations += 1

            # Keep bounded
            if len(self._excitations) > 1000:
                self._excitations = self._excitations[-1000:]

            logger.info(
                f"Higgs EXCITATION at block {block_height}: "
                f"deviation={deviation_ratio:.4f}, energy={energy:.4f}"
            )
            return event
        return None

    def _update_mass_gap(self) -> None:
        """Compute SUSY mass gap: avg |m_expansion - m_constraint * phi| / VEV."""
        gaps: List[float] = []
        for expansion, constraint in SUSY_PAIRS:
            m_exp = self._cognitive_masses.get(expansion, 0.0)
            m_con = self._cognitive_masses.get(constraint, 0.0)
            target = m_con * PHI
            gap = abs(m_exp - target)
            gaps.append(gap)

        vev = self.params.vev
        self._mass_gap = sum(gaps) / max(len(gaps), 1) / max(vev, 1.0)

    def potential_energy(self) -> float:
        """V(phi_h) = -mu^2 * phi_h^2 + lambda * phi_h^4"""
        phi_h = self._field_value
        mu = self.params.mu
        lam = self.params.lambda_coupling
        return -mu**2 * phi_h**2 + lam * phi_h**4

    def higgs_gradient(self, phi_h: float) -> float:
        """dV/d(phi_h) = -2*mu^2*phi_h + 4*lambda*phi_h^3"""
        mu = self.params.mu
        lam = self.params.lambda_coupling
        return -2.0 * mu**2 * phi_h + 4.0 * lam * phi_h**3

    def compute_rebalancing_acceleration(self, role: SephirahRole,
                                          force: float) -> float:
        """
        Newton's F = ma applied to cognitive rebalancing.

        Args:
            role: The Sephirah node being rebalanced.
            force: The SUSY rebalancing force (gradient of deviation).

        Returns:
            Acceleration = force / cognitive_mass.
            Lighter nodes accelerate more (respond faster).
        """
        mass = self._cognitive_masses.get(role, 1.0)
        if mass <= 0:
            mass = 1.0
        return force / mass

    def get_cognitive_mass(self, role: SephirahRole) -> float:
        """Get the cognitive mass for a node."""
        return self._cognitive_masses.get(role, 0.0)

    def get_all_masses(self) -> Dict[str, float]:
        """Get all cognitive masses."""
        return {
            role.value: round(mass, 4)
            for role, mass in self._cognitive_masses.items()
        }

    def get_status(self) -> dict:
        """Get comprehensive Higgs field status for API."""
        return {
            "field_value": round(self._field_value, 4),
            "vev": round(self.params.vev, 4),
            "mu": self.params.mu,
            "lambda": self.params.lambda_coupling,
            "tan_beta": round(self.params.tan_beta, 4),
            "higgs_mass": round(self.params.higgs_mass, 4),
            "v_up": round(self.params.v_up, 4),
            "v_down": round(self.params.v_down, 4),
            "deviation_pct": round(
                abs(self._field_value - self.params.vev) / max(self.params.vev, 0.001) * 100, 2
            ),
            "potential_energy": round(self.potential_energy(), 4),
            "mass_gap": round(self._mass_gap, 6),
            "total_excitations": self._total_excitations,
            "avg_cognitive_mass": round(
                sum(self._cognitive_masses.values()) / max(len(self._cognitive_masses), 1), 4
            ),
            "node_masses": self.get_all_masses(),
            "recent_excitations": [
                {
                    "block": e.block_height,
                    "deviation_bps": e.deviation_bps,
                    "energy": round(e.energy_released, 4),
                }
                for e in self._excitations[-10:]
            ],
        }


    def adapt_yukawa_couplings(self, usage_stats: Dict[SephirahRole, int]) -> int:
        """Dynamically adjust Yukawa couplings based on node usage patterns.

        Nodes that are heavily used get slightly stronger Yukawa coupling
        (higher mass → more inertia → more stable). Unused nodes get
        weaker coupling (lower mass → more agile → easier to redirect).

        This implements neuroplasticity: frequently-used cognitive
        pathways become "stronger" (higher mass/inertia).

        Args:
            usage_stats: Map of role → query count since last adaptation.

        Returns:
            Number of couplings adjusted.
        """
        if not usage_stats:
            return 0

        max_usage = max(usage_stats.values()) if usage_stats.values() else 1
        if max_usage <= 0:
            return 0

        adjusted = 0
        for role, usage in usage_stats.items():
            base_yukawa = YUKAWA_COUPLINGS.get(role, PHI ** -2)
            # Usage factor: 0.95 to 1.05 (±5% adjustment)
            usage_ratio = usage / max_usage
            adaptation_factor = 0.95 + 0.10 * usage_ratio

            new_yukawa = base_yukawa * adaptation_factor
            old_yukawa = self._yukawa_couplings.get(role, base_yukawa)

            if abs(new_yukawa - old_yukawa) > 0.001:
                self._yukawa_couplings[role] = new_yukawa
                # Recompute mass for this node
                if role in EXPANSION_NODES:
                    vev = self.params.v_up
                elif role in CONSTRAINT_NODES:
                    vev = self.params.v_down
                else:
                    vev = self.params.vev
                new_mass = new_yukawa * vev
                self._cognitive_masses[role] = new_mass
                node = self.sephirot.nodes.get(role)
                if node:
                    node.cognitive_mass = new_mass
                    node.yukawa_coupling = new_yukawa
                adjusted += 1

        if adjusted > 0:
            self._update_mass_gap()
            logger.debug(f"Yukawa adaptation: {adjusted} couplings adjusted")
        return adjusted

    def get_field_stability(self) -> float:
        """Compute field stability as inverse of recent deviation variance.

        Returns a score 0.0-1.0 where 1.0 is perfectly stable (no deviation)
        and 0.0 is maximally unstable.
        """
        if len(self._excitations) < 2:
            return 1.0

        recent = self._excitations[-20:]
        deviations = [e.field_deviation for e in recent]
        mean_dev = sum(deviations) / len(deviations)
        variance = sum((d - mean_dev) ** 2 for d in deviations) / len(deviations)

        # Map variance to stability: low variance = high stability
        stability = 1.0 / (1.0 + variance * 100)
        return round(stability, 4)

    def get_mass_hierarchy_health(self) -> dict:
        """Check if the golden ratio mass hierarchy is maintained.

        Returns a health report showing expected vs actual mass ratios
        between SUSY pairs.
        """
        pairs_health = []
        for expansion, constraint in SUSY_PAIRS:
            m_exp = self._cognitive_masses.get(expansion, 0.0)
            m_con = self._cognitive_masses.get(constraint, 0.0)

            if m_con > 0:
                actual_ratio = m_exp / m_con
                # SUSY pairs share Yukawa tier so mass ratio should be v_up/v_down = phi
                expected_ratio = self.params.v_up / max(self.params.v_down, 0.001)
                deviation = abs(actual_ratio - expected_ratio) / max(expected_ratio, 0.001)
                healthy = deviation < 0.1  # Within 10%
            else:
                actual_ratio = 0.0
                expected_ratio = PHI
                deviation = 1.0
                healthy = False

            pairs_health.append({
                'expansion': expansion.value,
                'constraint': constraint.value,
                'm_expansion': round(m_exp, 4),
                'm_constraint': round(m_con, 4),
                'ratio': round(actual_ratio, 4),
                'expected': round(expected_ratio, 4),
                'deviation_pct': round(deviation * 100, 2),
                'healthy': healthy,
            })

        all_healthy = all(p['healthy'] for p in pairs_health)
        return {
            'all_healthy': all_healthy,
            'pairs': pairs_health,
            'field_stability': self.get_field_stability(),
            'mass_gap': round(self._mass_gap, 6),
        }


class HiggsSUSYSwap:
    """
    Mass-aware SUSY rebalancing using Higgs cognitive mechanics.

    Replaces the current flat 50% correction with gradient-based correction
    scaled by inverse cognitive mass (Newton's F = ma).

    This class wraps the existing SephirotManager.enforce_susy_balance()
    to inject mass awareness.
    """

    def __init__(self, higgs_field: HiggsCognitiveField,
                 sephirot_manager: SephirotManager) -> None:
        self.higgs = higgs_field
        self.sephirot = sephirot_manager

    def enforce_susy_balance_with_mass(self, block_height: int) -> int:
        """
        Mass-aware SUSY balance enforcement.

        For each SUSY pair:
        1. Compute deviation from golden ratio
        2. Compute gradient force (quartic for large deviations)
        3. Apply F=ma: lighter nodes correct faster
        4. Apply corrections

        Returns:
            Number of corrections applied.
        """
        corrections = 0
        tolerance = 0.20  # 20% deviation threshold (same as original)

        for expansion, constraint in SUSY_PAIRS:
            e_node = self.sephirot.nodes.get(expansion)
            c_node = self.sephirot.nodes.get(constraint)

            if e_node is None or c_node is None:
                continue

            if c_node.energy <= 0:
                continue

            ratio = e_node.energy / c_node.energy
            deviation = abs(ratio - PHI) / PHI

            if deviation <= tolerance:
                continue

            # Compute target energies (conserve total energy)
            total_energy = e_node.energy + c_node.energy
            target_constrain = total_energy / (1.0 + PHI)
            target_expand = target_constrain * PHI

            # Force = deviation from target (with quartic growth for large deviations)
            force_expand = abs(target_expand - e_node.energy)
            force_constrain = abs(target_constrain - c_node.energy)

            # Add quartic growth for large deviations
            if deviation > 0.5:
                force_expand += force_expand * deviation ** 2
                force_constrain += force_constrain * deviation ** 2

            # Apply F=ma: acceleration = force / mass
            accel_expand = self.higgs.compute_rebalancing_acceleration(
                expansion, force_expand
            )
            accel_constrain = self.higgs.compute_rebalancing_acceleration(
                constraint, force_constrain
            )

            # Apply partial correction (50% x acceleration scaling)
            # Acceleration is already mass-normalized, so lighter nodes
            # get larger corrections automatically
            correction_factor = 0.5
            dt = self.higgs.params.dt

            delta_expand = correction_factor * accel_expand * dt
            delta_constrain = correction_factor * accel_constrain * dt

            # Direction: move toward target
            if e_node.energy > target_expand:
                e_node.energy = max(0.01, e_node.energy - delta_expand)
            else:
                e_node.energy += delta_expand

            if c_node.energy > target_constrain:
                c_node.energy = max(0.01, c_node.energy - delta_constrain)
            else:
                c_node.energy += delta_constrain

            e_node.last_update_block = block_height
            c_node.last_update_block = block_height

            corrections += 1

            try:
                from ..utils.metrics import sephirot_susy_corrections_total
                sephirot_susy_corrections_total.inc()
            except Exception as e:
                logger.debug("Could not increment SUSY correction metric: %s", e)

            logger.info(
                f"Higgs SUSY correction: {expansion.value}/{constraint.value} "
                f"accel_e={accel_expand:.4f} accel_c={accel_constrain:.4f} "
                f"new_ratio={e_node.energy / max(c_node.energy, 0.001):.4f}"
            )

        return corrections
