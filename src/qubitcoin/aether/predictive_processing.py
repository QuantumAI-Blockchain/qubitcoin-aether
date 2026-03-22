"""
Predictive Processing — Item #78
Hierarchical prediction error minimization following Clark/Friston.
Three-level hierarchy: sensory -> feature -> concept.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PredictionResult:
    """Result of hierarchical predictive processing."""
    predictions: Dict[str, np.ndarray]  # per-level predictions
    errors: Dict[str, np.ndarray]       # per-level prediction errors
    surprisal: float                     # total unexpectedness


class PredictiveProcessing:
    """Hierarchical prediction error minimization.

    Three-level hierarchy:
        Level 0 (sensory)  — raw input
        Level 1 (feature)  — extracted patterns
        Level 2 (concept)  — abstract representations

    Each level generates top-down predictions; bottom-up errors
    drive learning and update the generative model.
    """

    LEVELS = ("sensory", "feature", "concept")

    def __init__(
        self,
        input_dim: int = 16,
        feature_dim: int = 8,
        concept_dim: int = 4,
        learning_rate: float = 0.01,
        precision_weight: float = 1.0,
    ) -> None:
        self._dims = {
            "sensory": input_dim,
            "feature": feature_dim,
            "concept": concept_dim,
        }
        self._lr = learning_rate
        self._precision_weight = precision_weight

        # Generative model weights (top-down)
        rng = np.random.default_rng(42)
        self._weights: Dict[str, np.ndarray] = {
            # concept -> feature
            "concept_to_feature": rng.normal(0, 0.1, (feature_dim, concept_dim)),
            # feature -> sensory
            "feature_to_sensory": rng.normal(0, 0.1, (input_dim, feature_dim)),
        }

        # Internal states per level
        self._states: Dict[str, np.ndarray] = {
            "sensory": np.zeros(input_dim),
            "feature": np.zeros(feature_dim),
            "concept": np.zeros(concept_dim),
        }

        # Precision (inverse variance) per level — higher = trust predictions more
        self._precision: Dict[str, float] = {
            "sensory": 1.0,
            "feature": 1.0,
            "concept": 1.0,
        }

        self._total_processes: int = 0
        self._total_surprisal: float = 0.0
        self._min_surprisal: float = float("inf")
        self._max_surprisal: float = 0.0

    # ------------------------------------------------------------------
    def process(self, input_data: np.ndarray) -> PredictionResult:
        """Run one cycle of hierarchical prediction error minimization.

        1. Bottom-up pass: compare input with top-down prediction
        2. Update states to reduce prediction error
        3. Update generative model weights
        """
        self._total_processes += 1

        # Ensure correct shape
        x = np.asarray(input_data, dtype=np.float64).ravel()
        if len(x) < self._dims["sensory"]:
            x = np.pad(x, (0, self._dims["sensory"] - len(x)))
        else:
            x = x[: self._dims["sensory"]]

        # --- Top-down predictions ---
        pred_feature = self._weights["concept_to_feature"] @ self._states["concept"]
        pred_sensory = self._weights["feature_to_sensory"] @ self._states["feature"]

        predictions: Dict[str, np.ndarray] = {
            "sensory": pred_sensory.copy(),
            "feature": pred_feature.copy(),
            "concept": self._states["concept"].copy(),
        }

        # --- Bottom-up prediction errors ---
        error_sensory = x - pred_sensory
        # Feature-level: residual from concept prediction
        # Project sensory error up to feature space
        pseudo_inv = np.linalg.pinv(self._weights["feature_to_sensory"])
        feature_input = pseudo_inv @ x
        error_feature = feature_input - pred_feature
        # Concept-level error (self-prediction drift)
        error_concept = np.zeros(self._dims["concept"])

        errors: Dict[str, np.ndarray] = {
            "sensory": error_sensory,
            "feature": error_feature,
            "concept": error_concept,
        }

        # --- Surprisal (free energy proxy) ---
        surprisal = float(
            self._precision["sensory"] * np.sum(error_sensory ** 2)
            + self._precision["feature"] * np.sum(error_feature ** 2)
        )
        self._total_surprisal += surprisal
        self._min_surprisal = min(self._min_surprisal, surprisal)
        self._max_surprisal = max(self._max_surprisal, surprisal)

        # --- Update internal states (minimise prediction error) ---
        self._states["sensory"] = x
        self._states["feature"] += self._lr * error_feature
        # Concept update: shift toward reducing feature error
        concept_grad = self._weights["concept_to_feature"].T @ error_feature
        self._states["concept"] += self._lr * concept_grad

        # --- Update generative model weights ---
        # feature_to_sensory: reduce sensory error
        self._weights["feature_to_sensory"] += (
            self._lr
            * np.outer(error_sensory, self._states["feature"])
        )
        # concept_to_feature: reduce feature error
        self._weights["concept_to_feature"] += (
            self._lr
            * np.outer(error_feature, self._states["concept"])
        )

        return PredictionResult(
            predictions=predictions,
            errors=errors,
            surprisal=surprisal,
        )

    # ------------------------------------------------------------------
    def get_surprisal(self) -> float:
        """Total unexpectedness of last input."""
        if self._total_processes == 0:
            return 0.0
        return self._total_surprisal / self._total_processes

    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        return {
            "total_processes": self._total_processes,
            "avg_surprisal": self.get_surprisal(),
            "min_surprisal": self._min_surprisal if self._min_surprisal != float("inf") else 0.0,
            "max_surprisal": self._max_surprisal,
            "levels": list(self.LEVELS),
            "dims": dict(self._dims),
            "precision": dict(self._precision),
        }
