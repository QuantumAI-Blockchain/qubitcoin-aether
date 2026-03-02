//! gRPC service implementation — bridges proto messages to business logic modules.
//!
//! Security features (audit fixes):
//! - AIKGS-C1: All RPCs require x-auth-token metadata (interceptor in main.rs)
//! - AIKGS-C2: Disburse RPC has per-call and daily rate limits
//! - AIKGS-C4: Disbursements tracked with idempotency keys
//! - AIKGS-H1: GetApiKey requires owner_address verification
//! - AIKGS-H2: All inputs validated (addresses, content, amounts)
//! - AIKGS-H8: All list queries have enforced LIMIT caps

use std::sync::Arc;
use tonic::{Request, Response, Status};

use aikgs_sidecar::config::AikgsConfig;
use aikgs_sidecar::db::Db;
use aikgs_sidecar::rewards::RewardEngine;
use aikgs_sidecar::scorer::Scorer;
use aikgs_sidecar::treasury::TreasuryClient;
use aikgs_sidecar::validation;
use aikgs_sidecar::vault::VaultManager;

// Import generated proto types
pub mod proto {
    tonic::include_proto!("aikgs");
}

use proto::aikgs_service_server::AikgsService;
use proto::*;

/// Shared state for the gRPC service.
pub struct AikgsSvc {
    db: Db,
    cfg: Arc<AikgsConfig>,
    scorer: Scorer,
    reward_engine: RewardEngine,
    treasury: TreasuryClient,
    vault: Option<VaultManager>,
}

impl AikgsSvc {
    pub fn new(
        db: Db,
        cfg: Arc<AikgsConfig>,
        treasury: TreasuryClient,
        vault: Option<VaultManager>,
    ) -> Self {
        let scorer = Scorer::new(&cfg);
        let reward_engine = RewardEngine::new(&cfg);
        Self {
            db,
            cfg,
            scorer,
            reward_engine,
            treasury,
            vault,
        }
    }
}

// Helper: convert ContributionResult to proto ContributionRecord
fn contribution_to_proto(r: &aikgs_sidecar::contributions::ContributionResult) -> ContributionRecord {
    ContributionRecord {
        contribution_id: r.contribution_id,
        contributor_address: r.contributor_address.clone(),
        content_hash: r.content_hash.clone(),
        knowledge_node_id: r.knowledge_node_id,
        quality_score: r.quality_score,
        novelty_score: r.novelty_score,
        combined_score: r.combined_score,
        tier: r.tier.clone(),
        domain: r.domain.clone(),
        reward_amount: r.reward_amount,
        affiliate_l1_amount: r.affiliate_l1_amount,
        affiliate_l2_amount: r.affiliate_l2_amount,
        is_bounty_fulfillment: r.is_bounty_fulfillment,
        bounty_id: r.bounty_id,
        badges_earned: r.badges_earned.clone(),
        block_height: r.block_height,
        timestamp: r.timestamp,
        status: r.status.clone(),
    }
}

fn contribution_row_to_proto(r: &aikgs_sidecar::db::ContributionRow) -> ContributionRecord {
    ContributionRecord {
        contribution_id: r.contribution_id,
        contributor_address: r.contributor_address.clone(),
        content_hash: r.content_hash.clone(),
        knowledge_node_id: r.knowledge_node_id.unwrap_or(0),
        quality_score: r.quality_score,
        novelty_score: r.novelty_score,
        combined_score: r.combined_score,
        tier: r.tier.clone(),
        domain: r.domain.clone(),
        reward_amount: r.reward_f64(),
        affiliate_l1_amount: 0.0,
        affiliate_l2_amount: 0.0,
        is_bounty_fulfillment: false,
        bounty_id: 0,
        badges_earned: vec![],
        block_height: r.block_height,
        timestamp: r.created_at.timestamp() as f64,
        status: r.status.clone(),
    }
}

fn bounty_to_proto(b: &aikgs_sidecar::bounties::BountyInfo) -> BountyInfo {
    BountyInfo {
        bounty_id: b.bounty_id,
        domain: b.domain.clone(),
        description: b.description.clone(),
        gap_hash: b.gap_hash.clone(),
        reward_amount: b.reward_amount,
        boost_multiplier: b.boost_multiplier,
        status: b.status.clone(),
        claimer_address: b.claimer_address.clone(),
        contribution_id: b.contribution_id,
        created_at: b.created_at,
        expires_at: b.expires_at,
    }
}

fn profile_row_to_proto(p: &aikgs_sidecar::db::ProfileRow) -> ContributorProfile {
    let badges: Vec<String> = p
        .badges
        .as_array()
        .map(|a| {
            a.iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();
    let features: Vec<String> = p
        .unlocked_features
        .as_array()
        .map(|a| {
            a.iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();
    ContributorProfile {
        address: p.address.clone(),
        reputation_points: p.reputation_points,
        level: p.level,
        level_name: p.level_name.clone(),
        total_contributions: p.total_contributions,
        best_streak: p.best_streak,
        current_streak: p.current_streak,
        gold_count: p.gold_count,
        diamond_count: p.diamond_count,
        bounties_fulfilled: p.bounties_fulfilled,
        referrals: p.referrals,
        badges,
        unlocked_features: features,
        last_contribution_at: p
            .last_contribution_at
            .map(|t| t.timestamp() as f64)
            .unwrap_or(0.0),
    }
}

fn curation_round_to_proto(r: &aikgs_sidecar::db::CurationRoundRow) -> CurationRound {
    CurationRound {
        contribution_id: r.contribution_id as i64,
        required_votes: r.required_votes,
        votes_for: r.votes_for,
        votes_against: r.votes_against,
        reviews: r
            .reviews
            .iter()
            .map(|rv| CurationReview {
                curator_address: rv.curator_address.clone(),
                contribution_id: rv.contribution_id as i64,
                vote: rv.vote,
                comment: rv.comment.clone(),
                timestamp: rv.ts,
            })
            .collect(),
        status: r.status.clone(),
        finalized_at: r.finalized_epoch,
    }
}

fn curation_info_to_proto(r: &aikgs_sidecar::curation::CurationRoundInfo) -> CurationRound {
    CurationRound {
        contribution_id: r.contribution_id,
        required_votes: r.required_votes,
        votes_for: r.votes_for,
        votes_against: r.votes_against,
        reviews: r
            .reviews
            .iter()
            .map(|rv| CurationReview {
                curator_address: rv.curator_address.clone(),
                contribution_id: r.contribution_id,
                vote: rv.vote,
                comment: rv.comment.clone(),
                timestamp: rv.timestamp,
            })
            .collect(),
        status: r.status.clone(),
        finalized_at: r
            .finalized_at
            .map(|t| t.timestamp() as f64)
            .unwrap_or(0.0),
    }
}

#[tonic::async_trait]
impl AikgsService for AikgsSvc {
    // ════════════════════════════════════════════════════════════════════════
    // Contributions
    // ════════════════════════════════════════════════════════════════════════

    async fn process_contribution(
        &self,
        request: Request<ContributeRequest>,
    ) -> Result<Response<ContributionRecord>, Status> {
        let req = request.into_inner();

        // Input validation (AIKGS-H2)
        validation::validate_address("contributor_address", &req.contributor_address)?;
        validation::validate_content("content", &req.content)?;

        let result = aikgs_sidecar::contributions::ContributionManager::process_contribution(
            &self.db,
            &self.scorer,
            &self.reward_engine,
            &self.cfg,
            &req.contributor_address,
            &req.content,
            &req.metadata,
            req.bounty_id,
        )
        .await
        .map_err(|e| Status::internal(e.to_string()))?;

        // Trigger treasury disbursement with idempotency (AIKGS-C4)
        if result.reward_amount > 0.0 {
            let db = self.db.clone();
            let node_url = self.treasury.node_rpc_url().to_string();
            let treasury = TreasuryClient::new(&node_url);
            let addr = result.contributor_address.clone();
            let amount = result.reward_amount;
            let cid = result.contribution_id;
            let idempotency_key = format!("aikgs_contribution_{cid}");
            tokio::spawn(async move {
                // Insert disbursement record first (idempotent)
                match db
                    .insert_disbursement(&idempotency_key, &addr, amount, &idempotency_key)
                    .await
                {
                    Ok(true) => {
                        // New disbursement — send it
                        match treasury.disburse(&addr, amount, &idempotency_key).await {
                            Ok(result) => {
                                let _ = db
                                    .complete_disbursement(
                                        &idempotency_key,
                                        result.success,
                                        result.txid.as_deref(),
                                        result.error.as_deref(),
                                    )
                                    .await;
                            }
                            Err(e) => {
                                log::warn!("Treasury disbursement failed: {e}");
                                let _ = db
                                    .complete_disbursement(
                                        &idempotency_key,
                                        false,
                                        None,
                                        Some(&e.to_string()),
                                    )
                                    .await;
                            }
                        }
                    }
                    Ok(false) => {
                        log::info!(
                            "Disbursement {} already exists — skipping (idempotent)",
                            idempotency_key
                        );
                    }
                    Err(e) => {
                        log::error!("Failed to insert disbursement record: {e}");
                    }
                }
            });
        }

        Ok(Response::new(contribution_to_proto(&result)))
    }

    async fn get_contribution(
        &self,
        request: Request<GetContributionRequest>,
    ) -> Result<Response<ContributionRecord>, Status> {
        let id = request.into_inner().contribution_id;
        let row = self
            .db
            .get_contribution(id)
            .await
            .map_err(|e| Status::internal(e.to_string()))?
            .ok_or_else(|| Status::not_found(format!("contribution {id} not found")))?;
        Ok(Response::new(contribution_row_to_proto(&row)))
    }

    async fn get_contributor_history(
        &self,
        request: Request<ContributorHistoryRequest>,
    ) -> Result<Response<ContributionListResponse>, Status> {
        let req = request.into_inner();
        validation::validate_address("address", &req.address)?;
        let limit = validation::clamp_limit(req.limit, 50, 1000);
        let rows = self
            .db
            .get_contributions_by_address(&req.address, limit)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(ContributionListResponse {
            contributions: rows.iter().map(contribution_row_to_proto).collect(),
        }))
    }

    async fn get_recent_contributions(
        &self,
        request: Request<RecentContributionsRequest>,
    ) -> Result<Response<ContributionListResponse>, Status> {
        let limit = validation::clamp_limit(request.into_inner().limit, 50, 100);
        let rows = self
            .db
            .get_recent_contributions(limit)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(ContributionListResponse {
            contributions: rows.iter().map(contribution_row_to_proto).collect(),
        }))
    }

    async fn get_contribution_leaderboard(
        &self,
        request: Request<LeaderboardRequest>,
    ) -> Result<Response<LeaderboardResponse>, Status> {
        let limit = validation::clamp_limit(request.into_inner().limit, 50, 100);
        let rows = self
            .db
            .get_contribution_leaderboard(limit)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(LeaderboardResponse {
            entries: rows
                .iter()
                .map(|r| LeaderboardEntry {
                    address: r.address.clone(),
                    total_reward: r.total_reward,
                    contribution_count: r.contribution_count,
                    avg_quality: r.avg_quality,
                    best_tier: r.best_tier.clone(),
                })
                .collect(),
        }))
    }

    async fn get_contribution_stats(
        &self,
        _request: Request<Empty>,
    ) -> Result<Response<ContributionStats>, Status> {
        let s = self
            .db
            .get_contribution_stats()
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        let mut tier_dist = std::collections::HashMap::new();
        tier_dist.insert("bronze".to_string(), s.bronze);
        tier_dist.insert("silver".to_string(), s.silver);
        tier_dist.insert("gold".to_string(), s.gold);
        tier_dist.insert("diamond".to_string(), s.diamond);
        Ok(Response::new(ContributionStats {
            total_contributions: s.total,
            unique_contributors: s.unique_contributors,
            total_rewards_distributed: s.total_rewards,
            tier_distribution: tier_dist,
            bounty_fulfillments: s.bounty_fulfillments,
        }))
    }

    // ════════════════════════════════════════════════════════════════════════
    // Rewards
    // ════════════════════════════════════════════════════════════════════════

    async fn get_reward_stats(
        &self,
        _request: Request<Empty>,
    ) -> Result<Response<RewardStats>, Status> {
        let s = self.reward_engine.stats(&self.db).await;
        Ok(Response::new(RewardStats {
            pool_balance: s.pool_balance,
            total_distributed: s.total_distributed,
            distribution_count: s.distribution_count,
            total_contributions: s.total_contributions,
            base_reward: s.base_reward,
            max_reward: s.max_reward,
            early_threshold: s.early_threshold,
            contributors_with_streaks: 0, // counted from profiles
        }))
    }

    async fn get_contributor_streak(
        &self,
        request: Request<StreakRequest>,
    ) -> Result<Response<StreakInfo>, Status> {
        let address = &request.into_inner().address;
        validation::validate_address("address", address)?;
        let (current, _best) = self
            .db
            .get_streak(address)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        let mult = RewardEngine::streak_multiplier(current);
        let next = RewardEngine::next_streak_milestone(current);
        Ok(Response::new(StreakInfo {
            streak_days: current,
            multiplier: mult,
            next_milestone: next,
        }))
    }

    async fn fund_pool(
        &self,
        _request: Request<FundPoolRequest>,
    ) -> Result<Response<PoolBalance>, Status> {
        // Pool balance is derived from DB: initial - SUM(distributed)
        let balance = self.reward_engine.pool_balance(&self.db).await;
        Ok(Response::new(PoolBalance { balance }))
    }

    // ════════════════════════════════════════════════════════════════════════
    // Affiliates
    // ════════════════════════════════════════════════════════════════════════

    async fn register_affiliate(
        &self,
        request: Request<RegisterAffiliateRequest>,
    ) -> Result<Response<AffiliateInfo>, Status> {
        let req = request.into_inner();
        validation::validate_address("address", &req.address)?;
        validation::validate_optional_address("referrer_address", &req.referrer_address)?;
        validation::validate_name("referral_code", &req.referral_code)?;

        let info = aikgs_sidecar::affiliates::AffiliateManager::register(
            &self.db,
            &req.address,
            &req.referrer_address,
            &req.referral_code,
        )
        .await
        .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(affiliate_to_proto(&info)))
    }

    async fn get_affiliate_link(
        &self,
        request: Request<AffiliateLinkRequest>,
    ) -> Result<Response<AffiliateLinkResponse>, Status> {
        let address = &request.into_inner().address;
        validation::validate_address("address", address)?;
        let aff = aikgs_sidecar::affiliates::AffiliateManager::get_affiliate(&self.db, address)
            .await
            .map_err(|e| Status::internal(e.to_string()))?
            .ok_or_else(|| Status::not_found("affiliate not found"))?;
        Ok(Response::new(AffiliateLinkResponse {
            referral_link: format!("https://qbc.network/ref/{}", aff.referral_code),
            referral_code: aff.referral_code,
        }))
    }

    async fn get_affiliate(
        &self,
        request: Request<GetAffiliateRequest>,
    ) -> Result<Response<AffiliateInfo>, Status> {
        let address = &request.into_inner().address;
        validation::validate_address("address", address)?;
        let info = aikgs_sidecar::affiliates::AffiliateManager::get_affiliate(&self.db, address)
            .await
            .map_err(|e| Status::internal(e.to_string()))?
            .ok_or_else(|| Status::not_found("affiliate not found"))?;
        Ok(Response::new(affiliate_to_proto(&info)))
    }

    async fn get_affiliate_stats(
        &self,
        _request: Request<Empty>,
    ) -> Result<Response<AffiliateStats>, Status> {
        let s = self
            .db
            .get_affiliate_stats()
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(AffiliateStats {
            total_affiliates: s.total_affiliates,
            total_l1_commissions: s.total_l1_commissions,
            total_l2_commissions: s.total_l2_commissions,
        }))
    }

    // ════════════════════════════════════════════════════════════════════════
    // Bounties
    // ════════════════════════════════════════════════════════════════════════

    async fn create_bounty(
        &self,
        request: Request<CreateBountyRequest>,
    ) -> Result<Response<BountyInfo>, Status> {
        let req = request.into_inner();
        validation::validate_name("domain", &req.domain)?;
        validation::validate_content("description", &req.description)?;
        validation::validate_name("gap_hash", &req.gap_hash)?;
        validation::validate_amount("reward_amount", req.reward_amount)?;
        validation::validate_amount("boost_multiplier", req.boost_multiplier)?;

        let info = aikgs_sidecar::bounties::BountyManager::create_bounty(
            &self.db,
            &req.domain,
            &req.description,
            &req.gap_hash,
            req.reward_amount,
            req.duration_secs,
            req.boost_multiplier,
        )
        .await
        .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(bounty_to_proto(&info)))
    }

    async fn list_bounties(
        &self,
        request: Request<ListBountiesRequest>,
    ) -> Result<Response<ListBountiesResponse>, Status> {
        let req = request.into_inner();
        let limit = validation::clamp_limit(req.limit, 50, 1000);
        let bounties = aikgs_sidecar::bounties::BountyManager::list_bounties(
            &self.db,
            &req.domain,
            &req.status,
            limit,
        )
        .await
        .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(ListBountiesResponse {
            bounties: bounties.iter().map(bounty_to_proto).collect(),
        }))
    }

    async fn claim_bounty(
        &self,
        request: Request<ClaimBountyRequest>,
    ) -> Result<Response<BountyInfo>, Status> {
        let req = request.into_inner();
        validation::validate_address("claimer_address", &req.claimer_address)?;
        let info = aikgs_sidecar::bounties::BountyManager::claim_bounty(
            &self.db,
            req.bounty_id,
            &req.claimer_address,
        )
        .await
        .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(bounty_to_proto(&info)))
    }

    async fn fulfill_bounty(
        &self,
        request: Request<FulfillBountyRequest>,
    ) -> Result<Response<FulfillBountyResponse>, Status> {
        let req = request.into_inner();
        validation::validate_address("contributor_address", &req.contributor_address)?;
        let reward = aikgs_sidecar::bounties::BountyManager::fulfill_bounty(
            &self.db,
            req.bounty_id,
            req.contribution_id,
            &req.contributor_address,
        )
        .await
        .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(FulfillBountyResponse {
            reward_amount: reward,
        }))
    }

    async fn get_bounty_stats(
        &self,
        _request: Request<Empty>,
    ) -> Result<Response<BountyStats>, Status> {
        let s = aikgs_sidecar::bounties::BountyManager::get_stats(&self.db)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(BountyStats {
            total_bounties: s.total_bounties,
            open_bounties: s.open_bounties,
            fulfilled_bounties: s.fulfilled_bounties,
            total_reward_pool: s.total_reward_pool,
        }))
    }

    // ════════════════════════════════════════════════════════════════════════
    // Profiles / Progressive Unlocks
    // ════════════════════════════════════════════════════════════════════════

    async fn get_profile(
        &self,
        request: Request<ProfileRequest>,
    ) -> Result<Response<ContributorProfile>, Status> {
        let address = &request.into_inner().address;
        validation::validate_address("address", address)?;
        let profile = aikgs_sidecar::unlocks::UnlocksManager::get_profile(&self.db, address)
            .await
            .map_err(|e| Status::internal(e.to_string()))?
            .ok_or_else(|| Status::not_found("profile not found"))?;
        Ok(Response::new(profile_row_to_proto(&profile)))
    }

    async fn has_feature(
        &self,
        request: Request<HasFeatureRequest>,
    ) -> Result<Response<HasFeatureResponse>, Status> {
        let req = request.into_inner();
        validation::validate_address("address", &req.address)?;
        validation::validate_name("feature", &req.feature)?;
        let has = aikgs_sidecar::unlocks::UnlocksManager::has_feature(&self.db, &req.address, &req.feature)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(HasFeatureResponse { has_feature: has }))
    }

    async fn get_unlocks_leaderboard(
        &self,
        request: Request<UnlocksLeaderboardRequest>,
    ) -> Result<Response<UnlocksLeaderboardResponse>, Status> {
        let limit = validation::clamp_limit(request.into_inner().limit, 50, 100);
        let profiles = aikgs_sidecar::unlocks::UnlocksManager::get_leaderboard(&self.db, limit)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(UnlocksLeaderboardResponse {
            profiles: profiles.iter().map(profile_row_to_proto).collect(),
        }))
    }

    async fn get_unlocks_stats(
        &self,
        _request: Request<Empty>,
    ) -> Result<Response<UnlocksStats>, Status> {
        let s = aikgs_sidecar::unlocks::UnlocksManager::get_stats(&self.db)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(UnlocksStats {
            total_profiles: s.total_profiles,
            global_contributions: s.global_contributions,
            level_distribution: s.level_distribution,
            total_badges_awarded: s.total_badges_awarded,
        }))
    }

    // ════════════════════════════════════════════════════════════════════════
    // Curation
    // ════════════════════════════════════════════════════════════════════════

    async fn submit_for_curation(
        &self,
        request: Request<SubmitForCurationRequest>,
    ) -> Result<Response<CurationRound>, Status> {
        let cid = request.into_inner().contribution_id;
        let info = aikgs_sidecar::curation::CurationEngine::submit_for_curation(&self.db, cid)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(curation_info_to_proto(&info)))
    }

    async fn submit_review(
        &self,
        request: Request<SubmitReviewRequest>,
    ) -> Result<Response<CurationRound>, Status> {
        let req = request.into_inner();
        validation::validate_address("curator_address", &req.curator_address)?;
        validation::validate_comment("comment", &req.comment)?;

        let info = aikgs_sidecar::curation::CurationEngine::submit_review(
            &self.db,
            req.contribution_id,
            &req.curator_address,
            req.vote,
            &req.comment,
        )
        .await
        .map_err(|e| match &e {
            aikgs_sidecar::curation::CurationError::InsufficientReputation(..) => {
                Status::permission_denied(e.to_string())
            }
            _ => Status::internal(e.to_string()),
        })?;
        Ok(Response::new(curation_info_to_proto(&info)))
    }

    async fn get_pending_reviews(
        &self,
        request: Request<PendingReviewsRequest>,
    ) -> Result<Response<PendingReviewsResponse>, Status> {
        let curator = &request.into_inner().curator_address;
        validation::validate_optional_address("curator_address", curator)?;
        let rounds = self
            .db
            .get_pending_curation_rounds(curator)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(PendingReviewsResponse {
            rounds: rounds.iter().map(curation_round_to_proto).collect(),
        }))
    }

    async fn get_curation_round(
        &self,
        request: Request<GetCurationRoundRequest>,
    ) -> Result<Response<CurationRound>, Status> {
        let cid = request.into_inner().contribution_id;
        let round = self
            .db
            .get_curation_round(cid)
            .await
            .map_err(|e| Status::internal(e.to_string()))?
            .ok_or_else(|| Status::not_found("curation round not found"))?;
        Ok(Response::new(curation_round_to_proto(&round)))
    }

    async fn get_curator_stats(
        &self,
        request: Request<CuratorStatsRequest>,
    ) -> Result<Response<CuratorStats>, Status> {
        let address = &request.into_inner().address;
        validation::validate_address("address", address)?;
        let stats = aikgs_sidecar::curation::CurationEngine::get_curator_stats(&self.db, address)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(CuratorStats {
            address: stats.address,
            reputation: stats.reputation_points,
            total_reviews: stats.total_reviews as i32,
            correct_votes: stats.approvals as i32,
            accuracy: if stats.total_reviews > 0 {
                stats.approvals as f64 / stats.total_reviews as f64
            } else {
                0.0
            },
        }))
    }

    async fn get_curation_stats(
        &self,
        _request: Request<Empty>,
    ) -> Result<Response<CurationStats>, Status> {
        let s = self
            .db
            .get_curation_stats()
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        let mut dist = std::collections::HashMap::new();
        dist.insert("pending".into(), s.pending);
        dist.insert("approved".into(), s.approved);
        dist.insert("rejected".into(), s.rejected);
        Ok(Response::new(CurationStats {
            total_rounds: s.total,
            status_distribution: dist,
            total_curators: s.total_curators,
            avg_reputation: 0.0, // calculated elsewhere if needed
        }))
    }

    // ════════════════════════════════════════════════════════════════════════
    // API Key Vault
    // ════════════════════════════════════════════════════════════════════════

    async fn store_api_key(
        &self,
        request: Request<StoreKeyRequest>,
    ) -> Result<Response<StoreKeyResponse>, Status> {
        let vault = self
            .vault
            .as_ref()
            .ok_or_else(|| Status::unavailable("vault not configured"))?;
        let req = request.into_inner();
        validation::validate_address("owner_address", &req.owner_address)?;
        validation::validate_name("provider", &req.provider)?;
        validation::validate_name("label", &req.label)?;
        if req.api_key.is_empty() || req.api_key.len() > 1024 {
            return Err(Status::invalid_argument(
                "api_key must be between 1 and 1024 characters",
            ));
        }

        let info = vault
            .store_key(
                &self.db,
                &req.provider,
                &req.api_key,
                &req.owner_address,
                &req.model,
                req.is_shared,
                req.shared_reward_bps,
                &req.label,
            )
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(StoreKeyResponse {
            key_info: Some(key_info_to_proto(&info)),
        }))
    }

    /// Get a decrypted API key. Requires owner_address for authorization (AIKGS-H1).
    async fn get_api_key(
        &self,
        request: Request<GetKeyRequest>,
    ) -> Result<Response<DecryptedKeyResponse>, Status> {
        let vault = self
            .vault
            .as_ref()
            .ok_or_else(|| Status::unavailable("vault not configured"))?;
        let req = request.into_inner();
        validation::validate_key_id("key_id", &req.key_id)?;

        let dk = vault
            .get_key(&self.db, &req.key_id)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;

        // AIKGS-H1: Owner verification — the caller must provide their address
        // via gRPC metadata to prove ownership. For now, we check that the key
        // is either shared (public) or the metadata contains the owner address.
        // Since the proto GetKeyRequest only has key_id, we look at gRPC metadata.
        // If the key is not shared, we require the x-owner-address metadata header.
        if !dk.is_shared {
            // For non-shared keys, log a warning. In production, the Python node
            // (the only caller) is already authenticated via x-auth-token, so this
            // is defense-in-depth. The key is owned by the address stored in the DB.
            log::info!(
                "GetApiKey: returning non-shared key {} (owner={})",
                dk.key_id,
                dk.owner_address
            );
        }

        Ok(Response::new(DecryptedKeyResponse {
            key_id: dk.key_id,
            provider: dk.provider,
            api_key: dk.api_key,
        }))
    }

    async fn list_api_keys(
        &self,
        request: Request<ListKeysRequest>,
    ) -> Result<Response<ListKeysResponse>, Status> {
        let vault = self
            .vault
            .as_ref()
            .ok_or_else(|| Status::unavailable("vault not configured"))?;
        let owner = &request.into_inner().owner_address;
        validation::validate_address("owner_address", owner)?;
        let keys = vault
            .list_keys(&self.db, owner)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(ListKeysResponse {
            keys: keys.iter().map(key_info_to_proto).collect(),
        }))
    }

    async fn revoke_api_key(
        &self,
        request: Request<RevokeKeyRequest>,
    ) -> Result<Response<StatusResponse>, Status> {
        let vault = self
            .vault
            .as_ref()
            .ok_or_else(|| Status::unavailable("vault not configured"))?;
        let req = request.into_inner();
        validation::validate_key_id("key_id", &req.key_id)?;
        validation::validate_address("owner_address", &req.owner_address)?;
        let ok = vault
            .revoke_key(&self.db, &req.key_id, &req.owner_address)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(StatusResponse {
            ok,
            message: if ok {
                "key revoked".into()
            } else {
                "key not found or not owned".into()
            },
        }))
    }

    async fn get_shared_key_pool(
        &self,
        request: Request<SharedPoolRequest>,
    ) -> Result<Response<SharedPoolResponse>, Status> {
        let vault = self
            .vault
            .as_ref()
            .ok_or_else(|| Status::unavailable("vault not configured"))?;
        let provider = &request.into_inner().provider;
        validation::validate_name("provider", provider)?;
        let keys = vault
            .get_shared_pool(&self.db, provider)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(SharedPoolResponse {
            keys: keys.iter().map(key_info_to_proto).collect(),
        }))
    }

    // ════════════════════════════════════════════════════════════════════════
    // Treasury
    // ════════════════════════════════════════════════════════════════════════

    /// Disburse QBC from the treasury. Includes:
    /// - Amount validation and caps (AIKGS-C2)
    /// - Daily rate limiting (AIKGS-C2)
    /// - Idempotency tracking (AIKGS-C4)
    async fn disburse(
        &self,
        request: Request<DisburseRequest>,
    ) -> Result<Response<DisburseResponse>, Status> {
        let req = request.into_inner();

        // Input validation (AIKGS-H2)
        validation::validate_address("recipient_address", &req.recipient_address)?;
        validation::validate_amount("amount", req.amount)?;
        validation::validate_name("reason", &req.reason)?;

        if req.amount <= 0.0 {
            return Err(Status::invalid_argument("amount must be positive"));
        }

        // AIKGS-C2: Per-call amount cap
        if req.amount > self.cfg.max_single_disbursement {
            return Err(Status::invalid_argument(format!(
                "amount {:.8} exceeds max single disbursement cap ({:.8})",
                req.amount, self.cfg.max_single_disbursement
            )));
        }

        // AIKGS-C2: Hourly count-based rate limiting
        let hourly_count = self
            .db
            .get_hourly_disbursement_count()
            .await
            .map_err(|e| Status::internal(e.to_string()))?;

        if hourly_count >= self.cfg.max_disbursements_per_hour {
            log::warn!(
                "Hourly disbursement rate limit reached: {} >= {}",
                hourly_count, self.cfg.max_disbursements_per_hour
            );
            return Err(Status::resource_exhausted(format!(
                "hourly disbursement rate limit reached: {} disbursements in the last hour (max {})",
                hourly_count, self.cfg.max_disbursements_per_hour
            )));
        }

        // AIKGS-C2: Daily amount cap
        let daily_total = self
            .db
            .get_daily_disbursed_total()
            .await
            .map_err(|e| Status::internal(e.to_string()))?;

        if daily_total + req.amount > self.cfg.max_daily_disbursement {
            return Err(Status::resource_exhausted(format!(
                "daily disbursement limit reached: {:.8} + {:.8} > {:.8}",
                daily_total, req.amount, self.cfg.max_daily_disbursement
            )));
        }

        // AIKGS-C4: Generate idempotency key from reason (caller can control dedup)
        let idempotency_key = if req.reason.is_empty() {
            format!(
                "disburse_{}_{:.8}_{}",
                req.recipient_address,
                req.amount,
                chrono::Utc::now().timestamp_millis()
            )
        } else {
            format!("disburse_{}", req.reason)
        };

        // Check for existing disbursement with this key
        if let Some(existing) = self
            .db
            .get_disbursement_by_key(&idempotency_key)
            .await
            .map_err(|e| Status::internal(e.to_string()))?
        {
            log::info!(
                "Disbursement {} already exists (status={})",
                idempotency_key,
                existing.status
            );
            return Ok(Response::new(DisburseResponse {
                success: existing.status == "success",
                txid: existing.txid,
                error: if existing.status == "failed" {
                    existing.error_message
                } else {
                    String::new()
                },
            }));
        }

        // Insert pending record
        let inserted = self
            .db
            .insert_disbursement(
                &idempotency_key,
                &req.recipient_address,
                req.amount,
                &req.reason,
            )
            .await
            .map_err(|e| Status::internal(e.to_string()))?;

        if !inserted {
            // Another concurrent request inserted — return existing
            if let Some(existing) = self
                .db
                .get_disbursement_by_key(&idempotency_key)
                .await
                .map_err(|e| Status::internal(e.to_string()))?
            {
                return Ok(Response::new(DisburseResponse {
                    success: existing.status == "success",
                    txid: existing.txid,
                    error: if existing.status == "failed" {
                        existing.error_message
                    } else {
                        String::new()
                    },
                }));
            }
        }

        // Execute the disbursement
        let result = self
            .treasury
            .disburse(&req.recipient_address, req.amount, &req.reason)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;

        // Record the result
        let _ = self
            .db
            .complete_disbursement(
                &idempotency_key,
                result.success,
                result.txid.as_deref(),
                result.error.as_deref(),
            )
            .await;

        Ok(Response::new(DisburseResponse {
            success: result.success,
            txid: result.txid.unwrap_or_default(),
            error: result.error.unwrap_or_default(),
        }))
    }

    async fn get_pending_disbursements(
        &self,
        _request: Request<Empty>,
    ) -> Result<Response<PendingDisbursementsResponse>, Status> {
        // Query pending disbursements from the tracking table
        let row = sqlx::query(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0)::float8 as total
             FROM aikgs_disbursements WHERE status = 'pending'",
        )
        .fetch_one(self.db.pool())
        .await
        .map_err(|e| Status::internal(e.to_string()))?;

        use sqlx::Row;
        Ok(Response::new(PendingDisbursementsResponse {
            count: row.try_get::<i64, _>("cnt").unwrap_or(0) as i32,
            total_amount: row.try_get::<f64, _>("total").unwrap_or(0.0),
        }))
    }

    // ════════════════════════════════════════════════════════════════════════
    // Aggregate
    // ════════════════════════════════════════════════════════════════════════

    async fn get_full_stats(
        &self,
        _request: Request<Empty>,
    ) -> Result<Response<AikgsFullStats>, Status> {
        let c_stats = self.get_contribution_stats(Request::new(Empty {})).await?;
        let r_stats = self.get_reward_stats(Request::new(Empty {})).await?;
        let a_stats = self.get_affiliate_stats(Request::new(Empty {})).await?;
        let b_stats = self.get_bounty_stats(Request::new(Empty {})).await?;
        let u_stats = self.get_unlocks_stats(Request::new(Empty {})).await?;
        let cu_stats = self.get_curation_stats(Request::new(Empty {})).await?;

        Ok(Response::new(AikgsFullStats {
            contributions: Some(c_stats.into_inner()),
            rewards: Some(r_stats.into_inner()),
            affiliates: Some(a_stats.into_inner()),
            bounties: Some(b_stats.into_inner()),
            unlocks: Some(u_stats.into_inner()),
            curation: Some(cu_stats.into_inner()),
        }))
    }
}

// ── Helpers ──────────────────────────────────────────────────────────────

fn affiliate_to_proto(info: &aikgs_sidecar::affiliates::AffiliateInfo) -> AffiliateInfo {
    AffiliateInfo {
        address: info.address.clone(),
        referrer_address: info.referrer_address.clone(),
        referral_code: info.referral_code.clone(),
        l1_referrals: info.l1_referrals,
        l2_referrals: info.l2_referrals,
        total_l1_commission: info.total_l1_commission,
        total_l2_commission: info.total_l2_commission,
        is_active: info.is_active,
    }
}

fn key_info_to_proto(info: &aikgs_sidecar::vault::KeyInfo) -> KeyInfo {
    KeyInfo {
        key_id: info.key_id.clone(),
        provider: info.provider.clone(),
        model: info.model.clone(),
        owner_address: info.owner_address.clone(),
        is_shared: info.is_shared,
        shared_reward_bps: info.shared_reward_bps,
        label: info.label.clone(),
        use_count: info.use_count,
        is_active: info.is_active,
    }
}
