"""
Temporal Reasoning & Prediction Engine — Time-Aware Knowledge Processing

Tracks time-series data derived from the knowledge graph and block stream,
detects trends and anomalies, and generates prediction nodes.

Improvement #6: Without temporal reasoning, the system treats all knowledge
as a flat snapshot.  This module adds the ability to detect trends
("difficulty is rising"), anomalies ("transaction surge at block X"),
and make predictions that can be verified later.
"""
import math
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


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
        Detect anomalies using z-score deviation.

        Returns anomaly info if the latest value is > z_threshold
        standard deviations from the mean.
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

        latest = values[-1]
        z_score = (latest - mean) / std

        if abs(z_score) < z_threshold:
            return None

        return {
            'metric': metric,
            'z_score': round(z_score, 4),
            'value': latest,
            'mean': round(mean, 6),
            'std': round(std, 6),
            'direction': 'high' if z_score > 0 else 'low',
            'block': data[-1][0],
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

    def get_stats(self) -> dict:
        return {
            'tracked_metrics': len(self._series),
            'total_data_points': sum(len(s) for s in self._series.values()),
            'pending_predictions': len(self._predictions),
            'predictions_validated': self._predictions_validated,
            'predictions_correct': self._predictions_correct,
            'accuracy': round(self.get_accuracy(), 4),
            'metrics': list(self._series.keys()),
        }
