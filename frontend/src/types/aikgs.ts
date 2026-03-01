/** Shared AIKGS type definitions — single source of truth for frontend. */

export interface ContributorProfile {
  address: string;
  reputation_points: number;
  level: number;
  level_name: string;
  total_contributions: number;
  best_streak: number;
  current_streak: number;
  gold_count: number;
  diamond_count: number;
  bounties_fulfilled: number;
  referrals: number;
  badges: string[];
  unlocked_features: string[];
}

export interface ContributionRecord {
  contribution_id: number;
  contributor_address: string;
  content_hash: string;
  knowledge_node_id: number | null;
  quality_score: number;
  novelty_score: number;
  combined_score: number;
  tier: "bronze" | "silver" | "gold" | "diamond";
  domain: string;
  reward_amount: number;
  block_height: number;
  timestamp: number;
  status: string;
}

export interface RewardBreakdown {
  base_reward: number;
  quality_multiplier: number;
  novelty_bonus: number;
  tier_multiplier: number;
  streak_multiplier: number;
  staking_boost: number;
  early_bonus: number;
  final_reward: number;
}

export interface AffiliateInfo {
  address: string;
  referrer_address: string | null;
  referral_code: string;
  l1_referrals: number;
  l2_referrals: number;
  total_l1_commission: number;
  total_l2_commission: number;
}

export interface BountyInfo {
  bounty_id: number;
  domain: string;
  description: string;
  reward_amount: number;
  boost_multiplier: number;
  status: string;
  expires_at: number;
  created_at?: number;
}

export interface StoredKeyInfo {
  key_id: string;
  provider: string;
  model: string;
  label: string;
  is_shared: boolean;
  use_count: number;
  is_active: boolean;
}

export interface LeaderboardEntry {
  rank: number;
  address: string;
  reputation_points: number;
  level: number;
  level_name: string;
  total_contributions: number;
}

export interface PoolStats {
  pool_balance: number;
  total_distributed: number;
  total_contributions: number;
  unique_contributors: number;
  tier_breakdown: { bronze: number; silver: number; gold: number; diamond: number };
}

export interface CurationRound {
  round_id: string;
  contribution_id: number;
  status: "pending" | "approved" | "rejected";
  votes_for: number;
  votes_against: number;
  reviews: Array<{ curator: string; approved: boolean; comment: string }>;
}
