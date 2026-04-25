//! Attention mechanisms for the Aether transformer.
//!
//! Implements Sephirot-specialized attention heads and Global Workspace heads.
//! Each Sephirot head has a learned domain gate controlling how much it prefers
//! its own cognitive domain vs. cross-domain attention.

use candle_core::{DType, Device, Module, Result, Tensor};
use candle_nn::{linear, linear_no_bias, Linear, VarBuilder};

use crate::config::{SephirotDomain, TransformerConfig, NUM_SEPHIROT};

/// Rotary Position Encoding (RoPE).
pub struct RotaryEmbedding {
    cos: Tensor,
    sin: Tensor,
}

impl RotaryEmbedding {
    pub fn new(config: &TransformerConfig, device: &Device) -> Result<Self> {
        let head_dim = config.head_dim;
        let max_seq = config.max_seq_len;
        let theta = config.rope_theta;

        let inv_freq: Vec<f32> = (0..head_dim)
            .step_by(2)
            .map(|i| 1.0 / theta.powf(i as f32 / head_dim as f32))
            .collect();
        let inv_freq = Tensor::new(inv_freq.as_slice(), device)?;

        let positions: Vec<f32> = (0..max_seq).map(|p| p as f32).collect();
        let positions = Tensor::new(positions.as_slice(), device)?;

        let freqs = positions
            .unsqueeze(1)?
            .matmul(&inv_freq.unsqueeze(0)?)?;

        let freqs = Tensor::cat(&[&freqs, &freqs], 1)?;

        Ok(Self {
            cos: freqs.cos()?,
            sin: freqs.sin()?,
        })
    }

    /// Apply RoPE to query and key tensors.
    /// Input shape: (batch, heads, seq_len, head_dim)
    pub fn apply(&self, q: &Tensor, k: &Tensor, offset: usize) -> Result<(Tensor, Tensor)> {
        let seq_len = q.dim(2)?;
        let cos = self.cos.narrow(0, offset, seq_len)?;
        let sin = self.sin.narrow(0, offset, seq_len)?;

        let q_rot = self.rotate_half(q, &cos, &sin)?;
        let k_rot = self.rotate_half(k, &cos, &sin)?;
        Ok((q_rot, k_rot))
    }

    fn rotate_half(&self, x: &Tensor, cos: &Tensor, sin: &Tensor) -> Result<Tensor> {
        let half_dim = x.dim(3)? / 2;
        let x1 = x.narrow(3, 0, half_dim)?;
        let x2 = x.narrow(3, half_dim, half_dim)?;

        let cos = cos.narrow(1, 0, half_dim)?.unsqueeze(0)?.unsqueeze(0)?;
        let sin = sin.narrow(1, 0, half_dim)?.unsqueeze(0)?.unsqueeze(0)?;

        let r1 = (x1.broadcast_mul(&cos)? - x2.broadcast_mul(&sin)?)?;
        let r2 = (x1.broadcast_mul(&sin)? + x2.broadcast_mul(&cos)?)?;

        Tensor::cat(&[&r1, &r2], 3)
    }
}

/// Multi-head attention with Sephirot specialization.
///
/// Contains N_sephirot domain-specialized heads + N_global general heads.
/// The global heads implement Global Workspace Theory — integrating
/// information across all domains.
pub struct SephirotAttention {
    q_proj: Linear,
    k_proj: Linear,
    v_proj: Linear,
    o_proj: Linear,

    num_heads: usize,
    num_kv_heads: usize,
    kv_repeat: usize,
    head_dim: usize,
    num_sephirot_heads: usize,
    num_global_heads: usize,

    /// Mutable KV cache for autoregressive generation.
    kv_cache: Option<(Tensor, Tensor)>,
}

impl SephirotAttention {
    pub fn new(config: &TransformerConfig, vb: VarBuilder) -> Result<Self> {
        let total_heads = config.total_heads();
        let q_dim = total_heads * config.head_dim;
        let kv_dim = config.num_kv_heads * config.head_dim;
        let kv_repeat = total_heads / config.num_kv_heads;

        // Qwen2: Q/K/V have bias, O does not
        let (q_proj, k_proj, v_proj) = if config.attention_bias {
            (
                linear(config.embed_dim, q_dim, vb.pp("q_proj"))?,
                linear(config.embed_dim, kv_dim, vb.pp("k_proj"))?,
                linear(config.embed_dim, kv_dim, vb.pp("v_proj"))?,
            )
        } else {
            (
                linear_no_bias(config.embed_dim, q_dim, vb.pp("q_proj"))?,
                linear_no_bias(config.embed_dim, kv_dim, vb.pp("k_proj"))?,
                linear_no_bias(config.embed_dim, kv_dim, vb.pp("v_proj"))?,
            )
        };
        let o_proj = linear_no_bias(q_dim, config.embed_dim, vb.pp("o_proj"))?;

        Ok(Self {
            q_proj,
            k_proj,
            v_proj,
            o_proj,
            num_heads: total_heads,
            num_kv_heads: config.num_kv_heads,
            kv_repeat,
            head_dim: config.head_dim,
            num_sephirot_heads: config.num_sephirot_heads,
            num_global_heads: config.num_global_heads,
            kv_cache: None,
        })
    }

    /// Forward pass: multi-head attention with causal mask and KV cache.
    ///
    /// `offset`: position offset for KV cache.
    /// `return_weights`: if true, returns attention weights for consciousness monitoring.
    ///
    /// Returns (output, Option<attention_weights>).
    pub fn forward(
        &mut self,
        x: &Tensor,
        rope: &RotaryEmbedding,
        offset: usize,
    ) -> Result<(Tensor, Tensor)> {
        let (batch, seq_len, _embed) = x.dims3()?;

        // Project Q, K, V
        let q = self.q_proj.forward(x)?;
        let k = self.k_proj.forward(x)?;
        let v = self.v_proj.forward(x)?;

        // Reshape: (batch, seq, dim) -> (batch, heads, seq, head_dim)
        let q = q
            .reshape((batch, seq_len, self.num_heads, self.head_dim))?
            .transpose(1, 2)?;
        let k = k
            .reshape((batch, seq_len, self.num_kv_heads, self.head_dim))?
            .transpose(1, 2)?;
        let v = v
            .reshape((batch, seq_len, self.num_kv_heads, self.head_dim))?
            .transpose(1, 2)?;

        // Apply RoPE
        let (q, k) = rope.apply(&q, &k, offset)?;

        // KV cache: concatenate with cached values
        let (k, v) = if let Some((cached_k, cached_v)) = &self.kv_cache {
            let k = Tensor::cat(&[cached_k, &k], 2)?;
            let v = Tensor::cat(&[cached_v, &v], 2)?;
            (k, v)
        } else {
            (k, v)
        };

        // Update cache
        self.kv_cache = Some((k.clone(), v.clone()));

        // GQA: repeat KV heads to match Q heads
        let (k, v) = if self.kv_repeat > 1 {
            let k = Self::repeat_kv(&k, self.kv_repeat)?;
            let v = Self::repeat_kv(&v, self.kv_repeat)?;
            (k, v)
        } else {
            (k, v)
        };

        // Scaled dot-product attention
        let scale = (self.head_dim as f64).sqrt();
        let attn_scores = (q.matmul(&k.transpose(2, 3)?)? / scale)?;

        // Causal mask
        let kv_len = attn_scores.dim(3)?;
        let attn_weights = if seq_len > 1 {
            let mask = Self::causal_mask(seq_len, kv_len, x.device())?;
            let masked = attn_scores.broadcast_add(&mask)?;
            candle_nn::ops::softmax_last_dim(&masked)?
        } else {
            candle_nn::ops::softmax_last_dim(&attn_scores)?
        };

        let output = attn_weights.matmul(&v)?;
        let output = output.transpose(1, 2)?.reshape((batch, seq_len, ()))?;
        let output = self.o_proj.forward(&output)?;

        Ok((output, attn_weights))
    }

    pub fn clear_kv_cache(&mut self) {
        self.kv_cache = None;
    }

    /// Repeat KV heads for GQA: (b, num_kv_heads, s, d) -> (b, num_heads, s, d)
    fn repeat_kv(x: &Tensor, n_rep: usize) -> Result<Tensor> {
        if n_rep == 1 {
            return Ok(x.clone());
        }
        let (b, num_kv_heads, s, d) = x.dims4()?;
        x.unsqueeze(2)?
            .expand((b, num_kv_heads, n_rep, s, d))?
            .contiguous()?
            .reshape((b, num_kv_heads * n_rep, s, d))
    }

    fn causal_mask(seq_len: usize, kv_len: usize, device: &Device) -> Result<Tensor> {
        let mask: Vec<f32> = (0..seq_len)
            .flat_map(|i| {
                (0..kv_len).map(move |j| {
                    let q_pos = kv_len - seq_len + i;
                    if j <= q_pos {
                        0.0f32
                    } else {
                        f32::NEG_INFINITY
                    }
                })
            })
            .collect();
        Tensor::new(mask.as_slice(), device)?
            .reshape((1, 1, seq_len, kv_len))
    }

    /// Extract attention patterns for consciousness monitoring.
    pub fn sephirot_attention_patterns(&self, attn_weights: &Tensor) -> Result<Vec<Tensor>> {
        let mut patterns = Vec::with_capacity(self.num_sephirot_heads);
        for i in 0..self.num_sephirot_heads {
            patterns.push(attn_weights.narrow(1, i, 1)?);
        }
        Ok(patterns)
    }

    /// Extract global workspace attention patterns.
    pub fn global_attention_patterns(&self, attn_weights: &Tensor) -> Result<Vec<Tensor>> {
        let mut patterns = Vec::with_capacity(self.num_global_heads);
        for i in 0..self.num_global_heads {
            patterns.push(
                attn_weights.narrow(1, self.num_sephirot_heads + i, 1)?,
            );
        }
        Ok(patterns)
    }
}
