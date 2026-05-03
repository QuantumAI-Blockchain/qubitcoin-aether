//! Benchmarking setup for `pallet_qbc_utxo`.

#![cfg(feature = "runtime-benchmarks")]

use super::*;
use frame_benchmarking::v2::*;

#[benchmarks]
mod benchmarks {
    use super::*;
    use frame_support::BoundedVec;
    use frame_system::RawOrigin;
    use qbc_primitives::*;
    use sp_core::H256;

    /// Helper: create a dummy UTXO and insert it into storage.
    fn setup_utxo<T: Config>(txid: H256, vout: u32, address: Address, amount: QbcBalance) {
        let utxo = Utxo {
            txid,
            vout,
            address: address.clone(),
            amount,
            block_height: 1000, // well past coinbase maturity
            is_coinbase: false,
        };
        pallet::UtxoSet::<T>::insert((&txid, vout), utxo);
        pallet::Balances::<T>::mutate(&address, |bal| {
            *bal = bal.saturating_add(amount);
        });
        pallet::UtxoCount::<T>::mutate(|n| *n = n.saturating_add(1));
        pallet::CurrentHeight::<T>::put(2000u64);
    }

    #[benchmark]
    fn submit_transaction(
        i: Linear<1, 100>,
        o: Linear<1, 100>,
    ) {
        // NOTE: This benchmark sets up the storage state but cannot fully execute
        // submit_transaction because it requires valid Dilithium5 signatures.
        // The analytical weights in weights.rs are used instead.
        // This benchmark structure is here for when a full benchmark harness
        // with Dilithium key generation is available.

        let address = Address([42u8; 32]);
        let amount_per_utxo: QbcBalance = 1_000_000_000; // 10 QBC per input

        // Create input UTXOs
        let mut inputs = sp_std::vec::Vec::new();
        for idx in 0..i {
            let txid = H256::from_low_u64_be(idx as u64 + 1);
            setup_utxo::<T>(txid, 0, address.clone(), amount_per_utxo);
            inputs.push(TransactionInput {
                prev_txid: txid,
                prev_vout: 0,
            });
        }

        // Create outputs (distribute total evenly)
        let total_input = amount_per_utxo.saturating_mul(i as u128);
        let amount_per_output = total_input / (o as u128 + 1); // leave some as fee
        let mut outputs = sp_std::vec::Vec::new();
        for _ in 0..o {
            outputs.push(TransactionOutput {
                address: Address([99u8; 32]),
                amount: amount_per_output,
            });
        }

        let bounded_inputs: BoundedVec<TransactionInput, T::MaxInputs> =
            inputs.try_into().expect("inputs within bounds");
        let bounded_outputs: BoundedVec<TransactionOutput, T::MaxOutputs> =
            outputs.try_into().expect("outputs within bounds");

        // Create dummy signatures (will fail verification — this is a structural benchmark)
        let dummy_sig: BoundedVec<u8, frame_support::traits::ConstU32<MAX_DILITHIUM_SIG_SIZE>> =
            sp_std::vec![0u8; 4627].try_into().expect("sig within bounds");
        let mut sigs = sp_std::vec::Vec::new();
        for _ in 0..i {
            sigs.push(dummy_sig.clone());
        }
        let bounded_sigs: BoundedVec<
            BoundedVec<u8, frame_support::traits::ConstU32<MAX_DILITHIUM_SIG_SIZE>>,
            T::MaxInputs,
        > = sigs.try_into().expect("sigs within bounds");

        let caller: T::AccountId = frame_benchmarking::whitelisted_caller();

        // We use `#[extrinsic_call]` but expect it to fail at signature verification.
        // The weight is dominated by storage setup which is measured.
        // Real benchmarks would need a Dilithium key pair generator.
        #[extrinsic_call]
        submit_transaction(RawOrigin::Signed(caller), bounded_inputs, bounded_outputs, bounded_sigs);
    }
}
