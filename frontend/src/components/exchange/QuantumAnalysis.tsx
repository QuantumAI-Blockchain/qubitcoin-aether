// ─── QBC EXCHANGE — SUSY Alignment Signal Panel ─────────────────────────────
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
  ReferenceLine,
} from "recharts";
import { useSusySignal, useAetherPhi } from "./hooks";
import {
  X,
  FONT,
  formatPct,
  panelStyle,
  panelHeaderStyle,
} from "./shared";

function formatHour(ts: number): string {
  const d = new Date(ts);
  return `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:00`;
}

function formatDayShort(ts: number): string {
  const d = new Date(ts);
  return `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
}

function signalColor(score: number): string {
  if (score >= 0.95) return X.glowEmerald;
  if (score >= 0.80) return X.glowCyan;
  if (score >= 0.65) return X.glowAmber;
  return X.glowCrimson;
}

function signalLabel(score: number): string {
  if (score >= 0.95) return "STRONG BULLISH";
  if (score >= 0.80) return "BULLISH";
  if (score >= 0.65) return "NEUTRAL";
  return "BEARISH";
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

const QuantumAnalysis = memo(function QuantumAnalysis() {
  const { data: susy } = useSusySignal();
  const { data: aetherPhi } = useAetherPhi();

  // Blend real Aether Phi data into the score when available
  const rawScore = susy?.score ?? 0;
  const score = aetherPhi
    ? Math.min(1, Math.max(0, aetherPhi.phi / (aetherPhi.threshold || 3.0)))
    : rawScore;
  const label = signalLabel(score);
  const color = signalColor(score);

  const interpretation = aetherPhi
    ? aetherPhi.above_threshold
      ? `Aether Tree Phi is ${aetherPhi.phi.toFixed(2)} (above threshold ${aetherPhi.threshold.toFixed(1)}). ` +
        `High consciousness integration correlates with reduced volatility and upward price momentum for QBC. ` +
        `Knowledge graph: ${aetherPhi.knowledge_nodes.toLocaleString()} nodes, ${aetherPhi.knowledge_edges.toLocaleString()} edges.`
      : `Aether Tree Phi is ${aetherPhi.phi.toFixed(2)} (threshold: ${aetherPhi.threshold.toFixed(1)}). ` +
        `Consciousness emergence is progressing. ` +
        `Knowledge graph: ${aetherPhi.knowledge_nodes.toLocaleString()} nodes, ${aetherPhi.knowledge_edges.toLocaleString()} edges.`
    : susy?.interpretation ?? "Connecting to Aether Tree...";

  const chartData = useMemo(() => {
    if (!susy?.history) return [];
    return susy.history.filter((_, i) => i % 6 === 0 || i === susy.history.length - 1);
  }, [susy?.history]);

  return (
    <div style={panelStyle}>
      <div style={panelHeaderStyle}>SUSY Alignment Signal</div>
      <div style={{ padding: "12px 14px" }}>
        {/* Score bar */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <div style={{ flex: 1 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: 4,
              }}
            >
              <span style={{ fontFamily: FONT.mono, fontSize: 22, color }}>
                {(score * 100).toFixed(1)}%
              </span>
              <span
                style={{
                  fontFamily: FONT.display,
                  fontSize: 11,
                  letterSpacing: "0.08em",
                  color,
                  alignSelf: "center",
                  padding: "2px 8px",
                  borderRadius: 4,
                  background: color + "18",
                  border: `1px solid ${color}40`,
                }}
              >
                {label}
              </span>
            </div>
            <div
              style={{
                height: 6,
                borderRadius: 3,
                background: X.bgElevated,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${score * 100}%`,
                  height: "100%",
                  borderRadius: 3,
                  background: `linear-gradient(90deg, ${X.glowCrimson}, ${X.glowAmber}, ${X.glowCyan}, ${X.glowEmerald})`,
                  transition: "width 0.4s ease",
                }}
              />
            </div>
          </div>
        </div>

        {/* Interpretation */}
        <p
          style={{
            fontFamily: FONT.body,
            fontSize: 11,
            color: X.textSecondary,
            margin: "8px 0 12px",
            lineHeight: 1.5,
          }}
        >
          {interpretation}
        </p>

        {/* 7-day chart */}
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
                tickFormatter={formatDayShort}
                tick={chartAxisStyle}
                axisLine={false}
                tickLine={false}
                minTickGap={40}
              />
              <YAxis
                yAxisId="score"
                domain={[0.5, 1]}
                tick={chartAxisStyle}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                width={40}
              />
              <YAxis
                yAxisId="price"
                orientation="right"
                tick={chartAxisStyle}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `$${v.toFixed(3)}`}
                width={50}
              />
              <Tooltip
                contentStyle={tooltipContentStyle}
                labelFormatter={((ts: number) => formatHour(ts)) as never}
                formatter={((value: number, name: string) => {
                  if (name === "score") return [`${(value * 100).toFixed(1)}%`, "SUSY Score"];
                  return [`$${value.toFixed(4)}`, "QBC Price"];
                }) as never}
              />
              <ReferenceLine
                yAxisId="score"
                y={0.65}
                stroke={X.glowAmber}
                strokeDasharray="4 4"
                strokeOpacity={0.3}
              />
              <ReferenceLine
                yAxisId="score"
                y={0.80}
                stroke={X.glowCyan}
                strokeDasharray="4 4"
                strokeOpacity={0.3}
              />
              <ReferenceLine
                yAxisId="score"
                y={0.95}
                stroke={X.glowEmerald}
                strokeDasharray="4 4"
                strokeOpacity={0.3}
              />
              <Line
                yAxisId="score"
                type="monotone"
                dataKey="score"
                stroke={X.glowCyan}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, fill: X.glowCyan }}
              />
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="price"
                stroke={X.glowGold}
                strokeWidth={1.5}
                dot={false}
                activeDot={{ r: 3, fill: X.glowGold }}
                strokeDasharray="4 2"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Alignment zones legend */}
        <div
          style={{
            display: "flex",
            gap: 12,
            marginTop: 8,
            flexWrap: "wrap",
          }}
        >
          {[
            { label: "Strong Bullish", range: "95-100%", color: X.glowEmerald },
            { label: "Bullish", range: "80-95%", color: X.glowCyan },
            { label: "Neutral", range: "65-80%", color: X.glowAmber },
            { label: "Bearish", range: "<65%", color: X.glowCrimson },
          ].map((z) => (
            <div key={z.label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 2,
                  background: z.color,
                  opacity: 0.8,
                }}
              />
              <span
                style={{
                  fontFamily: FONT.mono,
                  fontSize: 9,
                  color: X.textSecondary,
                }}
              >
                {z.label} ({z.range})
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
});

export default QuantumAnalysis;
