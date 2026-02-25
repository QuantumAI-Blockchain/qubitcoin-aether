"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Block Detail View
   ───────────────────────────────────────────────────────────────────────── */

import { motion } from "framer-motion";
import { Box, ChevronLeft, ChevronRight, Clock, Cpu, Zap } from "lucide-react";
import { useBlock, useBlockTransactions } from "./hooks";
import { useExplorerStore } from "./store";
import {
  C, FONT, BackButton, Badge, CopyButton, DataTable, HashLink,
  LoadingSpinner, Panel, SectionHeader, StatCard, formatQBC, formatNumber,
  truncHash, txTypeColor, txTypeBadge,
} from "./shared";
import type { Transaction } from "./types";

export function BlockDetail({ height }: { height: number }) {
  const navigate = useExplorerStore((s) => s.navigate);
  const { data: block, isLoading } = useBlock(height);
  const { data: txs } = useBlockTransactions(height);

  if (isLoading) return <LoadingSpinner />;
  if (!block) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12">
        <Box size={48} style={{ color: C.textMuted }} />
        <p style={{ color: C.textSecondary, fontFamily: FONT.body }}>
          Block #{height} not found
        </p>
        <BackButton />
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      {/* Navigation */}
      <div className="flex items-center justify-between">
        <BackButton />
        <div className="flex items-center gap-2">
          {height > 0 && (
            <button
              onClick={() => navigate("block", { id: String(height - 1) })}
              className="flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition-opacity hover:opacity-80"
              style={{ borderColor: C.border, color: C.textSecondary, fontFamily: FONT.mono }}
            >
              <ChevronLeft size={12} />
              {height - 1}
            </button>
          )}
          <button
            onClick={() => navigate("block", { id: String(height + 1) })}
            className="flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition-opacity hover:opacity-80"
            style={{ borderColor: C.border, color: C.textSecondary, fontFamily: FONT.mono }}
          >
            {height + 1}
            <ChevronRight size={12} />
          </button>
        </div>
      </div>

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-3"
      >
        <div
          className="flex h-10 w-10 items-center justify-center rounded-lg"
          style={{ background: `${C.primary}18` }}
        >
          <Box size={20} style={{ color: C.primary }} />
        </div>
        <div>
          <h1
            className="text-lg font-bold"
            style={{ color: C.textPrimary, fontFamily: FONT.heading }}
          >
            BLOCK #{formatNumber(height)}
          </h1>
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
              {truncHash(block.hash, 16)}
            </span>
            <CopyButton text={block.hash} />
          </div>
        </div>
      </motion.div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <StatCard
          label="Transactions"
          value={block.txCount}
          icon={Zap}
          color={C.primary}
        />
        <StatCard
          label="Reward"
          value={`${block.reward.toFixed(2)} QBC`}
          color={C.success}
        />
        <StatCard
          label="VQE Energy"
          value={block.energy.toFixed(6)}
          sub={`Difficulty: ${block.difficulty.toFixed(4)}`}
          color={C.accent}
        />
        <StatCard
          label="Φ at Block"
          value={block.phiAtBlock.toFixed(4)}
          color={C.phi}
        />
      </div>

      {/* Detail Fields */}
      <Panel>
        <SectionHeader title="BLOCK DETAILS" />
        <div className="space-y-2 text-xs" style={{ fontFamily: FONT.mono }}>
          {[
            ["Hash", block.hash, true],
            ["Previous Hash", block.prevHash, true],
            ["Merkle Root", block.merkleRoot, true],
            ["Miner", block.miner, true],
            ["Timestamp", new Date(block.timestamp * 1000).toISOString()],
            ["Size", `${formatNumber(block.size)} bytes`],
            ["Gas Used", `${formatNumber(block.gasUsed)} / ${formatNumber(block.gasLimit)}`],
            ["Difficulty", block.difficulty.toFixed(6)],
            ["VQE Energy", block.energy.toFixed(8)],
          ].map(([label, value, copyable]) => (
            <div
              key={label as string}
              className="flex items-start gap-3 border-b py-2"
              style={{ borderColor: `${C.border}60` }}
            >
              <span
                className="w-28 shrink-0 text-[10px] uppercase tracking-wider"
                style={{ color: C.textMuted, fontFamily: FONT.heading }}
              >
                {label as string}
              </span>
              <span
                className="min-w-0 break-all"
                style={{ color: C.textPrimary }}
              >
                {value as string}
              </span>
              {copyable && <CopyButton text={value as string} />}
            </div>
          ))}

          {/* VQE Parameters */}
          <div
            className="flex items-start gap-3 border-b py-2"
            style={{ borderColor: `${C.border}60` }}
          >
            <span
              className="w-28 shrink-0 text-[10px] uppercase tracking-wider"
              style={{ color: C.textMuted, fontFamily: FONT.heading }}
            >
              VQE Params
            </span>
            <div className="flex flex-wrap gap-1">
              {block.vqeParams.map((p, i) => (
                <span
                  key={i}
                  className="rounded px-1 py-0.5 text-[10px]"
                  style={{ background: `${C.secondary}15`, color: C.secondary }}
                >
                  θ{i}={p.toFixed(3)}
                </span>
              ))}
            </div>
          </div>

          {/* Miner link */}
          <div className="flex items-center gap-3 py-2">
            <span
              className="w-28 shrink-0 text-[10px] uppercase tracking-wider"
              style={{ color: C.textMuted, fontFamily: FONT.heading }}
            >
              Miner
            </span>
            <HashLink hash={block.miner} type="wallet" truncLen={12} />
          </div>
        </div>
      </Panel>

      {/* Transactions Table */}
      <Panel>
        <SectionHeader title={`TRANSACTIONS (${txs?.length ?? 0})`} />
        <DataTable<Transaction>
          columns={[
            {
              key: "txid",
              header: "TXID",
              render: (t) => <HashLink hash={t.txid} type="transaction" truncLen={8} />,
            },
            {
              key: "type",
              header: "TYPE",
              render: (t) => <Badge label={txTypeBadge(t.type)} color={txTypeColor(t.type)} />,
            },
            {
              key: "from",
              header: "FROM",
              render: (t) => (
                t.from === "coinbase" ? (
                  <Badge label="COINBASE" color={C.success} />
                ) : (
                  <HashLink hash={t.from} type="wallet" truncLen={6} />
                )
              ),
            },
            {
              key: "to",
              header: "TO",
              render: (t) => <HashLink hash={t.to} type="wallet" truncLen={6} />,
            },
            {
              key: "value",
              header: "VALUE",
              align: "right",
              render: (t) => (
                <span style={{ color: t.isPrivate ? C.susy : C.textPrimary }}>
                  {t.isPrivate ? "HIDDEN" : `${formatQBC(t.value)} QBC`}
                </span>
              ),
            },
            {
              key: "fee",
              header: "FEE",
              align: "right",
              render: (t) => (
                <span style={{ color: C.textMuted }}>{t.fee.toFixed(4)}</span>
              ),
            },
          ]}
          data={txs ?? []}
          keyFn={(t) => t.txid}
          onRowClick={(t) => navigate("transaction", { id: t.txid })}
        />
      </Panel>
    </div>
  );
}
