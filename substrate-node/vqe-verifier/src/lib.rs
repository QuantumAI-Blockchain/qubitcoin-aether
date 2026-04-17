//! VQE Energy Re-Verification — `no_std` compatible.
//!
//! Given a Hamiltonian seed, variational parameters, and a claimed energy,
//! this crate re-computes the VQE energy and checks it matches within
//! tolerance.  Designed to run on-chain inside a Substrate pallet (WASM).
//!
//! The algorithms here MUST match the `qbc-mining` crate exactly:
//! - Same ChaCha8 RNG seeding from H256
//! - Same Pauli term generation (5 terms, 4 qubits, coefficients in [-1,1))
//! - Same TwoLocal ansatz (ry + cz, reps=2, 12 parameters)
//! - Same statevector expectation value calculation

#![cfg_attr(not(feature = "std"), no_std)]

#[cfg(not(feature = "std"))]
extern crate alloc;

pub mod simulator;
pub mod ansatz;
pub mod hamiltonian;
pub mod verify;

pub use verify::verify_energy;
