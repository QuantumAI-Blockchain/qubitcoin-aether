"""
Time-series Pattern Recognition for Blockchain Data (#50)

Detects patterns in time-series blockchain data beyond simple ARIMA:
- Trend detection (linear regression slope + significance)
- Change point detection (CUSUM algorithm)
- Anomaly detection (z-score based, >3 sigma)
- Seasonality detection (autocorrelation peaks)
- Cycle detection (dominant frequency via FFT)
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Pattern:
    """A detected pattern in a time series."""
    type: str           # trend_up, trend_down, trend_flat, seasonality,
                        # change_point, anomaly, cycle
    start_idx: int
    end_idx: int
    confidence: float   # 0.0 – 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'type': self.type,
            'start_idx': self.start_idx,
            'end_idx': self.end_idx,
            'confidence': round(self.confidence, 4),
            'metadata': self.metadata,
        }


class PatternDetector:
    """Detect structural patterns in time-series blockchain data."""

    def __init__(self, z_threshold: float = 3.0,
                 cusum_threshold: float = 5.0,
                 min_series_len: int = 20) -> None:
        self._z_threshold = z_threshold
        self._cusum_threshold = cusum_threshold
        self._min_series_len = min_series_len

        # Stats tracking
        self._calls: int = 0
        self._patterns_found: int = 0
        self._last_call: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_patterns(self, series: np.ndarray) -> List[Pattern]:
        """Detect all pattern types in a 1-D numeric series.

        Args:
            series: 1-D numpy array of numeric values.

        Returns:
            List of Pattern objects sorted by start_idx.
        """
        self._calls += 1
        self._last_call = time.time()

        if series.ndim != 1 or len(series) < self._min_series_len:
            return []

        series = series.astype(np.float64)
        patterns: List[Pattern] = []

        patterns.extend(self._detect_trends(series))
        patterns.extend(self._detect_change_points(series))
        patterns.extend(self._detect_anomalies(series))
        patterns.extend(self._detect_seasonality(series))
        patterns.extend(self._detect_cycles(series))

        patterns.sort(key=lambda p: p.start_idx)
        self._patterns_found += len(patterns)
        return patterns

    def summarize_patterns(self, patterns: List[Pattern]) -> str:
        """Produce a natural language summary of detected patterns.

        Args:
            patterns: List of Pattern objects.

        Returns:
            Human-readable summary string.
        """
        if not patterns:
            return "No significant patterns detected."

        parts: List[str] = []
        type_counts: Dict[str, int] = {}
        for p in patterns:
            type_counts[p.type] = type_counts.get(p.type, 0) + 1

        for ptype, count in type_counts.items():
            label = ptype.replace('_', ' ')
            if count == 1:
                p = next(pp for pp in patterns if pp.type == ptype)
                parts.append(
                    f"1 {label} pattern (idx {p.start_idx}-{p.end_idx}, "
                    f"confidence {p.confidence:.0%})"
                )
            else:
                parts.append(f"{count} {label} patterns")

        return "Detected: " + "; ".join(parts) + "."

    def get_stats(self) -> dict:
        """Return runtime statistics."""
        return {
            'calls': self._calls,
            'patterns_found': self._patterns_found,
            'z_threshold': self._z_threshold,
            'cusum_threshold': self._cusum_threshold,
            'min_series_len': self._min_series_len,
            'last_call': self._last_call,
        }

    # ------------------------------------------------------------------
    # Trend detection — linear regression
    # ------------------------------------------------------------------

    def _detect_trends(self, series: np.ndarray) -> List[Pattern]:
        """Detect linear trend segments via sliding-window regression."""
        n = len(series)
        if n < 10:
            return []

        patterns: List[Pattern] = []
        window = max(10, n // 5)  # Adaptive window

        for start in range(0, n - window + 1, window // 2):
            end = min(start + window, n)
            segment = series[start:end]
            seg_len = len(segment)
            if seg_len < 5:
                continue

            x = np.arange(seg_len, dtype=np.float64)
            x_mean = x.mean()
            y_mean = segment.mean()
            ss_xy = np.sum((x - x_mean) * (segment - y_mean))
            ss_xx = np.sum((x - x_mean) ** 2)

            if ss_xx < 1e-12:
                continue

            slope = ss_xy / ss_xx
            # R-squared for confidence
            y_hat = slope * (x - x_mean) + y_mean
            ss_res = np.sum((segment - y_hat) ** 2)
            ss_tot = np.sum((segment - y_mean) ** 2)
            r_sq = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
            r_sq = max(0.0, min(1.0, r_sq))

            # Significance: slope relative to std
            std = np.std(segment)
            if std < 1e-12:
                continue
            norm_slope = abs(slope) / std

            if norm_slope > 0.05 and r_sq > 0.3:
                if slope > 0:
                    ptype = 'trend_up'
                else:
                    ptype = 'trend_down'
                patterns.append(Pattern(
                    type=ptype,
                    start_idx=start,
                    end_idx=end - 1,
                    confidence=r_sq,
                    metadata={'slope': float(slope), 'r_squared': float(r_sq),
                              'normalized_slope': float(norm_slope)},
                ))
            elif norm_slope <= 0.05:
                patterns.append(Pattern(
                    type='trend_flat',
                    start_idx=start,
                    end_idx=end - 1,
                    confidence=max(0.3, 1.0 - norm_slope * 10),
                    metadata={'slope': float(slope), 'r_squared': float(r_sq)},
                ))

        return patterns

    # ------------------------------------------------------------------
    # Change point detection — CUSUM
    # ------------------------------------------------------------------

    def _detect_change_points(self, series: np.ndarray) -> List[Pattern]:
        """Detect change points using the CUSUM algorithm."""
        n = len(series)
        if n < 10:
            return []

        mean_val = np.mean(series)
        std_val = np.std(series)
        if std_val < 1e-12:
            return []

        # Normalize
        z = (series - mean_val) / std_val

        cusum_pos = np.zeros(n)
        cusum_neg = np.zeros(n)
        patterns: List[Pattern] = []

        for i in range(1, n):
            cusum_pos[i] = max(0.0, cusum_pos[i - 1] + z[i] - 0.5)
            cusum_neg[i] = max(0.0, cusum_neg[i - 1] - z[i] - 0.5)

            if cusum_pos[i] > self._cusum_threshold or cusum_neg[i] > self._cusum_threshold:
                direction = 'increase' if cusum_pos[i] > cusum_neg[i] else 'decrease'
                score = max(cusum_pos[i], cusum_neg[i])
                confidence = min(1.0, score / (self._cusum_threshold * 2))
                patterns.append(Pattern(
                    type='change_point',
                    start_idx=i,
                    end_idx=i,
                    confidence=confidence,
                    metadata={'direction': direction, 'cusum_score': float(score)},
                ))
                # Reset after detection
                cusum_pos[i] = 0.0
                cusum_neg[i] = 0.0

        return patterns

    # ------------------------------------------------------------------
    # Anomaly detection — z-score
    # ------------------------------------------------------------------

    def _detect_anomalies(self, series: np.ndarray) -> List[Pattern]:
        """Detect anomalies using z-score (>threshold sigma)."""
        std_val = np.std(series)
        if std_val < 1e-12:
            return []

        mean_val = np.mean(series)
        z_scores = np.abs((series - mean_val) / std_val)

        anomaly_mask = z_scores > self._z_threshold
        indices = np.where(anomaly_mask)[0]

        patterns: List[Pattern] = []
        for idx in indices:
            z = float(z_scores[idx])
            confidence = min(1.0, z / (self._z_threshold * 2))
            direction = 'high' if series[idx] > mean_val else 'low'
            patterns.append(Pattern(
                type='anomaly',
                start_idx=int(idx),
                end_idx=int(idx),
                confidence=confidence,
                metadata={'z_score': z, 'value': float(series[idx]),
                          'mean': float(mean_val), 'direction': direction},
            ))

        return patterns

    # ------------------------------------------------------------------
    # Seasonality detection — autocorrelation peaks
    # ------------------------------------------------------------------

    def _detect_seasonality(self, series: np.ndarray) -> List[Pattern]:
        """Detect seasonal patterns via autocorrelation peaks."""
        n = len(series)
        if n < 20:
            return []

        # Compute autocorrelation (unbiased)
        centered = series - np.mean(series)
        var = np.sum(centered ** 2)
        if var < 1e-12:
            return []

        max_lag = n // 3
        acf = np.zeros(max_lag)
        for lag in range(1, max_lag):
            acf[lag] = np.sum(centered[:n - lag] * centered[lag:]) / var

        # Find peaks in ACF (local maxima above significance threshold)
        sig_threshold = 2.0 / np.sqrt(n)  # Bartlett's formula approximation
        patterns: List[Pattern] = []

        for i in range(2, max_lag - 1):
            if acf[i] > sig_threshold and acf[i] > acf[i - 1] and acf[i] > acf[i + 1]:
                confidence = min(1.0, float(acf[i]) / 0.5)  # Normalize to 0.5 as "strong"
                patterns.append(Pattern(
                    type='seasonality',
                    start_idx=0,
                    end_idx=n - 1,
                    confidence=confidence,
                    metadata={'period': i, 'acf_value': float(acf[i]),
                              'significance': float(sig_threshold)},
                ))

        # Keep only top-3 seasonal components
        patterns.sort(key=lambda p: p.confidence, reverse=True)
        return patterns[:3]

    # ------------------------------------------------------------------
    # Cycle detection — FFT dominant frequency
    # ------------------------------------------------------------------

    def _detect_cycles(self, series: np.ndarray) -> List[Pattern]:
        """Detect dominant cycles via FFT."""
        n = len(series)
        if n < 20:
            return []

        # Detrend (remove linear trend)
        x = np.arange(n, dtype=np.float64)
        x_mean = x.mean()
        y_mean = series.mean()
        ss_xy = np.sum((x - x_mean) * (series - y_mean))
        ss_xx = np.sum((x - x_mean) ** 2)
        slope = ss_xy / ss_xx if ss_xx > 1e-12 else 0.0
        detrended = series - (slope * x + (y_mean - slope * x_mean))

        # FFT
        fft_vals = np.fft.rfft(detrended)
        magnitudes = np.abs(fft_vals)

        # Skip DC component (index 0) and very high frequencies
        if len(magnitudes) < 3:
            return []

        magnitudes[0] = 0.0  # Remove DC
        total_power = np.sum(magnitudes ** 2)
        if total_power < 1e-12:
            return []

        patterns: List[Pattern] = []
        # Find top-3 frequency peaks
        sorted_indices = np.argsort(magnitudes)[::-1]

        for freq_idx in sorted_indices[:3]:
            if freq_idx == 0:
                continue
            power_fraction = (magnitudes[freq_idx] ** 2) / total_power
            if power_fraction < 0.05:  # Less than 5% of total power
                continue

            period = n / freq_idx
            if period < 3:  # Ignore very short cycles
                continue

            confidence = min(1.0, power_fraction * 5)  # Scale confidence
            patterns.append(Pattern(
                type='cycle',
                start_idx=0,
                end_idx=n - 1,
                confidence=confidence,
                metadata={'period': float(period), 'frequency_idx': int(freq_idx),
                          'power_fraction': float(power_fraction)},
            ))

        return patterns
