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

    /// Total QBC permanently burned from transaction fees (in smallest units).
    #[pallet::storage]
    #[pallet::getter(fn total_fees_burned)]
    pub type TotalFeesBurned<T: Config> = StorageValue<_, QbcBalance, ValueQuery>;

    #[pallet::event]
    #[pallet::generate_deposit(pub(super) fn deposit_event)]
    pub enum Event<T: Config> {
        /// Block reward was calculated.
        RewardCalculated { block_height: u64, reward: QbcBalance, era: u32 },
        /// New era started (phi-halving occurred).
        NewEra { era: u32, reward: QbcBalance },
        /// Transaction fees were burned (50% of collected fees).
        FeesBurned { burned: QbcBalance, miner_portion: QbcBalance },
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
        /// Maximum number of eras for the phi-halving loop.
        ///
        /// At 15,474,020 blocks per era and 3.3s/block, 100 eras spans ~161 years.
        /// The reward at era 100 is astronomically small (INITIAL_REWARD / phi^100 ≈ 0).
        /// Capping prevents u128 overflow in the fixed-point multiplication chain
        /// and avoids unbounded loops from extreme block heights.
        const MAX_ERA: u32 = 100;

        pub fn calculate_reward(block_height: u64) -> QbcBalance {
            let era = (block_height / HALVING_INTERVAL) as u32;

            let base_reward = if era == 0 {
                INITIAL_REWARD
            } else {
                // Cap the era to prevent unbounded loops at extreme block heights.
                // Beyond MAX_ERA, the reward is effectively 1 (minimum unit).
                let capped_era = era.min(Self::MAX_ERA);

                // PHI^era using fixed-point: start with INITIAL_REWARD * PHI_DENOM,
                // then divide by PHI_SCALED `era` times.
                //
                // Each iteration computes: reward = reward * PHI_DENOM / PHI_SCALED
                // which is equivalent to: reward = reward / PHI (in fixed-point).
                //
                // The intermediate product `reward * PHI_DENOM` can overflow u128
                // when reward is still large (early eras). To avoid this, we split
                // the multiplication using 128-bit safe division:
                //   reward * PHI_DENOM / PHI_SCALED
                //   = reward * (PHI_DENOM / gcd) / (PHI_SCALED / gcd)
                //
                // But simpler: since PHI_DENOM and PHI_SCALED share factors, we can
                // reduce first: PHI_DENOM / PHI_SCALED = 1/phi, and we need to
                // compute reward / phi. Using the identity:
                //   reward * PHI_DENOM / PHI_SCALED
                // We pre-divide reward to avoid overflow when possible.
                let mut reward = INITIAL_REWARD as u128 * PHI_DENOM;
                for _ in 0..capped_era {
                    // Split to avoid overflow: divide first, then correct remainder.
                    // reward * PHI_DENOM / PHI_SCALED
                    // = (reward / PHI_SCALED) * PHI_DENOM + (reward % PHI_SCALED) * PHI_DENOM / PHI_SCALED
                    let quotient = reward / PHI_SCALED;
                    let remainder = reward % PHI_SCALED;
                    reward = quotient.saturating_mul(PHI_DENOM)
                        .saturating_add(remainder.saturating_mul(PHI_DENOM) / PHI_SCALED);
                    // If reward has decayed below PHI_DENOM, the final result will be < 1.
                    // Short-circuit to avoid unnecessary iterations.
                    if reward < PHI_DENOM {
                        reward = PHI_DENOM; // Will yield result.max(1) = 1 below
                        break;
                    }
                }
                let result = reward / PHI_DENOM;
                // Never go below 1 unit
                result.max(1)
            };

            // Tail emission floor: if phi-halving drops the reward below
            // TAIL_EMISSION_REWARD (0.1 QBC), use the tail emission instead.
            // This ensures miners always receive a minimum incentive.
            // Matches the Python node: Config.TAIL_EMISSION_REWARD = 0.1 QBC.
            let base_reward = if base_reward < TAIL_EMISSION_REWARD as u128 {
                TAIL_EMISSION_REWARD as u128
            } else {
                base_reward
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

        /// Burn a portion of collected transaction fees and return the miner's portion.
        ///
        /// Implements the same fee-burn logic as the Python node:
        ///   burned  = total_fees * FEE_BURN_PERCENTAGE / 100  (rounded to 8 decimals)
        ///   miner   = total_fees - burned
        ///
        /// The burned amount is permanently removed from circulation by incrementing
        /// `TotalFeesBurned` (and NOT adding it to any balance).
        ///
        /// Returns `(miner_portion, burned_amount)`.
        pub fn burn_fees(total_fees: QbcBalance) -> (QbcBalance, QbcBalance) {
            if total_fees == 0 {
                return (0, 0);
            }

            // FEE_BURN_PERCENTAGE is 50 (meaning 50%).
            // For 8-decimal-place rounding: we work in base units already (10^8),
            // so integer division here is equivalent to truncation at 8 decimals
            // (matching Python's Decimal quantize with ROUND_DOWN default).
            let burned = total_fees * FEE_BURN_PERCENTAGE as u128 / 100;
            let miner_portion = total_fees - burned;

            // Record cumulative burn in storage
            TotalFeesBurned::<T>::mutate(|total| {
                *total = total.saturating_add(burned);
            });

            Self::deposit_event(Event::FeesBurned {
                burned,
                miner_portion,
            });

            (miner_portion, burned)
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
    /// Mirrors the pallet's `calculate_reward` logic without needing storage.
    fn calculate_reward_standalone(block_height: u64) -> QbcBalance {
        let era = (block_height / HALVING_INTERVAL) as u32;
        if era == 0 {
            return INITIAL_REWARD;
        }
        let capped_era = era.min(100);
        let mut reward = INITIAL_REWARD as u128 * PHI_DENOM;
        for _ in 0..capped_era {
            let quotient = reward / PHI_SCALED;
            let remainder = reward % PHI_SCALED;
            reward = quotient.saturating_mul(PHI_DENOM)
                .saturating_add(remainder.saturating_mul(PHI_DENOM) / PHI_SCALED);
            if reward < PHI_DENOM {
                reward = PHI_DENOM;
                break;
            }
        }
        let result = (reward / PHI_DENOM).max(1);
        // Apply tail emission floor (matches Python node)
        if result < TAIL_EMISSION_REWARD as u128 {
            TAIL_EMISSION_REWARD as u128
        } else {
            result
        }
    }

    /// Standalone fee burn calculation for testing without runtime.
    fn burn_fees_standalone(total_fees: QbcBalance) -> (QbcBalance, QbcBalance) {
        let burned = total_fees * FEE_BURN_PERCENTAGE as u128 / 100;
        let miner_portion = total_fees - burned;
        (miner_portion, burned)
    }

    #[test]
    fn test_extreme_era_no_overflow() {
        // Even at an absurdly high era, the function should not overflow
        let reward = calculate_reward_standalone(1_000_000 * HALVING_INTERVAL);
        assert!(reward >= 1, "reward must be at least 1 even at extreme eras");
    }

    #[test]
    fn test_tail_emission_floor() {
        // At a very high era, phi-halving would drop reward below 0.1 QBC,
        // but tail emission ensures a floor of TAIL_EMISSION_REWARD.
        let reward = calculate_reward_standalone(50 * HALVING_INTERVAL);
        assert!(
            reward >= TAIL_EMISSION_REWARD as u128,
            "reward {} must be >= tail emission {}",
            reward,
            TAIL_EMISSION_REWARD
        );
    }

    #[test]
    fn test_tail_emission_exact_value() {
        // TAIL_EMISSION_REWARD = 0.1 QBC = 10_000_000 base units
        assert_eq!(TAIL_EMISSION_REWARD, 10_000_000u64);
    }

    #[test]
    fn test_fee_burn_50_percent() {
        // 1 QBC in fees → 0.5 burned, 0.5 to miner
        let total_fees: QbcBalance = 100_000_000; // 1 QBC
        let (miner, burned) = burn_fees_standalone(total_fees);
        assert_eq!(burned, 50_000_000);  // 0.5 QBC
        assert_eq!(miner, 50_000_000);   // 0.5 QBC
        assert_eq!(miner + burned, total_fees);
    }

    #[test]
    fn test_fee_burn_zero_fees() {
        let (miner, burned) = burn_fees_standalone(0);
        assert_eq!(miner, 0);
        assert_eq!(burned, 0);
    }

    #[test]
    fn test_fee_burn_odd_amount() {
        // 1 unit fee → burned = 0 (integer truncation), miner gets 1
        let (miner, burned) = burn_fees_standalone(1);
        assert_eq!(burned, 0);
        assert_eq!(miner, 1);
    }

    #[test]
    fn test_fee_burn_small_amount() {
        // 15 units → burned = 7, miner = 8 (integer truncation of 7.5)
        let (miner, burned) = burn_fees_standalone(15);
        assert_eq!(burned, 7);
        assert_eq!(miner, 8);
        assert_eq!(miner + burned, 15);
    }
}
