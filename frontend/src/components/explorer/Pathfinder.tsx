"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Cross-Block Pathfinder
   ───────────────────────────────────────────────────────────────────────── */

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Compass, ArrowRight, Search, RotateCcw } from "lucide-react";
import { usePathfinder } from "./hooks";
import { useExplorerStore } from "./store";
import {
  C, FONT, Badge, HashLink, Panel, SectionHeader, formatQBC, truncHash,
} from "./shared";

export function PathfinderView() {
  const navigate = useExplorerStore((s) => s.navigate);
  const [fromAddr, setFromAddr] = useState("");
  const [toAddr, setToAddr] = useState("");
  const [submitted, setSubmitted] = useState<{ from: string; to: string } | null>(null);

  const { data: result, isLoading } = usePathfinder(submitted?.from, submitted?.to);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (fromAddr.trim() && toAddr.trim()) {
        setSubmitted({ from: fromAddr.trim(), to: toAddr.trim() });
      }
    },
    [fromAddr, toAddr]
  );

  const handleReset = useCallback(() => {
    setFromAddr("");
    setToAddr("");
    setSubmitted(null);
  }, []);

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <h1
          className="mb-1 text-lg font-bold tracking-widest"
          style={{ color: C.textPrimary, fontFamily: FONT.heading }}
        >
          CROSS-BLOCK PATHFINDER
        </h1>
        <p className="text-xs" style={{ color: C.textSecondary, fontFamily: FONT.body }}>
          Trace transaction paths between any two addresses across the blockchain
        </p>
      </motion.div>

      {/* Search Form */}
      <Panel>
        <form onSubmit={handleSearch} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label
                className="mb-1 block text-[10px] uppercase tracking-widest"
                style={{ color: C.textMuted, fontFamily: FONT.heading }}
              >
                Source Address
              </label>
              <input
                type="text"
                value={fromAddr}
                onChange={(e) => setFromAddr(e.target.value)}
                placeholder="qbc1..."
                className="w-full rounded-md border px-3 py-2 text-xs outline-none"
                style={{
                  background: C.surfaceLight,
                  borderColor: C.border,
                  color: C.textPrimary,
                  fontFamily: FONT.mono,
                }}
              />
            </div>
            <div>
              <label
                className="mb-1 block text-[10px] uppercase tracking-widest"
                style={{ color: C.textMuted, fontFamily: FONT.heading }}
              >
                Destination Address
              </label>
              <input
                type="text"
                value={toAddr}
                onChange={(e) => setToAddr(e.target.value)}
                placeholder="qbc1..."
                className="w-full rounded-md border px-3 py-2 text-xs outline-none"
                style={{
                  background: C.surfaceLight,
                  borderColor: C.border,
                  color: C.textPrimary,
                  fontFamily: FONT.mono,
                }}
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={!fromAddr.trim() || !toAddr.trim() || isLoading}
              className="flex items-center gap-2 rounded-md px-4 py-2 text-xs font-bold transition-opacity hover:opacity-90 disabled:opacity-40"
              style={{
                background: C.primary,
                color: C.bg,
                fontFamily: FONT.heading,
              }}
            >
              <Search size={12} />
              FIND PATH
            </button>
            {submitted && (
              <button
                type="button"
                onClick={handleReset}
                className="flex items-center gap-1 rounded-md border px-3 py-2 text-xs transition-opacity hover:opacity-80"
                style={{ borderColor: C.border, color: C.textSecondary, fontFamily: FONT.body }}
              >
                <RotateCcw size={12} />
                Reset
              </button>
            )}
          </div>
        </form>
      </Panel>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div
            className="h-8 w-8 animate-spin rounded-full border-2"
            style={{ borderColor: C.border, borderTopColor: C.primary }}
          />
        </div>
      )}

      {/* Results */}
      {submitted && !isLoading && result && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <Panel>
            <SectionHeader title="PATH FOUND" />
            <div className="mb-4 flex flex-wrap items-center gap-3 text-xs" style={{ fontFamily: FONT.mono }}>
              <Badge label={`${result.path.length - 1} HOPS`} color={C.primary} />
              <Badge label={`${formatQBC(result.totalValue)} QBC`} color={C.success} />
              <Badge
                label={`BLOCKS ${result.blockRange[0]}–${result.blockRange[1]}`}
                color={C.secondary}
              />
            </div>

            {/* Path Visualization */}
            <div className="space-y-2">
              {result.path.map((addr, i) => (
                <div key={`${addr}-${i}`} className="flex items-center gap-2">
                  {/* Step indicator */}
                  <div className="flex flex-col items-center">
                    <div
                      className="flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold"
                      style={{
                        background:
                          i === 0
                            ? `${C.primary}20`
                            : i === result.path.length - 1
                              ? `${C.success}20`
                              : `${C.border}60`,
                        color:
                          i === 0
                            ? C.primary
                            : i === result.path.length - 1
                              ? C.success
                              : C.textSecondary,
                      }}
                    >
                      {i + 1}
                    </div>
                    {i < result.path.length - 1 && (
                      <div className="h-4 w-px" style={{ background: C.border }} />
                    )}
                  </div>

                  {/* Address */}
                  <div className="flex items-center gap-2">
                    <HashLink hash={addr} type="wallet" truncLen={14} />
                    {i === 0 && <Badge label="SOURCE" color={C.primary} />}
                    {i === result.path.length - 1 && <Badge label="DESTINATION" color={C.success} />}
                  </div>

                  {/* Arrow */}
                  {i < result.path.length - 1 && (
                    <ArrowRight size={12} style={{ color: C.textMuted }} />
                  )}
                </div>
              ))}
            </div>
          </Panel>
        </motion.div>
      )}

      {/* No path found */}
      {submitted && !isLoading && !result && (
        <Panel>
          <div className="flex flex-col items-center gap-3 py-8">
            <Compass size={36} style={{ color: C.textMuted }} />
            <p style={{ color: C.textSecondary, fontFamily: FONT.body }}>
              No path found between these addresses
            </p>
            <p className="text-xs" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
              Maximum search depth: 6 hops
            </p>
          </div>
        </Panel>
      )}

      {/* Instructions */}
      {!submitted && (
        <Panel>
          <div className="space-y-3 py-4 text-center">
            <Compass size={36} className="mx-auto" style={{ color: `${C.primary}60` }} />
            <p className="text-sm" style={{ color: C.textSecondary, fontFamily: FONT.body }}>
              Enter two addresses to find the shortest transaction path between them
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              <Badge label="BFS ALGORITHM" color={C.primary} />
              <Badge label="MAX 6 HOPS" color={C.secondary} />
              <Badge label="UTXO GRAPH" color={C.accent} />
            </div>
          </div>
        </Panel>
      )}
    </div>
  );
}
