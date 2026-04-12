//! aether-protocol: Proof-of-Thought consensus protocol, on-chain AGI bridge,
//! and reasoning task marketplace for the Aether Tree.
//!
//! This crate ports three Python modules into Rust:
//!
//! 1. **AetherEngine** (proof_of_thought.py) — orchestrates per-block reasoning
//!    proof generation, knowledge extraction, Phi computation, and the 10-gate
//!    AGI milestone system.
//!
//! 2. **OnChainBridge** (on_chain.py) — anchors AGI state to the blockchain
//!    via proof hashes, state commitments, and per-block metrics recording.
//!
//! 3. **TaskProtocol** (task_protocol.py) — Proof-of-Thought task marketplace
//!    with task creation, claiming, solution submission, BFT validation,
//!    reward distribution, and validator staking/slashing.
//!
//! All structures are thread-safe via `parking_lot::RwLock`.
//! No PyO3 annotations — pure Rust. PyO3 bindings come in a later batch.

pub mod proof_of_thought;
pub mod gate_system;
pub mod on_chain;
pub mod task_protocol;

pub use proof_of_thought::{AetherEngine, ThoughtProof, ThoughtProofValidation};
pub use gate_system::{GateSystem, GateDefinition, GateResult, GateStats};
pub use on_chain::{OnChainBridge, OnChainStats, BlockAnchor};
pub use task_protocol::{
    TaskMarket, ValidatorRegistry, ProofOfThoughtProtocol,
    ReasoningTask, TaskStatus, Validator, TaskFinalization,
};
