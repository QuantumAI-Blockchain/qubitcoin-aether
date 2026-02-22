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

export interface PhiGate {
  id: number;
  name: string;
  description: string;
  requirement: string;
  passed: boolean;
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
  // v2/v3 gate fields (post-fork, optional)
  phi_raw?: number;
  phi_version?: number;
  gates_passed?: number;
  gates_total?: number;
  gate_ceiling?: number;
  gates?: PhiGate[];
  // v3 fields
  connectivity?: number;
  maturity?: number;
  redundancy_factor?: number;
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

export interface KnowledgeGraphNode {
  id: number;
  content: string;
  node_type: "assertion" | "observation" | "inference" | "axiom" | "sephirot" | (string & {});
  confidence: number;
  is_contract?: boolean;
  source_block?: number | null;
  sephirot_name?: string;
  sephirot_title?: string;
  sephirot_function?: string;
  brain_analog?: string;
}

export interface KnowledgeGraphEdge {
  source: number;
  target: number;
  edge_type: string;
  weight: number;
}

export interface KnowledgeGraphData {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
  total_nodes: number;
  total_edges: number;
}

export interface NeuralReasonerStats {
  total_predictions: number;
  correct_predictions: number;
  accuracy: number;
  has_torch: boolean;
  hidden_dim: number;
  n_heads: number;
}

export interface CausalEngineStats {
  total_causal_edges_found: number;
  total_runs: number;
  last_run_block: number;
}

export interface DebateProtocolStats {
  total_debates: number;
  accepted: number;
  rejected: number;
  modified: number;
  acceptance_rate: number;
}

export interface TemporalEngineStats {
  tracked_metrics: number;
  total_data_points: number;
  pending_predictions: number;
  predictions_validated: number;
  predictions_correct: number;
  accuracy: number;
  metrics: string[];
}

export interface ConceptFormationStats {
  total_concepts_created: number;
  total_runs: number;
}

export interface MetacognitionStats {
  total_evaluations: number;
  total_correct: number;
  overall_accuracy: number;
  calibration_error: number;
  strategy_accuracies: Record<string, number>;
  strategy_weights: Record<string, number>;
  domain_accuracies: Record<string, number>;
}

export interface AetherInfo {
  knowledge_graph: { total_nodes: number; total_edges: number; [k: string]: unknown };
  phi: { current_value: number; threshold: number; above_threshold: boolean; version: number; gates_passed: number; [k: string]: unknown };
  reasoning: Record<string, unknown>;
  thought_proofs_generated: number;
  neural_reasoner?: NeuralReasonerStats;
  causal_engine?: CausalEngineStats;
  debate_protocol?: DebateProtocolStats;
  temporal_engine?: TemporalEngineStats;
  concept_formation?: ConceptFormationStats;
  metacognition?: MetacognitionStats;
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

export interface SephirotNode {
  id: number;
  name: string;
  title: string;
  function: string;
  brain_analog: string;
  min_stake: number;
  current_stakers: number;
  total_staked: string;
  apy_estimate: number;
}

export interface SephirotStatusNode {
  role: string;
  contract_address?: string;
  energy: number;
  qbc_stake: number;
  qubits: number;
  active: boolean;
  messages_processed: number;
  reasoning_ops: number;
}

export interface SUSYPair {
  expansion: string;
  constraint: string;
  ratio: number;
  target_ratio: number;
}

export interface SephirotStatus {
  [key: string]: SephirotStatusNode | SUSYPair[] | number;
  susy_pairs: SUSYPair[];
  coherence: number;
  total_violations: number;
}

export interface SephirotStake {
  stake_id: string;
  address: string;
  node_id: number;
  node_name?: string;
  amount: string;
  status: string;
  staked_at: string | null;
  unstake_requested_at: string | null;
  rewards_earned: string;
  rewards_claimed: string;
}

export interface SephirotRewards {
  total_earned: string;
  pending_claim: string;
  claimed: string;
  stakes: SephirotStake[];
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
  getAetherSubsystems: () =>
    get<AetherInfo>("/aether/info").then((info) => ({
      neural_reasoner: info.neural_reasoner,
      causal_engine: info.causal_engine,
      debate_protocol: info.debate_protocol,
      temporal_engine: info.temporal_engine,
      concept_formation: info.concept_formation,
      metacognition: info.metacognition,
    })),
  getKnowledge: () => get<Record<string, unknown>>("/aether/knowledge"),
  getKnowledgeGraph: (limit = 3300) => get<KnowledgeGraphData>(`/aether/knowledge/graph?limit=${limit}`),
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
  // Native wallet
  createWallet: () =>
    post<{ address: string; public_key_hex: string; private_key_hex: string }>(
      "/wallet/create",
      {},
    ),
  sendNative: (body: {
    from_address: string;
    to_address: string;
    amount: string;
    signature_hex: string;
    public_key_hex: string;
  }) => post<{ tx_hash: string; status: string }>("/wallet/send", body),
  signMessage: (body: { message_hash: string; private_key_hex: string }) =>
    post<{ signature_hex: string }>("/wallet/sign", body),

  // Transfer (UTXO → Account bridge)
  transferToAccount: (body: { to: string; amount: string }) =>
    post<{ tx_hash: string; from: string; to: string; amount: string }>(
      "/transfer",
      body,
    ),

  // Sephirot
  getSephirotNodes: () =>
    get<{ nodes: SephirotNode[] }>("/sephirot/nodes"),
  getSephirotStatus: () =>
    get<SephirotStatus>("/aether/sephirot"),
  stakeSephirot: (body: {
    address: string;
    node_id: number;
    amount: string;
    signature_hex: string;
    public_key_hex: string;
  }) =>
    post<{ stake_id: string; node_id: number; amount: string; status: string }>(
      "/sephirot/stake",
      body,
    ),
  unstakeSephirot: (body: {
    address: string;
    stake_id: string;
    signature_hex: string;
    public_key_hex: string;
  }) =>
    post<{ stake_id: string; status: string; available_at: string }>(
      "/sephirot/unstake",
      body,
    ),
  getMyStakes: (address: string) =>
    get<{ stakes: SephirotStake[] }>(`/sephirot/stakes/${address}`),
  getMyRewards: (address: string) =>
    get<SephirotRewards>(`/sephirot/rewards/${address}`),
  claimRewards: (body: {
    address: string;
    signature_hex: string;
    public_key_hex: string;
  }) =>
    post<{ claimed_amount: string; tx_hash: string | null }>(
      "/sephirot/claim-rewards",
      body,
    ),
} as const;
