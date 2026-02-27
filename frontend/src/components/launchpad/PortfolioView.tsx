// ─── QBC LAUNCHPAD — Portfolio View (4 Tabs) ──────────────────────────────────
"use client";

import React, { memo, useMemo, useState, useCallback } from "react";
import { useMyDeployed, useMyInvestments, useProjects } from "./hooks";
import { useLaunchpadStore } from "./store";
import { useWalletStore } from "@/stores/wallet-store";
import {
  TierBadge,
  QpcsGradeBadge,
  VerdictBadge,
  ProgressBar,
  TrancheStatusBadge,
  formatNumber,
  formatUsd,
  formatPct,
  formatAddr,
  timeAgo,
  daysRemaining,
  tierColor,
  L,
  FONT,
  panelStyle,
} from "./shared";
import type {
  Project,
  PortfolioInvestment,
  Vouch,
  DDReport,
  VouchStatus,
} from "./types";

/* ── Tab Config ───────────────────────────────────────────────────────────── */

type PortfolioTab = "projects" | "investments" | "vouches" | "dd";

const TABS: Array<{ key: PortfolioTab; label: string }> = [
  { key: "projects", label: "MY PROJECTS" },
  { key: "investments", label: "MY INVESTMENTS" },
  { key: "vouches", label: "MY VOUCHES" },
  { key: "dd", label: "MY DD REPORTS" },
];

/** Fallback address shown when no wallet is connected. */
const FALLBACK_WALLET = "QBC1user0000000000000000000000000000000000";

/* ── Vouch Status Badge ───────────────────────────────────────────────────── */

const VouchStatusBadge = memo(function VouchStatusBadge({ status }: { status: VouchStatus }) {
  const colors: Record<VouchStatus, string> = {
    active: L.success,
    completed_success: L.glowCyan,
    slashed: L.error,
    withdrawn: L.textMuted,
  };
  const labels: Record<VouchStatus, string> = {
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
        color: colors[status],
        textTransform: "uppercase",
        letterSpacing: "0.04em",
      }}
    >
      {labels[status]}
    </span>
  );
});

/* ── DD Outcome Badge ─────────────────────────────────────────────────────── */

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

/* ── DD Category Badge ────────────────────────────────────────────────────── */

const DDCatBadge = memo(function DDCatBadge({ category }: { category: string }) {
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
      {category}
    </span>
  );
});

/* ── My Projects Tab ──────────────────────────────────────────────────────── */

const MyProjectsTab = memo(function MyProjectsTab({
  projects,
  onSelect,
}: {
  projects: Project[];
  onSelect: (addr: string) => void;
}) {
  if (projects.length === 0) {
    return (
      <div style={{ ...panelStyle, padding: 40, textAlign: "center" }}>
        <span style={{ fontFamily: FONT.body, fontSize: 14, color: L.textMuted }}>
          You have not deployed any projects yet.
        </span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {projects.map((p) => {
        const mgtCompleted = p.mgtTranches.filter((t) => t.status === "released").length;
        const mgtTotal = p.mgtTranches.length;
        const gradProgress = (["seed", "early", "growth", "established", "protocol"].indexOf(p.tier) + 1) / 5;

        return (
          <div
            key={p.address}
            style={{
              ...panelStyle,
              padding: 16,
              cursor: "pointer",
              transition: "border-color 0.2s",
            }}
            onClick={() => onSelect(p.address)}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLDivElement).style.borderColor = L.borderMedium;
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLDivElement).style.borderColor = L.borderSubtle;
            }}
          >
            {/* Header row */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: 12,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h3
                  style={{
                    fontFamily: FONT.display,
                    fontSize: 14,
                    color: L.textPrimary,
                    margin: 0,
                    letterSpacing: "0.02em",
                  }}
                >
                  {p.name}
                </h3>
                <span style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textMuted }}>
                  ${p.symbol}
                </span>
                <TierBadge tier={p.tier} size="xs" />
              </div>
              <QpcsGradeBadge grade={p.qpcsGrade} score={p.qpcs} />
            </div>

            {/* Stats row */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(4, 1fr)",
                gap: 12,
                marginBottom: 12,
              }}
            >
              <StatMini label="HOLDERS" value={formatNumber(p.holderCount)} />
              <StatMini label="VOLUME 24H" value={formatUsd(p.volume24h)} />
              <StatMini label="MARKET CAP" value={formatUsd(p.marketCap)} />
              <StatMini
                label="24H CHANGE"
                value={formatPct(p.price24hChange)}
                color={p.price24hChange >= 0 ? L.success : L.error}
              />
            </div>

            {/* Progress bars */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.04em" }}>
                    GRADUATION
                  </span>
                  <span style={{ fontFamily: FONT.mono, fontSize: 9, color: tierColor(p.tier) }}>
                    {p.tier.toUpperCase()}
                  </span>
                </div>
                <ProgressBar value={gradProgress * 100} max={100} color={tierColor(p.tier)} height={4} />
              </div>

              {mgtTotal > 0 && (
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.04em" }}>
                      MGT MILESTONES
                    </span>
                    <span style={{ fontFamily: FONT.mono, fontSize: 9, color: L.textSecondary }}>
                      {mgtCompleted}/{mgtTotal}
                    </span>
                  </div>
                  <ProgressBar value={mgtCompleted} max={mgtTotal} color={L.glowEmerald} height={4} />
                </div>
              )}
            </div>

            {/* Domain status */}
            {p.qbcDomain && (
              <div style={{ marginTop: 8 }}>
                <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.glowCyan }}>
                  {p.qbcDomain}
                </span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
});

/* ── StatMini ─────────────────────────────────────────────────────────────── */

const StatMini = memo(function StatMini({
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
          fontSize: 8,
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
          fontSize: 12,
          color: color ?? L.textPrimary,
          display: "block",
          marginTop: 2,
        }}
      >
        {value}
      </span>
    </div>
  );
});

/* ── My Investments Tab ───────────────────────────────────────────────────── */

const MyInvestmentsTab = memo(function MyInvestmentsTab({
  investments,
  onSelect,
}: {
  investments: PortfolioInvestment[];
  onSelect: (addr: string) => void;
}) {
  const totals = useMemo(() => {
    const totalInvested = investments.reduce((s, inv) => s + inv.investedQusd, 0);
    const totalValue = investments.reduce((s, inv) => s + inv.currentValue, 0);
    const totalPnl = totalValue - totalInvested;
    const totalPnlPct = totalInvested > 0 ? ((totalValue - totalInvested) / totalInvested) * 100 : 0;
    return { totalInvested, totalValue, totalPnl, totalPnlPct };
  }, [investments]);

  if (investments.length === 0) {
    return (
      <div style={{ ...panelStyle, padding: 40, textAlign: "center" }}>
        <span style={{ fontFamily: FONT.body, fontSize: 14, color: L.textMuted }}>
          No investments yet. Explore projects to invest.
        </span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Portfolio Summary */}
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
          <span
            style={{
              fontFamily: FONT.display,
              fontSize: 9,
              color: L.textMuted,
              letterSpacing: "0.06em",
              display: "block",
            }}
          >
            PORTFOLIO VALUE
          </span>
          <span
            style={{
              fontFamily: FONT.display,
              fontSize: 22,
              color: L.textPrimary,
              display: "block",
              marginTop: 4,
            }}
          >
            {formatUsd(totals.totalValue)}
          </span>
        </div>
        <div style={{ display: "flex", gap: 24 }}>
          <div style={{ textAlign: "right" }}>
            <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.05em", display: "block" }}>
              INVESTED
            </span>
            <span style={{ fontFamily: FONT.mono, fontSize: 14, color: L.textSecondary, display: "block", marginTop: 2 }}>
              {formatUsd(totals.totalInvested)}
            </span>
          </div>
          <div style={{ textAlign: "right" }}>
            <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.05em", display: "block" }}>
              TOTAL PNL
            </span>
            <span
              style={{
                fontFamily: FONT.mono,
                fontSize: 14,
                color: totals.totalPnl >= 0 ? L.success : L.error,
                display: "block",
                marginTop: 2,
              }}
            >
              {totals.totalPnl >= 0 ? "+" : ""}
              {formatUsd(totals.totalPnl)} ({formatPct(totals.totalPnlPct)})
            </span>
          </div>
        </div>
      </div>

      {/* Investments Table */}
      <div style={{ ...panelStyle, padding: 0, overflow: "auto" }} className="launchpad-scroll">
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["PROJECT", "INVESTED", "TOKENS", "CURRENT VALUE", "PNL ($)", "PNL (%)", "VESTING"].map((h) => (
                <th
                  key={h}
                  style={{
                    fontFamily: FONT.display,
                    fontSize: 9,
                    color: L.textMuted,
                    textAlign: h === "PROJECT" ? "left" : "right",
                    padding: "8px 10px",
                    borderBottom: `1px solid ${L.borderSubtle}`,
                    letterSpacing: "0.06em",
                    whiteSpace: "nowrap",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {investments.map((inv) => (
              <tr
                key={inv.projectAddress}
                style={{ cursor: "pointer" }}
                onClick={() => onSelect(inv.projectAddress)}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLTableRowElement).style.background = L.bgHover;
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLTableRowElement).style.background = "transparent";
                }}
              >
                <td
                  style={{
                    fontFamily: FONT.body,
                    fontSize: 12,
                    color: L.textPrimary,
                    padding: "8px 10px",
                    borderBottom: `1px solid ${L.borderSubtle}10`,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontWeight: 600 }}>{inv.project.name}</span>
                    <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>
                      ${inv.project.symbol}
                    </span>
                  </div>
                </td>
                <td style={{ ...tdMono, textAlign: "right" }}>{formatUsd(inv.investedQusd)}</td>
                <td style={{ ...tdMono, textAlign: "right" }}>{formatNumber(inv.tokensReceived)}</td>
                <td style={{ ...tdMono, textAlign: "right" }}>{formatUsd(inv.currentValue)}</td>
                <td
                  style={{
                    ...tdMono,
                    textAlign: "right",
                    color: inv.pnl >= 0 ? L.success : L.error,
                    fontWeight: 600,
                  }}
                >
                  {inv.pnl >= 0 ? "+" : ""}
                  {formatUsd(inv.pnl)}
                </td>
                <td
                  style={{
                    ...tdMono,
                    textAlign: "right",
                    color: inv.pnlPercent >= 0 ? L.success : L.error,
                  }}
                >
                  {formatPct(inv.pnlPercent)}
                </td>
                <td style={{ ...tdMono, textAlign: "right", width: 100 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <div style={{ flex: 1 }}>
                      <ProgressBar
                        value={inv.vestingProgress * 100}
                        max={100}
                        color={L.glowCyan}
                        height={4}
                      />
                    </div>
                    <span style={{ fontFamily: FONT.mono, fontSize: 9, color: L.textMuted, width: 32, textAlign: "right" }}>
                      {(inv.vestingProgress * 100).toFixed(0)}%
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
});

/* ── My Vouches Tab ───────────────────────────────────────────────────────── */

const MyVouchesTab = memo(function MyVouchesTab({
  vouches,
  onSelect,
}: {
  vouches: Array<{ project: Project; vouch: Vouch }>;
  onSelect: (addr: string) => void;
}) {
  const totals = useMemo(() => {
    const totalStaked = vouches.reduce((s, v) => s + v.vouch.stakeAmountQusd, 0);
    const totalEarnings = vouches.reduce((s, v) => s + v.vouch.earningsQusd, 0);
    return { totalStaked, totalEarnings };
  }, [vouches]);

  if (vouches.length === 0) {
    return (
      <div style={{ ...panelStyle, padding: 40, textAlign: "center" }}>
        <span style={{ fontFamily: FONT.body, fontSize: 14, color: L.textMuted }}>
          No vouches placed yet. Stake QUSD on projects you trust.
        </span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Summary */}
      <div
        style={{
          ...panelStyle,
          padding: 16,
          display: "flex",
          justifyContent: "space-around",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.05em", display: "block" }}>
            TOTAL STAKED
          </span>
          <span style={{ fontFamily: FONT.mono, fontSize: 16, color: L.glowGold, display: "block", marginTop: 4 }}>
            {formatUsd(totals.totalStaked)} QUSD
          </span>
        </div>
        <div style={{ textAlign: "center" }}>
          <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.05em", display: "block" }}>
            TOTAL EARNINGS
          </span>
          <span style={{ fontFamily: FONT.mono, fontSize: 16, color: L.success, display: "block", marginTop: 4 }}>
            {formatUsd(totals.totalEarnings)} QUSD
          </span>
        </div>
        <div style={{ textAlign: "center" }}>
          <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.05em", display: "block" }}>
            ACTIVE VOUCHES
          </span>
          <span style={{ fontFamily: FONT.mono, fontSize: 16, color: L.textPrimary, display: "block", marginTop: 4 }}>
            {vouches.filter((v) => v.vouch.status === "active").length}
          </span>
        </div>
      </div>

      {/* Vouch list */}
      {vouches.map((item, i) => {
        const remaining = daysRemaining(item.vouch.timestamp + 90 * 86400);
        return (
          <div
            key={i}
            style={{
              ...panelStyle,
              padding: 14,
              cursor: "pointer",
            }}
            onClick={() => onSelect(item.project.address)}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLDivElement).style.borderColor = L.borderMedium;
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLDivElement).style.borderColor = L.borderSubtle;
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: 8,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontFamily: FONT.body, fontSize: 13, color: L.textPrimary, fontWeight: 600 }}>
                  {item.project.name}
                </span>
                <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>
                  ${item.project.symbol}
                </span>
                <TierBadge tier={item.project.tier} size="xs" />
              </div>
              <VouchStatusBadge status={item.vouch.status} />
            </div>

            <div style={{ display: "flex", gap: 20 }}>
              <StatMini label="STAKED" value={`${formatUsd(item.vouch.stakeAmountQusd)} QUSD`} color={L.glowGold} />
              <StatMini label="REMAINING" value={`${remaining}d`} />
              <StatMini label="EARNINGS" value={`${formatUsd(item.vouch.earningsQusd)} QUSD`} color={L.success} />
              <StatMini label="PLACED" value={timeAgo(item.vouch.timestamp)} />
            </div>
          </div>
        );
      })}
    </div>
  );
});

/* ── My DD Reports Tab ────────────────────────────────────────────────────── */

const MyDDReportsTab = memo(function MyDDReportsTab({
  reports,
  onSelect,
}: {
  reports: Array<{ project: Project; report: DDReport }>;
  onSelect: (addr: string) => void;
}) {
  if (reports.length === 0) {
    return (
      <div style={{ ...panelStyle, padding: 40, textAlign: "center" }}>
        <span style={{ fontFamily: FONT.body, fontSize: 14, color: L.textMuted }}>
          No DD reports submitted yet. Help the community by reviewing projects.
        </span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Summary */}
      <div
        style={{
          ...panelStyle,
          padding: 16,
          display: "flex",
          justifyContent: "space-around",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.05em", display: "block" }}>
            REPORTS SUBMITTED
          </span>
          <span style={{ fontFamily: FONT.mono, fontSize: 16, color: L.textPrimary, display: "block", marginTop: 4 }}>
            {reports.length}
          </span>
        </div>
        <div style={{ textAlign: "center" }}>
          <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.05em", display: "block" }}>
            VERIFIED
          </span>
          <span style={{ fontFamily: FONT.mono, fontSize: 16, color: L.success, display: "block", marginTop: 4 }}>
            {reports.filter((r) => r.report.outcome === "verified").length}
          </span>
        </div>
        <div style={{ textAlign: "center" }}>
          <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.textMuted, letterSpacing: "0.05em", display: "block" }}>
            TOTAL VOTES RECEIVED
          </span>
          <span style={{ fontFamily: FONT.mono, fontSize: 16, color: L.textPrimary, display: "block", marginTop: 4 }}>
            {reports.reduce((s, r) => s + r.report.positiveVotes + r.report.negativeVotes, 0)}
          </span>
        </div>
      </div>

      {/* Reports list */}
      {reports.map((item) => (
        <div
          key={item.report.id}
          style={{
            ...panelStyle,
            padding: 14,
            cursor: "pointer",
          }}
          onClick={() => onSelect(item.project.address)}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = L.borderMedium;
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = L.borderSubtle;
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontFamily: FONT.body, fontSize: 12, color: L.textPrimary, fontWeight: 600 }}>
                {item.project.name}
              </span>
              <DDCatBadge category={item.report.category} />
            </div>
            <OutcomeBadge outcome={item.report.outcome} />
          </div>

          <h4
            style={{
              fontFamily: FONT.body,
              fontSize: 13,
              color: L.textPrimary,
              margin: "0 0 4px 0",
              fontWeight: 500,
            }}
          >
            {item.report.title}
          </h4>

          <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.success }}>
              +{item.report.positiveVotes}
            </span>
            <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.error }}>
              -{item.report.negativeVotes}
            </span>
            <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>
              {timeAgo(item.report.timestamp)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
});

/* ── Table cell style ─────────────────────────────────────────────────────── */

const tdMono: React.CSSProperties = {
  fontFamily: FONT.mono,
  fontSize: 11,
  color: L.textSecondary,
  padding: "8px 10px",
  borderBottom: `1px solid ${L.borderSubtle}10`,
};

/* ══════════════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ══════════════════════════════════════════════════════════════════════════════ */

export const PortfolioView = memo(function PortfolioView() {
  const setSelectedProject = useLaunchpadStore((s) => s.setSelectedProject);
  const [activeTab, setActiveTab] = useState<PortfolioTab>("projects");

  // Use real wallet address from wallet store
  const walletAddress = useWalletStore((s) => s.address);
  const activeNativeWallet = useWalletStore((s) => s.activeNativeWallet);
  const myWallet = walletAddress ?? activeNativeWallet ?? FALLBACK_WALLET;

  const { data: deployedProjects, isLoading: loadingDeployed } = useMyDeployed();
  const { data: investments, isLoading: loadingInvestments } = useMyInvestments();
  const { data: allProjects } = useProjects();

  const handleSelect = useCallback(
    (addr: string) => {
      setSelectedProject(addr);
    },
    [setSelectedProject],
  );

  // Derive vouches from all projects where the voucher is myWallet
  const myVouches = useMemo(() => {
    if (!allProjects) return [];
    const results: Array<{ project: Project; vouch: Vouch }> = [];
    for (const p of allProjects) {
      for (const v of p.vouches) {
        if (v.voucherAddress === myWallet) {
          results.push({ project: p, vouch: v });
        }
      }
    }
    return results;
  }, [allProjects, myWallet]);

  // Derive DD reports from all projects where the author is myWallet
  const myDDReports = useMemo(() => {
    if (!allProjects) return [];
    const results: Array<{ project: Project; report: DDReport }> = [];
    for (const p of allProjects) {
      for (const r of p.ddReports) {
        if (r.author === myWallet) {
          results.push({ project: p, report: r });
        }
      }
    }
    return results;
  }, [allProjects, myWallet]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Title */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2
          style={{
            fontFamily: FONT.display,
            fontSize: 16,
            color: L.textPrimary,
            margin: 0,
            letterSpacing: "0.04em",
          }}
        >
          PORTFOLIO
        </h2>
        <span style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textMuted }}>
          {formatAddr(myWallet, 8)}
        </span>
      </div>

      {/* Tab Bar */}
      <div
        style={{
          display: "flex",
          gap: 0,
          borderBottom: `1px solid ${L.borderSubtle}`,
          overflowX: "auto",
        }}
      >
        {TABS.map((tab) => {
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
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

      {/* Tab Content */}
      {activeTab === "projects" && (
        loadingDeployed ? (
          <div style={{ padding: 32, textAlign: "center" }}>
            <span style={{ fontFamily: FONT.body, fontSize: 13, color: L.textMuted }}>
              Loading projects...
            </span>
          </div>
        ) : (
          <MyProjectsTab projects={deployedProjects ?? []} onSelect={handleSelect} />
        )
      )}

      {activeTab === "investments" && (
        loadingInvestments ? (
          <div style={{ padding: 32, textAlign: "center" }}>
            <span style={{ fontFamily: FONT.body, fontSize: 13, color: L.textMuted }}>
              Loading investments...
            </span>
          </div>
        ) : (
          <MyInvestmentsTab investments={investments ?? []} onSelect={handleSelect} />
        )
      )}

      {activeTab === "vouches" && (
        <MyVouchesTab vouches={myVouches} onSelect={handleSelect} />
      )}

      {activeTab === "dd" && (
        <MyDDReportsTab reports={myDDReports} onSelect={handleSelect} />
      )}
    </div>
  );
});
