//! Blockchain Entity Extractor
//!
//! Extracts blockchain-specific entities (addresses, transaction hashes,
//! block heights, contract names, token symbols) from raw text data.

use serde::{Deserialize, Serialize};

/// Type of blockchain entity.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum EntityType {
    /// Wallet or contract address
    Address,
    /// Transaction hash
    TransactionHash,
    /// Block height or hash
    Block,
    /// Token symbol (e.g. QBC, QUSD)
    TokenSymbol,
    /// Smart contract name
    ContractName,
    /// Chain identifier
    ChainId,
    /// Generic numeric value
    NumericValue,
}

/// A blockchain entity extracted from text.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockchainEntity {
    /// The extracted entity text
    pub value: String,
    /// Type of entity
    pub entity_type: EntityType,
    /// Character offset in the source text where entity starts
    pub offset: usize,
    /// Confidence of the extraction (0.0 - 1.0)
    pub confidence: f64,
}

/// Extracts blockchain-specific entities from text.
pub struct BlockchainEntityExtractor {
    /// Known token symbols for matching
    known_tokens: Vec<String>,
}

impl BlockchainEntityExtractor {
    /// Create a new extractor with default QBC ecosystem tokens.
    pub fn new() -> Self {
        Self {
            known_tokens: vec![
                "QBC".to_string(),
                "QUSD".to_string(),
                "wQBC".to_string(),
                "wQUSD".to_string(),
            ],
        }
    }

    /// Add additional known token symbols.
    pub fn add_tokens(&mut self, tokens: &[&str]) {
        for t in tokens {
            self.known_tokens.push(t.to_string());
        }
    }

    /// Extract all blockchain entities from a text string.
    pub fn extract(&self, text: &str) -> Vec<BlockchainEntity> {
        let mut entities = Vec::new();

        // Extract hex hashes (64-char hex strings, possibly prefixed with 0x)
        self.extract_hex_patterns(text, &mut entities);

        // Extract known token symbols
        self.extract_token_symbols(text, &mut entities);

        // Extract block heights (plain numbers in context)
        self.extract_block_heights(text, &mut entities);

        entities
    }

    fn extract_hex_patterns(&self, text: &str, entities: &mut Vec<BlockchainEntity>) {
        // Simple pattern: 0x followed by 40 or 64 hex chars
        let bytes = text.as_bytes();
        let len = text.len();
        let mut i = 0;
        while i + 2 < len {
            if i + 1 < len && bytes[i] == b'0' && bytes[i + 1] == b'x' {
                let start = i;
                i += 2;
                let hex_start = i;
                while i < len && bytes[i].is_ascii_hexdigit() {
                    i += 1;
                }
                let hex_len = i - hex_start;
                if hex_len == 40 {
                    entities.push(BlockchainEntity {
                        value: text[start..i].to_string(),
                        entity_type: EntityType::Address,
                        offset: start,
                        confidence: 0.9,
                    });
                } else if hex_len == 64 {
                    entities.push(BlockchainEntity {
                        value: text[start..i].to_string(),
                        entity_type: EntityType::TransactionHash,
                        offset: start,
                        confidence: 0.85,
                    });
                }
            } else {
                i += 1;
            }
        }
    }

    fn extract_token_symbols(&self, text: &str, entities: &mut Vec<BlockchainEntity>) {
        for token in &self.known_tokens {
            if let Some(offset) = text.find(token.as_str()) {
                entities.push(BlockchainEntity {
                    value: token.clone(),
                    entity_type: EntityType::TokenSymbol,
                    offset,
                    confidence: 0.95,
                });
            }
        }
    }

    fn extract_block_heights(&self, text: &str, entities: &mut Vec<BlockchainEntity>) {
        let lower = text.to_lowercase();
        // Look for "block N" or "height N" patterns
        for prefix in &["block ", "height "] {
            if let Some(pos) = lower.find(prefix) {
                let after = pos + prefix.len();
                let num_str: String = text[after..].chars().take_while(|c| c.is_ascii_digit()).collect();
                if !num_str.is_empty() {
                    entities.push(BlockchainEntity {
                        value: num_str,
                        entity_type: EntityType::Block,
                        offset: after,
                        confidence: 0.8,
                    });
                }
            }
        }
    }

    /// Number of known token symbols.
    pub fn known_token_count(&self) -> usize {
        self.known_tokens.len()
    }
}

impl Default for BlockchainEntityExtractor {
    fn default() -> Self {
        Self::new()
    }
}
