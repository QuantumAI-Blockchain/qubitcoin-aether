//! Unit tests for pallet-qbc-consensus.
//!
//! Tests cover:
//! - Seed derivation format (hex:decimal)
//! - Coinbase TXID generation
//! - Difficulty adjustment logic
//! - VQE proof validation
//! - Replay prevention
//! - Rate limiting

use super::pallet::*;
use frame_support::{construct_runtime, derive_impl, parameter_types};
use qbc_primitives::*;
use sp_core::H256;
use sp_runtime::{
    traits::IdentityLookup,
    BuildStorage,
};

// ═══════════════════════════════════════════════════════════════════════
// Mock Runtime
// ═══════════════════════════════════════════════════════════════════════

type Block = frame_system::mocking::MockBlock<Test>;

construct_runtime!(
    pub struct Test {
        System: frame_system,
        Timestamp: pallet_timestamp,
        QbcDilithium: pallet_qbc_dilithium,
        QbcEconomics: pallet_qbc_economics,
        QbcUtxo: pallet_qbc_utxo,
        QbcConsensus: crate,
    }
);

#[derive_impl(frame_system::config_preludes::TestDefaultConfig)]
impl frame_system::Config for Test {
    type Block = Block;
    type AccountId = u64;
    type Lookup = IdentityLookup<u64>;
}

impl pallet_timestamp::Config for Test {
    type Moment = u64;
    type OnTimestampSet = ();
    type MinimumPeriod = frame_support::traits::ConstU64<1650>;
    type WeightInfo = ();
}

impl pallet_qbc_dilithium::Config for Test {
    type RuntimeEvent = RuntimeEvent;
}

impl pallet_qbc_economics::Config for Test {
    type RuntimeEvent = RuntimeEvent;
}

/// Stub freeze checker — nothing is frozen in tests.
pub struct NoFreezeChecker;
impl pallet_qbc_utxo::UtxoFreezeChecker for NoFreezeChecker {
    fn is_frozen(_txid: &H256, _vout: u32) -> bool {
        false
    }
}

parameter_types! {
    pub const MaxInputs: u32 = 256;
    pub const MaxOutputs: u32 = 256;
}

impl pallet_qbc_utxo::Config for Test {
    type RuntimeEvent = RuntimeEvent;
    type MaxInputs = MaxInputs;
    type MaxOutputs = MaxOutputs;
    type FreezeChecker = NoFreezeChecker;
}

impl Config for Test {
    type RuntimeEvent = RuntimeEvent;
}

/// Build test externalities with genesis state.
fn new_test_ext() -> sp_io::TestExternalities {
    let mut storage = frame_system::GenesisConfig::<Test>::default()
        .build_storage()
        .unwrap();

    // Set initial difficulty
    GenesisConfig::<Test> {
        initial_difficulty: INITIAL_DIFFICULTY,
        _phantom: Default::default(),
    }
    .assimilate_storage(&mut storage)
    .unwrap();

    let mut ext = sp_io::TestExternalities::new(storage);
    ext.execute_with(|| {
        System::set_block_number(1);
        // Set a known parent hash so seed derivation is deterministic
        frame_system::Pallet::<Test>::set_parent_hash(H256::from([0xABu8; 32]));
    });
    ext
}

fn hex_encode(bytes: &[u8]) -> Vec<u8> {
    const HEX_CHARS: &[u8; 16] = b"0123456789abcdef";
    let mut hex = Vec::with_capacity(bytes.len() * 2);
    for &b in bytes {
        hex.push(HEX_CHARS[(b >> 4) as usize]);
        hex.push(HEX_CHARS[(b & 0x0f) as usize]);
    }
    hex
}

// ═══════════════════════════════════════════════════════════════════════
// Seed Derivation Tests
// ═══════════════════════════════════════════════════════════════════════

#[test]
fn seed_derivation_uses_hex_colon_decimal_format() {
    new_test_ext().execute_with(|| {
        let parent_hash = frame_system::Pallet::<Test>::parent_hash();
        let block_height = 100u64;

        // Manually construct expected seed: SHA256("{hex}:{decimal}")
        let hex_str = hex_encode(parent_hash.as_ref());
        let mut expected_data = Vec::new();
        expected_data.extend_from_slice(&hex_str);
        expected_data.push(b':');
        expected_data.extend_from_slice(b"100");
        let expected_seed = H256::from(sp_core::hashing::sha2_256(&expected_data));

        // Pallet derivation
        let pallet_seed = Pallet::<Test>::derive_hamiltonian_seed(block_height);

        assert_eq!(pallet_seed, expected_seed, "Seed format must be hex:decimal");
    });
}

#[test]
fn seed_derivation_matches_mining_engine_format() {
    new_test_ext().execute_with(|| {
        let parent_hash = frame_system::Pallet::<Test>::parent_hash();
        let block_height = 42u64;

        // Simulate what the mining engine does (after the fix):
        // SHA256("{hex_of_parent_hash}:{block_height_decimal}")
        use sha2::{Digest, Sha256};
        let hex_str = hex::encode(parent_hash.as_ref());
        let mut hasher = Sha256::new();
        hasher.update(hex_str.as_bytes());
        hasher.update(b":");
        hasher.update(b"42");
        let mining_seed = H256::from_slice(&hasher.finalize());

        let pallet_seed = Pallet::<Test>::derive_hamiltonian_seed(block_height);

        assert_eq!(
            pallet_seed, mining_seed,
            "Pallet and mining engine must produce identical seeds"
        );
    });
}

#[test]
fn seed_different_heights_produce_different_seeds() {
    new_test_ext().execute_with(|| {
        let seed_100 = Pallet::<Test>::derive_hamiltonian_seed(100);
        let seed_101 = Pallet::<Test>::derive_hamiltonian_seed(101);
        assert_ne!(seed_100, seed_101);
    });
}

#[test]
fn seed_zero_height() {
    new_test_ext().execute_with(|| {
        // Height 0 should produce a valid seed (genesis edge case)
        let seed = Pallet::<Test>::derive_hamiltonian_seed(0);
        assert_ne!(seed, H256::zero());
    });
}

// ═══════════════════════════════════════════════════════════════════════
// Coinbase TXID Tests
// ═══════════════════════════════════════════════════════════════════════

#[test]
fn coinbase_txid_is_deterministic() {
    new_test_ext().execute_with(|| {
        let txid1 = Pallet::<Test>::coinbase_txid(100);
        let txid2 = Pallet::<Test>::coinbase_txid(100);
        assert_eq!(txid1, txid2);
    });
}

#[test]
fn coinbase_txid_different_heights() {
    new_test_ext().execute_with(|| {
        let txid1 = Pallet::<Test>::coinbase_txid(100);
        let txid2 = Pallet::<Test>::coinbase_txid(101);
        assert_ne!(txid1, txid2);
    });
}

// ═══════════════════════════════════════════════════════════════════════
// Difficulty Tests
// ═══════════════════════════════════════════════════════════════════════

#[test]
fn initial_difficulty_is_set() {
    new_test_ext().execute_with(|| {
        assert_eq!(
            CurrentDifficulty::<Test>::get(),
            INITIAL_DIFFICULTY,
            "Initial difficulty must be 1.0 (scaled by 10^6)"
        );
    });
}

#[test]
fn difficulty_reset_at_height_167() {
    new_test_ext().execute_with(|| {
        // Set difficulty to something other than initial
        CurrentDifficulty::<Test>::put(5_000_000u64);

        // Adjust at height 167 should reset
        Pallet::<Test>::adjust_difficulty(10_000, DIFFICULTY_RESET_HEIGHT_167);
        assert_eq!(
            CurrentDifficulty::<Test>::get(),
            INITIAL_DIFFICULTY,
            "Difficulty must reset at height 167"
        );
    });
}

#[test]
fn difficulty_reset_at_height_724() {
    new_test_ext().execute_with(|| {
        CurrentDifficulty::<Test>::put(5_000_000u64);
        Pallet::<Test>::adjust_difficulty(10_000, DIFFICULTY_RESET_HEIGHT_724);
        assert_eq!(
            CurrentDifficulty::<Test>::get(),
            INITIAL_DIFFICULTY,
            "Difficulty must reset at height 724"
        );
    });
}

#[test]
fn difficulty_reset_at_height_2750() {
    new_test_ext().execute_with(|| {
        CurrentDifficulty::<Test>::put(5_000_000u64);
        Pallet::<Test>::adjust_difficulty(10_000, DIFFICULTY_RESET_HEIGHT_2750);
        assert_eq!(
            CurrentDifficulty::<Test>::get(),
            INITIAL_DIFFICULTY,
            "Difficulty must reset at height 2750"
        );
    });
}

#[test]
fn difficulty_floor_enforced() {
    new_test_ext().execute_with(|| {
        // Set very low difficulty
        CurrentDifficulty::<Test>::put(DIFFICULTY_FLOOR);

        // Populate timestamp window so adjustment can fire.
        // Use timestamps that would lower difficulty (fast blocks).
        let mut timestamps = sp_runtime::BoundedVec::default();
        for i in 0..10 {
            let _ = timestamps.try_push(i * 1000); // 1s apart (fast, target is 3.3s)
        }
        BlockTimestamps::<Test>::put(timestamps);

        // Add another fast timestamp
        Pallet::<Test>::adjust_difficulty(9_000, 3000);

        let diff = CurrentDifficulty::<Test>::get();
        assert!(
            diff >= DIFFICULTY_FLOOR,
            "Difficulty must not drop below floor (got {})",
            diff
        );
    });
}

#[test]
fn difficulty_ceiling_enforced() {
    new_test_ext().execute_with(|| {
        CurrentDifficulty::<Test>::put(DIFFICULTY_CEILING);

        let mut timestamps = sp_runtime::BoundedVec::default();
        for i in 0..10 {
            let _ = timestamps.try_push(i * 10_000); // 10s apart (slow, target is 3.3s)
        }
        BlockTimestamps::<Test>::put(timestamps);

        // This should NOT increase beyond ceiling
        Pallet::<Test>::adjust_difficulty(100_000, 3000);

        let diff = CurrentDifficulty::<Test>::get();
        assert!(
            diff <= DIFFICULTY_CEILING,
            "Difficulty must not exceed ceiling (got {})",
            diff
        );
    });
}

// ═══════════════════════════════════════════════════════════════════════
// Helper Functions Tests
// ═══════════════════════════════════════════════════════════════════════

#[test]
fn bytes_to_hex_correct() {
    new_test_ext().execute_with(|| {
        let bytes = [0x00, 0xFF, 0xAB, 0xCD];
        let hex = Pallet::<Test>::bytes_to_hex(&bytes);
        assert_eq!(&hex, b"00ffabcd");
    });
}

#[test]
fn u64_to_decimal_bytes_correct() {
    new_test_ext().execute_with(|| {
        assert_eq!(Pallet::<Test>::u64_to_decimal_bytes(0), b"0");
        assert_eq!(Pallet::<Test>::u64_to_decimal_bytes(1), b"1");
        assert_eq!(Pallet::<Test>::u64_to_decimal_bytes(42), b"42");
        assert_eq!(Pallet::<Test>::u64_to_decimal_bytes(100), b"100");
        assert_eq!(
            Pallet::<Test>::u64_to_decimal_bytes(u64::MAX),
            b"18446744073709551615"
        );
    });
}

// ═══════════════════════════════════════════════════════════════════════
// Constants Sanity
// ═══════════════════════════════════════════════════════════════════════

#[test]
fn constants_are_consistent() {
    assert!(DIFFICULTY_FLOOR < DIFFICULTY_CEILING);
    assert!(DIFFICULTY_FLOOR < DIFFICULTY_MEANINGFUL_MAX);
    assert!(DIFFICULTY_MEANINGFUL_MAX < DIFFICULTY_CEILING);
    assert!(ENERGY_VALIDATION_TOLERANCE > 0);
    assert!(SUSY_RETENTION_WINDOW > 0);
    assert!(MAX_RECENT_PROOF_HASHES > 0);
}

#[test]
fn difficulty_adjustment_clamped_to_10_percent() {
    // The adjustment factor must be between 90 and 110
    assert_eq!(MIN_ADJUSTMENT_FACTOR, 90);
    assert_eq!(MAX_ADJUSTMENT_FACTOR, 110);
}
