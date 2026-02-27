// ─── QBC LAUNCHPAD — Leaderboard View (5 Tabs) ───────────────────────────────
"use client";

import React, { memo, useCallback } from "react";
import { useLeaderboard } from "./hooks";
import { useLaunchpadStore } from "./store";
import {
  TierBadge,
  formatNumber,
  formatUsd,
  formatPct,
  formatAddr,
  illpLabel,
  illpColor,
  calculateILLP,
  contractTypeLabel,
  L,
  FONT,
  panelStyle,
} from "./shared";
import type { Project, LeaderboardTab, ILLPSignal, PresaleStatus } from "./types";

/* ── Tab Config ───────────────────────────────────────────────────────────── */

const TABS: Array<{ key: LeaderboardTab; label: string }> = [
  { key: "qpcs", label: "QPCS LEADERS" },
  { key: "raises", label: "TOP RAISES" },
  { key: "locks", label: "LOCK LEADERS" },
  { key: "growth", label: "GROWTH LEADERS" },
  { key: "reputation", label: "REPUTATION STAKES" },
];

/* ── Column Definitions ───────────────────────────────────────────────────── */

const thStyle: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 9,
  color: L.textMuted,
  textAlign: "left",
  padding: "6px 10px",
  borderBottom: `1px solid ${L.borderSubtle}`,
  letterSpacing: "0.06em",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  fontFamily: FONT.mono,
  fontSize: 11,
  color: L.textSecondary,
  padding: "8px 10px",
  borderBottom: `1px solid ${L.borderSubtle}10`,
};

/* ── Rank Change Indicator ────────────────────────────────────────────────── */

const RankChange = memo(function RankChange({
  current,
  previous,
}: {
  current: number;
  previous: number | null;
}) {
  if (previous === null) {
    return (
      <span style={{ fontFamily: FONT.display, fontSize: 9, color: L.glowCyan, marginLeft: 4 }}>
        NEW
      </span>
    );
  }
  const diff = previous - current;
  if (diff === 0) return null;
  if (diff > 0) {
    return (
      <span style={{ fontFamily: FONT.mono, fontSize: 9, color: L.success, marginLeft: 4 }}>
        {"\u25B2"}{diff}
      </span>
    );
  }
  return (
    <span style={{ fontFamily: FONT.mono, fontSize: 9, color: L.error, marginLeft: 4 }}>
      {"\u25BC"}{Math.abs(diff)}
    </span>
  );
});

/* ── Presale Status Badge (inline for table) ──────────────────────────────── */

const PresaleBadge = memo(function PresaleBadge({ status }: { status: PresaleStatus }) {
  const colors: Record<PresaleStatus, string> = {
    upcoming: L.info,
    active: L.success,
    completed: L.textSecondary,
    failed: L.error,
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

/* ── ILLP Signal Badge (inline for table) ─────────────────────────────────── */

const ILLPBadge = memo(function ILLPBadge({ lockDays }: { lockDays: number }) {
  const result = calculateILLP(lockDays);
  return (
    <span
      style={{
        fontFamily: FONT.display,
        fontSize: 9,
        color: illpColor(result.signal),
        textTransform: "uppercase",
        letterSpacing: "0.04em",
      }}
    >
      {illpLabel(result.signal)}
    </span>
  );
});

/* ── Project Name Cell ────────────────────────────────────────────────────── */

const ProjectCell = memo(function ProjectCell({ project }: { project: Project }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontFamily: FONT.body, fontSize: 12, color: L.textPrimary, fontWeight: 600 }}>
            {project.name}
          </span>
          <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>
            ${project.symbol}
          </span>
        </div>
        <div style={{ marginTop: 2 }}>
          <TierBadge tier={project.tier} size="xs" />
        </div>
      </div>
    </div>
  );
});

/* ── QPCS Table ───────────────────────────────────────────────────────────── */

const QPCSTable = memo(function QPCSTable({
  projects,
  onSelect,
}: {
  projects: Project[];
  onSelect: (addr: string) => void;
}) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={{ ...thStyle, textAlign: "center", width: 50 }}>RANK</th>
          <th style={thStyle}>PROJECT</th>
          <th style={{ ...thStyle, textAlign: "right" }}>QPCS</th>
          <th style={thStyle}>TYPE</th>
          <th style={{ ...thStyle, textAlign: "right" }}>HOLDERS</th>
          <th style={{ ...thStyle, textAlign: "right" }}>LOCKED</th>
          <th style={thStyle}>DOMAIN</th>
        </tr>
      </thead>
      <tbody>
        {projects.map((p, i) => {
          // Deterministic "previous rank" derived from address hash to avoid
          // render-flicker caused by Math.random() in the render path.
          const addrHash = p.address.charCodeAt(4) + p.address.charCodeAt(5);
          const prevRank = i > 0 ? i + 1 + ((addrHash % 2 === 0 ? 1 : -1) * (addrHash % 3)) : null;
          return (
            <tr
              key={p.address}
              style={{ cursor: "pointer" }}
              onClick={() => onSelect(p.address)}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLTableRowElement).style.background = L.bgHover;
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLTableRowElement).style.background = "transparent";
              }}
            >
              <td style={{ ...tdStyle, textAlign: "center" }}>
                <span style={{ color: i < 3 ? L.glowGold : L.textMuted }}>{i + 1}</span>
                <RankChange current={i + 1} previous={prevRank} />
              </td>
              <td style={tdStyle}><ProjectCell project={p} /></td>
              <td style={{ ...tdStyle, textAlign: "right", color: L.glowCyan, fontWeight: 600 }}>
                {p.qpcs.toFixed(1)}
              </td>
              <td style={tdStyle}>
                <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>
                  {contractTypeLabel(p.type)}
                </span>
              </td>
              <td style={{ ...tdStyle, textAlign: "right" }}>{formatNumber(p.holderCount)}</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>{formatUsd(p.liquidityLockedQusd)}</td>
              <td style={tdStyle}>
                {p.qbcDomain ? (
                  <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.glowCyan }}>
                    {p.qbcDomain}
                  </span>
                ) : (
                  <span style={{ color: L.textMuted }}>--</span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
});

/* ── Raises Table ─────────────────────────────────────────────────────────── */

const RaisesTable = memo(function RaisesTable({
  projects,
  onSelect,
}: {
  projects: Project[];
  onSelect: (addr: string) => void;
}) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={{ ...thStyle, textAlign: "center", width: 50 }}>RANK</th>
          <th style={thStyle}>PROJECT</th>
          <th style={{ ...thStyle, textAlign: "right" }}>RAISED</th>
          <th style={thStyle}>PRESALE TYPE</th>
          <th style={{ ...thStyle, textAlign: "right" }}>PARTICIPANTS</th>
          <th style={thStyle}>STATUS</th>
        </tr>
      </thead>
      <tbody>
        {projects.map((p, i) => (
          <tr
            key={p.address}
            style={{ cursor: "pointer" }}
            onClick={() => onSelect(p.address)}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLTableRowElement).style.background = L.bgHover;
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLTableRowElement).style.background = "transparent";
            }}
          >
            <td style={{ ...tdStyle, textAlign: "center" }}>
              <span style={{ color: i < 3 ? L.glowGold : L.textMuted }}>{i + 1}</span>
            </td>
            <td style={tdStyle}><ProjectCell project={p} /></td>
            <td style={{ ...tdStyle, textAlign: "right", color: L.glowGold, fontWeight: 600 }}>
              {p.presale ? formatUsd(p.presale.raised) : "--"}
            </td>
            <td style={tdStyle}>
              <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>
                {p.presale?.type.replace(/_/g, " ").toUpperCase() ?? "--"}
              </span>
            </td>
            <td style={{ ...tdStyle, textAlign: "right" }}>
              {p.presale ? formatNumber(p.presale.participants) : "--"}
            </td>
            <td style={tdStyle}>
              {p.presale ? <PresaleBadge status={p.presale.status} /> : "--"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
});

/* ── Locks Table ──────────────────────────────────────────────────────────── */

const LocksTable = memo(function LocksTable({
  projects,
  onSelect,
}: {
  projects: Project[];
  onSelect: (addr: string) => void;
}) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={{ ...thStyle, textAlign: "center", width: 50 }}>RANK</th>
          <th style={thStyle}>PROJECT</th>
          <th style={{ ...thStyle, textAlign: "right" }}>LOCK DAYS</th>
          <th style={{ ...thStyle, textAlign: "right" }}>LOCKED QUSD</th>
          <th style={thStyle}>EXPIRY</th>
          <th style={thStyle}>SIGNAL</th>
        </tr>
      </thead>
      <tbody>
        {projects.map((p, i) => (
          <tr
            key={p.address}
            style={{ cursor: "pointer" }}
            onClick={() => onSelect(p.address)}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLTableRowElement).style.background = L.bgHover;
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLTableRowElement).style.background = "transparent";
            }}
          >
            <td style={{ ...tdStyle, textAlign: "center" }}>
              <span style={{ color: i < 3 ? L.glowGold : L.textMuted }}>{i + 1}</span>
            </td>
            <td style={tdStyle}><ProjectCell project={p} /></td>
            <td style={{ ...tdStyle, textAlign: "right", color: L.glowCyan, fontWeight: 600 }}>
              {p.liquidityLockDays}d
            </td>
            <td style={{ ...tdStyle, textAlign: "right" }}>
              {formatUsd(p.liquidityLockedQusd)}
            </td>
            <td style={tdStyle}>
              <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>
                {new Date(p.liquidityLockExpiry * 1000).toLocaleDateString()}
              </span>
            </td>
            <td style={tdStyle}>
              <ILLPBadge lockDays={p.liquidityLockDays} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
});

/* ── Growth Table ─────────────────────────────────────────────────────────── */

const GrowthTable = memo(function GrowthTable({
  projects,
  onSelect,
}: {
  projects: Project[];
  onSelect: (addr: string) => void;
}) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={{ ...thStyle, textAlign: "center", width: 50 }}>RANK</th>
          <th style={thStyle}>PROJECT</th>
          <th style={{ ...thStyle, textAlign: "right" }}>24H CHANGE</th>
          <th style={{ ...thStyle, textAlign: "right" }}>VOLUME</th>
          <th style={{ ...thStyle, textAlign: "right" }}>HOLDERS</th>
          <th style={{ ...thStyle, textAlign: "right" }}>MARKET CAP</th>
        </tr>
      </thead>
      <tbody>
        {projects.map((p, i) => (
          <tr
            key={p.address}
            style={{ cursor: "pointer" }}
            onClick={() => onSelect(p.address)}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLTableRowElement).style.background = L.bgHover;
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLTableRowElement).style.background = "transparent";
            }}
          >
            <td style={{ ...tdStyle, textAlign: "center" }}>
              <span style={{ color: i < 3 ? L.glowGold : L.textMuted }}>{i + 1}</span>
            </td>
            <td style={tdStyle}><ProjectCell project={p} /></td>
            <td
              style={{
                ...tdStyle,
                textAlign: "right",
                color: p.price24hChange >= 0 ? L.success : L.error,
                fontWeight: 600,
              }}
            >
              {formatPct(p.price24hChange)}
            </td>
            <td style={{ ...tdStyle, textAlign: "right" }}>{formatUsd(p.volume24h)}</td>
            <td style={{ ...tdStyle, textAlign: "right" }}>{formatNumber(p.holderCount)}</td>
            <td style={{ ...tdStyle, textAlign: "right" }}>{formatUsd(p.marketCap)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
});

/* ── Reputation Table ─────────────────────────────────────────────────────── */

const ReputationTable = memo(function ReputationTable({
  projects,
  onSelect,
}: {
  projects: Project[];
  onSelect: (addr: string) => void;
}) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={{ ...thStyle, textAlign: "center", width: 50 }}>RANK</th>
          <th style={thStyle}>PROJECT</th>
          <th style={{ ...thStyle, textAlign: "right" }}>TOTAL STAKED</th>
          <th style={{ ...thStyle, textAlign: "right" }}>VOUCHES</th>
          <th style={{ ...thStyle, textAlign: "right" }}>QPCS</th>
          <th style={thStyle}>TIER</th>
        </tr>
      </thead>
      <tbody>
        {projects.map((p, i) => {
          const totalStaked = p.vouches.reduce((s, v) => s + v.stakeAmountQusd, 0);
          return (
            <tr
              key={p.address}
              style={{ cursor: "pointer" }}
              onClick={() => onSelect(p.address)}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLTableRowElement).style.background = L.bgHover;
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLTableRowElement).style.background = "transparent";
              }}
            >
              <td style={{ ...tdStyle, textAlign: "center" }}>
                <span style={{ color: i < 3 ? L.glowGold : L.textMuted }}>{i + 1}</span>
              </td>
              <td style={tdStyle}><ProjectCell project={p} /></td>
              <td style={{ ...tdStyle, textAlign: "right", color: L.glowGold, fontWeight: 600 }}>
                {formatUsd(totalStaked)} QUSD
              </td>
              <td style={{ ...tdStyle, textAlign: "right" }}>{p.vouches.length}</td>
              <td style={{ ...tdStyle, textAlign: "right", color: L.glowCyan }}>
                {p.qpcs.toFixed(1)}
              </td>
              <td style={tdStyle}><TierBadge tier={p.tier} size="xs" /></td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
});

/* ══════════════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ══════════════════════════════════════════════════════════════════════════════ */

export const LeaderboardView = memo(function LeaderboardView() {
  const leaderboardTab = useLaunchpadStore((s) => s.leaderboardTab);
  const setLeaderboardTab = useLaunchpadStore((s) => s.setLeaderboardTab);
  const setSelectedProject = useLaunchpadStore((s) => s.setSelectedProject);
  const { data: projects, isLoading } = useLeaderboard(leaderboardTab);

  const handleSelect = useCallback(
    (addr: string) => {
      setSelectedProject(addr);
    },
    [setSelectedProject],
  );

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
          LEADERBOARD
        </h2>
        <span style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textMuted }}>
          {projects?.length ?? 0} projects
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
          const active = leaderboardTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setLeaderboardTab(tab.key)}
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

      {/* Table Container */}
      <div
        style={{
          ...panelStyle,
          padding: 0,
          overflow: "auto",
        }}
        className="launchpad-scroll"
      >
        {isLoading ? (
          <div style={{ padding: 32, textAlign: "center" }}>
            <span style={{ fontFamily: FONT.body, fontSize: 13, color: L.textMuted }}>
              Loading leaderboard...
            </span>
          </div>
        ) : !projects || projects.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center" }}>
            <span style={{ fontFamily: FONT.body, fontSize: 13, color: L.textMuted }}>
              No data for this leaderboard.
            </span>
          </div>
        ) : (
          <>
            {leaderboardTab === "qpcs" && (
              <QPCSTable projects={projects} onSelect={handleSelect} />
            )}
            {leaderboardTab === "raises" && (
              <RaisesTable projects={projects} onSelect={handleSelect} />
            )}
            {leaderboardTab === "locks" && (
              <LocksTable projects={projects} onSelect={handleSelect} />
            )}
            {leaderboardTab === "growth" && (
              <GrowthTable projects={projects} onSelect={handleSelect} />
            )}
            {leaderboardTab === "reputation" && (
              <ReputationTable projects={projects} onSelect={handleSelect} />
            )}
          </>
        )}
      </div>
    </div>
  );
});
