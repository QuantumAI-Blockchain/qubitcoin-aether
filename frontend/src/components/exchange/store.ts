// ─── QBC EXCHANGE — Zustand Store ────────────────────────────────────────────
"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { MarketId, ExchangeView, ExchangeSettings, Timeframe } from "./types";

interface ExchangeState {
  // Navigation
  view: ExchangeView;
  setView: (v: ExchangeView) => void;

  // Market selection
  activeMarket: MarketId;
  setActiveMarket: (id: MarketId) => void;

  // Favourites
  favourites: MarketId[];
  toggleFavourite: (id: MarketId) => void;

  // Chart
  timeframe: Timeframe;
  setTimeframe: (tf: Timeframe) => void;
  indicators: string[];
  toggleIndicator: (ind: string) => void;

  // Order entry
  orderSide: "buy" | "sell";
  setOrderSide: (s: "buy" | "sell") => void;
  orderType: "limit" | "market" | "stop_limit" | "stop_market";
  setOrderType: (t: "limit" | "market" | "stop_limit" | "stop_market") => void;
  orderPrice: string;
  setOrderPrice: (p: string) => void;
  orderSize: string;
  setOrderSize: (s: string) => void;
  orderTriggerPrice: string;
  setOrderTriggerPrice: (p: string) => void;
  orderLeverage: number;
  setOrderLeverage: (l: number) => void;
  orderTif: "gtc" | "ioc" | "fok" | "post";
  setOrderTif: (t: "gtc" | "ioc" | "fok" | "post") => void;
  orderReduceOnly: boolean;
  setOrderReduceOnly: (r: boolean) => void;

  // Order book
  obGrouping: number;
  setObGrouping: (g: number) => void;
  obRows: 10 | 20 | 50;
  setObRows: (r: 10 | 20 | 50) => void;

  // Positions panel tab
  positionsTab: string;
  setPositionsTab: (t: string) => void;

  // Wallet connected state (local exchange wallet)
  walletConnected: boolean;
  walletAddress: string;
  setWallet: (connected: boolean, address: string) => void;

  // Settings
  settings: ExchangeSettings;
  updateSettings: (partial: Partial<ExchangeSettings>) => void;

  // UI
  marketSelectorOpen: boolean;
  setMarketSelectorOpen: (open: boolean) => void;
  depositModalOpen: boolean;
  setDepositModalOpen: (open: boolean) => void;
  depositAsset: string;
  setDepositAsset: (asset: string) => void;
  withdrawModalOpen: boolean;
  setWithdrawModalOpen: (open: boolean) => void;
  withdrawAsset: string;
  setWithdrawAsset: (asset: string) => void;
  settingsPanelOpen: boolean;
  setSettingsPanelOpen: (open: boolean) => void;

  // Toasts
  toasts: { id: string; message: string; type: "info" | "success" | "error" | "warning" }[];
  addToast: (message: string, type?: "info" | "success" | "error" | "warning") => void;
  removeToast: (id: string) => void;
}

const defaultSettings: ExchangeSettings = {
  defaultOrderType: "limit",
  defaultTif: "gtc",
  confirmOrders: true,
  confirmCancels: false,
  defaultLeverage: {} as Record<MarketId, number>,
  currencyDisplay: "qusd",
  candleStyle: "candle",
  orderBookGrouping: 0.0001,
  orderBookRows: 20,
  timestampFormat: "relative",
  soundEnabled: false,
  notifyFilled: true,
  notifyLiquidation: true,
  notifyFunding: false,
  rpcUrl: process.env.NEXT_PUBLIC_RPC_URL ?? "http://localhost:5000",
  expertMode: false,
};

export const useExchangeStore = create<ExchangeState>()(
  persist(
    (set) => ({
      view: "trading",
      setView: (v) => set({ view: v }),

      activeMarket: "QBC_QUSD",
      setActiveMarket: (id) => set({ activeMarket: id, orderPrice: "", orderSize: "" }),

      favourites: ["QBC_QUSD", "QBC_PERP", "ETH_PERP"],
      toggleFavourite: (id) =>
        set((s) => ({
          favourites: s.favourites.includes(id)
            ? s.favourites.filter((f) => f !== id)
            : [...s.favourites, id],
        })),

      timeframe: "1h",
      setTimeframe: (tf) => set({ timeframe: tf }),
      indicators: ["volume"],
      toggleIndicator: (ind) =>
        set((s) => ({
          indicators: s.indicators.includes(ind)
            ? s.indicators.filter((i) => i !== ind)
            : [...s.indicators, ind],
        })),

      orderSide: "buy",
      setOrderSide: (s) => set({ orderSide: s }),
      orderType: "limit",
      setOrderType: (t) => set({ orderType: t }),
      orderPrice: "",
      setOrderPrice: (p) => set({ orderPrice: p }),
      orderSize: "",
      setOrderSize: (s) => set({ orderSize: s }),
      orderTriggerPrice: "",
      setOrderTriggerPrice: (p) => set({ orderTriggerPrice: p }),
      orderLeverage: 5,
      setOrderLeverage: (l) => set({ orderLeverage: l }),
      orderTif: "gtc",
      setOrderTif: (t) => set({ orderTif: t }),
      orderReduceOnly: false,
      setOrderReduceOnly: (r) => set({ orderReduceOnly: r }),

      obGrouping: 0.0001,
      setObGrouping: (g) => set({ obGrouping: g }),
      obRows: 20,
      setObRows: (r) => set({ obRows: r }),

      positionsTab: "positions",
      setPositionsTab: (t) => set({ positionsTab: t }),

      walletConnected: true,
      walletAddress: "qbc1x7k4m9f2a8d3w...",
      setWallet: (connected, address) => set({ walletConnected: connected, walletAddress: address }),

      settings: defaultSettings,
      updateSettings: (partial) =>
        set((s) => ({ settings: { ...s.settings, ...partial } })),

      marketSelectorOpen: true,
      setMarketSelectorOpen: (open) => set({ marketSelectorOpen: open }),
      depositModalOpen: false,
      setDepositModalOpen: (open) => set({ depositModalOpen: open }),
      depositAsset: "QBC",
      setDepositAsset: (asset) => set({ depositAsset: asset }),
      withdrawModalOpen: false,
      setWithdrawModalOpen: (open) => set({ withdrawModalOpen: open }),
      withdrawAsset: "QBC",
      setWithdrawAsset: (asset) => set({ withdrawAsset: asset }),
      settingsPanelOpen: false,
      setSettingsPanelOpen: (open) => set({ settingsPanelOpen: open }),

      toasts: [],
      addToast: (message, type = "info") =>
        set((s) => ({
          toasts: [
            ...s.toasts,
            { id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), message, type },
          ],
        })),
      removeToast: (id) =>
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
    }),
    {
      name: "qbc-exchange-store",
      partialize: (state) => ({
        favourites: state.favourites,
        timeframe: state.timeframe,
        indicators: state.indicators,
        obGrouping: state.obGrouping,
        obRows: state.obRows,
        settings: state.settings,
        activeMarket: state.activeMarket,
      }),
    },
  ),
);
