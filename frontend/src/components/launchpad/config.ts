// ─── QBC LAUNCHPAD — Admin-Extensible Configuration ───────────────────────────

import type {
  ContractTypeConfig,
  TierConfig,
  LaunchpadFeeConfig,
} from "./types";

/* ── Contract Types (admin can add new types) ─────────────────────────────── */

export const CONTRACT_TYPES: ContractTypeConfig[] = [
  {
    type: "susy_governance",
    label: "SUSY-Staked Governance",
    icon: "\u26A1",
    description:
      "Quantum SUSY-alignment staking with full governance. The most advanced token type, unique to QBC. Maximum QPCS potential.",
    complexity: 5,
    deployFeeQbc: 12,
    maxQpcs: 100,
    features: [
      "SUSY alignment staking",
      "Full governance (proposals + voting)",
      "Milestone-gated treasury",
      "Auto-compounding rewards",
      "Quantum entropy integration",
    ],
    recommended: true,
    uniqueToQbc: true,
  },
  {
    type: "governance",
    label: "Governance",
    icon: "\uD83C\uDFDB\uFE0F",
    description:
      "Full DAO governance with proposals, voting, and timelock. Standard for serious protocol tokens.",
    complexity: 4,
    deployFeeQbc: 8,
    maxQpcs: 95,
    features: [
      "Proposal creation",
      "Token-weighted voting",
      "Timelock execution",
      "Quorum thresholds",
    ],
    recommended: true,
    uniqueToQbc: false,
  },
  {
    type: "vesting_reflection",
    label: "Vesting + Reflection Hybrid",
    icon: "\uD83D\uDCC8",
    description:
      "Combines linear vesting with automatic holder reflections. Rewards long-term holders.",
    complexity: 4,
    deployFeeQbc: 8,
    maxQpcs: 90,
    features: [
      "Linear vesting schedules",
      "Auto-reflection to holders",
      "Anti-dump mechanics",
      "Configurable tax rates",
    ],
    recommended: false,
    uniqueToQbc: false,
  },
  {
    type: "fixed_governance",
    label: "Fixed Supply + Governance",
    icon: "\uD83D\uDC8E",
    description:
      "Fixed supply token with lightweight governance. No mint function, supply set at deployment.",
    complexity: 3,
    deployFeeQbc: 5,
    maxQpcs: 85,
    features: [
      "Fixed supply (no mint)",
      "Lightweight governance",
      "Token-weighted voting",
    ],
    recommended: false,
    uniqueToQbc: false,
  },
  {
    type: "vesting",
    label: "Vesting",
    icon: "\uD83D\uDD12",
    description:
      "Vesting-only token with cliff and linear unlock. Standard for team and investor allocations.",
    complexity: 3,
    deployFeeQbc: 5,
    maxQpcs: 80,
    features: [
      "Cliff period",
      "Linear vesting",
      "Multiple beneficiaries",
      "Revocable option",
    ],
    recommended: false,
    uniqueToQbc: false,
  },
  {
    type: "qrc20_standard",
    label: "QRC-20 Standard",
    icon: "\uD83D\uDCCA",
    description:
      "Standard fungible token. ERC-20 compatible on QVM. Basic but functional.",
    complexity: 2,
    deployFeeQbc: 2,
    maxQpcs: 70,
    features: ["Transfer", "Approve / TransferFrom", "Mint (optional)", "Burn (optional)"],
    recommended: false,
    uniqueToQbc: false,
  },
  {
    type: "deflationary",
    label: "Deflationary",
    icon: "\uD83D\uDD25",
    description:
      "Burn-on-transfer token. Supply decreases over time. Simple but effective scarcity mechanic.",
    complexity: 2,
    deployFeeQbc: 2,
    maxQpcs: 65,
    features: ["Auto-burn on transfer", "Configurable burn rate", "Total burn tracking"],
    recommended: false,
    uniqueToQbc: false,
  },
  {
    type: "fair_launch",
    label: "Fair Launch",
    icon: "\uD83D\uDE80",
    description:
      "No team allocation, no vesting, no presale. 100% to liquidity. By design, limits QPCS ceiling.",
    complexity: 1,
    deployFeeQbc: 1,
    maxQpcs: 60,
    features: [
      "100% to liquidity",
      "No team allocation",
      "No presale",
      "Immediate full circulation",
    ],
    recommended: false,
    uniqueToQbc: false,
  },
];

/* ── Tier Configuration ───────────────────────────────────────────────────── */

export const TIER_CONFIGS: TierConfig[] = [
  {
    tier: "seed",
    label: "Seed",
    icon: "\uD83E\uDEB4",
    color: "#64748b",
    glowColor: "#64748b40",
    minQpcs: 0,
    minHolders: 0,
    minLiquidityQusd: 0,
    minLiquidityLockDays: 0,
  },
  {
    tier: "early",
    label: "Early",
    icon: "\uD83C\uDF31",
    color: "#8b5cf6",
    glowColor: "#8b5cf640",
    minQpcs: 40,
    minHolders: 100,
    minLiquidityQusd: 10000,
    minLiquidityLockDays: 30,
  },
  {
    tier: "growth",
    label: "Growth",
    icon: "\uD83C\uDF33",
    color: "#10b981",
    glowColor: "#10b98140",
    minQpcs: 60,
    minHolders: 500,
    minLiquidityQusd: 50000,
    minLiquidityLockDays: 90,
  },
  {
    tier: "established",
    label: "Established",
    icon: "\uD83C\uDFDB\uFE0F",
    color: "#f59e0b",
    glowColor: "#f59e0b40",
    minQpcs: 80,
    minHolders: 2000,
    minLiquidityQusd: 200000,
    minLiquidityLockDays: 180,
  },
  {
    tier: "protocol",
    label: "Protocol",
    icon: "\u26A1",
    color: "#00d4ff",
    glowColor: "#00d4ff40",
    minQpcs: 90,
    minHolders: 10000,
    minLiquidityQusd: 1000000,
    minLiquidityLockDays: 365,
  },
];

/* ── Fee Configuration ────────────────────────────────────────────────────── */

export const FEE_CONFIG: LaunchpadFeeConfig = {
  protocolTreasuryAddress:
    process.env.NEXT_PUBLIC_LAUNCHPAD_TREASURY ?? "QBC1treasury000000000000000000000000000000",
  treasurySplitPercent: 40,
  baseFeeQbc: 0.5,
  illpBaseQusd: 100,
  presaleFeePercent: 2.5,
  ddReportMinQbc: 500,
  vouchMinQusd: 1000,
  vouchLockDays: 90,
  vouchRewardPercent: 0.5,
  vouchSlashPercent: 50,
};

/* ── QPCS Weight Configuration ────────────────────────────────────────────── */

export const QPCS_WEIGHTS = {
  liquidityLock: { max: 25, label: "Liquidity Lock" },
  teamVesting: { max: 20, label: "Team Vesting" },
  tokenomicsDistribution: { max: 15, label: "Tokenomics" },
  contractComplexity: { max: 10, label: "Contract Complexity" },
  presaleStructure: { max: 10, label: "Presale Structure" },
  deployerHistory: { max: 8, label: "Deployer History" },
  socialVerification: { max: 7, label: "Social Verification" },
  susyAtDeploy: { max: 5, label: "SUSY at Deploy" },
} as const;

/* ── ILLP Fee Tiers ───────────────────────────────────────────────────────── */

export const ILLP_TIERS = [
  { minDays: 0, maxDays: 29, signal: "prohibited" as const, feeQusd: 999999, qpcs: 0, label: "PROHIBITED", description: "Cannot deploy — minimum 30-day lock required" },
  { minDays: 30, maxDays: 89, signal: "irrational" as const, feeQusd: 5000, qpcs: 2, label: "IRRATIONAL", description: "Extreme fee discourages short locks" },
  { minDays: 90, maxDays: 179, signal: "short_term" as const, feeQusd: 2000, qpcs: 5, label: "SHORT TERM", description: "High fee signals low commitment" },
  { minDays: 180, maxDays: 364, signal: "minimum" as const, feeQusd: 500, qpcs: 10, label: "MINIMUM", description: "Acceptable but not impressive" },
  { minDays: 365, maxDays: 729, signal: "acceptable" as const, feeQusd: 200, qpcs: 15, label: "ACCEPTABLE", description: "Reasonable commitment, moderate fee" },
  { minDays: 730, maxDays: 1094, signal: "recommended" as const, feeQusd: 50, qpcs: 20, label: "RECOMMENDED", description: "Strong commitment, low fee" },
  { minDays: 1095, maxDays: 1459, signal: "excellent" as const, feeQusd: 10, qpcs: 23, label: "EXCELLENT", description: "Outstanding commitment, minimal fee" },
  { minDays: 1460, maxDays: 99999, signal: "protocol_grade" as const, feeQusd: 0, qpcs: 25, label: "PROTOCOL GRADE", description: "Maximum commitment, zero fee" },
] as const;

/* ── Categories ───────────────────────────────────────────────────────────── */

export const PROJECT_CATEGORIES = [
  "DeFi",
  "GameFi",
  "Infrastructure",
  "DAO",
  "RWA",
  "Social",
  "Identity",
  "AI / AGI",
  "Privacy",
  "Other",
] as const;

export const DD_CATEGORIES = [
  { key: "contract" as const, label: "Contract Review", icon: "\uD83D\uDCDC" },
  { key: "team" as const, label: "Team Analysis", icon: "\uD83D\uDC65" },
  { key: "tokenomics" as const, label: "Tokenomics", icon: "\uD83D\uDCC8" },
  { key: "liquidity" as const, label: "Liquidity", icon: "\uD83D\uDCA7" },
  { key: "utility" as const, label: "Utility", icon: "\u2699\uFE0F" },
  { key: "community" as const, label: "Community", icon: "\uD83D\uDC65" },
] as const;

/* ── Helpers ──────────────────────────────────────────────────────────────── */

export function getContractTypeConfig(type: string) {
  return CONTRACT_TYPES.find((c) => c.type === type);
}

export function getTierConfig(tier: string) {
  return TIER_CONFIGS.find((t) => t.tier === tier);
}

export function getQpcsGrade(score: number) {
  if (score >= 90) return "quantum_grade" as const;
  if (score >= 70) return "verified" as const;
  if (score >= 50) return "basic" as const;
  if (score >= 30) return "restricted" as const;
  return "rejected" as const;
}

export function getProjectTier(
  qpcs: number,
  holders: number,
  liquidityQusd: number,
  lockDays: number,
): "seed" | "early" | "growth" | "established" | "protocol" {
  for (let i = TIER_CONFIGS.length - 1; i >= 0; i--) {
    const t = TIER_CONFIGS[i];
    if (
      qpcs >= t.minQpcs &&
      holders >= t.minHolders &&
      liquidityQusd >= t.minLiquidityQusd &&
      lockDays >= t.minLiquidityLockDays
    ) {
      return t.tier;
    }
  }
  return "seed";
}
