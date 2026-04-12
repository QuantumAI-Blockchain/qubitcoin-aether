//! KGQA -- Knowledge Graph Question Answering
//!
//! Answers natural-language questions by querying the knowledge graph.
//! Supports factual lookups, relationship queries, and domain-scoped search.

use serde::{Deserialize, Serialize};

/// The type of question being asked.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum QuestionType {
    /// Simple factual lookup ("What is X?")
    Factual,
    /// Relationship query ("How does X relate to Y?")
    Relational,
    /// Domain-scoped search ("What do we know about domain X?")
    DomainSearch,
    /// Causal query ("Why does X cause Y?")
    Causal,
    /// Unknown / unclassified
    Unknown,
}

/// Result of a QA query.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QAResult {
    /// The answer text
    pub answer: String,
    /// Confidence in the answer (0.0 - 1.0)
    pub confidence: f64,
    /// IDs of knowledge nodes used to derive the answer
    pub source_nodes: Vec<String>,
    /// The classified question type
    pub question_type: QuestionType,
}

/// Knowledge Graph Question Answering engine.
pub struct KGQA {
    /// Minimum confidence threshold for returning answers
    min_confidence: f64,
}

impl KGQA {
    /// Create a new KGQA engine.
    pub fn new() -> Self {
        Self {
            min_confidence: 0.3,
        }
    }

    /// Create with a custom confidence threshold.
    pub fn with_min_confidence(min_confidence: f64) -> Self {
        Self {
            min_confidence: min_confidence.clamp(0.0, 1.0),
        }
    }

    /// Classify a question into a QuestionType.
    pub fn classify_question(&self, question: &str) -> QuestionType {
        let q = question.to_lowercase();
        if q.starts_with("why") || q.contains("cause") || q.contains("because") {
            QuestionType::Causal
        } else if q.contains("relate") || q.contains("between") || q.contains("connection") {
            QuestionType::Relational
        } else if q.starts_with("what") || q.starts_with("who") || q.starts_with("when") {
            QuestionType::Factual
        } else if q.contains("domain") || q.contains("about") || q.contains("know about") {
            QuestionType::DomainSearch
        } else {
            QuestionType::Unknown
        }
    }

    /// Answer a question given a set of candidate knowledge texts and their IDs.
    /// Each candidate is (node_id, content, confidence).
    pub fn answer(
        &self,
        question: &str,
        candidates: &[(String, String, f64)],
    ) -> Option<QAResult> {
        if candidates.is_empty() {
            return None;
        }

        let question_type = self.classify_question(question);

        // Find the best matching candidate by confidence
        let mut best: Option<(usize, f64)> = None;
        for (i, (_, _, conf)) in candidates.iter().enumerate() {
            if *conf >= self.min_confidence {
                match best {
                    None => best = Some((i, *conf)),
                    Some((_, best_conf)) if *conf > best_conf => best = Some((i, *conf)),
                    _ => {}
                }
            }
        }

        best.map(|(idx, conf)| QAResult {
            answer: candidates[idx].1.clone(),
            confidence: conf,
            source_nodes: vec![candidates[idx].0.clone()],
            question_type,
        })
    }

    /// Get the minimum confidence threshold.
    pub fn min_confidence(&self) -> f64 {
        self.min_confidence
    }
}

impl Default for KGQA {
    fn default() -> Self {
        Self::new()
    }
}
