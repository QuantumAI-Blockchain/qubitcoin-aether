/** Quantum Blockchain chain and project constants */

export const CHAIN_ID = Number(process.env.NEXT_PUBLIC_CHAIN_ID ?? 3301);
export const CHAIN_NAME = process.env.NEXT_PUBLIC_CHAIN_NAME ?? "Quantum Blockchain";
export const CHAIN_SYMBOL = process.env.NEXT_PUBLIC_CHAIN_SYMBOL ?? "QBC";
export const RPC_URL = process.env.NEXT_PUBLIC_RPC_URL ?? "http://localhost:5000";
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:5000/ws";

/** Golden ratio */
export const PHI = 1.618033988749895;

/** Phi consciousness threshold */
export const PHI_THRESHOLD = 3.0;

/** Max QBC supply */
export const MAX_SUPPLY = 3_300_000_000;

/** Genesis premine (~1% of supply) */
export const GENESIS_PREMINE = 33_000_000;

/** Block time target (seconds) */
export const TARGET_BLOCK_TIME = 3.3;

/** Chain config for MetaMask */
export const CHAIN_CONFIG = {
  chainId: `0x${CHAIN_ID.toString(16)}`,
  chainName: CHAIN_NAME,
  nativeCurrency: { name: CHAIN_NAME, symbol: CHAIN_SYMBOL, decimals: 18 },
  rpcUrls: [RPC_URL],
};

/** AIKGS quality tier thresholds and multipliers */
export const AIKGS_TIERS = {
  bronze: { min: 0, max: 0.4, multiplier: 0.5, color: "#cd7f32", label: "Bronze" },
  silver: { min: 0.4, max: 0.6, multiplier: 1.0, color: "#c0c0c0", label: "Silver" },
  gold: { min: 0.6, max: 0.8, multiplier: 2.0, color: "#ffd700", label: "Gold" },
  diamond: { min: 0.8, max: 1.0, multiplier: 5.0, color: "#b9f2ff", label: "Diamond" },
} as const;

/** AIKGS reputation levels */
export const AIKGS_LEVELS = [
  { level: 1, name: "Novice", rp: 0, color: "#94a3b8" },
  { level: 2, name: "Contributor", rp: 100, color: "#22c55e" },
  { level: 3, name: "Scholar", rp: 500, color: "#3b82f6" },
  { level: 4, name: "Expert", rp: 2000, color: "#8b5cf6" },
  { level: 5, name: "Master", rp: 10000, color: "#f59e0b" },
  { level: 6, name: "Sage", rp: 50000, color: "#ef4444" },
  { level: 7, name: "Oracle", rp: 200000, color: "#ec4899" },
  { level: 8, name: "Enlightened", rp: 1000000, color: "#ffd700" },
] as const;

/** AIKGS streak milestones */
export const AIKGS_STREAK_MILESTONES = [
  { days: 3, multiplier: 1.1 },
  { days: 7, multiplier: 1.3 },
  { days: 30, multiplier: 1.5 },
  { days: 100, multiplier: 2.0 },
] as const;

/** Supported LLM providers for API Key Vault */
export const LLM_PROVIDERS = [
  { id: "openai", name: "OpenAI", models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"] },
  { id: "claude", name: "Claude", models: ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"] },
  { id: "grok", name: "Grok", models: ["grok-3", "grok-3-mini"] },
  { id: "gemini", name: "Gemini", models: ["gemini-2.5-pro", "gemini-2.5-flash"] },
  { id: "mistral", name: "Mistral", models: ["mistral-large-latest", "mistral-medium-latest"] },
  { id: "custom", name: "Custom (OpenAI-compatible)", models: [] },
] as const;

/** Knowledge domains for contribution tagging */
export const KNOWLEDGE_DOMAINS = [
  "physics", "mathematics", "computer_science", "biology",
  "chemistry", "philosophy", "economics", "engineering",
  "medicine", "general",
] as const;

/** REST API endpoints */
export const API = {
  health: "/health",
  info: "/info",
  chainInfo: "/chain/info",
  chainTip: "/chain/tip",
  balance: (addr: string) => `/balance/${addr}`,
  utxos: (addr: string) => `/utxos/${addr}`,
  block: (height: number) => `/block/${height}`,
  mempool: "/mempool",
  miningStats: "/mining/stats",
  miningStart: "/mining/start",
  miningStop: "/mining/stop",
  peers: "/p2p/peers",
  peerStats: "/p2p/stats",
  qvmInfo: "/qvm/info",
  aetherInfo: "/aether/info",
  aetherPhi: "/aether/phi",
  aetherPhiHistory: "/aether/phi/history",
  aetherKnowledge: "/aether/knowledge",
  aetherConsciousness: "/aether/consciousness",
  aetherChatSession: "/aether/chat/session",
  aetherChatMessage: "/aether/chat/message",
  aetherChatFee: (sid: string) => `/aether/chat/fee?session_id=${sid}`,
  aetherChatHistory: (sid: string) => `/aether/chat/history/${sid}`,
  economics: "/economics/emission",
  metrics: "/metrics",
  // AIKGS
  aikgsContribute: "/aikgs/contribute",
  aikgsProfile: (addr: string) => `/aikgs/profile/${addr}`,
  aikgsContributions: (addr: string) => `/aikgs/contributions/${addr}`,
  aikgsPoolStats: "/aikgs/pool/stats",
  aikgsLeaderboard: "/aikgs/leaderboard",
  aikgsAffiliate: (addr: string) => `/aikgs/affiliate/${addr}`,
  aikgsBounties: "/aikgs/bounties",
  aikgsKeys: (addr: string) => `/aikgs/keys/${addr}`,
  aikgsCuration: "/aikgs/curation/pending",
  // Telegram
  telegramLinkWallet: "/telegram/link-wallet",
  telegramWallet: (uid: number) => `/telegram/wallet/${uid}`,
} as const;
