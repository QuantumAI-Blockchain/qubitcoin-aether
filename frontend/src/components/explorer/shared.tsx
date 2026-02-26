"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Shared / Reusable Components
   ───────────────────────────────────────────────────────────────────────── */

import { motion } from "framer-motion";
import {
  Search,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  ArrowUpRight,
  ExternalLink,
  Shield,
  Cpu,
  Boxes,
  Brain,
  Activity,
  BarChart3,
  Compass,
  Trophy,
  Wallet,
  Settings,
  X,
} from "lucide-react";
import { useState, useCallback, useRef, useEffect } from "react";
import type { ViewType } from "./types";
import { useExplorerStore } from "./store";

/* ── Design Tokens (inline — no external CSS file needed) ─────────────── */

export const C = {
  bg: "#020408",
  surface: "#0a0e18",
  surfaceLight: "#111827",
  border: "#1a2744",
  borderLight: "#243352",
  primary: "#00d4ff",
  primaryDim: "#0080aa",
  secondary: "#7c3aed",
  accent: "#f59e0b",
  success: "#00ff88",
  error: "#ef4444",
  warning: "#f59e0b",
  textPrimary: "#e2e8f0",
  textSecondary: "#64748b",
  textMuted: "#475569",
  quantum: "#00d4ff",
  susy: "#7c3aed",
  phi: "#f59e0b",
} as const;

export const FONT = {
  heading: "'Orbitron', sans-serif",
  mono: "'Share Tech Mono', monospace",
  body: "'Exo 2', sans-serif",
} as const;

/* ── Utilities ────────────────────────────────────────────────────────── */

export function truncHash(hash: string, len: number = 8): string {
  if (hash.length <= len * 2 + 3) return hash;
  return hash.slice(0, len) + "…" + hash.slice(-len);
}

export function formatQBC(value: number): string {
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(2) + "M";
  if (value >= 1_000) return (value / 1_000).toFixed(2) + "K";
  return value.toFixed(4);
}

export function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

export function timeAgo(ts: number): string {
  const now = Date.now() / 1000;
  const diff = now - ts;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function txTypeColor(type: string): string {
  switch (type) {
    case "coinbase": return C.success;
    case "transfer": return C.primary;
    case "contract_deploy": return C.secondary;
    case "contract_call": return C.accent;
    case "susy_swap": return "#a855f7";
    case "bridge": return "#ec4899";
    default: return C.textSecondary;
  }
}

export function txTypeBadge(type: string): string {
  switch (type) {
    case "coinbase": return "COINBASE";
    case "transfer": return "TRANSFER";
    case "contract_deploy": return "DEPLOY";
    case "contract_call": return "CALL";
    case "susy_swap": return "SUSY SWAP";
    case "bridge": return "BRIDGE";
    default: return type.toUpperCase();
  }
}

/* ── NavItem ──────────────────────────────────────────────────────────── */

const NAV_ITEMS: { view: ViewType; icon: typeof Boxes; label: string }[] = [
  { view: "dashboard", icon: Activity, label: "Dashboard" },
  { view: "qvm", icon: Cpu, label: "QVM" },
  { view: "aether", icon: Brain, label: "Aether" },
  { view: "leaderboard", icon: Trophy, label: "SUSY" },
  { view: "metrics", icon: BarChart3, label: "Metrics" },
  { view: "pathfinder", icon: Compass, label: "Pathfinder" },
];

/* ── Header ───────────────────────────────────────────────────────────── */

export function ExplorerHeader() {
  const { route, navigate, setSearchOpen, searchOpen, toggleDevTools } =
    useExplorerStore();
  const [localQuery, setLocalQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (localQuery.trim().length >= 2) {
        navigate("search", { q: localQuery.trim() });
        setSearchOpen(false);
      }
    },
    [localQuery, navigate, setSearchOpen]
  );

  // Keyboard shortcut: / to focus search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "/" && !searchOpen && document.activeElement?.tagName !== "INPUT") {
        e.preventDefault();
        setSearchOpen(true);
        setTimeout(() => inputRef.current?.focus(), 50);
      }
      if (e.key === "Escape") setSearchOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [searchOpen, setSearchOpen]);

  return (
    <header
      className="sticky top-0 z-50 flex items-center gap-3 border-b px-4 py-2"
      style={{
        background: `${C.bg}ee`,
        borderColor: C.border,
        backdropFilter: "blur(12px)",
        fontFamily: FONT.body,
      }}
    >
      {/* Back to site */}
      <a
        href="/"
        className="flex items-center gap-0.5 rounded-md px-1.5 py-1.5 text-xs transition-opacity hover:opacity-80"
        style={{ color: C.textSecondary, fontFamily: FONT.body }}
        title="Back to QBC"
      >
        <ChevronLeft size={14} />
      </a>

      {/* Logo */}
      <button
        onClick={() => navigate("dashboard")}
        className="mr-2 flex items-center gap-2"
        style={{ fontFamily: FONT.heading }}
      >
        <div
          className="flex h-7 w-7 items-center justify-center rounded-md text-xs font-bold"
          style={{ background: C.primary, color: C.bg }}
        >
          Q
        </div>
        <span className="hidden text-sm font-semibold tracking-widest sm:inline" style={{ color: C.textPrimary }}>
          EXPLORER
        </span>
      </button>

      {/* Nav */}
      <nav className="flex items-center gap-1 overflow-x-auto">
        {NAV_ITEMS.map(({ view, icon: Icon, label }) => {
          const active = route.view === view;
          return (
            <button
              key={view}
              onClick={() => navigate(view)}
              className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs transition-colors"
              style={{
                color: active ? C.primary : C.textSecondary,
                background: active ? `${C.primary}15` : "transparent",
                fontFamily: FONT.body,
              }}
            >
              <Icon size={14} />
              <span className="hidden md:inline">{label}</span>
            </button>
          );
        })}
      </nav>

      {/* Search */}
      <div className="relative ml-auto flex items-center">
        {searchOpen ? (
          <form onSubmit={handleSearch} className="flex items-center gap-2">
            <input
              ref={inputRef}
              value={localQuery}
              onChange={(e) => setLocalQuery(e.target.value)}
              placeholder="Block, txid, address…"
              className="w-48 rounded-md border px-3 py-1.5 text-xs outline-none focus:border-[var(--qbc-primary)] sm:w-64"
              style={{
                background: C.surfaceLight,
                borderColor: C.border,
                color: C.textPrimary,
                fontFamily: FONT.mono,
              }}
              autoFocus
            />
            <button type="button" onClick={() => setSearchOpen(false)}>
              <X size={14} style={{ color: C.textSecondary }} />
            </button>
          </form>
        ) : (
          <button
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs transition-opacity hover:opacity-80"
            style={{ color: C.textSecondary }}
          >
            <Search size={14} />
            <span className="hidden sm:inline" style={{ fontFamily: FONT.mono }}>
              /
            </span>
          </button>
        )}
      </div>

      {/* DevTools toggle */}
      <button
        onClick={toggleDevTools}
        className="rounded-md p-1.5 transition-opacity hover:opacity-80"
        style={{ color: C.textSecondary }}
        title="DevTools (Ctrl+Shift+D)"
      >
        <Settings size={14} />
      </button>
    </header>
  );
}

/* ── StatCard ─────────────────────────────────────────────────────────── */

export function StatCard({
  label,
  value,
  sub,
  color = C.primary,
  icon: Icon,
  onClick,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
  icon?: typeof Activity;
  onClick?: () => void;
}) {
  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -2 }}
      onClick={onClick}
      className="flex flex-col gap-1 rounded-lg border p-3"
      style={{
        background: C.surface,
        borderColor: C.border,
        cursor: onClick ? "pointer" : "default",
      }}
    >
      <div className="flex items-center justify-between">
        <span
          className="text-[10px] uppercase tracking-widest"
          style={{ color: C.textMuted, fontFamily: FONT.heading }}
        >
          {label}
        </span>
        {Icon && <Icon size={14} style={{ color: `${color}80` }} />}
      </div>
      <span
        className="text-xl font-bold"
        style={{ color, fontFamily: FONT.mono }}
      >
        {typeof value === "number" ? formatNumber(value) : value}
      </span>
      {sub && (
        <span className="text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
          {sub}
        </span>
      )}
    </motion.div>
  );
}

/* ── Badge ────────────────────────────────────────────────────────────── */

export function Badge({
  label,
  color = C.primary,
}: {
  label: string;
  color?: string;
}) {
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wider"
      style={{
        color,
        background: `${color}18`,
        fontFamily: FONT.heading,
      }}
    >
      {label}
    </span>
  );
}

/* ── CopyButton ───────────────────────────────────────────────────────── */

export function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className="rounded p-0.5 transition-opacity hover:opacity-80"
      title="Copy"
    >
      {copied ? (
        <Check size={12} style={{ color: C.success }} />
      ) : (
        <Copy size={12} style={{ color: C.textSecondary }} />
      )}
    </button>
  );
}

/* ── HashLink — clickable hash that navigates ─────────────────────────── */

export function HashLink({
  hash,
  type,
  truncLen = 8,
}: {
  hash: string;
  type: "block" | "transaction" | "wallet" | "contract";
  truncLen?: number;
}) {
  const navigate = useExplorerStore((s) => s.navigate);

  const viewMap: Record<string, ViewType> = {
    block: "block",
    transaction: "transaction",
    wallet: "wallet",
    contract: "qvm",
  };

  return (
    <button
      onClick={() => navigate(viewMap[type] ?? "dashboard", { id: hash })}
      className="inline-flex items-center gap-1 transition-opacity hover:opacity-80"
      style={{ color: C.primary, fontFamily: FONT.mono, fontSize: "0.75rem" }}
    >
      {truncHash(hash, truncLen)}
      <ArrowUpRight size={10} />
    </button>
  );
}

/* ── BackButton ───────────────────────────────────────────────────────── */

export function BackButton() {
  const goBack = useExplorerStore((s) => s.goBack);
  return (
    <button
      onClick={goBack}
      className="flex items-center gap-1 text-xs transition-opacity hover:opacity-80"
      style={{ color: C.textSecondary, fontFamily: FONT.body }}
    >
      <ChevronLeft size={14} />
      Back
    </button>
  );
}

/* ── DataTable ────────────────────────────────────────────────────────── */

export function DataTable<T>({
  columns,
  data,
  keyFn,
  onRowClick,
  emptyMessage = "No data",
}: {
  columns: {
    key: string;
    header: string;
    render: (row: T) => React.ReactNode;
    align?: "left" | "right" | "center";
    width?: string;
  }[];
  data: T[];
  keyFn: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border" style={{ borderColor: C.border }}>
      <table className="w-full text-xs" style={{ fontFamily: FONT.mono }}>
        <thead>
          <tr style={{ background: C.surface }}>
            {columns.map((col) => (
              <th
                key={col.key}
                className="px-3 py-2 text-left"
                style={{
                  color: C.textMuted,
                  fontFamily: FONT.heading,
                  fontSize: "0.625rem",
                  letterSpacing: "0.08em",
                  textAlign: col.align ?? "left",
                  width: col.width,
                }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-3 py-8 text-center"
                style={{ color: C.textMuted }}
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row) => (
              <tr
                key={keyFn(row)}
                onClick={() => onRowClick?.(row)}
                className="border-t transition-colors"
                style={{
                  borderColor: `${C.border}80`,
                  cursor: onRowClick ? "pointer" : "default",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = `${C.primary}08`)
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "transparent")
                }
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className="px-3 py-2"
                    style={{
                      color: C.textPrimary,
                      textAlign: col.align ?? "left",
                    }}
                  >
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

/* ── Pagination ───────────────────────────────────────────────────────── */

export function Pagination({
  page,
  totalPages,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  onPageChange: (p: number) => void;
}) {
  return (
    <div className="flex items-center justify-center gap-3 py-3">
      <button
        onClick={() => onPageChange(Math.max(0, page - 1))}
        disabled={page === 0}
        className="rounded-md p-1.5 transition-opacity disabled:opacity-30"
        style={{ color: C.textSecondary }}
      >
        <ChevronLeft size={14} />
      </button>
      <span className="text-xs" style={{ color: C.textSecondary, fontFamily: FONT.mono }}>
        {page + 1} / {totalPages}
      </span>
      <button
        onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
        disabled={page >= totalPages - 1}
        className="rounded-md p-1.5 transition-opacity disabled:opacity-30"
        style={{ color: C.textSecondary }}
      >
        <ChevronRight size={14} />
      </button>
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
      <h2
        className="text-sm font-bold tracking-widest"
        style={{ color: C.textPrimary, fontFamily: FONT.heading }}
      >
        {title}
      </h2>
      {action}
    </div>
  );
}

/* ── Loading Spinner ──────────────────────────────────────────────────── */

export function LoadingSpinner({ size = 24 }: { size?: number }) {
  return (
    <div className="flex items-center justify-center p-8">
      <div
        className="animate-spin rounded-full border-2"
        style={{
          width: size,
          height: size,
          borderColor: C.border,
          borderTopColor: C.primary,
        }}
      />
    </div>
  );
}

/* ── Panel wrapper ────────────────────────────────────────────────────── */

export function Panel({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-lg border p-4 ${className}`}
      style={{ background: C.surface, borderColor: C.border }}
    >
      {children}
    </div>
  );
}
