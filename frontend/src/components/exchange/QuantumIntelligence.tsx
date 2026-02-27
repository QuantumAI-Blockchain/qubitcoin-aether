// ─── QBC EXCHANGE — Quantum Market Intelligence Panel ─────────────────────────
// Lazy-loaded wrapper for 4 sub-panels split for performance
"use client";

import React, { memo, Suspense, lazy } from "react";
import { X, FONT } from "./shared";

const QuantumAnalysis = lazy(() => import("./QuantumAnalysis"));
const RiskHeatmap = lazy(() => import("./RiskHeatmap"));
const SignalDashboard = lazy(() => import("./SignalDashboard"));
const SentimentGauge = lazy(() => import("./SentimentGauge"));

function PanelLoader() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 200,
        borderRadius: 8,
        border: `1px solid ${X.borderSubtle}`,
        background: X.bgPanel,
      }}
    >
      <span
        style={{
          fontFamily: FONT.display,
          fontSize: 10,
          letterSpacing: "0.08em",
          color: X.textSecondary,
        }}
      >
        LOADING...
      </span>
    </div>
  );
}

const QuantumIntelligence = memo(function QuantumIntelligence() {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
        gap: 12,
        width: "100%",
      }}
    >
      <Suspense fallback={<PanelLoader />}>
        <QuantumAnalysis />
      </Suspense>
      <Suspense fallback={<PanelLoader />}>
        <RiskHeatmap />
      </Suspense>
      <Suspense fallback={<PanelLoader />}>
        <SignalDashboard />
      </Suspense>
      <Suspense fallback={<PanelLoader />}>
        <SentimentGauge />
      </Suspense>
    </div>
  );
});

export default QuantumIntelligence;
