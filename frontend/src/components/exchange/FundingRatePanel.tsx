// ─── QBC EXCHANGE — Funding Rate Panel ──────────────────────────────────────
// Current / annualized / predicted rates, countdown, payment history bar chart,
// cross-market comparison table. Recharts BarChart, dark theme.
"use client";

import React, { memo, useMemo, useState, useEffect, useRef } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { useFunding, useMarkets } from "./hooks";
import { useExchangeStore } from "./store";
import {
  X,
  FONT,
  formatFundingRate,
  formatPct,
  formatUsd,
  panelStyle,
  panelHeaderStyle,
} from "./shared";
import type { MarketId, FundingPayment, Market } from "./types";

// ─── CONSTANTS ─────────────────────────────────────────────────────────────

const PERP_MARKET_IDS: MarketId[] = [
  "QBC_PERP",
  "ETH_PERP",
  "BNB_PERP",
  "SOL_PERP",
  "BTC_PERP",
];

const ANNUALIZE_FACTOR = 8760; // 1-hour intervals, 8760 hours/year
const DEMO_POSITION_SIZE = 10000; // units for estimated payment display

// ─── STYLES ────────────────────────────────────────────────────────────────

const sectionStyle: React.CSSProperties = {
  padding: "12px 14px",
  borderBottom: `1px solid ${X.borderSubtle}`,
};

const labelStyle: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 9,
  letterSpacing: "0.1em",
  color: X.textSecondary,
  textTransform: "uppercase" as const,
};

const valueStyle: React.CSSProperties = {
  fontFamily: FONT.mono,
  fontSize: 14,
  color: X.textPrimary,
};

const statRow: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  padding: "4px 0",
};

const tHeaderStyle: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 9,
  letterSpacing: "0.1em",
  color: X.textSecondary,
  textTransform: "uppercase" as const,
  textAlign: "right" as const,
  padding: "6px 8px",
  borderBottom: `1px solid ${X.borderSubtle}`,
};

const tCellStyle: React.CSSProperties = {
  fontFamily: FONT.mono,
  fontSize: 11,
  color: X.textPrimary,
  textAlign: "right" as const,
  padding: "6px 8px",
  borderBottom: `1px solid ${X.borderSubtle}08`,
};

// ─── COUNTDOWN HOOK ────────────────────────────────────────────────────────

function useCountdown(targetTs: number | undefined): string {
  const [str, setStr] = useState("--:--:--");
  useEffect(() => {
    if (!targetTs) return;
    const tick = () => {
      const diff = Math.max(0, Math.floor((targetTs - Date.now()) / 1000));
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      const s = diff % 60;
      setStr(
        `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`,
      );
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [targetTs]);
  return str;
}

// ─── BAR CHART DATA ────────────────────────────────────────────────────────

interface BarDatum {
  label: string;
  rate: number;
  fill: string;
  timestamp: number;
}

function buildBarData(payments: FundingPayment[]): BarDatum[] {
  // payments[0] is most recent; reverse so chart reads left-to-right chronologically
  const sorted = [...payments].sort((a, b) => a.timestamp - b.timestamp);
  return sorted.map((p) => {
    const rate = p.fundingRate * 100; // as percentage
    return {
      label: new Date(p.timestamp).toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }),
      rate,
      fill: rate >= 0 ? X.glowEmerald : X.glowCrimson,
      timestamp: p.timestamp,
    };
  });
}

// ─── CUSTOM TOOLTIP ────────────────────────────────────────────────────────

interface TooltipPayloadItem {
  payload?: BarDatum;
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  const color = d.rate >= 0 ? X.glowEmerald : X.glowCrimson;
  return (
    <div
      style={{
        background: X.bgElevated,
        border: `1px solid ${X.borderSubtle}`,
        borderRadius: 6,
        padding: "8px 12px",
        fontFamily: FONT.mono,
        fontSize: 11,
        boxShadow: `0 4px 16px ${X.bgBase}cc`,
      }}
    >
      <div style={{ color: X.textSecondary, fontSize: 9, marginBottom: 4 }}>
        {new Date(d.timestamp).toLocaleString("en-US", {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        })}
      </div>
      <div style={{ color, fontWeight: 600 }}>
        {d.rate >= 0 ? "+" : ""}
        {d.rate.toFixed(4)}%
      </div>
    </div>
  );
}

// ─── MAIN COMPONENT ────────────────────────────────────────────────────────

const FundingRatePanel = memo(function FundingRatePanel() {
  const activeMarket = useExchangeStore((s) => s.activeMarket);
  const { data: payments } = useFunding(activeMarket);
  const { data: allMarkets } = useMarkets();

  // Current market data for header stats
  const currentMarket: Market | undefined = useMemo(() => {
    if (!allMarkets) return undefined;
    return allMarkets.find((m) => m.id === activeMarket);
  }, [allMarkets, activeMarket]);

  const countdown = useCountdown(currentMarket?.nextFundingTs);

  // Derived stats
  const currentRate = currentMarket?.fundingRate ?? 0;
  const annualized = currentRate * ANNUALIZE_FACTOR;
  const favours: "LONG" | "SHORT" = currentRate >= 0 ? "SHORT" : "LONG";
  const favourColor = favours === "SHORT" ? X.glowCrimson : X.glowEmerald;

  // Estimated payment for a demo position
  const estimatedPayment = useMemo(() => {
    if (!currentMarket) return 0;
    return -(DEMO_POSITION_SIZE * currentMarket.markPrice * currentRate);
  }, [currentMarket, currentRate]);

  // Predicted next rate: weighted average of last 3 rates with decay
  const predictedNextRate = useMemo(() => {
    if (!payments || payments.length < 3) return currentRate;
    const recent = [...payments].sort((a, b) => b.timestamp - a.timestamp).slice(0, 3);
    const weights = [0.5, 0.3, 0.2];
    let sum = 0;
    for (let i = 0; i < recent.length; i++) {
      sum += recent[i].fundingRate * weights[i];
    }
    return sum;
  }, [payments, currentRate]);

  // Bar chart data
  const barData = useMemo(() => {
    if (!payments) return [];
    return buildBarData(payments);
  }, [payments]);

  // Cross-market comparison
  const perpMarkets = useMemo(() => {
    if (!allMarkets) return [];
    return allMarkets.filter(
      (m) => m.type === "perp" && PERP_MARKET_IDS.includes(m.id),
    );
  }, [allMarkets]);

  const isPerp = currentMarket?.type === "perp";

  if (!isPerp) {
    return (
      <div
        style={{
          ...panelStyle,
          display: "flex",
          flexDirection: "column",
          height: "100%",
        }}
      >
        <div style={panelHeaderStyle}>FUNDING RATE</div>
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: FONT.mono,
            fontSize: 12,
            color: X.textSecondary,
            padding: 20,
            textAlign: "center",
          }}
        >
          Funding rates are only available for perpetual markets.
          <br />
          Switch to a PERP market to view funding data.
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        ...panelStyle,
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div style={panelHeaderStyle}>FUNDING RATE</div>

      {/* Current Stats */}
      <div style={sectionStyle}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          {/* Current Rate */}
          <div style={{ flex: "1 1 120px" }}>
            <div style={labelStyle}>Current Rate</div>
            <div
              style={{
                ...valueStyle,
                fontSize: 20,
                color: currentRate >= 0 ? X.glowEmerald : X.glowCrimson,
                fontWeight: 700,
              }}
            >
              {formatFundingRate(currentRate * 100)}
            </div>
          </div>

          {/* Annualized */}
          <div style={{ flex: "1 1 120px" }}>
            <div style={labelStyle}>Annualized</div>
            <div
              style={{
                ...valueStyle,
                color: annualized >= 0 ? X.glowEmerald : X.glowCrimson,
              }}
            >
              {formatPct(annualized * 100)}
            </div>
          </div>

          {/* Favours */}
          <div style={{ flex: "1 1 80px" }}>
            <div style={labelStyle}>Favours</div>
            <div
              style={{
                ...valueStyle,
                color: favourColor,
                fontFamily: FONT.display,
                fontSize: 13,
                letterSpacing: "0.06em",
              }}
            >
              {favours}
            </div>
          </div>
        </div>
      </div>

      {/* Countdown + Payment + Predicted */}
      <div style={sectionStyle}>
        <div style={statRow}>
          <span style={labelStyle}>Next Payment</span>
          <span
            style={{
              fontFamily: FONT.mono,
              fontSize: 16,
              color: X.glowCyan,
              letterSpacing: "0.04em",
            }}
          >
            {countdown}
          </span>
        </div>
        <div style={statRow}>
          <span style={labelStyle}>
            Est. Payment ({formatUsd(DEMO_POSITION_SIZE)} pos.)
          </span>
          <span
            style={{
              fontFamily: FONT.mono,
              fontSize: 12,
              color:
                estimatedPayment >= 0 ? X.glowEmerald : X.glowCrimson,
            }}
          >
            {estimatedPayment >= 0 ? "+" : ""}
            {formatUsd(estimatedPayment)}
          </span>
        </div>
        <div style={statRow}>
          <span style={labelStyle}>Predicted Next Rate</span>
          <span
            style={{
              fontFamily: FONT.mono,
              fontSize: 12,
              color:
                predictedNextRate >= 0 ? X.glowEmerald : X.glowCrimson,
            }}
          >
            {formatFundingRate(predictedNextRate * 100)}
          </span>
        </div>
      </div>

      {/* Funding History Bar Chart */}
      <div style={{ ...sectionStyle, flex: "1 1 180px", minHeight: 180 }}>
        <div
          style={{
            ...labelStyle,
            marginBottom: 8,
          }}
        >
          Funding Rate History (48h)
        </div>
        {barData.length === 0 ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: 140,
              fontFamily: FONT.mono,
              fontSize: 12,
              color: X.textSecondary,
            }}
          >
            No funding data available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart
              data={barData}
              margin={{ top: 4, right: 4, bottom: 0, left: -20 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={X.borderSubtle}
                vertical={false}
              />
              <XAxis
                dataKey="label"
                tick={{
                  fill: X.textSecondary,
                  fontFamily: FONT.mono,
                  fontSize: 9,
                }}
                axisLine={{ stroke: X.borderSubtle }}
                tickLine={false}
                interval="preserveStartEnd"
                minTickGap={40}
              />
              <YAxis
                tick={{
                  fill: X.textSecondary,
                  fontFamily: FONT.mono,
                  fontSize: 9,
                }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => v.toFixed(3) + "%"}
                domain={["auto", "auto"]}
              />
              <Tooltip
                content={<ChartTooltip />}
                cursor={{ fill: X.borderSubtle + "40" }}
              />
              <ReferenceLine
                y={0}
                stroke={X.textSecondary}
                strokeWidth={0.5}
                strokeDasharray="4 2"
              />
              <Bar
                dataKey="rate"
                radius={[2, 2, 0, 0]}
                maxBarSize={8}
                isAnimationActive={false}
              >
                {barData.map((entry, index) => (
                  <rect
                    key={`bar-${index}`}
                    fill={entry.fill}
                    fillOpacity={0.85}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Cross-Market Comparison */}
      <div style={{ padding: "8px 0", overflowY: "auto" }} className="exchange-scroll">
        <div
          style={{
            ...labelStyle,
            padding: "4px 14px 8px",
          }}
        >
          Cross-Market Comparison
        </div>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontFamily: FONT.mono,
            fontSize: 11,
          }}
        >
          <thead>
            <tr>
              <th
                style={{
                  ...tHeaderStyle,
                  textAlign: "left" as const,
                  paddingLeft: 14,
                }}
              >
                Market
              </th>
              <th style={tHeaderStyle}>Rate / 1H</th>
              <th style={tHeaderStyle}>Annualised</th>
              <th style={{ ...tHeaderStyle, paddingRight: 14 }}>Favours</th>
            </tr>
          </thead>
          <tbody>
            {perpMarkets.map((m) => {
              const rate = m.fundingRate;
              const ann = rate * ANNUALIZE_FACTOR;
              const fav: "LONG" | "SHORT" = rate >= 0 ? "SHORT" : "LONG";
              const isActive = m.id === activeMarket;
              const rateColor =
                rate >= 0 ? X.glowEmerald : X.glowCrimson;
              return (
                <tr
                  key={m.id}
                  style={{
                    background: isActive ? X.bgElevated : "transparent",
                  }}
                >
                  <td
                    style={{
                      ...tCellStyle,
                      textAlign: "left" as const,
                      paddingLeft: 14,
                      color: isActive ? X.glowCyan : X.textPrimary,
                      fontFamily: FONT.display,
                      fontSize: 10,
                      letterSpacing: "0.04em",
                    }}
                  >
                    {m.displayName}
                  </td>
                  <td style={{ ...tCellStyle, color: rateColor }}>
                    {formatFundingRate(rate * 100)}
                  </td>
                  <td
                    style={{
                      ...tCellStyle,
                      color:
                        ann >= 0 ? X.glowEmerald : X.glowCrimson,
                    }}
                  >
                    {formatPct(ann * 100)}
                  </td>
                  <td
                    style={{
                      ...tCellStyle,
                      paddingRight: 14,
                      color:
                        fav === "SHORT"
                          ? X.glowCrimson
                          : X.glowEmerald,
                      fontFamily: FONT.display,
                      fontSize: 9,
                      letterSpacing: "0.06em",
                    }}
                  >
                    {fav}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
});

export default FundingRatePanel;
