"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — SUSY Mining Leaderboard
   ───────────────────────────────────────────────────────────────────────── */

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { Trophy, Medal, Star, TrendingUp, Zap } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { useMiners, useNetworkStats } from "./hooks";
import { useExplorerStore } from "./store";
import {
  C, FONT, Badge, DataTable, HashLink, LoadingSpinner,
  Panel, SectionHeader, StatCard, Pagination, formatQBC, formatNumber, truncHash,
} from "./shared";
import type { MinerStats } from "./types";

const PAGE_SIZE = 15;

function rankIcon(rank: number) {
  if (rank === 1) return <Trophy size={14} style={{ color: "#ffd700" }} />;
  if (rank === 2) return <Medal size={14} style={{ color: "#c0c0c0" }} />;
  if (rank === 3) return <Medal size={14} style={{ color: "#cd7f32" }} />;
  return <span style={{ color: C.textMuted }}>{rank}</span>;
}

function rankColor(rank: number): string {
  if (rank === 1) return "#ffd700";
  if (rank === 2) return "#c0c0c0";
  if (rank === 3) return "#cd7f32";
  return C.textSecondary;
}

export function SUSYLeaderboard() {
  const navigate = useExplorerStore((s) => s.navigate);
  const { data: miners, isLoading } = useMiners();
  const { data: stats } = useNetworkStats();
  const [page, setPage] = useState(0);
  const [sortBy, setSortBy] = useState<"blocksMined" | "totalRewards" | "susyScore">("blocksMined");

  const sorted = useMemo(() => {
    const list = [...(miners ?? [])];
    list.sort((a, b) => b[sortBy] - a[sortBy]);
    list.forEach((m, i) => (m.rank = i + 1));
    return list;
  }, [miners, sortBy]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const pageData = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  // Chart data — top 10
  const chartData = sorted.slice(0, 10).map((m) => ({
    address: truncHash(m.address, 4),
    blocks: m.blocksMined,
    rewards: m.totalRewards,
    susy: m.susyScore,
  }));

  if (isLoading) return <LoadingSpinner />;

  const totalBlocks = sorted.reduce((s, m) => s + m.blocksMined, 0);
  const totalRewards = sorted.reduce((s, m) => s + m.totalRewards, 0);
  const avgSusy = sorted.length > 0
    ? sorted.reduce((s, m) => s + m.susyScore, 0) / sorted.length
    : 0;

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <h1
          className="mb-1 text-lg font-bold tracking-widest"
          style={{ color: C.textPrimary, fontFamily: FONT.heading }}
        >
          SUSY LEADERBOARD
        </h1>
        <p className="text-xs" style={{ color: C.textSecondary, fontFamily: FONT.body }}>
          Proof-of-SUSY-Alignment mining competition — ranked by VQE performance
        </p>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Total Miners"
          value={formatNumber(sorted.length)}
          icon={Star}
          color={C.primary}
        />
        <StatCard
          label="Total Blocks"
          value={formatNumber(totalBlocks)}
          icon={Zap}
          color={C.success}
        />
        <StatCard
          label="Total Rewards"
          value={formatQBC(totalRewards) + " QBC"}
          icon={TrendingUp}
          color={C.accent}
        />
        <StatCard
          label="Avg SUSY Score"
          value={avgSusy.toFixed(1)}
          icon={Trophy}
          color={C.secondary}
        />
      </div>

      {/* Top 3 Podium */}
      {sorted.length >= 3 && (
        <div className="grid grid-cols-3 gap-3">
          {[1, 0, 2].map((idx) => {
            const miner = sorted[idx];
            const isFirst = idx === 0;
            return (
              <motion.div
                key={miner.address}
                whileHover={{ scale: 1.02 }}
                onClick={() => navigate("wallet", { id: miner.address })}
                className={`flex flex-col items-center gap-2 rounded-lg border p-4 ${isFirst ? "order-first sm:order-none" : ""}`}
                style={{
                  background: `${rankColor(idx + 1)}08`,
                  borderColor: `${rankColor(idx + 1)}30`,
                  cursor: "pointer",
                  marginTop: isFirst ? 0 : 16,
                }}
              >
                {rankIcon(idx + 1)}
                <span
                  className="text-[10px] uppercase tracking-widest"
                  style={{ color: rankColor(idx + 1), fontFamily: FONT.heading }}
                >
                  #{idx + 1}
                </span>
                <span className="text-xs" style={{ color: C.textPrimary, fontFamily: FONT.mono }}>
                  {truncHash(miner.address, 6)}
                </span>
                <span className="text-lg font-bold" style={{ color: C.success, fontFamily: FONT.mono }}>
                  {miner.blocksMined}
                </span>
                <span className="text-[10px]" style={{ color: C.textMuted }}>
                  blocks
                </span>
                <Badge label={`SUSY ${miner.susyScore.toFixed(1)}`} color={C.secondary} />
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Chart */}
      <Panel>
        <SectionHeader title="TOP 10 — BLOCKS MINED" />
        <div style={{ height: 200 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid stroke={`${C.border}40`} />
              <XAxis
                dataKey="address"
                tick={{ fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 9, fill: C.textMuted }}
                axisLine={false}
                tickLine={false}
                width={35}
              />
              <Tooltip
                contentStyle={{
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                  borderRadius: 6,
                  fontSize: 10,
                  fontFamily: FONT.mono,
                }}
              />
              <Bar dataKey="blocks" fill={C.primary} radius={[4, 4, 0, 0]} name="Blocks" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      {/* Sort Controls + Table */}
      <Panel>
        <div className="mb-3 flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-widest" style={{ color: C.textMuted, fontFamily: FONT.heading }}>
            SORT BY:
          </span>
          {(["blocksMined", "totalRewards", "susyScore"] as const).map((s) => (
            <button
              key={s}
              onClick={() => { setSortBy(s); setPage(0); }}
              className="rounded px-2 py-1 text-[10px] transition-colors"
              style={{
                color: sortBy === s ? C.primary : C.textSecondary,
                background: sortBy === s ? `${C.primary}15` : "transparent",
                fontFamily: FONT.heading,
              }}
            >
              {s === "blocksMined" ? "BLOCKS" : s === "totalRewards" ? "REWARDS" : "SUSY SCORE"}
            </button>
          ))}
        </div>

        <DataTable<MinerStats>
          columns={[
            {
              key: "rank",
              header: "#",
              width: "40px",
              render: (m) => rankIcon(m.rank),
            },
            {
              key: "address",
              header: "MINER",
              render: (m) => <HashLink hash={m.address} type="wallet" truncLen={10} />,
            },
            {
              key: "blocks",
              header: "BLOCKS",
              align: "right",
              render: (m) => (
                <span style={{ color: C.textPrimary, fontWeight: "bold" }}>
                  {formatNumber(m.blocksMined)}
                </span>
              ),
            },
            {
              key: "rewards",
              header: "REWARDS (QBC)",
              align: "right",
              render: (m) => <span style={{ color: C.success }}>{formatQBC(m.totalRewards)}</span>,
            },
            {
              key: "avgEnergy",
              header: "AVG ENERGY",
              align: "right",
              render: (m) => <span style={{ color: C.accent }}>{m.avgEnergy.toFixed(4)}</span>,
            },
            {
              key: "susy",
              header: "SUSY SCORE",
              align: "right",
              render: (m) => (
                <span style={{ color: C.secondary, fontWeight: "bold" }}>
                  {m.susyScore.toFixed(1)}
                </span>
              ),
            },
            {
              key: "power",
              header: "HASH POWER",
              align: "right",
              render: (m) => {
                const maxPower = sorted[0]?.hashPower ?? 1;
                const pct = (m.hashPower / maxPower) * 100;
                return (
                  <div className="flex items-center justify-end gap-2">
                    <div className="h-1 w-16 overflow-hidden rounded-full" style={{ background: `${C.border}40` }}>
                      <div className="h-full rounded-full" style={{ width: `${pct}%`, background: C.primary }} />
                    </div>
                    <span className="w-10 text-right text-[10px]" style={{ color: C.textMuted }}>
                      {m.hashPower.toFixed(1)}
                    </span>
                  </div>
                );
              },
            },
          ]}
          data={pageData}
          keyFn={(m) => m.address}
          onRowClick={(m) => navigate("wallet", { id: m.address })}
        />

        {totalPages > 1 && (
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        )}
      </Panel>
    </div>
  );
}
