//! Aether Engine — top-level orchestrator for the Aether Tree AI system.
//!
//! `AetherOrchestrator` is the composition root that wires all Aether
//! subsystems (graph, phi, reasoning, sephirot, chat, safety, etc.) into
//! a unified cognitive cycle. It exposes lifecycle hooks (`startup`,
//! `shutdown`, `on_block`) and diagnostics (`stats`, `health`, `mind_state`).
//!
//! This is Batch 11 of the V5 Rust migration — the final integration crate.

mod engine;
mod diagnostics;
mod lifecycle;

pub use engine::{AetherOrchestrator, OrchestratorConfig, BlockData, BlockResult};
pub use diagnostics::{SubsystemHealth, HealthStatus, MindState, FullStats};
pub use lifecycle::LifecyclePhase;
