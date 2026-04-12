//! Knowledge Scorer -- Quality, novelty, and anti-gaming scoring.
//!
//! Evaluates knowledge contributions on three axes:
//!   1. Quality (0-1.0): Specificity, concreteness, coherence, factual density
//!   2. Novelty (0-1.0): Distance from existing knowledge (higher = more novel)
//!   3. Gaming detection: Detects spam, paraphrasing, low-effort submissions
//!
//! Combined score determines quality tier: Diamond >= 0.90, Gold >= 0.70,
//! Silver >= 0.40, Bronze < 0.40.

use parking_lot::Mutex;
use regex::Regex;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};

/// Quality tier for a contribution.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum QualityTier {
    Diamond,
    Gold,
    Silver,
    Bronze,
}

impl QualityTier {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Diamond => "diamond",
            Self::Gold => "gold",
            Self::Silver => "silver",
            Self::Bronze => "bronze",
        }
    }
}

/// Result of scoring a knowledge contribution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContributionScore {
    pub quality_score: f64,
    pub novelty_score: f64,
    pub combined_score: f64,
    pub tier: QualityTier,
    pub is_spam: bool,
    pub spam_reason: String,
    pub domain: String,
    pub content_hash: String,
}

/// Domain keywords for classification.
pub fn domain_keywords() -> HashMap<&'static str, Vec<&'static str>> {
    let mut m = HashMap::new();
    m.insert("quantum_physics", vec!["quantum", "qubit", "superposition", "entanglement", "hamiltonian", "vqe"]);
    m.insert("mathematics", vec!["theorem", "proof", "equation", "formula", "integral", "algebra"]);
    m.insert("computer_science", vec!["algorithm", "complexity", "compiler", "data structure", "hash", "graph"]);
    m.insert("blockchain", vec!["block", "transaction", "consensus", "mining", "chain", "utxo", "merkle"]);
    m.insert("cryptography", vec!["cipher", "encryption", "signature", "dilithium", "kyber", "hash"]);
    m.insert("philosophy", vec!["consciousness", "epistemology", "ontology", "ethics", "reason"]);
    m.insert("biology", vec!["cell", "protein", "gene", "dna", "evolution", "organism"]);
    m.insert("physics", vec!["force", "energy", "mass", "velocity", "relativity", "particle"]);
    m.insert("economics", vec!["market", "supply", "demand", "inflation", "monetary", "fiscal"]);
    m.insert("ai_ml", vec!["neural", "training", "model", "inference", "gradient", "transformer"]);
    m
}

/// Knowledge scorer for evaluating contributions.
pub struct KnowledgeScorer {
    content_hashes: Mutex<HashSet<String>>,
    recent_contributions: Mutex<Vec<String>>,
    quality_weight: f64,
    novelty_weight: f64,
    score_count: Mutex<u64>,
    flagged_count: Mutex<u64>,
    max_recent: usize,
    max_hashes: usize,
}

impl KnowledgeScorer {
    pub fn new() -> Self {
        Self {
            content_hashes: Mutex::new(HashSet::new()),
            recent_contributions: Mutex::new(Vec::new()),
            quality_weight: 0.6,
            novelty_weight: 0.4,
            score_count: Mutex::new(0),
            flagged_count: Mutex::new(0),
            max_recent: 1000,
            max_hashes: 100_000,
        }
    }

    /// Create scorer with custom weights.
    pub fn with_weights(quality_weight: f64, novelty_weight: f64) -> Self {
        Self {
            quality_weight,
            novelty_weight,
            ..Self::new()
        }
    }

    /// Score a knowledge contribution.
    pub fn score_contribution(&self, content: &str) -> ContributionScore {
        let content_hash = self.compute_hash(content);

        // 1. Spam / gaming detection
        let (is_spam, spam_reason) = self.detect_gaming(content, &content_hash);
        if is_spam {
            *self.flagged_count.lock() += 1;
            return ContributionScore {
                quality_score: 0.0,
                novelty_score: 0.0,
                combined_score: 0.0,
                tier: QualityTier::Bronze,
                is_spam: true,
                spam_reason,
                domain: String::new(),
                content_hash,
            };
        }

        // 2. Quality scoring
        let quality = self.score_quality(content);

        // 3. Novelty scoring (without vector index, use hash-based estimate)
        let novelty = self.score_novelty(content);

        // 4. Domain detection
        let domain = self.detect_domain(content);

        // 5. Combined score
        let combined = quality * self.quality_weight + novelty * self.novelty_weight;

        // 6. Determine tier
        let tier = Self::determine_tier(combined);

        // Track for future detection
        {
            let mut hashes = self.content_hashes.lock();
            hashes.insert(content_hash.clone());
            if hashes.len() > self.max_hashes {
                let keep: Vec<String> = hashes.iter().skip(hashes.len() / 2).cloned().collect();
                *hashes = keep.into_iter().collect();
            }
        }
        {
            let mut recent = self.recent_contributions.lock();
            recent.push(content.to_lowercase());
            if recent.len() > self.max_recent {
                let start = recent.len() - self.max_recent;
                *recent = recent[start..].to_vec();
            }
        }
        *self.score_count.lock() += 1;

        ContributionScore {
            quality_score: quality,
            novelty_score: novelty,
            combined_score: combined,
            tier,
            is_spam: false,
            spam_reason: String::new(),
            domain,
            content_hash,
        }
    }

    /// Score a batch of contributions.
    pub fn score_batch(&self, contents: &[&str]) -> Vec<ContributionScore> {
        contents.iter().map(|c| self.score_contribution(c)).collect()
    }

    /// Get candidates for pruning based on a score threshold.
    pub fn get_pruning_candidates(
        &self,
        nodes: &[(u64, f64, usize, usize, f64, f64, bool)],
        threshold: f64,
    ) -> Vec<u64> {
        // Each tuple: (node_id, confidence, edge_degree, reference_count, recency_score, type_score, is_grounded)
        nodes.iter()
            .filter_map(|&(id, confidence, edge_degree, ref_count, recency, type_score, grounded)| {
                let score = type_score * 0.3
                    + (edge_degree as f64).min(10.0) / 10.0 * 0.2
                    + (ref_count as f64).min(10.0) / 10.0 * 0.2
                    + confidence * 0.15
                    + recency * 0.1
                    + if grounded { 0.05 } else { 0.0 };
                if score < threshold { Some(id) } else { None }
            })
            .collect()
    }

    fn score_quality(&self, content: &str) -> f64 {
        let mut score = 0.5_f64;
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

        // Numbers indicate specificity
        let num_re = Regex::new(r"\d+\.?\d*").unwrap();
        let num_count = num_re.find_iter(content).count();
        score += (num_count as f64 * 0.03).min(0.15);

        // Technical terms (long words)
        let technical = words.iter().filter(|w| w.len() > 8).count();
        score += (technical as f64 * 0.02).min(0.1);

        // Factual signals
        let factual_signals = [
            "defined as", "measured", "equals", "consists of",
            "proven", "demonstrated", "published", "according to",
            "formula", "theorem", "equation", "property",
        ];
        let fact_hits = factual_signals.iter().filter(|s| lower.contains(*s)).count();
        score += (fact_hits as f64 * 0.05).min(0.15);

        // Vague penalties
        let vague_signals = [
            "it depends", "generally", "it varies", "maybe",
            "sort of", "kind of", "basically", "honestly",
        ];
        let vague_hits = vague_signals.iter().filter(|s| lower.contains(*s)).count();
        score -= (vague_hits as f64 * 0.05).min(0.2);

        // Structure bonus
        let structure_signals = ["first", "second", "therefore", "however", "furthermore", "because"];
        let struct_hits = structure_signals.iter().filter(|s| lower.contains(*s)).count();
        score += (struct_hits as f64 * 0.03).min(0.1);

        // Unique word ratio
        if word_count > 10 {
            let unique: HashSet<&str> = words.iter().map(|w| *w).collect();
            let ratio = unique.len() as f64 / word_count as f64;
            if ratio < 0.4 {
                score -= 0.15;
            } else if ratio > 0.7 {
                score += 0.05;
            }
        }

        score.clamp(0.0, 1.0)
    }

    fn score_novelty(&self, content: &str) -> f64 {
        // Without vector index, estimate novelty using Jaccard similarity to recent
        let content_lower = content.to_lowercase();
        let content_words: HashSet<&str> = content_lower.split_whitespace().collect();
        let recent = self.recent_contributions.lock();

        if recent.is_empty() {
            return 0.9; // Very novel if nothing to compare
        }

        let mut max_sim = 0.0_f64;
        for r in recent.iter().rev().take(50) {
            let recent_words: HashSet<&str> = r.split_whitespace().collect();
            if content_words.is_empty() || recent_words.is_empty() {
                continue;
            }
            let intersection = content_words.iter().filter(|w| recent_words.contains(*w)).count();
            let union = content_words.len() + recent_words.len() - intersection;
            if union > 0 {
                let sim = intersection as f64 / union as f64;
                max_sim = max_sim.max(sim);
            }
        }

        (1.0 - max_sim).max(0.0)
    }

    fn detect_gaming(&self, content: &str, content_hash: &str) -> (bool, String) {
        // 1. Exact duplicate
        if self.content_hashes.lock().contains(content_hash) {
            return (true, "exact_duplicate".into());
        }

        let lower = content.trim().to_lowercase();

        // 2. Too short
        if lower.len() < 20 {
            return (true, "too_short".into());
        }

        // 3. Gibberish (low alpha ratio)
        let alpha_count = content.chars().filter(|c| c.is_alphabetic()).count();
        if !content.is_empty() && (alpha_count as f64 / content.len() as f64) < 0.4 {
            return (true, "gibberish".into());
        }

        // 4. All caps
        let upper_count = content.chars().filter(|c| c.is_uppercase()).count();
        if content.len() > 20 && (upper_count as f64 / content.len() as f64) > 0.8 {
            return (true, "all_caps".into());
        }

        // 5. Excessive repetition
        let words: Vec<&str> = lower.split_whitespace().collect();
        if words.len() > 5 {
            let mut freq: HashMap<&str, usize> = HashMap::new();
            for w in &words {
                *freq.entry(w).or_default() += 1;
            }
            let max_freq = *freq.values().max().unwrap_or(&0);
            if max_freq > 5 && (max_freq as f64 / words.len() as f64) > 0.3 {
                return (true, "excessive_repetition".into());
            }
        }

        // 6. Near-duplicate via Jaccard
        let content_words: HashSet<&str> = lower.split_whitespace().collect();
        let recent = self.recent_contributions.lock();
        for r in recent.iter().rev().take(100) {
            let recent_words: HashSet<&str> = r.split_whitespace().collect();
            if content_words.is_empty() || recent_words.is_empty() {
                continue;
            }
            let intersection = content_words.iter().filter(|w| recent_words.contains(*w)).count();
            let union = content_words.len() + recent_words.len() - intersection;
            if union > 0 && (intersection as f64 / union as f64) > 0.85 {
                return (true, "near_duplicate".into());
            }
        }

        (false, String::new())
    }

    fn detect_domain(&self, content: &str) -> String {
        let lower = content.to_lowercase();
        let keywords = domain_keywords();
        let mut scores: HashMap<&str, usize> = HashMap::new();

        for (domain, kws) in &keywords {
            let count = kws.iter().filter(|kw| lower.contains(*kw)).count();
            if count > 0 {
                scores.insert(domain, count);
            }
        }

        scores.into_iter()
            .max_by_key(|(_, v)| *v)
            .map(|(k, _)| k.to_string())
            .unwrap_or_else(|| "general".into())
    }

    fn determine_tier(combined: f64) -> QualityTier {
        if combined >= 0.90 {
            QualityTier::Diamond
        } else if combined >= 0.70 {
            QualityTier::Gold
        } else if combined >= 0.40 {
            QualityTier::Silver
        } else {
            QualityTier::Bronze
        }
    }

    fn compute_hash(&self, content: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(content.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    /// Get scorer statistics.
    pub fn get_stats(&self) -> HashMap<String, serde_json::Value> {
        let mut stats = HashMap::new();
        stats.insert("total_scored".into(), serde_json::json!(*self.score_count.lock()));
        stats.insert("total_flagged".into(), serde_json::json!(*self.flagged_count.lock()));
        stats.insert("unique_hashes".into(), serde_json::json!(self.content_hashes.lock().len()));
        stats.insert("recent_buffer_size".into(), serde_json::json!(self.recent_contributions.lock().len()));
        stats.insert("quality_weight".into(), serde_json::json!(self.quality_weight));
        stats.insert("novelty_weight".into(), serde_json::json!(self.novelty_weight));
        stats
    }
}

impl Default for KnowledgeScorer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_high_quality_content() {
        let scorer = KnowledgeScorer::new();
        let content = "The Variational Quantum Eigensolver (VQE) is defined as a hybrid \
                       quantum-classical algorithm that finds ground state energy. It uses \
                       parameterized quantum circuits with 4 qubits and converges in approximately \
                       100 iterations. Therefore, VQE demonstrates the variational principle.";
        let score = scorer.score_contribution(content);
        assert!(!score.is_spam);
        assert!(score.quality_score > 0.5);
        assert_eq!(score.domain, "quantum_physics");
    }

    #[test]
    fn test_spam_detection_too_short() {
        let scorer = KnowledgeScorer::new();
        let score = scorer.score_contribution("hi");
        assert!(score.is_spam);
        assert_eq!(score.spam_reason, "too_short");
    }

    #[test]
    fn test_spam_detection_duplicate() {
        let scorer = KnowledgeScorer::new();
        let content = "This is a valid contribution about blockchain technology and consensus.";
        let _ = scorer.score_contribution(content);
        let score2 = scorer.score_contribution(content);
        assert!(score2.is_spam);
        assert_eq!(score2.spam_reason, "exact_duplicate");
    }

    #[test]
    fn test_spam_detection_repetition() {
        let scorer = KnowledgeScorer::new();
        let content = "spam spam spam spam spam spam spam spam spam spam spam spam";
        let score = scorer.score_contribution(content);
        assert!(score.is_spam);
        assert_eq!(score.spam_reason, "excessive_repetition");
    }

    #[test]
    fn test_tier_determination() {
        assert_eq!(KnowledgeScorer::determine_tier(0.95), QualityTier::Diamond);
        assert_eq!(KnowledgeScorer::determine_tier(0.75), QualityTier::Gold);
        assert_eq!(KnowledgeScorer::determine_tier(0.50), QualityTier::Silver);
        assert_eq!(KnowledgeScorer::determine_tier(0.20), QualityTier::Bronze);
    }

    #[test]
    fn test_pruning_candidates() {
        let scorer = KnowledgeScorer::new();
        let nodes = vec![
            // (id, confidence, edges, refs, recency, type_score, grounded)
            (1, 0.9, 5, 3, 0.8, 0.8, true),   // High score
            (2, 0.1, 0, 0, 0.1, 0.1, false),   // Low score -> prune
            (3, 0.5, 2, 1, 0.5, 0.5, false),   // Mid score
        ];
        let candidates = scorer.get_pruning_candidates(&nodes, 0.3);
        assert!(candidates.contains(&2));
        assert!(!candidates.contains(&1));
    }

    #[test]
    fn test_domain_detection() {
        let scorer = KnowledgeScorer::new();
        let content = "The transformer architecture uses attention mechanisms for neural network training";
        let score = scorer.score_contribution(content);
        assert_eq!(score.domain, "ai_ml");
    }
}
