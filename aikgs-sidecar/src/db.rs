//! Database layer — CockroachDB persistence for all 10 AIKGS tables.

use chrono::{DateTime, Utc};
use serde_json::Value as JsonValue;
use sqlx::postgres::PgPoolOptions;
use sqlx::{PgPool, Row};

use crate::config::AikgsConfig;

/// Shared database handle.
#[derive(Clone)]
pub struct Db {
    pool: PgPool,
}

impl Db {
    /// Connect to CockroachDB and return a handle.
    pub async fn connect(cfg: &AikgsConfig) -> Result<Self, sqlx::Error> {
        let pool = PgPoolOptions::new()
            .max_connections(20)
            .connect(&cfg.database_url)
            .await?;
        log::info!("Connected to CockroachDB");
        Ok(Self { pool })
    }

    // ════════════════════════════════════════════════════════════════════════
    // Contributions
    // ════════════════════════════════════════════════════════════════════════

    pub async fn insert_contribution(
        &self,
        contribution_id: i64,
        contributor_address: &str,
        content_hash: &str,
        knowledge_node_id: Option<i64>,
        quality_score: f64,
        novelty_score: f64,
        combined_score: f64,
        tier: &str,
        domain: &str,
        reward_amount: f64,
        status: &str,
        block_height: i64,
    ) -> Result<(), sqlx::Error> {
        sqlx::query(
            "INSERT INTO aikgs_contributions
             (contribution_id, contributor_address, content_hash, knowledge_node_id,
              quality_score, novelty_score, combined_score, tier, domain,
              reward_amount, status, block_height)
             VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
             ON CONFLICT (contribution_id) DO NOTHING",
        )
        .bind(contribution_id)
        .bind(contributor_address)
        .bind(content_hash)
        .bind(knowledge_node_id)
        .bind(quality_score)
        .bind(novelty_score)
        .bind(combined_score)
        .bind(tier)
        .bind(domain)
        .bind(reward_amount)
        .bind(status)
        .bind(block_height)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    pub async fn get_contribution(
        &self,
        contribution_id: i64,
    ) -> Result<Option<ContributionRow>, sqlx::Error> {
        let row = sqlx::query_as::<_, ContributionRow>(
            "SELECT contribution_id, contributor_address, content_hash, knowledge_node_id,
                    quality_score, novelty_score, combined_score, tier, domain,
                    reward_amount, status, block_height, created_at
             FROM aikgs_contributions WHERE contribution_id = $1",
        )
        .bind(contribution_id)
        .fetch_optional(&self.pool)
        .await?;
        Ok(row)
    }

    pub async fn get_contributions_by_address(
        &self,
        address: &str,
        limit: i32,
    ) -> Result<Vec<ContributionRow>, sqlx::Error> {
        sqlx::query_as::<_, ContributionRow>(
            "SELECT contribution_id, contributor_address, content_hash, knowledge_node_id,
                    quality_score, novelty_score, combined_score, tier, domain,
                    reward_amount, status, block_height, created_at
             FROM aikgs_contributions WHERE contributor_address = $1
             ORDER BY contribution_id DESC LIMIT $2",
        )
        .bind(address)
        .bind(limit)
        .fetch_all(&self.pool)
        .await
    }

    pub async fn get_recent_contributions(
        &self,
        limit: i32,
    ) -> Result<Vec<ContributionRow>, sqlx::Error> {
        sqlx::query_as::<_, ContributionRow>(
            "SELECT contribution_id, contributor_address, content_hash, knowledge_node_id,
                    quality_score, novelty_score, combined_score, tier, domain,
                    reward_amount, status, block_height, created_at
             FROM aikgs_contributions ORDER BY contribution_id DESC LIMIT $1",
        )
        .bind(limit)
        .fetch_all(&self.pool)
        .await
    }

    pub async fn get_contribution_stats(&self) -> Result<ContributionStatsRow, sqlx::Error> {
        let row = sqlx::query(
            "SELECT COUNT(*) as total,
                    COUNT(DISTINCT contributor_address) as unique_contributors,
                    COALESCE(SUM(reward_amount), 0) as total_rewards,
                    COUNT(*) FILTER (WHERE status = 'accepted' AND tier = 'bronze') as bronze,
                    COUNT(*) FILTER (WHERE status = 'accepted' AND tier = 'silver') as silver,
                    COUNT(*) FILTER (WHERE status = 'accepted' AND tier = 'gold') as gold_count,
                    COUNT(*) FILTER (WHERE status = 'accepted' AND tier = 'diamond') as diamond,
                    COUNT(*) FILTER (WHERE status = 'accepted' AND is_bounty_fulfillment = true) as bounty_fulfillments
             FROM aikgs_contributions",
        )
        .fetch_one(&self.pool)
        .await?;
        Ok(ContributionStatsRow {
            total: row.try_get::<i64, _>("total").unwrap_or(0),
            unique_contributors: row.try_get::<i64, _>("unique_contributors").unwrap_or(0),
            total_rewards: row
                .try_get::<sqlx::types::BigDecimal, _>("total_rewards")
                .map(|v| bigdecimal_to_f64(&v))
                .unwrap_or(0.0),
            bronze: row.try_get::<i64, _>("bronze").unwrap_or(0),
            silver: row.try_get::<i64, _>("silver").unwrap_or(0),
            gold: row.try_get::<i64, _>("gold_count").unwrap_or(0),
            diamond: row.try_get::<i64, _>("diamond").unwrap_or(0),
            bounty_fulfillments: row.try_get::<i64, _>("bounty_fulfillments").unwrap_or(0),
        })
    }

    pub async fn get_contribution_leaderboard(
        &self,
        limit: i32,
    ) -> Result<Vec<LeaderboardRow>, sqlx::Error> {
        sqlx::query_as::<_, LeaderboardRow>(
            "SELECT contributor_address as address,
                    COALESCE(SUM(reward_amount), 0)::float8 as total_reward,
                    COUNT(*)::int4 as contribution_count,
                    COALESCE(AVG(quality_score), 0) as avg_quality,
                    MAX(tier) as best_tier
             FROM aikgs_contributions
             WHERE status = 'accepted'
             GROUP BY contributor_address
             ORDER BY total_reward DESC
             LIMIT $1",
        )
        .bind(limit)
        .fetch_all(&self.pool)
        .await
    }

    /// Check if an exact content hash already exists.
    pub async fn content_hash_exists(&self, content_hash: &str) -> Result<bool, sqlx::Error> {
        let row = sqlx::query("SELECT 1 FROM aikgs_contributions WHERE content_hash = $1 LIMIT 1")
            .bind(content_hash)
            .fetch_optional(&self.pool)
            .await?;
        Ok(row.is_some())
    }

    /// Count submissions today for rate limiting.
    pub async fn count_daily_submissions(&self, address: &str) -> Result<i64, sqlx::Error> {
        let row = sqlx::query(
            "SELECT COUNT(*) as cnt FROM aikgs_contributions
             WHERE contributor_address = $1
             AND created_at >= CURRENT_DATE",
        )
        .bind(address)
        .fetch_one(&self.pool)
        .await?;
        Ok(row.try_get::<i64, _>("cnt").unwrap_or(0))
    }

    /// Get the next contribution_id (max + 1).
    pub async fn next_contribution_id(&self) -> Result<i64, sqlx::Error> {
        let row =
            sqlx::query("SELECT COALESCE(MAX(contribution_id), 0) + 1 as next_id FROM aikgs_contributions")
                .fetch_one(&self.pool)
                .await?;
        Ok(row.try_get::<i64, _>("next_id").unwrap_or(1))
    }

    // ════════════════════════════════════════════════════════════════════════
    // Rewards
    // ════════════════════════════════════════════════════════════════════════

    pub async fn insert_reward(
        &self,
        contribution_id: i64,
        contributor_address: &str,
        amount: f64,
        base_reward: f64,
        quality_factor: f64,
        novelty_factor: f64,
        tier_multiplier: f64,
        streak_multiplier: f64,
        staking_boost: f64,
        early_bonus: f64,
        block_height: i64,
    ) -> Result<(), sqlx::Error> {
        sqlx::query(
            "INSERT INTO aikgs_rewards
             (contribution_id, contributor_address, amount, base_reward,
              quality_factor, novelty_factor, tier_multiplier, streak_multiplier,
              staking_boost, early_bonus, block_height)
             VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",
        )
        .bind(contribution_id)
        .bind(contributor_address)
        .bind(amount)
        .bind(base_reward)
        .bind(quality_factor)
        .bind(novelty_factor)
        .bind(tier_multiplier)
        .bind(streak_multiplier)
        .bind(staking_boost)
        .bind(early_bonus)
        .bind(block_height)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    pub async fn get_total_distributed(&self) -> Result<f64, sqlx::Error> {
        let row = sqlx::query(
            "SELECT COALESCE(SUM(amount), 0)::float8 as total FROM aikgs_rewards",
        )
        .fetch_one(&self.pool)
        .await?;
        Ok(row.try_get::<f64, _>("total").unwrap_or(0.0))
    }

    pub async fn get_reward_distribution_count(&self) -> Result<i64, sqlx::Error> {
        let row = sqlx::query("SELECT COUNT(*) as cnt FROM aikgs_rewards")
            .fetch_one(&self.pool)
            .await?;
        Ok(row.try_get::<i64, _>("cnt").unwrap_or(0))
    }

    // ════════════════════════════════════════════════════════════════════════
    // Affiliates
    // ════════════════════════════════════════════════════════════════════════

    pub async fn upsert_affiliate(
        &self,
        address: &str,
        referrer_address: &str,
        referral_code: &str,
    ) -> Result<(), sqlx::Error> {
        sqlx::query(
            "INSERT INTO aikgs_affiliates (address, referrer_address, referral_code)
             VALUES ($1, $2, $3)
             ON CONFLICT (address) DO NOTHING",
        )
        .bind(address)
        .bind(referrer_address)
        .bind(referral_code)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    pub async fn get_affiliate(&self, address: &str) -> Result<Option<AffiliateRow>, sqlx::Error> {
        sqlx::query_as::<_, AffiliateRow>(
            "SELECT address, referrer_address, referral_code,
                    l1_referrals, l2_referrals,
                    total_l1_commission::float8 as total_l1_commission,
                    total_l2_commission::float8 as total_l2_commission,
                    is_active
             FROM aikgs_affiliates WHERE address = $1",
        )
        .bind(address)
        .fetch_optional(&self.pool)
        .await
    }

    pub async fn get_affiliate_by_code(
        &self,
        code: &str,
    ) -> Result<Option<AffiliateRow>, sqlx::Error> {
        sqlx::query_as::<_, AffiliateRow>(
            "SELECT address, referrer_address, referral_code,
                    l1_referrals, l2_referrals,
                    total_l1_commission::float8 as total_l1_commission,
                    total_l2_commission::float8 as total_l2_commission,
                    is_active
             FROM aikgs_affiliates WHERE referral_code = $1",
        )
        .bind(code)
        .fetch_optional(&self.pool)
        .await
    }

    pub async fn increment_affiliate_commission(
        &self,
        address: &str,
        level: i32,
        amount: f64,
    ) -> Result<(), sqlx::Error> {
        let col = if level == 1 {
            "total_l1_commission"
        } else {
            "total_l2_commission"
        };
        let ref_col = if level == 1 {
            "l1_referrals"
        } else {
            "l2_referrals"
        };
        let query = format!(
            "UPDATE aikgs_affiliates SET {} = {} + $1, {} = {} + 1 WHERE address = $2",
            col, col, ref_col, ref_col
        );
        sqlx::query(&query)
            .bind(amount)
            .bind(address)
            .execute(&self.pool)
            .await?;
        Ok(())
    }

    pub async fn insert_commission(
        &self,
        affiliate_address: &str,
        contributor_address: &str,
        amount: f64,
        level: i16,
        contribution_id: i64,
    ) -> Result<(), sqlx::Error> {
        sqlx::query(
            "INSERT INTO aikgs_commissions
             (affiliate_address, contributor_address, amount, level, contribution_id)
             VALUES ($1,$2,$3,$4,$5)",
        )
        .bind(affiliate_address)
        .bind(contributor_address)
        .bind(amount)
        .bind(level)
        .bind(contribution_id)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    pub async fn get_affiliate_stats(&self) -> Result<AffiliateStatsRow, sqlx::Error> {
        let row = sqlx::query(
            "SELECT COUNT(*) as total,
                    COALESCE(SUM(total_l1_commission), 0)::float8 as l1_total,
                    COALESCE(SUM(total_l2_commission), 0)::float8 as l2_total
             FROM aikgs_affiliates",
        )
        .fetch_one(&self.pool)
        .await?;
        Ok(AffiliateStatsRow {
            total_affiliates: row.try_get::<i64, _>("total").unwrap_or(0),
            total_l1_commissions: row.try_get::<f64, _>("l1_total").unwrap_or(0.0),
            total_l2_commissions: row.try_get::<f64, _>("l2_total").unwrap_or(0.0),
        })
    }

    // ════════════════════════════════════════════════════════════════════════
    // Profiles (Progressive Unlocks)
    // ════════════════════════════════════════════════════════════════════════

    pub async fn upsert_profile(&self, p: &ProfileRow) -> Result<(), sqlx::Error> {
        sqlx::query(
            "INSERT INTO aikgs_profiles
             (address, reputation_points, level, level_name, total_contributions,
              best_streak, current_streak, gold_count, diamond_count,
              bounties_fulfilled, referrals, badges, unlocked_features, last_contribution_at)
             VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
             ON CONFLICT (address) DO UPDATE SET
              reputation_points = $2, level = $3, level_name = $4,
              total_contributions = $5, best_streak = $6, current_streak = $7,
              gold_count = $8, diamond_count = $9, bounties_fulfilled = $10,
              referrals = $11, badges = $12, unlocked_features = $13,
              last_contribution_at = $14, updated_at = now()",
        )
        .bind(&p.address)
        .bind(p.reputation_points)
        .bind(p.level)
        .bind(&p.level_name)
        .bind(p.total_contributions)
        .bind(p.best_streak)
        .bind(p.current_streak)
        .bind(p.gold_count)
        .bind(p.diamond_count)
        .bind(p.bounties_fulfilled)
        .bind(p.referrals)
        .bind(&p.badges)
        .bind(&p.unlocked_features)
        .bind(p.last_contribution_at)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    pub async fn get_profile(&self, address: &str) -> Result<Option<ProfileRow>, sqlx::Error> {
        sqlx::query_as::<_, ProfileRow>(
            "SELECT address, reputation_points, level, level_name, total_contributions,
                    best_streak, current_streak, gold_count, diamond_count,
                    bounties_fulfilled, referrals, badges, unlocked_features,
                    last_contribution_at
             FROM aikgs_profiles WHERE address = $1",
        )
        .bind(address)
        .fetch_optional(&self.pool)
        .await
    }

    pub async fn get_profiles_leaderboard(
        &self,
        limit: i32,
    ) -> Result<Vec<ProfileRow>, sqlx::Error> {
        sqlx::query_as::<_, ProfileRow>(
            "SELECT address, reputation_points, level, level_name, total_contributions,
                    best_streak, current_streak, gold_count, diamond_count,
                    bounties_fulfilled, referrals, badges, unlocked_features,
                    last_contribution_at
             FROM aikgs_profiles
             ORDER BY reputation_points DESC
             LIMIT $1",
        )
        .bind(limit)
        .fetch_all(&self.pool)
        .await
    }

    pub async fn get_unlocks_stats(&self) -> Result<UnlocksStatsRow, sqlx::Error> {
        let total: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM aikgs_profiles")
            .fetch_one(&self.pool)
            .await
            .unwrap_or(0);
        let global_contributions: i64 =
            sqlx::query_scalar("SELECT COALESCE(SUM(total_contributions), 0) FROM aikgs_profiles")
                .fetch_one(&self.pool)
                .await
                .unwrap_or(0);
        let total_badges: i64 = sqlx::query_scalar(
            "SELECT COALESCE(SUM(jsonb_array_length(badges)), 0) FROM aikgs_profiles",
        )
        .fetch_one(&self.pool)
        .await
        .unwrap_or(0);

        let level_rows = sqlx::query("SELECT level, COUNT(*) as cnt FROM aikgs_profiles GROUP BY level")
            .fetch_all(&self.pool)
            .await?;
        let mut level_dist = std::collections::HashMap::new();
        for r in &level_rows {
            let lvl: i32 = r.try_get("level").unwrap_or(1);
            let cnt: i64 = r.try_get("cnt").unwrap_or(0);
            level_dist.insert(lvl.to_string(), cnt);
        }

        Ok(UnlocksStatsRow {
            total_profiles: total,
            global_contributions,
            level_distribution: level_dist,
            total_badges_awarded: total_badges,
        })
    }

    // ════════════════════════════════════════════════════════════════════════
    // Bounties
    // ════════════════════════════════════════════════════════════════════════

    pub async fn insert_bounty(&self, b: &BountyRow) -> Result<(), sqlx::Error> {
        sqlx::query(
            "INSERT INTO aikgs_bounties
             (bounty_id, domain, description, gap_hash, reward_amount,
              boost_multiplier, status, expires_at)
             VALUES ($1,$2,$3,$4,$5,$6,'open',$7)",
        )
        .bind(b.bounty_id)
        .bind(&b.domain)
        .bind(&b.description)
        .bind(&b.gap_hash)
        .bind(b.reward_amount)
        .bind(b.boost_multiplier)
        .bind(b.expires_at_epoch)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    pub async fn get_bounty(&self, bounty_id: i64) -> Result<Option<BountyRow>, sqlx::Error> {
        sqlx::query_as::<_, BountyRow>(
            "SELECT bounty_id, domain, description, gap_hash,
                    reward_amount::float8 as reward_amount, boost_multiplier,
                    status, COALESCE(claimer_address, '') as claimer_address,
                    COALESCE(contribution_id, 0) as contribution_id,
                    EXTRACT(EPOCH FROM created_at) as created_at_epoch,
                    EXTRACT(EPOCH FROM expires_at) as expires_at_epoch
             FROM aikgs_bounties WHERE bounty_id = $1",
        )
        .bind(bounty_id)
        .fetch_optional(&self.pool)
        .await
    }

    pub async fn list_bounties(
        &self,
        domain: &str,
        status: &str,
        limit: i32,
    ) -> Result<Vec<BountyRow>, sqlx::Error> {
        let mut sql = String::from(
            "SELECT bounty_id, domain, description, gap_hash,
                    reward_amount::float8 as reward_amount, boost_multiplier,
                    status, COALESCE(claimer_address, '') as claimer_address,
                    COALESCE(contribution_id, 0) as contribution_id,
                    EXTRACT(EPOCH FROM created_at) as created_at_epoch,
                    EXTRACT(EPOCH FROM expires_at) as expires_at_epoch
             FROM aikgs_bounties WHERE 1=1",
        );
        let mut binds: Vec<String> = Vec::new();
        let mut idx = 1;
        if !domain.is_empty() {
            sql.push_str(&format!(" AND domain = ${idx}"));
            binds.push(domain.to_string());
            idx += 1;
        }
        if !status.is_empty() {
            sql.push_str(&format!(" AND status = ${idx}"));
            binds.push(status.to_string());
            idx += 1;
        }
        sql.push_str(&format!(" ORDER BY bounty_id DESC LIMIT ${idx}"));

        let mut q = sqlx::query_as::<_, BountyRow>(&sql);
        for b in &binds {
            q = q.bind(b);
        }
        q = q.bind(limit);
        q.fetch_all(&self.pool).await
    }

    pub async fn claim_bounty(
        &self,
        bounty_id: i64,
        claimer: &str,
    ) -> Result<bool, sqlx::Error> {
        let result = sqlx::query(
            "UPDATE aikgs_bounties SET status = 'claimed', claimer_address = $1
             WHERE bounty_id = $2 AND status = 'open' AND expires_at > now()",
        )
        .bind(claimer)
        .bind(bounty_id)
        .execute(&self.pool)
        .await?;
        Ok(result.rows_affected() > 0)
    }

    pub async fn fulfill_bounty(
        &self,
        bounty_id: i64,
        contribution_id: i64,
    ) -> Result<bool, sqlx::Error> {
        let result = sqlx::query(
            "UPDATE aikgs_bounties SET status = 'fulfilled', contribution_id = $1
             WHERE bounty_id = $2 AND status = 'claimed'",
        )
        .bind(contribution_id)
        .bind(bounty_id)
        .execute(&self.pool)
        .await?;
        Ok(result.rows_affected() > 0)
    }

    pub async fn next_bounty_id(&self) -> Result<i64, sqlx::Error> {
        let row = sqlx::query("SELECT COALESCE(MAX(bounty_id), 0) + 1 as nid FROM aikgs_bounties")
            .fetch_one(&self.pool)
            .await?;
        Ok(row.try_get::<i64, _>("nid").unwrap_or(1))
    }

    pub async fn get_bounty_stats(&self) -> Result<BountyStatsRow, sqlx::Error> {
        let row = sqlx::query(
            "SELECT COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'open') as open_count,
                    COUNT(*) FILTER (WHERE status = 'fulfilled') as fulfilled_count,
                    COALESCE(SUM(reward_amount) FILTER (WHERE status = 'open'), 0)::float8 as open_reward
             FROM aikgs_bounties",
        )
        .fetch_one(&self.pool)
        .await?;
        Ok(BountyStatsRow {
            total: row.try_get::<i64, _>("total").unwrap_or(0),
            open: row.try_get::<i64, _>("open_count").unwrap_or(0),
            fulfilled: row.try_get::<i64, _>("fulfilled_count").unwrap_or(0),
            open_reward: row.try_get::<f64, _>("open_reward").unwrap_or(0.0),
        })
    }

    // ════════════════════════════════════════════════════════════════════════
    // Curation
    // ════════════════════════════════════════════════════════════════════════

    pub async fn insert_curation_round(
        &self,
        contribution_id: i64,
        required_votes: i32,
    ) -> Result<(), sqlx::Error> {
        sqlx::query(
            "INSERT INTO aikgs_curation_rounds (contribution_id, required_votes)
             VALUES ($1, $2)
             ON CONFLICT (contribution_id) DO NOTHING",
        )
        .bind(contribution_id)
        .bind(required_votes)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    pub async fn get_curation_round(
        &self,
        contribution_id: i64,
    ) -> Result<Option<CurationRoundRow>, sqlx::Error> {
        let round = sqlx::query_as::<_, CurationRoundBasic>(
            "SELECT contribution_id, required_votes, votes_for, votes_against,
                    status, EXTRACT(EPOCH FROM COALESCE(finalized_at, '1970-01-01'::timestamptz)) as finalized_epoch
             FROM aikgs_curation_rounds WHERE contribution_id = $1",
        )
        .bind(contribution_id)
        .fetch_optional(&self.pool)
        .await?;

        match round {
            None => Ok(None),
            Some(r) => {
                let reviews = sqlx::query_as::<_, CurationReviewRow>(
                    "SELECT curator_address, contribution_id, vote, COALESCE(comment,'') as comment,
                            EXTRACT(EPOCH FROM created_at) as ts
                     FROM aikgs_curation_reviews WHERE contribution_id = $1",
                )
                .bind(contribution_id)
                .fetch_all(&self.pool)
                .await?;
                Ok(Some(CurationRoundRow {
                    contribution_id: r.contribution_id,
                    required_votes: r.required_votes,
                    votes_for: r.votes_for,
                    votes_against: r.votes_against,
                    status: r.status,
                    finalized_epoch: r.finalized_epoch,
                    reviews,
                }))
            }
        }
    }

    pub async fn insert_curation_review(
        &self,
        contribution_id: i64,
        curator_address: &str,
        vote: bool,
        comment: &str,
    ) -> Result<bool, sqlx::Error> {
        let result = sqlx::query(
            "INSERT INTO aikgs_curation_reviews (contribution_id, curator_address, vote, comment)
             VALUES ($1, $2, $3, $4)
             ON CONFLICT (contribution_id, curator_address) DO NOTHING",
        )
        .bind(contribution_id)
        .bind(curator_address)
        .bind(vote)
        .bind(comment)
        .execute(&self.pool)
        .await?;
        if result.rows_affected() == 0 {
            return Ok(false); // duplicate review
        }
        // Update round vote counts
        let col = if vote { "votes_for" } else { "votes_against" };
        let upd = format!(
            "UPDATE aikgs_curation_rounds SET {col} = {col} + 1 WHERE contribution_id = $1"
        );
        sqlx::query(&upd)
            .bind(contribution_id)
            .execute(&self.pool)
            .await?;
        Ok(true)
    }

    pub async fn finalize_curation_round(
        &self,
        contribution_id: i64,
        status: &str,
    ) -> Result<(), sqlx::Error> {
        sqlx::query(
            "UPDATE aikgs_curation_rounds SET status = $1, finalized_at = now()
             WHERE contribution_id = $2",
        )
        .bind(status)
        .bind(contribution_id)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    pub async fn get_pending_curation_rounds(
        &self,
        exclude_curator: &str,
    ) -> Result<Vec<CurationRoundRow>, sqlx::Error> {
        let basics = if exclude_curator.is_empty() {
            sqlx::query_as::<_, CurationRoundBasic>(
                "SELECT contribution_id, required_votes, votes_for, votes_against,
                        status, 0.0 as finalized_epoch
                 FROM aikgs_curation_rounds WHERE status = 'pending'",
            )
            .fetch_all(&self.pool)
            .await?
        } else {
            sqlx::query_as::<_, CurationRoundBasic>(
                "SELECT cr.contribution_id, cr.required_votes, cr.votes_for, cr.votes_against,
                        cr.status, 0.0 as finalized_epoch
                 FROM aikgs_curation_rounds cr
                 WHERE cr.status = 'pending'
                 AND NOT EXISTS (
                     SELECT 1 FROM aikgs_curation_reviews rv
                     WHERE rv.contribution_id = cr.contribution_id AND rv.curator_address = $1
                 )",
            )
            .bind(exclude_curator)
            .fetch_all(&self.pool)
            .await?
        };

        let mut rounds = Vec::new();
        for b in basics {
            let reviews = sqlx::query_as::<_, CurationReviewRow>(
                "SELECT curator_address, contribution_id, vote, COALESCE(comment,'') as comment,
                        EXTRACT(EPOCH FROM created_at) as ts
                 FROM aikgs_curation_reviews WHERE contribution_id = $1",
            )
            .bind(b.contribution_id)
            .fetch_all(&self.pool)
            .await?;
            rounds.push(CurationRoundRow {
                contribution_id: b.contribution_id,
                required_votes: b.required_votes,
                votes_for: b.votes_for,
                votes_against: b.votes_against,
                status: b.status,
                finalized_epoch: b.finalized_epoch,
                reviews,
            });
        }
        Ok(rounds)
    }

    pub async fn get_curation_stats(&self) -> Result<CurationStatsRow, sqlx::Error> {
        let row = sqlx::query(
            "SELECT COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending,
                    COUNT(*) FILTER (WHERE status = 'approved') as approved,
                    COUNT(*) FILTER (WHERE status = 'rejected') as rejected
             FROM aikgs_curation_rounds",
        )
        .fetch_one(&self.pool)
        .await?;

        let curators: i64 = sqlx::query_scalar(
            "SELECT COUNT(DISTINCT curator_address) FROM aikgs_curation_reviews",
        )
        .fetch_one(&self.pool)
        .await
        .unwrap_or(0);

        Ok(CurationStatsRow {
            total: row.try_get::<i64, _>("total").unwrap_or(0),
            pending: row.try_get::<i64, _>("pending").unwrap_or(0),
            approved: row.try_get::<i64, _>("approved").unwrap_or(0),
            rejected: row.try_get::<i64, _>("rejected").unwrap_or(0),
            total_curators: curators,
        })
    }

    // ════════════════════════════════════════════════════════════════════════
    // API Key Vault
    // ════════════════════════════════════════════════════════════════════════

    pub async fn insert_api_key(
        &self,
        key_id: &str,
        provider: &str,
        model: &str,
        owner_address: &str,
        encrypted_key: &[u8],
        is_shared: bool,
        shared_reward_bps: i32,
        label: &str,
    ) -> Result<(), sqlx::Error> {
        sqlx::query(
            "INSERT INTO aikgs_api_keys
             (key_id, provider, model, owner_address, encrypted_key,
              is_shared, shared_reward_bps, label)
             VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
        )
        .bind(key_id)
        .bind(provider)
        .bind(model)
        .bind(owner_address)
        .bind(encrypted_key)
        .bind(is_shared)
        .bind(shared_reward_bps)
        .bind(label)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    pub async fn get_api_key(&self, key_id: &str) -> Result<Option<ApiKeyRow>, sqlx::Error> {
        sqlx::query_as::<_, ApiKeyRow>(
            "SELECT key_id, provider, model, owner_address, encrypted_key,
                    is_shared, shared_reward_bps, label, use_count, is_active
             FROM aikgs_api_keys WHERE key_id = $1 AND is_active = true",
        )
        .bind(key_id)
        .fetch_optional(&self.pool)
        .await
    }

    pub async fn list_api_keys(&self, owner: &str) -> Result<Vec<ApiKeyRow>, sqlx::Error> {
        sqlx::query_as::<_, ApiKeyRow>(
            "SELECT key_id, provider, model, owner_address, encrypted_key,
                    is_shared, shared_reward_bps, label, use_count, is_active
             FROM aikgs_api_keys WHERE owner_address = $1 AND is_active = true
             ORDER BY key_id",
        )
        .bind(owner)
        .fetch_all(&self.pool)
        .await
    }

    pub async fn revoke_api_key(
        &self,
        key_id: &str,
        owner: &str,
    ) -> Result<bool, sqlx::Error> {
        let result = sqlx::query(
            "UPDATE aikgs_api_keys SET is_active = false
             WHERE key_id = $1 AND owner_address = $2",
        )
        .bind(key_id)
        .bind(owner)
        .execute(&self.pool)
        .await?;
        Ok(result.rows_affected() > 0)
    }

    pub async fn get_shared_keys(&self, provider: &str) -> Result<Vec<ApiKeyRow>, sqlx::Error> {
        sqlx::query_as::<_, ApiKeyRow>(
            "SELECT key_id, provider, model, owner_address, encrypted_key,
                    is_shared, shared_reward_bps, label, use_count, is_active
             FROM aikgs_api_keys
             WHERE provider = $1 AND is_shared = true AND is_active = true",
        )
        .bind(provider)
        .fetch_all(&self.pool)
        .await
    }

    pub async fn increment_key_usage(&self, key_id: &str) -> Result<(), sqlx::Error> {
        sqlx::query(
            "UPDATE aikgs_api_keys SET use_count = use_count + 1, last_used_at = now()
             WHERE key_id = $1",
        )
        .bind(key_id)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    // ════════════════════════════════════════════════════════════════════════
    // Streak tracking (per-contributor)
    // ════════════════════════════════════════════════════════════════════════

    /// Get the streak info for a contributor from their profile.
    pub async fn get_streak(&self, address: &str) -> Result<(i32, i32), sqlx::Error> {
        let row = sqlx::query(
            "SELECT current_streak, best_streak FROM aikgs_profiles WHERE address = $1",
        )
        .bind(address)
        .fetch_optional(&self.pool)
        .await?;
        match row {
            Some(r) => Ok((
                r.try_get::<i32, _>("current_streak").unwrap_or(0),
                r.try_get::<i32, _>("best_streak").unwrap_or(0),
            )),
            None => Ok((0, 0)),
        }
    }
}

// ════════════════════════════════════════════════════════════════════════════
// Row types
// ════════════════════════════════════════════════════════════════════════════

#[derive(Debug, sqlx::FromRow)]
pub struct ContributionRow {
    pub contribution_id: i64,
    pub contributor_address: String,
    pub content_hash: String,
    pub knowledge_node_id: Option<i64>,
    pub quality_score: f64,
    pub novelty_score: f64,
    pub combined_score: f64,
    pub tier: String,
    pub domain: String,
    pub reward_amount: sqlx::types::BigDecimal,
    pub status: String,
    pub block_height: i64,
    pub created_at: DateTime<Utc>,
}

impl ContributionRow {
    pub fn reward_f64(&self) -> f64 {
        bigdecimal_to_f64(&self.reward_amount)
    }
}

#[derive(Debug)]
pub struct ContributionStatsRow {
    pub total: i64,
    pub unique_contributors: i64,
    pub total_rewards: f64,
    pub bronze: i64,
    pub silver: i64,
    pub gold: i64,
    pub diamond: i64,
    pub bounty_fulfillments: i64,
}

#[derive(Debug, sqlx::FromRow)]
pub struct LeaderboardRow {
    pub address: String,
    pub total_reward: f64,
    pub contribution_count: i32,
    pub avg_quality: f64,
    pub best_tier: String,
}

#[derive(Debug, sqlx::FromRow)]
pub struct AffiliateRow {
    pub address: String,
    pub referrer_address: Option<String>,
    pub referral_code: String,
    pub l1_referrals: i32,
    pub l2_referrals: i32,
    pub total_l1_commission: f64,
    pub total_l2_commission: f64,
    pub is_active: bool,
}

pub struct AffiliateStatsRow {
    pub total_affiliates: i64,
    pub total_l1_commissions: f64,
    pub total_l2_commissions: f64,
}

#[derive(Debug, sqlx::FromRow)]
pub struct ProfileRow {
    pub address: String,
    pub reputation_points: f64,
    pub level: i32,
    pub level_name: String,
    pub total_contributions: i32,
    pub best_streak: i32,
    pub current_streak: i32,
    pub gold_count: i32,
    pub diamond_count: i32,
    pub bounties_fulfilled: i32,
    pub referrals: i32,
    pub badges: JsonValue,
    pub unlocked_features: JsonValue,
    pub last_contribution_at: Option<DateTime<Utc>>,
}

pub struct UnlocksStatsRow {
    pub total_profiles: i64,
    pub global_contributions: i64,
    pub level_distribution: std::collections::HashMap<String, i64>,
    pub total_badges_awarded: i64,
}

#[derive(Debug, sqlx::FromRow)]
pub struct BountyRow {
    pub bounty_id: i64,
    pub domain: String,
    pub description: String,
    pub gap_hash: String,
    pub reward_amount: f64,
    pub boost_multiplier: f64,
    pub status: String,
    pub claimer_address: String,
    pub contribution_id: i64,
    pub created_at_epoch: f64,
    pub expires_at_epoch: f64,
}

pub struct BountyStatsRow {
    pub total: i64,
    pub open: i64,
    pub fulfilled: i64,
    pub open_reward: f64,
}

#[derive(Debug, sqlx::FromRow)]
struct CurationRoundBasic {
    pub contribution_id: i64,
    pub required_votes: i32,
    pub votes_for: i32,
    pub votes_against: i32,
    pub status: String,
    pub finalized_epoch: f64,
}

#[derive(Debug)]
pub struct CurationRoundRow {
    pub contribution_id: i64,
    pub required_votes: i32,
    pub votes_for: i32,
    pub votes_against: i32,
    pub status: String,
    pub finalized_epoch: f64,
    pub reviews: Vec<CurationReviewRow>,
}

#[derive(Debug, sqlx::FromRow)]
pub struct CurationReviewRow {
    pub curator_address: String,
    pub contribution_id: i64,
    pub vote: bool,
    pub comment: String,
    pub ts: f64,
}

pub struct CurationStatsRow {
    pub total: i64,
    pub pending: i64,
    pub approved: i64,
    pub rejected: i64,
    pub total_curators: i64,
}

#[derive(Debug, sqlx::FromRow)]
pub struct ApiKeyRow {
    pub key_id: String,
    pub provider: String,
    pub model: String,
    pub owner_address: String,
    pub encrypted_key: Vec<u8>,
    pub is_shared: bool,
    pub shared_reward_bps: i32,
    pub label: String,
    pub use_count: i32,
    pub is_active: bool,
}

fn bigdecimal_to_f64(bd: &sqlx::types::BigDecimal) -> f64 {
    use std::str::FromStr;
    f64::from_str(&bd.to_string()).unwrap_or(0.0)
}
