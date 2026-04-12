//! Embedder — Text embedding system for the Aether Tree.
//!
//! Provides a trait-based embedding interface with two implementations:
//!
//! - **SimpleEmbedder**: A character n-gram hash embedder that works without any
//!   model files. Uses 3-grams hashed to a fixed-size vector (384 dims by default),
//!   normalized to unit vectors. Gives reasonable semantic similarity for keyword overlap.
//!
//! - **OnnxEmbedder** (future, feature-gated behind `onnx`): Wraps candle for running
//!   ONNX embedding models like all-MiniLM-L6-v2.
//!
//! Thread safety: `Arc<dyn Embedder + Send + Sync>` is the canonical sharing pattern.

use pyo3::prelude::*;
use sha2::{Digest, Sha256};

// ---------------------------------------------------------------------------
// Embedder trait
// ---------------------------------------------------------------------------

/// Trait for text embedding backends.
///
/// Implementations must be thread-safe (Send + Sync).
pub trait Embedder: Send + Sync {
    /// Embed a single text string into a dense vector.
    fn embed(&self, text: &str) -> Vec<f64>;

    /// Embed a batch of texts. Default implementation calls `embed` for each.
    fn embed_batch(&self, texts: &[&str]) -> Vec<Vec<f64>> {
        texts.iter().map(|t| self.embed(t)).collect()
    }

    /// The output dimension of this embedder.
    fn dim(&self) -> usize;

    /// Name of this embedder (for logging/diagnostics).
    fn name(&self) -> &str;
}

// ---------------------------------------------------------------------------
// SimpleEmbedder — character n-gram hash embedder (no model files needed)
// ---------------------------------------------------------------------------

/// A lightweight text embedder using character n-grams hashed to a fixed-size vector.
///
/// Algorithm:
/// 1. Lowercase the input text, strip non-alphanumeric (keep spaces).
/// 2. Generate character n-grams (default 3-grams) from the cleaned text.
/// 3. Hash each n-gram with SHA-256 and map to a bucket in [0, dim).
/// 4. Accumulate TF-IDF-like weights: each n-gram increments its bucket.
/// 5. Apply sublinear TF (log(1 + count)) to dampen high-frequency n-grams.
/// 6. L2-normalize to unit vector.
///
/// This gives reasonable cosine similarity for texts sharing character patterns,
/// without requiring any model files or external dependencies.
#[pyclass]
#[derive(Clone)]
pub struct SimpleEmbedder {
    /// Output vector dimension.
    dim: usize,
    /// Character n-gram size.
    ngram_size: usize,
}

#[pymethods]
impl SimpleEmbedder {
    /// Create a new SimpleEmbedder.
    ///
    /// # Arguments
    /// - `dim`: Output embedding dimension (default 384).
    /// - `ngram_size`: Character n-gram size (default 3).
    #[new]
    #[pyo3(signature = (dim = 384, ngram_size = 3))]
    pub fn new(dim: usize, ngram_size: usize) -> Self {
        SimpleEmbedder {
            dim: dim.max(1),
            ngram_size: ngram_size.max(1),
        }
    }

    /// Embed text into a dense vector (Python interface).
    pub fn embed_text(&self, text: &str) -> Vec<f64> {
        self.embed(text)
    }

    /// Embed a batch of texts (Python interface).
    pub fn embed_text_batch(&self, texts: Vec<String>) -> Vec<Vec<f64>> {
        let refs: Vec<&str> = texts.iter().map(|s| s.as_str()).collect();
        self.embed_batch(&refs)
    }

    /// Output dimension.
    #[getter]
    pub fn dimension(&self) -> usize {
        self.dim
    }

    /// N-gram size.
    #[getter]
    pub fn ngram_size_value(&self) -> usize {
        self.ngram_size
    }

    /// Compute cosine similarity between two texts.
    pub fn similarity(&self, text_a: &str, text_b: &str) -> f64 {
        let emb_a = self.embed(text_a);
        let emb_b = self.embed(text_b);
        cosine_sim(&emb_a, &emb_b)
    }

    fn __repr__(&self) -> String {
        format!(
            "SimpleEmbedder(dim={}, ngram_size={})",
            self.dim, self.ngram_size
        )
    }
}

impl Embedder for SimpleEmbedder {
    fn embed(&self, text: &str) -> Vec<f64> {
        let cleaned = clean_text(text);
        if cleaned.is_empty() {
            return vec![0.0; self.dim];
        }

        // Generate character n-grams and hash to buckets
        let mut counts = vec![0.0_f64; self.dim];
        let ngrams = char_ngrams(&cleaned, self.ngram_size);

        if ngrams.is_empty() {
            // Text shorter than ngram_size — hash the whole text
            let bucket = hash_to_bucket(cleaned.as_bytes(), self.dim);
            counts[bucket] = 1.0;
        } else {
            for ngram in &ngrams {
                let bucket = hash_to_bucket(ngram.as_bytes(), self.dim);
                counts[bucket] += 1.0;
            }
        }

        // Also add word-level unigrams for better semantic separation
        for word in cleaned.split_whitespace() {
            if word.len() >= 2 {
                let bucket = hash_to_bucket_with_seed(word.as_bytes(), self.dim, 0x9e3779b9);
                counts[bucket] += 0.5; // Lower weight than character n-grams
            }
        }

        // Sublinear TF: log(1 + count)
        for c in counts.iter_mut() {
            if *c > 0.0 {
                *c = (1.0 + *c).ln();
            }
        }

        // L2 normalize to unit vector
        l2_normalize(&mut counts);
        counts
    }

    fn embed_batch(&self, texts: &[&str]) -> Vec<Vec<f64>> {
        texts.iter().map(|t| self.embed(t)).collect()
    }

    fn dim(&self) -> usize {
        self.dim
    }

    fn name(&self) -> &str {
        "SimpleEmbedder"
    }
}

// ---------------------------------------------------------------------------
// IDF-weighted embedder (optional enhancement)
// ---------------------------------------------------------------------------

/// An enhanced embedder that accumulates IDF weights from a corpus.
///
/// Uses the same n-gram hashing as SimpleEmbedder but weights n-grams by their
/// inverse document frequency, giving rarer n-grams higher importance.
#[pyclass]
pub struct IDFEmbedder {
    base: SimpleEmbedder,
    /// bucket -> number of documents containing this bucket
    doc_freq: Vec<f64>,
    /// Total number of documents seen
    total_docs: f64,
}

#[pymethods]
impl IDFEmbedder {
    /// Create a new IDF-weighted embedder.
    #[new]
    #[pyo3(signature = (dim = 384, ngram_size = 3))]
    pub fn new(dim: usize, ngram_size: usize) -> Self {
        let base = SimpleEmbedder::new(dim, ngram_size);
        let actual_dim = base.dim;
        IDFEmbedder {
            base,
            doc_freq: vec![0.0; actual_dim],
            total_docs: 0.0,
        }
    }

    /// Feed a document to update IDF statistics.
    pub fn fit_document(&mut self, text: &str) {
        let cleaned = clean_text(text);
        let ngrams = char_ngrams(&cleaned, self.base.ngram_size);

        // Track which buckets this document hits (deduplicated)
        let mut seen_buckets = std::collections::HashSet::new();
        for ngram in &ngrams {
            let bucket = hash_to_bucket(ngram.as_bytes(), self.base.dim);
            seen_buckets.insert(bucket);
        }
        for word in cleaned.split_whitespace() {
            if word.len() >= 2 {
                let bucket =
                    hash_to_bucket_with_seed(word.as_bytes(), self.base.dim, 0x9e3779b9);
                seen_buckets.insert(bucket);
            }
        }

        for bucket in seen_buckets {
            self.doc_freq[bucket] += 1.0;
        }
        self.total_docs += 1.0;
    }

    /// Fit multiple documents at once.
    pub fn fit_documents(&mut self, texts: Vec<String>) {
        for text in &texts {
            self.fit_document(text);
        }
    }

    /// Embed text using TF-IDF weighting (Python interface).
    pub fn embed_text(&self, text: &str) -> Vec<f64> {
        self.embed(text)
    }

    /// Number of documents fitted.
    #[getter]
    pub fn total_documents(&self) -> f64 {
        self.total_docs
    }

    fn __repr__(&self) -> String {
        format!(
            "IDFEmbedder(dim={}, ngram_size={}, docs={})",
            self.base.dim, self.base.ngram_size, self.total_docs
        )
    }
}

impl Embedder for IDFEmbedder {
    fn embed(&self, text: &str) -> Vec<f64> {
        let cleaned = clean_text(text);
        if cleaned.is_empty() {
            return vec![0.0; self.base.dim];
        }

        let mut counts = vec![0.0_f64; self.base.dim];
        let ngrams = char_ngrams(&cleaned, self.base.ngram_size);

        if ngrams.is_empty() {
            let bucket = hash_to_bucket(cleaned.as_bytes(), self.base.dim);
            counts[bucket] = 1.0;
        } else {
            for ngram in &ngrams {
                let bucket = hash_to_bucket(ngram.as_bytes(), self.base.dim);
                counts[bucket] += 1.0;
            }
        }

        for word in cleaned.split_whitespace() {
            if word.len() >= 2 {
                let bucket =
                    hash_to_bucket_with_seed(word.as_bytes(), self.base.dim, 0x9e3779b9);
                counts[bucket] += 0.5;
            }
        }

        // Apply TF-IDF: tf * log(N / (1 + df))
        for (i, c) in counts.iter_mut().enumerate() {
            if *c > 0.0 {
                let tf = (1.0 + *c).ln();
                let idf = if self.total_docs > 0.0 {
                    (self.total_docs / (1.0 + self.doc_freq[i])).ln()
                } else {
                    1.0
                };
                *c = tf * idf;
            }
        }

        l2_normalize(&mut counts);
        counts
    }

    fn embed_batch(&self, texts: &[&str]) -> Vec<Vec<f64>> {
        texts.iter().map(|t| self.embed(t)).collect()
    }

    fn dim(&self) -> usize {
        self.base.dim
    }

    fn name(&self) -> &str {
        "IDFEmbedder"
    }
}

// ---------------------------------------------------------------------------
// Utility functions
// ---------------------------------------------------------------------------

/// Clean text: lowercase, keep alphanumeric + spaces, collapse whitespace.
fn clean_text(text: &str) -> String {
    let lower = text.to_lowercase();
    let cleaned: String = lower
        .chars()
        .map(|c| {
            if c.is_alphanumeric() || c == ' ' {
                c
            } else {
                ' '
            }
        })
        .collect();
    // Collapse multiple spaces
    let mut result = String::with_capacity(cleaned.len());
    let mut prev_space = true;
    for c in cleaned.chars() {
        if c == ' ' {
            if !prev_space {
                result.push(' ');
            }
            prev_space = true;
        } else {
            result.push(c);
            prev_space = false;
        }
    }
    result.trim().to_string()
}

/// Generate character n-grams from a string.
fn char_ngrams(text: &str, n: usize) -> Vec<String> {
    let chars: Vec<char> = text.chars().collect();
    if chars.len() < n {
        return Vec::new();
    }
    let mut ngrams = Vec::with_capacity(chars.len() - n + 1);
    for i in 0..=(chars.len() - n) {
        ngrams.push(chars[i..i + n].iter().collect());
    }
    ngrams
}

/// Hash bytes to a bucket index in [0, dim) using SHA-256.
fn hash_to_bucket(data: &[u8], dim: usize) -> usize {
    let mut hasher = Sha256::new();
    hasher.update(data);
    let hash = hasher.finalize();
    // Use first 8 bytes as u64
    let val = u64::from_le_bytes([
        hash[0], hash[1], hash[2], hash[3], hash[4], hash[5], hash[6], hash[7],
    ]);
    (val as usize) % dim
}

/// Hash bytes to a bucket index with an additional seed for namespace separation.
fn hash_to_bucket_with_seed(data: &[u8], dim: usize, seed: u32) -> usize {
    let mut hasher = Sha256::new();
    hasher.update(seed.to_le_bytes());
    hasher.update(data);
    let hash = hasher.finalize();
    let val = u64::from_le_bytes([
        hash[0], hash[1], hash[2], hash[3], hash[4], hash[5], hash[6], hash[7],
    ]);
    (val as usize) % dim
}

/// L2-normalize a vector in place. If the norm is zero, the vector is left as-is.
fn l2_normalize(v: &mut [f64]) {
    let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
    if norm > 1e-15 {
        for x in v.iter_mut() {
            *x /= norm;
        }
    }
}

/// Cosine similarity between two vectors.
pub fn cosine_sim(a: &[f64], b: &[f64]) -> f64 {
    const EPSILON: f64 = 1e-15;
    let mut dot = 0.0_f64;
    let mut norm_a = 0.0_f64;
    let mut norm_b = 0.0_f64;
    for (x, y) in a.iter().zip(b.iter()) {
        dot += x * y;
        norm_a += x * x;
        norm_b += y * y;
    }
    if norm_a < EPSILON || norm_b < EPSILON {
        return 0.0;
    }
    (dot / (norm_a.sqrt() * norm_b.sqrt())).clamp(-1.0, 1.0)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -- clean_text tests --

    #[test]
    fn test_clean_text_basic() {
        assert_eq!(clean_text("Hello, World!"), "hello world");
    }

    #[test]
    fn test_clean_text_preserves_alphanumeric() {
        assert_eq!(clean_text("test123"), "test123");
    }

    #[test]
    fn test_clean_text_collapses_spaces() {
        assert_eq!(clean_text("hello   world   test"), "hello world test");
    }

    #[test]
    fn test_clean_text_strips_special_chars() {
        assert_eq!(clean_text("a@b#c$d%e"), "a b c d e");
    }

    #[test]
    fn test_clean_text_empty() {
        assert_eq!(clean_text(""), "");
    }

    #[test]
    fn test_clean_text_only_special() {
        assert_eq!(clean_text("@#$%^&"), "");
    }

    // -- char_ngrams tests --

    #[test]
    fn test_ngrams_basic() {
        let ngrams = char_ngrams("hello", 3);
        assert_eq!(ngrams, vec!["hel", "ell", "llo"]);
    }

    #[test]
    fn test_ngrams_short_text() {
        let ngrams = char_ngrams("hi", 3);
        assert!(ngrams.is_empty());
    }

    #[test]
    fn test_ngrams_exact_length() {
        let ngrams = char_ngrams("abc", 3);
        assert_eq!(ngrams, vec!["abc"]);
    }

    #[test]
    fn test_ngrams_single_char() {
        let ngrams = char_ngrams("a", 1);
        assert_eq!(ngrams, vec!["a"]);
    }

    // -- hash_to_bucket tests --

    #[test]
    fn test_hash_deterministic() {
        let b1 = hash_to_bucket(b"test", 256);
        let b2 = hash_to_bucket(b"test", 256);
        assert_eq!(b1, b2);
    }

    #[test]
    fn test_hash_in_range() {
        for i in 0..100u32 {
            let bucket = hash_to_bucket(&i.to_le_bytes(), 384);
            assert!(bucket < 384);
        }
    }

    #[test]
    fn test_hash_different_inputs() {
        let b1 = hash_to_bucket(b"hello", 1000);
        let b2 = hash_to_bucket(b"world", 1000);
        // Different inputs should (usually) produce different buckets
        // This is probabilistic but extremely likely with 1000 buckets
        // We just check they're both valid
        assert!(b1 < 1000);
        assert!(b2 < 1000);
    }

    #[test]
    fn test_hash_with_seed_different() {
        let b1 = hash_to_bucket(b"test", 384);
        let b2 = hash_to_bucket_with_seed(b"test", 384, 0x12345678);
        // Seeded hash should differ from unseeded (extremely likely)
        // At minimum both should be in range
        assert!(b1 < 384);
        assert!(b2 < 384);
    }

    // -- l2_normalize tests --

    #[test]
    fn test_l2_normalize_unit() {
        let mut v = vec![3.0, 4.0];
        l2_normalize(&mut v);
        assert!((v[0] - 0.6).abs() < 1e-10);
        assert!((v[1] - 0.8).abs() < 1e-10);
    }

    #[test]
    fn test_l2_normalize_zero_vector() {
        let mut v = vec![0.0, 0.0, 0.0];
        l2_normalize(&mut v);
        // Should remain zero
        for x in &v {
            assert!(x.abs() < 1e-15);
        }
    }

    #[test]
    fn test_l2_normalize_already_unit() {
        let mut v = vec![1.0, 0.0, 0.0];
        l2_normalize(&mut v);
        assert!((v[0] - 1.0).abs() < 1e-10);
    }

    // -- cosine_sim tests --

    #[test]
    fn test_cosine_sim_identical() {
        let v = vec![1.0, 2.0, 3.0];
        let sim = cosine_sim(&v, &v);
        assert!((sim - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_cosine_sim_orthogonal() {
        let a = vec![1.0, 0.0];
        let b = vec![0.0, 1.0];
        let sim = cosine_sim(&a, &b);
        assert!(sim.abs() < 1e-10);
    }

    #[test]
    fn test_cosine_sim_opposite() {
        let a = vec![1.0, 2.0, 3.0];
        let b: Vec<f64> = a.iter().map(|x| -x).collect();
        let sim = cosine_sim(&a, &b);
        assert!((sim - (-1.0)).abs() < 1e-10);
    }

    #[test]
    fn test_cosine_sim_zero_vector() {
        let a = vec![1.0, 2.0, 3.0];
        let b = vec![0.0, 0.0, 0.0];
        let sim = cosine_sim(&a, &b);
        assert!(sim.abs() < 1e-10);
    }

    // -- SimpleEmbedder tests --

    #[test]
    fn test_simple_embedder_default() {
        let emb = SimpleEmbedder::new(384, 3);
        assert_eq!(emb.dim(), 384);
        assert_eq!(emb.name(), "SimpleEmbedder");
    }

    #[test]
    fn test_simple_embed_produces_correct_dim() {
        let emb = SimpleEmbedder::new(256, 3);
        let v = emb.embed("hello world");
        assert_eq!(v.len(), 256);
    }

    #[test]
    fn test_simple_embed_unit_vector() {
        let emb = SimpleEmbedder::new(384, 3);
        let v = emb.embed("quantum blockchain technology");
        let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        assert!(
            (norm - 1.0).abs() < 1e-10,
            "embedding should be unit vector, got norm={}",
            norm
        );
    }

    #[test]
    fn test_simple_embed_deterministic() {
        let emb = SimpleEmbedder::new(384, 3);
        let v1 = emb.embed("deterministic test");
        let v2 = emb.embed("deterministic test");
        assert_eq!(v1, v2);
    }

    #[test]
    fn test_simple_embed_empty_text() {
        let emb = SimpleEmbedder::new(384, 3);
        let v = emb.embed("");
        assert_eq!(v.len(), 384);
        // Empty text should produce zero vector
        for x in &v {
            assert!(x.abs() < 1e-15);
        }
    }

    #[test]
    fn test_simple_embed_similar_texts_high_similarity() {
        let emb = SimpleEmbedder::new(384, 3);
        let v1 = emb.embed("quantum computing research");
        let v2 = emb.embed("quantum computing study");
        let sim = cosine_sim(&v1, &v2);
        // These share "quantum computing " prefix so should have high similarity
        assert!(
            sim > 0.5,
            "similar texts should have high similarity, got {}",
            sim
        );
    }

    #[test]
    fn test_simple_embed_different_texts_lower_similarity() {
        let emb = SimpleEmbedder::new(384, 3);
        let v1 = emb.embed("quantum physics experiment");
        let v2 = emb.embed("banana chocolate cake");
        let sim = cosine_sim(&v1, &v2);
        // Very different texts should have low similarity
        assert!(
            sim < 0.5,
            "different texts should have lower similarity, got {}",
            sim
        );
    }

    #[test]
    fn test_simple_embed_batch() {
        let emb = SimpleEmbedder::new(256, 3);
        let texts = vec!["hello", "world", "test"];
        let embeddings = emb.embed_batch(&texts);
        assert_eq!(embeddings.len(), 3);
        for v in &embeddings {
            assert_eq!(v.len(), 256);
        }
    }

    #[test]
    fn test_simple_embed_batch_matches_individual() {
        let emb = SimpleEmbedder::new(384, 3);
        let texts = vec!["alpha", "beta", "gamma"];
        let batch = emb.embed_batch(&texts);
        for (i, text) in texts.iter().enumerate() {
            let individual = emb.embed(text);
            assert_eq!(batch[i], individual);
        }
    }

    #[test]
    fn test_simple_embed_short_text() {
        let emb = SimpleEmbedder::new(384, 3);
        let v = emb.embed("hi");
        assert_eq!(v.len(), 384);
        // Short text (< ngram_size) should still produce a non-zero embedding
        let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        assert!(norm > 0.5, "short text should produce non-zero embedding");
    }

    #[test]
    fn test_simple_embed_single_char() {
        let emb = SimpleEmbedder::new(384, 3);
        let v = emb.embed("x");
        assert_eq!(v.len(), 384);
        let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        assert!(norm > 0.5);
    }

    #[test]
    fn test_simple_embed_special_chars_only() {
        let emb = SimpleEmbedder::new(384, 3);
        let v = emb.embed("@#$%^&*()");
        assert_eq!(v.len(), 384);
        // All special chars get cleaned to empty -> zero vector
        for x in &v {
            assert!(x.abs() < 1e-15);
        }
    }

    #[test]
    fn test_simple_embed_unicode() {
        let emb = SimpleEmbedder::new(384, 3);
        let v = emb.embed("quantum 量子 blockchain");
        assert_eq!(v.len(), 384);
        let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        assert!((norm - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_simple_embed_case_insensitive() {
        let emb = SimpleEmbedder::new(384, 3);
        let v1 = emb.embed("Hello World");
        let v2 = emb.embed("hello world");
        let sim = cosine_sim(&v1, &v2);
        assert!(
            (sim - 1.0).abs() < 1e-10,
            "case should not affect embeddings"
        );
    }

    #[test]
    fn test_simple_embedder_similarity_method() {
        let emb = SimpleEmbedder::new(384, 3);
        let sim = emb.similarity("hello world", "hello world");
        assert!((sim - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_simple_embedder_min_dim() {
        let emb = SimpleEmbedder::new(0, 3); // Should clamp to 1
        assert_eq!(emb.dim(), 1);
    }

    #[test]
    fn test_simple_embedder_min_ngram() {
        let emb = SimpleEmbedder::new(384, 0); // Should clamp to 1
        assert_eq!(emb.ngram_size, 1);
    }

    // -- IDFEmbedder tests --

    #[test]
    fn test_idf_embedder_basic() {
        let mut emb = IDFEmbedder::new(384, 3);
        emb.fit_document("quantum computing research");
        emb.fit_document("machine learning algorithms");
        emb.fit_document("quantum machine entanglement");
        assert!((emb.total_documents() - 3.0).abs() < 1e-10);

        let v = emb.embed("quantum computing");
        assert_eq!(v.len(), 384);
        let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        assert!((norm - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_idf_embedder_fit_documents() {
        let mut emb = IDFEmbedder::new(256, 3);
        emb.fit_documents(vec![
            "alpha beta".to_string(),
            "gamma delta".to_string(),
        ]);
        assert!((emb.total_documents() - 2.0).abs() < 1e-10);
    }

    #[test]
    fn test_idf_embedder_no_fit_still_works() {
        let emb = IDFEmbedder::new(384, 3);
        let v = emb.embed("hello world");
        assert_eq!(v.len(), 384);
        // With no documents fitted, IDF = 1.0 fallback
        let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        assert!((norm - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_idf_embedder_repr() {
        let emb = IDFEmbedder::new(384, 3);
        let repr = emb.__repr__();
        assert!(repr.contains("384"));
        assert!(repr.contains("IDFEmbedder"));
    }
}
