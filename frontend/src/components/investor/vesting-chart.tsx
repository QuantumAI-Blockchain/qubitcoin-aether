"use client";

import type { VestingInfo } from "@/lib/investor-api";

export function VestingChart({ vesting }: { vesting: VestingInfo | null }) {
  if (!vesting) {
    return (
      <div className="rounded-xl border border-border-subtle bg-bg-panel p-6 text-center text-text-secondary">
        Loading vesting data...
      </div>
    );
  }

  const fraction = vesting.vested_fraction;
  const cliffPct = (180 / (180 + 720)) * 100; // cliff as % of total schedule
  const progressPct = vesting.tge_set ? Math.min(100, fraction * 100) : 0;
  const inCliff = vesting.tge_set && fraction === 0;

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
      <h3 className="mb-4 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-text-secondary">
        Vesting Schedule
      </h3>

      {/* Timeline visualization */}
      <div className="mb-6">
        <div className="relative h-3 overflow-hidden rounded-full bg-white/10">
          {/* Cliff zone */}
          <div
            className="absolute inset-y-0 left-0 border-r border-amber-400/60 bg-amber-500/15"
            style={{ width: `${cliffPct}%` }}
          />
          {/* Progress */}
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-glow-cyan to-green-400 transition-all duration-700"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <div className="mt-1 flex justify-between text-xs text-text-secondary">
          <span>TGE</span>
          <span style={{ position: "relative", left: `${cliffPct - 50}%` }}>
            6mo Cliff
          </span>
          <span>30mo Full Vest</span>
        </div>
      </div>

      {/* Status */}
      <div className="mb-4 rounded-lg bg-white/5 p-3">
        <div className="text-xs text-text-secondary">Status</div>
        <div className="text-sm font-bold">
          {!vesting.tge_set ? (
            <span className="text-amber-400">TGE Not Set — Preview Mode</span>
          ) : inCliff ? (
            <span className="text-amber-400">IN CLIFF PERIOD</span>
          ) : fraction >= 1 ? (
            <span className="text-green-400">FULLY VESTED</span>
          ) : (
            <span className="text-glow-cyan">
              {(fraction * 100).toFixed(1)}% VESTED
            </span>
          )}
        </div>
      </div>

      {/* Amounts */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-white/5 p-3">
          <div className="text-xs text-text-secondary">Total QBC</div>
          <div className="font-mono text-sm font-bold text-text-primary">
            {parseFloat(vesting.total_qbc).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
        </div>
        <div className="rounded-lg bg-white/5 p-3">
          <div className="text-xs text-text-secondary">Vested QBC</div>
          <div className="font-mono text-sm font-bold text-glow-cyan">
            {parseFloat(vesting.vested_qbc).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
        </div>
        <div className="rounded-lg bg-white/5 p-3">
          <div className="text-xs text-text-secondary">Claimed QBC</div>
          <div className="font-mono text-sm text-text-primary">
            {parseFloat(vesting.claimed_qbc).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
        </div>
        <div className="rounded-lg bg-white/5 p-3">
          <div className="text-xs text-text-secondary">Claimable QBC</div>
          <div className="font-mono text-sm font-bold text-green-400">
            {parseFloat(vesting.claimable_qbc).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
        </div>
      </div>
    </div>
  );
}
