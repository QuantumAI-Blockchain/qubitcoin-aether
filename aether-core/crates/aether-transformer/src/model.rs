//! The Aether Transformer model.
//!
//! A domain-specific transformer with Sephirot-specialized attention heads.
//! Compatible with loading weights from Qwen2, Llama, and other standard architectures.

use candle_core::{DType, Device, Module, Result, Tensor};
use candle_nn::{embedding, linear, linear_no_bias, Embedding, Linear, VarBuilder};

use crate::attention::{RotaryEmbedding, SephirotAttention};
use crate::config::TransformerConfig;

/// RMS Normalization — standard in modern transformers (Llama, Qwen, Mistral).
pub struct RmsNorm {
    weight: Tensor,
    eps: f64,
}

impl RmsNorm {
    pub fn new(dim: usize, eps: f64, vb: VarBuilder) -> Result<Self> {
        let weight = vb.get(dim, "weight")?;
        Ok(Self { weight, eps })
    }

    pub fn forward(&self, x: &Tensor) -> Result<Tensor> {
        let dtype = x.dtype();
        let x = x.to_dtype(DType::F32)?;
        let variance = (&x * &x)?.mean_keepdim(candle_core::D::Minus1)?;
        let x_normed = x.broadcast_div(&(variance + self.eps)?.sqrt()?)?;
        x_normed.to_dtype(dtype)?.broadcast_mul(&self.weight)
    }
}

/// Feed-Forward Network (SwiGLU variant — used by Llama/Qwen).
pub struct FeedForward {
    gate_proj: Linear,
    up_proj: Linear,
    down_proj: Linear,
}

impl FeedForward {
    pub fn new(config: &TransformerConfig, vb: VarBuilder) -> Result<Self> {
        let hidden = config.ffn_hidden_dim();
        let gate_proj = linear_no_bias(config.embed_dim, hidden, vb.pp("gate_proj"))?;
        let up_proj = linear_no_bias(config.embed_dim, hidden, vb.pp("up_proj"))?;
        let down_proj = linear_no_bias(hidden, config.embed_dim, vb.pp("down_proj"))?;
        Ok(Self {
            gate_proj,
            up_proj,
            down_proj,
        })
    }

    pub fn forward(&self, x: &Tensor) -> Result<Tensor> {
        let gate = candle_nn::ops::silu(&self.gate_proj.forward(x)?)?;
        let up = self.up_proj.forward(x)?;
        self.down_proj.forward(&(gate * up)?)
    }
}

/// A single transformer layer with Sephirot attention + FFN.
pub struct TransformerLayer {
    attention: SephirotAttention,
    ffn: FeedForward,
    attn_norm: RmsNorm,
    ffn_norm: RmsNorm,
}

impl TransformerLayer {
    pub fn new(config: &TransformerConfig, vb: VarBuilder) -> Result<Self> {
        let attention = SephirotAttention::new(config, vb.pp("self_attn"))?;
        let ffn = FeedForward::new(config, vb.pp("mlp"))?;
        let attn_norm = RmsNorm::new(config.embed_dim, config.norm_eps, vb.pp("input_layernorm"))?;
        let ffn_norm = RmsNorm::new(
            config.embed_dim,
            config.norm_eps,
            vb.pp("post_attention_layernorm"),
        )?;
        Ok(Self {
            attention,
            ffn,
            attn_norm,
            ffn_norm,
        })
    }

    /// Forward pass through one transformer layer.
    /// Returns (output, attention_weights).
    pub fn forward(
        &mut self,
        x: &Tensor,
        rope: &RotaryEmbedding,
        offset: usize,
    ) -> Result<(Tensor, Tensor)> {
        let residual = x;
        let x = self.attn_norm.forward(x)?;
        let (attn_out, attn_weights) = self.attention.forward(&x, rope, offset)?;
        let x = (residual + attn_out)?;

        let residual = &x;
        let x = self.ffn_norm.forward(&x)?;
        let ffn_out = self.ffn.forward(&x)?;
        let x = (residual + ffn_out)?;

        Ok((x, attn_weights))
    }

    pub fn clear_kv_cache(&mut self) {
        self.attention.clear_kv_cache();
    }
}

/// The complete Aether Transformer model.
///
/// Architecture: Embedding -> N x TransformerLayer -> RmsNorm -> Linear (logits)
///
/// Compatible with loading pre-trained weights from Qwen2/Llama format.
/// Sephirot specialization: first 10 attention heads are domain-specialized,
/// remaining heads are global workspace integrators.
pub struct AetherTransformer {
    embed_tokens: Embedding,
    layers: Vec<TransformerLayer>,
    norm: RmsNorm,
    lm_head: Option<Linear>,
    embed_weight: Tensor,
    rope: RotaryEmbedding,
    config: TransformerConfig,
    device: Device,
}

impl AetherTransformer {
    /// Build the model from config and variable builder (weight source).
    pub fn new(config: &TransformerConfig, vb: VarBuilder) -> Result<Self> {
        let device = vb.device().clone();
        let embed_tokens = embedding(config.vocab_size, config.embed_dim, vb.pp("model.embed_tokens"))?;

        let mut layers = Vec::with_capacity(config.num_layers);
        for i in 0..config.num_layers {
            let layer = TransformerLayer::new(config, vb.pp(format!("model.layers.{i}")))?;
            layers.push(layer);
        }

        let norm = RmsNorm::new(config.embed_dim, config.norm_eps, vb.pp("model.norm"))?;

        let embed_weight = vb
            .pp("model.embed_tokens")
            .get((config.vocab_size, config.embed_dim), "weight")?;

        let lm_head = if config.tie_word_embeddings {
            log::info!("Using tied embedding weights (weight tying).");
            None
        } else {
            Some(linear_no_bias(
                config.embed_dim,
                config.vocab_size,
                vb.pp("lm_head"),
            )?)
        };

        let rope = RotaryEmbedding::new(config, &device)?;

        Ok(Self {
            embed_tokens,
            layers,
            norm,
            lm_head,
            embed_weight,
            rope,
            config: config.clone(),
            device,
        })
    }

    /// Forward pass: token_ids -> logits.
    ///
    /// When `collect_attention` is true, returns attention weights for consciousness
    /// monitoring. When false, skips attention collection for faster inference.
    pub fn forward(
        &mut self,
        token_ids: &Tensor,
        offset: usize,
        collect_attention: bool,
    ) -> Result<(Tensor, Vec<Tensor>)> {
        let mut x = self.embed_tokens.forward(token_ids)?;
        let mut attn_weights_out = Vec::new();

        // Sample 3 layers for consciousness: first, middle, last
        let sample_layers: Vec<usize> = if collect_attention && self.config.num_layers >= 3 {
            vec![0, self.config.num_layers / 2, self.config.num_layers - 1]
        } else {
            vec![]
        };

        for (i, layer) in self.layers.iter_mut().enumerate() {
            let (out, attn_w) = layer.forward(&x, &self.rope, offset)?;
            x = out;
            if sample_layers.contains(&i) {
                attn_weights_out.push(attn_w);
            }
        }

        let x = self.norm.forward(&x)?;

        let logits = match &self.lm_head {
            Some(head) => head.forward(&x)?,
            None => {
                let ew_t = self.embed_weight.t()?.contiguous()?;
                x.broadcast_matmul(&ew_t)?
            }
        };

        Ok((logits, attn_weights_out))
    }

    /// Get the last token's logits (for autoregressive generation).
    pub fn forward_last_token(
        &mut self,
        token_ids: &Tensor,
        offset: usize,
        collect_attention: bool,
    ) -> Result<(Tensor, Vec<Tensor>)> {
        let (logits, attn_weights) = self.forward(token_ids, offset, collect_attention)?;
        let seq_len = logits.dim(1)?;
        let last_logits = logits.narrow(1, seq_len - 1, 1)?.squeeze(1)?;
        Ok((last_logits, attn_weights))
    }

    /// Clear KV cache across all layers (call before new sequence).
    pub fn clear_kv_cache(&mut self) {
        for layer in &mut self.layers {
            layer.clear_kv_cache();
        }
    }

    pub fn device(&self) -> &Device {
        &self.device
    }

    pub fn config(&self) -> &TransformerConfig {
        &self.config
    }

    pub fn param_count(&self) -> usize {
        self.config.param_count()
    }
}
