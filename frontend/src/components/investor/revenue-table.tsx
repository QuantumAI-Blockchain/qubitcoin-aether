"use client";

import type { RevenueInfo } from "@/lib/investor-api";

export function RevenueTable({ revenue }: { revenue: RevenueInfo | null }) {
  if (!revenue) {
    return (
      <div className="rounded-xl border border-border-subtle bg-bg-panel p-6 text-center text-text-secondary">
        Loading revenue data...
      </div>
    );
  }

  const pending = parseFloat(revenue.pending);

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
      <h3 className="mb-4 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-text-secondary">
        Revenue Share
      </h3>

      <div className="mb-4 grid grid-cols-3 gap-3">
        <div className="rounded-lg bg-white/5 p-3 text-center">
          <div className="text-xs text-text-secondary">Your Share</div>
          <div className="font-mono text-sm font-bold text-glow-gold">
            {revenue.share_percentage.toFixed(2)}%
          </div>
          <div className="text-xs text-text-secondary">of investor pool</div>
        </div>
        <div className="rounded-lg bg-white/5 p-3 text-center">
          <div className="text-xs text-text-secondary">Total Claimed</div>
          <div className="font-mono text-sm text-text-primary">
            {parseFloat(revenue.total_claimed).toLocaleString(undefined, { maximumFractionDigits: 2 })} QBC
          </div>
        </div>
        <div className="rounded-lg bg-green-500/10 p-3 text-center">
          <div className="text-xs text-green-400">Pending</div>
          <div className="font-mono text-sm font-bold text-green-400">
            {pending.toLocaleString(undefined, { maximumFractionDigits: 2 })} QBC
          </div>
        </div>
      </div>

      <button
        disabled={pending <= 0}
        className="w-full rounded-lg bg-gradient-to-r from-glow-gold to-amber-500 py-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-bg-deep transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {pending > 0 ? "Claim Revenue" : "No Pending Revenue"}
      </button>

      <p className="mt-3 text-xs text-text-secondary">
        10% of all protocol fees flow to the investor revenue pool. Your share is proportional to your investment.
      </p>
    </div>
  );
}
