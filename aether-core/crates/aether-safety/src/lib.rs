//! aether-safety: Gevurah veto system and adversarial defense for Aether Tree AI.
//!
//! The Gevurah (Severity) Sephirah acts as the amygdala of the AI system —
//! a dedicated threat detection and safety enforcement layer with the authority
//! to veto any operation that violates constitutional safety principles.
//!
//! # Modules
//!
//! - [`gevurah`] — Core veto system, constitutional principles, BFT consensus
//! - [`content_filter`] — Content safety checking, injection detection, chat sanitization
//! - [`operation_guard`] — Operation-level safety for knowledge graph modifications
//! - [`audit_log`] — Safety event audit logging and statistics

pub mod gevurah;
pub mod content_filter;
pub mod operation_guard;
pub mod audit_log;

pub use gevurah::{
    GevurahVeto, SafetyPrinciple, VetoRecord, ThreatLevel, VetoReason,
    MultiNodeConsensus, ConsensusVote, VetoAuthenticator, SafetyManager,
};
pub use content_filter::ContentFilter;
pub use operation_guard::{OperationGuard, OperationType, OperationVerdict};
pub use audit_log::{AuditLog, SafetyEvent, EventKind};
