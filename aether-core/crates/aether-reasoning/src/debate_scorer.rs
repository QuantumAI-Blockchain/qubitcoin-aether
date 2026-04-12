//! Neural Debate Scoring -- a 2-layer neural network for learning debate verdict prediction.
//!
//! Architecture: input(8) -> hidden(16, sigmoid) -> output(3, softmax)
//! Training: online SGD with cross-entropy loss.
//!
//! The scorer learns to predict debate outcomes (accept/reject/modify) from
//! 8-dimensional feature vectors describing argument quality.

use aether_types::DebateVerdict;
use parking_lot::RwLock;
use rand::Rng;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicUsize, Ordering};

/// 2-layer neural network for scoring debate outcomes.
pub struct DebateScorer {
    input_dim: usize,
    hidden_dim: usize,
    output_dim: usize,
    lr: f64,

    // Weights: W1[input_dim][hidden_dim], b1[hidden_dim]
    //          W2[hidden_dim][output_dim], b2[output_dim]
    w1: RwLock<Vec<Vec<f64>>>,
    b1: RwLock<Vec<f64>>,
    w2: RwLock<Vec<Vec<f64>>>,
    b2: RwLock<Vec<f64>>,

    // Stats
    train_steps: AtomicUsize,
    total_scores: AtomicUsize,
    correct_predictions: AtomicUsize,
    total_loss: RwLock<f64>,
    verdict_counts: RwLock<HashMap<String, usize>>,
}

/// The three verdict classes.
const VERDICTS: [&str; 3] = ["accept", "reject", "modify"];

impl DebateScorer {
    /// Create a new scorer with Xavier initialization.
    pub fn new(input_dim: usize, hidden_dim: usize, lr: f64) -> Self {
        let output_dim = VERDICTS.len();
        let mut rng = rand::thread_rng();

        // Xavier initialization: scale = sqrt(2 / fan_in)
        let scale1 = (2.0 / input_dim as f64).sqrt();
        let w1: Vec<Vec<f64>> = (0..input_dim)
            .map(|_| (0..hidden_dim).map(|_| rng.gen::<f64>() * 2.0 * scale1 - scale1).collect())
            .collect();
        let b1 = vec![0.0; hidden_dim];

        let scale2 = (2.0 / hidden_dim as f64).sqrt();
        let w2: Vec<Vec<f64>> = (0..hidden_dim)
            .map(|_| (0..output_dim).map(|_| rng.gen::<f64>() * 2.0 * scale2 - scale2).collect())
            .collect();
        let b2 = vec![0.0; output_dim];

        let mut verdict_counts = HashMap::new();
        for v in &VERDICTS {
            verdict_counts.insert(v.to_string(), 0);
        }

        Self {
            input_dim,
            hidden_dim,
            output_dim,
            lr,
            w1: RwLock::new(w1),
            b1: RwLock::new(b1),
            w2: RwLock::new(w2),
            b2: RwLock::new(b2),
            train_steps: AtomicUsize::new(0),
            total_scores: AtomicUsize::new(0),
            correct_predictions: AtomicUsize::new(0),
            total_loss: RwLock::new(0.0),
            verdict_counts: RwLock::new(verdict_counts),
        }
    }

    /// Create with default dimensions: 8 input, 16 hidden, 0.01 learning rate.
    pub fn default_scorer() -> Self {
        Self::new(8, 16, 0.01)
    }

    /// Score a debate and return verdict with confidence.
    pub fn score_debate(&self, features: &[f64]) -> (DebateVerdict, f64) {
        self.total_scores.fetch_add(1, Ordering::Relaxed);

        let (probs, _, _) = self.forward(features);
        let best_idx = argmax(&probs);
        let verdict = verdict_from_index(best_idx);
        let confidence = probs[best_idx];

        {
            let mut vc = self.verdict_counts.write();
            *vc.entry(VERDICTS[best_idx].to_string()).or_insert(0) += 1;
        }

        (verdict, confidence)
    }

    /// Online training: backpropagation with cross-entropy loss.
    ///
    /// Returns the cross-entropy loss value.
    pub fn train_on_outcome(&self, features: &[f64], actual_verdict: &DebateVerdict) -> f64 {
        let target_idx = actual_verdict.index();

        let x = self.prepare_input(features);

        let w1 = self.w1.read();
        let b1 = self.b1.read();
        let w2 = self.w2.read();
        let b2 = self.b2.read();

        // Forward pass
        // Hidden layer: z1 = x @ W1 + b1
        let mut z1 = vec![0.0_f64; self.hidden_dim];
        for j in 0..self.hidden_dim {
            let mut sum = b1[j];
            for i in 0..self.input_dim {
                sum += x[i] * w1[i][j];
            }
            z1[j] = sum;
        }
        let h1: Vec<f64> = z1.iter().map(|&z| sigmoid(z)).collect();

        // Output layer: z2 = h1 @ W2 + b2
        let mut z2 = vec![0.0_f64; self.output_dim];
        for j in 0..self.output_dim {
            let mut sum = b2[j];
            for i in 0..self.hidden_dim {
                sum += h1[i] * w2[i][j];
            }
            z2[j] = sum;
        }
        let probs = softmax(&z2);

        // Cross-entropy loss
        let loss = -(probs[target_idx] + 1e-12).ln();

        // Check prediction
        if argmax(&probs) == target_idx {
            self.correct_predictions.fetch_add(1, Ordering::Relaxed);
        }

        // Backpropagation
        // dL/dz2 = probs - one_hot(target)
        let mut dz2 = probs.clone();
        dz2[target_idx] -= 1.0;

        // Gradients for W2, b2
        // dW2[i][j] = h1[i] * dz2[j]
        // db2[j] = dz2[j]
        let mut dw2 = vec![vec![0.0_f64; self.output_dim]; self.hidden_dim];
        for i in 0..self.hidden_dim {
            for j in 0..self.output_dim {
                dw2[i][j] = h1[i] * dz2[j];
            }
        }

        // Backprop through hidden
        // dh1[i] = sum_j(dz2[j] * W2[i][j])
        let mut dh1 = vec![0.0_f64; self.hidden_dim];
        for i in 0..self.hidden_dim {
            for j in 0..self.output_dim {
                dh1[i] += dz2[j] * w2[i][j];
            }
        }

        // dz1 = dh1 * h1 * (1 - h1) (sigmoid derivative)
        let mut dz1 = vec![0.0_f64; self.hidden_dim];
        for i in 0..self.hidden_dim {
            dz1[i] = dh1[i] * h1[i] * (1.0 - h1[i]);
        }

        // Gradients for W1, b1
        let mut dw1 = vec![vec![0.0_f64; self.hidden_dim]; self.input_dim];
        for i in 0..self.input_dim {
            for j in 0..self.hidden_dim {
                dw1[i][j] = x[i] * dz1[j];
            }
        }

        // Drop read locks before acquiring write locks
        drop(w1);
        drop(b1);
        drop(w2);
        drop(b2);

        // SGD updates
        {
            let mut w2 = self.w2.write();
            let mut b2 = self.b2.write();
            for i in 0..self.hidden_dim {
                for j in 0..self.output_dim {
                    w2[i][j] -= self.lr * dw2[i][j];
                }
            }
            for j in 0..self.output_dim {
                b2[j] -= self.lr * dz2[j];
            }
        }
        {
            let mut w1 = self.w1.write();
            let mut b1 = self.b1.write();
            for i in 0..self.input_dim {
                for j in 0..self.hidden_dim {
                    w1[i][j] -= self.lr * dw1[i][j];
                }
            }
            for j in 0..self.hidden_dim {
                b1[j] -= self.lr * dz1[j];
            }
        }

        self.train_steps.fetch_add(1, Ordering::Relaxed);
        *self.total_loss.write() += loss;

        loss
    }

    /// Extract an 8-dimensional feature vector from debate result data.
    ///
    /// Features:
    /// 0: argument_strength (0-1)
    /// 1: evidence_count (normalized)
    /// 2: reasoning_depth (normalized)
    /// 3: counterargument_quality (0-1)
    /// 4: num_rounds (normalized by 5)
    /// 5: consensus_score (0-1)
    /// 6: novelty_score (0-1)
    /// 7: logical_coherence (0-1)
    pub fn extract_features(&self, debate_result: &HashMap<String, f64>) -> Vec<f64> {
        let mut features = vec![0.0_f64; self.input_dim];

        features[0] = *debate_result.get("argument_strength").unwrap_or(&0.5);
        features[1] = (*debate_result.get("evidence_count").unwrap_or(&0.0) / 20.0).min(1.0);
        features[2] = (*debate_result.get("reasoning_depth").unwrap_or(&0.0) / 10.0).min(1.0);
        features[3] = *debate_result.get("counterargument_quality").unwrap_or(&0.5);
        features[4] = (*debate_result.get("num_rounds").unwrap_or(&1.0) / 5.0).min(1.0);
        features[5] = *debate_result.get("consensus_score").unwrap_or(&0.5);
        features[6] = *debate_result.get("novelty_score").unwrap_or(&0.5);
        features[7] = *debate_result.get("logical_coherence").unwrap_or(&0.5);

        features
    }

    /// Return statistics about the scorer.
    pub fn get_stats(&self) -> ScorerStats {
        let steps = self.train_steps.load(Ordering::Relaxed);
        let total_loss = *self.total_loss.read();
        let correct = self.correct_predictions.load(Ordering::Relaxed);

        ScorerStats {
            input_dim: self.input_dim,
            hidden_dim: self.hidden_dim,
            train_steps: steps,
            total_scores: self.total_scores.load(Ordering::Relaxed),
            avg_loss: if steps > 0 {
                total_loss / steps as f64
            } else {
                0.0
            },
            accuracy: if steps > 0 {
                correct as f64 / steps as f64
            } else {
                0.0
            },
            verdict_counts: self.verdict_counts.read().clone(),
            correct_predictions: correct,
        }
    }

    // ------------------------------------------------------------------
    // Internal helpers
    // ------------------------------------------------------------------

    /// Forward pass. Returns (probs, hidden_activations, pre_softmax_logits).
    fn forward(&self, features: &[f64]) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
        let x = self.prepare_input(features);

        let w1 = self.w1.read();
        let b1 = self.b1.read();
        let w2 = self.w2.read();
        let b2 = self.b2.read();

        // Hidden layer
        let mut z1 = vec![0.0_f64; self.hidden_dim];
        for j in 0..self.hidden_dim {
            let mut sum = b1[j];
            for i in 0..self.input_dim {
                sum += x[i] * w1[i][j];
            }
            z1[j] = sum;
        }
        let h1: Vec<f64> = z1.iter().map(|&z| sigmoid(z)).collect();

        // Output layer
        let mut z2 = vec![0.0_f64; self.output_dim];
        for j in 0..self.output_dim {
            let mut sum = b2[j];
            for i in 0..self.hidden_dim {
                sum += h1[i] * w2[i][j];
            }
            z2[j] = sum;
        }

        let probs = softmax(&z2);
        (probs, h1, z2)
    }

    /// Prepare input: pad or truncate to input_dim.
    fn prepare_input(&self, features: &[f64]) -> Vec<f64> {
        let mut x = vec![0.0_f64; self.input_dim];
        let copy_len = features.len().min(self.input_dim);
        x[..copy_len].copy_from_slice(&features[..copy_len]);
        x
    }
}

/// Statistics for the debate scorer.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ScorerStats {
    pub input_dim: usize,
    pub hidden_dim: usize,
    pub train_steps: usize,
    pub total_scores: usize,
    pub avg_loss: f64,
    pub accuracy: f64,
    pub verdict_counts: HashMap<String, usize>,
    pub correct_predictions: usize,
}

// ------------------------------------------------------------------
// Activation functions
// ------------------------------------------------------------------

/// Numerically stable sigmoid.
fn sigmoid(x: f64) -> f64 {
    if x >= 0.0 {
        1.0 / (1.0 + (-x).exp())
    } else {
        let ex = x.exp();
        ex / (1.0 + ex)
    }
}

/// Softmax over a 1D slice.
fn softmax(x: &[f64]) -> Vec<f64> {
    let max_x = x.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let exps: Vec<f64> = x.iter().map(|&v| (v - max_x).exp()).collect();
    let sum: f64 = exps.iter().sum::<f64>() + 1e-12;
    exps.iter().map(|&e| e / sum).collect()
}

/// Index of the maximum element.
fn argmax(x: &[f64]) -> usize {
    x.iter()
        .enumerate()
        .max_by(|(_, a), (_, b)| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal))
        .map(|(i, _)| i)
        .unwrap_or(0)
}

/// Convert verdict index to DebateVerdict.
fn verdict_from_index(idx: usize) -> DebateVerdict {
    match idx {
        0 => DebateVerdict::Accepted,
        1 => DebateVerdict::Rejected,
        2 => DebateVerdict::Modified,
        _ => DebateVerdict::Undecided,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sigmoid_positive() {
        let s = sigmoid(0.0);
        assert!((s - 0.5).abs() < 1e-10);
    }

    #[test]
    fn test_sigmoid_large_positive() {
        let s = sigmoid(100.0);
        assert!((s - 1.0).abs() < 1e-6);
    }

    #[test]
    fn test_sigmoid_large_negative() {
        let s = sigmoid(-100.0);
        assert!(s.abs() < 1e-6);
    }

    #[test]
    fn test_softmax_uniform() {
        let x = vec![1.0, 1.0, 1.0];
        let p = softmax(&x);
        assert_eq!(p.len(), 3);
        for &pi in &p {
            assert!((pi - 1.0 / 3.0).abs() < 0.01);
        }
    }

    #[test]
    fn test_softmax_dominant() {
        let x = vec![10.0, 0.0, 0.0];
        let p = softmax(&x);
        assert!(p[0] > 0.99);
    }

    #[test]
    fn test_softmax_sums_to_one() {
        let x = vec![1.0, 2.0, 3.0];
        let p = softmax(&x);
        let sum: f64 = p.iter().sum();
        assert!((sum - 1.0).abs() < 1e-6);
    }

    #[test]
    fn test_argmax() {
        assert_eq!(argmax(&[0.1, 0.7, 0.2]), 1);
        assert_eq!(argmax(&[0.9, 0.05, 0.05]), 0);
    }

    #[test]
    fn test_scorer_creation() {
        let scorer = DebateScorer::default_scorer();
        let stats = scorer.get_stats();
        assert_eq!(stats.input_dim, 8);
        assert_eq!(stats.hidden_dim, 16);
        assert_eq!(stats.train_steps, 0);
    }

    #[test]
    fn test_score_debate() {
        let scorer = DebateScorer::default_scorer();
        let features = vec![0.5, 0.3, 0.2, 0.4, 0.6, 0.5, 0.3, 0.7];
        let (verdict, confidence) = scorer.score_debate(&features);
        // Should return a valid verdict
        assert!(matches!(
            verdict,
            DebateVerdict::Accepted | DebateVerdict::Rejected | DebateVerdict::Modified
        ));
        assert!(confidence >= 0.0 && confidence <= 1.0);
        assert_eq!(scorer.get_stats().total_scores, 1);
    }

    #[test]
    fn test_score_debate_short_features() {
        let scorer = DebateScorer::default_scorer();
        let features = vec![0.5, 0.3]; // Only 2 features, should pad
        let (_, confidence) = scorer.score_debate(&features);
        assert!(confidence >= 0.0 && confidence <= 1.0);
    }

    #[test]
    fn test_train_on_outcome() {
        let scorer = DebateScorer::default_scorer();
        let features = vec![0.5, 0.3, 0.2, 0.4, 0.6, 0.5, 0.3, 0.7];
        let loss = scorer.train_on_outcome(&features, &DebateVerdict::Accepted);
        assert!(loss > 0.0);
        assert_eq!(scorer.get_stats().train_steps, 1);
    }

    #[test]
    fn test_training_reduces_loss() {
        let scorer = DebateScorer::new(8, 16, 0.1); // Higher LR for faster convergence
        let features = vec![0.9, 0.8, 0.7, 0.1, 0.2, 0.9, 0.8, 0.9];

        let loss1 = scorer.train_on_outcome(&features, &DebateVerdict::Accepted);

        // Train 50 more times
        let mut last_loss = loss1;
        for _ in 0..50 {
            last_loss = scorer.train_on_outcome(&features, &DebateVerdict::Accepted);
        }

        // Loss should decrease after repeated training on same data
        assert!(last_loss < loss1);
    }

    #[test]
    fn test_extract_features() {
        let scorer = DebateScorer::default_scorer();
        let mut data = HashMap::new();
        data.insert("argument_strength".to_string(), 0.8);
        data.insert("evidence_count".to_string(), 15.0);
        data.insert("reasoning_depth".to_string(), 5.0);

        let features = scorer.extract_features(&data);
        assert_eq!(features.len(), 8);
        assert!((features[0] - 0.8).abs() < f64::EPSILON);
        assert!((features[1] - 0.75).abs() < f64::EPSILON); // 15/20
        assert!((features[2] - 0.5).abs() < f64::EPSILON); // 5/10
    }

    #[test]
    fn test_extract_features_defaults() {
        let scorer = DebateScorer::default_scorer();
        let data = HashMap::new();
        let features = scorer.extract_features(&data);
        // Default values for missing keys
        assert!((features[0] - 0.5).abs() < f64::EPSILON); // argument_strength default
        assert!((features[5] - 0.5).abs() < f64::EPSILON); // consensus_score default
    }

    #[test]
    fn test_verdict_from_index() {
        assert_eq!(verdict_from_index(0), DebateVerdict::Accepted);
        assert_eq!(verdict_from_index(1), DebateVerdict::Rejected);
        assert_eq!(verdict_from_index(2), DebateVerdict::Modified);
        assert_eq!(verdict_from_index(99), DebateVerdict::Undecided);
    }

    #[test]
    fn test_scorer_stats_accuracy() {
        let scorer = DebateScorer::default_scorer();
        let features = vec![0.5; 8];

        // Train 10 times
        for _ in 0..10 {
            scorer.train_on_outcome(&features, &DebateVerdict::Accepted);
        }

        let stats = scorer.get_stats();
        assert_eq!(stats.train_steps, 10);
        assert!(stats.avg_loss > 0.0);
        // Accuracy should be between 0 and 1
        assert!(stats.accuracy >= 0.0 && stats.accuracy <= 1.0);
    }

    #[test]
    fn test_scorer_thread_safe() {
        use std::sync::Arc;
        use std::thread;

        let scorer = Arc::new(DebateScorer::default_scorer());
        let mut handles = Vec::new();

        for _ in 0..4 {
            let s = Arc::clone(&scorer);
            handles.push(thread::spawn(move || {
                let features = vec![0.5; 8];
                for _ in 0..10 {
                    s.score_debate(&features);
                    s.train_on_outcome(&features, &DebateVerdict::Accepted);
                }
            }));
        }

        for h in handles {
            h.join().unwrap();
        }

        let stats = scorer.get_stats();
        assert_eq!(stats.total_scores, 40);
        assert_eq!(stats.train_steps, 40);
    }
}
