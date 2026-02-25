"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — QVM Contract Explorer
   ───────────────────────────────────────────────────────────────────────── */

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { Cpu, Code, Database, Search } from "lucide-react";
import { useContracts, useNetworkStats } from "./hooks";
import { useExplorerStore } from "./store";
import {
  C, FONT, Badge, DataTable, HashLink, LoadingSpinner, Panel,
  SectionHeader, StatCard, Pagination, formatNumber, formatQBC, truncHash,
} from "./shared";
import type { QVMContract } from "./types";

const PAGE_SIZE = 20;

function standardColor(std: string): string {
  switch (std) {
    case "QBC-20": return C.primary;
    case "QBC-721": return C.secondary;
    case "QBC-1155": return C.accent;
    case "ERC-20-QC": return C.success;
    default: return C.textSecondary;
  }
}

export function QVMExplorerView() {
  const navigate = useExplorerStore((s) => s.navigate);
  const { data: contracts, isLoading } = useContracts();
  const { data: stats } = useNetworkStats();
  const [page, setPage] = useState(0);
  const [filter, setFilter] = useState("");
  const [sortBy, setSortBy] = useState<"txCount" | "balance" | "bytecodeSize">("txCount");

  const filtered = useMemo(() => {
    let list = contracts ?? [];
    if (filter) {
      const q = filter.toLowerCase();
      list = list.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.address.toLowerCase().includes(q) ||
          c.standard.toLowerCase().includes(q)
      );
    }
    list = [...list].sort((a, b) => b[sortBy] - a[sortBy]);
    return list;
  }, [contracts, filter, sortBy]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageData = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  // Standard distribution
  const standardCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const c of contracts ?? []) {
      counts[c.standard] = (counts[c.standard] ?? 0) + 1;
    }
    return counts;
  }, [contracts]);

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <h1
          className="mb-1 text-lg font-bold tracking-widest"
          style={{ color: C.textPrimary, fontFamily: FONT.heading }}
        >
          QVM CONTRACTS
        </h1>
        <p className="text-xs" style={{ color: C.textSecondary, fontFamily: FONT.body }}>
          Quantum Virtual Machine — 167 opcodes (155 EVM + 10 quantum + 2 AGI)
        </p>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Total Contracts"
          value={formatNumber(stats?.totalContracts ?? 0)}
          icon={Cpu}
          color={C.primary}
        />
        <StatCard
          label="Gas Limit / Block"
          value="30M"
          icon={Database}
          color={C.accent}
        />
        <StatCard
          label="Opcodes"
          value="167"
          sub="155 EVM + 10 QTM + 2 AGI"
          icon={Code}
          color={C.secondary}
        />
        <StatCard
          label="Standards"
          value={Object.keys(standardCounts).length}
          color={C.success}
        />
      </div>

      {/* Standard Distribution */}
      <Panel>
        <SectionHeader title="CONTRACT STANDARDS" />
        <div className="flex flex-wrap gap-3">
          {Object.entries(standardCounts)
            .sort(([, a], [, b]) => b - a)
            .map(([std, count]) => (
              <div
                key={std}
                className="flex items-center gap-2 rounded-md border px-3 py-2"
                style={{ borderColor: `${standardColor(std)}30`, background: `${standardColor(std)}08` }}
              >
                <Badge label={std} color={standardColor(std)} />
                <span className="text-xs font-bold" style={{ color: C.textPrimary, fontFamily: FONT.mono }}>
                  {count}
                </span>
              </div>
            ))}
        </div>
      </Panel>

      {/* Filters */}
      <Panel>
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search
              size={12}
              className="absolute left-2.5 top-1/2 -translate-y-1/2"
              style={{ color: C.textMuted }}
            />
            <input
              type="text"
              value={filter}
              onChange={(e) => { setFilter(e.target.value); setPage(0); }}
              placeholder="Search contracts…"
              className="rounded-md border py-1.5 pl-7 pr-3 text-xs outline-none"
              style={{
                background: C.surfaceLight,
                borderColor: C.border,
                color: C.textPrimary,
                fontFamily: FONT.mono,
                width: 220,
              }}
            />
          </div>
          <div className="flex items-center gap-1 text-[10px]" style={{ fontFamily: FONT.heading, color: C.textMuted }}>
            SORT:
            {(["txCount", "balance", "bytecodeSize"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSortBy(s)}
                className="rounded px-2 py-1 transition-colors"
                style={{
                  color: sortBy === s ? C.primary : C.textSecondary,
                  background: sortBy === s ? `${C.primary}15` : "transparent",
                }}
              >
                {s === "txCount" ? "TX COUNT" : s === "balance" ? "BALANCE" : "SIZE"}
              </button>
            ))}
          </div>
        </div>
      </Panel>

      {/* Contract Table */}
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
              <span style={{ color: C.textPrimary, fontFamily: FONT.body, fontSize: "0.7rem" }}>
                {c.name}
              </span>
            ),
          },
          {
            key: "standard",
            header: "STANDARD",
            render: (c) => <Badge label={c.standard} color={standardColor(c.standard)} />,
          },
          {
            key: "txCount",
            header: "TXS",
            align: "right",
            render: (c) => <span style={{ color: C.textPrimary }}>{formatNumber(c.txCount)}</span>,
          },
          {
            key: "balance",
            header: "BALANCE",
            align: "right",
            render: (c) => <span style={{ color: C.success }}>{formatQBC(c.balance)}</span>,
          },
          {
            key: "size",
            header: "SIZE",
            align: "right",
            render: (c) => (
              <span style={{ color: C.textSecondary }}>
                {(c.bytecodeSize / 1024).toFixed(1)}KB
              </span>
            ),
          },
          {
            key: "deployHeight",
            header: "DEPLOYED",
            align: "right",
            render: (c) => (
              <HashLink hash={String(c.deployHeight)} type="block" truncLen={10} />
            ),
          },
        ]}
        data={pageData}
        keyFn={(c) => c.address}
      />

      {totalPages > 1 && (
        <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
      )}
    </div>
  );
}
