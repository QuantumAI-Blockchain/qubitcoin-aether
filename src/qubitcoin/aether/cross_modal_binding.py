"""
Cross-Modal Binding — Item #81
Integrate information across modalities: temporal, structural, semantic.
Binding via learned projection to shared space + element-wise product.
"""
from typing import Dict, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


class CrossModalBinding:
    """Bind temporal, structural, and semantic modalities into a unified
    representation in a shared embedding space."""

    MODALITIES = ("temporal", "structural", "semantic")

    def __init__(
        self,
        temporal_dim: int = 16,
        structural_dim: int = 16,
        semantic_dim: int = 16,
        shared_dim: int = 16,
        learning_rate: float = 0.01,
    ) -> None:
        self._dims = {
            "temporal": temporal_dim,
            "structural": structural_dim,
            "semantic": semantic_dim,
        }
        self._shared_dim = shared_dim
        self._lr = learning_rate

        rng = np.random.default_rng(42)

        # Projection matrices: modality -> shared space
        self._projections: Dict[str, np.ndarray] = {
            mod: rng.normal(0, 0.1, (shared_dim, dim)).astype(np.float64)
            for mod, dim in self._dims.items()
        }
        # Inverse projections: shared space -> modality (for unbinding)
        self._inv_projections: Dict[str, np.ndarray] = {
            mod: rng.normal(0, 0.1, (dim, shared_dim)).astype(np.float64)
            for mod, dim in self._dims.items()
        }

        self._bind_count: int = 0
        self._unbind_count: int = 0

    # ------------------------------------------------------------------
    def _project(self, data: np.ndarray, modality: str) -> np.ndarray:
        """Project modality data to shared space."""
        d = np.asarray(data, dtype=np.float64).ravel()
        expected = self._dims[modality]
        if len(d) < expected:
            d = np.pad(d, (0, expected - len(d)))
        else:
            d = d[:expected]
        return self._projections[modality] @ d

    # ------------------------------------------------------------------
    def bind(
        self,
        temporal: np.ndarray,
        structural: np.ndarray,
        semantic: np.ndarray,
    ) -> np.ndarray:
        """Bind three modalities into a single representation.

        Mechanism: project each to shared space, then element-wise product.
        """
        self._bind_count += 1
        t_proj = self._project(temporal, "temporal")
        s_proj = self._project(structural, "structural")
        m_proj = self._project(semantic, "semantic")

        # Element-wise product binding
        bound = t_proj * s_proj * m_proj

        # Normalise to unit length to keep stable
        norm = np.linalg.norm(bound)
        if norm > 1e-12:
            bound = bound / norm

        return bound

    # ------------------------------------------------------------------
    def unbind(self, bound: np.ndarray, modality: str) -> np.ndarray:
        """Project bound representation back to a specific modality space."""
        if modality not in self._inv_projections:
            raise ValueError(f"Unknown modality: {modality}")
        self._unbind_count += 1
        b = np.asarray(bound, dtype=np.float64).ravel()
        if len(b) < self._shared_dim:
            b = np.pad(b, (0, self._shared_dim - len(b)))
        else:
            b = b[:self._shared_dim]
        return self._inv_projections[modality] @ b

    # ------------------------------------------------------------------
    def binding_strength(self, bound: np.ndarray) -> float:
        """Measure how coherently the representation is bound (0-1).

        A strongly bound vector has high magnitude and low entropy.
        """
        b = np.asarray(bound, dtype=np.float64).ravel()
        norm = float(np.linalg.norm(b))
        if norm < 1e-12:
            return 0.0

        # Entropy of normalised absolute values
        abs_b = np.abs(b)
        s = abs_b.sum()
        if s < 1e-12:
            return 0.0
        probs = abs_b / s
        probs = probs[probs > 1e-12]
        entropy = float(-np.sum(probs * np.log2(probs)))
        max_entropy = np.log2(len(b)) if len(b) > 1 else 1.0

        # Strength = 1 - normalised entropy (low entropy = coherent binding)
        strength = 1.0 - (entropy / max_entropy) if max_entropy > 0 else 0.0
        return float(np.clip(strength, 0.0, 1.0))

    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        return {
            "shared_dim": self._shared_dim,
            "modality_dims": dict(self._dims),
            "bind_count": self._bind_count,
            "unbind_count": self._unbind_count,
        }
