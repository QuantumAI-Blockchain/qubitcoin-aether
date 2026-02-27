// ─── QBC EXCHANGE — Quantum Entropy Volatility Index (QEVI) Panel ────────────
// Split from QuantumIntelligence.tsx for lazy loading
"use client";

import React, { memo, useMemo } from "react";
import {
  BarChart,
  Bar,
  Cell,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { useQevi } from "./hooks";
import {
  X,
  FONT,
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

function regimeColor(score: number): string {
  if (score <= 30) return X.glowEmerald;
  if (score <= 60) return X.glowAmber;
  if (score <= 80) return "#f97316"; // orange
  return X.glowCrimson;
}

function regimeLabel(score: number): string {
  if (score <= 30) return "LOW VOLATILITY";
  if (score <= 60) return "MODERATE";
  if (score <= 80) return "ELEVATED";
  return "EXTREME";
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

const SentimentGauge = memo(function SentimentGauge() {
  const { data: qevi } = useQevi();

  const entropy = qevi?.entropy ?? 0;
  const score = qevi?.score ?? 0;
  const regime = regimeLabel(score);
  const color = regimeColor(score);

  const interpretation = useMemo(() => {
    if (score <= 30)
      return "Quantum entropy levels indicate low market volatility. Favorable conditions for mean-reversion strategies and tight spreads.";
    if (score <= 60)
      return "Moderate entropy detected. Standard volatility regime — normal trading conditions with typical spread widths.";
    if (score <= 80)
      return "Elevated quantum entropy suggests increasing volatility. Consider reducing position sizes and widening stop-losses.";
    return "Extreme entropy readings signal high volatility. Exercise caution — rapid price moves likely. Consider hedging open positions.";
  }, [score]);

  const chartData = useMemo(() => {
    if (!qevi?.history) return [];
    return qevi.history.filter((_, i) => i % 6 === 0 || i === qevi.history.length - 1);
  }, [qevi?.history]);

  // Color bars by regime
  const coloredChartData = useMemo(() => {
    return chartData.map((d) => ({
      ...d,
      fill: regimeColor(d.qevi),
    }));
  }, [chartData]);

  return (
    <div style={panelStyle}>
      <div style={panelHeaderStyle}>Quantum Entropy Volatility Index (QEVI)</div>
      <div style={{ padding: "12px 14px" }}>
        {/* Entropy + QEVI score */}
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <div>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 2 }}>
              Quantum Entropy
            </div>
            <span style={{ fontFamily: FONT.mono, fontSize: 15, color: X.textPrimary }}>
              {entropy.toExponential(3)}
            </span>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 2 }}>
              QEVI Score
            </div>
            <span style={{ fontFamily: FONT.mono, fontSize: 22, color }}>
              {score.toFixed(1)}
            </span>
            <span style={{ fontFamily: FONT.mono, fontSize: 13, color: X.textSecondary }}>/100</span>
          </div>
        </div>

        {/* Regime badge */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            padding: "6px 0",
            marginBottom: 8,
            borderRadius: 4,
            background: color + "10",
            border: `1px solid ${color}30`,
          }}
        >
          <span
            style={{
              fontFamily: FONT.display,
              fontSize: 11,
              letterSpacing: "0.08em",
              color,
            }}
          >
            {regime}
          </span>
        </div>

        {/* Interpretation */}
        <p
          style={{
            fontFamily: FONT.body,
            fontSize: 11,
            color: X.textSecondary,
            margin: "0 0 12px",
            lineHeight: 1.5,
          }}
        >
          {interpretation}
        </p>

        {/* 7-day chart: bars + realized vol line */}
        <div style={{ width: "100%", height: 140 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={coloredChartData} margin={{ top: 4, right: 4, bottom: 0, left: -10 }}>
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
                yAxisId="qevi"
                domain={[0, 100]}
                tick={chartAxisStyle}
                axisLine={false}
                tickLine={false}
                width={30}
              />
              <YAxis
                yAxisId="vol"
                orientation="right"
                tick={chartAxisStyle}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `${v.toFixed(0)}%`}
                width={36}
              />
              <Tooltip
                contentStyle={tooltipContentStyle}
                labelFormatter={((ts: number) => formatHour(ts)) as never}
                formatter={((value: number, name: string) => {
                  if (name === "qevi") return [value.toFixed(1), "QEVI"];
                  return [`${value.toFixed(1)}%`, "Realized Vol"];
                }) as never}
              />
              <ReferenceLine
                yAxisId="qevi"
                y={30}
                stroke={X.glowEmerald}
                strokeDasharray="4 4"
                strokeOpacity={0.25}
              />
              <ReferenceLine
                yAxisId="qevi"
                y={60}
                stroke={X.glowAmber}
                strokeDasharray="4 4"
                strokeOpacity={0.25}
              />
              <ReferenceLine
                yAxisId="qevi"
                y={80}
                stroke={X.glowCrimson}
                strokeDasharray="4 4"
                strokeOpacity={0.25}
              />
              <Bar
                yAxisId="qevi"
                dataKey="qevi"
                radius={[2, 2, 0, 0]}
                maxBarSize={8}
                isAnimationActive={false}
              >
                {coloredChartData.map((entry, index) => (
                  <Cell key={index} fill={entry.fill + "90"} />
                ))}
              </Bar>
              <Line
                yAxisId="vol"
                type="monotone"
                dataKey="realizedVol"
                stroke={X.glowViolet}
                strokeWidth={1.5}
                dot={false}
                activeDot={{ r: 3, fill: X.glowViolet }}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
});

export default SentimentGauge;
