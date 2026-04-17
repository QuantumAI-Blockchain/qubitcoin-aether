//! aether-reasoning: Reasoning, causal discovery, and adversarial debate engines
//! for the Aether Tree AI system.
//!
//! This crate ports three Python modules into Rust:
//!
//! 1. **ReasoningEngine** — deductive, inductive, and abductive reasoning over
//!    the knowledge graph, plus chain-of-thought with backtracking and
//!    contradiction detection.
//!
//! 2. **CausalDiscovery** — PC (Peter-Clark) and FCI (Fast Causal Inference)
//!    algorithms for discovering genuine causal relationships from the
//!    knowledge graph's feature vectors, with Fisher-Z conditional
//!    independence testing and intervention validation.
//!
//! 3. **DebateProtocol** / **MultiPartyDebate** / **DebateScorer** —
//!    adversarial debate between proposer (Chesed) and critic (Gevurah),
//!    N-party coalition-forming debate, and a 2-layer neural network for
//!    learning debate verdict prediction.
//!
//! All structures are thread-safe via `parking_lot::RwLock` and `Arc`.
//! PyO3 bindings available via the `pyo3` feature flag.

pub mod reasoning;
pub mod reasoning_chain;
pub mod reasoning_extras;
pub mod causal_engine;
pub mod causal_pag;
pub mod causal_stats;
pub mod debate;
pub mod debate_multi;
pub mod debate_scorer;
pub mod logic_bridge;

pub use reasoning::{ReasoningEngine, ReasoningResult, ReasoningStep};
pub use reasoning_chain::ReasonChainResult;
pub use causal_engine::CausalDiscovery;
pub use causal_pag::{PAG, PAGEdge, EndpointMark};
pub use causal_stats::{pearson_correlation, fisher_z_p_value};
pub use debate::{DebateProtocol, DebateResult, DebatePosition};
pub use debate_multi::MultiPartyDebate;
pub use debate_scorer::DebateScorer;
pub use logic_bridge::{LogicBridge, DerivedFact, Explanation, InductiveRule, ProofResult};

#[cfg(feature = "pyo3")]
pub mod pyo3_bindings;
#[cfg(feature = "pyo3")]
pub use pyo3_bindings::PyLogicBridge;
