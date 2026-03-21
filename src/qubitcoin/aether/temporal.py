"""
Temporal Reasoning & Prediction Engine — Time-Aware Knowledge Processing

Tracks time-series data derived from the knowledge graph and block stream,
detects trends and anomalies, and generates prediction nodes.

Improvement #6: Without temporal reasoning, the system treats all knowledge
as a flat snapshot.  This module adds the ability to detect trends
("difficulty is rising"), anomalies ("transaction surge at block X"),
and make predictions that can be verified later.

Includes ARIMA(1,1,1)-style multi-step forecasting for metric prediction
with confidence intervals, using only numpy for computation.
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# ARIMA(1,1,1) Forecasting Data Structures
# ============================================================================

@dataclass
class ARIMAResult:
    """Result of an ARIMA(1,1,1) model fit."""
    ar_coeff: float           # AR(1) coefficient (phi_1)
    ma_coeff: float           # MA(1) coefficient (theta_1)
    intercept: float          # Drift/intercept term
    residual_std: float       # Standard deviation of residuals
    n_observations: int       # Number of observations used
    aic: float = 0.0          # Akaike Information Criterion (approximate)


@dataclass
class ForecastPoint:
    """A single forecast point with confidence interval."""
    step: int                 # Steps ahead from last observation
    value: float              # Point forecast
    lower_80: float           # 80% confidence interval lower bound
    upper_80: float           # 80% confidence interval upper bound
    lower_95: float           # 95% confidence interval lower bound
    upper_95: float           # 95% confidence interval upper bound


@dataclass
class ForecastResult:
    """Complete forecast result from ARIMA model."""
    metric_name: str
    model: ARIMAResult
    forecasts: List[ForecastPoint] = field(default_factory=list)
    method: str = "arima"     # "arima" or "linear" (fallback)
    history_length: int = 0


class TemporalEngine:
    """
    Temporal reasoning over the knowledge graph.

    Capabilities:
    1. Time-series tracking of key metrics (difficulty, tx count, etc.)
    2. Trend detection via linear regression over a sliding window
    3. Anomaly detection via z-score (>2 standard deviations)
    4. Prediction nodes: forecasts that can be verified in future blocks
    5. Prediction validation: compare predictions to outcomes
    """

    def __init__(self, knowledge_graph=None) -> None:
        self.kg = knowledge_graph
        # Time-series buffers: metric_name -> [(block_height, value)]
        self._series: Dict[str, List[Tuple[int, float]]] = {}
        self._max_series_length: int = 2000
        # Prediction tracking
        self._predictions: List[dict] = []
        self._predictions_validated: int = 0
        self._predictions_correct: int = 0
        # Recently verified predictions (for feedback loop)
        self._verified_outcomes: List[dict] = []
        self._max_verified_outcomes: int = 500

    def record_metric(self, metric: str, block_height: int, value: float) -> None:
        """Record a time-series data point."""
        if metric not in self._series:
            self._series[metric] = []
        self._series[metric].append((block_height, value))
        # Trim to window
        if len(self._series[metric]) > self._max_series_length:
            self._series[metric] = self._series[metric][-self._max_series_length:]

    def detect_trend(self, metric: str, window: int = 100) -> Optional[dict]:
        """
        Detect trend in a metric using linear regression.

        Returns:
            Dict with slope, direction ('rising'/'falling'/'stable'),
            r_squared, and confidence.
        """
        series = self._series.get(metric, [])
        if len(series) < max(10, window // 5):
            return None

        # Use last `window` points
        data = series[-window:]
        n = len(data)
        blocks = [d[0] for d in data]
        values = [d[1] for d in data]

        # Linear regression: y = mx + b
        mean_x = sum(blocks) / n
        mean_y = sum(values) / n

        ss_xx = sum((x - mean_x) ** 2 for x in blocks)
        ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(blocks, values))
        ss_yy = sum((y - mean_y) ** 2 for y in values)

        if ss_xx == 0:
            return None

        slope = ss_xy / ss_xx
        r_squared = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_yy > 0 else 0

        # Classify direction
        if abs(slope) < 1e-6:
            direction = 'stable'
        elif slope > 0:
            direction = 'rising'
        else:
            direction = 'falling'

        return {
            'metric': metric,
            'slope': round(slope, 8),
            'direction': direction,
            'r_squared': round(r_squared, 4),
            'confidence': round(min(1.0, r_squared * (n / window)), 4),
            'window': n,
            'latest_value': values[-1],
            'latest_block': blocks[-1],
        }

    def detect_anomaly(self, metric: str,
                       z_threshold: float = 2.0,
                       window: int = 100) -> Optional[dict]:
        """
        Detect anomalies using adaptive z-score deviation.

        Uses an adaptive threshold based on recent variance: if the metric
        has been volatile recently, the threshold is raised to avoid
        false positives. If stable, it is kept low for sensitivity.

        Returns anomaly info if the latest value exceeds the adaptive threshold.
        """
        series = self._series.get(metric, [])
        if len(series) < 20:
            return None

        data = series[-window:]
        values = [d[1] for d in data]
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = math.sqrt(variance) if variance > 0 else 0

        if std == 0:
            return None

        # Adaptive threshold: compute recent variance (last 20% of window)
        # vs overall variance. If recent variance is higher, raise threshold.
        recent_count = max(5, n // 5)
        recent_values = values[-recent_count:]
        recent_mean = sum(recent_values) / len(recent_values)
        recent_var = sum((v - recent_mean) ** 2 for v in recent_values) / len(recent_values)
        recent_std = math.sqrt(recent_var) if recent_var > 0 else 0

        # Adaptive factor: if recent volatility > 1.5x overall, raise threshold
        if std > 0 and recent_std / std > 1.5:
            adaptive_threshold = z_threshold * 1.3
        elif std > 0 and recent_std / std < 0.5:
            # Very stable recently: lower threshold for sensitivity
            adaptive_threshold = z_threshold * 0.8
        else:
            adaptive_threshold = z_threshold

        latest = values[-1]
        z_score = (latest - mean) / std

        if abs(z_score) < adaptive_threshold:
            return None

        return {
            'metric': metric,
            'z_score': round(z_score, 4),
            'value': latest,
            'mean': round(mean, 6),
            'std': round(std, 6),
            'direction': 'high' if z_score > 0 else 'low',
            'block': data[-1][0],
            'adaptive_threshold': round(adaptive_threshold, 2),
            'recent_volatility': round(recent_std / std, 3) if std > 0 else 0.0,
        }

    def make_prediction(self, metric: str, blocks_ahead: int = 100,
                        block_height: int = 0) -> Optional[dict]:
        """
        Generate a prediction node based on trend extrapolation.

        Creates a 'prediction' type node in the knowledge graph.
        """
        trend = self.detect_trend(metric)
        if not trend or trend['confidence'] < 0.3:
            return None

        predicted_value = trend['latest_value'] + trend['slope'] * blocks_ahead
        target_block = trend['latest_block'] + blocks_ahead

        prediction = {
            'metric': metric,
            'predicted_value': round(predicted_value, 6),
            'target_block': target_block,
            'source_block': block_height or trend['latest_block'],
            'confidence': trend['confidence'] * 0.7,  # Discount for extrapolation
            'trend_direction': trend['direction'],
            'slope': trend['slope'],
        }

        self._predictions.append(prediction)
        if len(self._predictions) > 500:
            self._predictions = self._predictions[-500:]

        # Create prediction node in knowledge graph
        if self.kg:
            content = {
                'type': 'temporal_prediction',
                'text': (f"Predicted {metric} will be ~{predicted_value:.4f} "
                         f"at block {target_block} (trend: {trend['direction']})"),
                **prediction,
            }
            node = self.kg.add_node(
                node_type='prediction',
                content=content,
                confidence=prediction['confidence'],
                source_block=prediction['source_block'],
            )
            prediction['node_id'] = node.node_id if node else None

        return prediction

    def validate_predictions(self, block_height: int) -> int:
        """
        Check past predictions against actual values.

        For each prediction whose target_block has passed, compare
        the predicted value to the actual value. Update the knowledge
        graph node accordingly.

        Returns:
            Number of predictions validated.
        """
        validated = 0
        remaining: List[dict] = []

        for pred in self._predictions:
            target_block = pred['target_block']
            if target_block > block_height:
                remaining.append(pred)
                continue

            # Check actual value
            metric = pred['metric']
            series = self._series.get(metric, [])
            # Find the closest data point to the target block
            actual = None
            for block, value in reversed(series):
                if block <= target_block:
                    actual = value
                    break

            if actual is None:
                remaining.append(pred)
                continue

            self._predictions_validated += 1
            validated += 1

            # Compute prediction accuracy
            predicted = pred['predicted_value']
            if actual != 0:
                error_pct = abs(predicted - actual) / abs(actual)
            else:
                error_pct = abs(predicted - actual)

            correct = error_pct < 0.2  # Within 20% = correct
            if correct:
                self._predictions_correct += 1

            # Update knowledge graph node if exists
            node_id = pred.get('node_id')
            if node_id and self.kg:
                node = self.kg.nodes.get(node_id)
                if node:
                    # Adjust confidence based on accuracy
                    if correct:
                        node.confidence = min(1.0, node.confidence + 0.1)
                    else:
                        node.confidence = max(0.05, node.confidence - 0.2)

                    # Add verification content
                    node.content['verified'] = True
                    node.content['actual_value'] = round(actual, 6)
                    node.content['error_pct'] = round(error_pct, 4)
                    node.content['prediction_correct'] = correct

                    # Create a verification result node in the knowledge graph
                    pred_confidence = pred.get('confidence', 0.5)
                    if correct:
                        verification_content = {
                            'type': 'prediction_confirmed',
                            'metric': metric,
                            'predicted': round(predicted, 6),
                            'actual': round(actual, 6),
                            'error_pct': round(error_pct, 4),
                        }
                        verification_confidence = min(1.0, pred_confidence + 0.2)
                    else:
                        verification_content = {
                            'type': 'prediction_falsified',
                            'metric': metric,
                            'predicted': round(predicted, 6),
                            'actual': round(actual, 6),
                            'error_pct': round(error_pct, 4),
                        }
                        verification_confidence = max(0.1, pred_confidence - 0.3)

                    try:
                        v_node = self.kg.add_node(
                            node_type='assertion',
                            content=verification_content,
                            confidence=verification_confidence,
                            source_block=block_height,
                        )
                        if v_node:
                            # Verified predictions are grounded by comparison to actual data
                            v_node.grounding_source = 'prediction_verified'
                            self.kg.add_edge(node_id, v_node.node_id, edge_type='derives')
                            pred['verification_node_id'] = v_node.node_id
                    except Exception as e:
                        logger.debug(f"Failed to create verification node: {e}")

            # Record verified outcome for feedback loop consumption
            self._verified_outcomes.append({
                'metric': metric,
                'predicted': round(predicted, 6),
                'actual': round(actual, 6),
                'error_pct': round(error_pct, 4),
                'correct': correct,
                'prediction_node_id': node_id,
                'verification_node_id': pred.get('verification_node_id'),
                'target_block': target_block,
                'validated_at_block': block_height,
            })

        # Trim verified outcomes buffer
        if len(self._verified_outcomes) > self._max_verified_outcomes:
            self._verified_outcomes = self._verified_outcomes[-self._max_verified_outcomes:]

        self._predictions = remaining

        if validated > 0:
            logger.info(
                f"Validated {validated} predictions at block {block_height} "
                f"(accuracy: {self.get_accuracy():.1%})"
            )
        return validated

    def process_block(self, block_height: int, block_data: dict) -> dict:
        """
        Process a new block for temporal reasoning.

        Extracts metrics, checks for anomalies, validates predictions,
        and generates new predictions periodically.

        Args:
            block_height: Current block height.
            block_data: Dict with block metadata (difficulty, tx_count, etc.)

        Returns:
            Dict with temporal analysis results.
        """
        results: dict = {
            'metrics_recorded': 0,
            'trends': [],
            'anomalies': [],
            'predictions_validated': 0,
            'new_predictions': [],
        }

        # Record standard metrics
        for key in ('difficulty', 'tx_count', 'energy', 'knowledge_nodes',
                     'knowledge_edges', 'phi_value'):
            value = block_data.get(key)
            if value is not None:
                self.record_metric(key, block_height, float(value))
                results['metrics_recorded'] += 1

        # Detect trends every 50 blocks
        if block_height % 50 == 0:
            for metric in self._series:
                trend = self.detect_trend(metric)
                if trend and trend['confidence'] > 0.3:
                    results['trends'].append(trend)

                    # Create trend observation node
                    if self.kg and trend['direction'] != 'stable':
                        self.kg.add_node(
                            node_type='observation',
                            content={
                                'type': 'trend_observation',
                                'text': (f"{metric} is {trend['direction']} "
                                         f"(slope={trend['slope']:.6f}, "
                                         f"r²={trend['r_squared']:.3f})"),
                                **trend,
                            },
                            confidence=trend['confidence'],
                            source_block=block_height,
                        )

        # Detect anomalies every block
        for metric in self._series:
            anomaly = self.detect_anomaly(metric)
            if anomaly:
                results['anomalies'].append(anomaly)
                if self.kg:
                    self.kg.add_node(
                        node_type='observation',
                        content={
                            'type': 'anomaly_detection',
                            'text': (f"Anomaly in {metric}: z-score={anomaly['z_score']:.2f} "
                                     f"({anomaly['direction']})"),
                            **anomaly,
                        },
                        confidence=0.85,
                        source_block=block_height,
                    )

        # Validate past predictions
        results['predictions_validated'] = self.validate_predictions(block_height)

        # Make new predictions every 200 blocks
        if block_height % 200 == 0:
            for metric in self._series:
                pred = self.make_prediction(metric, blocks_ahead=200,
                                            block_height=block_height)
                if pred:
                    results['new_predictions'].append(pred)

        return results

    def get_accuracy(self) -> float:
        """Get prediction accuracy rate."""
        if self._predictions_validated == 0:
            return 0.0
        return self._predictions_correct / self._predictions_validated

    def get_verified_outcomes(self, since_block: int = 0) -> List[dict]:
        """Return recently verified predictions with their outcomes.

        Used by the proof_of_thought feedback loop to feed outcomes
        to neural_reasoner and metacognition.

        Args:
            since_block: Only return outcomes validated at or after this block.

        Returns:
            List of dicts with keys: metric, predicted, actual, error_pct,
            correct, prediction_node_id, verification_node_id,
            target_block, validated_at_block.
        """
        if since_block <= 0:
            return list(self._verified_outcomes)
        return [
            o for o in self._verified_outcomes
            if o.get('validated_at_block', 0) >= since_block
        ]

    # ========================================================================
    # ARIMA(1,1,1) Forecasting
    # ========================================================================

    def forecast_metric(self, metric_name: str, history: List[float],
                        steps_ahead: int = 5) -> ForecastResult:
        """
        Generate multi-step forecasts using ARIMA(1,1,1) or linear fallback.

        Implements a simple ARIMA(1,1,1) model:
          - Differencing (d=1) to make the series stationary
          - AR(1) component for autoregressive structure
          - MA(1) component for moving average of residuals
          - Multi-step forecast with expanding confidence intervals

        If history has fewer than 10 points, falls back to simple linear
        extrapolation.

        Args:
            metric_name: Name of the metric being forecast.
            history: List of float values (time-ordered, evenly spaced).
            steps_ahead: Number of future steps to forecast (default 5).

        Returns:
            ForecastResult with point forecasts and confidence intervals.
        """
        if not history or steps_ahead < 1:
            return ForecastResult(
                metric_name=metric_name,
                model=ARIMAResult(0.0, 0.0, 0.0, 0.0, 0),
                forecasts=[],
                method="none",
                history_length=len(history) if history else 0,
            )

        if len(history) < 10:
            return self._linear_extrapolation(metric_name, history, steps_ahead)

        try:
            model = self._fit_arima(history)
        except Exception as e:
            logger.debug(f"ARIMA fit failed for {metric_name}: {e}, falling back to linear")
            return self._linear_extrapolation(metric_name, history, steps_ahead)

        # Generate multi-step forecast on the differenced series
        # then invert back to original scale
        diff_series = np.diff(np.array(history, dtype=np.float64))
        n = len(diff_series)

        # Reconstruct residuals from the fitted model for last MA term
        residuals = self._compute_residuals(diff_series, model)
        last_residual = residuals[-1] if len(residuals) > 0 else 0.0

        forecasts: List[ForecastPoint] = []
        last_diff = float(diff_series[-1])
        last_value = float(history[-1])
        cumulative_variance = 0.0

        for step in range(1, steps_ahead + 1):
            # ARIMA(1,1,1) forecast on differenced series:
            # d_hat(t+h) = intercept + ar_coeff * d(t+h-1) + ma_coeff * e(t+h-1)
            if step == 1:
                diff_forecast = (model.intercept
                                 + model.ar_coeff * last_diff
                                 + model.ma_coeff * last_residual)
            else:
                # For h > 1, the MA term drops out (future residuals are 0)
                diff_forecast = (model.intercept
                                 + model.ar_coeff * prev_diff_forecast)

            prev_diff_forecast = diff_forecast

            # Inverse difference: cumulative sum back to original scale
            forecast_value = last_value + diff_forecast
            last_value = forecast_value

            # Expanding confidence intervals
            # Variance grows with each step for ARIMA forecasts
            if step == 1:
                step_var = model.residual_std ** 2
            else:
                # For ARIMA(1,1,1), forecast variance expands with AR propagation
                step_var = (model.residual_std ** 2) * (
                    1.0 + sum(model.ar_coeff ** (2 * j) for j in range(1, step))
                )
            cumulative_variance += step_var
            cumulative_std = math.sqrt(max(cumulative_variance, 1e-12))

            # z-scores: 80% -> 1.282, 95% -> 1.960
            forecasts.append(ForecastPoint(
                step=step,
                value=round(forecast_value, 6),
                lower_80=round(forecast_value - 1.282 * cumulative_std, 6),
                upper_80=round(forecast_value + 1.282 * cumulative_std, 6),
                lower_95=round(forecast_value - 1.960 * cumulative_std, 6),
                upper_95=round(forecast_value + 1.960 * cumulative_std, 6),
            ))

        return ForecastResult(
            metric_name=metric_name,
            model=model,
            forecasts=forecasts,
            method="arima",
            history_length=len(history),
        )

    def _fit_arima(self, history: List[float]) -> ARIMAResult:
        """
        Fit an ARIMA(1,1,1) model to the history using least squares.

        Steps:
          1. Difference the series (d=1): diff[t] = y[t] - y[t-1]
          2. Fit AR(1) coefficient via OLS on lagged differences
          3. Compute residuals, then fit MA(1) on lagged residuals
          4. Iterate once to refine (conditional least squares)

        Args:
            history: Raw time series values (at least 10 points).

        Returns:
            ARIMAResult with fitted coefficients.

        Raises:
            ValueError: If history is too short for fitting.
        """
        y = np.array(history, dtype=np.float64)
        if len(y) < 10:
            raise ValueError(f"History too short for ARIMA: {len(y)} < 10")

        # Step 1: Difference the series (d=1)
        diff = np.diff(y)
        n = len(diff)

        # Step 2: Initial AR(1) fit via OLS
        # diff[t] = intercept + ar_coeff * diff[t-1] + e[t]
        X_ar = diff[:-1]  # lagged values (t-1)
        y_ar = diff[1:]   # current values (t)

        ar_coeff, intercept = self._ols_fit(X_ar, y_ar)

        # Clamp AR coefficient to stationary region (-0.99, 0.99)
        ar_coeff = max(-0.99, min(0.99, ar_coeff))

        # Step 3: Compute residuals and fit MA(1)
        residuals = np.zeros(n)
        for t in range(1, n):
            predicted = intercept + ar_coeff * diff[t - 1]
            residuals[t] = diff[t] - predicted

        # MA(1) fit: residuals[t] should include theta * residuals[t-1]
        # Re-fit: diff[t] = intercept + ar_coeff * diff[t-1] + ma_coeff * e[t-1] + e[t]
        if n > 3:
            X_resid = residuals[1:-1]  # lagged residuals
            y_resid = y_ar[1:] - intercept - ar_coeff * X_ar[1:]
            if len(X_resid) > 0 and np.std(X_resid) > 1e-12:
                ma_coeff, _ = self._ols_fit(X_resid, y_resid)
            else:
                ma_coeff = 0.0
        else:
            ma_coeff = 0.0

        # Clamp MA coefficient to invertibility region (-0.99, 0.99)
        ma_coeff = max(-0.99, min(0.99, ma_coeff))

        # Step 4: Recompute final residuals with both AR and MA
        final_residuals = np.zeros(n)
        for t in range(1, n):
            predicted = (intercept
                         + ar_coeff * diff[t - 1]
                         + ma_coeff * final_residuals[t - 1])
            final_residuals[t] = diff[t] - predicted

        residual_std = float(np.std(final_residuals[1:])) if n > 2 else 0.0

        # Approximate AIC = n * ln(RSS/n) + 2k (k=3 parameters)
        rss = float(np.sum(final_residuals[1:] ** 2))
        n_eff = n - 1
        if n_eff > 0 and rss > 0:
            aic = n_eff * math.log(rss / n_eff) + 2 * 3
        else:
            aic = 0.0

        return ARIMAResult(
            ar_coeff=round(float(ar_coeff), 8),
            ma_coeff=round(float(ma_coeff), 8),
            intercept=round(float(intercept), 8),
            residual_std=round(residual_std, 8),
            n_observations=len(history),
            aic=round(aic, 4),
        )

    @staticmethod
    def _ols_fit(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
        """
        Ordinary least squares fit: y = coeff * x + intercept.

        Args:
            x: Independent variable array.
            y: Dependent variable array.

        Returns:
            Tuple of (coefficient, intercept).
        """
        n = len(x)
        if n == 0:
            return 0.0, 0.0

        mean_x = float(np.mean(x))
        mean_y = float(np.mean(y))

        ss_xx = float(np.sum((x - mean_x) ** 2))
        ss_xy = float(np.sum((x - mean_x) * (y - mean_y)))

        if abs(ss_xx) < 1e-15:
            return 0.0, mean_y

        coeff = ss_xy / ss_xx
        intercept = mean_y - coeff * mean_x
        return float(coeff), float(intercept)

    def _compute_residuals(self, diff_series: np.ndarray,
                           model: ARIMAResult) -> np.ndarray:
        """
        Compute residuals from a fitted ARIMA model on the differenced series.

        Args:
            diff_series: First-differenced time series.
            model: Fitted ARIMA model parameters.

        Returns:
            Array of residuals.
        """
        n = len(diff_series)
        residuals = np.zeros(n)
        for t in range(1, n):
            predicted = (model.intercept
                         + model.ar_coeff * diff_series[t - 1]
                         + model.ma_coeff * residuals[t - 1])
            residuals[t] = diff_series[t] - predicted
        return residuals

    def _inverse_difference(self, last_original: float,
                            diff_forecasts: List[float]) -> List[float]:
        """
        Convert differenced forecasts back to original scale.

        Applies cumulative summation starting from the last observed value:
          y_hat[t+h] = y[t] + sum(diff_hat[1..h])

        Args:
            last_original: Last observed value in the original (undifferenced) series.
            diff_forecasts: List of forecasted differences.

        Returns:
            List of forecasted values in original scale.
        """
        result = []
        cumsum = last_original
        for d in diff_forecasts:
            cumsum += d
            result.append(cumsum)
        return result

    def _linear_extrapolation(self, metric_name: str, history: List[float],
                              steps_ahead: int) -> ForecastResult:
        """
        Fallback linear extrapolation when history is too short for ARIMA.

        Fits y = slope * t + intercept via least squares and projects forward.

        Args:
            metric_name: Name of the metric.
            history: Short history (< 10 points).
            steps_ahead: Number of steps to forecast.

        Returns:
            ForecastResult with method="linear".
        """
        n = len(history)
        if n == 0:
            return ForecastResult(
                metric_name=metric_name,
                model=ARIMAResult(0.0, 0.0, 0.0, 0.0, 0),
                forecasts=[],
                method="linear",
                history_length=0,
            )

        if n == 1:
            # Constant forecast
            val = history[0]
            forecasts = [
                ForecastPoint(step=s, value=round(val, 6),
                              lower_80=round(val, 6), upper_80=round(val, 6),
                              lower_95=round(val, 6), upper_95=round(val, 6))
                for s in range(1, steps_ahead + 1)
            ]
            return ForecastResult(
                metric_name=metric_name,
                model=ARIMAResult(0.0, 0.0, val, 0.0, 1),
                forecasts=forecasts,
                method="linear",
                history_length=1,
            )

        # Fit linear regression: y = slope * t + intercept
        t = np.arange(n, dtype=np.float64)
        y = np.array(history, dtype=np.float64)
        slope, intercept = self._ols_fit(t, y)

        # Residual standard deviation for confidence intervals
        y_hat = intercept + slope * t
        residuals = y - y_hat
        residual_std = float(np.std(residuals)) if n > 2 else abs(slope) * 0.1

        forecasts: List[ForecastPoint] = []
        for step in range(1, steps_ahead + 1):
            t_future = n - 1 + step
            forecast_value = intercept + slope * t_future
            # Confidence intervals grow with distance from data
            step_std = residual_std * math.sqrt(1.0 + step / n)

            forecasts.append(ForecastPoint(
                step=step,
                value=round(forecast_value, 6),
                lower_80=round(forecast_value - 1.282 * step_std, 6),
                upper_80=round(forecast_value + 1.282 * step_std, 6),
                lower_95=round(forecast_value - 1.960 * step_std, 6),
                upper_95=round(forecast_value + 1.960 * step_std, 6),
            ))

        model = ARIMAResult(
            ar_coeff=0.0,
            ma_coeff=0.0,
            intercept=round(float(intercept), 8),
            residual_std=round(residual_std, 8),
            n_observations=n,
        )

        return ForecastResult(
            metric_name=metric_name,
            model=model,
            forecasts=forecasts,
            method="linear",
            history_length=n,
        )

    def get_predictions_summary(self) -> dict:
        """Get a comprehensive summary of prediction activity for chat exposure.

        Returns:
            Dict with pending predictions, validation stats, accuracy,
            recent outcomes, and per-metric breakdown.
        """
        # Per-metric prediction breakdown
        metric_stats: Dict[str, dict] = {}
        for pred in self._predictions:
            m = pred['metric']
            if m not in metric_stats:
                metric_stats[m] = {'pending': 0, 'total_predicted': 0}
            metric_stats[m]['pending'] += 1
            metric_stats[m]['total_predicted'] += 1

        # Recent outcomes
        recent_outcomes = self._verified_outcomes[-10:] if self._verified_outcomes else []

        # Per-metric accuracy from verified outcomes
        for outcome in self._verified_outcomes:
            m = outcome['metric']
            if m not in metric_stats:
                metric_stats[m] = {'pending': 0, 'total_predicted': 0}
            metric_stats[m]['total_predicted'] = metric_stats[m].get('total_predicted', 0) + 1

        return {
            'pending_predictions': len(self._predictions),
            'total_validated': self._predictions_validated,
            'total_correct': self._predictions_correct,
            'accuracy': round(self.get_accuracy(), 4),
            'accuracy_pct': f"{self.get_accuracy():.1%}",
            'verified_outcomes_count': len(self._verified_outcomes),
            'recent_outcomes': recent_outcomes,
            'per_metric': metric_stats,
            'tracked_metrics': list(self._series.keys()),
        }

    def save_to_db(self, persistence: 'AGIPersistence') -> bool:
        """Persist time series data to CockroachDB."""
        try:
            saved = 0
            for metric_name, data_points in self._series.items():
                # Only save recent data (last 500 points)
                recent = data_points[-500:]
                saved += persistence.save_time_series(metric_name, recent)
            if saved > 0:
                logger.info("Saved %d time series data points to DB", saved)
            return saved > 0
        except Exception as e:
            logger.warning("Failed to save time series: %s", e)
            return False

    def load_from_db(self, persistence: 'AGIPersistence') -> bool:
        """Load time series data from CockroachDB."""
        try:
            all_series = persistence.load_all_time_series(limit_per_metric=self._max_series_length)
            if not all_series:
                return False
            for metric_name, data_points in all_series.items():
                self._series[metric_name] = data_points
            logger.info("Loaded time series from DB: %d metrics", len(all_series))
            return True
        except Exception as e:
            logger.warning("Failed to load time series: %s", e)
            return False

    def get_stats(self) -> dict:
        return {
            'tracked_metrics': len(self._series),
            'total_data_points': sum(len(s) for s in self._series.values()),
            'pending_predictions': len(self._predictions),
            'predictions_validated': self._predictions_validated,
            'predictions_correct': self._predictions_correct,
            'accuracy': round(self.get_accuracy(), 4),
            'metrics': list(self._series.keys()),
            'verified_outcomes': len(self._verified_outcomes),
        }
