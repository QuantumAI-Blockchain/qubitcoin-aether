// ─── QBC LAUNCHPAD — Community Due Diligence Board ──────────────────────────
"use client";

import React, { memo, useState, useMemo, useCallback } from "react";
import { useAllDDReports, useProjects } from "./hooks";
import { DD_CATEGORIES, FEE_CONFIG } from "./config";
import type { DDReport, DDCategory, Project } from "./types";
import {
  TierBadge,
  VerdictBadge,
  CopyButton,
  ProgressBar,
  formatNumber,
  formatAddr,
  timeAgo,
  L,
  FONT,
  panelStyle,
  inputStyle,
} from "./shared";

/* ── Types ──────────────────────────────────────────────────────────────────── */

type OutcomeFilter = "all" | "verified" | "flagged" | "neutral" | "pending";
type SortMode = "newest" | "most_votes" | "highest_positive";

/* ── Component ──────────────────────────────────────────────────────────────── */

export const CommunityDDView = memo(function CommunityDDView() {
  const { data: reports } = useAllDDReports();
  const { data: projects } = useProjects();

  /* ── Filter / Sort State ─────────────────────────────────────────────────── */
  const [projectFilter, setProjectFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<DDCategory | "all">("all");
  const [verdictFilter, setVerdictFilter] = useState<OutcomeFilter>("all");
  const [sortMode, setSortMode] = useState<SortMode>("newest");

  /* ── Submit form state ───────────────────────────────────────────────────── */
  const [showForm, setShowForm] = useState(false);
  const [formProject, setFormProject] = useState<string>("");
  const [formCategory, setFormCategory] = useState<DDCategory>("contract");
  const [formTitle, setFormTitle] = useState("");
  const [formContent, setFormContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  /* ── Expanded reports ────────────────────────────────────────────────────── */
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleExpand = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  /* ── Project lookup ──────────────────────────────────────────────────────── */
  const projectMap = useMemo(() => {
    const map = new Map<string, Project>();
    if (projects) {
      for (const p of projects) map.set(p.address, p);
    }
    return map;
  }, [projects]);

  /* ── Filter + sort ───────────────────────────────────────────────────────── */
  const filtered = useMemo(() => {
    if (!reports) return [];
    let list = [...reports];

    if (projectFilter !== "all") {
      list = list.filter((r) => r.projectAddress === projectFilter);
    }
    if (categoryFilter !== "all") {
      list = list.filter((r) => r.category === categoryFilter);
    }
    if (verdictFilter !== "all") {
      list = list.filter((r) => r.outcome === verdictFilter);
    }

    switch (sortMode) {
      case "newest":
        list.sort((a, b) => b.timestamp - a.timestamp);
        break;
      case "most_votes":
        list.sort(
          (a, b) =>
            b.positiveVotes + b.negativeVotes - (a.positiveVotes + a.negativeVotes)
        );
        break;
      case "highest_positive":
        list.sort((a, b) => b.positivePercent - a.positivePercent);
        break;
    }
    return list;
  }, [reports, projectFilter, categoryFilter, verdictFilter, sortMode]);

  /* ── Stats ───────────────────────────────────────────────────────────────── */
  const stats = useMemo(() => {
    if (!reports || reports.length === 0) {
      return { total: 0, verified: 0, flagged: 0, avgPositive: 0 };
    }
    const verified = reports.filter((r) => r.outcome === "verified").length;
    const flagged = reports.filter((r) => r.outcome === "flagged").length;
    const avgPositive =
      reports.reduce((s, r) => s + r.positivePercent, 0) / reports.length;
    return { total: reports.length, verified, flagged, avgPositive };
  }, [reports]);

  /* ── Form submit handler ─────────────────────────────────────────────────── */
  const handleSubmit = useCallback(() => {
    if (!formTitle.trim() || !formContent.trim() || !formProject) return;
    setSubmitting(true);
    setTimeout(() => {
      setSubmitting(false);
      setSubmitted(true);
      setShowForm(false);
      setFormTitle("");
      setFormContent("");
      setFormProject("");
      setFormCategory("contract");
      setTimeout(() => setSubmitted(false), 3000);
    }, 1000);
  }, [formTitle, formContent, formProject]);

  /* ── Category badge helper ───────────────────────────────────────────────── */
  const catMeta = useMemo(() => {
    const map = new Map<string, { icon: string; label: string }>();
    for (const c of DD_CATEGORIES) map.set(c.key, { icon: c.icon, label: c.label });
    return map;
  }, []);

  /* ── Outcome badge helper ────────────────────────────────────────────────── */
  const outcomeStyle = useCallback(
    (outcome: DDReport["outcome"]): { color: string; label: string; icon: string } => {
      switch (outcome) {
        case "verified":
          return { color: L.success, label: "VERIFIED", icon: "\u2713" };
        case "flagged":
          return { color: L.error, label: "FLAGGED", icon: "\u2717" };
        case "neutral":
          return { color: L.textSecondary, label: "NEUTRAL", icon: "\u2014" };
        case "pending":
          return { color: L.warning, label: "PENDING", icon: "\u25CB" };
      }
    },
    []
  );

  /* ── Render ───────────────────────────────────────────────────────────────── */
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Stats Bar */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 12,
        }}
      >
        {[
          { label: "TOTAL REPORTS", value: formatNumber(stats.total), color: L.glowCyan },
          { label: "VERIFIED", value: formatNumber(stats.verified), color: L.success },
          { label: "FLAGGED", value: formatNumber(stats.flagged), color: L.error },
          {
            label: "AVG POSITIVE %",
            value: stats.avgPositive.toFixed(1) + "%",
            color: L.glowGold,
          },
        ].map((s) => (
          <div
            key={s.label}
            style={{
              ...panelStyle,
              padding: "12px 16px",
              textAlign: "center",
            }}
          >
            <div
              style={{
                fontFamily: FONT.display,
                fontSize: 9,
                color: L.textSecondary,
                letterSpacing: "0.06em",
                marginBottom: 4,
              }}
            >
              {s.label}
            </div>
            <div
              style={{
                fontFamily: FONT.mono,
                fontSize: 20,
                color: s.color,
              }}
            >
              {s.value}
            </div>
          </div>
        ))}
      </div>

      {/* Submit button / success toast */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <button
          onClick={() => setShowForm(!showForm)}
          style={{
            fontFamily: FONT.display,
            fontSize: 11,
            letterSpacing: "0.06em",
            padding: "8px 20px",
            borderRadius: 6,
            border: `1px solid ${L.glowCyan}60`,
            background: showForm ? L.bgHover : L.glowCyan + "14",
            color: L.glowCyan,
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
        >
          {showForm ? "CANCEL" : "SUBMIT DD REPORT"}
        </button>
        {submitted && (
          <span
            style={{
              fontFamily: FONT.body,
              fontSize: 12,
              color: L.success,
              padding: "6px 14px",
              background: L.success + "14",
              border: `1px solid ${L.success}40`,
              borderRadius: 4,
            }}
          >
            Report submitted successfully. Will be stored on QVM after backend integration.
          </span>
        )}
      </div>

      {/* Submit form */}
      {showForm && (
        <div style={{ ...panelStyle, padding: 20 }}>
          <div
            style={{
              fontFamily: FONT.display,
              fontSize: 13,
              color: L.textPrimary,
              letterSpacing: "0.04em",
              marginBottom: 16,
            }}
          >
            NEW DD REPORT
          </div>

          {/* Project selector */}
          <div style={{ marginBottom: 12 }}>
            <label style={formLabelStyle}>PROJECT</label>
            <select
              value={formProject}
              onChange={(e) => setFormProject(e.target.value)}
              style={{ ...inputStyle, cursor: "pointer" }}
            >
              <option value="">Select project...</option>
              {projects?.map((p) => (
                <option key={p.address} value={p.address}>
                  {p.name} ({p.symbol})
                </option>
              ))}
            </select>
          </div>

          {/* Category selector */}
          <div style={{ marginBottom: 12 }}>
            <label style={formLabelStyle}>CATEGORY</label>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {DD_CATEGORIES.map((cat) => (
                <button
                  key={cat.key}
                  onClick={() => setFormCategory(cat.key)}
                  style={{
                    fontFamily: FONT.body,
                    fontSize: 12,
                    padding: "6px 12px",
                    borderRadius: 4,
                    border: `1px solid ${
                      formCategory === cat.key ? L.glowCyan + "60" : L.borderSubtle
                    }`,
                    background:
                      formCategory === cat.key ? L.glowCyan + "14" : "transparent",
                    color:
                      formCategory === cat.key ? L.glowCyan : L.textSecondary,
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  {cat.icon} {cat.label}
                </button>
              ))}
            </div>
          </div>

          {/* Title */}
          <div style={{ marginBottom: 12 }}>
            <label style={formLabelStyle}>TITLE</label>
            <input
              type="text"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              placeholder="e.g. Contract Review — ALPH"
              style={inputStyle}
            />
          </div>

          {/* Content */}
          <div style={{ marginBottom: 12 }}>
            <label style={formLabelStyle}>
              CONTENT{" "}
              <span style={{ color: L.textMuted, fontFamily: FONT.mono, fontSize: 10 }}>
                ({formContent.length}/2000)
              </span>
            </label>
            <textarea
              value={formContent}
              onChange={(e) =>
                setFormContent(e.target.value.slice(0, 2000))
              }
              placeholder="Detailed analysis... Markdown supported."
              rows={6}
              style={{
                ...inputStyle,
                resize: "vertical",
                minHeight: 100,
              }}
            />
          </div>

          {/* Notices */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 4,
              marginBottom: 16,
            }}
          >
            <span
              style={{
                fontFamily: FONT.body,
                fontSize: 11,
                color: L.warning,
              }}
            >
              Requires {"\u2265"} {FEE_CONFIG.ddReportMinQbc} QBC to submit
            </span>
            <span
              style={{
                fontFamily: FONT.body,
                fontSize: 11,
                color: L.textMuted,
              }}
            >
              Reports will be Dilithium2-signed and stored on QVM when backend is connected
            </span>
          </div>

          {/* Buttons */}
          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={handleSubmit}
              disabled={
                submitting || !formTitle.trim() || !formContent.trim() || !formProject
              }
              style={{
                fontFamily: FONT.display,
                fontSize: 11,
                letterSpacing: "0.06em",
                padding: "8px 24px",
                borderRadius: 6,
                border: "none",
                background:
                  submitting || !formTitle.trim() || !formContent.trim() || !formProject
                    ? L.textMuted
                    : L.glowCyan,
                color: L.textInverse,
                cursor:
                  submitting || !formTitle.trim() || !formContent.trim() || !formProject
                    ? "not-allowed"
                    : "pointer",
                transition: "all 0.15s ease",
              }}
            >
              {submitting ? "SUBMITTING..." : "SUBMIT"}
            </button>
            <button
              onClick={() => setShowForm(false)}
              style={{
                fontFamily: FONT.display,
                fontSize: 11,
                letterSpacing: "0.06em",
                padding: "8px 24px",
                borderRadius: 6,
                border: `1px solid ${L.borderSubtle}`,
                background: "transparent",
                color: L.textSecondary,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              CANCEL
            </button>
          </div>
        </div>
      )}

      {/* Filter Bar */}
      <div
        style={{
          display: "flex",
          gap: 10,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        {/* Project dropdown */}
        <select
          value={projectFilter}
          onChange={(e) => setProjectFilter(e.target.value)}
          style={{ ...inputStyle, width: 200, cursor: "pointer" }}
        >
          <option value="all">All Projects</option>
          {projects?.map((p) => (
            <option key={p.address} value={p.address}>
              {p.name}
            </option>
          ))}
        </select>

        {/* Category dropdown */}
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value as DDCategory | "all")}
          style={{ ...inputStyle, width: 160, cursor: "pointer" }}
        >
          <option value="all">All Categories</option>
          {DD_CATEGORIES.map((c) => (
            <option key={c.key} value={c.key}>
              {c.icon} {c.label}
            </option>
          ))}
        </select>

        {/* Verdict dropdown */}
        <select
          value={verdictFilter}
          onChange={(e) => setVerdictFilter(e.target.value as OutcomeFilter)}
          style={{ ...inputStyle, width: 140, cursor: "pointer" }}
        >
          <option value="all">All Verdicts</option>
          <option value="verified">Verified</option>
          <option value="flagged">Flagged</option>
          <option value="neutral">Neutral</option>
          <option value="pending">Pending</option>
        </select>

        {/* Sort dropdown */}
        <select
          value={sortMode}
          onChange={(e) => setSortMode(e.target.value as SortMode)}
          style={{ ...inputStyle, width: 160, cursor: "pointer" }}
        >
          <option value="newest">Newest</option>
          <option value="most_votes">Most Votes</option>
          <option value="highest_positive">Highest Positive %</option>
        </select>

        <span
          style={{
            fontFamily: FONT.mono,
            fontSize: 11,
            color: L.textMuted,
            marginLeft: "auto",
          }}
        >
          {filtered.length} report{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Report Feed */}
      <div
        className="launchpad-scroll"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 10,
          maxHeight: 700,
          overflowY: "auto",
          paddingRight: 4,
        }}
      >
        {filtered.length === 0 && (
          <div
            style={{
              textAlign: "center",
              padding: 40,
              color: L.textMuted,
              fontFamily: FONT.body,
              fontSize: 13,
            }}
          >
            No reports match the current filters.
          </div>
        )}

        {filtered.map((report) => {
          const project = projectMap.get(report.projectAddress);
          const cat = catMeta.get(report.category);
          const outcome = outcomeStyle(report.outcome);
          const expanded = expandedIds.has(report.id);
          const needsTruncation = report.content.length > 200;
          const displayContent =
            expanded || !needsTruncation
              ? report.content
              : report.content.slice(0, 200) + "...";
          const totalVotes = report.positiveVotes + report.negativeVotes;

          return (
            <div key={report.id} style={{ ...panelStyle, padding: 16 }}>
              {/* Header row */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  flexWrap: "wrap",
                  marginBottom: 8,
                }}
              >
                {project && (
                  <span
                    style={{
                      fontFamily: FONT.display,
                      fontSize: 11,
                      color: L.textPrimary,
                      letterSpacing: "0.04em",
                    }}
                  >
                    {project.symbol}
                  </span>
                )}
                {project && <TierBadge tier={project.tier} size="xs" />}
                {cat && (
                  <span
                    style={{
                      fontFamily: FONT.body,
                      fontSize: 10,
                      color: L.glowCyan,
                      background: L.glowCyan + "14",
                      border: `1px solid ${L.glowCyan}30`,
                      borderRadius: 3,
                      padding: "2px 6px",
                    }}
                  >
                    {cat.icon} {cat.label}
                  </span>
                )}
                <span
                  style={{
                    marginLeft: "auto",
                    fontFamily: FONT.mono,
                    fontSize: 10,
                    color: L.textMuted,
                  }}
                >
                  {timeAgo(report.timestamp)}
                </span>
              </div>

              {/* Title */}
              <div
                style={{
                  fontFamily: FONT.display,
                  fontSize: 13,
                  color: L.textPrimary,
                  letterSpacing: "0.03em",
                  marginBottom: 6,
                }}
              >
                {report.title}
              </div>

              {/* Content */}
              <div
                style={{
                  fontFamily: FONT.body,
                  fontSize: 12,
                  lineHeight: "18px",
                  color: L.textSecondary,
                  marginBottom: 10,
                  whiteSpace: "pre-wrap",
                }}
              >
                {displayContent}
                {needsTruncation && (
                  <button
                    onClick={() => toggleExpand(report.id)}
                    style={{
                      background: "none",
                      border: "none",
                      color: L.glowCyan,
                      cursor: "pointer",
                      fontFamily: FONT.body,
                      fontSize: 11,
                      padding: "0 4px",
                      marginLeft: 2,
                    }}
                  >
                    {expanded ? "Show less" : "Read more"}
                  </button>
                )}
              </div>

              {/* Author row */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginBottom: 10,
                }}
              >
                <span
                  style={{
                    fontFamily: FONT.mono,
                    fontSize: 11,
                    color: L.textMuted,
                  }}
                >
                  {formatAddr(report.author, 8)}
                </span>
                <CopyButton text={report.author} />
                <span
                  style={{
                    fontFamily: FONT.mono,
                    fontSize: 9,
                    color: L.glowGold,
                    background: L.glowGold + "14",
                    border: `1px solid ${L.glowGold}30`,
                    borderRadius: 3,
                    padding: "2px 6px",
                  }}
                >
                  {formatNumber(report.authorQbcBalance)} QBC
                </span>
              </div>

              {/* Vote bar */}
              <div style={{ marginBottom: 10 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 4,
                  }}
                >
                  <span
                    style={{
                      fontFamily: FONT.mono,
                      fontSize: 10,
                      color: L.success,
                    }}
                  >
                    +{report.positiveVotes}
                  </span>
                  <span
                    style={{
                      fontFamily: FONT.mono,
                      fontSize: 10,
                      color: L.textSecondary,
                    }}
                  >
                    {report.positivePercent}% positive ({totalVotes} votes)
                  </span>
                  <span
                    style={{
                      fontFamily: FONT.mono,
                      fontSize: 10,
                      color: L.error,
                    }}
                  >
                    -{report.negativeVotes}
                  </span>
                </div>
                <div
                  style={{
                    display: "flex",
                    width: "100%",
                    height: 6,
                    borderRadius: 3,
                    overflow: "hidden",
                    background: L.bgBase,
                  }}
                >
                  <div
                    style={{
                      width: `${report.positivePercent}%`,
                      height: "100%",
                      background: L.success,
                      borderRadius: report.positivePercent === 100 ? 3 : "3px 0 0 3px",
                      transition: "width 0.3s ease",
                    }}
                  />
                  <div
                    style={{
                      width: `${100 - report.positivePercent}%`,
                      height: "100%",
                      background: L.error,
                      borderRadius:
                        report.positivePercent === 0 ? 3 : "0 3px 3px 0",
                      transition: "width 0.3s ease",
                    }}
                  />
                </div>
              </div>

              {/* Outcome badge */}
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  fontFamily: FONT.display,
                  fontSize: 9,
                  letterSpacing: "0.05em",
                  color: outcome.color,
                  border: `1px solid ${outcome.color}40`,
                  borderRadius: 4,
                  padding: "3px 8px",
                  textTransform: "uppercase",
                }}
              >
                {outcome.icon} {outcome.label}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});

/* ── Inline Style Helpers ─────────────────────────────────────────────────── */

const formLabelStyle: React.CSSProperties = {
  display: "block",
  fontFamily: FONT.display,
  fontSize: 9,
  color: L.textSecondary,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  marginBottom: 4,
};
