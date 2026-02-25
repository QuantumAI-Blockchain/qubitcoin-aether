/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — React Query Hooks (backed by MockDataEngine)
   ───────────────────────────────────────────────────────────────────────── */

import { useQuery } from "@tanstack/react-query";
import { getMockEngine } from "./mock-engine";
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

function engine() {
  return getMockEngine();
}

/* ── Network ──────────────────────────────────────────────────────────── */

export function useNetworkStats() {
  return useQuery<NetworkStats>({
    queryKey: ["explorer", "networkStats"],
    queryFn: () => engine().getNetworkStats(),
    staleTime: STALE_TIME,
    refetchInterval: 5_000,
  });
}

/* ── Blocks ───────────────────────────────────────────────────────────── */

export function useRecentBlocks(count: number = 20) {
  return useQuery<Block[]>({
    queryKey: ["explorer", "recentBlocks", count],
    queryFn: () => engine().blocks.slice(-count).reverse(),
    staleTime: STALE_TIME,
  });
}

export function useBlock(height: number | undefined) {
  return useQuery<Block | undefined>({
    queryKey: ["explorer", "block", height],
    queryFn: () => (height !== undefined ? engine().getBlock(height) : undefined),
    enabled: height !== undefined,
    staleTime: 60_000,
  });
}

export function useBlockTransactions(height: number | undefined) {
  return useQuery<Transaction[]>({
    queryKey: ["explorer", "blockTxs", height],
    queryFn: () =>
      height !== undefined ? engine().getTransactionsForBlock(height) : [],
    enabled: height !== undefined,
    staleTime: 60_000,
  });
}

/* ── Transactions ─────────────────────────────────────────────────────── */

export function useRecentTransactions(count: number = 30) {
  return useQuery<Transaction[]>({
    queryKey: ["explorer", "recentTxs", count],
    queryFn: () => engine().transactions.slice(-count).reverse(),
    staleTime: STALE_TIME,
  });
}

export function useTransaction(txid: string | undefined) {
  return useQuery<Transaction | undefined>({
    queryKey: ["explorer", "tx", txid],
    queryFn: () => (txid ? engine().getTransaction(txid) : undefined),
    enabled: !!txid,
    staleTime: 60_000,
  });
}

/* ── Contracts ────────────────────────────────────────────────────────── */

export function useContracts() {
  return useQuery<QVMContract[]>({
    queryKey: ["explorer", "contracts"],
    queryFn: () => engine().contracts,
    staleTime: 30_000,
  });
}

export function useContract(address: string | undefined) {
  return useQuery<QVMContract | undefined>({
    queryKey: ["explorer", "contract", address],
    queryFn: () => (address ? engine().getContract(address) : undefined),
    enabled: !!address,
    staleTime: 60_000,
  });
}

/* ── Aether Tree ──────────────────────────────────────────────────────── */

export function useAetherNodes() {
  return useQuery<AetherNode[]>({
    queryKey: ["explorer", "aetherNodes"],
    queryFn: () => engine().aetherNodes,
    staleTime: 30_000,
  });
}

export function useAetherEdges() {
  return useQuery<AetherEdge[]>({
    queryKey: ["explorer", "aetherEdges"],
    queryFn: () => engine().aetherEdges,
    staleTime: 30_000,
  });
}

/* ── Miners / Leaderboard ─────────────────────────────────────────────── */

export function useMiners() {
  return useQuery<MinerStats[]>({
    queryKey: ["explorer", "miners"],
    queryFn: () => engine().miners,
    staleTime: STALE_TIME,
  });
}

/* ── Wallet / Address ─────────────────────────────────────────────────── */

export function useWallet(address: string | undefined) {
  return useQuery<WalletData | undefined>({
    queryKey: ["explorer", "wallet", address],
    queryFn: () => (address ? engine().getWallet(address) : undefined),
    enabled: !!address,
    staleTime: 30_000,
  });
}

/* ── Time Series ──────────────────────────────────────────────────────── */

export function usePhiHistory() {
  return useQuery<PhiDataPoint[]>({
    queryKey: ["explorer", "phiHistory"],
    queryFn: () => engine().phiHistory,
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
    queryFn: () => engine().search(query),
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
