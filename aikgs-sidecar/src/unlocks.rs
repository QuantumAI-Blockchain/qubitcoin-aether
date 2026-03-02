//! Progressive Unlocks / Reputation System
//!
//! Contributors earn Reputation Points (RP) from accepted contributions.
//! RP determines their level, which unlocks features and badges.
//!
//! 8 levels (Novice → Enlightened), 7 badge triggers, streak milestones.
//! All state persists in `aikgs_profiles` via the DB layer.

use chrono::Utc;
use serde_json::Value as JsonValue;

use crate::db::{Db, ProfileRow};

// ════════════════════════════════════════════════════════════════════════════
// Error
// ════════════════════════════════════════════════════════════════════════════

#[derive(Debug, thiserror::Error)]
pub enum UnlocksError {
    #[error("database error: {0}")]
    Db(#[from] sqlx::Error),
    #[error("profile not found: {0}")]
    NotFound(String),
}

// ════════════════════════════════════════════════════════════════════════════
// Level definitions
// ════════════════════════════════════════════════════════════════════════════

struct LevelDef {
    level: i32,
    name: &'static str,
    min_rp: f64,
    features: &'static [&'static str],
}

const LEVELS: &[LevelDef] = &[
    LevelDef {
        level: 1,
        name: "Novice",
        min_rp: 0.0,
        features: &["basic_chat", "contribute"],
    },
    LevelDef {
        level: 2,
        name: "Learner",
        min_rp: 100.0,
        features: &["custom_theme", "profile_badge"],
    },
    LevelDef {
        level: 3,
        name: "Scholar",
        min_rp: 500.0,
        features: &["priority_queue"],
    },
    LevelDef {
        level: 4,
        name: "Curator",
        min_rp: 1_000.0,
        features: &["curation_voting"],
    },
    LevelDef {
        level: 5,
        name: "Sage",
        min_rp: 2_500.0,
        features: &["governance_voting"],
    },
    LevelDef {
        level: 6,
        name: "Master",
        min_rp: 5_000.0,
        features: &["create_bounties"],
    },
    LevelDef {
        level: 7,
        name: "Archon",
        min_rp: 10_000.0,
        features: &["custom_llm_config"],
    },
    LevelDef {
        level: 8,
        name: "Enlightened",
        min_rp: 25_000.0,
        features: &["elite_badge", "early_access"],
    },
];

// ════════════════════════════════════════════════════════════════════════════
// Tier → RP multiplier
// ════════════════════════════════════════════════════════════════════════════

fn tier_multiplier(tier: &str) -> f64 {
    match tier {
        "bronze" => 0.5,
        "silver" => 1.0,
        "gold" => 2.0,
        "diamond" => 5.0,
        _ => 1.0,
    }
}

// ════════════════════════════════════════════════════════════════════════════
// Streak RP milestones: (days, bonus_rp)
// ════════════════════════════════════════════════════════════════════════════

const STREAK_RP_MILESTONES: &[(i32, f64)] = &[
    (3, 10.0),
    (7, 25.0),
    (30, 50.0),
    (100, 100.0),
];

// ════════════════════════════════════════════════════════════════════════════
// Badge definitions
// ════════════════════════════════════════════════════════════════════════════

struct BadgeDef {
    name: &'static str,
    check: fn(&ProfileRow) -> bool,
}

const BADGES: &[BadgeDef] = &[
    BadgeDef {
        name: "first_contribution",
        check: |p| p.total_contributions >= 1,
    },
    BadgeDef {
        name: "streak_3",
        check: |p| p.best_streak >= 3,
    },
    BadgeDef {
        name: "streak_7",
        check: |p| p.best_streak >= 7,
    },
    BadgeDef {
        name: "streak_30",
        check: |p| p.best_streak >= 30,
    },
    BadgeDef {
        name: "streak_100",
        check: |p| p.best_streak >= 100,
    },
    BadgeDef {
        name: "gold_contributor",
        check: |p| p.gold_count >= 10,
    },
    BadgeDef {
        name: "diamond_contributor",
        check: |p| p.diamond_count >= 1,
    },
    BadgeDef {
        name: "bounty_hunter",
        check: |p| p.bounties_fulfilled >= 10,
    },
];

// ════════════════════════════════════════════════════════════════════════════
// Helper: resolve level from RP
// ════════════════════════════════════════════════════════════════════════════

fn level_for_rp(rp: f64) -> (i32, &'static str) {
    // Walk levels in reverse to find the highest qualifying one.
    for def in LEVELS.iter().rev() {
        if rp >= def.min_rp {
            return (def.level, def.name);
        }
    }
    (1, "Novice")
}

/// Collect all features unlocked up to (and including) the given level.
fn features_for_level(level: i32) -> Vec<String> {
    LEVELS
        .iter()
        .filter(|d| d.level <= level)
        .flat_map(|d| d.features.iter().map(|f| (*f).to_string()))
        .collect()
}

/// Build a default profile for a new contributor.
fn default_profile(address: &str) -> ProfileRow {
    ProfileRow {
        address: address.to_string(),
        reputation_points: 0.0,
        level: 1,
        level_name: "Novice".to_string(),
        total_contributions: 0,
        best_streak: 0,
        current_streak: 0,
        gold_count: 0,
        diamond_count: 0,
        bounties_fulfilled: 0,
        referrals: 0,
        badges: JsonValue::Array(vec![]),
        unlocked_features: serde_json::to_value(features_for_level(1)).unwrap_or(JsonValue::Array(vec![])),
        last_contribution_at: None,
    }
}

// ════════════════════════════════════════════════════════════════════════════
// UnlocksManager
// ════════════════════════════════════════════════════════════════════════════

pub struct UnlocksManager;

impl UnlocksManager {
    /// Record a contribution and update the contributor's profile.
    ///
    /// Returns a list of newly earned badge names (may be empty).
    pub async fn record_contribution(
        db: &Db,
        address: &str,
        combined_score: f64,
        tier: &str,
    ) -> Result<Vec<String>, UnlocksError> {
        // Load existing profile or create a default.
        let mut profile = db
            .get_profile(address)
            .await?
            .unwrap_or_else(|| default_profile(address));

        // ── Update contribution stats ──
        profile.total_contributions += 1;
        if tier == "gold" {
            profile.gold_count += 1;
        }
        if tier == "diamond" {
            profile.diamond_count += 1;
        }

        // ── Award RP = combined_score * 10.0 * tier_multiplier ──
        let rp_earned = combined_score * 10.0 * tier_multiplier(tier);
        profile.reputation_points += rp_earned;

        // ── Update streak ──
        let today = Utc::now().date_naive();
        let mut streak_rp_bonus = 0.0;

        match profile.last_contribution_at {
            Some(last_dt) => {
                let last_date = last_dt.date_naive();
                let diff = (today - last_date).num_days();

                if diff == 1 {
                    // Consecutive day — extend streak.
                    profile.current_streak += 1;
                } else if diff == 0 {
                    // Same day — streak unchanged (no break, no extension).
                } else {
                    // Streak broken — reset.
                    profile.current_streak = 1;
                }
            }
            None => {
                // First ever contribution.
                profile.current_streak = 1;
            }
        }

        if profile.current_streak > profile.best_streak {
            profile.best_streak = profile.current_streak;
        }

        // Check if current streak just hit a milestone.
        for &(days, bonus) in STREAK_RP_MILESTONES {
            if profile.current_streak == days {
                streak_rp_bonus = bonus;
                break;
            }
        }
        profile.reputation_points += streak_rp_bonus;

        // ── Update level ──
        let (new_level, new_name) = level_for_rp(profile.reputation_points);
        let level_changed = new_level != profile.level;
        profile.level = new_level;
        profile.level_name = new_name.to_string();

        // ── Update unlocked features ──
        let features = features_for_level(profile.level);
        profile.unlocked_features =
            serde_json::to_value(&features).unwrap_or(JsonValue::Array(vec![]));

        // ── Check badges ──
        let existing_badges: Vec<String> = match &profile.badges {
            JsonValue::Array(arr) => arr
                .iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect(),
            _ => Vec::new(),
        };

        let mut new_badges: Vec<String> = Vec::new();
        let mut all_badges = existing_badges.clone();

        for badge_def in BADGES {
            if !existing_badges.contains(&badge_def.name.to_string()) && (badge_def.check)(&profile)
            {
                new_badges.push(badge_def.name.to_string());
                all_badges.push(badge_def.name.to_string());
            }
        }

        profile.badges = serde_json::to_value(&all_badges).unwrap_or(JsonValue::Array(vec![]));

        // ── Update timestamp ──
        profile.last_contribution_at = Some(Utc::now());

        // ── Persist ──
        db.upsert_profile(&profile).await?;

        if level_changed {
            log::info!(
                "Profile {} leveled up to {} ({}) — RP={:.1}",
                address,
                profile.level,
                profile.level_name,
                profile.reputation_points,
            );
        }
        if !new_badges.is_empty() {
            log::info!(
                "Profile {} earned badges: {:?}",
                address,
                new_badges,
            );
        }

        Ok(new_badges)
    }

    /// Get a contributor's profile. Returns `None` if not found.
    pub async fn get_profile(
        db: &Db,
        address: &str,
    ) -> Result<Option<ProfileRow>, UnlocksError> {
        Ok(db.get_profile(address).await?)
    }

    /// Check whether a contributor has unlocked a specific feature.
    pub async fn has_feature(
        db: &Db,
        address: &str,
        feature: &str,
    ) -> Result<bool, UnlocksError> {
        let profile = match db.get_profile(address).await? {
            Some(p) => p,
            None => {
                // Unregistered users get level-1 features.
                let defaults = features_for_level(1);
                return Ok(defaults.iter().any(|f| f == feature));
            }
        };

        let unlocked = match &profile.unlocked_features {
            JsonValue::Array(arr) => arr.iter().any(|v| v.as_str() == Some(feature)),
            _ => false,
        };
        Ok(unlocked)
    }

    /// Reputation leaderboard ordered by RP descending.
    pub async fn get_leaderboard(
        db: &Db,
        limit: i32,
    ) -> Result<Vec<ProfileRow>, UnlocksError> {
        Ok(db.get_profiles_leaderboard(limit).await?)
    }

    /// Aggregate unlock/profile statistics.
    pub async fn get_stats(db: &Db) -> Result<UnlocksStats, UnlocksError> {
        let row = db.get_unlocks_stats().await?;
        Ok(UnlocksStats {
            total_profiles: row.total_profiles,
            global_contributions: row.global_contributions,
            level_distribution: row.level_distribution,
            total_badges_awarded: row.total_badges_awarded,
        })
    }
}

// ════════════════════════════════════════════════════════════════════════════
// Stats type
// ════════════════════════════════════════════════════════════════════════════

#[derive(Debug, Clone)]
pub struct UnlocksStats {
    pub total_profiles: i64,
    pub global_contributions: i64,
    pub level_distribution: std::collections::HashMap<String, i64>,
    pub total_badges_awarded: i64,
}
