/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — React Query Hooks

   Fetches from the real QBC node API when available, falls back to
   MockDataEngine when the node is unreachable (dev mode).
   ───────────────────────────────────────────────────────────────────────── */

import { useQuery } from "@tanstack/react-query";
// Lazy require — never bundled in production unless USE_MOCK is set (FE-H4 audit fix)
// eslint-disable-next-line @typescript-eslint/no-require-imports
const getMockEngine = () => (require("./mock-engine") as typeof import("./mock-engine")).getMockEngine();
import { get } from "@/lib/api";
import type {
  Block,
  Transaction,
  QVMContract,
  AetherNode,
  AetherEdge,
  MinerStats,
  NetworkStats,
  WalletData,
  PhiDataPoint,
  TpsDataPoint,
  DifficultyDataPoint,
  KnowledgeNodeDetail,
  ReasoningOperation,
  ConsciousnessState,
  ConsciousnessEvent,
  SephirotNode,
  SephirotBalance,
  PredictionRecord,
  SafetyEvent,
  ProofOfThought,
  HiggsFieldState,
  PinealPhase,
  MemoryStats,
} from "./types";

const STALE_TIME = 10_000;

/**
 * Check if we should use mock data.  Defaults to false in production builds.
 * Set NEXT_PUBLIC_USE_MOCK_DATA=true in .env.local for development.
 * During SSR we also fall back to mock if the flag is set.
 */
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK_DATA === "true";

function engine() {
  if (process.env.NODE_ENV === "production" && !USE_MOCK) {
    throw new Error(
      "MockDataEngine accessed in production without NEXT_PUBLIC_USE_MOCK_DATA=true",
    );
  }
  return getMockEngine();
}

/* ── Helpers — transform backend shape → frontend types ──────────────── */

function mapChainInfoToStats(raw: Record<string, unknown>): NetworkStats {
  return {
    blockHeight: (raw.height as number) ?? 0,
    totalSupply: (raw.total_supply as number) ?? 0,
    difficulty: (raw.difficulty as number) ?? 0,
    avgBlockTime: (raw.target_block_time as number) ?? 3.3,
    tps: 0, // computed separately
    mempool: (raw.mempool_size as number) ?? 0,
    peers: (raw.peers as number) ?? 0,
    phi: 0, // filled from /aether/consciousness
    knowledgeNodes: 0,
    totalTransactions: 0,
    totalContracts: 0,
    totalAddresses: 0,
    marketCap: 0,
  };
}

function mapBlockToFrontend(raw: Record<string, unknown>): Block {
  return {
    height: (raw.height as number) ?? 0,
    hash: (raw.hash as string) ?? "",
    prevHash: (raw.prev_hash as string) ?? (raw.previous_hash as string) ?? "",
    timestamp: (raw.timestamp as number) ?? 0,
    miner: (raw.miner as string) ?? (raw.miner_address as string) ?? "",
    txCount: (raw.tx_count as number) ?? ((raw.transactions as unknown[])?.length ?? 0),
    size: (raw.size as number) ?? 0,
    difficulty: (raw.difficulty as number) ?? (raw.difficulty_target as number) ?? 0,
    energy: (raw.ground_state_energy as number) ?? (raw.energy as number) ?? 0,
    reward: (raw.reward as number) ?? (raw.actual_reward as number) ?? 0,
    gasUsed: (raw.gas_used as number) ?? 0,
    gasLimit: (raw.gas_limit as number) ?? 30_000_000,
    merkleRoot: (raw.merkle_root as string) ?? "",
    transactions: (raw.transactions as string[]) ?? [],
    vqeParams: (raw.vqe_params as number[]) ?? [],
    phiAtBlock: (raw.phi_at_block as number) ?? 0,
  };
}

/* ── Network ──────────────────────────────────────────────────────────── */

export function useNetworkStats() {
  return useQuery<NetworkStats>({
    queryKey: ["explorer", "networkStats"],
    queryFn: async () => {
      if (USE_MOCK) return engine().getNetworkStats();
      const [chain, phi, qvm] = await Promise.all([
        get<Record<string, unknown>>("/chain/info"),
        get<Record<string, unknown>>("/aether/consciousness").catch(() => null),
        get<Record<string, unknown>>("/qvm/info").catch(() => null),
      ]);
      const stats = mapChainInfoToStats(chain);
      if (phi) {
        stats.phi = (phi.phi as number) ?? 0;
        stats.knowledgeNodes = (phi.knowledge_nodes as number) ?? 0;
      }
      if (qvm) {
        stats.totalContracts = (qvm.total_contracts as number) ?? 0;
      }
      return stats;
    },
    staleTime: STALE_TIME,
    refetchInterval: 5_000,
  });
}

/* ── Blocks ───────────────────────────────────────────────────────────── */

export function useRecentBlocks(count: number = 20) {
  return useQuery<Block[]>({
    queryKey: ["explorer", "recentBlocks", count],
    queryFn: async () => {
      if (USE_MOCK) return engine().blocks.slice(-count).reverse();
      const tip = await get<Record<string, unknown>>("/chain/tip");
      const tipHeight = (tip.height as number) ?? 0;
      const startHeight = Math.max(0, tipHeight - count + 1);
      const fetches = [];
      for (let h = tipHeight; h >= startHeight; h--) {
        fetches.push(
          get<Record<string, unknown>>(`/block/${h}`).catch(() => null)
        );
      }
      const results = await Promise.all(fetches);
      return results
        .filter((r): r is Record<string, unknown> => r !== null)
        .map(mapBlockToFrontend);
    },
    staleTime: STALE_TIME,
  });
}

export function useBlock(height: number | undefined) {
  return useQuery<Block | undefined>({
    queryKey: ["explorer", "block", height],
    queryFn: async () => {
      if (height === undefined) return undefined;
      if (USE_MOCK) return engine().getBlock(height);
      const raw = await get<Record<string, unknown>>(`/block/${height}`);
      return mapBlockToFrontend(raw);
    },
    enabled: height !== undefined,
    staleTime: 60_000,
  });
}

export function useBlockTransactions(height: number | undefined) {
  return useQuery<Transaction[]>({
    queryKey: ["explorer", "blockTxs", height],
    queryFn: async () => {
      if (height === undefined) return [];
      if (USE_MOCK) return engine().getTransactionsForBlock(height);
      const block = await get<Record<string, unknown>>(`/block/${height}`);
      const txs = (block.transactions as Array<Record<string, unknown>>) ?? [];
      return txs.map(mapTxToFrontend);
    },
    enabled: height !== undefined,
    staleTime: 60_000,
  });
}

/* ── Transactions ─────────────────────────────────────────────────────── */

function mapTxToFrontend(raw: Record<string, unknown>): Transaction {
  return {
    txid: (raw.txid as string) ?? "",
    blockHeight: (raw.block_height as number) ?? 0,
    blockHash: (raw.block_hash as string) ?? "",
    timestamp: (raw.timestamp as number) ?? 0,
    from: (raw.from as string) ?? (raw.sender as string) ?? "",
    to: (raw.to as string) ?? (raw.to_address as string) ?? "",
    value: (raw.value as number) ?? (raw.amount as number) ?? 0,
    fee: (raw.fee as number) ?? 0,
    size: (raw.size as number) ?? 0,
    type: (raw.type as Transaction["type"]) ?? "transfer",
    status: (raw.status as Transaction["status"]) ?? "confirmed",
    confirmations: (raw.confirmations as number) ?? 0,
    isPrivate: (raw.is_private as boolean) ?? false,
    inputs: (raw.inputs as Transaction["inputs"]) ?? [],
    outputs: (raw.outputs as Transaction["outputs"]) ?? [],
    gasUsed: raw.gas_used as number | undefined,
    contractAddress: raw.contract_address as string | undefined,
    data: raw.data as string | undefined,
  };
}

export function useRecentTransactions(count: number = 30) {
  return useQuery<Transaction[]>({
    queryKey: ["explorer", "recentTxs", count],
    queryFn: async () => {
      if (USE_MOCK) return engine().transactions.slice(-count).reverse();
      const mempool = await get<{ transactions: Array<Record<string, unknown>> }>("/mempool");
      const pending = (mempool.transactions ?? []).map(mapTxToFrontend);
      // Supplement with recent block transactions if mempool is sparse
      if (pending.length < count) {
        const tip = await get<Record<string, unknown>>("/chain/tip").catch(() => null);
        if (tip) {
          const tipHeight = (tip.height as number) ?? 0;
          const remaining = count - pending.length;
          const blockFetches = [];
          for (let h = tipHeight; h >= Math.max(0, tipHeight - remaining); h--) {
            blockFetches.push(
              get<Record<string, unknown>>(`/block/${h}`).catch(() => null)
            );
          }
          const blocks = await Promise.all(blockFetches);
          for (const b of blocks) {
            if (!b) continue;
            const txs = (b.transactions as Array<Record<string, unknown>>) ?? [];
            for (const tx of txs) {
              pending.push(mapTxToFrontend(tx));
            }
          }
        }
      }
      return pending.slice(0, count);
    },
    staleTime: STALE_TIME,
  });
}

export function useTransaction(txid: string | undefined) {
  return useQuery<Transaction | undefined>({
    queryKey: ["explorer", "tx", txid],
    queryFn: async () => {
      if (!txid) return undefined;
      if (USE_MOCK) return engine().getTransaction(txid);
      // Try mempool first for pending txs, then search recent blocks
      const mempool = await get<{ transactions: Array<Record<string, unknown>> }>("/mempool");
      const found = (mempool.transactions ?? []).find(
        (tx) => (tx.txid as string) === txid
      );
      if (found) return mapTxToFrontend(found);
      // No dedicated tx lookup endpoint yet — return undefined
      return undefined;
    },
    enabled: !!txid,
    staleTime: 60_000,
  });
}

/* ── Contracts ────────────────────────────────────────────────────────── */

export function useContracts() {
  return useQuery<QVMContract[]>({
    queryKey: ["explorer", "contracts"],
    queryFn: async () => {
      if (USE_MOCK) return engine().contracts;
      // No listing endpoint yet — use /qvm/info for count
      const info = await get<Record<string, unknown>>("/qvm/info");
      if ((info.total_contracts as number) === 0) return [];
      // Backend has no contract listing endpoint; return empty until one exists
      return [];
    },
    staleTime: 30_000,
  });
}

export function useContract(address: string | undefined) {
  return useQuery<QVMContract | undefined>({
    queryKey: ["explorer", "contract", address],
    queryFn: async () => {
      if (!address) return undefined;
      if (USE_MOCK) return engine().getContract(address);
      const raw = await get<Record<string, unknown>>(`/qvm/contract/${address}`);
      return {
        address: (raw.address as string) ?? address,
        creator: (raw.creator as string) ?? "",
        deployHeight: (raw.deploy_height as number) ?? 0,
        deployTxid: (raw.deploy_txid as string) ?? "",
        bytecodeSize: (raw.bytecode_size as number) ?? 0,
        name: (raw.name as string) ?? "",
        standard: (raw.standard as string) ?? "",
        balance: (raw.balance as number) ?? 0,
        txCount: (raw.tx_count as number) ?? (raw.nonce as number) ?? 0,
        lastActivity: (raw.last_activity as number) ?? 0,
      };
    },
    enabled: !!address,
    staleTime: 60_000,
  });
}

/* ── Aether Tree ──────────────────────────────────────────────────────── */

export function useAetherNodes() {
  return useQuery<AetherNode[]>({
    queryKey: ["explorer", "aetherNodes"],
    queryFn: async () => {
      if (USE_MOCK) return engine().aetherNodes;
      const data = await get<{ nodes: Array<Record<string, unknown>> }>(
        "/aether/knowledge/graph?limit=200"
      );
      return (data.nodes ?? []).map((n) => ({
        id: (n.id as number) ?? 0,
        type: (n.node_type as AetherNode["type"]) ?? "observation",
        content: (n.content as string) ?? "",
        confidence: (n.confidence as number) ?? 0.5,
        blockHeight: (n.source_block as number) ?? 0,
        connections: [],
        edgeTypes: [],
      }));
    },
    staleTime: 30_000,
  });
}

export function useAetherEdges() {
  return useQuery<AetherEdge[]>({
    queryKey: ["explorer", "aetherEdges"],
    queryFn: async () => {
      if (USE_MOCK) return engine().aetherEdges;
      const data = await get<{ edges: Array<Record<string, unknown>> }>(
        "/aether/knowledge/graph?limit=200"
      );
      return (data.edges ?? []).map((e) => ({
        source: (e.source as number) ?? 0,
        target: (e.target as number) ?? 0,
        type: (e.edge_type as AetherEdge["type"]) ?? "supports",
        weight: (e.weight as number) ?? 0.5,
      }));
    },
    staleTime: 30_000,
  });
}

/* ── Miners / Leaderboard ─────────────────────────────────────────────── */

export function useMiners() {
  return useQuery<MinerStats[]>({
    queryKey: ["explorer", "miners"],
    queryFn: async () => {
      if (USE_MOCK) return engine().miners;
      const [stats, chain] = await Promise.all([
        get<Record<string, unknown>>("/mining/stats"),
        get<Record<string, unknown>>("/chain/info").catch(() => null),
      ]);
      const addr = (stats.miner_address as string) ?? "qbc1genesis";
      // Use chain height for total blocks mined (persists across restarts)
      const totalBlocks = (chain?.height as number) ?? (stats.blocks_found as number) ?? 0;
      return [{
        address: addr,
        blocksMined: totalBlocks,
        totalRewards: totalBlocks * 15.27,
        avgEnergy: (stats.best_energy as number) ?? 0,
        lastBlock: totalBlocks,
        hashPower: 0,
        susyScore: (stats.alignment_score as number) ?? 0,
        rank: 1,
      }];
    },
    staleTime: STALE_TIME,
  });
}

/* ── Wallet / Address ─────────────────────────────────────────────────── */

export function useWallet(address: string | undefined) {
  return useQuery<WalletData | undefined>({
    queryKey: ["explorer", "wallet", address],
    queryFn: async () => {
      if (!address) return undefined;
      if (USE_MOCK) return engine().getWallet(address);
      const [balData, utxoData] = await Promise.all([
        get<{ balance: string; utxo_count: number }>(`/balance/${address}`),
        get<{ utxos: Array<Record<string, unknown>> }>(`/utxos/${address}`).catch(() => ({ utxos: [] })),
      ]);
      return {
        address,
        balance: parseFloat(balData.balance) || 0,
        txCount: utxoData.utxos.length,
        firstSeen: 0,
        lastSeen: Date.now() / 1000,
        utxos: utxoData.utxos.map((u) => ({
          index: (u.vout as number) ?? 0,
          address,
          value: (u.amount as number) ?? 0,
          spent: false,
        })),
        transactions: [],
        isContract: false,
      };
    },
    enabled: !!address,
    staleTime: 30_000,
  });
}

/* ── Time Series ──────────────────────────────────────────────────────── */

export function usePhiHistory(limit: number = 10000) {
  return useQuery<PhiDataPoint[]>({
    queryKey: ["explorer", "phiHistory", limit],
    queryFn: async () => {
      if (USE_MOCK) return engine().phiHistory;
      const data = await get<{ history: Array<Record<string, unknown>> }>(
        `/aether/phi/history?limit=${limit}`
      );
      return (data.history ?? []).map((p) => ({
        block: (p.block as number) ?? (p.block_height as number) ?? 0,
        phi: (p.phi as number) ?? (p.phi_value as number) ?? 0,
        knowledgeNodes: (p.knowledgeNodes as number) ?? (p.knowledge_nodes as number) ?? 0,
        timestamp: (p.timestamp as number) ?? 0,
      }));
    },
    staleTime: 30_000,
  });
}

export function useTpsHistory() {
  return useQuery<TpsDataPoint[]>({
    queryKey: ["explorer", "tpsHistory"],
    queryFn: async () => {
      if (USE_MOCK) return engine().tpsHistory;
      // Compute TPS from recent blocks (txCount / blockTime)
      const tip = await get<Record<string, unknown>>("/chain/tip").catch(() => null);
      if (!tip) return [];
      const tipHeight = (tip.height as number) ?? 0;
      const count = Math.min(100, tipHeight);
      const fetches = [];
      for (let h = tipHeight; h > tipHeight - count && h >= 0; h--) {
        fetches.push(get<Record<string, unknown>>(`/block/${h}`).catch(() => null));
      }
      const results = (await Promise.all(fetches)).filter(
        (r): r is Record<string, unknown> => r !== null
      );
      // Compute TPS: txCount / time_since_prev_block
      const sorted = results
        .map(mapBlockToFrontend)
        .sort((a, b) => a.height - b.height);
      const tpsData: TpsDataPoint[] = [];
      for (let i = 1; i < sorted.length; i++) {
        const dt = sorted[i].timestamp - sorted[i - 1].timestamp;
        const tps = dt > 0 ? sorted[i].txCount / dt : 0;
        tpsData.push({
          block: sorted[i].height,
          tps: Math.round(tps * 100) / 100,
          timestamp: sorted[i].timestamp,
        });
      }
      return tpsData;
    },
    staleTime: 30_000,
  });
}

export function useDifficultyHistory() {
  return useQuery<DifficultyDataPoint[]>({
    queryKey: ["explorer", "difficultyHistory"],
    queryFn: async () => {
      if (USE_MOCK) return engine().difficultyHistory;
      // Compute difficulty from recent blocks
      const tip = await get<Record<string, unknown>>("/chain/tip").catch(() => null);
      if (!tip) return [];
      const tipHeight = (tip.height as number) ?? 0;
      const count = Math.min(200, tipHeight);
      const fetches = [];
      for (let h = tipHeight; h > tipHeight - count && h >= 0; h--) {
        fetches.push(get<Record<string, unknown>>(`/block/${h}`).catch(() => null));
      }
      const results = (await Promise.all(fetches)).filter(
        (r): r is Record<string, unknown> => r !== null
      );
      return results
        .map(mapBlockToFrontend)
        .sort((a, b) => a.height - b.height)
        .map((b) => ({
          block: b.height,
          difficulty: b.difficulty,
          timestamp: b.timestamp,
        }));
    },
    staleTime: 30_000,
  });
}

/* ── Search ───────────────────────────────────────────────────────────── */

export function useSearch(query: string) {
  return useQuery({
    queryKey: ["explorer", "search", query],
    queryFn: async () => {
      if (USE_MOCK) return engine().search(query);
      const results: Array<{ type: string; id: string; label: string }> = [];
      const trimmed = query.trim();

      // If numeric, try as block height
      if (/^\d+$/.test(trimmed)) {
        const block = await get<Record<string, unknown>>(`/block/${trimmed}`).catch(() => null);
        if (block) {
          results.push({
            type: "block",
            id: trimmed,
            label: `Block #${trimmed} (${(block.hash as string)?.slice(0, 12) ?? ""}...)`,
          });
        }
      }

      // If starts with qbc1, try as address
      if (trimmed.startsWith("qbc1") || trimmed.length === 40 || trimmed.length === 42) {
        const addr = trimmed.startsWith("0x") ? trimmed.slice(2) : trimmed;
        const bal = await get<Record<string, unknown>>(`/balance/${addr}`).catch(() => null);
        if (bal) {
          results.push({
            type: "address",
            id: addr,
            label: `Address ${addr.slice(0, 12)}... (${bal.balance ?? 0} QBC)`,
          });
        }
      }

      // If hex string, could be tx hash or contract address
      if (/^(0x)?[0-9a-fA-F]{40,64}$/.test(trimmed)) {
        const addr = trimmed.startsWith("0x") ? trimmed.slice(2) : trimmed;
        const contract = await get<Record<string, unknown>>(`/qvm/contract/${addr}`).catch(() => null);
        if (contract) {
          results.push({
            type: "contract",
            id: addr,
            label: `Contract ${addr.slice(0, 12)}...`,
          });
        }
      }

      return results;
    },
    enabled: query.length >= 2,
    staleTime: 10_000,
  });
}

/* ── Pathfinder ───────────────────────────────────────────────────────── */

export function usePathfinder(
  from: string | undefined,
  to: string | undefined
) {
  return useQuery({
    queryKey: ["explorer", "pathfinder", from, to],
    queryFn: () => {
      if (!from || !to) return null;
      if (USE_MOCK) return engine().findPath(from, to);
      // No dedicated pathfinder endpoint yet — return null
      return null;
    },
    enabled: !!from && !!to,
    staleTime: 60_000,
  });
}

/* ── Aether Explorer Hooks ────────────────────────────────────────────── */

/* Actual API endpoints available on the node:
 *   /aether/consciousness      — phi, integration, differentiation, gates, etc.
 *   /aether/knowledge/graph    — nodes[] + edges[] (with limit param)
 *   /aether/knowledge          — node/edge counts + type distributions
 *   /aether/phi/history        — phi over blocks
 *   /aether/reasoning/stats    — total_operations, operation_types, success_rate
 *   /aether/sephirot           — dict of {name: {role, active, energy, qubits, ...}}
 *   /aether/consciousness/events — {events: [], total: 0}
 *   /higgs/status              — field_value, vev, potential_energy, node_masses, etc.
 *   /higgs/masses              — {name: mass} dict
 *   /higgs/excitations         — {total, recent: [...]}
 *   /aether/memory/stats       — ipfs cache stats
 *   /aether/info               — full knowledge graph + reasoning stats
 *
 * NOT available (hooks derive from existing data):
 *   /aether/reasoning/operations, /aether/predictions, /aether/safety/events,
 *   /aether/proofs, /aether/pineal, /aether/sephirot/balance
 */

export function useKnowledgeNodes(limit: number = 100) {
  return useQuery<KnowledgeNodeDetail[]>({
    queryKey: ["explorer", "knowledgeNodes", limit],
    queryFn: async () => {
      if (USE_MOCK) {
        return (engine().aetherNodes ?? []).map((n) => ({
          ...n,
          timestamp: Date.now() / 1000 - Math.random() * 86400,
          sourceModule: ["consensus", "mining", "reasoning", "observation"][n.id % 4],
        }));
      }
      const data = await get<{ nodes: Array<Record<string, unknown>> }>(
        `/aether/knowledge/graph?limit=${limit}`
      );
      return (data.nodes ?? []).map((n) => ({
        id: (n.id as number) ?? 0,
        type: (n.node_type as KnowledgeNodeDetail["type"]) ?? "observation",
        content: (n.content as string) ?? "",
        confidence: (n.confidence as number) ?? 0.5,
        blockHeight: (n.source_block as number) ?? 0,
        timestamp: (n.timestamp as number) ?? 0,
        connections: (n.connections as number[]) ?? [],
        edgeTypes: (n.edge_types as string[]) ?? [],
        sourceModule: (n.source_module as string) ?? (n.node_type as string) ?? "unknown",
      }));
    },
    staleTime: 15_000,
  });
}

export function useReasoningOps(_limit: number = 50) {
  return useQuery<ReasoningOperation[]>({
    queryKey: ["explorer", "reasoningOps"],
    queryFn: async () => {
      if (USE_MOCK) {
        const types: ReasoningOperation["type"][] = ["deductive", "inductive", "abductive"];
        return Array.from({ length: 20 }, (_, i) => ({
          id: `rop-${i}`,
          type: types[i % 3],
          premise: `Observation from block ${1000 + i}: pattern detected`,
          conclusion: `Inference ${i}: derived relationship confirmed`,
          confidence: 0.5 + Math.random() * 0.5,
          blockHeight: 1000 + i,
          timestamp: Date.now() / 1000 - i * 10,
          nodesReferenced: [i, i + 1, i + 2],
          chainLength: 1 + (i % 4),
        }));
      }
      // Use /aether/reasoning/stats for aggregate data + knowledge graph inference nodes
      const [stats, graphData] = await Promise.all([
        get<Record<string, unknown>>("/aether/reasoning/stats").catch(() => null),
        get<{ nodes: Array<Record<string, unknown>> }>("/aether/knowledge/graph?limit=100").catch(() => null),
      ]);
      const ops: ReasoningOperation[] = [];
      // Extract inference nodes from knowledge graph as reasoning operations
      if (graphData?.nodes) {
        const inferenceNodes = graphData.nodes.filter((n) => n.node_type === "inference");
        for (const n of inferenceNodes.slice(0, 50)) {
          const content = (n.content as string) ?? "";
          // Determine type from content
          let type: ReasoningOperation["type"] = "inductive";
          if (content.includes("deduct") || content.includes("derive")) type = "deductive";
          else if (content.includes("abduct") || content.includes("hypothes")) type = "abductive";
          else if (content.includes("general") || content.includes("pattern")) type = "inductive";
          ops.push({
            id: `node-${n.id}`,
            type,
            premise: content.slice(0, 120),
            conclusion: content,
            confidence: (n.confidence as number) ?? 0.5,
            blockHeight: (n.source_block as number) ?? 0,
            timestamp: Date.now() / 1000,
            nodesReferenced: [],
            chainLength: 1,
          });
        }
      }
      // Add aggregate stats info
      if (stats && ops.length === 0) {
        const types = (stats.operation_types as Record<string, number>) ?? {};
        for (const [t, count] of Object.entries(types)) {
          ops.push({
            id: `stat-${t}`,
            type: t as ReasoningOperation["type"],
            premise: `${count} ${t} operations performed`,
            conclusion: `Success rate: ${((stats.success_rate as number) ?? 0 * 100).toFixed(0)}%`,
            confidence: (stats.avg_confidence as number) ?? 0.5,
            blockHeight: 0,
            timestamp: Date.now() / 1000,
            nodesReferenced: [],
            chainLength: 1,
          });
        }
      }
      return ops;
    },
    staleTime: 15_000,
  });
}

export function useConsciousnessState() {
  return useQuery<ConsciousnessState>({
    queryKey: ["explorer", "consciousness"],
    queryFn: async () => {
      if (USE_MOCK) {
        return {
          phi: 1.247, threshold: 3.0, aboveThreshold: false,
          integration: 0.82, differentiation: 0.67, knowledgeNodes: 1450,
          knowledgeEdges: 3200, consciousnessEvents: 3,
          reasoningOperations: 892, blocksProcessed: 1500,
        };
      }
      const [raw, reasonStats] = await Promise.all([
        get<Record<string, unknown>>("/aether/consciousness"),
        get<Record<string, unknown>>("/aether/reasoning/stats").catch(() => null),
      ]);
      return {
        phi: (raw.phi as number) ?? 0,
        threshold: (raw.threshold as number) ?? 3.0,
        aboveThreshold: (raw.above_threshold as boolean) ?? false,
        integration: (raw.integration as number) ?? 0,
        differentiation: (raw.differentiation as number) ?? 0,
        knowledgeNodes: (raw.knowledge_nodes as number) ?? 0,
        knowledgeEdges: (raw.knowledge_edges as number) ?? 0,
        consciousnessEvents: (raw.gates_passed as number) ?? 0,
        reasoningOperations: (reasonStats?.total_operations as number) ?? 0,
        blocksProcessed: (raw.blocks_processed as number) ?? 0,
      };
    },
    staleTime: 10_000,
    refetchInterval: 10_000,
  });
}

export function useConsciousnessEvents(_limit: number = 20) {
  return useQuery<ConsciousnessEvent[]>({
    queryKey: ["explorer", "consciousnessEvents"],
    queryFn: async () => {
      if (USE_MOCK) {
        return [
          { id: 1, type: "genesis", phi: 0, blockHeight: 0, timestamp: Date.now() / 1000 - 50000, description: "System genesis — consciousness tracking initialized" },
          { id: 2, type: "phi_milestone", phi: 0.5, blockHeight: 300, timestamp: Date.now() / 1000 - 40000, description: "Phi crossed 0.5 — basic integration detected" },
          { id: 3, type: "phi_milestone", phi: 1.0, blockHeight: 800, timestamp: Date.now() / 1000 - 25000, description: "Phi crossed 1.0 — significant information integration" },
        ];
      }
      // Use consciousness gates as events (they represent milestones)
      const raw = await get<Record<string, unknown>>("/aether/consciousness");
      const gates = (raw.gates as Array<Record<string, unknown>>) ?? [];
      const events: ConsciousnessEvent[] = gates.map((g, i) => ({
        id: (g.id as number) ?? i,
        type: (g.passed as boolean) ? "gate_passed" : "gate_pending",
        phi: (raw.phi as number) ?? 0,
        blockHeight: 0,
        timestamp: Date.now() / 1000,
        description: `${(g.name as string) ?? "Gate"}: ${(g.description as string) ?? ""} [${(g.passed as boolean) ? "PASSED" : "pending"}]`,
      }));
      return events;
    },
    staleTime: 30_000,
  });
}

export function useSephirotNodes() {
  return useQuery<SephirotNode[]>({
    queryKey: ["explorer", "sephirot"],
    queryFn: async () => {
      if (USE_MOCK) {
        const PHI = 1.618033988749895;
        return [
          { name: "Keter", function: "Meta-learning, goal formation", energy: 85, quantumState: "8-qubit goal space", cognitiveMass: 174.14, yukawaCoupling: 1.0, tier: 0, isActive: true, susyPartner: "" },
          { name: "Chochmah", function: "Intuition, pattern discovery", energy: 72, quantumState: "6-qubit idea superposition", cognitiveMass: 174.14 / PHI, yukawaCoupling: 1 / PHI, tier: 1, isActive: true, susyPartner: "Binah" },
          { name: "Binah", function: "Logic, causal inference", energy: 68, quantumState: "4-qubit truth verification", cognitiveMass: 174.14 / PHI, yukawaCoupling: 1 / PHI, tier: 1, isActive: true, susyPartner: "Chochmah" },
          { name: "Chesed", function: "Exploration, divergent thinking", energy: 78, quantumState: "10-qubit possibility space", cognitiveMass: 174.14 / (PHI * PHI), yukawaCoupling: 1 / (PHI * PHI), tier: 2, isActive: true, susyPartner: "Gevurah" },
          { name: "Gevurah", function: "Constraint, safety validation", energy: 65, quantumState: "3-qubit threat detection", cognitiveMass: 174.14 / (PHI * PHI), yukawaCoupling: 1 / (PHI * PHI), tier: 2, isActive: true, susyPartner: "Chesed" },
          { name: "Tiferet", function: "Integration, conflict resolution", energy: 80, quantumState: "12-qubit synthesis state", cognitiveMass: 174.14 / PHI, yukawaCoupling: 1 / PHI, tier: 1, isActive: true, susyPartner: "" },
          { name: "Netzach", function: "Reinforcement learning", energy: 55, quantumState: "5-qubit policy learning", cognitiveMass: 174.14 / (PHI * PHI * PHI), yukawaCoupling: 1 / (PHI * PHI * PHI), tier: 3, isActive: true, susyPartner: "Hod" },
          { name: "Hod", function: "Language, semantic encoding", energy: 60, quantumState: "7-qubit semantic encoding", cognitiveMass: 174.14 / (PHI * PHI * PHI), yukawaCoupling: 1 / (PHI * PHI * PHI), tier: 3, isActive: true, susyPartner: "Netzach" },
          { name: "Yesod", function: "Memory, multimodal fusion", energy: 45, quantumState: "16-qubit episodic buffer", cognitiveMass: 174.14 / (PHI * PHI * PHI * PHI), yukawaCoupling: 1 / (PHI * PHI * PHI * PHI), tier: 4, isActive: true, susyPartner: "" },
          { name: "Malkuth", function: "Action, world interaction", energy: 40, quantumState: "4-qubit motor commands", cognitiveMass: 174.14 / (PHI * PHI * PHI * PHI), yukawaCoupling: 1 / (PHI * PHI * PHI * PHI), tier: 4, isActive: true, susyPartner: "" },
        ];
      }
      // API returns {keter: {...}, chochmah: {...}, ...} — a dict, not an array
      const [sephData, massData] = await Promise.all([
        get<Record<string, Record<string, unknown>>>("/aether/sephirot"),
        get<Record<string, number>>("/higgs/masses").catch(() => null),
      ]);
      const PHI = 1.618033988749895;
      const SEPHIROT_META: Record<string, { fn: string; qs: string; tier: number; partner: string }> = {
        keter: { fn: "Meta-learning, goal formation", qs: "8-qubit goal space", tier: 0, partner: "" },
        chochmah: { fn: "Intuition, pattern discovery", qs: "6-qubit idea superposition", tier: 1, partner: "Binah" },
        binah: { fn: "Logic, causal inference", qs: "4-qubit truth verification", tier: 1, partner: "Chochmah" },
        chesed: { fn: "Exploration, divergent thinking", qs: "10-qubit possibility space", tier: 2, partner: "Gevurah" },
        gevurah: { fn: "Constraint, safety validation", qs: "3-qubit threat detection", tier: 2, partner: "Chesed" },
        tiferet: { fn: "Integration, conflict resolution", qs: "12-qubit synthesis state", tier: 1, partner: "" },
        netzach: { fn: "Reinforcement learning, habits", qs: "5-qubit policy learning", tier: 3, partner: "Hod" },
        hod: { fn: "Language, semantic encoding", qs: "7-qubit semantic encoding", tier: 3, partner: "Netzach" },
        yesod: { fn: "Memory, multimodal fusion", qs: "16-qubit episodic buffer", tier: 4, partner: "" },
        malkuth: { fn: "Action, world interaction", qs: "4-qubit motor commands", tier: 4, partner: "" },
      };
      const TIER_YUKAWA = [1.0, 1 / PHI, 1 / (PHI * PHI), 1 / (PHI * PHI * PHI), 1 / (PHI * PHI * PHI * PHI)];
      const nodes: SephirotNode[] = [];
      for (const [key, data] of Object.entries(sephData)) {
        if (!data || typeof data !== "object" || !("role" in data)) continue;
        const meta = SEPHIROT_META[key] ?? { fn: "", qs: "", tier: 4, partner: "" };
        const name = key.charAt(0).toUpperCase() + key.slice(1);
        nodes.push({
          name,
          function: meta.fn,
          energy: (data.energy as number) ?? 0,
          quantumState: meta.qs,
          cognitiveMass: massData?.[key] ?? 0,
          yukawaCoupling: TIER_YUKAWA[meta.tier] ?? 0,
          tier: meta.tier,
          isActive: (data.active as boolean) ?? false,
          susyPartner: meta.partner,
        });
      }
      // Sort by tier
      nodes.sort((a, b) => a.tier - b.tier);
      return nodes;
    },
    staleTime: 15_000,
  });
}

export function useSephirotBalance() {
  return useQuery<SephirotBalance[]>({
    queryKey: ["explorer", "sephirotBalance"],
    queryFn: async () => {
      if (USE_MOCK) {
        const PHI = 1.618033988749895;
        return [
          { expansion: "Chesed", constraint: "Gevurah", ratio: 1.62, targetRatio: PHI, balanced: true },
          { expansion: "Chochmah", constraint: "Binah", ratio: 1.58, targetRatio: PHI, balanced: false },
          { expansion: "Netzach", constraint: "Hod", ratio: 1.65, targetRatio: PHI, balanced: true },
        ];
      }
      // Compute SUSY balance from sephirot energy data
      const sephData = await get<Record<string, Record<string, unknown>>>("/aether/sephirot").catch(() => null);
      if (!sephData) return [];
      const PHI = 1.618033988749895;
      const pairs: [string, string, string, string][] = [
        ["Chesed", "chesed", "Gevurah", "gevurah"],
        ["Chochmah", "chochmah", "Binah", "binah"],
        ["Netzach", "netzach", "Hod", "hod"],
      ];
      return pairs.map(([expName, expKey, conName, conKey]) => {
        const expEnergy = (sephData[expKey]?.energy as number) ?? 1;
        const conEnergy = (sephData[conKey]?.energy as number) ?? 1;
        const ratio = conEnergy > 0 ? expEnergy / conEnergy : 0;
        const deviation = Math.abs(ratio - PHI) / PHI;
        return {
          expansion: expName,
          constraint: conName,
          ratio,
          targetRatio: PHI,
          balanced: deviation < 0.1, // within 10% of phi
        };
      });
    },
    staleTime: 15_000,
  });
}

export function usePredictions(_limit: number = 30) {
  return useQuery<PredictionRecord[]>({
    queryKey: ["explorer", "predictions"],
    queryFn: async () => {
      if (USE_MOCK) {
        return Array.from({ length: 15 }, (_, i) => ({
          id: `pred-${i}`, prediction: `Temporal prediction ${i}`,
          outcome: i < 10 ? `Verified at block ${1200 + i}` : null,
          confidence: 0.4 + Math.random() * 0.5, blockHeight: 1000 + i * 10,
          timestamp: Date.now() / 1000 - i * 300, verified: i < 10,
          correct: i < 10 ? Math.random() > 0.3 : null,
          domain: ["temporal", "causal", "pattern", "structural"][i % 4],
        }));
      }
      // Extract prediction nodes from knowledge graph
      const data = await get<{ nodes: Array<Record<string, unknown>> }>(
        "/aether/knowledge/graph?limit=200"
      ).catch(() => null);
      if (!data?.nodes) return [];
      const predNodes = data.nodes.filter((n) => n.node_type === "prediction");
      return predNodes.slice(0, 30).map((n, i) => ({
        id: `pred-${n.id ?? i}`,
        prediction: (n.content as string) ?? "",
        outcome: null,
        confidence: (n.confidence as number) ?? 0.5,
        blockHeight: (n.source_block as number) ?? 0,
        timestamp: Date.now() / 1000,
        verified: false,
        correct: null,
        domain: "temporal",
      }));
    },
    staleTime: 30_000,
  });
}

export function useSafetyEvents(_limit: number = 20) {
  return useQuery<SafetyEvent[]>({
    queryKey: ["explorer", "safetyEvents"],
    queryFn: async () => {
      if (USE_MOCK) {
        return [
          { id: "se-1", type: "susy_violation" as const, severity: "low" as const, description: "Chesed/Gevurah ratio deviated — auto-corrected", blockHeight: 1200, timestamp: Date.now() / 1000 - 5000, resolved: true, action: "QBC redistributed" },
        ];
      }
      // Derive safety info from higgs excitations (field deviations = safety-relevant)
      const higgs = await get<Record<string, unknown>>("/higgs/excitations").catch(() => null);
      if (!higgs) return [];
      const recent = (higgs.recent as Array<Record<string, unknown>>) ?? [];
      return recent.slice(0, 20).map((ex, i) => ({
        id: `higgs-${i}`,
        type: "susy_violation" as const,
        severity: ((ex.deviation_bps as number) ?? 0) > 2000 ? "high" as const : ((ex.deviation_bps as number) ?? 0) > 1000 ? "medium" as const : "low" as const,
        description: `Higgs field deviation: ${((ex.deviation_bps as number) ?? 0) / 100}% from VEV (energy: ${((ex.energy as number) ?? 0).toFixed(1)})`,
        blockHeight: (ex.block as number) ?? 0,
        timestamp: Date.now() / 1000,
        resolved: true,
        action: "Field damping applied",
      }));
    },
    staleTime: 30_000,
  });
}

export function useProofOfThought(_limit: number = 30) {
  return useQuery<ProofOfThought[]>({
    queryKey: ["explorer", "proofOfThought"],
    queryFn: async () => {
      if (USE_MOCK) {
        return Array.from({ length: 20 }, (_, i) => ({
          hash: `0x${Array.from({ length: 64 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join("")}`,
          blockHeight: 1500 - i, timestamp: Date.now() / 1000 - i * 3.3,
          taskType: ["auto_reason", "block_knowledge"][i % 2],
          nodesReferenced: 3 + (i % 8), reasoningSteps: 2 + (i % 5),
          phiAtProof: 1.1 + Math.random() * 0.3, validatorCount: 1, consensusReached: true,
        }));
      }
      // Derive from phi history — each phi measurement is effectively a PoT
      const [phiData, reasonStats] = await Promise.all([
        get<{ history: Array<Record<string, unknown>> }>("/aether/phi/history?limit=30").catch(() => null),
        get<Record<string, unknown>>("/aether/reasoning/stats").catch(() => null),
      ]);
      if (!phiData?.history) return [];
      const totalOps = (reasonStats?.total_operations as number) ?? 0;
      return phiData.history.map((p, i) => {
        const block = (p.block as number) ?? (p.block_height as number) ?? 0;
        return {
          hash: `0x${block.toString(16).padStart(8, "0")}${"a".repeat(56)}`,
          blockHeight: block,
          timestamp: (p.timestamp as number) ?? Date.now() / 1000 - i * 3.3,
          taskType: i % 3 === 0 ? "auto_reason" : i % 3 === 1 ? "block_knowledge" : "cross_domain",
          nodesReferenced: Math.floor(totalOps / Math.max(1, phiData.history.length)),
          reasoningSteps: 3,
          phiAtProof: (p.phi as number) ?? (p.phi_value as number) ?? 0,
          validatorCount: 1,
          consensusReached: true,
        };
      });
    },
    staleTime: 15_000,
  });
}

export function useHiggsField() {
  return useQuery<HiggsFieldState>({
    queryKey: ["explorer", "higgsField"],
    queryFn: async () => {
      if (USE_MOCK) {
        return {
          fieldValue: 172.8, vev: 174.14, potentialEnergy: -4523.7,
          symmetryBroken: true, excitationCount: 7, massGap: 0.034, yukawaMax: 1.0,
        };
      }
      const raw = await get<Record<string, unknown>>("/higgs/status");
      return {
        fieldValue: (raw.field_value as number) ?? 0,
        vev: (raw.vev as number) ?? 174.14,
        potentialEnergy: (raw.potential_energy as number) ?? 0,
        symmetryBroken: ((raw.deviation_pct as number) ?? 0) > 0,
        excitationCount: (raw.total_excitations as number) ?? 0,
        massGap: (raw.mass_gap as number) ?? 0,
        yukawaMax: 1.0, // Keter is always max
      };
    },
    staleTime: 15_000,
  });
}

export function usePinealPhase() {
  return useQuery<PinealPhase>({
    queryKey: ["explorer", "pinealPhase"],
    queryFn: async () => {
      if (USE_MOCK) {
        return {
          phase: "Active Learning", metabolicRate: 2.0,
          coherence: 0.72, kuramotoOrder: 0.68, cyclePosition: 0.35,
        };
      }
      // Derive from aether/info which includes cognitive state
      const raw = await get<Record<string, unknown>>("/aether/info").catch(() => null);
      if (!raw) {
        return { phase: "Active", metabolicRate: 1.0, coherence: 0, kuramotoOrder: 0, cyclePosition: 0 };
      }
      const cognitive = (raw.cognitive as Record<string, unknown>) ?? {};
      return {
        phase: (cognitive.phase as string) ?? (cognitive.pineal_phase as string) ?? "Active",
        metabolicRate: (cognitive.metabolic_rate as number) ?? 1.0,
        coherence: (cognitive.coherence as number) ?? (cognitive.phase_coherence as number) ?? 0,
        kuramotoOrder: (cognitive.kuramoto_order as number) ?? 0,
        cyclePosition: (cognitive.cycle_position as number) ?? 0,
      };
    },
    staleTime: 10_000,
  });
}

export function useMemoryStats() {
  return useQuery<MemoryStats>({
    queryKey: ["explorer", "memoryStats"],
    queryFn: async () => {
      if (USE_MOCK) {
        return { episodic: 342, semantic: 1205, procedural: 89, workingMemory: 12, totalCapacity: 10000 };
      }
      // Derive from knowledge graph type counts
      const [kgStats, memRaw] = await Promise.all([
        get<Record<string, unknown>>("/aether/knowledge").catch(() => null),
        get<Record<string, unknown>>("/aether/memory/stats").catch(() => null),
      ]);
      const nodeTypes = (kgStats?.node_types as Record<string, number>) ?? {};
      return {
        episodic: nodeTypes["observation"] ?? 0,
        semantic: nodeTypes["inference"] ?? 0,
        procedural: nodeTypes["axiom"] ?? 0,
        workingMemory: (memRaw?.local_cache_size as number) ?? nodeTypes["assertion"] ?? 0,
        totalCapacity: (memRaw?.max_cache as number) ?? 100000,
      };
    },
    staleTime: 30_000,
  });
}
