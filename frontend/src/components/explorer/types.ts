/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Type Definitions
   ───────────────────────────────────────────────────────────────────────── */

export interface Block {
  height: number;
  hash: string;
  prevHash: string;
  timestamp: number;
  miner: string;
  txCount: number;
  size: number;
  difficulty: number;
  energy: number;
  reward: number;
  gasUsed: number;
  gasLimit: number;
  merkleRoot: string;
  transactions: string[];
  vqeParams: number[];
  phiAtBlock: number;
}

export interface TxInput {
  txid: string;
  vout: number;
  address: string;
  value: number;
}

export interface TxOutput {
  index: number;
  address: string;
  value: number;
  spent: boolean;
}

export interface Transaction {
  txid: string;
  blockHeight: number;
  blockHash: string;
  timestamp: number;
  from: string;
  to: string;
  value: number;
  fee: number;
  size: number;
  type:
    | "transfer"
    | "coinbase"
    | "contract_deploy"
    | "contract_call"
    | "susy_swap"
    | "bridge";
  status: "confirmed" | "pending" | "failed";
  confirmations: number;
  isPrivate: boolean;
  inputs: TxInput[];
  outputs: TxOutput[];
  gasUsed?: number;
  contractAddress?: string;
  data?: string;
}

export interface QVMContract {
  address: string;
  creator: string;
  deployHeight: number;
  deployTxid: string;
  bytecodeSize: number;
  name: string;
  standard: string;
  balance: number;
  txCount: number;
  lastActivity: number;
}

export interface AetherNode {
  id: number;
  type: "assertion" | "observation" | "inference" | "axiom";
  content: string;
  confidence: number;
  blockHeight: number;
  connections: number[];
  edgeTypes: string[];
}

export interface AetherEdge {
  source: number;
  target: number;
  type: "supports" | "contradicts" | "derives" | "requires" | "refines";
  weight: number;
}

export interface MinerStats {
  address: string;
  blocksMined: number;
  totalRewards: number;
  avgEnergy: number;
  lastBlock: number;
  hashPower: number;
  susyScore: number;
  rank: number;
}

export interface NetworkStats {
  blockHeight: number;
  totalSupply: number;
  difficulty: number;
  avgBlockTime: number;
  tps: number;
  mempool: number;
  peers: number;
  phi: number;
  knowledgeNodes: number;
  totalTransactions: number;
  totalContracts: number;
  totalAddresses: number;
  marketCap: number;
}

export interface WalletData {
  address: string;
  balance: number;
  txCount: number;
  firstSeen: number;
  lastSeen: number;
  utxos: TxOutput[];
  transactions: Transaction[];
  isContract: boolean;
}

export interface PathfinderResult {
  path: string[];
  hops: number;
  totalValue: number;
  blockRange: [number, number];
}

export interface PhiDataPoint {
  block: number;
  phi: number;
  knowledgeNodes: number;
  timestamp: number;
}

export interface TpsDataPoint {
  block: number;
  tps: number;
  timestamp: number;
}

export interface DifficultyDataPoint {
  block: number;
  difficulty: number;
  timestamp: number;
}

export type ViewType =
  | "dashboard"
  | "block"
  | "transaction"
  | "qvm"
  | "aether"
  | "wallet"
  | "metrics"
  | "search"
  | "pathfinder"
  | "leaderboard"
  | "hamiltonian";

export interface ExplorerRoute {
  view: ViewType;
  params: Record<string, string>;
}

export interface HeartbeatPoint {
  x: number;
  y: number;
  txid: string;
  value: number;
  type: Transaction["type"];
}

/* ── Aether Explorer Types ──────────────────────────────────────────── */

export interface KnowledgeNodeDetail {
  id: number;
  type: "assertion" | "observation" | "inference" | "axiom";
  content: string;
  confidence: number;
  blockHeight: number;
  timestamp: number;
  connections: number[];
  edgeTypes: string[];
  sourceModule: string;
}

export interface ReasoningOperation {
  id: string;
  type: "deductive" | "inductive" | "abductive";
  premise: string;
  conclusion: string;
  confidence: number;
  blockHeight: number;
  timestamp: number;
  nodesReferenced: number[];
  chainLength: number;
}

export interface ConsciousnessState {
  phi: number;
  threshold: number;
  aboveThreshold: boolean;
  integration: number;
  differentiation: number;
  knowledgeNodes: number;
  knowledgeEdges: number;
  consciousnessEvents: number;
  reasoningOperations: number;
  blocksProcessed: number;
}

export interface ConsciousnessEvent {
  id: number;
  type: string;
  phi: number;
  blockHeight: number;
  timestamp: number;
  description: string;
}

export interface SephirotNode {
  name: string;
  function: string;
  energy: number;
  quantumState: string;
  cognitiveMass: number;
  yukawaCoupling: number;
  tier: number;
  isActive: boolean;
  susyPartner: string;
}

export interface SephirotBalance {
  expansion: string;
  constraint: string;
  ratio: number;
  targetRatio: number;
  balanced: boolean;
}

export interface PredictionRecord {
  id: string;
  prediction: string;
  outcome: string | null;
  confidence: number;
  blockHeight: number;
  timestamp: number;
  verified: boolean;
  correct: boolean | null;
  domain: string;
}

export interface SafetyEvent {
  id: string;
  type: "veto" | "susy_violation" | "emergency" | "constitutional";
  severity: "low" | "medium" | "high" | "critical";
  description: string;
  blockHeight: number;
  timestamp: number;
  resolved: boolean;
  action: string;
}

export interface ProofOfThought {
  hash: string;
  blockHeight: number;
  timestamp: number;
  taskType: string;
  nodesReferenced: number;
  reasoningSteps: number;
  phiAtProof: number;
  validatorCount: number;
  consensusReached: boolean;
}

export interface HiggsFieldState {
  fieldValue: number;
  vev: number;
  potentialEnergy: number;
  symmetryBroken: boolean;
  excitationCount: number;
  massGap: number;
  yukawaMax: number;
}

export interface PinealPhase {
  phase: string;
  metabolicRate: number;
  coherence: number;
  kuramotoOrder: number;
  cyclePosition: number;
}

export interface MemoryStats {
  episodic: number;
  semantic: number;
  procedural: number;
  workingMemory: number;
  totalCapacity: number;
}

/* ── Hamiltonian Lab Types ────────────────────────────────────────────── */

export interface HamiltonianSolution {
  block_height: number;
  hamiltonian: [string, number][];
  params: number[];
  energy: number | null;
  miner_address: string;
  eigenvalues: number[] | null;
  matrix_real: number[] | null;
  qubit_count: number;
}

export interface HamiltonianDetail extends HamiltonianSolution {
  ipfs_cid: string | null;
}

export interface HamiltonianLabData {
  solutions: HamiltonianSolution[];
  count: number;
  archive_stats: {
    total_archives?: number;
    total_solutions_archived?: number;
    last_archive_height?: number;
    cids_stored?: number;
  };
}
