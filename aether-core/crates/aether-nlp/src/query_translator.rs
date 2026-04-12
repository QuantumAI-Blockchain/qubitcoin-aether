//! Query Translator — Natural language to structured knowledge graph queries.
//!
//! Translates user queries into structured queries with intent classification,
//! keyword extraction, entity identification, and filter generation.

use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::sync::LazyLock;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Query intent categories.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum QueryIntentType {
    Factual,
    Causal,
    Temporal,
    Relational,
    Exploratory,
    Analytical,
}

impl QueryIntentType {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Factual => "factual",
            Self::Causal => "causal",
            Self::Temporal => "temporal",
            Self::Relational => "relational",
            Self::Exploratory => "exploratory",
            Self::Analytical => "analytical",
        }
    }
}

/// Parsed intent from a natural language query.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryIntent {
    pub intent_type: QueryIntentType,
    pub keywords: Vec<String>,
    pub raw_query: String,
    pub confidence: f64,
}

/// A structured query to execute against the knowledge graph.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StructuredQuery {
    pub intent: QueryIntent,
    pub entities: Vec<String>,
    pub filters: Vec<QueryFilter>,
    pub sort_order: SortOrder,
    pub max_results: usize,
}

/// Filter for query results.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryFilter {
    pub field: String,
    pub operator: FilterOp,
    pub value: String,
}

/// Filter operator.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum FilterOp {
    Equals,
    Contains,
    GreaterThan,
    LessThan,
}

/// Sort order for results.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum SortOrder {
    Relevance,
    Recency,
    Confidence,
}

// ---------------------------------------------------------------------------
// Signal words
// ---------------------------------------------------------------------------

static CAUSAL_SIGNALS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    ["why", "because", "cause", "reason", "due", "result", "effect", "leads"]
        .iter().copied().collect()
});

static TEMPORAL_SIGNALS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    ["when", "before", "after", "during", "since", "until", "time", "block", "recent"]
        .iter().copied().collect()
});

static RELATIONAL_SIGNALS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    ["how", "related", "between", "connection", "link", "relationship", "compare"]
        .iter().copied().collect()
});

static ANALYTICAL_SIGNALS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    ["pattern", "trend", "analyze", "statistics", "average", "distribution"]
        .iter().copied().collect()
});

static FACTUAL_SIGNALS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    ["what", "which", "who", "where", "define", "explain"]
        .iter().copied().collect()
});

static STOP_WORDS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    [
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "about", "up",
        "out", "if", "or", "and", "but", "not", "no", "so", "than", "too",
        "very", "just", "that", "this", "it", "its", "my", "me", "i",
        "you", "your", "we", "they", "them", "he", "she", "tell",
    ].iter().copied().collect()
});

// ---------------------------------------------------------------------------
// QueryTranslator
// ---------------------------------------------------------------------------

/// Translate natural language queries into structured knowledge graph queries.
pub struct QueryTranslator {
    calls: u64,
}

impl QueryTranslator {
    pub fn new() -> Self {
        Self { calls: 0 }
    }

    /// Translate a natural language query into a structured query.
    pub fn translate(&mut self, query: &str) -> StructuredQuery {
        self.calls += 1;

        let intent = self.classify_intent(query);
        let entities = self.extract_entities(query);
        let filters = self.extract_filters(query, &intent);
        let sort_order = match intent.intent_type {
            QueryIntentType::Temporal => SortOrder::Recency,
            QueryIntentType::Analytical => SortOrder::Confidence,
            _ => SortOrder::Relevance,
        };

        StructuredQuery {
            intent,
            entities,
            filters,
            sort_order,
            max_results: 10,
        }
    }

    /// Classify the intent of a natural language query.
    pub fn classify_intent(&self, query: &str) -> QueryIntent {
        let query_lower = query.to_lowercase();
        let words: HashSet<&str> = query_lower
            .split(|c: char| !c.is_alphanumeric())
            .filter(|w| !w.is_empty())
            .collect();

        let scores = [
            (QueryIntentType::Causal, words.iter().filter(|w| CAUSAL_SIGNALS.contains(*w)).count()),
            (QueryIntentType::Temporal, words.iter().filter(|w| TEMPORAL_SIGNALS.contains(*w)).count()),
            (QueryIntentType::Relational, words.iter().filter(|w| RELATIONAL_SIGNALS.contains(*w)).count()),
            (QueryIntentType::Analytical, words.iter().filter(|w| ANALYTICAL_SIGNALS.contains(*w)).count()),
            (QueryIntentType::Factual, words.iter().filter(|w| FACTUAL_SIGNALS.contains(*w)).count()),
        ];

        let (best_intent, best_score) = scores
            .iter()
            .max_by_key(|(_, s)| *s)
            .map(|(t, s)| (*t, *s))
            .unwrap_or((QueryIntentType::Exploratory, 0));

        let intent_type = if best_score == 0 {
            QueryIntentType::Exploratory
        } else {
            best_intent
        };

        // Extract keywords (non-stop words, length > 2)
        let keywords: Vec<String> = query_lower
            .split(|c: char| !c.is_alphanumeric())
            .filter(|w| w.len() > 2 && !STOP_WORDS.contains(w))
            .map(|w| w.to_string())
            .collect();

        let confidence = (0.3 + (best_score as f64 * 0.2) + (keywords.len() as f64 * 0.05)).min(0.9);

        QueryIntent {
            intent_type,
            keywords,
            raw_query: query.to_string(),
            confidence,
        }
    }

    /// Extract entity references from the query.
    fn extract_entities(&self, query: &str) -> Vec<String> {
        let query_lower = query.to_lowercase();
        let mut entities = Vec::new();

        // Look for known entity patterns
        let entity_keywords = [
            "blockchain", "block", "transaction", "tx", "contract", "address", "wallet",
            "node", "token", "bridge", "chain", "network", "miner",
        ];

        for &kw in &entity_keywords {
            if query_lower.contains(kw) {
                entities.push(kw.to_string());
            }
        }

        // Look for hex addresses
        if query_lower.contains("0x") {
            entities.push("hex_reference".to_string());
        }

        entities
    }

    /// Extract filters from the query based on intent.
    fn extract_filters(&self, query: &str, intent: &QueryIntent) -> Vec<QueryFilter> {
        let mut filters = Vec::new();
        let query_lower = query.to_lowercase();

        // Domain filter from keywords
        let domain_keywords = [
            ("blockchain", "blockchain"),
            ("quantum", "quantum_physics"),
            ("economic", "economics"),
            ("security", "security"),
            ("governance", "governance"),
        ];

        for &(keyword, domain) in &domain_keywords {
            if query_lower.contains(keyword) {
                filters.push(QueryFilter {
                    field: "domain".to_string(),
                    operator: FilterOp::Equals,
                    value: domain.to_string(),
                });
                break;
            }
        }

        // Temporal filter
        if intent.intent_type == QueryIntentType::Temporal {
            if query_lower.contains("recent") || query_lower.contains("latest") {
                filters.push(QueryFilter {
                    field: "sort".to_string(),
                    operator: FilterOp::Equals,
                    value: "recency".to_string(),
                });
            }
        }

        // Confidence filter
        if query_lower.contains("certain") || query_lower.contains("confident") {
            filters.push(QueryFilter {
                field: "confidence".to_string(),
                operator: FilterOp::GreaterThan,
                value: "0.8".to_string(),
            });
        }

        filters
    }

    /// Get translator statistics.
    pub fn get_calls(&self) -> u64 {
        self.calls
    }
}

impl Default for QueryTranslator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_classify_causal() {
        let translator = QueryTranslator::new();
        let intent = translator.classify_intent("Why did the difficulty increase?");
        assert_eq!(intent.intent_type, QueryIntentType::Causal);
    }

    #[test]
    fn test_classify_temporal() {
        let translator = QueryTranslator::new();
        let intent = translator.classify_intent("When was the last block mined?");
        assert_eq!(intent.intent_type, QueryIntentType::Temporal);
    }

    #[test]
    fn test_classify_relational() {
        let translator = QueryTranslator::new();
        let intent = translator.classify_intent("How is mining related to consensus?");
        assert_eq!(intent.intent_type, QueryIntentType::Relational);
    }

    #[test]
    fn test_classify_factual() {
        let translator = QueryTranslator::new();
        let intent = translator.classify_intent("What is the current block height?");
        assert_eq!(intent.intent_type, QueryIntentType::Factual);
    }

    #[test]
    fn test_classify_exploratory() {
        let translator = QueryTranslator::new();
        let intent = translator.classify_intent("Tell me about QBC");
        assert_eq!(intent.intent_type, QueryIntentType::Exploratory);
    }

    #[test]
    fn test_translate_full() {
        let mut translator = QueryTranslator::new();
        let query = translator.translate("Why did the blockchain difficulty change recently?");
        assert_eq!(query.intent.intent_type, QueryIntentType::Causal);
        assert!(!query.intent.keywords.is_empty());
        assert!(query.entities.contains(&"blockchain".to_string()));
    }

    #[test]
    fn test_keyword_extraction() {
        let translator = QueryTranslator::new();
        let intent = translator.classify_intent("What is quantum mining efficiency?");
        assert!(intent.keywords.contains(&"quantum".to_string()));
        assert!(intent.keywords.contains(&"mining".to_string()));
        assert!(intent.keywords.contains(&"efficiency".to_string()));
    }
}
