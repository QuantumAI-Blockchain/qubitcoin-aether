//! Benchmarking setup for `pallet_qbc_consensus`.

#![cfg(feature = "runtime-benchmarks")]

use super::*;
use frame_benchmarking::v2::*;

#[benchmarks]
mod benchmarks {
    use super::*;
    use frame_system::RawOrigin;
    use qbc_primitives::*;
    use sp_core::H256;
    use sp_runtime::BoundedVec;

    #[benchmark]
    fn submit_mining_proof() {
        // Set up initial chain state
        pallet::CurrentDifficulty::<T>::put(INITIAL_DIFFICULTY);
        pallet::NetworkTheta::<T>::put(0i64);
        pallet::NetworkAlpha::<T>::put(0i64);

        // Create a VQE proof structure
        let params: BoundedVec<i64, frame_support::traits::ConstU32<{ pallet::MAX_VQE_PARAMS }>> =
            sp_std::vec![100_000i64; 8].try_into().expect("params within bounds");

        let vqe_proof = VqeProof {
            hamiltonian_seed: H256::zero(),
            energy: 0i128,
            params,
            n_qubits: 4,
        };

        // Create dummy Ed25519 key pair (benchmark only — real validation in dispatch)
        let miner_public_key = [1u8; 32];
        let miner_signature = [0u8; 64];

        // NOTE: This benchmark cannot fully execute because it requires:
        // 1. A valid Ed25519 signature matching the proof data
        // 2. A valid Hamiltonian seed derived from the parent block hash
        // 3. A VQE energy below difficulty threshold
        // The analytical weights in weights.rs are used instead.
        // This benchmark structure exists for when a full benchmark harness is available.

        #[extrinsic_call]
        submit_mining_proof(RawOrigin::None, vqe_proof, miner_public_key, miner_signature);
    }
}
