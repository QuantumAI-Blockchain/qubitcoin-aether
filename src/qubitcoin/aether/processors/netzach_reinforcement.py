"""
Netzach Reinforcement Processor — Strategy evaluation and reward learning.

Netzach is the habitual learning Sephirah. It:
1. Tracks which reasoning strategies have worked historically per domain
2. Recommends the best approach for the current stimulus
3. Learns from feedback (successful/failed reasoning outcomes)
4. Maintains per-domain strategy weights that evolve over time

Netzach answers: "Given what we know about this domain, what reasoning
approach has the best track record?"
"""
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from ..cognitive_processor import (
    CognitiveProcessor,
    CognitiveResponse,
    SoulPriors,
    WorkspaceItem,
)
from ...utils.logger import get_logger

logger = get_logger(__name__)

# Default reasoning strategies that Netzach tracks
DEFAULT_STRATEGIES: List[str] = [
    "deductive",       # Formal logic, syllogism chains
    "inductive",       # Pattern generalization from examples
    "abductive",       # Inference to the best explanation
    "analogical",      # Cross-domain structural mapping
    "causal",          # Cause-effect chain reasoning
    "exploratory",     # Divergent, Chesed-style creative exploration
    "adversarial",     # Debate-style thesis/antithesis
    "retrieval",       # Memory-heavy, rely on stored knowledge
]

# Minimum observations before a strategy is considered reliable
MIN_OBSERVATIONS: int = 3

# Decay factor for older outcomes (exponential recency weighting)
RECENCY_DECAY: float = 0.95


class NetzachReinforcementProcessor(CognitiveProcessor):
    """Strategy evaluation and reinforcement learning processor.

    Maintains a running record of which reasoning strategies succeeded
    or failed for each knowledge domain. Uses these statistics to
    recommend the best strategy for the current stimulus.
    """

    def __init__(self, knowledge_graph: Any = None,
                 soul: Optional[SoulPriors] = None) -> None:
        super().__init__(role="netzach", knowledge_graph=knowledge_graph, soul=soul)

        # {domain: {strategy: [success_bools]}} — chronological order
        self._strategy_records: Dict[str, Dict[str, List[bool]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Global fallback records (domain-agnostic)
        self._global_records: Dict[str, List[bool]] = defaultdict(list)

        # Maximum history per domain-strategy pair to prevent unbounded growth
        self._max_history: int = 200

        logger.info("Netzach reinforcement processor initialized")

    # ------------------------------------------------------------------
    # Public API — called by other processors / orchestrator
    # ------------------------------------------------------------------

    def record_outcome(self, domain: str, strategy: str, success: bool) -> None:
        """Record the outcome of a reasoning attempt.

        Args:
            domain: Knowledge domain the reasoning was in.
            strategy: Which strategy was used (e.g. 'deductive', 'causal').
            success: Whether the reasoning led to a useful result.
        """
        records = self._strategy_records[domain][strategy]
        records.append(success)

        # Trim to max history
        if len(records) > self._max_history:
            self._strategy_records[domain][strategy] = records[-self._max_history:]

        # Also record globally
        global_records = self._global_records[strategy]
        global_records.append(success)
        if len(global_records) > self._max_history:
            self._global_records[strategy] = global_records[-self._max_history:]

        logger.debug(
            "Netzach recorded outcome: domain=%s strategy=%s success=%s "
            "(total=%d for this pair)",
            domain, strategy, success, len(self._strategy_records[domain][strategy]),
        )

    def get_success_rate(self, domain: str, strategy: str) -> Tuple[float, int]:
        """Compute the recency-weighted success rate for a domain-strategy pair.

        Returns:
            Tuple of (weighted_success_rate, observation_count).
        """
        records = self._strategy_records.get(domain, {}).get(strategy, [])
        if not records:
            # Fall back to global records
            records = self._global_records.get(strategy, [])
        if not records:
            return 0.5, 0  # No data — prior of 0.5

        weighted_sum = 0.0
        weight_total = 0.0
        for i, outcome in enumerate(records):
            weight = RECENCY_DECAY ** (len(records) - 1 - i)
            weighted_sum += weight * (1.0 if outcome else 0.0)
            weight_total += weight

        rate = weighted_sum / weight_total if weight_total > 0 else 0.5
        return rate, len(records)

    def get_domain_performance(self, domain: str) -> Dict[str, Dict[str, Any]]:
        """Get success rates for all strategies in a domain.

        Returns:
            Dict mapping strategy name to {rate, observations}.
        """
        performance: Dict[str, Dict[str, Any]] = {}
        strategies = set(DEFAULT_STRATEGIES)
        strategies.update(self._strategy_records.get(domain, {}).keys())
        strategies.update(self._global_records.keys())

        for strategy in sorted(strategies):
            rate, obs = self.get_success_rate(domain, strategy)
            performance[strategy] = {
                "success_rate": round(rate, 3),
                "observations": obs,
                "reliable": obs >= MIN_OBSERVATIONS,
            }
        return performance

    # ------------------------------------------------------------------
    # CognitiveProcessor interface
    # ------------------------------------------------------------------

    def process(self, stimulus: WorkspaceItem) -> CognitiveResponse:
        """Analyze the stimulus domain and recommend the best strategy."""
        t0 = time.time()

        # Determine the domain from context or by searching the KG
        domain = self._detect_domain(stimulus)
        performance = self.get_domain_performance(domain)

        # Rank strategies by success rate (only those with enough data)
        reliable = {
            s: p for s, p in performance.items() if p["reliable"]
        }
        unreliable = {
            s: p for s, p in performance.items() if not p["reliable"]
        }

        if reliable:
            best_strategy = max(reliable, key=lambda s: reliable[s]["success_rate"])
            best_rate = reliable[best_strategy]["success_rate"]
        else:
            # No reliable data — recommend exploratory to gather info
            best_strategy = "exploratory"
            best_rate = 0.5

        # Build a reasoning trace
        trace = [
            {"step": "domain_detection", "domain": domain},
            {"step": "strategy_ranking", "reliable_count": len(reliable)},
            {"step": "recommendation", "strategy": best_strategy, "rate": best_rate},
        ]

        # Construct content describing what Netzach learned
        content_parts: List[str] = []
        content_parts.append(
            f"For the domain '{domain}', I recommend the '{best_strategy}' "
            f"reasoning strategy (success rate: {best_rate:.0%})."
        )

        if reliable:
            ranked = sorted(reliable.items(), key=lambda x: x[1]["success_rate"], reverse=True)
            top_three = ranked[:3]
            summaries = [
                f"{s} ({p['success_rate']:.0%} over {p['observations']} uses)"
                for s, p in top_three
            ]
            content_parts.append(f"Top strategies: {', '.join(summaries)}.")
        else:
            content_parts.append(
                "Not enough data yet for reliable recommendations in this domain. "
                "Suggesting exploratory reasoning to build experience."
            )

        if unreliable:
            under_explored = [s for s in unreliable if unreliable[s]["observations"] < MIN_OBSERVATIONS]
            if under_explored:
                content_parts.append(
                    f"Under-explored strategies worth trying: {', '.join(under_explored[:3])}."
                )

        content = " ".join(content_parts)

        # Confidence: higher when we have more reliable data
        confidence = min(0.9, 0.3 + 0.1 * len(reliable))

        # Relevance: moderate — strategy advice is supportive, not primary
        relevance = 0.4 if stimulus.is_user_message else 0.6

        latency_ms = (time.time() - t0) * 1000
        self._record_metrics(latency_ms, confidence)

        return self._make_response(
            content=content,
            confidence=confidence,
            relevance=relevance,
            novelty=0.3,
            trace=trace,
            metadata={
                "recommended_strategy": best_strategy,
                "domain_performance": {
                    s: p["success_rate"] for s, p in performance.items()
                },
                "domain": domain,
                "reliable_strategies": len(reliable),
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_domain(self, stimulus: WorkspaceItem) -> str:
        """Detect the knowledge domain of the stimulus.

        Uses context hints first, then falls back to KG search.
        """
        # Check explicit context
        domain = stimulus.context.get("domain", "")
        if domain:
            return domain

        # Check if knowledge refs have a dominant domain
        if stimulus.knowledge_refs and self.kg is not None:
            domain_counts: Dict[str, int] = defaultdict(int)
            for nid in stimulus.knowledge_refs[:20]:
                node = self.kg.nodes.get(nid)
                if node and hasattr(node, "domain") and node.domain:
                    domain_counts[node.domain] += 1
            if domain_counts:
                return max(domain_counts, key=domain_counts.get)  # type: ignore[arg-type]

        # Fall back to searching the KG for the stimulus content
        if self.kg is not None and stimulus.content:
            try:
                results = self.kg.search(stimulus.content, limit=5)
                domain_counts = defaultdict(int)
                for nid in results:
                    node = self.kg.nodes.get(nid)
                    if node and hasattr(node, "domain") and node.domain:
                        domain_counts[node.domain] += 1
                if domain_counts:
                    return max(domain_counts, key=domain_counts.get)  # type: ignore[arg-type]
            except Exception as e:
                logger.debug("Netzach KG search failed: %s", e)

        return "general"

    def get_stats(self) -> Dict[str, Any]:
        """Extended stats including strategy tracking."""
        base = super().get_stats()
        total_records = sum(
            len(outcomes)
            for domain_strats in self._strategy_records.values()
            for outcomes in domain_strats.values()
        )
        base.update({
            "domains_tracked": len(self._strategy_records),
            "total_outcomes_recorded": total_records,
            "global_strategies_tracked": len(self._global_records),
        })
        return base
