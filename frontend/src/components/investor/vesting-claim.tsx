"use client";

import type { VestingInfo } from "@/lib/investor-api";

export function VestingClaim({ vesting }: { vesting: VestingInfo | null }) {
  if (!vesting) return null;

  const claimableQBC = parseFloat(vesting.claimable_qbc);
  const claimableQUSD = parseFloat(vesting.claimable_qusd);
  const hasClaimable = claimableQBC > 0 || claimableQUSD > 0;

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
      <h3 className="mb-4 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-text-secondary">
        Claim Vested Tokens
      </h3>

      <div className="mb-4 grid grid-cols-3 gap-3">
        <div className="rounded-lg bg-white/5 p-3 text-center">
          <div className="text-xs text-text-secondary">Vested</div>
          <div className="font-mono text-sm font-bold text-text-primary">
            {parseFloat(vesting.vested_qbc).toLocaleString(undefined, { maximumFractionDigits: 0 })} QBC
          </div>
        </div>
        <div className="rounded-lg bg-white/5 p-3 text-center">
          <div className="text-xs text-text-secondary">Claimed</div>
          <div className="font-mono text-sm text-text-primary">
            {parseFloat(vesting.claimed_qbc).toLocaleString(undefined, { maximumFractionDigits: 0 })} QBC
          </div>
        </div>
        <div className="rounded-lg bg-green-500/10 p-3 text-center">
          <div className="text-xs text-green-400">Claimable</div>
          <div className="font-mono text-sm font-bold text-green-400">
            {claimableQBC.toLocaleString(undefined, { maximumFractionDigits: 0 })} QBC
          </div>
        </div>
      </div>

      {claimableQUSD > 0 && (
        <div className="mb-4 rounded-lg bg-white/5 p-3 text-center">
          <div className="text-xs text-text-secondary">QUSD Claimable</div>
          <div className="font-mono text-sm font-bold text-glow-gold">
            {claimableQUSD.toLocaleString(undefined, { maximumFractionDigits: 0 })} QUSD
          </div>
        </div>
      )}

      <button
        disabled={!hasClaimable}
        className="w-full rounded-lg bg-gradient-to-r from-green-500 to-glow-cyan py-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-bg-deep transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {hasClaimable ? "Claim Tokens" : "Nothing to Claim"}
      </button>

      {!vesting.tge_set && (
        <p className="mt-3 text-xs text-amber-400">
          TGE has not occurred yet. Claiming will be available after the Token Generation Event.
        </p>
      )}
    </div>
  );
}
