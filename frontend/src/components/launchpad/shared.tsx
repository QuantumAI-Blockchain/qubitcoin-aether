// ─── QBC LAUNCHPAD — Shared Design Tokens, Utilities & Components ─────────────
"use client";

import React, { memo, useEffect, useState } from "react";
import type {
  ProjectTier,
  QpcsGrade,
  ILLPSignal,
  EhgStatus,
  CommunityVerdict,
  TrancheStatus,
  PresaleStatus,
  ContractType,
} from "./types";

/* ── Design Tokens ────────────────────────────────────────────────────────── */

export const L = {
  // backgrounds
  bgBase: "#020408",
  bgPanel: "#040c14",
  bgSurface: "#081018",
  bgHover: "#0c1824",
  bgInput: "#06101a",
  bgModal: "rgba(0,0,0,0.85)",

  // borders
  borderSubtle: "#0d2137",
  borderMedium: "#143050",
  borderFocus: "#00d4ff",

  // text
  textPrimary: "#e2e8f0",
  textSecondary: "#64748b",
  textMuted: "#475569",
  textInverse: "#020408",

  // tier colours
  tierProtocol: "#00d4ff",
  tierEstablished: "#f59e0b",
  tierGrowth: "#10b981",
  tierEarly: "#8b5cf6",
  tierSeed: "#64748b",

  // QPCS grade colours
  gradeQuantum: "#00d4ff",
  gradeVerified: "#10b981",
  gradeBasic: "#f59e0b",
  gradeRestricted: "#ef4444",
  gradeRejected: "#6b7280",

  // accents
  glowCyan: "#00d4ff",
  glowGold: "#f59e0b",
  glowViolet: "#8b5cf6",
  glowEmerald: "#10b981",
  glowRed: "#ef4444",

  // community verdict
  verdictVerified: "#10b981",
  verdictFlagged: "#ef4444",
  verdictReview: "#f59e0b",

  // ILLP signals
  illpProhibited: "#ef4444",
  illpIrrational: "#ef4444",
  illpShortTerm: "#f97316",
  illpMinimum: "#f59e0b",
  illpAcceptable: "#eab308",
  illpRecommended: "#10b981",
  illpExcellent: "#00d4ff",
  illpProtocol: "#8b5cf6",

  // DNA helix colours (from 2-bit hash values)
  dnaCyan: "#00d4ff",
  dnaGold: "#f59e0b",
  dnaViolet: "#8b5cf6",
  dnaEmerald: "#10b981",

  // misc
  success: "#22c55e",
  warning: "#f59e0b",
  error: "#ef4444",
  info: "#00d4ff",
} as const;

export const FONT = {
  display: "'Orbitron', sans-serif",
  mono: "'Share Tech Mono', monospace",
  body: "'Exo 2', sans-serif",
} as const;

/* ── Utility Functions ────────────────────────────────────────────────────── */

export function formatNumber(n: number, decimals = 0): string {
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + "B";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toFixed(decimals);
}

export function formatUsd(n: number): string {
  if (n >= 1_000_000) return "$" + (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1_000) return "$" + (n / 1_000).toFixed(1) + "K";
  return "$" + n.toFixed(2);
}

export function formatQbc(n: number): string {
  return n.toFixed(2) + " QBC";
}

export function formatQusd(n: number): string {
  return formatUsd(n) + " QUSD";
}

export function formatPct(n: number): string {
  const sign = n >= 0 ? "+" : "";
  return sign + n.toFixed(2) + "%";
}

export function formatAddr(addr: string, chars = 6): string {
  if (addr.length <= chars * 2 + 3) return addr;
  return addr.slice(0, chars) + "..." + addr.slice(-chars);
}

export function timeAgo(ts: number): string {
  const diff = Math.floor(Date.now() / 1000 - ts);
  if (diff < 60) return diff + "s ago";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  return Math.floor(diff / 86400) + "d ago";
}

export function daysRemaining(expiryTs: number): number {
  return Math.max(0, Math.floor((expiryTs - Date.now() / 1000) / 86400));
}

export function tierColor(tier: ProjectTier): string {
  const map: Record<ProjectTier, string> = {
    protocol: L.tierProtocol,
    established: L.tierEstablished,
    growth: L.tierGrowth,
    early: L.tierEarly,
    seed: L.tierSeed,
  };
  return map[tier];
}

export function tierIcon(tier: ProjectTier): string {
  const map: Record<ProjectTier, string> = {
    protocol: "\u26A1",
    established: "\uD83C\uDFDB\uFE0F",
    growth: "\uD83C\uDF33",
    early: "\uD83C\uDF31",
    seed: "\uD83E\uDEB4",
  };
  return map[tier];
}

export function tierLabel(tier: ProjectTier): string {
  return tier.charAt(0).toUpperCase() + tier.slice(1);
}

export function gradeColor(grade: QpcsGrade): string {
  const map: Record<QpcsGrade, string> = {
    quantum_grade: L.gradeQuantum,
    verified: L.gradeVerified,
    basic: L.gradeBasic,
    restricted: L.gradeRestricted,
    rejected: L.gradeRejected,
  };
  return map[grade];
}

export function gradeLabel(grade: QpcsGrade): string {
  const map: Record<QpcsGrade, string> = {
    quantum_grade: "QUANTUM GRADE",
    verified: "VERIFIED",
    basic: "BASIC",
    restricted: "RESTRICTED",
    rejected: "REJECTED",
  };
  return map[grade];
}

export function illpColor(signal: ILLPSignal): string {
  const map: Record<ILLPSignal, string> = {
    prohibited: L.illpProhibited,
    irrational: L.illpIrrational,
    short_term: L.illpShortTerm,
    minimum: L.illpMinimum,
    acceptable: L.illpAcceptable,
    recommended: L.illpRecommended,
    excellent: L.illpExcellent,
    protocol_grade: L.illpProtocol,
  };
  return map[signal];
}

export function illpLabel(signal: ILLPSignal): string {
  return signal.replace(/_/g, " ").toUpperCase();
}

export function verdictColor(v: CommunityVerdict): string {
  const map: Record<CommunityVerdict, string> = {
    verified: L.verdictVerified,
    flagged: L.verdictFlagged,
    under_review: L.verdictReview,
    no_reports: L.textMuted,
  };
  return map[v];
}

export function verdictLabel(v: CommunityVerdict): string {
  const map: Record<CommunityVerdict, string> = {
    verified: "COMMUNITY VERIFIED",
    flagged: "COMMUNITY FLAGGED",
    under_review: "UNDER REVIEW",
    no_reports: "NO REPORTS",
  };
  return map[v];
}

export function ehgColor(s: EhgStatus): string {
  const map: Record<EhgStatus, string> = { optimal: L.success, degraded: L.warning, critical: L.error };
  return map[s];
}

export function contractTypeLabel(t: ContractType): string {
  const map: Record<ContractType, string> = {
    susy_governance: "SUSY-Staked Governance",
    governance: "Governance",
    vesting_reflection: "Vesting + Reflection",
    fixed_governance: "Fixed Supply + Governance",
    vesting: "Vesting",
    qrc20_standard: "QRC-20 Standard",
    deflationary: "Deflationary",
    fair_launch: "Fair Launch",
  };
  return map[t];
}

export function calculateILLP(lockDays: number): {
  feeQusd: number;
  signal: ILLPSignal;
  qpcsImpact: number;
} {
  if (lockDays < 30)
    return { feeQusd: 999999, signal: "prohibited", qpcsImpact: 0 };
  if (lockDays < 90)
    return { feeQusd: 5000, signal: "irrational", qpcsImpact: 2 };
  if (lockDays < 180)
    return { feeQusd: 2000, signal: "short_term", qpcsImpact: 5 };
  if (lockDays < 365)
    return { feeQusd: 500, signal: "minimum", qpcsImpact: 10 };
  if (lockDays < 730)
    return { feeQusd: 200, signal: "acceptable", qpcsImpact: 15 };
  if (lockDays < 1095)
    return { feeQusd: 50, signal: "recommended", qpcsImpact: 20 };
  if (lockDays < 1460)
    return { feeQusd: 10, signal: "excellent", qpcsImpact: 23 };
  return { feeQusd: 0, signal: "protocol_grade", qpcsImpact: 25 };
}

/* ── Panel Style ──────────────────────────────────────────────────────────── */

export const panelStyle: React.CSSProperties = {
  background: L.bgPanel,
  border: `1px solid ${L.borderSubtle}`,
  borderRadius: 8,
};

export const inputStyle: React.CSSProperties = {
  background: L.bgInput,
  border: `1px solid ${L.borderSubtle}`,
  borderRadius: 6,
  color: L.textPrimary,
  fontFamily: FONT.body,
  fontSize: 13,
  padding: "8px 12px",
  width: "100%",
  outline: "none",
};

/* ── Shared Small Components ──────────────────────────────────────────────── */

export const TierBadge = memo(function TierBadge({
  tier,
  size = "sm",
}: {
  tier: ProjectTier;
  size?: "xs" | "sm" | "md";
}) {
  const color = tierColor(tier);
  const icon = tierIcon(tier);
  const label = tierLabel(tier);
  const fontSize = size === "xs" ? 9 : size === "sm" ? 10 : 12;
  const pad = size === "xs" ? "2px 6px" : size === "sm" ? "3px 8px" : "4px 12px";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontFamily: FONT.display,
        fontSize,
        letterSpacing: "0.05em",
        color,
        border: `1px solid ${color}40`,
        borderRadius: 4,
        padding: pad,
        textTransform: "uppercase",
      }}
    >
      {icon} {label}
    </span>
  );
});

export const QpcsGradeBadge = memo(function QpcsGradeBadge({
  grade,
  score,
}: {
  grade: QpcsGrade;
  score: number;
}) {
  const color = gradeColor(grade);
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontFamily: FONT.display,
        fontSize: 10,
        letterSpacing: "0.05em",
        color,
        border: `1px solid ${color}40`,
        borderRadius: 4,
        padding: "3px 8px",
        textTransform: "uppercase",
      }}
    >
      {score.toFixed(1)} {gradeLabel(grade)}
    </span>
  );
});

export const VerdictBadge = memo(function VerdictBadge({
  verdict,
}: {
  verdict: CommunityVerdict;
}) {
  const color = verdictColor(verdict);
  const icons: Record<CommunityVerdict, string> = {
    verified: "\u2713",
    flagged: "\uD83D\uDD34",
    under_review: "\uD83D\uDFE1",
    no_reports: "",
  };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontFamily: FONT.display,
        fontSize: 9,
        letterSpacing: "0.04em",
        color,
        textTransform: "uppercase",
      }}
    >
      {icons[verdict]} {verdictLabel(verdict)}
    </span>
  );
});

export const EhgBadge = memo(function EhgBadge({ status }: { status: EhgStatus }) {
  const color = ehgColor(status);
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontFamily: FONT.display,
        fontSize: 9,
        letterSpacing: "0.04em",
        color,
        textTransform: "uppercase",
      }}
    >
      {"\u2B21"} EHG: {status.toUpperCase()}
    </span>
  );
});

export const TrancheStatusBadge = memo(function TrancheStatusBadge({
  status,
}: {
  status: TrancheStatus;
}) {
  const colors: Record<TrancheStatus, string> = {
    locked: L.error,
    unlocked: L.warning,
    released: L.success,
  };
  return (
    <span
      style={{
        fontFamily: FONT.display,
        fontSize: 9,
        color: colors[status],
        textTransform: "uppercase",
        letterSpacing: "0.04em",
      }}
    >
      {status}
    </span>
  );
});

export const PresaleStatusBadge = memo(function PresaleStatusBadge({
  status,
}: {
  status: PresaleStatus;
}) {
  const colors: Record<PresaleStatus, string> = {
    upcoming: L.info,
    active: L.success,
    completed: L.textSecondary,
    failed: L.error,
  };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontFamily: FONT.display,
        fontSize: 9,
        color: colors[status],
        textTransform: "uppercase",
        letterSpacing: "0.04em",
      }}
    >
      {status === "active" && "\uD83D\uDD34"} {status}
    </span>
  );
});

export const CopyButton = memo(function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button
      onClick={handleCopy}
      style={{
        background: "none",
        border: "none",
        color: copied ? L.success : L.textSecondary,
        cursor: "pointer",
        fontFamily: FONT.mono,
        fontSize: 10,
        padding: "2px 4px",
      }}
    >
      {copied ? "\u2713" : "\u2398"}
    </button>
  );
});

export const SkeletonLoader = memo(function SkeletonLoader({
  width = "100%",
  height = 20,
}: {
  width?: number | string;
  height?: number;
}) {
  return (
    <div
      className="launchpad-shimmer"
      style={{
        width,
        height,
        borderRadius: 4,
        background: `linear-gradient(90deg, ${L.bgPanel}, ${L.bgHover}, ${L.bgPanel})`,
        backgroundSize: "200% 100%",
      }}
    />
  );
});

export const ProgressBar = memo(function ProgressBar({
  value,
  max = 100,
  color = L.glowCyan,
  height = 6,
}: {
  value: number;
  max?: number;
  color?: string;
  height?: number;
}) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div
      style={{
        width: "100%",
        height,
        borderRadius: height / 2,
        background: L.bgBase,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${pct}%`,
          height: "100%",
          borderRadius: height / 2,
          background: color,
          transition: "width 0.4s ease",
          boxShadow: `0 0 8px ${color}40`,
        }}
      />
    </div>
  );
});

export const CountdownTimer = memo(function CountdownTimer({
  targetTs,
}: {
  targetTs: number;
}) {
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(id);
  }, []);
  const diff = Math.max(0, Math.floor(targetTs - now));
  const d = Math.floor(diff / 86400);
  const h = Math.floor((diff % 86400) / 3600);
  const m = Math.floor((diff % 3600) / 60);
  const s = diff % 60;
  return (
    <span style={{ fontFamily: FONT.mono, fontSize: 12, color: L.glowCyan }}>
      {d > 0 && `${d}d `}{h.toString().padStart(2, "0")}:{m.toString().padStart(2, "0")}:{s.toString().padStart(2, "0")}
    </span>
  );
});

/* ── CSS Injection ────────────────────────────────────────────────────────── */

if (typeof document !== "undefined") {
  const id = "launchpad-css";
  if (!document.getElementById(id)) {
    const style = document.createElement("style");
    style.id = id;
    style.textContent = `
      @keyframes launchpadShimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
      }
      .launchpad-shimmer {
        animation: launchpadShimmer 1.5s ease-in-out infinite;
      }
      @keyframes tierGlow {
        0%, 100% { opacity: 0.5; }
        50% { opacity: 1; }
      }
      .tier-glow-pulse {
        animation: tierGlow 2s ease-in-out infinite;
      }
      @keyframes presalePulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(245,158,11,0.3); }
        50% { box-shadow: 0 0 20px 4px rgba(245,158,11,0.15); }
      }
      .presale-pulse {
        animation: presalePulse 2s ease-in-out infinite;
      }
      .launchpad-scroll::-webkit-scrollbar { width: 4px; height: 4px; }
      .launchpad-scroll::-webkit-scrollbar-track { background: transparent; }
      .launchpad-scroll::-webkit-scrollbar-thumb { background: ${L.borderSubtle}; border-radius: 2px; }
      .launchpad-scroll::-webkit-scrollbar-thumb:hover { background: ${L.borderMedium}; }
    `;
    document.head.appendChild(style);
  }
}
