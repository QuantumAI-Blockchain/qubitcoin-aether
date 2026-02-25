"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Wallet / Address View
   ───────────────────────────────────────────────────────────────────────── */

import { motion } from "framer-motion";
import { Wallet, Code, ArrowDownRight, ArrowUpRight } from "lucide-react";
import { useWallet } from "./hooks";
import { useExplorerStore } from "./store";
import {
  C, FONT, BackButton, Badge, CopyButton, DataTable, HashLink,
  LoadingSpinner, Panel, SectionHeader, StatCard, formatQBC, formatNumber,
  truncHash, txTypeColor, txTypeBadge,
} from "./shared";
import type { Transaction, TxOutput } from "./types";

export function WalletView({ address }: { address: string }) {
  const navigate = useExplorerStore((s) => s.navigate);
  const { data: wallet, isLoading } = useWallet(address);

  if (isLoading) return <LoadingSpinner />;
  if (!wallet) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12">
        <Wallet size={48} style={{ color: C.textMuted }} />
        <p style={{ color: C.textSecondary, fontFamily: FONT.body }}>
          Address not found
        </p>
        <p className="text-xs" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
          {truncHash(address, 16)}
        </p>
        <BackButton />
      </div>
    );
  }

  // Separate sent and received
  const sent = wallet.transactions.filter((t) => t.from === address);
  const received = wallet.transactions.filter((t) => t.to === address || t.outputs.some((o) => o.address === address));

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
          style={{ background: wallet.isContract ? `${C.secondary}18` : `${C.primary}18` }}
        >
          {wallet.isContract ? (
            <Code size={20} style={{ color: C.secondary }} />
          ) : (
            <Wallet size={20} style={{ color: C.primary }} />
          )}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1
              className="text-lg font-bold"
              style={{ color: C.textPrimary, fontFamily: FONT.heading }}
            >
              {wallet.isContract ? "CONTRACT" : "ADDRESS"}
            </h1>
            {wallet.isContract && <Badge label="CONTRACT" color={C.secondary} />}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
              {truncHash(address, 16)}
            </span>
            <CopyButton text={address} />
          </div>
        </div>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Balance"
          value={`${formatQBC(wallet.balance)} QBC`}
          color={C.success}
        />
        <StatCard
          label="Transactions"
          value={formatNumber(wallet.txCount)}
          color={C.primary}
        />
        <StatCard
          label="UTXOs"
          value={formatNumber(wallet.utxos.length)}
          color={C.accent}
        />
        <StatCard
          label="First Seen"
          value={new Date(wallet.firstSeen * 1000).toLocaleDateString()}
          sub={new Date(wallet.lastSeen * 1000).toLocaleDateString()}
          color={C.textSecondary}
        />
      </div>

      {/* UTXOs */}
      {wallet.utxos.length > 0 && (
        <Panel>
          <SectionHeader title={`UNSPENT OUTPUTS (${wallet.utxos.length})`} />
          <DataTable<TxOutput>
            columns={[
              {
                key: "index",
                header: "INDEX",
                width: "50px",
                render: (u) => <span style={{ color: C.textSecondary }}>{u.index}</span>,
              },
              {
                key: "value",
                header: "VALUE",
                render: (u) => (
                  <span style={{ color: C.success, fontFamily: FONT.mono }}>
                    {formatQBC(u.value)} QBC
                  </span>
                ),
              },
              {
                key: "status",
                header: "STATUS",
                align: "right",
                render: () => <Badge label="UNSPENT" color={C.success} />,
              },
            ]}
            data={wallet.utxos.slice(0, 20)}
            keyFn={(u) => `${u.address}:${u.index}:${u.value}`}
          />
        </Panel>
      )}

      {/* Transaction History */}
      <Panel>
        <SectionHeader title={`TRANSACTIONS (${wallet.transactions.length})`} />
        <DataTable<Transaction>
          columns={[
            {
              key: "txid",
              header: "TXID",
              render: (t) => <HashLink hash={t.txid} type="transaction" truncLen={8} />,
            },
            {
              key: "direction",
              header: "",
              width: "30px",
              render: (t) =>
                t.from === address ? (
                  <ArrowUpRight size={12} style={{ color: C.error }} />
                ) : (
                  <ArrowDownRight size={12} style={{ color: C.success }} />
                ),
            },
            {
              key: "type",
              header: "TYPE",
              render: (t) => <Badge label={txTypeBadge(t.type)} color={txTypeColor(t.type)} />,
            },
            {
              key: "counterparty",
              header: "COUNTERPARTY",
              render: (t) => {
                const cp = t.from === address ? t.to : t.from;
                return cp === "coinbase" ? (
                  <Badge label="COINBASE" color={C.success} />
                ) : (
                  <HashLink hash={cp} type="wallet" truncLen={6} />
                );
              },
            },
            {
              key: "value",
              header: "VALUE",
              align: "right",
              render: (t) => (
                <span
                  style={{
                    color: t.from === address ? C.error : C.success,
                    fontFamily: FONT.mono,
                  }}
                >
                  {t.from === address ? "-" : "+"}
                  {formatQBC(t.value)}
                </span>
              ),
            },
            {
              key: "block",
              header: "BLOCK",
              align: "right",
              width: "60px",
              render: (t) => (
                <HashLink hash={String(t.blockHeight)} type="block" truncLen={10} />
              ),
            },
          ]}
          data={wallet.transactions.slice(0, 50)}
          keyFn={(t) => t.txid}
          onRowClick={(t) => navigate("transaction", { id: t.txid })}
        />
      </Panel>
    </div>
  );
}
