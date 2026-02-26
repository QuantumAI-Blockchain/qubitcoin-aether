// ─── QBC LAUNCHPAD — Type Definitions ─────────────────────────────────────────

/* ── Enums / Unions ───────────────────────────────────────────────────────── */

export type ContractType =
  | "susy_governance"
  | "governance"
  | "vesting_reflection"
  | "fixed_governance"
  | "vesting"
  | "qrc20_standard"
  | "deflationary"
  | "fair_launch";

export type ProjectTier = "seed" | "early" | "growth" | "established" | "protocol";

export type QpcsGrade = "rejected" | "restricted" | "basic" | "verified" | "quantum_grade";

export type PresaleType = "standard_ido" | "whitelist_ido" | "dutch_auction" | "fair_launch";

export type MGTMilestoneType =
  | "holder_count"
  | "dex_volume"
  | "liquidity_depth"
  | "susy_streak"
  | "governance_passed"
  | "qpcs_sustained"
  | "price_sustained"
  | "community_vote";

export type DDCategory = "contract" | "team" | "tokenomics" | "liquidity" | "utility" | "community";

export type CommunityVerdict = "verified" | "flagged" | "under_review" | "no_reports";

export type EhgStatus = "optimal" | "degraded" | "critical";

export type LaunchpadView =
  | "discover"
  | "deploy"
  | "token"
  | "leaderboard"
  | "ecosystem"
  | "cdd"
  | "portfolio";

export type ILLPSignal =
  | "prohibited"
  | "irrational"
  | "short_term"
  | "minimum"
  | "acceptable"
  | "recommended"
  | "excellent"
  | "protocol_grade";

export type DeployStep = 1 | 2 | 3 | 4 | 5 | 6 | 7;

export type VouchStatus = "active" | "completed_success" | "slashed" | "withdrawn";
export type TrancheStatus = "locked" | "unlocked" | "released";
export type PresaleStatus = "upcoming" | "active" | "completed" | "failed";
export type LeaderboardTab = "qpcs" | "raises" | "locks" | "growth" | "reputation";

/* ── QPCS Components ──────────────────────────────────────────────────────── */

export interface QPCSComponents {
  liquidityLock: number;          // 0–25
  teamVesting: number;            // 0–20
  tokenomicsDistribution: number; // 0–15
  contractComplexity: number;     // 0–10
  presaleStructure: number;       // 0–10
  deployerHistory: number;        // 0–8
  socialVerification: number;     // 0–7
  susyAtDeploy: number;           // 0–5
}

/* ── Allocation / Tokenomics ──────────────────────────────────────────────── */

export interface AllocationItem {
  label: string;
  percent: number;
  address: string;
  vestingCliffDays: number;
  vestingDurationDays: number;
  color: string;
}

export interface VestingSchedule {
  beneficiary: string;
  label: string;
  totalTokens: number;
  cliffDays: number;
  vestingDays: number;
  startTime: number;
  released: number;
  releasable: number;
}

/* ── Milestone-Gated Treasury ─────────────────────────────────────────────── */

export interface MGTTranche {
  index: number;
  tokens: number;
  percent: number;
  milestoneType: MGTMilestoneType;
  milestoneTarget: number;
  milestoneCurrentValue: number;
  status: TrancheStatus;
  unlockedAt: number | null;
  releasedAt: number | null;
  releaseTxHash: string | null;
}

/* ── Reputation Vouching ──────────────────────────────────────────────────── */

export interface Vouch {
  voucherAddress: string;
  voucherProjectName: string;
  voucherProjectAddress: string;
  voucherTier: ProjectTier;
  voucherQpcs: number;
  stakeAmountQusd: number;
  note: string;
  timestamp: number;
  txHash: string;
  status: VouchStatus;
  earningsQusd: number;
}

/* ── Community Due Diligence ──────────────────────────────────────────────── */

export interface DDReport {
  id: string;
  projectAddress: string;
  author: string;
  authorQbcBalance: number;
  category: DDCategory;
  title: string;
  content: string;
  timestamp: number;
  txHash: string;
  positiveVotes: number;
  negativeVotes: number;
  positivePercent: number;
  outcome: "verified" | "flagged" | "neutral" | "pending";
}

/* ── Presale ──────────────────────────────────────────────────────────────── */

export interface Presale {
  id: string;
  projectAddress: string;
  type: PresaleType;
  tokenPrice: number;
  hardCap: number;
  softCap: number;
  raised: number;
  startBlock: number;
  endBlock: number;
  startTime: number;
  endTime: number;
  minContribution: number;
  maxContribution: number;
  vestingCliffDays: number;
  vestingDurationDays: number;
  whitelistEnabled: boolean;
  participants: number;
  status: PresaleStatus;
  tokensForSale: number;
  tokensDistributed: number;
  startPrice?: number;
  endPrice?: number;
  priceDecayRate?: number;
}

/* ── Main Project Interface ───────────────────────────────────────────────── */

export interface Project {
  address: string;
  name: string;
  symbol: string;
  decimals: number;
  totalSupply: number;
  type: ContractType;
  tier: ProjectTier;
  qpcs: number;
  qpcsGrade: QpcsGrade;
  qpcsComponents: QPCSComponents;
  qpcsHistory: Array<{ date: string; score: number }>;
  deployer: string;
  deployedBlock: number;
  deployedAt: number;
  deployTxHash: string;
  dilithiumSig: string;
  templateVersion: string;
  logoUrl: string | null;
  description: string;
  fullDescription: string;
  website: string | null;
  twitter: string | null;
  telegram: string | null;
  discord: string | null;
  github: string | null;
  whitepaper: string | null;
  qbcDomain: string | null;
  dnaFingerprint: string;
  lastPrice: number;
  price24hChange: number;
  marketCap: number;
  volume24h: number;
  holderCount: number;
  liquidityLockedQusd: number;
  liquidityLockDays: number;
  liquidityLockExpiry: number;
  illpFeePaid: number;
  qaslEnabled: boolean;
  qaslLaunchBlock: number | null;
  qaslMaxBuyPercent: number;
  qaslFeeMultiplier: number;
  qaslSnipePenalty: number;
  susyAtDeploy: number;
  ehgAtDeploy: EhgStatus;
  graduationHistory: Array<{ tier: ProjectTier; block: number; timestamp: number }>;
  tokenomics: AllocationItem[];
  mgtTranches: MGTTranche[];
  vestingSchedules: VestingSchedule[];
  vouches: Vouch[];
  ddReports: DDReport[];
  communityVerdict: CommunityVerdict;
  priceHistory: Array<{ time: number; price: number }>;
  topHolders: Array<{ address: string; balance: number; percent: number }>;
  presale: Presale | null;
}

/* ── Ecosystem Health ─────────────────────────────────────────────────────── */

export interface EcosystemHealth {
  status: EhgStatus;
  blockHeight: number;
  networkHashrate: number;
  memPoolDepth: number;
  susyAlignment: number;
  peerCount: number;
  totalProjectsLaunched: number;
  totalLiquidityLockedQusd: number;
  totalQbcDomains: number;
  totalDDReports: number;
  totalReputationStakes: number;
  qbcQusdPrice: number;
  avgQpcs: number;
  latestLaunch: { name: string; symbol: string; time: number } | null;
}

/* ── ILLP Calculation ─────────────────────────────────────────────────────── */

export interface ILLPCalcResult {
  lockDays: number;
  feeQusd: number;
  qpcsImpact: number;
  signal: ILLPSignal;
  treasuryAmount: number;
  burnAmount: number;
}

/* ── Contract Type Config (Admin) ─────────────────────────────────────────── */

export interface ContractTypeConfig {
  type: ContractType;
  label: string;
  icon: string;
  description: string;
  complexity: number;
  deployFeeQbc: number;
  maxQpcs: number;
  features: string[];
  recommended: boolean;
  uniqueToQbc: boolean;
}

/* ── Tier Config ──────────────────────────────────────────────────────────── */

export interface TierConfig {
  tier: ProjectTier;
  label: string;
  icon: string;
  color: string;
  glowColor: string;
  minQpcs: number;
  minHolders: number;
  minLiquidityQusd: number;
  minLiquidityLockDays: number;
}

/* ── Leaderboard ──────────────────────────────────────────────────────────── */

export interface LeaderboardEntry {
  rank: number;
  project: Project;
  previousRank: number | null;
  metric: number;
}

/* ── Deploy Wizard Form State ─────────────────────────────────────────────── */

export interface DeployFormState {
  step: DeployStep;
  contractType: ContractType | null;
  // identity
  name: string;
  symbol: string;
  description: string;
  fullDescription: string;
  category: string;
  website: string;
  twitter: string;
  telegram: string;
  discord: string;
  github: string;
  whitepaper: string;
  logoPreview: string | null;
  teamMembers: Array<{ name: string; role: string; twitter: string; wallet: string }>;
  // token
  totalSupply: number;
  decimals: number;
  // tokenomics
  allocations: AllocationItem[];
  mgtEnabled: boolean;
  mgtTranches: Array<{ percent: number; milestoneType: MGTMilestoneType; milestoneTarget: number }>;
  // presale
  presaleEnabled: boolean;
  presaleType: PresaleType;
  presaleTokenPercent: number;
  presalePrice: number;
  presaleHardCap: number;
  presaleSoftCap: number;
  presaleMinContribution: number;
  presaleMaxContribution: number;
  presaleVestingCliffDays: number;
  presaleVestingDurationDays: number;
  // launch
  liquidityLockDays: number;
  liquidityPercent: number;
  qaslEnabled: boolean;
  qaslWindowStart: number;
  qaslWindowEnd: number;
  qaslMaxBuyPercent: number;
  qaslFeeMultiplier: number;
  qaslSnipePenalty: number;
}

/* ── Fee Config ───────────────────────────────────────────────────────────── */

export interface LaunchpadFeeConfig {
  protocolTreasuryAddress: string;
  treasurySplitPercent: number;      // 40 — rest is burned
  baseFeeQbc: number;                // minimum deploy fee
  illpBaseQusd: number;              // base ILLP fee
  presaleFeePercent: number;         // % of raise taken as fee
  ddReportMinQbc: number;            // min QBC to submit DD report
  vouchMinQusd: number;              // min QUSD to vouch
  vouchLockDays: number;             // minimum vouch stake duration
  vouchRewardPercent: number;        // % of launchpad fees to voucher
  vouchSlashPercent: number;         // % slashed on rug
}

/* ── Portfolio ────────────────────────────────────────────────────────────── */

export interface PortfolioInvestment {
  projectAddress: string;
  project: Project;
  investedQusd: number;
  tokensReceived: number;
  currentValue: number;
  pnl: number;
  pnlPercent: number;
  vestingProgress: number;
}

export interface PortfolioVouch {
  project: Project;
  vouch: Vouch;
}
