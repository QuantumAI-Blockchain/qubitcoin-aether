"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { PhiSpinner } from "@/components/ui/loading";
import { useWalletStore } from "@/stores/wallet-store";

const TABS = ["Overview", "Mining", "Aether", "Network"] as const;
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

  const { data: balance } = useQuery({
    queryKey: ["balance", address],
    queryFn: () => api.getBalance(address!),
    enabled: !!address,
    refetchInterval: 10_000,
  });

  if (chainLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center pt-16">
        <PhiSpinner />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 pt-20 pb-12">
      <h1 className="font-[family-name:var(--font-heading)] text-3xl font-bold">
        Dashboard
      </h1>

      {/* Tabs */}
      <div className="mt-6 flex gap-1 border-b border-surface-light">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`relative px-4 py-2 text-sm transition-colors ${
              tab === t ? "text-quantum-green" : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {t}
            {tab === t && (
              <motion.span
                layoutId="dashboard-tab"
                className="absolute inset-x-0 -bottom-[1px] h-0.5 bg-quantum-green"
              />
            )}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {tab === "Overview" && (
          <OverviewTab chain={chain} phi={phi} balance={balance?.balance} connected={connected} />
        )}
        {tab === "Mining" && <MiningTab mining={mining} chain={chain} />}
        {tab === "Aether" && <AetherTab phi={phi} />}
        {tab === "Network" && <NetworkTab chain={chain} />}
      </div>
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
  const stats = [
    { label: "Block Height", value: chain?.height?.toLocaleString() ?? "---" },
    { label: "Total Supply", value: chain?.total_supply ? `${(chain.total_supply / 1e9).toFixed(4)}B` : "---" },
    { label: "Difficulty", value: chain?.difficulty?.toFixed(6) ?? "---" },
    { label: "Mempool", value: chain?.mempool_size?.toString() ?? "---" },
    { label: "Phi (\u03A6)", value: phi?.phi?.toFixed(4) ?? "---" },
    { label: "Knowledge", value: phi?.knowledge_nodes?.toLocaleString() ?? "---" },
  ];

  return (
    <div className="space-y-6">
      {connected && (
        <Card glow="green">
          <p className="text-sm text-text-secondary">Your Balance</p>
          <p className="mt-1 font-[family-name:var(--font-mono)] text-2xl font-bold text-quantum-green">
            {balance != null ? balance.toLocaleString() : "---"} QBC
          </p>
        </Card>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {stats.map(({ label, value }) => (
          <Card key={label}>
            <p className="text-xs text-text-secondary">{label}</p>
            <p className="mt-1 font-[family-name:var(--font-mono)] text-xl font-semibold">
              {value}
            </p>
          </Card>
        ))}
      </div>
    </div>
  );
}

function MiningTab({
  mining,
  chain,
}: {
  mining: Record<string, unknown> | undefined;
  chain: ReturnType<typeof api.getChainInfo> extends Promise<infer T> ? T | undefined : never;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">Mining Status</h3>
        <p className="text-lg font-semibold">
          {mining ? (
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
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">Blocks Mined</h3>
        <p className="font-[family-name:var(--font-mono)] text-2xl font-bold">
          {(mining?.blocks_mined as number)?.toLocaleString() ?? "---"}
        </p>
      </Card>
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">VQE Energy</h3>
        <p className="font-[family-name:var(--font-mono)] text-lg">
          {(mining?.best_energy as number)?.toFixed(6) ?? "---"}
        </p>
      </Card>
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">Alignment Score</h3>
        <p className="font-[family-name:var(--font-mono)] text-lg">
          {(mining?.alignment_score as number)?.toFixed(4) ?? "---"}
        </p>
      </Card>
    </div>
  );
}

function AetherTab({
  phi,
}: {
  phi: ReturnType<typeof api.getPhi> extends Promise<infer T> ? T | undefined : never;
}) {
  const pct = phi ? Math.min((phi.phi / phi.threshold) * 100, 100) : 0;

  return (
    <div className="space-y-6">
      <Card glow="violet">
        <h3 className="mb-3 font-[family-name:var(--font-heading)] text-lg font-semibold">
          Consciousness Status
        </h3>
        <div className="flex items-end gap-4">
          <p className="font-[family-name:var(--font-mono)] text-4xl font-bold text-quantum-green">
            {phi?.phi?.toFixed(4) ?? "0.0000"}
          </p>
          <p className="mb-1 text-sm text-text-secondary">
            / {phi?.threshold?.toFixed(1) ?? "3.0"} threshold ({pct.toFixed(1)}%)
          </p>
        </div>
        <div className="mt-4 h-3 w-full overflow-hidden rounded-full bg-void">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-quantum-violet to-quantum-green"
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 1.5 }}
          />
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <p className="text-xs text-text-secondary">Knowledge Nodes</p>
          <p className="mt-1 font-[family-name:var(--font-mono)] text-xl font-semibold">
            {phi?.knowledge_nodes?.toLocaleString() ?? "---"}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Knowledge Edges</p>
          <p className="mt-1 font-[family-name:var(--font-mono)] text-xl font-semibold">
            {phi?.knowledge_edges?.toLocaleString() ?? "---"}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Integration</p>
          <p className="mt-1 font-[family-name:var(--font-mono)] text-xl font-semibold">
            {phi?.integration?.toFixed(4) ?? "---"}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Differentiation</p>
          <p className="mt-1 font-[family-name:var(--font-mono)] text-xl font-semibold">
            {phi?.differentiation?.toFixed(4) ?? "---"}
          </p>
        </Card>
      </div>
    </div>
  );
}

function NetworkTab({
  chain,
}: {
  chain: ReturnType<typeof api.getChainInfo> extends Promise<infer T> ? T | undefined : never;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">Peers</h3>
        <p className="font-[family-name:var(--font-mono)] text-2xl font-bold">
          {chain?.peers?.toString() ?? "---"}
        </p>
      </Card>
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">Mempool</h3>
        <p className="font-[family-name:var(--font-mono)] text-2xl font-bold">
          {chain?.mempool_size?.toString() ?? "---"} tx
        </p>
      </Card>
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">Chain ID</h3>
        <p className="font-[family-name:var(--font-mono)] text-xl">
          {chain?.chain_id ?? "3301"}
        </p>
      </Card>
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">Block Height</h3>
        <p className="font-[family-name:var(--font-mono)] text-xl">
          {chain?.height?.toLocaleString() ?? "---"}
        </p>
      </Card>
    </div>
  );
}
