// ─── QBC EXCHANGE — Trading Layout (Main Grid) ──────────────────────────────
"use client";

import React, { memo, useState, lazy, Suspense } from "react";
import { useExchangeStore } from "./store";
import { X, FONT, SkeletonLoader, panelStyle } from "./shared";
import { MarketSelector } from "./MarketSelector";
import { MarketStatsBar } from "./MarketStatsBar";
import PriceChart from "./PriceChart";
import OrderBook from "./OrderBook";
import OrderEntry from "./OrderEntry";
import { TradeHistory } from "./TradeHistory";

const DepthChart = lazy(() => import("./DepthChart"));
const PositionsPanel = lazy(() => import("./PositionsPanel"));
const FundingRatePanel = lazy(() => import("./FundingRatePanel"));
const LiquidationHeatmap = lazy(() => import("./LiquidationHeatmap"));
const QuantumIntelligence = lazy(() => import("./QuantumIntelligence"));

type BottomTab = "positions" | "funding" | "liquidation" | "quantum";

const LoadingFallback = () => (
  <div style={{ ...panelStyle, padding: 24, display: "flex", justifyContent: "center" }}>
    <SkeletonLoader width="100%" height={200} />
  </div>
);

export const TradingLayout = memo(function TradingLayout() {
  const activeMarket = useExchangeStore((s) => s.activeMarket);
  const isPerp = activeMarket.includes("PERP");
  const [bottomTab, setBottomTab] = useState<BottomTab>("positions");

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
      {/* Market stats bar */}
      <MarketStatsBar />

      {/* Main trading grid */}
      <div
        style={{
          display: "flex",
          flex: 1,
          overflow: "hidden",
          minHeight: 0,
        }}
      >
        {/* Left: Market selector */}
        <MarketSelector />

        {/* Centre + Right */}
        <div style={{ display: "flex", flex: 1, overflow: "hidden", minWidth: 0 }}>
          {/* Centre: Chart + Depth */}
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              minWidth: 0,
            }}
          >
            {/* Price chart */}
            <div style={{ flex: 2, minHeight: 300, overflow: "hidden" }}>
              <PriceChart />
            </div>
            {/* Depth chart */}
            <div style={{ flex: 1, minHeight: 160, overflow: "hidden", borderTop: `1px solid ${X.borderSubtle}` }}>
              <Suspense fallback={<LoadingFallback />}>
                <DepthChart />
              </Suspense>
            </div>
          </div>

          {/* Right sidebar: OrderBook + OrderEntry + TradeHistory */}
          <div
            style={{
              width: 300,
              minWidth: 280,
              maxWidth: 340,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              borderLeft: `1px solid ${X.borderSubtle}`,
              flexShrink: 0,
            }}
          >
            {/* Order book */}
            <div style={{ flex: 2, minHeight: 200, overflow: "hidden" }}>
              <OrderBook />
            </div>
            {/* Order entry */}
            <div style={{ borderTop: `1px solid ${X.borderSubtle}`, overflow: "auto" }} className="exchange-scroll">
              <OrderEntry />
            </div>
            {/* Trade history */}
            <div style={{ flex: 1, minHeight: 150, overflow: "hidden", borderTop: `1px solid ${X.borderSubtle}` }}>
              <TradeHistory />
            </div>
          </div>
        </div>
      </div>

      {/* Bottom panel with tabs */}
      <div style={{ borderTop: `1px solid ${X.borderSubtle}`, flexShrink: 0 }}>
        {/* Tab bar */}
        <div style={{ display: "flex", gap: 0, background: X.bgPanel, borderBottom: `1px solid ${X.borderSubtle}` }}>
          {(
            [
              { key: "positions", label: "Positions & Orders" },
              ...(isPerp ? [{ key: "funding", label: "Funding" }] : []),
              ...(isPerp ? [{ key: "liquidation", label: "Liquidation Map" }] : []),
              { key: "quantum", label: "Quantum Intelligence" },
            ] as { key: BottomTab; label: string }[]
          ).map((t) => (
            <button
              key={t.key}
              onClick={() => setBottomTab(t.key)}
              style={{
                fontFamily: FONT.display,
                fontSize: 10,
                letterSpacing: "0.06em",
                color: bottomTab === t.key ? X.glowCyan : X.textSecondary,
                background: "none",
                border: "none",
                borderBottom: bottomTab === t.key ? `2px solid ${X.glowCyan}` : "2px solid transparent",
                padding: "10px 18px",
                cursor: "pointer",
                textTransform: "uppercase",
                transition: "color 0.15s",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div style={{ maxHeight: 360, overflow: "auto" }} className="exchange-scroll">
          <Suspense fallback={<LoadingFallback />}>
            {bottomTab === "positions" && <PositionsPanel />}
            {bottomTab === "funding" && <FundingRatePanel />}
            {bottomTab === "liquidation" && <LiquidationHeatmap />}
            {bottomTab === "quantum" && <QuantumIntelligence />}
          </Suspense>
        </div>
      </div>
    </div>
  );
});
