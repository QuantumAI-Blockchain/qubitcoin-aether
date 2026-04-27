"""
Tests for ARIMA(1,1,1) forecasting in TemporalEngine.

Covers:
- Basic ARIMA fit and forecast
- Linear extrapolation fallback (short history)
- Edge cases (empty, single value, constant series)
- Confidence intervals expand with forecast horizon
- Inverse differencing correctness
- OLS fitting
- ARIMA coefficient bounds (stationarity/invertibility)
- Integration with TemporalEngine.forecast_metric
"""
import math

import numpy as np
import pytest

from qubitcoin.aether.temporal import (
    ARIMAResult,
    ForecastPoint,
    ForecastResult,
    TemporalEngine,
)


@pytest.fixture
def engine() -> TemporalEngine:
    """Create a fresh TemporalEngine with no knowledge graph."""
    return TemporalEngine(knowledge_graph=None)


# ============================================================================
# 1. Basic ARIMA forecast with enough data
# ============================================================================

class TestForecastMetricARIMA:
    """Tests for ARIMA-based forecasting (history >= 10 points)."""

    def test_basic_arima_returns_correct_steps(self, engine: TemporalEngine) -> None:
        """forecast_metric returns the requested number of forecast steps."""
        history = [float(i) + 0.1 * i for i in range(50)]
        result = engine.forecast_metric("difficulty", history, steps_ahead=5)

        assert isinstance(result, ForecastResult)
        assert result.method == "arima"
        assert result.metric_name == "difficulty"
        assert len(result.forecasts) == 5
        assert result.history_length == 50

    def test_arima_forecast_step_numbering(self, engine: TemporalEngine) -> None:
        """Each ForecastPoint has the correct step number (1..N)."""
        history = list(range(30))
        result = engine.forecast_metric("tx_count", history, steps_ahead=7)

        for i, fp in enumerate(result.forecasts):
            assert fp.step == i + 1

    def test_arima_model_has_valid_coefficients(self, engine: TemporalEngine) -> None:
        """Fitted ARIMA model has AR and MA coefficients in (-1, 1)."""
        # AR(1) process with known coefficient
        np.random.seed(42)
        y = [10.0]
        for _ in range(99):
            y.append(y[-1] + 0.5 * (y[-1] - y[-2] if len(y) > 1 else 0) + np.random.normal(0, 0.1))

        result = engine.forecast_metric("test_metric", y, steps_ahead=3)
        model = result.model

        assert -1.0 < model.ar_coeff < 1.0
        assert -1.0 < model.ma_coeff < 1.0
        assert model.n_observations == len(y)

    def test_arima_confidence_intervals_expand(self, engine: TemporalEngine) -> None:
        """Confidence intervals should widen as forecast horizon increases."""
        history = [10.0 + 0.5 * i + 0.3 * math.sin(i) for i in range(60)]
        result = engine.forecast_metric("phi_value", history, steps_ahead=10)

        # 95% CI width should increase monotonically
        prev_width = 0.0
        for fp in result.forecasts:
            width_95 = fp.upper_95 - fp.lower_95
            assert width_95 >= prev_width - 1e-9, (
                f"Step {fp.step}: CI width {width_95:.4f} < previous {prev_width:.4f}"
            )
            prev_width = width_95

    def test_arima_80_inside_95_confidence(self, engine: TemporalEngine) -> None:
        """80% CI should be strictly inside 95% CI."""
        history = [float(x) for x in range(30)]
        result = engine.forecast_metric("energy", history, steps_ahead=5)

        for fp in result.forecasts:
            assert fp.lower_95 <= fp.lower_80, f"Step {fp.step}: 95% lower > 80% lower"
            assert fp.upper_80 <= fp.upper_95, f"Step {fp.step}: 80% upper > 95% upper"

    def test_arima_trending_series_forecasts_trend(self, engine: TemporalEngine) -> None:
        """A clearly rising series should produce rising forecasts."""
        history = [100.0 + 2.0 * i for i in range(40)]
        result = engine.forecast_metric("difficulty", history, steps_ahead=5)

        # All forecasts should be above the last observed value
        last_val = history[-1]
        for fp in result.forecasts:
            assert fp.value >= last_val - 1.0, (
                f"Step {fp.step}: forecast {fp.value} below last value {last_val}"
            )

    def test_arima_large_steps_ahead(self, engine: TemporalEngine) -> None:
        """Forecast many steps ahead without error."""
        history = [float(i) for i in range(100)]
        result = engine.forecast_metric("blocks", history, steps_ahead=50)
        assert len(result.forecasts) == 50
        assert result.method == "arima"


# ============================================================================
# 2. Linear extrapolation fallback (short history)
# ============================================================================

class TestLinearExtrapolation:
    """Tests for the linear fallback when history < 10 points."""

    def test_short_history_uses_linear(self, engine: TemporalEngine) -> None:
        """History with < 10 points falls back to linear extrapolation."""
        history = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = engine.forecast_metric("test", history, steps_ahead=3)
        assert result.method == "linear"
        assert len(result.forecasts) == 3

    def test_linear_extrapolation_direction(self, engine: TemporalEngine) -> None:
        """Linear extrapolation of a rising 5-point series should rise."""
        history = [10.0, 12.0, 14.0, 16.0, 18.0]
        result = engine.forecast_metric("linear_test", history, steps_ahead=3)
        # Each forecast should be higher than the previous
        prev = history[-1]
        for fp in result.forecasts:
            assert fp.value > prev - 0.01
            prev = fp.value

    def test_single_point_history(self, engine: TemporalEngine) -> None:
        """Single-point history produces constant forecasts."""
        result = engine.forecast_metric("const", [42.0], steps_ahead=3)
        assert result.method == "linear"
        for fp in result.forecasts:
            assert abs(fp.value - 42.0) < 1e-6

    def test_two_point_history(self, engine: TemporalEngine) -> None:
        """Two-point history should extrapolate the slope."""
        result = engine.forecast_metric("slope", [10.0, 20.0], steps_ahead=2)
        assert result.method == "linear"
        # Slope is 10 per step; forecast step 1 at index 2 should be ~30
        assert result.forecasts[0].value == pytest.approx(30.0, abs=1.0)


# ============================================================================
# 3. Edge cases
# ============================================================================

class TestEdgeCases:
    """Tests for degenerate and edge-case inputs."""

    def test_empty_history(self, engine: TemporalEngine) -> None:
        """Empty history returns empty forecasts with method='none'."""
        result = engine.forecast_metric("empty", [], steps_ahead=5)
        assert result.method == "none"
        assert len(result.forecasts) == 0

    def test_zero_steps_ahead(self, engine: TemporalEngine) -> None:
        """Zero steps ahead returns empty forecasts."""
        result = engine.forecast_metric("zero", [1.0, 2.0, 3.0], steps_ahead=0)
        assert len(result.forecasts) == 0

    def test_constant_series(self, engine: TemporalEngine) -> None:
        """Constant series should forecast approximately the same value."""
        history = [5.0] * 50
        result = engine.forecast_metric("const", history, steps_ahead=5)
        for fp in result.forecasts:
            # Forecast should be near the constant value
            assert abs(fp.value - 5.0) < 1.0, f"Step {fp.step}: {fp.value} != ~5.0"

    def test_negative_steps_ahead(self, engine: TemporalEngine) -> None:
        """Negative steps_ahead returns empty forecasts."""
        result = engine.forecast_metric("neg", [1.0, 2.0], steps_ahead=-1)
        assert len(result.forecasts) == 0


# ============================================================================
# 4. Internal methods
# ============================================================================

class TestInternalMethods:
    """Tests for _fit_arima, _ols_fit, _inverse_difference, _compute_residuals."""

    def test_ols_fit_perfect_linear(self, engine: TemporalEngine) -> None:
        """OLS on a perfect line y = 2x + 3 recovers exact coefficients."""
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = 2.0 * x + 3.0
        coeff, intercept = engine._ols_fit(x, y)
        assert abs(coeff - 2.0) < 1e-10
        assert abs(intercept - 3.0) < 1e-10

    def test_ols_fit_empty(self, engine: TemporalEngine) -> None:
        """OLS on empty arrays returns (0, 0)."""
        coeff, intercept = engine._ols_fit(np.array([]), np.array([]))
        assert coeff == 0.0
        assert intercept == 0.0

    def test_inverse_difference(self, engine: TemporalEngine) -> None:
        """Inverse differencing reconstructs original scale from diffs."""
        original = [10.0, 12.0, 15.0, 13.0, 18.0]
        diffs = [original[i] - original[i - 1] for i in range(1, len(original))]
        reconstructed = engine._inverse_difference(original[0], diffs)
        for a, b in zip(original[1:], reconstructed):
            assert abs(a - b) < 1e-10

    def test_fit_arima_raises_on_short_history(self, engine: TemporalEngine) -> None:
        """_fit_arima raises ValueError if history < 10 points."""
        with pytest.raises(ValueError, match="too short"):
            engine._fit_arima([1.0, 2.0, 3.0])

    def test_fit_arima_returns_arima_result(self, engine: TemporalEngine) -> None:
        """_fit_arima returns a valid ARIMAResult dataclass."""
        history = [float(i) + 0.1 * (i % 3) for i in range(30)]
        result = engine._fit_arima(history)
        assert isinstance(result, ARIMAResult)
        assert result.n_observations == 30
        assert result.residual_std >= 0.0

    def test_compute_residuals_length(self, engine: TemporalEngine) -> None:
        """_compute_residuals returns array of same length as diff series."""
        history = [float(i) for i in range(20)]
        model = engine._fit_arima(history)
        diff = np.diff(np.array(history, dtype=np.float64))
        residuals = engine._compute_residuals(diff, model)
        assert len(residuals) == len(diff)
