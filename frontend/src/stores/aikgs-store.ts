/** AIKGS (Aether Incentivized Knowledge Growth System) global state */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  ContributorProfile,
  ContributionRecord,
  AffiliateInfo,
  BountyInfo,
  StoredKeyInfo,
} from "@/types/aikgs";

// Re-export shared types so existing imports still work
export type { ContributorProfile, ContributionRecord, AffiliateInfo, BountyInfo, StoredKeyInfo };

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
