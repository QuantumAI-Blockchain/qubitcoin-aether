//! Qubitcoin Primitives — shared types used across all pallets and runtime.
//!
//! Contains: Address, TxId, UTXO types, DilithiumSignature, amount constants,
//! Poseidon2 ZK-friendly hash function.

#![cfg_attr(not(feature = "std"), no_std)]

#[cfg(not(feature = "std"))]
extern crate alloc;

pub mod poseidon2;

use codec::{Decode, DecodeWithMemTracking, Encode, MaxEncodedLen};
use scale_info::TypeInfo;
use sp_core::H256;
use sp_runtime::RuntimeDebug;

/// QBC amount in smallest unit (1 QBC = 10^8 units, like satoshis).
pub type QbcBalance = u128;

/// QBC decimals — 8 decimal places.
pub const QBC_DECIMALS: u32 = 8;
/// 1 QBC in smallest units.
pub const QBC_UNIT: QbcBalance = 100_000_000;

// ═══════════════════════════════════════════════════════════════════════
// Golden Ratio Economics Constants
// ═══════════════════════════════════════════════════════════════════════

/// Golden ratio (φ) scaled to 18 decimal places for fixed-point arithmetic.
/// PHI = 1.618033988749895 → 1_618_033_988_749_895_000
pub const PHI_SCALED: u128 = 1_618_033_988_749_895_000;
/// Denominator for PHI_SCALED (10^18).
pub const PHI_DENOM: u128 = 1_000_000_000_000_000_000;

/// Maximum supply: 3.3 billion QBC in smallest units.
pub const MAX_SUPPLY: QbcBalance = 3_300_000_000 * QBC_UNIT;
/// Initial block reward: 15.27 QBC in smallest units.
pub const INITIAL_REWARD: QbcBalance = 15_27_000_000; // 15.27 * 10^8
/// Halving interval: ~1.618 years in blocks (at 3.3s/block).
pub const HALVING_INTERVAL: u64 = 15_474_020;
/// Genesis premine: 33 million QBC.
pub const GENESIS_PREMINE: QbcBalance = 33_000_000 * QBC_UNIT;
/// Target block time in milliseconds: 3.3 seconds.
pub const TARGET_BLOCK_TIME_MS: u64 = 3_300;
/// Difficulty adjustment window in blocks.
pub const DIFFICULTY_WINDOW: u32 = 144;
/// Maximum difficulty adjustment factor (1.1 = +10%).
pub const MAX_ADJUSTMENT_FACTOR: u32 = 110;
/// Minimum difficulty adjustment factor (0.9 = -10%).
pub const MIN_ADJUSTMENT_FACTOR: u32 = 90;
/// Chain ID — Mainnet.
pub const CHAIN_ID_MAINNET: u64 = 3303;
/// Chain ID — Testnet.
pub const CHAIN_ID_TESTNET: u64 = 3304;
/// Block gas limit for QVM (L2 only).
pub const BLOCK_GAS_LIMIT: u64 = 30_000_000;
/// Coinbase maturity — blocks before coinbase is spendable.
pub const COINBASE_MATURITY: u32 = 100;

// ═══════════════════════════════════════════════════════════════════════
// One-Time Difficulty Reset Heights (fork-prevention)
// ═══════════════════════════════════════════════════════════════════════
// These heights record one-time difficulty resets that occurred on the live
// chain to recover from specific issues.  The Substrate node MUST apply the
// same resets at the same heights to produce an identical chain history.
// Changing or removing these values would cause a consensus fork.

/// Height 167: difficulty dropped below Hamiltonian ground state (0.0798 < 0.182),
/// making mining impossible.  Reset to INITIAL_DIFFICULTY.
pub const DIFFICULTY_GROUND_STATE_FIX_HEIGHT: u32 = 167;

/// Height 724: pre-fix blocks used inverted ratio (expected/actual) which caused
/// a death spiral — lowering difficulty when blocks were slow.  Reset + corrected
/// ratio applied from this height onward.
pub const DIFFICULTY_RATIO_FIX_HEIGHT: u32 = 724;

/// Height 2750: difficulty ran away to ceiling (1000) because no meaningful-max
/// clamp existed.  Reset to INITIAL_DIFFICULTY and clamp added.
pub const DIFFICULTY_CEILING_FIX_HEIGHT: u32 = 2750;

// ═══════════════════════════════════════════════════════════════════════
// Difficulty Bounds (scaled by 10^6 for fixed-point arithmetic)
// ═══════════════════════════════════════════════════════════════════════

/// Minimum difficulty: 2.0 (scaled by 10^6).
/// Must be high enough that ALL possible 4-qubit Hamiltonians have
/// ground state energy below this threshold. With 5 terms and |coeff| < 1,
/// eigenvalues are bounded by [-5, 5], so energy < 2.0 is always achievable.
pub const DIFFICULTY_FLOOR: u64 = 2_000_000;
/// Maximum difficulty: 1000.0 (scaled by 10^6).
pub const DIFFICULTY_CEILING: u64 = 1_000_000_000;
/// Meaningful max: 10.0 (scaled by 10^6).  When difficulty exceeds this, blocks
/// are slow due to VQE compute time, not puzzle hardness — upward adjustment is
/// suppressed to prevent runaway.
pub const DIFFICULTY_MEANINGFUL_MAX: u64 = 10_000_000;

// ═══════════════════════════════════════════════════════════════════════
// Validation & Safety Constants
// ═══════════════════════════════════════════════════════════════════════

/// Energy validation tolerance (scaled by 10^6).  Corresponds to 1e-3 in the
/// Python node (Config.ENERGY_VALIDATION_TOLERANCE).
pub const ENERGY_VALIDATION_TOLERANCE: i128 = 1_000;

/// Maximum future block timestamp in milliseconds (120 seconds).
/// Blocks with timestamps more than this far in the future are rejected.
pub const MAX_FUTURE_BLOCK_TIME_MS: u64 = 120_000;

/// Maximum reorg depth — forks deeper than this are rejected to prevent
/// long-range attacks.  Matches Config.MAX_REORG_DEPTH in the Python node.
pub const MAX_REORG_DEPTH: u32 = 100;

/// Confirmation depth for finality consideration (180 blocks ≈ ~10 min at 3.3s).
pub const CONFIRMATION_DEPTH: u32 = 180;

// ═══════════════════════════════════════════════════════════════════════
// Fee Economics
// ═══════════════════════════════════════════════════════════════════════

/// Percentage of transaction fees that are burned (destroyed).
/// 50 = 50%.  Miners receive the remaining 50%.
/// Matches Config.FEE_BURN_PERCENTAGE = 0.5 in the Python node.
pub const FEE_BURN_PERCENTAGE: u64 = 50;

/// Tail emission reward: 0.1 QBC in base units (0.1 * 10^8 = 10,000,000).
/// When phi-halving drops the block reward below this floor, tail emission
/// kicks in to ensure miners always receive at least this amount (until
/// MAX_SUPPLY is reached).  Matches Config.TAIL_EMISSION_REWARD in Python.
pub const TAIL_EMISSION_REWARD: u64 = 10_000_000;

// ═══════════════════════════════════════════════════════════════════════
// Genesis Constants
// ═══════════════════════════════════════════════════════════════════════
// These values MUST match the Python node exactly to produce the same genesis
// block.  Any mismatch causes a consensus fork from block 0.

/// Canonical genesis timestamp: 2024-02-08T00:00:00Z in milliseconds.
pub const CANONICAL_GENESIS_TIMESTAMP_MS: u64 = 1_707_350_400_000;

/// Canonical genesis coinbase transaction ID (same as Bitcoin's for homage).
pub const CANONICAL_GENESIS_COINBASE_TXID: &str =
    "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b";

// ═══════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════

/// Transaction ID — SHA3-256 hash of the serialized transaction.
pub type TxId = H256;

/// Qubitcoin address — derived from SHA3-256 of Dilithium public key.
/// 32 bytes, displayed as hex with "qbc1" prefix in user-facing contexts.
#[derive(
    Clone, PartialEq, Eq, Encode, Decode, DecodeWithMemTracking, MaxEncodedLen, TypeInfo, RuntimeDebug, Default,
)]
#[derive(serde::Serialize, serde::Deserialize)]
pub struct Address(pub [u8; 32]);

impl From<[u8; 32]> for Address {
    fn from(bytes: [u8; 32]) -> Self {
        Self(bytes)
    }
}

impl From<H256> for Address {
    fn from(h: H256) -> Self {
        Self(h.0)
    }
}

impl AsRef<[u8]> for Address {
    fn as_ref(&self) -> &[u8] {
        &self.0
    }
}

/// A single unspent transaction output.
#[derive(Clone, PartialEq, Eq, Encode, Decode, DecodeWithMemTracking, MaxEncodedLen, TypeInfo, RuntimeDebug)]
#[derive(serde::Serialize, serde::Deserialize)]
pub struct Utxo {
    /// Transaction that created this output.
    pub txid: TxId,
    /// Output index within that transaction.
    pub vout: u32,
    /// Recipient address.
    pub address: Address,
    /// Amount in smallest QBC units.
    pub amount: QbcBalance,
    /// Block height where this UTXO was created.
    pub block_height: u64,
    /// Whether this is a coinbase output (subject to maturity requirement).
    pub is_coinbase: bool,
}

/// Transaction input — references a UTXO to spend.
#[derive(Clone, PartialEq, Eq, Encode, Decode, DecodeWithMemTracking, MaxEncodedLen, TypeInfo, RuntimeDebug)]
#[derive(serde::Serialize, serde::Deserialize)]
pub struct TransactionInput {
    /// Transaction ID of the UTXO being spent.
    pub prev_txid: TxId,
    /// Output index of the UTXO being spent.
    pub prev_vout: u32,
}

/// Transaction output — creates a new UTXO.
#[derive(Clone, PartialEq, Eq, Encode, Decode, DecodeWithMemTracking, MaxEncodedLen, TypeInfo, RuntimeDebug)]
#[derive(serde::Serialize, serde::Deserialize)]
pub struct TransactionOutput {
    /// Recipient address.
    pub address: Address,
    /// Amount in smallest QBC units.
    pub amount: QbcBalance,
}

/// Dilithium5 signature (variable length, ~4627 bytes).
/// Stored as bounded vector for on-chain use.
pub const MAX_DILITHIUM_SIG_SIZE: u32 = 4_800;
/// Dilithium5 public key size (~2592 bytes).
pub const MAX_DILITHIUM_PK_SIZE: u32 = 2_720;

/// VQE mining parameters — the solution submitted by miners.
#[derive(Clone, PartialEq, Eq, Encode, Decode, DecodeWithMemTracking, MaxEncodedLen, TypeInfo, RuntimeDebug)]
#[derive(serde::Serialize, serde::Deserialize)]
pub struct VqeProof {
    /// Optimized VQE circuit parameters (angles as fixed-point i64 * 10^12).
    pub params: sp_runtime::BoundedVec<i64, sp_runtime::traits::ConstU32<32>>,
    /// Achieved ground state energy (fixed-point: value * 10^12).
    pub energy: i128,
    /// Hamiltonian seed derived from previous block hash.
    pub hamiltonian_seed: H256,
    /// Number of qubits used (typically 4).
    pub n_qubits: u8,
}

/// Difficulty value (fixed-point: value * 10^6).
/// Higher difficulty = easier mining (energy threshold is more generous).
pub type Difficulty = u64;

/// Default initial difficulty: 1.0 (scaled by 10^6).
pub const INITIAL_DIFFICULTY: Difficulty = 1_000_000;

/// Phi measurement stored per block.
#[derive(Clone, PartialEq, Eq, Encode, Decode, DecodeWithMemTracking, MaxEncodedLen, TypeInfo, RuntimeDebug)]
#[derive(serde::Serialize, serde::Deserialize)]
pub struct PhiMeasurement {
    /// Block height of this measurement.
    pub block_height: u64,
    /// Phi value (scaled by 1000 — e.g., 3000 = Phi of 3.0).
    pub phi_scaled: u64,
    /// Number of knowledge nodes at this block.
    pub knowledge_nodes: u64,
    /// Number of knowledge edges at this block.
    pub knowledge_edges: u64,
}

/// Consciousness threshold — Phi must exceed this for emergence.
/// 3.0 * 1000 = 3000 in scaled representation.
pub const PHI_THRESHOLD_SCALED: u64 = 3_000;

// ═══════════════════════════════════════════════════════════════════════
// Runtime API for consensus queries (used by weighted fork choice)
// ═══════════════════════════════════════════════════════════════════════

sp_api::decl_runtime_apis! {
    /// Runtime API for querying QBC consensus state from the node side.
    ///
    /// Used by the weighted fork choice rule (`WeightedChain`) to read
    /// per-block difficulty without direct storage access.
    pub trait QbcConsensusApi {
        /// Return the current difficulty stored in the QbcConsensus pallet.
        /// Value is scaled by 10^6 (e.g., 1_000_000 = difficulty 1.0).
        fn current_difficulty() -> Difficulty;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_constants() {
        // 3.3 billion * 10^8
        assert_eq!(MAX_SUPPLY, 330_000_000_000_000_000);
        // 15.27 * 10^8
        assert_eq!(INITIAL_REWARD, 1_527_000_000);
        // 33M * 10^8
        assert_eq!(GENESIS_PREMINE, 3_300_000_000_000_000);
    }

    #[test]
    fn test_phi_scaling() {
        // PHI_SCALED / PHI_DENOM should approximate 1.618
        let phi_f64 = PHI_SCALED as f64 / PHI_DENOM as f64;
        assert!((phi_f64 - 1.618033988749895).abs() < 1e-12);
    }

    #[test]
    fn test_address_from_bytes() {
        let bytes = [42u8; 32];
        let addr = Address::from(bytes);
        assert_eq!(addr.0, bytes);
    }

    #[test]
    fn test_difficulty_constants() {
        // Floor < Ceiling
        assert!(DIFFICULTY_FLOOR < DIFFICULTY_CEILING);
        // Meaningful max is between floor and ceiling
        assert!(DIFFICULTY_FLOOR < DIFFICULTY_MEANINGFUL_MAX);
        assert!(DIFFICULTY_MEANINGFUL_MAX < DIFFICULTY_CEILING);
        // Fix heights are in ascending order
        assert!(DIFFICULTY_GROUND_STATE_FIX_HEIGHT < DIFFICULTY_RATIO_FIX_HEIGHT);
        assert!(DIFFICULTY_RATIO_FIX_HEIGHT < DIFFICULTY_CEILING_FIX_HEIGHT);
    }

    #[test]
    fn test_fee_and_tail_constants() {
        assert_eq!(FEE_BURN_PERCENTAGE, 50);
        // Tail emission = 0.1 QBC = 10_000_000 base units
        assert_eq!(TAIL_EMISSION_REWARD, QBC_UNIT as u64 / 10);
    }

    #[test]
    fn test_genesis_constants() {
        // Timestamp corresponds to 2024-02-08T00:00:00Z
        assert_eq!(CANONICAL_GENESIS_TIMESTAMP_MS, 1_707_350_400_000);
        // Coinbase txid is 64 hex chars
        assert_eq!(CANONICAL_GENESIS_COINBASE_TXID.len(), 64);
    }

    #[test]
    fn test_utxo_encoding_roundtrip() {
        let utxo = Utxo {
            txid: H256::from([1u8; 32]),
            vout: 0,
            address: Address([2u8; 32]),
            amount: 1_527_000_000,
            block_height: 0,
            is_coinbase: true,
        };
        let encoded = utxo.encode();
        let decoded = Utxo::decode(&mut &encoded[..]).unwrap();
        assert_eq!(utxo, decoded);
    }
}
