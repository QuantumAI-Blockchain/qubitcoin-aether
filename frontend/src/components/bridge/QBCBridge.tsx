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
