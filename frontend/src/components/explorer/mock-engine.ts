/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Deterministic Mock Data Engine
   mulberry32 PRNG — same seed = identical data every reload

   WARNING: This file provides MOCK DATA for development and testing only.
   It is imported lazily and should never be loaded in production builds.
   All consuming hooks guard imports behind:
     process.env.NEXT_PUBLIC_USE_MOCK_DATA === "true"
   ───────────────────────────────────────────────────────────────────────── */

import type {
  Block,
  Transaction,
  TxInput,
  TxOutput,
  QVMContract,
  AetherNode,
  AetherEdge,
  MinerStats,
  NetworkStats,
  WalletData,
  PhiDataPoint,
  TpsDataPoint,
  DifficultyDataPoint,
} from "./types";

/* ── PRNG ─────────────────────────────────────────────────────────────── */

function mulberry32(seed: number): () => number {
  let s = seed | 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* ── Helper generators ────────────────────────────────────────────────── */

function hexStr(rng: () => number, len: number): string {
  const chars = "0123456789abcdef";
  let s = "";
  for (let i = 0; i < len; i++) s += chars[(rng() * 16) | 0];
  return s;
}

function qbcAddress(rng: () => number): string {
  return "qbc1" + hexStr(rng, 38);
}

function contractAddress(rng: () => number): string {
  return "0x" + hexStr(rng, 40);
}

function pick<T>(rng: () => number, arr: readonly T[]): T {
  return arr[(rng() * arr.length) | 0];
}

function rangeInt(rng: () => number, min: number, max: number): number {
  return min + ((rng() * (max - min + 1)) | 0);
}

function rangeFloat(rng: () => number, min: number, max: number): number {
  return min + rng() * (max - min);
}

/* ── Constants ────────────────────────────────────────────────────────── */

const PHI = 1.618033988749895;
const GENESIS_TIMESTAMP = 1740000000; // ~Feb 2025
const BLOCK_INTERVAL = 3.3;
const INITIAL_REWARD = 15.27;
const MAX_SUPPLY = 3_300_000_000;
const GENESIS_PREMINE = 33_000_000;

const TX_TYPES = [
  "transfer",
  "coinbase",
  "contract_deploy",
  "contract_call",
  "susy_swap",
  "bridge",
] as const;

const CONTRACT_NAMES = [
  "QBC-20 Token",
  "QBC-721 NFT",
  "QUSD Stablecoin",
  "SynapticStaking",
  "AetherKernel",
  "ProofOfThought",
  "TaskMarket",
  "ValidatorRegistry",
  "ConsciousnessDB",
  "BridgeEthereum",
  "BridgeSolana",
  "DEXRouter",
  "LendingPool",
  "GovernanceDAO",
  "OracleAggregator",
  "EmergencyShutdown",
];

const CONTRACT_STANDARDS = [
  "QBC-20",
  "QBC-721",
  "Custom",
  "QBC-1155",
  "ERC-20-QC",
];

const AETHER_NODE_TYPES = [
  "assertion",
  "observation",
  "inference",
  "axiom",
] as const;

const AETHER_EDGE_TYPES = [
  "supports",
  "contradicts",
  "derives",
  "requires",
  "refines",
] as const;

const AETHER_CONTENTS = [
  "Block propagation follows log-normal distribution",
  "SUSY Hamiltonian ground state energy correlates with difficulty",
  "VQE convergence improves with EfficientSU2 ansatz depth ≥ 2",
  "Transaction fee density follows power-law distribution",
  "Knowledge graph density increases superlinearly with block height",
  "Phi integration score correlates with edge connectivity ratio",
  "Stealth address usage indicates growing privacy demand",
  "Bridge transfers peak during cross-chain arbitrage windows",
  "Mining reward halving follows golden ratio schedule",
  "Contract deployment rate suggests healthy developer ecosystem",
  "Consensus finality achieved within 6 confirmations on average",
  "Memory consolidation improves prediction accuracy by 12%",
  "Causal inference identifies fee spikes from mempool congestion",
  "Sephirot energy balance maintained within phi tolerance",
  "Quantum state persistence reduces cross-contract gas by 40%",
  "Neural reasoning identifies novel SUSY violation patterns",
  "Temporal reasoning predicts block time variance ±0.3s",
  "Debate engine resolves conflicting observations with 94% accuracy",
  "Episodic replay strengthens long-term knowledge retention",
  "Curiosity-driven exploration discovers 3 novel axioms per epoch",
];

/* ── MockDataEngine ───────────────────────────────────────────────────── */

export class MockDataEngine {
  private rng: () => number;
  private _blocks: Block[] = [];
  private _transactions: Transaction[] = [];
  private _contracts: QVMContract[] = [];
  private _aetherNodes: AetherNode[] = [];
  private _aetherEdges: AetherEdge[] = [];
  private _miners: MinerStats[] = [];
  private _minerAddresses: string[] = [];
  private _wallets: Map<string, WalletData> = new Map();
  private _phiHistory: PhiDataPoint[] = [];
  private _tpsHistory: TpsDataPoint[] = [];
  private _difficultyHistory: DifficultyDataPoint[] = [];
  private _built = false;

  constructor(private seed: number = 3301) {
    this.rng = mulberry32(seed);
  }

  build(blockCount: number = 500): this {
    if (this._built) return this;
    this._built = true;

    this._generateMiners(24);
    this._generateBlocks(blockCount);
    this._generateContracts(48);
    this._generateAetherGraph(200);
    this._generateTimeSeries(blockCount);
    this._buildWalletIndex();
    return this;
  }

  /* ── Miners ──────────────────────────────────────────────────────── */

  private _generateMiners(count: number): void {
    for (let i = 0; i < count; i++) {
      const addr = qbcAddress(this.rng);
      this._minerAddresses.push(addr);
      this._miners.push({
        address: addr,
        blocksMined: 0,
        totalRewards: 0,
        avgEnergy: 0,
        lastBlock: 0,
        hashPower: rangeFloat(this.rng, 0.5, 15),
        susyScore: rangeFloat(this.rng, 60, 99.9),
        rank: i + 1,
      });
    }
  }

  /* ── Blocks + Transactions ──────────────────────────────────────── */

  private _generateBlocks(count: number): void {
    let prevHash = "0".repeat(64);
    let supply = GENESIS_PREMINE;
    let difficulty = 1.0;

    for (let h = 0; h < count; h++) {
      const hash = hexStr(this.rng, 64);
      const minerIdx = rangeInt(this.rng, 0, this._minerAddresses.length - 1);
      const miner = this._minerAddresses[minerIdx];
      const era = Math.floor(h / 15_474_020);
      const reward = INITIAL_REWARD / Math.pow(PHI, era);
      const txCount = h === 0 ? 1 : rangeInt(this.rng, 1, 12);
      const energy = rangeFloat(this.rng, 0.1, difficulty * 0.95);
      const phiVal = Math.min(
        0.05 * Math.sqrt(Math.max(0, h) / 500) * (1 + this.rng() * 0.3),
        5.0
      );

      const jitter = rangeFloat(this.rng, -0.8, 1.5);
      const ts = GENESIS_TIMESTAMP + h * (BLOCK_INTERVAL + jitter);

      const txs = this._generateBlockTransactions(h, hash, ts, miner, reward, txCount);
      supply = Math.min(supply + reward, MAX_SUPPLY);

      difficulty += (this.rng() - 0.48) * 0.05;
      if (difficulty < 0.3) difficulty = 0.3;
      if (difficulty > 5.0) difficulty = 5.0;

      const vqeParams: number[] = [];
      for (let p = 0; p < 12; p++) vqeParams.push(rangeFloat(this.rng, -Math.PI, Math.PI));

      const block: Block = {
        height: h,
        hash,
        prevHash,
        timestamp: ts,
        miner,
        txCount: txs.length,
        size: rangeInt(this.rng, 800, 45000),
        difficulty,
        energy,
        reward,
        gasUsed: rangeInt(this.rng, 0, 30_000_000),
        gasLimit: 30_000_000,
        merkleRoot: hexStr(this.rng, 64),
        transactions: txs.map((t) => t.txid),
        vqeParams,
        phiAtBlock: phiVal,
      };

      this._blocks.push(block);
      this._transactions.push(...txs);
      prevHash = hash;

      // Update miner stats
      const ms = this._miners[minerIdx];
      ms.blocksMined++;
      ms.totalRewards += reward;
      ms.avgEnergy =
        (ms.avgEnergy * (ms.blocksMined - 1) + energy) / ms.blocksMined;
      ms.lastBlock = h;
    }

    // Sort miners by blocks mined and re-rank
    this._miners.sort((a, b) => b.blocksMined - a.blocksMined);
    this._miners.forEach((m, i) => (m.rank = i + 1));
  }

  private _generateBlockTransactions(
    height: number,
    blockHash: string,
    timestamp: number,
    miner: string,
    reward: number,
    count: number
  ): Transaction[] {
    const txs: Transaction[] = [];

    // Coinbase tx
    const cbTxid = hexStr(this.rng, 64);
    txs.push({
      txid: cbTxid,
      blockHeight: height,
      blockHash,
      timestamp,
      from: "coinbase",
      to: miner,
      value: reward,
      fee: 0,
      size: rangeInt(this.rng, 200, 400),
      type: "coinbase",
      status: "confirmed",
      confirmations: Math.max(0, (this._blocks.length || 500) - height),
      isPrivate: false,
      inputs: [],
      outputs: [{ index: 0, address: miner, value: reward, spent: this.rng() > 0.4 }],
      gasUsed: 0,
    });

    // Regular txs
    for (let i = 1; i < count; i++) {
      const txid = hexStr(this.rng, 64);
      const type = this.rng() < 0.05 ? pick(this.rng, TX_TYPES.filter((t) => t !== "coinbase")) : pick(this.rng, ["transfer", "transfer", "transfer", "contract_call", "susy_swap"] as const);
      const isPrivate = type === "susy_swap";
      const from = qbcAddress(this.rng);
      const to = type === "contract_deploy"
        ? contractAddress(this.rng)
        : type === "contract_call"
          ? contractAddress(this.rng)
          : qbcAddress(this.rng);
      const value = rangeFloat(this.rng, 0.001, 5000);
      const fee = rangeFloat(this.rng, 0.0001, 0.05);

      const inputCount = rangeInt(this.rng, 1, 3);
      const inputs: TxInput[] = [];
      for (let j = 0; j < inputCount; j++) {
        inputs.push({
          txid: hexStr(this.rng, 64),
          vout: rangeInt(this.rng, 0, 3),
          address: from,
          value: value / inputCount + fee / inputCount,
        });
      }

      const outputCount = rangeInt(this.rng, 1, 3);
      const outputs: TxOutput[] = [];
      for (let j = 0; j < outputCount; j++) {
        outputs.push({
          index: j,
          address: j === 0 ? to : qbcAddress(this.rng),
          value: j === 0 ? value : rangeFloat(this.rng, 0.001, value * 0.1),
          spent: this.rng() > 0.5,
        });
      }

      txs.push({
        txid,
        blockHeight: height,
        blockHash,
        timestamp: timestamp + this.rng() * BLOCK_INTERVAL,
        from,
        to,
        value,
        fee,
        size: rangeInt(this.rng, 250, isPrivate ? 2500 : 800),
        type: type as Transaction["type"],
        status: "confirmed",
        confirmations: Math.max(0, 500 - height),
        isPrivate,
        inputs,
        outputs,
        gasUsed: type === "contract_call" ? rangeInt(this.rng, 21000, 500000) : undefined,
        contractAddress: type === "contract_deploy" ? to : undefined,
        data: type === "contract_call" ? "0x" + hexStr(this.rng, 8) : undefined,
      });
    }

    return txs;
  }

  /* ── QVM Contracts ──────────────────────────────────────────────── */

  private _generateContracts(count: number): void {
    for (let i = 0; i < count; i++) {
      const deployHeight = rangeInt(this.rng, 10, (this._blocks.length || 500) - 1);
      this._contracts.push({
        address: contractAddress(this.rng),
        creator: qbcAddress(this.rng),
        deployHeight,
        deployTxid: hexStr(this.rng, 64),
        bytecodeSize: rangeInt(this.rng, 200, 24576),
        name: pick(this.rng, CONTRACT_NAMES),
        standard: pick(this.rng, CONTRACT_STANDARDS),
        balance: rangeFloat(this.rng, 0, 100000),
        txCount: rangeInt(this.rng, 1, 5000),
        lastActivity: deployHeight + rangeInt(this.rng, 0, 200),
      });
    }
  }

  /* ── Aether Tree Knowledge Graph ───────────────────────────────── */

  private _generateAetherGraph(nodeCount: number): void {
    for (let i = 0; i < nodeCount; i++) {
      const connections: number[] = [];
      const edgeTypes: string[] = [];
      const connCount = rangeInt(this.rng, 1, Math.min(6, nodeCount - 1));
      for (let c = 0; c < connCount; c++) {
        let target = rangeInt(this.rng, 0, nodeCount - 1);
        if (target === i) target = (i + 1) % nodeCount;
        if (!connections.includes(target)) {
          connections.push(target);
          edgeTypes.push(pick(this.rng, AETHER_EDGE_TYPES));
        }
      }

      this._aetherNodes.push({
        id: i,
        type: pick(this.rng, AETHER_NODE_TYPES),
        content: pick(this.rng, AETHER_CONTENTS),
        confidence: rangeFloat(this.rng, 0.3, 1.0),
        blockHeight: rangeInt(this.rng, 0, (this._blocks.length || 500) - 1),
        connections,
        edgeTypes,
      });
    }

    // Build edges from connections
    for (const node of this._aetherNodes) {
      for (let i = 0; i < node.connections.length; i++) {
        this._aetherEdges.push({
          source: node.id,
          target: node.connections[i],
          type: node.edgeTypes[i] as AetherEdge["type"],
          weight: rangeFloat(this.rng, 0.1, 1.0),
        });
      }
    }
  }

  /* ── Time Series ────────────────────────────────────────────────── */

  private _generateTimeSeries(blockCount: number): void {
    for (let h = 0; h < blockCount; h++) {
      const blk = this._blocks[h];

      this._phiHistory.push({
        block: h,
        phi: blk.phiAtBlock,
        knowledgeNodes: Math.min(h * 2 + rangeInt(this.rng, 0, 3), 200),
        timestamp: blk.timestamp,
      });

      this._tpsHistory.push({
        block: h,
        tps: blk.txCount / BLOCK_INTERVAL,
        timestamp: blk.timestamp,
      });

      this._difficultyHistory.push({
        block: h,
        difficulty: blk.difficulty,
        timestamp: blk.timestamp,
      });
    }
  }

  /* ── Wallet Index ───────────────────────────────────────────────── */

  private _buildWalletIndex(): void {
    const addressMap = new Map<
      string,
      { txs: Transaction[]; firstSeen: number; lastSeen: number; balance: number }
    >();

    for (const tx of this._transactions) {
      for (const addr of [tx.from, tx.to]) {
        if (!addr || addr === "coinbase") continue;
        if (!addressMap.has(addr)) {
          addressMap.set(addr, { txs: [], firstSeen: tx.timestamp, lastSeen: tx.timestamp, balance: 0 });
        }
        const entry = addressMap.get(addr)!;
        entry.txs.push(tx);
        if (tx.timestamp < entry.firstSeen) entry.firstSeen = tx.timestamp;
        if (tx.timestamp > entry.lastSeen) entry.lastSeen = tx.timestamp;
      }
    }

    for (const [addr, data] of addressMap) {
      // Simple balance estimation from outputs
      let bal = 0;
      for (const tx of data.txs) {
        for (const out of tx.outputs) {
          if (out.address === addr && !out.spent) bal += out.value;
        }
      }
      const isContract = addr.startsWith("0x");
      this._wallets.set(addr, {
        address: addr,
        balance: bal,
        txCount: data.txs.length,
        firstSeen: data.firstSeen,
        lastSeen: data.lastSeen,
        utxos: data.txs
          .flatMap((t) => t.outputs)
          .filter((o) => o.address === addr && !o.spent),
        transactions: data.txs.slice(0, 100),
        isContract,
      });
    }
  }

  /* ── Public accessors ───────────────────────────────────────────── */

  get blocks(): Block[] {
    return this._blocks;
  }

  get transactions(): Transaction[] {
    return this._transactions;
  }

  get contracts(): QVMContract[] {
    return this._contracts;
  }

  get aetherNodes(): AetherNode[] {
    return this._aetherNodes;
  }

  get aetherEdges(): AetherEdge[] {
    return this._aetherEdges;
  }

  get miners(): MinerStats[] {
    return this._miners;
  }

  get phiHistory(): PhiDataPoint[] {
    return this._phiHistory;
  }

  get tpsHistory(): TpsDataPoint[] {
    return this._tpsHistory;
  }

  get difficultyHistory(): DifficultyDataPoint[] {
    return this._difficultyHistory;
  }

  getBlock(height: number): Block | undefined {
    return this._blocks[height];
  }

  getBlockByHash(hash: string): Block | undefined {
    return this._blocks.find((b) => b.hash === hash);
  }

  getTransaction(txid: string): Transaction | undefined {
    return this._transactions.find((t) => t.txid === txid);
  }

  getTransactionsForBlock(height: number): Transaction[] {
    return this._transactions.filter((t) => t.blockHeight === height);
  }

  getContract(address: string): QVMContract | undefined {
    return this._contracts.find((c) => c.address === address);
  }

  getWallet(address: string): WalletData | undefined {
    return this._wallets.get(address);
  }

  getNetworkStats(): NetworkStats {
    const latest = this._blocks[this._blocks.length - 1];
    const recentTps = this._tpsHistory.slice(-100);
    const avgTps =
      recentTps.reduce((s, p) => s + p.tps, 0) / (recentTps.length || 1);

    let supply = GENESIS_PREMINE;
    for (const b of this._blocks) supply += b.reward;

    return {
      blockHeight: latest?.height ?? 0,
      totalSupply: Math.min(supply, MAX_SUPPLY),
      difficulty: latest?.difficulty ?? 1.0,
      avgBlockTime: BLOCK_INTERVAL,
      tps: avgTps,
      mempool: rangeInt(this.rng, 0, 200),
      peers: rangeInt(this.rng, 12, 64),
      phi: latest?.phiAtBlock ?? 0,
      knowledgeNodes: this._aetherNodes.length,
      totalTransactions: this._transactions.length,
      totalContracts: this._contracts.length,
      totalAddresses: this._wallets.size,
      marketCap: supply * 0.42,
    };
  }

  search(query: string): {
    blocks: Block[];
    transactions: Transaction[];
    addresses: WalletData[];
    contracts: QVMContract[];
  } {
    const q = query.toLowerCase().trim();
    const heightMatch = parseInt(q, 10);

    const blocks: Block[] = [];
    const transactions: Transaction[] = [];
    const addresses: WalletData[] = [];
    const contracts: QVMContract[] = [];

    // Search by block height
    if (!isNaN(heightMatch) && this._blocks[heightMatch]) {
      blocks.push(this._blocks[heightMatch]);
    }

    // Search by hash prefix
    if (q.length >= 8) {
      for (const b of this._blocks) {
        if (b.hash.startsWith(q)) blocks.push(b);
        if (blocks.length >= 5) break;
      }
      for (const t of this._transactions) {
        if (t.txid.startsWith(q)) transactions.push(t);
        if (transactions.length >= 10) break;
      }
    }

    // Search by address prefix
    if (q.startsWith("qbc1") || q.startsWith("0x")) {
      for (const [addr, w] of this._wallets) {
        if (addr.startsWith(q)) addresses.push(w);
        if (addresses.length >= 10) break;
      }
      for (const c of this._contracts) {
        if (c.address.startsWith(q) || c.name.toLowerCase().includes(q))
          contracts.push(c);
        if (contracts.length >= 10) break;
      }
    }

    // Search contract names
    if (q.length >= 3) {
      for (const c of this._contracts) {
        if (
          c.name.toLowerCase().includes(q) &&
          !contracts.find((x) => x.address === c.address)
        ) {
          contracts.push(c);
        }
        if (contracts.length >= 10) break;
      }
    }

    return { blocks, transactions, addresses, contracts };
  }

  findPath(
    fromAddr: string,
    toAddr: string,
    maxHops: number = 6
  ): { path: string[]; totalValue: number; blockRange: [number, number] } | null {
    // BFS through transaction graph
    const visited = new Set<string>();
    const queue: { addr: string; path: string[]; value: number; minBlock: number; maxBlock: number }[] = [
      { addr: fromAddr, path: [fromAddr], value: 0, minBlock: Infinity, maxBlock: 0 },
    ];
    visited.add(fromAddr);

    // Build adjacency from transactions
    const adj = new Map<string, { to: string; value: number; block: number }[]>();
    for (const tx of this._transactions) {
      if (!tx.from || tx.from === "coinbase") continue;
      if (!adj.has(tx.from)) adj.set(tx.from, []);
      adj.get(tx.from)!.push({ to: tx.to, value: tx.value, block: tx.blockHeight });
    }

    while (queue.length > 0) {
      const current = queue.shift()!;
      if (current.path.length > maxHops) continue;

      if (current.addr === toAddr) {
        return {
          path: current.path,
          totalValue: current.value,
          blockRange: [current.minBlock, current.maxBlock],
        };
      }

      const neighbors = adj.get(current.addr) || [];
      for (const n of neighbors) {
        if (!visited.has(n.to)) {
          visited.add(n.to);
          queue.push({
            addr: n.to,
            path: [...current.path, n.to],
            value: current.value + n.value,
            minBlock: Math.min(current.minBlock, n.block),
            maxBlock: Math.max(current.maxBlock, n.block),
          });
        }
      }
    }

    return null;
  }
}

/* ── Singleton ────────────────────────────────────────────────────────── */

let _instance: MockDataEngine | null = null;

export function getMockEngine(): MockDataEngine {
  if (!_instance) {
    _instance = new MockDataEngine(3301).build(500);
  }
  return _instance;
}
