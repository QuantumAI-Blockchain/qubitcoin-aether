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

export const api = {
  getChainInfo: () => get<ChainInfo>("/chain/info"),
  getHealth: () => get<{ status: string }>("/health"),
  getBalance: (addr: string) => get<{ balance: number }>(`/balance/${addr}`),
  getMiningStats: () => get<Record<string, unknown>>("/mining/stats"),
  getPhi: () => get<PhiData>("/aether/consciousness"),
  getPhiHistory: () => get<{ history: Array<{ block: number; phi: number }> }>("/aether/phi/history"),
  getKnowledge: () => get<Record<string, unknown>>("/aether/knowledge"),

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
