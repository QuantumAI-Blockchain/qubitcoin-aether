// ─── QBC EXCHANGE — Quantum Market Intelligence Panel ─────────────────────────
"use client";

import React, { memo, useMemo } from "react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { useSusySignal, useVqeOracle, useValidators, useQevi } from "./hooks";
import {
  X,
  FONT,
  formatPrice,
  formatPct,
  panelStyle,
  panelHeaderStyle,
  StatusBadge,
} from "./shared";

// ─── HELPERS ──────────────────────────────────────────────────────────────────

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

function consensusLabel(onlineCount: number, total: number): { label: string; color: string } {
  const ratio = onlineCount / total;
  if (ratio >= 0.9) return { label: "STRONG", color: X.glowEmerald };
  if (ratio >= 0.7) return { label: "MODERATE", color: X.glowAmber };
  return { label: "WEAK", color: X.glowCrimson };
}

function exchangeImpact(onlineCount: number, total: number): { label: string; color: string } {
  const ratio = onlineCount / total;
  if (ratio >= 0.9) return { label: "LOW RISK", color: X.glowEmerald };
  if (ratio >= 0.7) return { label: "MEDIUM RISK", color: X.glowAmber };
  return { label: "HIGH RISK", color: X.glowCrimson };
}

const validatorStatusColor: Record<string, string> = {
  online: X.glowEmerald,
  offline: X.glowCrimson,
  degraded: X.glowAmber,
};

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

// ─── SECTION 1: SUSY ALIGNMENT SIGNAL ─────────────────────────────────────────

const SusyAlignmentSignal = memo(function SusyAlignmentSignal() {
  const { data: susy } = useSusySignal();

  const score = susy?.score ?? 0;
  const label = susy ? signalLabel(score) : "---";
  const color = signalColor(score);
  const interpretation = susy?.interpretation ?? "Loading SUSY alignment data...";

  const chartData = useMemo(() => {
    if (!susy?.history) return [];
    // Downsample: take every 6th point (hourly data over 7 days = 168 points)
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

// ─── SECTION 2: VQE PRICE ORACLE ──────────────────────────────────────────────

const VqePriceOracle = memo(function VqePriceOracle() {
  const { data: oracle } = useVqeOracle();

  const fairValue = oracle?.fairValue ?? 0;
  const marketPrice = oracle?.marketPrice ?? 0;
  const deviation = oracle?.deviation ?? 0;
  const deviationPct = oracle?.deviationPct ?? 0;
  const oracleSources = oracle?.oracleSources ?? 0;
  const oracleTotal = oracle?.oracleTotal ?? 0;
  const confidence = oracle?.confidence ?? 0;

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

// ─── SECTION 3: AETHERTREE VALIDATOR CONSENSUS ────────────────────────────────

const ValidatorConsensus = memo(function ValidatorConsensus() {
  const { data: validators } = useValidators();

  const validatorList = validators ?? [];
  const total = validatorList.length || 11;
  const onlineCount = validatorList.filter((v) => v.status === "online").length;
  const degradedCount = validatorList.filter((v) => v.status === "degraded").length;
  const offlineCount = validatorList.filter((v) => v.status === "offline").length;

  const consensus = consensusLabel(onlineCount, total);
  const impact = exchangeImpact(onlineCount, total);

  const finalityStatus = useMemo(() => {
    if (onlineCount >= Math.ceil(total * 2 / 3)) return { label: "FINALIZED", color: X.glowEmerald };
    if (onlineCount >= Math.ceil(total / 2)) return { label: "PENDING", color: X.glowAmber };
    return { label: "AT RISK", color: X.glowCrimson };
  }, [onlineCount, total]);

  // Arrange 11 validators in a visually interesting grid: 4-3-4 pattern
  const rows = useMemo(() => {
    const items = validatorList.length > 0 ? validatorList : Array.from({ length: 11 }, (_, i) => ({
      name: `Node ${i}`,
      status: "online" as const,
      lastSeen: Date.now(),
    }));
    return [items.slice(0, 4), items.slice(4, 7), items.slice(7, 11)];
  }, [validatorList]);

  return (
    <div style={panelStyle}>
      <div style={panelHeaderStyle}>AetherTree Validator Consensus</div>
      <div style={{ padding: "12px 14px" }}>
        {/* Stats row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 8,
            marginBottom: 12,
          }}
        >
          <div>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 2 }}>
              Active Validators
            </div>
            <span style={{ fontFamily: FONT.mono, fontSize: 18, color: X.textPrimary }}>
              {onlineCount}
              <span style={{ fontSize: 13, color: X.textSecondary }}>/{total}</span>
            </span>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 2 }}>
              Consensus Health
            </div>
            <span
              style={{
                fontFamily: FONT.display,
                fontSize: 13,
                letterSpacing: "0.06em",
                color: consensus.color,
              }}
            >
              {consensus.label}
            </span>
          </div>
          <div>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 2 }}>
              Block Finality
            </div>
            <span
              style={{
                fontFamily: FONT.display,
                fontSize: 11,
                letterSpacing: "0.06em",
                padding: "2px 6px",
                borderRadius: 3,
                background: finalityStatus.color + "18",
                color: finalityStatus.color,
                border: `1px solid ${finalityStatus.color}30`,
              }}
            >
              {finalityStatus.label}
            </span>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 2 }}>
              Exchange Impact
            </div>
            <span
              style={{
                fontFamily: FONT.display,
                fontSize: 11,
                letterSpacing: "0.06em",
                padding: "2px 6px",
                borderRadius: 3,
                background: impact.color + "18",
                color: impact.color,
                border: `1px solid ${impact.color}30`,
              }}
            >
              {impact.label}
            </span>
          </div>
        </div>

        {/* Validator grid: 4-3-4 */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 6,
            marginBottom: 10,
          }}
        >
          {rows.map((row, ri) => (
            <div key={ri} style={{ display: "flex", gap: 6, justifyContent: "center" }}>
              {row.map((v) => {
                const c = validatorStatusColor[v.status] ?? X.textSecondary;
                return (
                  <div
                    key={v.name}
                    title={`${v.name}: ${v.status}`}
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: 4,
                      background: c + "20",
                      border: `1px solid ${c}50`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      cursor: "default",
                      position: "relative",
                    }}
                  >
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background: c,
                        boxShadow: v.status === "online" ? `0 0 6px ${c}80` : "none",
                      }}
                    />
                    <span
                      style={{
                        position: "absolute",
                        bottom: -12,
                        fontFamily: FONT.mono,
                        fontSize: 7,
                        color: X.textSecondary,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {v.name.slice(0, 3).toUpperCase()}
                    </span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Legend */}
        <div
          style={{
            display: "flex",
            gap: 14,
            justifyContent: "center",
            marginTop: 16,
            paddingTop: 8,
            borderTop: `1px solid ${X.borderSubtle}`,
          }}
        >
          {[
            { label: `Online (${onlineCount})`, color: X.glowEmerald },
            { label: `Degraded (${degradedCount})`, color: X.glowAmber },
            { label: `Offline (${offlineCount})`, color: X.glowCrimson },
          ].map((item) => (
            <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: item.color }} />
              <span style={{ fontFamily: FONT.mono, fontSize: 9, color: X.textSecondary }}>
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
});

// ─── SECTION 4: QUANTUM ENTROPY VOLATILITY INDEX (QEVI) ──────────────────────

const QuantumEntropyVolatility = memo(function QuantumEntropyVolatility() {
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

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────

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
      <SusyAlignmentSignal />
      <VqePriceOracle />
      <ValidatorConsensus />
      <QuantumEntropyVolatility />
    </div>
  );
});

export default QuantumIntelligence;
