// ─── QBC LAUNCHPAD — API Layer with Mock Fallback ──────────────────────────────
//
// When NEXT_PUBLIC_LAUNCHPAD_MOCK === 'true', all functions fall back to the
// LaunchpadMockEngine so the UI works without a running backend.

import { get, post } from "./api";
import type {
  Project,
  ProjectTier,
  DDReport,
  EcosystemHealth,
  ContractType,
  AllocationItem,
  PresaleType,
  MGTMilestoneType,
  LeaderboardTab,
  Vouch,
  PortfolioInvestment,
} from "@/components/launchpad/types";

/* ── Mock toggle ─────────────────────────────────────────────────────────── */

const USE_MOCK = process.env.NEXT_PUBLIC_LAUNCHPAD_MOCK === "true";

/** Lazy-loaded mock engine — only imported when mock mode is active. */
async function getMockEngine() {
  const { LaunchpadMockEngine } = await import(
    "@/components/launchpad/mock-engine"
  );
  return LaunchpadMockEngine.getInstance();
}

/* ── Deploy Contract ─────────────────────────────────────────────────────── */

export interface DeployContractRequest {
  contractType: ContractType;
  name: string;
  symbol: string;
  description: string;
  fullDescription: string;
  category: string;
  totalSupply: number;
  decimals: number;
  deployer: string;
  allocations: AllocationItem[];
  mgtEnabled: boolean;
  mgtTranches: Array<{
    percent: number;
    milestoneType: MGTMilestoneType;
    milestoneTarget: number;
  }>;
  presaleEnabled: boolean;
  presaleType: PresaleType;
  presaleTokenPercent: number;
  presalePrice: number;
  presaleHardCap: number;
  presaleSoftCap: number;
  liquidityLockDays: number;
  liquidityPercent: number;
  qaslEnabled: boolean;
  qaslWindowSize: number;
  website: string;
  twitter: string;
  telegram: string;
  discord: string;
  github: string;
  whitepaper: string;
  teamMembers: Array<{
    name: string;
    role: string;
    twitter: string;
    wallet: string;
  }>;
}

export interface DeployContractResponse {
  success: boolean;
  message: string;
  contract_id: string;
  deployer: string;
  contract_type: string;
  block_height: number;
  fee_paid: string;
}

export async function deployContract(
  req: DeployContractRequest,
): Promise<DeployContractResponse> {
  if (USE_MOCK) {
    // Simulate a 2-second deployment
    await new Promise((r) => setTimeout(r, 2000));
    const hex = (len: number) => {
      let h = "";
      for (let i = 0; i < len; i++)
        h += "0123456789abcdef"[Math.floor(Math.random() * 16)];
      return h;
    };
    return {
      success: true,
      message: "Contract deployed (mock)",
      contract_id: "QBC1" + hex(36),
      deployer: req.deployer,
      contract_type: req.contractType,
      block_height: 19247 + Math.floor(Math.random() * 100),
      fee_paid: "1.0",
    };
  }

  return post<DeployContractResponse>("/contracts/deploy", {
    contract_type: req.contractType,
    contract_code: {
      name: req.name,
      symbol: req.symbol,
      description: req.description,
      full_description: req.fullDescription,
      category: req.category,
      total_supply: req.totalSupply,
      decimals: req.decimals,
      allocations: req.allocations.map((a) => ({
        label: a.label,
        percent: a.percent,
        address: a.address,
        vesting_cliff_days: a.vestingCliffDays,
        vesting_duration_days: a.vestingDurationDays,
      })),
      mgt_enabled: req.mgtEnabled,
      mgt_tranches: req.mgtTranches.map((t) => ({
        percent: t.percent,
        milestone_type: t.milestoneType,
        milestone_target: t.milestoneTarget,
      })),
      presale_enabled: req.presaleEnabled,
      presale_type: req.presaleType,
      presale_token_percent: req.presaleTokenPercent,
      presale_price: req.presalePrice,
      presale_hard_cap: req.presaleHardCap,
      presale_soft_cap: req.presaleSoftCap,
      liquidity_lock_days: req.liquidityLockDays,
      liquidity_percent: req.liquidityPercent,
      qasl_enabled: req.qaslEnabled,
      qasl_window_size: req.qaslWindowSize,
      website: req.website,
      twitter: req.twitter,
      telegram: req.telegram,
      discord: req.discord,
      github: req.github,
      whitepaper: req.whitepaper,
      team_members: req.teamMembers,
    },
    deployer: req.deployer,
  });
}

/* ── Get Projects ────────────────────────────────────────────────────────── */

export async function getProjects(): Promise<Project[]> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    return engine.getProjects();
  }

  const result = await get<{ projects: Project[] }>("/contracts/projects");
  return result.projects;
}

/* ── Get Single Project ──────────────────────────────────────────────────── */

export async function getProject(address: string): Promise<Project | null> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    return engine.getProject(address) ?? null;
  }

  return await get<Project>(`/contracts/project/${address}`);
}

/* ── QPCS Scoring ────────────────────────────────────────────────────────── */

export interface QPCSScoreResponse {
  address: string;
  score: number;
  components: {
    bytecode_size_score: number;
    deployment_age_score: number;
    tx_count_score: number;
    holder_count_score: number;
  };
  computed_at: number;
}

export async function getProjectScore(
  address: string,
): Promise<QPCSScoreResponse> {
  if (USE_MOCK) {
    return {
      address,
      score: 42.5 + Math.random() * 40,
      components: {
        bytecode_size_score: 6,
        deployment_age_score: 3,
        tx_count_score: 4,
        holder_count_score: 2,
      },
      computed_at: Date.now() / 1000,
    };
  }

  return get<QPCSScoreResponse>(`/contracts/score/${address}`);
}

/* ── DD Report Submission ────────────────────────────────────────────────── */

export interface SubmitDDReportRequest {
  project_address: string;
  author: string;
  category: string;
  title: string;
  content: string;
}

export interface SubmitDDReportResponse {
  success: boolean;
  report_id: string;
  message: string;
}

export async function submitDDReport(
  req: SubmitDDReportRequest,
): Promise<SubmitDDReportResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 800));
    const hex = (len: number) => {
      let h = "";
      for (let i = 0; i < len; i++)
        h += "0123456789abcdef"[Math.floor(Math.random() * 16)];
      return h;
    };
    return {
      success: true,
      report_id: hex(32),
      message: "DD report submitted (mock). Will be stored on QVM when backend is connected.",
    };
  }

  return post<SubmitDDReportResponse>("/contracts/dd-report", req);
}

/* ── Ecosystem Health ────────────────────────────────────────────────────── */

export async function getEcosystemHealth(): Promise<EcosystemHealth> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    return engine.getEcosystemHealth();
  }

  const chainInfo = await get<{
    height: number;
    difficulty: number;
    peers: number;
    mempool_size: number;
    total_supply: number;
  }>("/chain/info");

  return {
    status: "optimal",
    blockHeight: chainInfo.height,
    networkHashrate: chainInfo.difficulty,
    memPoolDepth: chainInfo.mempool_size,
    susyAlignment: 0,
    peerCount: chainInfo.peers,
    totalProjectsLaunched: 0,
    totalLiquidityLockedQusd: 0,
    totalQbcDomains: 0,
    totalDDReports: 0,
    totalReputationStakes: 0,
    qbcQusdPrice: 0,
    avgQpcs: 0,
    latestLaunch: null,
  };
}

/* ── Leaderboard ─────────────────────────────────────────────────────────── */

export async function getLeaderboard(
  tab: LeaderboardTab,
): Promise<Project[]> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    switch (tab) {
      case "qpcs":
        return engine.getLeaderboardQPCS();
      case "raises":
        return engine.getLeaderboardRaises();
      case "locks":
        return engine.getLeaderboardLocks();
      case "growth":
        return engine.getLeaderboardGrowth();
      case "reputation":
        return engine.getLeaderboardReputation();
    }
  }

  const result = await get<{ projects: Project[] }>(
    `/contracts/leaderboard/${tab}`,
  );
  return result.projects;
}

/* ── DD Reports (all) ────────────────────────────────────────────────────── */

export async function getAllDDReports(): Promise<DDReport[]> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    return engine.getAllDDReports();
  }

  const result = await get<{ reports: DDReport[] }>("/contracts/dd-reports");
  return result.reports;
}

/* ── Vouches (all) ───────────────────────────────────────────────────────── */

export async function getAllVouches(): Promise<Vouch[]> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    return engine.getAllVouches();
  }

  const result = await get<{ vouches: Vouch[] }>("/contracts/vouches");
  return result.vouches;
}

/* ── Ecosystem Edges ─────────────────────────────────────────────────────── */

export async function getEcosystemEdges(): Promise<
  Array<{
    source: string;
    target: string;
    type: string;
    weight: number;
  }>
> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    return engine.getEcosystemEdges();
  }

  const result = await get<{
    edges: Array<{
      source: string;
      target: string;
      type: string;
      weight: number;
    }>;
  }>("/contracts/ecosystem/edges");
  return result.edges;
}

/* ── Projects by Tier ────────────────────────────────────────────────────── */

export async function getProjectsByTier(
  tier: ProjectTier,
): Promise<Project[]> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    return engine.getProjectsByTier(tier);
  }

  const result = await get<{ projects: Project[] }>(
    `/contracts/projects?tier=${tier}`,
  );
  return result.projects;
}

/* ── Projects with Presale ───────────────────────────────────────────────── */

export async function getProjectsWithPresale(): Promise<Project[]> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    return engine.getProjectsWithPresale();
  }

  const result = await get<{ projects: Project[] }>(
    "/contracts/projects?presale=true",
  );
  return result.projects;
}

/* ── Vouched Projects ────────────────────────────────────────────────────── */

export async function getProjectsVouched(): Promise<Project[]> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    return engine.getProjectsVouched();
  }

  const result = await get<{ projects: Project[] }>(
    "/contracts/projects?vouched=true",
  );
  return result.projects;
}

/* ── Verified Projects ───────────────────────────────────────────────────── */

export async function getProjectsVerified(): Promise<Project[]> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    return engine.getProjectsVerified();
  }

  const result = await get<{ projects: Project[] }>(
    "/contracts/projects?verified=true",
  );
  return result.projects;
}

/* ── Domain Projects ─────────────────────────────────────────────────────── */

export async function getProjectsWithDomain(): Promise<Project[]> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    return engine.getProjectsWithDomain();
  }

  const result = await get<{ projects: Project[] }>(
    "/contracts/projects?domain=true",
  );
  return result.projects;
}

/* ── Portfolio ───────────────────────────────────────────────────────────── */

export async function getMyDeployed(): Promise<Project[]> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    return engine.getMyDeployed();
  }

  const result = await get<{ projects: Project[] }>(
    "/contracts/portfolio/deployed",
  );
  return result.projects;
}

export async function getMyInvestments(): Promise<PortfolioInvestment[]> {
  if (USE_MOCK) {
    const engine = await getMockEngine();
    return engine.getMyInvestments();
  }

  const result = await get<{ investments: PortfolioInvestment[] }>(
    "/contracts/portfolio/investments",
  );
  return result.investments;
}
