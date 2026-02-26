"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Bridge — Design System + Shared Components
   ───────────────────────────────────────────────────────────────────────── */

import { motion, useReducedMotion, useSpring, useTransform } from "framer-motion";
import { Copy, Check, ExternalLink, Lock, AlertTriangle, CheckCircle, XCircle, Clock, Loader2 } from "lucide-react";
import { useState, useCallback, useEffect, memo } from "react";
import type { ChainId, ExternalChainId, TokenType, WrappedToken, BridgeStatus, OperationType } from "./types";
import { CHAINS } from "./chain-config";

/* ── Design Tokens ────────────────────────────────────────────────────── */

export const B = {
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
} as const;

export const FONT = {
  display: "'Orbitron', sans-serif",
  mono: "'Share Tech Mono', monospace",
  body: "'Exo 2', sans-serif",
} as const;

/* ── Token Color System ───────────────────────────────────────────────── */

export function tokenColor(token: TokenType | WrappedToken): string {
  switch (token) {
    case "QBC": return B.glowCyan;
    case "QUSD": return B.glowViolet;
    case "wQBC": return B.glowGold;
    case "wQUSD": return B.glowEmerald;
  }
}

export function chainColor(chain: ChainId): string {
  return CHAINS[chain]?.color ?? B.textSecondary;
}

export function statusColor(status: BridgeStatus): string {
  switch (status) {
    case "complete": return B.glowEmerald;
    case "pending": return B.glowAmber;
    case "failed": return B.glowCrimson;
    case "refunded": return B.glowViolet;
  }
}

/* ── Panel style ──────────────────────────────────────────────────────── */

export const panelStyle: React.CSSProperties = {
  border: `1px solid ${B.borderSubtle}`,
  boxShadow: "inset 0 0 20px rgba(0, 212, 255, 0.03)",
  background: B.bgPanel,
  borderRadius: 12,
};

/* ── Utilities ────────────────────────────────────────────────────────── */

export function truncAddr(addr: string, pre: number = 6, post: number = 4): string {
  if (addr.length <= pre + post + 3) return addr;
  return addr.slice(0, pre) + "…" + addr.slice(-post);
}

export function formatAmount(n: number, dp: number = 6): string {
  return n.toFixed(dp);
}

export function formatUsd(n: number): string {
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatPct(n: number): string {
  return n.toFixed(3) + "%";
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${s}s`;
}

export function timeAgo(ts: number): string {
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

/* ── WTokenLabel ──────────────────────────────────────────────────────── */

export const WTokenLabel = memo(function WTokenLabel({ token }: { token: "wQBC" | "wQUSD" }) {
  return (
    <span style={{ fontFamily: FONT.mono }}>
      <span style={{ color: B.textSecondary, fontSize: "0.8em" }}>w</span>
      <span style={{ color: token === "wQBC" ? B.glowGold : B.glowEmerald }}>
        {token.slice(1)}
      </span>
    </span>
  );
});

/* ── TokenBadge ───────────────────────────────────────────────────────── */

export const TokenBadge = memo(function TokenBadge({
  token,
  size = "sm",
}: {
  token: TokenType | WrappedToken;
  size?: "sm" | "md" | "lg";
}) {
  const isWrapped = token.startsWith("w");
  const fontSize = size === "lg" ? "0.875rem" : size === "md" ? "0.75rem" : "0.625rem";
  const px = size === "lg" ? 12 : size === "md" ? 8 : 6;
  const py = size === "lg" ? 6 : size === "md" ? 4 : 2;
  const color = tokenColor(token);

  return (
    <span
      className="inline-flex items-center rounded font-bold tracking-wider"
      style={{
        fontSize,
        paddingLeft: px,
        paddingRight: px,
        paddingTop: py,
        paddingBottom: py,
        color,
        background: `${color}15`,
        fontFamily: FONT.display,
      }}
    >
      {isWrapped ? <WTokenLabel token={token as WrappedToken} /> : token}
    </span>
  );
});

/* ── ChainBadge ───────────────────────────────────────────────────────── */

export const ChainBadge = memo(function ChainBadge({
  chain,
  showStatus = false,
}: {
  chain: ChainId;
  showStatus?: boolean;
}) {
  const info = CHAINS[chain];
  const color = info?.color ?? B.textSecondary;

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded px-2 py-1 text-[10px] font-bold tracking-wider"
      style={{ color, background: `${color}12`, fontFamily: FONT.display }}
    >
      {showStatus && (
        <span
          className="inline-block h-1.5 w-1.5 rounded-full"
          style={{ background: info?.available ? B.glowEmerald : B.glowCrimson }}
        />
      )}
      {info?.shortName ?? chain}
    </span>
  );
});

/* ── HashDisplay ──────────────────────────────────────────────────────── */

export const HashDisplay = memo(function HashDisplay({
  hash,
  truncLen = 8,
}: {
  hash: string;
  truncLen?: number;
}) {
  // Alternating character band colors
  const chars = truncAddr(hash, truncLen, truncLen);

  return (
    <span style={{ fontFamily: FONT.mono, fontSize: "0.75rem" }}>
      {chars.split("").map((ch, i) => (
        <span
          key={i}
          style={{ color: i % 2 === 0 ? B.glowCyan : "#0099bb" }}
        >
          {ch}
        </span>
      ))}
    </span>
  );
});

/* ── CopyButton ───────────────────────────────────────────────────────── */

export function CopyButton({ text, size = 12 }: { text: string; size?: number }) {
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
      className="rounded p-0.5 transition-opacity hover:opacity-80"
      title="Copy"
    >
      {copied ? (
        <Check size={size} style={{ color: B.glowEmerald }} />
      ) : (
        <Copy size={size} style={{ color: B.textSecondary }} />
      )}
    </button>
  );
}

/* ── Toast ─────────────────────────────────────────────────────────────── */

let toastTimeout: ReturnType<typeof setTimeout> | null = null;
let setToastFn: ((msg: string | null) => void) | null = null;

export function showToast(msg: string) {
  if (toastTimeout) clearTimeout(toastTimeout);
  setToastFn?.(msg);
  toastTimeout = setTimeout(() => setToastFn?.(null), 2000);
}

export function ToastContainer() {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    setToastFn = setMsg;
    return () => { setToastFn = null; };
  }, []);

  if (!msg) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      className="fixed bottom-4 left-1/2 z-[100] -translate-x-1/2 rounded-lg border px-4 py-2 text-xs"
      style={{
        background: B.bgElevated,
        borderColor: B.glowCyan,
        color: B.textPrimary,
        fontFamily: FONT.mono,
      }}
    >
      {msg}
    </motion.div>
  );
}

/* ── StatusBadge ──────────────────────────────────────────────────────── */

export const StatusBadge = memo(function StatusBadge({ status }: { status: BridgeStatus }) {
  const color = statusColor(status);
  const icons: Record<BridgeStatus, typeof CheckCircle> = {
    complete: CheckCircle,
    pending: Clock,
    failed: XCircle,
    refunded: AlertTriangle,
  };
  const Icon = icons[status];

  return (
    <span
      className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold tracking-wider"
      style={{ color, background: `${color}15`, fontFamily: FONT.display }}
    >
      <Icon size={10} />
      {status.toUpperCase()}
    </span>
  );
});

/* ── VaultBackingBadge ────────────────────────────────────────────────── */

export const VaultBackingBadge = memo(function VaultBackingBadge({
  ratio = 1.0,
  onClick,
}: {
  ratio?: number;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 transition-opacity hover:opacity-90"
      style={{
        borderColor: `${B.glowGold}40`,
        background: `${B.glowGold}08`,
        cursor: onClick ? "pointer" : "default",
      }}
    >
      <Lock size={12} style={{ color: B.glowGold }} />
      <span className="text-xs font-bold" style={{ color: B.glowGold, fontFamily: FONT.mono }}>
        VAULT BACKING: {(ratio * 100).toFixed(2)}%
      </span>
    </button>
  );
});

/* ── SkeletonLoader ───────────────────────────────────────────────────── */

export function Skeleton({ width, height = 16 }: { width: number | string; height?: number | string }) {
  return (
    <div
      className="animate-pulse rounded"
      style={{
        width,
        height,
        background: `linear-gradient(90deg, ${B.bgElevated} 25%, ${B.borderSubtle} 50%, ${B.bgElevated} 75%)`,
        backgroundSize: "200% 100%",
        animation: "shimmer 1.5s infinite",
      }}
    />
  );
}

/* ── AnimatedNumber ───────────────────────────────────────────────────── */

export function AnimatedNumber({
  value,
  decimals = 2,
  prefix = "",
  suffix = "",
  color = B.textPrimary,
  size = "text-xl",
}: {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  color?: string;
  size?: string;
}) {
  const prefersReduced = useReducedMotion();
  const spring = useSpring(0, { stiffness: 50, damping: 15 });
  const display = useTransform(spring, (v: number) => v.toFixed(decimals));
  const [text, setText] = useState(value.toFixed(decimals));

  useEffect(() => {
    if (prefersReduced) {
      setText(value.toFixed(decimals));
    } else {
      spring.set(value);
    }
  }, [value, decimals, spring, prefersReduced]);

  useEffect(() => {
    if (prefersReduced) return;
    const unsub = display.on("change", (v: string) => setText(v));
    return unsub;
  }, [display, prefersReduced]);

  return (
    <span className={`font-bold ${size}`} style={{ color, fontFamily: FONT.mono }}>
      {prefix}{text}{suffix}
    </span>
  );
}

/* ── OperationBadge ───────────────────────────────────────────────────── */

export const OperationBadge = memo(function OperationBadge({
  operation,
  size = "sm",
}: {
  operation: OperationType;
  size?: "sm" | "md";
}) {
  const isWrap = operation === "wrap";
  const color = isWrap ? B.glowGold : B.glowViolet;
  const fontSize = size === "md" ? "0.75rem" : "0.625rem";
  const label = isWrap ? "WRAP ▼" : "UNWRAP ▲";

  return (
    <span
      className="inline-flex items-center rounded px-2 py-0.5 font-bold tracking-wider"
      style={{ fontSize, color, background: `${color}15`, fontFamily: FONT.display }}
    >
      {label}
    </span>
  );
});

/* ── Panel ─────────────────────────────────────────────────────────────── */

export function Panel({
  children,
  className = "",
  accent,
  style: extraStyle,
}: {
  children: React.ReactNode;
  className?: string;
  accent?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={`rounded-xl p-4 ${className}`}
      style={{
        ...panelStyle,
        borderColor: accent ? `${accent}40` : B.borderSubtle,
        ...extraStyle,
      }}
    >
      {children}
    </div>
  );
}

/* ── SectionHeader ────────────────────────────────────────────────────── */

export function SectionHeader({
  title,
  action,
}: {
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h3
        className="text-[10px] font-bold uppercase tracking-[0.15em]"
        style={{ color: B.textSecondary, fontFamily: FONT.display }}
      >
        {title}
      </h3>
      {action}
    </div>
  );
}

/* ── ExternalLink Button ──────────────────────────────────────────────── */

export function ExtLink({ href, label }: { href: string; label?: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-[10px] transition-opacity hover:opacity-80"
      style={{ color: B.glowCyan, fontFamily: FONT.mono }}
    >
      {label ?? "View"}
      <ExternalLink size={10} />
    </a>
  );
}

/* ── GlowButton ───────────────────────────────────────────────────────── */

export function GlowButton({
  children,
  onClick,
  disabled = false,
  color = B.glowCyan,
  variant = "primary",
  className = "",
  style: extraStyle,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  color?: string;
  variant?: "primary" | "secondary" | "ghost";
  className?: string;
  style?: React.CSSProperties;
}) {
  const isPrimary = variant === "primary";

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center justify-center gap-2 rounded-lg px-6 font-bold tracking-wider transition-all ${className}`}
      style={{
        height: isPrimary ? 56 : 40,
        background: disabled
          ? `${B.borderSubtle}`
          : isPrimary
            ? color
            : variant === "ghost"
              ? "transparent"
              : `${color}15`,
        color: disabled
          ? B.textSecondary
          : isPrimary
            ? B.bgBase
            : color,
        border: variant === "ghost" ? `1px solid ${B.borderSubtle}` : "none",
        fontFamily: FONT.display,
        fontSize: isPrimary ? "0.8rem" : "0.7rem",
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? "not-allowed" : "pointer",
        boxShadow: !disabled && isPrimary ? `0 0 20px ${color}40` : "none",
        ...extraStyle,
      }}
    >
      {children}
    </button>
  );
}

/* ── CSS Injection ────────────────────────────────────────────────────── */

export function BridgeStyles() {
  return (
    <style>{`
      @keyframes shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
      }
      @keyframes ticker-scroll {
        0% { transform: translateX(0); }
        100% { transform: translateX(-50%); }
      }
      @keyframes pulse-glow {
        0%, 100% { box-shadow: 0 0 8px rgba(0, 212, 255, 0.3); }
        50% { box-shadow: 0 0 20px rgba(0, 212, 255, 0.6); }
      }
      .bridge-ticker {
        animation: ticker-scroll 60s linear infinite;
      }
      .bridge-ticker:hover {
        animation-play-state: paused;
      }
      .glow-pulse {
        animation: pulse-glow 2s ease-in-out infinite;
      }
    `}</style>
  );
}
