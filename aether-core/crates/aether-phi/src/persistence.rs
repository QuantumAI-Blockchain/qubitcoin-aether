//! PhiPersistence: DB persistence for phi measurements.
//!
//! Saves and retrieves phi measurements from the database.
//! Pure Rust API (not PyO3).

use aether_persistence::error::PersistenceError;
use aether_persistence::{PhiMeasurementRow, PhiRepo, PgPool};

/// Persistence layer for phi measurements.
pub struct PhiPersistence {
    pool: PgPool,
}

impl PhiPersistence {
    /// Create a new PhiPersistence with a database pool.
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    /// Save a phi measurement to the database. Returns the inserted row ID.
    pub async fn save_measurement(
        &self,
        phi_value: f64,
        integration: f64,
        differentiation: f64,
        num_nodes: i64,
        num_edges: i64,
        block_height: i64,
    ) -> Result<i64, PersistenceError> {
        let row = PhiMeasurementRow {
            id: 0, // auto-generated
            phi_value,
            phi_threshold: 3.0, // default threshold
            integration_score: integration,
            differentiation_score: differentiation,
            num_nodes,
            num_edges,
            block_height,
            measured_at: chrono::Utc::now().naive_utc(),
        };
        PhiRepo::insert(&self.pool, &row).await
    }

    /// Get the latest phi measurement from the database.
    pub async fn get_latest(&self) -> Result<Option<PhiMeasurementRow>, PersistenceError> {
        PhiRepo::get_latest(&self.pool).await
    }

    /// Get measurement at a specific block height.
    pub async fn get_at_block(
        &self,
        block_height: i64,
    ) -> Result<Option<PhiMeasurementRow>, PersistenceError> {
        PhiRepo::get_by_block(&self.pool, block_height).await
    }

    /// Get phi history for a range of blocks.
    pub async fn get_history(
        &self,
        from_block: i64,
        to_block: i64,
    ) -> Result<Vec<PhiMeasurementRow>, PersistenceError> {
        PhiRepo::get_history(&self.pool, from_block, to_block).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_phi_measurement_row_debug() {
        let row = PhiMeasurementRow {
            id: 1,
            phi_value: 0.5,
            phi_threshold: 3.0,
            integration_score: 0.3,
            differentiation_score: 0.7,
            num_nodes: 100,
            num_edges: 50,
            block_height: 1000,
            measured_at: chrono::NaiveDateTime::default(),
        };
        let debug_str = format!("{:?}", row);
        assert!(debug_str.contains("phi_value"));
        assert!(debug_str.contains("0.5"));
    }

    #[test]
    fn test_phi_measurement_row_clone() {
        let row = PhiMeasurementRow {
            id: 42,
            phi_value: 1.5,
            phi_threshold: 3.0,
            integration_score: 0.8,
            differentiation_score: 0.9,
            num_nodes: 500,
            num_edges: 200,
            block_height: 5000,
            measured_at: chrono::NaiveDateTime::default(),
        };
        let cloned = row.clone();
        assert_eq!(cloned.id, 42);
        assert!((cloned.phi_value - 1.5).abs() < f64::EPSILON);
        assert_eq!(cloned.num_nodes, 500);
        assert_eq!(cloned.block_height, 5000);
    }
}
