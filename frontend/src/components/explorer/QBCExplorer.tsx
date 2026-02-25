"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Block Explorer — Main Wrapper + Hash Router
   Qubitcoin quantum blockchain explorer: blocks, transactions, QVM
   contracts, AetherTree topology, SUSY leaderboard, and pathfinder.
   ───────────────────────────────────────────────────────────────────────── */

import { useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useExplorerStore } from "./store";
import { C, FONT, ExplorerHeader } from "./shared";

/* ── View imports ─────────────────────────────────────────────────────── */
import { Dashboard } from "./Dashboard";
import { BlockDetail } from "./BlockDetail";
import { TransactionDetail } from "./TransactionDetail";
import { QVMExplorerView } from "./QVMExplorer";
import { AetherTreeView } from "./AetherTreeVis";
import { WalletView } from "./WalletView";
import { MetricsDashboard } from "./MetricsDashboard";
import { SearchResults } from "./SearchResults";
import { PathfinderView } from "./Pathfinder";
import { SUSYLeaderboard } from "./SUSYLeaderboard";
import { DevToolsPanel } from "./DevTools";

/* ── React Query client ───────────────────────────────────────────────── */

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

/* ── Google Fonts injection ───────────────────────────────────────────── */

function FontLoader() {
  useEffect(() => {
    if (document.getElementById("qbc-explorer-fonts")) return;
    const link = document.createElement("link");
    link.id = "qbc-explorer-fonts";
    link.rel = "stylesheet";
    link.href =
      "https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Share+Tech+Mono&family=Exo+2:wght@300;400;500;600;700&display=swap";
    document.head.appendChild(link);
  }, []);
  return null;
}

/* ── Hash Router ──────────────────────────────────────────────────────── */

function ExplorerRouter() {
  const { route, syncFromHash } = useExplorerStore();

  // Listen for browser back/forward
  useEffect(() => {
    const handler = () => syncFromHash();
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, [syncFromHash]);

  // Keyboard: Ctrl+Shift+D for DevTools
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === "D") {
        e.preventDefault();
        useExplorerStore.getState().toggleDevTools();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const { view, params } = route;

  switch (view) {
    case "dashboard":
      return <Dashboard />;

    case "block": {
      const height = parseInt(params.id ?? "0", 10);
      return <BlockDetail height={isNaN(height) ? 0 : height} />;
    }

    case "transaction":
      return <TransactionDetail txid={params.id ?? ""} />;

    case "qvm":
      return <QVMExplorerView />;

    case "aether":
      return <AetherTreeView />;

    case "wallet":
      return <WalletView address={params.id ?? ""} />;

    case "metrics":
      return <MetricsDashboard />;

    case "search":
      return <SearchResults query={params.q ?? params.id ?? ""} />;

    case "pathfinder":
      return <PathfinderView />;

    case "leaderboard":
      return <SUSYLeaderboard />;

    default:
      return <Dashboard />;
  }
}

/* ── Main Component ───────────────────────────────────────────────────── */

export default function QBCExplorer() {
  return (
    <QueryClientProvider client={queryClient}>
      <FontLoader />
      <div
        className="flex min-h-screen flex-col"
        style={{
          background: C.bg,
          color: C.textPrimary,
          fontFamily: FONT.body,
        }}
      >
        <ExplorerHeader />
        <main className="flex-1">
          <ExplorerRouter />
        </main>

        {/* Footer */}
        <footer
          className="border-t px-4 py-2 text-center"
          style={{ borderColor: C.border }}
        >
          <span
            className="text-[9px] uppercase tracking-widest"
            style={{ color: C.textMuted, fontFamily: FONT.heading }}
          >
            Qubitcoin Block Explorer — Physics-Secured Digital Assets with On-Chain AGI
          </span>
        </footer>

        {/* DevTools Overlay */}
        <DevToolsPanel />
      </div>
    </QueryClientProvider>
  );
}
