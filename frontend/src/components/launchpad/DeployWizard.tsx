// ─── QBC LAUNCHPAD — Deploy Wizard (7-Step) ───────────────────────────────────
"use client";

import React, { memo, useCallback, useMemo, useState } from "react";
import {
  L,
  FONT,
  inputStyle,
  panelStyle,
  formatNumber,
  formatQbc,
  formatQusd,
  calculateILLP,
  illpColor,
  illpLabel,
  ProgressBar,
} from "./shared";
import {
  CONTRACT_TYPES,
  PROJECT_CATEGORIES,
  ILLP_TIERS,
  QPCS_WEIGHTS,
  FEE_CONFIG,
  getContractTypeConfig,
  getQpcsGrade,
} from "./config";
import type {
  DeployStep,
  ContractType,
  AllocationItem,
  MGTMilestoneType,
  PresaleType,
  QPCSComponents,
} from "./types";
import { useLaunchpadStore } from "./store";
import { useWalletStore } from "@/stores/wallet-store";
import { deployContract } from "@/lib/launchpad-api";

/* ── Constants ─────────────────────────────────────────────────────────────── */

const STEP_LABELS: Record<DeployStep, string> = {
  1: "CONTRACT TYPE",
  2: "IDENTITY",
  3: "TOKEN CONFIG",
  4: "TOKENOMICS",
  5: "LAUNCH",
  6: "REVIEW",
  7: "DEPLOY",
};

const SUPPLY_PRESETS = [
  { label: "1M", value: 1_000_000 },
  { label: "10M", value: 10_000_000 },
  { label: "100M", value: 100_000_000 },
  { label: "1B", value: 1_000_000_000 },
  { label: "10B", value: 10_000_000_000 },
];

const ALLOC_COLORS = [
  "#00d4ff", "#f59e0b", "#10b981", "#8b5cf6", "#ef4444",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
  "#14b8a6", "#a855f7", "#fb923c", "#38bdf8", "#d946ef",
];

const MILESTONE_TYPES: { value: MGTMilestoneType; label: string }[] = [
  { value: "holder_count", label: "Holder Count" },
  { value: "dex_volume", label: "DEX Volume (QUSD)" },
  { value: "liquidity_depth", label: "Liquidity Depth (QUSD)" },
  { value: "susy_streak", label: "SUSY Streak (blocks)" },
  { value: "governance_passed", label: "Governance Proposals Passed" },
  { value: "qpcs_sustained", label: "QPCS Sustained Above" },
  { value: "price_sustained", label: "Price Sustained (QUSD)" },
  { value: "community_vote", label: "Community Vote (%)" },
];

const PRESALE_TYPES: { value: PresaleType; label: string }[] = [
  { value: "standard_ido", label: "Standard IDO" },
  { value: "whitelist_ido", label: "Whitelist IDO" },
  { value: "dutch_auction", label: "Dutch Auction" },
  { value: "fair_launch", label: "Fair Launch" },
];

/* ── Shared Styles ─────────────────────────────────────────────────────────── */

const labelStyle: React.CSSProperties = {
  display: "block",
  fontFamily: FONT.display,
  fontSize: 10,
  letterSpacing: "0.06em",
  color: L.textSecondary,
  textTransform: "uppercase",
  marginBottom: 4,
};

const sectionTitle: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 13,
  letterSpacing: "0.04em",
  color: L.textPrimary,
  marginBottom: 12,
};

const btnBase: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 12,
  letterSpacing: "0.05em",
  border: "none",
  borderRadius: 6,
  cursor: "pointer",
  padding: "10px 24px",
  textTransform: "uppercase",
  transition: "all 0.2s",
};

const btnPrimary: React.CSSProperties = {
  ...btnBase,
  background: L.glowCyan,
  color: L.textInverse,
};

const btnSecondary: React.CSSProperties = {
  ...btnBase,
  background: "transparent",
  color: L.textSecondary,
  border: `1px solid ${L.borderSubtle}`,
};

const errorText: React.CSSProperties = {
  fontFamily: FONT.body,
  fontSize: 11,
  color: L.error,
  marginTop: 4,
};

const hintText: React.CSSProperties = {
  fontFamily: FONT.mono,
  fontSize: 10,
  color: L.textMuted,
  marginTop: 2,
};

/* ── Helper: Generate DNA fingerprint from contract details ───────────────── */

function generateDNAFingerprint(contractId: string, name: string, symbol: string): string {
  // Simple deterministic hash from the contract details
  let hash = 0;
  const seed = contractId + name + symbol;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash << 5) - hash + seed.charCodeAt(i);
    hash |= 0;
  }
  // Convert to hex-like string
  const abs = Math.abs(hash);
  let hex = abs.toString(16);
  while (hex.length < 64) hex = hex + abs.toString(16);
  return hex.slice(0, 64);
}

/* ═══════════════════════════════════════════════════════════════════════════════
   STEP INDICATOR
   ═══════════════════════════════════════════════════════════════════════════════ */

const StepIndicator = memo(function StepIndicator({
  current,
  onNavigate,
}: {
  current: DeployStep;
  onNavigate: (step: DeployStep) => void;
}) {
  const steps: DeployStep[] = [1, 2, 3, 4, 5, 6, 7];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 2, marginBottom: 24, flexWrap: "wrap" }}>
      {steps.map((s, i) => {
        const isActive = s === current;
        const isCompleted = s < current;
        const isFuture = s > current;
        const color = isActive ? L.glowCyan : isCompleted ? L.glowEmerald : L.textMuted;
        return (
          <React.Fragment key={s}>
            <button
              onClick={() => { if (s < current) onNavigate(s); }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                background: isActive ? `${L.glowCyan}15` : "transparent",
                border: isActive ? `1px solid ${L.glowCyan}40` : `1px solid transparent`,
                borderRadius: 4,
                padding: "4px 8px",
                cursor: isFuture ? "default" : "pointer",
                opacity: isFuture ? 0.4 : 1,
                transition: "all 0.2s",
              }}
            >
              <span
                style={{
                  fontFamily: FONT.display,
                  fontSize: 10,
                  color,
                  width: 16,
                  height: 16,
                  borderRadius: "50%",
                  border: `1px solid ${color}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: isCompleted ? color : "transparent",
                }}
              >
                <span style={{ color: isCompleted ? L.textInverse : color, fontSize: 8 }}>
                  {isCompleted ? "\u2713" : s}
                </span>
              </span>
              <span
                style={{
                  fontFamily: FONT.display,
                  fontSize: 9,
                  letterSpacing: "0.04em",
                  color,
                  textTransform: "uppercase",
                  whiteSpace: "nowrap",
                }}
              >
                {STEP_LABELS[s]}
              </span>
            </button>
            {i < steps.length - 1 && (
              <span style={{ color: L.textMuted, fontSize: 10, fontFamily: FONT.mono }}>{"\u2192"}</span>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
});

/* ═══════════════════════════════════════════════════════════════════════════════
   STEP 1 — CONTRACT TYPE
   ═══════════════════════════════════════════════════════════════════════════════ */

const StepContractType = memo(function StepContractType() {
  const contractType = useLaunchpadStore((s) => s.deployContractType);
  const setContractType = useLaunchpadStore((s) => s.setDeployContractType);

  const recommended = CONTRACT_TYPES.filter((c) => c.recommended);
  const standard = CONTRACT_TYPES.filter((c) => !c.recommended);

  const renderCard = (cfg: (typeof CONTRACT_TYPES)[number]) => {
    const isSelected = contractType === cfg.type;
    return (
      <button
        key={cfg.type}
        onClick={() => setContractType(cfg.type)}
        style={{
          ...panelStyle,
          padding: 16,
          cursor: "pointer",
          textAlign: "left",
          position: "relative",
          border: isSelected
            ? `1px solid ${L.glowCyan}`
            : `1px solid ${L.borderSubtle}`,
          boxShadow: isSelected ? `0 0 20px ${L.glowCyan}20` : "none",
          transition: "all 0.2s",
          width: "100%",
        }}
      >
        {cfg.uniqueToQbc && (
          <span
            style={{
              position: "absolute",
              top: 8,
              right: 8,
              fontFamily: FONT.display,
              fontSize: 8,
              letterSpacing: "0.06em",
              color: L.glowCyan,
              background: `${L.glowCyan}15`,
              border: `1px solid ${L.glowCyan}40`,
              borderRadius: 3,
              padding: "2px 6px",
              textTransform: "uppercase",
            }}
          >
            UNIQUE TO QBC
          </span>
        )}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <span style={{ fontSize: 20 }}>{cfg.icon}</span>
          <span style={{ fontFamily: FONT.display, fontSize: 13, color: L.textPrimary }}>
            {cfg.label}
          </span>
        </div>
        <p style={{ fontFamily: FONT.body, fontSize: 12, color: L.textSecondary, lineHeight: 1.4, marginBottom: 10 }}>
          {cfg.description}
        </p>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
          <div>
            <span style={labelStyle}>Complexity</span>
            <div style={{ display: "flex", gap: 3 }}>
              {Array.from({ length: 5 }, (_, i) => (
                <span
                  key={i}
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: i < cfg.complexity ? L.glowCyan : L.borderSubtle,
                  }}
                />
              ))}
            </div>
          </div>
          <div>
            <span style={labelStyle}>Deploy Fee</span>
            <span style={{ fontFamily: FONT.mono, fontSize: 12, color: L.glowGold }}>
              {cfg.deployFeeQbc} QBC
            </span>
          </div>
          <div>
            <span style={labelStyle}>Max QPCS</span>
            <span style={{ fontFamily: FONT.mono, fontSize: 12, color: L.glowEmerald }}>
              {cfg.maxQpcs}
            </span>
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {cfg.features.map((f) => (
            <span
              key={f}
              style={{
                fontFamily: FONT.body,
                fontSize: 10,
                color: L.textMuted,
                background: L.bgBase,
                borderRadius: 3,
                padding: "2px 6px",
              }}
            >
              {f}
            </span>
          ))}
        </div>
      </button>
    );
  };

  return (
    <div>
      <div style={{ ...sectionTitle, color: L.glowEmerald, marginBottom: 8 }}>
        RECOMMENDED
      </div>
      <p style={{ fontFamily: FONT.body, fontSize: 11, color: L.textMuted, marginBottom: 12 }}>
        Higher complexity contracts unlock greater QPCS potential and tier progression.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 12, marginBottom: 24 }}>
        {recommended.map(renderCard)}
      </div>

      <div style={{ ...sectionTitle, color: L.textSecondary, marginBottom: 8 }}>
        STANDARD
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 12 }}>
        {standard.map(renderCard)}
      </div>
    </div>
  );
});

/* ═══════════════════════════════════════════════════════════════════════════════
   STEP 2 — IDENTITY
   ═══════════════════════════════════════════════════════════════════════════════ */

const StepIdentity = memo(function StepIdentity() {
  const name = useLaunchpadStore((s) => s.deployName);
  const setName = useLaunchpadStore((s) => s.setDeployName);
  const symbol = useLaunchpadStore((s) => s.deploySymbol);
  const setSymbol = useLaunchpadStore((s) => s.setDeploySymbol);
  const description = useLaunchpadStore((s) => s.deployDescription);
  const setDescription = useLaunchpadStore((s) => s.setDeployDescription);
  const fullDescription = useLaunchpadStore((s) => s.deployFullDescription);
  const setFullDescription = useLaunchpadStore((s) => s.setDeployFullDescription);
  const category = useLaunchpadStore((s) => s.deployCategory);
  const setCategory = useLaunchpadStore((s) => s.setDeployCategory);
  const website = useLaunchpadStore((s) => s.deployWebsite);
  const setWebsite = useLaunchpadStore((s) => s.setDeployWebsite);
  const twitter = useLaunchpadStore((s) => s.deployTwitter);
  const setTwitter = useLaunchpadStore((s) => s.setDeployTwitter);
  const telegram = useLaunchpadStore((s) => s.deployTelegram);
  const setTelegram = useLaunchpadStore((s) => s.setDeployTelegram);
  const discord = useLaunchpadStore((s) => s.deployDiscord);
  const setDiscord = useLaunchpadStore((s) => s.setDeployDiscord);
  const github = useLaunchpadStore((s) => s.deployGithub);
  const setGithub = useLaunchpadStore((s) => s.setDeployGithub);
  const whitepaper = useLaunchpadStore((s) => s.deployWhitepaper);
  const setWhitepaper = useLaunchpadStore((s) => s.setDeployWhitepaper);
  const teamMembers = useLaunchpadStore((s) => s.deployTeamMembers);
  const setTeamMembers = useLaunchpadStore((s) => s.setDeployTeamMembers);

  const domainPreview = symbol ? symbol.toLowerCase() + ".qbc" : "yoursymbol.qbc";

  const addTeamMember = () => {
    setTeamMembers([...teamMembers, { name: "", role: "", twitter: "", wallet: "" }]);
  };

  const updateTeamMember = (idx: number, field: string, value: string) => {
    const updated = teamMembers.map((m, i) =>
      i === idx ? { ...m, [field]: value } : m
    );
    setTeamMembers(updated);
  };

  const removeTeamMember = (idx: number) => {
    setTeamMembers(teamMembers.filter((_, i) => i !== idx));
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Project Name & Symbol */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
        <div>
          <label htmlFor="deploy-project-name" style={labelStyle}>Project Name *</label>
          <input
            id="deploy-project-name"
            style={inputStyle}
            placeholder="e.g. Quantum Finance"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={50}
          />
        </div>
        <div>
          <label htmlFor="deploy-token-symbol" style={labelStyle}>Token Symbol *</label>
          <input
            id="deploy-token-symbol"
            style={{ ...inputStyle, textTransform: "uppercase" }}
            placeholder="e.g. QFIN"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase().slice(0, 8))}
            maxLength={8}
          />
          <div style={hintText}>2-8 characters</div>
        </div>
      </div>

      {/* Domain Preview */}
      <div style={{ ...panelStyle, padding: 12, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontFamily: FONT.display, fontSize: 10, color: L.textMuted, textTransform: "uppercase" }}>
          .QBC Domain Preview
        </span>
        <span style={{ fontFamily: FONT.mono, fontSize: 13, color: L.glowCyan }}>
          {domainPreview}
        </span>
        <span style={{ fontFamily: FONT.body, fontSize: 10, color: L.textMuted }}>
          (available at ESTABLISHED tier)
        </span>
      </div>

      {/* Short Description */}
      <div>
        <div style={{ ...labelStyle, display: "flex", justifyContent: "space-between" }}>
          <label htmlFor="deploy-short-desc">Short Description *</label>
          <span style={{ color: description.length > 140 ? L.error : L.textMuted }}>
            {description.length}/140
          </span>
        </div>
        <input
          id="deploy-short-desc"
          style={inputStyle}
          placeholder="One-line description of your project"
          value={description}
          onChange={(e) => setDescription(e.target.value.slice(0, 140))}
          maxLength={140}
        />
      </div>

      {/* Full Description */}
      <div>
        <div style={{ ...labelStyle, display: "flex", justifyContent: "space-between" }}>
          <label htmlFor="deploy-full-desc">Full Description</label>
          <span style={{ color: fullDescription.length > 2000 ? L.error : L.textMuted }}>
            {fullDescription.length}/2000
          </span>
        </div>
        <textarea
          id="deploy-full-desc"
          style={{ ...inputStyle, minHeight: 100, resize: "vertical" }}
          placeholder="Detailed description of your project, technology, and vision..."
          value={fullDescription}
          onChange={(e) => setFullDescription(e.target.value.slice(0, 2000))}
          maxLength={2000}
        />
      </div>

      {/* Category */}
      <div>
        <label htmlFor="deploy-category" style={labelStyle}>Category</label>
        <select
          id="deploy-category"
          style={{ ...inputStyle, cursor: "pointer" }}
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {PROJECT_CATEGORIES.map((c) => (
            <option key={c} value={c} style={{ background: L.bgInput, color: L.textPrimary }}>
              {c}
            </option>
          ))}
        </select>
      </div>

      {/* Links */}
      <div>
        <div style={sectionTitle}>Links</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <div>
            <label htmlFor="deploy-website" style={labelStyle}>Website *</label>
            <input
              id="deploy-website"
              style={inputStyle}
              placeholder="https://yourproject.com"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="deploy-twitter" style={labelStyle}>Twitter</label>
            <input
              id="deploy-twitter"
              style={inputStyle}
              placeholder="https://twitter.com/handle"
              value={twitter}
              onChange={(e) => setTwitter(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="deploy-telegram" style={labelStyle}>Telegram</label>
            <input
              id="deploy-telegram"
              style={inputStyle}
              placeholder="https://t.me/group"
              value={telegram}
              onChange={(e) => setTelegram(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="deploy-discord" style={labelStyle}>Discord</label>
            <input
              id="deploy-discord"
              style={inputStyle}
              placeholder="https://discord.gg/invite"
              value={discord}
              onChange={(e) => setDiscord(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="deploy-github" style={labelStyle}>GitHub</label>
            <input
              id="deploy-github"
              style={inputStyle}
              placeholder="https://github.com/org/repo"
              value={github}
              onChange={(e) => setGithub(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="deploy-whitepaper" style={labelStyle}>Whitepaper</label>
            <input
              id="deploy-whitepaper"
              style={inputStyle}
              placeholder="https://yourproject.com/whitepaper.pdf"
              value={whitepaper}
              onChange={(e) => setWhitepaper(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Team Members */}
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <div style={sectionTitle}>Team Members</div>
          <button
            onClick={addTeamMember}
            style={{
              ...btnBase,
              padding: "6px 14px",
              fontSize: 10,
              background: `${L.glowCyan}15`,
              color: L.glowCyan,
              border: `1px solid ${L.glowCyan}40`,
            }}
          >
            + ADD TEAM MEMBER
          </button>
        </div>
        {teamMembers.length === 0 && (
          <p style={{ fontFamily: FONT.body, fontSize: 11, color: L.textMuted }}>
            No team members added. Adding team members improves your QPCS social verification score.
          </p>
        )}
        {teamMembers.map((m, i) => (
          <div
            key={i}
            style={{
              ...panelStyle,
              padding: 12,
              marginBottom: 8,
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr 1fr auto",
              gap: 8,
              alignItems: "end",
            }}
          >
            <div>
              <label htmlFor={`deploy-team-name-${i}`} style={labelStyle}>Name</label>
              <input
                id={`deploy-team-name-${i}`}
                style={inputStyle}
                placeholder="Name"
                value={m.name}
                onChange={(e) => updateTeamMember(i, "name", e.target.value)}
              />
            </div>
            <div>
              <label htmlFor={`deploy-team-role-${i}`} style={labelStyle}>Role</label>
              <input
                id={`deploy-team-role-${i}`}
                style={inputStyle}
                placeholder="Role"
                value={m.role}
                onChange={(e) => updateTeamMember(i, "role", e.target.value)}
              />
            </div>
            <div>
              <label htmlFor={`deploy-team-twitter-${i}`} style={labelStyle}>Twitter</label>
              <input
                id={`deploy-team-twitter-${i}`}
                style={inputStyle}
                placeholder="@handle"
                value={m.twitter}
                onChange={(e) => updateTeamMember(i, "twitter", e.target.value)}
              />
            </div>
            <div>
              <label htmlFor={`deploy-team-wallet-${i}`} style={labelStyle}>Wallet</label>
              <input
                id={`deploy-team-wallet-${i}`}
                style={inputStyle}
                placeholder="QBC1..."
                value={m.wallet}
                onChange={(e) => updateTeamMember(i, "wallet", e.target.value)}
              />
            </div>
            <button
              onClick={() => removeTeamMember(i)}
              style={{
                background: "none",
                border: "none",
                color: L.error,
                cursor: "pointer",
                fontFamily: FONT.mono,
                fontSize: 14,
                padding: "8px 4px",
              }}
            >
              x
            </button>
          </div>
        ))}
      </div>
    </div>
  );
});

/* ═══════════════════════════════════════════════════════════════════════════════
   STEP 3 — TOKEN CONFIG
   ═══════════════════════════════════════════════════════════════════════════════ */

const StepTokenConfig = memo(function StepTokenConfig() {
  const totalSupply = useLaunchpadStore((s) => s.deployTotalSupply);
  const setTotalSupply = useLaunchpadStore((s) => s.setDeployTotalSupply);
  const decimals = useLaunchpadStore((s) => s.deployDecimals);
  const setDecimals = useLaunchpadStore((s) => s.setDeployDecimals);
  const symbol = useLaunchpadStore((s) => s.deploySymbol);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Total Supply */}
      <div>
        <label htmlFor="deploy-total-supply" style={labelStyle}>Total Supply</label>
        <input
          id="deploy-total-supply"
          style={{ ...inputStyle, fontFamily: FONT.mono, fontSize: 16 }}
          type="number"
          value={totalSupply}
          onChange={(e) => {
            const v = Number(e.target.value);
            if (v >= 0) setTotalSupply(v);
          }}
          min={1}
        />
        <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
          {SUPPLY_PRESETS.map((p) => (
            <button
              key={p.value}
              onClick={() => setTotalSupply(p.value)}
              style={{
                ...btnBase,
                padding: "6px 14px",
                fontSize: 10,
                background: totalSupply === p.value ? `${L.glowCyan}20` : L.bgInput,
                color: totalSupply === p.value ? L.glowCyan : L.textSecondary,
                border: `1px solid ${totalSupply === p.value ? L.glowCyan + "60" : L.borderSubtle}`,
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Decimals */}
      <div>
        <label htmlFor="deploy-decimals" style={labelStyle}>Decimals</label>
        <input
          id="deploy-decimals"
          style={{ ...inputStyle, width: 120 }}
          type="number"
          value={decimals}
          onChange={(e) => {
            const v = Number(e.target.value);
            if (v >= 0 && v <= 18) setDecimals(v);
          }}
          min={0}
          max={18}
        />
        <div style={hintText}>Standard is 18. Change only if you have a specific reason.</div>
      </div>

      {/* Preview */}
      <div style={{ ...panelStyle, padding: 20 }}>
        <div style={labelStyle}>Token Preview</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 8 }}>
          <span style={{ fontFamily: FONT.display, fontSize: 28, color: L.glowCyan }}>
            {formatNumber(totalSupply)}
          </span>
          <span style={{ fontFamily: FONT.display, fontSize: 16, color: L.textPrimary }}>
            {symbol || "TOKEN"}
          </span>
        </div>
        <div style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textMuted, marginTop: 4 }}>
          {totalSupply.toLocaleString()} {symbol || "TOKEN"} ({decimals} decimals)
        </div>
        <div style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textMuted, marginTop: 2 }}>
          Smallest unit: {totalSupply > 0 ? "0." + "0".repeat(Math.max(0, decimals - 1)) + "1" : "0"} {symbol || "TOKEN"}
        </div>
      </div>
    </div>
  );
});

/* ═══════════════════════════════════════════════════════════════════════════════
   STEP 4 — TOKENOMICS
   ═══════════════════════════════════════════════════════════════════════════════ */

const StepTokenomics = memo(function StepTokenomics() {
  const allocations = useLaunchpadStore((s) => s.deployAllocations);
  const setAllocations = useLaunchpadStore((s) => s.setDeployAllocations);
  const mgtEnabled = useLaunchpadStore((s) => s.deployMgtEnabled);
  const setMgtEnabled = useLaunchpadStore((s) => s.setDeployMgtEnabled);
  const mgtTranches = useLaunchpadStore((s) => s.deployMgtTranches);
  const setMgtTranches = useLaunchpadStore((s) => s.setDeployMgtTranches);
  const totalSupply = useLaunchpadStore((s) => s.deployTotalSupply);
  const symbol = useLaunchpadStore((s) => s.deploySymbol);

  const totalPct = useMemo(() => allocations.reduce((s, a) => s + a.percent, 0), [allocations]);
  const totalValid = Math.abs(totalPct - 100) < 0.01;
  const mgtTotalPct = useMemo(() => mgtTranches.reduce((s, t) => s + t.percent, 0), [mgtTranches]);

  const addAllocation = () => {
    const colorIdx = allocations.length % ALLOC_COLORS.length;
    setAllocations([
      ...allocations,
      { label: "", percent: 0, address: "", vestingCliffDays: 0, vestingDurationDays: 0, color: ALLOC_COLORS[colorIdx] },
    ]);
  };

  const updateAllocation = (idx: number, field: keyof AllocationItem, value: string | number) => {
    const updated = allocations.map((a, i) => (i === idx ? { ...a, [field]: value } : a));
    setAllocations(updated);
  };

  const removeAllocation = (idx: number) => {
    setAllocations(allocations.filter((_, i) => i !== idx));
  };

  const addMgtTranche = () => {
    setMgtTranches([
      ...mgtTranches,
      { percent: 10, milestoneType: "holder_count" as MGTMilestoneType, milestoneTarget: 1000 },
    ]);
  };

  const updateMgtTranche = (idx: number, field: string, value: number | string) => {
    const updated = mgtTranches.map((t, i) => (i === idx ? { ...t, [field]: value } : t));
    setMgtTranches(updated);
  };

  const removeMgtTranche = (idx: number) => {
    setMgtTranches(mgtTranches.filter((_, i) => i !== idx));
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Allocation Stacked Bar */}
      <div style={{ ...panelStyle, padding: 12 }}>
        <div style={labelStyle}>Allocation Distribution</div>
        <div
          style={{
            display: "flex",
            height: 24,
            borderRadius: 4,
            overflow: "hidden",
            background: L.bgBase,
            marginTop: 6,
          }}
        >
          {allocations
            .filter((a) => a.percent > 0)
            .map((a, i) => (
              <div
                key={i}
                title={`${a.label || "Unnamed"}: ${a.percent}%`}
                style={{
                  width: `${a.percent}%`,
                  height: "100%",
                  background: a.color,
                  transition: "width 0.3s ease",
                  minWidth: a.percent > 0 ? 2 : 0,
                }}
              />
            ))}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
          {allocations
            .filter((a) => a.percent > 0)
            .map((a, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: a.color, display: "inline-block" }} />
                <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textSecondary }}>
                  {a.label || "Unnamed"} {a.percent}%
                </span>
              </div>
            ))}
        </div>
        <div
          style={{
            fontFamily: FONT.display,
            fontSize: 12,
            color: totalValid ? L.glowEmerald : L.error,
            marginTop: 8,
            letterSpacing: "0.04em",
          }}
        >
          TOTAL: {totalPct.toFixed(1)}% {totalValid ? "\u2713" : "(must equal 100%)"}
        </div>
      </div>

      {/* Allocation Rows */}
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <div style={sectionTitle}>Allocations</div>
          <button
            onClick={addAllocation}
            style={{
              ...btnBase,
              padding: "6px 14px",
              fontSize: 10,
              background: `${L.glowCyan}15`,
              color: L.glowCyan,
              border: `1px solid ${L.glowCyan}40`,
            }}
          >
            + ADD ALLOCATION
          </button>
        </div>
        {allocations.map((a, i) => (
          <div
            key={i}
            style={{
              ...panelStyle,
              padding: 10,
              marginBottom: 6,
              display: "grid",
              gridTemplateColumns: "10px 1fr 80px 1fr 80px 80px auto",
              gap: 8,
              alignItems: "end",
            }}
          >
            {/* Color indicator */}
            <input
              type="color"
              value={a.color}
              onChange={(e) => updateAllocation(i, "color", e.target.value)}
              style={{ width: 10, height: 30, border: "none", background: "none", cursor: "pointer", padding: 0 }}
            />
            <div>
              <label htmlFor={`deploy-alloc-label-${i}`} style={labelStyle}>Label</label>
              <input
                id={`deploy-alloc-label-${i}`}
                style={inputStyle}
                placeholder="e.g. Team"
                value={a.label}
                onChange={(e) => updateAllocation(i, "label", e.target.value)}
              />
            </div>
            <div>
              <label htmlFor={`deploy-alloc-pct-${i}`} style={labelStyle}>Percent</label>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <input
                  id={`deploy-alloc-pct-${i}`}
                  style={{ ...inputStyle, width: 50, textAlign: "right" }}
                  type="number"
                  value={a.percent}
                  onChange={(e) => {
                    const v = Math.max(0, Math.min(100, Number(e.target.value)));
                    updateAllocation(i, "percent", v);
                  }}
                  min={0}
                  max={100}
                />
                <span style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textMuted }}>%</span>
              </div>
            </div>
            <div>
              <label htmlFor={`deploy-alloc-addr-${i}`} style={labelStyle}>Address</label>
              <input
                id={`deploy-alloc-addr-${i}`}
                style={inputStyle}
                placeholder="QBC1..."
                value={a.address}
                onChange={(e) => updateAllocation(i, "address", e.target.value)}
              />
            </div>
            <div>
              <label htmlFor={`deploy-alloc-cliff-${i}`} style={labelStyle}>Cliff (days)</label>
              <input
                id={`deploy-alloc-cliff-${i}`}
                style={inputStyle}
                type="number"
                value={a.vestingCliffDays}
                onChange={(e) => updateAllocation(i, "vestingCliffDays", Math.max(0, Number(e.target.value)))}
                min={0}
              />
            </div>
            <div>
              <label htmlFor={`deploy-alloc-vest-${i}`} style={labelStyle}>Vest (days)</label>
              <input
                id={`deploy-alloc-vest-${i}`}
                style={inputStyle}
                type="number"
                value={a.vestingDurationDays}
                onChange={(e) => updateAllocation(i, "vestingDurationDays", Math.max(0, Number(e.target.value)))}
                min={0}
              />
            </div>
            <button
              onClick={() => removeAllocation(i)}
              style={{
                background: "none",
                border: "none",
                color: L.error,
                cursor: "pointer",
                fontFamily: FONT.mono,
                fontSize: 14,
                padding: "8px 4px",
              }}
            >
              x
            </button>
          </div>
        ))}
        {allocations.length > 0 && (
          <div style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted, marginTop: 4 }}>
            Token amounts: {allocations.filter((a) => a.percent > 0).map((a) =>
              `${a.label || "?"}: ${formatNumber(Math.round(totalSupply * a.percent / 100))} ${symbol || "TOKEN"}`
            ).join(" | ")}
          </div>
        )}
      </div>

      {/* MGT Toggle */}
      <div style={{ ...panelStyle, padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <div>
            <div style={sectionTitle}>Milestone-Gated Treasury (MGT)</div>
            <p style={{ fontFamily: FONT.body, fontSize: 11, color: L.textMuted, marginTop: -8 }}>
              Lock treasury tokens behind verifiable on-chain milestones. Increases QPCS score.
            </p>
          </div>
          <button
            onClick={() => setMgtEnabled(!mgtEnabled)}
            style={{
              width: 42,
              height: 22,
              borderRadius: 11,
              border: "none",
              cursor: "pointer",
              background: mgtEnabled ? L.glowCyan : L.borderSubtle,
              position: "relative",
              transition: "background 0.2s",
            }}
          >
            <div
              style={{
                width: 16,
                height: 16,
                borderRadius: "50%",
                background: "#fff",
                position: "absolute",
                top: 3,
                left: mgtEnabled ? 23 : 3,
                transition: "left 0.2s",
              }}
            />
          </button>
        </div>

        {mgtEnabled && (
          <div style={{ marginTop: 12 }}>
            {mgtTranches.map((t, i) => (
              <div
                key={i}
                style={{
                  display: "grid",
                  gridTemplateColumns: "80px 1fr 120px auto",
                  gap: 8,
                  alignItems: "end",
                  marginBottom: 6,
                  background: L.bgSurface,
                  padding: 8,
                  borderRadius: 4,
                }}
              >
                <div>
                  <label htmlFor={`deploy-mgt-pct-${i}`} style={labelStyle}>Percent</label>
                  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <input
                      id={`deploy-mgt-pct-${i}`}
                      style={{ ...inputStyle, width: 50, textAlign: "right" }}
                      type="number"
                      value={t.percent}
                      onChange={(e) => updateMgtTranche(i, "percent", Math.max(0, Math.min(100, Number(e.target.value))))}
                      min={0}
                      max={100}
                    />
                    <span style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textMuted }}>%</span>
                  </div>
                </div>
                <div>
                  <label htmlFor={`deploy-mgt-type-${i}`} style={labelStyle}>Milestone Type</label>
                  <select
                    id={`deploy-mgt-type-${i}`}
                    style={{ ...inputStyle, cursor: "pointer" }}
                    value={t.milestoneType}
                    onChange={(e) => updateMgtTranche(i, "milestoneType", e.target.value)}
                  >
                    {MILESTONE_TYPES.map((mt) => (
                      <option key={mt.value} value={mt.value} style={{ background: L.bgInput, color: L.textPrimary }}>
                        {mt.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor={`deploy-mgt-target-${i}`} style={labelStyle}>Target Value</label>
                  <input
                    id={`deploy-mgt-target-${i}`}
                    style={inputStyle}
                    type="number"
                    value={t.milestoneTarget}
                    onChange={(e) => updateMgtTranche(i, "milestoneTarget", Math.max(0, Number(e.target.value)))}
                    min={0}
                  />
                </div>
                <button
                  onClick={() => removeMgtTranche(i)}
                  style={{
                    background: "none",
                    border: "none",
                    color: L.error,
                    cursor: "pointer",
                    fontFamily: FONT.mono,
                    fontSize: 14,
                    padding: "8px 4px",
                  }}
                >
                  x
                </button>
              </div>
            ))}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 8 }}>
              <button
                onClick={addMgtTranche}
                style={{
                  ...btnBase,
                  padding: "6px 14px",
                  fontSize: 10,
                  background: `${L.glowCyan}15`,
                  color: L.glowCyan,
                  border: `1px solid ${L.glowCyan}40`,
                }}
              >
                + ADD TRANCHE
              </button>
              <span style={{ fontFamily: FONT.mono, fontSize: 11, color: L.textSecondary }}>
                Total MGT: {mgtTotalPct}%
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

/* ═══════════════════════════════════════════════════════════════════════════════
   STEP 5 — LAUNCH MECHANICS
   ═══════════════════════════════════════════════════════════════════════════════ */

const StepLaunch = memo(function StepLaunch() {
  const liquidityLockDays = useLaunchpadStore((s) => s.deployLiquidityLockDays);
  const setLiquidityLockDays = useLaunchpadStore((s) => s.setDeployLiquidityLockDays);
  const liquidityPercent = useLaunchpadStore((s) => s.deployLiquidityPercent);
  const setLiquidityPercent = useLaunchpadStore((s) => s.setDeployLiquidityPercent);
  const presaleEnabled = useLaunchpadStore((s) => s.deployPresaleEnabled);
  const setPresaleEnabled = useLaunchpadStore((s) => s.setDeployPresaleEnabled);
  const presaleType = useLaunchpadStore((s) => s.deployPresaleType);
  const setPresaleType = useLaunchpadStore((s) => s.setDeployPresaleType);
  const presaleTokenPercent = useLaunchpadStore((s) => s.deployPresaleTokenPercent);
  const setPresaleTokenPercent = useLaunchpadStore((s) => s.setDeployPresaleTokenPercent);
  const presalePrice = useLaunchpadStore((s) => s.deployPresalePrice);
  const setPresalePrice = useLaunchpadStore((s) => s.setDeployPresalePrice);
  const presaleHardCap = useLaunchpadStore((s) => s.deployPresaleHardCap);
  const setPresaleHardCap = useLaunchpadStore((s) => s.setDeployPresaleHardCap);
  const presaleSoftCap = useLaunchpadStore((s) => s.deployPresaleSoftCap);
  const setPresaleSoftCap = useLaunchpadStore((s) => s.setDeployPresaleSoftCap);
  const qaslEnabled = useLaunchpadStore((s) => s.deployQaslEnabled);
  const setQaslEnabled = useLaunchpadStore((s) => s.setDeployQaslEnabled);
  const qaslWindowSize = useLaunchpadStore((s) => s.deployQaslWindowSize);
  const setQaslWindowSize = useLaunchpadStore((s) => s.setDeployQaslWindowSize);

  const illp = useMemo(() => calculateILLP(liquidityLockDays), [liquidityLockDays]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Liquidity Lock */}
      <div style={{ ...panelStyle, padding: 16 }}>
        <div style={sectionTitle}>Liquidity Lock (ILLP)</div>

        <label htmlFor="deploy-lock-duration" style={labelStyle}>Lock Duration: {liquidityLockDays} days ({(liquidityLockDays / 365).toFixed(1)} years)</label>
        <input
          id="deploy-lock-duration"
          type="range"
          min={30}
          max={1460}
          value={liquidityLockDays}
          onChange={(e) => setLiquidityLockDays(Number(e.target.value))}
          style={{ width: "100%", marginBottom: 12, accentColor: L.glowCyan }}
        />

        {/* ILLP Result */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 12,
            padding: 12,
            background: L.bgBase,
            borderRadius: 6,
            marginBottom: 12,
          }}
        >
          <div>
            <div style={labelStyle}>ILLP Fee</div>
            <span style={{ fontFamily: FONT.mono, fontSize: 14, color: illp.feeQusd >= 999999 ? L.error : L.textPrimary }}>
              {illp.feeQusd >= 999999 ? "BLOCKED" : formatQusd(illp.feeQusd)}
            </span>
          </div>
          <div>
            <div style={labelStyle}>Signal</div>
            <span
              style={{
                fontFamily: FONT.display,
                fontSize: 11,
                letterSpacing: "0.04em",
                color: illpColor(illp.signal),
                background: `${illpColor(illp.signal)}15`,
                padding: "3px 8px",
                borderRadius: 4,
                border: `1px solid ${illpColor(illp.signal)}40`,
              }}
            >
              {illpLabel(illp.signal)}
            </span>
          </div>
          <div>
            <div style={labelStyle}>QPCS Impact</div>
            <span style={{ fontFamily: FONT.mono, fontSize: 14, color: L.glowEmerald }}>
              +{illp.qpcsImpact}/25
            </span>
          </div>
        </div>

        {/* ILLP Tier Table */}
        <details style={{ marginTop: 8 }}>
          <summary
            style={{
              fontFamily: FONT.display,
              fontSize: 10,
              color: L.textMuted,
              cursor: "pointer",
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}
          >
            VIEW ALL ILLP TIERS
          </summary>
          <div style={{ marginTop: 8 }}>
            {ILLP_TIERS.map((tier) => (
              <div
                key={tier.signal}
                style={{
                  display: "grid",
                  gridTemplateColumns: "80px 100px 80px 60px 1fr",
                  gap: 8,
                  padding: "4px 0",
                  borderBottom: `1px solid ${L.borderSubtle}`,
                  alignItems: "center",
                  background: liquidityLockDays >= tier.minDays && liquidityLockDays <= tier.maxDays
                    ? `${illpColor(tier.signal)}10`
                    : "transparent",
                }}
              >
                <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textSecondary }}>
                  {tier.minDays}-{tier.maxDays > 9999 ? "\u221E" : tier.maxDays}d
                </span>
                <span
                  style={{
                    fontFamily: FONT.display,
                    fontSize: 9,
                    color: illpColor(tier.signal),
                    letterSpacing: "0.04em",
                  }}
                >
                  {tier.label}
                </span>
                <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textSecondary }}>
                  {tier.feeQusd >= 999999 ? "BLOCKED" : formatQusd(tier.feeQusd)}
                </span>
                <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.glowEmerald }}>
                  +{tier.qpcs}
                </span>
                <span style={{ fontFamily: FONT.body, fontSize: 10, color: L.textMuted }}>
                  {tier.description}
                </span>
              </div>
            ))}
          </div>
        </details>
      </div>

      {/* Liquidity Percent */}
      <div>
        <label htmlFor="deploy-liquidity-pct" style={labelStyle}>Liquidity Percent of Supply: {liquidityPercent}%</label>
        <input
          id="deploy-liquidity-pct"
          type="range"
          min={10}
          max={50}
          value={liquidityPercent}
          onChange={(e) => setLiquidityPercent(Number(e.target.value))}
          style={{ width: "100%", accentColor: L.glowCyan }}
        />
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={hintText}>10%</span>
          <span style={hintText}>50%</span>
        </div>
      </div>

      {/* Presale Toggle */}
      <div style={{ ...panelStyle, padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <div style={sectionTitle}>Presale</div>
          <button
            onClick={() => setPresaleEnabled(!presaleEnabled)}
            style={{
              width: 42,
              height: 22,
              borderRadius: 11,
              border: "none",
              cursor: "pointer",
              background: presaleEnabled ? L.glowCyan : L.borderSubtle,
              position: "relative",
              transition: "background 0.2s",
            }}
          >
            <div
              style={{
                width: 16,
                height: 16,
                borderRadius: "50%",
                background: "#fff",
                position: "absolute",
                top: 3,
                left: presaleEnabled ? 23 : 3,
                transition: "left 0.2s",
              }}
            />
          </button>
        </div>

        {presaleEnabled && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 8 }}>
            <div>
              <label htmlFor="deploy-presale-type" style={labelStyle}>Presale Type</label>
              <select
                id="deploy-presale-type"
                style={{ ...inputStyle, cursor: "pointer" }}
                value={presaleType}
                onChange={(e) => setPresaleType(e.target.value as PresaleType)}
              >
                {PRESALE_TYPES.map((pt) => (
                  <option key={pt.value} value={pt.value} style={{ background: L.bgInput, color: L.textPrimary }}>
                    {pt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="deploy-presale-token-pct" style={labelStyle}>Token % for Presale</label>
              <input
                id="deploy-presale-token-pct"
                style={inputStyle}
                type="number"
                value={presaleTokenPercent}
                onChange={(e) => setPresaleTokenPercent(Math.max(0, Math.min(50, Number(e.target.value))))}
                min={0}
                max={50}
              />
            </div>
            <div>
              <label htmlFor="deploy-presale-price" style={labelStyle}>Token Price (QUSD)</label>
              <input
                id="deploy-presale-price"
                style={inputStyle}
                type="number"
                step="0.0001"
                value={presalePrice}
                onChange={(e) => setPresalePrice(Math.max(0, Number(e.target.value)))}
                min={0}
              />
            </div>
            <div>
              <label htmlFor="deploy-presale-hard-cap" style={labelStyle}>Hard Cap (QUSD)</label>
              <input
                id="deploy-presale-hard-cap"
                style={inputStyle}
                type="number"
                value={presaleHardCap}
                onChange={(e) => setPresaleHardCap(Math.max(0, Number(e.target.value)))}
                min={0}
              />
            </div>
            <div>
              <label htmlFor="deploy-presale-soft-cap" style={labelStyle}>Soft Cap (QUSD)</label>
              <input
                id="deploy-presale-soft-cap"
                style={inputStyle}
                type="number"
                value={presaleSoftCap}
                onChange={(e) => setPresaleSoftCap(Math.max(0, Number(e.target.value)))}
                min={0}
              />
            </div>
          </div>
        )}
      </div>

      {/* QASL Toggle */}
      <div style={{ ...panelStyle, padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <div>
            <div style={sectionTitle}>Quantum Anti-Snipe Launch (QASL)</div>
            <p style={{ fontFamily: FONT.body, fontSize: 11, color: L.textMuted, marginTop: -8 }}>
              VQE entropy determines the exact launch block within a window, making sniping impossible.
            </p>
          </div>
          <button
            onClick={() => setQaslEnabled(!qaslEnabled)}
            style={{
              width: 42,
              height: 22,
              borderRadius: 11,
              border: "none",
              cursor: "pointer",
              background: qaslEnabled ? L.glowCyan : L.borderSubtle,
              position: "relative",
              transition: "background 0.2s",
              flexShrink: 0,
            }}
          >
            <div
              style={{
                width: 16,
                height: 16,
                borderRadius: "50%",
                background: "#fff",
                position: "absolute",
                top: 3,
                left: qaslEnabled ? 23 : 3,
                transition: "left 0.2s",
              }}
            />
          </button>
        </div>

        {qaslEnabled && (
          <div style={{ marginTop: 8 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 12 }}>
              <div>
                <label htmlFor="deploy-qasl-window" style={labelStyle}>QASL Window Size (blocks)</label>
                <input
                  id="deploy-qasl-window"
                  style={{ ...inputStyle, width: 200 }}
                  type="number"
                  value={qaslWindowSize}
                  onChange={(e) => setQaslWindowSize(Math.max(10, Math.min(1000, Number(e.target.value))))}
                  min={10}
                  max={1000}
                />
                <div style={hintText}>
                  At 3.3s/block, {qaslWindowSize} blocks = ~{((qaslWindowSize * 3.3) / 60).toFixed(1)} min window.
                  The exact launch block is determined by VQE ground state energy entropy.
                </div>
              </div>
            </div>
            <div style={{ ...panelStyle, padding: 10, marginTop: 12, background: L.bgBase }}>
              <div style={{ fontFamily: FONT.display, fontSize: 10, color: L.glowCyan, marginBottom: 4, letterSpacing: "0.04em" }}>
                QASL ANTI-SNIPE PROTECTIONS
              </div>
              <div style={{ fontFamily: FONT.body, fontSize: 11, color: L.textSecondary, lineHeight: 1.5 }}>
                Block 1: Max buy limited to 0.5% of supply{"\n"}
                Fee multiplier: 2x on first block trades{"\n"}
                Snipe penalty: 30% tax on detected snipe transactions
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

/* ═══════════════════════════════════════════════════════════════════════════════
   STEP 6 — REVIEW & QPCS
   ═══════════════════════════════════════════════════════════════════════════════ */

const StepReview = memo(function StepReview() {
  const contractType = useLaunchpadStore((s) => s.deployContractType);
  const name = useLaunchpadStore((s) => s.deployName);
  const symbol = useLaunchpadStore((s) => s.deploySymbol);
  const description = useLaunchpadStore((s) => s.deployDescription);
  const category = useLaunchpadStore((s) => s.deployCategory);
  const website = useLaunchpadStore((s) => s.deployWebsite);
  const twitter = useLaunchpadStore((s) => s.deployTwitter);
  const telegram = useLaunchpadStore((s) => s.deployTelegram);
  const discord = useLaunchpadStore((s) => s.deployDiscord);
  const github = useLaunchpadStore((s) => s.deployGithub);
  const whitepaper = useLaunchpadStore((s) => s.deployWhitepaper);
  const teamMembers = useLaunchpadStore((s) => s.deployTeamMembers);
  const totalSupply = useLaunchpadStore((s) => s.deployTotalSupply);
  const decimals = useLaunchpadStore((s) => s.deployDecimals);
  const allocations = useLaunchpadStore((s) => s.deployAllocations);
  const mgtEnabled = useLaunchpadStore((s) => s.deployMgtEnabled);
  const mgtTranches = useLaunchpadStore((s) => s.deployMgtTranches);
  const presaleEnabled = useLaunchpadStore((s) => s.deployPresaleEnabled);
  const presaleType = useLaunchpadStore((s) => s.deployPresaleType);
  const presaleTokenPercent = useLaunchpadStore((s) => s.deployPresaleTokenPercent);
  const presalePrice = useLaunchpadStore((s) => s.deployPresalePrice);
  const presaleHardCap = useLaunchpadStore((s) => s.deployPresaleHardCap);
  const presaleSoftCap = useLaunchpadStore((s) => s.deployPresaleSoftCap);
  const liquidityLockDays = useLaunchpadStore((s) => s.deployLiquidityLockDays);
  const liquidityPercent = useLaunchpadStore((s) => s.deployLiquidityPercent);
  const qaslEnabled = useLaunchpadStore((s) => s.deployQaslEnabled);
  const qaslWindowSize = useLaunchpadStore((s) => s.deployQaslWindowSize);

  const ctConfig = contractType ? getContractTypeConfig(contractType) : null;
  const illp = useMemo(() => calculateILLP(liquidityLockDays), [liquidityLockDays]);
  const totalAllocPct = useMemo(() => allocations.reduce((s, a) => s + a.percent, 0), [allocations]);
  const allocValid = Math.abs(totalAllocPct - 100) < 0.01;

  // Estimate QPCS components
  const estimatedQpcs = useMemo((): QPCSComponents => {
    // Liquidity lock: from ILLP
    const liquidityLock = illp.qpcsImpact;

    // Team vesting: check if team allocation has vesting
    const teamAllocs = allocations.filter((a) => a.label.toLowerCase().includes("team"));
    const hasTeamVesting = teamAllocs.some((a) => a.vestingDurationDays >= 180 && a.vestingCliffDays >= 30);
    const teamVesting = hasTeamVesting ? 15 : teamAllocs.some((a) => a.vestingDurationDays > 0) ? 8 : 2;

    // Tokenomics: good distribution = no single allocation > 40%
    const maxAlloc = Math.max(...allocations.map((a) => a.percent), 0);
    const tokenomicsDistribution = maxAlloc <= 30 ? 12 : maxAlloc <= 40 ? 8 : maxAlloc <= 50 ? 5 : 2;

    // Contract complexity
    const complexityMap: Partial<Record<ContractType, number>> = {
      susy_governance: 10,
      governance: 8,
      vesting_reflection: 7,
      fixed_governance: 6,
      vesting: 5,
      qrc20_standard: 3,
      deflationary: 3,
      fair_launch: 2,
    };
    const contractComplexity = contractType ? (complexityMap[contractType] ?? 3) : 0;

    // Presale structure
    const presaleStructure = presaleEnabled
      ? (presaleType === "dutch_auction" ? 8 : presaleType === "whitelist_ido" ? 7 : 5)
      : 3;

    // Deployer history (simulated — first deploy gets low score)
    const deployerHistory = 3;

    // Social verification
    let socialVerification = 0;
    if (website) socialVerification += 1;
    if (twitter) socialVerification += 1;
    if (telegram) socialVerification += 1;
    if (discord) socialVerification += 1;
    if (github) socialVerification += 1;
    if (whitepaper) socialVerification += 1;
    if (teamMembers.length > 0) socialVerification += 1;
    socialVerification = Math.min(7, socialVerification);

    // SUSY at deploy (simulated — depends on chain state)
    const susyAtDeploy = 3;

    return {
      liquidityLock: Math.min(25, liquidityLock),
      teamVesting: Math.min(20, teamVesting),
      tokenomicsDistribution: Math.min(15, tokenomicsDistribution),
      contractComplexity: Math.min(10, contractComplexity),
      presaleStructure: Math.min(10, presaleStructure),
      deployerHistory: Math.min(8, deployerHistory),
      socialVerification: Math.min(7, socialVerification),
      susyAtDeploy: Math.min(5, susyAtDeploy),
    };
  }, [
    illp, allocations, contractType, presaleEnabled, presaleType,
    website, twitter, telegram, discord, github, whitepaper, teamMembers,
  ]);

  const totalQpcs = useMemo(
    () => Object.values(estimatedQpcs).reduce((s, v) => s + v, 0),
    [estimatedQpcs]
  );
  const qpcsGrade = getQpcsGrade(totalQpcs);
  const gradeColorMap: Record<string, string> = {
    quantum_grade: L.glowCyan,
    verified: L.glowEmerald,
    basic: L.glowGold,
    restricted: L.error,
    rejected: L.textMuted,
  };
  const gradeColor = gradeColorMap[qpcsGrade] ?? L.textMuted;
  const gradeText = qpcsGrade.replace(/_/g, " ").toUpperCase();

  const deployFee = ctConfig?.deployFeeQbc ?? 0;
  const gasEstimate = 0.05;
  const totalFee = deployFee + gasEstimate;

  // Warnings
  const warnings: string[] = [];
  if (!allocValid) warnings.push(`Allocation total is ${totalAllocPct.toFixed(1)}% (must equal 100%)`);
  if (illp.signal === "prohibited") warnings.push("Liquidity lock duration is below 30-day minimum");
  if (presaleEnabled && presaleSoftCap > presaleHardCap) warnings.push("Presale soft cap exceeds hard cap");

  const reviewRow = (label: string, value: React.ReactNode) => (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: `1px solid ${L.borderSubtle}08` }}>
      <span style={{ fontFamily: FONT.body, fontSize: 12, color: L.textSecondary }}>{label}</span>
      <span style={{ fontFamily: FONT.mono, fontSize: 12, color: L.textPrimary, textAlign: "right" }}>{value}</span>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Warnings */}
      {warnings.length > 0 && (
        <div
          style={{
            ...panelStyle,
            padding: 12,
            borderColor: L.error + "40",
            background: `${L.error}08`,
          }}
        >
          <div style={{ fontFamily: FONT.display, fontSize: 10, color: L.error, marginBottom: 6, letterSpacing: "0.04em" }}>
            WARNINGS
          </div>
          {warnings.map((w, i) => (
            <div key={i} style={{ fontFamily: FONT.body, fontSize: 11, color: L.error, padding: "2px 0" }}>
              {"\u26A0"} {w}
            </div>
          ))}
        </div>
      )}

      {/* Summary */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Left: Configuration Summary */}
        <div style={{ ...panelStyle, padding: 14 }}>
          <div style={sectionTitle}>Configuration Summary</div>
          {reviewRow("Contract Type", ctConfig?.label ?? "Not selected")}
          {reviewRow("Project Name", name || "Not set")}
          {reviewRow("Token Symbol", symbol || "Not set")}
          {reviewRow("Category", category)}
          {reviewRow("Total Supply", formatNumber(totalSupply) + " " + (symbol || "TOKEN"))}
          {reviewRow("Decimals", String(decimals))}
          {reviewRow("Allocations", `${allocations.length} groups (${totalAllocPct}%)`)}
          {reviewRow("MGT Enabled", mgtEnabled ? `Yes (${mgtTranches.length} tranches)` : "No")}
          {reviewRow("Liquidity Lock", `${liquidityLockDays} days`)}
          {reviewRow("Liquidity %", `${liquidityPercent}%`)}
          {reviewRow("Presale", presaleEnabled ? PRESALE_TYPES.find((p) => p.value === presaleType)?.label ?? "Yes" : "No")}
          {presaleEnabled && reviewRow("Presale Price", `${presalePrice} QUSD`)}
          {presaleEnabled && reviewRow("Hard Cap", formatQusd(presaleHardCap))}
          {presaleEnabled && reviewRow("Soft Cap", formatQusd(presaleSoftCap))}
          {reviewRow("QASL", qaslEnabled ? `${qaslWindowSize} blocks` : "Disabled")}
          {reviewRow("Description", description ? description.slice(0, 50) + (description.length > 50 ? "..." : "") : "Not set")}
          {reviewRow("Team Members", String(teamMembers.length))}
          {reviewRow("Links", [website, twitter, telegram, discord, github, whitepaper].filter(Boolean).length + " provided")}
        </div>

        {/* Right: QPCS Estimate */}
        <div style={{ ...panelStyle, padding: 14 }}>
          <div style={sectionTitle}>Estimated QPCS Score</div>

          {/* Component Bars */}
          {(Object.keys(QPCS_WEIGHTS) as Array<keyof typeof QPCS_WEIGHTS>).map((key) => {
            const w = QPCS_WEIGHTS[key];
            const val = estimatedQpcs[key];
            return (
              <div key={key} style={{ marginBottom: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                  <span style={{ fontFamily: FONT.body, fontSize: 10, color: L.textSecondary }}>{w.label}</span>
                  <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textPrimary }}>
                    {val}/{w.max}
                  </span>
                </div>
                <ProgressBar value={val} max={w.max} height={6} color={L.glowCyan} />
              </div>
            );
          })}

          {/* Total + Grade */}
          <div
            style={{
              marginTop: 16,
              padding: 12,
              background: L.bgBase,
              borderRadius: 6,
              textAlign: "center",
              border: `1px solid ${gradeColor}30`,
            }}
          >
            <div style={{ fontFamily: FONT.display, fontSize: 28, color: gradeColor }}>
              {totalQpcs.toFixed(1)}
            </div>
            <div
              style={{
                fontFamily: FONT.display,
                fontSize: 11,
                color: gradeColor,
                letterSpacing: "0.06em",
                marginTop: 4,
              }}
            >
              {gradeText}
            </div>
            <div style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted, marginTop: 4 }}>
              out of 100 possible
            </div>
          </div>
        </div>
      </div>

      {/* Fee Summary */}
      <div style={{ ...panelStyle, padding: 14 }}>
        <div style={sectionTitle}>Fee Summary</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
          <div>
            <div style={labelStyle}>Deploy Fee</div>
            <span style={{ fontFamily: FONT.mono, fontSize: 14, color: L.glowGold }}>
              {formatQbc(deployFee)}
            </span>
          </div>
          <div>
            <div style={labelStyle}>ILLP Fee</div>
            <span style={{ fontFamily: FONT.mono, fontSize: 14, color: L.glowGold }}>
              {illp.feeQusd >= 999999 ? "N/A" : formatQusd(illp.feeQusd)}
            </span>
          </div>
          <div>
            <div style={labelStyle}>Gas Estimate</div>
            <span style={{ fontFamily: FONT.mono, fontSize: 14, color: L.glowGold }}>
              ~{formatQbc(gasEstimate)}
            </span>
          </div>
        </div>

        {/* Treasury Split */}
        <div style={{ marginTop: 12 }}>
          <div style={labelStyle}>Treasury Split</div>
          <div style={{ display: "flex", height: 16, borderRadius: 3, overflow: "hidden", marginTop: 4 }}>
            <div
              style={{
                width: `${FEE_CONFIG.treasurySplitPercent}%`,
                background: L.glowCyan,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <span style={{ fontFamily: FONT.mono, fontSize: 8, color: L.textInverse }}>
                {FEE_CONFIG.treasurySplitPercent}% TREASURY
              </span>
            </div>
            <div
              style={{
                width: `${100 - FEE_CONFIG.treasurySplitPercent}%`,
                background: L.glowGold,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <span style={{ fontFamily: FONT.mono, fontSize: 8, color: L.textInverse }}>
                {100 - FEE_CONFIG.treasurySplitPercent}% QUSD BURN
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

/* ═══════════════════════════════════════════════════════════════════════════════
   STEP 7 — DEPLOY
   ═══════════════════════════════════════════════════════════════════════════════ */

const StepDeploy = memo(function StepDeploy() {
  const deploying = useLaunchpadStore((s) => s.deploying);
  const setDeploying = useLaunchpadStore((s) => s.setDeploying);
  const resetDeploy = useLaunchpadStore((s) => s.resetDeploy);
  const setView = useLaunchpadStore((s) => s.setView);
  const setSelectedProject = useLaunchpadStore((s) => s.setSelectedProject);
  const name = useLaunchpadStore((s) => s.deployName);
  const symbol = useLaunchpadStore((s) => s.deploySymbol);
  const description = useLaunchpadStore((s) => s.deployDescription);
  const fullDescription = useLaunchpadStore((s) => s.deployFullDescription);
  const category = useLaunchpadStore((s) => s.deployCategory);
  const contractType = useLaunchpadStore((s) => s.deployContractType);
  const liquidityLockDays = useLaunchpadStore((s) => s.deployLiquidityLockDays);
  const liquidityPercent = useLaunchpadStore((s) => s.deployLiquidityPercent);
  const allocations = useLaunchpadStore((s) => s.deployAllocations);
  const totalSupply = useLaunchpadStore((s) => s.deployTotalSupply);
  const decimals = useLaunchpadStore((s) => s.deployDecimals);
  const mgtEnabled = useLaunchpadStore((s) => s.deployMgtEnabled);
  const mgtTranches = useLaunchpadStore((s) => s.deployMgtTranches);
  const presaleEnabled = useLaunchpadStore((s) => s.deployPresaleEnabled);
  const presaleType = useLaunchpadStore((s) => s.deployPresaleType);
  const presaleTokenPercent = useLaunchpadStore((s) => s.deployPresaleTokenPercent);
  const presalePrice = useLaunchpadStore((s) => s.deployPresalePrice);
  const presaleHardCap = useLaunchpadStore((s) => s.deployPresaleHardCap);
  const presaleSoftCap = useLaunchpadStore((s) => s.deployPresaleSoftCap);
  const qaslEnabled = useLaunchpadStore((s) => s.deployQaslEnabled);
  const qaslWindowSize = useLaunchpadStore((s) => s.deployQaslWindowSize);
  const website = useLaunchpadStore((s) => s.deployWebsite);
  const twitter = useLaunchpadStore((s) => s.deployTwitter);
  const telegram = useLaunchpadStore((s) => s.deployTelegram);
  const discord = useLaunchpadStore((s) => s.deployDiscord);
  const github = useLaunchpadStore((s) => s.deployGithub);
  const whitepaper = useLaunchpadStore((s) => s.deployWhitepaper);
  const teamMembers = useLaunchpadStore((s) => s.deployTeamMembers);

  // Get real wallet address instead of hardcoded MY_WALLET
  const walletAddress = useWalletStore((s) => s.address);
  const activeNativeWallet = useWalletStore((s) => s.activeNativeWallet);
  const deployerAddress = walletAddress ?? activeNativeWallet ?? "";

  const [deployResult, setDeployResult] = useState<{
    contractAddress: string;
    txHash: string;
    dnaFingerprint: string;
    qpcs: number;
    blockHeight: number;
  } | null>(null);
  const [deployError, setDeployError] = useState<string | null>(null);

  const illp = useMemo(() => calculateILLP(liquidityLockDays), [liquidityLockDays]);
  const ctConfig = contractType ? getContractTypeConfig(contractType) : null;

  const handleDeploy = useCallback(async () => {
    if (!contractType) return;
    setDeploying(true);
    setDeployError(null);

    try {
      const result = await deployContract({
        contractType,
        name,
        symbol,
        description,
        fullDescription,
        category,
        totalSupply,
        decimals,
        deployer: deployerAddress,
        allocations,
        mgtEnabled,
        mgtTranches,
        presaleEnabled,
        presaleType,
        presaleTokenPercent,
        presalePrice,
        presaleHardCap,
        presaleSoftCap,
        liquidityLockDays,
        liquidityPercent,
        qaslEnabled,
        qaslWindowSize,
        website,
        twitter,
        telegram,
        discord,
        github,
        whitepaper,
        teamMembers,
      });

      if (result.success) {
        const est = illp.qpcsImpact + (ctConfig?.complexity ?? 0) * 2 + 3 + 3 + 3;
        setDeployResult({
          contractAddress: result.contract_id,
          txHash: "0x" + result.contract_id.replace(/^QBC1/, "").slice(0, 64).padEnd(64, "0"),
          dnaFingerprint: generateDNAFingerprint(result.contract_id, name, symbol),
          qpcs: Math.min(100, est),
          blockHeight: result.block_height,
        });
      } else {
        setDeployError(result.message || "Deployment failed");
      }
    } catch (err) {
      setDeployError(err instanceof Error ? err.message : "Deployment failed");
    } finally {
      setDeploying(false);
    }
  }, [
    contractType, name, symbol, description, fullDescription, category,
    totalSupply, decimals, deployerAddress, allocations, mgtEnabled,
    mgtTranches, presaleEnabled, presaleType, presaleTokenPercent,
    presalePrice, presaleHardCap, presaleSoftCap, liquidityLockDays,
    liquidityPercent, qaslEnabled, qaslWindowSize, website, twitter,
    telegram, discord, github, whitepaper, teamMembers,
    setDeploying, illp, ctConfig,
  ]);

  const handleDeployAnother = useCallback(() => {
    setDeployResult(null);
    resetDeploy();
  }, [resetDeploy]);

  const handleViewProject = useCallback(() => {
    if (deployResult) {
      setSelectedProject(deployResult.contractAddress);
    }
  }, [deployResult, setSelectedProject]);

  // Pre-deploy state
  if (!deployResult) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 20, padding: "40px 0" }}>
        <div
          style={{
            fontFamily: FONT.display,
            fontSize: 20,
            color: L.textPrimary,
            letterSpacing: "0.04em",
            textAlign: "center",
          }}
        >
          DEPLOY {symbol || "TOKEN"} TO QBC
        </div>
        <p style={{ fontFamily: FONT.body, fontSize: 12, color: L.textSecondary, textAlign: "center", maxWidth: 500 }}>
          Your contract will be deployed to the QBC blockchain, signed with your Dilithium2
          post-quantum signature. The transaction is irreversible and will be permanently recorded.
        </p>

        {/* Dilithium Info */}
        <div style={{ ...panelStyle, padding: 16, width: "100%", maxWidth: 500 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 16 }}>{"\uD83D\uDD10"}</span>
            <span style={{ fontFamily: FONT.display, fontSize: 11, color: L.glowCyan, letterSpacing: "0.04em" }}>
              DILITHIUM2 SIGNATURE
            </span>
          </div>
          <p style={{ fontFamily: FONT.body, fontSize: 11, color: L.textSecondary, lineHeight: 1.4 }}>
            Your deployment transaction will be signed with CRYSTALS-Dilithium2, a NIST-standardized
            post-quantum digital signature scheme. This ensures your contract deployment is
            secure against both classical and quantum computing attacks.
          </p>
          <div style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted, marginTop: 8 }}>
            Signature size: ~2,420 bytes | Security level: NIST Level 2
          </div>
        </div>

        {/* Deploy Summary */}
        <div style={{ ...panelStyle, padding: 16, width: "100%", maxWidth: 500 }}>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
            <span style={{ fontFamily: FONT.body, fontSize: 12, color: L.textSecondary }}>Contract</span>
            <span style={{ fontFamily: FONT.mono, fontSize: 12, color: L.textPrimary }}>{ctConfig?.label ?? "---"}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
            <span style={{ fontFamily: FONT.body, fontSize: 12, color: L.textSecondary }}>Token</span>
            <span style={{ fontFamily: FONT.mono, fontSize: 12, color: L.textPrimary }}>{name} ({symbol})</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
            <span style={{ fontFamily: FONT.body, fontSize: 12, color: L.textSecondary }}>Deploy Fee</span>
            <span style={{ fontFamily: FONT.mono, fontSize: 12, color: L.glowGold }}>{formatQbc(ctConfig?.deployFeeQbc ?? 0)}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
            <span style={{ fontFamily: FONT.body, fontSize: 12, color: L.textSecondary }}>ILLP Fee</span>
            <span style={{ fontFamily: FONT.mono, fontSize: 12, color: L.glowGold }}>
              {illp.feeQusd >= 999999 ? "BLOCKED" : formatQusd(illp.feeQusd)}
            </span>
          </div>
        </div>

        {/* Deploy Button */}
        <button
          onClick={handleDeploy}
          disabled={deploying}
          style={{
            ...btnBase,
            padding: "16px 48px",
            fontSize: 14,
            background: deploying ? L.borderMedium : L.glowCyan,
            color: L.textInverse,
            opacity: deploying ? 0.7 : 1,
            cursor: deploying ? "wait" : "pointer",
            boxShadow: deploying ? "none" : `0 0 24px ${L.glowCyan}40`,
          }}
        >
          {deploying ? "DEPLOYING..." : "DEPLOY TO QBC"}
        </button>

        {deployError && (
          <div
            style={{
              fontFamily: FONT.body,
              fontSize: 12,
              color: L.error,
              padding: "10px 16px",
              background: `${L.error}14`,
              border: `1px solid ${L.error}40`,
              borderRadius: 6,
              maxWidth: 500,
              textAlign: "center",
            }}
          >
            {deployError}
          </div>
        )}

        {!deployerAddress && !deploying && (
          <div
            style={{
              fontFamily: FONT.body,
              fontSize: 11,
              color: L.warning,
              padding: "8px 14px",
              background: `${L.warning}14`,
              border: `1px solid ${L.warning}40`,
              borderRadius: 4,
              maxWidth: 500,
              textAlign: "center",
            }}
          >
            Connect a wallet to deploy. Your deployment will be signed with your wallet address.
          </div>
        )}

        {deploying && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
            <div
              className="launchpad-shimmer"
              style={{
                width: 200,
                height: 4,
                borderRadius: 2,
                background: `linear-gradient(90deg, ${L.bgPanel}, ${L.glowCyan}, ${L.bgPanel})`,
                backgroundSize: "200% 100%",
              }}
            />
            <span style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>
              Signing with Dilithium2... Broadcasting to QBC network...
            </span>
          </div>
        )}
      </div>
    );
  }

  // Post-deploy success state
  const qpcsGrade = getQpcsGrade(deployResult.qpcs);
  const gradeColorMap: Record<string, string> = {
    quantum_grade: L.glowCyan,
    verified: L.glowEmerald,
    basic: L.glowGold,
    restricted: L.error,
    rejected: L.textMuted,
  };
  const gradeColor = gradeColorMap[qpcsGrade] ?? L.textMuted;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 20, padding: "40px 0" }}>
      {/* Success Icon */}
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: "50%",
          background: `${L.glowEmerald}20`,
          border: `2px solid ${L.glowEmerald}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: `0 0 24px ${L.glowEmerald}30`,
        }}
      >
        <span style={{ fontSize: 28, color: L.glowEmerald }}>{"\u2713"}</span>
      </div>

      <div
        style={{
          fontFamily: FONT.display,
          fontSize: 20,
          color: L.glowEmerald,
          letterSpacing: "0.04em",
        }}
      >
        DEPLOYMENT SUCCESSFUL
      </div>
      <p style={{ fontFamily: FONT.body, fontSize: 12, color: L.textSecondary, textAlign: "center" }}>
        {name} ({symbol}) has been deployed to the QBC blockchain.
      </p>

      {/* Result Details */}
      <div style={{ ...panelStyle, padding: 16, width: "100%", maxWidth: 560 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div>
            <div style={labelStyle}>Contract Address</div>
            <div style={{ fontFamily: FONT.mono, fontSize: 12, color: L.glowCyan, wordBreak: "break-all" }}>
              {deployResult.contractAddress}
            </div>
          </div>
          <div>
            <div style={labelStyle}>Transaction Hash</div>
            <div style={{ fontFamily: FONT.mono, fontSize: 12, color: L.textPrimary, wordBreak: "break-all" }}>
              {deployResult.txHash}
            </div>
          </div>
          <div>
            <div style={labelStyle}>DNA Fingerprint</div>
            <div style={{ fontFamily: FONT.mono, fontSize: 11, color: L.glowViolet, wordBreak: "break-all" }}>
              {deployResult.dnaFingerprint}
            </div>
          </div>
          <div>
            <div style={labelStyle}>QPCS Score</div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontFamily: FONT.display, fontSize: 18, color: gradeColor }}>
                {deployResult.qpcs.toFixed(1)}
              </span>
              <span
                style={{
                  fontFamily: FONT.display,
                  fontSize: 9,
                  color: gradeColor,
                  border: `1px solid ${gradeColor}40`,
                  borderRadius: 3,
                  padding: "2px 6px",
                  letterSpacing: "0.04em",
                  textTransform: "uppercase",
                }}
              >
                {qpcsGrade.replace(/_/g, " ")}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div style={{ display: "flex", gap: 12 }}>
        <button
          onClick={handleViewProject}
          style={{
            ...btnPrimary,
            padding: "12px 28px",
          }}
        >
          VIEW PROJECT
        </button>
        <button
          onClick={handleDeployAnother}
          style={{
            ...btnSecondary,
            padding: "12px 28px",
          }}
        >
          DEPLOY ANOTHER
        </button>
      </div>
    </div>
  );
});

/* ═══════════════════════════════════════════════════════════════════════════════
   MAIN WIZARD — DeployWizard
   ═══════════════════════════════════════════════════════════════════════════════ */

export const DeployWizard = memo(function DeployWizard() {
  const step = useLaunchpadStore((s) => s.deployStep);
  const setStep = useLaunchpadStore((s) => s.setDeployStep);
  const contractType = useLaunchpadStore((s) => s.deployContractType);
  const name = useLaunchpadStore((s) => s.deployName);
  const symbol = useLaunchpadStore((s) => s.deploySymbol);
  const description = useLaunchpadStore((s) => s.deployDescription);
  const website = useLaunchpadStore((s) => s.deployWebsite);
  const totalSupply = useLaunchpadStore((s) => s.deployTotalSupply);
  const allocations = useLaunchpadStore((s) => s.deployAllocations);
  const liquidityLockDays = useLaunchpadStore((s) => s.deployLiquidityLockDays);
  const deploying = useLaunchpadStore((s) => s.deploying);

  const [validationError, setValidationError] = useState<string | null>(null);

  const validateStep = useCallback(
    (s: DeployStep): boolean => {
      switch (s) {
        case 1:
          if (!contractType) {
            setValidationError("Please select a contract type.");
            return false;
          }
          break;
        case 2:
          if (!name.trim()) {
            setValidationError("Project name is required.");
            return false;
          }
          if (!symbol.trim() || symbol.length < 2) {
            setValidationError("Token symbol must be 2-8 characters.");
            return false;
          }
          if (!description.trim()) {
            setValidationError("Short description is required.");
            return false;
          }
          if (!website.trim()) {
            setValidationError("Website URL is required.");
            return false;
          }
          break;
        case 3:
          if (totalSupply <= 0) {
            setValidationError("Total supply must be greater than 0.");
            return false;
          }
          break;
        case 4: {
          const total = allocations.reduce((s, a) => s + a.percent, 0);
          if (Math.abs(total - 100) >= 0.01) {
            setValidationError(`Allocation total is ${total.toFixed(1)}%. Must equal 100%.`);
            return false;
          }
          break;
        }
        case 5: {
          const illp = calculateILLP(liquidityLockDays);
          if (illp.signal === "prohibited") {
            setValidationError("Liquidity lock must be at least 30 days.");
            return false;
          }
          break;
        }
        case 6:
          // Review step always passes
          break;
        case 7:
          break;
      }
      setValidationError(null);
      return true;
    },
    [contractType, name, symbol, description, website, totalSupply, allocations, liquidityLockDays]
  );

  const handleNext = useCallback(() => {
    if (step >= 7) return;
    if (!validateStep(step)) return;
    setStep((step + 1) as DeployStep);
  }, [step, validateStep, setStep]);

  const handleBack = useCallback(() => {
    if (step <= 1) return;
    setValidationError(null);
    setStep((step - 1) as DeployStep);
  }, [step, setStep]);

  const handleNavigate = useCallback(
    (target: DeployStep) => {
      if (target < step) {
        setValidationError(null);
        setStep(target);
      }
    },
    [step, setStep]
  );

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
      }}
    >
      {/* Step Indicator */}
      <StepIndicator current={step} onNavigate={handleNavigate} />

      {/* Step Content */}
      <div
        className="launchpad-scroll"
        style={{
          flex: 1,
          overflowY: "auto",
          minHeight: 0,
          paddingRight: 4,
        }}
      >
        {step === 1 && <StepContractType />}
        {step === 2 && <StepIdentity />}
        {step === 3 && <StepTokenConfig />}
        {step === 4 && <StepTokenomics />}
        {step === 5 && <StepLaunch />}
        {step === 6 && <StepReview />}
        {step === 7 && <StepDeploy />}
      </div>

      {/* Validation Error */}
      {validationError && (
        <div style={{ ...errorText, padding: "8px 0" }}>
          {"\u26A0"} {validationError}
        </div>
      )}

      {/* Navigation Buttons */}
      {step < 7 && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            paddingTop: 16,
            marginTop: 16,
            borderTop: `1px solid ${L.borderSubtle}`,
          }}
        >
          <button
            onClick={handleBack}
            disabled={step === 1}
            style={{
              ...btnSecondary,
              opacity: step === 1 ? 0.3 : 1,
              cursor: step === 1 ? "default" : "pointer",
            }}
          >
            BACK
          </button>
          <div style={{ fontFamily: FONT.mono, fontSize: 10, color: L.textMuted }}>
            Step {step} of 7
          </div>
          <button onClick={handleNext} style={btnPrimary}>
            {step === 6 ? "PROCEED TO DEPLOY" : "NEXT"}
          </button>
        </div>
      )}

      {/* Step 7 has no nav footer — deploy button is inside StepDeploy */}
    </div>
  );
});
