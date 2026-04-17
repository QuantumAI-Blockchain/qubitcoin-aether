"""
Theory Engine — Generate and test hypotheses about blockchain behavior.

Auto-generates hypotheses from observed patterns, tests them statistically,
and consolidates compatible hypotheses into theories.

AI Roadmap Item #63.
"""
import time
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Hypothesis:
    """A testable hypothesis about system behavior."""
    statement: str
    variables: List[str]
    predicted_relationship: str  # positive_correlation, negative_correlation, threshold, cyclic
    confidence: float = 0.5
    evidence_for: int = 0
    evidence_against: int = 0
    created_at: float = field(default_factory=time.time)
    last_tested: float = 0.0
    domain: str = "general"


@dataclass
class TestResult:
    """Result of testing a hypothesis."""
    hypothesis: Hypothesis
    supported: bool
    p_value: float
    effect_size: float
    sample_size: int
    method: str


class TheoryEngine:
    """Generate and test hypotheses about blockchain/AI behavior."""

    def __init__(self, min_samples: int = 20, significance: float = 0.05) -> None:
        self._hypotheses: List[Hypothesis] = []
        self._test_results: List[TestResult] = []
        self._min_samples: int = min_samples
        self._significance: float = significance
        self._hypotheses_generated: int = 0
        self._tests_run: int = 0
        self._theories_formed: int = 0
        self._max_hypotheses: int = 200
        self._max_results: int = 500
        # Observation buffer for pattern detection
        self._observations: List[dict] = []
        self._max_observations: int = 2000

    def record_observation(self, observation: dict) -> None:
        """Record an observation for hypothesis generation."""
        self._observations.append(observation)
        if len(self._observations) > self._max_observations:
            self._observations = self._observations[-self._max_observations:]

    def generate_hypotheses(self, observations: Optional[List[dict]] = None) -> List[Hypothesis]:
        """Generate hypotheses from observed patterns.

        Looks for correlations between numeric variables and creates
        hypotheses about their relationships.
        """
        obs = observations or self._observations
        if len(obs) < self._min_samples:
            return []

        hypotheses = []

        # Extract numeric variables
        numeric_vars: Dict[str, List[float]] = {}
        for ob in obs:
            for key, val in ob.items():
                if isinstance(val, (int, float)):
                    if key not in numeric_vars:
                        numeric_vars[key] = []
                    numeric_vars[key].append(float(val))

        # Look for correlations between variable pairs
        var_names = list(numeric_vars.keys())
        for i in range(len(var_names)):
            for j in range(i + 1, len(var_names)):
                x_name, y_name = var_names[i], var_names[j]
                x_vals = numeric_vars[x_name]
                y_vals = numeric_vars[y_name]
                min_len = min(len(x_vals), len(y_vals))
                if min_len < self._min_samples:
                    continue

                x_arr = np.array(x_vals[:min_len])
                y_arr = np.array(y_vals[:min_len])

                # Compute correlation
                corr = self._pearson_correlation(x_arr, y_arr)
                abs_corr = abs(corr)

                if abs_corr > 0.3:
                    relationship = "positive_correlation" if corr > 0 else "negative_correlation"
                    h = Hypothesis(
                        statement=f"When {x_name} increases, {y_name} {'increases' if corr > 0 else 'decreases'}",
                        variables=[x_name, y_name],
                        predicted_relationship=relationship,
                        confidence=abs_corr,
                        domain=self._infer_domain(x_name, y_name),
                    )
                    hypotheses.append(h)

        # Look for threshold effects
        for var_name, values in numeric_vars.items():
            if len(values) < self._min_samples:
                continue
            arr = np.array(values)
            mean_val = float(np.mean(arr))
            std_val = float(np.std(arr))
            if std_val > 0 and abs(float(np.median(arr)) - mean_val) / std_val > 0.5:
                h = Hypothesis(
                    statement=f"{var_name} shows bimodal distribution (possible threshold effect)",
                    variables=[var_name],
                    predicted_relationship="threshold",
                    confidence=0.4,
                    domain=self._infer_domain(var_name),
                )
                hypotheses.append(h)

        # Deduplicate
        seen_statements: set = set()
        unique: List[Hypothesis] = []
        for h in hypotheses:
            if h.statement not in seen_statements:
                seen_statements.add(h.statement)
                unique.append(h)

        self._hypotheses.extend(unique)
        if len(self._hypotheses) > self._max_hypotheses:
            # Keep highest confidence
            self._hypotheses.sort(key=lambda h: h.confidence, reverse=True)
            self._hypotheses = self._hypotheses[:self._max_hypotheses]

        self._hypotheses_generated += len(unique)
        if unique:
            logger.debug(f"Generated {len(unique)} hypotheses from {len(obs)} observations")

        return unique

    def test_hypothesis(self, hypothesis: Hypothesis,
                        data: Dict[str, np.ndarray]) -> TestResult:
        """Test a hypothesis against data.

        Args:
            hypothesis: The hypothesis to test.
            data: Dict mapping variable names to arrays of values.

        Returns:
            TestResult with statistical assessment.
        """
        self._tests_run += 1
        hypothesis.last_tested = time.time()

        variables = hypothesis.variables
        if len(variables) < 2:
            # Single variable threshold test
            return self._test_threshold(hypothesis, data)

        x_name, y_name = variables[0], variables[1]
        if x_name not in data or y_name not in data:
            return TestResult(
                hypothesis=hypothesis,
                supported=False,
                p_value=1.0,
                effect_size=0.0,
                sample_size=0,
                method="missing_data",
            )

        x = data[x_name]
        y = data[y_name]
        min_len = min(len(x), len(y))
        x = x[:min_len]
        y = y[:min_len]

        if min_len < self._min_samples:
            return TestResult(
                hypothesis=hypothesis,
                supported=False,
                p_value=1.0,
                effect_size=0.0,
                sample_size=min_len,
                method="insufficient_data",
            )

        # Correlation test
        corr = self._pearson_correlation(x, y)
        # Approximate p-value using t-test for correlation
        t_stat = corr * np.sqrt((min_len - 2) / max(1 - corr ** 2, 1e-10))
        # Two-tailed p-value approximation
        p_value = self._approx_p_value(abs(t_stat), min_len - 2)

        # Check if direction matches hypothesis
        if hypothesis.predicted_relationship == "positive_correlation":
            supported = corr > 0 and p_value < self._significance
        elif hypothesis.predicted_relationship == "negative_correlation":
            supported = corr < 0 and p_value < self._significance
        else:
            supported = p_value < self._significance

        if supported:
            hypothesis.evidence_for += 1
            hypothesis.confidence = min(hypothesis.confidence * 1.1, 1.0)
        else:
            hypothesis.evidence_against += 1
            hypothesis.confidence = max(hypothesis.confidence * 0.9, 0.0)

        result = TestResult(
            hypothesis=hypothesis,
            supported=supported,
            p_value=float(p_value),
            effect_size=float(abs(corr)),
            sample_size=min_len,
            method="correlation",
        )
        self._test_results.append(result)
        if len(self._test_results) > self._max_results:
            self._test_results = self._test_results[-self._max_results:]

        return result

    def _test_threshold(self, hypothesis: Hypothesis,
                        data: Dict[str, np.ndarray]) -> TestResult:
        """Test a threshold hypothesis using distribution analysis."""
        var = hypothesis.variables[0]
        if var not in data:
            return TestResult(hypothesis=hypothesis, supported=False,
                              p_value=1.0, effect_size=0.0, sample_size=0,
                              method="missing_data")

        values = data[var]
        if len(values) < self._min_samples:
            return TestResult(hypothesis=hypothesis, supported=False,
                              p_value=1.0, effect_size=0.0,
                              sample_size=len(values), method="insufficient_data")

        # Bimodality test: compare mean vs median distance to std
        mean_val = float(np.mean(values))
        median_val = float(np.median(values))
        std_val = float(np.std(values))
        effect_size = abs(mean_val - median_val) / max(std_val, 1e-10)
        supported = effect_size > 0.5

        if supported:
            hypothesis.evidence_for += 1
        else:
            hypothesis.evidence_against += 1

        return TestResult(
            hypothesis=hypothesis,
            supported=supported,
            p_value=max(0.0, 1.0 - effect_size),
            effect_size=effect_size,
            sample_size=len(values),
            method="threshold_bimodality",
        )

    def consolidate_theories(self) -> int:
        """Merge compatible hypotheses into stronger theories.

        Returns:
            Number of merges performed.
        """
        merges = 0
        to_remove = set()

        for i in range(len(self._hypotheses)):
            if i in to_remove:
                continue
            for j in range(i + 1, len(self._hypotheses)):
                if j in to_remove:
                    continue
                hi = self._hypotheses[i]
                hj = self._hypotheses[j]
                # Same variables, same relationship direction
                if (set(hi.variables) == set(hj.variables)
                        and hi.predicted_relationship == hj.predicted_relationship):
                    # Merge: keep the one with more evidence
                    if hi.evidence_for >= hj.evidence_for:
                        hi.evidence_for += hj.evidence_for
                        hi.evidence_against += hj.evidence_against
                        hi.confidence = max(hi.confidence, hj.confidence)
                        to_remove.add(j)
                    else:
                        hj.evidence_for += hi.evidence_for
                        hj.evidence_against += hi.evidence_against
                        hj.confidence = max(hi.confidence, hj.confidence)
                        to_remove.add(i)
                    merges += 1

        if to_remove:
            self._hypotheses = [h for idx, h in enumerate(self._hypotheses)
                                if idx not in to_remove]
            self._theories_formed += merges

        return merges

    def _pearson_correlation(self, x: np.ndarray, y: np.ndarray) -> float:
        """Compute Pearson correlation coefficient."""
        n = len(x)
        if n < 2:
            return 0.0
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        x_std = np.std(x)
        y_std = np.std(y)
        if x_std < 1e-10 or y_std < 1e-10:
            return 0.0
        return float(np.sum((x - x_mean) * (y - y_mean)) / (n * x_std * y_std))

    def _approx_p_value(self, t_stat: float, df: int) -> float:
        """Approximate two-tailed p-value from t-statistic.

        Uses a simple sigmoid approximation for speed.
        """
        if df <= 0:
            return 1.0
        # Approximation: p ~ 2 * (1 - sigmoid(|t| * sqrt(df/10)))
        z = abs(t_stat) * np.sqrt(df / 10.0)
        p = 2.0 * (1.0 / (1.0 + np.exp(z)))
        return float(np.clip(p, 0.0, 1.0))

    def _infer_domain(self, *var_names: str) -> str:
        """Infer the domain from variable names."""
        domain_keywords = {
            "blockchain": ["block", "height", "tx", "hash", "difficulty"],
            "quantum_physics": ["energy", "qubit", "quantum", "vqe"],
            "economics": ["reward", "fee", "supply", "price"],
            "technology": ["latency", "throughput", "cpu", "memory"],
        }
        for domain, keywords in domain_keywords.items():
            for vname in var_names:
                for kw in keywords:
                    if kw in vname.lower():
                        return domain
        return "general"

    def granger_causality_approx(self, x: np.ndarray, y: np.ndarray,
                                 max_lag: int = 5) -> float:
        """Approximate Granger causality test.

        Returns improvement in prediction of Y when X-lags are included.
        Higher = more likely X Granger-causes Y.
        """
        if len(x) < max_lag + self._min_samples or len(y) < max_lag + self._min_samples:
            return 0.0

        n = min(len(x), len(y))
        x = x[:n]
        y = y[:n]

        # Restricted model: predict Y from its own lags
        y_lags = np.column_stack([y[max_lag - i - 1:n - i - 1] for i in range(max_lag)])
        y_target = y[max_lag:]

        # Unrestricted model: predict Y from its own lags + X lags
        x_lags = np.column_stack([x[max_lag - i - 1:n - i - 1] for i in range(max_lag)])
        full_lags = np.column_stack([y_lags, x_lags])

        # Fit linear models (via pseudoinverse)
        restricted_resid = self._ols_residuals(y_lags, y_target)
        unrestricted_resid = self._ols_residuals(full_lags, y_target)

        rss_r = float(np.sum(restricted_resid ** 2))
        rss_u = float(np.sum(unrestricted_resid ** 2))

        if rss_r < 1e-10:
            return 0.0

        improvement = (rss_r - rss_u) / rss_r
        return float(np.clip(improvement, 0.0, 1.0))

    def _ols_residuals(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """OLS residuals via pseudoinverse."""
        try:
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            return y - X @ beta
        except np.linalg.LinAlgError:
            return y

    def get_stats(self) -> dict:
        """Return theory engine statistics."""
        supported_count = sum(1 for r in self._test_results if r.supported)
        return {
            "hypotheses_generated": self._hypotheses_generated,
            "active_hypotheses": len(self._hypotheses),
            "tests_run": self._tests_run,
            "tests_supported": supported_count,
            "theories_formed": self._theories_formed,
            "observations_recorded": len(self._observations),
            "avg_confidence": float(np.mean(
                [h.confidence for h in self._hypotheses]
            )) if self._hypotheses else 0.0,
        }
