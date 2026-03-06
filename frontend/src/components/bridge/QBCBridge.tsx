"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Bridge — Main Wrapper + Router
   Default export for the entire bridge. Provides QueryClientProvider,
   injects fonts and global styles, handles hash-based routing, and
   renders the correct view.
   ───────────────────────────────────────────────────────────────────────── */

import { useEffect, useMemo, Suspense, lazy } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useBridgeStore } from "./store";
import { B, FONT, BridgeStyles, ToastContainer } from "./shared";
import { GlobalHeader } from "./GlobalHeader";
import { BridgePanel } from "./BridgePanel";
import { WalletModal } from "./WalletModal";
import { PreFlightModal } from "./PreFlightModal";
import { SettingsPanel } from "./SettingsPanel";
import { DevTools } from "./DevTools";
import type { BridgeView } from "./types";

/* ── Lazy-loaded heavy views ─────────────────────────────────────────── */

const TxStatusView = lazy(() => import("./TxStatusView"));
const HistoryView = lazy(() => import("./HistoryView"));
const VaultDashboard = lazy(() => import("./VaultDashboard"));
const FeeAnalytics = lazy(() => import("./FeeAnalytics"));

/* ── Loading Fallback ────────────────────────────────────────────────── */

function ViewLoader() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="text-center">
        <div
          className="mx-auto h-8 w-8 animate-spin rounded-full border-2"
          style={{ borderColor: B.borderSubtle, borderTopColor: B.glowCyan }}
        />
        <p
          className="mt-3 text-[10px] tracking-widest"
          style={{ color: B.textSecondary, fontFamily: FONT.display }}
        >
          LOADING
        </p>
      </div>
    </div>
  );
}

/* ── View Router ─────────────────────────────────────────────────────── */

function BridgeRouter() {
  const view = useBridgeStore((s) => s.view);
  const viewParams = useBridgeStore((s) => s.viewParams);

  switch (view) {
    case "bridge":
      return <BridgePanel />;
    case "tx":
      return (
        <Suspense fallback={<ViewLoader />}>
          <TxStatusView />
        </Suspense>
      );
    case "history":
      return (
        <Suspense fallback={<ViewLoader />}>
          <HistoryView />
        </Suspense>
      );
    case "vault":
      return (
        <Suspense fallback={<ViewLoader />}>
          <VaultDashboard />
        </Suspense>
      );
    case "fees":
      return (
        <Suspense fallback={<ViewLoader />}>
          <FeeAnalytics />
        </Suspense>
      );
    default:
      return <BridgePanel />;
  }
}

/* ── Fonts ────────────────────────────────────────────────────────────
   Orbitron, Share Tech Mono, and Exo 2 are loaded via next/font/google
   in the root layout (app/layout.tsx). No manual injection needed.
   ───────────────────────────────────────────────────────────────────── */

/* ── Main Bridge App ─────────────────────────────────────────────────── */

function BridgeApp() {
  const syncFromHash = useBridgeStore((s) => s.syncFromHash);

  // Listen for hash changes (browser back/forward)
  useEffect(() => {
    function onHashChange() {
      syncFromHash();
    }
    window.addEventListener("hashchange", onHashChange);
    // Initial sync
    syncFromHash();
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [syncFromHash]);

  return (
    <div
      className="min-h-screen"
      style={{
        background: B.bgBase,
        fontFamily: FONT.body,
        color: B.textPrimary,
      }}
    >
      {/* Inject global CSS animations */}
      <BridgeStyles />

      {/* Fonts loaded via next/font/google in root layout */}

      {/* Header + Ticker */}
      <GlobalHeader />

      {/* Main content area */}
      <main className="mx-auto max-w-7xl px-4 py-6">
        <BridgeRouter />
      </main>

      {/* Verified Contracts Banner */}
      <section className="border-t px-4 py-6" style={{ borderColor: B.borderSubtle, background: `${B.bgPanel}` }}>
        <div className="mx-auto max-w-7xl">
          <h3
            className="mb-4 text-center text-[10px] font-bold uppercase tracking-[0.3em]"
            style={{ color: B.textSecondary, fontFamily: FONT.display }}
          >
            Verified Contracts & Live Pools
          </h3>
          <div className="grid gap-4 sm:grid-cols-2">
            {/* Ethereum */}
            <div className="rounded-xl border p-4" style={{ borderColor: "#627eea30", background: `${B.bgBase}` }}>
              <div className="mb-3 flex items-center gap-2">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: "#627eea", boxShadow: "0 0 6px #627eea80" }} />
                <span className="text-xs font-bold tracking-widest" style={{ color: "#627eea", fontFamily: FONT.display }}>ETHEREUM</span>
              </div>
              <div className="space-y-2 text-[10px]" style={{ fontFamily: FONT.mono }}>
                <div className="flex items-center justify-between">
                  <span style={{ color: B.textSecondary }}>wQBC</span>
                  <a href="https://etherscan.io/token/0xB7c8783dDfb7f72b2C27AFBDFFD2B0206046Fa67" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 transition-opacity hover:opacity-80" style={{ color: B.glowCyan }}>
                    0xB7c8…Fa67 <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
                  </a>
                </div>
                <div className="flex items-center justify-between">
                  <span style={{ color: B.textSecondary }}>wQUSD</span>
                  <a href="https://etherscan.io/token/0x884867d25552b6117F85428405aeAA208A8CAdB3" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 transition-opacity hover:opacity-80" style={{ color: B.glowEmerald }}>
                    0x8848…CAdB3 <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
                  </a>
                </div>
                <div className="flex items-center justify-between border-t pt-2" style={{ borderColor: `${B.borderSubtle}60` }}>
                  <span style={{ color: B.glowGold }}>Uniswap V3</span>
                  <span style={{ color: B.textSecondary }}>100K/100K · 0.3% fee</span>
                </div>
              </div>
            </div>
            {/* BNB Chain */}
            <div className="rounded-xl border p-4" style={{ borderColor: "#f3ba2f30", background: `${B.bgBase}` }}>
              <div className="mb-3 flex items-center gap-2">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: "#f3ba2f", boxShadow: "0 0 6px #f3ba2f80" }} />
                <span className="text-xs font-bold tracking-widest" style={{ color: "#f3ba2f", fontFamily: FONT.display }}>BNB CHAIN</span>
              </div>
              <div className="space-y-2 text-[10px]" style={{ fontFamily: FONT.mono }}>
                <div className="flex items-center justify-between">
                  <span style={{ color: B.textSecondary }}>wQBC</span>
                  <a href="https://bscscan.com/token/0xA8dAB13B55D7D5f9d140D0ec7B3772D373616147" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 transition-opacity hover:opacity-80" style={{ color: B.glowCyan }}>
                    0xA8dA…6147 <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
                  </a>
                </div>
                <div className="flex items-center justify-between">
                  <span style={{ color: B.textSecondary }}>wQUSD</span>
                  <a href="https://bscscan.com/token/0xD137C89ed83d1D54802d07487bf1AF6e0b409BE3" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 transition-opacity hover:opacity-80" style={{ color: B.glowEmerald }}>
                    0xD137…BE3 <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
                  </a>
                </div>
                <div className="flex items-center justify-between border-t pt-2" style={{ borderColor: `${B.borderSubtle}60` }}>
                  <span style={{ color: B.glowGold }}>PancakeSwap V2</span>
                  <a href="https://bscscan.com/address/0x3927EfB12bDaf7E2d9930A3581177a0646456abd" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 transition-opacity hover:opacity-80" style={{ color: B.textSecondary }}>
                    100K/100K · 0.25% fee <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
                  </a>
                </div>
              </div>
            </div>
          </div>
          <p className="mt-3 text-center text-[9px]" style={{ color: B.textSecondary, fontFamily: FONT.mono }}>
            All contracts source-verified on Etherscan & BscScan · Solidity 0.8.28 · MIT License
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-4" style={{ borderColor: B.borderSubtle }}>
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4">
          <span className="text-[9px] tracking-wider" style={{ color: B.textSecondary, fontFamily: FONT.mono }}>
            QBC BRIDGE v1.0.0 — PROTOCOL v3.0
          </span>
          <div className="flex items-center gap-4">
            <span className="text-[9px]" style={{ color: B.textSecondary }}>
              100% Vault-Backed — Post-Quantum Secured
            </span>
            <a
              href="https://qbc.network"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[9px] transition-opacity hover:opacity-80"
              style={{ color: B.glowCyan, fontFamily: FONT.display }}
            >
              qbc.network
            </a>
          </div>
        </div>
      </footer>

      {/* Overlays */}
      <WalletModal />
      <PreFlightModal />
      <SettingsPanel />
      {process.env.NODE_ENV !== "production" && <DevTools />}
      <ToastContainer />
    </div>
  );
}

/* ── Root Export (with QueryClientProvider) ───────────────────────────── */

export default function QBCBridge() {
  const queryClient = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 10_000,
            refetchOnWindowFocus: false,
          },
        },
      }),
    []
  );

  return (
    <QueryClientProvider client={queryClient}>
      <BridgeApp />
    </QueryClientProvider>
  );
}
