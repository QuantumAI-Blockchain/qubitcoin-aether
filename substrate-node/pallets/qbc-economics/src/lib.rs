//! Pallet QBC Economics — Golden ratio emission schedule and phi-halving.
//!
//! Implements Qubitcoin's unique economic model:
//! - Initial reward: 15.27 QBC per block
//! - Phi-halving: reward / PHI^era (where era = height / HALVING_INTERVAL)
//! - Max supply: 3.3 billion QBC
//! - Genesis premine: 33 million QBC (~1%)

#![cfg_attr(not(feature = "std"), no_std)]

pub use pallet::*;

#[frame_support::pallet]
pub mod pallet {
    use frame_support::pallet_prelude::*;
    use frame_system::pallet_prelude::*;
    use qbc_primitives::*;

    #[pallet::pallet]
    pub struct Pallet<T>(_);

    #[pallet::config]
    pub trait Config: frame_system::Config {
        type RuntimeEvent: From<Event<Self>> + IsType<<Self as frame_system::Config>::RuntimeEvent>;
    }

    /// Total QBC ever emitted (in smallest units).
    #[pallet::storage]
    #[pallet::getter(fn total_emitted)]
    pub type TotalEmitted<T: Config> = StorageValue<_, QbcBalance, ValueQuery>;

    /// Current era (for phi-halving calculation).
    #[pallet::storage]
    #[pallet::getter(fn current_era)]
    pub type CurrentEra<T: Config> = StorageValue<_, u32, ValueQuery>;

    /// Block height when last era change occurred.
    #[pallet::storage]
    #[pallet::getter(fn era_start_block)]
    pub type EraStartBlock<T: Config> = StorageValue<_, u64, ValueQuery>;

    #[pallet::event]
    #[pallet::generate_deposit(pub(super) fn deposit_event)]
    pub enum Event<T: Config> {
        /// Block reward was calculated.
        RewardCalculated { block_height: u64, reward: QbcBalance, era: u32 },
        /// New era started (phi-halving occurred).
        NewEra { era: u32, reward: QbcBalance },
        // Note: PremineEmitted was removed because Substrate genesis_build
        // cannot emit events (no block context during genesis construction).
        // The genesis premine is recorded via TotalEmitted storage instead.
    }

    // Note: No #[pallet::error] enum is defined for this pallet because
    // calculate_reward() returns a capped value (or 0) rather than an error
    // when supply is depleted. The previously defined MaxSupplyExceeded
    // variant was never used and has been removed.

    #[pallet::genesis_config]
    #[derive(frame_support::DefaultNoBound)]
    pub struct GenesisConfig<T: Config> {
        /// Initial total emitted (for genesis premine).
        pub initial_emitted: QbcBalance,
        #[serde(skip)]
        pub _phantom: core::marker::PhantomData<T>,
    }

    #[pallet::genesis_build]
    impl<T: Config> BuildGenesisConfig for GenesisConfig<T> {
        fn build(&self) {
            TotalEmitted::<T>::put(self.initial_emitted);
            CurrentEra::<T>::put(0u32);
        }
    }

    impl<T: Config> Pallet<T> {
        /// Calculate the block reward for a given height.
        ///
        /// reward = INITIAL_REWARD / PHI^era
        /// era = block_height / HALVING_INTERVAL
        ///
        /// Uses fixed-point arithmetic to avoid floating point in runtime.
        /// If the total emitted plus the reward would exceed MAX_SUPPLY,
        /// the reward is capped to the remaining supply (or 0 if already at max).
        pub fn calculate_reward(block_height: u64) -> QbcBalance {
            let era = (block_height / HALVING_INTERVAL) as u32;

            let base_reward = if era == 0 {
                INITIAL_REWARD
            } else {
                // PHI^era using fixed-point: start with INITIAL_REWARD * PHI_DENOM,
                // then divide by PHI_SCALED `era` times.
                let mut reward = INITIAL_REWARD as u128 * PHI_DENOM;
                for _ in 0..era {
                    reward = reward * PHI_DENOM / PHI_SCALED;
                }
                let result = reward / PHI_DENOM;
                // Never go below 1 unit
                result.max(1)
            };

            // Cap reward so total emitted never exceeds MAX_SUPPLY
            let total = TotalEmitted::<T>::get();
            let remaining = MAX_SUPPLY.saturating_sub(total);
            if remaining == 0 {
                return 0;
            }
            base_reward.min(remaining)
        }

        /// Return the current total emitted supply.
        ///
        /// This is O(1) — it reads directly from the `TotalEmitted` storage
        /// value which is updated incrementally by `on_block_authored()`.
        /// The previous implementation iterated over every block height,
        /// which was O(block_height) and would become unusable on a mature chain.
        ///
        /// The `block_height` parameter is accepted for API compatibility but
        /// is not used; the canonical total is always the storage value.
        pub fn compute_total_emitted(_block_height: u64) -> QbcBalance {
            TotalEmitted::<T>::get()
        }

        /// Record emission for a new block. Returns the reward amount.
        pub fn on_block_authored(block_height: u64) -> QbcBalance {
            let reward = Self::calculate_reward(block_height);
            let era = (block_height / HALVING_INTERVAL) as u32;

            // Update storage
            TotalEmitted::<T>::mutate(|total| {
                *total = total.saturating_add(reward).min(MAX_SUPPLY);
            });

            // Check for era change
            let current = CurrentEra::<T>::get();
            if era > current {
                CurrentEra::<T>::put(era);
                EraStartBlock::<T>::put(block_height);
                Self::deposit_event(Event::NewEra { era, reward });
            }

            Self::deposit_event(Event::RewardCalculated {
                block_height,
                reward,
                era,
            });

            reward
        }
    }
}

#[cfg(test)]
mod tests {
    use super::pallet::*;
    use qbc_primitives::*;

    // Direct function tests (no runtime needed)

    #[test]
    fn test_era_0_reward() {
        let reward = calculate_reward_standalone(0);
        assert_eq!(reward, INITIAL_REWARD);
    }

    #[test]
    fn test_era_1_reward() {
        let reward = calculate_reward_standalone(HALVING_INTERVAL);
        // reward ≈ 15.27 / 1.618 ≈ 9.44 QBC
        let expected_approx = (15.27 / 1.618033988749895 * 1e8) as u128;
        let diff = if reward > expected_approx {
            reward - expected_approx
        } else {
            expected_approx - reward
        };
        // Allow 1 unit tolerance for fixed-point rounding
        assert!(diff <= 1, "era 1 reward {} vs expected {}", reward, expected_approx);
    }

    #[test]
    fn test_era_2_reward() {
        let reward = calculate_reward_standalone(2 * HALVING_INTERVAL);
        // reward ≈ 15.27 / 1.618^2 ≈ 5.83 QBC
        let expected_approx = (15.27 / (1.618033988749895 * 1.618033988749895) * 1e8) as u128;
        let diff = if reward > expected_approx {
            reward - expected_approx
        } else {
            expected_approx - reward
        };
        assert!(diff <= 1, "era 2 reward {} vs expected {}", reward, expected_approx);
    }

    #[test]
    fn test_reward_never_zero() {
        // Even at very high era, reward should be at least 1
        let reward = calculate_reward_standalone(100 * HALVING_INTERVAL);
        assert!(reward >= 1);
    }

    /// Standalone reward calculation for testing without runtime.
    fn calculate_reward_standalone(block_height: u64) -> QbcBalance {
        let era = (block_height / HALVING_INTERVAL) as u32;
        if era == 0 {
            return INITIAL_REWARD;
        }
        let mut reward = INITIAL_REWARD as u128 * PHI_DENOM;
        for _ in 0..era {
            reward = reward * PHI_DENOM / PHI_SCALED;
        }
        (reward / PHI_DENOM).max(1)
    }
}
