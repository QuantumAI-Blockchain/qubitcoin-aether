/** Qubitcoin chain and project constants */

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

/** Block time target (seconds) */
export const TARGET_BLOCK_TIME = 3.3;

/** Chain config for MetaMask */
export const CHAIN_CONFIG = {
  chainId: `0x${CHAIN_ID.toString(16)}`,
  chainName: CHAIN_NAME,
  nativeCurrency: { name: CHAIN_NAME, symbol: CHAIN_SYMBOL, decimals: 18 },
  rpcUrls: [RPC_URL],
};

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
} as const;
