"use client";

// ─── QBC EXCHANGE — Real-Time Order Book ────────────────────────────────────
import React, { memo, useMemo, useCallback, useRef } from "react";
import type { OrderBook as OrderBookType, OrderBookLevel, MarketId } from "./types";
import { useOrderBook } from "./hooks";
import { useExchangeStore } from "./store";
import {
  X,
  FONT,
  formatPrice,
  formatSize,
  panelStyle,
  panelHeaderStyle,
} from "./shared";

// ─── CONSTANTS ──────────────────────────────────────────────────────────────

const GROUPING_OPTIONS = [0.0001, 0.001, 0.01, 0.1] as const;
const ROW_OPTIONS = [10, 20, 50] as const;
const ROW_HEIGHT = 22;

// ─── PRICE GROUPING ─────────────────────────────────────────────────────────

interface GroupedLevel {
  price: number;
  size: number;
  total: number;
  orderCount: number;
  myOrderSize: number;
}

function groupLevels(
  levels: OrderBookLevel[],
  grouping: number,
  side: "bid" | "ask",
): GroupedLevel[] {
  if (levels.length === 0) return [];

  const bucketMap = new Map<number, GroupedLevel>();

  for (const level of levels) {
    // For bids: floor to bucket. For asks: ceil to bucket.
    const bucketPrice =
      side === "bid"
        ? Math.floor(level.price / grouping) * grouping
        : Math.ceil(level.price / grouping) * grouping;

    const existing = bucketMap.get(bucketPrice);
    if (existing) {
      existing.size += level.size;
      existing.orderCount += level.orderCount;
      existing.myOrderSize += level.myOrderSize;
    } else {
      bucketMap.set(bucketPrice, {
        price: bucketPrice,
        size: level.size,
        total: 0,
        orderCount: level.orderCount,
        myOrderSize: level.myOrderSize,
      });
    }
  }

  // Sort: bids descending, asks ascending
  const sorted = Array.from(bucketMap.values()).sort((a, b) =>
    side === "bid" ? b.price - a.price : a.price - b.price,
  );

  // Compute running totals
  let runningTotal = 0;
  for (const level of sorted) {
    runningTotal += level.size;
    level.total = runningTotal;
  }

  return sorted;
}

// ─── ORDER BOOK ROW ─────────────────────────────────────────────────────────

interface OrderBookRowProps {
  level: GroupedLevel;
  maxTotal: number;
  side: "bid" | "ask";
  decimals: number;
  sizeDecimals: number;
  onClickPrice: (price: number) => void;
}

const OrderBookRow = memo(function OrderBookRow({
  level,
  maxTotal,
  side,
  decimals,
  sizeDecimals,
  onClickPrice,
}: OrderBookRowProps) {
  const fillPct = maxTotal > 0 ? (level.total / maxTotal) * 100 : 0;
  const barColor = side === "bid" ? X.bid : X.ask;
  const priceColor = side === "bid" ? X.bid : X.ask;

  const handleClick = useCallback(() => {
    onClickPrice(level.price);
  }, [level.price, onClickPrice]);

  return (
    <div
      onClick={handleClick}
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr 1fr",
        alignItems: "center",
        height: ROW_HEIGHT,
        padding: "0 10px",
        cursor: "pointer",
        position: "relative",
        userSelect: "none",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.background =
          X.bgElevated + "80";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.background = "transparent";
      }}
    >
      {/* Background fill bar */}
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          right: 0,
          width: `${fillPct}%`,
          background: barColor + "26",
          pointerEvents: "none",
          transition: "width 0.15s ease-out",
        }}
      />

      {/* Price */}
      <span
        style={{
          fontFamily: FONT.mono,
          fontSize: 12,
          color: priceColor,
          position: "relative",
          zIndex: 1,
          textAlign: "left",
        }}
      >
        {formatPrice(level.price, decimals)}
      </span>

      {/* Size */}
      <span
        style={{
          fontFamily: FONT.mono,
          fontSize: 12,
          color: X.textPrimary,
          position: "relative",
          zIndex: 1,
          textAlign: "right",
        }}
      >
        {formatSize(level.size, sizeDecimals)}
      </span>

      {/* Total */}
      <span
        style={{
          fontFamily: FONT.mono,
          fontSize: 12,
          color: X.textSecondary,
          position: "relative",
          zIndex: 1,
          textAlign: "right",
        }}
      >
        {formatSize(level.total, sizeDecimals)}
      </span>

      {/* My order indicator */}
      {level.myOrderSize > 0 && (
        <div
          style={{
            position: "absolute",
            left: 2,
            top: "50%",
            transform: "translateY(-50%)",
            width: 3,
            height: 10,
            borderRadius: 1,
            background: X.glowCyan,
            zIndex: 2,
          }}
        />
      )}
    </div>
  );
});

// ─── SPREAD BAR ─────────────────────────────────────────────────────────────

interface SpreadBarProps {
  lastPrice: number;
  prevPrice: number;
  spread: number;
  spreadPct: number;
  decimals: number;
}

const SpreadBar = memo(function SpreadBar({
  lastPrice,
  prevPrice,
  spread,
  spreadPct,
  decimals,
}: SpreadBarProps) {
  const isUp = lastPrice >= prevPrice;
  const arrowChar = isUp ? "\u25B2" : "\u25BC";
  const arrowColor = isUp ? X.bid : X.ask;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        height: 30,
        padding: "0 10px",
        borderTop: `1px solid ${X.borderSubtle}`,
        borderBottom: `1px solid ${X.borderSubtle}`,
        background: X.bgElevated + "40",
      }}
    >
      {/* Last price with arrow */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span
          style={{
            fontFamily: FONT.mono,
            fontSize: 14,
            fontWeight: 700,
            color: arrowColor,
          }}
        >
          {formatPrice(lastPrice, decimals)}
        </span>
        <span
          style={{
            fontSize: 10,
            color: arrowColor,
            lineHeight: 1,
          }}
        >
          {arrowChar}
        </span>
      </div>

      {/* Spread info */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            fontFamily: FONT.mono,
            fontSize: 10,
            color: X.textSecondary,
          }}
        >
          Spread: {formatPrice(spread, decimals)}
        </span>
        <span
          style={{
            fontFamily: FONT.mono,
            fontSize: 10,
            color: X.textSecondary,
          }}
        >
          ({spreadPct.toFixed(2)}%)
        </span>
      </div>
    </div>
  );
});

// ─── SELECT DROPDOWN ────────────────────────────────────────────────────────

interface MiniSelectProps<T extends string | number> {
  value: T;
  options: readonly T[];
  onChange: (v: T) => void;
  formatLabel?: (v: T) => string;
}

function MiniSelect<T extends string | number>({
  value,
  options,
  onChange,
  formatLabel,
}: MiniSelectProps<T>) {
  return (
    <select
      value={String(value)}
      onChange={(e) => {
        const raw = e.target.value;
        const parsed = typeof value === "number" ? (Number(raw) as T) : (raw as T);
        onChange(parsed);
      }}
      style={{
        fontFamily: FONT.mono,
        fontSize: 10,
        color: X.textSecondary,
        background: X.bgElevated,
        border: `1px solid ${X.borderSubtle}`,
        borderRadius: 3,
        padding: "2px 4px",
        cursor: "pointer",
        outline: "none",
      }}
    >
      {options.map((opt) => (
        <option key={String(opt)} value={String(opt)}>
          {formatLabel ? formatLabel(opt) : String(opt)}
        </option>
      ))}
    </select>
  );
}

// ─── COLUMN HEADERS ─────────────────────────────────────────────────────────

const ColumnHeaders = memo(function ColumnHeaders() {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr 1fr",
        padding: "4px 10px",
        borderBottom: `1px solid ${X.borderSubtle}`,
      }}
    >
      <span
        style={{
          fontFamily: FONT.display,
          fontSize: 9,
          letterSpacing: "0.08em",
          color: X.textSecondary,
          textTransform: "uppercase",
          textAlign: "left",
        }}
      >
        Price (QUSD)
      </span>
      <span
        style={{
          fontFamily: FONT.display,
          fontSize: 9,
          letterSpacing: "0.08em",
          color: X.textSecondary,
          textTransform: "uppercase",
          textAlign: "right",
        }}
      >
        Size
      </span>
      <span
        style={{
          fontFamily: FONT.display,
          fontSize: 9,
          letterSpacing: "0.08em",
          color: X.textSecondary,
          textTransform: "uppercase",
          textAlign: "right",
        }}
      >
        Total
      </span>
    </div>
  );
});

// ─── MAIN ORDER BOOK COMPONENT ──────────────────────────────────────────────

const OrderBook = memo(function OrderBook() {
  const activeMarket = useExchangeStore((s) => s.activeMarket);
  const obGrouping = useExchangeStore((s) => s.obGrouping);
  const obRows = useExchangeStore((s) => s.obRows);
  const setObGrouping = useExchangeStore((s) => s.setObGrouping);
  const setObRows = useExchangeStore((s) => s.setObRows);
  const setOrderPrice = useExchangeStore((s) => s.setOrderPrice);

  const { data: book } = useOrderBook(activeMarket);

  const prevMidRef = useRef<number>(0);

  // Derive display name from MarketId (e.g., "QBC_QUSD" -> "QBC / QUSD")
  const marketDisplay = useMemo(() => {
    return activeMarket.replace("_", " / ");
  }, [activeMarket]);

  // Determine decimals from grouping
  const priceDecimals = useMemo(() => {
    const g = obGrouping;
    if (g >= 1) return 0;
    if (g >= 0.1) return 1;
    if (g >= 0.01) return 2;
    if (g >= 0.001) return 3;
    return 4;
  }, [obGrouping]);

  const sizeDecimals = 2;

  // Group and slice levels
  const { askRows, bidRows, maxTotal } = useMemo(() => {
    if (!book) {
      return { askRows: [] as GroupedLevel[], bidRows: [] as GroupedLevel[], maxTotal: 0 };
    }

    const groupedBids = groupLevels(book.bids, obGrouping, "bid");
    const groupedAsks = groupLevels(book.asks, obGrouping, "ask");

    // Slice to obRows count
    const slicedBids = groupedBids.slice(0, obRows);
    const slicedAsks = groupedAsks.slice(0, obRows);

    // Compute max total across both sides for consistent bar widths
    const maxBidTotal = slicedBids.length > 0 ? slicedBids[slicedBids.length - 1].total : 0;
    const maxAskTotal = slicedAsks.length > 0 ? slicedAsks[slicedAsks.length - 1].total : 0;
    const mt = Math.max(maxBidTotal, maxAskTotal);

    return { askRows: slicedAsks, bidRows: slicedBids, maxTotal: mt };
  }, [book, obGrouping, obRows]);

  // Reverse asks so lowest ask is at the bottom (near spread)
  const reversedAsks = useMemo(() => [...askRows].reverse(), [askRows]);

  // Handle price click -> fill order entry
  const handlePriceClick = useCallback(
    (price: number) => {
      setOrderPrice(formatPrice(price, priceDecimals));
    },
    [setOrderPrice, priceDecimals],
  );

  // Track previous mid price for spread bar arrow
  const midPrice = book?.midPrice ?? 0;
  const prevMidPrice = prevMidRef.current;
  if (midPrice > 0) {
    prevMidRef.current = midPrice;
  }

  const spread = book?.spread ?? 0;
  const spreadPct = book?.spreadPct ?? 0;

  return (
    <div style={{ ...panelStyle, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* ── Header ────────────────────────────────────────────────────── */}
      <div
        style={{
          ...panelHeaderStyle,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>ORDER BOOK</span>
          <span
            style={{
              fontFamily: FONT.mono,
              fontSize: 10,
              color: X.textPrimary,
              letterSpacing: "0.02em",
            }}
          >
            {marketDisplay}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <MiniSelect
            value={obGrouping}
            options={GROUPING_OPTIONS}
            onChange={(v) => setObGrouping(v as number)}
          />
          <MiniSelect
            value={obRows}
            options={ROW_OPTIONS}
            onChange={(v) => setObRows(v as 10 | 20 | 50)}
          />
        </div>
      </div>

      {/* ── Column Headers ────────────────────────────────────────────── */}
      <ColumnHeaders />

      {/* ── Ask Side (reversed: highest at top, lowest at bottom near spread) ── */}
      <div
        className="exchange-scroll"
        style={{
          flex: 1,
          overflowY: "auto",
          overflowX: "hidden",
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-end",
          minHeight: 0,
        }}
      >
        {reversedAsks.map((level) => (
          <OrderBookRow
            key={level.price}
            level={level}
            maxTotal={maxTotal}
            side="ask"
            decimals={priceDecimals}
            sizeDecimals={sizeDecimals}
            onClickPrice={handlePriceClick}
          />
        ))}
      </div>

      {/* ── Spread Bar ──────────────────────────────────────────────── */}
      <SpreadBar
        lastPrice={midPrice}
        prevPrice={prevMidPrice || midPrice}
        spread={spread}
        spreadPct={spreadPct}
        decimals={priceDecimals}
      />

      {/* ── Bid Side (highest at top near spread) ─────────────────── */}
      <div
        className="exchange-scroll"
        style={{
          flex: 1,
          overflowY: "auto",
          overflowX: "hidden",
          minHeight: 0,
        }}
      >
        {bidRows.map((level) => (
          <OrderBookRow
            key={level.price}
            level={level}
            maxTotal={maxTotal}
            side="bid"
            decimals={priceDecimals}
            sizeDecimals={sizeDecimals}
            onClickPrice={handlePriceClick}
          />
        ))}
      </div>
    </div>
  );
});

export default OrderBook;
