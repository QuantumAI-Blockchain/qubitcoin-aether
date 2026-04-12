//! NLP Pipeline — Lightweight text processing for Aether Tree.
//!
//! Tokenization, POS tagging, named entity recognition, dependency parsing.
//! All rule-based / regex — no external NLP libraries required.

use regex::Regex;
use serde::{Deserialize, Serialize};
use std::sync::LazyLock;

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

/// A named entity extracted from text.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct NLPEntity {
    pub text: String,
    pub label: EntityLabel,
    pub start: usize,
    pub end: usize,
    pub confidence: f64,
}

/// Entity label categories.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum EntityLabel {
    Address,
    TxRef,
    BlockRef,
    Amount,
    ContractRef,
    Timestamp,
    CryptoTerm,
}

/// Part-of-speech tag.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum PosTag {
    NN,   // Noun
    NNS,  // Noun plural
    NNP,  // Proper noun
    VB,   // Verb base
    VBD,  // Verb past
    VBG,  // Verb gerund
    JJ,   // Adjective
    JJS,  // Adjective superlative
    RB,   // Adverb
    DT,   // Determiner
    IN,   // Preposition
    CC,   // Conjunction
    PRP,  // Pronoun
    WP,   // Wh-pronoun
    CD,   // Cardinal number
    Punct,
    Sym,
}

/// A dependency arc.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Dependency {
    pub token_index: usize,
    pub head_index: Option<usize>, // None = root
    pub relation: String,
}

/// Full result of NLP pipeline processing.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NLPResult {
    pub raw_text: String,
    pub tokens: Vec<String>,
    pub pos_tags: Vec<PosTag>,
    pub entities: Vec<NLPEntity>,
    pub deps: Vec<Dependency>,
}

/// Pipeline statistics.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PipelineStats {
    pub calls: u64,
    pub total_tokens: u64,
    pub total_entities: u64,
}

// ---------------------------------------------------------------------------
// Word lists
// ---------------------------------------------------------------------------

static DETERMINERS: &[&str] = &[
    "a", "an", "the", "this", "that", "these", "those", "my", "your",
    "his", "her", "its", "our", "their", "some", "any", "no", "every",
];

static PREPOSITIONS: &[&str] = &[
    "in", "on", "at", "to", "for", "with", "from", "by", "of",
    "about", "into", "through", "during", "before", "after",
    "above", "below", "between", "under", "over", "across",
];

static CONJUNCTIONS: &[&str] = &[
    "and", "or", "but", "nor", "yet", "so", "because", "although",
    "while", "if", "when", "unless", "since", "until",
];

static PRONOUNS: &[&str] = &[
    "i", "me", "you", "he", "she", "it", "we", "they", "him", "her",
    "us", "them", "who", "what", "which", "whom", "whose", "myself",
];

static AUX_VERBS: &[&str] = &[
    "is", "am", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "shall", "should", "may", "might", "can", "could", "must",
];

static COMMON_VERBS: &[&str] = &[
    "get", "got", "make", "go", "went", "gone", "take", "took",
    "come", "came", "see", "saw", "know", "knew", "think",
    "thought", "say", "said", "give", "gave", "find", "found",
    "tell", "told", "ask", "asked", "use", "used", "work",
    "worked", "call", "called", "try", "tried", "need",
    "needed", "run", "ran", "mine", "mined", "send", "sent",
    "create", "created", "deploy", "deployed", "stake", "staked",
    "transfer", "transferred", "bridge", "bridged",
];

static WH_WORDS: &[&str] = &["what", "who", "where", "when", "why", "how", "which", "whom"];

static CRYPTO_TERMS: &[&str] = &[
    "bitcoin", "btc", "ethereum", "eth", "qubitcoin", "qbc", "qusd",
    "dilithium", "quantum", "mining", "consensus", "staking", "defi",
    "nft", "token", "blockchain", "block", "hash", "utxo", "wallet",
    "bridge", "swap", "liquidity", "gas", "aether", "sephirot", "phi",
    "susy", "vqe", "hamiltonian", "entanglement", "qvm", "solidity",
    "contract", "governance", "dao", "yield", "miner", "validator",
    "merkle", "genesis", "mainnet", "testnet", "mempool", "difficulty",
    "reward", "halving", "emission", "supply", "address", "signature",
    "keypair", "node", "peer", "gossip", "p2p", "rpc", "api",
];

// Suffix -> POS heuristics
static SUFFIX_POS: &[(&str, PosTag)] = &[
    ("ing", PosTag::VBG),
    ("tion", PosTag::NN),
    ("sion", PosTag::NN),
    ("ment", PosTag::NN),
    ("ness", PosTag::NN),
    ("ity", PosTag::NN),
    ("ance", PosTag::NN),
    ("ence", PosTag::NN),
    ("ism", PosTag::NN),
    ("ist", PosTag::NN),
    ("ous", PosTag::JJ),
    ("ive", PosTag::JJ),
    ("ful", PosTag::JJ),
    ("less", PosTag::JJ),
    ("able", PosTag::JJ),
    ("ible", PosTag::JJ),
    ("al", PosTag::JJ),
    ("ial", PosTag::JJ),
    ("ed", PosTag::VBD),
    ("ly", PosTag::RB),
    ("er", PosTag::NN),
    ("est", PosTag::JJS),
    ("es", PosTag::NNS),
    ("s", PosTag::NNS),
];

// ---------------------------------------------------------------------------
// Regex patterns (lazy static)
// ---------------------------------------------------------------------------

static TOKEN_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"[A-Za-z0-9_]+(?:'[A-Za-z]+)?|[^\s]").unwrap());

static ADDR_HEX: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\b0x[0-9a-fA-F]{40}\b").unwrap());

static TX_HASH: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\b0x[0-9a-fA-F]{64}\b").unwrap());

static BLOCK_REF: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)\bblock\s*#?\s*(\d+)\b").unwrap());

static AMOUNT_QBC: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\b(\d+(?:\.\d+)?)\s*(?:QBC|qbc|QUSD|qusd)\b").unwrap());

static AMOUNT_NUM: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)\b(\d+(?:\.\d+)?)\s*(?:tokens?|coins?)\b").unwrap());

static CONTRACT_NAME: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(QBC-?20|QBC-?721|ERC-?20|ERC-?721|QUSD|AetherTree|HiggsField|SUSYToken)\b")
        .unwrap()
});

static TIMESTAMP_ISO: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2})?Z?\b").unwrap());

// ---------------------------------------------------------------------------
// Helper functions
// ---------------------------------------------------------------------------

fn is_in_list(word: &str, list: &[&str]) -> bool {
    list.iter().any(|&w| w == word)
}

fn is_verb_tag(tag: PosTag) -> bool {
    matches!(tag, PosTag::VB | PosTag::VBD | PosTag::VBG)
}

fn is_noun_tag(tag: PosTag) -> bool {
    matches!(tag, PosTag::NN | PosTag::NNS | PosTag::NNP)
}

// ---------------------------------------------------------------------------
// NLPPipeline
// ---------------------------------------------------------------------------

/// Lightweight NLP pipeline: tokenize -> POS tag -> NER -> dependency parse.
pub struct NLPPipeline {
    stats: PipelineStats,
}

impl NLPPipeline {
    pub fn new() -> Self {
        Self {
            stats: PipelineStats::default(),
        }
    }

    /// Run full NLP pipeline on input text.
    pub fn process(&mut self, text: &str) -> NLPResult {
        let tokens = self.tokenize(text);
        let pos_tags = self.pos_tag(&tokens);
        let entities = self.extract_entities(text, &tokens);
        let deps = self.parse_dependencies(&tokens, &pos_tags);

        self.stats.calls += 1;
        self.stats.total_tokens += tokens.len() as u64;
        self.stats.total_entities += entities.len() as u64;

        NLPResult {
            raw_text: text.to_string(),
            tokens,
            pos_tags,
            entities,
            deps,
        }
    }

    /// Tokenize text into words and punctuation.
    pub fn tokenize(&self, text: &str) -> Vec<String> {
        // Normalize unicode
        let text = text
            .replace('\u{2019}', "'")
            .replace('\u{2018}', "'")
            .replace('\u{201c}', "\"")
            .replace('\u{201d}', "\"")
            .replace('\u{2014}', " -- ")
            .replace('\u{2013}', " - ");

        TOKEN_RE
            .find_iter(&text)
            .map(|m| m.as_str().to_string())
            .collect()
    }

    /// Rule-based POS tagging.
    pub fn pos_tag(&self, tokens: &[String]) -> Vec<PosTag> {
        tokens.iter().map(|token| {
            let lower = token.to_lowercase();

            // Punctuation
            if token.len() == 1 && !token.chars().next().unwrap_or(' ').is_alphanumeric() {
                let ch = token.as_bytes()[0];
                return if ch == b'.' || ch == b'!' || ch == b'?' {
                    PosTag::Punct
                } else if ch == b',' || ch == b';' || ch == b':' {
                    PosTag::Punct
                } else {
                    PosTag::Sym
                };
            }

            // Numbers
            let stripped = token.replace('.', "").replace(',', "");
            if !stripped.is_empty() && stripped.chars().all(|c| c.is_ascii_digit()) {
                return PosTag::CD;
            }

            // Hex addresses
            if lower.starts_with("0x") {
                return PosTag::NNP;
            }

            // Closed-class words
            if is_in_list(&lower, DETERMINERS) {
                PosTag::DT
            } else if is_in_list(&lower, PREPOSITIONS) {
                PosTag::IN
            } else if is_in_list(&lower, CONJUNCTIONS) {
                PosTag::CC
            } else if is_in_list(&lower, PRONOUNS) {
                PosTag::PRP
            } else if is_in_list(&lower, WH_WORDS) {
                PosTag::WP
            } else if is_in_list(&lower, AUX_VERBS) {
                PosTag::VB
            } else if is_in_list(&lower, COMMON_VERBS) {
                PosTag::VB
            } else if is_in_list(&lower, CRYPTO_TERMS) {
                PosTag::NN
            } else if token.chars().next().map_or(false, |c| c.is_uppercase()) && token.len() > 1 {
                PosTag::NNP
            } else {
                // Suffix-based
                for &(suffix, pos) in SUFFIX_POS {
                    if lower.ends_with(suffix) && lower.len() > suffix.len() + 1 {
                        return pos;
                    }
                }
                PosTag::NN
            }
        }).collect()
    }

    /// Regex + dictionary-based Named Entity Recognition.
    pub fn extract_entities(&self, text: &str, tokens: &[String]) -> Vec<NLPEntity> {
        let mut entities: Vec<NLPEntity> = Vec::new();

        // TX hashes (64 hex chars) — check first so addresses don't consume them
        for m in TX_HASH.find_iter(text) {
            entities.push(NLPEntity {
                text: m.as_str().to_string(),
                label: EntityLabel::TxRef,
                start: m.start(),
                end: m.end(),
                confidence: 0.95,
            });
        }

        // Hex addresses (40 hex chars)
        for m in ADDR_HEX.find_iter(text) {
            // Skip if overlaps with a tx hash
            if entities.iter().any(|e| m.start() >= e.start && m.end() <= e.end) {
                continue;
            }
            entities.push(NLPEntity {
                text: m.as_str().to_string(),
                label: EntityLabel::Address,
                start: m.start(),
                end: m.end(),
                confidence: 0.95,
            });
        }

        // Block references
        for m in BLOCK_REF.find_iter(text) {
            entities.push(NLPEntity {
                text: m.as_str().to_string(),
                label: EntityLabel::BlockRef,
                start: m.start(),
                end: m.end(),
                confidence: 0.90,
            });
        }

        // Amounts (QBC/QUSD)
        for m in AMOUNT_QBC.find_iter(text) {
            entities.push(NLPEntity {
                text: m.as_str().to_string(),
                label: EntityLabel::Amount,
                start: m.start(),
                end: m.end(),
                confidence: 0.90,
            });
        }

        // Amounts (generic tokens/coins)
        for m in AMOUNT_NUM.find_iter(text) {
            entities.push(NLPEntity {
                text: m.as_str().to_string(),
                label: EntityLabel::Amount,
                start: m.start(),
                end: m.end(),
                confidence: 0.75,
            });
        }

        // Contract names
        for m in CONTRACT_NAME.find_iter(text) {
            entities.push(NLPEntity {
                text: m.as_str().to_string(),
                label: EntityLabel::ContractRef,
                start: m.start(),
                end: m.end(),
                confidence: 0.85,
            });
        }

        // Timestamps
        for m in TIMESTAMP_ISO.find_iter(text) {
            entities.push(NLPEntity {
                text: m.as_str().to_string(),
                label: EntityLabel::Timestamp,
                start: m.start(),
                end: m.end(),
                confidence: 0.85,
            });
        }

        // Crypto terms (token-level)
        for token in tokens {
            if is_in_list(&token.to_lowercase(), CRYPTO_TERMS) {
                entities.push(NLPEntity {
                    text: token.clone(),
                    label: EntityLabel::CryptoTerm,
                    start: 0,
                    end: 0,
                    confidence: 0.80,
                });
            }
        }

        // Deduplicate by (start, end, label) — keep highest confidence
        entities.sort_by(|a, b| a.start.cmp(&b.start).then(a.end.cmp(&b.end)));
        entities.dedup_by(|a, b| {
            if a.start == b.start && a.end == b.end && a.label == b.label {
                if a.confidence > b.confidence {
                    std::mem::swap(a, b);
                }
                true
            } else {
                false
            }
        });

        entities
    }

    /// Simple head-finding dependency parse.
    pub fn parse_dependencies(&self, tokens: &[String], pos_tags: &[PosTag]) -> Vec<Dependency> {
        let n = tokens.len();
        if n == 0 {
            return Vec::new();
        }

        // Find root: first verb
        let root_idx = pos_tags
            .iter()
            .position(|t| is_verb_tag(*t))
            .or_else(|| pos_tags.iter().position(|t| is_noun_tag(*t)))
            .unwrap_or(0);

        let mut deps: Vec<Dependency> = Vec::with_capacity(n);

        for i in 0..n {
            if i == root_idx {
                deps.push(Dependency {
                    token_index: i,
                    head_index: None,
                    relation: "root".to_string(),
                });
                continue;
            }

            let tag = pos_tags[i];
            let (head, relation) = match tag {
                PosTag::DT => {
                    let head = find_next_noun(pos_tags, i + 1).unwrap_or(root_idx);
                    (head, "det")
                }
                PosTag::JJ | PosTag::JJS => {
                    let head = find_next_noun(pos_tags, i + 1).unwrap_or(root_idx);
                    (head, "amod")
                }
                PosTag::RB => {
                    let head = find_nearest_verb(pos_tags, i).unwrap_or(root_idx);
                    (head, "advmod")
                }
                PosTag::IN => (root_idx, "prep"),
                PosTag::CC => (root_idx, "cc"),
                PosTag::PRP | PosTag::WP => {
                    if i < root_idx {
                        (root_idx, "nsubj")
                    } else {
                        (root_idx, "dobj")
                    }
                }
                PosTag::NN | PosTag::NNS | PosTag::NNP => {
                    if i < root_idx {
                        (root_idx, "nsubj")
                    } else {
                        (root_idx, "dobj")
                    }
                }
                PosTag::CD => {
                    let head = find_nearest_noun(pos_tags, i).unwrap_or(root_idx);
                    (head, "nummod")
                }
                PosTag::Punct => (root_idx, "punct"),
                _ => (root_idx, "dep"),
            };

            deps.push(Dependency {
                token_index: i,
                head_index: Some(head),
                relation: relation.to_string(),
            });
        }

        deps
    }

    /// Get pipeline statistics.
    pub fn get_stats(&self) -> &PipelineStats {
        &self.stats
    }
}

impl Default for NLPPipeline {
    fn default() -> Self {
        Self::new()
    }
}

fn find_next_noun(tags: &[PosTag], start: usize) -> Option<usize> {
    tags[start..].iter().position(|t| is_noun_tag(*t)).map(|i| i + start)
}

fn find_nearest_verb(tags: &[PosTag], origin: usize) -> Option<usize> {
    let mut best: Option<usize> = None;
    let mut best_dist = usize::MAX;
    for (i, &tag) in tags.iter().enumerate() {
        if i == origin {
            continue;
        }
        if is_verb_tag(tag) {
            let dist = if i > origin { i - origin } else { origin - i };
            if dist < best_dist {
                best = Some(i);
                best_dist = dist;
            }
        }
    }
    best
}

fn find_nearest_noun(tags: &[PosTag], origin: usize) -> Option<usize> {
    let mut best: Option<usize> = None;
    let mut best_dist = usize::MAX;
    for (i, &tag) in tags.iter().enumerate() {
        if i == origin {
            continue;
        }
        if is_noun_tag(tag) {
            let dist = if i > origin { i - origin } else { origin - i };
            if dist < best_dist {
                best = Some(i);
                best_dist = dist;
            }
        }
    }
    best
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tokenize_basic() {
        let pipe = NLPPipeline::new();
        let tokens = pipe.tokenize("Hello world! This is a test.");
        assert!(tokens.contains(&"Hello".to_string()));
        assert!(tokens.contains(&"world".to_string()));
        assert!(tokens.contains(&"!".to_string()));
    }

    #[test]
    fn test_pos_tag_basic() {
        let pipe = NLPPipeline::new();
        let tokens = vec!["the".to_string(), "miner".to_string(), "is".to_string(), "running".to_string()];
        let tags = pipe.pos_tag(&tokens);
        assert_eq!(tags[0], PosTag::DT);
        assert_eq!(tags[2], PosTag::VB);
        assert_eq!(tags[3], PosTag::VBG);
    }

    #[test]
    fn test_extract_entities_address() {
        let pipe = NLPPipeline::new();
        let text = "Send to 0x1234567890abcdef1234567890abcdef12345678 please";
        let tokens = pipe.tokenize(text);
        let entities = pipe.extract_entities(text, &tokens);
        assert!(entities.iter().any(|e| e.label == EntityLabel::Address));
    }

    #[test]
    fn test_extract_entities_amount() {
        let pipe = NLPPipeline::new();
        let text = "Transfer 100.5 QBC to the wallet";
        let tokens = pipe.tokenize(text);
        let entities = pipe.extract_entities(text, &tokens);
        assert!(entities.iter().any(|e| e.label == EntityLabel::Amount));
    }

    #[test]
    fn test_extract_entities_block_ref() {
        let pipe = NLPPipeline::new();
        let text = "Check block #12345 for details";
        let tokens = pipe.tokenize(text);
        let entities = pipe.extract_entities(text, &tokens);
        assert!(entities.iter().any(|e| e.label == EntityLabel::BlockRef));
    }

    #[test]
    fn test_full_pipeline() {
        let mut pipe = NLPPipeline::new();
        let result = pipe.process("The miner created block #100 with 5 QBC reward");
        assert!(!result.tokens.is_empty());
        assert_eq!(result.tokens.len(), result.pos_tags.len());
        assert!(!result.entities.is_empty());
        assert!(result.deps.iter().any(|d| d.relation == "root"));
    }

    #[test]
    fn test_dependency_parse_has_root() {
        let pipe = NLPPipeline::new();
        let tokens = vec!["she".to_string(), "mined".to_string(), "a".to_string(), "block".to_string()];
        let tags = pipe.pos_tag(&tokens);
        let deps = pipe.parse_dependencies(&tokens, &tags);
        assert!(deps.iter().any(|d| d.head_index.is_none() && d.relation == "root"));
    }
}
