/* ---------------------------------------------------------------------------
   QBC Bridge — React Query Hooks (wired to bridge-api with mock fallback)
   --------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { bridgeApi } from "@/lib/bridge-api";

// Lazy-load mock engine only when mock mode is active (no production bundle cost)
let _bridgeMock: ReturnType<typeof import("./mock-engine")["getBridgeMockEngine"]> | null = null;
function getBridgeMockEngine() {
  if (!_bridgeMock) {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    _bridgeMock = require("./mock-engine").getBridgeMockEngine();
  }
  return _bridgeMock!;
}
import type {
  BridgeStatus,
  BridgeTx,
  ExternalChainId,
  FeeEstimate,
  GasPrice,
  OperationType,
  TickerItem,
  TokenType,
  VaultState,
} from "./types";

// ---------------------------------------------------------------------------
// Environment switch
// ---------------------------------------------------------------------------

const USE_MOCK = process.env.NEXT_PUBLIC_BRIDGE_MOCK === "true";

// ---------------------------------------------------------------------------
// Query Key Factory (collision-safe, easy invalidation)
// ---------------------------------------------------------------------------

const bridgeKeys = {
  all: ["bridge"] as const,
  vault: () => [...bridgeKeys.all, "vault"] as const,
  transactions: () => [...bridgeKeys.all, "transactions"] as const,
  transaction: (id: string) => [...bridgeKeys.all, "transaction", id] as const,
  feeEstimate: (
    operation: OperationType,
    token: TokenType,
    chain: ExternalChainId,
    amount: number,
  ) => [...bridgeKeys.all, "fee", operation, token, chain, amount] as const,
  gasPrices: () => [...bridgeKeys.all, "gasPrices"] as const,
  ticker: () => [...bridgeKeys.all, "ticker"] as const,
  history: (filters: HistoryFilters) => [...bridgeKeys.all, "history", filters] as const,
  stats: () => [...bridgeKeys.all, "stats"] as const,
  chains: () => [...bridgeKeys.all, "chains"] as const,
  balance: (chain: string, address: string) => [...bridgeKeys.all, "balance", chain, address] as const,
  qbcBalance: (address: string) => [...bridgeKeys.all, "qbcBalance", address] as const,
  validators: () => [...bridgeKeys.all, "validators"] as const,
};

// ---------------------------------------------------------------------------
// Filter types
// ---------------------------------------------------------------------------

interface HistoryFilters {
  operation?: OperationType;
  chain?: ExternalChainId;
  token?: TokenType;
  status?: BridgeStatus;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Fetch the current vault state: locked balances, minted wrapped tokens,
 * backing ratios, daily limits, and historical charts.
 *
 * In mock mode: uses BridgeMockEngine.
 * In live mode: fetches from /bridge/stats and assembles vault state.
 */
export function useVaultState() {
  return useQuery<VaultState>({
    queryKey: bridgeKeys.vault(),
    queryFn: async (): Promise<VaultState> => {
      if (USE_MOCK) {
        return getBridgeMockEngine().vaultState;
      }
      const result = await bridgeApi.getVaultState();
      return {
        qbcLocked: result.qbcLocked,
        qusdLocked: result.qusdLocked,
        wqbcByChain: result.wqbcByChain as VaultState["wqbcByChain"],
        wqusdByChain: result.wqusdByChain as VaultState["wqusdByChain"],
        totalWqbc: result.totalWqbc,
        totalWqusd: result.totalWqusd,
        backingRatioQbc: result.backingRatioQbc as VaultState["backingRatioQbc"],
        backingRatioQusd: result.backingRatioQusd as VaultState["backingRatioQusd"],
        vaultAddrQbc: result.vaultAddrQbc,
        vaultAddrQusd: result.vaultAddrQusd,
        dailyWrapVol: result.dailyWrapVol,
        dailyUnwrapVol: result.dailyUnwrapVol,
        dailyLimit: result.dailyLimit,
        dailyUsed: result.dailyUsed,
        dailyResetIn: result.dailyResetIn,
        backingHistory: result.backingHistory,
        wrapUnwrapHistory: result.wrapUnwrapHistory,
      };
    },
    staleTime: 10_000,
    refetchInterval: 15_000,
  });
}

/**
 * Fetch all bridge transactions (wrap and unwrap, all chains).
 * Sorted by most recent first.
 *
 * Note: The backend does not yet have a dedicated transfer history endpoint.
 * In live mode, we still fall back to mock data for the full transaction list.
 * Individual transaction lookups use the mock engine in both modes for now.
 */
export function useBridgeTransactions() {
  return useQuery<BridgeTx[]>({
    queryKey: bridgeKeys.transactions(),
    queryFn: () => getBridgeMockEngine().transactions,
    staleTime: 10_000,
  });
}

/**
 * Fetch a single bridge transaction by ID.
 * Polls every 5 seconds so the UI can show real-time confirmation progress
 * on active (pending) transactions.
 */
export function useBridgeTransaction(id: string | undefined) {
  return useQuery<BridgeTx>({
    queryKey: bridgeKeys.transaction(id ?? ""),
    queryFn: () => {
      const tx = getBridgeMockEngine().getTransaction(id!);
      if (!tx) {
        throw new Error(`Bridge transaction not found: ${id}`);
      }
      return tx;
    },
    enabled: id !== undefined && id !== "",
    staleTime: 5_000,
    refetchInterval: 5_000,
  });
}

/**
 * Estimate fees for a bridge operation before the user confirms.
 * Only runs when all parameters are valid and amount > 0.
 *
 * In live mode: calls /bridge/fees/{chain}/{amount}.
 * In mock mode: uses BridgeMockEngine.estimateFee().
 */
export function useFeeEstimate(
  operation: OperationType | undefined,
  token: TokenType | undefined,
  chain: ExternalChainId | null | undefined,
  amount: string,
) {
  const numAmount = parseFloat(amount);
  const isValid =
    operation !== undefined &&
    token !== undefined &&
    chain !== null &&
    chain !== undefined &&
    !isNaN(numAmount) &&
    numAmount > 0;

  return useQuery<FeeEstimate>({
    queryKey: bridgeKeys.feeEstimate(
      operation ?? "wrap",
      token ?? "QBC",
      chain ?? "ethereum",
      isValid ? numAmount : 0,
    ),
    queryFn: async (): Promise<FeeEstimate> => {
      if (USE_MOCK) {
        return getBridgeMockEngine().estimateFee(operation!, token!, chain!, numAmount);
      }

      // Call real API, then transform to frontend FeeEstimate shape
      const result = await bridgeApi.getBridgeFees(chain!, String(numAmount));
      const bridgeFee = parseFloat(result.bridge_fee) || 0;
      const gasQbc = parseFloat(result.estimated_gas) || 0;
      const totalFee = parseFloat(result.total_cost) || 0;
      const receiveAmount = parseFloat(result.receive_amount) || 0;

      // Estimate time based on chain
      const estTimes: Record<string, { min: number; max: number }> = {
        ethereum: { min: 180, max: 600 },
        bnb: { min: 60, max: 180 },
        solana: { min: 15, max: 60 },
        polygon: { min: 120, max: 420 },
        avalanche: { min: 30, max: 120 },
        arbitrum: { min: 30, max: 120 },
        optimism: { min: 30, max: 120 },
        base: { min: 30, max: 120 },
      };
      const estTime = estTimes[chain!] ?? { min: 60, max: 300 };

      return {
        operation: operation!,
        token: token!,
        chain: chain!,
        amount: numAmount,
        protocolFeePercent: 0.1,
        relayerFeePercent: 0.05,
        protocolFee: bridgeFee * 0.667, // ~2/3 protocol
        relayerFee: bridgeFee * 0.333,  // ~1/3 relayer
        destGasNative: 0,
        destGasUsd: 0,
        destGasQbcEquiv: gasQbc,
        totalFeeToken: totalFee,
        totalFeePercent: numAmount > 0 ? (totalFee / numAmount) * 100 : 0,
        amountReceived: receiveAmount,
        estTimeSeconds: estTime,
        updatedAt: Date.now() / 1000,
      };
    },
    enabled: isValid,
    staleTime: 10_000,
  });
}

/**
 * Fetch current gas prices across all supported chains.
 * Refreshes every 30 seconds.
 */
export function useGasPrices() {
  return useQuery<GasPrice[]>({
    queryKey: bridgeKeys.gasPrices(),
    queryFn: () => getBridgeMockEngine().gasPrices,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });
}

/**
 * Fetch ticker items for the scrolling status bar
 * (vault TVL, 24h volume, active bridges, gas prices, etc.).
 *
 * In live mode: fetches bridge stats and assembles ticker items.
 * In mock mode: uses BridgeMockEngine.getTickerItems().
 */
export function useTickerItems() {
  return useQuery<TickerItem[]>({
    queryKey: bridgeKeys.ticker(),
    queryFn: async (): Promise<TickerItem[]> => {
      if (USE_MOCK) {
        return getBridgeMockEngine().getTickerItems();
      }

      try {
        const stats = await bridgeApi.getBridgeStats();
        const items: TickerItem[] = [
          { label: "Total Volume", value: `${Math.floor(parseFloat(stats.totals.total_volume)).toLocaleString()} QBC`, color: "#00ff88" },
          { label: "Total Deposits", value: stats.totals.total_deposits.toLocaleString(), color: "#00d4ff" },
          { label: "Total Withdrawals", value: stats.totals.total_withdrawals.toLocaleString(), color: "#f5c842" },
          { label: "Active Chains", value: stats.totals.active_chains.toString(), color: "#10b981" },
          { label: "Backing Ratio", value: "1:1", color: "#22c55e" },
          { label: "Protocol Fee", value: "0.10%" },
          { label: "Relayer Fee", value: "0.05%" },
          { label: "Bridge Version", value: "v2.1.0", color: "#94a3b8" },
        ];

        // Add per-chain volume
        for (const chain of stats.chains) {
          items.push({
            label: `${chain.chain.toUpperCase()} Vol`,
            value: `${Math.floor(parseFloat(chain.total_volume)).toLocaleString()} QBC`,
          });
        }

        return items;
      } catch {
        // Fallback to mock on error
        return getBridgeMockEngine().getTickerItems();
      }
    },
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
}

/**
 * Fetch bridge transaction history with optional filters.
 * Delegates to the mock engine's built-in filter method which
 * supports operation, token, chain, and status filters.
 */
export function useFilteredHistory(filters: HistoryFilters) {
  return useQuery<BridgeTx[]>({
    queryKey: bridgeKeys.history(filters),
    queryFn: () => {
      const engine = getBridgeMockEngine();
      return engine.getHistoryFiltered({
        operation: filters.operation,
        token: filters.token,
        chain: filters.chain,
        status: filters.status,
      });
    },
    staleTime: 10_000,
  });
}

/**
 * Fetch bridge stats from the real API (or mock).
 */
export function useBridgeStats() {
  return useQuery({
    queryKey: bridgeKeys.stats(),
    queryFn: () => bridgeApi.getBridgeStats(),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

/**
 * Fetch supported bridge chains.
 */
export function useSupportedChains() {
  return useQuery({
    queryKey: bridgeKeys.chains(),
    queryFn: () => bridgeApi.getSupportedChains(),
    staleTime: 60_000,
  });
}

/**
 * Fetch wQBC/wQUSD balance on a specific chain.
 */
export function useBridgeBalance(chain: string | null, address: string | null) {
  return useQuery({
    queryKey: bridgeKeys.balance(chain ?? "", address ?? ""),
    queryFn: () => bridgeApi.getBridgeBalance(chain!, address!),
    enabled: chain !== null && address !== null && address !== "",
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

/**
 * Fetch QBC native balance from the L1 node.
 */
export function useQbcBalance(address: string | null) {
  return useQuery({
    queryKey: bridgeKeys.qbcBalance(address ?? ""),
    queryFn: () => bridgeApi.getQbcBalance(address!),
    enabled: address !== null && address !== "",
    staleTime: 10_000,
    refetchInterval: 15_000,
  });
}

/**
 * Fetch bridge validator statistics.
 */
export function useValidatorStats() {
  return useQuery({
    queryKey: bridgeKeys.validators(),
    queryFn: () => bridgeApi.getValidatorStats(),
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Re-export query keys for external invalidation and filter type
// ---------------------------------------------------------------------------

export { bridgeKeys };
export type { HistoryFilters };
