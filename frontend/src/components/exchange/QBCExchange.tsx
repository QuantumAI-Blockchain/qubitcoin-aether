// ─── QBC EXCHANGE — Root Component ───────────────────────────────────────────
"use client";

import React, { memo, lazy, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AnimatePresence } from "framer-motion";
import { useExchangeStore } from "./store";
import { useTickSimulation } from "./hooks";
import { X, FONT, SkeletonLoader, Toast, panelStyle } from "./shared";
import { ExchangeHeader } from "./ExchangeHeader";
import { TradingLayout } from "./TradingLayout";

const PortfolioPanel = lazy(() => import("./PortfolioPanel"));
const DepositModal = lazy(() => import("./DepositModal"));
const WithdrawModal = lazy(() => import("./WithdrawModal"));
const ExchangeSettings = lazy(() => import("./ExchangeSettings"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const LoadingFallback = () => (
  <div style={{ padding: 40, display: "flex", justifyContent: "center" }}>
    <SkeletonLoader width={600} height={400} />
  </div>
);

// ─── INNER EXCHANGE (needs store + query context) ───────────────────────────

const ExchangeInner = memo(function ExchangeInner() {
  const view = useExchangeStore((s) => s.view);
  const depositOpen = useExchangeStore((s) => s.depositModalOpen);
  const withdrawOpen = useExchangeStore((s) => s.withdrawModalOpen);
  const settingsOpen = useExchangeStore((s) => s.settingsPanelOpen);
  const toasts = useExchangeStore((s) => s.toasts);
  const removeToast = useExchangeStore((s) => s.removeToast);

  // Tick simulation drives mock data updates
  useTickSimulation();

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 64px)", // Account for site navbar
        background: X.bgBase,
        color: X.textPrimary,
        fontFamily: FONT.body,
        overflow: "hidden",
      }}
    >
      {/* Header + Ticker */}
      <ExchangeHeader />

      {/* Main content area */}
      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {view === "trading" && <TradingLayout />}
        {view === "portfolio" && (
          <Suspense fallback={<LoadingFallback />}>
            <div style={{ flex: 1, overflow: "auto", padding: 16 }} className="exchange-scroll">
              <PortfolioPanel />
            </div>
          </Suspense>
        )}
      </div>

      {/* Modals */}
      <Suspense fallback={null}>
        {depositOpen && <DepositModal />}
        {withdrawOpen && <WithdrawModal />}
        {settingsOpen && <ExchangeSettings />}
      </Suspense>

      {/* Toast stack */}
      <div
        style={{
          position: "fixed",
          bottom: 20,
          right: 20,
          zIndex: 60,
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <AnimatePresence>
          {toasts.map((t) => (
            <Toast
              key={t.id}
              message={t.message}
              type={t.type}
              onDismiss={() => removeToast(t.id)}
            />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
});

// ─── ROOT EXPORT ────────────────────────────────────────────────────────────

export default function QBCExchange() {
  return (
    <QueryClientProvider client={queryClient}>
      <ExchangeInner />
    </QueryClientProvider>
  );
}
