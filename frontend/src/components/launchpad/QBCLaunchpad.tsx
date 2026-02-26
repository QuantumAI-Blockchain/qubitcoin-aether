// ─── QBC LAUNCHPAD — Root Component ───────────────────────────────────────────
"use client";

import React, { memo, lazy, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useLaunchpadStore } from "./store";
import { L, FONT, SkeletonLoader } from "./shared";
import LaunchpadHeader from "./LaunchpadHeader";
import DiscoverView from "./DiscoverView";

const DeployWizard = lazy(() =>
  import("./DeployWizard").then((m) => ({ default: m.DeployWizard }))
);
const TokenDetailView = lazy(() =>
  import("./TokenDetailView").then((m) => ({ default: m.TokenDetailView }))
);
const LeaderboardView = lazy(() =>
  import("./LeaderboardView").then((m) => ({ default: m.LeaderboardView }))
);
const EcosystemMap = lazy(() =>
  import("./EcosystemMap").then((m) => ({ default: m.EcosystemMap }))
);
const CommunityDDView = lazy(() =>
  import("./CommunityDDView").then((m) => ({ default: m.CommunityDDView }))
);
const PortfolioView = lazy(() =>
  import("./PortfolioView").then((m) => ({ default: m.PortfolioView }))
);

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

/* ── Inner Launchpad (needs store + query context) ────────────────────────── */

const LaunchpadInner = memo(function LaunchpadInner() {
  const view = useLaunchpadStore((s) => s.view);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 64px)",
        background: L.bgBase,
        color: L.textPrimary,
        fontFamily: FONT.body,
        overflow: "hidden",
      }}
    >
      <LaunchpadHeader />

      <div
        style={{ flex: 1, overflow: "auto" }}
        className="launchpad-scroll"
      >
        <Suspense fallback={<LoadingFallback />}>
          {view === "discover" && <DiscoverView />}
          {view === "deploy" && <DeployWizard />}
          {view === "token" && <TokenDetailView />}
          {view === "leaderboard" && <LeaderboardView />}
          {view === "ecosystem" && <EcosystemMap />}
          {view === "cdd" && <CommunityDDView />}
          {view === "portfolio" && <PortfolioView />}
        </Suspense>
      </div>
    </div>
  );
});

/* ── Root Export ───────────────────────────────────────────────────────────── */

export default function QBCLaunchpad() {
  return (
    <QueryClientProvider client={queryClient}>
      <LaunchpadInner />
    </QueryClientProvider>
  );
}
