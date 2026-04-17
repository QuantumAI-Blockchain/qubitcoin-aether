"""
AI Persistence Layer — Save/Load AI State to CockroachDB

Provides save/load functions for all AI subsystems so that learned
weights, episodic memories, calibration data, and time series
survive node restarts.

Each subsystem calls save_*() periodically (e.g., every 100 blocks)
and load_*() on startup.
"""
import io
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Try to import torch for weight serialization
_HAS_TORCH = False
try:
    import torch
    _HAS_TORCH = True
except ImportError:
    pass


class AGIPersistence:
    """Persistence manager for AI subsystem state.

    Uses the node's existing DatabaseManager (SQLAlchemy + CockroachDB)
    to store and retrieve AI state via get_session().
    """

    def __init__(self, db_manager: object) -> None:
        """Initialize with a DatabaseManager instance.

        Args:
            db_manager: The node's DatabaseManager with get_session().
        """
        self._db = db_manager
        self._initialized = False
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Verify persistence tables exist (created by SQL migration)."""
        try:
            with self._db.get_session() as session:
                result = session.execute(
                    text("SELECT COUNT(*) FROM agi_neural_weights")
                ).fetchone()
                self._initialized = True
                logger.info("AI persistence tables verified")
        except Exception as e:
            logger.warning("AI persistence tables not ready (run 06_agi_persistence.sql): %s", e)

    # ========================================================================
    # Neural Reasoner Weights
    # ========================================================================

    def save_neural_weights(self, model: Any, model_name: str = 'neural_reasoner',
                            block_height: int = 0, metadata: Optional[dict] = None) -> bool:
        """Save PyTorch model weights to DB.

        Args:
            model: A torch.nn.Module or dict of numpy arrays.
            model_name: Identifier for the model.
            block_height: Current block height.
            metadata: Optional metadata dict (architecture info, etc.).

        Returns:
            True if saved successfully.
        """
        try:
            if _HAS_TORCH and hasattr(model, 'state_dict'):
                # Serialize PyTorch model
                buffer = io.BytesIO()
                torch.save(model.state_dict(), buffer)
                weights_blob = buffer.getvalue()
            elif isinstance(model, dict):
                # Serialize numpy arrays as JSON
                serializable = {}
                for k, v in model.items():
                    if hasattr(v, 'tolist'):
                        serializable[k] = v.tolist()
                    else:
                        serializable[k] = v
                weights_blob = json.dumps(serializable).encode('utf-8')
            else:
                logger.warning("Cannot serialize model of type %s", type(model))
                return False

            meta_json = json.dumps(metadata or {})

            with self._db.get_session() as session:
                # Get next version number
                result = session.execute(
                    text("SELECT COALESCE(MAX(version), 0) + 1 FROM agi_neural_weights "
                         "WHERE model_name = :model_name"),
                    {'model_name': model_name}
                ).fetchone()
                version = result[0] if result else 1

                session.execute(
                    text("INSERT INTO agi_neural_weights "
                         "(model_name, version, weights_blob, metadata, block_height) "
                         "VALUES (:model_name, :version, :weights_blob, :metadata, :block_height)"),
                    {
                        'model_name': model_name,
                        'version': version,
                        'weights_blob': weights_blob,
                        'metadata': meta_json,
                        'block_height': block_height,
                    }
                )
                session.commit()

            logger.info(
                "Saved neural weights: model=%s version=%d size=%d bytes block=%d",
                model_name, version, len(weights_blob), block_height
            )
            return True

        except Exception as e:
            logger.warning("Failed to save neural weights: %s", e)
            return False

    def load_neural_weights(self, model: Any = None,
                            model_name: str = 'neural_reasoner') -> Optional[Any]:
        """Load the latest neural weights from DB.

        Args:
            model: If a torch.nn.Module, loads state_dict into it.
                   If None, returns the raw state dict/numpy arrays.
            model_name: Identifier for the model.

        Returns:
            The loaded state dict, or None if not found.
        """
        try:
            with self._db.get_session() as session:
                result = session.execute(
                    text("SELECT weights_blob, metadata, version, block_height "
                         "FROM agi_neural_weights WHERE model_name = :model_name "
                         "ORDER BY version DESC LIMIT 1"),
                    {'model_name': model_name}
                ).fetchone()

            if not result:
                return None

            weights_blob, meta_str, version, block_height = result

            if _HAS_TORCH and model is not None and hasattr(model, 'load_state_dict'):
                buffer = io.BytesIO(bytes(weights_blob))
                state_dict = torch.load(buffer, weights_only=True)
                model.load_state_dict(state_dict)
                logger.info(
                    "Loaded neural weights into model: version=%d block=%d",
                    version, block_height
                )
                return state_dict
            else:
                # Try JSON deserialization (numpy fallback)
                try:
                    data = json.loads(bytes(weights_blob).decode('utf-8'))
                    logger.info(
                        "Loaded neural weights (numpy): version=%d block=%d",
                        version, block_height
                    )
                    return data
                except (json.JSONDecodeError, UnicodeDecodeError):
                    logger.warning("Cannot deserialize weights without PyTorch")
                    return None

        except Exception as e:
            logger.warning("Failed to load neural weights: %s", e)
            return None

    # ========================================================================
    # Episodic Memory
    # ========================================================================

    def save_episodes(self, episodes: List[Any], clear_existing: bool = False) -> int:
        """Save episodic memory episodes to DB.

        Args:
            episodes: List of Episode dataclass instances.
            clear_existing: If True, removes all existing episodes first.

        Returns:
            Number of episodes saved.
        """
        try:
            with self._db.get_session() as session:
                if clear_existing:
                    session.execute(text("DELETE FROM agi_episodes"))

                saved = 0
                for ep in episodes:
                    input_ids = getattr(ep, 'input_node_ids', [])
                    # Format as PostgreSQL array literal
                    input_ids_str = '{' + ','.join(str(i) for i in input_ids) + '}'
                    session.execute(
                        text("INSERT INTO agi_episodes "
                             "(block_height, input_node_ids, reasoning_strategy, "
                             "conclusion_node_id, success, confidence, replay_count) "
                             "VALUES (:block_height, :input_node_ids, :strategy, "
                             ":conclusion_id, :success, :confidence, :replay_count) "
                             "ON CONFLICT DO NOTHING"),
                        {
                            'block_height': ep.block_height,
                            'input_node_ids': input_ids_str,
                            'strategy': ep.reasoning_strategy,
                            'conclusion_id': ep.conclusion_node_id,
                            'success': ep.success,
                            'confidence': ep.confidence,
                            'replay_count': ep.replay_count,
                        }
                    )
                    saved += 1

                session.commit()

            if saved > 0:
                logger.info("Saved %d episodic memories to DB", saved)
            return saved

        except Exception as e:
            logger.warning("Failed to save episodes: %s", e)
            return 0

    def load_episodes(self, limit: int = 1000) -> List[dict]:
        """Load episodic memories from DB.

        Returns:
            List of episode dicts (caller converts to Episode dataclass).
        """
        try:
            with self._db.get_session() as session:
                result = session.execute(
                    text("SELECT episode_id, block_height, input_node_ids, "
                         "reasoning_strategy, conclusion_node_id, success, "
                         "confidence, replay_count, created_at "
                         "FROM agi_episodes ORDER BY block_height DESC LIMIT :lim"),
                    {'lim': limit}
                ).fetchall()

            if not result:
                return []

            episodes = []
            for row in result:
                episodes.append({
                    'episode_id': row[0],
                    'block_height': row[1],
                    'input_node_ids': list(row[2]) if row[2] else [],
                    'reasoning_strategy': row[3],
                    'conclusion_node_id': row[4],
                    'success': row[5],
                    'confidence': row[6],
                    'replay_count': row[7],
                    'timestamp': row[8].timestamp() if row[8] else time.time(),
                })

            logger.info("Loaded %d episodic memories from DB", len(episodes))
            return episodes

        except Exception as e:
            logger.warning("Failed to load episodes: %s", e)
            return []

    # ========================================================================
    # Self-Improvement Domain Weights
    # ========================================================================

    def save_domain_weights(self, domain_weights: Dict[str, Dict[str, float]],
                            block_height: int = 0) -> bool:
        """Save the self-improvement domain weight matrix.

        Args:
            domain_weights: domain -> {strategy -> weight} mapping.
            block_height: Current block height.

        Returns:
            True if saved successfully.
        """
        try:
            with self._db.get_session() as session:
                for domain, strategies in domain_weights.items():
                    for strategy, weight in strategies.items():
                        session.execute(
                            text("UPSERT INTO agi_domain_weights "
                                 "(domain, strategy, weight, block_height, updated_at) "
                                 "VALUES (:domain, :strategy, :weight, :block_height, now())"),
                            {
                                'domain': domain,
                                'strategy': strategy,
                                'weight': weight,
                                'block_height': block_height,
                            }
                        )
                session.commit()

            logger.info(
                "Saved domain weights: %d domains at block %d",
                len(domain_weights), block_height
            )
            return True

        except Exception as e:
            logger.warning("Failed to save domain weights: %s", e)
            return False

    def load_domain_weights(self) -> Dict[str, Dict[str, float]]:
        """Load the self-improvement domain weight matrix.

        Returns:
            domain -> {strategy -> weight} mapping.
        """
        try:
            with self._db.get_session() as session:
                result = session.execute(
                    text("SELECT domain, strategy, weight FROM agi_domain_weights")
                ).fetchall()

            if not result:
                return {}

            weights: Dict[str, Dict[str, float]] = {}
            for domain, strategy, weight in result:
                if domain not in weights:
                    weights[domain] = {}
                weights[domain][strategy] = weight

            logger.info("Loaded domain weights: %d domains", len(weights))
            return weights

        except Exception as e:
            logger.warning("Failed to load domain weights: %s", e)
            return {}

    # ========================================================================
    # Metacognition State
    # ========================================================================

    def save_metacognition(self, metacog: Any, block_height: int = 0) -> bool:
        """Save metacognition state to DB.

        Args:
            metacog: MetacognitiveLoop instance.
            block_height: Current block height.

        Returns:
            True if saved.
        """
        try:
            with self._db.get_session() as session:
                session.execute(
                    text("INSERT INTO agi_metacognition "
                         "(strategy_stats, domain_stats, confidence_bins, "
                         "strategy_weights, total_evaluations, total_correct, block_height) "
                         "VALUES (:strategy_stats, :domain_stats, :confidence_bins, "
                         ":strategy_weights, :total_evaluations, :total_correct, :block_height)"),
                    {
                        'strategy_stats': json.dumps(metacog._strategy_stats),
                        'domain_stats': json.dumps(metacog._domain_stats),
                        'confidence_bins': json.dumps({str(k): v for k, v in metacog._confidence_bins.items()}),
                        'strategy_weights': json.dumps(metacog._strategy_weights),
                        'total_evaluations': metacog._total_evaluations,
                        'total_correct': metacog._total_correct,
                        'block_height': block_height,
                    }
                )
                session.commit()

            logger.info(
                "Saved metacognition state: %d evaluations at block %d",
                metacog._total_evaluations, block_height
            )
            return True

        except Exception as e:
            logger.warning("Failed to save metacognition: %s", e)
            return False

    def load_metacognition(self, metacog: Any) -> bool:
        """Load metacognition state from DB into existing instance.

        Args:
            metacog: MetacognitiveLoop instance to populate.

        Returns:
            True if loaded.
        """
        try:
            with self._db.get_session() as session:
                result = session.execute(
                    text("SELECT strategy_stats, domain_stats, confidence_bins, "
                         "strategy_weights, total_evaluations, total_correct "
                         "FROM agi_metacognition ORDER BY created_at DESC LIMIT 1")
                ).fetchone()

            if not result:
                return False

            def _parse_jsonb(val: Any) -> dict:
                """Parse JSONB — may be dict (already parsed) or str."""
                if not val:
                    return {}
                if isinstance(val, dict):
                    return val
                return json.loads(val)

            metacog._strategy_stats = _parse_jsonb(result[0])
            metacog._domain_stats = _parse_jsonb(result[1])
            bins_raw = _parse_jsonb(result[2])
            metacog._confidence_bins = {int(k): v for k, v in bins_raw.items()}
            metacog._strategy_weights = _parse_jsonb(result[3])
            metacog._total_evaluations = result[4] or 0
            metacog._total_correct = result[5] or 0

            # Clear stale confidence bins so ECE builds fresh from new
            # evaluations rather than being skewed by old calibration data.
            # Strategy stats and total counts are preserved for weight adaptation.
            metacog._confidence_bins = {}

            # Reconstruct adaptive temperature from loaded bin data
            if hasattr(metacog, '_update_temperature'):
                metacog._update_temperature()

            logger.info(
                "Loaded metacognition state: %d evaluations",
                metacog._total_evaluations
            )
            return True

        except Exception as e:
            logger.warning("Failed to load metacognition: %s", e)
            return False

    # ========================================================================
    # Temporal Time Series
    # ========================================================================

    def save_time_series(self, metric_name: str,
                         data_points: List[Tuple[int, float]]) -> int:
        """Save time series data points to DB.

        Args:
            metric_name: Name of the metric.
            data_points: List of (block_height, value) tuples.

        Returns:
            Number of points saved.
        """
        try:
            with self._db.get_session() as session:
                saved = 0
                for block_height, value in data_points:
                    session.execute(
                        text("INSERT INTO agi_time_series "
                             "(metric_name, block_height, value) "
                             "VALUES (:metric_name, :block_height, :value) "
                             "ON CONFLICT DO NOTHING"),
                        {
                            'metric_name': metric_name,
                            'block_height': block_height,
                            'value': value,
                        }
                    )
                    saved += 1
                session.commit()

            if saved > 0:
                logger.debug("Saved %d time series points for %s", saved, metric_name)
            return saved

        except Exception as e:
            logger.warning("Failed to save time series: %s", e)
            return 0

    def load_time_series(self, metric_name: str,
                         limit: int = 2000) -> List[Tuple[int, float]]:
        """Load time series data from DB.

        Args:
            metric_name: Name of the metric.
            limit: Maximum number of data points.

        Returns:
            List of (block_height, value) tuples.
        """
        try:
            with self._db.get_session() as session:
                result = session.execute(
                    text("SELECT block_height, value FROM agi_time_series "
                         "WHERE metric_name = :metric_name "
                         "ORDER BY block_height ASC LIMIT :lim"),
                    {'metric_name': metric_name, 'lim': limit}
                ).fetchall()

            if not result:
                return []

            data = [(row[0], row[1]) for row in result]
            logger.debug("Loaded %d time series points for %s", len(data), metric_name)
            return data

        except Exception as e:
            logger.warning("Failed to load time series: %s", e)
            return []

    def load_all_time_series(self, limit_per_metric: int = 2000) -> Dict[str, List[Tuple[int, float]]]:
        """Load all time series metrics from DB.

        Returns:
            Dict mapping metric_name -> [(block_height, value), ...].
        """
        try:
            with self._db.get_session() as session:
                result = session.execute(
                    text("SELECT DISTINCT metric_name FROM agi_time_series")
                ).fetchall()

            if not result:
                return {}

            all_series: Dict[str, List[Tuple[int, float]]] = {}
            for row in result:
                metric_name = row[0]
                all_series[metric_name] = self.load_time_series(
                    metric_name, limit_per_metric
                )

            logger.info("Loaded time series for %d metrics", len(all_series))
            return all_series

        except Exception as e:
            logger.warning("Failed to load all time series: %s", e)
            return {}
