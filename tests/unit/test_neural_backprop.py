"""
Tests for neural reasoner backpropagation (Item A13).

Verifies:
  - has_pytorch attribute is set correctly
  - training_mode property returns correct value
  - _train_backprop method works with PyTorch
  - Evolutionary fallback when PyTorch is unavailable
  - Training statistics tracking
  - Backprop weight sync to GATLayer
"""

import math
from unittest.mock import patch, MagicMock
from typing import Dict, List

import pytest


# ============================================================================
# Utility: check if PyTorch is available (used in skipif decorators)
# ============================================================================

def _torch_available() -> bool:
    try:
        import torch
        return True
    except ImportError:
        return False


# ============================================================================
# Helpers
# ============================================================================

def _make_features(n_nodes: int = 5, dim: int = 8) -> Dict[int, List[float]]:
    """Create synthetic node features for testing."""
    import random
    random.seed(42)
    return {
        i: [random.gauss(0, 1) for _ in range(dim)]
        for i in range(n_nodes)
    }


def _make_adj(n_nodes: int = 5) -> Dict[int, List[int]]:
    """Create a simple chain adjacency for testing."""
    adj: Dict[int, List[int]] = {i: [] for i in range(n_nodes)}
    for i in range(n_nodes - 1):
        adj[i].append(i + 1)
        adj[i + 1].append(i)
    return adj


def _make_training_samples(n_samples: int = 40, dim: int = 8) -> List[dict]:
    """Create synthetic training samples."""
    import random
    random.seed(99)
    samples = []
    for _ in range(n_samples):
        feats = {
            j: [random.gauss(0, 1) for _ in range(dim)]
            for j in range(3)
        }
        samples.append({
            'node_features': feats,
            'edge_index': {0: [1], 1: [0, 2], 2: [1]},
            'target_confidence': random.random(),
            'actual_outcome': 1.0 if random.random() > 0.5 else 0.0,
        })
    return samples


# ============================================================================
# Tests: has_pytorch attribute
# ============================================================================

class TestHasPytorch:
    """Tests for the has_pytorch attribute and training_mode property."""

    def test_has_pytorch_reflects_torch_availability(self):
        """has_pytorch should reflect actual torch availability."""
        from qubitcoin.aether.neural_reasoner import GATReasoner, _HAS_TORCH
        r = GATReasoner()
        assert r.has_pytorch == _HAS_TORCH

    def test_training_mode_with_torch(self):
        """training_mode should be 'backprop' when PyTorch is available."""
        from qubitcoin.aether.neural_reasoner import GATReasoner
        r = GATReasoner()
        r.has_pytorch = True
        assert r.training_mode == 'backprop'

    def test_training_mode_without_torch(self):
        """training_mode should be 'evolutionary' when PyTorch is unavailable."""
        from qubitcoin.aether.neural_reasoner import GATReasoner
        r = GATReasoner()
        r.has_pytorch = False
        assert r.training_mode == 'evolutionary'

    def test_has_pytorch_is_bool(self):
        """has_pytorch should be a boolean type."""
        from qubitcoin.aether.neural_reasoner import GATReasoner
        r = GATReasoner()
        assert isinstance(r.has_pytorch, bool)


# ============================================================================
# Tests: Evolutionary fallback
# ============================================================================

class TestEvolutionaryFallback:
    """Tests for evolutionary training when PyTorch is unavailable."""

    def test_evolutionary_path_when_no_pytorch(self):
        """record_outcome should use evolutionary strategy when has_pytorch=False."""
        from qubitcoin.aether.neural_reasoner import GATReasoner, GATLayer
        r = GATReasoner(hidden_dim=8)
        r.has_pytorch = False

        # Initialize layers manually
        r._layer1 = GATLayer(4, 8)
        r._layer2 = GATLayer(8, 8)
        r._initialized = True

        # Store initial weights
        w_before = r._layer1.W[0][0]

        # Fill a sample into last_embeddings for the buffer path
        r._last_embeddings = {
            'features': _make_features(3, 4),
            'adj': _make_adj(3),
            'confidence': 0.5,
            'query_node_ids': [0],
        }

        r.record_outcome(True)

        # Weights should have changed via evolutionary perturbation
        assert r._layer1.W[0][0] != w_before
        assert r._evolutionary_steps == 1

    def test_evolutionary_increments_counter(self):
        """Each evolutionary step should increment the counter."""
        from qubitcoin.aether.neural_reasoner import GATReasoner, GATLayer
        r = GATReasoner(hidden_dim=4)
        r.has_pytorch = False
        r._layer1 = GATLayer(4, 4)
        r._layer2 = GATLayer(4, 4)
        r._initialized = True

        r._last_embeddings = {
            'features': _make_features(2, 4),
            'adj': {0: [1], 1: [0]},
            'confidence': 0.5,
            'query_node_ids': [0],
        }

        for _ in range(5):
            r.record_outcome(True)

        assert r._evolutionary_steps == 5
        assert r._backprop_steps == 0


# ============================================================================
# Tests: Backpropagation path
# ============================================================================

class TestBackpropTraining:
    """Tests for backpropagation training when PyTorch is available."""

    def test_train_backprop_returns_negative_without_layers(self):
        """_train_backprop should return -1.0 if layers are not initialized."""
        from qubitcoin.aether.neural_reasoner import GATReasoner
        r = GATReasoner()
        result = r._train_backprop([{'node_features': {0: [1.0]}, 'actual_outcome': 1.0}])
        assert result == -1.0

    def test_train_backprop_returns_negative_on_empty_data(self):
        """_train_backprop should return -1.0 on empty training data."""
        from qubitcoin.aether.neural_reasoner import GATReasoner, GATLayer
        r = GATReasoner(hidden_dim=4)
        r._layer1 = GATLayer(4, 4)
        r._layer2 = GATLayer(4, 4)
        r._initialized = True
        result = r._train_backprop([])
        assert result == -1.0

    @pytest.mark.skipif(
        not _torch_available(),
        reason="PyTorch not installed"
    )
    def test_train_backprop_produces_valid_loss(self):
        """_train_backprop should produce a non-negative loss value."""
        from qubitcoin.aether.neural_reasoner import GATReasoner, GATLayer
        r = GATReasoner(hidden_dim=8)
        r._layer1 = GATLayer(8, 8)
        r._layer2 = GATLayer(8, 8)
        r._initialized = True

        samples = _make_training_samples(10, 8)
        loss = r._train_backprop(samples)
        assert loss >= 0.0
        assert r._backprop_steps == 1

    @pytest.mark.skipif(
        not _torch_available(),
        reason="PyTorch not installed"
    )
    def test_train_backprop_updates_gatlayer_weights(self):
        """_train_backprop should copy updated weights back to GATLayers."""
        from qubitcoin.aether.neural_reasoner import GATReasoner, GATLayer
        r = GATReasoner(hidden_dim=8)
        r._layer1 = GATLayer(8, 8)
        r._layer2 = GATLayer(8, 8)
        r._initialized = True

        w1_before = [row[:] for row in r._layer1.W]

        samples = _make_training_samples(10, 8)
        loss = r._train_backprop(samples)

        assert loss >= 0.0
        # At least some weights should have changed
        changed = False
        for i in range(r._layer1.in_dim):
            for j in range(r._layer1.out_dim):
                if abs(r._layer1.W[i][j] - w1_before[i][j]) > 1e-10:
                    changed = True
                    break
            if changed:
                break
        assert changed, "GATLayer weights should have been updated by backprop"

    @pytest.mark.skipif(
        not _torch_available(),
        reason="PyTorch not installed"
    )
    def test_record_outcome_triggers_backprop_when_buffer_full(self):
        """record_outcome should trigger backprop once buffer reaches batch size."""
        from qubitcoin.aether.neural_reasoner import GATReasoner, GATLayer
        r = GATReasoner(hidden_dim=8)
        r.TRAINING_BATCH_SIZE = 4  # Small batch for fast test
        r.has_pytorch = True
        r._layer1 = GATLayer(8, 8)
        r._layer2 = GATLayer(8, 8)
        r._initialized = True

        # Fill buffer with samples via record_outcome
        for i in range(5):
            r._last_embeddings = {
                'features': _make_features(3, 8),
                'adj': _make_adj(3),
                'confidence': 0.5,
                'query_node_ids': [0],
            }
            r.record_outcome(i % 2 == 0)

        # Should have triggered backprop at least once (5 samples, batch_size=4)
        assert r._backprop_steps >= 1

    @pytest.mark.skipif(
        not _torch_available(),
        reason="PyTorch not installed"
    )
    def test_multiple_backprop_steps_accumulate(self):
        """Multiple backprop steps should accumulate loss statistics."""
        from qubitcoin.aether.neural_reasoner import GATReasoner, GATLayer
        r = GATReasoner(hidden_dim=8)
        r._layer1 = GATLayer(8, 8)
        r._layer2 = GATLayer(8, 8)
        r._initialized = True

        for _ in range(3):
            samples = _make_training_samples(10, 8)
            loss = r._train_backprop(samples)
            assert loss >= 0.0

        assert r._backprop_steps == 3
        assert r._backprop_total_loss > 0.0


# ============================================================================
# Tests: Statistics tracking
# ============================================================================

class TestTrainingStats:
    """Tests for training statistics in get_stats()."""

    def test_stats_include_training_mode(self):
        """get_stats should include training_mode field."""
        from qubitcoin.aether.neural_reasoner import GATReasoner
        r = GATReasoner()
        stats = r.get_stats()
        assert 'training_mode' in stats
        assert stats['training_mode'] in ('backprop', 'evolutionary')

    def test_stats_include_has_pytorch(self):
        """get_stats should include has_pytorch field."""
        from qubitcoin.aether.neural_reasoner import GATReasoner
        r = GATReasoner()
        stats = r.get_stats()
        assert 'has_pytorch' in stats
        assert isinstance(stats['has_pytorch'], bool)

    def test_stats_include_backprop_counters(self):
        """get_stats should include backprop and evolutionary step counters."""
        from qubitcoin.aether.neural_reasoner import GATReasoner
        r = GATReasoner()
        stats = r.get_stats()
        assert 'backprop_steps' in stats
        assert 'evolutionary_steps' in stats
        assert 'backprop_avg_loss' in stats
        assert stats['backprop_steps'] == 0
        assert stats['evolutionary_steps'] == 0
        assert stats['backprop_avg_loss'] == 0.0

    def test_stats_avg_loss_after_training(self):
        """backprop_avg_loss should reflect actual training losses."""
        from qubitcoin.aether.neural_reasoner import GATReasoner
        r = GATReasoner()
        # Simulate training stats
        r._backprop_steps = 10
        r._backprop_total_loss = 5.0
        stats = r.get_stats()
        assert stats['backprop_avg_loss'] == 0.5
