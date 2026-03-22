"""
#99: Meta-Learning (Optimize Learning Rate / Architecture Per Domain)

Learn how to learn: track hyperparameter configurations per domain,
use a Bayesian optimization lite approach to suggest the best
configuration for each domain.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI = 1.618033988749895

# Default hyperparameter search space
DEFAULT_CONFIGS = [
    {'learning_rate': 0.001, 'batch_size': 8, 'architecture': 'small'},
    {'learning_rate': 0.005, 'batch_size': 16, 'architecture': 'small'},
    {'learning_rate': 0.01, 'batch_size': 16, 'architecture': 'medium'},
    {'learning_rate': 0.01, 'batch_size': 32, 'architecture': 'medium'},
    {'learning_rate': 0.05, 'batch_size': 32, 'architecture': 'large'},
    {'learning_rate': 0.05, 'batch_size': 64, 'architecture': 'large'},
    {'learning_rate': 0.1, 'batch_size': 64, 'architecture': 'large'},
]


@dataclass
class ConfigTrial:
    """Record of a hyperparameter configuration trial."""
    config: dict
    performance: float
    domain: str
    timestamp: float = field(default_factory=time.time)


class MetaLearner:
    """Meta-learning engine: learn how to learn.

    Tracks hyperparameter configurations per domain and uses a simple
    surrogate model (Gaussian Process lite) to suggest the best config.
    """

    def __init__(self, max_trials_per_domain: int = 100) -> None:
        self._max_trials = max_trials_per_domain
        # Trials per domain
        self._trials: Dict[str, List[ConfigTrial]] = {}
        # Best known config per domain
        self._best_configs: Dict[str, dict] = {}
        self._best_performance: Dict[str, float] = {}
        # Global performance trends
        self._global_trials: List[ConfigTrial] = []
        self._max_global = 1000
        # Stats
        self._total_updates = 0
        self._total_suggestions = 0

    # ------------------------------------------------------------------
    # Record outcomes
    # ------------------------------------------------------------------

    def update(
        self, domain: str, config: dict, performance: float
    ) -> None:
        """Record outcome of a hyperparameter configuration trial.

        Args:
            domain: Domain where the config was tested.
            config: Hyperparameter dict.
            performance: Performance metric (higher is better).
        """
        self._total_updates += 1
        trial = ConfigTrial(
            config=config, performance=performance, domain=domain
        )

        if domain not in self._trials:
            self._trials[domain] = []
        self._trials[domain].append(trial)
        if len(self._trials[domain]) > self._max_trials:
            self._trials[domain] = self._trials[domain][-self._max_trials:]

        self._global_trials.append(trial)
        if len(self._global_trials) > self._max_global:
            self._global_trials = self._global_trials[-self._max_global:]

        # Update best
        if (domain not in self._best_performance
                or performance > self._best_performance[domain]):
            self._best_performance[domain] = performance
            self._best_configs[domain] = dict(config)

    # ------------------------------------------------------------------
    # Suggest configuration
    # ------------------------------------------------------------------

    def suggest_config(self, domain: str) -> dict:
        """Suggest best hyperparameter config for a domain.

        Uses Thompson sampling inspired approach: exploit known good
        configs most of the time, explore new configs occasionally.

        Args:
            domain: Domain to suggest config for.

        Returns:
            Hyperparameter configuration dict.
        """
        self._total_suggestions += 1
        trials = self._trials.get(domain, [])

        # If no trials, use default based on global best or random
        if not trials:
            return self._suggest_from_global(domain)

        # Thompson sampling: sample from performance distribution
        # For each tried config, compute mean + noise
        config_scores: Dict[str, Tuple[dict, float]] = {}
        for trial in trials:
            key = str(sorted(trial.config.items()))
            if key not in config_scores:
                config_scores[key] = (trial.config, trial.performance)
            else:
                old_perf = config_scores[key][1]
                # Running average
                config_scores[key] = (
                    trial.config,
                    (old_perf + trial.performance) / 2,
                )

        # Add exploration noise
        best_key = None
        best_score = -np.inf
        for key, (config, perf) in config_scores.items():
            noisy_score = perf + np.random.randn() * 0.1
            if noisy_score > best_score:
                best_score = noisy_score
                best_key = key

        if best_key and best_key in config_scores:
            chosen = config_scores[best_key][0]
        else:
            chosen = self._best_configs.get(domain, DEFAULT_CONFIGS[0])

        # Occasionally explore a random config (10% exploration)
        if np.random.random() < 0.1:
            chosen = DEFAULT_CONFIGS[np.random.randint(len(DEFAULT_CONFIGS))]

        return dict(chosen)

    def _suggest_from_global(self, domain: str) -> dict:
        """Suggest config based on global performance data."""
        if not self._global_trials:
            return dict(DEFAULT_CONFIGS[0])

        # Find best global config
        best_trial = max(self._global_trials, key=lambda t: t.performance)
        return dict(best_trial.config)

    # ------------------------------------------------------------------
    # Hyperparameter optimization
    # ------------------------------------------------------------------

    def optimize_hyperparams(
        self,
        domain: str,
        performance_history: List[float],
    ) -> dict:
        """Analyze performance history and suggest optimized hyperparams.

        Args:
            domain: Domain to optimize for.
            performance_history: Recent performance values.

        Returns:
            Optimized hyperparameter configuration.
        """
        if not performance_history:
            return self.suggest_config(domain)

        # Analyze trend
        arr = np.array(performance_history[-50:])
        trend = 0.0
        if len(arr) >= 3:
            # Simple linear regression slope
            x = np.arange(len(arr), dtype=np.float64)
            x_mean = np.mean(x)
            y_mean = np.mean(arr)
            denom = np.sum((x - x_mean) ** 2)
            if denom > 1e-12:
                trend = float(np.sum((x - x_mean) * (arr - y_mean)) / denom)

        current_best = self.suggest_config(domain)

        # If performance is declining, try different config
        if trend < -0.01:
            # Reduce learning rate
            lr = current_best.get('learning_rate', 0.01)
            current_best['learning_rate'] = lr * 0.5
        elif trend > 0.01:
            # Performance improving, slightly increase LR
            lr = current_best.get('learning_rate', 0.01)
            current_best['learning_rate'] = min(lr * 1.2, 0.1)

        # Adjust batch size based on variance
        variance = float(np.var(arr)) if len(arr) > 1 else 0.0
        if variance > 0.1:
            # High variance: increase batch size for stability
            bs = current_best.get('batch_size', 16)
            current_best['batch_size'] = min(bs * 2, 128)

        return current_best

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return meta-learner statistics."""
        domains_with_trials = len(self._trials)
        total_trials = sum(len(t) for t in self._trials.values())
        return {
            'total_updates': self._total_updates,
            'total_suggestions': self._total_suggestions,
            'domains_tracked': domains_with_trials,
            'total_trials': total_trials,
            'best_performance': dict(self._best_performance),
            'best_configs': {
                d: str(c) for d, c in self._best_configs.items()
            },
        }
