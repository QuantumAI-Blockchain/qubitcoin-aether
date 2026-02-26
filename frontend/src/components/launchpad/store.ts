// ─── QBC LAUNCHPAD — Zustand Store ────────────────────────────────────────────
"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  LaunchpadView,
  ProjectTier,
  QpcsGrade,
  DeployStep,
  ContractType,
  PresaleType,
  MGTMilestoneType,
  AllocationItem,
  LeaderboardTab,
} from "./types";

/* ── Default Allocations ──────────────────────────────────────────────────── */

const DEFAULT_ALLOCATIONS: AllocationItem[] = [
  { label: "Liquidity", percent: 30, address: "", vestingCliffDays: 0, vestingDurationDays: 0, color: "#00d4ff" },
  { label: "Team", percent: 15, address: "", vestingCliffDays: 90, vestingDurationDays: 365, color: "#f59e0b" },
  { label: "Ecosystem", percent: 25, address: "", vestingCliffDays: 0, vestingDurationDays: 180, color: "#10b981" },
  { label: "Presale", percent: 20, address: "", vestingCliffDays: 0, vestingDurationDays: 0, color: "#8b5cf6" },
  { label: "Marketing", percent: 10, address: "", vestingCliffDays: 0, vestingDurationDays: 0, color: "#ef4444" },
];

/* ── Store Interface ──────────────────────────────────────────────────────── */

interface LaunchpadStore {
  // Navigation
  view: LaunchpadView;
  setView: (v: LaunchpadView) => void;
  selectedProjectAddr: string | null;
  setSelectedProject: (addr: string | null) => void;

  // Discover filters
  tierFilter: ProjectTier | "all";
  setTierFilter: (t: ProjectTier | "all") => void;
  minQpcs: number;
  setMinQpcs: (n: number) => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  sortBy: "qpcs" | "marketCap" | "volume24h" | "holderCount" | "recent";
  setSortBy: (s: "qpcs" | "marketCap" | "volume24h" | "holderCount" | "recent") => void;
  showVouchedOnly: boolean;
  toggleVouchedOnly: () => void;
  showVerifiedOnly: boolean;
  toggleVerifiedOnly: () => void;
  showDomainsOnly: boolean;
  toggleDomainsOnly: () => void;
  showPresaleOnly: boolean;
  togglePresaleOnly: () => void;

  // Leaderboard
  leaderboardTab: LeaderboardTab;
  setLeaderboardTab: (t: LeaderboardTab) => void;

  // Token detail tab
  tokenDetailTab: string;
  setTokenDetailTab: (t: string) => void;

  // Deploy wizard
  deployStep: DeployStep;
  setDeployStep: (s: DeployStep) => void;
  deployContractType: ContractType | null;
  setDeployContractType: (t: ContractType | null) => void;
  deployName: string;
  setDeployName: (n: string) => void;
  deploySymbol: string;
  setDeploySymbol: (s: string) => void;
  deployDescription: string;
  setDeployDescription: (d: string) => void;
  deployFullDescription: string;
  setDeployFullDescription: (d: string) => void;
  deployCategory: string;
  setDeployCategory: (c: string) => void;
  deployWebsite: string;
  setDeployWebsite: (w: string) => void;
  deployTwitter: string;
  setDeployTwitter: (t: string) => void;
  deployTelegram: string;
  setDeployTelegram: (t: string) => void;
  deployDiscord: string;
  setDeployDiscord: (d: string) => void;
  deployGithub: string;
  setDeployGithub: (g: string) => void;
  deployWhitepaper: string;
  setDeployWhitepaper: (w: string) => void;
  deployLogoPreview: string | null;
  setDeployLogoPreview: (p: string | null) => void;
  deployTeamMembers: Array<{ name: string; role: string; twitter: string; wallet: string }>;
  setDeployTeamMembers: (m: Array<{ name: string; role: string; twitter: string; wallet: string }>) => void;
  deployTotalSupply: number;
  setDeployTotalSupply: (n: number) => void;
  deployDecimals: number;
  setDeployDecimals: (n: number) => void;
  deployAllocations: AllocationItem[];
  setDeployAllocations: (a: AllocationItem[]) => void;
  deployMgtEnabled: boolean;
  setDeployMgtEnabled: (b: boolean) => void;
  deployMgtTranches: Array<{ percent: number; milestoneType: MGTMilestoneType; milestoneTarget: number }>;
  setDeployMgtTranches: (t: Array<{ percent: number; milestoneType: MGTMilestoneType; milestoneTarget: number }>) => void;
  deployPresaleEnabled: boolean;
  setDeployPresaleEnabled: (b: boolean) => void;
  deployPresaleType: PresaleType;
  setDeployPresaleType: (t: PresaleType) => void;
  deployPresaleTokenPercent: number;
  setDeployPresaleTokenPercent: (n: number) => void;
  deployPresalePrice: number;
  setDeployPresalePrice: (n: number) => void;
  deployPresaleHardCap: number;
  setDeployPresaleHardCap: (n: number) => void;
  deployPresaleSoftCap: number;
  setDeployPresaleSoftCap: (n: number) => void;
  deployLiquidityLockDays: number;
  setDeployLiquidityLockDays: (n: number) => void;
  deployLiquidityPercent: number;
  setDeployLiquidityPercent: (n: number) => void;
  deployQaslEnabled: boolean;
  setDeployQaslEnabled: (b: boolean) => void;
  deployQaslWindowSize: number;
  setDeployQaslWindowSize: (n: number) => void;

  // UI state
  deploying: boolean;
  setDeploying: (b: boolean) => void;

  // Reset deploy
  resetDeploy: () => void;
}

/* ── Store ─────────────────────────────────────────────────────────────────── */

export const useLaunchpadStore = create<LaunchpadStore>()(
  persist(
    (set) => ({
      // Navigation
      view: "discover",
      setView: (v) => set({ view: v }),
      selectedProjectAddr: null,
      setSelectedProject: (addr) => set({ selectedProjectAddr: addr, view: addr ? "token" : "discover" }),

      // Discover
      tierFilter: "all",
      setTierFilter: (t) => set({ tierFilter: t }),
      minQpcs: 0,
      setMinQpcs: (n) => set({ minQpcs: n }),
      searchQuery: "",
      setSearchQuery: (q) => set({ searchQuery: q }),
      sortBy: "qpcs",
      setSortBy: (s) => set({ sortBy: s }),
      showVouchedOnly: false,
      toggleVouchedOnly: () => set((s) => ({ showVouchedOnly: !s.showVouchedOnly })),
      showVerifiedOnly: false,
      toggleVerifiedOnly: () => set((s) => ({ showVerifiedOnly: !s.showVerifiedOnly })),
      showDomainsOnly: false,
      toggleDomainsOnly: () => set((s) => ({ showDomainsOnly: !s.showDomainsOnly })),
      showPresaleOnly: false,
      togglePresaleOnly: () => set((s) => ({ showPresaleOnly: !s.showPresaleOnly })),

      // Leaderboard
      leaderboardTab: "qpcs",
      setLeaderboardTab: (t) => set({ leaderboardTab: t }),

      // Token detail
      tokenDetailTab: "overview",
      setTokenDetailTab: (t) => set({ tokenDetailTab: t }),

      // Deploy wizard
      deployStep: 1,
      setDeployStep: (s) => set({ deployStep: s }),
      deployContractType: null,
      setDeployContractType: (t) => set({ deployContractType: t }),
      deployName: "",
      setDeployName: (n) => set({ deployName: n }),
      deploySymbol: "",
      setDeploySymbol: (s) => set({ deploySymbol: s.toUpperCase().slice(0, 8) }),
      deployDescription: "",
      setDeployDescription: (d) => set({ deployDescription: d }),
      deployFullDescription: "",
      setDeployFullDescription: (d) => set({ deployFullDescription: d }),
      deployCategory: "DeFi",
      setDeployCategory: (c) => set({ deployCategory: c }),
      deployWebsite: "",
      setDeployWebsite: (w) => set({ deployWebsite: w }),
      deployTwitter: "",
      setDeployTwitter: (t) => set({ deployTwitter: t }),
      deployTelegram: "",
      setDeployTelegram: (t) => set({ deployTelegram: t }),
      deployDiscord: "",
      setDeployDiscord: (d) => set({ deployDiscord: d }),
      deployGithub: "",
      setDeployGithub: (g) => set({ deployGithub: g }),
      deployWhitepaper: "",
      setDeployWhitepaper: (w) => set({ deployWhitepaper: w }),
      deployLogoPreview: null,
      setDeployLogoPreview: (p) => set({ deployLogoPreview: p }),
      deployTeamMembers: [],
      setDeployTeamMembers: (m) => set({ deployTeamMembers: m }),
      deployTotalSupply: 1_000_000_000,
      setDeployTotalSupply: (n) => set({ deployTotalSupply: n }),
      deployDecimals: 18,
      setDeployDecimals: (n) => set({ deployDecimals: n }),
      deployAllocations: DEFAULT_ALLOCATIONS,
      setDeployAllocations: (a) => set({ deployAllocations: a }),
      deployMgtEnabled: false,
      setDeployMgtEnabled: (b) => set({ deployMgtEnabled: b }),
      deployMgtTranches: [],
      setDeployMgtTranches: (t) => set({ deployMgtTranches: t }),
      deployPresaleEnabled: false,
      setDeployPresaleEnabled: (b) => set({ deployPresaleEnabled: b }),
      deployPresaleType: "standard_ido",
      setDeployPresaleType: (t) => set({ deployPresaleType: t }),
      deployPresaleTokenPercent: 15,
      setDeployPresaleTokenPercent: (n) => set({ deployPresaleTokenPercent: n }),
      deployPresalePrice: 0.001,
      setDeployPresalePrice: (n) => set({ deployPresalePrice: n }),
      deployPresaleHardCap: 100000,
      setDeployPresaleHardCap: (n) => set({ deployPresaleHardCap: n }),
      deployPresaleSoftCap: 40000,
      setDeployPresaleSoftCap: (n) => set({ deployPresaleSoftCap: n }),
      deployLiquidityLockDays: 365,
      setDeployLiquidityLockDays: (n) => set({ deployLiquidityLockDays: n }),
      deployLiquidityPercent: 30,
      setDeployLiquidityPercent: (n) => set({ deployLiquidityPercent: n }),
      deployQaslEnabled: true,
      setDeployQaslEnabled: (b) => set({ deployQaslEnabled: b }),
      deployQaslWindowSize: 100,
      setDeployQaslWindowSize: (n) => set({ deployQaslWindowSize: n }),

      // UI
      deploying: false,
      setDeploying: (b) => set({ deploying: b }),

      // Reset
      resetDeploy: () =>
        set({
          deployStep: 1,
          deployContractType: null,
          deployName: "",
          deploySymbol: "",
          deployDescription: "",
          deployFullDescription: "",
          deployCategory: "DeFi",
          deployWebsite: "",
          deployTwitter: "",
          deployTelegram: "",
          deployDiscord: "",
          deployGithub: "",
          deployWhitepaper: "",
          deployLogoPreview: null,
          deployTeamMembers: [],
          deployTotalSupply: 1_000_000_000,
          deployDecimals: 18,
          deployAllocations: DEFAULT_ALLOCATIONS,
          deployMgtEnabled: false,
          deployMgtTranches: [],
          deployPresaleEnabled: false,
          deployPresaleType: "standard_ido",
          deployPresaleTokenPercent: 15,
          deployPresalePrice: 0.001,
          deployPresaleHardCap: 100000,
          deployPresaleSoftCap: 40000,
          deployLiquidityLockDays: 365,
          deployLiquidityPercent: 30,
          deployQaslEnabled: true,
          deployQaslWindowSize: 100,
          deploying: false,
        }),
    }),
    {
      name: "qbc-launchpad",
      partialize: (state: LaunchpadStore) => ({
        tierFilter: state.tierFilter,
        minQpcs: state.minQpcs,
        sortBy: state.sortBy,
        leaderboardTab: state.leaderboardTab,
      }),
    } as never,
  ),
);
