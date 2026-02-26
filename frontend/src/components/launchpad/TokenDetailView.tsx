// ─── QBC LAUNCHPAD — Token Detail View (6 Tabs) ──────────────────────────────
"use client";

import React, { memo, useMemo, useCallback } from "react";
import { useProject } from "./hooks";
import { useLaunchpadStore } from "./store";
import {
  TierBadge,
  VerdictBadge,
  QpcsGradeBadge,
  EhgBadge,
  CopyButton,
  ProgressBar,
  TrancheStatusBadge,
  CountdownTimer,
  formatNumber,
  formatUsd,
  formatPct,
  formatAddr,
  timeAgo,
  daysRemaining,
  tierColor,
  illpColor,
  illpLabel,
  L,
  FONT,
  panelStyle,
} from "./shared";
import DNAFingerprint from "./DNAFingerprint";
import QPCSGauge from "./QPCSGauge";
import { QPCS_WEIGHTS, TIER_CONFIGS, DD_CATEGORIES } from "./config";
import type {
  Project,
  ProjectTier,
  QPCSComponents,
  DDReport,
  Vouch,
  MGTTranche,
  VestingSchedule,
  AllocationItem,
} from "./types";

/* ── Constants ────────────────────────────────────────────────────────────── */

const TABS = [
  { key: "overview", label: "OVERVIEW" },
  { key: "mechanics", label: "MECHANICS" },
  { key: "qpcs", label: "QPCS" },
  { key: "graduation", label: "GRADUATION" },
  { key: "cdd", label: "COMMUNITY DD" },
  { key: "vouches", label: "VOUCHES" },
] as const;

const TIER_ORDER: ProjectTier[] = ["seed", "early", "growth", "established", "protocol"];

const COMPONENT_KEYS: Array<keyof QPCSComponents> = [
  "liquidityLock",
  "teamVesting",
  "tokenomicsDistribution",
  "contractComplexity",
  "presaleStructure",
  "deployerHistory",
  "socialVerification",
  "susyAtDeploy",
];

const COMPONENT_COLORS: Record<keyof QPCSComponents, string> = {
  liquidityLock: L.glowCyan,
  teamVesting: L.glowGold,
  tokenomicsDistribution: L.glowEmerald,
  contractComplexity: L.glowViolet,
  presaleStructure: "#ec4899",
  deployerHistory: "#06b6d4",
  socialVerification: "#84cc16",
  susyAtDeploy: "#f97316",
};

const IMPROVEMENT_MAP: Record<keyof QPCSComponents, string> = {
  liquidityLock: "Extend liquidity lock duration for higher QPCS",
  teamVesting: "Add cliff + linear vesting for team tokens",
  tokenomicsDistribution: "Improve distribution across more wallet categories",
  contractComplexity: "Upgrade to a more advanced contract template",
  presaleStructure: "Add a structured presale with vesting requirements",
  deployerHistory: "Build deployer reputation by launching successful projects",
  socialVerification: "Complete social verification (Twitter, Discord, Telegram)",
  susyAtDeploy: "Deploy when SUSY alignment is highest for bonus points",
};

/* ── Inline SVG line chart ────────────────────────────────────────────────── */

const MiniLineChart = memo(function MiniLineChart({
  data,
  width,
  height,
  color,
  showArea,
}: {
  data: Array<{ x: number; y: number }>;
  width: number;
  height: number;
  color: string;
  showArea?: boolean;
}) {
  if (data.length < 2) return null;

  const xs = data.map((d) => d.x);
  const ys = data.map((d) => d.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;
  const pad = 4;
  const cw = width - pad * 2;
  const ch = height - pad * 2;

  const points = data.map((d) => {
    const px = pad + ((d.x - minX) / rangeX) * cw;
    const py = pad + ch - ((d.y - minY) / rangeY) * ch;
    return `${px},${py}`;
  });

  const pathD = `M${points.join(" L")}`;
  const areaD = `${pathD} L${pad + cw},${pad + ch} L${pad},${pad + ch} Z`;

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {showArea && (
        <path d={areaD} fill={color} opacity={0.08} />
      )}
      <path d={pathD} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
      {/* Last point dot */}
      {data.length > 0 && (
        <circle
          cx={parseFloat(points[points.length - 1].split(",")[0])}
          cy={parseFloat(points[points.length - 1].split(",")[1])}
          r={3}
          fill={color}
          filter={`drop-shadow(0 0 3px ${color})`}
        />
      )}
      {/* Min/Max labels */}
      <text
        x={pad}
        y={pad + ch + 2}
        fill={L.textMuted}
        fontFamily={FONT.mono}
        fontSize={8}
        dominantBaseline="hanging"
      >
        {formatUsd(minY)}
      </text>
      <text
        x={width - pad}
        y={pad + ch + 2}
        fill={L.textMuted}
        fontFamily={FONT.mono}
        fontSize={8}
        textAnchor="end"
        dominantBaseline="hanging"
      >
        {formatUsd(maxY)}
      </text>
    </svg>
  );
});

/* ── DD Category Badge ────────────────────────────────────────────────────── */

const DDCategoryBadge = memo(function DDCategoryBadge({ category }: { category: string }) {
  const cfg = DD_CATEGORIES.find((c) => c.key === category);
  return (
    <span
      style={{
        fontFamily: FONT.display,
        fontSize: 9,
        color: L.glowCyan,
        border: `1px solid ${L.glowCyan}30`,
        borderRadius: 3,
        padding: "2px 6px",
        textTransform: "uppercase",
        letterSpacing: "0.04em",
      }}
    >
      {cfg?.icon ?? ""} {cfg?.label ?? category}
    </span>
  );
});

/* ── Outcome Badge ────────────────────────────────────────────────────────── */

const OutcomeBadge = memo(function OutcomeBadge({
  outcome,
}: {
  outcome: "verified" | "flagged" | "neutral" | "pending";
}) {
  const colors: Record<string, string> = {
    verified: L.success,
    flagged: L.error,
    neutral: L.warning,
    pending: L.textMuted,
  };
  return (
    <span
      style={{
        fontFamily: FONT.display,
        fontSize: 9,
        color: colors[outcome] ?? L.textMuted,
        textTransform: "uppercase",
        letterSpacing: "0.04em",
      }}
    >
      {outcome}
    </span>
  );
});

/* ── Vote Bar ─────────────────────────────────────────────────────────────── */

const VoteBar = memo(function VoteBar({
  positive,
  negative,
}: {
  positive: number;
  negative: number;
}) {
  const total = positive + negative;
  const posPct = total > 0 ? (positive / total) * 100 : 50;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, width: "100%" }}>
      <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.success, width: 30, textAlign: "right" }}>
        {positive}
      </span>
      <div
        style={{
          flex: 1,
          height: 4,
          borderRadius: 2,
          background: L.error,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${posPct}%`,
            height: "100%",
            borderRadius: 2,
            background: L.success,
          }}
        />
      </div>
      <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.error, width: 30 }}>
        {negative}
      </span>
    </div>
  );
});

/* ── Vouch Status Badge ───────────────────────────────────────────────────── */

const VouchStatusBadge = memo(function VouchStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: L.success,
    completed_success: L.glowCyan,
    slashed: L.error,
    withdrawn: L.textMuted,
  };
  const labels: Record<string, string> = {
    active: "ACTIVE",
    completed_success: "SUCCESS",
    slashed: "SLASHED",
    withdrawn: "WITHDRAWN",
  };
  return (
    <span
      style={{
        fontFamily: FONT.display,
        fontSize: 9,
        color: colors[status] ?? L.textMuted,
        textTransform: "uppercase",
        letterSpacing: "0.04em",
      }}
    >
      {labels[status] ?? status}
    </span>
  );
});

/* ── Section Header ───────────────────────────────────────────────────────── */

const SectionHeader = memo(function SectionHeader({ text }: { text: string }) {
  return (
    <h3
      style={{
        fontFamily: FONT.display,
        fontSize: 12,
        color: L.textPrimary,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        margin: 0,
        paddingBottom: 8,
        borderBottom: `1px solid ${L.borderSubtle}`,
      }}
    >
      {text}
    </h3>
  );
});

/* ── Tab: OVERVIEW ────────────────────────────────────────────────────────── */

const OverviewTab = memo(function OverviewTab({ p }: { p: Project }) {
  const chartData = useMemo(
    () => p.priceHistory.map((ph) => ({ x: ph.time, y: ph.price })),
    [p.priceHistory],
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Price chart */}
      <div style={{ ...panelStyle, padding: 16 }}>
        <SectionHeader text="Price Chart (90D)" />
        <div style={{ marginTop: 12 }}>
          <MiniLineChart
            data={chartData}
            width={680}
            height={200}
            color={p.price24hChange >= 0 ? L.success : L.error}
            showArea
          />
        </div>
      </div>

      {/* About */}
      <div style={{ ...panelStyle, padding: 16 }}>
        <SectionHeader text="About" />
        <p
          style={{
            fontFamily: FONT.body,
            fontSize: 13,
            color: L.textSecondary,
            lineHeight: 1.6,
            margin: "12px 0 0 0",
            whiteSpace: "pre-line",
          }}
        >
          {p.fullDescription || p.description}
        </p>
      </div>

      {/* Links */}
      {(p.website || p.twitter || p.telegram || p.discord || p.github || p.whitepaper) && (
        <div style={{ ...panelStyle, padding: 16 }}>
          <SectionHeader text="Links" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 12 }}>
            {p.website && <LinkPill label="Website" href={p.website} />}
            {p.twitter && <LinkPill label="Twitter" href={p.twitter} />}
            {p.telegram && <LinkPill label="Telegram" href={p.telegram} />}
            {p.discord && <LinkPill label="Discord" href={p.discord} />}
            {p.github && <LinkPill label="GitHub" href={p.github} />}
            {p.whitepaper && <LinkPill label="Whitepaper" href={p.whitepaper} />}
          </div>
        </div>
      )}

      {/* Tokenomics */}
      <div style={{ ...panelStyle, padding: 16 }}>
        <SectionHeader text="Tokenomics" />
        <TokenomicsBar allocations={p.tokenomics} />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 12 }}>
          {p.tokenomics.map((a) => (
            <div key={a.label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: a.color }} />
              <span style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textSecondary }}>
                {a.label} {a.percent}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Top Holders */}
      <div style={{ ...panelStyle, padding: 16 }}>
        <SectionHeader text="Top Holders" />
        <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 12 }}>
          <thead>
            <tr>
              {["#", "ADDRESS", "BALANCE", "%"].map((h) => (
                <th
                  key={h}
                  style={{
                    fontFamily: FONT.display,
                    fontSize: 9,
                    color: L.textMuted,
                    textAlign: h === "#" ? "center" : "left",
                    padding: "4px 8px",
                    borderBottom: `1px solid ${L.borderSubtle}`,
                    letterSpacing: "0.05em",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {p.topHolders.map((h, i) => (
              <tr key={i}>
                <td
                  style={{
                    fontFamily: FONT.mono,
                    fontSize: 11,
                    color: L.textMuted,
                    textAlign: "center",
                    padding: "6px 8px",
                  }}
                >
                  {i + 1}
                </td>
                <td
                  style={{
                    fontFamily: FONT.mono,
                    fontSize: 11,
                    color: L.textPrimary,
                    padding: "6px 8px",
                  }}
                >
                  {formatAddr(h.address, 8)}
                </td>
                <td
                  style={{
                    fontFamily: FONT.mono,
                    fontSize: 11,
                    color: L.textSecondary,
                    padding: "6px 8px",
                  }}
                >
                  {formatNumber(h.balance)}
                </td>
                <td
                  style={{
                    fontFamily: FONT.mono,
                    fontSize: 11,
                    color: L.textSecondary,
                    padding: "6px 8px",
                  }}
                >
                  {h.percent.toFixed(2)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
});

/* ── Tokenomics stacked bar ───────────────────────────────────────────────── */

const TokenomicsBar = memo(function TokenomicsBar({
  allocations,
}: {
  allocations: AllocationItem[];
}) {
  return (
    <div
      style={{
        display: "flex",
        width: "100%",
        height: 14,
        borderRadius: 7,
        overflow: "hidden",
        marginTop: 12,
        background: L.bgBase,
      }}
    >
      {allocations.map((a) => (
        <div
          key={a.label}
          style={{
            width: `${a.percent}%`,
            height: "100%",
            background: a.color,
            transition: "width 0.3s ease",
          }}
          title={`${a.label}: ${a.percent}%`}
        />
      ))}
    </div>
  );
});

/* ── Link Pill ────────────────────────────────────────────────────────────── */

const LinkPill = memo(function LinkPill({ label, href }: { label: string; href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        fontFamily: FONT.mono,
        fontSize: 11,
        color: L.glowCyan,
        border: `1px solid ${L.glowCyan}30`,
        borderRadius: 4,
        padding: "4px 10px",
        textDecoration: "none",
        transition: "border-color 0.2s",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLAnchorElement).style.borderColor = L.glowCyan;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLAnchorElement).style.borderColor = `${L.glowCyan}30`;
      }}
    >
      {label}
    </a>
  );
});

/* ── Tab: MECHANICS ───────────────────────────────────────────────────────── */

const MechanicsTab = memo(function MechanicsTab({ p }: { p: Project }) {
  const lockRemaining = daysRemaining(p.liquidityLockExpiry);
  const lockSignal = lockRemaining > 365 * 3
    ? "protocol_grade"
    : lockRemaining > 365 * 2
      ? "excellent"
      : lockRemaining > 365
        ? "recommended"
        : lockRemaining > 180
          ? "acceptable"
          : lockRemaining > 90
            ? "minimum"
            : lockRemaining > 30
              ? "short_term"
              : "irrational";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Lock Status */}
      <div style={{ ...panelStyle, padding: 16 }}>
        <SectionHeader text="Liquidity Lock" />
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 16,
            marginTop: 12,
          }}
        >
          <StatCell label="LOCKED QUSD" value={formatUsd(p.liquidityLockedQusd)} />
          <StatCell label="LOCK DAYS" value={`${p.liquidityLockDays}d`} />
          <StatCell label="REMAINING" value={`${lockRemaining}d`} />
          <StatCell
            label="EXPIRY"
            value={new Date(p.liquidityLockExpiry * 1000).toLocaleDateString()}
          />
          <StatCell label="ILLP FEE PAID" value={formatUsd(p.illpFeePaid)} />
          <div>
            <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.05em" }}>
              SIGNAL
            </span>
            <div style={{ marginTop: 4 }}>
              <span
                style={{
                  fontFamily: FONT.display,
                  fontSize: 10,
                  color: illpColor(lockSignal as never),
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}
              >
                {illpLabel(lockSignal as never)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* MGT Tranches */}
      {p.mgtTranches.length > 0 && (
        <div style={{ ...panelStyle, padding: 16 }}>
          <SectionHeader text="Milestone-Gated Treasury (MGT)" />
          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
            {p.mgtTranches.map((t) => (
              <TrancheRow key={t.index} tranche={t} totalSupply={p.totalSupply} />
            ))}
          </div>
        </div>
      )}

      {/* QASL */}
      {p.qaslEnabled && (
        <div style={{ ...panelStyle, padding: 16 }}>
          <SectionHeader text="Quantum Anti-Snipe Launch (QASL)" />
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: 16,
              marginTop: 12,
            }}
          >
            <StatCell label="LAUNCH BLOCK" value={`#${p.qaslLaunchBlock ?? "N/A"}`} />
            <StatCell label="MAX BUY %" value={`${(p.qaslMaxBuyPercent * 100).toFixed(1)}%`} />
            <StatCell label="FEE MULTIPLIER" value={`${p.qaslFeeMultiplier}x`} />
            <StatCell label="SNIPE PENALTY" value={`${p.qaslSnipePenalty}%`} />
            <StatCell label="ENTROPY SOURCE" value="SUSY Hamiltonian" />
            <StatCell label="STATUS" value="COMPLETED" color={L.success} />
          </div>
        </div>
      )}

      {/* Vesting Schedules */}
      {p.vestingSchedules.length > 0 && (
        <div style={{ ...panelStyle, padding: 16 }}>
          <SectionHeader text="Vesting Schedules" />
          <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 12 }}>
            <thead>
              <tr>
                {["BENEFICIARY", "LABEL", "CLIFF", "DURATION", "RELEASED", "RELEASABLE"].map(
                  (h) => (
                    <th
                      key={h}
                      style={{
                        fontFamily: FONT.display,
                        fontSize: 9,
                        color: L.textMuted,
                        textAlign: "left",
                        padding: "4px 8px",
                        borderBottom: `1px solid ${L.borderSubtle}`,
                        letterSpacing: "0.05em",
                      }}
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {p.vestingSchedules.map((v, i) => (
                <tr key={i}>
                  <td style={tdMono}>{formatAddr(v.beneficiary, 6)}</td>
                  <td style={tdMono}>{v.label}</td>
                  <td style={tdMono}>{v.cliffDays}d</td>
                  <td style={tdMono}>{v.vestingDays}d</td>
                  <td style={tdMono}>{formatNumber(v.released)}</td>
                  <td style={{ ...tdMono, color: v.releasable > 0 ? L.success : L.textMuted }}>
                    {formatNumber(v.releasable)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
});

/* ── Tranche Row ──────────────────────────────────────────────────────────── */

const TrancheRow = memo(function TrancheRow({
  tranche,
  totalSupply,
}: {
  tranche: MGTTranche;
  totalSupply: number;
}) {
  const progress =
    tranche.milestoneTarget > 0
      ? tranche.milestoneCurrentValue / tranche.milestoneTarget
      : 0;
  const milestoneLabel = tranche.milestoneType.replace(/_/g, " ").toUpperCase();

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "8px 0",
        borderBottom: `1px solid ${L.borderSubtle}10`,
      }}
    >
      <span
        style={{
          fontFamily: FONT.display,
          fontSize: 11,
          color: L.textMuted,
          width: 24,
          textAlign: "center",
        }}
      >
        #{tranche.index + 1}
      </span>

      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textPrimary }}>
            {milestoneLabel}: {formatNumber(tranche.milestoneCurrentValue)} /{" "}
            {formatNumber(tranche.milestoneTarget)}
          </span>
          <TrancheStatusBadge status={tranche.status} />
        </div>
        <ProgressBar
          value={progress * 100}
          max={100}
          color={
            tranche.status === "released"
              ? L.success
              : tranche.status === "unlocked"
                ? L.warning
                : L.glowCyan
          }
          height={5}
        />
      </div>

      <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textSecondary, width: 60, textAlign: "right" }}>
        {tranche.percent}% ({formatNumber(tranche.tokens)})
      </span>
    </div>
  );
});

/* ── StatCell ─────────────────────────────────────────────────────────────── */

const StatCell = memo(function StatCell({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div>
      <span
        style={{
          fontFamily: FONT.display,
          fontSize: 9,
          color: L.textMuted,
          letterSpacing: "0.05em",
          display: "block",
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: FONT.mono,
          fontSize: 13,
          color: color ?? L.textPrimary,
          display: "block",
          marginTop: 4,
        }}
      >
        {value}
      </span>
    </div>
  );
});

/* ── Tab: QPCS ────────────────────────────────────────────────────────────── */

const QPCSTab = memo(function QPCSTab({ p }: { p: Project }) {
  const chartData = useMemo(
    () =>
      p.qpcsHistory.map((h, i) => ({
        x: i,
        y: h.score,
      })),
    [p.qpcsHistory],
  );

  const improvements = useMemo(() => {
    const items: Array<{ key: keyof QPCSComponents; gap: number; suggestion: string }> = [];
    for (const k of COMPONENT_KEYS) {
      const max = QPCS_WEIGHTS[k].max;
      const val = p.qpcsComponents[k];
      const gap = max - val;
      if (gap > max * 0.3) {
        items.push({ key: k, gap, suggestion: IMPROVEMENT_MAP[k] });
      }
    }
    return items.sort((a, b) => b.gap - a.gap).slice(0, 4);
  }, [p.qpcsComponents]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Full Breakdown */}
      <div style={{ ...panelStyle, padding: 16 }}>
        <SectionHeader text="QPCS Breakdown" />
        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
          {COMPONENT_KEYS.map((key) => {
            const value = p.qpcsComponents[key];
            const config = QPCS_WEIGHTS[key];
            const barColor = COMPONENT_COLORS[key];
            const pct = Math.min(100, (value / config.max) * 100);

            return (
              <div key={key} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span
                  style={{
                    fontFamily: FONT.mono,
                    fontSize: 11,
                    color: L.textSecondary,
                    width: 130,
                    flexShrink: 0,
                    textAlign: "right",
                  }}
                >
                  {config.label}
                </span>
                <div
                  style={{
                    flex: 1,
                    height: 8,
                    borderRadius: 4,
                    background: L.bgBase,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${pct}%`,
                      height: "100%",
                      borderRadius: 4,
                      background: barColor,
                      boxShadow: `0 0 6px ${barColor}40`,
                      transition: "width 0.4s ease",
                    }}
                  />
                </div>
                <span
                  style={{
                    fontFamily: FONT.mono,
                    fontSize: 11,
                    color: L.textMuted,
                    width: 50,
                    textAlign: "right",
                    flexShrink: 0,
                  }}
                >
                  {value}/{config.max}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* QPCS History */}
      <div style={{ ...panelStyle, padding: 16 }}>
        <SectionHeader text="QPCS History (30D)" />
        <div style={{ marginTop: 12 }}>
          <MiniLineChart
            data={chartData}
            width={680}
            height={160}
            color={L.glowCyan}
            showArea
          />
        </div>
      </div>

      {/* Improvement Opportunities */}
      {improvements.length > 0 && (
        <div style={{ ...panelStyle, padding: 16 }}>
          <SectionHeader text="Improvement Opportunities" />
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
            {improvements.map((imp) => (
              <div
                key={imp.key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 12px",
                  background: L.bgSurface,
                  borderRadius: 6,
                  border: `1px solid ${L.borderSubtle}`,
                }}
              >
                <span
                  style={{
                    fontFamily: FONT.display,
                    fontSize: 10,
                    color: L.warning,
                    width: 50,
                    textAlign: "center",
                    flexShrink: 0,
                  }}
                >
                  +{imp.gap}
                </span>
                <span style={{ fontFamily: FONT.body, fontSize: 12, color: L.textSecondary }}>
                  {imp.suggestion}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});

/* ── Tab: GRADUATION ──────────────────────────────────────────────────────── */

const GraduationTab = memo(function GraduationTab({ p }: { p: Project }) {
  const currentIdx = TIER_ORDER.indexOf(p.tier);
  const nextTier = currentIdx < TIER_ORDER.length - 1 ? TIER_ORDER[currentIdx + 1] : null;
  const nextTierCfg = nextTier ? TIER_CONFIGS.find((t) => t.tier === nextTier) : null;

  const requirements = nextTierCfg
    ? [
        {
          label: "QPCS Score",
          current: p.qpcs,
          required: nextTierCfg.minQpcs,
          met: p.qpcs >= nextTierCfg.minQpcs,
        },
        {
          label: "Holders",
          current: p.holderCount,
          required: nextTierCfg.minHolders,
          met: p.holderCount >= nextTierCfg.minHolders,
        },
        {
          label: "Liquidity (QUSD)",
          current: p.liquidityLockedQusd,
          required: nextTierCfg.minLiquidityQusd,
          met: p.liquidityLockedQusd >= nextTierCfg.minLiquidityQusd,
        },
        {
          label: "Lock Days",
          current: p.liquidityLockDays,
          required: nextTierCfg.minLiquidityLockDays,
          met: p.liquidityLockDays >= nextTierCfg.minLiquidityLockDays,
        },
      ]
    : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Tier progress visual */}
      <div style={{ ...panelStyle, padding: 20 }}>
        <SectionHeader text="Graduation Progress" />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 0,
            marginTop: 16,
            position: "relative",
          }}
        >
          {TIER_ORDER.map((tier, i) => {
            const completed = i <= currentIdx;
            const current = i === currentIdx;
            const tc = tierColor(tier);
            return (
              <React.Fragment key={tier}>
                {i > 0 && (
                  <div
                    style={{
                      flex: 1,
                      height: 2,
                      background: i <= currentIdx ? tc : L.borderSubtle,
                      transition: "background 0.3s",
                    }}
                  />
                )}
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 6,
                    position: "relative",
                  }}
                >
                  <div
                    style={{
                      width: current ? 36 : 28,
                      height: current ? 36 : 28,
                      borderRadius: "50%",
                      background: completed ? tc : L.bgBase,
                      border: `2px solid ${completed ? tc : L.borderSubtle}`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      boxShadow: current ? `0 0 16px ${tc}60` : "none",
                      transition: "all 0.3s",
                    }}
                  >
                    <span style={{ fontFamily: FONT.display, fontSize: current ? 12 : 10, color: completed ? L.bgBase : L.textMuted }}>
                      {completed ? "\u2713" : i + 1}
                    </span>
                  </div>
                  <span
                    style={{
                      fontFamily: FONT.display,
                      fontSize: 9,
                      color: current ? tc : completed ? L.textSecondary : L.textMuted,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    {tier}
                  </span>
                </div>
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Graduation History */}
      {p.graduationHistory.length > 0 && (
        <div style={{ ...panelStyle, padding: 16 }}>
          <SectionHeader text="Graduation History" />
          <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 12 }}>
            <thead>
              <tr>
                {["TIER", "BLOCK", "TIMESTAMP"].map((h) => (
                  <th
                    key={h}
                    style={{
                      fontFamily: FONT.display,
                      fontSize: 9,
                      color: L.textMuted,
                      textAlign: "left",
                      padding: "4px 8px",
                      borderBottom: `1px solid ${L.borderSubtle}`,
                      letterSpacing: "0.05em",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {p.graduationHistory.map((g, i) => (
                <tr key={i}>
                  <td style={{ padding: "6px 8px" }}>
                    <TierBadge tier={g.tier} size="xs" />
                  </td>
                  <td style={tdMono}>#{g.block}</td>
                  <td style={tdMono}>{new Date(g.timestamp * 1000).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Next Tier Requirements */}
      {nextTierCfg && requirements.length > 0 && (
        <div style={{ ...panelStyle, padding: 16 }}>
          <SectionHeader text={`Requirements for ${nextTierCfg.label}`} />
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
            {requirements.map((r) => (
              <div
                key={r.label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 12px",
                  background: L.bgSurface,
                  borderRadius: 6,
                  border: `1px solid ${r.met ? `${L.success}30` : `${L.error}30`}`,
                }}
              >
                <span
                  style={{
                    fontFamily: FONT.display,
                    fontSize: 14,
                    color: r.met ? L.success : L.error,
                    width: 20,
                    textAlign: "center",
                  }}
                >
                  {r.met ? "\u2713" : "\u2717"}
                </span>
                <span
                  style={{
                    fontFamily: FONT.mono,
                    fontSize: 11,
                    color: L.textSecondary,
                    flex: 1,
                  }}
                >
                  {r.label}
                </span>
                <span
                  style={{
                    fontFamily: FONT.mono,
                    fontSize: 11,
                    color: r.met ? L.success : L.textPrimary,
                  }}
                >
                  {typeof r.current === "number" && r.current >= 1000
                    ? formatNumber(r.current)
                    : r.current}
                </span>
                <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>/</span>
                <span style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textMuted }}>
                  {typeof r.required === "number" && r.required >= 1000
                    ? formatNumber(r.required)
                    : r.required}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* .qbc Domain */}
      <div style={{ ...panelStyle, padding: 16 }}>
        <SectionHeader text=".qbc Domain" />
        <div style={{ marginTop: 12 }}>
          {p.qbcDomain ? (
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  fontFamily: FONT.mono,
                  fontSize: 14,
                  color: L.glowCyan,
                  background: `${L.glowCyan}10`,
                  padding: "6px 14px",
                  borderRadius: 6,
                  border: `1px solid ${L.glowCyan}30`,
                }}
              >
                {p.qbcDomain}
              </span>
              <span style={{ fontFamily: FONT.display, fontSize: 10, color: L.success }}>
                REGISTERED
              </span>
            </div>
          ) : (
            <span style={{ fontFamily: FONT.body, fontSize: 12, color: L.textMuted }}>
              No .qbc domain registered. Available at Established tier or above.
            </span>
          )}
        </div>
      </div>
    </div>
  );
});

/* ── Tab: COMMUNITY DD ────────────────────────────────────────────────────── */

const CommunityDDTab = memo(function CommunityDDTab({ p }: { p: Project }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Verdict banner */}
      <div
        style={{
          ...panelStyle,
          padding: 16,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <span style={{ fontFamily: FONT.display, fontSize: 10, color: L.textMuted, letterSpacing: "0.05em" }}>
            COMMUNITY VERDICT
          </span>
          <div style={{ marginTop: 6 }}>
            <VerdictBadge verdict={p.communityVerdict} />
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <span style={{ fontFamily: FONT.mono, fontSize: 12, color: L.textSecondary }}>
            {p.ddReports.length} report{p.ddReports.length !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Submit button */}
      <div
        style={{
          ...panelStyle,
          padding: 12,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span style={{ fontFamily: FONT.body, fontSize: 12, color: L.textSecondary }}>
          Submit a due diligence report (requires 500+ QBC balance)
        </span>
        <button
          style={{
            fontFamily: FONT.display,
            fontSize: 10,
            color: L.bgBase,
            background: L.glowCyan,
            border: "none",
            borderRadius: 4,
            padding: "6px 16px",
            cursor: "pointer",
            letterSpacing: "0.04em",
          }}
        >
          SUBMIT REPORT
        </button>
      </div>

      {/* Reports list */}
      {p.ddReports.length === 0 ? (
        <div
          style={{
            ...panelStyle,
            padding: 32,
            textAlign: "center",
          }}
        >
          <span style={{ fontFamily: FONT.body, fontSize: 13, color: L.textMuted }}>
            No community DD reports yet. Be the first to review this project.
          </span>
        </div>
      ) : (
        p.ddReports.map((report) => (
          <DDReportCard key={report.id} report={report} />
        ))
      )}
    </div>
  );
});

/* ── DD Report Card ───────────────────────────────────────────────────────── */

const DDReportCard = memo(function DDReportCard({ report }: { report: DDReport }) {
  return (
    <div style={{ ...panelStyle, padding: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <DDCategoryBadge category={report.category} />
          <OutcomeBadge outcome={report.outcome} />
        </div>
        <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>
          {timeAgo(report.timestamp)}
        </span>
      </div>

      <h4
        style={{
          fontFamily: FONT.body,
          fontSize: 13,
          color: L.textPrimary,
          margin: "0 0 6px 0",
          fontWeight: 600,
        }}
      >
        {report.title}
      </h4>

      <p
        style={{
          fontFamily: FONT.body,
          fontSize: 12,
          color: L.textSecondary,
          margin: "0 0 10px 0",
          lineHeight: 1.5,
        }}
      >
        {report.content.length > 200 ? report.content.slice(0, 200) + "..." : report.content}
      </p>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>
          by {formatAddr(report.author, 6)}
        </span>
        <div style={{ width: 160 }}>
          <VoteBar positive={report.positiveVotes} negative={report.negativeVotes} />
        </div>
      </div>
    </div>
  );
});

/* ── Tab: VOUCHES ─────────────────────────────────────────────────────────── */

const VouchesTab = memo(function VouchesTab({ p }: { p: Project }) {
  const hasProtocol = p.vouches.some((v) => v.voucherTier === "protocol");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Protocol endorsed badge */}
      {hasProtocol && (
        <div
          style={{
            ...panelStyle,
            padding: 12,
            display: "flex",
            alignItems: "center",
            gap: 10,
            borderColor: `${L.tierProtocol}40`,
          }}
        >
          <span style={{ fontFamily: FONT.display, fontSize: 16, color: L.tierProtocol }}>
            {"\u26A1"}
          </span>
          <span
            style={{
              fontFamily: FONT.display,
              fontSize: 11,
              color: L.tierProtocol,
              letterSpacing: "0.06em",
            }}
          >
            PROTOCOL ENDORSED
          </span>
          <span style={{ fontFamily: FONT.body, fontSize: 11, color: L.textSecondary, marginLeft: 8 }}>
            At least one Protocol-tier project has vouched for this project.
          </span>
        </div>
      )}

      {p.vouches.length === 0 ? (
        <div style={{ ...panelStyle, padding: 32, textAlign: "center" }}>
          <span style={{ fontFamily: FONT.body, fontSize: 13, color: L.textMuted }}>
            No vouches yet. Projects can vouch for each other by staking QUSD.
          </span>
        </div>
      ) : (
        p.vouches.map((v, i) => <VouchCard key={i} vouch={v} />)
      )}
    </div>
  );
});

/* ── Vouch Card ───────────────────────────────────────────────────────────── */

const VouchCard = memo(function VouchCard({ vouch }: { vouch: Vouch }) {
  return (
    <div style={{ ...panelStyle, padding: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontFamily: FONT.body, fontSize: 13, color: L.textPrimary, fontWeight: 600 }}>
            {vouch.voucherProjectName}
          </span>
          <TierBadge tier={vouch.voucherTier} size="xs" />
          <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>
            QPCS {vouch.voucherQpcs}
          </span>
        </div>
        <VouchStatusBadge status={vouch.status} />
      </div>

      <div style={{ display: "flex", gap: 20, marginBottom: 8 }}>
        <div>
          <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.04em" }}>
            STAKED
          </span>
          <div style={{ fontFamily: FONT.mono, fontSize: 12, color: L.glowGold, marginTop: 2 }}>
            {formatUsd(vouch.stakeAmountQusd)} QUSD
          </div>
        </div>
        <div>
          <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.04em" }}>
            EARNINGS
          </span>
          <div style={{ fontFamily: FONT.mono, fontSize: 12, color: L.success, marginTop: 2 }}>
            {formatUsd(vouch.earningsQusd)} QUSD
          </div>
        </div>
        <div>
          <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.04em" }}>
            TIMESTAMP
          </span>
          <div style={{ fontFamily: FONT.mono, fontSize: 12, color: L.textSecondary, marginTop: 2 }}>
            {timeAgo(vouch.timestamp)}
          </div>
        </div>
      </div>

      {vouch.note && (
        <p
          style={{
            fontFamily: FONT.body,
            fontSize: 12,
            color: L.textSecondary,
            margin: 0,
            fontStyle: "italic",
            lineHeight: 1.5,
          }}
        >
          &ldquo;{vouch.note}&rdquo;
        </p>
      )}
    </div>
  );
});

/* ── Table cell style ─────────────────────────────────────────────────────── */

const tdMono: React.CSSProperties = {
  fontFamily: FONT.mono,
  fontSize: 11,
  color: L.textSecondary,
  padding: "6px 8px",
};

/* ══════════════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ══════════════════════════════════════════════════════════════════════════════ */

export const TokenDetailView = memo(function TokenDetailView() {
  const selectedProjectAddr = useLaunchpadStore((s) => s.selectedProjectAddr);
  const setSelectedProject = useLaunchpadStore((s) => s.setSelectedProject);
  const tokenDetailTab = useLaunchpadStore((s) => s.tokenDetailTab);
  const setTokenDetailTab = useLaunchpadStore((s) => s.setTokenDetailTab);
  const { data: project, isLoading } = useProject(selectedProjectAddr);

  const handleBack = useCallback(() => {
    setSelectedProject(null);
  }, [setSelectedProject]);

  if (isLoading || !project) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        <span style={{ fontFamily: FONT.body, fontSize: 14, color: L.textMuted }}>
          Loading project...
        </span>
      </div>
    );
  }

  const p = project;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Back button */}
      <button
        onClick={handleBack}
        style={{
          background: "none",
          border: "none",
          color: L.textSecondary,
          fontFamily: FONT.body,
          fontSize: 13,
          cursor: "pointer",
          padding: "4px 0",
          display: "flex",
          alignItems: "center",
          gap: 6,
          alignSelf: "flex-start",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = L.textPrimary;
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = L.textSecondary;
        }}
      >
        {"\u2190"} Back to Discover
      </button>

      {/* ── HEADER ────────────────────────────────────────────────────────────── */}
      <div
        style={{
          ...panelStyle,
          padding: 20,
          display: "flex",
          alignItems: "flex-start",
          gap: 20,
        }}
      >
        {/* DNA Fingerprint */}
        <DNAFingerprint
          hash={p.dnaFingerprint}
          size={60}
          dilithiumVerified
        />

        {/* Name, symbol, badges */}
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <TierBadge tier={p.tier} size="md" />
            <h2
              style={{
                fontFamily: FONT.display,
                fontSize: 20,
                color: L.textPrimary,
                margin: 0,
                letterSpacing: "0.02em",
              }}
            >
              {p.name}
            </h2>
            <span
              style={{
                fontFamily: FONT.mono,
                fontSize: 12,
                color: L.textMuted,
              }}
            >
              ${p.symbol}
            </span>
          </div>

          {p.qbcDomain && (
            <span
              style={{
                fontFamily: FONT.mono,
                fontSize: 11,
                color: L.glowCyan,
                display: "block",
                marginTop: 4,
              }}
            >
              {p.qbcDomain}
            </span>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
            <span style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textMuted }}>
              {formatAddr(p.address, 8)}
            </span>
            <CopyButton text={p.address} />
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 6 }}>
            <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>
              v{p.templateVersion}
            </span>
            <EhgBadge status={p.ehgAtDeploy} />
          </div>
        </div>

        {/* QPCS Gauge */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
          <QPCSGauge score={p.qpcs} grade={p.qpcsGrade} size={80} />
        </div>
      </div>

      {/* ── STATS BAR ─────────────────────────────────────────────────────────── */}
      <div
        style={{
          ...panelStyle,
          padding: "12px 16px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <StatsItem label="PRICE" value={formatUsd(p.lastPrice)} />
        <StatsItem
          label="24H CHANGE"
          value={formatPct(p.price24hChange)}
          color={p.price24hChange >= 0 ? L.success : L.error}
        />
        <StatsItem label="MARKET CAP" value={formatUsd(p.marketCap)} />
        <StatsItem label="VOLUME 24H" value={formatUsd(p.volume24h)} />
        <StatsItem label="HOLDERS" value={formatNumber(p.holderCount)} />
        <StatsItem
          label="LOCK REMAINING"
          value={`${daysRemaining(p.liquidityLockExpiry)}d`}
        />
      </div>

      {/* ── TAB BAR ───────────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          gap: 0,
          borderBottom: `1px solid ${L.borderSubtle}`,
          overflowX: "auto",
        }}
      >
        {TABS.map((tab) => {
          const active = tokenDetailTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setTokenDetailTab(tab.key)}
              style={{
                background: "none",
                border: "none",
                borderBottom: active ? `2px solid ${L.glowCyan}` : "2px solid transparent",
                color: active ? L.glowCyan : L.textMuted,
                fontFamily: FONT.display,
                fontSize: 10,
                letterSpacing: "0.06em",
                padding: "10px 16px",
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "color 0.2s, border-color 0.2s",
              }}
              onMouseEnter={(e) => {
                if (!active) (e.currentTarget as HTMLButtonElement).style.color = L.textSecondary;
              }}
              onMouseLeave={(e) => {
                if (!active) (e.currentTarget as HTMLButtonElement).style.color = L.textMuted;
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ── TAB CONTENT ───────────────────────────────────────────────────────── */}
      {tokenDetailTab === "overview" && <OverviewTab p={p} />}
      {tokenDetailTab === "mechanics" && <MechanicsTab p={p} />}
      {tokenDetailTab === "qpcs" && <QPCSTab p={p} />}
      {tokenDetailTab === "graduation" && <GraduationTab p={p} />}
      {tokenDetailTab === "cdd" && <CommunityDDTab p={p} />}
      {tokenDetailTab === "vouches" && <VouchesTab p={p} />}
    </div>
  );
});

/* ── Stats Item ───────────────────────────────────────────────────────────── */

const StatsItem = memo(function StatsItem({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
      <span
        style={{
          fontFamily: FONT.display,
          fontSize: 8,
          color: L.textMuted,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: FONT.mono,
          fontSize: 13,
          color: color ?? L.textPrimary,
          fontWeight: 600,
        }}
      >
        {value}
      </span>
    </div>
  );
});
