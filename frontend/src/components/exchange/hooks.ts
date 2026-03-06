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
  const vol = ASSET_VOLATILITY[baseAsset] ?? 0.05;

  // Backend returns Decimal values as strings — parse to number.
  // Fall back to reference price when no trades have occurred yet (price == 0).
  const rawPrice = typeof api.lastPrice === "string" ? parseFloat(api.lastPrice) : api.lastPrice;
  const rawChange = typeof api.change24h === "string" ? parseFloat(api.change24h) : api.change24h;
  const rawVol = typeof api.volume24h === "string" ? parseFloat(api.volume24h) : api.volume24h;
  const rawHigh = typeof api.high24h === "string" ? parseFloat(api.high24h) : api.high24h;
  const rawLow = typeof api.low24h === "string" ? parseFloat(api.low24h) : api.low24h;

  const refPrice = getBasePrice(baseAsset);
  const lastPrice = rawPrice > 0 ? rawPrice : refPrice;
  const change24h = rawPrice > 0 ? rawChange : 0;
  const volume24h = rawVol || 0;
  const high24h = rawHigh > 0 ? rawHigh : lastPrice;
  const low24h = rawLow > 0 ? rawLow : lastPrice;

  const open = change24h !== 0 ? lastPrice / (1 + change24h / 100) : lastPrice;

  return {
    id: api.pair as MarketId,
    baseAsset,
    quoteAsset: "QUSD",
    type,
    displayName: type === "perp" ? baseAsset + "-PERP" : baseAsset + "/QUSD",
    lastPrice,
    indexPrice: lastPrice,
    markPrice: lastPrice,
    fundingRate: 0,
    nextFundingTs: 0,
    openInterest: 0,
    price24hOpen: open,
    price24hHigh: high24h,
    price24hLow: low24h,
    volume24h,
    volume24hUsd: volume24h * lastPrice,
    priceChange24h: lastPrice - open,
    priceChangePct24h: change24h,
    maxLeverage: cfg?.maxLeverage ?? 1,
    minOrderSize: cfg?.minOrderSize ?? 1,
    tickSize: cfg?.tickSize ?? 0.0001,
    stepSize: cfg?.stepSize ?? 0.01,
    decimals: (cfg?.tickSize ?? 0.0001) < 0.001 ? 4 : 2,
    sizeDecimals: (cfg?.stepSize ?? 0.01) < 0.01 ? 4 : 2,
    baseIcon: baseAsset.charAt(0),
    marketCap: lastPrice * 1e9 * (0.5 + vol),
  };
}

function num(v: unknown): number {
  return typeof v === "string" ? parseFloat(v) || 0 : Number(v) || 0;
}

function adaptApiOrderBook(api: OrderBookData): OrderBook {
  const bids: OrderBookLevel[] = api.bids.map((b) => ({
    price: num(b.price),
    size: num(b.size),
    total: num(b.total),
    orderCount: num(b.orderCount),
    myOrderSize: 0,
  }));
  const asks: OrderBookLevel[] = api.asks.map((a) => ({
    price: num(a.price),
    size: num(a.size),
    total: num(a.total),
    orderCount: num(a.orderCount),
    myOrderSize: 0,
  }));
  return {
    marketId: api.pair as MarketId,
    bids,
    asks,
    spread: num(api.spread),
    spreadPct: num(api.spreadPct),
    midPrice: num(api.midPrice),
    updatedAt: num(api.updatedAt),
  };
}

function adaptApiTrade(api: TradeEntry): Trade {
  const price = num(api.price);
  const size = num(api.size);
  return {
    id: api.id,
    marketId: api.pair as MarketId,
    price,
    size,
    side: api.side,
    timestamp: num(api.timestamp) * 1000,
    txHash: api.maker_order_id,
    isLarge: size > 10000,
  };
}

function adaptApiOrder(api: ApiOrderEntry): Order {
  const price = num(api.price);
  const filled = num(api.filled);
  return {
    id: api.id,
    marketId: api.pair as MarketId,
    side: api.side,
    type: api.type,
    status: api.status === "partial" ? "partial" : api.status,
    price,
    triggerPrice: null,
    size: num(api.size),
    filledSize: filled,
    remainingSize: num(api.remaining),
    avgFillPrice: filled > 0 ? price : null,
    fee: 0,
    tif: "gtc",
    reduceOnly: false,
    postOnly: false,
    createdAt: num(api.timestamp) * 1000,
    updatedAt: num(api.timestamp) * 1000,
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
      if (USE_MOCK) return getMockEngine().getAllMarkets();
      const apiMarkets = await apiGetMarkets();
      const liveMarkets = apiMarkets.map(adaptApiMarket);
      const liveIds = new Set(liveMarkets.map((m) => m.id));

      // Add configured markets that the backend doesn't serve yet (e.g. perps)
      for (const cfg of MARKET_CONFIGS) {
        if (!cfg.enabled || liveIds.has(cfg.id as MarketId)) continue;
        const refPrice = getBasePrice(cfg.baseAsset);
        liveMarkets.push({
          id: cfg.id as MarketId,
          baseAsset: cfg.baseAsset,
          quoteAsset: "QUSD",
          type: cfg.type,
          displayName: cfg.type === "perp" ? cfg.baseAsset + "-PERP" : cfg.baseAsset + "/QUSD",
          lastPrice: refPrice,
          indexPrice: refPrice,
          markPrice: refPrice,
          fundingRate: 0,
          nextFundingTs: 0,
          openInterest: 0,
          price24hOpen: refPrice,
          price24hHigh: refPrice,
          price24hLow: refPrice,
          volume24h: 0,
          volume24hUsd: 0,
          priceChange24h: 0,
          priceChangePct24h: 0,
          maxLeverage: cfg.maxLeverage,
          minOrderSize: cfg.minOrderSize,
          tickSize: cfg.tickSize,
          stepSize: cfg.stepSize,
          decimals: cfg.tickSize < 0.001 ? 4 : 2,
          sizeDecimals: cfg.stepSize < 0.01 ? 4 : 2,
          baseIcon: cfg.baseAsset.charAt(0),
          marketCap: refPrice * 1e9 * 0.5,
        });
      }
      return liveMarkets;
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
    queryFn: (): Market | undefined => {
      if (market) return market;
      if (USE_MOCK) return getMockEngine().getMarket(id);
      return undefined;
    },
    staleTime: 1000,
    refetchInterval: 1000,
    initialData: market,
  });
}

// ─── OHLC HOOK ──────────────────────────────────────────────────────────────

export function useOHLC(id: MarketId, tf: Timeframe) {
  return useQuery({
    queryKey: qk.ohlc(id, tf),
    queryFn: async (): Promise<OHLCBar[]> => {
      if (USE_MOCK) return getMockEngine().generateOHLC(id, tf);
      try {
        const res = await fetchJson<{ bars: OHLCBar[] }>(`/exchange/ohlc/${id}?timeframe=${tf}`);
        return res.bars;
      } catch {
        return [];
      }
    },
    staleTime: 10000,
  });
}

// ─── ORDER BOOK HOOK ────────────────────────────────────────────────────────

export function useOrderBook(id: MarketId) {
  return useQuery({
    queryKey: qk.orderbook(id),
    queryFn: async (): Promise<OrderBook | undefined> => {
      if (USE_MOCK) return getMockEngine().getOrderBook(id);
      const apiBook = await apiGetOrderBook(id);
      return adaptApiOrderBook(apiBook);
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
      if (USE_MOCK) return getMockEngine().getTrades(id);
      const apiTrades = await apiGetRecentTrades(id, 50);
      return apiTrades.map(adaptApiTrade);
    },
    staleTime: 1000,
    refetchInterval: 1000,
  });
}

// ─── POSITION HOOKS ─────────────────────────────────────────────────────────

export function usePositions() {
  return useQuery({
    queryKey: qk.positions,
    queryFn: async (): Promise<Position[]> => {
      if (USE_MOCK) return getMockEngine().generatePositions();
      try {
        const res = await fetchJson<{ positions: Position[] }>("/exchange/positions");
        return res.positions;
      } catch {
        return [];
      }
    },
    staleTime: 2000,
    refetchInterval: 2000,
  });
}

export function useOpenOrders() {
  const walletAddress = useExchangeStore((s) => s.walletAddress);

  return useQuery({
    queryKey: qk.openOrders,
    queryFn: async (): Promise<Order[]> => {
      if (USE_MOCK) return getMockEngine().generateOpenOrders();
      if (!walletAddress) return [];
      const apiOrders = await apiGetUserOrders(walletAddress);
      return apiOrders.map(adaptApiOrder);
    },
    staleTime: 2000,
    refetchInterval: 5000,
  });
}

export function useMyFills() {
  const walletAddress = useExchangeStore((s) => s.walletAddress);

  return useQuery({
    queryKey: qk.myFills,
    queryFn: async (): Promise<Order[]> => {
      if (USE_MOCK) return getMockEngine().generateMyFills();
      if (!walletAddress) return [];
      try {
        const res = await fetchJson<{ fills: Order[] }>(`/exchange/fills/${walletAddress}`);
        return res.fills;
      } catch {
        return [];
      }
    },
    staleTime: 10000,
  });
}

// ─── BALANCE HOOKS ──────────────────────────────────────────────────────────

export function useBalances() {
  const walletAddress = useExchangeStore((s) => s.walletAddress);

  return useQuery({
    queryKey: qk.balances,
    queryFn: async (): Promise<Balance[]> => {
      if (USE_MOCK) return getMockEngine().generateBalances();
      if (!walletAddress) return [];
      const apiBalance = await apiGetUserBalance(walletAddress);
      return apiBalance.balances.map(adaptApiBalance);
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
      if (!walletAddress) throw new Error("Wallet not connected");
      const order: NewOrder = {
        pair: params.pair,
        side: params.side,
        type: params.type,
        price: params.price,
        size: params.size,
        address: walletAddress,
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
    queryFn: async (): Promise<FundingPayment[]> => {
      if (USE_MOCK) return getMockEngine().generateFundingPayments(id);
      try {
        const res = await fetchJson<{ payments: FundingPayment[] }>(`/exchange/funding/${id}`);
        return res.payments;
      } catch {
        return [];
      }
    },
    staleTime: 30000,
  });
}

// ─── LIQUIDATION HOOK ───────────────────────────────────────────────────────

export function useLiquidationLevels(id: MarketId) {
  return useQuery({
    queryKey: qk.liquidations(id),
    queryFn: async (): Promise<LiquidationLevel[]> => {
      if (USE_MOCK) return getMockEngine().generateLiquidationLevels(id);
      try {
        const res = await fetchJson<{ levels: LiquidationLevel[] }>(`/exchange/liquidations/${id}`);
        return res.levels;
      } catch {
        return [];
      }
    },
    staleTime: 30000,
  });
}

// ─── EQUITY HOOK ────────────────────────────────────────────────────────────

export function useEquityHistory() {
  const walletAddress = useExchangeStore((s) => s.walletAddress);

  return useQuery({
    queryKey: qk.equity,
    queryFn: async (): Promise<EquitySnapshot[]> => {
      if (USE_MOCK) return getMockEngine().generateEquityHistory();
      if (!walletAddress) return [];
      try {
        const res = await fetchJson<{ snapshots: EquitySnapshot[] }>(`/exchange/equity/${walletAddress}`);
        return res.snapshots;
      } catch {
        return [];
      }
    },
    staleTime: 60000,
  });
}

// ─── QUANTUM INTELLIGENCE HOOKS ─────────────────────────────────────────────

export function useSusySignal() {
  return useQuery({
    queryKey: qk.susy,
    queryFn: async (): Promise<SusySignal> => {
      if (USE_MOCK) return getMockEngine().generateSusySignal();
      try {
        return await fetchJson<SusySignal>("/exchange/susy-signal");
      } catch {
        return { score: 0, label: "unavailable", interpretation: "Data unavailable", history: [] };
      }
    },
    staleTime: 30000,
  });
}

export function useVqeOracle() {
  return useQuery({
    queryKey: qk.vqe,
    queryFn: async (): Promise<VqeOracle> => {
      if (USE_MOCK) return getMockEngine().generateVqeOracle();
      try {
        return await fetchJson<VqeOracle>("/exchange/vqe-oracle");
      } catch {
        return {
          fairValue: 0, marketPrice: 0, deviation: 0, deviationPct: 0,
          oracleSources: 0, oracleTotal: 0, confidence: 0,
          lastBlock: 0, lastBlockAge: 0, history: [],
        };
      }
    },
    staleTime: 15000,
  });
}

export function useValidators() {
  return useQuery({
    queryKey: qk.validators,
    queryFn: async (): Promise<ValidatorStatus[]> => {
      if (USE_MOCK) return getMockEngine().generateValidators();
      try {
        const res = await fetchJson<{ validators: ValidatorStatus[] }>("/exchange/validators");
        return res.validators;
      } catch {
        return [];
      }
    },
    staleTime: 15000,
  });
}

export function useQevi() {
  return useQuery({
    queryKey: qk.qevi,
    queryFn: async (): Promise<QeviData> => {
      if (USE_MOCK) return getMockEngine().generateQevi();
      try {
        return await fetchJson<QeviData>("/exchange/qevi");
      } catch {
        return { entropy: 0, score: 0, regime: "unavailable", history: [] };
      }
    },
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
