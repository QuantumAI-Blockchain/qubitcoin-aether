//! Bounty Manager — Create, claim, and fulfill knowledge bounties.
//!
//! Bounties are knowledge gaps identified by the system or community. Users
//! create bounties with QBC rewards, contributors claim and fulfill them, and
//! the reward (multiplied by `boost_multiplier`) is disbursed on fulfillment.

use chrono::{Duration, Utc};

use crate::db::{BountyRow, BountyStatsRow, Db};

// ════════════════════════════════════════════════════════════════════════════
// Error
// ════════════════════════════════════════════════════════════════════════════

#[derive(Debug, thiserror::Error)]
pub enum BountyError {
    #[error("database error: {0}")]
    Db(#[from] sqlx::Error),
    #[error("bounty not found: {0}")]
    NotFound(i64),
    #[error("bounty {0} is not in expected status (expected={1}, actual={2})")]
    InvalidStatus(i64, String, String),
    #[error("claim failed: bounty {0} is expired or already claimed")]
    ClaimFailed(i64),
}

// ════════════════════════════════════════════════════════════════════════════
// BountyInfo — matches proto BountyInfo fields exactly
// ════════════════════════════════════════════════════════════════════════════

#[derive(Debug, Clone)]
pub struct BountyInfo {
    pub bounty_id: i64,
    pub domain: String,
    pub description: String,
    pub gap_hash: String,
    pub reward_amount: f64,
    pub boost_multiplier: f64,
    pub status: String,
    pub claimer_address: String,
    pub contribution_id: i64,
    pub created_at: f64,
    pub expires_at: f64,
}

impl From<BountyRow> for BountyInfo {
    fn from(row: BountyRow) -> Self {
        Self {
            bounty_id: row.bounty_id,
            domain: row.domain,
            description: row.description,
            gap_hash: row.gap_hash,
            reward_amount: row.reward_amount,
            boost_multiplier: row.boost_multiplier,
            status: row.status,
            claimer_address: row.claimer_address,
            contribution_id: row.contribution_id,
            created_at: row.created_at_epoch,
            expires_at: row.expires_at_epoch,
        }
    }
}

// ════════════════════════════════════════════════════════════════════════════
// BountyStats — mirrors proto BountyStats
// ════════════════════════════════════════════════════════════════════════════

#[derive(Debug, Clone)]
pub struct BountyStats {
    pub total_bounties: i64,
    pub open_bounties: i64,
    pub fulfilled_bounties: i64,
    pub total_reward_pool: f64,
}

impl From<BountyStatsRow> for BountyStats {
    fn from(row: BountyStatsRow) -> Self {
        Self {
            total_bounties: row.total,
            open_bounties: row.open,
            fulfilled_bounties: row.fulfilled,
            total_reward_pool: row.open_reward,
        }
    }
}

// ════════════════════════════════════════════════════════════════════════════
// BountyManager
// ════════════════════════════════════════════════════════════════════════════

pub struct BountyManager;

impl BountyManager {
    /// Create a new bounty targeting a knowledge gap.
    ///
    /// Assigns the next sequential bounty_id, calculates the expiration
    /// timestamp, inserts into DB, and returns the created bounty.
    /// Create a new bounty targeting a knowledge gap.
    ///
    /// Uses atomic ID generation via `INSERT ... RETURNING bounty_id`.
    pub async fn create_bounty(
        db: &Db,
        domain: &str,
        description: &str,
        gap_hash: &str,
        reward_amount: f64,
        duration_secs: i64,
        boost_multiplier: f64,
    ) -> Result<BountyInfo, BountyError> {
        let expires_at = Utc::now() + Duration::seconds(duration_secs);
        let expires_at_epoch = expires_at.timestamp() as f64;

        // Atomic insert with DB-generated bounty_id
        let bounty_id = db
            .insert_bounty_returning_id(
                domain,
                description,
                gap_hash,
                reward_amount,
                boost_multiplier,
                expires_at_epoch,
            )
            .await?;

        log::info!(
            "Created bounty {} in domain={} reward={} boost={} expires={}s",
            bounty_id,
            domain,
            reward_amount,
            boost_multiplier,
            duration_secs,
        );

        Ok(BountyInfo {
            bounty_id,
            domain: domain.to_string(),
            description: description.to_string(),
            gap_hash: gap_hash.to_string(),
            reward_amount,
            boost_multiplier,
            status: "open".to_string(),
            claimer_address: String::new(),
            contribution_id: 0,
            created_at: Utc::now().timestamp() as f64,
            expires_at: expires_at_epoch,
        })
    }

    /// List bounties filtered by domain and/or status.
    ///
    /// Pass empty strings for `domain` or `status` to skip those filters.
    pub async fn list_bounties(
        db: &Db,
        domain: &str,
        status: &str,
        limit: i32,
    ) -> Result<Vec<BountyInfo>, BountyError> {
        let rows = db.list_bounties(domain, status, limit).await?;
        Ok(rows.into_iter().map(BountyInfo::from).collect())
    }

    /// Claim an open bounty. The bounty must be open and not expired.
    ///
    /// On success, the bounty status transitions from "open" to "claimed"
    /// and `claimer_address` is recorded.
    pub async fn claim_bounty(
        db: &Db,
        bounty_id: i64,
        claimer_address: &str,
    ) -> Result<BountyInfo, BountyError> {
        let claimed = db.claim_bounty(bounty_id, claimer_address).await?;
        if !claimed {
            return Err(BountyError::ClaimFailed(bounty_id));
        }

        log::info!(
            "Bounty {} claimed by {}",
            bounty_id,
            claimer_address,
        );

        // Fetch the updated bounty to return current state.
        let row = db
            .get_bounty(bounty_id)
            .await?
            .ok_or(BountyError::NotFound(bounty_id))?;
        Ok(BountyInfo::from(row))
    }

    /// Fulfill a claimed bounty with a contribution.
    ///
    /// Uses atomic `UPDATE ... WHERE status = 'claimed' RETURNING *` to prevent
    /// double-fulfill race condition. If the bounty is not in "claimed" status,
    /// the update affects zero rows and we return an error.
    pub async fn fulfill_bounty(
        db: &Db,
        bounty_id: i64,
        contribution_id: i64,
        _contributor_address: &str,
    ) -> Result<f64, BountyError> {
        // Atomic check-and-update: only fulfills if status is still 'claimed'.
        // This prevents double-fulfill even under concurrent requests.
        let fulfilled = db.fulfill_bounty(bounty_id, contribution_id).await?;
        if !fulfilled {
            // Either the bounty doesn't exist or isn't in 'claimed' status.
            let bounty = db.get_bounty(bounty_id).await?;
            match bounty {
                None => return Err(BountyError::NotFound(bounty_id)),
                Some(b) => {
                    return Err(BountyError::InvalidStatus(
                        bounty_id,
                        "claimed".to_string(),
                        b.status,
                    ))
                }
            }
        }

        // Fetch the now-fulfilled bounty to compute the effective reward.
        let bounty = db
            .get_bounty(bounty_id)
            .await?
            .ok_or(BountyError::NotFound(bounty_id))?;

        let effective_reward = bounty.reward_amount * bounty.boost_multiplier;

        log::info!(
            "Bounty {} fulfilled via contribution {} — reward={:.8} ({}x{} boost)",
            bounty_id,
            contribution_id,
            effective_reward,
            bounty.reward_amount,
            bounty.boost_multiplier,
        );

        Ok(effective_reward)
    }

    /// Aggregate bounty statistics.
    pub async fn get_stats(db: &Db) -> Result<BountyStats, BountyError> {
        let row = db.get_bounty_stats().await?;
        Ok(BountyStats::from(row))
    }
}
