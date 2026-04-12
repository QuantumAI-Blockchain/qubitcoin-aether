//! Coreference Resolution — Resolve pronouns/references in multi-turn chat.
//!
//! Rule-based: track noun phrases, replace pronouns with most recent matching antecedent.

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// A mention of an entity in text.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Mention {
    pub text: String,
    pub entity_id: String,
    pub position: usize,
    pub entity_type: String,
}

/// An entity registered for coreference tracking.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegisteredEntity {
    pub id: String,
    pub entity_type: String,
    pub text: String,
    pub turn: u32,
}

/// Pronoun types and the entity categories they typically refer to.
fn pronoun_types(pronoun: &str) -> Option<&'static [&'static str]> {
    match pronoun {
        "it" | "its" => Some(&["block", "transaction", "contract", "address", "metric", "token", "concept"]),
        "this" | "that" => Some(&["block", "transaction", "contract", "address", "metric", "topic", "concept"]),
        "they" | "them" | "their" => Some(&["address", "node", "peer", "validator", "agent"]),
        "these" | "those" => Some(&["block", "transaction", "contract", "node"]),
        _ => None,
    }
}

/// Map a word to an entity type.
fn type_from_word(word: &str) -> Option<&'static str> {
    match word {
        "block" => Some("block"),
        "transaction" | "tx" => Some("transaction"),
        "contract" => Some("contract"),
        "address" | "wallet" | "miner" => Some("address"),
        "node" => Some("node"),
        "peer" => Some("peer"),
        "token" => Some("token"),
        "bridge" => Some("bridge"),
        "chain" => Some("chain"),
        "network" => Some("network"),
        "reward" | "difficulty" | "phi" => Some("metric"),
        _ => None,
    }
}

// ---------------------------------------------------------------------------
// CoreferenceResolver
// ---------------------------------------------------------------------------

/// Resolve pronouns and references in multi-turn chat.
pub struct CoreferenceResolver {
    entity_register: VecDeque<RegisteredEntity>,
    max_register: usize,
    resolves: u64,
    successful_resolutions: u64,
}

impl CoreferenceResolver {
    pub fn new() -> Self {
        Self {
            entity_register: VecDeque::new(),
            max_register: 200,
            resolves: 0,
            successful_resolutions: 0,
        }
    }

    /// Resolve pronouns and references in text using registered entities.
    ///
    /// Returns text with pronouns replaced by `[referent]`.
    pub fn resolve(&mut self, text: &str, context: &[RegisteredEntity]) -> String {
        self.resolves += 1;

        // Update register with new context
        for entity in context {
            self.register_entity(entity.clone());
        }

        if self.entity_register.is_empty() {
            return text.to_string();
        }

        let mut replacements: Vec<(usize, usize, String)> = Vec::new();
        let text_lower = text.to_lowercase();

        // Resolve pronouns
        let pronouns = ["it", "its", "this", "that", "they", "them", "their", "these", "those"];
        for pronoun in &pronouns {
            if let Some(expected_types) = pronoun_types(pronoun) {
                let search = format!(" {} ", pronoun);
                let mut start = 0;
                while let Some(pos) = text_lower[start..].find(&search) {
                    let actual_pos = start + pos + 1; // skip leading space
                    let end_pos = actual_pos + pronoun.len();
                    if let Some(ref_text) = self.find_referent(expected_types).map(|r| r.text.clone()) {
                        self.successful_resolutions += 1;
                        replacements.push((actual_pos, end_pos, format!("[{}]", ref_text)));
                    }
                    start = start + pos + search.len();
                }
                // Check at start of text
                if text_lower.starts_with(*pronoun)
                    && text.get(pronoun.len()..pronoun.len() + 1).map_or(false, |c| !c.chars().next().unwrap_or('a').is_alphanumeric())
                {
                    if let Some(ref_text) = self.find_referent(expected_types).map(|r| r.text.clone()) {
                        self.successful_resolutions += 1;
                        replacements.push((0, pronoun.len(), format!("[{}]", ref_text)));
                    }
                }
            }
        }

        // Resolve "the <entity_type>" references
        let reference_patterns = [
            ("the block", "block"),
            ("the transaction", "transaction"),
            ("the contract", "contract"),
            ("the address", "address"),
            ("the wallet", "address"),
            ("the node", "node"),
            ("the token", "token"),
        ];

        for &(pattern, entity_type) in &reference_patterns {
            if let Some(pos) = text_lower.find(pattern) {
                if let Some(ref_text) = self.find_referent(&[entity_type]).map(|r| r.text.clone()) {
                    self.successful_resolutions += 1;
                    replacements.push((pos, pos + pattern.len(), format!("[{}]", ref_text)));
                }
            }
        }

        // Remove overlapping replacements (keep first)
        replacements.sort_by_key(|r| r.0);
        let mut non_overlapping: Vec<(usize, usize, String)> = Vec::new();
        let mut last_end = 0;
        for (start, end, repl) in replacements {
            if start >= last_end {
                non_overlapping.push((start, end, repl));
                last_end = end;
            }
        }

        // Apply in reverse order
        let mut result = text.to_string();
        for (start, end, repl) in non_overlapping.into_iter().rev() {
            if start <= result.len() && end <= result.len() {
                result.replace_range(start..end, &repl);
            }
        }

        result
    }

    /// Register an entity for future coreference resolution.
    pub fn register_entity(&mut self, entity: RegisteredEntity) {
        if entity.id.is_empty() || entity.entity_type.is_empty() {
            return;
        }

        // Update if already exists
        for existing in self.entity_register.iter_mut() {
            if existing.id == entity.id && existing.entity_type == entity.entity_type {
                existing.turn = entity.turn;
                return;
            }
        }

        self.entity_register.push_back(entity);

        // Bound register size
        while self.entity_register.len() > self.max_register {
            self.entity_register.pop_front();
        }
    }

    /// Track entity mentions in text.
    pub fn track_mentions(&self, text: &str, entities: &[RegisteredEntity]) -> Vec<Mention> {
        let text_lower = text.to_lowercase();
        let mut mentions = Vec::new();

        for entity in entities {
            let entity_text_lower = entity.text.to_lowercase();
            if entity_text_lower.len() < 2 {
                continue;
            }
            let mut start = 0;
            while let Some(idx) = text_lower[start..].find(&entity_text_lower) {
                let actual_idx = start + idx;
                mentions.push(Mention {
                    text: text[actual_idx..actual_idx + entity_text_lower.len()].to_string(),
                    entity_id: entity.id.clone(),
                    position: actual_idx,
                    entity_type: entity.entity_type.clone(),
                });
                start = actual_idx + 1;
            }
        }

        mentions
    }

    /// Clear the entity register.
    pub fn reset(&mut self) {
        self.entity_register.clear();
    }

    /// Get resolution statistics.
    pub fn get_stats(&self) -> (u64, u64, usize) {
        (self.resolves, self.successful_resolutions, self.entity_register.len())
    }

    // Internal: find most recent entity matching any expected type.
    fn find_referent(&self, expected_types: &[&str]) -> Option<&RegisteredEntity> {
        for entity in self.entity_register.iter().rev() {
            if expected_types.contains(&entity.entity_type.as_str()) {
                return Some(entity);
            }
        }
        // Fallback: most recent entity
        self.entity_register.back()
    }
}

impl Default for CoreferenceResolver {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_entity(id: &str, etype: &str, text: &str) -> RegisteredEntity {
        RegisteredEntity {
            id: id.to_string(),
            entity_type: etype.to_string(),
            text: text.to_string(),
            turn: 0,
        }
    }

    #[test]
    fn test_resolve_pronoun() {
        let mut resolver = CoreferenceResolver::new();
        let context = vec![make_entity("blk_100", "block", "block #100")];
        let result = resolver.resolve("What happened in it today?", &context);
        assert!(result.contains("[block #100]"));
    }

    #[test]
    fn test_resolve_the_block() {
        let mut resolver = CoreferenceResolver::new();
        let context = vec![make_entity("blk_200", "block", "block #200")];
        let result = resolver.resolve("Tell me about the block", &context);
        assert!(result.contains("[block #200]"));
    }

    #[test]
    fn test_no_resolution_without_context() {
        let mut resolver = CoreferenceResolver::new();
        let result = resolver.resolve("Tell me about it", &[]);
        assert_eq!(result, "Tell me about it");
    }

    #[test]
    fn test_track_mentions() {
        let resolver = CoreferenceResolver::new();
        let entities = vec![make_entity("addr_1", "address", "the wallet")];
        let mentions = resolver.track_mentions("Check the wallet balance", &entities);
        assert_eq!(mentions.len(), 1);
        assert_eq!(mentions[0].entity_type, "address");
    }

    #[test]
    fn test_register_dedup() {
        let mut resolver = CoreferenceResolver::new();
        resolver.register_entity(make_entity("a", "block", "blk1"));
        resolver.register_entity(make_entity("a", "block", "blk1"));
        assert_eq!(resolver.entity_register.len(), 1);
    }
}
