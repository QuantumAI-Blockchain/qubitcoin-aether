//! # SUGRA Bimetric Field Mathematics for Qubitcoin Consensus
//!
//! Implements the mathematical framework for Proof-of-SUSY-Alignment mining.
//!
//! The full VQE Hamiltonian is:
//!
//! ```text
//! H_VQE = H_SUSY + H_bimetric(theta) + lambda * H_IIT
//! ```
//!
//! Where:
//! - **H_SUSY** = {Q, Q-dagger}/2 from N=2 broken supergravity, encoding the
//!   fermion-boson superpartner structure with golden-ratio mass hierarchy.
//! - **H_bimetric(theta)** = m'^2 cos(theta) h_uv h'^uv, the Hassan-Rosen
//!   graviton mass-mixing term that rotates the energy landscape per block.
//! - **H_IIT** = -hbar * omega_Phi * Sum Phi(P)|P><P|, an operator-valued
//!   Integrated Information Theory term encoding partition-level consciousness
//!   contributions into the quantum Hamiltonian.
//!
//! ## Architecture
//!
//! - [`potential`] — Mexican-hat potential, VEV, modified Newtonian acceleration
//! - [`sephirot`] — 10 Sephirot phase assignments (golden-angle spacing), alignment scoring
//! - [`coupling`] — alpha(phi) geometric weight from VQE solution parameters
//! - [`hamiltonian`] — H_SUSY, H_bimetric, H_IIT Pauli term generation
//!
//! ## no_std Compatibility
//!
//! This crate is `no_std` compatible (with `alloc`) for use inside the
//! Substrate WASM runtime. Disable the default `std` feature:
//!
//! ```toml
//! bimetric-physics = { path = "../bimetric-physics", default-features = false }
//! ```

#![cfg_attr(not(feature = "std"), no_std)]

#[cfg(not(feature = "std"))]
extern crate alloc;

pub mod coupling;
pub mod hamiltonian;
pub mod potential;
pub mod sephirot;
