"use client";
/* ---------------------------------------------------------------------------
   QBC Bridge — History View (past wrap/unwrap operations)
   --------------------------------------------------------------------------- */

import { useState, useMemo, useCallback, memo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Download,
  Filter,
  Search,
  Shield,
  Clock,
} from "lucide-react";
import { CHAINS, EXTERNAL_CHAINS, getExplorerTxUrl } from "./chain-config";
import { useBridgeStore } from "./store";
import { useFilteredHistory } from "./hooks";
import {
  B,
  FONT,
  Panel,
  SectionHeader,
  WTokenLabel,
  TokenBadge,
  ChainBadge,
  CopyButton,
  HashDisplay,
  GlowButton,
  StatusBadge,
  AnimatedNumber,
  OperationBadge,
  ExtLink,
  Skeleton,
  truncAddr,
  formatAmount,
  formatPct,
  formatDuration,
  timeAgo,
  panelStyle,
  statusColor,
} from "./shared";
import type {
  BridgeTx,
  BridgeStatus,
  ExternalChainId,
  OperationType,
  TokenType,
} from "./types";
import type { HistoryFilters } from "./hooks";

/* ── Constants ───────────────────────────────────────────────────────────── */

const PAGE_SIZE = 20;

/* ── Summary Stat Card ───────────────────────────────────────────────────── */

const StatCard = memo(function StatCard({
  label,
  value,
  decimals,
  suffix,
  color,
}: {
  label: string;
  value: number;
  decimals?: number;
  suffix?: string;
  color: string;
}) {
  return (
    <div
      className="flex flex-col gap-1 rounded-xl border px-4 py-3"
      style={{
        ...panelStyle,
        borderColor: `${color}25`,
        background: `${B.bgPanel}`,
      }}
    >
      <span
        className="text-[9px] font-bold uppercase tracking-[0.15em]"
        style={{ color: B.textSecondary, fontFamily: FONT.display }}
      >
        {label}
      </span>
      <AnimatedNumber
        value={value}
        decimals={decimals ?? 2}
        suffix={suffix}
        color={color}
        size="text-lg"
      />
    </div>
  );
});

/* ── Filter Bar ──────────────────────────────────────────────────────────── */

interface FilterBarProps {
  filters: HistoryFilters;
  onFilterChange: (patch: Partial<HistoryFilters>) => void;
}

function FilterBar({ filters, onFilterChange }: FilterBarProps) {
  const selectStyle: React.CSSProperties = {
    background: B.bgBase,
    borderColor: B.borderSubtle,
    color: B.textPrimary,
    fontFamily: FONT.mono,
    fontSize: "0.625rem",
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Filter size={12} style={{ color: B.textSecondary }} />
      <span
        className="text-[9px] font-bold uppercase tracking-[0.15em]"
        style={{ color: B.textSecondary, fontFamily: FONT.display }}
      >
        Filters
      </span>

      {/* Operation */}
      <select
        value={filters.operation ?? ""}
        onChange={(e) =>
          onFilterChange({
            operation: (e.target.value as OperationType) || undefined,
          })
        }
        className="rounded border px-2 py-1"
        style={selectStyle}
      >
        <option value="">ALL OPS</option>
        <option value="wrap">WRAP</option>
        <option value="unwrap">UNWRAP</option>
      </select>

      {/* Chain */}
      <select
        value={filters.chain ?? ""}
        onChange={(e) =>
          onFilterChange({
            chain: (e.target.value as ExternalChainId) || undefined,
          })
        }
        className="rounded border px-2 py-1"
        style={selectStyle}
      >
        <option value="">ALL CHAINS</option>
        {EXTERNAL_CHAINS.map((c) => (
          <option key={c} value={c}>
            {CHAINS[c].shortName}
          </option>
        ))}
      </select>

      {/* Token */}
      <select
        value={filters.token ?? ""}
        onChange={(e) =>
          onFilterChange({
            token: (e.target.value as TokenType) || undefined,
          })
        }
        className="rounded border px-2 py-1"
        style={selectStyle}
      >
        <option value="">ALL TOKENS</option>
        <option value="QBC">QBC</option>
        <option value="QUSD">QUSD</option>
      </select>

      {/* Status */}
      <select
        value={filters.status ?? ""}
        onChange={(e) =>
          onFilterChange({
            status: (e.target.value as BridgeStatus) || undefined,
          })
        }
        className="rounded border px-2 py-1"
        style={selectStyle}
      >
        <option value="">ALL STATUS</option>
        <option value="complete">COMPLETE</option>
        <option value="pending">PENDING</option>
        <option value="failed">FAILED</option>
        <option value="refunded">REFUNDED</option>
      </select>
    </div>
  );
}

/* ── Expanded Row Detail ─────────────────────────────────────────────────── */

function ExpandedDetail({ tx }: { tx: BridgeTx }) {
  return (
    <motion.tr
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
    >
      <td colSpan={10} style={{ padding: 0 }}>
        <div
          className="border-t px-4 py-3"
          style={{ borderColor: `${B.borderSubtle}60`, background: B.bgBase }}
        >
          <div className="grid gap-4 md:grid-cols-2">
            {/* Quantum Bridge Proof */}
            <div className="space-y-2">
              <div className="flex items-center gap-1.5">
                <Shield size={12} style={{ color: B.glowViolet }} />
                <span
                  className="text-[10px] font-bold uppercase tracking-[0.15em]"
                  style={{
                    color: B.glowViolet,
                    fontFamily: FONT.display,
                  }}
                >
                  Quantum Bridge Proof
                </span>
              </div>

              <div className="space-y-1 text-[10px]" style={{ fontFamily: FONT.mono }}>
                <div className="flex items-center gap-2">
                  <span style={{ color: B.textSecondary }}>Dilithium Sig:</span>
                  <HashDisplay hash={tx.dilithiumSig} truncLen={10} />
                  <CopyButton text={tx.dilithiumSig} size={10} />
                </div>
                <div className="flex items-center gap-2">
                  <span style={{ color: B.textSecondary }}>Cross-chain Msg:</span>
                  <HashDisplay hash={tx.crossChainMsgHash} truncLen={10} />
                  <CopyButton text={tx.crossChainMsgHash} size={10} />
                </div>
                <div className="flex items-center gap-2">
                  <span style={{ color: B.textSecondary }}>SUSY Alignment:</span>
                  <span style={{ color: B.glowEmerald }}>
                    {(tx.susyAlignmentAtOp * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span style={{ color: B.textSecondary }}>Relay Node:</span>
                  <span style={{ color: B.glowCyan }}>{tx.aetherRelayNodeId}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span style={{ color: B.textSecondary }}>Protocol:</span>
                  <span style={{ color: B.textPrimary }}>{tx.bridgeProtocolVersion}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span style={{ color: B.textSecondary }}>Src Confirmations:</span>
                  <span style={{ color: B.textPrimary }}>
                    {tx.confirmations.source}/{tx.confirmations.sourceRequired}
                  </span>
                </div>
                {tx.confirmations.destination !== null && (
                  <div className="flex items-center gap-2">
                    <span style={{ color: B.textSecondary }}>Dest Confirmations:</span>
                    <span style={{ color: B.textPrimary }}>
                      {tx.confirmations.destination}/{tx.confirmations.destinationRequired}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Event Log */}
            <div className="space-y-2">
              <div className="flex items-center gap-1.5">
                <Clock size={12} style={{ color: B.glowCyan }} />
                <span
                  className="text-[10px] font-bold uppercase tracking-[0.15em]"
                  style={{
                    color: B.glowCyan,
                    fontFamily: FONT.display,
                  }}
                >
                  Event Log
                </span>
              </div>

              <div className="space-y-1.5">
                {tx.eventLog.map((event, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 text-[10px]"
                    style={{ fontFamily: FONT.mono }}
                  >
                    <span
                      className="mt-0.5 shrink-0"
                      style={{ color: B.textSecondary }}
                    >
                      {new Date(event.timestamp * 1000)
                        .toLocaleTimeString("en-US", { hour12: false })}
                    </span>
                    <span style={{ color: B.textPrimary }}>{event.message}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </td>
    </motion.tr>
  );
}

/* ── Transaction Row ─────────────────────────────────────────────────────── */

const TxRow = memo(function TxRow({
  tx,
  expanded,
  onToggle,
}: {
  tx: BridgeTx;
  expanded: boolean;
  onToggle: () => void;
}) {
  const isWrap = tx.operation === "wrap";
  const externalChain = isWrap ? tx.destinationChain : tx.sourceChain;
  const wrapped: "wQBC" | "wQUSD" = tx.token === "QBC" ? "wQBC" : "wQUSD";
  const isPending = tx.status === "pending";

  const sourceChainInfo = CHAINS[tx.sourceChain];
  const destChainInfo = CHAINS[tx.destinationChain];

  return (
    <>
      <motion.tr
        layout
        onClick={onToggle}
        className="cursor-pointer transition-colors"
        style={{
          borderBottom: `1px solid ${B.borderSubtle}40`,
          background: isPending ? `${B.glowAmber}05` : "transparent",
        }}
        whileHover={{ backgroundColor: `${B.bgElevated}` }}
      >
        {/* Date */}
        <td className="px-3 py-2.5">
          <div className="space-y-0.5">
            <div
              className="text-[10px]"
              style={{ color: B.textPrimary, fontFamily: FONT.mono }}
            >
              {new Date(tx.initiatedAt * 1000).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
              })}
            </div>
            <div className="text-[9px]" style={{ color: B.textSecondary, fontFamily: FONT.mono }}>
              {timeAgo(tx.initiatedAt)}
            </div>
          </div>
        </td>

        {/* Operation */}
        <td className="px-3 py-2.5">
          <OperationBadge operation={tx.operation} size="sm" />
        </td>

        {/* Chain */}
        <td className="px-3 py-2.5">
          <ChainBadge chain={externalChain} showStatus />
        </td>

        {/* Token flow */}
        <td className="px-3 py-2.5">
          <div
            className="flex items-center gap-1 text-[10px]"
            style={{ fontFamily: FONT.mono }}
          >
            {isWrap ? (
              <>
                <span style={{ color: B.glowCyan }}>{tx.token}</span>
                <span style={{ color: B.textSecondary }}>{"->"}</span>
                <WTokenLabel token={wrapped} />
              </>
            ) : (
              <>
                <WTokenLabel token={wrapped} />
                <span style={{ color: B.textSecondary }}>{"->"}</span>
                <span style={{ color: B.glowCyan }}>{tx.token}</span>
              </>
            )}
          </div>
        </td>

        {/* Sent */}
        <td
          className="px-3 py-2.5 text-right text-[10px]"
          style={{ color: B.textPrimary, fontFamily: FONT.mono }}
        >
          {formatAmount(tx.amountSent)}
        </td>

        {/* Received */}
        <td
          className="px-3 py-2.5 text-right text-[10px]"
          style={{
            color: isWrap ? B.glowGold : B.glowCyan,
            fontFamily: FONT.mono,
          }}
        >
          {formatAmount(tx.amountReceived)}
        </td>

        {/* Fee */}
        <td
          className="px-3 py-2.5 text-right text-[10px]"
          style={{ color: B.glowAmber, fontFamily: FONT.mono }}
        >
          {formatAmount(tx.totalFee, 4)}
          <div className="text-[8px]" style={{ color: B.textSecondary }}>
            {formatPct(tx.totalFeePercent)}
          </div>
        </td>

        {/* Time */}
        <td
          className="px-3 py-2.5 text-right text-[10px]"
          style={{ color: B.textSecondary, fontFamily: FONT.mono }}
        >
          {tx.bridgeTimeSeconds !== null
            ? formatDuration(tx.bridgeTimeSeconds)
            : isPending
              ? "..."
              : "--"}
        </td>

        {/* Status */}
        <td className="px-3 py-2.5">
          {isPending ? (
            <motion.div
              animate={{
                boxShadow: [
                  `0 0 4px ${B.glowAmber}40`,
                  `0 0 12px ${B.glowAmber}80`,
                  `0 0 4px ${B.glowAmber}40`,
                ],
              }}
              transition={{ duration: 2, repeat: Infinity }}
              className="inline-block rounded"
            >
              <StatusBadge status={tx.status} />
            </motion.div>
          ) : (
            <StatusBadge status={tx.status} />
          )}
        </td>

        {/* Links */}
        <td className="px-3 py-2.5">
          <div className="flex items-center gap-1.5">
            <CopyButton text={tx.sourceTxHash} size={10} />
            <ExtLink
              href={getExplorerTxUrl(sourceChainInfo, tx.sourceTxHash)}
              label="Src"
            />
            {tx.destinationTxHash && (
              <>
                <span style={{ color: B.textSecondary }}>|</span>
                <CopyButton text={tx.destinationTxHash} size={10} />
                <ExtLink
                  href={getExplorerTxUrl(destChainInfo, tx.destinationTxHash)}
                  label="Dst"
                />
              </>
            )}
            {/* Expand chevron */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggle();
              }}
              className="ml-1 rounded p-0.5 transition-opacity hover:opacity-80"
              style={{ color: B.textSecondary }}
            >
              {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
          </div>
        </td>
      </motion.tr>

      <AnimatePresence>{expanded && <ExpandedDetail tx={tx} />}</AnimatePresence>
    </>
  );
});

/* ── CSV Export ───────────────────────────────────────────────────────────── */

function generateCsv(txs: BridgeTx[]): string {
  const header =
    "ID,Date,Operation,Token,Source Chain,Dest Chain,Sent,Received,Protocol Fee,Relayer Fee,Dest Gas,Total Fee,Fee %,Time (s),Status,Source Tx,Dest Tx";
  const rows = txs.map((tx) =>
    [
      tx.id,
      new Date(tx.initiatedAt * 1000).toISOString(),
      tx.operation,
      tx.token,
      tx.sourceChain,
      tx.destinationChain,
      tx.amountSent,
      tx.amountReceived,
      tx.protocolFee,
      tx.relayerFee,
      tx.destinationGasFee,
      tx.totalFee,
      tx.totalFeePercent,
      tx.bridgeTimeSeconds ?? "",
      tx.status,
      tx.sourceTxHash,
      tx.destinationTxHash ?? "",
    ].join(","),
  );
  return [header, ...rows].join("\n");
}

function downloadCsv(txs: BridgeTx[]): void {
  const csv = generateCsv(txs);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `qbc-bridge-history-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ── Pagination ──────────────────────────────────────────────────────────── */

function Pagination({
  page,
  totalPages,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  onPageChange: (p: number) => void;
}) {
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-center gap-2 pt-3">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page === 0}
        className="rounded border p-1.5 transition-opacity hover:opacity-80 disabled:opacity-30"
        style={{ borderColor: B.borderSubtle, color: B.textSecondary }}
      >
        <ChevronLeft size={14} />
      </button>

      <span
        className="text-[10px]"
        style={{ color: B.textSecondary, fontFamily: FONT.mono }}
      >
        {page + 1} / {totalPages}
      </span>

      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages - 1}
        className="rounded border p-1.5 transition-opacity hover:opacity-80 disabled:opacity-30"
        style={{ borderColor: B.borderSubtle, color: B.textSecondary }}
      >
        <ChevronRight size={14} />
      </button>
    </div>
  );
}

/* ── History View (Main Export) ───────────────────────────────────────────── */

export function HistoryView() {
  const [filters, setFilters] = useState<HistoryFilters>({});
  const [page, setPage] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: allTxs, isLoading } = useFilteredHistory(filters);

  const onFilterChange = useCallback((patch: Partial<HistoryFilters>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
    setPage(0);
  }, []);

  // Sort: pending first (amber pulse), then by date desc
  const sorted = useMemo(() => {
    if (!allTxs) return [];
    return [...allTxs].sort((a, b) => {
      if (a.status === "pending" && b.status !== "pending") return -1;
      if (a.status !== "pending" && b.status === "pending") return 1;
      return b.initiatedAt - a.initiatedAt;
    });
  }, [allTxs]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const paginated = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  // Summary stats from ALL transactions (unfiltered query result)
  const stats = useMemo(() => {
    if (!allTxs || allTxs.length === 0) {
      return {
        totalWrapped: 0,
        totalUnwrapped: 0,
        currentWqbc: 0,
        totalFees: 0,
        successRate: 0,
      };
    }

    const wraps = allTxs.filter((tx) => tx.operation === "wrap");
    const unwraps = allTxs.filter((tx) => tx.operation === "unwrap");
    const completed = allTxs.filter((tx) => tx.status === "complete");
    const totalWrapped = wraps.reduce((s, tx) => s + tx.amountSent, 0);
    const totalUnwrapped = unwraps.reduce((s, tx) => s + tx.amountSent, 0);
    const currentWqbc = totalWrapped - totalUnwrapped;
    const totalFees = allTxs.reduce((s, tx) => s + tx.totalFee, 0);
    const successRate =
      allTxs.length > 0 ? (completed.length / allTxs.length) * 100 : 0;

    return { totalWrapped, totalUnwrapped, currentWqbc, totalFees, successRate };
  }, [allTxs]);

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4">
      <SectionHeader
        title="BRIDGE HISTORY"
        action={
          <GlowButton
            onClick={() => allTxs && downloadCsv(allTxs)}
            variant="ghost"
            disabled={!allTxs || allTxs.length === 0}
            className="!h-7 !px-3 !text-[9px]"
          >
            <Download size={10} />
            EXPORT CSV
          </GlowButton>
        }
      />

      {/* Summary Stats */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatCard
          label="Total QBC Wrapped"
          value={stats.totalWrapped}
          suffix=" QBC"
          color={B.glowCyan}
        />
        <StatCard
          label="Total wQBC Unwrapped"
          value={stats.totalUnwrapped}
          suffix=" wQBC"
          color={B.glowGold}
        />
        <StatCard
          label="Current wQBC Held"
          value={stats.currentWqbc}
          suffix=" wQBC"
          color={B.glowViolet}
        />
        <StatCard
          label="Total Fees Paid"
          value={stats.totalFees}
          decimals={4}
          suffix=" QBC"
          color={B.glowAmber}
        />
        <StatCard
          label="Success Rate"
          value={stats.successRate}
          decimals={1}
          suffix="%"
          color={B.glowEmerald}
        />
      </div>

      {/* Filters */}
      <Panel>
        <FilterBar filters={filters} onFilterChange={onFilterChange} />
      </Panel>

      {/* Transaction Table */}
      <Panel style={{ padding: 0, overflow: "hidden" }}>
        {isLoading ? (
          <div className="space-y-3 p-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} width="100%" height={36} />
            ))}
          </div>
        ) : paginated.length === 0 ? (
          <div
            className="flex flex-col items-center gap-2 py-12"
            style={{ color: B.textSecondary, fontFamily: FONT.body }}
          >
            <Search size={24} />
            <span className="text-sm">No transactions match your filters</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full" style={{ borderCollapse: "collapse" }}>
              <thead>
                <tr
                  style={{
                    borderBottom: `1px solid ${B.borderSubtle}`,
                    background: B.bgBase,
                  }}
                >
                  {[
                    "DATE",
                    "OP",
                    "CHAIN",
                    "TOKEN",
                    "SENT",
                    "RECEIVED",
                    "FEE",
                    "TIME",
                    "STATUS",
                    "LINKS",
                  ].map((col) => (
                    <th
                      key={col}
                      className="px-3 py-2 text-left text-[9px] font-bold uppercase tracking-[0.15em]"
                      style={{
                        color: B.textSecondary,
                        fontFamily: FONT.display,
                      }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {paginated.map((tx) => (
                  <TxRow
                    key={tx.id}
                    tx={tx}
                    expanded={expandedId === tx.id}
                    onToggle={() =>
                      setExpandedId((prev) => (prev === tx.id ? null : tx.id))
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {sorted.length > PAGE_SIZE && (
          <div
            className="border-t px-4 py-2"
            style={{ borderColor: `${B.borderSubtle}60` }}
          >
            <div className="flex items-center justify-between">
              <span
                className="text-[10px]"
                style={{ color: B.textSecondary, fontFamily: FONT.mono }}
              >
                {sorted.length} transactions
              </span>
              <Pagination
                page={page}
                totalPages={totalPages}
                onPageChange={setPage}
              />
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}

export default HistoryView;
