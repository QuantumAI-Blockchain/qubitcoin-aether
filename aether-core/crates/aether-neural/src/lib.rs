//! aether-neural: Neural reasoning (GAT) for the Aether Tree.

mod mod_neural;
pub mod trainer;
pub mod python_bindings;

pub use mod_neural::*;
pub use python_bindings::RustGATReasoner;
