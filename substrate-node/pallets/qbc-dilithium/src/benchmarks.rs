//! Benchmarking setup for `pallet_qbc_dilithium`.

#![cfg(feature = "runtime-benchmarks")]

use super::*;
use frame_benchmarking::v2::*;

#[benchmarks]
mod benchmarks {
    use super::*;
    use frame_support::BoundedVec;
    use frame_system::RawOrigin;
    use qbc_primitives::{Address, MAX_DILITHIUM_PK_SIZE, MAX_DILITHIUM_SIG_SIZE};

    #[benchmark]
    fn register_key() {
        let caller: T::AccountId = frame_benchmarking::whitelisted_caller();

        // Create a dummy Dilithium5 public key (2592 bytes)
        let public_key: BoundedVec<u8, frame_support::traits::ConstU32<MAX_DILITHIUM_PK_SIZE>> =
            sp_std::vec![42u8; 2592].try_into().expect("pk within bounds");

        #[extrinsic_call]
        register_key(RawOrigin::Signed(caller), public_key);
    }

    #[benchmark]
    fn revoke_key() {
        let caller: T::AccountId = frame_benchmarking::whitelisted_caller();

        // First register a key so we can revoke it
        let public_key: BoundedVec<u8, frame_support::traits::ConstU32<MAX_DILITHIUM_PK_SIZE>> =
            sp_std::vec![42u8; 2592].try_into().expect("pk within bounds");

        let address = pallet::Pallet::<T>::derive_address(&public_key);
        pallet::PublicKeys::<T>::insert(&address, &public_key);
        pallet::TotalKeys::<T>::put(1u64);

        // Create a dummy revocation signature (will fail real verification,
        // but benchmarks measure compute cost)
        let revocation_sig: BoundedVec<u8, frame_support::traits::ConstU32<MAX_DILITHIUM_SIG_SIZE>> =
            sp_std::vec![0u8; 4627].try_into().expect("sig within bounds");

        // NOTE: This will fail at signature verification in std builds.
        // Analytical weights are used until a full benchmark harness with
        // real Dilithium key generation is available.
        #[extrinsic_call]
        revoke_key(RawOrigin::Signed(caller), address, revocation_sig);
    }

    #[benchmark]
    fn sudo_register_key_for_address() {
        let address = Address([99u8; 32]);
        let public_key: BoundedVec<u8, frame_support::traits::ConstU32<MAX_DILITHIUM_PK_SIZE>> =
            sp_std::vec![55u8; 2592].try_into().expect("pk within bounds");

        #[extrinsic_call]
        sudo_register_key_for_address(RawOrigin::Root, address, public_key);
    }
}
