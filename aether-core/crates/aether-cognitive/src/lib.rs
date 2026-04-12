//! aether-cognitive: Metacognition, self-improvement, curiosity, and emotional state.
//!
//! This crate implements the cognitive feedback loops that enable the Aether Tree
//! to reason about its own reasoning (metacognition), adjust strategy weights
//! (self-improvement), explore knowledge gaps (curiosity), and track cognitive
//! emotional states derived from live system metrics (emotional state).
//!
//! All four modules are designed for PyO3 interop with `#[pyclass]` annotations.

pub mod metacognition;
pub mod self_improvement;
pub mod curiosity_engine;
pub mod emotional_state;

pub use metacognition::MetacognitionEngine;
pub use self_improvement::SelfImprovementEngine;
pub use curiosity_engine::CuriosityEngine;
pub use emotional_state::EmotionalState;
