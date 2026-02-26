// ─── QBC EXCHANGE — Market Selector Panel ────────────────────────────────────
"use client";

import React, { memo, useState, useMemo, useCallback } from "react";
import { useMarkets } from "./hooks";
import { useExchangeStore } from "./store";
import { X, FONT, formatPrice, formatPct, formatUsd, panelStyle, TabBar } from "./shared";
import type { Market, MarketId } from "./types";

const MarketRow = memo(function MarketRow({
  market,
  isActive,
  isFav,
  onSelect,
  onToggleFav,
}: {
  market: Market;
  isActive: boolean;
  isFav: boolean;
  onSelect: () => void;
  onToggleFav: () => void;
}) {
  const changeColor = market.priceChangePct24h >= 0 ? X.bid : X.ask;
  return (
    <div
      onClick={onSelect}
      style={{
        display: "grid",
        gridTemplateColumns: "24px 1fr 90px 70px",
        alignItems: "center",
        padding: "8px 12px",
        cursor: "pointer",
        borderLeft: isActive ? `3px solid ${X.glowCyan}` : "3px solid transparent",
        background: isActive ? X.bgElevated : "transparent",
        transition: "background 0.15s",
      }}
      onMouseEnter={(e) => { if (!isActive) (e.currentTarget as HTMLDivElement).style.background = X.bgElevated + "80"; }}
      onMouseLeave={(e) => { if (!isActive) (e.currentTarget as HTMLDivElement).style.background = "transparent"; }}
    >
      <button
        onClick={(e) => { e.stopPropagation(); onToggleFav(); }}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          fontSize: 14,
          color: isFav ? X.glowGold : X.textSecondary + "40",
          padding: 0,
          lineHeight: 1,
        }}
        title={isFav ? "Remove from favourites" : "Add to favourites"}
      >
        {isFav ? "\u2605" : "\u2606"}
      </button>
      <div>
        <div style={{ fontFamily: FONT.display, fontSize: 11, letterSpacing: "0.05em", color: X.textPrimary }}>
          {market.displayName}
        </div>
        <div style={{ fontFamily: FONT.body, fontSize: 9, color: X.textSecondary, marginTop: 1 }}>
          {market.type === "perp" ? "Perpetual" : "Spot"}
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontFamily: FONT.mono, fontSize: 12, color: X.textPrimary }}>
          {formatPrice(market.lastPrice, market.decimals)}
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <span style={{ fontFamily: FONT.mono, fontSize: 11, color: changeColor }}>
          {formatPct(market.priceChangePct24h)}
        </span>
      </div>
    </div>
  );
});

export const MarketSelector = memo(function MarketSelector() {
  const { data: markets } = useMarkets();
  const activeMarket = useExchangeStore((s) => s.activeMarket);
  const favourites = useExchangeStore((s) => s.favourites);
  const setActiveMarket = useExchangeStore((s) => s.setActiveMarket);
  const toggleFavourite = useExchangeStore((s) => s.toggleFavourite);
  const isOpen = useExchangeStore((s) => s.marketSelectorOpen);
  const setOpen = useExchangeStore((s) => s.setMarketSelectorOpen);

  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<"spot" | "perps" | "favourites">("spot");

  const filtered = useMemo(() => {
    if (!markets) return [];
    let list = markets;

    if (tab === "spot") list = list.filter((m) => m.type === "spot");
    else if (tab === "perps") list = list.filter((m) => m.type === "perp");
    else if (tab === "favourites") list = list.filter((m) => favourites.includes(m.id));

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (m) =>
          m.baseAsset.toLowerCase().includes(q) ||
          m.displayName.toLowerCase().includes(q) ||
          m.id.toLowerCase().includes(q),
      );
    }
    return list;
  }, [markets, tab, search, favourites]);

  const handleSelect = useCallback(
    (id: MarketId) => setActiveMarket(id),
    [setActiveMarket],
  );

  if (!isOpen) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{
          position: "absolute",
          left: 0,
          top: 8,
          background: X.bgPanel,
          border: `1px solid ${X.borderSubtle}`,
          borderLeft: "none",
          borderRadius: "0 6px 6px 0",
          color: X.glowCyan,
          cursor: "pointer",
          padding: "8px 6px",
          fontFamily: FONT.display,
          fontSize: 10,
          zIndex: 5,
          writingMode: "vertical-lr",
          letterSpacing: "0.1em",
        }}
      >
        MARKETS
      </button>
    );
  }

  return (
    <div
      style={{
        ...panelStyle,
        width: 260,
        minWidth: 260,
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", borderBottom: `1px solid ${X.borderSubtle}` }}>
        <span style={{ fontFamily: FONT.display, fontSize: 11, letterSpacing: "0.08em", color: X.textSecondary }}>MARKETS</span>
        <button
          onClick={() => setOpen(false)}
          style={{ background: "none", border: "none", color: X.textSecondary, cursor: "pointer", fontSize: 16, padding: 0, lineHeight: 1 }}
        >
          \u00D7
        </button>
      </div>

      {/* Search */}
      <div style={{ padding: "8px 12px" }}>
        <input
          type="text"
          placeholder="Search markets..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            width: "100%",
            background: X.bgElevated,
            border: `1px solid ${X.borderSubtle}`,
            borderRadius: 6,
            color: X.textPrimary,
            fontFamily: FONT.body,
            fontSize: 12,
            padding: "6px 10px",
            outline: "none",
          }}
          onFocus={(e) => { e.currentTarget.style.borderColor = X.glowCyan; }}
          onBlur={(e) => { e.currentTarget.style.borderColor = X.borderSubtle; }}
        />
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 0, borderBottom: `1px solid ${X.borderSubtle}`, padding: "0 12px" }}>
        {(["spot", "perps", "favourites"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              fontFamily: FONT.display,
              fontSize: 9,
              letterSpacing: "0.08em",
              color: tab === t ? X.glowCyan : X.textSecondary,
              background: "none",
              border: "none",
              borderBottom: tab === t ? `2px solid ${X.glowCyan}` : "2px solid transparent",
              padding: "8px 12px",
              cursor: "pointer",
              textTransform: "uppercase",
            }}
          >
            {t === "favourites" ? "\u2605 FAV" : t.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Column headers */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "24px 1fr 90px 70px",
          padding: "6px 12px",
          fontSize: 9,
          fontFamily: FONT.display,
          letterSpacing: "0.08em",
          color: X.textSecondary,
        }}
      >
        <span />
        <span>Market</span>
        <span style={{ textAlign: "right" }}>Price</span>
        <span style={{ textAlign: "right" }}>24h</span>
      </div>

      {/* Market list */}
      <div className="exchange-scroll" style={{ flex: 1, overflowY: "auto" }}>
        {filtered.map((m) => (
          <MarketRow
            key={m.id}
            market={m}
            isActive={m.id === activeMarket}
            isFav={favourites.includes(m.id)}
            onSelect={() => handleSelect(m.id)}
            onToggleFav={() => toggleFavourite(m.id)}
          />
        ))}
        {filtered.length === 0 && (
          <div style={{ padding: 24, textAlign: "center", fontFamily: FONT.body, fontSize: 12, color: X.textSecondary }}>
            No markets found
          </div>
        )}
      </div>
    </div>
  );
});
