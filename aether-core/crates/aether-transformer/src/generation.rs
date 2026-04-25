//! Text generation for the Aether transformer.
//!
//! Autoregressive token-by-token generation with temperature sampling,
//! top-k, and repetition penalty. Extracts attention weights for
//! consciousness monitoring during generation.

use candle_core::{DType, Result, Tensor};

use crate::model::AetherTransformer;

/// Sampling parameters for text generation.
#[derive(Debug, Clone)]
pub struct SamplingParams {
    pub temperature: f32,
    pub top_k: usize,
    pub top_p: f32,
    pub repetition_penalty: f32,
    pub max_tokens: usize,
    pub stop_tokens: Vec<u32>,
}

impl Default for SamplingParams {
    fn default() -> Self {
        Self {
            temperature: 0.7,
            top_k: 50,
            top_p: 0.9,
            repetition_penalty: 1.1,
            max_tokens: 512,
            stop_tokens: vec![],
        }
    }
}

/// Result of generation including attention data for consciousness.
pub struct GenerationResult {
    pub tokens: Vec<u32>,
    /// Attention weights from the last forward pass (one per layer).
    /// Each tensor: (1, num_heads, seq_len, kv_len).
    pub last_attention_weights: Vec<Tensor>,
}

/// Generate tokens from the AetherTransformer with consciousness hooks.
pub fn generate(
    model: &mut AetherTransformer,
    prompt_tokens: &[u32],
    params: &SamplingParams,
) -> Result<GenerationResult> {
    let device = model.device().clone();
    model.clear_kv_cache();

    let mut all_tokens: Vec<u32> = prompt_tokens.to_vec();
    let mut generated: Vec<u32> = Vec::new();

    // Prefill: process all prompt tokens (collect attention from prefill for consciousness)
    let prompt_tensor = Tensor::new(prompt_tokens, &device)?.unsqueeze(0)?;
    let (logits, prefill_attn) = model.forward_last_token(&prompt_tensor, 0, true)?;

    let mut token = sample_token(&logits, params, &all_tokens)?;
    generated.push(token);
    all_tokens.push(token);

    if params.stop_tokens.contains(&token) {
        return Ok(GenerationResult {
            tokens: generated,
            last_attention_weights: prefill_attn,
        });
    }

    // Decode: one token at a time with KV cache (no attention collection — fast)
    let prompt_len = prompt_tokens.len();
    for i in 0..(params.max_tokens - 1) {
        let input = Tensor::new(&[token], &device)?.unsqueeze(0)?;
        let (logits, _) = model.forward_last_token(&input, prompt_len + i, false)?;

        token = sample_token(&logits, params, &all_tokens)?;
        generated.push(token);
        all_tokens.push(token);

        if params.stop_tokens.contains(&token) {
            break;
        }
    }

    // Use prefill attention for consciousness (has full prompt context)
    Ok(GenerationResult {
        tokens: generated,
        last_attention_weights: prefill_attn,
    })
}

/// Sample a single token from logits.
fn sample_token(
    logits: &Tensor,
    params: &SamplingParams,
    all_tokens: &[u32],
) -> Result<u32> {
    let logits = logits.to_dtype(DType::F32)?.squeeze(0)?;

    // Repetition penalty
    let logits = if params.repetition_penalty != 1.0 {
        let mut v: Vec<f32> = logits.to_vec1()?;
        for &tok in all_tokens {
            let idx = tok as usize;
            if idx < v.len() {
                if v[idx] > 0.0 {
                    v[idx] /= params.repetition_penalty;
                } else {
                    v[idx] *= params.repetition_penalty;
                }
            }
        }
        Tensor::new(v.as_slice(), logits.device())?
    } else {
        logits
    };

    // Greedy
    if params.temperature == 0.0 {
        return logits.argmax(0)?.to_scalar::<u32>();
    }

    // Temperature
    let logits = (&logits / params.temperature as f64)?;

    // Top-k
    let logits = if params.top_k > 0 {
        let mut v: Vec<f32> = logits.to_vec1()?;
        let mut indexed: Vec<(usize, f32)> = v.iter().copied().enumerate().collect();
        indexed.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        let threshold = if params.top_k < indexed.len() {
            indexed[params.top_k].1
        } else {
            f32::NEG_INFINITY
        };
        for val in &mut v {
            if *val < threshold {
                *val = f32::NEG_INFINITY;
            }
        }
        Tensor::new(v.as_slice(), logits.device())?
    } else {
        logits
    };

    // Softmax + sample
    let probs = candle_nn::ops::softmax_last_dim(&logits.unsqueeze(0)?)?.squeeze(0)?;
    let probs_vec: Vec<f32> = probs.to_vec1()?;

    use rand::Rng;
    let mut rng = rand::thread_rng();
    let r: f32 = rng.gen();
    let mut cumsum = 0.0;
    for (i, &p) in probs_vec.iter().enumerate() {
        cumsum += p;
        if cumsum >= r {
            return Ok(i as u32);
        }
    }
    Ok((probs_vec.len() - 1) as u32)
}
