"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Search Results View
   ───────────────────────────────────────────────────────────────────────── */

import { motion } from "framer-motion";
import { Search, Box, FileText, Wallet, Code } from "lucide-react";
import { useSearch } from "./hooks";
import { useExplorerStore } from "./store";
import {
  C, FONT, Badge, DataTable, HashLink, LoadingSpinner,
  Panel, SectionHeader, formatQBC, formatNumber, truncHash,
  txTypeColor, txTypeBadge,
} from "./shared";
import type { Block, Transaction, WalletData, QVMContract } from "./types";

type StructuredResults = {
  blocks: Block[];
  transactions: Transaction[];
  addresses: WalletData[];
  contracts: QVMContract[];
};

function normalizeResults(
  raw: StructuredResults | Array<{ type: string; id: string; label: string }> | undefined
): StructuredResults {
  if (!raw) return { blocks: [], transactions: [], addresses: [], contracts: [] };
  if (!Array.isArray(raw)) return raw;
  // Convert flat array to structured format (from real API)
  const blocks: Block[] = [];
  const addresses: WalletData[] = [];
  const contracts: QVMContract[] = [];
  for (const r of raw) {
    if (r.type === "block") {
      blocks.push({ height: Number(r.id), hash: r.id, txCount: 0, miner: "", timestamp: 0, difficulty: 0, energy: 0, size: 0, reward: 0, prevHash: "", merkleRoot: "" } as Block);
    } else if (r.type === "address") {
      addresses.push({ address: r.id, balance: 0, txCount: 0, utxos: [], isContract: false } as unknown as WalletData);
    } else if (r.type === "contract") {
      contracts.push({ address: r.id, name: r.label, standard: "QBC-20", balance: 0, creator: "", deployHeight: 0, txCount: 0 } as QVMContract);
    }
  }
  return { blocks, transactions: [], addresses, contracts };
}

export function SearchResults({ query }: { query: string }) {
  const navigate = useExplorerStore((s) => s.navigate);
  const { data: rawResults, isLoading } = useSearch(query);

  if (isLoading) return <LoadingSpinner />;

  const results = normalizeResults(rawResults);
  const totalResults =
    results.blocks.length +
    results.transactions.length +
    results.addresses.length +
    results.contracts.length;

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3">
          <Search size={20} style={{ color: C.primary }} />
          <div>
            <h1
              className="text-lg font-bold tracking-widest"
              style={{ color: C.textPrimary, fontFamily: FONT.heading }}
            >
              SEARCH RESULTS
            </h1>
            <p className="text-xs" style={{ color: C.textSecondary, fontFamily: FONT.mono }}>
              {totalResults} results for &quot;{truncHash(query, 20)}&quot;
            </p>
          </div>
        </div>
      </motion.div>

      {totalResults === 0 && (
        <div className="flex flex-col items-center gap-4 py-16">
          <Search size={48} style={{ color: C.textMuted }} />
          <p style={{ color: C.textSecondary, fontFamily: FONT.body }}>
            No results found
          </p>
          <p className="text-xs" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
            Try a block height, transaction hash, or address
          </p>
        </div>
      )}

      {/* Blocks */}
      {results.blocks.length > 0 && (
        <Panel>
          <SectionHeader
            title={`BLOCKS (${results.blocks.length})`}
            action={<Box size={14} style={{ color: C.primary }} />}
          />
          <DataTable<Block>
            columns={[
              {
                key: "height",
                header: "HEIGHT",
                render: (b) => <HashLink hash={String(b.height)} type="block" truncLen={10} />,
              },
              {
                key: "hash",
                header: "HASH",
                render: (b) => (
                  <span className="text-[10px]" style={{ color: C.textSecondary, fontFamily: FONT.mono }}>
                    {truncHash(b.hash, 12)}
                  </span>
                ),
              },
              {
                key: "txs",
                header: "TXS",
                align: "right",
                render: (b) => <span>{b.txCount}</span>,
              },
              {
                key: "miner",
                header: "MINER",
                render: (b) => <HashLink hash={b.miner} type="wallet" truncLen={6} />,
              },
            ]}
            data={results.blocks}
            keyFn={(b) => String(b.height)}
            onRowClick={(b) => navigate("block", { id: String(b.height) })}
          />
        </Panel>
      )}

      {/* Transactions */}
      {results.transactions.length > 0 && (
        <Panel>
          <SectionHeader
            title={`TRANSACTIONS (${results.transactions.length})`}
            action={<FileText size={14} style={{ color: C.primary }} />}
          />
          <DataTable<Transaction>
            columns={[
              {
                key: "txid",
                header: "TXID",
                render: (t) => <HashLink hash={t.txid} type="transaction" truncLen={10} />,
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
                render: (t) => <span style={{ color: C.textPrimary }}>{formatQBC(t.value)}</span>,
              },
              {
                key: "block",
                header: "BLOCK",
                align: "right",
                render: (t) => <span style={{ color: C.textSecondary }}>{t.blockHeight}</span>,
              },
            ]}
            data={results.transactions}
            keyFn={(t) => t.txid}
            onRowClick={(t) => navigate("transaction", { id: t.txid })}
          />
        </Panel>
      )}

      {/* Addresses */}
      {results.addresses.length > 0 && (
        <Panel>
          <SectionHeader
            title={`ADDRESSES (${results.addresses.length})`}
            action={<Wallet size={14} style={{ color: C.primary }} />}
          />
          <DataTable<WalletData>
            columns={[
              {
                key: "address",
                header: "ADDRESS",
                render: (w) => <HashLink hash={w.address} type="wallet" truncLen={12} />,
              },
              {
                key: "balance",
                header: "BALANCE",
                align: "right",
                render: (w) => (
                  <span style={{ color: C.success }}>{formatQBC(w.balance)} QBC</span>
                ),
              },
              {
                key: "txCount",
                header: "TXS",
                align: "right",
                render: (w) => <span>{formatNumber(w.txCount)}</span>,
              },
              {
                key: "type",
                header: "TYPE",
                align: "right",
                render: (w) => (
                  <Badge
                    label={w.isContract ? "CONTRACT" : "ADDRESS"}
                    color={w.isContract ? C.secondary : C.textSecondary}
                  />
                ),
              },
            ]}
            data={results.addresses}
            keyFn={(w) => w.address}
            onRowClick={(w) => navigate("wallet", { id: w.address })}
          />
        </Panel>
      )}

      {/* Contracts */}
      {results.contracts.length > 0 && (
        <Panel>
          <SectionHeader
            title={`CONTRACTS (${results.contracts.length})`}
            action={<Code size={14} style={{ color: C.secondary }} />}
          />
          <DataTable<QVMContract>
            columns={[
              {
                key: "address",
                header: "ADDRESS",
                render: (c) => <HashLink hash={c.address} type="contract" truncLen={8} />,
              },
              {
                key: "name",
                header: "NAME",
                render: (c) => (
                  <span style={{ color: C.textPrimary, fontFamily: FONT.body }}>{c.name}</span>
                ),
              },
              {
                key: "standard",
                header: "STANDARD",
                render: (c) => <Badge label={c.standard} color={C.primary} />,
              },
              {
                key: "balance",
                header: "BALANCE",
                align: "right",
                render: (c) => <span style={{ color: C.success }}>{formatQBC(c.balance)}</span>,
              },
            ]}
            data={results.contracts}
            keyFn={(c) => c.address}
          />
        </Panel>
      )}
    </div>
  );
}
