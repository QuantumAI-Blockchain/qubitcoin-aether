// ─── QBC EXCHANGE — Trade History (Recent Fills) ─────────────────────────────
"use client";

import React, { memo, useMemo } from "react";
import { useTrades, useTradeSimulation } from "./hooks";
import { useExchangeStore } from "./store";
import { X, FONT, formatPrice, formatSize, timeAgo, formatUtcTime, panelStyle, panelHeaderStyle } from "./shared";
import type { Trade, MarketId } from "./types";

const TradeRow = memo(function TradeRow({
  trade,
  decimals,
  sizeDecimals,
  tsFormat,
}: {
  trade: Trade;
  decimals: number;
  sizeDecimals: number;
  tsFormat: "relative" | "utc";
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr 80px",
        padding: "3px 12px",
        fontSize: 12,
        fontFamily: FONT.mono,
        fontWeight: trade.isLarge ? 700 : 400,
        opacity: trade.isLarge ? 1 : 0.85,
      }}
    >
      <span style={{ color: trade.side === "buy" ? X.bid : X.ask }}>
        {formatPrice(trade.price, decimals)}
      </span>
      <span style={{ color: X.textPrimary, textAlign: "right" }}>
        {formatSize(trade.size, sizeDecimals)}
      </span>
      <span style={{ color: X.textSecondary, textAlign: "right", fontSize: 10 }}>
        {tsFormat === "relative" ? timeAgo(trade.timestamp) : formatUtcTime(trade.timestamp).slice(11, 19)}
      </span>
    </div>
  );
});

export const TradeHistory = memo(function TradeHistory() {
  const activeMarket = useExchangeStore((s) => s.activeMarket);
  const tsFormat = useExchangeStore((s) => s.settings.timestampFormat);
  const { data: trades } = useTrades(activeMarket);
  useTradeSimulation(activeMarket);

  const market = useExchangeStore((s) => s.activeMarket);
  const decimals = market.includes("PERP") || market.includes("ETH") || market.includes("BNB") || market.includes("SOL") || market.includes("BTC") ? 2 : 4;
  const sizeDecimals = market.includes("ETH") || market.includes("BTC") ? 4 : 2;

  const sorted = useMemo(() => (trades ?? []).slice(0, 50), [trades]);

  return (
    <div style={{ ...panelStyle, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <div style={panelHeaderStyle}>Recent Trades</div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 80px",
          padding: "6px 12px",
          fontSize: 10,
          fontFamily: FONT.display,
          letterSpacing: "0.08em",
          color: X.textSecondary,
          borderBottom: `1px solid ${X.borderSubtle}`,
        }}
      >
        <span>Price</span>
        <span style={{ textAlign: "right" }}>Size</span>
        <span style={{ textAlign: "right" }}>Time</span>
      </div>
      <div className="exchange-scroll" style={{ flex: 1, overflowY: "auto" }}>
        {sorted.map((t) => (
          <TradeRow key={t.id} trade={t} decimals={decimals} sizeDecimals={sizeDecimals} tsFormat={tsFormat} />
        ))}
      </div>
    </div>
  );
});
