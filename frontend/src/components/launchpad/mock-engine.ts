// ─── QBC LAUNCHPAD — Mock Data Engine ─────────────────────────────────────────

import type {
  Project,
  ProjectTier,
  QpcsGrade,
  ContractType,
  QPCSComponents,
  AllocationItem,
  VestingSchedule,
  MGTTranche,
  Vouch,
  DDReport,
  Presale,
  EcosystemHealth,
  EhgStatus,
  CommunityVerdict,
  DDCategory,
  MGTMilestoneType,
  PresaleStatus,
  TrancheStatus,
  VouchStatus,
  PortfolioInvestment,
} from "./types";
import { getQpcsGrade } from "./config";
import { calculateILLP } from "./shared";

/* ── Deterministic PRNG (mulberry32) ──────────────────────────────────────── */

function mulberry32(seed: number): () => number {
  let s = seed | 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rng = mulberry32(0xcafe_babe);
const rand = () => rng();
const randInt = (min: number, max: number) => Math.floor(rand() * (max - min + 1)) + min;
const pick = <T>(arr: T[]): T => arr[Math.floor(rand() * arr.length)];
const shuffle = <T>(arr: T[]): T[] => {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

/* ── Name Generation ──────────────────────────────────────────────────────── */

const PREFIXES = [
  "Alpha", "Nova", "Quantum", "Stellar", "Nexus", "Zenith", "Helix", "Aether",
  "Pulse", "Vortex", "Cipher", "Nebula", "Flux", "Prism", "Echo", "Axiom",
  "Quark", "Photon", "Vertex", "Sigma", "Delta", "Omega", "Zeta", "Krypton",
  "Orion", "Titan", "Plasma", "Fusion", "Neutron", "Proton", "Cosmo", "Lunar",
  "Solar", "Astral", "Qubit", "Parity", "Entropy", "Synapse", "Matrix", "Vector",
  "Tensor", "Scalar", "Fractal", "Spiral", "Radial", "Polar", "Nodal", "Lattice",
  "Crystal", "Carbon",
];

const SUFFIXES = [
  "Protocol", "Finance", "Network", "Labs", "Vault", "DAO", "Chain", "Exchange",
  "Swap", "Bridge", "Guard", "Shield", "Core", "Hub", "Link", "Gate", "Port",
  "Stack", "Flow", "Wave", "Pay", "Lend", "Stake", "Yield", "Farm",
];

const SYMBOLS = [
  "ALPH", "NOVA", "QNTM", "STLR", "NEXS", "ZNTH", "HELX", "AETH",
  "PULS", "VRTX", "CPHR", "NEBL", "FLUX", "PRSM", "ECHO", "AXOM",
  "QRKT", "PHTN", "VRTC", "SGMA", "DLTA", "OMGA", "ZETA", "KRYP",
  "ORIN", "TITN", "PLSM", "FUSN", "NTRN", "PRTN", "COSM", "LUNR",
  "SOLR", "ASTR", "QBIT", "PRTY", "ENTR", "SYNP", "MTRX", "VCTR",
  "TNSR", "SCLR", "FRCL", "SPRL", "RDAL", "POLR", "NODL", "LTCE",
  "CRST", "CRBN",
];

const DESCRIPTIONS = [
  "Quantum-secured DeFi protocol with SUSY-aligned staking and governance.",
  "Cross-chain liquidity aggregator powered by QBC bridge technology.",
  "Decentralised lending market with post-quantum collateral verification.",
  "GameFi ecosystem with on-chain physics simulation and quantum entropy.",
  "Privacy-preserving identity protocol using Dilithium-3 signatures.",
  "Yield optimiser with autonomous SUSY-balanced portfolio management.",
  "Decentralised autonomous organisation for quantum computing research.",
  "Real-world asset tokenisation with QVM compliance engine integration.",
  "Social token platform with Aether Tree AI-powered content curation.",
  "Infrastructure protocol for quantum-resistant messaging and data storage.",
];

const CATEGORIES = ["DeFi", "GameFi", "Infrastructure", "DAO", "RWA", "Social", "Identity", "AI / AGI", "Privacy"];

const MILESTONE_TYPES: MGTMilestoneType[] = [
  "holder_count", "dex_volume", "liquidity_depth", "susy_streak",
  "governance_passed", "qpcs_sustained", "price_sustained", "community_vote",
];

const DD_CATS: DDCategory[] = ["contract", "team", "tokenomics", "liquidity", "utility", "community"];

/* ── Address Generation ───────────────────────────────────────────────────── */

function genAddr(): string {
  let h = "QBC1";
  for (let i = 0; i < 36; i++) h += "0123456789abcdef"[randInt(0, 15)];
  return h;
}

function genTxHash(): string {
  let h = "0x";
  for (let i = 0; i < 64; i++) h += "0123456789abcdef"[randInt(0, 15)];
  return h;
}

function genDNA(): string {
  let h = "";
  for (let i = 0; i < 64; i++) h += "0123456789abcdef"[randInt(0, 15)];
  return h;
}

function genDilithiumSig(): string {
  let s = "dilithium3:";
  for (let i = 0; i < 128; i++) s += "0123456789abcdef"[randInt(0, 15)];
  return s;
}

/* ── Colour Palette for Allocations ───────────────────────────────────────── */

const ALLOC_COLORS = [
  "#00d4ff", "#f59e0b", "#10b981", "#8b5cf6", "#ef4444",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
];

/* ── Tier Distribution: 2 PROTOCOL, 8 ESTABLISHED, 15 GROWTH, 15 EARLY, 10 SEED */

const TIER_DISTRIBUTION: ProjectTier[] = [
  ...Array(2).fill("protocol" as const),
  ...Array(8).fill("established" as const),
  ...Array(15).fill("growth" as const),
  ...Array(15).fill("early" as const),
  ...Array(10).fill("seed" as const),
];

/* ── Contract Type Distribution ───────────────────────────────────────────── */

function contractForTier(tier: ProjectTier): ContractType {
  if (tier === "protocol") return pick(["susy_governance", "governance"] as ContractType[]);
  if (tier === "established") return pick(["susy_governance", "governance", "vesting_reflection", "fixed_governance"] as ContractType[]);
  if (tier === "growth") return pick(["governance", "vesting_reflection", "fixed_governance", "vesting"] as ContractType[]);
  if (tier === "early") return pick(["vesting", "qrc20_standard", "deflationary"] as ContractType[]);
  return pick(["qrc20_standard", "deflationary", "fair_launch"] as ContractType[]);
}

/* ── QPCS Generator ──────────────────────────────────────────────────────── */

function qpcsForTier(tier: ProjectTier): { score: number; components: QPCSComponents } {
  const ranges: Record<ProjectTier, [number, number]> = {
    protocol: [90, 98],
    established: [80, 89],
    growth: [65, 79],
    early: [50, 64],
    seed: [15, 49],
  };
  const [lo, hi] = ranges[tier];
  const score = lo + rand() * (hi - lo);

  const ratio = score / 100;
  const components: QPCSComponents = {
    liquidityLock: Math.round(25 * ratio * (0.8 + rand() * 0.4)),
    teamVesting: Math.round(20 * ratio * (0.7 + rand() * 0.6)),
    tokenomicsDistribution: Math.round(15 * ratio * (0.7 + rand() * 0.6)),
    contractComplexity: Math.round(10 * ratio * (0.8 + rand() * 0.4)),
    presaleStructure: Math.round(10 * ratio * (0.6 + rand() * 0.8)),
    deployerHistory: Math.round(8 * ratio * (0.5 + rand() * 1.0)),
    socialVerification: Math.round(7 * ratio * (0.4 + rand() * 1.2)),
    susyAtDeploy: Math.round(5 * ratio * (0.6 + rand() * 0.8)),
  };
  // clamp
  components.liquidityLock = Math.min(25, components.liquidityLock);
  components.teamVesting = Math.min(20, components.teamVesting);
  components.tokenomicsDistribution = Math.min(15, components.tokenomicsDistribution);
  components.contractComplexity = Math.min(10, components.contractComplexity);
  components.presaleStructure = Math.min(10, components.presaleStructure);
  components.deployerHistory = Math.min(8, components.deployerHistory);
  components.socialVerification = Math.min(7, components.socialVerification);
  components.susyAtDeploy = Math.min(5, components.susyAtDeploy);

  return { score: Math.round(score * 10) / 10, components };
}

/* ── Project Generator ────────────────────────────────────────────────────── */

const NOW = Math.floor(Date.now() / 1000);
const DAY = 86400;
const BASE_BLOCK = 19247;

function generateProject(index: number, tier: ProjectTier): Project {
  const name = PREFIXES[index] + " " + pick(SUFFIXES);
  const symbol = SYMBOLS[index];
  const address = genAddr();
  const deployer = genAddr();
  const type = contractForTier(tier);
  const { score, components } = qpcsForTier(tier);
  const grade = getQpcsGrade(score);
  const deployedDaysAgo = randInt(tier === "protocol" ? 180 : 7, tier === "protocol" ? 365 : 180);
  const deployedAt = NOW - deployedDaysAgo * DAY;
  const deployedBlock = BASE_BLOCK - deployedDaysAgo * 26182; // ~26182 blocks/day at 3.3s

  // Tokenomics
  const totalSupply = pick([1e6, 1e7, 1e8, 1e9, 1e10]);
  const allocLabels = ["Liquidity", "Team", "Marketing", "Ecosystem", "Presale", "Reserve"];
  const allocPcts = [
    randInt(15, 30), randInt(5, 20), randInt(3, 10), randInt(10, 25), randInt(5, 20),
  ];
  const remainder = 100 - allocPcts.reduce((a, b) => a + b, 0);
  allocPcts.push(Math.max(0, remainder));
  const tokenomics: AllocationItem[] = allocLabels.map((label, i) => ({
    label,
    percent: allocPcts[i] ?? 0,
    address: genAddr(),
    vestingCliffDays: label === "Team" ? randInt(30, 180) : 0,
    vestingDurationDays: label === "Team" ? randInt(180, 730) : label === "Ecosystem" ? randInt(90, 365) : 0,
    color: ALLOC_COLORS[i],
  })).filter(a => a.percent > 0);

  // Liquidity lock
  const lockDaysMap: Record<ProjectTier, [number, number]> = {
    protocol: [730, 1460],
    established: [365, 730],
    growth: [180, 365],
    early: [60, 180],
    seed: [30, 90],
  };
  const [lockLo, lockHi] = lockDaysMap[tier];
  const liquidityLockDays = randInt(lockLo, lockHi);
  const liquidityLockExpiry = deployedAt + liquidityLockDays * DAY;
  const liquidityLockedQusd = tier === "protocol" ? randInt(1_000_000, 8_000_000)
    : tier === "established" ? randInt(200_000, 1_500_000)
    : tier === "growth" ? randInt(50_000, 300_000)
    : tier === "early" ? randInt(10_000, 80_000)
    : randInt(1_000, 15_000);

  // MGT tranches
  const mgtTranches: MGTTranche[] = type === "fair_launch" ? [] :
    Array.from({ length: randInt(2, 5) }, (_, i) => {
      const pct = Math.round(100 / (i + 2));
      const mType = pick(MILESTONE_TYPES);
      const target = mType === "holder_count" ? randInt(500, 10000)
        : mType === "dex_volume" ? randInt(100000, 5000000)
        : randInt(50000, 1000000);
      const progress = rand();
      const status: TrancheStatus = progress > 0.8 ? "released" : progress > 0.5 ? "unlocked" : "locked";
      return {
        index: i,
        tokens: Math.round(totalSupply * pct / 100),
        percent: pct,
        milestoneType: mType,
        milestoneTarget: target,
        milestoneCurrentValue: Math.round(target * progress),
        status,
        unlockedAt: status !== "locked" ? deployedAt + randInt(30, 120) * DAY : null,
        releasedAt: status === "released" ? deployedAt + randInt(60, 180) * DAY : null,
        releaseTxHash: status === "released" ? genTxHash() : null,
      };
    });

  // Vesting schedules
  const vestingSchedules: VestingSchedule[] = tokenomics
    .filter(a => a.vestingDurationDays > 0)
    .map(a => {
      const total = Math.round(totalSupply * a.percent / 100);
      const elapsed = (NOW - deployedAt) / DAY;
      const vestable = Math.max(0, elapsed - a.vestingCliffDays) / a.vestingDurationDays;
      const released = Math.min(total, Math.round(total * Math.min(1, vestable)));
      return {
        beneficiary: a.address,
        label: a.label,
        totalTokens: total,
        cliffDays: a.vestingCliffDays,
        vestingDays: a.vestingDurationDays,
        startTime: deployedAt,
        released,
        releasable: Math.min(total - released, Math.round(total * 0.05)),
      };
    });

  // Vouches
  const vouchCount = tier === "protocol" ? randInt(3, 6)
    : tier === "established" ? randInt(1, 4)
    : tier === "growth" ? randInt(0, 2) : 0;
  const vouches: Vouch[] = Array.from({ length: vouchCount }, () => {
    const vTier = pick(["established", "protocol"] as ProjectTier[]);
    const status: VouchStatus = rand() > 0.8 ? "completed_success" : "active";
    return {
      voucherAddress: genAddr(),
      voucherProjectName: pick(PREFIXES) + " " + pick(SUFFIXES),
      voucherProjectAddress: genAddr(),
      voucherTier: vTier,
      voucherQpcs: randInt(80, 98),
      stakeAmountQusd: randInt(1000, 10000),
      note: pick([
        "Strong technical team, novel implementation.",
        "Reviewed tokenomics thoroughly. Legitimate long-term project.",
        "Solid fundamentals. We vouch without hesitation.",
        "Innovative use of SUSY staking. Promising roadmap.",
      ]),
      timestamp: NOW - randInt(1, 60) * DAY,
      txHash: genTxHash(),
      status,
      earningsQusd: status === "completed_success" ? randInt(50, 2000) : randInt(0, 100),
    };
  });

  // DD Reports
  const ddCount = tier === "protocol" ? randInt(3, 8)
    : tier === "established" ? randInt(2, 5)
    : tier === "growth" ? randInt(1, 3)
    : randInt(0, 2);
  const ddReports: DDReport[] = Array.from({ length: ddCount }, (_, i) => {
    const cat = pick(DD_CATS);
    const posVotes = randInt(50, 500);
    const negVotes = randInt(5, posVotes);
    const posPct = Math.round((posVotes / (posVotes + negVotes)) * 100);
    const outcome = posPct >= 60 ? "verified" as const
      : posPct <= 40 ? "flagged" as const
      : "neutral" as const;
    return {
      id: `dd-${index}-${i}`,
      projectAddress: address,
      author: genAddr(),
      authorQbcBalance: randInt(500, 50000),
      category: cat,
      title: pick([
        `${cat.charAt(0).toUpperCase() + cat.slice(1)} Review — ${symbol}`,
        `${symbol} ${cat} Analysis`,
        `Community ${cat} Assessment`,
      ]),
      content: pick([
        "Contract matches described functionality. No hidden mint, no proxy upgrade pattern, no owner backdoors.",
        "Team allocation with cliff and vest is reasonable. No single wallet holds excessive supply.",
        "Liquidity depth is adequate for current market cap. Lock duration is appropriate.",
        "Token has genuine utility within its ecosystem. SUSY staking implementation is novel.",
        "Community activity appears organic. Growth trajectory is sustainable.",
        "Twitter account is relatively new. Recommend longer track record before tier upgrade.",
      ]),
      timestamp: NOW - randInt(1, 30) * DAY,
      txHash: genTxHash(),
      positiveVotes: posVotes,
      negativeVotes: negVotes,
      positivePercent: posPct,
      outcome,
    };
  });

  const communityVerdict: CommunityVerdict = ddReports.length === 0
    ? "no_reports"
    : ddReports.filter(d => d.outcome === "verified").length > ddReports.length / 2
      ? "verified"
      : ddReports.filter(d => d.outcome === "flagged").length > ddReports.length / 2
        ? "flagged"
        : "under_review";

  // Presale
  const hasPresale = type !== "fair_launch" && rand() > 0.4;
  const presale: Presale | null = hasPresale ? (() => {
    const presaleType = pick(["standard_ido", "whitelist_ido", "dutch_auction"] as const);
    const hardCap = randInt(50000, 500000);
    const softCap = Math.round(hardCap * 0.4);
    const raised = Math.round(hardCap * (0.3 + rand() * 0.7));
    const startTime = deployedAt - randInt(7, 30) * DAY;
    const endTime = startTime + randInt(3, 14) * DAY;
    const status: PresaleStatus = NOW > endTime ? (raised >= softCap ? "completed" : "failed")
      : NOW > startTime ? "active" : "upcoming";
    return {
      id: `presale-${index}`,
      projectAddress: address,
      type: presaleType,
      tokenPrice: rand() * 0.01 + 0.0001,
      hardCap,
      softCap,
      raised,
      startBlock: deployedBlock - randInt(7, 30) * 26182,
      endBlock: deployedBlock - randInt(1, 6) * 26182,
      startTime,
      endTime,
      minContribution: pick([10, 50, 100]),
      maxContribution: pick([1000, 5000, 10000, 50000]),
      vestingCliffDays: randInt(0, 30),
      vestingDurationDays: randInt(0, 180),
      whitelistEnabled: presaleType === "whitelist_ido",
      participants: randInt(50, 2000),
      status,
      tokensForSale: Math.round(totalSupply * 0.15),
      tokensDistributed: Math.round(totalSupply * 0.15 * (raised / hardCap)),
      ...(presaleType === "dutch_auction" ? {
        startPrice: rand() * 0.02 + 0.001,
        endPrice: rand() * 0.005 + 0.0001,
        priceDecayRate: rand() * 0.001,
      } : {}),
    };
  })() : null;

  // Price history
  const basePrice = rand() * 0.01 + 0.0001;
  const priceHistory = Array.from({ length: 90 }, (_, i) => ({
    time: NOW - (89 - i) * DAY,
    price: basePrice * (0.5 + rand() * 1.5) * (1 + (tier === "protocol" ? 0.005 : -0.001) * i),
  }));
  const lastPrice = priceHistory[priceHistory.length - 1].price;
  const prevPrice = priceHistory[priceHistory.length - 2].price;
  const price24hChange = ((lastPrice - prevPrice) / prevPrice) * 100;

  // Holders & volume
  const holderCount = tier === "protocol" ? randInt(10000, 50000)
    : tier === "established" ? randInt(2000, 15000)
    : tier === "growth" ? randInt(500, 3000)
    : tier === "early" ? randInt(100, 600)
    : randInt(10, 150);
  const volume24h = tier === "protocol" ? randInt(500000, 5000000)
    : tier === "established" ? randInt(100000, 1000000)
    : tier === "growth" ? randInt(10000, 200000)
    : tier === "early" ? randInt(1000, 20000)
    : randInt(100, 2000);
  const marketCap = lastPrice * totalSupply;

  // Top holders
  const topHolders = Array.from({ length: 10 }, (_, i) => {
    const pct = (10 - i) * (rand() * 2 + 0.5);
    return {
      address: i === 0 ? deployer : genAddr(),
      balance: Math.round(totalSupply * pct / 100),
      percent: Math.round(pct * 100) / 100,
    };
  });

  // QPCS history
  const qpcsHistory = Array.from({ length: 30 }, (_, i) => ({
    date: new Date((NOW - (29 - i) * DAY) * 1000).toISOString().split("T")[0],
    score: Math.max(0, Math.min(100, score + (rand() - 0.5) * 8)),
  }));

  // Graduation history
  const graduationHistory: Array<{ tier: ProjectTier; block: number; timestamp: number }> = [];
  const tiers: ProjectTier[] = ["seed", "early", "growth", "established", "protocol"];
  const tierIdx = tiers.indexOf(tier);
  for (let i = 0; i <= tierIdx; i++) {
    graduationHistory.push({
      tier: tiers[i],
      block: deployedBlock + i * randInt(5000, 50000),
      timestamp: deployedAt + i * randInt(7, 60) * DAY,
    });
  }

  // .qbc domain
  const qbcDomain = tier === "protocol" || tier === "established"
    ? symbol.toLowerCase() + ".qbc"
    : null;

  // QASL
  const qaslEnabled = rand() > 0.3;
  const qaslLaunchBlock = qaslEnabled ? deployedBlock - randInt(1, 100) : null;

  // SUSY at deploy
  const susyAtDeploy = rand() * 0.4 + 0.6;

  // ILLP fee paid
  const illpResult = calculateILLP(liquidityLockDays);

  return {
    address,
    name,
    symbol,
    decimals: 18,
    totalSupply,
    type,
    tier,
    qpcs: score,
    qpcsGrade: grade,
    qpcsComponents: components,
    qpcsHistory,
    deployer,
    deployedBlock: Math.max(0, deployedBlock),
    deployedAt,
    deployTxHash: genTxHash(),
    dilithiumSig: genDilithiumSig(),
    templateVersion: `${type.toUpperCase()}_v${randInt(1, 3)}.${randInt(0, 5)}.0`,
    logoUrl: null,
    description: pick(DESCRIPTIONS),
    fullDescription: pick(DESCRIPTIONS) + "\n\n" + pick(DESCRIPTIONS) + "\n\nBuilt on QBC with Dilithium-3 quantum-resistant signatures.",
    website: `https://${symbol.toLowerCase()}.qbc.network`,
    twitter: rand() > 0.2 ? `https://twitter.com/${symbol.toLowerCase()}` : null,
    telegram: rand() > 0.3 ? `https://t.me/${symbol.toLowerCase()}` : null,
    discord: rand() > 0.4 ? `https://discord.gg/${symbol.toLowerCase()}` : null,
    github: rand() > 0.5 ? `https://github.com/${symbol.toLowerCase()}` : null,
    whitepaper: rand() > 0.4 ? `https://${symbol.toLowerCase()}.qbc.network/whitepaper.pdf` : null,
    qbcDomain,
    dnaFingerprint: genDNA(),
    lastPrice,
    price24hChange,
    marketCap,
    volume24h,
    holderCount,
    liquidityLockedQusd,
    liquidityLockDays,
    liquidityLockExpiry,
    illpFeePaid: illpResult.feeQusd,
    qaslEnabled,
    qaslLaunchBlock,
    qaslMaxBuyPercent: 0.5,
    qaslFeeMultiplier: 2,
    qaslSnipePenalty: 30,
    susyAtDeploy,
    ehgAtDeploy: pick(["optimal", "optimal", "optimal", "degraded"] as EhgStatus[]),
    graduationHistory,
    tokenomics,
    mgtTranches,
    vestingSchedules,
    vouches,
    ddReports,
    communityVerdict,
    priceHistory,
    topHolders,
    presale,
  };
}

/* calculateILLP is imported from shared.tsx — single source of truth for ILLP fee tiers */

/* ── Generate All 50 Projects ─────────────────────────────────────────────── */

const shuffledTiers = shuffle(TIER_DISTRIBUTION);

const ALL_PROJECTS: Project[] = shuffledTiers.map((tier, i) => generateProject(i, tier));

// Sort by QPCS descending (default display order)
ALL_PROJECTS.sort((a, b) => b.qpcs - a.qpcs);

/* ── Ecosystem Health ─────────────────────────────────────────────────────── */

const ECOSYSTEM_HEALTH: EcosystemHealth = {
  status: "optimal",
  blockHeight: BASE_BLOCK,
  networkHashrate: 847.3,
  memPoolDepth: 142,
  susyAlignment: 0.847,
  peerCount: 312,
  totalProjectsLaunched: ALL_PROJECTS.length,
  totalLiquidityLockedQusd: ALL_PROJECTS.reduce((s, p) => s + p.liquidityLockedQusd, 0),
  totalQbcDomains: ALL_PROJECTS.filter(p => p.qbcDomain).length,
  totalDDReports: ALL_PROJECTS.reduce((s, p) => s + p.ddReports.length, 0),
  totalReputationStakes: ALL_PROJECTS.reduce((s, p) => s + p.vouches.length, 0),
  qbcQusdPrice: 0.2847,
  avgQpcs: Math.round(ALL_PROJECTS.reduce((s, p) => s + p.qpcs, 0) / ALL_PROJECTS.length * 10) / 10,
  latestLaunch: (() => {
    const latest = [...ALL_PROJECTS].sort((a, b) => b.deployedAt - a.deployedAt)[0];
    return { name: latest.name, symbol: latest.symbol, time: latest.deployedAt };
  })(),
};

/* ── Portfolio Mock Data ──────────────────────────────────────────────────── */

const MY_WALLET = "QBC1user0000000000000000000000000000000000";

const MY_DEPLOYED = ALL_PROJECTS.slice(0, 3).map(p => ({ ...p, deployer: MY_WALLET }));

const MY_INVESTMENTS: PortfolioInvestment[] = ALL_PROJECTS.slice(5, 10).map(p => {
  const invested = randInt(100, 5000);
  const tokens = invested / (p.lastPrice || 0.001);
  const current = tokens * p.lastPrice;
  return {
    projectAddress: p.address,
    project: p,
    investedQusd: invested,
    tokensReceived: Math.round(tokens),
    currentValue: current,
    pnl: current - invested,
    pnlPercent: ((current - invested) / invested) * 100,
    vestingProgress: rand(),
  };
});

/* ── Public API ───────────────────────────────────────────────────────────── */

export class LaunchpadMockEngine {
  private static instance: LaunchpadMockEngine | null = null;

  static getInstance(): LaunchpadMockEngine {
    if (!this.instance) this.instance = new LaunchpadMockEngine();
    return this.instance;
  }

  getProjects(): Project[] {
    return ALL_PROJECTS;
  }

  getProject(address: string): Project | undefined {
    return ALL_PROJECTS.find(p => p.address === address);
  }

  getProjectsByTier(tier: ProjectTier): Project[] {
    return ALL_PROJECTS.filter(p => p.tier === tier);
  }

  getProjectsWithPresale(): Project[] {
    return ALL_PROJECTS.filter(p => p.presale && p.presale.status === "active");
  }

  getProjectsVouched(): Project[] {
    return ALL_PROJECTS.filter(p => p.vouches.length > 0);
  }

  getProjectsVerified(): Project[] {
    return ALL_PROJECTS.filter(p => p.communityVerdict === "verified");
  }

  getProjectsWithDomain(): Project[] {
    return ALL_PROJECTS.filter(p => p.qbcDomain !== null);
  }

  getEcosystemHealth(): EcosystemHealth {
    return ECOSYSTEM_HEALTH;
  }

  getAllDDReports(): DDReport[] {
    return ALL_PROJECTS.flatMap(p => p.ddReports).sort((a, b) => b.timestamp - a.timestamp);
  }

  getAllVouches(): Vouch[] {
    return ALL_PROJECTS.flatMap(p => p.vouches).sort((a, b) => b.stakeAmountQusd - a.stakeAmountQusd);
  }

  getLeaderboardQPCS(): Project[] {
    return [...ALL_PROJECTS].sort((a, b) => b.qpcs - a.qpcs).slice(0, 50);
  }

  getLeaderboardRaises(): Project[] {
    return ALL_PROJECTS.filter(p => p.presale).sort((a, b) => (b.presale?.raised ?? 0) - (a.presale?.raised ?? 0)).slice(0, 50);
  }

  getLeaderboardLocks(): Project[] {
    return [...ALL_PROJECTS].sort((a, b) => b.liquidityLockDays - a.liquidityLockDays).slice(0, 50);
  }

  getLeaderboardGrowth(): Project[] {
    return [...ALL_PROJECTS].sort((a, b) => b.price24hChange - a.price24hChange).slice(0, 50);
  }

  getLeaderboardReputation(): Project[] {
    return ALL_PROJECTS
      .filter(p => p.vouches.length > 0)
      .sort((a, b) => b.vouches.reduce((s, v) => s + v.stakeAmountQusd, 0) - a.vouches.reduce((s, v) => s + v.stakeAmountQusd, 0))
      .slice(0, 50);
  }

  getMyDeployed(): Project[] {
    return MY_DEPLOYED;
  }

  getMyInvestments(): PortfolioInvestment[] {
    return MY_INVESTMENTS;
  }

  getMyWallet(): string {
    return MY_WALLET;
  }

  // Simulate ecosystem map edges
  getEcosystemEdges(): Array<{
    source: string;
    target: string;
    type: "vouch" | "shared_deployer" | "governance";
    weight: number;
  }> {
    const edges: Array<{ source: string; target: string; type: "vouch" | "shared_deployer" | "governance"; weight: number }> = [];

    // Vouch edges
    for (const p of ALL_PROJECTS) {
      for (const v of p.vouches) {
        const voucher = ALL_PROJECTS.find(pp => pp.address === v.voucherProjectAddress);
        if (voucher) {
          edges.push({ source: voucher.address, target: p.address, type: "vouch", weight: v.stakeAmountQusd });
        }
      }
    }

    // Shared deployer edges
    const byDeployer = new Map<string, Project[]>();
    for (const p of ALL_PROJECTS) {
      const list = byDeployer.get(p.deployer) ?? [];
      list.push(p);
      byDeployer.set(p.deployer, list);
    }
    for (const [, projects] of byDeployer) {
      if (projects.length > 1) {
        for (let i = 0; i < projects.length - 1; i++) {
          edges.push({ source: projects[i].address, target: projects[i + 1].address, type: "shared_deployer", weight: 1 });
        }
      }
    }

    return edges;
  }
}
