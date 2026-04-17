"""
Belief Revision — AGM-style belief revision on contradicting evidence.

Implements expansion, contraction, and revision operators with
epistemic entrenchment for minimal change.

AI Roadmap Item #64.
"""
from typing import Dict, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


class BeliefRevision:
    """AGM-style belief revision with epistemic entrenchment.

    Maintains a belief set with entrenchment scores (higher = harder to give up).
    Supports:
    - Expansion: add new belief (no contradictions)
    - Contraction: remove a belief (minimal change)
    - Revision: add new belief, removing contradictions
    """

    def __init__(self, max_beliefs: int = 5000) -> None:
        # belief -> entrenchment score (0.0 to 1.0)
        self._beliefs: Dict[str, float] = {}
        self._max_beliefs: int = max_beliefs

        # Contradiction rules: (belief_a, belief_b) pairs that conflict
        self._contradictions: List[Tuple[str, str]] = []
        self._max_contradictions: int = 2000

        # Stats
        self._expansions: int = 0
        self._contractions: int = 0
        self._revisions: int = 0
        self._contradictions_detected: int = 0
        self._beliefs_removed: int = 0

    def expand(self, belief_set: Set[str], belief: str,
               entrenchment: float = 0.5) -> Set[str]:
        """Expand the belief set by adding a new belief.

        AGM expansion: K + p = Cn(K union {p})
        Simply adds the belief if no contradiction exists.

        Args:
            belief_set: Current beliefs.
            belief: New belief to add.
            entrenchment: How entrenched this new belief is.

        Returns:
            Expanded belief set.
        """
        self._expansions += 1
        result = set(belief_set)
        result.add(belief)
        self._beliefs[belief] = entrenchment
        self._enforce_capacity()
        return result

    def contract(self, belief_set: Set[str], belief: str) -> Set[str]:
        """Contract the belief set by removing a belief.

        AGM contraction: K - p = maximal subset of K that doesn't imply p.
        Uses epistemic entrenchment for minimal change.

        Args:
            belief_set: Current beliefs.
            belief: Belief to remove.

        Returns:
            Contracted belief set.
        """
        self._contractions += 1
        result = set(belief_set)

        if belief not in result:
            return result

        result.discard(belief)
        self._beliefs.pop(belief, None)
        self._beliefs_removed += 1

        # Also remove beliefs that only made sense in context of removed belief
        # (beliefs with lower entrenchment that reference the same concepts)
        removed_words = set(belief.lower().split())
        to_remove = []
        for b in result:
            if b == belief:
                continue
            b_words = set(b.lower().split())
            overlap = len(removed_words & b_words) / max(len(b_words), 1)
            b_entrenchment = self._beliefs.get(b, 0.5)
            # Remove low-entrenchment beliefs with high word overlap
            if overlap > 0.5 and b_entrenchment < 0.3:
                to_remove.append(b)

        for b in to_remove:
            result.discard(b)
            self._beliefs.pop(b, None)
            self._beliefs_removed += 1

        return result

    def revise(self, belief_set: Set[str], new_evidence: str,
               entrenchment: float = 0.6) -> Set[str]:
        """Revise the belief set with new evidence.

        AGM revision: K * p = (K - ~p) + p
        If new evidence contradicts existing beliefs, remove the
        least entrenched contradicting beliefs, then add the new one.

        Args:
            belief_set: Current beliefs.
            new_evidence: New belief to integrate.
            entrenchment: Entrenchment of the new evidence.

        Returns:
            Revised belief set.
        """
        self._revisions += 1
        result = set(belief_set)

        # Find contradicting beliefs
        contradicting = self._find_contradicting(result, new_evidence)

        if contradicting:
            # Remove contradicting beliefs, starting with least entrenched
            sorted_contra = sorted(
                contradicting,
                key=lambda b: self._beliefs.get(b, 0.5),
            )
            for b in sorted_contra:
                b_entrenchment = self._beliefs.get(b, 0.5)
                if b_entrenchment < entrenchment:
                    result.discard(b)
                    self._beliefs.pop(b, None)
                    self._beliefs_removed += 1
                    logger.debug(
                        f"Belief revision: removed '{b[:60]}...' "
                        f"(entrenchment={b_entrenchment:.3f}) "
                        f"in favor of new evidence"
                    )

        # Add new evidence
        result.add(new_evidence)
        self._beliefs[new_evidence] = entrenchment
        self._enforce_capacity()

        return result

    def _find_contradicting(self, belief_set: Set[str], belief: str) -> List[str]:
        """Find beliefs in the set that contradict the given belief."""
        contradicting = []

        # Check registered contradiction rules
        for a, b in self._contradictions:
            if a == belief and b in belief_set:
                contradicting.append(b)
            elif b == belief and a in belief_set:
                contradicting.append(a)

        # Heuristic: detect negation patterns
        belief_lower = belief.lower().strip()
        for existing in belief_set:
            existing_lower = existing.lower().strip()
            # "X increases" vs "X decreases"
            if self._is_negation(belief_lower, existing_lower):
                contradicting.append(existing)

        return list(set(contradicting))

    def _is_negation(self, a: str, b: str) -> bool:
        """Heuristic check if two beliefs negate each other."""
        negation_pairs = [
            ("increases", "decreases"),
            ("positive", "negative"),
            ("true", "false"),
            ("high", "low"),
            ("grows", "shrinks"),
            ("improves", "degrades"),
            ("rising", "falling"),
        ]
        for pos, neg in negation_pairs:
            if pos in a and neg in b:
                # Check they share a subject (first significant word)
                a_words = set(a.split()) - {"when", "the", "a", "is", "are", "has", "have"}
                b_words = set(b.split()) - {"when", "the", "a", "is", "are", "has", "have"}
                overlap = a_words & b_words
                if len(overlap) >= 1:
                    return True
            if neg in a and pos in b:
                a_words = set(a.split()) - {"when", "the", "a", "is", "are", "has", "have"}
                b_words = set(b.split()) - {"when", "the", "a", "is", "are", "has", "have"}
                overlap = a_words & b_words
                if len(overlap) >= 1:
                    return True
        return False

    def add_contradiction_rule(self, belief_a: str, belief_b: str) -> None:
        """Register that two beliefs are contradictory."""
        self._contradictions.append((belief_a, belief_b))
        if len(self._contradictions) > self._max_contradictions:
            self._contradictions = self._contradictions[-self._max_contradictions:]

    def detect_contradiction(self, belief_set: Set[str]) -> Optional[Tuple[str, str]]:
        """Detect the first contradiction in the belief set.

        Returns:
            Tuple of (belief_a, belief_b) if contradiction found, else None.
        """
        # Check registered contradiction rules
        for a, b in self._contradictions:
            if a in belief_set and b in belief_set:
                self._contradictions_detected += 1
                return (a, b)

        # Heuristic negation check
        beliefs_list = list(belief_set)
        for i in range(len(beliefs_list)):
            for j in range(i + 1, len(beliefs_list)):
                if self._is_negation(beliefs_list[i].lower(), beliefs_list[j].lower()):
                    self._contradictions_detected += 1
                    return (beliefs_list[i], beliefs_list[j])

        return None

    def get_entrenchment(self, belief: str) -> float:
        """Get the entrenchment score of a belief."""
        return self._beliefs.get(belief, 0.0)

    def set_entrenchment(self, belief: str, score: float) -> None:
        """Set the entrenchment score of a belief."""
        self._beliefs[belief] = max(0.0, min(1.0, score))

    def _enforce_capacity(self) -> None:
        """Remove least-entrenched beliefs if over capacity."""
        if len(self._beliefs) <= self._max_beliefs:
            return
        sorted_beliefs = sorted(self._beliefs.items(), key=lambda x: x[1])
        excess = len(self._beliefs) - self._max_beliefs
        for belief, _ in sorted_beliefs[:excess]:
            del self._beliefs[belief]
            self._beliefs_removed += 1

    def get_stats(self) -> dict:
        """Return belief revision statistics."""
        entrenchment_vals = list(self._beliefs.values())
        return {
            "total_beliefs": len(self._beliefs),
            "expansions": self._expansions,
            "contractions": self._contractions,
            "revisions": self._revisions,
            "contradictions_detected": self._contradictions_detected,
            "beliefs_removed": self._beliefs_removed,
            "contradiction_rules": len(self._contradictions),
            "avg_entrenchment": (
                sum(entrenchment_vals) / len(entrenchment_vals)
                if entrenchment_vals else 0.0
            ),
        }
