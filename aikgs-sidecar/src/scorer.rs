//! Knowledge Scorer — Quality, novelty, and anti-gaming scoring.
//!
//! Evaluates knowledge contributions on three axes:
//!   1. Quality (0-1.0): Specificity, concreteness, coherence, factual density
//!   2. Novelty (0-1.0): Content hash uniqueness (DB-backed dedup)
//!   3. Gaming detection: Spam, paraphrasing, low-effort submissions

use regex::Regex;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::LazyLock;

use crate::config::AikgsConfig;

/// Domain keywords for classification.
static DOMAIN_KEYWORDS: LazyLock<HashMap<&str, Vec<&str>>> = LazyLock::new(|| {
    let mut m = HashMap::new();
    m.insert(
        "quantum_physics",
        vec![
            "quantum",
            "qubit",
            "superposition",
            "entanglement",
            "hamiltonian",
            "vqe",
        ],
    );
    m.insert(
        "mathematics",
        vec![
            "theorem", "proof", "equation", "formula", "integral", "algebra",
        ],
    );
    m.insert(
        "computer_science",
        vec![
            "algorithm",
            "complexity",
            "compiler",
            "data structure",
            "hash",
            "graph",
        ],
    );
    m.insert(
        "blockchain",
        vec![
            "block",
            "transaction",
            "consensus",
            "mining",
            "chain",
            "utxo",
            "merkle",
        ],
    );
    m.insert(
        "cryptography",
        vec![
            "cipher",
            "encryption",
            "signature",
            "dilithium",
            "kyber",
            "hash",
        ],
    );
    m.insert(
        "philosophy",
        vec![
            "consciousness",
            "epistemology",
            "ontology",
            "ethics",
            "reason",
        ],
    );
    m.insert(
        "biology",
        vec!["cell", "protein", "gene", "dna", "evolution", "organism"],
    );
    m.insert(
        "physics",
        vec![
            "force", "energy", "mass", "velocity", "relativity", "particle",
        ],
    );
    m.insert(
        "economics",
        vec![
            "market", "supply", "demand", "inflation", "monetary", "fiscal",
        ],
    );
    m.insert(
        "ai_ml",
        vec![
            "neural",
            "training",
            "model",
            "inference",
            "gradient",
            "transformer",
        ],
    );
    m
});

static FACTUAL_SIGNALS: &[&str] = &[
    "defined as",
    "measured",
    "equals",
    "consists of",
    "proven",
    "demonstrated",
    "published",
    "according to",
    "formula",
    "theorem",
    "equation",
    "property",
];

static VAGUE_SIGNALS: &[&str] = &[
    "it depends",
    "generally",
    "it varies",
    "maybe",
    "sort of",
    "kind of",
    "basically",
    "honestly",
];

static STRUCTURE_SIGNALS: &[&str] = &[
    "first",
    "second",
    "therefore",
    "however",
    "furthermore",
    "in conclusion",
    "because",
];

static NUMBER_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\d+\.?\d*").unwrap());

/// Result of scoring a knowledge contribution.
#[derive(Debug, Clone)]
pub struct ContributionScore {
    pub quality_score: f64,
    pub novelty_score: f64,
    pub combined_score: f64,
    pub tier: String,
    pub is_spam: bool,
    pub spam_reason: String,
    pub domain: String,
    pub content_hash: String,
    pub scoring_time_ms: f64,
}

/// Pure scoring functions — no I/O, no state.
pub struct Scorer {
    quality_weight: f64,
    novelty_weight: f64,
}

impl Scorer {
    pub fn new(cfg: &AikgsConfig) -> Self {
        Self {
            quality_weight: cfg.quality_weight,
            novelty_weight: cfg.novelty_weight,
        }
    }

    /// Compute the SHA-256 content hash.
    pub fn content_hash(content: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(content.as_bytes());
        hex::encode(hasher.finalize())
    }

    /// Full scoring pipeline (except DB-backed checks which are done externally).
    pub fn score(&self, content: &str) -> ContributionScore {
        let start = std::time::Instant::now();
        let content_hash = Self::content_hash(content);

        // Spam / gaming detection (local checks only; DB dedup done externally)
        let (is_spam, spam_reason) = self.detect_gaming(content);
        if is_spam {
            return ContributionScore {
                quality_score: 0.0,
                novelty_score: 0.0,
                combined_score: 0.0,
                tier: "bronze".into(),
                is_spam: true,
                spam_reason,
                domain: String::new(),
                content_hash,
                scoring_time_ms: start.elapsed().as_secs_f64() * 1000.0,
            };
        }

        let quality = self.score_quality(content);
        // Novelty defaults to 0.5 (neutral) — real novelty is checked via DB
        let novelty = 0.5;
        let combined = quality * self.quality_weight + novelty * self.novelty_weight;
        let tier = Self::determine_tier(combined);
        let domain = Self::detect_domain(content);

        ContributionScore {
            quality_score: quality,
            novelty_score: novelty,
            combined_score: combined,
            tier,
            is_spam: false,
            spam_reason: String::new(),
            domain,
            content_hash,
            scoring_time_ms: start.elapsed().as_secs_f64() * 1000.0,
        }
    }

    /// Set novelty and recompute combined score + tier.
    pub fn with_novelty(&self, mut score: ContributionScore, novelty: f64) -> ContributionScore {
        score.novelty_score = novelty;
        score.combined_score =
            score.quality_score * self.quality_weight + novelty * self.novelty_weight;
        score.tier = Self::determine_tier(score.combined_score);
        score
    }

    fn score_quality(&self, content: &str) -> f64 {
        let mut score: f64 = 0.5;
        let lower = content.to_lowercase();
        let words: Vec<&str> = content.split_whitespace().collect();
        let word_count = words.len();

        // Length bonus/penalty
        if word_count < 10 {
            score -= 0.3;
        } else if word_count < 30 {
            score -= 0.1;
        } else if word_count > 100 {
            score += 0.1;
        } else if word_count > 50 {
            score += 0.05;
        }

        // Numbers (specificity)
        let num_count = NUMBER_RE.find_iter(content).count();
        score += (num_count as f64 * 0.03).min(0.15);

        // Technical terms (long words)
        let technical = words.iter().filter(|w| w.len() > 8).count();
        score += (technical as f64 * 0.02).min(0.1);

        // Factual signals
        let fact_hits = FACTUAL_SIGNALS
            .iter()
            .filter(|s| lower.contains(**s))
            .count();
        score += (fact_hits as f64 * 0.05).min(0.15);

        // Vague penalties
        let vague_hits = VAGUE_SIGNALS
            .iter()
            .filter(|s| lower.contains(**s))
            .count();
        score -= (vague_hits as f64 * 0.05).min(0.2);

        // Structure bonus
        let struct_hits = STRUCTURE_SIGNALS
            .iter()
            .filter(|s| lower.contains(**s))
            .count();
        score += (struct_hits as f64 * 0.03).min(0.1);

        // Unique word ratio
        if word_count > 10 {
            let unique: std::collections::HashSet<String> =
                words.iter().map(|w| w.to_lowercase()).collect();
            let ratio = unique.len() as f64 / word_count as f64;
            if ratio < 0.4 {
                score -= 0.15;
            } else if ratio > 0.7 {
                score += 0.05;
            }
        }

        score.clamp(0.0, 1.0)
    }

    fn detect_gaming(&self, content: &str) -> (bool, String) {
        let lower = content.to_lowercase();
        let trimmed = lower.trim();

        // Too short
        if trimmed.len() < 20 {
            return (true, "too_short".into());
        }

        // Gibberish (low letter ratio)
        let alpha_count = content.chars().filter(|c| c.is_alphabetic()).count();
        if !content.is_empty() && (alpha_count as f64 / content.len() as f64) < 0.4 {
            return (true, "gibberish".into());
        }

        // All caps
        let upper_count = content.chars().filter(|c| c.is_uppercase()).count();
        if content.len() > 20 && (upper_count as f64 / content.len() as f64) > 0.8 {
            return (true, "all_caps".into());
        }

        // Excessive repetition
        let words: Vec<&str> = trimmed.split_whitespace().collect();
        if words.len() > 5 {
            let mut freq: HashMap<&str, usize> = HashMap::new();
            for w in &words {
                *freq.entry(w).or_default() += 1;
            }
            if let Some(&max_freq) = freq.values().max() {
                if max_freq > 5 && (max_freq as f64 / words.len() as f64) > 0.3 {
                    return (true, "excessive_repetition".into());
                }
            }
        }

        (false, String::new())
    }

    pub fn determine_tier(combined: f64) -> String {
        if combined >= 0.90 {
            "diamond".into()
        } else if combined >= 0.70 {
            "gold".into()
        } else if combined >= 0.40 {
            "silver".into()
        } else {
            "bronze".into()
        }
    }

    pub fn detect_domain(content: &str) -> String {
        let lower = content.to_lowercase();
        let mut scores: HashMap<&str, usize> = HashMap::new();

        for (domain, keywords) in DOMAIN_KEYWORDS.iter() {
            let count = keywords.iter().filter(|kw| lower.contains(**kw)).count();
            if count > 0 {
                scores.insert(domain, count);
            }
        }

        scores
            .into_iter()
            .max_by_key(|&(_, v)| v)
            .map(|(k, _)| k.to_string())
            .unwrap_or_else(|| "general".to_string())
    }
}
