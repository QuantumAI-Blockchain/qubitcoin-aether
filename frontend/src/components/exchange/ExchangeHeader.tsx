// ─── QBC EXCHANGE — Global Header + Ticker ───────────────────────────────────
"use client";

import React, { memo, useMemo, useRef, useEffect, useState } from "react";
import { useMarkets, usePositions } from "./hooks";
import { useExchangeStore } from "./store";
import { X, FONT, formatPrice, formatPct, formatUsd, formatFundingRate, PnlDisplay } from "./shared";
import type { MarketId } from "./types";

// ─── TICKER BAR ─────────────────────────────────────────────────────────────

const TickerBar = memo(function TickerBar() {
  const { data: markets } = useMarkets();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);

  const items = useMemo(() => {
    if (!markets) return [];
    const lines: { label: string; value: string; color: string }[] = [];
    for (const m of markets) {
      const c = m.priceChangePct24h >= 0 ? X.bid : X.ask;
      let val = `$${formatPrice(m.lastPrice, m.decimals)} (${formatPct(m.priceChangePct24h)})`;
      if (m.type === "perp") val += ` Funding: ${formatFundingRate(m.fundingRate * 100)}/1h`;
      lines.push({ label: m.displayName, value: val, color: c });
    }
    // Exchange-wide stats
    const totalVol = markets.reduce((s, m) => s + m.volume24hUsd, 0);
    const totalOI = markets.filter((m) => m.type === "perp").reduce((s, m) => s + m.openInterest, 0);
    lines.push({ label: "EXCHANGE VOL 24H", value: formatUsd(totalVol), color: X.glowCyan });
    lines.push({ label: "OPEN INTEREST", value: formatUsd(totalOI), color: X.glowViolet });
    lines.push({ label: "QUANTUM ORACLE", value: "11/11 NODES", color: X.glowEmerald });
    return lines;
  }, [markets]);

  useEffect(() => {
    if (paused || !scrollRef.current) return;
    let frame: number;
    let pos = 0;
    const el = scrollRef.current;
    const speed = 0.5;
    const tick = () => {
      pos += speed;
      if (pos >= el.scrollWidth / 2) pos = 0;
      el.scrollLeft = pos;
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [paused]);

  return (
    <div
      ref={scrollRef}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      style={{
        display: "flex",
        overflow: "hidden",
        whiteSpace: "nowrap",
        background: X.bgBase,
        borderBottom: `1px solid ${X.borderSubtle}`,
        padding: "4px 0",
      }}
    >
      {[0, 1].map((dup) => (
        <div key={dup} style={{ display: "flex", gap: 24, padding: "0 12px", flexShrink: 0 }}>
          {items.map((it, i) => (
            <span key={`${dup}-${i}`} style={{ fontFamily: FONT.mono, fontSize: 10, color: X.textSecondary, display: "flex", gap: 6, alignItems: "center" }}>
              <span style={{ color: X.textSecondary }}>&#9656;</span>
              <span style={{ color: X.textPrimary }}>{it.label}:</span>
              <span style={{ color: it.color }}>{it.value}</span>
            </span>
          ))}
        </div>
      ))}
    </div>
  );
});

// ─── HEADER ─────────────────────────────────────────────────────────────────

export const ExchangeHeader = memo(function ExchangeHeader() {
  const activeMarket = useExchangeStore((s) => s.activeMarket);
  const setActiveMarket = useExchangeStore((s) => s.setActiveMarket);
  const setView = useExchangeStore((s) => s.setView);
  const view = useExchangeStore((s) => s.view);
  const setDepositModalOpen = useExchangeStore((s) => s.setDepositModalOpen);
  const setSettingsPanelOpen = useExchangeStore((s) => s.setSettingsPanelOpen);
  const walletConnected = useExchangeStore((s) => s.walletConnected);
  const walletAddress = useExchangeStore((s) => s.walletAddress);
  const { data: markets } = useMarkets();
  const { data: positions } = usePositions();

  // Top 5 markets by volume
  const topMarkets = useMemo(() => {
    if (!markets) return [];
    return [...markets].sort((a, b) => b.volume24hUsd - a.volume24hUsd).slice(0, 5);
  }, [markets]);

  // Portfolio summary
  const equity = useMemo(() => {
    const unrealised = positions?.reduce((s, p) => s + p.unrealisedPnl, 0) ?? 0;
    return { total: 12847.32, pnl24h: 284.21, pnlPct: 2.26, unrealised };
  }, [positions]);

  return (
    <div style={{ flexShrink: 0 }}>
      {/* Main header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 16px",
          background: X.bgPanel,
          borderBottom: `1px solid ${X.borderSubtle}`,
          gap: 12,
        }}
      >
        {/* Left: Logo + title */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L14 8L20 8L15 12L17 18L12 14L7 18L9 12L4 8L10 8L12 2Z" fill={X.glowCyan} />
            <path d="M12 6L13 9H16L13.5 11L14.5 14L12 12L9.5 14L10.5 11L8 9H11L12 6Z" fill={X.bgPanel} />
          </svg>
          <span style={{ fontFamily: FONT.display, fontSize: 13, letterSpacing: "0.1em", color: X.textPrimary }}>
            QBC <span style={{ color: X.glowCyan }}>EXCHANGE</span>
          </span>
        </div>

        {/* Centre: Quick market pills */}
        <div style={{ display: "flex", gap: 4, overflowX: "auto", flex: 1, justifyContent: "center" }}>
          {topMarkets.map((m) => (
            <button
              key={m.id}
              onClick={() => { setActiveMarket(m.id); setView("trading"); }}
              style={{
                fontFamily: FONT.display,
                fontSize: 9,
                letterSpacing: "0.06em",
                color: m.id === activeMarket ? X.glowCyan : X.textSecondary,
                background: m.id === activeMarket ? X.glowCyan + "12" : "transparent",
                border: "none",
                borderBottom: m.id === activeMarket ? `2px solid ${X.glowCyan}` : "2px solid transparent",
                padding: "6px 12px",
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "color 0.15s",
              }}
            >
              {m.displayName}
            </button>
          ))}
        </div>

        {/* Right: Portfolio + actions */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
          {walletConnected && (
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontFamily: FONT.mono, fontSize: 11, color: X.textPrimary }}>
                  Equity: {formatUsd(equity.total)}
                </div>
                <PnlDisplay pnl={equity.pnl24h} pct={equity.pnlPct} />
              </div>
            </div>
          )}

          {/* View toggle */}
          <div style={{ display: "flex", gap: 2 }}>
            {(["trading", "portfolio"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                style={{
                  fontFamily: FONT.display,
                  fontSize: 9,
                  letterSpacing: "0.06em",
                  color: view === v ? X.glowCyan : X.textSecondary,
                  background: view === v ? X.glowCyan + "15" : "transparent",
                  border: `1px solid ${view === v ? X.glowCyan + "40" : X.borderSubtle}`,
                  borderRadius: 4,
                  padding: "5px 10px",
                  cursor: "pointer",
                  textTransform: "uppercase",
                }}
              >
                {v}
              </button>
            ))}
          </div>

          {/* Deposit button */}
          <button
            onClick={() => setDepositModalOpen(true)}
            style={{
              fontFamily: FONT.display,
              fontSize: 10,
              letterSpacing: "0.08em",
              color: X.bgBase,
              background: X.glowCyan,
              border: "none",
              borderRadius: 6,
              padding: "7px 16px",
              cursor: "pointer",
              boxShadow: `0 0 15px ${X.glowCyan}30`,
              fontWeight: 700,
            }}
          >
            DEPOSIT
          </button>

          {/* Settings */}
          <button
            onClick={() => setSettingsPanelOpen(true)}
            style={{
              background: "none",
              border: "none",
              color: X.textSecondary,
              cursor: "pointer",
              fontSize: 18,
              padding: "4px",
              lineHeight: 1,
            }}
            title="Settings"
          >
            &#9881;
          </button>
        </div>
      </div>

      {/* Ticker */}
      <TickerBar />
    </div>
  );
});
