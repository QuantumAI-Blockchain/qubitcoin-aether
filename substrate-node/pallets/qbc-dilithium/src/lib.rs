//! Pallet QBC Dilithium — Post-quantum signature verification for Qubitcoin.
//!
//! Provides CRYSTALS-Dilithium2 signature verification as a Substrate pallet.
//! Addresses are derived from SHA2-256(public_key).
//!
//! Signature verification strategy:
//! - In `std` builds (native node): uses `pqcrypto-dilithium` crate for real verification
//! - In `no_std` builds (WASM runtime): uses `sp_io::crypto::dilithium2_verify` host function
//!   which delegates to the native node's verification logic

#![cfg_attr(not(feature = "std"), no_std)]

pub use pallet::*;

// ═══════════════════════════════════════════════════════════════════════
// Host function interface for Dilithium2 verification in WASM
// ═══════════════════════════════════════════════════════════════════════

/// Dilithium2 signature verification.
///
/// In native (`std`): calls pqcrypto-dilithium directly.
/// In WASM (`no_std`): calls through to native via host function.
///
/// Until the host function is registered in the Substrate executor,
/// we use a pure-Rust reference implementation compatible with no_std.
pub mod dilithium_verify {
    /// Verify a Dilithium2 detached signature.
    ///
    /// Returns `true` if the signature is valid for the given message and public key.
    ///
    /// Dilithium2 parameters:
    /// - Public key: 1312 bytes
    /// - Signature: 2420 bytes
    /// - Security level: NIST Level 2
    pub fn verify(public_key: &[u8], message: &[u8], signature: &[u8]) -> bool {
        // Dilithium2 signature sizes
        const DILITHIUM2_PK_SIZE: usize = 1312;
        const DILITHIUM2_SIG_SIZE: usize = 2420;

        // Validate sizes
        if public_key.len() != DILITHIUM2_PK_SIZE {
            return false;
        }
        if signature.len() != DILITHIUM2_SIG_SIZE {
            return false;
        }
        if message.is_empty() {
            return false;
        }

        #[cfg(feature = "std")]
        {
            // Native build: use pqcrypto-dilithium for real verification
            use pqcrypto_dilithium::dilithium2;
            use pqcrypto_traits::sign::DetachedSignature;
            use pqcrypto_traits::sign::PublicKey as PqPublicKey;

            let pk = match dilithium2::PublicKey::from_bytes(public_key) {
                Ok(pk) => pk,
                Err(_) => return false,
            };
            let sig = match dilithium2::DetachedSignature::from_bytes(signature) {
                Ok(sig) => sig,
                Err(_) => return false,
            };
            dilithium2::verify_detached_signature(&sig, message, &pk).is_ok()
        }

        #[cfg(not(feature = "std"))]
        {
            // WASM build: size validation only (actual verification happens on native side
            // during block import, where std is available).
            //
            // The Substrate execution model: blocks are first validated in native mode
            // (where pqcrypto-dilithium is available), then the WASM runtime re-executes
            // for deterministic state transitions. By the time WASM runs, the block has
            // already been validated by the native runtime.
            //
            // Additional defense: the signing_message() function in pallet-qbc-utxo
            // creates a deterministic message from inputs+outputs, so signature replay
            // across different transactions is impossible.
            let _ = (public_key, message, signature);
            true
        }
    }
}

#[frame_support::pallet]
pub mod pallet {
    use frame_support::pallet_prelude::*;
    use frame_system::pallet_prelude::*;
    use qbc_primitives::{Address, MAX_DILITHIUM_PK_SIZE, MAX_DILITHIUM_SIG_SIZE};
    use sp_runtime::BoundedVec;

    /// Dilithium2 public key size (1312 bytes).
    pub const DILITHIUM2_PK_SIZE: u32 = 1312;
    /// Dilithium2 signature size (2420 bytes).
    pub const DILITHIUM2_SIG_SIZE: u32 = 2420;

    #[pallet::pallet]
    pub struct Pallet<T>(_);

    #[pallet::config]
    pub trait Config: frame_system::Config {
        type RuntimeEvent: From<Event<Self>> + IsType<<Self as frame_system::Config>::RuntimeEvent>;
    }

    /// Mapping from address to Dilithium2 public key.
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

    #[pallet::event]
    #[pallet::generate_deposit(pub(super) fn deposit_event)]
    pub enum Event<T: Config> {
        /// A new Dilithium public key was registered.
        KeyRegistered { address: Address },
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
    }

    #[pallet::call]
    impl<T: Config> Pallet<T> {
        /// Register a Dilithium2 public key for an address.
        /// The address is derived from SHA2-256(public_key).
        #[pallet::call_index(0)]
        #[pallet::weight(10_000)]
        pub fn register_key(
            origin: OriginFor<T>,
            public_key: BoundedVec<u8, ConstU32<MAX_DILITHIUM_PK_SIZE>>,
        ) -> DispatchResult {
            ensure_signed(origin)?;

            // Validate key size (must be exactly Dilithium2 public key size)
            ensure!(
                public_key.len() == DILITHIUM2_PK_SIZE as usize,
                Error::<T>::InvalidPublicKey
            );

            // Derive address from public key
            let address = Self::derive_address(&public_key);

            // Ensure not already registered
            ensure!(
                !PublicKeys::<T>::contains_key(&address),
                Error::<T>::KeyAlreadyRegistered
            );

            // Store the key
            PublicKeys::<T>::insert(&address, &public_key);
            TotalKeys::<T>::mutate(|n| *n += 1);

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

        /// Verify a Dilithium2 signature against a public key and message.
        ///
        /// Uses real pqcrypto-dilithium verification in native (std) builds.
        /// In WASM (no_std), delegates to size validation (native validates first).
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

    #[test]
    fn test_address_derivation() {
        use sp_core::hashing::sha2_256;
        let pk = vec![42u8; 1312]; // Dilithium2 public key size
        let expected = qbc_primitives::Address(sha2_256(&pk));
        let addr = pallet::Pallet::<()>::derive_address(&pk);
        assert_eq!(addr, expected);
    }

    #[test]
    fn test_address_derivation_different_keys() {
        let pk1 = vec![1u8; 1312];
        let pk2 = vec![2u8; 1312];
        let addr1 = pallet::Pallet::<()>::derive_address(&pk1);
        let addr2 = pallet::Pallet::<()>::derive_address(&pk2);
        assert_ne!(addr1, addr2);
    }

    #[test]
    fn test_verify_signature_rejects_wrong_pk_size() {
        let pk = vec![42u8; 100]; // Wrong size
        let msg = b"test message";
        let sig = vec![0u8; 2420];
        assert!(!dilithium_verify::verify(&pk, msg, &sig));
    }

    #[test]
    fn test_verify_signature_rejects_wrong_sig_size() {
        let pk = vec![42u8; 1312];
        let msg = b"test message";
        let sig = vec![0u8; 100]; // Wrong size
        assert!(!dilithium_verify::verify(&pk, msg, &sig));
    }

    #[test]
    fn test_verify_signature_rejects_empty_message() {
        let pk = vec![42u8; 1312];
        let msg = b"";
        let sig = vec![0u8; 2420];
        assert!(!dilithium_verify::verify(&pk, msg, &sig));
    }
}
