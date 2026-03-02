//! Reward Engine — Calculates QBC rewards for knowledge contributions.
//!
//! Reward formula:
//!   base_reward * quality * novelty_bonus * tier_multiplier * streak_multiplier
//!   * staking_boost * early_contributor_bonus
//!
//! Pool balance is derived from DB (initial_pool - SUM(distributed)), never from RAM.

use crate::config::AikgsConfig;
use crate::db::Db;

/// Tier multipliers.
const TIER_MULTIPLIERS: &[(&str, f64)] = &[
    ("bronze", 0.5),
    ("silver", 1.0),
    ("gold", 2.0),
    ("diamond", 5.0),
];

/// Streak multipliers: (min_days, multiplier).
const STREAK_MULTIPLIERS: &[(i32, f64)] = &[(100, 2.0), (30, 1.5), (7, 1.3), (3, 1.1), (0, 1.0)];

/// Staking boost thresholds: (min_staked, multiplier).
const STAKING_BOOSTS: &[(f64, f64)] = &[
    (10_000.0, 1.5),
    (1_000.0, 1.3),
    (100.0, 1.1),
    (0.0, 1.0),
];

/// Breakdown of a reward calculation.
#[derive(Debug, Clone)]
pub struct RewardCalculation {
    pub base_reward: f64,
    pub quality_factor: f64,
    pub novelty_factor: f64,
    pub tier_multiplier: f64,
    pub streak_multiplier: f64,
    pub staking_boost: f64,
    pub early_bonus: f64,
    pub final_reward: f64,
}

pub struct RewardEngine {
    base_reward: f64,
    max_reward: f64,
    initial_pool: f64,
    early_threshold: i64,
    early_max_bonus: f64,
}

impl RewardEngine {
    pub fn new(cfg: &AikgsConfig) -> Self {
        Self {
            base_reward: cfg.base_reward_qbc,
            max_reward: cfg.max_reward_qbc,
            initial_pool: cfg.initial_pool_qbc,
            early_threshold: cfg.early_threshold,
            early_max_bonus: cfg.early_max_bonus,
        }
    }

    /// Calculate reward with full breakdown.
    /// `total_contributions` and `streak_days` come from DB (not RAM).
    pub fn calculate(
        &self,
        quality_score: f64,
        novelty_score: f64,
        tier: &str,
        streak_days: i32,
        staked_amount: f64,
        total_contributions: i64,
        pool_balance: f64,
    ) -> RewardCalculation {
        let quality_factor = quality_score.clamp(0.0, 1.0);
        let novelty_factor = 1.0 + (novelty_score.clamp(0.0, 1.0) * 0.5);

        let tier_mult = TIER_MULTIPLIERS
            .iter()
            .find(|(t, _)| *t == tier)
            .map(|(_, m)| *m)
            .unwrap_or(1.0);

        let streak_mult = STREAK_MULTIPLIERS
            .iter()
            .find(|(days, _)| streak_days >= *days)
            .map(|(_, m)| *m)
            .unwrap_or(1.0);

        let staking_boost = STAKING_BOOSTS
            .iter()
            .find(|(thresh, _)| staked_amount >= *thresh)
            .map(|(_, m)| *m)
            .unwrap_or(1.0);

        let early_bonus = if total_contributions < self.early_threshold {
            let decay =
                (self.early_threshold - total_contributions) as f64 / self.early_threshold as f64;
            1.0 + (self.early_max_bonus - 1.0) * decay
        } else {
            1.0
        };

        let mut reward = self.base_reward
            * quality_factor
            * novelty_factor
            * tier_mult
            * streak_mult
            * staking_boost
            * early_bonus;

        reward = reward.min(self.max_reward);
        reward = reward.min(pool_balance);
        reward = reward.max(0.0);

        RewardCalculation {
            base_reward: self.base_reward,
            quality_factor,
            novelty_factor,
            tier_multiplier: tier_mult,
            streak_multiplier: streak_mult,
            staking_boost,
            early_bonus,
            final_reward: (reward * 1e8).round() / 1e8,
        }
    }

    /// Get the current pool balance = initial_pool - total_distributed.
    pub async fn pool_balance(&self, db: &Db) -> f64 {
        let distributed = db.get_total_distributed().await.unwrap_or(0.0);
        (self.initial_pool - distributed).max(0.0)
    }

    /// Get reward stats from DB.
    pub async fn stats(&self, db: &Db) -> RewardStats {
        let distributed = db.get_total_distributed().await.unwrap_or(0.0);
        let count = db.get_reward_distribution_count().await.unwrap_or(0);
        let total_contributions = db.next_contribution_id().await.unwrap_or(1) - 1;

        RewardStats {
            pool_balance: (self.initial_pool - distributed).max(0.0),
            total_distributed: distributed,
            distribution_count: count,
            total_contributions,
            base_reward: self.base_reward,
            max_reward: self.max_reward,
            early_threshold: self.early_threshold,
        }
    }

    /// Get streak multiplier for display.
    pub fn streak_multiplier(streak_days: i32) -> f64 {
        STREAK_MULTIPLIERS
            .iter()
            .find(|(days, _)| streak_days >= *days)
            .map(|(_, m)| *m)
            .unwrap_or(1.0)
    }

    /// Get next streak milestone.
    pub fn next_streak_milestone(current: i32) -> i32 {
        let milestones = [3, 7, 30, 100];
        for &m in &milestones {
            if current < m {
                return m;
            }
        }
        0
    }
}

pub struct RewardStats {
    pub pool_balance: f64,
    pub total_distributed: f64,
    pub distribution_count: i64,
    pub total_contributions: i64,
    pub base_reward: f64,
    pub max_reward: f64,
    pub early_threshold: i64,
}
