//! PyO3 bindings for the GAT neural reasoner.
//!
//! Exposes `RustGATReasoner` as a Python class with methods for reasoning,
//! training, recording outcomes, saving/loading weights, and querying stats.

use std::fs;
use std::path::Path;

use nalgebra::DMatrix;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::neural::trainer::{GATTrainer, TrainerConfig};
use crate::neural::GATReasoner;

/// Python-accessible GAT reasoning network.
///
/// Wraps a `GATReasoner` + `GATTrainer` with a convenient Python API.
///
/// Example (Python):
/// ```python
/// from aether_core import RustGATReasoner
/// gat = RustGATReasoner(input_dim=64, hidden_dim=64, output_dim=32, n_heads=4, n_layers=2)
/// result = gat.reason(node_features=[[0.1]*64, [0.2]*64], adjacency=[(0,1),(1,0)], query_nodes=[0])
/// gat.record_outcome(True)
/// loss = gat.train_step(16)
/// ```
#[pyclass]
pub struct RustGATReasoner {
    trainer: GATTrainer,
    input_dim: usize,
    hidden_dim: usize,
    output_dim: usize,
    n_heads: usize,
    n_layers: usize,
    /// Cache the last prediction context for record_outcome.
    last_features: Option<DMatrix<f64>>,
    last_adj: Option<Vec<(usize, usize)>>,
    last_query: Option<usize>,
}

#[pymethods]
impl RustGATReasoner {
    /// Create a new GAT reasoner.
    ///
    /// Args:
    ///     input_dim: Input feature dimension (default 64).
    ///     hidden_dim: Hidden dimension per head (default 64).
    ///     output_dim: Output dimension per head (default 32).
    ///     n_heads: Number of attention heads (default 4).
    ///     n_layers: Number of GAT layers (default 2).
    #[new]
    #[pyo3(signature = (input_dim=64, hidden_dim=64, output_dim=32, n_heads=4, n_layers=2))]
    fn new(
        input_dim: usize,
        hidden_dim: usize,
        output_dim: usize,
        n_heads: usize,
        n_layers: usize,
    ) -> PyResult<Self> {
        if input_dim == 0 || hidden_dim == 0 || output_dim == 0 {
            return Err(PyValueError::new_err("Dimensions must be > 0"));
        }
        if n_heads == 0 {
            return Err(PyValueError::new_err("n_heads must be > 0"));
        }
        if n_layers == 0 {
            return Err(PyValueError::new_err("n_layers must be > 0"));
        }

        let model = GATReasoner::new(input_dim, hidden_dim, output_dim, n_heads, n_layers, 0.3);
        let config = TrainerConfig {
            lr: 0.01,
            momentum: 0.9,
            weight_decay: 1e-4,
            max_grad_norm: 1.0,
            buffer_capacity: 1024,
            ema_alpha: 0.05,
        };
        let trainer = GATTrainer::new(model, config, input_dim);

        Ok(RustGATReasoner {
            trainer,
            input_dim,
            hidden_dim,
            output_dim,
            n_heads,
            n_layers,
            last_features: None,
            last_adj: None,
            last_query: None,
        })
    }

    /// Run reasoning inference over a graph.
    ///
    /// Args:
    ///     node_features: List of lists — [[f64; input_dim]; n_nodes].
    ///     adjacency: List of (src, dst) tuples.
    ///     query_nodes: List of node indices to query (predictions returned for each).
    ///
    /// Returns:
    ///     dict with keys: "predictions" (list of floats), "confidence" (float),
    ///     "n_nodes" (int), "n_edges" (int).
    #[pyo3(signature = (node_features, adjacency, query_nodes))]
    fn reason<'py>(
        &mut self,
        py: Python<'py>,
        node_features: Vec<Vec<f64>>,
        adjacency: Vec<(usize, usize)>,
        query_nodes: Vec<usize>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let n_nodes = node_features.len();
        if n_nodes == 0 {
            return Err(PyValueError::new_err("node_features cannot be empty"));
        }
        let feat_dim = node_features[0].len();
        if feat_dim != self.input_dim {
            return Err(PyValueError::new_err(format!(
                "Feature dim {} != expected input_dim {}",
                feat_dim, self.input_dim
            )));
        }

        // Flatten to row-major for DMatrix.
        let flat: Vec<f64> = node_features.iter().flatten().copied().collect();
        let features = DMatrix::from_row_slice(n_nodes, self.input_dim, &flat);

        let mut predictions = Vec::with_capacity(query_nodes.len());
        for &qn in &query_nodes {
            let prob = self.trainer.predict(&flat, n_nodes, &adjacency, qn);
            predictions.push(prob);
        }

        // Cache for record_outcome.
        let primary_query = query_nodes.first().copied().unwrap_or(0);
        self.last_features = Some(features);
        self.last_adj = Some(adjacency.clone());
        self.last_query = Some(primary_query);

        // Compute confidence as mean prediction closeness to 0 or 1.
        let confidence = if predictions.is_empty() {
            0.5
        } else {
            predictions.iter().map(|p| 2.0 * (p - 0.5).abs()).sum::<f64>()
                / predictions.len() as f64
        };

        let dict = PyDict::new(py);
        dict.set_item("predictions", predictions)?;
        dict.set_item("confidence", confidence)?;
        dict.set_item("n_nodes", n_nodes)?;
        dict.set_item("n_edges", adjacency.len())?;

        Ok(dict)
    }

    /// Record whether the last prediction was correct.
    ///
    /// This feeds the training buffer. If context from a previous `reason()` call
    /// is available, it uses that; otherwise generates a synthetic sample.
    #[pyo3(signature = (prediction_correct))]
    fn record_outcome(&mut self, prediction_correct: bool) {
        if let (Some(features), Some(adj), Some(query)) =
            (self.last_features.take(), self.last_adj.take(), self.last_query.take())
        {
            self.trainer
                .record_outcome_with_context(features, adj, query, prediction_correct);
        } else {
            self.trainer.record_outcome(prediction_correct);
        }
    }

    /// Run one training step over a mini-batch from the ring buffer.
    ///
    /// Args:
    ///     batch_size: Number of samples per step (default 16).
    ///
    /// Returns:
    ///     Average BCE loss, or -1.0 if buffer is empty.
    #[pyo3(signature = (batch_size=16))]
    fn train_step(&self, batch_size: usize) -> f64 {
        self.trainer.train_step(batch_size).unwrap_or(-1.0)
    }

    /// Get training statistics.
    ///
    /// Returns:
    ///     dict with keys: "total_steps", "total_samples", "total_correct",
    ///     "recent_loss", "recent_accuracy", "ema_loss", "ema_accuracy",
    ///     "buffer_size", "input_dim", "hidden_dim", "output_dim",
    ///     "n_heads", "n_layers".
    fn get_stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let stats = self.trainer.get_stats();
        let dict = PyDict::new(py);
        dict.set_item("total_steps", stats.total_steps)?;
        dict.set_item("total_samples", stats.total_samples)?;
        dict.set_item("total_correct", stats.total_correct)?;
        dict.set_item("recent_loss", stats.recent_loss)?;
        dict.set_item("recent_accuracy", stats.recent_accuracy)?;
        dict.set_item("ema_loss", stats.ema_loss)?;
        dict.set_item("ema_accuracy", stats.ema_accuracy)?;
        dict.set_item("buffer_size", self.trainer.buffer_size())?;
        dict.set_item("input_dim", self.input_dim)?;
        dict.set_item("hidden_dim", self.hidden_dim)?;
        dict.set_item("output_dim", self.output_dim)?;
        dict.set_item("n_heads", self.n_heads)?;
        dict.set_item("n_layers", self.n_layers)?;
        Ok(dict)
    }

    /// Save model weights to a JSON file.
    ///
    /// Args:
    ///     path: File path to save to.
    #[pyo3(signature = (path))]
    fn save_weights(&self, path: &str) -> PyResult<()> {
        let data = self
            .trainer
            .save_weights()
            .map_err(|e| PyValueError::new_err(e))?;
        fs::write(Path::new(path), data)
            .map_err(|e| PyValueError::new_err(format!("IO error: {}", e)))?;
        log::info!("GAT weights saved to {}", path);
        Ok(())
    }

    /// Load model weights from a JSON file.
    ///
    /// Args:
    ///     path: File path to load from.
    #[pyo3(signature = (path))]
    fn load_weights(&self, path: &str) -> PyResult<()> {
        let data = fs::read(Path::new(path))
            .map_err(|e| PyValueError::new_err(format!("IO error: {}", e)))?;
        self.trainer
            .load_weights(&data)
            .map_err(|e| PyValueError::new_err(e))?;
        log::info!("GAT weights loaded from {}", path);
        Ok(())
    }

    /// String representation.
    fn __repr__(&self) -> String {
        format!(
            "RustGATReasoner(input_dim={}, hidden_dim={}, output_dim={}, n_heads={}, n_layers={}, buffer={})",
            self.input_dim, self.hidden_dim, self.output_dim, self.n_heads, self.n_layers,
            self.trainer.buffer_size()
        )
    }
}
