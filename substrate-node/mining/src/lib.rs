//! Qubitcoin VQE Mining Engine — native Rust implementation.
//!
//! Provides a complete VQE mining engine that can run inside the Substrate
//! node binary, eliminating the need for the Python stack when mining.
//!
//! # Architecture
//!
//! ```text
//! Mining Engine
//! ├── simulator  — 4-qubit statevector quantum simulator
//! ├── hamiltonian — Deterministic Hamiltonian from block hash seed
//! ├── ansatz     — TwoLocal(4, RY, CZ, linear, reps=2) circuit
//! ├── vqe        — COBYLA optimization loop
//! └── engine     — Block watcher + proof submission
//! ```
//!
//! # Usage
//!
//! ```ignore
//! use qbc_mining::{engine, substrate_bridge};
//!
//! // Create bridge to Substrate client
//! let reader = substrate_bridge::SubstrateChainReader::new(client.clone());
//! let submitter = substrate_bridge::SubstrateProofSubmitter::new(client, pool, keystore);
//!
//! // Run mining loop (blocking — spawn on a dedicated thread)
//! engine::run_mining(
//!     Arc::new(reader),
//!     Arc::new(submitter),
//!     engine::MiningConfig { thread_id: 0, max_attempts: 50 },
//! );
//! ```

pub mod ansatz;
pub mod engine;
pub mod hamiltonian;
pub mod simulator;
pub mod vqe;

pub use engine::{ChainReader, MiningConfig, ProofSubmitter};
