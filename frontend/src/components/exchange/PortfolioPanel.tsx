// ─── QBC EXCHANGE — Portfolio Panel (Balances + P&L) ──────────────────────────
"use client";

import React, { memo, useMemo, useState, useCallback } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { useBalances, usePositions, useEquityHistory } from "./hooks";
import { useExchangeStore } from "./store";
import {
  X,
  FONT,
  formatUsd,
  formatSize,
  formatPct,
  PnlDisplay,
  panelStyle,
  panelHeaderStyle,
  TabBar,
} from "./shared";
import type { Balance } from "./types";

// ─── CONSTANTS ──────────────────────────────────────────────────────────────

const EQUITY_GRADIENT_ID = "portfolioEquityGradient";

const cardStyle: React.CSSProperties = {
  flex: 1,
  background: X.bgElevated,
  border: `1px solid ${X.borderSubtle}`,
  borderRadius: 6,
  padding: "14px 16px",
  display: "flex",
  flexDirection: "column",
  gap: 4,
};

const cardLabelStyle: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 9,
  letterSpacing: "0.1em",
  color: X.textSecondary,
  textTransform: "uppercase" as const,
};

const cardValueStyle: React.CSSProperties = {
  fontFamily: FONT.mono,
  fontSize: 20,
  color: X.textPrimary,
  lineHeight: 1.2,
};

const cardSubStyle: React.CSSProperties = {
  fontFamily: FONT.body,
  fontSize: 10,
  color: X.textSecondary,
};

const tableHeaderStyle: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 9,
  letterSpacing: "0.08em",
  color: X.textSecondary,
  textTransform: "uppercase" as const,
  padding: "8px 12px",
  textAlign: "left" as const,
};

const tableCellStyle: React.CSSProperties = {
  fontFamily: FONT.mono,
  fontSize: 12,
  color: X.textPrimary,
  padding: "7px 12px",
  verticalAlign: "middle" as const,
};

const actionBtnBase: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 9,
  letterSpacing: "0.06em",
  padding: "3px 8px",
  borderRadius: 3,
  border: "none",
  cursor: "pointer",
  textTransform: "uppercase" as const,
  transition: "opacity 0.15s",
};

// ─── BALANCE ROW ────────────────────────────────────────────────────────────

const BalanceRow = memo(function BalanceRow({
  balance,
  onDeposit,
  onWithdraw,
  onTrade,
}: {
  balance: Balance;
  onDeposit: (asset: string) => void;
  onWithdraw: (asset: string) => void;
  onTrade: (asset: string) => void;
}) {
  return (
    <tr
      style={{
        borderBottom: `1px solid ${X.borderSubtle}10`,
      }}
    >
      <td style={tableCellStyle}>
        <span style={{ fontFamily: FONT.body, fontWeight: 600, color: X.textPrimary }}>
          {balance.asset}
        </span>
      </td>
      <td style={{ ...tableCellStyle, textAlign: "right" }}>
        {formatSize(balance.total, balance.decimals > 4 ? 4 : balance.decimals)}
      </td>
      <td style={{ ...tableCellStyle, textAlign: "right" }}>
        {formatUsd(balance.usdValue)}
      </td>
      <td style={{ ...tableCellStyle, textAlign: "right", color: X.textSecondary }}>
        {formatSize(balance.inOrders, balance.decimals > 4 ? 4 : balance.decimals)}
      </td>
      <td style={{ ...tableCellStyle, textAlign: "right" }}>
        <span style={{ color: balance.available > 0 ? X.textPrimary : X.textSecondary }}>
          {formatSize(balance.available, balance.decimals > 4 ? 4 : balance.decimals)}
        </span>
      </td>
      <td style={{ ...tableCellStyle, textAlign: "right" }}>
        <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
          <button
            onClick={() => onDeposit(balance.asset)}
            style={{
              ...actionBtnBase,
              background: X.glowCyan + "18",
              color: X.glowCyan,
            }}
          >
            Deposit
          </button>
          <button
            onClick={() => onWithdraw(balance.asset)}
            style={{
              ...actionBtnBase,
              background: X.glowAmber + "18",
              color: X.glowAmber,
            }}
          >
            Withdraw
          </button>
          <button
            onClick={() => onTrade(balance.asset)}
            style={{
              ...actionBtnBase,
              background: X.glowEmerald + "18",
              color: X.glowEmerald,
            }}
          >
            Trade
          </button>
        </div>
      </td>
    </tr>
  );
});

// ─── CUSTOM TOOLTIP ─────────────────────────────────────────────────────────

function EquityTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: { timestamp: number; totalEquity: number } }[];
}) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload;
  const date = new Date(d.timestamp);
  return (
    <div
      style={{
        background: X.bgElevated,
        border: `1px solid ${X.borderSubtle}`,
        borderRadius: 4,
        padding: "8px 12px",
        fontFamily: FONT.mono,
        fontSize: 11,
      }}
    >
      <div style={{ color: X.textSecondary, fontSize: 9, marginBottom: 4 }}>
        {date.toLocaleDateString("en-US", { month: "short", day: "numeric" })}{" "}
        {date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}
      </div>
      <div style={{ color: X.glowCyan }}>
        {formatUsd(d.totalEquity)}
      </div>
    </div>
  );
}

// ─── BALANCES TAB ───────────────────────────────────────────────────────────

const BalancesTab = memo(function BalancesTab() {
  const { data: balances } = useBalances();
  const setDepositAsset = useExchangeStore((s) => s.setDepositAsset);
  const setDepositModalOpen = useExchangeStore((s) => s.setDepositModalOpen);
  const setWithdrawAsset = useExchangeStore((s) => s.setWithdrawAsset);
  const setWithdrawModalOpen = useExchangeStore((s) => s.setWithdrawModalOpen);
  const setActiveMarket = useExchangeStore((s) => s.setActiveMarket);

  const handleDeposit = useCallback(
    (asset: string) => {
      setDepositAsset(asset);
      setDepositModalOpen(true);
    },
    [setDepositAsset, setDepositModalOpen],
  );

  const handleWithdraw = useCallback(
    (asset: string) => {
      setWithdrawAsset(asset);
      setWithdrawModalOpen(true);
    },
    [setWithdrawAsset, setWithdrawModalOpen],
  );

  const handleTrade = useCallback(
    (asset: string) => {
      const spotMap: Record<string, string> = {
        QBC: "QBC_QUSD",
        WETH: "WETH_QUSD",
        WBNB: "WBNB_QUSD",
        WSOL: "WSOL_QUSD",
        WQBC: "WQBC_QUSD",
      };
      const marketId = spotMap[asset];
      if (marketId) {
        setActiveMarket(marketId as Parameters<typeof setActiveMarket>[0]);
      }
    },
    [setActiveMarket],
  );

  const rows = balances ?? [];

  return (
    <div
      className="exchange-scroll"
      style={{ overflowY: "auto", flex: 1 }}
    >
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: `1px solid ${X.borderSubtle}` }}>
            <th style={tableHeaderStyle}>Asset</th>
            <th style={{ ...tableHeaderStyle, textAlign: "right" }}>Balance</th>
            <th style={{ ...tableHeaderStyle, textAlign: "right" }}>Value (USD)</th>
            <th style={{ ...tableHeaderStyle, textAlign: "right" }}>In Orders</th>
            <th style={{ ...tableHeaderStyle, textAlign: "right" }}>Available</th>
            <th style={{ ...tableHeaderStyle, textAlign: "right" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((b) => (
            <BalanceRow
              key={b.asset}
              balance={b}
              onDeposit={handleDeposit}
              onWithdraw={handleWithdraw}
              onTrade={handleTrade}
            />
          ))}
          {rows.length === 0 && (
            <tr>
              <td
                colSpan={6}
                style={{
                  ...tableCellStyle,
                  textAlign: "center",
                  color: X.textSecondary,
                  padding: "32px 12px",
                  fontFamily: FONT.body,
                  fontSize: 13,
                }}
              >
                No balances found. Deposit assets to start trading.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
});

// ─── P&L TAB ────────────────────────────────────────────────────────────────

const PnlTab = memo(function PnlTab() {
  const { data: equityHistory } = useEquityHistory();
  const { data: positions } = usePositions();

  const chartData = useMemo(() => {
    const snapshots = equityHistory ?? [];
    return snapshots.slice(-30);
  }, [equityHistory]);

  const { totalRealised, totalUnrealised, totalFees } = useMemo(() => {
    const pos = positions ?? [];
    let realised = 0;
    let unrealised = 0;
    let fees = 0;
    for (const p of pos) {
      realised += p.realisedPnl;
      unrealised += p.unrealisedPnl;
      fees += p.fundingPaid;
    }
    return { totalRealised: realised, totalUnrealised: unrealised, totalFees: fees };
  }, [positions]);

  const yDomain = useMemo(() => {
    if (chartData.length === 0) return [0, 100];
    const values = chartData.map((d) => d.totalEquity);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min) * 0.1 || max * 0.05 || 100;
    return [min - padding, max + padding];
  }, [chartData]);

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
      {/* Equity Chart */}
      <div style={{ flex: 1, minHeight: 180, padding: "12px 8px 4px" }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 4, right: 12, bottom: 0, left: 8 }}>
            <defs>
              <linearGradient id={EQUITY_GRADIENT_ID} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={X.glowCyan} stopOpacity={0.3} />
                <stop offset="100%" stopColor={X.glowCyan} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={X.borderSubtle}
              vertical={false}
            />
            <XAxis
              dataKey="timestamp"
              tickFormatter={(ts: number) => {
                const d = new Date(ts);
                return `${d.getMonth() + 1}/${d.getDate()}`;
              }}
              tick={{ fill: X.textSecondary, fontSize: 9, fontFamily: FONT.mono }}
              axisLine={{ stroke: X.borderSubtle }}
              tickLine={false}
              minTickGap={40}
            />
            <YAxis
              domain={yDomain as [number, number]}
              tickFormatter={(v: number) => formatUsd(v).replace("$", "")}
              tick={{ fill: X.textSecondary, fontSize: 9, fontFamily: FONT.mono }}
              axisLine={false}
              tickLine={false}
              width={60}
            />
            <Tooltip
              content={<EquityTooltip />}
              cursor={{ stroke: X.glowCyan, strokeWidth: 1, strokeDasharray: "4 4" }}
            />
            <Area
              type="monotone"
              dataKey="totalEquity"
              stroke={X.glowCyan}
              strokeWidth={2}
              fill={`url(#${EQUITY_GRADIENT_ID})`}
              dot={false}
              activeDot={{
                r: 4,
                fill: X.glowCyan,
                stroke: X.bgPanel,
                strokeWidth: 2,
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Summary Cards */}
      <div style={{ display: "flex", gap: 8, padding: "8px 12px 12px" }}>
        <div style={cardStyle}>
          <span style={cardLabelStyle}>Realised P&L</span>
          <PnlDisplay pnl={totalRealised} showPct={false} />
        </div>
        <div style={cardStyle}>
          <span style={cardLabelStyle}>Unrealised P&L</span>
          <PnlDisplay pnl={totalUnrealised} showPct={false} />
        </div>
        <div style={cardStyle}>
          <span style={cardLabelStyle}>Fees Paid</span>
          <span
            style={{
              fontFamily: FONT.mono,
              fontSize: 13,
              color: totalFees > 0 ? X.glowCrimson : X.textSecondary,
            }}
          >
            {totalFees > 0 ? "-" : ""}
            {formatUsd(Math.abs(totalFees))}
          </span>
        </div>
      </div>
    </div>
  );
});

// ─── PORTFOLIO PANEL (MAIN) ─────────────────────────────────────────────────

const TABS = [
  { key: "balances", label: "Balances" },
  { key: "pnl", label: "P&L" },
];

export const PortfolioPanel = memo(function PortfolioPanel() {
  const [activeTab, setActiveTab] = useState("balances");
  const { data: balances } = useBalances();
  const { data: positions } = usePositions();
  const { data: equityHistory } = useEquityHistory();

  // ── Computed account metrics ────────────────────────────────────────────

  const { totalEquity, availableMargin, usedMargin, pnl24h } = useMemo(() => {
    const bals = balances ?? [];
    const pos = positions ?? [];
    const snaps = equityHistory ?? [];

    // Total USD value of all balances
    let balanceUsd = 0;
    let marginUsed = 0;
    for (const b of bals) {
      balanceUsd += b.usdValue;
      marginUsed += b.usedAsMargin;
    }

    // Unrealised P&L from open positions
    let unrealised = 0;
    for (const p of pos) {
      unrealised += p.unrealisedPnl;
    }

    const equity = balanceUsd + unrealised;
    const available = equity - marginUsed;

    // 24h P&L: compare current equity to earliest snapshot within the last 24h
    let dayPnl = 0;
    if (snaps.length >= 2) {
      const cutoff = Date.now() - 24 * 60 * 60 * 1000;
      const dayAgoSnap = snaps.find((s) => s.timestamp >= cutoff) ?? snaps[0];
      dayPnl = equity - dayAgoSnap.totalEquity;
    }

    return {
      totalEquity: equity,
      availableMargin: available,
      usedMargin: marginUsed,
      pnl24h: dayPnl,
    };
  }, [balances, positions, equityHistory]);

  const pnl24hPct = totalEquity > 0 && totalEquity !== pnl24h
    ? (pnl24h / (totalEquity - pnl24h)) * 100
    : 0;

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
      <div style={panelHeaderStyle}>Portfolio</div>

      {/* Equity Summary Cards */}
      <div style={{ display: "flex", gap: 8, padding: "12px 12px 8px" }}>
        {/* Total Equity */}
        <div style={cardStyle}>
          <span style={cardLabelStyle}>Total Equity</span>
          <span style={cardValueStyle}>{formatUsd(totalEquity)}</span>
          <div style={{ marginTop: 2 }}>
            <PnlDisplay pnl={pnl24h} pct={pnl24hPct} showPct />
            <span style={{ ...cardSubStyle, marginLeft: 4 }}>24h</span>
          </div>
        </div>

        {/* Available Margin */}
        <div style={cardStyle}>
          <span style={cardLabelStyle}>Available Margin</span>
          <span style={cardValueStyle}>{formatUsd(availableMargin)}</span>
          <span style={cardSubStyle}>Available to trade</span>
        </div>

        {/* Used Margin */}
        <div style={cardStyle}>
          <span style={cardLabelStyle}>Used Margin</span>
          <span style={cardValueStyle}>{formatUsd(usedMargin)}</span>
          <span style={cardSubStyle}>In open positions</span>
        </div>
      </div>

      {/* Tab Navigation */}
      <TabBar tabs={TABS} active={activeTab} onChange={setActiveTab} />

      {/* Tab Content */}
      {activeTab === "balances" ? <BalancesTab /> : <PnlTab />}
    </div>
  );
});

export default PortfolioPanel;
