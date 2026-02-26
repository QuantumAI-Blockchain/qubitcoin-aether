// ─── QBC LAUNCHPAD — Discover View (Filters + Project Cards Grid) ─────────────
"use client";

import React, { memo, useMemo, useCallback } from "react";
import type { Project, ProjectTier } from "./types";
import { useProjects } from "./hooks";
import { useLaunchpadStore } from "./store";
import DNAFingerprint from "./DNAFingerprint";
import QPCSGauge from "./QPCSGauge";
import {
  TierBadge,
  VerdictBadge,
  ProgressBar,
  formatNumber,
  formatUsd,
  tierColor,
  contractTypeLabel,
  L,
  FONT,
  panelStyle,
  SkeletonLoader,
  daysRemaining,
} from "./shared";

/* ── Filter Constants ────────────────────────────────────────────────────── */

const TIER_FILTERS: Array<{ key: ProjectTier | "all"; label: string }> = [
  { key: "all", label: "ALL" },
  { key: "protocol", label: "PROTOCOL" },
  { key: "established", label: "ESTABLISHED" },
  { key: "growth", label: "GROWTH" },
  { key: "early", label: "LIVE PRESALE" },
];

const QPCS_MIN_OPTIONS = [
  { value: 0, label: "ANY" },
  { value: 50, label: "50+" },
  { value: 65, label: "65+" },
  { value: 80, label: "80+" },
];

const SORT_OPTIONS: Array<{
  value: "qpcs" | "marketCap" | "volume24h" | "holderCount" | "recent";
  label: string;
}> = [
  { value: "qpcs", label: "QPCS" },
  { value: "marketCap", label: "Market Cap" },
  { value: "volume24h", label: "Volume" },
  { value: "holderCount", label: "Holders" },
  { value: "recent", label: "Recent" },
];

/* ── Toggle Button ───────────────────────────────────────────────────────── */

const ToggleButton = memo(function ToggleButton({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? `${L.glowCyan}15` : "transparent",
        border: `1px solid ${active ? L.glowCyan : L.borderSubtle}`,
        borderRadius: 4,
        color: active ? L.glowCyan : L.textSecondary,
        fontFamily: FONT.display,
        fontSize: 9,
        letterSpacing: "0.04em",
        padding: "4px 8px",
        cursor: "pointer",
        transition: "all 0.15s ease",
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </button>
  );
});

/* ── Filter Pill Button ──────────────────────────────────────────────────── */

const FilterPill = memo(function FilterPill({
  active,
  label,
  color,
  onClick,
}: {
  active: boolean;
  label: string;
  color?: string;
  onClick: () => void;
}) {
  const c = color ?? L.glowCyan;
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? `${c}20` : "transparent",
        border: `1px solid ${active ? c : L.borderSubtle}`,
        borderRadius: 4,
        color: active ? c : L.textSecondary,
        fontFamily: FONT.display,
        fontSize: 10,
        letterSpacing: "0.05em",
        padding: "5px 10px",
        cursor: "pointer",
        transition: "all 0.15s ease",
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </button>
  );
});

/* ── Project Card ────────────────────────────────────────────────────────── */

const ProjectCard = memo(function ProjectCard({
  project,
  onSelect,
}: {
  project: Project;
  onSelect: (addr: string) => void;
}) {
  const tc = tierColor(project.tier);
  const isLowQuality = project.qpcs < 50;
  const isPresaleActive = project.presale?.status === "active";
  const isHighTier = project.tier === "protocol" || project.tier === "established";
  const hasVouch = project.vouches.some((v) => v.voucherTier === "protocol");
  const isVerified = project.communityVerdict === "verified";
  const hasMgtTranches = project.mgtTranches.length > 0;
  const mgtProgress =
    hasMgtTranches
      ? project.mgtTranches.filter((t) => t.status === "released").length /
        project.mgtTranches.length
      : 0;

  const lockRemaining = daysRemaining(project.liquidityLockExpiry);
  const hasMint = project.type === "qrc20_standard" || project.type === "deflationary";
  const hasLockGap = project.liquidityLockDays < 90;

  return (
    <div
      className={isPresaleActive ? "presale-pulse" : undefined}
      style={{
        ...panelStyle,
        padding: 16,
        position: "relative",
        opacity: isLowQuality ? 0.7 : 1,
        overflow: "hidden",
        cursor: "pointer",
        transition: "transform 0.15s ease, box-shadow 0.15s ease",
        ...(isHighTier
          ? {
              borderColor: `${tc}40`,
              boxShadow: `0 0 12px ${tc}15, inset 0 0 12px ${tc}05`,
            }
          : {}),
      }}
      onClick={() => onSelect(project.address)}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = `0 4px 20px ${tc}25`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "translateY(0)";
        e.currentTarget.style.boxShadow = isHighTier
          ? `0 0 12px ${tc}15, inset 0 0 12px ${tc}05`
          : "none";
      }}
    >
      {/* Low quality watermark */}
      {isLowQuality && (
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%) rotate(-30deg)",
            fontFamily: FONT.display,
            fontSize: 14,
            color: L.error,
            opacity: 0.12,
            whiteSpace: "nowrap",
            letterSpacing: "0.15em",
            pointerEvents: "none",
            zIndex: 1,
          }}
        >
          LOW QUALITY SCORE
        </div>
      )}

      {/* Top row: DNA + Logo + Name */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <DNAFingerprint
          hash={project.dnaFingerprint}
          size={20}
          hasMint={hasMint}
          hasLockGap={hasLockGap}
          dilithiumVerified={project.dilithiumSig.startsWith("dilithium3:")}
        />

        {/* Logo placeholder circle */}
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: "50%",
            background: `linear-gradient(135deg, ${tc}30, ${L.bgSurface})`,
            border: `1px solid ${tc}40`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: FONT.display,
            fontSize: 16,
            color: tc,
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          {project.symbol.charAt(0)}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              flexWrap: "wrap",
            }}
          >
            <span
              style={{
                fontFamily: FONT.display,
                fontSize: 13,
                color: L.textPrimary,
                fontWeight: 600,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {project.name}
            </span>
            <span
              style={{
                fontFamily: FONT.mono,
                fontSize: 10,
                color: L.textSecondary,
              }}
            >
              ${project.symbol}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
            <TierBadge tier={project.tier} size="xs" />
            {project.qbcDomain && (
              <span
                style={{
                  fontFamily: FONT.mono,
                  fontSize: 9,
                  color: L.glowViolet,
                  opacity: 0.8,
                }}
              >
                {project.qbcDomain}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* QPCS + Contract type row */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 8,
        }}
      >
        <QPCSGauge score={project.qpcs} grade={project.qpcsGrade} size={60} />
        <div style={{ textAlign: "right" }}>
          <div
            style={{
              fontFamily: FONT.mono,
              fontSize: 9,
              color: L.textMuted,
              marginBottom: 4,
            }}
          >
            {contractTypeLabel(project.type)}
          </div>
          {/* Badges */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 3 }}>
            {hasVouch && (
              <span
                style={{
                  fontFamily: FONT.display,
                  fontSize: 8,
                  color: L.glowGold,
                  letterSpacing: "0.04em",
                }}
              >
                PROTOCOL ENDORSED
              </span>
            )}
            {isVerified && <VerdictBadge verdict="verified" />}
          </div>
        </div>
      </div>

      {/* Liquidity lock info */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "6px 0",
          borderTop: `1px solid ${L.borderSubtle}`,
          borderBottom: `1px solid ${L.borderSubtle}`,
          marginBottom: 8,
        }}
      >
        <div>
          <div
            style={{
              fontFamily: FONT.display,
              fontSize: 8,
              color: L.textMuted,
              letterSpacing: "0.06em",
              marginBottom: 2,
            }}
          >
            LIQUIDITY LOCKED
          </div>
          <div style={{ fontFamily: FONT.mono, fontSize: 11, color: L.glowEmerald }}>
            {formatUsd(project.liquidityLockedQusd)}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div
            style={{
              fontFamily: FONT.display,
              fontSize: 8,
              color: L.textMuted,
              letterSpacing: "0.06em",
              marginBottom: 2,
            }}
          >
            LOCK REMAINING
          </div>
          <div
            style={{
              fontFamily: FONT.mono,
              fontSize: 11,
              color: lockRemaining > 180 ? L.glowCyan : lockRemaining > 30 ? L.warning : L.error,
            }}
          >
            {lockRemaining}d
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 8,
          marginBottom: hasMgtTranches ? 8 : 0,
        }}
      >
        <div>
          <div
            style={{
              fontFamily: FONT.display,
              fontSize: 8,
              color: L.textMuted,
              letterSpacing: "0.06em",
              marginBottom: 1,
            }}
          >
            HOLDERS
          </div>
          <div style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textPrimary }}>
            {formatNumber(project.holderCount)}
          </div>
        </div>
        <div>
          <div
            style={{
              fontFamily: FONT.display,
              fontSize: 8,
              color: L.textMuted,
              letterSpacing: "0.06em",
              marginBottom: 1,
            }}
          >
            VOL 24H
          </div>
          <div style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textPrimary }}>
            {formatUsd(project.volume24h)}
          </div>
        </div>
        <div>
          <div
            style={{
              fontFamily: FONT.display,
              fontSize: 8,
              color: L.textMuted,
              letterSpacing: "0.06em",
              marginBottom: 1,
            }}
          >
            MCAP
          </div>
          <div style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textPrimary }}>
            {formatUsd(project.marketCap)}
          </div>
        </div>
      </div>

      {/* MGT progress */}
      {hasMgtTranches && (
        <div style={{ marginBottom: 8 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginBottom: 3,
            }}
          >
            <span
              style={{
                fontFamily: FONT.display,
                fontSize: 8,
                color: L.textMuted,
                letterSpacing: "0.06em",
              }}
            >
              MGT TRANCHES
            </span>
            <span style={{ fontFamily: FONT.mono, fontSize: 9, color: L.textSecondary }}>
              {project.mgtTranches.filter((t) => t.status === "released").length}/
              {project.mgtTranches.length}
            </span>
          </div>
          <ProgressBar
            value={mgtProgress * 100}
            max={100}
            color={L.glowEmerald}
            height={4}
          />
        </div>
      )}

      {/* View Project button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onSelect(project.address);
        }}
        style={{
          width: "100%",
          padding: "8px 0",
          background: `${tc}15`,
          border: `1px solid ${tc}40`,
          borderRadius: 4,
          color: tc,
          fontFamily: FONT.display,
          fontSize: 10,
          letterSpacing: "0.08em",
          cursor: "pointer",
          transition: "background 0.15s ease",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = `${tc}30`;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = `${tc}15`;
        }}
      >
        VIEW PROJECT
      </button>
    </div>
  );
});

/* ── Discover View ───────────────────────────────────────────────────────── */

const DiscoverView = memo(function DiscoverView() {
  const { data: projects, isLoading } = useProjects();
  const {
    tierFilter,
    setTierFilter,
    minQpcs,
    setMinQpcs,
    searchQuery,
    setSearchQuery,
    sortBy,
    setSortBy,
    showVouchedOnly,
    toggleVouchedOnly,
    showVerifiedOnly,
    toggleVerifiedOnly,
    showDomainsOnly,
    toggleDomainsOnly,
    setSelectedProject,
  } = useLaunchpadStore();

  const handleSelect = useCallback(
    (addr: string) => {
      setSelectedProject(addr);
    },
    [setSelectedProject],
  );

  const filtered = useMemo(() => {
    if (!projects) return [];
    let list = [...projects];

    // Tier filter — "early" maps to live presale
    if (tierFilter !== "all") {
      if (tierFilter === "early") {
        list = list.filter((p) => p.presale?.status === "active");
      } else {
        list = list.filter((p) => p.tier === tierFilter);
      }
    }

    // QPCS minimum
    if (minQpcs > 0) {
      list = list.filter((p) => p.qpcs >= minQpcs);
    }

    // Toggles
    if (showVouchedOnly) {
      list = list.filter((p) => p.vouches.length > 0);
    }
    if (showVerifiedOnly) {
      list = list.filter((p) => p.communityVerdict === "verified");
    }
    if (showDomainsOnly) {
      list = list.filter((p) => p.qbcDomain !== null);
    }

    // Search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.symbol.toLowerCase().includes(q) ||
          p.address.toLowerCase().includes(q) ||
          (p.qbcDomain && p.qbcDomain.toLowerCase().includes(q)),
      );
    }

    // Sort
    switch (sortBy) {
      case "qpcs":
        list.sort((a, b) => b.qpcs - a.qpcs);
        break;
      case "marketCap":
        list.sort((a, b) => b.marketCap - a.marketCap);
        break;
      case "volume24h":
        list.sort((a, b) => b.volume24h - a.volume24h);
        break;
      case "holderCount":
        list.sort((a, b) => b.holderCount - a.holderCount);
        break;
      case "recent":
        list.sort((a, b) => b.deployedAt - a.deployedAt);
        break;
    }

    return list;
  }, [
    projects,
    tierFilter,
    minQpcs,
    showVouchedOnly,
    showVerifiedOnly,
    showDomainsOnly,
    searchQuery,
    sortBy,
  ]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* ── Filter Bar ──────────────────────────────────────────────── */}
      <div
        style={{
          ...panelStyle,
          padding: 12,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {/* Row 1: Tier + QPCS filters */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: 6,
          }}
        >
          {TIER_FILTERS.map((tf) => {
            const tierMap: Record<string, string | undefined> = {
              protocol: L.tierProtocol,
              established: L.tierEstablished,
              growth: L.tierGrowth,
              early: L.tierEarly,
            };
            return (
              <FilterPill
                key={tf.key}
                active={tierFilter === tf.key}
                label={tf.label}
                color={tierMap[tf.key]}
                onClick={() => setTierFilter(tf.key)}
              />
            );
          })}

          <span
            style={{
              width: 1,
              height: 20,
              background: L.borderSubtle,
              margin: "0 4px",
            }}
          />

          <span
            style={{
              fontFamily: FONT.display,
              fontSize: 9,
              color: L.textMuted,
              letterSpacing: "0.04em",
            }}
          >
            MIN QPCS:
          </span>
          {QPCS_MIN_OPTIONS.map((opt) => (
            <FilterPill
              key={opt.value}
              active={minQpcs === opt.value}
              label={opt.label}
              onClick={() => setMinQpcs(opt.value)}
            />
          ))}
        </div>

        {/* Row 2: Sort + Toggles + Search */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: 8,
          }}
        >
          {/* Sort dropdown */}
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span
              style={{
                fontFamily: FONT.display,
                fontSize: 9,
                color: L.textMuted,
                letterSpacing: "0.04em",
              }}
            >
              SORT:
            </span>
            <select
              value={sortBy}
              onChange={(e) =>
                setSortBy(
                  e.target.value as "qpcs" | "marketCap" | "volume24h" | "holderCount" | "recent",
                )
              }
              style={{
                background: L.bgInput,
                border: `1px solid ${L.borderSubtle}`,
                borderRadius: 4,
                color: L.textPrimary,
                fontFamily: FONT.mono,
                fontSize: 10,
                padding: "4px 8px",
                outline: "none",
                cursor: "pointer",
              }}
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <span
            style={{
              width: 1,
              height: 20,
              background: L.borderSubtle,
            }}
          />

          {/* Toggle filters */}
          <ToggleButton
            active={showDomainsOnly}
            label=".qbc DOMAINS ONLY"
            onClick={toggleDomainsOnly}
          />
          <ToggleButton
            active={showVouchedOnly}
            label="VOUCHED ONLY"
            onClick={toggleVouchedOnly}
          />
          <ToggleButton
            active={showVerifiedOnly}
            label="VERIFIED ONLY"
            onClick={toggleVerifiedOnly}
          />

          {/* Search input — flex-grow to fill remaining space */}
          <div style={{ flex: 1, minWidth: 140 }}>
            <input
              type="text"
              placeholder="Search name, symbol, address..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: "100%",
                background: L.bgInput,
                border: `1px solid ${L.borderSubtle}`,
                borderRadius: 4,
                color: L.textPrimary,
                fontFamily: FONT.mono,
                fontSize: 11,
                padding: "6px 10px",
                outline: "none",
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = L.borderFocus;
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = L.borderSubtle;
              }}
            />
          </div>
        </div>
      </div>

      {/* ── Results count ───────────────────────────────────────────── */}
      <div
        style={{
          fontFamily: FONT.mono,
          fontSize: 11,
          color: L.textSecondary,
          padding: "0 4px",
        }}
      >
        {isLoading ? "Loading..." : `${filtered.length} projects`}
      </div>

      {/* ── Project Cards Grid ──────────────────────────────────────── */}
      {isLoading ? (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 12,
          }}
        >
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} style={{ ...panelStyle, padding: 16 }}>
              <SkeletonLoader height={160} />
            </div>
          ))}
        </div>
      ) : (
        <>
          <style>{`
            .discover-grid {
              display: grid;
              grid-template-columns: repeat(3, 1fr);
              gap: 12px;
            }
            @media (max-width: 1024px) {
              .discover-grid {
                grid-template-columns: repeat(2, 1fr);
              }
            }
            @media (max-width: 640px) {
              .discover-grid {
                grid-template-columns: 1fr;
              }
            }
          `}</style>
          <div className="discover-grid">
            {filtered.map((p) => (
              <ProjectCard key={p.address} project={p} onSelect={handleSelect} />
            ))}
          </div>

          {filtered.length === 0 && !isLoading && (
            <div
              style={{
                textAlign: "center",
                padding: "48px 16px",
                fontFamily: FONT.body,
                fontSize: 14,
                color: L.textSecondary,
              }}
            >
              No projects match your filters. Try broadening your search.
            </div>
          )}
        </>
      )}
    </div>
  );
});

export default DiscoverView;
