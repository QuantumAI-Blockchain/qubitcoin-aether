// ─── QBC EXCHANGE — React Query Hooks + WebSocket Simulation ─────────────────
"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useCallback } from "react";
import { mockEngine } from "./mock-engine";
import { useExchangeStore } from "./store";
import type { MarketId, Timeframe, Market, OrderBook, Trade, OHLCBar, Position, Order, Balance, FundingPayment, LiquidationLevel, EquitySnapshot, SusySignal, VqeOracle, ValidatorStatus, QeviData } from "./types";

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

// ─── MARKET HOOKS ───────────────────────────────────────────────────────────

export function useMarkets() {
  return useQuery({
    queryKey: qk.markets,
    queryFn: (): Market[] => mockEngine.getAllMarkets(),
    staleTime: 2000,
    refetchInterval: 2000,
  });
}

export function useMarket(id: MarketId) {
  return useQuery({
    queryKey: qk.market(id),
    queryFn: (): Market | undefined => mockEngine.getMarket(id),
    staleTime: 1000,
    refetchInterval: 1000,
  });
}

// ─── OHLC HOOK ──────────────────────────────────────────────────────────────

export function useOHLC(id: MarketId, tf: Timeframe) {
  return useQuery({
    queryKey: qk.ohlc(id, tf),
    queryFn: (): OHLCBar[] => mockEngine.generateOHLC(id, tf),
    staleTime: 10000,
  });
}

// ─── ORDER BOOK HOOK ────────────────────────────────────────────────────────

export function useOrderBook(id: MarketId) {
  return useQuery({
    queryKey: qk.orderbook(id),
    queryFn: (): OrderBook | undefined => mockEngine.getOrderBook(id),
    staleTime: 500,
    refetchInterval: 500,
  });
}

// ─── TRADES HOOK ────────────────────────────────────────────────────────────

export function useTrades(id: MarketId) {
  return useQuery({
    queryKey: qk.trades(id),
    queryFn: (): Trade[] => mockEngine.getTrades(id),
    staleTime: 1000,
    refetchInterval: 1000,
  });
}

// ─── POSITION HOOKS ─────────────────────────────────────────────────────────

export function usePositions() {
  return useQuery({
    queryKey: qk.positions,
    queryFn: (): Position[] => mockEngine.generatePositions(),
    staleTime: 2000,
    refetchInterval: 2000,
  });
}

export function useOpenOrders() {
  return useQuery({
    queryKey: qk.openOrders,
    queryFn: (): Order[] => mockEngine.generateOpenOrders(),
    staleTime: 2000,
    refetchInterval: 5000,
  });
}

export function useMyFills() {
  return useQuery({
    queryKey: qk.myFills,
    queryFn: (): Order[] => mockEngine.generateMyFills(),
    staleTime: 10000,
  });
}

// ─── BALANCE HOOKS ──────────────────────────────────────────────────────────

export function useBalances() {
  return useQuery({
    queryKey: qk.balances,
    queryFn: (): Balance[] => mockEngine.generateBalances(),
    staleTime: 5000,
    refetchInterval: 5000,
  });
}

// ─── FUNDING HOOK ───────────────────────────────────────────────────────────

export function useFunding(id: MarketId) {
  return useQuery({
    queryKey: qk.funding(id),
    queryFn: (): FundingPayment[] => mockEngine.generateFundingPayments(id),
    staleTime: 30000,
  });
}

// ─── LIQUIDATION HOOK ───────────────────────────────────────────────────────

export function useLiquidationLevels(id: MarketId) {
  return useQuery({
    queryKey: qk.liquidations(id),
    queryFn: (): LiquidationLevel[] => mockEngine.generateLiquidationLevels(id),
    staleTime: 30000,
  });
}

// ─── EQUITY HOOK ────────────────────────────────────────────────────────────

export function useEquityHistory() {
  return useQuery({
    queryKey: qk.equity,
    queryFn: (): EquitySnapshot[] => mockEngine.generateEquityHistory(),
    staleTime: 60000,
  });
}

// ─── QUANTUM INTELLIGENCE HOOKS ─────────────────────────────────────────────

export function useSusySignal() {
  return useQuery({
    queryKey: qk.susy,
    queryFn: (): SusySignal => mockEngine.generateSusySignal(),
    staleTime: 30000,
  });
}

export function useVqeOracle() {
  return useQuery({
    queryKey: qk.vqe,
    queryFn: (): VqeOracle => mockEngine.generateVqeOracle(),
    staleTime: 15000,
  });
}

export function useValidators() {
  return useQuery({
    queryKey: qk.validators,
    queryFn: (): ValidatorStatus[] => mockEngine.generateValidators(),
    staleTime: 15000,
  });
}

export function useQevi() {
  return useQuery({
    queryKey: qk.qevi,
    queryFn: (): QeviData => mockEngine.generateQevi(),
    staleTime: 30000,
  });
}

// ─── TICK SIMULATION (WebSocket substitute) ─────────────────────────────────

export function useTickSimulation() {
  const intervalRef = useRef<ReturnType<typeof setInterval>>(undefined);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      mockEngine.tick();
    }, 1000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);
}

// ─── TRADE SIMULATION ───────────────────────────────────────────────────────

export function useTradeSimulation(id: MarketId) {
  useEffect(() => {
    const interval = setInterval(() => {
      mockEngine.addTrade(id);
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
