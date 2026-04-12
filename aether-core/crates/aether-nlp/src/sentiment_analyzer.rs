//! Sentiment Analyzer — Lexicon-based sentiment analysis for Aether Tree.
//!
//! AFINN-style word-level sentiment with crypto-specific terms,
//! negation handling, and intensifier support.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::LazyLock;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Result of sentiment analysis.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SentimentResult {
    /// Normalized score in [-1.0, 1.0].
    pub score: f64,
    /// Label: "positive", "negative", or "neutral".
    pub label: SentimentLabel,
    /// Confidence in [0.0, 1.0].
    pub confidence: f64,
    /// Unnormalized sum.
    pub raw_score: f64,
    /// Total words analyzed.
    pub word_count: usize,
    /// Words that contributed to sentiment.
    pub sentiment_words: usize,
}

/// Sentiment label.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum SentimentLabel {
    Positive,
    Negative,
    Neutral,
}

impl SentimentLabel {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Positive => "positive",
            Self::Negative => "negative",
            Self::Neutral => "neutral",
        }
    }
}

// ---------------------------------------------------------------------------
// Lexicon
// ---------------------------------------------------------------------------

static LEXICON: LazyLock<HashMap<&'static str, i32>> = LazyLock::new(|| {
    let mut m = HashMap::new();
    // Positive general
    for &(w, v) in &[
        ("good", 3), ("great", 3), ("excellent", 4), ("amazing", 4), ("wonderful", 4),
        ("fantastic", 4), ("awesome", 4), ("brilliant", 4), ("outstanding", 5),
        ("superb", 4), ("perfect", 5), ("best", 4), ("better", 2), ("nice", 2),
        ("fine", 1), ("love", 3), ("like", 2), ("enjoy", 2), ("happy", 3),
        ("glad", 2), ("pleased", 2), ("excited", 3), ("thrilled", 4),
        ("impressive", 3), ("remarkable", 3), ("exceptional", 4),
        ("beautiful", 3), ("elegant", 3), ("innovative", 3), ("revolutionary", 4),
        ("breakthrough", 4), ("success", 3), ("successful", 3), ("win", 3),
        ("progress", 2), ("improve", 2), ("improved", 2), ("improvement", 2),
        ("strong", 2), ("powerful", 2), ("efficient", 2), ("effective", 2),
        ("reliable", 2), ("stable", 2), ("secure", 2), ("safe", 2),
        ("trust", 2), ("trusted", 2), ("confident", 2), ("optimistic", 3),
        ("promising", 3), ("growth", 2), ("gain", 2), ("profit", 2),
        ("valuable", 2), ("reward", 2), ("rewarding", 3), ("fast", 2),
        ("smooth", 1), ("solid", 2), ("robust", 2), ("healthy", 2),
        ("positive", 2), ("confirmed", 2), ("verified", 2), ("launched", 2),
        ("live", 2), ("working", 1), ("running", 1),
    ] {
        m.insert(w, v);
    }
    // Negative general
    for &(w, v) in &[
        ("bad", -3), ("terrible", -4), ("horrible", -4), ("awful", -4), ("worst", -5),
        ("worse", -3), ("poor", -2), ("weak", -2), ("fail", -3), ("failed", -3),
        ("failure", -3), ("error", -2), ("bug", -2), ("broken", -3), ("crash", -4),
        ("crashed", -4), ("down", -2), ("slow", -2), ("lag", -2),
        ("stuck", -2), ("frozen", -2), ("dead", -3), ("lost", -3), ("lose", -3),
        ("losing", -3), ("loss", -3), ("damage", -3), ("damaged", -3),
        ("risk", -2), ("risky", -2), ("danger", -3), ("dangerous", -3),
        ("threat", -3), ("vulnerable", -3), ("exploit", -4),
        ("hack", -4), ("hacked", -4), ("scam", -5), ("fraud", -5), ("fake", -4),
        ("spam", -3), ("malicious", -4), ("attack", -3), ("attacked", -3),
        ("fear", -2), ("worried", -2), ("concerned", -1),
        ("angry", -3), ("furious", -4), ("frustrated", -3), ("annoyed", -2),
        ("disappointed", -3), ("sad", -2), ("hate", -4),
        ("ugly", -3), ("mess", -2), ("confusing", -2),
        ("difficult", -1), ("impossible", -3), ("useless", -3), ("worthless", -4),
        ("waste", -3), ("wasted", -3), ("decline", -2), ("declining", -2),
        ("drop", -2), ("dropped", -2), ("falling", -2), ("plunge", -3),
        ("reject", -2), ("rejected", -2), ("problem", -2), ("issue", -1),
        ("wrong", -2), ("negative", -2), ("suspicious", -2), ("unstable", -2),
        ("insecure", -3), ("abandoned", -3),
    ] {
        m.insert(w, v);
    }
    // Crypto-specific positive
    for &(w, v) in &[
        ("bullish", 3), ("moon", 3), ("mooning", 4), ("pump", 2), ("rally", 3),
        ("breakout", 3), ("adoption", 3), ("decentralized", 2), ("hodl", 2),
        ("accumulate", 2), ("undervalued", 2), ("mainnet", 2), ("upgrade", 2),
        ("partnership", 3), ("listing", 3), ("listed", 3), ("airdrop", 2),
        ("staking", 1), ("audited", 2), ("transparent", 2), ("quantum", 2),
        ("aether", 2), ("milestone", 2), ("consensus", 1), ("governance", 1),
    ] {
        m.insert(w, v);
    }
    // Crypto-specific negative
    for &(w, v) in &[
        ("bearish", -3), ("dump", -3), ("dumping", -4), ("rug", -5), ("rugpull", -5),
        ("ponzi", -5), ("bubble", -3), ("fud", -3), ("rekt", -4),
        ("liquidated", -4), ("liquidation", -3), ("capitulation", -4),
        ("correction", -2), ("bleeding", -3), ("panic", -3),
        ("selloff", -3), ("overvalued", -2), ("centralized", -2), ("censored", -3),
        ("delisted", -3), ("banned", -3), ("illegal", -4), ("shutdown", -3),
        ("offline", -2), ("reorg", -3), ("doublespend", -5),
    ] {
        m.insert(w, v);
    }
    m
});

static NEGATORS: LazyLock<Vec<&'static str>> = LazyLock::new(|| {
    vec![
        "not", "no", "never", "neither", "nobody", "nothing", "nowhere",
        "nor", "without", "hardly", "barely", "scarcely",
        "don't", "dont", "doesn't", "doesnt", "didn't", "didnt",
        "won't", "wont", "wouldn't", "wouldnt", "can't", "cant",
        "cannot", "couldn't", "couldnt", "shouldn't", "shouldnt",
        "isn't", "isnt", "aren't", "arent", "wasn't", "wasnt",
        "weren't", "werent", "haven't", "havent", "hasn't", "hasnt",
    ]
});

static INTENSIFIERS: LazyLock<HashMap<&'static str, f64>> = LazyLock::new(|| {
    let mut m = HashMap::new();
    m.insert("very", 1.5);
    m.insert("really", 1.5);
    m.insert("extremely", 2.0);
    m.insert("incredibly", 2.0);
    m.insert("absolutely", 2.0);
    m.insert("totally", 1.5);
    m.insert("completely", 1.5);
    m.insert("highly", 1.5);
    m.insert("super", 1.5);
    m.insert("so", 1.3);
    m.insert("quite", 1.2);
    m.insert("fairly", 0.8);
    m.insert("somewhat", 0.7);
    m.insert("slightly", 0.5);
    m.insert("barely", 0.3);
    m
});

// ---------------------------------------------------------------------------
// SentimentAnalyzer
// ---------------------------------------------------------------------------

/// Lexicon-based sentiment analyzer with negation and intensifier handling.
pub struct SentimentAnalyzer {
    calls: u64,
    label_counts: [u64; 3], // positive, negative, neutral
}

impl SentimentAnalyzer {
    pub fn new() -> Self {
        Self {
            calls: 0,
            label_counts: [0, 0, 0],
        }
    }

    /// Analyze sentiment of a text string.
    pub fn analyze(&mut self, text: &str) -> SentimentResult {
        self.calls += 1;

        let tokens: Vec<&str> = text
            .split(|c: char| !c.is_alphanumeric() && c != '\'')
            .filter(|w| !w.is_empty())
            .collect();

        let word_count = tokens.len();
        if word_count == 0 {
            return SentimentResult {
                score: 0.0,
                label: SentimentLabel::Neutral,
                confidence: 0.5,
                raw_score: 0.0,
                word_count: 0,
                sentiment_words: 0,
            };
        }

        let mut raw_score: f64 = 0.0;
        let mut sentiment_words: usize = 0;
        let mut negate = false;
        let mut intensifier: f64 = 1.0;

        for token in &tokens {
            let lower = token.to_lowercase();
            let lower_str = lower.as_str();

            // Check negator
            if NEGATORS.contains(&lower_str) {
                negate = true;
                continue;
            }

            // Check intensifier
            if let Some(&int_val) = INTENSIFIERS.get(lower_str) {
                intensifier = int_val;
                continue;
            }

            // Check lexicon
            if let Some(&val) = LEXICON.get(lower_str) {
                let mut fval = val as f64 * intensifier;
                if negate {
                    fval = -fval * 0.75;
                    negate = false;
                }
                raw_score += fval;
                sentiment_words += 1;
            }

            // Reset modifiers
            intensifier = 1.0;
            if !NEGATORS.contains(&lower_str) {
                negate = false;
            }
        }

        // Normalize to [-1, 1]
        let max_possible = if sentiment_words > 0 {
            sentiment_words as f64 * 5.0
        } else {
            1.0
        };
        let normalized = (raw_score / max_possible).clamp(-1.0, 1.0);

        // Label
        let label = if normalized > 0.05 {
            SentimentLabel::Positive
        } else if normalized < -0.05 {
            SentimentLabel::Negative
        } else {
            SentimentLabel::Neutral
        };

        // Confidence
        let confidence = if word_count > 0 && sentiment_words > 0 {
            let coverage = sentiment_words as f64 / word_count as f64;
            let magnitude = normalized.abs();
            (0.3 + coverage * 0.4 + magnitude * 0.3).min(1.0)
        } else {
            0.3
        };

        match label {
            SentimentLabel::Positive => self.label_counts[0] += 1,
            SentimentLabel::Negative => self.label_counts[1] += 1,
            SentimentLabel::Neutral => self.label_counts[2] += 1,
        }

        SentimentResult {
            score: (normalized * 10000.0).round() / 10000.0,
            label,
            confidence: (confidence * 10000.0).round() / 10000.0,
            raw_score: (raw_score * 10000.0).round() / 10000.0,
            word_count,
            sentiment_words,
        }
    }

    /// Get analyzer statistics.
    pub fn get_stats(&self) -> (u64, [u64; 3]) {
        (self.calls, self.label_counts)
    }
}

impl Default for SentimentAnalyzer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_positive_sentiment() {
        let mut analyzer = SentimentAnalyzer::new();
        let result = analyzer.analyze("This is a great and amazing project");
        assert_eq!(result.label, SentimentLabel::Positive);
        assert!(result.score > 0.0);
    }

    #[test]
    fn test_negative_sentiment() {
        let mut analyzer = SentimentAnalyzer::new();
        let result = analyzer.analyze("The system crashed and failed terribly");
        assert_eq!(result.label, SentimentLabel::Negative);
        assert!(result.score < 0.0);
    }

    #[test]
    fn test_neutral_sentiment() {
        let mut analyzer = SentimentAnalyzer::new();
        let result = analyzer.analyze("The block contains three transactions");
        assert_eq!(result.label, SentimentLabel::Neutral);
    }

    #[test]
    fn test_negation() {
        let mut analyzer = SentimentAnalyzer::new();
        let result = analyzer.analyze("This is not good at all");
        assert!(result.score < 0.0);
    }

    #[test]
    fn test_intensifier() {
        let mut analyzer = SentimentAnalyzer::new();
        let normal = analyzer.analyze("good project");
        let intensified = analyzer.analyze("extremely good project");
        assert!(intensified.raw_score > normal.raw_score);
    }

    #[test]
    fn test_crypto_sentiment() {
        let mut analyzer = SentimentAnalyzer::new();
        let result = analyzer.analyze("QBC is bullish, mooning to new highs");
        assert_eq!(result.label, SentimentLabel::Positive);
    }

    #[test]
    fn test_empty_text() {
        let mut analyzer = SentimentAnalyzer::new();
        let result = analyzer.analyze("");
        assert_eq!(result.label, SentimentLabel::Neutral);
        assert_eq!(result.word_count, 0);
    }
}
