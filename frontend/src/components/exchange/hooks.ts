// ─── QBC EXCHANGE — React Query Hooks + WebSocket Simulation ─────────────────
// Hooks now consume exchange-api.ts service layer.
// Mock engine is retained for local tick simulation and data types
// that the API does not yet serve (OHLC, positions, funding, liquidation,
// equity, quantum intelligence).
// Mock engine is lazily imported and only active when USE_MOCK is true.
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useCallback, useMemo } from "react";
import { useExchangeStore } from "./store";

const USE_MOCK = process.env.NEXT_PUBLIC_EXCHANGE_MOCK === "true";

// Lazy-load mock engine only when mock mode is active
let _mockEngine: typeof import("./mock-engine")["mockEngine"] | null = null;
function getMockEngine() {
  if (!_mockEngine) {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    _mockEngine = require("./mock-engine").mockEngine;
  }
  return _mockEngine!;
}
import {
  getMarkets as apiGetMarkets,
  getOrderBook as apiGetOrderBook,
  getRecentTrades as apiGetRecentTrades,
  getUserOrders as apiGetUserOrders,
  getUserBalance as apiGetUserBalance,
  placeOrder as apiPlaceOrder,
  cancelOrder as apiCancelOrder,
  deposit as apiDeposit,
  withdraw as apiWithdraw,
} from "@/lib/exchange-api";
import type {
  Market as ApiMarket,
  OrderBookData,
  TradeEntry,
  OrderEntry as ApiOrderEntry,
  NewOrder,
  BalanceEntry,
} from "@/lib/exchange-api";
import type {
  MarketId,
  Timeframe,
  Market,
  OrderBook,
  OrderBookLevel,
  Trade,
  OHLCBar,
  Position,
  Order,
  Balance,
  FundingPayment,
  LiquidationLevel,
  EquitySnapshot,
  SusySignal,
  VqeOracle,
  ValidatorStatus,
  QeviData,
} from "./types";
import { MARKET_CONFIGS, getBasePrice, ASSET_VOLATILITY } from "./config";

// ─── QUERY KEY FACTORY ──────────────────────────────────────────────────────

const qk = {
  markets: ["exchange", "markets"] as const,
  market: (id: MarketId) => ["exchange", "market", id] as const,
  ohlc: (id: MarketId, tf: Timeframe) => ["exchange", "ohlc", id, tf] as const,
  orderbook: (id: MarketId) => ["exchange", "orderbook", id] as const,
  trades: (id: MarketId) => ["exchange", "trades", id] as const,
  positions: ["exchange", "positions"] as const,
  openOrders: ["exchange", "openOrders"] as const,
  myFills: ["exchange", "myFills"] as const,
  balances: ["exchange", "balances"] as const,
  funding: (id: MarketId) => ["exchange", "funding", id] as const,
  liquidations: (id: MarketId) => ["exchange", "liquidations", id] as const,
  equity: ["exchange", "equity"] as const,
  susy: ["exchange", "susy"] as const,
  vqe: ["exchange", "vqe"] as const,
  validators: ["exchange", "validators"] as const,
  qevi: ["exchange", "qevi"] as const,
};

// ─── ADAPTERS: convert exchange-api types → frontend types ──────────────────

function adaptApiMarket(api: ApiMarket): Market {
  const cfg = MARKET_CONFIGS.find((m) => m.id === api.pair && m.enabled);
  const baseAsset = cfg?.baseAsset ?? api.pair.split("_")[0];
  const type = cfg?.type ?? "spot";
  const basePrice = api.lastPrice;
  const vol = ASSET_VOLATILITY[baseAsset] ?? 0.05;

  return {
    id: api.pair as MarketId,
    baseAsset,
    quoteAsset: "QUSD",
    type,
    displayName: type === "perp" ? baseAsset + "-PERP" : baseAsset + "/QUSD",
    lastPrice: api.lastPrice,
    indexPrice: api.lastPrice, // API does not serve index price separately
    markPrice: api.lastPrice,
    fundingRate: 0,
    nextFundingTs: 0,
    openInterest: 0,
    price24hOpen: api.lastPrice / (1 + api.change24h / 100),
    price24hHigh: api.high24h,
    price24hLow: api.low24h,
    volume24h: api.volume24h,
    volume24hUsd: api.volume24h * api.lastPrice,
    priceChange24h: api.lastPrice - api.lastPrice / (1 + api.change24h / 100),
    priceChangePct24h: api.change24h,
    maxLeverage: cfg?.maxLeverage ?? 1,
    minOrderSize: cfg?.minOrderSize ?? 1,
    tickSize: cfg?.tickSize ?? 0.0001,
    stepSize: cfg?.stepSize ?? 0.01,
    decimals: (cfg?.tickSize ?? 0.0001) < 0.001 ? 4 : 2,
    sizeDecimals: (cfg?.stepSize ?? 0.01) < 0.01 ? 4 : 2,
    baseIcon: baseAsset.charAt(0),
    marketCap: basePrice * 1e9 * (0.5 + vol),
  };
}

function adaptApiOrderBook(api: OrderBookData): OrderBook {
  const bids: OrderBookLevel[] = api.bids.map((b) => ({
    price: b.price,
    size: b.size,
    total: b.total,
    orderCount: b.orderCount,
    myOrderSize: 0,
  }));
  const asks: OrderBookLevel[] = api.asks.map((a) => ({
    price: a.price,
    size: a.size,
    total: a.total,
    orderCount: a.orderCount,
    myOrderSize: 0,
  }));
  return {
    marketId: api.pair as MarketId,
    bids,
    asks,
    spread: api.spread,
    spreadPct: api.spreadPct,
    midPrice: api.midPrice,
    updatedAt: api.updatedAt,
  };
}

function adaptApiTrade(api: TradeEntry): Trade {
  return {
    id: api.id,
    marketId: api.pair as MarketId,
    price: api.price,
    size: api.size,
    side: api.side,
    timestamp: api.timestamp * 1000, // convert to ms
    txHash: api.maker_order_id, // best proxy
    isLarge: api.size > 10000,
  };
}

function adaptApiOrder(api: ApiOrderEntry): Order {
  return {
    id: api.id,
    marketId: api.pair as MarketId,
    side: api.side,
    type: api.type,
    status: api.status === "partial" ? "partial" : api.status,
    price: api.price,
    triggerPrice: null,
    size: api.size,
    filledSize: api.filled,
    remainingSize: api.remaining,
    avgFillPrice: api.filled > 0 ? api.price : null,
    fee: 0,
    tif: "gtc",
    reduceOnly: false,
    postOnly: false,
    createdAt: api.timestamp * 1000,
    updatedAt: api.timestamp * 1000,
    txHash: "",
    dilithiumSig: "",
  };
}

function adaptApiBalance(api: BalanceEntry): Balance {
  return {
    asset: api.asset,
    total: api.total,
    available: api.available,
    inOrders: api.inOrders,
    usedAsMargin: 0,
    usdValue: api.total, // approximate
    decimals: 8,
  };
}

// ─── MARKET HOOKS ───────────────────────────────────────────────────────────

export function useMarkets() {
  return useQuery({
    queryKey: qk.markets,
    queryFn: async (): Promise<Market[]> => {
      try {
        const apiMarkets = await apiGetMarkets();
        return apiMarkets.map(adaptApiMarket);
      } catch {
        // Fallback to mock engine if API call fails
        return getMockEngine().getAllMarkets();
      }
    },
    staleTime: 2000,
    refetchInterval: 2000,
  });
}

export function useMarket(id: MarketId) {
  const { data: markets } = useMarkets();
  const market = useMemo(
    () => markets?.find((m) => m.id === id),
    [markets, id],
  );
  return useQuery({
    queryKey: qk.market(id),
    queryFn: (): Market | undefined => market ?? getMockEngine().getMarket(id),
    staleTime: 1000,
    refetchInterval: 1000,
    initialData: market,
  });
}

// ─── OHLC HOOK ──────────────────────────────────────────────────────────────
// OHLC data is not yet served by the backend — keep using mock engine.

export function useOHLC(id: MarketId, tf: Timeframe) {
  return useQuery({
    queryKey: qk.ohlc(id, tf),
    queryFn: (): OHLCBar[] => getMockEngine().generateOHLC(id, tf),
    staleTime: 10000,
  });
}

// ─── ORDER BOOK HOOK ────────────────────────────────────────────────────────

export function useOrderBook(id: MarketId) {
  return useQuery({
    queryKey: qk.orderbook(id),
    queryFn: async (): Promise<OrderBook | undefined> => {
      try {
        const apiBook = await apiGetOrderBook(id);
        return adaptApiOrderBook(apiBook);
      } catch {
        return getMockEngine().getOrderBook(id);
      }
    },
    staleTime: 2000,
    refetchInterval: 2000,
    // Keep previous data visible during refetch to prevent flicker
    placeholderData: (prev) => prev,
  });
}

// ─── TRADES HOOK ────────────────────────────────────────────────────────────

export function useTrades(id: MarketId) {
  return useQuery({
    queryKey: qk.trades(id),
    queryFn: async (): Promise<Trade[]> => {
      try {
        const apiTrades = await apiGetRecentTrades(id, 50);
        return apiTrades.map(adaptApiTrade);
      } catch {
        return getMockEngine().getTrades(id);
      }
    },
    staleTime: 1000,
    refetchInterval: 1000,
  });
}

// ─── POSITION HOOKS ─────────────────────────────────────────────────────────
// Positions are mock-only (backend does not serve them yet for perps).

export function usePositions() {
  return useQuery({
    queryKey: qk.positions,
    queryFn: (): Position[] => getMockEngine().generatePositions(),
    staleTime: 2000,
    refetchInterval: 2000,
  });
}

export function useOpenOrders() {
  const walletAddress = useExchangeStore((s) => s.walletAddress);

  return useQuery({
    queryKey: qk.openOrders,
    queryFn: async (): Promise<Order[]> => {
      if (!walletAddress) return getMockEngine().generateOpenOrders();
      try {
        const apiOrders = await apiGetUserOrders(walletAddress);
        return apiOrders.map(adaptApiOrder);
      } catch {
        return getMockEngine().generateOpenOrders();
      }
    },
    staleTime: 2000,
    refetchInterval: 5000,
  });
}

export function useMyFills() {
  return useQuery({
    queryKey: qk.myFills,
    queryFn: (): Order[] => getMockEngine().generateMyFills(),
    staleTime: 10000,
  });
}

// ─── BALANCE HOOKS ──────────────────────────────────────────────────────────

export function useBalances() {
  const walletAddress = useExchangeStore((s) => s.walletAddress);

  return useQuery({
    queryKey: qk.balances,
    queryFn: async (): Promise<Balance[]> => {
      if (!walletAddress) return getMockEngine().generateBalances();
      try {
        const apiBalance = await apiGetUserBalance(walletAddress);
        return apiBalance.balances.map(adaptApiBalance);
      } catch {
        return getMockEngine().generateBalances();
      }
    },
    staleTime: 5000,
    refetchInterval: 5000,
  });
}

// ─── ORDER PLACEMENT MUTATION ───────────────────────────────────────────────

export function usePlaceOrder() {
  const queryClient = useQueryClient();
  const walletAddress = useExchangeStore((s) => s.walletAddress);
  const addToast = useExchangeStore((s) => s.addToast);

  return useMutation({
    mutationFn: async (params: {
      pair: string;
      side: "buy" | "sell";
      type: "limit" | "market";
      price: number;
      size: number;
    }) => {
      const order: NewOrder = {
        pair: params.pair,
        side: params.side,
        type: params.type,
        price: params.price,
        size: params.size,
        address: walletAddress || "qbc1demo",
      };
      return apiPlaceOrder(order);
    },
    onSuccess: (_data, vars) => {
      addToast(
        `Order submitted: ${vars.side.toUpperCase()} ${vars.size} @ ${vars.type === "market" ? "MARKET" : vars.price}`,
        "success",
      );
      // Invalidate relevant queries
      void queryClient.invalidateQueries({ queryKey: qk.openOrders });
      void queryClient.invalidateQueries({ queryKey: qk.balances });
      void queryClient.invalidateQueries({ queryKey: ["exchange", "orderbook"] });
    },
    onError: (err: Error) => {
      addToast(`Order failed: ${err.message}`, "error");
    },
  });
}

// ─── ORDER CANCELLATION MUTATION ────────────────────────────────────────────

export function useCancelOrder() {
  const queryClient = useQueryClient();
  const addToast = useExchangeStore((s) => s.addToast);

  return useMutation({
    mutationFn: async (params: { orderId: string; pair?: string }) => {
      await apiCancelOrder(params.orderId, params.pair);
    },
    onSuccess: () => {
      addToast("Order cancelled", "success");
      void queryClient.invalidateQueries({ queryKey: qk.openOrders });
      void queryClient.invalidateQueries({ queryKey: qk.balances });
      void queryClient.invalidateQueries({ queryKey: ["exchange", "orderbook"] });
    },
    onError: (err: Error) => {
      addToast(`Cancel failed: ${err.message}`, "error");
    },
  });
}

// ─── DEPOSIT MUTATION ───────────────────────────────────────────────────────

export function useDeposit() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: {
      address: string;
      asset: string;
      amount: number;
    }) => {
      return apiDeposit(params.address, params.asset, params.amount);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.balances });
    },
  });
}

// ─── WITHDRAW MUTATION ──────────────────────────────────────────────────────

export function useWithdraw() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: {
      address: string;
      asset: string;
      amount: number;
    }) => {
      return apiWithdraw(params.address, params.asset, params.amount);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.balances });
    },
  });
}

// ─── FUNDING HOOK ───────────────────────────────────────────────────────────

export function useFunding(id: MarketId) {
  return useQuery({
    queryKey: qk.funding(id),
    queryFn: (): FundingPayment[] => getMockEngine().generateFundingPayments(id),
    staleTime: 30000,
  });
}

// ─── LIQUIDATION HOOK ───────────────────────────────────────────────────────

export function useLiquidationLevels(id: MarketId) {
  return useQuery({
    queryKey: qk.liquidations(id),
    queryFn: (): LiquidationLevel[] => getMockEngine().generateLiquidationLevels(id),
    staleTime: 30000,
  });
}

// ─── EQUITY HOOK ────────────────────────────────────────────────────────────

export function useEquityHistory() {
  return useQuery({
    queryKey: qk.equity,
    queryFn: (): EquitySnapshot[] => getMockEngine().generateEquityHistory(),
    staleTime: 60000,
  });
}

// ─── QUANTUM INTELLIGENCE HOOKS ─────────────────────────────────────────────

export function useSusySignal() {
  return useQuery({
    queryKey: qk.susy,
    queryFn: (): SusySignal => getMockEngine().generateSusySignal(),
    staleTime: 30000,
  });
}

export function useVqeOracle() {
  return useQuery({
    queryKey: qk.vqe,
    queryFn: (): VqeOracle => getMockEngine().generateVqeOracle(),
    staleTime: 15000,
  });
}

export function useValidators() {
  return useQuery({
    queryKey: qk.validators,
    queryFn: (): ValidatorStatus[] => getMockEngine().generateValidators(),
    staleTime: 15000,
  });
}

export function useQevi() {
  return useQuery({
    queryKey: qk.qevi,
    queryFn: (): QeviData => getMockEngine().generateQevi(),
    staleTime: 30000,
  });
}

// ─── AETHER DATA HOOKS (real backend) ───────────────────────────────────────

interface AetherPhiResponse {
  phi: number;
  threshold: number;
  above_threshold: boolean;
  knowledge_nodes: number;
  knowledge_edges: number;
}

interface AetherReasoningResponse {
  total_operations: number;
  deductive: number;
  inductive: number;
  abductive: number;
  blocks_processed: number;
}

interface MiningStatsResponse {
  blocks_mined: number;
  total_energy: number;
  avg_energy: number;
  difficulty: number;
  hashrate: number;
}

const RPC_BASE = process.env.NEXT_PUBLIC_RPC_URL ?? "http://localhost:5000";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${RPC_BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export function useAetherPhi() {
  return useQuery({
    queryKey: ["aether", "phi"] as const,
    queryFn: () => fetchJson<AetherPhiResponse>("/aether/phi"),
    staleTime: 10000,
    refetchInterval: 15000,
    retry: 1,
  });
}

export function useAetherReasoning() {
  return useQuery({
    queryKey: ["aether", "reasoning"] as const,
    queryFn: () => fetchJson<AetherReasoningResponse>("/aether/reasoning/stats"),
    staleTime: 15000,
    refetchInterval: 30000,
    retry: 1,
  });
}

export function useMiningStats() {
  return useQuery({
    queryKey: ["mining", "stats"] as const,
    queryFn: () => fetchJson<MiningStatsResponse>("/mining/stats"),
    staleTime: 10000,
    refetchInterval: 15000,
    retry: 1,
  });
}

// ─── TICK SIMULATION (WebSocket substitute) ─────────────────────────────────

export function useTickSimulation() {
  const intervalRef = useRef<ReturnType<typeof setInterval>>(undefined);

  useEffect(() => {
    if (!USE_MOCK) return; // Only run tick simulation in mock mode
    intervalRef.current = setInterval(() => {
      getMockEngine().tick();
    }, 1000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);
}

// ─── TRADE SIMULATION ───────────────────────────────────────────────────────

export function useTradeSimulation(id: MarketId) {
  useEffect(() => {
    if (!USE_MOCK) return; // Only run trade simulation in mock mode
    const interval = setInterval(() => {
      getMockEngine().addTrade(id);
    }, 1500 + Math.random() * 3000);
    return () => clearInterval(interval);
  }, [id]);
}

// ─── FUNDING COUNTDOWN ─────────────────────────────────────────────────────

export function useFundingCountdown(nextTs: number | undefined) {
  const ref = useRef<string>("--:--:--");
  useEffect(() => {
    if (!nextTs) return;
    const update = () => {
      const diff = Math.max(0, Math.floor((nextTs - Date.now()) / 1000));
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      const s = diff % 60;
      ref.current = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    };
    update();
    const i = setInterval(update, 1000);
    return () => clearInterval(i);
  }, [nextTs]);
  return ref;
}
