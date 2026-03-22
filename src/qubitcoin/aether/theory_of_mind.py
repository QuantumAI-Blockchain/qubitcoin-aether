"""
#67: Theory of Mind — Social Modeling

Models other agents' beliefs, goals, and intentions.  Tracks interaction
history, predicts actions, and estimates knowledge levels.

Numpy-only implementation (no PyTorch).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AgentModel:
    """Representation of another agent's mental state."""
    agent_id: str
    beliefs: Dict[str, float] = field(default_factory=dict)
    goals: List[str] = field(default_factory=list)
    trust_level: float = 0.5
    interaction_history: List[Dict[str, Any]] = field(default_factory=list)
    expertise: Dict[str, float] = field(default_factory=dict)  # domain -> level [0,1]
    last_updated: float = 0.0
    total_interactions: int = 0

    def summary(self) -> dict:
        return {
            'agent_id': self.agent_id,
            'trust_level': round(self.trust_level, 4),
            'num_beliefs': len(self.beliefs),
            'num_goals': len(self.goals),
            'total_interactions': self.total_interactions,
            'domains': list(self.expertise.keys()),
        }


# ---------------------------------------------------------------------------
# Intent vocabulary (simple categorical)
# ---------------------------------------------------------------------------
_INTENTS = [
    'query', 'explore', 'teach', 'trade', 'challenge',
    'collaborate', 'observe', 'unknown',
]

_ACTIONS = [
    'ask_question', 'provide_answer', 'request_data', 'submit_tx',
    'create_contract', 'mine_block', 'stake', 'idle', 'unknown',
]


class TheoryOfMind:
    """Model other agents' beliefs, intentions, and predict their actions."""

    def __init__(self, max_agents: int = 1000, history_cap: int = 200) -> None:
        self._models: Dict[str, AgentModel] = {}
        self._max_agents = max_agents
        self._history_cap = history_cap

        # Simple transition matrix: action_i -> action_j counts
        n_actions = len(_ACTIONS)
        self._transition_counts: np.ndarray = np.ones((n_actions, n_actions), dtype=np.float64)

        # Stats
        self._inferences: int = 0
        self._predictions: int = 0
        self._updates: int = 0

        logger.info("TheoryOfMind initialized (max_agents=%d)", max_agents)

    # ------------------------------------------------------------------
    # Agent model management
    # ------------------------------------------------------------------

    def get_or_create_model(self, agent_id: str) -> AgentModel:
        if agent_id not in self._models:
            if len(self._models) >= self._max_agents:
                # Evict least recently updated
                oldest = min(self._models.values(), key=lambda m: m.last_updated)
                del self._models[oldest.agent_id]
            self._models[agent_id] = AgentModel(agent_id=agent_id)
        return self._models[agent_id]

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def infer_intent(self, agent_id: str, recent_actions: List[str]) -> str:
        """Predict what the agent wants based on recent actions.

        Uses action frequency weighted by recency to pick the most
        likely intent category.
        """
        model = self.get_or_create_model(agent_id)
        self._inferences += 1

        if not recent_actions:
            return 'unknown'

        # Map actions to intent categories via simple heuristic
        intent_scores: Dict[str, float] = {intent: 0.0 for intent in _INTENTS}
        for i, action in enumerate(recent_actions):
            weight = 1.0 + i * 0.5  # More recent = higher weight
            action_lower = action.lower()
            if 'question' in action_lower or 'ask' in action_lower or 'query' in action_lower:
                intent_scores['query'] += weight
            elif 'answer' in action_lower or 'teach' in action_lower:
                intent_scores['teach'] += weight
            elif 'explore' in action_lower or 'search' in action_lower:
                intent_scores['explore'] += weight
            elif 'trade' in action_lower or 'swap' in action_lower or 'tx' in action_lower:
                intent_scores['trade'] += weight
            elif 'challenge' in action_lower or 'debate' in action_lower:
                intent_scores['challenge'] += weight
            elif 'collaborate' in action_lower or 'help' in action_lower:
                intent_scores['collaborate'] += weight
            else:
                intent_scores['observe'] += weight

        best_intent = max(intent_scores, key=intent_scores.get)  # type: ignore[arg-type]
        # Update model beliefs
        model.beliefs['likely_intent'] = _INTENTS.index(best_intent) / len(_INTENTS)
        model.last_updated = time.time()

        return best_intent

    def predict_action(self, agent_id: str, context: dict) -> str:
        """Predict the agent's next action based on transition model.

        Uses the Markov transition matrix built from observed actions.
        """
        model = self.get_or_create_model(agent_id)
        self._predictions += 1

        # Find the last known action index
        last_action_str = 'unknown'
        if model.interaction_history:
            last_action_str = model.interaction_history[-1].get('action', 'unknown')

        last_idx = _ACTIONS.index(last_action_str) if last_action_str in _ACTIONS else len(_ACTIONS) - 1

        # Sample from transition distribution
        row = self._transition_counts[last_idx]
        probs = row / row.sum()
        next_idx = int(np.argmax(probs))  # Greedy prediction

        return _ACTIONS[next_idx]

    def update_model(self, agent_id: str, observed_action: str, outcome: dict) -> None:
        """Update beliefs about an agent after observing their action."""
        model = self.get_or_create_model(agent_id)
        self._updates += 1

        # Record interaction
        interaction = {
            'action': observed_action,
            'outcome': outcome,
            'timestamp': time.time(),
        }
        model.interaction_history.append(interaction)
        if len(model.interaction_history) > self._history_cap:
            model.interaction_history = model.interaction_history[-self._history_cap:]
        model.total_interactions += 1
        model.last_updated = time.time()

        # Update transition matrix
        if len(model.interaction_history) >= 2:
            prev_action = model.interaction_history[-2].get('action', 'unknown')
            prev_idx = _ACTIONS.index(prev_action) if prev_action in _ACTIONS else len(_ACTIONS) - 1
            curr_idx = _ACTIONS.index(observed_action) if observed_action in _ACTIONS else len(_ACTIONS) - 1
            self._transition_counts[prev_idx, curr_idx] += 1.0

        # Update trust based on outcome
        success = outcome.get('success', None)
        if success is True:
            model.trust_level = min(1.0, model.trust_level + 0.02)
        elif success is False:
            model.trust_level = max(0.0, model.trust_level - 0.03)

        # Update expertise from outcome domain
        domain = outcome.get('domain', None)
        if domain:
            current = model.expertise.get(domain, 0.3)
            if success:
                model.expertise[domain] = min(1.0, current + 0.05)
            else:
                model.expertise[domain] = max(0.0, current - 0.02)

    def estimate_knowledge_level(self, agent_id: str, domain: str) -> float:
        """Estimate how knowledgeable an agent is in a given domain.

        Returns a value in [0, 1].
        """
        model = self.get_or_create_model(agent_id)
        if domain in model.expertise:
            return model.expertise[domain]

        # Infer from interaction history
        domain_interactions = [
            h for h in model.interaction_history
            if h.get('outcome', {}).get('domain') == domain
        ]
        if not domain_interactions:
            return 0.3  # Prior — modest default

        successes = sum(
            1 for h in domain_interactions
            if h.get('outcome', {}).get('success', False)
        )
        level = successes / max(len(domain_interactions), 1)
        model.expertise[domain] = level
        return level

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        return {
            'agents_tracked': len(self._models),
            'total_inferences': self._inferences,
            'total_predictions': self._predictions,
            'total_updates': self._updates,
            'avg_trust': round(
                float(np.mean([m.trust_level for m in self._models.values()]))
                if self._models else 0.5,
                4,
            ),
        }
