"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Metrics Dashboard
   ───────────────────────────────────────────────────────────────────────── */

import { motion } from "framer-motion";
import { BarChart3, Box, Zap, TrendingUp, Activity, Database } from "lucide-react";
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import {
  useNetworkStats, usePhiHistory, useTpsHistory,
  useDifficultyHistory, useRecentBlocks,
} from "./hooks";
import {
  C, FONT, LoadingSpinner, Panel, SectionHeader, StatCard, formatNumber, formatQBC,
} from "./shared";

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { name: string; value: number; color: string }[] }) {
  if (!active || !payload?.[0]) return null;
  return (
    <div
      className="rounded border px-2 py-1.5"
      style={{ background: C.surface, borderColor: C.border, fontFamily: FONT.mono }}
    >
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 text-[10px]">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: p.color }} />
          <span style={{ color: C.textMuted }}>{p.name}:</span>
          <span style={{ color: C.textPrimary }}>{p.value.toFixed(4)}</span>
        </div>
      ))}
    </div>
  );
}

export function MetricsDashboard() {
  const { data: stats } = useNetworkStats();
  const { data: phiHistory } = usePhiHistory();
  const { data: tpsHistory } = useTpsHistory();
  const { data: diffHistory } = useDifficultyHistory();
  const { data: blocks } = useRecentBlocks(200);

  if (!stats) return <LoadingSpinner />;

  const phiSlice = (phiHistory ?? []).slice(-200);
  const tpsSlice = (tpsHistory ?? []).slice(-200);
  const diffSlice = (diffHistory ?? []).slice(-200);

  // Block tx count for bar chart (L1 has no gas metering — show tx throughput)
  const blockTxData = (blocks ?? []).slice(0, 100)
    .sort((a, b) => a.height - b.height)
    .map((b) => ({
      height: b.height,
      txCount: b.txCount,
      size: b.size,
    }));

  // Energy vs difficulty — use all available blocks sorted by height
  const energyData = (blocks ?? [])
    .sort((a, b) => a.height - b.height)
    .map((b) => ({
      height: b.height,
      energy: b.energy,
      difficulty: b.difficulty,
    }));

  return (
    <div className="space-y-4 p-4">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <h1
          className="mb-1 text-lg font-bold tracking-widest"
          style={{ color: C.textPrimary, fontFamily: FONT.heading }}
        >
          NETWORK METRICS
        </h1>
        <p className="text-xs" style={{ color: C.textSecondary, fontFamily: FONT.body }}>
          Real-time blockchain analytics and performance data
        </p>
      </motion.div>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Block Height" value={formatNumber(stats.blockHeight)} icon={Box} color={C.primary} />
        <StatCard label="Avg Block Time" value={`${stats.avgBlockTime.toFixed(1)}s`} icon={Activity} color={C.success} />
        <StatCard label="TPS" value={stats.tps.toFixed(1)} icon={Zap} color={C.accent} />
        <StatCard label="Total Supply" value={formatQBC(stats.totalSupply)} icon={Database} color={C.primary} />
        <StatCard label="Mempool" value={formatNumber(stats.mempool)} icon={BarChart3} color={C.warning} />
        <StatCard label="Peers" value={formatNumber(stats.peers)} icon={TrendingUp} color={C.secondary} />
      </div>

      {/* Charts Grid */}
      <div className="grid gap-3 lg:grid-cols-2">
        {/* TPS */}
        <Panel>
          <SectionHeader title="THROUGHPUT (TPS)" />
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={tpsSlice}>
                <defs>
                  <linearGradient id="tpsG" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.success} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={C.success} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={`${C.border}40`} />
                <XAxis dataKey="block" tick={{ fontSize: 9, fill: C.textMuted }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: C.textMuted }} axisLine={false} tickLine={false} width={30} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="tps" stroke={C.success} fill="url(#tpsG)" strokeWidth={1.5} dot={false} name="TPS" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* Phi */}
        <Panel>
          <SectionHeader title="Φ CONSCIOUSNESS METRIC" />
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={phiSlice}>
                <defs>
                  <linearGradient id="phiG" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.phi} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={C.phi} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={`${C.border}40`} />
                <XAxis dataKey="block" tick={{ fontSize: 9, fill: C.textMuted }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: C.textMuted }} axisLine={false} tickLine={false} width={30} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="phi" stroke={C.phi} fill="url(#phiG)" strokeWidth={1.5} dot={false} name="Phi" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* Difficulty */}
        <Panel>
          <SectionHeader title="DIFFICULTY" />
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={diffSlice}>
                <CartesianGrid stroke={`${C.border}40`} />
                <XAxis dataKey="block" tick={{ fontSize: 9, fill: C.textMuted }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: C.textMuted }} axisLine={false} tickLine={false} width={30} />
                <Tooltip content={<ChartTooltip />} />
                <Line type="monotone" dataKey="difficulty" stroke={C.secondary} strokeWidth={1.5} dot={false} name="Difficulty" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* VQE Energy vs Difficulty */}
        <Panel>
          <SectionHeader title="VQE ENERGY vs DIFFICULTY" />
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={energyData}>
                <CartesianGrid stroke={`${C.border}40`} />
                <XAxis dataKey="height" tick={{ fontSize: 9, fill: C.textMuted }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: C.textMuted }} axisLine={false} tickLine={false} width={30} />
                <Tooltip content={<ChartTooltip />} />
                <Line type="monotone" dataKey="energy" stroke={C.accent} strokeWidth={1} dot={false} name="Energy" />
                <Line type="monotone" dataKey="difficulty" stroke={C.secondary} strokeWidth={1} dot={false} name="Difficulty" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* Block Tx Count */}
        <Panel className="lg:col-span-2">
          <SectionHeader title="TRANSACTIONS PER BLOCK" />
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={blockTxData}>
                <CartesianGrid stroke={`${C.border}40`} />
                <XAxis dataKey="height" tick={{ fontSize: 9, fill: C.textMuted }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: C.textMuted }} axisLine={false} tickLine={false} width={30} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="txCount" fill={C.primary} radius={[2, 2, 0, 0]} name="Tx Count" opacity={0.7} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>
    </div>
  );
}
