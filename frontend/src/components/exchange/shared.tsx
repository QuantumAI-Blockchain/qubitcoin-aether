// ─── QBC EXCHANGE — Design System & Shared Components ────────────────────────
"use client";

import React, { memo, useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import type { OrderSide, PositionSide } from "./types";

// ─── DESIGN TOKENS ──────────────────────────────────────────────────────────
export const X = {
  bgBase: "#020408",
  bgPanel: "#040c14",
  bgElevated: "#071422",
  borderSubtle: "#0d2a44",
  borderActive: "#143a5a",
  glowCyan: "#00d4ff",
  glowGold: "#f5c842",
  glowViolet: "#7c3aed",
  glowEmerald: "#10b981",
  glowCrimson: "#dc2626",
  glowAmber: "#f59e0b",
  textPrimary: "#e2f4ff",
  textSecondary: "#5a8fa8",
  textMono: "#00d4ff",
  bid: "#10b981",
  ask: "#dc2626",
  neutral: "#5a8fa8",
};

export const FONT = {
  display: "'Orbitron', sans-serif",
  mono: "'Share Tech Mono', monospace",
  body: "'Exo 2', sans-serif",
};

// ─── UTILITY FUNCTIONS ──────────────────────────────────────────────────────

export function formatPrice(n: number, decimals = 4): string {
  return n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export function formatSize(n: number, decimals = 2): string {
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  return n.toFixed(decimals);
}

export function formatUsd(n: number): string {
  if (Math.abs(n) >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
  if (Math.abs(n) >= 1e6) return "$" + (n / 1e6).toFixed(2) + "M";
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatPct(n: number): string {
  const sign = n >= 0 ? "+" : "";
  return sign + n.toFixed(2) + "%";
}

export function formatFundingRate(n: number): string {
  const sign = n >= 0 ? "+" : "";
  return sign + n.toFixed(4) + "%";
}

export function timeAgo(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function formatUtcTime(ts: number): string {
  return new Date(ts).toISOString().replace("T", " ").slice(0, 19) + " UTC";
}

export function truncHash(h: string, n = 6): string {
  if (h.length <= n * 2 + 2) return h;
  return h.slice(0, n + 2) + "..." + h.slice(-n);
}

export function sideColor(side: OrderSide | PositionSide): string {
  return side === "buy" || side === "long" ? X.bid : X.ask;
}

export function pnlColor(pnl: number): string {
  if (pnl > 0) return X.glowEmerald;
  if (pnl < 0) return X.glowCrimson;
  return X.textSecondary;
}

export function countdownStr(targetTs: number): string {
  const diff = Math.max(0, Math.floor((targetTs - Date.now()) / 1000));
  const h = Math.floor(diff / 3600);
  const m = Math.floor((diff % 3600) / 60);
  const s = diff % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

// ─── PANEL STYLE ────────────────────────────────────────────────────────────

export const panelStyle: React.CSSProperties = {
  background: X.bgPanel,
  border: `1px solid ${X.borderSubtle}`,
  borderRadius: 8,
};

export const panelHeaderStyle: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 11,
  letterSpacing: "0.08em",
  color: X.textSecondary,
  textTransform: "uppercase" as const,
  padding: "10px 14px",
  borderBottom: `1px solid ${X.borderSubtle}`,
};

// ─── SHARED COMPONENTS ──────────────────────────────────────────────────────

export const PriceDisplay = memo(function PriceDisplay({
  price,
  prevPrice,
  decimals = 4,
  size = "md",
}: {
  price: number;
  prevPrice?: number;
  decimals?: number;
  size?: "sm" | "md" | "lg";
}) {
  const [flash, setFlash] = useState<"up" | "down" | null>(null);
  const prevRef = useRef(price);
  const reduced = useReducedMotion();

  useEffect(() => {
    const prev = prevPrice ?? prevRef.current;
    if (price > prev) setFlash("up");
    else if (price < prev) setFlash("down");
    prevRef.current = price;
    if (!reduced) {
      const t = setTimeout(() => setFlash(null), 200);
      return () => clearTimeout(t);
    }
    setFlash(null);
  }, [price, prevPrice, reduced]);

  const fontSize = size === "lg" ? 22 : size === "md" ? 15 : 12;
  const color = flash === "up" ? X.bid : flash === "down" ? X.ask : X.textPrimary;

  return (
    <span
      style={{
        fontFamily: FONT.mono,
        fontSize,
        color,
        transition: "color 0.15s",
      }}
    >
      {formatPrice(price, decimals)}
    </span>
  );
});

export const SizeDisplay = memo(function SizeDisplay({
  size,
  decimals = 2,
}: {
  size: number;
  decimals?: number;
}) {
  return (
    <span style={{ fontFamily: FONT.mono, fontSize: 13, color: X.textPrimary }}>
      {formatSize(size, decimals)}
    </span>
  );
});

export const PnlDisplay = memo(function PnlDisplay({
  pnl,
  pct,
  showPct = true,
}: {
  pnl: number;
  pct?: number;
  showPct?: boolean;
}) {
  const color = pnlColor(pnl);
  const sign = pnl >= 0 ? "+" : "";
  return (
    <span style={{ fontFamily: FONT.mono, fontSize: 13, color }}>
      {sign}
      {formatUsd(Math.abs(pnl)).replace("$", pnl < 0 ? "-$" : "$")}
      {showPct && pct !== undefined && (
        <span style={{ fontSize: 11, marginLeft: 4, opacity: 0.8 }}>
          ({formatPct(pct)})
        </span>
      )}
    </span>
  );
});

export const SideBadge = memo(function SideBadge({
  side,
}: {
  side: OrderSide | PositionSide;
}) {
  const isLong = side === "buy" || side === "long";
  const label = side === "buy" ? "BUY" : side === "sell" ? "SELL" : side.toUpperCase();
  return (
    <span
      style={{
        fontFamily: FONT.display,
        fontSize: 10,
        letterSpacing: "0.08em",
        padding: "2px 8px",
        borderRadius: 4,
        background: isLong ? X.bid + "20" : X.ask + "20",
        color: isLong ? X.bid : X.ask,
        border: `1px solid ${isLong ? X.bid : X.ask}40`,
      }}
    >
      {label}
    </span>
  );
});

export const StatusBadge = memo(function StatusBadge({
  status,
}: {
  status: string;
}) {
  const colors: Record<string, string> = {
    open: X.glowCyan,
    filled: X.glowEmerald,
    partial: X.glowAmber,
    cancelled: X.textSecondary,
    expired: X.textSecondary,
    online: X.glowEmerald,
    offline: X.glowCrimson,
    degraded: X.glowAmber,
  };
  const c = colors[status] ?? X.textSecondary;
  return (
    <span
      style={{
        fontFamily: FONT.display,
        fontSize: 9,
        letterSpacing: "0.1em",
        padding: "2px 6px",
        borderRadius: 3,
        background: c + "18",
        color: c,
        textTransform: "uppercase",
      }}
    >
      {status}
    </span>
  );
});

export const CopyButton = memo(function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);
  return (
    <button
      onClick={handleCopy}
      style={{
        background: "none",
        border: "none",
        cursor: "pointer",
        color: copied ? X.glowEmerald : X.textSecondary,
        fontSize: 11,
        fontFamily: FONT.mono,
        padding: "2px 4px",
      }}
      title="Copy"
    >
      {copied ? "Copied!" : "Copy"}
    </button>
  );
});

export const SkeletonLoader = memo(function SkeletonLoader({
  width = "100%",
  height = 16,
  count = 1,
}: {
  width?: number | string;
  height?: number;
  count?: number;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {Array.from({ length: count }, (_, i) => (
        <div
          key={i}
          style={{
            width,
            height,
            borderRadius: 4,
            background: `linear-gradient(90deg, ${X.bgElevated} 25%, ${X.borderSubtle} 50%, ${X.bgElevated} 75%)`,
            backgroundSize: "200% 100%",
            animation: "shimmer 1.5s infinite",
          }}
        />
      ))}
    </div>
  );
});

export const TabBar = memo(function TabBar({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string; count?: number }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 0,
        borderBottom: `1px solid ${X.borderSubtle}`,
        padding: "0 12px",
      }}
    >
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          style={{
            fontFamily: FONT.display,
            fontSize: 10,
            letterSpacing: "0.08em",
            color: active === t.key ? X.glowCyan : X.textSecondary,
            background: "none",
            border: "none",
            borderBottom: active === t.key ? `2px solid ${X.glowCyan}` : "2px solid transparent",
            padding: "10px 16px",
            cursor: "pointer",
            textTransform: "uppercase",
            transition: "color 0.15s, border-color 0.15s",
          }}
        >
          {t.label}
          {t.count !== undefined && (
            <span style={{ marginLeft: 6, fontSize: 9, opacity: 0.6 }}>({t.count})</span>
          )}
        </button>
      ))}
    </div>
  );
});

export const Toast = memo(function Toast({
  message,
  type = "info",
  onDismiss,
}: {
  message: string;
  type?: "info" | "success" | "error" | "warning";
  onDismiss: () => void;
}) {
  const colors = {
    info: X.glowCyan,
    success: X.glowEmerald,
    error: X.glowCrimson,
    warning: X.glowAmber,
  };
  useEffect(() => {
    const t = setTimeout(onDismiss, 2000);
    return () => clearTimeout(t);
  }, [onDismiss]);
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      style={{
        ...panelStyle,
        padding: "10px 16px",
        fontSize: 12,
        fontFamily: FONT.body,
        color: colors[type],
        borderColor: colors[type] + "40",
        display: "flex",
        alignItems: "center",
        gap: 8,
      }}
    >
      {message}
    </motion.div>
  );
});

// CSS injection for shimmer animation
if (typeof document !== "undefined") {
  const id = "qbc-exchange-css";
  if (!document.getElementById(id)) {
    const style = document.createElement("style");
    style.id = id;
    style.textContent = `
      @keyframes shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
      }
      @keyframes pulseCrimson {
        0%, 100% { box-shadow: 0 0 8px ${X.glowCrimson}40; }
        50% { box-shadow: 0 0 16px ${X.glowCrimson}80; }
      }
      .exchange-scroll::-webkit-scrollbar { width: 4px; }
      .exchange-scroll::-webkit-scrollbar-track { background: transparent; }
      .exchange-scroll::-webkit-scrollbar-thumb { background: ${X.borderSubtle}; border-radius: 2px; }
      .exchange-scroll::-webkit-scrollbar-thumb:hover { background: ${X.borderActive}; }
    `;
    document.head.appendChild(style);
  }
}
