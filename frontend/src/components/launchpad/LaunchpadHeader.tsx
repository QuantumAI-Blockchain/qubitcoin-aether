// ─── QBC LAUNCHPAD — Header Bar with Ecosystem Stats Ticker + Navigation ──────
"use client";

import React, { memo, useEffect, useRef, useState } from "react";
import { useEcosystemHealth } from "./hooks";
import { useLaunchpadStore } from "./store";
import type { LaunchpadView } from "./types";
import { formatNumber, formatUsd, timeAgo, L, FONT, panelStyle } from "./shared";

/* ── Navigation Tabs ─────────────────────────────────────────────────────── */

interface NavTab {
  key: LaunchpadView;
  label: string;
}

const TABS: NavTab[] = [
  { key: "discover", label: "DISCOVER" },
  { key: "deploy", label: "DEPLOY" },
  { key: "leaderboard", label: "LEADERBOARD" },
  { key: "ecosystem", label: "ECOSYSTEM" },
  { key: "cdd", label: "COMMUNITY DD" },
  { key: "portfolio", label: "PORTFOLIO" },
];

/* ── Stat Item ───────────────────────────────────────────────────────────── */

interface StatItemProps {
  label: string;
  value: string;
  color?: string;
}

const StatItem = memo(function StatItem({ label, value, color }: StatItemProps) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        whiteSpace: "nowrap",
        paddingRight: 32,
      }}
    >
      <span
        style={{
          fontFamily: FONT.display,
          fontSize: 9,
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
          fontSize: 12,
          color: color ?? L.glowCyan,
          fontWeight: 600,
        }}
      >
        {value}
      </span>
    </span>
  );
});

/* ── Header Component ────────────────────────────────────────────────────── */

const LaunchpadHeader = memo(function LaunchpadHeader() {
  const { data: eco } = useEcosystemHealth();
  const { view, setView, selectedProjectAddr, setSelectedProject } = useLaunchpadStore();
  const tickerRef = useRef<HTMLDivElement>(null);
  const [tickerOffset, setTickerOffset] = useState(0);

  // Ticker animation
  useEffect(() => {
    let rafId: number;
    let offset = 0;
    const speed = 0.4; // px per frame

    const tick = () => {
      offset -= speed;
      if (tickerRef.current) {
        const contentWidth = tickerRef.current.scrollWidth / 2;
        if (Math.abs(offset) >= contentWidth) {
          offset = 0;
        }
      }
      setTickerOffset(offset);
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, []);

  const stats: StatItemProps[] = eco
    ? [
        { label: "PROJECTS LAUNCHED", value: String(eco.totalProjectsLaunched) },
        { label: "TOTAL LIQUIDITY LOCKED", value: formatUsd(eco.totalLiquidityLockedQusd), color: L.glowEmerald },
        { label: ".qbc DOMAINS", value: String(eco.totalQbcDomains), color: L.glowViolet },
        { label: "DD REPORTS", value: String(eco.totalDDReports) },
        { label: "REPUTATION STAKES", value: String(eco.totalReputationStakes), color: L.glowGold },
        { label: "QBC/QUSD", value: "$" + eco.qbcQusdPrice.toFixed(4), color: L.glowCyan },
        { label: "AVG QPCS", value: eco.avgQpcs.toFixed(1) },
        {
          label: "LATEST LAUNCH",
          value: eco.latestLaunch
            ? `${eco.latestLaunch.symbol} (${timeAgo(eco.latestLaunch.time)})`
            : "---",
          color: L.glowGold,
        },
      ]
    : [];

  const showBack = selectedProjectAddr !== null;

  return (
    <div style={{ ...panelStyle, padding: 0, overflow: "hidden" }}>
      {/* ── Ticker Row ─────────────────────────────────────────────────── */}
      <div
        style={{
          width: "100%",
          overflow: "hidden",
          borderBottom: `1px solid ${L.borderSubtle}`,
          padding: "6px 0",
          background: L.bgBase,
        }}
      >
        <div
          ref={tickerRef}
          style={{
            display: "inline-flex",
            transform: `translateX(${tickerOffset}px)`,
            willChange: "transform",
          }}
        >
          {/* Duplicate content for seamless scroll */}
          {[0, 1].map((pass) => (
            <span key={pass} style={{ display: "inline-flex", alignItems: "center" }}>
              {stats.map((s, i) => (
                <StatItem key={`${pass}-${i}`} label={s.label} value={s.value} color={s.color} />
              ))}
            </span>
          ))}
        </div>
      </div>

      {/* ── Navigation Row ─────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 0,
          padding: "0 12px",
          background: L.bgPanel,
        }}
      >
        {showBack && (
          <button
            onClick={() => setSelectedProject(null)}
            style={{
              background: "none",
              border: "none",
              color: L.textSecondary,
              fontFamily: FONT.display,
              fontSize: 11,
              letterSpacing: "0.04em",
              cursor: "pointer",
              padding: "10px 14px 10px 0",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <span style={{ fontSize: 14 }}>{"\u2190"}</span> BACK
          </button>
        )}

        {TABS.map((tab) => {
          const isActive = view === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setView(tab.key)}
              style={{
                background: "none",
                border: "none",
                borderBottom: isActive ? `2px solid ${L.glowCyan}` : "2px solid transparent",
                color: isActive ? L.glowCyan : L.textSecondary,
                fontFamily: FONT.display,
                fontSize: 11,
                letterSpacing: "0.06em",
                cursor: "pointer",
                padding: "10px 16px",
                transition: "color 0.2s, border-color 0.2s",
                boxShadow: isActive ? `0 2px 8px ${L.glowCyan}30` : "none",
                position: "relative",
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.color = L.textPrimary;
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.color = L.textSecondary;
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </div>
  );
});

export default LaunchpadHeader;
