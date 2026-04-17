//! aether-logic: First-Order Logic reasoning engine for the Aether Tree.
//!
//! This crate implements **real** logical inference -- the foundational capability
//! required for genuine AI reasoning. Unlike graph-traversal approaches that label
//! BFS as "deduction," this crate provides:
//!
//! - **First-Order Logic terms and formulas** (`term`, `formula`)
//! - **Robinson's unification algorithm** with occurs check (`unify`)
//! - **Sound inference rules**: modus ponens, modus tollens, resolution,
//!   universal instantiation, hypothetical syllogism (`inference`)
//! - **Forward and backward chaining** over a knowledge base (`knowledge_base`)
//! - **Abductive reasoning**: hypothesis generation from observations (`abduction`)
//! - **Inductive generalization**: anti-unification over examples (`induction`)
//!
//! Every derivation produces an auditable `Proof` tree, ensuring that the Aether
//! Tree's reasoning is transparent, verifiable, and cryptographically anchored
//! on-chain via Proof-of-Thought.

pub mod term;
pub mod formula;
pub mod unify;
pub mod inference;
pub mod knowledge_base;
pub mod abduction;
pub mod induction;

pub use term::{Term, Symbol, SymbolTable};
pub use formula::Formula;
pub use unify::{Substitution, unify, unify_atoms};
pub use inference::{
    modus_ponens, modus_tollens, universal_instantiation,
    resolution, hypothetical_syllogism,
};
pub use knowledge_base::{KnowledgeBase, Proof, ProofStep, InferenceRule};
pub use abduction::{abduce, Hypothesis};
pub use induction::{induce, anti_unify, Generalization};
