"use client";

import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";

const RPC_URL = process.env.NEXT_PUBLIC_RPC_URL ?? "http://localhost:5000";

interface FinalityData {
  enabled: boolean;
  last_finalized_height: number;
  current_height: number;
  is_current_finalized: boolean;
  voted_stake: number;
  total_stake: number;
  vote_ratio: number;
  threshold: number;
  voter_count: number;
  validator_count: number;
}

async function fetchFinalityStatus(): Promise<FinalityData> {
  const res = await fetch(`${RPC_URL}/finality/status`);
  if (!res.ok) throw new Error("Failed to fetch finality status");
  return res.json();
}

/**
 * Finality Status dashboard panel — shows BFT finality information.
 */
export function FinalityStatus() {
  const { data, isError } = useQuery({
    queryKey: ["finalityStatus"],
    queryFn: fetchFinalityStatus,
    refetchInterval: 10_000,
    retry: false,
  });

  if (isError || !data) {
    return (
      <Card>
        <h3 className="text-sm font-semibold text-text-secondary">
          BFT Finality
        </h3>
        <p className="mt-2 text-xs text-text-secondary">
          Finality gadget not available
        </p>
      </Card>
    );
  }

  const ratioPercent = (data.vote_ratio * 100).toFixed(1);
  const thresholdPercent = (data.threshold * 100).toFixed(1);

  return (
    <Card glow={data.is_current_finalized ? "green" : undefined}>
      <h3 className="text-sm font-semibold text-text-secondary">
        BFT Finality
      </h3>
      <div className="mt-3 space-y-2">
        <div className="flex justify-between">
          <span className="text-xs text-text-secondary">Last Finalized</span>
          <span className="font-[family-name:var(--font-code)] text-sm font-bold text-quantum-green">
            #{data.last_finalized_height.toLocaleString()}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-xs text-text-secondary">Validators</span>
          <span className="font-[family-name:var(--font-code)] text-sm">
            {data.validator_count}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-xs text-text-secondary">Total Stake</span>
          <span className="font-[family-name:var(--font-code)] text-sm">
            {data.total_stake.toLocaleString()} QBC
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-xs text-text-secondary">Vote Ratio</span>
          <span className="font-[family-name:var(--font-code)] text-sm">
            {ratioPercent}% / {thresholdPercent}%
          </span>
        </div>

        {/* Progress bar */}
        <div className="mt-1 h-1.5 w-full rounded-full bg-bg-deep">
          <div
            className={`h-full rounded-full transition-all ${
              data.vote_ratio >= data.threshold
                ? "bg-quantum-green"
                : "bg-amber-500"
            }`}
            style={{ width: `${Math.min(data.vote_ratio * 100, 100)}%` }}
          />
        </div>
      </div>
    </Card>
  );
}
