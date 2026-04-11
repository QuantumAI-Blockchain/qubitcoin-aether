//! aether-types: Shared types for the Aether Tree AGI engine.
//!
//! Provides KeterNode, KeterEdge, and domain constants used across all crates.

pub mod keter_node;
pub mod keter_edge;

pub use keter_node::{KeterNode, VALID_NODE_TYPES};
pub use keter_edge::{KeterEdge, VALID_EDGE_TYPES};

/// The 10 Sephirot cognitive domains.
pub const SEPHIROT_DOMAINS: &[&str] = &[
    "keter", "chochmah", "binah", "chesed", "gevurah",
    "tiferet", "netzach", "hod", "yesod", "malkuth",
];

/// Golden ratio constant.
pub const PHI: f64 = 1.618_033_988_749_895;

/// Maximum supply of QBC.
pub const MAX_SUPPLY: f64 = 3_300_000_000.0;

/// Chain ID for mainnet.
pub const CHAIN_ID: u64 = 3303;
