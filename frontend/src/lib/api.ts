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

/* ---- Typed helpers ---- */

export interface ChainInfo {
  chain_id: number;
  height: number;
  total_supply: number;
  difficulty: number;
  peers: number;
  mempool_size: number;
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
  creator: string;
  bytecode_hash: string;
  deployed_at: number;
  contract_type: string;
  is_active: boolean;
  storage_slots: number;
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

export const api = {
  getChainInfo: () => get<ChainInfo>("/chain/info"),
  getHealth: () => get<{ status: string }>("/health"),
  getBalance: (addr: string) => get<{ balance: number }>(`/balance/${addr}`),
  getMiningStats: () => get<Record<string, unknown>>("/mining/stats"),
  getPhi: () => get<PhiData>("/aether/consciousness"),
  getPhiHistory: () => get<{ history: Array<{ block: number; phi: number }> }>("/aether/phi/history"),
  getKnowledge: () => get<Record<string, unknown>>("/aether/knowledge"),

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
    get<{ transactions: TransactionInfo[] }>("/mempool"),

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
