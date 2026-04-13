"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { api, type AetherInfo, type AetherEngineHealth, type AetherEngineInfo, type ConversationStats } from "@/lib/api";
import { exportData, type ExportFormat } from "@/lib/export";
import { Card } from "@/components/ui/card";
import { PhiSpinner } from "@/components/ui/loading";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { PhiChart } from "@/components/dashboard/phi-chart";
import { MiningControls } from "@/components/dashboard/mining-controls";
import { QUSDReserveGauge, QUSDMilestoneTimeline } from "@/components/dashboard/qusd-reserve";
import { MilestoneGates } from "@/components/dashboard/milestone-gates";
import { SephirotExplorer } from "@/components/dashboard/sephirot-explorer";
import { FinalityStatus } from "@/components/dashboard/finality-status";
import { StratumStats } from "@/components/dashboard/stratum-stats";
import { useWalletStore } from "@/stores/wallet-store";

function formatSupply(supply: number): string {
  if (supply >= 1e9) return `${(supply / 1e9).toFixed(2)}B QBC`;
  if (supply >= 1e6) return `${(supply / 1e6).toFixed(2)}M QBC`;
  if (supply >= 1e3) return `${(supply / 1e3).toFixed(2)}K QBC`;
  return `${supply.toFixed(2)} QBC`;
}

function formatDifficulty(d: number): string {
  if (d >= 1000) return d.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (d >= 10) return d.toFixed(4);
  return d.toFixed(6);
}

const TABS = ["Overview", "Mining", "Contracts", "Wallet", "Aether", "Network"] as const;
type Tab = (typeof TABS)[number];

export default function DashboardPage() {
  const [tab, setTab] = useState<Tab>("Overview");
  const { address, connected } = useWalletStore();

  const { data: chain, isLoading: chainLoading } = useQuery({
    queryKey: ["chainInfo"],
    queryFn: api.getChainInfo,
    refetchInterval: 6_600,
  });

  const { data: mining } = useQuery({
    queryKey: ["miningStats"],
    queryFn: api.getMiningStats,
    refetchInterval: 10_000,
  });

  const { data: phi } = useQuery({
    queryKey: ["phi"],
    queryFn: api.getPhi,
    refetchInterval: 10_000,
  });

  const { data: balanceData } = useQuery({
    queryKey: ["balance", address],
    queryFn: () => api.getBalance(address!),
    enabled: !!address,
    refetchInterval: 10_000,
  });

  const parsedBalance = balanceData?.balance ? parseFloat(balanceData.balance) : undefined;

  if (chainLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center pt-16">
        <PhiSpinner />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 pt-20 pb-12">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold glow-cyan">
        Dashboard
      </h1>
      <p className="mt-1 font-[family-name:var(--font-display)] text-[10px] uppercase tracking-[0.3em] text-text-secondary">
        Command Center
      </p>

      {/* Tabs */}
      <div className="mt-6 flex gap-1 border-b border-border-subtle">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`relative px-4 py-2 font-[family-name:var(--font-display)] text-[11px] uppercase tracking-widest transition-colors ${
              tab === t ? "glow-cyan" : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {t}
            {tab === t && (
              <motion.span
                layoutId="dashboard-tab"
                className="absolute inset-x-0 -bottom-[1px] h-0.5 bg-glow-cyan"
                style={{ boxShadow: "0 0 8px rgba(0,212,255,0.5)" }}
              />
            )}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {tab === "Overview" && (
          <OverviewTab chain={chain} phi={phi} balance={parsedBalance} connected={connected} />
        )}
        {tab === "Mining" && <MiningTab mining={mining} chain={chain} />}
        {tab === "Contracts" && <ContractsTab />}
        {tab === "Wallet" && <WalletTab address={address} connected={connected} />}
        {tab === "Aether" && <AetherTab phi={phi} />}
        {tab === "Network" && <NetworkTab chain={chain} />}
      </div>
    </div>
  );
}

/* --- Export Button --- */

function ExportButton({
  getData,
  filenameBase,
  columns,
}: {
  getData: () => Record<string, unknown>[];
  filenameBase: string;
  columns?: string[];
}) {
  const [open, setOpen] = useState(false);
  const handleExport = (format: ExportFormat) => {
    const data = getData();
    if (data.length === 0) return;
    exportData(data, filenameBase, format, columns);
    setOpen(false);
  };
  return (
    <div className="relative inline-block">
      <button
        onClick={() => setOpen(!open)}
        className="rounded-lg border border-border-subtle px-3 py-1.5 text-xs text-text-secondary transition hover:border-quantum-green hover:text-quantum-green"
      >
        Export
      </button>
      {open && (
        <div className="absolute right-0 z-10 mt-1 rounded-lg border border-border-subtle bg-bg-panel p-1 shadow-lg">
          <button
            onClick={() => handleExport("csv")}
            className="block w-full rounded px-4 py-1.5 text-left text-xs text-text-secondary hover:bg-quantum-green/10 hover:text-quantum-green"
          >
            CSV
          </button>
          <button
            onClick={() => handleExport("json")}
            className="block w-full rounded px-4 py-1.5 text-left text-xs text-text-secondary hover:bg-quantum-green/10 hover:text-quantum-green"
          >
            JSON
          </button>
        </div>
      )}
    </div>
  );
}

/* --- Tab Components --- */

function OverviewTab({
  chain,
  phi,
  balance,
  connected,
}: {
  chain: ReturnType<typeof api.getChainInfo> extends Promise<infer T> ? T | undefined : never;
  phi: ReturnType<typeof api.getPhi> extends Promise<infer T> ? T | undefined : never;
  balance: number | undefined;
  connected: boolean;
}) {
  const gatesPassed = phi?.gates_passed ?? 0;
  const gatesTotal = phi?.gates_total ?? 10;

  const stats = [
    { label: "Block Height", value: chain?.height?.toLocaleString() ?? "---" },
    { label: "Circulating Supply", value: chain?.total_supply != null ? formatSupply(chain.total_supply) : "---" },
    { label: "Difficulty", value: chain?.difficulty != null ? formatDifficulty(chain.difficulty) : "---" },
    { label: "Mempool", value: chain?.mempool_size?.toString() ?? "---" },
    { label: "HMS-Phi (\u03A6)", value: phi?.phi?.toFixed(4) ?? "---" },
    { label: "Knowledge Nodes", value: phi?.knowledge_nodes?.toLocaleString() ?? "---" },
    { label: "AGI Gates", value: `${gatesPassed}/${gatesTotal}` },
  ];

  return (
    <div className="space-y-6">
      {connected && (
        <Card glow="green">
          <p className="text-sm text-text-secondary">Your Balance</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-2xl font-bold text-quantum-green">
            {balance != null ? balance.toLocaleString() : "---"} QBC
          </p>
        </Card>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {stats.map(({ label, value }) => (
          <Card key={label}>
            <p className="text-xs text-text-secondary">{label}</p>
            <p className="mt-1 font-[family-name:var(--font-code)] text-xl font-semibold">
              {value}
            </p>
          </Card>
        ))}
      </div>

      {/* QUSD Reserve Status */}
      <div className="grid gap-4 sm:grid-cols-2">
        <ErrorBoundary>
          <QUSDReserveGauge />
        </ErrorBoundary>
        <ErrorBoundary>
          <QUSDMilestoneTimeline />
        </ErrorBoundary>
      </div>

      {/* Finality & Stratum */}
      <div className="grid gap-4 sm:grid-cols-2">
        <ErrorBoundary>
          <FinalityStatus />
        </ErrorBoundary>
        <ErrorBoundary>
          <StratumStats />
        </ErrorBoundary>
      </div>
    </div>
  );
}

function MiningTab({
  mining,
  chain,
}: {
  mining: ReturnType<typeof api.getMiningStats> extends Promise<infer T> ? T | undefined : never;
  chain: ReturnType<typeof api.getChainInfo> extends Promise<infer T> ? T | undefined : never;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <ErrorBoundary>
          <MiningControls isActive={mining?.is_mining ?? false} />
        </ErrorBoundary>
        <ExportButton
          filenameBase="mining_stats"
          getData={() =>
            mining
              ? [
                  {
                    is_mining: mining.is_mining,
                    blocks_found: mining.blocks_found,
                    total_attempts: mining.total_attempts,
                    success_rate: mining.success_rate,
                    best_energy: mining.best_energy,
                    alignment_score: mining.alignment_score,
                    difficulty: chain?.difficulty,
                    block_height: chain?.height,
                    exported_at: new Date().toISOString(),
                  },
                ]
              : []
          }
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">Mining Status</h3>
          <p className="text-lg font-semibold">
            {mining?.is_mining ? (
              <span className="text-quantum-green">Active</span>
            ) : (
              <span className="text-text-secondary">Offline</span>
            )}
          </p>
          <p className="mt-2 text-xs text-text-secondary">
            Difficulty: {chain?.difficulty?.toFixed(6) ?? "---"}
          </p>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">Blocks Found</h3>
          <p className="font-[family-name:var(--font-code)] text-2xl font-bold">
            {mining?.blocks_found?.toLocaleString() ?? "---"}
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            Attempts: {mining?.total_attempts?.toLocaleString() ?? "---"}
          </p>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">Success Rate</h3>
          <p className="font-[family-name:var(--font-code)] text-lg">
            {mining?.success_rate != null ? `${(mining.success_rate * 100).toFixed(2)}%` : "---"}
          </p>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">VQE Energy</h3>
          <p className="font-[family-name:var(--font-code)] text-lg">
            {mining?.best_energy != null ? mining.best_energy.toFixed(6) : "---"}
          </p>
        </Card>
      </div>
    </div>
  );
}

function AetherTab({
  phi,
}: {
  phi: ReturnType<typeof api.getPhi> extends Promise<infer T> ? T | undefined : never;
}) {
  const pct = phi ? Math.min((phi.phi / phi.threshold) * 100, 100) : 0;
  const isV2 = (phi?.phi_version ?? 0) >= 2;

  const { data: aetherInfo } = useQuery({
    queryKey: ["aetherInfo"],
    queryFn: api.getAetherInfo,
    refetchInterval: 15_000,
    retry: false,
  });

  return (
    <div className="space-y-6">
      <Card glow="violet">
        <h3 className="mb-3 font-[family-name:var(--font-display)] text-lg font-semibold">
          Integration Status
        </h3>
        <div className="flex items-end gap-4">
          <p className="font-[family-name:var(--font-code)] text-4xl font-bold text-quantum-green">
            {phi?.phi?.toFixed(4) ?? "0.0000"}
          </p>
          <p className="mb-1 text-sm text-text-secondary">
            / {phi?.threshold?.toFixed(1) ?? "3.0"} threshold ({pct.toFixed(1)}%)
          </p>
        </div>
        {isV2 && phi?.phi_raw != null && (
          <p className="mt-1 text-xs text-text-secondary">
            Raw: {phi.phi_raw.toFixed(4)} | Ceiling: {phi.gate_ceiling?.toFixed(1) ?? "---"}
            {phi.convergence_stddev != null && ` | Convergence: ${phi.convergence_stddev.toFixed(4)}`}
            {phi.convergence_status != null && ` | Status: ${phi.convergence_status}`}
          </p>
        )}
        <div className="mt-4 h-3 w-full overflow-hidden rounded-full bg-bg-deep">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-quantum-violet to-quantum-green"
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 1.5 }}
          />
        </div>
      </Card>

      {/* Milestone Gates (v2+) */}
      {isV2 && phi?.gates && phi.gates.length > 0 && (
        <MilestoneGates
          gates={phi.gates}
          gatesPassed={phi.gates_passed ?? 0}
          gatesTotal={phi.gates_total ?? 10}
          gateCeiling={phi.gate_ceiling ?? 0}
          phiRaw={phi.phi_raw ?? phi.phi}
        />
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <p className="text-xs text-text-secondary">Knowledge Nodes</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-xl font-semibold">
            {phi?.knowledge_nodes?.toLocaleString() ?? "---"}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Knowledge Edges</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-xl font-semibold">
            {phi?.knowledge_edges?.toLocaleString() ?? "---"}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Integration</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-xl font-semibold">
            {phi?.integration?.toFixed(4) ?? "---"}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Differentiation</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-xl font-semibold">
            {phi?.differentiation?.toFixed(4) ?? "---"}
          </p>
        </Card>
      </div>

      {/* AGI Reasoning Subsystems */}
      {aetherInfo && <AGISubsystemsPanel info={aetherInfo} />}

      {/* Conversation Memory + Graph Shard Stats */}
      <div className="grid gap-4 sm:grid-cols-2">
        <ConversationMemoryCard />
        <GraphShardCard />
      </div>

      {/* Rust Aether Engine Stats */}
      <AetherEnginePanel />

      <ErrorBoundary>
        <SephirotExplorer />
      </ErrorBoundary>

      <ErrorBoundary>
        <PhiChart />
      </ErrorBoundary>
    </div>
  );
}

function AetherEnginePanel() {
  const { data: health } = useQuery({
    queryKey: ["aetherEngineHealth"],
    queryFn: api.getAetherHealth,
    refetchInterval: 10_000,
    retry: false,
  });

  const { data: info } = useQuery({
    queryKey: ["aetherEngineInfo"],
    queryFn: api.getAetherEngineInfo,
    refetchInterval: 10_000,
    retry: false,
  });

  if (!health && !info) return null;

  const uptime = health?.uptime_seconds ?? 0;
  const uptimeStr =
    uptime >= 3600
      ? `${Math.floor(uptime / 3600)}h ${Math.floor((uptime % 3600) / 60)}m`
      : uptime >= 60
        ? `${Math.floor(uptime / 60)}m ${uptime % 60}s`
        : `${uptime}s`;

  const cacheHitRate = info?.cache_stats?.hit_rate ?? 0;

  return (
    <Card>
      <h3 className="mb-4 font-[family-name:var(--font-display)] text-lg font-semibold">
        Aether Engine
        <span className="ml-2 text-xs font-normal text-quantum-green">Rust</span>
      </h3>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-3">
          <p className="text-xs text-text-secondary">Status</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-sm font-semibold">
            {health?.status === "ok" ? (
              <span className="text-quantum-green">Online</span>
            ) : (
              <span className="text-red-400">Offline</span>
            )}
          </p>
        </div>
        <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-3">
          <p className="text-xs text-text-secondary">Inference</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-sm font-semibold">
            {info?.inference_backend ?? health?.engines?.inference ?? "---"}
          </p>
        </div>
        <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-3">
          <p className="text-xs text-text-secondary">Uptime</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-sm font-semibold">
            {uptimeStr}
          </p>
        </div>
        <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-3">
          <p className="text-xs text-text-secondary">Cache Hit Rate</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-sm font-semibold">
            {(cacheHitRate * 100).toFixed(1)}%
          </p>
        </div>
        <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-3">
          <p className="text-xs text-text-secondary">Nodes / Edges</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-sm font-semibold">
            {(info?.node_count ?? 0).toLocaleString()} / {(info?.edge_count ?? 0).toLocaleString()}
          </p>
        </div>
        <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-3">
          <p className="text-xs text-text-secondary">Search Index</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-sm font-semibold">
            {(info?.search_index?.indexed_nodes ?? 0).toLocaleString()} nodes
          </p>
        </div>
        <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-3">
          <p className="text-xs text-text-secondary">Gates Passed</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-sm font-semibold text-quantum-green">
            {info?.gates_passed?.length ?? 0} / 10
          </p>
        </div>
      </div>
      {info?.emotional_state && Object.keys(info.emotional_state).length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs text-text-secondary">Emotional State</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(info.emotional_state)
              .sort(([, a], [, b]) => (b as number) - (a as number))
              .map(([emotion, value]) => (
                <span
                  key={emotion}
                  className="rounded-full border border-border-subtle bg-bg-deep/50 px-2 py-0.5 text-xs"
                  title={`${emotion}: ${((value as number) * 100).toFixed(0)}%`}
                >
                  {emotion}{" "}
                  <span className="font-[family-name:var(--font-code)] text-quantum-green">
                    {((value as number) * 100).toFixed(0)}%
                  </span>
                </span>
              ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function AGISubsystemsPanel({ info }: { info: AetherInfo }) {
  const hasAny =
    info.neural_reasoner || info.causal_engine || info.debate_protocol ||
    info.temporal_engine || info.concept_formation || info.metacognition ||
    info.self_improvement;

  if (!hasAny) return null;

  return (
    <Card>
      <h3 className="mb-4 font-[family-name:var(--font-display)] text-lg font-semibold">
        AGI Reasoning Subsystems
      </h3>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {info.neural_reasoner && (
          <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-4">
            <p className="text-xs font-semibold text-quantum-violet">Neural Reasoner</p>
            <div className="mt-2 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">Accuracy</span>
                <span className="font-[family-name:var(--font-code)]">
                  {(info.neural_reasoner.accuracy * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Predictions</span>
                <span className="font-[family-name:var(--font-code)]">
                  {info.neural_reasoner.total_predictions.toLocaleString()}
                </span>
              </div>
            </div>
          </div>
        )}

        {info.causal_engine && (
          <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-4">
            <p className="text-xs font-semibold text-quantum-violet">Causal Engine</p>
            <div className="mt-2 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">Causal Edges</span>
                <span className="font-[family-name:var(--font-code)]">
                  {info.causal_engine.total_causal_edges_found.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Runs</span>
                <span className="font-[family-name:var(--font-code)]">
                  {info.causal_engine.total_runs.toLocaleString()}
                </span>
              </div>
            </div>
          </div>
        )}

        {info.debate_protocol && (
          <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-4">
            <p className="text-xs font-semibold text-quantum-violet">Debate Protocol</p>
            <div className="mt-2 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">Debates</span>
                <span className="font-[family-name:var(--font-code)]">
                  {info.debate_protocol.total_debates.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Acceptance</span>
                <span className="font-[family-name:var(--font-code)]">
                  {(info.debate_protocol.acceptance_rate * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between text-xs text-text-secondary">
                <span>{info.debate_protocol.accepted}A / {info.debate_protocol.rejected}R / {info.debate_protocol.modified}M</span>
              </div>
            </div>
          </div>
        )}

        {info.temporal_engine && (
          <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-4">
            <p className="text-xs font-semibold text-quantum-violet">Temporal Engine</p>
            <div className="mt-2 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">Tracked</span>
                <span className="font-[family-name:var(--font-code)]">
                  {info.temporal_engine.tracked_metrics} metrics
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Predictions</span>
                <span className="font-[family-name:var(--font-code)]">
                  {info.temporal_engine.predictions_validated.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Accuracy</span>
                <span className="font-[family-name:var(--font-code)]">
                  {(info.temporal_engine.accuracy * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        )}

        {info.concept_formation && (
          <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-4">
            <p className="text-xs font-semibold text-quantum-violet">Concept Formation</p>
            <div className="mt-2 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">Concepts</span>
                <span className="font-[family-name:var(--font-code)]">
                  {info.concept_formation.total_concepts_created.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Runs</span>
                <span className="font-[family-name:var(--font-code)]">
                  {info.concept_formation.total_runs.toLocaleString()}
                </span>
              </div>
            </div>
          </div>
        )}

        {info.metacognition && (
          <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-4">
            <p className="text-xs font-semibold text-quantum-violet">Metacognition</p>
            <div className="mt-2 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">Accuracy</span>
                <span className="font-[family-name:var(--font-code)]">
                  {(info.metacognition.overall_accuracy * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Calibration Err</span>
                <span className="font-[family-name:var(--font-code)]">
                  {info.metacognition.calibration_error.toFixed(4)}
                </span>
              </div>
              {Object.keys(info.metacognition.strategy_weights).length > 0 && (
                <div className="mt-1 border-t border-border-subtle/50 pt-1">
                  <p className="text-xs text-text-secondary">Strategy Weights</p>
                  {Object.entries(info.metacognition.strategy_weights).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs">
                      <span className="text-text-secondary">{k}</span>
                      <span className="font-[family-name:var(--font-code)]">{v.toFixed(3)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {info.self_improvement && (
          <div className="rounded-lg border border-border-subtle bg-bg-deep/50 p-4">
            <p className="text-xs font-semibold text-quantum-green">Self-Improvement</p>
            <div className="mt-2 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">Cycles</span>
                <span className="font-[family-name:var(--font-code)]">
                  {info.self_improvement.cycles_completed.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Adjustments</span>
                <span className="font-[family-name:var(--font-code)]">
                  {info.self_improvement.total_adjustments.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Perf Delta</span>
                <span className={`font-[family-name:var(--font-code)] ${
                  (info.self_improvement.performance_delta ?? 0) > 0
                    ? "text-quantum-green"
                    : (info.self_improvement.performance_delta ?? 0) < 0
                      ? "text-red-400"
                      : ""
                }`}>
                  {((info.self_improvement.performance_delta ?? 0) * 100).toFixed(2)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Rollbacks</span>
                <span className="font-[family-name:var(--font-code)]">
                  {(info.self_improvement.rollbacks ?? 0).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Diversity</span>
                <span className="font-[family-name:var(--font-code)]">
                  {(info.self_improvement.diversity_score * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Domains</span>
                <span className="font-[family-name:var(--font-code)]">
                  {info.self_improvement.domains_tracked}
                </span>
              </div>
              {Object.keys(info.self_improvement.average_weights).length > 0 && (
                <div className="mt-1 border-t border-border-subtle/50 pt-1">
                  <p className="text-xs text-text-secondary">Strategy Weights</p>
                  {Object.entries(info.self_improvement.average_weights).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs">
                      <span className="text-text-secondary">{k}</span>
                      <span className="font-[family-name:var(--font-code)]">{v.toFixed(3)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

function ConversationMemoryCard() {
  const { data: stats } = useQuery({
    queryKey: ["conversationStats"],
    queryFn: api.getConversationStats,
    refetchInterval: 30_000,
    retry: false,
  });

  return (
    <Card>
      <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-semibold text-text-secondary">
        Conversation Memory
      </h3>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-text-secondary">Total Sessions</span>
          <span className="font-[family-name:var(--font-code)]">
            {stats?.total_sessions?.toLocaleString() ?? "---"}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-secondary">Active Sessions</span>
          <span className="font-[family-name:var(--font-code)] text-quantum-green">
            {stats?.active_sessions?.toLocaleString() ?? "---"}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-secondary">Total Messages</span>
          <span className="font-[family-name:var(--font-code)]">
            {stats?.total_messages?.toLocaleString() ?? "---"}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-secondary">Unique Users</span>
          <span className="font-[family-name:var(--font-code)]">
            {stats?.unique_users?.toLocaleString() ?? "---"}
          </span>
        </div>
        <div className="mt-2 border-t border-border-subtle/50 pt-2">
          <div className="flex justify-between">
            <span className="text-text-secondary">User Memories</span>
            <span className="font-[family-name:var(--font-code)] text-quantum-violet">
              {stats?.total_user_memories?.toLocaleString() ?? "---"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-secondary">Insights</span>
            <span className="font-[family-name:var(--font-code)] text-quantum-violet">
              {stats?.total_insights?.toLocaleString() ?? "---"}
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}

function GraphShardCard() {
  const { data: aetherEngineInfo } = useQuery({
    queryKey: ["aetherEngineInfo"],
    queryFn: api.getAetherEngineInfo,
    refetchInterval: 15_000,
    retry: false,
  });

  const { data: phi } = useQuery({
    queryKey: ["phi"],
    queryFn: api.getPhi,
    refetchInterval: 10_000,
  });

  const nodeCount = aetherEngineInfo?.node_count ?? 0;
  const edgeCount = aetherEngineInfo?.edge_count ?? 0;
  const kgNodes = phi?.knowledge_nodes ?? 0;
  const gatesPassed = phi?.gates_passed ?? 0;
  const gatesTotal = phi?.gates_total ?? 10;

  return (
    <Card>
      <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-semibold text-text-secondary">
        Graph Shard / AGI Status
      </h3>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-text-secondary">KG Nodes (in-memory)</span>
          <span className="font-[family-name:var(--font-code)]">
            {kgNodes.toLocaleString()}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-secondary">Shard Nodes (Rust)</span>
          <span className="font-[family-name:var(--font-code)] text-quantum-green">
            {nodeCount > 0 ? nodeCount.toLocaleString() : "---"}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-secondary">Shard Edges</span>
          <span className="font-[family-name:var(--font-code)]">
            {edgeCount > 0 ? edgeCount.toLocaleString() : "---"}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-secondary">Search Index</span>
          <span className="font-[family-name:var(--font-code)]">
            {(aetherEngineInfo?.search_index?.indexed_nodes ?? 0).toLocaleString()} nodes
          </span>
        </div>
        <div className="mt-2 border-t border-border-subtle/50 pt-2">
          <div className="flex justify-between">
            <span className="text-text-secondary">Gates Passed</span>
            <span className="font-[family-name:var(--font-code)] text-quantum-violet">
              {gatesPassed}/{gatesTotal}
            </span>
          </div>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-bg-deep">
            <div
              className="h-full rounded-full bg-gradient-to-r from-quantum-violet to-quantum-green transition-all duration-700"
              style={{ width: `${(gatesPassed / Math.max(gatesTotal, 1)) * 100}%` }}
            />
          </div>
          {phi?.phi != null && (
            <div className="mt-2 flex justify-between">
              <span className="text-text-secondary">HMS-Phi</span>
              <span className="font-[family-name:var(--font-code)] text-quantum-green">
                {phi.phi.toFixed(4)}
              </span>
            </div>
          )}
          {(phi?.phi_micro != null || phi?.phi_meso != null || phi?.phi_macro != null) && (
            <div className="mt-1 space-y-1">
              {phi?.phi_micro != null && (
                <div className="flex justify-between text-xs">
                  <span className="text-text-secondary">Micro (IIT)</span>
                  <span className="font-[family-name:var(--font-code)]">{phi.phi_micro.toFixed(4)}</span>
                </div>
              )}
              {phi?.phi_meso != null && (
                <div className="flex justify-between text-xs">
                  <span className="text-text-secondary">Meso (Domain)</span>
                  <span className="font-[family-name:var(--font-code)]">{phi.phi_meso.toFixed(4)}</span>
                </div>
              )}
              {phi?.phi_macro != null && (
                <div className="flex justify-between text-xs">
                  <span className="text-text-secondary">Macro (Cross)</span>
                  <span className="font-[family-name:var(--font-code)]">{phi.phi_macro.toFixed(4)}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function ContractsTab() {
  const [deployAddr, setDeployAddr] = useState("");
  const [deployType, setDeployType] = useState("custom");
  const [bytecode, setBytecode] = useState("");

  return (
    <div className="space-y-6">
      {/* Deploy */}
      <Card>
        <h3 className="mb-4 font-[family-name:var(--font-display)] text-lg font-semibold">
          Deploy Contract
        </h3>
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs text-text-secondary">Contract Type</label>
            <select
              value={deployType}
              onChange={(e) => setDeployType(e.target.value)}
              className="w-full rounded-lg bg-bg-deep px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            >
              <option value="custom">Custom Bytecode</option>
              <option value="token">QBC-20 Token</option>
              <option value="nft">QBC-721 NFT</option>
              <option value="governance">Governance</option>
              <option value="escrow">Escrow</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-secondary">Bytecode (hex)</label>
            <textarea
              rows={3}
              value={bytecode}
              onChange={(e) => setBytecode(e.target.value)}
              placeholder="0x6080604052..."
              className="w-full rounded-lg bg-bg-deep px-4 py-2.5 font-[family-name:var(--font-code)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            />
          </div>
          <button className="rounded-lg bg-quantum-violet px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-quantum-violet/80">
            Deploy to QVM
          </button>
        </div>
      </Card>

      {/* Lookup */}
      <Card>
        <h3 className="mb-4 font-[family-name:var(--font-display)] text-lg font-semibold">
          View Contract
        </h3>
        <div className="flex gap-3">
          <input
            value={deployAddr}
            onChange={(e) => setDeployAddr(e.target.value)}
            placeholder="Contract address (0x...)"
            className="flex-1 rounded-lg bg-bg-deep px-4 py-2.5 font-[family-name:var(--font-code)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
          <a
            href={`/qvm?contract=${deployAddr}`}
            className="rounded-lg bg-quantum-green/20 px-5 py-2.5 text-sm font-medium text-quantum-green transition hover:bg-quantum-green/30"
          >
            Open in QVM
          </a>
        </div>
      </Card>
    </div>
  );
}

function WalletTab({
  address,
  connected,
}: {
  address: string | null;
  connected: boolean;
}) {
  const { data: utxos } = useQuery({
    queryKey: ["utxos", address],
    queryFn: () => api.getUTXOs(address!),
    enabled: !!address,
    refetchInterval: 15_000,
  });

  const { data: balance } = useQuery({
    queryKey: ["balance-wallet-tab", address],
    queryFn: () => api.getBalance(address!),
    enabled: !!address,
    refetchInterval: 10_000,
  });

  if (!connected || !address) {
    return (
      <Card>
        <p className="text-center text-sm text-text-secondary">
          Connect your wallet to view UTXO breakdown.
        </p>
      </Card>
    );
  }

  const utxoList = utxos?.utxos ?? [];
  const totalBalance = balance?.balance ? parseFloat(balance.balance) : 0;

  return (
    <div className="space-y-6">
      {/* Balance summary */}
      <Card glow="green">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-text-secondary">Total Balance</p>
            <p className="mt-1 font-[family-name:var(--font-code)] text-3xl font-bold text-quantum-green">
              {totalBalance.toLocaleString()} QBC
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm text-text-secondary">UTXOs</p>
            <p className="mt-1 font-[family-name:var(--font-code)] text-2xl font-bold">
              {utxoList.length}
            </p>
          </div>
        </div>
      </Card>

      {/* UTXO list */}
      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
            UTXO Breakdown
          </h3>
          {utxoList.length > 0 && (
            <ExportButton
              filenameBase="utxo_export"
              getData={() =>
                utxoList.map((u) => ({
                  txid: u.txid,
                  vout: u.vout,
                  amount: u.amount,
                  confirmations: u.confirmations,
                }))
              }
              columns={["txid", "vout", "amount", "confirmations"]}
            />
          )}
        </div>
        {utxoList.length === 0 ? (
          <p className="text-sm text-text-secondary">No UTXOs found.</p>
        ) : (
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-bg-panel">
                <tr className="border-b border-border-subtle text-left text-xs text-text-secondary">
                  <th className="pb-2 pr-4">Tx ID</th>
                  <th className="pb-2 pr-4">Vout</th>
                  <th className="pb-2 pr-4 text-right">Amount</th>
                  <th className="pb-2 text-right">Confirmations</th>
                </tr>
              </thead>
              <tbody className="font-[family-name:var(--font-code)]">
                {utxoList.map((utxo) => (
                  <tr
                    key={`${utxo.txid}-${utxo.vout}`}
                    className="border-b border-border-subtle/30"
                  >
                    <td className="py-2 pr-4 text-xs text-quantum-violet">
                      {utxo.txid.slice(0, 12)}...{utxo.txid.slice(-8)}
                    </td>
                    <td className="py-2 pr-4 text-xs text-text-secondary">
                      {utxo.vout}
                    </td>
                    <td className="py-2 pr-4 text-right text-quantum-green">
                      {utxo.amount.toLocaleString()} QBC
                    </td>
                    <td className="py-2 text-right text-xs text-text-secondary">
                      {utxo.confirmations.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Address */}
      <Card>
        <h3 className="mb-2 text-sm font-semibold text-text-secondary">Address</h3>
        <p className="break-all font-[family-name:var(--font-code)] text-xs text-quantum-green">
          {address}
        </p>
      </Card>
    </div>
  );
}

function NetworkTab({
  chain,
}: {
  chain: ReturnType<typeof api.getChainInfo> extends Promise<infer T> ? T | undefined : never;
}) {
  const { data: peerStats } = useQuery({
    queryKey: ["p2pStats"],
    queryFn: api.getPeerStats,
    refetchInterval: 15_000,
    retry: false,
  });

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">Peers</h3>
          <p className="font-[family-name:var(--font-code)] text-2xl font-bold">
            {chain?.peers?.toString() ?? "---"}
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            Type: {peerStats?.network?.type ?? "---"}
          </p>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">Mempool</h3>
          <p className="font-[family-name:var(--font-code)] text-2xl font-bold">
            {chain?.mempool_size?.toString() ?? "---"} tx
          </p>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">Chain ID</h3>
          <p className="font-[family-name:var(--font-code)] text-xl">
            {chain?.chain_id ?? "3303"}
          </p>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">Block Height</h3>
          <p className="font-[family-name:var(--font-code)] text-xl">
            {chain?.height?.toLocaleString() ?? "---"}
          </p>
        </Card>
      </div>

      {/* Message stats */}
      {peerStats?.messages && Object.keys(peerStats.messages).length > 0 && (
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">P2P Messages</h3>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(peerStats.messages).map(([key, val]) => (
              <div key={key} className="text-sm">
                <span className="text-text-secondary">{key}: </span>
                <span className="font-[family-name:var(--font-code)] text-text-primary">
                  {val?.toLocaleString() ?? "0"}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
