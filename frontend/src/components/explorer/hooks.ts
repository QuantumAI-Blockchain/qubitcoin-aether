/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — React Query Hooks

   Fetches from the real QBC node API when available, falls back to
   MockDataEngine when the node is unreachable (dev mode).
   ───────────────────────────────────────────────────────────────────────── */

import { useQuery } from "@tanstack/react-query";
import { getMockEngine } from "./mock-engine";
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
} from "./types";

const STALE_TIME = 10_000;

/** Check if we should use mock data (no node running or SSR). */
const USE_MOCK = typeof window !== "undefined"
  ? process.env.NEXT_PUBLIC_USE_MOCK_DATA === "true"
  : true;

function engine() {
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
      try {
        const [chain, phi] = await Promise.all([
          get<Record<string, unknown>>("/chain/info"),
          get<Record<string, unknown>>("/aether/consciousness").catch(() => null),
        ]);
        const stats = mapChainInfoToStats(chain);
        if (phi) {
          stats.phi = (phi.phi as number) ?? 0;
          stats.knowledgeNodes = (phi.knowledge_nodes as number) ?? 0;
        }
        return stats;
      } catch {
        return engine().getNetworkStats();
      }
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
      try {
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
      } catch {
        return engine().blocks.slice(-count).reverse();
      }
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
      try {
        const raw = await get<Record<string, unknown>>(`/block/${height}`);
        return mapBlockToFrontend(raw);
      } catch {
        return engine().getBlock(height);
      }
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
      try {
        const block = await get<Record<string, unknown>>(`/block/${height}`);
        const txs = (block.transactions as Array<Record<string, unknown>>) ?? [];
        return txs.map(mapTxToFrontend);
      } catch {
        return engine().getTransactionsForBlock(height);
      }
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
      try {
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
      } catch {
        return engine().transactions.slice(-count).reverse();
      }
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
      try {
        // Try mempool first for pending txs, then search recent blocks
        const mempool = await get<{ transactions: Array<Record<string, unknown>> }>("/mempool");
        const found = (mempool.transactions ?? []).find(
          (tx) => (tx.txid as string) === txid
        );
        if (found) return mapTxToFrontend(found);
        // Fallback to mock if no dedicated tx lookup endpoint
        return engine().getTransaction(txid);
      } catch {
        return engine().getTransaction(txid);
      }
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
      try {
        // No listing endpoint yet — use /qvm/info for count, fall back to mock for details
        const info = await get<Record<string, unknown>>("/qvm/info");
        if ((info.total_contracts as number) === 0) return [];
        // Backend has no contract listing endpoint; fall back to mock data
        return engine().contracts;
      } catch {
        return engine().contracts;
      }
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
      try {
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
      } catch {
        return engine().getContract(address);
      }
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
      try {
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
      } catch {
        return engine().aetherNodes;
      }
    },
    staleTime: 30_000,
  });
}

export function useAetherEdges() {
  return useQuery<AetherEdge[]>({
    queryKey: ["explorer", "aetherEdges"],
    queryFn: async () => {
      if (USE_MOCK) return engine().aetherEdges;
      try {
        const data = await get<{ edges: Array<Record<string, unknown>> }>(
          "/aether/knowledge/graph?limit=200"
        );
        return (data.edges ?? []).map((e) => ({
          source: (e.source as number) ?? 0,
          target: (e.target as number) ?? 0,
          type: (e.edge_type as AetherEdge["type"]) ?? "supports",
          weight: (e.weight as number) ?? 0.5,
        }));
      } catch {
        return engine().aetherEdges;
      }
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
      try {
        const stats = await get<Record<string, unknown>>("/mining/stats");
        const addr = (stats.miner_address as string) ?? "qbc1genesis";
        return [{
          address: addr,
          blocksMined: (stats.blocks_found as number) ?? 0,
          totalRewards: ((stats.blocks_found as number) ?? 0) * 15.27,
          avgEnergy: (stats.best_energy as number) ?? 0,
          lastBlock: 0,
          hashPower: 0,
          susyScore: (stats.alignment_score as number) ?? 0,
          rank: 1,
        }];
      } catch {
        return engine().miners;
      }
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
      try {
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
      } catch {
        return engine().getWallet(address);
      }
    },
    enabled: !!address,
    staleTime: 30_000,
  });
}

/* ── Time Series ──────────────────────────────────────────────────────── */

export function usePhiHistory() {
  return useQuery<PhiDataPoint[]>({
    queryKey: ["explorer", "phiHistory"],
    queryFn: async () => {
      if (USE_MOCK) return engine().phiHistory;
      try {
        const data = await get<{ history: Array<Record<string, unknown>> }>(
          "/aether/phi/history"
        );
        return (data.history ?? []).map((p) => ({
          block: (p.block as number) ?? (p.block_height as number) ?? 0,
          phi: (p.phi as number) ?? (p.phi_value as number) ?? 0,
          knowledgeNodes: (p.knowledgeNodes as number) ?? (p.knowledge_nodes as number) ?? 0,
          timestamp: (p.timestamp as number) ?? 0,
        }));
      } catch {
        return engine().phiHistory;
      }
    },
    staleTime: 30_000,
  });
}

export function useTpsHistory() {
  return useQuery<TpsDataPoint[]>({
    queryKey: ["explorer", "tpsHistory"],
    queryFn: () => engine().tpsHistory,
    staleTime: 30_000,
  });
}

export function useDifficultyHistory() {
  return useQuery<DifficultyDataPoint[]>({
    queryKey: ["explorer", "difficultyHistory"],
    queryFn: () => engine().difficultyHistory,
    staleTime: 30_000,
  });
}

/* ── Search ───────────────────────────────────────────────────────────── */

export function useSearch(query: string) {
  return useQuery({
    queryKey: ["explorer", "search", query],
    queryFn: async () => {
      if (USE_MOCK) return engine().search(query);
      try {
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

        if (results.length > 0) return results;
        // Fall back to mock search
        return engine().search(query);
      } catch {
        return engine().search(query);
      }
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
    queryFn: () =>
      from && to ? engine().findPath(from, to) : null,
    enabled: !!from && !!to,
    staleTime: 60_000,
  });
}
