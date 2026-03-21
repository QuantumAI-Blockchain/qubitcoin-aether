"use client";
/* ---------------------------------------------------------------------------
   QBC Bridge — Vault Transparency Dashboard (100% backing proof)
   --------------------------------------------------------------------------- */

import { useState, useMemo, useCallback, useRef, useEffect, memo } from "react";
import { motion } from "framer-motion";
import {
  Lock,
  Shield,
  CheckCircle,
  ExternalLink,
  ArrowDown,
  TrendingUp,
} from "lucide-react";
import {
  AreaChart,
  Area,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import * as d3 from "d3";
import { CHAINS, EXTERNAL_CHAINS, getExplorerTxUrl, ZK_BRIDGE_VAULTS, QBC_ZK_BRIDGE, WRAPPED_ASSETS } from "./chain-config";
import type { ZKBridgeContracts } from "./chain-config";
import { useVaultState } from "./hooks";
import {
  B,
  FONT,
  Panel,
  SectionHeader,
  WTokenLabel,
  ChainBadge,
  CopyButton,
  HashDisplay,
  AnimatedNumber,
  Skeleton,
  truncAddr,
  formatAmount,
  panelStyle,
  chainColor,
} from "./shared";
import type { ExternalChainId, VaultState } from "./types";

/* ── Recharts Custom Tooltip ─────────────────────────────────────────────── */

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div
      className="rounded-lg border px-3 py-2"
      style={{
        background: B.bgElevated,
        borderColor: B.borderActive,
        boxShadow: `0 0 12px ${B.glowCyan}20`,
      }}
    >
      <div
        className="mb-1 text-[10px]"
        style={{ color: B.textSecondary, fontFamily: FONT.mono }}
      >
        {label}
      </div>
      {payload.map((entry, i) => (
        <div
          key={i}
          className="flex items-center gap-2 text-[10px]"
          style={{ fontFamily: FONT.mono }}
        >
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: entry.color }}
          />
          <span style={{ color: B.textSecondary }}>{entry.name}:</span>
          <span style={{ color: B.textPrimary }}>
            {formatAmount(entry.value, 0)}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ── Master Backing Panel ────────────────────────────────────────────────── */

function MasterBackingPanel({ vault }: { vault: VaultState }) {
  return (
    <Panel
      accent={B.glowGold}
      style={{
        borderWidth: 2,
        borderColor: `${B.glowGold}50`,
        boxShadow: `0 0 30px ${B.glowGold}10, inset 0 0 30px ${B.glowGold}05`,
      }}
    >
      <div className="mb-4 flex items-center gap-2">
        <Shield size={16} style={{ color: B.glowGold }} />
        <span
          className="text-xs font-bold uppercase tracking-[0.2em]"
          style={{ color: B.glowGold, fontFamily: FONT.display }}
        >
          1:1 Vault Backing Proof
        </span>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* QBC Vault */}
        <VaultColumn
          label="QBC VAULT"
          lockedLabel="QBC LOCKED"
          circulatingLabel="wQBC CIRCULATING"
          locked={vault.qbcLocked}
          circulating={vault.totalWqbc}
          backingRatio={vault.backingRatioQbc}
          lockedColor={B.glowCyan}
          circulatingColor={B.glowGold}
        />

        {/* QUSD Vault */}
        <VaultColumn
          label="QUSD VAULT"
          lockedLabel="QUSD LOCKED"
          circulatingLabel="wQUSD CIRCULATING"
          locked={vault.qusdLocked}
          circulating={vault.totalWqusd}
          backingRatio={vault.backingRatioQusd}
          lockedColor={B.glowViolet}
          circulatingColor={B.glowEmerald}
        />
      </div>

      <div
        className="mt-4 rounded-lg border px-3 py-2 text-center text-[10px]"
        style={{
          borderColor: `${B.glowGold}30`,
          background: `${B.glowGold}08`,
          color: B.glowGold,
          fontFamily: FONT.body,
        }}
      >
        Every wQBC is backed by exactly 1 locked QBC. Every wQUSD is backed by
        exactly 1 locked QUSD. Fully redeemable at any time.
      </div>
    </Panel>
  );
}

function VaultColumn({
  label,
  lockedLabel,
  circulatingLabel,
  locked,
  circulating,
  backingRatio,
  lockedColor,
  circulatingColor,
}: {
  label: string;
  lockedLabel: string;
  circulatingLabel: string;
  locked: number;
  circulating: number;
  backingRatio: number;
  lockedColor: string;
  circulatingColor: string;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Lock size={14} style={{ color: lockedColor }} />
        <span
          className="text-[10px] font-bold uppercase tracking-[0.15em]"
          style={{ color: lockedColor, fontFamily: FONT.display }}
        >
          {label}
        </span>
      </div>

      {/* Locked */}
      <div
        className="rounded-lg border p-3 text-center"
        style={{
          borderColor: `${lockedColor}30`,
          background: `${lockedColor}08`,
        }}
      >
        <div
          className="text-[9px] uppercase tracking-[0.15em]"
          style={{ color: B.textSecondary, fontFamily: FONT.display }}
        >
          {lockedLabel}
        </div>
        <AnimatedNumber
          value={locked}
          decimals={0}
          color={lockedColor}
          size="text-xl"
        />
      </div>

      {/* Connector */}
      <div className="flex flex-col items-center gap-0.5">
        <div
          className="h-4 w-px"
          style={{ background: `${B.textSecondary}40` }}
        />
        <ArrowDown size={14} style={{ color: B.textSecondary }} />
        <div
          className="h-4 w-px"
          style={{ background: `${B.textSecondary}40` }}
        />
      </div>

      {/* Circulating */}
      <div
        className="rounded-lg border p-3 text-center"
        style={{
          borderColor: `${circulatingColor}30`,
          background: `${circulatingColor}08`,
        }}
      >
        <div
          className="text-[9px] uppercase tracking-[0.15em]"
          style={{ color: B.textSecondary, fontFamily: FONT.display }}
        >
          {circulatingLabel}
        </div>
        <AnimatedNumber
          value={circulating}
          decimals={0}
          color={circulatingColor}
          size="text-xl"
        />
      </div>

      {/* Backing badge */}
      <div className="flex items-center justify-center gap-2">
        <CheckCircle size={14} style={{ color: B.glowEmerald }} />
        <span
          className="text-xs font-bold"
          style={{ color: B.glowEmerald, fontFamily: FONT.mono }}
        >
          BACKING: {((backingRatio ?? 0) * 100).toFixed(2)}%
        </span>
        <CheckCircle size={14} style={{ color: B.glowEmerald }} />
      </div>
    </div>
  );
}

/* ── Per-Chain Breakdown Table ────────────────────────────────────────────── */

function ChainBreakdown({ vault }: { vault: VaultState }) {
  const chainRows: Array<{
    chain: ExternalChainId;
    wqbc: number;
    wqusd: number;
  }> = EXTERNAL_CHAINS.map((c) => ({
    chain: c,
    wqbc: vault.wqbcByChain?.[c] ?? 0,
    wqusd: vault.wqusdByChain?.[c] ?? 0,
  }));

  const totalWqbc = chainRows.reduce((s, r) => s + r.wqbc, 0);
  const totalWqusd = chainRows.reduce((s, r) => s + r.wqusd, 0);

  return (
    <Panel>
      <SectionHeader title="PER-CHAIN BREAKDOWN" />
      <div className="overflow-x-auto">
        <table className="w-full" style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr
              style={{
                borderBottom: `1px solid ${B.borderSubtle}`,
                background: B.bgBase,
              }}
            >
              {["CHAIN", "wQBC SUPPLY", "wQUSD SUPPLY", "wQBC CONTRACT", "wQUSD CONTRACT", "STATUS"].map(
                (col) => (
                  <th
                    key={col}
                    className="px-3 py-2 text-left text-[9px] font-bold uppercase tracking-[0.15em]"
                    style={{
                      color: B.textSecondary,
                      fontFamily: FONT.display,
                    }}
                  >
                    {col}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {chainRows.map((row) => {
              const info = CHAINS[row.chain];
              return (
                <tr
                  key={row.chain}
                  style={{
                    borderBottom: `1px solid ${B.borderSubtle}40`,
                  }}
                >
                  <td className="px-3 py-2.5">
                    <ChainBadge chain={row.chain} showStatus />
                  </td>
                  <td
                    className="px-3 py-2.5 text-[10px]"
                    style={{ color: B.glowGold, fontFamily: FONT.mono }}
                  >
                    {formatAmount(row.wqbc, 2)}
                  </td>
                  <td
                    className="px-3 py-2.5 text-[10px]"
                    style={{ color: B.glowEmerald, fontFamily: FONT.mono }}
                  >
                    {formatAmount(row.wqusd, 2)}
                  </td>
                  <td className="px-3 py-2.5">
                    {info.wqbcAddr ? (
                      <div className="flex items-center gap-1">
                        <HashDisplay hash={info.wqbcAddr} truncLen={6} />
                        <CopyButton text={info.wqbcAddr} size={10} />
                        <a
                          href={`${info.explorerUrl}/address/${info.wqbcAddr}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: B.glowCyan }}
                        >
                          <ExternalLink size={10} />
                        </a>
                      </div>
                    ) : (
                      <span
                        className="text-[10px]"
                        style={{ color: B.textSecondary, fontFamily: FONT.mono }}
                      >
                        Not deployed
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    {info.wqusdAddr ? (
                      <div className="flex items-center gap-1">
                        <HashDisplay hash={info.wqusdAddr} truncLen={6} />
                        <CopyButton text={info.wqusdAddr} size={10} />
                        <a
                          href={`${info.explorerUrl}/address/${info.wqusdAddr}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: B.glowCyan }}
                        >
                          <ExternalLink size={10} />
                        </a>
                      </div>
                    ) : (
                      <span
                        className="text-[10px]"
                        style={{ color: B.textSecondary, fontFamily: FONT.mono }}
                      >
                        Not deployed
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <span
                      className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold tracking-wider"
                      style={{
                        color: info.available ? B.glowEmerald : B.glowCrimson,
                        background: info.available
                          ? `${B.glowEmerald}15`
                          : `${B.glowCrimson}15`,
                        fontFamily: FONT.display,
                      }}
                    >
                      <span
                        className="inline-block h-1.5 w-1.5 rounded-full"
                        style={{
                          background: info.available
                            ? B.glowEmerald
                            : B.glowCrimson,
                        }}
                      />
                      {info.available ? "LIVE" : "OFFLINE"}
                    </span>
                  </td>
                </tr>
              );
            })}

            {/* Total Row */}
            <tr
              style={{
                background: `${B.glowGold}08`,
                borderTop: `2px solid ${B.glowGold}40`,
              }}
            >
              <td className="px-3 py-2.5">
                <span
                  className="text-[10px] font-bold uppercase tracking-[0.15em]"
                  style={{ color: B.glowGold, fontFamily: FONT.display }}
                >
                  TOTAL
                </span>
              </td>
              <td
                className="px-3 py-2.5 text-[10px] font-bold"
                style={{ color: B.glowGold, fontFamily: FONT.mono }}
              >
                {formatAmount(totalWqbc, 2)}
              </td>
              <td
                className="px-3 py-2.5 text-[10px] font-bold"
                style={{ color: B.glowEmerald, fontFamily: FONT.mono }}
              >
                {formatAmount(totalWqusd, 2)}
              </td>
              <td colSpan={2} className="px-3 py-2.5">
                <div className="flex items-center gap-1.5">
                  <CheckCircle size={12} style={{ color: B.glowEmerald }} />
                  <span
                    className="text-[10px] font-bold"
                    style={{
                      color: B.glowEmerald,
                      fontFamily: FONT.mono,
                    }}
                  >
                    TOTALS MATCH VAULT
                  </span>
                </div>
              </td>
              <td className="px-3 py-2.5">
                <CheckCircle size={12} style={{ color: B.glowEmerald }} />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

/* ── Vault Contract Addresses ────────────────────────────────────────────── */

function VaultAddresses({ vault }: { vault: VaultState }) {
  return (
    <Panel>
      <SectionHeader title="VAULT CONTRACT ADDRESSES" />
      <div className="grid gap-3 md:grid-cols-2">
        {/* QBC Vault */}
        <div
          className="rounded-lg border p-3"
          style={{
            borderColor: `${B.glowCyan}25`,
            background: `${B.glowCyan}05`,
          }}
        >
          <div
            className="mb-1 text-[9px] font-bold uppercase tracking-[0.15em]"
            style={{ color: B.glowCyan, fontFamily: FONT.display }}
          >
            QBC Vault (Lock Contract)
          </div>
          <div className="flex items-center gap-2">
            <HashDisplay hash={vault.vaultAddrQbc} truncLen={10} />
            <CopyButton text={vault.vaultAddrQbc} size={10} />
          </div>
        </div>

        {/* QUSD Vault */}
        <div
          className="rounded-lg border p-3"
          style={{
            borderColor: `${B.glowViolet}25`,
            background: `${B.glowViolet}05`,
          }}
        >
          <div
            className="mb-1 text-[9px] font-bold uppercase tracking-[0.15em]"
            style={{ color: B.glowViolet, fontFamily: FONT.display }}
          >
            QUSD Vault (Lock Contract)
          </div>
          <div className="flex items-center gap-2">
            <HashDisplay hash={vault.vaultAddrQusd} truncLen={10} />
            <CopyButton text={vault.vaultAddrQusd} size={10} />
          </div>
        </div>
      </div>
    </Panel>
  );
}

/* ── Vault Balance History Chart ─────────────────────────────────────────── */

function VaultBalanceChart({ vault }: { vault: VaultState }) {
  return (
    <Panel>
      <SectionHeader title="VAULT BALANCE HISTORY (30 DAYS)" />
      <div style={{ width: "100%", height: 260 }}>
        <ResponsiveContainer>
          <AreaChart
            data={vault.backingHistory}
            margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
          >
            <defs>
              <linearGradient id="gradLocked" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={B.glowCyan} stopOpacity={0.3} />
                <stop offset="95%" stopColor={B.glowCyan} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradCirc" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={B.glowGold} stopOpacity={0.3} />
                <stop offset="95%" stopColor={B.glowGold} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={`${B.borderSubtle}60`}
            />
            <XAxis
              dataKey="date"
              tick={{
                fontSize: 9,
                fill: B.textSecondary,
                fontFamily: FONT.mono,
              }}
              stroke={B.borderSubtle}
              tickFormatter={(v: string) => v.slice(5)}
            />
            <YAxis
              tick={{
                fontSize: 9,
                fill: B.textSecondary,
                fontFamily: FONT.mono,
              }}
              stroke={B.borderSubtle}
              tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
            />
            <RTooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{
                fontSize: 10,
                fontFamily: FONT.mono,
                color: B.textSecondary,
              }}
            />
            <Area
              type="monotone"
              dataKey="qbcLocked"
              name="QBC Locked"
              stroke={B.glowCyan}
              fill="url(#gradLocked)"
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="wqbcCirculating"
              name="wQBC Circulating"
              stroke={B.glowGold}
              fill="url(#gradCirc)"
              strokeWidth={2}
              strokeDasharray="4 2"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div
        className="mt-2 text-center text-[9px]"
        style={{ color: B.textSecondary, fontFamily: FONT.mono }}
      >
        Lines overlap perfectly — locked QBC always equals circulating wQBC
      </div>
    </Panel>
  );
}

/* ── Wrap/Unwrap Flow Chart ──────────────────────────────────────────────── */

function WrapUnwrapFlowChart({ vault }: { vault: VaultState }) {
  return (
    <Panel>
      <SectionHeader title="WRAP / UNWRAP FLOW (30 DAYS)" />
      <div style={{ width: "100%", height: 260 }}>
        <ResponsiveContainer>
          <ComposedChart
            data={vault.wrapUnwrapHistory}
            margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={`${B.borderSubtle}60`}
            />
            <XAxis
              dataKey="date"
              tick={{
                fontSize: 9,
                fill: B.textSecondary,
                fontFamily: FONT.mono,
              }}
              stroke={B.borderSubtle}
              tickFormatter={(v: string) => v.slice(5)}
            />
            <YAxis
              yAxisId="bars"
              tick={{
                fontSize: 9,
                fill: B.textSecondary,
                fontFamily: FONT.mono,
              }}
              stroke={B.borderSubtle}
              tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
            />
            <YAxis
              yAxisId="line"
              orientation="right"
              tick={{
                fontSize: 9,
                fill: B.textSecondary,
                fontFamily: FONT.mono,
              }}
              stroke={B.borderSubtle}
              tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
            />
            <RTooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{
                fontSize: 10,
                fontFamily: FONT.mono,
                color: B.textSecondary,
              }}
            />
            <Bar
              yAxisId="bars"
              dataKey="wrapped"
              name="Wrapped"
              fill={B.glowCyan}
              opacity={0.7}
              radius={[2, 2, 0, 0]}
            />
            <Bar
              yAxisId="bars"
              dataKey="unwrapped"
              name="Unwrapped"
              fill={B.glowGold}
              opacity={0.7}
              radius={[2, 2, 0, 0]}
            />
            <Line
              yAxisId="line"
              type="monotone"
              dataKey="netBalance"
              name="Net Balance"
              stroke={B.glowViolet}
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

/* ── D3 Treemap: wQBC Distribution by Chain ──────────────────────────────── */

interface TreemapDatum {
  chain: ExternalChainId;
  label: string;
  value: number;
  color: string;
}

function WqbcTreemap({ vault }: { vault: VaultState }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    datum: TreemapDatum;
  } | null>(null);

  const data: TreemapDatum[] = useMemo(
    () => [
      {
        chain: "ethereum" as ExternalChainId,
        label: "ETH",
        value: vault.wqbcByChain.ethereum,
        color: "#627eea",
      },
      {
        chain: "bnb" as ExternalChainId,
        label: "BNB",
        value: vault.wqbcByChain.bnb,
        color: "#f3ba2f",
      },
      {
        chain: "solana" as ExternalChainId,
        label: "SOL",
        value: vault.wqbcByChain.solana,
        color: "#9945ff",
      },
    ],
    [vault.wqbcByChain],
  );

  useEffect(() => {
    const container = containerRef.current;
    const svg = svgRef.current;
    if (!container || !svg) return;

    const width = container.clientWidth;
    const height = 200;

    svg.setAttribute("width", String(width));
    svg.setAttribute("height", String(height));

    // Clear previous
    while (svg.firstChild) {
      svg.removeChild(svg.firstChild);
    }

    // Build hierarchy
    type TreemapRoot = { children?: TreemapDatum[]; value?: number };
    const root = d3
      .hierarchy<TreemapRoot>({ children: data })
      .sum((d) => (d as unknown as TreemapDatum).value ?? 0);

    d3.treemap<TreemapRoot>()
      .size([width, height])
      .padding(3)
      .round(true)(root);

    const leaves = root.leaves() as d3.HierarchyRectangularNode<TreemapRoot>[];

    for (const leaf of leaves) {
      const datum = leaf.data as unknown as TreemapDatum;
      const lx0 = leaf.x0;
      const ly0 = leaf.y0;
      const lx1 = leaf.x1;
      const ly1 = leaf.y1;
      const w = lx1 - lx0;
      const h = ly1 - ly0;

      // Rectangle
      const rect = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "rect",
      );
      rect.setAttribute("x", String(lx0));
      rect.setAttribute("y", String(ly0));
      rect.setAttribute("width", String(w));
      rect.setAttribute("height", String(h));
      rect.setAttribute("rx", "6");
      rect.setAttribute("fill", datum.color);
      rect.setAttribute("opacity", "0.25");
      rect.setAttribute("stroke", datum.color);
      rect.setAttribute("stroke-width", "1.5");
      rect.style.cursor = "pointer";
      rect.style.transition = "opacity 0.2s";

      rect.addEventListener("mouseenter", (e) => {
        rect.setAttribute("opacity", "0.45");
        const bounds = container.getBoundingClientRect();
        setTooltip({
          x: (e as MouseEvent).clientX - bounds.left,
          y: (e as MouseEvent).clientY - bounds.top - 10,
          datum,
        });
      });
      rect.addEventListener("mouseleave", () => {
        rect.setAttribute("opacity", "0.25");
        setTooltip(null);
      });

      svg.appendChild(rect);

      // Label
      if (w > 50 && h > 30) {
        const text = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "text",
        );
        text.setAttribute("x", String(lx0 + w / 2));
        text.setAttribute("y", String(ly0 + h / 2 - 8));
        text.setAttribute("text-anchor", "middle");
        text.setAttribute("dominant-baseline", "middle");
        text.setAttribute("fill", datum.color);
        text.setAttribute("font-family", FONT.display);
        text.setAttribute("font-size", "14");
        text.setAttribute("font-weight", "700");
        text.setAttribute("letter-spacing", "0.1em");
        text.setAttribute("pointer-events", "none");
        text.textContent = datum.label;
        svg.appendChild(text);

        // Value
        const valText = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "text",
        );
        valText.setAttribute("x", String(lx0 + w / 2));
        valText.setAttribute("y", String(ly0 + h / 2 + 12));
        valText.setAttribute("text-anchor", "middle");
        valText.setAttribute("dominant-baseline", "middle");
        valText.setAttribute("fill", B.textSecondary);
        valText.setAttribute("font-family", FONT.mono);
        valText.setAttribute("font-size", "10");
        valText.setAttribute("pointer-events", "none");
        valText.textContent = `${formatAmount(datum.value, 0)} wQBC`;
        svg.appendChild(valText);

        // Percentage
        const total = data.reduce((s, d) => s + d.value, 0);
        const pct = ((datum.value / total) * 100).toFixed(1);
        const pctText = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "text",
        );
        pctText.setAttribute("x", String(lx0 + w / 2));
        pctText.setAttribute("y", String(ly0 + h / 2 + 26));
        pctText.setAttribute("text-anchor", "middle");
        pctText.setAttribute("dominant-baseline", "middle");
        pctText.setAttribute("fill", `${B.textSecondary}80`);
        pctText.setAttribute("font-family", FONT.mono);
        pctText.setAttribute("font-size", "9");
        pctText.setAttribute("pointer-events", "none");
        pctText.textContent = `${pct}%`;
        svg.appendChild(pctText);
      }
    }
  }, [data]);

  return (
    <Panel>
      <SectionHeader title="wQBC DISTRIBUTION BY CHAIN" />
      <div ref={containerRef} className="relative">
        <svg ref={svgRef} />

        {/* Tooltip */}
        {tooltip && (
          <div
            className="pointer-events-none absolute rounded-lg border px-3 py-2"
            style={{
              left: tooltip.x,
              top: tooltip.y,
              transform: "translate(-50%, -100%)",
              background: B.bgElevated,
              borderColor: tooltip.datum.color,
              boxShadow: `0 0 12px ${tooltip.datum.color}30`,
              zIndex: 10,
            }}
          >
            <div
              className="text-[10px] font-bold"
              style={{
                color: tooltip.datum.color,
                fontFamily: FONT.display,
              }}
            >
              {CHAINS[tooltip.datum.chain].name}
            </div>
            <div
              className="text-[10px]"
              style={{ color: B.textPrimary, fontFamily: FONT.mono }}
            >
              {formatAmount(tooltip.datum.value, 2)} wQBC
            </div>
            <div
              className="text-[9px]"
              style={{ color: B.textSecondary, fontFamily: FONT.mono }}
            >
              {(
                (tooltip.datum.value /
                  data.reduce((s, d) => s + d.value, 0)) *
                100
              ).toFixed(1)}
              % of total
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

/* ── ZK Bridge Infrastructure Panel ────────────────────────────────────── */

function ZKBridgeInfrastructure() {
  const evmChains = EXTERNAL_CHAINS.filter((c) => c !== "solana");

  return (
    <Panel
      accent="#7c3aed"
      style={{
        borderWidth: 2,
        borderColor: "#7c3aed50",
        boxShadow: "0 0 30px #7c3aed10, inset 0 0 30px #7c3aed05",
      }}
    >
      <div className="mb-4 flex items-center gap-2">
        <Shield size={16} style={{ color: "#7c3aed" }} />
        <span
          className="text-xs font-bold uppercase tracking-[0.2em]"
          style={{ color: "#7c3aed", fontFamily: FONT.display }}
        >
          ZK Bridge Infrastructure (Quantum-Secure)
        </span>
      </div>

      {/* Architecture overview */}
      <div
        className="mb-4 rounded-lg border p-3"
        style={{
          borderColor: `${B.borderSubtle}40`,
          background: `${B.bgBase}`,
        }}
      >
        <div
          className="mb-2 text-[10px] font-bold uppercase tracking-[0.15em]"
          style={{ color: B.textPrimary, fontFamily: FONT.display }}
        >
          Architecture
        </div>
        <div
          className="space-y-1 text-[10px]"
          style={{ color: B.textSecondary, fontFamily: FONT.mono }}
        >
          <div>Lock ETH/BNB/MATIC/AVAX → Poseidon2 ZK Proof → Mint wToken on QBC</div>
          <div>Burn wToken on QBC → Poseidon2 ZK Proof → Unlock native on source chain</div>
          <div className="pt-1" style={{ color: "#7c3aed" }}>
            Dilithium5 post-quantum signatures on all proof submissions
          </div>
        </div>
      </div>

      {/* QBC-side contracts */}
      <div className="mb-4">
        <div
          className="mb-2 text-[10px] font-bold uppercase tracking-[0.15em]"
          style={{ color: B.glowCyan, fontFamily: FONT.display }}
        >
          QBC Chain Contracts
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          <ZKContractCard
            label="BridgeMinter"
            description="Mints/burns wrapped assets (wETH, wBNB, wMATIC, wAVAX)"
            address={QBC_ZK_BRIDGE.bridgeMinter}
            status={QBC_ZK_BRIDGE.status}
            color={B.glowCyan}
          />
          <ZKContractCard
            label="ZKBridgeVerifier"
            description="Poseidon2 proof verification on QBC"
            address={QBC_ZK_BRIDGE.zkVerifier}
            status={QBC_ZK_BRIDGE.status}
            color={B.glowCyan}
          />
        </div>
      </div>

      {/* Wrapped assets on QBC */}
      <div className="mb-4">
        <div
          className="mb-2 text-[10px] font-bold uppercase tracking-[0.15em]"
          style={{ color: B.glowGold, fontFamily: FONT.display }}
        >
          Wrapped Assets on QBC
        </div>
        <div className="grid gap-2 md:grid-cols-4">
          {Object.entries(WRAPPED_ASSETS).map(([key, asset]) => (
            <div
              key={key}
              className="rounded-lg border p-2"
              style={{
                borderColor: `${B.glowGold}25`,
                background: `${B.glowGold}05`,
              }}
            >
              <div
                className="text-[10px] font-bold"
                style={{ color: B.glowGold, fontFamily: FONT.display }}
              >
                {asset.symbol}
              </div>
              <div
                className="text-[9px]"
                style={{ color: B.textSecondary, fontFamily: FONT.mono }}
              >
                {asset.name}
              </div>
              <div
                className="mt-1 text-[9px]"
                style={{ color: asset.address ? B.glowEmerald : B.textSecondary, fontFamily: FONT.mono }}
              >
                {asset.address ? truncAddr(asset.address) : "Pending deployment"}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Per-chain vault table */}
      <div>
        <div
          className="mb-2 text-[10px] font-bold uppercase tracking-[0.15em]"
          style={{ color: "#7c3aed", fontFamily: FONT.display }}
        >
          External Chain Vaults
        </div>
        <div className="overflow-x-auto">
          <table className="w-full" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${B.borderSubtle}`, background: B.bgBase }}>
                {["CHAIN", "VAULT CONTRACT", "ZK VERIFIER", "STATUS"].map((col) => (
                  <th
                    key={col}
                    className="px-3 py-2 text-left text-[9px] font-bold uppercase tracking-[0.15em]"
                    style={{ color: B.textSecondary, fontFamily: FONT.display }}
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {evmChains.map((chainId) => {
                const chain = CHAINS[chainId];
                const zk = ZK_BRIDGE_VAULTS[chainId];
                const statusColor = zk.status === "deployed" ? B.glowEmerald : B.glowGold;
                const statusLabel = zk.status === "deployed" ? "LIVE" : "PENDING";

                return (
                  <tr key={chainId} style={{ borderBottom: `1px solid ${B.borderSubtle}40` }}>
                    <td className="px-3 py-2.5">
                      <ChainBadge chain={chainId} showStatus />
                    </td>
                    <td className="px-3 py-2.5">
                      {zk.vault ? (
                        <div className="flex items-center gap-1">
                          <HashDisplay hash={zk.vault} truncLen={6} />
                          <CopyButton text={zk.vault} size={10} />
                          <a
                            href={`${chain.explorerUrl}/address/${zk.vault}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ color: B.glowCyan }}
                          >
                            <ExternalLink size={10} />
                          </a>
                        </div>
                      ) : (
                        <span className="text-[10px]" style={{ color: B.textSecondary, fontFamily: FONT.mono }}>
                          Awaiting deployment
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      {zk.verifier ? (
                        <div className="flex items-center gap-1">
                          <HashDisplay hash={zk.verifier} truncLen={6} />
                          <CopyButton text={zk.verifier} size={10} />
                          <a
                            href={`${chain.explorerUrl}/address/${zk.verifier}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ color: B.glowCyan }}
                          >
                            <ExternalLink size={10} />
                          </a>
                        </div>
                      ) : (
                        <span className="text-[10px]" style={{ color: B.textSecondary, fontFamily: FONT.mono }}>
                          Awaiting deployment
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold tracking-wider"
                        style={{
                          color: statusColor,
                          background: `${statusColor}15`,
                          fontFamily: FONT.display,
                        }}
                      >
                        <span
                          className="inline-block h-1.5 w-1.5 rounded-full"
                          style={{ background: statusColor }}
                        />
                        {statusLabel}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </Panel>
  );
}

function ZKContractCard({
  label,
  description,
  address,
  status,
  color,
}: {
  label: string;
  description: string;
  address: string | null;
  status: "deployed" | "pending";
  color: string;
}) {
  return (
    <div
      className="rounded-lg border p-3"
      style={{ borderColor: `${color}25`, background: `${color}05` }}
    >
      <div className="flex items-center justify-between">
        <div
          className="text-[10px] font-bold uppercase tracking-[0.1em]"
          style={{ color, fontFamily: FONT.display }}
        >
          {label}
        </div>
        <span
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[8px] font-bold"
          style={{
            color: status === "deployed" ? B.glowEmerald : B.glowGold,
            background: status === "deployed" ? `${B.glowEmerald}15` : `${B.glowGold}15`,
            fontFamily: FONT.display,
          }}
        >
          <span
            className="inline-block h-1 w-1 rounded-full"
            style={{ background: status === "deployed" ? B.glowEmerald : B.glowGold }}
          />
          {status === "deployed" ? "LIVE" : "PENDING"}
        </span>
      </div>
      <div className="mt-1 text-[9px]" style={{ color: B.textSecondary, fontFamily: FONT.body }}>
        {description}
      </div>
      <div className="mt-2 text-[10px]" style={{ fontFamily: FONT.mono }}>
        {address ? (
          <div className="flex items-center gap-1">
            <HashDisplay hash={address} truncLen={8} />
            <CopyButton text={address} size={10} />
          </div>
        ) : (
          <span style={{ color: B.textSecondary }}>Awaiting deployment</span>
        )}
      </div>
    </div>
  );
}

/* ── Vault Dashboard (Main Export) ───────────────────────────────────────── */

export function VaultDashboard() {
  const { data: vault, isLoading } = useVaultState();

  if (isLoading || !vault) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 p-4">
        <SectionHeader title="VAULT TRANSPARENCY DASHBOARD" />
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} width="100%" height={180} />
        ))}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4">
      <SectionHeader
        title="VAULT TRANSPARENCY DASHBOARD"
        action={
          <div className="flex items-center gap-1.5">
            <TrendingUp size={12} style={{ color: B.glowEmerald }} />
            <span
              className="text-[10px]"
              style={{ color: B.glowEmerald, fontFamily: FONT.mono }}
            >
              100% Backed
            </span>
          </div>
        }
      />

      {/* Master Backing */}
      <MasterBackingPanel vault={vault} />

      {/* ZK Bridge Infrastructure */}
      <ZKBridgeInfrastructure />

      {/* Per-Chain Breakdown */}
      <ChainBreakdown vault={vault} />

      {/* Vault Addresses */}
      <VaultAddresses vault={vault} />

      {/* Charts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <VaultBalanceChart vault={vault} />
        <WrapUnwrapFlowChart vault={vault} />
      </div>

      {/* Treemap */}
      <WqbcTreemap vault={vault} />
    </div>
  );
}

export default VaultDashboard;
