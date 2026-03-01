/** AIKGS (Aether Incentivized Knowledge Growth System) global state */
import { create } from "zustand";
import { persist } from "zustand/middleware";

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

interface AIKGSState {
  // Profile
  profile: ContributorProfile | null;
  setProfile: (p: ContributorProfile) => void;

  // Contributions
  recentContributions: ContributionRecord[];
  setRecentContributions: (c: ContributionRecord[]) => void;

  // Affiliate
  affiliateInfo: AffiliateInfo | null;
  setAffiliateInfo: (a: AffiliateInfo) => void;

  // Bounties
  openBounties: BountyInfo[];
  setOpenBounties: (b: BountyInfo[]) => void;

  // API Keys
  storedKeys: StoredKeyInfo[];
  setStoredKeys: (k: StoredKeyInfo[]) => void;

  // Reward pool
  poolBalance: number;
  totalDistributed: number;
  setPoolStats: (balance: number, distributed: number) => void;

  // UI state
  activeTab: "contribute" | "rewards" | "bounties" | "affiliate" | "keys";
  setActiveTab: (tab: AIKGSState["activeTab"]) => void;
}

export const useAIKGSStore = create<AIKGSState>()(
  persist(
    (set) => ({
      profile: null,
      setProfile: (p) => set({ profile: p }),

      recentContributions: [],
      setRecentContributions: (c) => set({ recentContributions: c }),

      affiliateInfo: null,
      setAffiliateInfo: (a) => set({ affiliateInfo: a }),

      openBounties: [],
      setOpenBounties: (b) => set({ openBounties: b }),

      storedKeys: [],
      setStoredKeys: (k) => set({ storedKeys: k }),

      poolBalance: 0,
      totalDistributed: 0,
      setPoolStats: (balance, distributed) =>
        set({ poolBalance: balance, totalDistributed: distributed }),

      activeTab: "contribute",
      setActiveTab: (tab) => set({ activeTab: tab }),
    }),
    {
      name: "qbc-aikgs",
      partialize: (state) => ({
        activeTab: state.activeTab,
      }),
    },
  ),
);
