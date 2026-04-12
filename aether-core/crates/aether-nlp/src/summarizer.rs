//! Text Summarizer — Extractive summarization via sentence scoring.
//!
//! Scores sentences by position, term frequency, keyword overlap, and length.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Result of text summarization.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Summary {
    pub sentences: Vec<String>,
    pub scores: Vec<f64>,
    pub compression_ratio: f64,
}

/// Configuration for the summarizer.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SummarizerConfig {
    /// Weight for sentence position score (earlier = higher).
    pub position_weight: f64,
    /// Weight for term frequency score.
    pub tf_weight: f64,
    /// Weight for keyword overlap score.
    pub keyword_weight: f64,
    /// Weight for sentence length score (prefer medium-length).
    pub length_weight: f64,
    /// Ideal sentence length in words.
    pub ideal_length: usize,
}

impl Default for SummarizerConfig {
    fn default() -> Self {
        Self {
            position_weight: 0.25,
            tf_weight: 0.35,
            keyword_weight: 0.25,
            length_weight: 0.15,
            ideal_length: 20,
        }
    }
}

/// Extractive text summarizer.
pub struct TextSummarizer {
    config: SummarizerConfig,
    calls: u64,
}

impl TextSummarizer {
    pub fn new() -> Self {
        Self {
            config: SummarizerConfig::default(),
            calls: 0,
        }
    }

    pub fn with_config(config: SummarizerConfig) -> Self {
        Self { config, calls: 0 }
    }

    /// Summarize text by selecting the top-scoring sentences.
    pub fn summarize(&mut self, text: &str, max_sentences: usize) -> Summary {
        self.calls += 1;

        let sentences = split_sentences(text);
        if sentences.is_empty() {
            return Summary {
                sentences: Vec::new(),
                scores: Vec::new(),
                compression_ratio: 1.0,
            };
        }

        let max_sentences = max_sentences.min(sentences.len());
        let scores = self.score_sentences(&sentences);

        // Get indices sorted by score descending
        let mut indexed: Vec<(usize, f64)> = scores.iter().copied().enumerate().collect();
        indexed.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        // Take top-N and sort by original position to maintain order
        let mut selected: Vec<usize> = indexed.iter().take(max_sentences).map(|&(i, _)| i).collect();
        selected.sort_unstable();

        let selected_sentences: Vec<String> = selected.iter().map(|&i| sentences[i].clone()).collect();
        let selected_scores: Vec<f64> = selected.iter().map(|&i| scores[i]).collect();

        let original_len: usize = sentences.iter().map(|s| s.len()).sum();
        let summary_len: usize = selected_sentences.iter().map(|s| s.len()).sum();
        let compression_ratio = if original_len > 0 {
            summary_len as f64 / original_len as f64
        } else {
            1.0
        };

        Summary {
            sentences: selected_sentences,
            scores: selected_scores,
            compression_ratio,
        }
    }

    /// Score each sentence in the document.
    pub fn score_sentences(&self, sentences: &[String]) -> Vec<f64> {
        let n = sentences.len();
        if n == 0 {
            return Vec::new();
        }

        // Build term frequency map across all sentences
        let mut tf: HashMap<String, usize> = HashMap::new();
        let tokenized: Vec<Vec<String>> = sentences.iter().map(|s| tokenize_words(s)).collect();
        for words in &tokenized {
            for w in words {
                *tf.entry(w.clone()).or_insert(0) += 1;
            }
        }

        // Extract top keywords (highest TF)
        let mut tf_sorted: Vec<(&String, &usize)> = tf.iter().collect();
        tf_sorted.sort_by(|a, b| b.1.cmp(a.1));
        let keywords: Vec<&str> = tf_sorted.iter().take(20).map(|(k, _)| k.as_str()).collect();

        let mut scores = Vec::with_capacity(n);

        for (i, words) in tokenized.iter().enumerate() {
            // Position score: first and last sentences get bonus
            let position_score = if i == 0 {
                1.0
            } else if i == n - 1 {
                0.7
            } else {
                1.0 - (i as f64 / n as f64) * 0.5
            };

            // Term frequency score: average TF of words in sentence
            let tf_score = if !words.is_empty() {
                let sum: f64 = words.iter().map(|w| *tf.get(w).unwrap_or(&0) as f64).sum();
                sum / words.len() as f64 / n as f64
            } else {
                0.0
            };

            // Keyword overlap score
            let keyword_score = if !words.is_empty() {
                let overlap = words.iter().filter(|w| keywords.contains(&w.as_str())).count();
                overlap as f64 / words.len().min(keywords.len()).max(1) as f64
            } else {
                0.0
            };

            // Length score: prefer medium-length sentences
            let len = words.len();
            let length_score = if len == 0 {
                0.0
            } else {
                let diff = (len as f64 - self.config.ideal_length as f64).abs();
                1.0 / (1.0 + diff / self.config.ideal_length as f64)
            };

            let score = position_score * self.config.position_weight
                + tf_score * self.config.tf_weight
                + keyword_score * self.config.keyword_weight
                + length_score * self.config.length_weight;

            scores.push(score);
        }

        scores
    }

    /// Get summarizer statistics.
    pub fn get_calls(&self) -> u64 {
        self.calls
    }
}

impl Default for TextSummarizer {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Split text into sentences.
pub fn split_sentences(text: &str) -> Vec<String> {
    let mut sentences = Vec::new();
    let mut current = String::new();

    for ch in text.chars() {
        current.push(ch);
        if ch == '.' || ch == '!' || ch == '?' {
            let trimmed = current.trim().to_string();
            if !trimmed.is_empty() && trimmed.len() > 3 {
                sentences.push(trimmed);
            }
            current.clear();
        }
    }

    // Remaining text as a sentence
    let trimmed = current.trim().to_string();
    if !trimmed.is_empty() && trimmed.len() > 3 {
        sentences.push(trimmed);
    }

    sentences
}

/// Tokenize into lowercase words.
fn tokenize_words(text: &str) -> Vec<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|w| w.len() > 2)
        .map(|w| w.to_lowercase())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_split_sentences() {
        let text = "First sentence. Second sentence! Third one?";
        let sents = split_sentences(text);
        assert_eq!(sents.len(), 3);
    }

    #[test]
    fn test_summarize_basic() {
        let mut sum = TextSummarizer::new();
        let text = "The blockchain is secure. Mining requires quantum computation. \
                    Blocks are produced every 3.3 seconds. The network has many nodes. \
                    Consensus ensures agreement.";
        let result = sum.summarize(text, 2);
        assert_eq!(result.sentences.len(), 2);
        assert!(result.compression_ratio < 1.0);
        assert!(result.compression_ratio > 0.0);
    }

    #[test]
    fn test_summarize_empty() {
        let mut sum = TextSummarizer::new();
        let result = sum.summarize("", 3);
        assert!(result.sentences.is_empty());
    }

    #[test]
    fn test_score_sentences() {
        let sum = TextSummarizer::new();
        let sentences = vec![
            "The miner found a block.".to_string(),
            "It was a great day.".to_string(),
            "The block had many transactions.".to_string(),
        ];
        let scores = sum.score_sentences(&sentences);
        assert_eq!(scores.len(), 3);
        // First sentence should score high due to position
        assert!(scores[0] > 0.0);
    }
}
