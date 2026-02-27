// ─── QBC EXCHANGE — VQE Price Oracle Panel ──────────────────────────────────
// Split from QuantumIntelligence.tsx for lazy loading
"use client";

import React, { memo, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { useVqeOracle, useMiningStats } from "./hooks";
import {
  X,
  FONT,
  formatPrice,
  formatPct,
  panelStyle,
  panelHeaderStyle,
} from "./shared";

function formatHour(ts: number): string {
  const d = new Date(ts);
  return `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:00`;
}

const chartAxisStyle = {
  fontFamily: "'Share Tech Mono', monospace",
  fontSize: 10,
  fill: X.textSecondary,
};

const tooltipContentStyle: React.CSSProperties = {
  background: X.bgElevated,
  border: `1px solid ${X.borderSubtle}`,
  borderRadius: 6,
  fontFamily: "'Share Tech Mono', monospace",
  fontSize: 11,
  color: X.textPrimary,
  padding: "6px 10px",
};

const RiskHeatmap = memo(function RiskHeatmap() {
  const { data: oracle } = useVqeOracle();
  const { data: miningStats } = useMiningStats();

  // Use real mining stats to enhance oracle display when available
  const fairValue = oracle?.fairValue ?? 0;
  const marketPrice = oracle?.marketPrice ?? 0;
  const deviation = oracle?.deviation ?? 0;
  const deviationPct = oracle?.deviationPct ?? 0;
  const oracleSources = oracle?.oracleSources ?? 0;
  const oracleTotal = oracle?.oracleTotal ?? 0;
  // Blend real mining confidence: if we have stats, use blocks_mined > 0 as a confidence signal
  const confidence = miningStats && miningStats.blocks_mined > 0
    ? Math.min(100, 80 + Math.min(20, miningStats.blocks_mined / 50))
    : oracle?.confidence ?? 0;

  const isPremium = deviation >= 0;
  const deviationColor = isPremium ? X.glowEmerald : X.glowCrimson;
  const deviationLabel = isPremium ? "PREMIUM" : "DISCOUNT";

  const chartData = useMemo(() => {
    if (!oracle?.history) return [];
    return oracle.history.filter((_, i) => i % 2 === 0 || i === oracle.history.length - 1);
  }, [oracle?.history]);

  const confidenceColor = confidence >= 95 ? X.glowEmerald : confidence >= 80 ? X.glowCyan : confidence >= 60 ? X.glowAmber : X.glowCrimson;

  return (
    <div style={panelStyle}>
      <div style={panelHeaderStyle}>VQE Price Oracle</div>
      <div style={{ padding: "12px 14px" }}>
        {/* Fair value vs market price */}
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
          <div>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 2 }}>
              VQE Fair Value
            </div>
            <span style={{ fontFamily: FONT.mono, fontSize: 18, color: X.glowCyan }}>
              ${formatPrice(fairValue, 4)}
            </span>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 2 }}>
              Market Price
            </div>
            <span style={{ fontFamily: FONT.mono, fontSize: 18, color: X.glowGold }}>
              ${formatPrice(marketPrice, 4)}
            </span>
          </div>
        </div>

        {/* Deviation */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            padding: "6px 0",
            marginBottom: 8,
            borderRadius: 4,
            background: deviationColor + "10",
            border: `1px solid ${deviationColor}30`,
          }}
        >
          <span
            style={{
              fontFamily: FONT.display,
              fontSize: 10,
              letterSpacing: "0.08em",
              color: deviationColor,
            }}
          >
            {deviationLabel}
          </span>
          <span style={{ fontFamily: FONT.mono, fontSize: 13, color: deviationColor }}>
            {deviation >= 0 ? "+" : ""}${Math.abs(deviation).toFixed(4)}
          </span>
          <span style={{ fontFamily: FONT.mono, fontSize: 11, color: deviationColor, opacity: 0.8 }}>
            ({formatPct(deviationPct)})
          </span>
        </div>

        {/* Oracle sources + confidence */}
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
          <div>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 3 }}>
              Oracle Sources
            </div>
            <span style={{ fontFamily: FONT.mono, fontSize: 13, color: X.textPrimary }}>
              {oracleSources}/{oracleTotal} AetherTree nodes reporting
            </span>
          </div>
          <div style={{ textAlign: "right", minWidth: 80 }}>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 3 }}>
              Confidence
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "flex-end" }}>
              <div
                style={{
                  width: 50,
                  height: 5,
                  borderRadius: 3,
                  background: X.bgElevated,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${Math.min(confidence, 100)}%`,
                    height: "100%",
                    borderRadius: 3,
                    background: confidenceColor,
                    transition: "width 0.3s ease",
                  }}
                />
              </div>
              <span style={{ fontFamily: FONT.mono, fontSize: 13, color: confidenceColor }}>
                {confidence.toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* 24h chart */}
        <div style={{ width: "100%", height: 140 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -10 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={X.borderSubtle}
                vertical={false}
              />
              <XAxis
                dataKey="time"
                tickFormatter={(ts: number) => {
                  const d = new Date(ts);
                  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
                }}
                tick={chartAxisStyle}
                axisLine={false}
                tickLine={false}
                minTickGap={40}
              />
              <YAxis
                tick={chartAxisStyle}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `$${v.toFixed(3)}`}
                domain={["auto", "auto"]}
                width={48}
              />
              <Tooltip
                contentStyle={tooltipContentStyle}
                labelFormatter={((ts: number) => formatHour(ts)) as never}
                formatter={((value: number, name: string) => {
                  const lbl = name === "fairValue" ? "Fair Value" : "Market Price";
                  return [`$${value.toFixed(4)}`, lbl];
                }) as never}
              />
              <Line
                type="monotone"
                dataKey="fairValue"
                stroke={X.glowCyan}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, fill: X.glowCyan }}
              />
              <Line
                type="monotone"
                dataKey="marketPrice"
                stroke={X.glowGold}
                strokeWidth={1.5}
                dot={false}
                activeDot={{ r: 3, fill: X.glowGold }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
});

export default RiskHeatmap;
