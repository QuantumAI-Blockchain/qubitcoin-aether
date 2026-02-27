// ─── QBC LAUNCHPAD — React Query Hooks ────────────────────────────────────────
"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getProjects,
  getProject as apiGetProject,
  getProjectsByTier,
  getProjectsWithPresale,
  getProjectsVouched,
  getProjectsVerified,
  getProjectsWithDomain,
  getEcosystemHealth,
  getAllDDReports,
  getAllVouches,
  getLeaderboard,
  getEcosystemEdges,
  getMyDeployed,
  getMyInvestments,
} from "@/lib/launchpad-api";
import type { ProjectTier, LeaderboardTab } from "./types";

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
    queryFn: () => getProjects(),
    staleTime: 30_000,
  });
}

export function useProject(address: string | null) {
  return useQuery({
    queryKey: keys.project(address ?? ""),
    queryFn: () => apiGetProject(address ?? ""),
    enabled: !!address,
    staleTime: 10_000,
  });
}

export function useProjectsByTier(tier: ProjectTier) {
  return useQuery({
    queryKey: keys.projectsByTier(tier),
    queryFn: () => getProjectsByTier(tier),
    staleTime: 30_000,
  });
}

export function usePresaleProjects() {
  return useQuery({
    queryKey: keys.presaleProjects,
    queryFn: () => getProjectsWithPresale(),
    staleTime: 15_000,
  });
}

export function useVouchedProjects() {
  return useQuery({
    queryKey: keys.vouchedProjects,
    queryFn: () => getProjectsVouched(),
    staleTime: 30_000,
  });
}

export function useVerifiedProjects() {
  return useQuery({
    queryKey: keys.verifiedProjects,
    queryFn: () => getProjectsVerified(),
    staleTime: 30_000,
  });
}

export function useDomainProjects() {
  return useQuery({
    queryKey: keys.domainProjects,
    queryFn: () => getProjectsWithDomain(),
    staleTime: 30_000,
  });
}

export function useEcosystemHealth() {
  return useQuery({
    queryKey: keys.ecosystem,
    queryFn: () => getEcosystemHealth(),
    staleTime: 10_000,
  });
}

export function useAllDDReports() {
  return useQuery({
    queryKey: keys.ddReports,
    queryFn: () => getAllDDReports(),
    staleTime: 30_000,
  });
}

export function useAllVouches() {
  return useQuery({
    queryKey: keys.vouches,
    queryFn: () => getAllVouches(),
    staleTime: 30_000,
  });
}

export function useLeaderboard(tab: LeaderboardTab) {
  return useQuery({
    queryKey: keys.leaderboard(tab),
    queryFn: () => getLeaderboard(tab),
    staleTime: 30_000,
  });
}

export function useEcosystemEdges() {
  return useQuery({
    queryKey: keys.ecosystemEdges,
    queryFn: () => getEcosystemEdges(),
    staleTime: 60_000,
  });
}

export function useMyDeployed() {
  return useQuery({
    queryKey: keys.myDeployed,
    queryFn: () => getMyDeployed(),
    staleTime: 30_000,
  });
}

export function useMyInvestments() {
  return useQuery({
    queryKey: keys.myInvestments,
    queryFn: () => getMyInvestments(),
    staleTime: 30_000,
  });
}
