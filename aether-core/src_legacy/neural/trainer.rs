//! GATTrainer — Training loop with ring buffer, BCE loss, SGD optimizer.

use crate::neural::GATReasoner;
use nalgebra::DMatrix;
use parking_lot::Mutex;
use rand::seq::SliceRandom;
use rand::Rng;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Training sample
// ---------------------------------------------------------------------------

/// A single training sample stored in the ring buffer.
#[derive(Clone)]
struct TrainingSample {
    /// Node features: (n_nodes, input_dim).
    features: DMatrix<f64>,
    /// Adjacency edge list.
    adj: Vec<(usize, usize)>,
    /// Query node index.
    query_node: usize,
    /// Ground truth label (1.0 = correct prediction, 0.0 = incorrect).
    label: f64,
}

// ---------------------------------------------------------------------------
// Ring buffer
// ---------------------------------------------------------------------------

/// Fixed-capacity ring buffer for training samples.
struct RingBuffer {
    buffer: Vec<TrainingSample>,
    capacity: usize,
    write_pos: usize,
    count: usize,
}

impl RingBuffer {
    fn new(capacity: usize) -> Self {
        RingBuffer {
            buffer: Vec::with_capacity(capacity),
            capacity,
            write_pos: 0,
            count: 0,
        }
    }

    fn push(&mut self, sample: TrainingSample) {
        if self.buffer.len() < self.capacity {
            self.buffer.push(sample);
        } else {
            self.buffer[self.write_pos] = sample;
        }
        self.write_pos = (self.write_pos + 1) % self.capacity;
        self.count = (self.count + 1).min(self.capacity);
    }

    fn len(&self) -> usize {
        self.count
    }

    fn sample_batch(&self, batch_size: usize) -> Vec<&TrainingSample> {
        let mut rng = rand::thread_rng();
        let actual_size = batch_size.min(self.count);
        let mut indices: Vec<usize> = (0..self.count).collect();
        indices.shuffle(&mut rng);
        indices.truncate(actual_size);
        indices.iter().map(|&i| &self.buffer[i]).collect()
    }
}

// ---------------------------------------------------------------------------
// Training statistics
// ---------------------------------------------------------------------------

/// Training statistics tracked across the lifetime of the trainer.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TrainingStats {
    pub total_steps: u64,
    pub total_samples: u64,
    pub total_correct: u64,
    pub recent_loss: f64,
    pub recent_accuracy: f64,
    /// Exponential moving average of loss.
    pub ema_loss: f64,
    /// Exponential moving average of accuracy.
    pub ema_accuracy: f64,
}

impl Default for TrainingStats {
    fn default() -> Self {
        TrainingStats {
            total_steps: 0,
            total_samples: 0,
            total_correct: 0,
            recent_loss: 0.0,
            recent_accuracy: 0.5,
            ema_loss: 0.0,
            ema_accuracy: 0.5,
        }
    }
}

// ---------------------------------------------------------------------------
// GATTrainer
// ---------------------------------------------------------------------------

/// Hyperparameters for training.
#[derive(Clone, Debug)]
pub struct TrainerConfig {
    pub lr: f64,
    pub momentum: f64,
    pub weight_decay: f64,
    pub max_grad_norm: f64,
    pub buffer_capacity: usize,
    pub ema_alpha: f64,
}

impl Default for TrainerConfig {
    fn default() -> Self {
        TrainerConfig {
            lr: 0.01,
            momentum: 0.9,
            weight_decay: 1e-4,
            max_grad_norm: 1.0,
            buffer_capacity: 1024,
            ema_alpha: 0.05,
        }
    }
}

/// GATTrainer manages training of a GATReasoner.
///
/// Thread-safe: the model and buffer are behind a Mutex so `record_outcome`,
/// `train_step`, and `predict` can be called from different threads.
pub struct GATTrainer {
    model: Mutex<GATReasoner>,
    buffer: Mutex<RingBuffer>,
    config: TrainerConfig,
    stats: Mutex<TrainingStats>,
    /// Input dimension (needed to create dummy features for record_outcome).
    input_dim: usize,
}

impl GATTrainer {
    /// Create a new trainer wrapping a GATReasoner.
    pub fn new(model: GATReasoner, config: TrainerConfig, input_dim: usize) -> Self {
        let buffer_cap = config.buffer_capacity;
        GATTrainer {
            model: Mutex::new(model),
            buffer: Mutex::new(RingBuffer::new(buffer_cap)),
            config,
            stats: Mutex::new(TrainingStats::default()),
            input_dim,
        }
    }

    /// Record an outcome from the reasoning system.
    ///
    /// Creates a synthetic training sample from the last prediction context
    /// and adds it to the ring buffer.
    ///
    /// - `features`: Node features from the reasoning context.
    /// - `adj`: Adjacency from the reasoning context.
    /// - `query_node`: The query node index.
    /// - `prediction_correct`: Whether the prediction was correct.
    pub fn record_outcome_with_context(
        &self,
        features: DMatrix<f64>,
        adj: Vec<(usize, usize)>,
        query_node: usize,
        prediction_correct: bool,
    ) {
        let label = if prediction_correct { 1.0 } else { 0.0 };
        let sample = TrainingSample {
            features,
            adj,
            query_node,
            label,
        };
        self.buffer.lock().push(sample);

        let mut stats = self.stats.lock();
        stats.total_samples += 1;
        if prediction_correct {
            stats.total_correct += 1;
        }
    }

    /// Record a simple outcome (generates a small synthetic graph).
    ///
    /// This is the simple API: just pass whether the last prediction was correct.
    /// Internally generates a small random graph for training signal.
    pub fn record_outcome(&self, prediction_correct: bool) {
        let mut rng = rand::thread_rng();
        let n_nodes = rng.gen_range(3..8);
        let features = DMatrix::from_fn(n_nodes, self.input_dim, |_, _| {
            rng.gen_range(-1.0..1.0)
        });
        // Random sparse graph.
        let mut adj = Vec::new();
        for i in 0..n_nodes {
            adj.push((i, i)); // self-loop
            if i + 1 < n_nodes {
                adj.push((i, i + 1));
                adj.push((i + 1, i));
            }
            // Random extra edge.
            if rng.gen_bool(0.3) {
                let j = rng.gen_range(0..n_nodes);
                if j != i {
                    adj.push((i, j));
                }
            }
        }
        let query_node = rng.gen_range(0..n_nodes);
        self.record_outcome_with_context(features, adj, query_node, prediction_correct);
    }

    /// Run one training step over a mini-batch.
    ///
    /// Returns the average BCE loss over the batch, or None if the buffer is empty.
    pub fn train_step(&self, batch_size: usize) -> Option<f64> {
        let batch: Vec<TrainingSample>;
        {
            let buf = self.buffer.lock();
            if buf.len() == 0 {
                return None;
            }
            batch = buf.sample_batch(batch_size).into_iter().cloned().collect();
        }

        let actual_batch_size = batch.len();
        let mut total_loss = 0.0;

        let mut model = self.model.lock();

        for sample in &batch {
            // Forward pass (training mode = true for dropout).
            let (prob, cache) = model.forward(
                &sample.features,
                &sample.adj,
                sample.query_node,
                true,
            );

            // BCE loss: -[y * ln(p) + (1-y) * ln(1-p)]
            let eps = 1e-7;
            let p = prob.clamp(eps, 1.0 - eps);
            let loss = -(sample.label * p.ln() + (1.0 - sample.label) * (1.0 - p).ln());
            total_loss += loss;

            // Backward pass.
            let (layer_grads, cls_grad) = model.backward(
                sample.label,
                &cache,
                &sample.adj,
                sample.query_node,
            );

            // Apply gradients (per-sample SGD, effectively SGD with batch_size=1 per update).
            model.apply_gradients(
                layer_grads,
                &cls_grad,
                self.config.lr,
                self.config.weight_decay,
                self.config.max_grad_norm,
            );
        }

        let avg_loss = total_loss / actual_batch_size as f64;

        // Update stats.
        let mut stats = self.stats.lock();
        stats.total_steps += 1;
        stats.recent_loss = avg_loss;
        stats.ema_loss = stats.ema_loss * (1.0 - self.config.ema_alpha)
            + avg_loss * self.config.ema_alpha;
        if stats.total_samples > 0 {
            let acc = stats.total_correct as f64 / stats.total_samples as f64;
            stats.ema_accuracy = stats.ema_accuracy * (1.0 - self.config.ema_alpha)
                + acc * self.config.ema_alpha;
            stats.recent_accuracy = acc;
        }

        Some(avg_loss)
    }

    /// Run inference (no dropout, no gradient).
    ///
    /// - `features`: Flat slice of node features, row-major, (n_nodes * input_dim).
    /// - `n_nodes`: Number of nodes.
    /// - `adj`: Edge list.
    /// - `query_node`: Node to classify.
    ///
    /// Returns probability in [0, 1].
    pub fn predict(
        &self,
        features: &[f64],
        n_nodes: usize,
        adj: &[(usize, usize)],
        query_node: usize,
    ) -> f64 {
        let feat_matrix = DMatrix::from_row_slice(n_nodes, self.input_dim, features);
        let model = self.model.lock();
        let (prob, _) = model.forward(&feat_matrix, adj, query_node, false);
        prob
    }

    /// Get current training statistics.
    pub fn get_stats(&self) -> TrainingStats {
        self.stats.lock().clone()
    }

    /// Save model weights to bytes.
    pub fn save_weights(&self) -> Result<Vec<u8>, String> {
        let model = self.model.lock();
        model.save_weights()
    }

    /// Load model weights from bytes.
    pub fn load_weights(&self, data: &[u8]) -> Result<(), String> {
        let new_model = GATReasoner::load_weights(data)?;
        let mut model = self.model.lock();
        *model = new_model;
        Ok(())
    }

    /// Predict link probability between two nodes given their feature vectors.
    ///
    /// Thread-safe wrapper around `GATReasoner::predict_link`.
    ///
    /// - `node_a_features`: Feature vector for node A.
    /// - `node_b_features`: Feature vector for node B.
    ///
    /// Returns probability in [0, 1] that an edge should exist.
    pub fn predict_link(&self, node_a_features: &[f64], node_b_features: &[f64]) -> f64 {
        let model = self.model.lock();
        model.predict_link(node_a_features, node_b_features)
    }

    /// Get the number of samples in the training buffer.
    pub fn buffer_size(&self) -> usize {
        self.buffer.lock().len()
    }
}
