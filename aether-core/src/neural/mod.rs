//! Neural reasoning module — Graph Attention Network (GAT) for the Aether Tree.
//!
//! Implements a real GAT neural network from scratch using `nalgebra` for matrix
//! operations. No deep learning framework required.
//!
//! ## Architecture
//!
//! - **GATLayer**: Single GAT layer with multi-head attention.
//! - **GATReasoner**: Stacked GAT layers with classification head.
//! - **GATTrainer**: SGD training loop with BCE loss and ring buffer.
//! - **RustGATReasoner** (PyO3): Python-accessible wrapper.
//!
//! ## Attention Mechanism
//!
//! For each edge (i, j):
//!   e_ij = LeakyReLU(a^T [W h_i || W h_j])
//!   alpha_ij = softmax_j(e_ij)
//!   h'_i = ELU( sum_j alpha_ij * W h_j )
//!
//! Multi-head: concatenate (hidden layers) or average (output layer).

pub mod trainer;
pub mod python_bindings;

use nalgebra::{DMatrix, DVector};
use rand::Rng;
use serde::{Deserialize, Serialize, Serializer, Deserializer};

// ---------------------------------------------------------------------------
// Serde helpers for nalgebra types (nalgebra serde feature not enabled)
// ---------------------------------------------------------------------------

/// Serializable representation of a DMatrix.
#[derive(Serialize, Deserialize)]
struct MatrixData {
    rows: usize,
    cols: usize,
    data: Vec<f64>,
}

fn serialize_dmatrix<S: Serializer>(m: &DMatrix<f64>, s: S) -> Result<S::Ok, S::Error> {
    let md = MatrixData {
        rows: m.nrows(),
        cols: m.ncols(),
        data: m.iter().cloned().collect(), // column-major
    };
    md.serialize(s)
}

fn deserialize_dmatrix<'de, D: Deserializer<'de>>(d: D) -> Result<DMatrix<f64>, D::Error> {
    let md = MatrixData::deserialize(d)?;
    Ok(DMatrix::from_vec(md.rows, md.cols, md.data))
}

/// Serializable representation of a DVector.
#[derive(Serialize, Deserialize)]
struct VectorData {
    len: usize,
    data: Vec<f64>,
}

fn serialize_dvector<S: Serializer>(v: &DVector<f64>, s: S) -> Result<S::Ok, S::Error> {
    let vd = VectorData {
        len: v.len(),
        data: v.iter().cloned().collect(),
    };
    vd.serialize(s)
}

fn deserialize_dvector<'de, D: Deserializer<'de>>(d: D) -> Result<DVector<f64>, D::Error> {
    let vd = VectorData::deserialize(d)?;
    Ok(DVector::from_vec(vd.data))
}

// ---------------------------------------------------------------------------
// Activation functions
// ---------------------------------------------------------------------------

/// LeakyReLU with configurable negative slope.
#[inline]
fn leaky_relu(x: f64, alpha: f64) -> f64 {
    if x > 0.0 { x } else { alpha * x }
}

/// Derivative of LeakyReLU.
#[inline]
fn leaky_relu_grad(x: f64, alpha: f64) -> f64 {
    if x > 0.0 { 1.0 } else { alpha }
}

/// ELU activation.
#[inline]
fn elu(x: f64, alpha: f64) -> f64 {
    if x > 0.0 { x } else { alpha * (x.exp() - 1.0) }
}

/// Derivative of ELU.
#[inline]
fn elu_grad(x: f64, alpha: f64) -> f64 {
    if x > 0.0 { 1.0 } else { elu(x, alpha) + alpha }
}

/// Sigmoid activation.
#[inline]
fn sigmoid(x: f64) -> f64 {
    1.0 / (1.0 + (-x).exp())
}

/// Stable softmax over a slice. Modifies in place.
fn softmax_inplace(vals: &mut [f64]) {
    if vals.is_empty() {
        return;
    }
    let max_val = vals.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let mut sum = 0.0;
    for v in vals.iter_mut() {
        *v = (*v - max_val).exp();
        sum += *v;
    }
    if sum > 0.0 {
        for v in vals.iter_mut() {
            *v /= sum;
        }
    }
}

// ---------------------------------------------------------------------------
// Xavier initialization
// ---------------------------------------------------------------------------

/// Xavier uniform initialization: U(-limit, limit) where limit = sqrt(6 / (fan_in + fan_out)).
fn xavier_uniform(rows: usize, cols: usize, rng: &mut impl Rng) -> DMatrix<f64> {
    let limit = (6.0 / (rows as f64 + cols as f64)).sqrt();
    DMatrix::from_fn(rows, cols, |_, _| rng.gen_range(-limit..limit))
}

/// Xavier uniform initialization for a vector (used for attention parameters).
fn xavier_uniform_vec(dim: usize, fan_in: usize, fan_out: usize, rng: &mut impl Rng) -> DVector<f64> {
    let limit = (6.0 / (fan_in as f64 + fan_out as f64)).sqrt();
    DVector::from_fn(dim, |_, _| rng.gen_range(-limit..limit))
}

// ---------------------------------------------------------------------------
// GATLayer
// ---------------------------------------------------------------------------

/// Parameters for a single attention head.
#[derive(Clone, Serialize, Deserialize)]
struct AttentionHead {
    /// Linear transformation weight: (out_dim, in_dim).
    #[serde(serialize_with = "serialize_dmatrix", deserialize_with = "deserialize_dmatrix")]
    w: DMatrix<f64>,
    /// Bias for linear transformation: (out_dim,).
    #[serde(serialize_with = "serialize_dvector", deserialize_with = "deserialize_dvector")]
    b: DVector<f64>,
    /// Attention vector for source: (out_dim,).
    #[serde(serialize_with = "serialize_dvector", deserialize_with = "deserialize_dvector")]
    a_src: DVector<f64>,
    /// Attention vector for target: (out_dim,).
    #[serde(serialize_with = "serialize_dvector", deserialize_with = "deserialize_dvector")]
    a_dst: DVector<f64>,
}

/// Cached forward-pass intermediates for backpropagation.
#[derive(Clone)]
pub(crate) struct HeadForwardCache {
    /// Projected features: W * h + b for each node. Shape: (n_nodes, out_dim).
    wh: DMatrix<f64>,
    /// Raw attention coefficients e_ij (before softmax). Indexed by (src, dst_index_in_neighbors).
    e_raw: Vec<Vec<f64>>,
    /// Attention coefficients alpha_ij (after softmax). Same indexing as e_raw.
    alpha: Vec<Vec<f64>>,
    /// Pre-activation output (before ELU). Shape: (n_nodes, out_dim).
    pre_act: DMatrix<f64>,
    /// Neighbor indices for each node (for backprop).
    neighbors: Vec<Vec<usize>>,
}

/// A single Graph Attention Network layer.
#[derive(Clone, Serialize, Deserialize)]
pub struct GATLayer {
    in_dim: usize,
    out_dim: usize,
    n_heads: usize,
    leaky_alpha: f64,
    concat: bool,
    heads: Vec<AttentionHead>,
}

impl GATLayer {
    /// Create a new GAT layer.
    ///
    /// - `in_dim`: Input feature dimension.
    /// - `out_dim`: Output dimension per head.
    /// - `n_heads`: Number of attention heads.
    /// - `concat`: If true, concatenate heads (output = n_heads * out_dim).
    ///             If false, average heads (output = out_dim).
    /// - `leaky_alpha`: Negative slope for LeakyReLU in attention.
    pub fn new(
        in_dim: usize,
        out_dim: usize,
        n_heads: usize,
        concat: bool,
        leaky_alpha: f64,
    ) -> Self {
        let mut rng = rand::thread_rng();
        let heads = (0..n_heads)
            .map(|_| AttentionHead {
                w: xavier_uniform(out_dim, in_dim, &mut rng),
                b: DVector::zeros(out_dim),
                a_src: xavier_uniform_vec(out_dim, out_dim, 1, &mut rng),
                a_dst: xavier_uniform_vec(out_dim, out_dim, 1, &mut rng),
            })
            .collect();

        GATLayer {
            in_dim,
            out_dim,
            n_heads,
            leaky_alpha,
            concat,
            heads,
        }
    }

    /// Output dimension of this layer.
    pub fn output_dim(&self) -> usize {
        if self.concat {
            self.n_heads * self.out_dim
        } else {
            self.out_dim
        }
    }

    /// Forward pass.
    ///
    /// - `features`: (n_nodes, in_dim) matrix of node features.
    /// - `adj`: List of directed edges (src, dst). Self-loops should be included.
    ///
    /// Returns (output, caches_per_head).
    pub(crate) fn forward(
        &self,
        features: &DMatrix<f64>,
        adj: &[(usize, usize)],
    ) -> (DMatrix<f64>, Vec<HeadForwardCache>) {
        let n_nodes = features.nrows();

        // Build adjacency list (including self-loops).
        let mut neighbors: Vec<Vec<usize>> = vec![Vec::new(); n_nodes];
        for &(src, dst) in adj {
            if src < n_nodes && dst < n_nodes {
                neighbors[dst].push(src); // For node dst, gather from src.
            }
        }
        // Ensure self-loops.
        for i in 0..n_nodes {
            if !neighbors[i].contains(&i) {
                neighbors[i].push(i);
            }
        }

        let mut head_outputs: Vec<DMatrix<f64>> = Vec::with_capacity(self.n_heads);
        let mut caches: Vec<HeadForwardCache> = Vec::with_capacity(self.n_heads);

        for head in &self.heads {
            // Project: wh_i = W * h_i + b, stored as rows of wh.
            // wh = features * W^T, then add bias.
            let wh = features * head.w.transpose();
            let wh = DMatrix::from_fn(n_nodes, self.out_dim, |i, j| {
                wh[(i, j)] + head.b[j]
            });

            // Compute attention scores.
            // e_src[i] = a_src^T * wh_i  (scalar per node)
            // e_dst[i] = a_dst^T * wh_i
            let mut e_src_scores = vec![0.0; n_nodes];
            let mut e_dst_scores = vec![0.0; n_nodes];
            for i in 0..n_nodes {
                for k in 0..self.out_dim {
                    e_src_scores[i] += head.a_src[k] * wh[(i, k)];
                    e_dst_scores[i] += head.a_dst[k] * wh[(i, k)];
                }
            }

            // For each node, compute attention over its neighbors.
            let mut e_raw: Vec<Vec<f64>> = Vec::with_capacity(n_nodes);
            let mut alpha: Vec<Vec<f64>> = Vec::with_capacity(n_nodes);
            let mut pre_act = DMatrix::zeros(n_nodes, self.out_dim);

            for i in 0..n_nodes {
                let nbrs = &neighbors[i];
                // e_ij = LeakyReLU(e_src[j] + e_dst[i]) for each neighbor j of i.
                let mut scores: Vec<f64> = nbrs
                    .iter()
                    .map(|&j| leaky_relu(e_src_scores[j] + e_dst_scores[i], self.leaky_alpha))
                    .collect();
                let raw_scores = scores.clone();
                softmax_inplace(&mut scores);

                // Aggregate: h'_i = sum_j alpha_ij * wh_j
                for (idx, &j) in nbrs.iter().enumerate() {
                    let a = scores[idx];
                    for k in 0..self.out_dim {
                        pre_act[(i, k)] += a * wh[(j, k)];
                    }
                }

                e_raw.push(raw_scores);
                alpha.push(scores);
            }

            // Apply ELU activation.
            let output = DMatrix::from_fn(n_nodes, self.out_dim, |i, j| {
                elu(pre_act[(i, j)], 1.0)
            });

            caches.push(HeadForwardCache {
                wh,
                e_raw,
                alpha,
                pre_act,
                neighbors: neighbors.clone(),
            });
            head_outputs.push(output);
        }

        // Combine heads.
        let combined = if self.concat {
            // Concatenate along feature dimension.
            let total_dim = self.n_heads * self.out_dim;
            DMatrix::from_fn(n_nodes, total_dim, |i, j| {
                let head_idx = j / self.out_dim;
                let feat_idx = j % self.out_dim;
                head_outputs[head_idx][(i, feat_idx)]
            })
        } else {
            // Average across heads.
            let mut avg = DMatrix::zeros(n_nodes, self.out_dim);
            for ho in &head_outputs {
                avg += ho;
            }
            avg /= self.n_heads as f64;
            avg
        };

        (combined, caches)
    }

    /// Backward pass for one GAT layer.
    ///
    /// - `d_output`: Gradient of loss w.r.t. this layer's output. (n_nodes, output_dim).
    /// - `features`: The input features that were fed to forward().
    /// - `caches`: The forward caches returned by forward().
    ///
    /// Returns (d_input, gradients).
    /// `d_input` shape: (n_nodes, in_dim).
    /// Gradients: Vec of (d_w, d_b, d_a_src, d_a_dst) per head.
    pub(crate) fn backward(
        &self,
        d_output: &DMatrix<f64>,
        features: &DMatrix<f64>,
        caches: &[HeadForwardCache],
    ) -> (DMatrix<f64>, Vec<HeadGrad>) {
        let n_nodes = features.nrows();
        let mut d_input = DMatrix::zeros(n_nodes, self.in_dim);
        let mut head_grads = Vec::with_capacity(self.n_heads);

        for (h_idx, (head, cache)) in self.heads.iter().zip(caches.iter()).enumerate() {
            // Extract per-head gradient from d_output.
            let d_head_out = if self.concat {
                let offset = h_idx * self.out_dim;
                DMatrix::from_fn(n_nodes, self.out_dim, |i, j| {
                    d_output[(i, offset + j)]
                })
            } else {
                DMatrix::from_fn(n_nodes, self.out_dim, |i, j| {
                    d_output[(i, j)] / self.n_heads as f64
                })
            };

            // Backprop through ELU.
            let d_pre_act = DMatrix::from_fn(n_nodes, self.out_dim, |i, j| {
                d_head_out[(i, j)] * elu_grad(cache.pre_act[(i, j)], 1.0)
            });

            // Gradients for attention and projection.
            let mut d_w = DMatrix::zeros(self.out_dim, self.in_dim);
            let mut d_b = DVector::zeros(self.out_dim);
            let mut d_a_src = DVector::zeros(self.out_dim);
            let mut d_a_dst = DVector::zeros(self.out_dim);
            let mut d_wh = DMatrix::zeros(n_nodes, self.out_dim);

            for i in 0..n_nodes {
                let nbrs = &cache.neighbors[i];
                let n_nbrs = nbrs.len();
                if n_nbrs == 0 {
                    continue;
                }

                // d_pre_act[i] = sum_j alpha_ij * wh[j]
                // => d_alpha_ij = d_pre_act[i]^T * wh[j]
                // => d_wh[j] += alpha_ij * d_pre_act[i]

                let mut d_alpha = vec![0.0; n_nbrs];
                for (idx, &j) in nbrs.iter().enumerate() {
                    // d_wh[j] += alpha_ij * d_pre_act[i]
                    for k in 0..self.out_dim {
                        d_wh[(j, k)] += cache.alpha[i][idx] * d_pre_act[(i, k)];
                    }
                    // d_alpha_ij = dot(d_pre_act[i], wh[j])
                    let mut dot = 0.0;
                    for k in 0..self.out_dim {
                        dot += d_pre_act[(i, k)] * cache.wh[(j, k)];
                    }
                    d_alpha[idx] = dot;
                }

                // Backprop through softmax: d_e = alpha * (d_alpha - sum(alpha * d_alpha))
                let sum_alpha_dalpha: f64 = (0..n_nbrs)
                    .map(|idx| cache.alpha[i][idx] * d_alpha[idx])
                    .sum();
                let mut d_e = vec![0.0; n_nbrs];
                for idx in 0..n_nbrs {
                    d_e[idx] = cache.alpha[i][idx] * (d_alpha[idx] - sum_alpha_dalpha);
                }

                // Backprop through LeakyReLU: d_raw = d_e * leaky_relu_grad
                for (idx, &j) in nbrs.iter().enumerate() {
                    let raw = cache.e_raw[i][idx];
                    // The raw score before LeakyReLU was e_src[j] + e_dst[i].
                    // We stored the post-LeakyReLU value in e_raw. Need pre-LeakyReLU
                    // for the gradient. Since LeakyReLU is monotonic, we can infer sign
                    // from the stored value.
                    let pre_leaky = if raw > 0.0 {
                        raw
                    } else {
                        raw / self.leaky_alpha
                    };
                    let d_leaky = d_e[idx] * leaky_relu_grad(pre_leaky, self.leaky_alpha);

                    // d_e_src[j] += d_leaky, d_e_dst[i] += d_leaky
                    // e_src[j] = a_src^T * wh[j] => d_a_src += d_leaky * wh[j], d_wh[j] += d_leaky * a_src
                    // e_dst[i] = a_dst^T * wh[i] => d_a_dst += d_leaky * wh[i], d_wh[i] += d_leaky * a_dst
                    for k in 0..self.out_dim {
                        d_a_src[k] += d_leaky * cache.wh[(j, k)];
                        d_wh[(j, k)] += d_leaky * head.a_src[k];
                        d_a_dst[k] += d_leaky * cache.wh[(i, k)];
                        d_wh[(i, k)] += d_leaky * head.a_dst[k];
                    }
                }
            }

            // Backprop through projection: wh = features * W^T + b
            // d_W += d_wh^T * features
            // d_b += sum of d_wh rows
            // d_input += d_wh * W
            d_w += d_wh.transpose() * features;
            for i in 0..n_nodes {
                for k in 0..self.out_dim {
                    d_b[k] += d_wh[(i, k)];
                }
            }
            d_input += &d_wh * &head.w;

            head_grads.push(HeadGrad {
                d_w,
                d_b,
                d_a_src,
                d_a_dst,
            });
        }

        (d_input, head_grads)
    }

    /// Apply parameter updates (called by optimizer).
    pub fn apply_gradients(&mut self, grads: &[HeadGrad], lr: f64, weight_decay: f64) {
        for (head, grad) in self.heads.iter_mut().zip(grads.iter()) {
            // SGD with L2 weight decay.
            head.w = &head.w * (1.0 - lr * weight_decay) - &grad.d_w * lr;
            head.b -= &grad.d_b * lr;
            head.a_src = &head.a_src * (1.0 - lr * weight_decay) - &grad.d_a_src * lr;
            head.a_dst = &head.a_dst * (1.0 - lr * weight_decay) - &grad.d_a_dst * lr;
        }
    }

    /// Collect all parameter magnitudes for gradient clipping.
    pub fn grad_norm_sq(grads: &[HeadGrad]) -> f64 {
        let mut norm_sq = 0.0;
        for g in grads {
            norm_sq += g.d_w.iter().map(|x| x * x).sum::<f64>();
            norm_sq += g.d_b.iter().map(|x| x * x).sum::<f64>();
            norm_sq += g.d_a_src.iter().map(|x| x * x).sum::<f64>();
            norm_sq += g.d_a_dst.iter().map(|x| x * x).sum::<f64>();
        }
        norm_sq
    }

    /// Scale all gradients by a factor (for clipping).
    pub fn scale_grads(grads: &mut [HeadGrad], factor: f64) {
        for g in grads {
            g.d_w *= factor;
            g.d_b *= factor;
            g.d_a_src *= factor;
            g.d_a_dst *= factor;
        }
    }
}

/// Gradient storage for a single attention head.
#[derive(Clone)]
pub struct HeadGrad {
    pub d_w: DMatrix<f64>,
    pub d_b: DVector<f64>,
    pub d_a_src: DVector<f64>,
    pub d_a_dst: DVector<f64>,
}

// ---------------------------------------------------------------------------
// GATReasoner
// ---------------------------------------------------------------------------

/// Full GAT reasoning network with multiple layers and a classification head.
#[derive(Clone, Serialize, Deserialize)]
pub struct GATReasoner {
    layers: Vec<GATLayer>,
    /// Classification head weights: (1, final_layer_output_dim).
    #[serde(serialize_with = "serialize_dvector", deserialize_with = "deserialize_dvector")]
    cls_w: DVector<f64>,
    /// Classification head bias (scalar).
    cls_b: f64,
    /// Dropout rate (applied between layers during training).
    dropout_rate: f64,
}

/// Cached forward pass for the full reasoner (used in backprop).
pub struct ReasonerForwardCache {
    /// Per-layer input features.
    layer_inputs: Vec<DMatrix<f64>>,
    /// Per-layer GAT caches.
    layer_caches: Vec<Vec<HeadForwardCache>>,
    /// Per-layer dropout masks (None if not training).
    dropout_masks: Vec<Option<Vec<bool>>>,
    /// Final features before classification head.
    final_features: DVector<f64>,
    /// Pre-sigmoid logit.
    #[allow(dead_code)]
    logit: f64,
    /// Sigmoid output.
    prob: f64,
}

/// Gradients for the classification head.
pub struct ClsGrad {
    pub d_w: DVector<f64>,
    pub d_b: f64,
}

impl GATReasoner {
    /// Create a new GATReasoner.
    ///
    /// - `input_dim`: Input feature dimension.
    /// - `hidden_dim`: Hidden dimension per attention head.
    /// - `output_dim`: Output dimension per head in the final GAT layer.
    /// - `n_heads`: Number of attention heads per layer.
    /// - `n_layers`: Number of GAT layers (minimum 1).
    pub fn new(
        input_dim: usize,
        hidden_dim: usize,
        output_dim: usize,
        n_heads: usize,
        n_layers: usize,
        dropout_rate: f64,
    ) -> Self {
        assert!(n_layers >= 1, "Need at least 1 GAT layer");

        let mut layers = Vec::with_capacity(n_layers);

        if n_layers == 1 {
            // Single layer: no concatenation, output_dim per head.
            layers.push(GATLayer::new(input_dim, output_dim, n_heads, false, 0.2));
        } else {
            // First layer: concat heads.
            layers.push(GATLayer::new(input_dim, hidden_dim, n_heads, true, 0.2));

            // Middle layers: concat heads, input = n_heads * hidden_dim.
            for _ in 1..n_layers - 1 {
                let prev_out = layers.last().unwrap().output_dim();
                layers.push(GATLayer::new(prev_out, hidden_dim, n_heads, true, 0.2));
            }

            // Last layer: average heads, output = output_dim.
            let prev_out = layers.last().unwrap().output_dim();
            layers.push(GATLayer::new(prev_out, output_dim, n_heads, false, 0.2));
        }

        let final_dim = layers.last().unwrap().output_dim();
        let mut rng = rand::thread_rng();
        let limit = (6.0 / (final_dim as f64 + 1.0)).sqrt();
        let cls_w = DVector::from_fn(final_dim, |_, _| rng.gen_range(-limit..limit));
        let cls_b = 0.0;

        GATReasoner {
            layers,
            cls_w,
            cls_b,
            dropout_rate,
        }
    }

    /// Forward pass through the entire network.
    ///
    /// - `features`: (n_nodes, input_dim) — node feature matrix.
    /// - `adj`: Edge list.
    /// - `query_node`: Index of the node to classify.
    /// - `training`: If true, apply dropout.
    ///
    /// Returns (probability, cache).
    pub fn forward(
        &self,
        features: &DMatrix<f64>,
        adj: &[(usize, usize)],
        query_node: usize,
        training: bool,
    ) -> (f64, ReasonerForwardCache) {
        let mut rng = rand::thread_rng();
        let mut current = features.clone();
        let mut layer_inputs = Vec::with_capacity(self.layers.len());
        let mut layer_caches = Vec::with_capacity(self.layers.len());
        let mut dropout_masks = Vec::with_capacity(self.layers.len());

        for (l_idx, layer) in self.layers.iter().enumerate() {
            layer_inputs.push(current.clone());
            let (output, caches) = layer.forward(&current, adj);
            layer_caches.push(caches);

            // Apply dropout between layers (not after the last).
            if training && l_idx < self.layers.len() - 1 && self.dropout_rate > 0.0 {
                let n_elements = output.nrows() * output.ncols();
                let mask: Vec<bool> = (0..n_elements)
                    .map(|_| rng.gen::<f64>() > self.dropout_rate)
                    .collect();
                let scale = 1.0 / (1.0 - self.dropout_rate);
                current = DMatrix::from_fn(output.nrows(), output.ncols(), |i, j| {
                    let idx = i * output.ncols() + j;
                    if mask[idx] { output[(i, j)] * scale } else { 0.0 }
                });
                dropout_masks.push(Some(mask));
            } else {
                current = output;
                dropout_masks.push(None);
            }
        }

        // Extract features for the query node.
        let final_dim = current.ncols();
        let qn = query_node.min(current.nrows().saturating_sub(1));
        let final_features = DVector::from_fn(final_dim, |j, _| current[(qn, j)]);

        // Classification head: logit = cls_w^T * features + cls_b.
        let logit: f64 = self.cls_w.dot(&final_features) + self.cls_b;
        let prob = sigmoid(logit);

        let cache = ReasonerForwardCache {
            layer_inputs,
            layer_caches,
            dropout_masks,
            final_features,
            logit,
            prob,
        };

        (prob, cache)
    }

    /// Backward pass. Returns gradients for all layers and the classification head.
    ///
    /// - `target`: Ground truth label (0.0 or 1.0).
    /// - `cache`: Forward pass cache.
    /// - `adj`: Edge list (same as forward).
    /// - `query_node`: Same query node as forward.
    pub fn backward(
        &self,
        target: f64,
        cache: &ReasonerForwardCache,
        _adj: &[(usize, usize)],
        query_node: usize,
    ) -> (Vec<Vec<HeadGrad>>, ClsGrad) {
        // BCE loss gradient w.r.t. logit:
        // dL/d_logit = sigmoid(logit) - target
        let d_logit = cache.prob - target;

        // Gradient for classification head.
        let d_cls_w = &cache.final_features * d_logit;
        let d_cls_b = d_logit;

        // Gradient w.r.t. final features of query node.
        let d_final_features = &self.cls_w * d_logit;

        // Scatter gradient back to the full node matrix.
        let n_nodes = cache.layer_inputs[0].nrows();
        let qn = query_node.min(n_nodes.saturating_sub(1));
        let final_dim = self.layers.last().unwrap().output_dim();
        let mut d_current = DMatrix::zeros(n_nodes, final_dim);
        for j in 0..final_dim {
            d_current[(qn, j)] = d_final_features[j];
        }

        // Backprop through layers in reverse.
        let mut all_layer_grads = Vec::with_capacity(self.layers.len());
        for l_idx in (0..self.layers.len()).rev() {
            // Undo dropout mask if applied.
            if let Some(ref mask) = cache.dropout_masks[l_idx] {
                let scale = 1.0 / (1.0 - self.dropout_rate);
                let ncols = d_current.ncols();
                for i in 0..d_current.nrows() {
                    for j in 0..ncols {
                        let idx = i * ncols + j;
                        if !mask[idx] {
                            d_current[(i, j)] = 0.0;
                        } else {
                            d_current[(i, j)] *= scale;
                        }
                    }
                }
            }

            let (d_input, head_grads) = self.layers[l_idx].backward(
                &d_current,
                &cache.layer_inputs[l_idx],
                &cache.layer_caches[l_idx],
            );
            all_layer_grads.push(head_grads);
            d_current = d_input;
        }

        // Reverse so index 0 = first layer.
        all_layer_grads.reverse();

        let cls_grad = ClsGrad {
            d_w: d_cls_w,
            d_b: d_cls_b,
        };

        (all_layer_grads, cls_grad)
    }

    /// Apply gradients with SGD + weight decay + gradient clipping.
    pub fn apply_gradients(
        &mut self,
        mut layer_grads: Vec<Vec<HeadGrad>>,
        cls_grad: &ClsGrad,
        lr: f64,
        weight_decay: f64,
        max_grad_norm: f64,
    ) {
        // Compute total gradient norm.
        let mut total_norm_sq = 0.0;
        for grads in &layer_grads {
            total_norm_sq += GATLayer::grad_norm_sq(grads);
        }
        total_norm_sq += cls_grad.d_w.iter().map(|x| x * x).sum::<f64>();
        total_norm_sq += cls_grad.d_b * cls_grad.d_b;
        let total_norm = total_norm_sq.sqrt();

        // Clip if needed.
        if total_norm > max_grad_norm {
            let scale = max_grad_norm / total_norm;
            for grads in &mut layer_grads {
                GATLayer::scale_grads(grads, scale);
            }
            // cls grads are scaled below.
            let scaled_cls_w = &cls_grad.d_w * scale;
            let scaled_cls_b = cls_grad.d_b * scale;

            for (layer, grads) in self.layers.iter_mut().zip(layer_grads.iter()) {
                layer.apply_gradients(grads, lr, weight_decay);
            }
            self.cls_w = &self.cls_w * (1.0 - lr * weight_decay) - &scaled_cls_w * lr;
            self.cls_b -= lr * scaled_cls_b;
        } else {
            for (layer, grads) in self.layers.iter_mut().zip(layer_grads.iter()) {
                layer.apply_gradients(grads, lr, weight_decay);
            }
            self.cls_w = &self.cls_w * (1.0 - lr * weight_decay) - &cls_grad.d_w * lr;
            self.cls_b -= lr * cls_grad.d_b;
        }
    }

    /// Predict whether an edge should exist between two nodes.
    ///
    /// Constructs a minimal 2-node graph from the provided feature vectors,
    /// runs forward passes to obtain embeddings, then computes a dot-product
    /// similarity score passed through sigmoid to yield a probability.
    ///
    /// - `node_a_features`: Feature vector for node A (length = input_dim).
    /// - `node_b_features`: Feature vector for node B (length = input_dim).
    ///
    /// Returns probability in [0, 1] that an edge should exist between them.
    pub fn predict_link(&self, node_a_features: &[f64], node_b_features: &[f64]) -> f64 {
        let input_dim = node_a_features.len();
        assert_eq!(
            input_dim,
            node_b_features.len(),
            "Feature vectors must have the same dimension"
        );

        // Build a 2-node graph with bidirectional edges + self-loops.
        let mut flat = Vec::with_capacity(2 * input_dim);
        flat.extend_from_slice(node_a_features);
        flat.extend_from_slice(node_b_features);
        let features = DMatrix::from_row_slice(2, input_dim, &flat);
        let adj: Vec<(usize, usize)> = vec![(0, 1), (1, 0), (0, 0), (1, 1)];

        // Forward pass for node A (index 0) — inference mode (no dropout).
        let (_, cache_a) = self.forward(&features, &adj, 0, false);
        // Forward pass for node B (index 1).
        let (_, cache_b) = self.forward(&features, &adj, 1, false);

        // Dot-product similarity between the two node embeddings.
        let emb_a = &cache_a.final_features;
        let emb_b = &cache_b.final_features;
        let similarity: f64 = emb_a.dot(emb_b);

        sigmoid(similarity)
    }

    /// Serialize weights to JSON bytes.
    pub fn save_weights(&self) -> Result<Vec<u8>, String> {
        serde_json::to_vec(self).map_err(|e| format!("Serialization error: {}", e))
    }

    /// Deserialize weights from JSON bytes.
    pub fn load_weights(data: &[u8]) -> Result<Self, String> {
        serde_json::from_slice(data).map_err(|e| format!("Deserialization error: {}", e))
    }
}
