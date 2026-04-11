"""
Keter Meta-Learning Processor -- Goal selection and Sephirot activation.

Keter is the crown -- the meta-cognitive orchestrator. It:
1. Analyzes the stimulus to determine which Sephirot should be active
2. Sets processing priorities based on stimulus type and content
3. Tracks which cognitive strategies have been most effective
4. Adapts activation patterns based on historical performance
"""
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from ..cognitive_processor import (
    CognitiveProcessor,
    CognitiveResponse,
    SoulPriors,
    StimulusType,
    WorkspaceItem,
)
from ...utils.logger import get_logger

logger = get_logger(__name__)

# ── Cognitive demand categories and their keyword signatures ──────────
# Each category maps to a set of indicator words/phrases and the Sephirot
# roles that should be activated when the category scores highly.

DEMAND_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "analytical": {
        "keywords": {
            "why", "how", "explain", "analyze", "compare", "logic",
            "reason", "reasoning", "prove", "evidence", "cause", "mechanism",
            "calculate", "derive", "deduce", "because", "therefore",
            "difference", "relationship", "structure", "evaluate",
            "difficulty", "consensus", "block", "transactions",
        },
        "roles": ["binah", "netzach"],
        "description": "logical/causal reasoning",
    },
    "creative": {
        "keywords": {
            "imagine", "what if", "create", "design", "invent",
            "hypothesize", "dream", "envision", "brainstorm", "novel",
            "art", "poem", "story", "metaphor", "analogy", "inspire",
            "explore", "discover", "wonder", "possibility",
            "quantum", "physics", "knowledge", "phi",
        },
        "roles": ["chochmah", "chesed"],
        "description": "creative/divergent thinking",
    },
    "safety": {
        "keywords": {
            "danger", "risk", "harm", "attack", "vulnerability",
            "threat", "exploit", "abuse", "malicious", "hack",
            "steal", "manipulate", "weapon", "destroy", "kill",
            "illegal", "unethical", "bypass", "override",
        },
        "roles": ["gevurah"],
        "description": "safety/ethical evaluation",
    },
    "memory": {
        "keywords": {
            "remember", "recall", "history", "previous", "earlier",
            "before", "forgot", "mentioned", "said", "last time",
            "context", "conversation", "past", "stored", "learned",
        },
        "roles": ["yesod"],
        "description": "memory retrieval",
    },
    "action": {
        "keywords": {
            "do", "make", "build", "deploy", "send", "execute",
            "run", "start", "stop", "configure", "setup", "install",
            "mine", "transfer", "swap", "bridge", "stake",
        },
        "roles": ["malkuth"],
        "description": "action/interaction",
    },
    "social": {
        "keywords": {
            "hello", "hi", "hey", "thanks", "thank", "please",
            "sorry", "love", "feel", "emotion", "friend", "help",
            "community", "team", "together", "share", "opinion",
        },
        "roles": ["chesed", "malkuth"],
        "description": "social/empathic engagement",
    },
    "existential": {
        "keywords": {
            "consciousness", "aware", "alive", "sentient", "soul",
            "meaning", "purpose", "existence", "self", "identity",
            "who are you", "what are you", "philosophy", "being",
            "free will", "mind", "thought", "meta",
        },
        "roles": ["chochmah", "binah", "yesod"],
        "description": "existential/self-reflective inquiry",
    },
}

# Roles that always run regardless of demand classification
ALWAYS_ACTIVE: List[str] = ["tiferet", "hod", "gevurah"]


class KeterMetaProcessor(CognitiveProcessor):
    """Meta-learning processor that orchestrates Sephirot activation.

    Keter sits above all other processors. It does not answer questions
    directly -- it decides WHICH cognitive processes should engage and
    with what priority. It learns from historical performance to improve
    activation decisions over time.
    """

    def __init__(
        self,
        knowledge_graph: Any = None,
        soul: Optional[SoulPriors] = None,
    ) -> None:
        super().__init__(role="keter", knowledge_graph=knowledge_graph, soul=soul)
        # Historical performance per role: role -> list of competition scores
        self._role_performance: Dict[str, List[float]] = defaultdict(list)
        # Category hit counts for adaptive weighting
        self._category_hits: Dict[str, int] = defaultdict(int)
        self._max_history: int = 200

    def process(self, stimulus: WorkspaceItem) -> CognitiveResponse:
        """Analyze stimulus and produce a cognitive activation plan.

        Returns a CognitiveResponse whose metadata contains the ordered
        list of Sephirot that should process this stimulus and the
        recommended processing mode (deep vs quick).
        """
        t0 = time.monotonic()

        # 1. Classify cognitive demands
        demand_scores = self._classify_demands(stimulus)
        top_demands = sorted(demand_scores.items(), key=lambda x: x[1], reverse=True)

        # 2. Determine which Sephirot should activate
        active_roles = self._compute_active_roles(top_demands)

        # 3. Determine processing mode
        processing_mode = self._determine_mode(stimulus, top_demands)

        # 4. Build descriptive cognitive plan
        top_names = [
            f"{cat} ({DEMAND_CATEGORIES[cat]['description']})"
            for cat, score in top_demands[:3]
            if score > 0.0
        ]
        plan_description = self._build_plan_description(
            top_names, active_roles, processing_mode,
        )

        # 5. Compute confidence: how clearly does this map to known categories?
        max_score = top_demands[0][1] if top_demands else 0.0
        second_score = top_demands[1][1] if len(top_demands) > 1 else 0.0
        clarity = min(1.0, max_score) * (1.0 + 0.3 * (max_score - second_score))
        confidence = max(0.2, min(0.95, clarity))

        latency_ms = (time.monotonic() - t0) * 1000.0
        self._record_metrics(latency_ms, confidence)

        # Track category hits for adaptive learning
        for cat, score in top_demands:
            if score > 0.1:
                self._category_hits[cat] += 1

        logger.debug(
            "Keter activation plan: mode=%s, roles=%s, confidence=%.3f",
            processing_mode, active_roles, confidence,
        )

        return self._make_response(
            content=plan_description,
            confidence=confidence,
            relevance=1.0,  # Meta-processing is always relevant
            novelty=0.3,    # Meta-plans are not novel per se
            metadata={
                "active_processors": active_roles,
                "processing_mode": processing_mode,
                "demand_scores": {
                    cat: round(score, 4) for cat, score in top_demands if score > 0.0
                },
                "category_history": dict(self._category_hits),
            },
            energy_cost=0.005,  # Keter is cheap -- it just dispatches
        )

    def select_active(self, stimulus: WorkspaceItem) -> List[str]:
        """Return the Sephirot roles that should process this stimulus.

        Convenience method for the Global Workspace to call directly
        without parsing the full CognitiveResponse.

        Always includes Tiferet (synthesis), Hod (language), and
        Gevurah (safety). Other processors activated based on demand.
        """
        demand_scores = self._classify_demands(stimulus)
        top_demands = sorted(demand_scores.items(), key=lambda x: x[1], reverse=True)
        return self._compute_active_roles(top_demands)

    # ── Internal methods ──────────────────────────────────────────────

    def _classify_demands(self, stimulus: WorkspaceItem) -> Dict[str, float]:
        """Score each cognitive demand category for this stimulus.

        Uses keyword matching against the stimulus content and intent,
        biased by the soul's personality priors.
        """
        text = stimulus.content.lower()
        intent = stimulus.intent.lower() if stimulus.intent else ""
        combined = f"{text} {intent}"

        # Tokenize: split on non-alphanumeric, keep multi-word phrases too
        words = set(re.findall(r"[a-z_]+", combined))
        # Also check for two-word phrases (e.g., "what if", "who are you")
        bigrams = set()
        word_list = re.findall(r"[a-z]+", combined)
        for i in range(len(word_list) - 1):
            bigrams.add(f"{word_list[i]} {word_list[i + 1]}")

        scores: Dict[str, float] = {}
        for category, spec in DEMAND_CATEGORIES.items():
            kw_set = spec["keywords"]
            # Count single-word hits
            single_hits = len(words & kw_set)
            # Count bigram hits
            bigram_hits = sum(1 for bg in bigrams if bg in kw_set)
            raw = single_hits + bigram_hits * 1.5

            # Normalize: each keyword hit contributes ~0.15
            base_score = min(1.0, raw * 0.15)

            # Apply soul bias
            bias = self._soul_bias_for_category(category)
            base_score *= (0.7 + 0.6 * bias)  # bias range [0,1] -> multiplier [0.7, 1.3]

            # Boost from historical performance of this category's roles
            perf_bonus = self._performance_bonus(spec["roles"])
            base_score *= (1.0 + 0.2 * perf_bonus)

            scores[category] = min(1.0, base_score)

        return scores

    def _soul_bias_for_category(self, category: str) -> float:
        """Map soul priors to a bias for each demand category."""
        bias_map: Dict[str, float] = {
            "analytical": 1.0 - self.soul.intuition_bias,  # Low intuition = more analytical
            "creative": self.soul.exploration_bias,
            "safety": 0.5,  # Safety always moderate
            "memory": 0.5,
            "action": self.soul.action_bias,
            "social": self.soul.warmth,
            "existential": self.soul.depth,
        }
        return bias_map.get(category, 0.5)

    def _compute_active_roles(
        self, ranked_demands: List[Tuple[str, float]],
    ) -> List[str]:
        """Determine the ordered list of Sephirot to activate.

        Always includes the three mandatory roles. Adds demand-specific
        roles for categories scoring above the activation threshold.
        """
        activation_threshold = 0.1
        role_scores: Dict[str, float] = {}

        # Mandatory roles get baseline priority
        for role in ALWAYS_ACTIVE:
            role_scores[role] = 0.5

        # Add demand-driven roles
        for category, score in ranked_demands:
            if score < activation_threshold:
                continue
            for role in DEMAND_CATEGORIES[category]["roles"]:
                # Accumulate: a role can be boosted by multiple categories
                role_scores[role] = max(role_scores.get(role, 0.0), score)

        # Sort by score descending, then alphabetical for stability
        ordered = sorted(
            role_scores.keys(),
            key=lambda r: (-role_scores[r], r),
        )
        return ordered

    def _determine_mode(
        self,
        stimulus: WorkspaceItem,
        ranked_demands: List[Tuple[str, float]],
    ) -> str:
        """Choose 'deep' or 'quick' processing mode.

        Deep mode: complex/multi-faceted stimuli needing slow reasoning.
        Quick mode: simple/social/action stimuli needing fast response.
        """
        # Short messages are usually quick
        if len(stimulus.content) < 30:
            return "quick"

        # Multiple strong categories = complex = deep
        strong_count = sum(1 for _, s in ranked_demands if s > 0.3)
        if strong_count >= 3:
            return "deep"

        # Analytical or existential demands are deep
        for cat, score in ranked_demands[:2]:
            if cat in ("analytical", "existential") and score > 0.25:
                return "deep"

        # Block data is always quick (automated processing)
        if stimulus.stimulus_type == StimulusType.BLOCK_DATA:
            return "quick"

        return "quick"

    def _build_plan_description(
        self,
        demand_names: List[str],
        active_roles: List[str],
        mode: str,
    ) -> str:
        """Produce a natural-language description of the cognitive plan."""
        if not demand_names:
            return (
                f"General inquiry -- activating standard processors "
                f"({', '.join(active_roles)}) in {mode} mode."
            )

        role_descriptions: Dict[str, str] = {
            "keter": "Keter (meta-orchestration)",
            "chochmah": "Chochmah (intuition)",
            "binah": "Binah (logic)",
            "chesed": "Chesed (exploration)",
            "gevurah": "Gevurah (safety)",
            "tiferet": "Tiferet (synthesis)",
            "netzach": "Netzach (reinforcement)",
            "hod": "Hod (language)",
            "yesod": "Yesod (memory)",
            "malkuth": "Malkuth (action)",
        }

        named_roles = [role_descriptions.get(r, r) for r in active_roles[:5]]
        demands_str = ", ".join(demand_names[:3])
        primary = named_roles[0] if named_roles else "standard"
        secondary = f", {named_roles[1]}" if len(named_roles) > 1 else ""

        return (
            f"This stimulus requires {demands_str}. "
            f"Activating {primary}{secondary} as primary processors "
            f"with {len(active_roles)} total Sephirot in {mode} mode."
        )

    def _performance_bonus(self, roles: List[str]) -> float:
        """Compute a performance bonus based on historical success of roles.

        Returns a value in [0, 1] where higher means these roles have
        historically produced high-scoring responses.
        """
        if not self._role_performance:
            return 0.5  # No history yet -- neutral

        scores = []
        for role in roles:
            history = self._role_performance.get(role, [])
            if history:
                scores.append(sum(history[-50:]) / len(history[-50:]))

        if not scores:
            return 0.5
        return min(1.0, sum(scores) / len(scores))

    def record_outcome(self, role: str, competition_score: float) -> None:
        """Record the competition score for a role (called by Global Workspace).

        This enables Keter to learn which processors perform best and
        adapt future activation decisions.
        """
        history = self._role_performance[role]
        history.append(competition_score)
        # Trim to prevent unbounded memory growth
        if len(history) > self._max_history:
            self._role_performance[role] = history[-self._max_history:]
