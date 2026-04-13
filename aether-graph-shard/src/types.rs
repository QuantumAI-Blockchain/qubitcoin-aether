//! Core types for the distributed knowledge graph shard service.
//!
//! Designed for trillion-node scale with domain-based sharding.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

/// The 10 Sephirot cognitive domains + general + cross-domain
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Domain {
    Keter,         // Meta-learning, governance
    Chochmah,      // Intuition, pattern discovery
    Binah,         // Logic, causal inference
    Chesed,        // Exploration, divergent thinking
    Gevurah,       // Safety, constraints
    Tiferet,       // Integration, synthesis
    Netzach,       // Reinforcement learning
    Hod,           // Language, semantics
    Yesod,         // Memory, fusion
    Malkuth,       // Action, interaction
    General,       // Unclassified
    CrossDomain,   // Spans multiple domains
}

impl Domain {
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "keter" | "meta_learning" | "governance" => Domain::Keter,
            "chochmah" | "intuition" | "quantum_physics" | "physics" => Domain::Chochmah,
            "binah" | "logic" | "mathematics" | "computer_science" => Domain::Binah,
            "chesed" | "exploration" | "biology" => Domain::Chesed,
            "gevurah" | "safety" | "cryptography" => Domain::Gevurah,
            "tiferet" | "integration" | "blockchain" => Domain::Tiferet,
            "netzach" | "reinforcement" | "economics" => Domain::Netzach,
            "hod" | "language" | "ai_ml" => Domain::Hod,
            "yesod" | "memory" | "technology" => Domain::Yesod,
            "malkuth" | "action" | "general" => Domain::Malkuth,
            "cross_domain" => Domain::CrossDomain,
            _ => Domain::General,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Domain::Keter => "keter",
            Domain::Chochmah => "chochmah",
            Domain::Binah => "binah",
            Domain::Chesed => "chesed",
            Domain::Gevurah => "gevurah",
            Domain::Tiferet => "tiferet",
            Domain::Netzach => "netzach",
            Domain::Hod => "hod",
            Domain::Yesod => "yesod",
            Domain::Malkuth => "malkuth",
            Domain::General => "general",
            Domain::CrossDomain => "cross_domain",
        }
    }

    pub fn shard_base_id(&self) -> u32 {
        match self {
            Domain::Keter => 0,
            Domain::Chochmah => 1,
            Domain::Binah => 2,
            Domain::Chesed => 3,
            Domain::Gevurah => 4,
            Domain::Tiferet => 5,
            Domain::Netzach => 6,
            Domain::Hod => 7,
            Domain::Yesod => 8,
            Domain::Malkuth => 9,
            Domain::General => 10,
            Domain::CrossDomain => 11,
        }
    }

    pub fn all() -> &'static [Domain] {
        &[
            Domain::Keter,
            Domain::Chochmah,
            Domain::Binah,
            Domain::Chesed,
            Domain::Gevurah,
            Domain::Tiferet,
            Domain::Netzach,
            Domain::Hod,
            Domain::Yesod,
            Domain::Malkuth,
            Domain::General,
            Domain::CrossDomain,
        ]
    }
}

/// A knowledge node in the distributed graph.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShardNode {
    pub node_id: i64,
    pub node_type: String,
    pub content_hash: String,
    pub content: BTreeMap<String, String>,
    pub confidence: f64,
    pub source_block: i64,
    pub timestamp: f64,
    pub domain: String,
    pub last_referenced_block: i64,
    pub reference_count: i64,
    pub grounding_source: String,
    pub edges_out: Vec<i64>,
    pub edges_in: Vec<i64>,
    pub embedding: Option<Vec<f32>>,
}

impl ShardNode {
    pub fn compute_hash(&self) -> String {
        let mut hasher = Sha256::new();
        // Deterministic: sorted BTreeMap
        let json = serde_json::to_string(&self.content).unwrap_or_default();
        hasher.update(format!(
            "{}:{}:{}:{:.6}",
            self.node_id, self.node_type, json, self.confidence
        ));
        hex::encode(hasher.finalize())
    }

    /// Leaf hash for Merkle tree (matches Python/Rust aether-core)
    pub fn merkle_leaf(&self) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(format!(
            "{}:{}:{:.6}",
            self.node_id, self.content_hash, self.confidence
        ));
        hasher.finalize().into()
    }

    /// Value score for pruning decisions (matches Python knowledge_scorer)
    pub fn value_score(&self, current_block: i64) -> f64 {
        let type_score = match self.node_type.as_str() {
            "axiom" => 1.0,
            "inference" => 0.8,
            "prediction" => 0.7,
            "assertion" => 0.6,
            "meta_observation" => 0.5,
            "observation" => 0.3,
            _ => 0.2,
        };

        let edge_degree = (self.edges_out.len() + self.edges_in.len()) as f64;
        let edge_score = (edge_degree / 10.0).min(1.0);

        let ref_score = (self.reference_count as f64 / 20.0).min(1.0);

        let grounding = if self.grounding_source == "prediction_verified"
            || self.grounding_source == "block_oracle"
        {
            1.0
        } else {
            0.3
        };

        let blocks_since = (current_block - self.last_referenced_block).max(0) as f64;
        let recency = (-blocks_since / 50000.0).exp(); // Half-life ~50K blocks

        type_score * 0.30
            + edge_score * 0.20
            + ref_score * 0.20
            + self.confidence * 0.15
            + recency * 0.10
            + grounding * 0.05
    }
}

/// A knowledge edge in the distributed graph.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShardEdge {
    pub from_node_id: i64,
    pub to_node_id: i64,
    pub edge_type: String,
    pub weight: f64,
    pub timestamp: f64,
}

/// Compact binary format for RocksDB storage.
impl ShardNode {
    pub fn to_bytes(&self) -> Vec<u8> {
        bincode::serialize(self).expect("node serialization")
    }

    pub fn from_bytes(data: &[u8]) -> anyhow::Result<Self> {
        Ok(bincode::deserialize(data)?)
    }
}

impl ShardEdge {
    pub fn to_bytes(&self) -> Vec<u8> {
        bincode::serialize(self).expect("edge serialization")
    }

    pub fn from_bytes(data: &[u8]) -> anyhow::Result<Self> {
        Ok(bincode::deserialize(data)?)
    }

    /// Key for RocksDB edge storage: "from_id:to_id:type"
    pub fn storage_key(&self) -> Vec<u8> {
        format!(
            "{}:{}:{}",
            self.from_node_id, self.to_node_id, self.edge_type
        )
        .into_bytes()
    }
}

/// Shard configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShardConfig {
    pub shard_id: u32,
    pub domain: Domain,
    pub sub_shard: u32,          // Sub-shard within domain (0-255)
    pub data_dir: String,
    pub cache_capacity: usize,   // LRU cache size (nodes)
    pub compaction_threshold: f64, // Min value score to keep
}

/// Statistics for a single shard
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ShardStats {
    pub shard_id: u32,
    pub domain: String,
    pub node_count: i64,
    pub edge_count: i64,
    pub disk_bytes: u64,
    pub avg_confidence: f64,
    pub merkle_root: String,
    pub cache_hits: u64,
    pub cache_misses: u64,
}

/// Global statistics across all shards
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct GlobalStats {
    pub total_nodes: i64,
    pub total_edges: i64,
    pub nodes_per_domain: BTreeMap<String, i64>,
    pub nodes_per_type: BTreeMap<String, i64>,
    pub edges_per_type: BTreeMap<String, i64>,
    pub avg_confidence: f64,
    pub active_shards: u32,
    pub total_cache_hits: u64,
    pub total_cache_misses: u64,
    pub global_merkle_root: String,
}
