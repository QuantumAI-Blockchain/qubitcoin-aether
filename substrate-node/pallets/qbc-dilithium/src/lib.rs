//! Pallet QBC Dilithium — Post-quantum signature verification for Qubitcoin.
//!
//! Provides CRYSTALS-Dilithium5 (NIST Level 5) signature verification as a Substrate pallet.
//! Addresses are derived from SHA2-256(public_key).
//!
//! Signature verification strategy:
//! - In `std` builds (native node): uses `pqcrypto-dilithium` crate for real verification
//! - In `no_std` builds (WASM runtime): always returns `false` (fail-closed).
//!   Native execution validates signatures before WASM re-execution.

#![cfg_attr(not(feature = "std"), no_std)]

pub use pallet::*;

// ═══════════════════════════════════════════════════════════════════════
// Host function interface for Dilithium5 verification in WASM
// ═══════════════════════════════════════════════════════════════════════

/// Dilithium5 signature verification.
///
/// In native (`std`): calls pqcrypto-dilithium directly.
/// In WASM (`no_std`): always returns `false` (fail-closed). No bypass.
pub mod dilithium_verify {
    /// Verify a Dilithium5 detached signature.
    ///
    /// Returns `true` if the signature is valid for the given message and public key.
    ///
    /// Dilithium5 parameters:
    /// - Public key: 2592 bytes
    /// - Signature: 4627 bytes
    /// - Security level: NIST Level 5 (highest)
    ///
    /// ## Security Model
    ///
    /// - **Native (`std`) builds**: Uses `pqcrypto-dilithium` for full cryptographic
    ///   Dilithium5 signature verification.
    /// - **WASM (`no_std`) builds**: **Always returns `false`** (fail-closed). The
    ///   `pqcrypto-dilithium` crate is not available in `no_std`, so rather than
    ///   implementing a bypass or partial check, we reject all signatures. This is
    ///   safe in Substrate's hybrid execution model where native validation runs
    ///   first. If WASM-only execution is ever attempted, the failure is loud and
    ///   obvious rather than silently accepting forged signatures.
    pub fn verify(public_key: &[u8], message: &[u8], signature: &[u8]) -> bool {
        // Dilithium5 signature sizes
        const DILITHIUM5_PK_SIZE: usize = 2592;
        const DILITHIUM5_SIG_SIZE: usize = 4627;

        // Validate sizes — these checks apply to BOTH std and no_std builds
        if public_key.len() != DILITHIUM5_PK_SIZE {
            return false;
        }
        if signature.len() != DILITHIUM5_SIG_SIZE {
            return false;
        }
        if message.is_empty() {
            return false;
        }

        #[cfg(feature = "std")]
        {
            // Native build: use pqcrypto-dilithium for real verification
            use pqcrypto_dilithium::dilithium5;
            use pqcrypto_traits::sign::DetachedSignature;
            use pqcrypto_traits::sign::PublicKey as PqPublicKey;

            let pk = match dilithium5::PublicKey::from_bytes(public_key) {
                Ok(pk) => pk,
                Err(_) => return false,
            };
            let sig = match dilithium5::DetachedSignature::from_bytes(signature) {
                Ok(sig) => sig,
                Err(_) => return false,
            };
            dilithium5::verify_detached_signature(&sig, message, &pk).is_ok()
        }

        #[cfg(not(feature = "std"))]
        {
            // WASM build: ALWAYS REJECT — fail closed.
            //
            // Dilithium5 cryptographic verification requires the `pqcrypto-dilithium`
            // crate which is only available in native (`std`) builds. Rather than
            // implementing a partial/bypass check that could be exploited, we
            // unconditionally reject all signatures in WASM.
            //
            // This is safe in Substrate's hybrid execution model because:
            //
            // 1. **Native execution validates first**: Blocks are validated in native
            //    mode (where `pqcrypto-dilithium` is available) BEFORE the WASM
            //    runtime re-executes for deterministic state transitions.
            // 2. **WASM re-execution trusts native**: By the time WASM runs, the
            //    native runtime has already cryptographically verified every
            //    signature in the block. The WASM runtime should never independently
            //    accept a signature that native didn't validate.
            // 3. **Fail-closed security**: If WASM-only execution is ever attempted
            //    (e.g., light-client, forkless upgrade), ALL signatures will be
            //    rejected rather than silently accepted. This makes the failure
            //    mode obvious and auditable.
            //
            // When a pure-Rust `no_std`-compatible Dilithium5 implementation
            // becomes available (e.g., via `pqc-dilithium` or `ml-dsa`), replace
            // this block with real verification.

            // Suppress unused variable warnings for the no_std path
            let _ = (public_key, message, signature);

            // FAIL CLOSED: No signature is valid in WASM-only mode.
            false
        }
    }
}

#[frame_support::pallet]
pub mod pallet {
    use frame_support::pallet_prelude::*;
    use frame_system::pallet_prelude::*;
    use qbc_primitives::{Address, MAX_DILITHIUM_PK_SIZE, MAX_DILITHIUM_SIG_SIZE};
    use sp_runtime::BoundedVec;

    /// Dilithium5 public key size (2592 bytes).
    pub const DILITHIUM5_PK_SIZE: u32 = 2592;
    /// Dilithium5 signature size (4627 bytes).
    pub const DILITHIUM5_SIG_SIZE: u32 = 4627;

    #[pallet::pallet]
    pub struct Pallet<T>(_);

    #[pallet::config]
    pub trait Config: frame_system::Config {
        type RuntimeEvent: From<Event<Self>> + IsType<<Self as frame_system::Config>::RuntimeEvent>;
    }

    /// Mapping from address to Dilithium5 public key.
    #[pallet::storage]
    #[pallet::getter(fn public_keys)]
    pub type PublicKeys<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        Address,
        BoundedVec<u8, ConstU32<MAX_DILITHIUM_PK_SIZE>>,
        OptionQuery,
    >;

    /// Total registered addresses.
    #[pallet::storage]
    #[pallet::getter(fn total_keys)]
    pub type TotalKeys<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Revoked keys — addresses whose keys have been permanently revoked.
    #[pallet::storage]
    #[pallet::getter(fn is_revoked)]
    pub type RevokedKeys<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        Address,
        bool,
        ValueQuery,
    >;

    #[pallet::event]
    #[pallet::generate_deposit(pub(super) fn deposit_event)]
    pub enum Event<T: Config> {
        /// A new Dilithium public key was registered.
        KeyRegistered { address: Address },
        /// A Dilithium public key was revoked.
        KeyRevoked { address: Address },
    }

    #[pallet::error]
    pub enum Error<T> {
        /// Public key is invalid or wrong size.
        InvalidPublicKey,
        /// Address already has a registered key.
        KeyAlreadyRegistered,
        /// Signature verification failed.
        InvalidSignature,
        /// Public key not found for address.
        KeyNotFound,
        /// Key has been revoked and cannot be used.
        KeyRevoked,
    }

    #[pallet::call]
    impl<T: Config> Pallet<T> {
        /// Register a Dilithium5 public key for an address.
        /// The address is derived from SHA2-256(public_key).
        #[pallet::call_index(0)]
        // Analytical weight: SHA2-256 hash (10µs) + 1 storage read (25µs) + 1 write (25µs)
        // + Dilithium5 key validation (~200µs for 2592-byte key) = ~260µs ≈ 260_000
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
        #[pallet::weight(260_000)]
        pub fn register_key(
            origin: OriginFor<T>,
            public_key: BoundedVec<u8, ConstU32<MAX_DILITHIUM_PK_SIZE>>,
        ) -> DispatchResult {
            ensure_signed(origin)?;

            // Validate key size (must be exactly Dilithium5 public key size)
            ensure!(
                public_key.len() == DILITHIUM5_PK_SIZE as usize,
                Error::<T>::InvalidPublicKey
            );

            // Derive address from public key
            let address = Self::derive_address(&public_key);

            // Ensure not already registered
            ensure!(
                !PublicKeys::<T>::contains_key(&address),
                Error::<T>::KeyAlreadyRegistered
            );

            // Ensure not previously revoked
            ensure!(
                !RevokedKeys::<T>::get(&address),
                Error::<T>::KeyRevoked
            );

            // Store the key
            PublicKeys::<T>::insert(&address, &public_key);
            TotalKeys::<T>::mutate(|n| *n = n.saturating_add(1));

            Self::deposit_event(Event::KeyRegistered { address });
            Ok(())
        }

        /// Revoke a Dilithium5 public key.
        ///
        /// The caller must prove ownership by providing a valid signature
        /// over a revocation message using the key being revoked.
        /// Once revoked, the key cannot be re-registered.
        #[pallet::call_index(1)]
        // Analytical weight: 1 Dilithium5 verify (800µs) + 3 storage ops (75µs) = ~875µs
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
        #[pallet::weight(875_000)]
        pub fn revoke_key(
            origin: OriginFor<T>,
            address: Address,
            revocation_sig: BoundedVec<u8, ConstU32<MAX_DILITHIUM_SIG_SIZE>>,
        ) -> DispatchResult {
            ensure_signed(origin)?;

            // Key must exist
            let pk = PublicKeys::<T>::get(&address)
                .ok_or(Error::<T>::KeyNotFound)?;

            // Must not already be revoked
            ensure!(
                !RevokedKeys::<T>::get(&address),
                Error::<T>::KeyRevoked
            );

            // Verify revocation signature to prove ownership
            let revocation_msg = b"QUBITCOIN_KEY_REVOCATION";
            ensure!(
                Self::verify_signature(&pk, revocation_msg, &revocation_sig),
                Error::<T>::InvalidSignature
            );

            // Remove the public key and mark as revoked
            PublicKeys::<T>::remove(&address);
            RevokedKeys::<T>::insert(&address, true);
            TotalKeys::<T>::mutate(|n| *n = n.saturating_sub(1));

            Self::deposit_event(Event::KeyRevoked { address });
            Ok(())
        }

        /// Register a Dilithium5 public key for a specific address (sudo only).
        ///
        /// This allows associating a Dilithium key with an address that wasn't
        /// derived from that key (e.g., mining coinbase addresses derived from
        /// Ed25519 keys). Required for spending coinbase UTXOs via submit_transaction.
        #[pallet::call_index(2)]
        #[pallet::weight(260_000)]
        pub fn sudo_register_key_for_address(
            origin: OriginFor<T>,
            address: Address,
            public_key: BoundedVec<u8, ConstU32<MAX_DILITHIUM_PK_SIZE>>,
        ) -> DispatchResult {
            ensure_root(origin)?;

            ensure!(
                public_key.len() == DILITHIUM5_PK_SIZE as usize,
                Error::<T>::InvalidPublicKey
            );
            ensure!(
                !PublicKeys::<T>::contains_key(&address),
                Error::<T>::KeyAlreadyRegistered
            );
            ensure!(
                !RevokedKeys::<T>::get(&address),
                Error::<T>::KeyRevoked
            );

            PublicKeys::<T>::insert(&address, &public_key);
            TotalKeys::<T>::mutate(|n| *n = n.saturating_add(1));

            Self::deposit_event(Event::KeyRegistered { address });
            Ok(())
        }
    }

    impl<T: Config> Pallet<T> {
        /// Derive a Qubitcoin address from a Dilithium public key.
        /// address = SHA2-256(public_key)[0..32]
        pub fn derive_address(public_key: &[u8]) -> Address {
            use sp_core::hashing::sha2_256;
            let hash = sha2_256(public_key);
            Address(hash)
        }

        /// Verify a Dilithium5 signature against a public key and message.
        ///
        /// Uses real pqcrypto-dilithium verification in native (std) builds.
        /// In WASM (no_std), always returns `false` (fail-closed).
        pub fn verify_signature(
            public_key: &[u8],
            message: &[u8],
            signature: &[u8],
        ) -> bool {
            super::dilithium_verify::verify(public_key, message, signature)
        }

        /// Look up the public key for an address.
        pub fn get_public_key(
            address: &Address,
        ) -> Option<sp_runtime::BoundedVec<u8, ConstU32<MAX_DILITHIUM_PK_SIZE>>> {
            PublicKeys::<T>::get(address)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Helper: derive address directly without needing Pallet<T> (pure function)
    fn derive_address(public_key: &[u8]) -> qbc_primitives::Address {
        use sp_core::hashing::sha2_256;
        qbc_primitives::Address(sha2_256(public_key))
    }

    #[test]
    fn test_address_derivation() {
        use sp_core::hashing::sha2_256;
        let pk = vec![42u8; 2592]; // Dilithium5 public key size
        let expected = qbc_primitives::Address(sha2_256(&pk));
        let addr = derive_address(&pk);
        assert_eq!(addr, expected);
    }

    #[test]
    fn test_address_derivation_different_keys() {
        let pk1 = vec![1u8; 2592];
        let pk2 = vec![2u8; 2592];
        let addr1 = derive_address(&pk1);
        let addr2 = derive_address(&pk2);
        assert_ne!(addr1, addr2);
    }

    #[test]
    fn test_verify_signature_rejects_wrong_pk_size() {
        let pk = vec![42u8; 100]; // Wrong size
        let msg = b"test message";
        let sig = vec![0u8; 4627];
        assert!(!dilithium_verify::verify(&pk, msg, &sig));
    }

    #[test]
    fn test_verify_signature_rejects_wrong_sig_size() {
        let pk = vec![42u8; 2592];
        let msg = b"test message";
        let sig = vec![0u8; 100]; // Wrong size
        assert!(!dilithium_verify::verify(&pk, msg, &sig));
    }

    #[test]
    fn test_verify_signature_rejects_empty_message() {
        let pk = vec![42u8; 2592];
        let msg = b"";
        let sig = vec![0u8; 4627];
        assert!(!dilithium_verify::verify(&pk, msg, &sig));
    }

    #[test]
    fn test_verify_signature_rejects_all_zero_sig() {
        let pk = vec![42u8; 2592];
        let msg = b"test message";
        let sig = vec![0u8; 4627]; // All zeros
        assert!(!dilithium_verify::verify(&pk, msg, &sig));
    }

    #[test]
    fn test_verify_signature_rejects_all_zero_pk() {
        let pk = vec![0u8; 2592]; // All zeros
        let msg = b"test message";
        let sig = vec![42u8; 4627];
        assert!(!dilithium_verify::verify(&pk, msg, &sig));
    }

    #[test]
    fn test_verify_rejects_random_signature() {
        // In std builds: real Dilithium verification rejects invalid signatures.
        // In no_std builds: fail-closed — always returns false.
        let pk = vec![42u8; 2592];
        let msg = b"test message";
        let sig = vec![0xAB; 4627]; // Random bytes, not a valid Dilithium5 signature
        assert!(!dilithium_verify::verify(&pk, msg, &sig));
    }

    #[test]
    fn test_verify_rejects_dilithium2_sizes() {
        // Ensure old Dilithium2 sizes are rejected
        let pk = vec![42u8; 1312]; // Dilithium2 PK size — should be rejected
        let msg = b"test message";
        let sig = vec![0u8; 2420]; // Dilithium2 sig size — should be rejected
        assert!(!dilithium_verify::verify(&pk, msg, &sig));
    }
}
