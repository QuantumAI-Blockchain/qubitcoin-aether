import { RPC_URL } from "./constants";

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 500;

/** Generic fetch wrapper for the QBC node REST API with exponential backoff retry. */
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${RPC_URL}${path}`;
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(url, {
        headers: { "Content-Type": "application/json", ...init?.headers },
        ...init,
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        // Don't retry 4xx client errors (except 429 rate limit)
        if (res.status >= 400 && res.status < 500 && res.status !== 429) {
          throw new Error(`API ${res.status}: ${body || res.statusText}`);
        }
        throw new Error(`API ${res.status}: ${body || res.statusText}`);
      }
      return res.json() as Promise<T>;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      // Don't retry non-retryable errors
      if (lastError.message.startsWith("API 4") && !lastError.message.startsWith("API 429")) {
        throw lastError;
      }
      if (attempt < MAX_RETRIES) {
        const delay = BASE_DELAY_MS * Math.pow(2, attempt);
        await new Promise((r) => setTimeout(r, delay));
      }
    }
  }
  throw lastError ?? new Error("Request failed after retries");
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

export interface StealthKeyPair {
  spend_privkey: number;
  spend_pubkey: string;
  view_privkey: number;
  view_pubkey: string;
  public_address: string;
}

export interface ConfidentialTxResult {
  txid: string;
  inputs: Array<Record<string, unknown>>;
  outputs: Array<Record<string, unknown>>;
  fee: number;
  key_images: string[];
  excess_commitment: string;
  signature: string;
  timestamp: number;
  is_private: boolean;
  tx_type: string;
}

/* ---- AIKGS Interfaces (re-exported from shared types) ---- */

import type {
  ContributorProfile as AIKGSContributorProfile,
  ContributionRecord as AIKGSContribution,
  RewardBreakdown as AIKGSRewardBreakdown,
  AffiliateInfo as AIKGSAffiliateInfo,
  BountyInfo as AIKGSBounty,
  LeaderboardEntry as AIKGSLeaderboardEntry,
  PoolStats as AIKGSPoolStats,
  StoredKeyInfo as AIKGSStoredKey,
  CurationRound as AIKGSCurationRound,
} from "@/types/aikgs";

export type {
  AIKGSContributorProfile,
  AIKGSContribution,
  AIKGSRewardBreakdown,
  AIKGSAffiliateInfo,
  AIKGSBounty,
  AIKGSLeaderboardEntry,
  AIKGSPoolStats,
  AIKGSStoredKey,
  AIKGSCurationRound,
};

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
  // Knowledge seeding (user-provided API key)
  seedKnowledge: (body: {
    wallet_address: string;
    api_key: string;
    prompt: string;
    model?: string;
    max_tokens?: number;
  }) =>
    post<{
      status: string;
      nodes_created: number;
      node_ids: number[];
      tokens_used: number;
      model: string;
      latency_ms: number;
      knowledge_nodes: number;
      phi_after: number;
    }>("/aether/llm/seed-user", body),

  // Native wallet
  // SECURITY [FE-C1]: /wallet/create no longer returns private_key_hex.
  // The server generates a keypair but only returns the address and public key.
  // Private keys must be generated client-side via Dilithium2 WASM.
  // See: https://github.com/nicoburniske/pqc-wasm for a reference WASM build.
  createWallet: () =>
    post<{ address: string; public_key_hex: string }>(
      "/wallet/create",
      {},
    ),
  sendNative: (body: {
    from_address: string;
    to_address: string;
    amount: string;
    signature_hex: string;
    public_key_hex: string;
    utxo_strategy?: "largest_first" | "smallest_first" | "exact_match";
  }) => post<{ tx_hash: string; status: string }>("/wallet/send", body),
  // SECURITY: signMessage removed — private keys must NEVER be sent to the
  // backend. Use signTransaction() from @/lib/dilithium for client-side signing.
  // signMessage is intentionally omitted to prevent accidental private key leakage.

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

  // Privacy (Susy Swaps)
  generateStealthKeypair: () =>
    post<StealthKeyPair>("/privacy/stealth/generate-keypair", {}),
  createStealthOutput: (body: {
    recipient_spend_pub: string;
    recipient_view_pub: string;
  }) =>
    post<{ one_time_address: string; ephemeral_pubkey: string }>(
      "/privacy/stealth/create-output",
      body,
    ),
  scanStealthOutput: (body: {
    ephemeral_pubkey: string;
    output_address: string;
    view_privkey: number;
    spend_pubkey: string;
    view_pubkey?: string;
  }) => post<{ is_mine: boolean }>("/privacy/stealth/scan", body),
  buildPrivateTx: (body: {
    inputs: Array<{
      txid: string;
      vout: number;
      value: number;
      blinding: number;
      spending_key: number;
    }>;
    outputs: Array<{
      value: number;
      recipient_spend_pub?: string;
      recipient_view_pub?: string;
    }>;
    fee_atoms: number;
  }) => post<ConfidentialTxResult>("/privacy/tx/build", body),
  submitPrivateTx: (body: ConfidentialTxResult) =>
    post<{ status: string; txid: string }>("/privacy/tx/submit", body),
  createCommitment: (value: number) =>
    post<{ commitment: string; blinding: string }>(
      "/privacy/commitment/create",
      { value },
    ),
  generateRangeProof: (body: { value: number; blinding?: string }) =>
    post<{ proof: string; commitment: string; blinding: string }>(
      "/privacy/range-proof/generate",
      body,
    ),

  // ─── AIKGS ──────────────────────────────────────────────────────────
  aikgsSubmitContribution: (body: {
    contributor_address: string;
    content: string;
    domain?: string;
    session_id?: string;
  }) =>
    post<{
      contribution_id: number;
      quality_score: number;
      novelty_score: number;
      combined_score: number;
      tier: string;
      reward_amount: number;
      knowledge_node_id: number | null;
    }>("/aikgs/contribute", body),

  aikgsGetProfile: (address: string) =>
    get<AIKGSContributorProfile>(`/aikgs/profile/${address}`),

  aikgsGetContributions: (address: string, limit = 20) =>
    get<{ contributions: AIKGSContribution[] }>(`/aikgs/contributions/${address}?limit=${limit}`),

  aikgsGetRewardBreakdown: (contributionId: number) =>
    get<AIKGSRewardBreakdown>(`/aikgs/reward/${contributionId}`),

  aikgsGetPoolStats: () =>
    get<AIKGSPoolStats>("/aikgs/pool/stats"),

  aikgsGetLeaderboard: (limit = 20) =>
    get<{ leaderboard: AIKGSLeaderboardEntry[] }>(`/aikgs/leaderboard?limit=${limit}`),

  aikgsGetStreak: (address: string) =>
    get<{ current_streak: number; best_streak: number; multiplier: number }>(
      `/aikgs/streak/${address}`,
    ),

  // Affiliate
  aikgsRegisterAffiliate: (body: { address: string; referral_code?: string }) =>
    post<{ referral_code: string; referrer: string | null }>("/aikgs/affiliate/register", body),

  aikgsGetAffiliate: (address: string) =>
    get<AIKGSAffiliateInfo>(`/aikgs/affiliate/${address}`),

  aikgsGetReferralLink: (address: string) =>
    get<{ referral_code: string; link: string; telegram_link: string }>(
      `/aikgs/affiliate/link/${address}`,
    ),

  // Bounties
  aikgsGetBounties: (status = "open") =>
    get<{ bounties: AIKGSBounty[] }>(`/aikgs/bounties?status=${status}`),

  aikgsClaimBounty: (body: { bounty_id: number; contributor_address: string }) =>
    post<{ status: string }>("/aikgs/bounty/claim", body),

  aikgsFulfillBounty: (body: {
    bounty_id: number;
    contributor_address: string;
    contribution_id: number;
  }) =>
    post<{ status: string; reward_amount: number }>("/aikgs/bounty/fulfill", body),

  // API Key Vault
  aikgsStoreKey: (body: {
    owner_address: string;
    provider: string;
    api_key: string;
    model: string;
    label?: string;
    is_shared?: boolean;
    signature_hex?: string;
    public_key_hex?: string;
  }) =>
    post<{ key_id: string; status: string }>("/aikgs/keys/store", body),

  aikgsGetKeys: (address: string) =>
    get<{ keys: AIKGSStoredKey[] }>(`/aikgs/keys/${address}`),

  aikgsRevokeKey: (body: {
    owner_address: string;
    key_id: string;
    signature_hex?: string;
    public_key_hex?: string;
  }) =>
    post<{ status: string }>("/aikgs/keys/revoke", body),

  aikgsGetSharedPool: () =>
    get<{ pool_size: number; providers: Record<string, number> }>("/aikgs/keys/shared-pool"),

  // Curation
  aikgsGetPendingCuration: () =>
    get<{ rounds: AIKGSCurationRound[] }>("/aikgs/curation/pending"),

  aikgsSubmitCurationVote: (body: {
    curator_address: string;
    round_id: string;
    approved: boolean;
    comment?: string;
  }) =>
    post<{ status: string }>("/aikgs/curation/vote", body),

  // ─── Telegram ───────────────────────────────────────────────────────
  telegramLinkWallet: (body: { telegram_user_id: number; qbc_address: string }) =>
    post<{ status: string }>("/telegram/link-wallet", body),

  telegramGetWallet: (telegramUserId: number) =>
    get<{ address: string | null }>(`/telegram/wallet/${telegramUserId}`),

  telegramWebhook: (body: Record<string, unknown>) =>
    post<Record<string, unknown>>("/telegram/webhook", body),
} as const;
