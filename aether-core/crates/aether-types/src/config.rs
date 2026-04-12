//! Aether configuration types.
//!
//! `AetherConfig` centralises tunable parameters that span multiple crates.
//! Default values match the Python `Config` class in `src/qubitcoin/config.py`.

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

/// Central configuration for the Aether Tree engine.
#[pyclass(get_all, set_all)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AetherConfig {
    /// Phi consciousness threshold (Gate 6 target = 3.0).
    pub phi_threshold: f64,

    /// Maximum knowledge nodes kept in the hot in-memory cache.
    pub max_nodes_in_memory: usize,

    /// CockroachDB connection URL (PostgreSQL wire protocol).
    pub db_url: String,

    /// Maximum database connection pool size.
    pub db_max_connections: u32,

    /// Time-decay half-life in blocks for confidence decay.
    pub confidence_halflife: f64,

    /// Minimum confidence floor after decay.
    pub confidence_floor: f64,

    /// How many blocks between long-term memory consolidation runs.
    pub consolidation_interval_blocks: u64,

    /// Number of Sephirot domains (always 10).
    pub num_sephirot: usize,

    /// Higgs VEV constant.
    pub higgs_vev: f64,

    /// Higgs tan(beta) = phi.
    pub higgs_tan_beta: f64,

    /// Whether to enable autonomous curiosity engine.
    pub curiosity_enabled: bool,

    /// Whether to enable governed self-improvement.
    pub self_improvement_enabled: bool,

    /// Maximum depth for chain-of-thought reasoning.
    pub max_reasoning_depth: usize,

    /// Batch size for knowledge ingestion.
    pub ingest_batch_size: usize,
}

impl Default for AetherConfig {
    fn default() -> Self {
        Self {
            phi_threshold: 3.0,
            max_nodes_in_memory: 100_000,
            db_url: "postgresql://root@localhost:26257/qbc?sslmode=disable".to_string(),
            db_max_connections: 10,
            confidence_halflife: 10_000.0,
            confidence_floor: 0.3,
            consolidation_interval_blocks: 3300,
            num_sephirot: 10,
            higgs_vev: 174.14,
            higgs_tan_beta: 1.618_033_988_749_895,
            curiosity_enabled: true,
            self_improvement_enabled: true,
            max_reasoning_depth: 10,
            ingest_batch_size: 100,
        }
    }
}

#[pymethods]
impl AetherConfig {
    /// Create a new AetherConfig with defaults.
    #[new]
    #[pyo3(signature = (
        phi_threshold = 3.0,
        max_nodes_in_memory = 100_000,
        db_url = "postgresql://root@localhost:26257/qbc?sslmode=disable".to_string(),
        db_max_connections = 10,
        confidence_halflife = 10_000.0,
        confidence_floor = 0.3,
        consolidation_interval_blocks = 3300,
        num_sephirot = 10,
        higgs_vev = 174.14,
        higgs_tan_beta = 1.618_033_988_749_895,
        curiosity_enabled = true,
        self_improvement_enabled = true,
        max_reasoning_depth = 10,
        ingest_batch_size = 100,
    ))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        phi_threshold: f64,
        max_nodes_in_memory: usize,
        db_url: String,
        db_max_connections: u32,
        confidence_halflife: f64,
        confidence_floor: f64,
        consolidation_interval_blocks: u64,
        num_sephirot: usize,
        higgs_vev: f64,
        higgs_tan_beta: f64,
        curiosity_enabled: bool,
        self_improvement_enabled: bool,
        max_reasoning_depth: usize,
        ingest_batch_size: usize,
    ) -> Self {
        Self {
            phi_threshold,
            max_nodes_in_memory,
            db_url,
            db_max_connections,
            confidence_halflife,
            confidence_floor,
            consolidation_interval_blocks,
            num_sephirot,
            higgs_vev,
            higgs_tan_beta,
            curiosity_enabled,
            self_improvement_enabled,
            max_reasoning_depth,
            ingest_batch_size,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "AetherConfig(phi_threshold={}, max_nodes={}, db_pool={})",
            self.phi_threshold, self.max_nodes_in_memory, self.db_max_connections
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_values() {
        let cfg = AetherConfig::default();
        assert!((cfg.phi_threshold - 3.0).abs() < f64::EPSILON);
        assert_eq!(cfg.max_nodes_in_memory, 100_000);
        assert_eq!(cfg.db_max_connections, 10);
        assert!((cfg.confidence_halflife - 10_000.0).abs() < f64::EPSILON);
        assert!((cfg.confidence_floor - 0.3).abs() < f64::EPSILON);
        assert_eq!(cfg.consolidation_interval_blocks, 3300);
        assert_eq!(cfg.num_sephirot, 10);
        assert!((cfg.higgs_vev - 174.14).abs() < f64::EPSILON);
        assert!(cfg.curiosity_enabled);
        assert!(cfg.self_improvement_enabled);
        assert_eq!(cfg.max_reasoning_depth, 10);
        assert_eq!(cfg.ingest_batch_size, 100);
    }

    #[test]
    fn test_serde_roundtrip() {
        let cfg = AetherConfig::default();
        let json = serde_json::to_string(&cfg).unwrap();
        let back: AetherConfig = serde_json::from_str(&json).unwrap();
        assert!((back.phi_threshold - cfg.phi_threshold).abs() < f64::EPSILON);
        assert_eq!(back.max_nodes_in_memory, cfg.max_nodes_in_memory);
        assert_eq!(back.db_url, cfg.db_url);
    }

    #[test]
    fn test_custom_config() {
        let cfg = AetherConfig {
            phi_threshold: 5.0,
            max_nodes_in_memory: 500_000,
            db_url: "postgresql://user@db:5432/aether".into(),
            db_max_connections: 32,
            ..Default::default()
        };
        assert!((cfg.phi_threshold - 5.0).abs() < f64::EPSILON);
        assert_eq!(cfg.max_nodes_in_memory, 500_000);
        assert_eq!(cfg.db_max_connections, 32);
        // Defaults preserved for remaining fields
        assert!(cfg.curiosity_enabled);
    }

    #[test]
    fn test_clone() {
        let cfg = AetherConfig::default();
        let cloned = cfg.clone();
        assert_eq!(cfg.db_url, cloned.db_url);
        assert_eq!(cfg.max_nodes_in_memory, cloned.max_nodes_in_memory);
    }
}
