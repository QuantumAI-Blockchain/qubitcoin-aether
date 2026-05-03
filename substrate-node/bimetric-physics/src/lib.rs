//! # Parameterized Hamiltonian for VQE Mining
//!
//! Implements the mathematical framework for Qubitcoin's VQE-based mining.
//!
//! The full VQE Hamiltonian is:
//!
//! ```text
//! H_VQE = H_base + H_rotating(theta) + H_diagonal + H_random
//! ```
//!
//! Where:
//! - **H_base** = 3 Pauli terms with golden-ratio coefficient hierarchy
//!   (coefficients scale as base_coeff * phi^{0,-1,-2}).
//! - **H_rotating(theta)** = 2 rotating-coefficient terms parameterized by
//!   cos(theta)/sin(theta), creating a per-block energy landscape rotation.
//! - **H_diagonal** = 2 diagonal bias terms with small negative coefficient
//!   (scales as omega * phi^{-2,-3}), breaking remaining degeneracies.
//! - **H_random** = 2 seed-derived random Pauli terms preventing precomputation.
//!
//! ## Architecture
//!
//! - [`potential`] — Mexican-hat potential, VEV, modified Newtonian acceleration
//! - [`sephirot`] — 10 Sephirot phase assignments (golden-angle spacing), alignment scoring
//! - [`coupling`] — alpha(phi) geometric weight from VQE solution parameters
//! - [`hamiltonian`] — Base Pauli, rotating coupling, diagonal bias term generation
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

#[cfg(test)]
mod determinism_tests;
