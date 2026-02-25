"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Transaction Detail View
   ───────────────────────────────────────────────────────────────────────── */

import { motion } from "framer-motion";
import { ArrowRight, FileText, Lock, Shield } from "lucide-react";
import { useTransaction } from "./hooks";
import { useExplorerStore } from "./store";
import {
  C, FONT, BackButton, Badge, CopyButton, DataTable, HashLink,
  LoadingSpinner, Panel, SectionHeader, StatCard, formatQBC, formatNumber,
  truncHash, txTypeColor, txTypeBadge,
} from "./shared";
import type { TxInput, TxOutput } from "./types";

export function TransactionDetail({ txid }: { txid: string }) {
  const navigate = useExplorerStore((s) => s.navigate);
  const { data: tx, isLoading } = useTransaction(txid);

  if (isLoading) return <LoadingSpinner />;
  if (!tx) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12">
        <FileText size={48} style={{ color: C.textMuted }} />
        <p style={{ color: C.textSecondary, fontFamily: FONT.body }}>
          Transaction not found
        </p>
        <p className="text-xs" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
          {truncHash(txid, 16)}
        </p>
        <BackButton />
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      <BackButton />

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-start gap-3"
      >
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
          style={{ background: `${txTypeColor(tx.type)}18` }}
        >
          {tx.isPrivate ? (
            <Lock size={20} style={{ color: C.susy }} />
          ) : (
            <FileText size={20} style={{ color: txTypeColor(tx.type) }} />
          )}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1
              className="text-lg font-bold"
              style={{ color: C.textPrimary, fontFamily: FONT.heading }}
            >
              TRANSACTION
            </h1>
            <Badge label={txTypeBadge(tx.type)} color={txTypeColor(tx.type)} />
            {tx.isPrivate && <Badge label="PRIVATE" color={C.susy} />}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
              {truncHash(tx.txid, 20)}
            </span>
            <CopyButton text={tx.txid} />
          </div>
        </div>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Value"
          value={tx.isPrivate ? "HIDDEN" : `${formatQBC(tx.value)} QBC`}
          color={tx.isPrivate ? C.susy : C.primary}
        />
        <StatCard
          label="Fee"
          value={`${tx.fee.toFixed(4)} QBC`}
          color={C.warning}
        />
        <StatCard
          label="Block"
          value={formatNumber(tx.blockHeight)}
          color={C.primary}
          onClick={() => navigate("block", { id: String(tx.blockHeight) })}
        />
        <StatCard
          label="Confirmations"
          value={formatNumber(tx.confirmations)}
          sub={tx.confirmations >= 6 ? "Finalized" : "Pending"}
          color={tx.confirmations >= 6 ? C.success : C.warning}
        />
      </div>

      {/* Detail Fields */}
      <Panel>
        <SectionHeader title="TRANSACTION DETAILS" />
        <div className="space-y-2 text-xs" style={{ fontFamily: FONT.mono }}>
          {[
            ["TXID", tx.txid, true],
            ["Block Hash", tx.blockHash, true],
            ["Status", tx.status.toUpperCase()],
            ["Timestamp", new Date(tx.timestamp * 1000).toISOString()],
            ["Size", `${formatNumber(tx.size)} bytes`],
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
              <span className="min-w-0 break-all" style={{ color: C.textPrimary }}>
                {value as string}
              </span>
              {copyable && <CopyButton text={value as string} />}
            </div>
          ))}

          {/* From → To */}
          <div className="flex items-center gap-3 border-b py-3" style={{ borderColor: `${C.border}60` }}>
            <span
              className="w-28 shrink-0 text-[10px] uppercase tracking-wider"
              style={{ color: C.textMuted, fontFamily: FONT.heading }}
            >
              Transfer
            </span>
            <div className="flex flex-wrap items-center gap-2">
              {tx.from === "coinbase" ? (
                <Badge label="COINBASE" color={C.success} />
              ) : (
                <HashLink hash={tx.from} type="wallet" truncLen={10} />
              )}
              <ArrowRight size={14} style={{ color: C.textMuted }} />
              <HashLink hash={tx.to} type="wallet" truncLen={10} />
            </div>
          </div>

          {/* Gas */}
          {tx.gasUsed !== undefined && (
            <div className="flex items-center gap-3 border-b py-2" style={{ borderColor: `${C.border}60` }}>
              <span
                className="w-28 shrink-0 text-[10px] uppercase tracking-wider"
                style={{ color: C.textMuted, fontFamily: FONT.heading }}
              >
                Gas Used
              </span>
              <span style={{ color: C.textPrimary }}>{formatNumber(tx.gasUsed)}</span>
            </div>
          )}

          {/* Contract Address */}
          {tx.contractAddress && (
            <div className="flex items-center gap-3 border-b py-2" style={{ borderColor: `${C.border}60` }}>
              <span
                className="w-28 shrink-0 text-[10px] uppercase tracking-wider"
                style={{ color: C.textMuted, fontFamily: FONT.heading }}
              >
                Contract
              </span>
              <HashLink hash={tx.contractAddress} type="contract" truncLen={12} />
            </div>
          )}

          {/* Data */}
          {tx.data && (
            <div className="flex items-start gap-3 py-2">
              <span
                className="w-28 shrink-0 text-[10px] uppercase tracking-wider"
                style={{ color: C.textMuted, fontFamily: FONT.heading }}
              >
                Input Data
              </span>
              <code
                className="rounded px-2 py-1 text-[10px]"
                style={{ background: `${C.border}40`, color: C.textSecondary }}
              >
                {tx.data}
              </code>
            </div>
          )}
        </div>
      </Panel>

      {/* UTXO Inputs */}
      {tx.inputs.length > 0 && (
        <Panel>
          <SectionHeader title={`INPUTS (${tx.inputs.length})`} />
          <DataTable<TxInput>
            columns={[
              {
                key: "txid",
                header: "SOURCE TXID",
                render: (inp) => <HashLink hash={inp.txid} type="transaction" truncLen={8} />,
              },
              {
                key: "vout",
                header: "VOUT",
                width: "50px",
                render: (inp) => <span style={{ color: C.textSecondary }}>{inp.vout}</span>,
              },
              {
                key: "address",
                header: "ADDRESS",
                render: (inp) => <HashLink hash={inp.address} type="wallet" truncLen={8} />,
              },
              {
                key: "value",
                header: "VALUE",
                align: "right",
                render: (inp) => (
                  <span style={{ color: C.error }}>{formatQBC(inp.value)} QBC</span>
                ),
              },
            ]}
            data={tx.inputs}
            keyFn={(inp) => `${inp.txid}:${inp.vout}`}
          />
        </Panel>
      )}

      {/* UTXO Outputs */}
      {tx.outputs.length > 0 && (
        <Panel>
          <SectionHeader title={`OUTPUTS (${tx.outputs.length})`} />
          <DataTable<TxOutput>
            columns={[
              {
                key: "index",
                header: "INDEX",
                width: "50px",
                render: (out) => <span style={{ color: C.textSecondary }}>{out.index}</span>,
              },
              {
                key: "address",
                header: "ADDRESS",
                render: (out) => <HashLink hash={out.address} type="wallet" truncLen={10} />,
              },
              {
                key: "value",
                header: "VALUE",
                align: "right",
                render: (out) => (
                  <span style={{ color: C.success }}>{formatQBC(out.value)} QBC</span>
                ),
              },
              {
                key: "spent",
                header: "STATUS",
                align: "right",
                render: (out) => (
                  <Badge
                    label={out.spent ? "SPENT" : "UNSPENT"}
                    color={out.spent ? C.textMuted : C.success}
                  />
                ),
              },
            ]}
            data={tx.outputs}
            keyFn={(out) => `${out.index}`}
          />
        </Panel>
      )}
    </div>
  );
}
