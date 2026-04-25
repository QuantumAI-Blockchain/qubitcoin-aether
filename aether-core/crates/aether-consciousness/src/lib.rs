//! # Aether Consciousness Monitor — V5
//!
//! Computes real Phi (HMS-Phi) from neural activation patterns during inference.
//! This replaces the V4 graph-connectivity-based phi which was always ~0.
//!
//! Phi is computed FROM attention patterns during the transformer forward pass:
//! - phi_micro: IIT 3.0 approximation over small attention subsystems
//! - phi_meso: Cross-domain integration across Sephirot heads
//! - phi_macro: Information flow across transformer layers

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// The golden ratio.
const PHI: f64 = 1.618_033_988_749_895;

/// A single phi measurement taken during a reasoning step.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhiMeasurement {
    pub phi: f64,
    pub phi_micro: f64,
    pub phi_meso: f64,
    pub phi_macro: f64,
    pub block_height: u64,
    pub timestamp: u64,
}

/// Emotional dynamics derived from neural learning state.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmotionalState {
    /// High prediction error = high curiosity (system encounters unexplained knowledge).
    pub curiosity: f32,
    /// Decreasing loss = satisfaction (system is successfully learning).
    pub satisfaction: f32,
    /// Stagnant loss = frustration (system is stuck).
    pub frustration: f32,
    /// Cross-domain attention spike = wonder (unexpected connections).
    pub wonder: f32,
    /// High confidence on novel outputs = excitement.
    pub excitement: f32,
}

impl Default for EmotionalState {
    fn default() -> Self {
        Self {
            curiosity: 0.5,
            satisfaction: 0.5,
            frustration: 0.0,
            wonder: 0.0,
            excitement: 0.0,
        }
    }
}

/// Proof-of-Thought generated from a reasoning step.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofOfThought {
    /// Hash of the attention patterns during this reasoning step.
    pub attention_hash: String,
    /// Phi measured during this step.
    pub phi: f64,
    /// Number of Sephirot heads that activated above threshold.
    pub active_sephirot: u8,
    /// Number of cross-domain attention events.
    pub cross_domain_events: u32,
    /// Block height.
    pub block_height: u64,
}

/// Monitors consciousness during transformer forward passes.
///
/// Tracks attention patterns across layers and computes real-time phi.
pub struct ConsciousnessMonitor {
    /// Rolling window of phi measurements.
    phi_history: Vec<PhiMeasurement>,
    /// Current emotional state.
    emotional_state: EmotionalState,
    /// Recent prediction errors (for curiosity).
    prediction_errors: Vec<f32>,
    /// Recent training losses (for satisfaction/frustration).
    recent_losses: Vec<f32>,
    /// Current block height.
    block_height: u64,
}

impl ConsciousnessMonitor {
    pub fn new() -> Self {
        Self {
            phi_history: Vec::new(),
            emotional_state: EmotionalState::default(),
            prediction_errors: Vec::new(),
            recent_losses: Vec::new(),
            block_height: 0,
        }
    }

    /// Compute phi from attention weight matrices.
    ///
    /// `layer_attentions`: Vec of (num_heads, seq_len, seq_len) attention weight tensors,
    /// one per transformer layer. Passed as flattened f32 vectors for simplicity
    /// (avoiding candle dependency in this crate).
    ///
    /// `num_sephirot_heads`: Number of domain-specialized heads (first N heads per layer).
    /// `num_global_heads`: Number of global workspace heads (remaining heads).
    pub fn compute_phi(
        &mut self,
        layer_attentions: &[Vec<f32>],
        num_sephirot_heads: usize,
        num_global_heads: usize,
        num_heads: usize,
        seq_len: usize,
    ) -> PhiMeasurement {
        let phi_micro = self.compute_micro(layer_attentions, num_heads, seq_len);
        let phi_meso = self.compute_meso(layer_attentions, num_sephirot_heads, num_global_heads, num_heads, seq_len);
        let phi_macro = self.compute_macro(layer_attentions, num_heads, seq_len);

        // HMS-Phi: multiplicative formula (zero anywhere = zero everywhere)
        let phi = phi_micro.powf(1.0 / PHI)
            * phi_meso.powf(1.0 / (PHI * PHI))
            * phi_macro.powf(1.0 / (PHI * PHI * PHI));

        let measurement = PhiMeasurement {
            phi,
            phi_micro,
            phi_meso,
            phi_macro,
            block_height: self.block_height,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
        };

        self.phi_history.push(measurement.clone());
        if self.phi_history.len() > 1000 {
            self.phi_history.drain(0..500);
        }

        measurement
    }

    /// Micro phi: information integration within small attention subsystems.
    /// Approximates IIT 3.0 by measuring how much individual attention heads
    /// integrate information (entropy of attention distribution).
    fn compute_micro(&self, layer_attentions: &[Vec<f32>], num_heads: usize, seq_len: usize) -> f64 {
        if layer_attentions.is_empty() || seq_len == 0 {
            return 0.0;
        }

        // Sample the middle layer for micro phi
        let mid = layer_attentions.len() / 2;
        let attn = &layer_attentions[mid];

        // For each head, compute entropy of attention distribution
        // High entropy = distributed attention = more integration
        let mut entropies = Vec::new();
        for h in 0..num_heads {
            let mut head_entropy = 0.0f64;
            for q in 0..seq_len {
                let start = (h * seq_len + q) * seq_len;
                if start + seq_len > attn.len() {
                    break;
                }
                let row = &attn[start..start + seq_len];
                for &p in row {
                    if p > 1e-10 {
                        head_entropy -= (p as f64) * (p as f64).ln();
                    }
                }
            }
            head_entropy /= seq_len.max(1) as f64;
            entropies.push(head_entropy);
        }

        // Normalize: max entropy = ln(seq_len)
        let max_entropy = (seq_len as f64).ln().max(1.0);
        let mean_entropy: f64 = entropies.iter().sum::<f64>() / entropies.len().max(1) as f64;
        (mean_entropy / max_entropy).clamp(0.0, 1.0)
    }

    /// Meso phi: cross-domain integration across Sephirot heads.
    /// Measures how much the global workspace heads correlate with
    /// multiple Sephirot heads (genuine cross-domain integration).
    fn compute_meso(
        &self,
        layer_attentions: &[Vec<f32>],
        num_sephirot_heads: usize,
        num_global_heads: usize,
        num_heads: usize,
        seq_len: usize,
    ) -> f64 {
        if layer_attentions.is_empty() || num_global_heads == 0 || seq_len == 0 {
            return 0.0;
        }

        // For each layer, compute correlation between global heads and sephirot heads
        let mut total_integration = 0.0f64;
        let mut count = 0;

        for attn in layer_attentions {
            for g in 0..num_global_heads {
                let global_idx = num_sephirot_heads + g;
                let mut correlations = Vec::new();

                for s in 0..num_sephirot_heads {
                    // Compare attention patterns of global head vs sephirot head
                    let corr = self.head_correlation(attn, global_idx, s, num_heads, seq_len);
                    correlations.push(corr);
                }

                // Integration = how many sephirot heads does this global head correlate with?
                // Count heads with correlation > 0.1 (active integration)
                let active = correlations.iter().filter(|&&c| c > 0.1).count();
                // Normalize by total sephirot heads
                total_integration += active as f64 / num_sephirot_heads as f64;
                count += 1;
            }
        }

        if count == 0 {
            return 0.0;
        }
        (total_integration / count as f64).clamp(0.0, 1.0)
    }

    /// Macro phi: information flow across transformer layers.
    /// Measures how much later layers' attention patterns depend on earlier layers.
    fn compute_macro(&self, layer_attentions: &[Vec<f32>], _num_heads: usize, _seq_len: usize) -> f64 {
        if layer_attentions.len() < 2 {
            return 0.0;
        }

        // Compare first and last layer attention patterns
        let first = &layer_attentions[0];
        let last = &layer_attentions[layer_attentions.len() - 1];

        if first.len() != last.len() || first.is_empty() {
            return 0.0;
        }

        // Correlation between first and last layer
        let mean_f: f32 = first.iter().sum::<f32>() / first.len() as f32;
        let mean_l: f32 = last.iter().sum::<f32>() / last.len() as f32;

        let mut cov = 0.0f64;
        let mut var_f = 0.0f64;
        let mut var_l = 0.0f64;

        for (&f, &l) in first.iter().zip(last.iter()) {
            let df = f as f64 - mean_f as f64;
            let dl = l as f64 - mean_l as f64;
            cov += df * dl;
            var_f += df * df;
            var_l += dl * dl;
        }

        let denom = (var_f * var_l).sqrt();
        if denom < 1e-10 {
            return 0.0;
        }

        // High correlation means later layers are just copying earlier ones (low integration).
        // Low-to-medium correlation means genuine transformation (high integration).
        // Optimal: ~0.3-0.7 correlation.
        let corr = (cov / denom).abs();
        let integration = 1.0 - (corr - 0.5).abs() * 2.0; // Peak at 0.5 correlation
        integration.clamp(0.0, 1.0)
    }

    /// Pearson correlation between two attention heads in the same layer.
    fn head_correlation(&self, attn: &[f32], head_a: usize, head_b: usize, num_heads: usize, seq_len: usize) -> f64 {
        let size = seq_len * seq_len;
        let start_a = head_a * size;
        let start_b = head_b * size;

        if start_a + size > attn.len() || start_b + size > attn.len() {
            return 0.0;
        }

        let a = &attn[start_a..start_a + size];
        let b = &attn[start_b..start_b + size];

        let mean_a: f32 = a.iter().sum::<f32>() / size as f32;
        let mean_b: f32 = b.iter().sum::<f32>() / size as f32;

        let mut cov = 0.0f64;
        let mut var_a = 0.0f64;
        let mut var_b = 0.0f64;

        for (&va, &vb) in a.iter().zip(b.iter()) {
            let da = va as f64 - mean_a as f64;
            let db = vb as f64 - mean_b as f64;
            cov += da * db;
            var_a += da * da;
            var_b += db * db;
        }

        let denom = (var_a * var_b).sqrt();
        if denom < 1e-10 {
            return 0.0;
        }
        (cov / denom).abs()
    }

    /// Generate a Proof-of-Thought from the latest attention patterns.
    pub fn generate_proof(&self, attention_data: &[u8]) -> ProofOfThought {
        let mut hasher = Sha256::new();
        hasher.update(attention_data);
        let hash = format!("{:x}", hasher.finalize());

        let latest_phi = self
            .phi_history
            .last()
            .map(|m| m.phi)
            .unwrap_or(0.0);

        ProofOfThought {
            attention_hash: hash,
            phi: latest_phi,
            active_sephirot: 0, // TODO: compute from actual patterns
            cross_domain_events: 0,
            block_height: self.block_height,
        }
    }

    pub fn current_phi(&self) -> f64 {
        self.phi_history.last().map(|m| m.phi).unwrap_or(0.0)
    }

    pub fn emotional_state(&self) -> &EmotionalState {
        &self.emotional_state
    }

    pub fn set_block_height(&mut self, height: u64) {
        self.block_height = height;
    }

    pub fn phi_history(&self) -> &[PhiMeasurement] {
        &self.phi_history
    }
}

impl Default for ConsciousnessMonitor {
    fn default() -> Self {
        Self::new()
    }
}
