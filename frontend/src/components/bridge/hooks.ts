/* ---------------------------------------------------------------------------
   QBC Bridge — React Query Hooks (data fetching backed by mock engine)
   --------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { getBridgeMockEngine } from "./mock-engine";
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
 */
export function useVaultState() {
  return useQuery<VaultState>({
    queryKey: bridgeKeys.vault(),
    queryFn: () => getBridgeMockEngine().vaultState,
    staleTime: 10_000,
    refetchInterval: 15_000,
  });
}

/**
 * Fetch all bridge transactions (wrap and unwrap, all chains).
 * Sorted by most recent first.
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
    queryFn: () =>
      getBridgeMockEngine().estimateFee(operation!, token!, chain!, numAmount),
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
 */
export function useTickerItems() {
  return useQuery<TickerItem[]>({
    queryKey: bridgeKeys.ticker(),
    queryFn: () => getBridgeMockEngine().getTickerItems(),
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

// ---------------------------------------------------------------------------
// Re-export query keys for external invalidation and filter type
// ---------------------------------------------------------------------------

export { bridgeKeys };
export type { HistoryFilters };
