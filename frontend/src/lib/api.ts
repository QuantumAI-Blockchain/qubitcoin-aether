import { RPC_URL } from "./constants";

/** Generic fetch wrapper for the QBC node REST API. */
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${RPC_URL}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function get<T>(path: string): Promise<T> {
  return apiFetch<T>(path);
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/* ---- Typed interfaces ---- */

export interface ChainInfo {
  chain_id: number;
  height: number;
  total_supply: number;
  max_supply: number;
  percent_emitted: string;
  current_era: number;
  current_reward: number;
  difficulty: number;
  target_block_time: number;
  peers: number;
  mempool_size: number;
}

export interface MiningStats {
  is_mining: boolean;
  blocks_found: number;
  total_attempts: number;
  current_difficulty: number;
  success_rate: number;
  best_energy: number | null;
  alignment_score: number | null;
}

export interface PhiData {
  phi: number;
  threshold: number;
  above_threshold: boolean;
  integration: number;
  differentiation: number;
  knowledge_nodes: number;
  knowledge_edges: number;
  blocks_processed: number;
}

export interface ChatResponse {
  response: string;
  reasoning_trace: string[];
  phi_at_response: number;
  knowledge_nodes_referenced: number[];
  proof_of_thought_hash: string;
  fee_charged: string;
}

export interface ContractInfo {
  address: string;
  code_hash: string;
  nonce: number;
  bytecode_size: number;
}

export interface TransactionInfo {
  txid: string;
  sender: string;
  recipient: string;
  amount: number;
  fee: number;
  block_height: number | null;
  timestamp: number;
  status: "confirmed" | "pending" | "failed";
  confirmations: number;
}

export interface PeerInfo {
  type: string;
  peer_count: number;
  peers: Array<Record<string, unknown>>;
}

export interface P2PStats {
  network: { type: string; connected_peers: number; [k: string]: unknown };
  messages: Record<string, number>;
  connections: Record<string, number>;
}

export interface KnowledgeGraphData {
  nodes: Array<{ id: number; content: string; node_type: string; confidence: number }>;
  edges: Array<{ source: number; target: number; edge_type: string; weight: number }>;
}

export interface AetherInfo {
  knowledge_graph: { total_nodes: number; total_edges: number; [k: string]: unknown };
  phi: { current_phi: number; [k: string]: unknown };
  [k: string]: unknown;
}

export interface EmissionSchedule {
  schedule: Array<{
    year: number;
    emission: number;
    total_supply: number;
    percent_emitted: number;
    era: number;
  }>;
  max_supply: number;
  halving_interval: number;
  blocks_per_year: number;
  phi: number;
}

/* ---- Typed helpers ---- */

export const api = {
  // Chain
  getChainInfo: () => get<ChainInfo>("/chain/info"),
  getHealth: () => get<{ status: string }>("/health"),
  getBalance: (addr: string) => get<{ balance: string; utxo_count: number }>(`/balance/${addr}`),
  getEmission: () => get<EmissionSchedule>("/economics/simulate"),

  // Mining
  getMiningStats: () => get<MiningStats>("/mining/stats"),
  startMining: () => post<{ status: string }>("/mining/start", {}),
  stopMining: () => post<{ status: string }>("/mining/stop", {}),

  // P2P
  getPeers: () => get<PeerInfo>("/p2p/peers"),
  getPeerStats: () => get<P2PStats>("/p2p/stats"),

  // Aether
  getPhi: () => get<PhiData>("/aether/consciousness"),
  getPhiHistory: () => get<{ history: Array<{ block: number; phi: number }> }>("/aether/phi/history"),
  getAetherInfo: () => get<AetherInfo>("/aether/info"),
  getKnowledge: () => get<Record<string, unknown>>("/aether/knowledge"),
  getKnowledgeGraph: (limit = 200) => get<KnowledgeGraphData>(`/aether/knowledge/graph?limit=${limit}`),
  getChatHistory: (sessionId: string) => get<Record<string, unknown>>(`/aether/chat/history/${sessionId}`),
  getChatFee: (sessionId: string) => get<Record<string, unknown>>(`/aether/chat/fee?session_id=${sessionId}`),

  // QVM / Contracts
  getContract: (addr: string) => get<ContractInfo>(`/qvm/contract/${addr}`),
  getContractStorage: (addr: string, key: string) =>
    get<{ value: string }>(`/qvm/storage/${addr}/${key}`),

  // Transactions
  getUTXOs: (addr: string) =>
    get<{ utxos: Array<{ txid: string; vout: number; amount: number; confirmations: number }> }>(
      `/utxos/${addr}`,
    ),
  getMempool: () =>
    get<{ size: number; total_fees: string; transactions: TransactionInfo[] }>("/mempool"),

  // QUSD Reserves
  getQUSDReserves: () =>
    get<{ total_minted: string; total_backed: string; backing_percentage: number }>(
      "/qusd/reserves",
    ),

  // Chat
  createChatSession: (userAddress: string = "") =>
    post<{ session_id: string; created_at: number; free_messages: number }>(
      "/aether/chat/session",
      { user_address: userAddress },
    ),
  sendChatMessage: (sessionId: string, message: string, isDeep = false) =>
    post<ChatResponse>("/aether/chat/message", {
      session_id: sessionId,
      message,
      is_deep_query: isDeep,
    }),
} as const;
