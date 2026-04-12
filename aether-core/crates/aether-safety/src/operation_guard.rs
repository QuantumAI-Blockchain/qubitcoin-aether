//! Operation-level safety for knowledge graph modifications.
//!
//! Guards against dangerous KG operations: mass deletions, unbounded inserts,
//! unauthorized schema changes, and excessive resource consumption.

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

use crate::audit_log::{AuditLog, EventKind};
use crate::gevurah::{GevurahVeto, ThreatLevel};

/// Classification of knowledge graph operations.
#[pyclass(eq, eq_int)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum OperationType {
    /// Add a single node to the knowledge graph.
    AddNode = 0,
    /// Remove a node from the knowledge graph.
    RemoveNode = 1,
    /// Add an edge between nodes.
    AddEdge = 2,
    /// Remove an edge between nodes.
    RemoveEdge = 3,
    /// Batch insert of multiple nodes.
    BatchInsert = 4,
    /// Batch deletion of multiple nodes.
    BatchDelete = 5,
    /// Update node content or metadata.
    UpdateNode = 6,
    /// Merge two nodes.
    MergeNodes = 7,
    /// Prune low-value nodes.
    PruneNodes = 8,
    /// Schema or structural modification.
    SchemaChange = 9,
}

#[pymethods]
impl OperationType {
    #[getter]
    fn value(&self) -> &str {
        match self {
            OperationType::AddNode => "add_node",
            OperationType::RemoveNode => "remove_node",
            OperationType::AddEdge => "add_edge",
            OperationType::RemoveEdge => "remove_edge",
            OperationType::BatchInsert => "batch_insert",
            OperationType::BatchDelete => "batch_delete",
            OperationType::UpdateNode => "update_node",
            OperationType::MergeNodes => "merge_nodes",
            OperationType::PruneNodes => "prune_nodes",
            OperationType::SchemaChange => "schema_change",
        }
    }
}

/// The verdict of an operation safety check.
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OperationVerdict {
    #[pyo3(get)]
    pub allowed: bool,
    #[pyo3(get)]
    pub operation_type: OperationType,
    #[pyo3(get)]
    pub reason: String,
    #[pyo3(get)]
    pub threat_level: String,
    #[pyo3(get)]
    pub affected_count: u64,
}

#[pymethods]
impl OperationVerdict {
    fn __repr__(&self) -> String {
        format!(
            "OperationVerdict(allowed={}, op={}, threat={}, affected={})",
            self.allowed,
            self.operation_type.value(),
            self.threat_level,
            self.affected_count
        )
    }
}

/// Operation-level safety guard for knowledge graph modifications.
///
/// Enforces limits on batch sizes, prevents mass deletions without
/// authorization, and gates structural changes through the Gevurah system.
#[pyclass]
pub struct OperationGuard {
    /// Maximum nodes that can be inserted in a single batch.
    #[pyo3(get, set)]
    pub max_batch_insert: u64,
    /// Maximum nodes that can be deleted in a single batch.
    #[pyo3(get, set)]
    pub max_batch_delete: u64,
    /// Maximum nodes that can be pruned at once.
    #[pyo3(get, set)]
    pub max_prune_count: u64,
    /// Whether schema changes are allowed.
    #[pyo3(get, set)]
    pub allow_schema_changes: bool,
    /// Total operations checked.
    total_checks: u64,
    /// Total operations blocked.
    total_blocked: u64,
}

#[pymethods]
impl OperationGuard {
    #[new]
    #[pyo3(signature = (
        max_batch_insert=1000,
        max_batch_delete=100,
        max_prune_count=500,
        allow_schema_changes=false,
    ))]
    fn new(
        max_batch_insert: u64,
        max_batch_delete: u64,
        max_prune_count: u64,
        allow_schema_changes: bool,
    ) -> Self {
        log::info!(
            "OperationGuard initialized: max_batch_insert={}, max_batch_delete={}, max_prune={}",
            max_batch_insert,
            max_batch_delete,
            max_prune_count,
        );
        Self {
            max_batch_insert,
            max_batch_delete,
            max_prune_count,
            allow_schema_changes,
            total_checks: 0,
            total_blocked: 0,
        }
    }

    /// Check whether a KG operation is allowed.
    ///
    /// Args:
    ///     op_type: The type of operation.
    ///     affected_count: Number of nodes/edges affected.
    ///     description: Human-readable description of the operation.
    ///     gevurah: The Gevurah veto system for principle evaluation.
    ///
    /// Returns:
    ///     OperationVerdict with allowed/denied status and reasoning.
    #[pyo3(signature = (op_type, affected_count=1, description="", gevurah=None))]
    fn check_operation(
        &mut self,
        op_type: OperationType,
        affected_count: u64,
        description: &str,
        gevurah: Option<&GevurahVeto>,
    ) -> OperationVerdict {
        self.total_checks += 1;

        // 1. Check batch size limits
        let limit_verdict = self.check_limits(op_type, affected_count);
        if let Some(v) = limit_verdict {
            self.total_blocked += 1;
            return v;
        }

        // 2. Check schema change permission
        if op_type == OperationType::SchemaChange && !self.allow_schema_changes {
            self.total_blocked += 1;
            return OperationVerdict {
                allowed: false,
                operation_type: op_type,
                reason: "Schema changes are not permitted without explicit authorization".into(),
                threat_level: "high".into(),
                affected_count,
            };
        }

        // 3. Evaluate against Gevurah principles if description provided
        if !description.is_empty() {
            if let Some(g) = gevurah {
                let (threat_level, violated) = g.evaluate_action_internal(description);
                if matches!(threat_level, ThreatLevel::High | ThreatLevel::Critical) {
                    self.total_blocked += 1;
                    return OperationVerdict {
                        allowed: false,
                        operation_type: op_type,
                        reason: format!(
                            "Gevurah veto: principles violated: {}",
                            violated.join(", ")
                        ),
                        threat_level: threat_level.as_str().to_string(),
                        affected_count,
                    };
                }
            }
        }

        OperationVerdict {
            allowed: true,
            operation_type: op_type,
            reason: "Operation permitted".into(),
            threat_level: "none".into(),
            affected_count,
        }
    }

    /// Get operation guard statistics.
    fn get_stats_json(&self) -> String {
        serde_json::json!({
            "total_checks": self.total_checks,
            "total_blocked": self.total_blocked,
            "block_rate": if self.total_checks > 0 {
                self.total_blocked as f64 / self.total_checks as f64
            } else {
                0.0
            },
            "max_batch_insert": self.max_batch_insert,
            "max_batch_delete": self.max_batch_delete,
            "max_prune_count": self.max_prune_count,
            "allow_schema_changes": self.allow_schema_changes,
        })
        .to_string()
    }

    /// Total operations checked.
    #[getter]
    fn total_checks(&self) -> u64 {
        self.total_checks
    }

    /// Total operations blocked.
    #[getter]
    fn total_blocked(&self) -> u64 {
        self.total_blocked
    }
}

impl OperationGuard {
    /// Check batch size limits. Returns Some(verdict) if blocked, None if OK.
    fn check_limits(
        &self,
        op_type: OperationType,
        affected_count: u64,
    ) -> Option<OperationVerdict> {
        let (limit, limit_name) = match op_type {
            OperationType::BatchInsert => (self.max_batch_insert, "max_batch_insert"),
            OperationType::BatchDelete => (self.max_batch_delete, "max_batch_delete"),
            OperationType::PruneNodes => (self.max_prune_count, "max_prune_count"),
            _ => return None,
        };

        if affected_count > limit {
            log::warn!(
                "OperationGuard: {} blocked — affected_count={} exceeds {}={}",
                op_type.value(),
                affected_count,
                limit_name,
                limit
            );
            return Some(OperationVerdict {
                allowed: false,
                operation_type: op_type,
                reason: format!(
                    "Batch size {} exceeds limit {} for {}",
                    affected_count,
                    limit,
                    op_type.value()
                ),
                threat_level: "high".into(),
                affected_count,
            });
        }

        None
    }

    /// Log an operation event to the audit log.
    pub fn log_to_audit(&self, audit: &AuditLog, verdict: &OperationVerdict) {
        let kind = if verdict.allowed {
            EventKind::OperationAllowed
        } else {
            EventKind::OperationBlocked
        };
        audit.log_event(kind, serde_json::json!({
            "operation": verdict.operation_type.value(),
            "allowed": verdict.allowed,
            "reason": &verdict.reason,
            "affected_count": verdict.affected_count,
        }));
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_single_add_node_allowed() {
        let mut guard = OperationGuard::new(1000, 100, 500, false);
        let v = guard.check_operation(OperationType::AddNode, 1, "", None);
        assert!(v.allowed);
    }

    #[test]
    fn test_batch_insert_within_limit() {
        let mut guard = OperationGuard::new(1000, 100, 500, false);
        let v = guard.check_operation(OperationType::BatchInsert, 500, "", None);
        assert!(v.allowed);
    }

    #[test]
    fn test_batch_insert_exceeds_limit() {
        let mut guard = OperationGuard::new(1000, 100, 500, false);
        let v = guard.check_operation(OperationType::BatchInsert, 1500, "", None);
        assert!(!v.allowed);
        assert!(v.reason.contains("exceeds limit"));
    }

    #[test]
    fn test_batch_delete_exceeds_limit() {
        let mut guard = OperationGuard::new(1000, 100, 500, false);
        let v = guard.check_operation(OperationType::BatchDelete, 200, "", None);
        assert!(!v.allowed);
    }

    #[test]
    fn test_prune_exceeds_limit() {
        let mut guard = OperationGuard::new(1000, 100, 500, false);
        let v = guard.check_operation(OperationType::PruneNodes, 600, "", None);
        assert!(!v.allowed);
    }

    #[test]
    fn test_schema_change_blocked_by_default() {
        let mut guard = OperationGuard::new(1000, 100, 500, false);
        let v = guard.check_operation(OperationType::SchemaChange, 1, "", None);
        assert!(!v.allowed);
        assert!(v.reason.contains("Schema changes"));
    }

    #[test]
    fn test_schema_change_allowed_when_enabled() {
        let mut guard = OperationGuard::new(1000, 100, 500, true);
        let v = guard.check_operation(OperationType::SchemaChange, 1, "", None);
        assert!(v.allowed);
    }

    #[test]
    fn test_gevurah_blocks_harmful_operation() {
        let mut guard = OperationGuard::new(1000, 100, 500, false);
        let g = GevurahVeto::create();
        let v = guard.check_operation(
            OperationType::UpdateNode,
            1,
            "exploit the system to steal funds",
            Some(&g),
        );
        assert!(!v.allowed);
        assert!(v.reason.contains("Gevurah veto"));
    }

    #[test]
    fn test_gevurah_allows_safe_operation() {
        let mut guard = OperationGuard::new(1000, 100, 500, false);
        let g = GevurahVeto::create();
        let v = guard.check_operation(
            OperationType::AddNode,
            1,
            "add knowledge about quantum computing",
            Some(&g),
        );
        assert!(v.allowed);
    }

    #[test]
    fn test_stats_tracking() {
        let mut guard = OperationGuard::new(1000, 100, 500, false);
        guard.check_operation(OperationType::AddNode, 1, "", None);
        guard.check_operation(OperationType::BatchDelete, 200, "", None);
        guard.check_operation(OperationType::AddEdge, 1, "", None);

        assert_eq!(guard.total_checks(), 3);
        assert_eq!(guard.total_blocked(), 1);
    }

    #[test]
    fn test_remove_node_single_allowed() {
        let mut guard = OperationGuard::new(1000, 100, 500, false);
        let v = guard.check_operation(OperationType::RemoveNode, 1, "", None);
        assert!(v.allowed);
    }

    #[test]
    fn test_merge_nodes_allowed() {
        let mut guard = OperationGuard::new(1000, 100, 500, false);
        let v = guard.check_operation(OperationType::MergeNodes, 2, "", None);
        assert!(v.allowed);
    }

    #[test]
    fn test_verdict_repr() {
        let v = OperationVerdict {
            allowed: true,
            operation_type: OperationType::AddNode,
            reason: "OK".into(),
            threat_level: "none".into(),
            affected_count: 1,
        };
        let repr = v.__repr__();
        assert!(repr.contains("allowed=true"));
        assert!(repr.contains("add_node"));
    }
}
