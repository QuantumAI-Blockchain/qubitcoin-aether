//! AIKGS Sidecar — Aether Incentivized Knowledge Growth System.
//!
//! Business logic modules for contribution scoring, reward calculation,
//! affiliate commissions, bounties, curation, progressive unlocks,
//! API key vault, and treasury. All state is persisted in CockroachDB
//! via the `db` module.

pub mod affiliates;
pub mod bounties;
pub mod config;
pub mod contributions;
pub mod curation;
pub mod db;
pub mod rewards;
pub mod scorer;
pub mod treasury;
pub mod unlocks;
pub mod vault;
