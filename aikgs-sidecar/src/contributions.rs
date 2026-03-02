//! Contribution Manager — Orchestrates the full AIKGS contribution lifecycle.
//!
//! Flow:
//!   1. Rate-limit check (daily submissions per address)
//!   2. Score content (quality, novelty, gaming detection)
//!   3. Dedup check (content hash already exists in DB)
//!   4. Calculate novelty (0.9 if novel, 0.5 if existing hash)
//!   5. Calculate reward via RewardEngine
//!   6. Insert contribution + reward records to DB
//!   7. Process affiliate commissions (L1 + L2)
//!   8. Update contributor profile (progressive unlocks)
//!   9. Submit gold/diamond contributions for peer curation
//!  10. Return ContributionResult with all data

use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::affiliates::AffiliateManager;
use crate::config::AikgsConfig;
use crate::db::{
    ContributionRow, ContributionStatsRow, Db, LeaderboardRow, ProfileRow,
};
use crate::rewards::RewardEngine;
use crate::scorer::Scorer;

/// Errors that can occur during contribution processing.
#[derive(Debug, thiserror::Error)]
pub enum AikgsError {
    #[error("rate limit exceeded: {0} daily submissions (max {1})")]
    RateLimitExceeded(i64, i32),

    #[error("content rejected as spam: {0}")]
    SpamRejected(String),

    #[error("duplicate content: hash {0} already exists")]
    DuplicateContent(String),

    #[error("database error: {0}")]
    Database(#[from] sqlx::Error),

    #[error("affiliate error: {0}")]
    Affiliate(#[from] crate::affiliates::AikgsError),

    #[error("internal error: {0}")]
    Internal(String),
}

/// Complete result of a processed contribution, matching the proto ContributionRecord.
#[derive(Debug, Clone)]
pub struct ContributionResult {
    pub contribution_id: i64,
    pub contributor_address: String,
    pub content_hash: String,
    pub knowledge_node_id: i64,
    pub quality_score: f64,
    pub novelty_score: f64,
    pub combined_score: f64,
    pub tier: String,
    pub domain: String,
    pub reward_amount: f64,
    pub affiliate_l1_amount: f64,
    pub affiliate_l2_amount: f64,
    pub is_bounty_fulfillment: bool,
    pub bounty_id: i64,
    pub badges_earned: Vec<String>,
    pub block_height: i64,
    pub timestamp: f64,
    pub status: String,
}

// ── Progressive Unlock Constants ────────────────────────────────────────────

/// Level definitions: (min_rp, level, name, features_unlocked).
const LEVELS: &[(f64, i32, &str, &[&str])] = &[
    (0.0, 1, "Novice", &["basic_chat", "contribute"]),
    (100.0, 2, "Learner", &["custom_theme", "profile_badge"]),
    (500.0, 3, "Scholar", &["priority_queue"]),
    (1000.0, 4, "Curator", &["curation_voting"]),
    (2500.0, 5, "Sage", &["governance_voting"]),
    (5000.0, 6, "Master", &["create_bounties"]),
    (10000.0, 7, "Archon", &["custom_llm_config"]),
    (25000.0, 8, "Enlightened", &["elite_badge", "early_access"]),
];

/// Reputation points per contribution = combined_score * BASE * tier_mult.
const RP_CONTRIBUTION_BASE: f64 = 10.0;
const RP_BOUNTY_FULFILLMENT: f64 = 50.0;

/// Tier RP multipliers.
fn tier_rp_multiplier(tier: &str) -> f64 {
    match tier {
        "bronze" => 0.5,
        "silver" => 1.0,
        "gold" => 2.0,
        "diamond" => 5.0,
        _ => 1.0,
    }
}

/// Streak milestone RP bonuses: (streak_days, bonus_rp).
const STREAK_RP_MILESTONES: &[(i32, f64)] = &[(3, 10.0), (7, 25.0), (30, 50.0), (100, 100.0)];

/// Badge trigger checks against profile stats.
fn check_badge(name: &str, profile: &ProfileRow, global_rank: i64) -> bool {
    match name {
        "first_contribution" => profile.total_contributions >= 1,
        "streak_3" => profile.best_streak >= 3,
        "streak_7" => profile.best_streak >= 7,
        "streak_30" => profile.best_streak >= 30,
        "streak_100" => profile.best_streak >= 100,
        "gold_contributor" => profile.gold_count >= 10,
        "diamond_contributor" => profile.diamond_count >= 1,
        "bounty_hunter" => profile.bounties_fulfilled >= 10,
        "early_adopter" => global_rank > 0 && global_rank <= 1000,
        "affiliate_leader" => profile.referrals >= 50,
        _ => false,
    }
}

/// All known badge names.
const ALL_BADGES: &[&str] = &[
    "first_contribution",
    "streak_3",
    "streak_7",
    "streak_30",
    "streak_100",
    "gold_contributor",
    "diamond_contributor",
    "bounty_hunter",
    "early_adopter",
    "affiliate_leader",
];

// ── ContributionManager ─────────────────────────────────────────────────────

/// Orchestrates the full AIKGS contribution lifecycle.
pub struct ContributionManager;

impl ContributionManager {
    /// Process a new knowledge contribution through the full pipeline.
    ///
    /// Steps:
    ///   1. Rate-limit check
    ///   2. Score content
    ///   3. Dedup check (content hash)
    ///   4. Reject if spam or duplicate
    ///   5. Compute novelty, reward, insert to DB
    ///   6. Process affiliate commissions
    ///   7. Update profile (progressive unlocks)
    ///   8. Submit for curation if gold/diamond
    ///   9. Return ContributionResult
    pub async fn process_contribution(
        db: &Db,
        scorer: &Scorer,
        reward_engine: &RewardEngine,
        cfg: &AikgsConfig,
        contributor_address: &str,
        content: &str,
        _metadata: &HashMap<String, String>,
        bounty_id: i64,
    ) -> Result<ContributionResult, AikgsError> {
        let now_ts = now_f64();

        // 1. Rate-limit check
        let daily_count = db.count_daily_submissions(contributor_address).await?;
        if daily_count >= cfg.max_daily_submissions as i64 {
            return Err(AikgsError::RateLimitExceeded(
                daily_count,
                cfg.max_daily_submissions,
            ));
        }

        // 2. Score content (local quality + gaming detection)
        let score = scorer.score(content);

        // 3. Reject spam
        if score.is_spam {
            let contribution_id = db.next_contribution_id().await?;
            let block_height = 0_i64; // Rejected contributions don't need block height

            db.insert_contribution(
                contribution_id,
                contributor_address,
                &score.content_hash,
                None,
                0.0,
                0.0,
                0.0,
                "bronze",
                &score.domain,
                0.0,
                "rejected_spam",
                block_height,
            )
            .await?;

            return Ok(ContributionResult {
                contribution_id,
                contributor_address: contributor_address.to_string(),
                content_hash: score.content_hash,
                knowledge_node_id: 0,
                quality_score: 0.0,
                novelty_score: 0.0,
                combined_score: 0.0,
                tier: "bronze".into(),
                domain: score.domain,
                reward_amount: 0.0,
                affiliate_l1_amount: 0.0,
                affiliate_l2_amount: 0.0,
                is_bounty_fulfillment: false,
                bounty_id: 0,
                badges_earned: vec![],
                block_height,
                timestamp: now_ts,
                status: "rejected_spam".into(),
            });
        }

        // 4. Dedup check
        let is_duplicate = db.content_hash_exists(&score.content_hash).await?;
        if is_duplicate {
            let contribution_id = db.next_contribution_id().await?;

            db.insert_contribution(
                contribution_id,
                contributor_address,
                &score.content_hash,
                None,
                score.quality_score,
                0.0,
                0.0,
                "bronze",
                &score.domain,
                0.0,
                "rejected_duplicate",
                0,
            )
            .await?;

            return Ok(ContributionResult {
                contribution_id,
                contributor_address: contributor_address.to_string(),
                content_hash: score.content_hash,
                knowledge_node_id: 0,
                quality_score: score.quality_score,
                novelty_score: 0.0,
                combined_score: 0.0,
                tier: "bronze".into(),
                domain: score.domain,
                reward_amount: 0.0,
                affiliate_l1_amount: 0.0,
                affiliate_l2_amount: 0.0,
                is_bounty_fulfillment: false,
                bounty_id: 0,
                badges_earned: vec![],
                block_height: 0,
                timestamp: now_ts,
                status: "rejected_duplicate".into(),
            });
        }

        // 5. Calculate novelty (0.9 for novel content, since hash doesn't exist)
        let novelty = 0.9;
        let score = scorer.with_novelty(score, novelty);

        // 6. Calculate reward
        let (streak_days, _best_streak) = db.get_streak(contributor_address).await?;
        let pool_balance = reward_engine.pool_balance(db).await;
        let total_contributions = db.next_contribution_id().await? - 1;
        let staked_amount = 0.0; // Staking not yet wired to sidecar

        let reward_calc = reward_engine.calculate(
            score.quality_score,
            score.novelty_score,
            &score.tier,
            streak_days,
            staked_amount,
            total_contributions,
            pool_balance,
        );

        let mut reward_amount = reward_calc.final_reward;

        // 7. Handle bounty fulfillment (adds bounty reward on top)
        let mut is_bounty_fulfillment = false;
        if bounty_id > 0 {
            if let Ok(Some(bounty)) = db.get_bounty(bounty_id).await {
                if bounty.status == "claimed" && bounty.claimer_address == contributor_address {
                    let contribution_id = db.next_contribution_id().await?;
                    if db.fulfill_bounty(bounty_id, contribution_id).await? {
                        reward_amount += bounty.reward_amount * bounty.boost_multiplier;
                        is_bounty_fulfillment = true;
                    }
                }
            }
        }

        // 8. Allocate contribution_id and insert
        let contribution_id = db.next_contribution_id().await?;
        let block_height = 0_i64; // Will be set by the node when included in a block

        db.insert_contribution(
            contribution_id,
            contributor_address,
            &score.content_hash,
            None, // knowledge_node_id — set when KG integration is wired
            score.quality_score,
            score.novelty_score,
            score.combined_score,
            &score.tier,
            &score.domain,
            reward_amount,
            "accepted",
            block_height,
        )
        .await?;

        // 9. Insert reward record
        db.insert_reward(
            contribution_id,
            contributor_address,
            reward_calc.final_reward,
            reward_calc.base_reward,
            reward_calc.quality_factor,
            reward_calc.novelty_factor,
            reward_calc.tier_multiplier,
            reward_calc.streak_multiplier,
            reward_calc.staking_boost,
            reward_calc.early_bonus,
            block_height,
        )
        .await?;

        // 10. Process affiliate commissions
        let (l1_amount, l2_amount) = AffiliateManager::process_commissions(
            db,
            contributor_address,
            reward_amount,
            contribution_id,
            cfg,
        )
        .await?;

        // 11. Update profile (progressive unlocks)
        let badges_earned = Self::update_profile(
            db,
            contributor_address,
            score.combined_score,
            &score.tier,
            is_bounty_fulfillment,
            total_contributions + 1,
        )
        .await?;

        // 12. Submit gold/diamond for curation
        if score.tier == "gold" || score.tier == "diamond" {
            let required_votes = if score.tier == "diamond" { 5 } else { 3 };
            let _ = db
                .insert_curation_round(contribution_id, required_votes)
                .await;
        }

        log::info!(
            "Contribution processed: id={} tier={} quality={:.2} novelty={:.2} reward={:.4} QBC",
            contribution_id,
            score.tier,
            score.quality_score,
            score.novelty_score,
            reward_amount,
        );

        Ok(ContributionResult {
            contribution_id,
            contributor_address: contributor_address.to_string(),
            content_hash: score.content_hash,
            knowledge_node_id: 0,
            quality_score: score.quality_score,
            novelty_score: score.novelty_score,
            combined_score: score.combined_score,
            tier: score.tier,
            domain: score.domain,
            reward_amount,
            affiliate_l1_amount: l1_amount,
            affiliate_l2_amount: l2_amount,
            is_bounty_fulfillment,
            bounty_id: if is_bounty_fulfillment { bounty_id } else { 0 },
            badges_earned,
            block_height,
            timestamp: now_ts,
            status: "accepted".into(),
        })
    }

    /// Get a single contribution by ID.
    pub async fn get_contribution(
        db: &Db,
        contribution_id: i64,
    ) -> Result<Option<ContributionRow>, AikgsError> {
        Ok(db.get_contribution(contribution_id).await?)
    }

    /// Get contribution history for an address.
    pub async fn get_history(
        db: &Db,
        address: &str,
        limit: i32,
    ) -> Result<Vec<ContributionRow>, AikgsError> {
        Ok(db.get_contributions_by_address(address, limit).await?)
    }

    /// Get the most recent contributions across all contributors.
    pub async fn get_recent(
        db: &Db,
        limit: i32,
    ) -> Result<Vec<ContributionRow>, AikgsError> {
        Ok(db.get_recent_contributions(limit).await?)
    }

    /// Get the contribution leaderboard (top contributors by total reward).
    pub async fn get_leaderboard(
        db: &Db,
        limit: i32,
    ) -> Result<Vec<LeaderboardRow>, AikgsError> {
        Ok(db.get_contribution_leaderboard(limit).await?)
    }

    /// Get aggregate contribution statistics.
    pub async fn get_stats(db: &Db) -> Result<ContributionStatsRow, AikgsError> {
        Ok(db.get_contribution_stats().await?)
    }

    // ── Progressive Unlock Helpers ──────────────────────────────────────────

    /// Update a contributor's profile after a contribution:
    ///   - Increment counts (total, gold, diamond, bounties)
    ///   - Award reputation points
    ///   - Update streak
    ///   - Recalculate level and features
    ///   - Check for new badges
    ///   - Persist to DB
    ///
    /// Returns newly earned badge names.
    async fn update_profile(
        db: &Db,
        address: &str,
        combined_score: f64,
        tier: &str,
        is_bounty: bool,
        global_rank: i64,
    ) -> Result<Vec<String>, AikgsError> {
        // Fetch or create profile
        let mut profile = db
            .get_profile(address)
            .await?
            .unwrap_or_else(|| new_profile(address));

        // Increment stats
        profile.total_contributions += 1;
        match tier {
            "gold" => profile.gold_count += 1,
            "diamond" => profile.diamond_count += 1,
            _ => {}
        }
        if is_bounty {
            profile.bounties_fulfilled += 1;
            profile.reputation_points += RP_BOUNTY_FULFILLMENT;
        }

        // Award reputation points: combined_score * BASE * tier_mult
        let tier_mult = tier_rp_multiplier(tier);
        let rp_earned = combined_score * RP_CONTRIBUTION_BASE * tier_mult;
        profile.reputation_points += rp_earned;

        // Update streak
        let now_secs = now_f64();
        let today = (now_secs / 86400.0) as i64;
        let last_day = if let Some(last_ts) = profile.last_contribution_at {
            (last_ts.timestamp() as f64 / 86400.0) as i64
        } else {
            0
        };

        profile.last_contribution_at = Some(
            chrono::DateTime::from_timestamp(now_secs as i64, 0)
                .unwrap_or_else(|| chrono::Utc::now().naive_utc().and_utc())
                .with_timezone(&chrono::Utc),
        );

        if last_day > 0 && today == last_day + 1 {
            profile.current_streak += 1;
        } else if last_day == 0 || today > last_day + 1 {
            profile.current_streak = 1;
        }
        // Same day: no streak change

        if profile.current_streak > profile.best_streak {
            profile.best_streak = profile.current_streak;
            // Streak milestone RP bonus
            for &(milestone, rp) in STREAK_RP_MILESTONES {
                if profile.best_streak == milestone {
                    profile.reputation_points += rp;
                }
            }
        }

        // Recalculate level
        let (new_level, new_name, features) = compute_level(profile.reputation_points);
        profile.level = new_level;
        profile.level_name = new_name.to_string();
        profile.unlocked_features = serde_json::to_value(&features).unwrap_or_default();

        // Check for new badges
        let existing_badges: Vec<String> = serde_json::from_value(profile.badges.clone())
            .unwrap_or_default();
        let mut new_badges: Vec<String> = Vec::new();
        let mut all_badges = existing_badges.clone();

        for &badge_name in ALL_BADGES {
            if !existing_badges.contains(&badge_name.to_string())
                && check_badge(badge_name, &profile, global_rank)
            {
                new_badges.push(badge_name.to_string());
                all_badges.push(badge_name.to_string());
            }
        }
        profile.badges = serde_json::to_value(&all_badges).unwrap_or_default();

        // Persist
        db.upsert_profile(&profile).await?;

        if !new_badges.is_empty() {
            log::info!(
                "Badges earned by {}...: {:?}",
                &address[..address.len().min(8)],
                new_badges
            );
        }

        Ok(new_badges)
    }
}

/// Create a fresh profile for a new contributor.
fn new_profile(address: &str) -> ProfileRow {
    ProfileRow {
        address: address.to_string(),
        reputation_points: 0.0,
        level: 1,
        level_name: "Novice".into(),
        total_contributions: 0,
        best_streak: 0,
        current_streak: 0,
        gold_count: 0,
        diamond_count: 0,
        bounties_fulfilled: 0,
        referrals: 0,
        badges: serde_json::json!([]),
        unlocked_features: serde_json::json!(["basic_chat", "contribute"]),
        last_contribution_at: None,
    }
}

/// Compute level, name, and cumulative features for a given RP total.
fn compute_level(rp: f64) -> (i32, &'static str, Vec<&'static str>) {
    let mut level = 1;
    let mut name = "Novice";
    let mut features: Vec<&str> = Vec::new();

    for &(min_rp, lvl, lvl_name, lvl_features) in LEVELS {
        if rp >= min_rp {
            level = lvl;
            name = lvl_name;
            features.extend_from_slice(lvl_features);
        }
    }

    (level, name, features)
}

/// Current wall-clock time as seconds since UNIX epoch.
fn now_f64() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_level_novice() {
        let (level, name, features) = compute_level(0.0);
        assert_eq!(level, 1);
        assert_eq!(name, "Novice");
        assert!(features.contains(&"basic_chat"));
        assert!(features.contains(&"contribute"));
    }

    #[test]
    fn test_compute_level_scholar() {
        let (level, name, features) = compute_level(500.0);
        assert_eq!(level, 3);
        assert_eq!(name, "Scholar");
        assert!(features.contains(&"priority_queue"));
        assert!(features.contains(&"basic_chat"));
    }

    #[test]
    fn test_compute_level_enlightened() {
        let (level, name, features) = compute_level(30000.0);
        assert_eq!(level, 8);
        assert_eq!(name, "Enlightened");
        assert!(features.contains(&"elite_badge"));
        assert!(features.contains(&"early_access"));
        assert!(features.contains(&"governance_voting"));
    }

    #[test]
    fn test_tier_rp_multiplier() {
        assert!((tier_rp_multiplier("bronze") - 0.5).abs() < f64::EPSILON);
        assert!((tier_rp_multiplier("diamond") - 5.0).abs() < f64::EPSILON);
        assert!((tier_rp_multiplier("unknown") - 1.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_new_profile_defaults() {
        let p = new_profile("qbc1test");
        assert_eq!(p.level, 1);
        assert_eq!(p.level_name, "Novice");
        assert_eq!(p.total_contributions, 0);
        assert_eq!(p.reputation_points, 0.0);
    }

    #[test]
    fn test_check_badge_first_contribution() {
        let mut p = new_profile("qbc1test");
        assert!(!check_badge("first_contribution", &p, 1));
        p.total_contributions = 1;
        assert!(check_badge("first_contribution", &p, 1));
    }

    #[test]
    fn test_check_badge_early_adopter() {
        let p = new_profile("qbc1test");
        assert!(check_badge("early_adopter", &p, 500));
        assert!(!check_badge("early_adopter", &p, 1001));
        assert!(!check_badge("early_adopter", &p, 0));
    }
}
