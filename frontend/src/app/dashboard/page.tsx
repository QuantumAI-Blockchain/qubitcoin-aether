"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { PhiSpinner } from "@/components/ui/loading";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { PhiChart } from "@/components/dashboard/phi-chart";
import { MiningControls } from "@/components/dashboard/mining-controls";
import { QUSDReserveGauge, QUSDMilestoneTimeline } from "@/components/dashboard/qusd-reserve";
import { useWalletStore } from "@/stores/wallet-store";

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

      {/* QUSD Reserve Status */}
      <div className="grid gap-4 sm:grid-cols-2">
        <ErrorBoundary>
          <QUSDReserveGauge />
        </ErrorBoundary>
        <ErrorBoundary>
          <QUSDMilestoneTimeline />
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
      <ErrorBoundary>
        <MiningControls isActive={mining?.is_mining ?? false} />
      </ErrorBoundary>
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
          <p className="font-[family-name:var(--font-mono)] text-2xl font-bold">
            {mining?.blocks_found?.toLocaleString() ?? "---"}
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            Attempts: {mining?.total_attempts?.toLocaleString() ?? "---"}
          </p>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">Success Rate</h3>
          <p className="font-[family-name:var(--font-mono)] text-lg">
            {mining?.success_rate != null ? `${(mining.success_rate * 100).toFixed(2)}%` : "---"}
          </p>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">VQE Energy</h3>
          <p className="font-[family-name:var(--font-mono)] text-lg">
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

      <ErrorBoundary>
        <PhiChart />
      </ErrorBoundary>
    </div>
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
        <h3 className="mb-4 font-[family-name:var(--font-heading)] text-lg font-semibold">
          Deploy Contract
        </h3>
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs text-text-secondary">Contract Type</label>
            <select
              value={deployType}
              onChange={(e) => setDeployType(e.target.value)}
              className="w-full rounded-lg bg-void px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
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
              className="w-full rounded-lg bg-void px-4 py-2.5 font-[family-name:var(--font-mono)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            />
          </div>
          <button className="rounded-lg bg-quantum-violet px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-quantum-violet/80">
            Deploy to QVM
          </button>
        </div>
      </Card>

      {/* Lookup */}
      <Card>
        <h3 className="mb-4 font-[family-name:var(--font-heading)] text-lg font-semibold">
          View Contract
        </h3>
        <div className="flex gap-3">
          <input
            value={deployAddr}
            onChange={(e) => setDeployAddr(e.target.value)}
            placeholder="Contract address (0x...)"
            className="flex-1 rounded-lg bg-void px-4 py-2.5 font-[family-name:var(--font-mono)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
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
            <p className="mt-1 font-[family-name:var(--font-mono)] text-3xl font-bold text-quantum-green">
              {totalBalance.toLocaleString()} QBC
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm text-text-secondary">UTXOs</p>
            <p className="mt-1 font-[family-name:var(--font-mono)] text-2xl font-bold">
              {utxoList.length}
            </p>
          </div>
        </div>
      </Card>

      {/* UTXO list */}
      <Card>
        <h3 className="mb-4 font-[family-name:var(--font-heading)] text-lg font-semibold">
          UTXO Breakdown
        </h3>
        {utxoList.length === 0 ? (
          <p className="text-sm text-text-secondary">No UTXOs found.</p>
        ) : (
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface">
                <tr className="border-b border-surface-light text-left text-xs text-text-secondary">
                  <th className="pb-2 pr-4">Tx ID</th>
                  <th className="pb-2 pr-4">Vout</th>
                  <th className="pb-2 pr-4 text-right">Amount</th>
                  <th className="pb-2 text-right">Confirmations</th>
                </tr>
              </thead>
              <tbody className="font-[family-name:var(--font-mono)]">
                {utxoList.map((utxo) => (
                  <tr
                    key={`${utxo.txid}-${utxo.vout}`}
                    className="border-b border-surface-light/30"
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
        <p className="break-all font-[family-name:var(--font-mono)] text-xs text-quantum-green">
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
          <p className="font-[family-name:var(--font-mono)] text-2xl font-bold">
            {chain?.peers?.toString() ?? "---"}
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            Type: {peerStats?.network?.type ?? "---"}
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

      {/* Message stats */}
      {peerStats?.messages && Object.keys(peerStats.messages).length > 0 && (
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">P2P Messages</h3>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(peerStats.messages).map(([key, val]) => (
              <div key={key} className="text-sm">
                <span className="text-text-secondary">{key}: </span>
                <span className="font-[family-name:var(--font-mono)] text-text-primary">
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
