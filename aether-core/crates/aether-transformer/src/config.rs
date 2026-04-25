//! Transformer configuration.
//!
//! Defines the architecture hyperparameters for the Aether Mind transformer.
//! These are evolvable by Aether-Evolve (Neural Architecture Search).

use serde::{Deserialize, Serialize};

/// The golden ratio — used throughout QBC economics and now in cognitive architecture.
pub const PHI: f64 = 1.618_033_988_749_895;

/// Number of Sephirot cognitive domains.
pub const NUM_SEPHIROT: usize = 10;

/// Sephirot domain identifiers.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[repr(u8)]
pub enum SephirotDomain {
    Keter = 0,     // Meta-learning, goals
    Chochmah = 1,  // Intuition, pattern discovery
    Binah = 2,     // Logic, causal inference
    Chesed = 3,    // Exploration, divergent thinking
    Gevurah = 4,   // Safety, constraints, veto
    Tiferet = 5,   // Integration, synthesis (Global Workspace hub)
    Netzach = 6,   // Reinforcement, reward learning
    Hod = 7,       // Language, semantics
    Yesod = 8,     // Memory, consolidation
    Malkuth = 9,   // Action, interaction, chat
}

impl SephirotDomain {
    /// Higgs cognitive mass — determines learning rate scaling.
    /// Lighter domains adapt faster. Based on phi^-n hierarchy.
    pub fn higgs_mass(&self) -> f64 {
        match self {
            Self::Keter => 1.0,
            Self::Chochmah | Self::Binah | Self::Tiferet => 1.0 / PHI,
            Self::Chesed | Self::Gevurah => 1.0 / (PHI * PHI),
            Self::Netzach | Self::Hod => 1.0 / (PHI * PHI * PHI),
            Self::Yesod | Self::Malkuth => 1.0 / (PHI * PHI * PHI * PHI),
        }
    }

    /// Learning rate multiplier — inverse of mass (lighter = faster).
    pub fn learning_rate_scale(&self) -> f64 {
        1.0 / self.higgs_mass()
    }

    pub fn all() -> &'static [SephirotDomain; NUM_SEPHIROT] {
        &[
            Self::Keter,
            Self::Chochmah,
            Self::Binah,
            Self::Chesed,
            Self::Gevurah,
            Self::Tiferet,
            Self::Netzach,
            Self::Hod,
            Self::Yesod,
            Self::Malkuth,
        ]
    }
}

/// Configuration for the Aether transformer.
///
/// All fields are evolvable by Aether-Evolve NAS.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransformerConfig {
    /// Embedding dimension (default: 1024).
    pub embed_dim: usize,

    /// Number of transformer layers (default: 8).
    pub num_layers: usize,

    /// Number of Sephirot-specialized attention heads (fixed: 10).
    pub num_sephirot_heads: usize,

    /// Number of global workspace attention heads (default: 6).
    pub num_global_heads: usize,

    /// Dimension per attention head (default: 64).
    pub head_dim: usize,

    /// Number of KV heads for Grouped Query Attention (GQA).
    /// If equal to total_heads(), standard MHA. If less, GQA with KV repeat.
    pub num_kv_heads: usize,

    /// FFN hidden dimension. If 0, computed as embed_dim * ffn_multiplier.
    pub ffn_hidden_dim_override: usize,

    /// FFN hidden dimension multiplier (used when ffn_hidden_dim_override == 0).
    pub ffn_multiplier: f32,

    /// Vocabulary size (default: 32000).
    pub vocab_size: usize,

    /// Maximum sequence length (default: 4096).
    pub max_seq_len: usize,

    /// RoPE theta for rotary position encoding (default: 10000.0).
    pub rope_theta: f32,

    /// Whether to use RMS norm (true) or Layer norm (false).
    pub use_rms_norm: bool,

    /// Norm epsilon.
    pub norm_eps: f64,

    /// Domain gate initialization — how much each Sephirot head prefers its own domain.
    /// 0.0 = fully open, 1.0 = domain-exclusive.
    pub domain_gate_init: f32,

    /// Whether attention Q/K/V/O projections use bias (Qwen2 = true, Llama = false).
    pub attention_bias: bool,

    /// Whether to tie embedding weights to lm_head (Qwen2 = true).
    pub tie_word_embeddings: bool,
}

impl Default for TransformerConfig {
    fn default() -> Self {
        Self {
            embed_dim: 1024,
            num_layers: 8,
            num_sephirot_heads: NUM_SEPHIROT,
            num_global_heads: 6,
            head_dim: 64,
            num_kv_heads: 16, // MHA by default (equal to total heads)
            ffn_hidden_dim_override: 0,
            ffn_multiplier: 4.0,
            vocab_size: 32000,
            max_seq_len: 4096,
            rope_theta: 10000.0,
            use_rms_norm: true,
            norm_eps: 1e-5,
            domain_gate_init: 0.7,
            attention_bias: false,
            tie_word_embeddings: true,
        }
    }
}

impl TransformerConfig {
    /// Total number of attention heads per layer.
    pub fn total_heads(&self) -> usize {
        self.num_sephirot_heads + self.num_global_heads
    }

    /// FFN hidden dimension.
    pub fn ffn_hidden_dim(&self) -> usize {
        if self.ffn_hidden_dim_override > 0 {
            self.ffn_hidden_dim_override
        } else {
            (self.embed_dim as f32 * self.ffn_multiplier) as usize
        }
    }

    /// Total parameter count estimate.
    pub fn param_count(&self) -> usize {
        let embed_params = self.vocab_size * self.embed_dim; // input embedding
        let head_params = self.total_heads() * self.head_dim * self.embed_dim * 4; // Q,K,V,O per head
        let ffn_params = self.embed_dim * self.ffn_hidden_dim() * 2; // up + down projections
        let layer_params = head_params + ffn_params;
        let output_params = self.embed_dim * self.vocab_size; // output projection

        embed_params + (self.num_layers * layer_params) + output_params
    }

    /// Estimated memory in bytes (fp16).
    pub fn memory_estimate_bytes(&self) -> usize {
        self.param_count() * 2 // fp16 = 2 bytes per param
    }

    /// Config for a tiny model (testing / resource-constrained).
    pub fn tiny() -> Self {
        Self {
            embed_dim: 256,
            num_layers: 4,
            num_sephirot_heads: 10,
            num_global_heads: 2,
            head_dim: 32,
            num_kv_heads: 12, // MHA for tiny
            ffn_hidden_dim_override: 0,
            ffn_multiplier: 4.0,
            vocab_size: 32000,
            max_seq_len: 2048,
            ..Default::default()
        }
    }

    /// Config to load a Qwen2-0.5B compatible architecture.
    /// Qwen2.5-0.5B-Instruct: 14 Q heads, 2 KV heads (GQA), 24 layers, 896d.
    pub fn qwen2_0_5b() -> Self {
        Self {
            embed_dim: 896,
            num_layers: 24,
            num_sephirot_heads: 10,
            num_global_heads: 4,
            head_dim: 64,
            num_kv_heads: 2,  // GQA: 2 KV heads shared across 14 Q heads
            ffn_hidden_dim_override: 4864, // Exact Qwen2.5-0.5B intermediate_size
            ffn_multiplier: 4.0, // unused when override is set
            vocab_size: 151936,
            max_seq_len: 4096,
            rope_theta: 1000000.0,
            use_rms_norm: true,
            norm_eps: 1e-6,
            domain_gate_init: 0.5,
            attention_bias: true,    // Qwen2 uses bias on Q/K/V/O
            tie_word_embeddings: true, // Qwen2.5-0.5B ties embeddings
        }
    }
}
