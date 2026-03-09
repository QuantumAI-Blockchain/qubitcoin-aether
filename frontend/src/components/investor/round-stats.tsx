"use client";

import type { RoundInfo } from "@/lib/investor-api";

function formatUSD(val: string | number): string {
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n)) return "$0";
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return `$${n.toFixed(2)}`;
}

export function RoundStats({ round }: { round: RoundInfo | null }) {
  if (!round) {
    return (
      <div className="rounded-xl border border-border-subtle bg-bg-panel p-6 text-center text-text-secondary">
        Loading round info...
      </div>
    );
  }

  const price = parseFloat(round.token_price_usd);
  const endTime = new Date(round.end_time);
  const now = new Date();
  const remaining = Math.max(0, endTime.getTime() - now.getTime());
  const days = Math.floor(remaining / 86400000);
  const hours = Math.floor((remaining % 86400000) / 3600000);

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-[family-name:var(--font-display)] text-lg font-bold glow-gold">
          QUANTUM SEED ROUND
        </h2>
        {round.active && (
          <span className="rounded-full bg-green-500/20 px-3 py-1 text-xs font-medium text-green-400">
            LIVE
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <div className="text-xs text-text-secondary">Price</div>
          <div className="font-mono text-lg font-bold text-text-primary">
            ${price.toFixed(4)}
          </div>
          <div className="text-xs text-text-secondary">per QBC</div>
        </div>
        <div>
          <div className="text-xs text-text-secondary">Raised</div>
          <div className="font-mono text-lg font-bold text-glow-cyan">
            {formatUSD(round.total_raised_usd)}
          </div>
          <div className="text-xs text-text-secondary">
            of {formatUSD(round.hard_cap_usd)}
          </div>
        </div>
        <div>
          <div className="text-xs text-text-secondary">Investors</div>
          <div className="font-mono text-lg font-bold text-text-primary">
            {round.investors.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="text-xs text-text-secondary">Time Left</div>
          <div className="font-mono text-lg font-bold text-text-primary">
            {remaining > 0 ? `${days}d ${hours}h` : "Ended"}
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mt-4">
        <div className="mb-1 flex justify-between text-xs text-text-secondary">
          <span>{round.percent_filled.toFixed(1)}% filled</span>
          <span>{formatUSD(round.hard_cap_usd)} cap</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-gradient-to-r from-glow-cyan to-glow-gold transition-all duration-700"
            style={{ width: `${Math.min(100, round.percent_filled)}%` }}
          />
        </div>
      </div>
    </div>
  );
}
