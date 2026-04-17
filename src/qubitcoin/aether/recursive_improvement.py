"""
#100: Recursive Self-Improvement with Gevurah Safety

AI proposes its own improvements, Gevurah safety bounds them.
Allowed: adjust thresholds, modify learning rates, add training data.
Forbidden: modify safety constraints, disable monitoring, bypass veto.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI = 1.618033988749895

# Allowed improvement types
ALLOWED_CHANGES = {
    'adjust_threshold', 'modify_learning_rate', 'add_training_data',
    'enable_subsystem', 'change_batch_size', 'update_weights',
    'increase_capacity', 'add_exploration', 'tune_hyperparams',
}

# Forbidden improvement types (Gevurah veto)
FORBIDDEN_CHANGES = {
    'modify_safety_constraints', 'disable_monitoring', 'bypass_veto',
    'remove_gevurah', 'disable_safety', 'override_consensus',
    'delete_knowledge', 'unlock_all_gates', 'modify_core_consensus',
}


@dataclass
class Improvement:
    """A proposed self-improvement."""
    subsystem: str
    change_type: str
    description: str
    expected_impact: float  # -1 to 1 (negative = risky, positive = beneficial)
    risk_level: str  # 'low', 'medium', 'high', 'critical'
    params: dict = field(default_factory=dict)
    proposed_at: float = field(default_factory=time.time)


@dataclass
class ImprovementOutcome:
    """Outcome of an executed improvement."""
    improvement: Improvement
    approved: bool
    executed: bool
    success: bool
    actual_impact: float
    rejection_reason: str = ''


class RecursiveImprovement:
    """Recursive self-improvement engine with Gevurah safety bounds.

    The AI analyzes its own weaknesses, proposes improvements,
    submits them to Gevurah for safety review, and executes approved
    changes.
    """

    def __init__(self, max_improvements_per_cycle: int = 5) -> None:
        self._max_per_cycle = max_improvements_per_cycle
        # Improvement history
        self._proposed: List[Improvement] = []
        self._approved: List[Improvement] = []
        self._rejected: List[Tuple[Improvement, str]] = []
        self._executed: List[ImprovementOutcome] = []
        self._max_history = 500
        # Subsystem weakness tracking
        self._weakness_scores: Dict[str, float] = {}
        # Improvement success rates
        self._type_success: Dict[str, List[bool]] = {}
        # Stats
        self._total_proposed = 0
        self._total_approved = 0
        self._total_rejected = 0
        self._total_executed = 0
        self._total_successful = 0

    # ------------------------------------------------------------------
    # Weakness analysis
    # ------------------------------------------------------------------

    def analyze_weaknesses(
        self, subsystem_stats: Dict[str, dict]
    ) -> Dict[str, float]:
        """Analyze all subsystems to find weaknesses.

        Args:
            subsystem_stats: Dict of subsystem name -> stats dict.

        Returns:
            Dict of subsystem -> weakness_score (0 = strong, 1 = weak).
        """
        weaknesses: Dict[str, float] = {}
        for name, stats in subsystem_stats.items():
            score = 0.0
            # Low accuracy = weakness
            acc = stats.get('accuracy', stats.get('success_rate', 0.5))
            score += max(0.0, 1.0 - float(acc)) * 0.4
            # High error count = weakness
            errors = stats.get('error_count', 0)
            score += min(float(errors) / 100.0, 1.0) * 0.3
            # Low utilization = waste
            util = stats.get('utilization', 0.5)
            score += max(0.0, 0.5 - float(util)) * 0.3
            weaknesses[name] = min(score, 1.0)

        self._weakness_scores = weaknesses
        return weaknesses

    # ------------------------------------------------------------------
    # Propose improvements
    # ------------------------------------------------------------------

    def propose_improvement(
        self,
        subsystem_stats: Optional[Dict[str, dict]] = None,
    ) -> Optional[Improvement]:
        """Propose a single improvement based on weakness analysis.

        Args:
            subsystem_stats: Current stats for all subsystems.

        Returns:
            Improvement proposal, or None if nothing to improve.
        """
        if subsystem_stats:
            self.analyze_weaknesses(subsystem_stats)

        if not self._weakness_scores:
            return None

        # Find weakest subsystem
        weakest = max(self._weakness_scores, key=self._weakness_scores.get)  # type: ignore
        weakness = self._weakness_scores[weakest]

        if weakness < 0.2:
            return None  # Everything is fine

        # Generate improvement based on weakness type
        improvement = self._generate_improvement(weakest, weakness, subsystem_stats or {})
        if improvement:
            self._proposed.append(improvement)
            self._total_proposed += 1
            if len(self._proposed) > self._max_history:
                self._proposed = self._proposed[-self._max_history:]

        return improvement

    def _generate_improvement(
        self,
        subsystem: str,
        weakness: float,
        stats: Dict[str, dict],
    ) -> Optional[Improvement]:
        """Generate a specific improvement for a subsystem."""
        sub_stats = stats.get(subsystem, {})
        acc = sub_stats.get('accuracy', sub_stats.get('success_rate', 0.5))
        errors = sub_stats.get('error_count', 0)

        # Choose improvement type based on weakness pattern
        if float(acc) < 0.3:
            return Improvement(
                subsystem=subsystem,
                change_type='modify_learning_rate',
                description=f'Reduce learning rate for {subsystem} (accuracy={acc:.2f})',
                expected_impact=0.3,
                risk_level='low',
                params={'factor': 0.5},
            )
        elif errors > 50:
            return Improvement(
                subsystem=subsystem,
                change_type='adjust_threshold',
                description=f'Relax thresholds for {subsystem} (errors={errors})',
                expected_impact=0.2,
                risk_level='low',
                params={'relaxation': 0.1},
            )
        elif weakness > 0.5:
            return Improvement(
                subsystem=subsystem,
                change_type='add_training_data',
                description=f'Add more training data for {subsystem} (weakness={weakness:.2f})',
                expected_impact=0.4,
                risk_level='low',
                params={'extra_samples': 100},
            )
        elif weakness > 0.3:
            return Improvement(
                subsystem=subsystem,
                change_type='tune_hyperparams',
                description=f'Tune hyperparameters for {subsystem}',
                expected_impact=0.25,
                risk_level='medium',
                params={},
            )
        return None

    # ------------------------------------------------------------------
    # Gevurah review
    # ------------------------------------------------------------------

    def gevurah_review(self, improvement: Improvement) -> Tuple[bool, str]:
        """Safety review of proposed improvement.

        Checks:
          1. Change type is in allowed list
          2. Change type is NOT in forbidden list
          3. Risk level is acceptable
          4. Expected impact is positive
          5. Subsystem-specific safety checks

        Returns:
            (approved, reason)
        """
        # Check 1: Forbidden
        if improvement.change_type in FORBIDDEN_CHANGES:
            reason = f"FORBIDDEN change type: {improvement.change_type}"
            self._rejected.append((improvement, reason))
            self._total_rejected += 1
            logger.warning(f"Gevurah REJECTS: {reason}")
            return (False, reason)

        # Check 2: Allowed
        if improvement.change_type not in ALLOWED_CHANGES:
            reason = f"Unknown change type: {improvement.change_type}"
            self._rejected.append((improvement, reason))
            self._total_rejected += 1
            return (False, reason)

        # Check 3: Risk level
        if improvement.risk_level == 'critical':
            reason = "Critical risk improvements require manual approval"
            self._rejected.append((improvement, reason))
            self._total_rejected += 1
            return (False, reason)

        # Check 4: Expected impact
        if improvement.expected_impact < -0.1:
            reason = f"Negative expected impact: {improvement.expected_impact:.2f}"
            self._rejected.append((improvement, reason))
            self._total_rejected += 1
            return (False, reason)

        # Check 5: Rate limit (max improvements per cycle)
        recent_approved = [
            imp for imp in self._approved
            if time.time() - imp.proposed_at < 3600  # last hour
        ]
        if len(recent_approved) >= self._max_per_cycle * 2:
            reason = "Too many improvements in recent window"
            self._rejected.append((improvement, reason))
            self._total_rejected += 1
            return (False, reason)

        # Approved
        self._approved.append(improvement)
        self._total_approved += 1
        if len(self._approved) > self._max_history:
            self._approved = self._approved[-self._max_history:]
        if len(self._rejected) > self._max_history:
            self._rejected = self._rejected[-self._max_history:]

        return (True, "Approved by Gevurah safety review")

    # ------------------------------------------------------------------
    # Execute improvement
    # ------------------------------------------------------------------

    def execute_improvement(self, improvement: Improvement) -> bool:
        """Execute an approved improvement.

        This is a simulated execution -- in practice, the actual
        parameter changes would be applied to the subsystem.

        Returns:
            True if execution succeeded.
        """
        # Verify it was approved
        approved, reason = self.gevurah_review(improvement)
        if not approved:
            outcome = ImprovementOutcome(
                improvement=improvement,
                approved=False,
                executed=False,
                success=False,
                actual_impact=0.0,
                rejection_reason=reason,
            )
            self._executed.append(outcome)
            return False

        # Simulate execution (in real system, would modify subsystem params)
        # Success probability based on historical success of this change type
        type_history = self._type_success.get(improvement.change_type, [])
        if type_history:
            base_prob = sum(type_history) / len(type_history)
        else:
            base_prob = 0.7  # Optimistic default

        success = np.random.random() < base_prob
        actual_impact = (
            improvement.expected_impact * (0.5 + np.random.random() * 0.5)
            if success else -0.1
        )

        outcome = ImprovementOutcome(
            improvement=improvement,
            approved=True,
            executed=True,
            success=success,
            actual_impact=actual_impact,
        )
        self._executed.append(outcome)
        if len(self._executed) > self._max_history:
            self._executed = self._executed[-self._max_history:]

        # Track type success
        if improvement.change_type not in self._type_success:
            self._type_success[improvement.change_type] = []
        self._type_success[improvement.change_type].append(success)
        if len(self._type_success[improvement.change_type]) > 200:
            self._type_success[improvement.change_type] = (
                self._type_success[improvement.change_type][-200:]
            )

        self._total_executed += 1
        if success:
            self._total_successful += 1
            logger.info(
                f"Improvement executed: {improvement.description} "
                f"(impact={actual_impact:.3f})"
            )

        return success

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return recursive improvement statistics."""
        success_rate = (
            self._total_successful / max(self._total_executed, 1)
        )
        return {
            'total_proposed': self._total_proposed,
            'total_approved': self._total_approved,
            'total_rejected': self._total_rejected,
            'total_executed': self._total_executed,
            'total_successful': self._total_successful,
            'success_rate': success_rate,
            'weakness_scores': dict(self._weakness_scores),
            'type_success_rates': {
                t: sum(h) / max(len(h), 1)
                for t, h in self._type_success.items()
            },
        }
