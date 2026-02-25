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
  | "leaderboard";

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
