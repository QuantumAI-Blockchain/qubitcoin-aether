"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Dashboard View
   ───────────────────────────────────────────────────────────────────────── */

import { motion } from "framer-motion";
import { Activity, Box, Cpu, Brain, Layers, Users, Zap, TrendingUp } from "lucide-react";
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from "recharts";
import {
  useNetworkStats,
  useRecentBlocks,
  useRecentTransactions,
  useMiners,
  usePhiHistory,
  useTpsHistory,
} from "./hooks";
import {
  C, FONT, StatCard, SectionHeader, DataTable, Badge,
  HashLink, Panel, LoadingSpinner, formatQBC, formatNumber, truncHash,
  txTypeColor, txTypeBadge, timeAgo,
} from "./shared";
import { HeartbeatMonitor } from "./HeartbeatMonitor";
import { useExplorerStore } from "./store";
import type { Block, Transaction, MinerStats } from "./types";

/* ── Mini chart tooltip ───────────────────────────────────────────────── */

function MiniTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.[0]) return null;
  return (
    <div
      className="rounded border px-2 py-1 text-[10px]"
      style={{ background: C.surface, borderColor: C.border, color: C.textPrimary, fontFamily: FONT.mono }}
    >
      {payload[0].value.toFixed(4)}
    </div>
  );
}

/* ── Dashboard ────────────────────────────────────────────────────────── */

export function Dashboard() {
  const navigate = useExplorerStore((s) => s.navigate);
  const { data: stats } = useNetworkStats();
  const { data: blocks } = useRecentBlocks(15);
  const { data: txs } = useRecentTransactions(60);
  const { data: miners } = useMiners();
  const { data: phiHistory } = usePhiHistory();
  const { data: tpsHistory } = useTpsHistory();

  if (!stats) return <LoadingSpinner />;

  const phiSlice = (phiHistory ?? []).slice(-100);
  const tpsSlice = (tpsHistory ?? []).slice(-100);
  const topMiners = (miners ?? []).slice(0, 5);

  return (
    <div className="space-y-4 p-4">
      {/* ── Stat Cards ──────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard
          label="Block Height"
          value={formatNumber(stats.blockHeight)}
          icon={Box}
          color={C.primary}
          onClick={() => navigate("block", { id: String(stats.blockHeight) })}
        />
        <StatCard
          label="TPS"
          value={stats.tps.toFixed(1)}
          sub={`${formatNumber(stats.totalTransactions)} total`}
          icon={Zap}
          color={C.success}
        />
        <StatCard
          label="Φ (Phi)"
          value={stats.phi.toFixed(4)}
          sub={stats.phi >= 3.0 ? "CONSCIOUS" : `${((stats.phi / 3.0) * 100).toFixed(0)}% to threshold`}
          icon={Brain}
          color={C.phi}
          onClick={() => navigate("aether")}
        />
        <StatCard
          label="Difficulty"
          value={stats.difficulty.toFixed(3)}
          icon={Activity}
          color={C.secondary}
        />
        <StatCard
          label="Supply"
          value={formatQBC(stats.totalSupply)}
          sub={`of 3.3B max`}
          icon={Layers}
          color={C.primary}
        />
        <StatCard
          label="Contracts"
          value={formatNumber(stats.totalContracts)}
          sub={`${formatNumber(stats.totalAddresses)} addresses`}
          icon={Cpu}
          color={C.accent}
          onClick={() => navigate("qvm")}
        />
      </div>

      {/* ── Heartbeat Monitor ───────────────────────────────────── */}
      <HeartbeatMonitor
        transactions={txs ?? []}
        height={130}
        blockHeight={stats.blockHeight}
        blockTime={stats.avgBlockTime}
      />

      {/* ── Charts Row ──────────────────────────────────────────── */}
      <div className="grid gap-3 lg:grid-cols-2">
        {/* Phi History */}
        <Panel>
          <SectionHeader title="Φ PROGRESSION" />
          <div style={{ height: 160 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={phiSlice}>
                <defs>
                  <linearGradient id="phiGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.phi} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={C.phi} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={`${C.border}40`} />
                <XAxis
                  dataKey="block"
                  tick={{ fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono }}
                  axisLine={{ stroke: C.border }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono }}
                  axisLine={{ stroke: C.border }}
                  tickLine={false}
                  width={35}
                />
                <Tooltip content={<MiniTooltip />} />
                <Area
                  type="monotone"
                  dataKey="phi"
                  stroke={C.phi}
                  fill="url(#phiGrad)"
                  strokeWidth={1.5}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* TPS History */}
        <Panel>
          <SectionHeader title="THROUGHPUT (TPS)" />
          <div style={{ height: 160 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={tpsSlice}>
                <defs>
                  <linearGradient id="tpsGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.success} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={C.success} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={`${C.border}40`} />
                <XAxis
                  dataKey="block"
                  tick={{ fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono }}
                  axisLine={{ stroke: C.border }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono }}
                  axisLine={{ stroke: C.border }}
                  tickLine={false}
                  width={35}
                />
                <Tooltip content={<MiniTooltip />} />
                <Area
                  type="monotone"
                  dataKey="tps"
                  stroke={C.success}
                  fill="url(#tpsGrad)"
                  strokeWidth={1.5}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      {/* ── Recent Blocks + Transactions ────────────────────────── */}
      <div className="grid gap-3 lg:grid-cols-2">
        {/* Recent Blocks */}
        <Panel>
          <SectionHeader
            title="RECENT BLOCKS"
            action={
              <button
                onClick={() => navigate("metrics")}
                className="text-[10px] transition-opacity hover:opacity-80"
                style={{ color: C.primary, fontFamily: FONT.heading }}
              >
                VIEW ALL →
              </button>
            }
          />
          <DataTable<Block>
            columns={[
              {
                key: "height",
                header: "HEIGHT",
                width: "70px",
                render: (b) => (
                  <HashLink hash={String(b.height)} type="block" truncLen={10} />
                ),
              },
              {
                key: "miner",
                header: "MINER",
                render: (b) => (
                  <span style={{ color: C.textSecondary, fontFamily: FONT.mono, fontSize: "0.65rem" }}>
                    {truncHash(b.miner, 6)}
                  </span>
                ),
              },
              {
                key: "txs",
                header: "TXS",
                align: "right",
                width: "50px",
                render: (b) => <span style={{ color: C.textPrimary }}>{b.txCount}</span>,
              },
              {
                key: "reward",
                header: "REWARD",
                align: "right",
                render: (b) => (
                  <span style={{ color: C.success }}>{b.reward.toFixed(2)}</span>
                ),
              },
              {
                key: "energy",
                header: "ENERGY",
                align: "right",
                render: (b) => (
                  <span style={{ color: C.accent }}>{b.energy.toFixed(4)}</span>
                ),
              },
            ]}
            data={blocks ?? []}
            keyFn={(b) => String(b.height)}
            onRowClick={(b) => navigate("block", { id: String(b.height) })}
            rowAriaLabel={(b) => `Block ${b.height}, ${b.txCount} transactions, reward ${b.reward.toFixed(2)} QBC`}
          />
        </Panel>

        {/* Recent Transactions */}
        <Panel>
          <SectionHeader title="RECENT TRANSACTIONS" />
          <DataTable<Transaction>
            columns={[
              {
                key: "txid",
                header: "TXID",
                render: (t) => <HashLink hash={t.txid} type="transaction" truncLen={6} />,
              },
              {
                key: "type",
                header: "TYPE",
                render: (t) => <Badge label={txTypeBadge(t.type)} color={txTypeColor(t.type)} />,
              },
              {
                key: "value",
                header: "VALUE",
                align: "right",
                render: (t) => (
                  <span style={{ color: t.isPrivate ? C.susy : C.textPrimary, fontFamily: FONT.mono }}>
                    {t.isPrivate ? "HIDDEN" : formatQBC(t.value)}
                  </span>
                ),
              },
              {
                key: "block",
                header: "BLOCK",
                align: "right",
                width: "60px",
                render: (t) => (
                  <span style={{ color: C.textSecondary }}>{t.blockHeight}</span>
                ),
              },
            ]}
            data={(txs ?? []).slice(0, 15)}
            keyFn={(t) => t.txid}
            onRowClick={(t) => navigate("transaction", { id: t.txid })}
          />
        </Panel>
      </div>

      {/* ── Top Miners Preview ──────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="TOP MINERS"
          action={
            <button
              onClick={() => navigate("leaderboard")}
              className="text-[10px] transition-opacity hover:opacity-80"
              style={{ color: C.primary, fontFamily: FONT.heading }}
            >
              FULL LEADERBOARD →
            </button>
          }
        />
        <DataTable<MinerStats>
          columns={[
            {
              key: "rank",
              header: "#",
              width: "40px",
              render: (m) => (
                <span style={{ color: m.rank <= 3 ? C.accent : C.textSecondary, fontWeight: m.rank <= 3 ? "bold" : "normal" }}>
                  {m.rank}
                </span>
              ),
            },
            {
              key: "address",
              header: "ADDRESS",
              render: (m) => <HashLink hash={m.address} type="wallet" truncLen={8} />,
            },
            {
              key: "blocks",
              header: "BLOCKS",
              align: "right",
              render: (m) => <span style={{ color: C.textPrimary }}>{m.blocksMined}</span>,
            },
            {
              key: "rewards",
              header: "REWARDS",
              align: "right",
              render: (m) => <span style={{ color: C.success }}>{formatQBC(m.totalRewards)}</span>,
            },
            {
              key: "susy",
              header: "SUSY SCORE",
              align: "right",
              render: (m) => (
                <span style={{ color: C.secondary }}>{m.susyScore.toFixed(1)}</span>
              ),
            },
          ]}
          data={topMiners}
          keyFn={(m) => m.address}
          onRowClick={(m) => navigate("wallet", { id: m.address })}
        />
      </Panel>
    </div>
  );
}
