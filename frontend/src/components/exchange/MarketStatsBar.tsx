// ─── QBC EXCHANGE — Market Stats Bar ─────────────────────────────────────────
"use client";

import React, { memo, useState, useEffect } from "react";
import { useMarket } from "./hooks";
import { useExchangeStore } from "./store";
import { X, FONT, formatPrice, formatPct, formatUsd, formatSize, formatFundingRate, countdownStr, PriceDisplay } from "./shared";

export const MarketStatsBar = memo(function MarketStatsBar() {
  const activeMarket = useExchangeStore((s) => s.activeMarket);
  const { data: market } = useMarket(activeMarket);
  const [countdown, setCountdown] = useState("--:--:--");

  useEffect(() => {
    if (!market?.nextFundingTs) return;
    const update = () => setCountdown(countdownStr(market.nextFundingTs));
    update();
    const i = setInterval(update, 1000);
    return () => clearInterval(i);
  }, [market?.nextFundingTs]);

  if (!market) return null;

  const isPerp = market.type === "perp";
  const changeColor = market.priceChangePct24h >= 0 ? X.bid : X.ask;

  const stats = [
    { label: "LAST PRICE", value: <PriceDisplay price={market.lastPrice} decimals={market.decimals} size="lg" /> },
    { label: "24H CHANGE", value: <span style={{ color: changeColor, fontFamily: FONT.mono, fontSize: 14 }}>{market.priceChange24h >= 0 ? "+" : ""}{formatPrice(market.priceChange24h, market.decimals)} ({formatPct(market.priceChangePct24h)})</span> },
    { label: "24H HIGH", value: formatPrice(market.price24hHigh, market.decimals) },
    { label: "24H LOW", value: formatPrice(market.price24hLow, market.decimals) },
    { label: "24H VOLUME", value: formatSize(market.volume24h, 0) + " " + market.baseAsset },
  ];

  if (isPerp) {
    stats.push(
      { label: "INDEX", value: formatPrice(market.indexPrice, market.decimals) },
      { label: "MARK", value: formatPrice(market.markPrice, market.decimals) },
      { label: "FUNDING", value: <span style={{ color: market.fundingRate >= 0 ? X.bid : X.ask, fontFamily: FONT.mono, fontSize: 12 }}>{formatFundingRate(market.fundingRate * 100)}/1h</span> },
      { label: "NEXT FUNDING", value: countdown },
      { label: "OPEN INTEREST", value: formatUsd(market.openInterest) },
    );
  } else {
    stats.push({ label: "MKT CAP", value: formatUsd(market.marketCap) });
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 0,
        padding: "8px 16px",
        background: X.bgPanel,
        borderBottom: `1px solid ${X.borderSubtle}`,
        overflowX: "auto",
        flexShrink: 0,
      }}
    >
      {/* Market name */}
      <div style={{ marginRight: 20, flexShrink: 0 }}>
        <div style={{ fontFamily: FONT.display, fontSize: 14, letterSpacing: "0.06em", color: X.textPrimary }}>
          {market.displayName}
        </div>
        <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginTop: 1 }}>
          {isPerp ? "Perpetual" : "Spot"} Market
        </div>
      </div>

      {/* Stats */}
      {stats.map((s, i) => (
        <div
          key={s.label}
          style={{
            padding: "0 16px",
            borderLeft: i > 0 ? `1px solid ${X.borderSubtle}` : "none",
            flexShrink: 0,
          }}
        >
          <div style={{ fontFamily: FONT.display, fontSize: 8, letterSpacing: "0.1em", color: X.textSecondary, marginBottom: 2 }}>
            {s.label}
          </div>
          <div style={{ fontFamily: FONT.mono, fontSize: 12, color: X.textPrimary }}>
            {s.value}
          </div>
        </div>
      ))}

      {/* Oracle badge */}
      <div style={{ marginLeft: "auto", flexShrink: 0, display: "flex", alignItems: "center", gap: 6 }}>
        <div style={{ width: 6, height: 6, borderRadius: "50%", background: X.glowEmerald }} />
        <span style={{ fontFamily: FONT.display, fontSize: 9, letterSpacing: "0.08em", color: X.glowEmerald }}>
          QUANTUM ORACLE: VERIFIED
        </span>
      </div>
    </div>
  );
});
