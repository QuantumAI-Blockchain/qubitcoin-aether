// ─── QBC LAUNCHPAD — React Query Hooks ────────────────────────────────────────
"use client";

import { useQuery } from "@tanstack/react-query";
import { LaunchpadMockEngine } from "./mock-engine";
import type { ProjectTier, LeaderboardTab } from "./types";

const engine = LaunchpadMockEngine.getInstance();

/* ── Query Key Factory ────────────────────────────────────────────────────── */

const keys = {
  projects: ["launchpad", "projects"] as const,
  project: (addr: string) => ["launchpad", "project", addr] as const,
  projectsByTier: (tier: ProjectTier) => ["launchpad", "projects", "tier", tier] as const,
  presaleProjects: ["launchpad", "projects", "presale"] as const,
  vouchedProjects: ["launchpad", "projects", "vouched"] as const,
  verifiedProjects: ["launchpad", "projects", "verified"] as const,
  domainProjects: ["launchpad", "projects", "domains"] as const,
  ecosystem: ["launchpad", "ecosystem"] as const,
  ddReports: ["launchpad", "dd-reports"] as const,
  vouches: ["launchpad", "vouches"] as const,
  leaderboard: (tab: LeaderboardTab) => ["launchpad", "leaderboard", tab] as const,
  ecosystemEdges: ["launchpad", "ecosystem", "edges"] as const,
  myDeployed: ["launchpad", "portfolio", "deployed"] as const,
  myInvestments: ["launchpad", "portfolio", "investments"] as const,
};

/* ── Hooks ─────────────────────────────────────────────────────────────────── */

export function useProjects() {
  return useQuery({
    queryKey: keys.projects,
    queryFn: () => engine.getProjects(),
    staleTime: 30_000,
  });
}

export function useProject(address: string | null) {
  return useQuery({
    queryKey: keys.project(address ?? ""),
    queryFn: () => engine.getProject(address ?? ""),
    enabled: !!address,
    staleTime: 10_000,
  });
}

export function useProjectsByTier(tier: ProjectTier) {
  return useQuery({
    queryKey: keys.projectsByTier(tier),
    queryFn: () => engine.getProjectsByTier(tier),
    staleTime: 30_000,
  });
}

export function usePresaleProjects() {
  return useQuery({
    queryKey: keys.presaleProjects,
    queryFn: () => engine.getProjectsWithPresale(),
    staleTime: 15_000,
  });
}

export function useVouchedProjects() {
  return useQuery({
    queryKey: keys.vouchedProjects,
    queryFn: () => engine.getProjectsVouched(),
    staleTime: 30_000,
  });
}

export function useVerifiedProjects() {
  return useQuery({
    queryKey: keys.verifiedProjects,
    queryFn: () => engine.getProjectsVerified(),
    staleTime: 30_000,
  });
}

export function useDomainProjects() {
  return useQuery({
    queryKey: keys.domainProjects,
    queryFn: () => engine.getProjectsWithDomain(),
    staleTime: 30_000,
  });
}

export function useEcosystemHealth() {
  return useQuery({
    queryKey: keys.ecosystem,
    queryFn: () => engine.getEcosystemHealth(),
    staleTime: 10_000,
  });
}

export function useAllDDReports() {
  return useQuery({
    queryKey: keys.ddReports,
    queryFn: () => engine.getAllDDReports(),
    staleTime: 30_000,
  });
}

export function useAllVouches() {
  return useQuery({
    queryKey: keys.vouches,
    queryFn: () => engine.getAllVouches(),
    staleTime: 30_000,
  });
}

export function useLeaderboard(tab: LeaderboardTab) {
  return useQuery({
    queryKey: keys.leaderboard(tab),
    queryFn: () => {
      switch (tab) {
        case "qpcs": return engine.getLeaderboardQPCS();
        case "raises": return engine.getLeaderboardRaises();
        case "locks": return engine.getLeaderboardLocks();
        case "growth": return engine.getLeaderboardGrowth();
        case "reputation": return engine.getLeaderboardReputation();
      }
    },
    staleTime: 30_000,
  });
}

export function useEcosystemEdges() {
  return useQuery({
    queryKey: keys.ecosystemEdges,
    queryFn: () => engine.getEcosystemEdges(),
    staleTime: 60_000,
  });
}

export function useMyDeployed() {
  return useQuery({
    queryKey: keys.myDeployed,
    queryFn: () => engine.getMyDeployed(),
    staleTime: 30_000,
  });
}

export function useMyInvestments() {
  return useQuery({
    queryKey: keys.myInvestments,
    queryFn: () => engine.getMyInvestments(),
    staleTime: 30_000,
  });
}
