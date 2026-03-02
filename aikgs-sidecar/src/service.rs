//! gRPC service implementation — bridges proto messages to business logic modules.

use std::sync::Arc;
use tonic::{Request, Response, Status};

use aikgs_sidecar::config::AikgsConfig;
use aikgs_sidecar::db::Db;
use aikgs_sidecar::rewards::RewardEngine;
use aikgs_sidecar::scorer::Scorer;
use aikgs_sidecar::treasury::TreasuryClient;
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

        // Trigger treasury disbursement (fire-and-forget)
        if result.reward_amount > 0.0 {
            let node_url = self.treasury.node_rpc_url().to_string();
            let treasury = TreasuryClient::new(&node_url);
            let addr = result.contributor_address.clone();
            let amount = result.reward_amount;
            let cid = result.contribution_id;
            tokio::spawn(async move {
                if let Err(e) = treasury
                    .disburse(&addr, amount, &format!("aikgs_contribution_{cid}"))
                    .await
                {
                    log::warn!("Treasury disbursement failed: {e}");
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
        let limit = if req.limit > 0 { req.limit } else { 50 };
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
        let limit = request.into_inner().limit.max(1).min(100);
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
        let limit = request.into_inner().limit.max(1).min(100);
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
        let limit = if req.limit > 0 { req.limit } else { 50 };
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
        let has = aikgs_sidecar::unlocks::UnlocksManager::has_feature(&self.db, &req.address, &req.feature)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(HasFeatureResponse { has_feature: has }))
    }

    async fn get_unlocks_leaderboard(
        &self,
        request: Request<UnlocksLeaderboardRequest>,
    ) -> Result<Response<UnlocksLeaderboardResponse>, Status> {
        let limit = request.into_inner().limit.max(1).min(100);
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

    async fn get_api_key(
        &self,
        request: Request<GetKeyRequest>,
    ) -> Result<Response<DecryptedKeyResponse>, Status> {
        let vault = self
            .vault
            .as_ref()
            .ok_or_else(|| Status::unavailable("vault not configured"))?;
        let key_id = &request.into_inner().key_id;
        let dk = vault
            .get_key(&self.db, key_id)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
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

    async fn disburse(
        &self,
        request: Request<DisburseRequest>,
    ) -> Result<Response<DisburseResponse>, Status> {
        let req = request.into_inner();
        let result = self
            .treasury
            .disburse(&req.recipient_address, req.amount, &req.reason)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
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
        // Pending disbursements = rewards with no corresponding treasury tx
        // For now, this is informational — the sidecar disburses immediately
        Ok(Response::new(PendingDisbursementsResponse {
            count: 0,
            total_amount: 0.0,
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
