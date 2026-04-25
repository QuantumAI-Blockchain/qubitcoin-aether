//! # Aether Transformer — V5 Neural Reasoning Core
//!
//! The core reasoning engine for the Aether Mind. A domain-specific transformer
//! with Sephirot-specialized attention heads and a Global Workspace for cross-domain
//! integration.
//!
//! This replaces all Python reasoning (BFS/DFS graph traversal, template matching)
//! with genuine neural attention-based reasoning.

pub mod attention;
pub mod config;
pub mod generation;
pub mod model;

pub use config::TransformerConfig;
pub use model::AetherTransformer;
