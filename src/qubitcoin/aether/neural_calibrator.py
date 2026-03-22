"""
Neural Calibration — Item #39

Proper neural calibration beyond basic temperature scaling:
- Platt scaling: logistic regression on logits to calibrate probabilities
- Expected Calibration Error (ECE) and Maximum Calibration Error (MCE)
- Reliability diagram data for visualization
- Can calibrate any subsystem's confidence scores
"""
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid."""
    return np.where(x >= 0,
                    1.0 / (1.0 + np.exp(-x)),
                    np.exp(x) / (1.0 + np.exp(x)))


class NeuralCalibrator:
    """Calibrates neural network confidence scores via Platt scaling.

    Learns a logistic regression mapping: calibrated_prob = sigmoid(a * logit + b)
    where a and b are fitted to minimize NLL on a calibration set.
    """

    def __init__(self, lr: float = 0.01, max_iter: int = 200,
                 reg_lambda: float = 0.001) -> None:
        """Initialize calibrator.

        Args:
            lr: Learning rate for Platt scaling optimization.
            max_iter: Max iterations for fitting.
            reg_lambda: L2 regularization strength.
        """
        self._lr = lr
        self._max_iter = max_iter
        self._reg_lambda = reg_lambda

        # Platt scaling parameters: sigmoid(a * logit + b)
        self._a: float = 1.0  # Scale
        self._b: float = 0.0  # Shift
        self._is_fitted: bool = False

        # Stats
        self._fit_count: int = 0
        self._calibrations: int = 0
        self._ece_history: List[float] = []
        self._mce_history: List[float] = []
        self._pre_ece: float = 0.0
        self._post_ece: float = 0.0

    def fit(self, logits: np.ndarray, labels: np.ndarray) -> None:
        """Learn calibration parameters via Platt scaling.

        Fits a logistic regression: P(y=1|logit) = sigmoid(a * logit + b)
        using gradient descent on negative log-likelihood.

        Args:
            logits: Raw model logits/scores, shape (n_samples,).
            labels: Binary ground truth labels, shape (n_samples,).
        """
        logits = np.asarray(logits, dtype=np.float64).flatten()
        labels = np.asarray(labels, dtype=np.float64).flatten()

        if len(logits) < 2:
            logger.warning("Need at least 2 samples for calibration fitting")
            return

        n = len(logits)

        # Initialize Platt parameters
        a = 1.0
        b = 0.0

        # Pre-calibration ECE for comparison
        pre_probs = _sigmoid(logits)
        self._pre_ece = self.compute_ece(pre_probs, labels)

        best_a, best_b = a, b
        best_nll = float('inf')

        for iteration in range(self._max_iter):
            # Forward: p = sigmoid(a * logits + b)
            z = a * logits + b
            p = _sigmoid(z)
            p = np.clip(p, 1e-10, 1 - 1e-10)

            # Negative log-likelihood + L2 reg
            nll = -np.mean(labels * np.log(p) + (1 - labels) * np.log(1 - p))
            nll += self._reg_lambda * (a ** 2 + b ** 2)

            if nll < best_nll:
                best_nll = nll
                best_a, best_b = a, b

            # Gradients
            residual = p - labels  # shape (n,)
            grad_a = np.mean(residual * logits) + 2 * self._reg_lambda * a
            grad_b = np.mean(residual) + 2 * self._reg_lambda * b

            # Update with gradient clipping
            a -= self._lr * np.clip(grad_a, -10, 10)
            b -= self._lr * np.clip(grad_b, -10, 10)

        self._a = best_a
        self._b = best_b
        self._is_fitted = True
        self._fit_count += 1

        # Post-calibration ECE
        post_probs = self.calibrate(logits)
        self._post_ece = self.compute_ece(post_probs, labels)

        logger.info(
            f"Calibrator fitted: a={self._a:.4f}, b={self._b:.4f}, "
            f"ECE {self._pre_ece:.4f} -> {self._post_ece:.4f}"
        )

    def calibrate(self, logits: np.ndarray) -> np.ndarray:
        """Apply learned calibration to raw logits.

        Args:
            logits: Raw scores/logits, shape (n,) or (n, k) for multi-class.

        Returns:
            Calibrated probabilities, same shape as input.
        """
        logits = np.asarray(logits, dtype=np.float64)
        self._calibrations += 1

        if not self._is_fitted:
            # Fallback: plain sigmoid
            return _sigmoid(logits)

        return _sigmoid(self._a * logits + self._b)

    def compute_ece(self, probs: np.ndarray, labels: np.ndarray,
                    n_bins: int = 15) -> float:
        """Compute Expected Calibration Error.

        ECE = sum_b (|B_b| / n) * |acc(B_b) - conf(B_b)|
        where B_b is the set of predictions in bin b.

        Args:
            probs: Predicted probabilities, shape (n,).
            labels: Binary ground truth, shape (n,).
            n_bins: Number of equal-width bins.

        Returns:
            ECE value in [0, 1].
        """
        probs = np.asarray(probs, dtype=np.float64).flatten()
        labels = np.asarray(labels, dtype=np.float64).flatten()
        n = len(probs)
        if n == 0:
            return 0.0

        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        ece = 0.0

        for i in range(n_bins):
            low, high = bin_boundaries[i], bin_boundaries[i + 1]
            mask = (probs > low) & (probs <= high) if i > 0 else (probs >= low) & (probs <= high)
            bin_size = np.sum(mask)
            if bin_size == 0:
                continue
            avg_conf = np.mean(probs[mask])
            avg_acc = np.mean(labels[mask])
            ece += (bin_size / n) * abs(avg_acc - avg_conf)

        ece_val = float(ece)
        self._ece_history.append(ece_val)
        return ece_val

    def compute_mce(self, probs: np.ndarray, labels: np.ndarray,
                    n_bins: int = 15) -> float:
        """Compute Maximum Calibration Error.

        MCE = max_b |acc(B_b) - conf(B_b)|

        Args:
            probs: Predicted probabilities, shape (n,).
            labels: Binary ground truth, shape (n,).
            n_bins: Number of equal-width bins.

        Returns:
            MCE value in [0, 1].
        """
        probs = np.asarray(probs, dtype=np.float64).flatten()
        labels = np.asarray(labels, dtype=np.float64).flatten()
        n = len(probs)
        if n == 0:
            return 0.0

        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        mce = 0.0

        for i in range(n_bins):
            low, high = bin_boundaries[i], bin_boundaries[i + 1]
            mask = (probs > low) & (probs <= high) if i > 0 else (probs >= low) & (probs <= high)
            bin_size = np.sum(mask)
            if bin_size == 0:
                continue
            avg_conf = np.mean(probs[mask])
            avg_acc = np.mean(labels[mask])
            mce = max(mce, abs(avg_acc - avg_conf))

        mce_val = float(mce)
        self._mce_history.append(mce_val)
        return mce_val

    def get_reliability_data(self, probs: np.ndarray, labels: np.ndarray,
                             n_bins: int = 15) -> Dict[str, Any]:
        """Generate reliability diagram data for visualization.

        Args:
            probs: Predicted probabilities, shape (n,).
            labels: Binary ground truth, shape (n,).
            n_bins: Number of bins.

        Returns:
            Dict with keys: bin_centers, bin_accuracies, bin_confidences,
            bin_counts, ece, mce.
        """
        probs = np.asarray(probs, dtype=np.float64).flatten()
        labels = np.asarray(labels, dtype=np.float64).flatten()
        n = len(probs)

        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        bin_centers = []
        bin_accuracies = []
        bin_confidences = []
        bin_counts = []

        for i in range(n_bins):
            low, high = bin_boundaries[i], bin_boundaries[i + 1]
            mask = (probs > low) & (probs <= high) if i > 0 else (probs >= low) & (probs <= high)
            bin_size = int(np.sum(mask))
            bin_counts.append(bin_size)
            bin_centers.append(float((low + high) / 2))

            if bin_size == 0:
                bin_accuracies.append(0.0)
                bin_confidences.append(0.0)
            else:
                bin_accuracies.append(float(np.mean(labels[mask])))
                bin_confidences.append(float(np.mean(probs[mask])))

        return {
            'bin_centers': bin_centers,
            'bin_accuracies': bin_accuracies,
            'bin_confidences': bin_confidences,
            'bin_counts': bin_counts,
            'ece': self.compute_ece(probs, labels, n_bins),
            'mce': self.compute_mce(probs, labels, n_bins),
            'n_samples': n,
            'n_bins': n_bins,
        }

    def calibrate_confidence(self, confidence: float) -> float:
        """Calibrate a single confidence score.

        Convenience method for calibrating individual subsystem confidences.

        Args:
            confidence: Raw confidence in [0, 1].

        Returns:
            Calibrated confidence in [0, 1].
        """
        # Convert confidence to logit space
        conf = np.clip(confidence, 1e-6, 1 - 1e-6)
        logit = np.log(conf / (1 - conf))
        calibrated = self.calibrate(np.array([logit]))
        return float(calibrated[0])

    def get_stats(self) -> Dict[str, Any]:
        """Return calibrator statistics."""
        return {
            'is_fitted': self._is_fitted,
            'fit_count': self._fit_count,
            'calibrations': self._calibrations,
            'platt_a': round(self._a, 4),
            'platt_b': round(self._b, 4),
            'pre_ece': round(self._pre_ece, 6),
            'post_ece': round(self._post_ece, 6),
            'ece_improvement': round(self._pre_ece - self._post_ece, 6) if self._is_fitted else 0.0,
            'avg_ece': round(float(np.mean(self._ece_history)), 6) if self._ece_history else 0.0,
            'avg_mce': round(float(np.mean(self._mce_history)), 6) if self._mce_history else 0.0,
            'ece_history_len': len(self._ece_history),
        }
