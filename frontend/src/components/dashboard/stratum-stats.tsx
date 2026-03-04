"use client";

import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";

const RPC_URL = process.env.NEXT_PUBLIC_RPC_URL ?? "http://localhost:5000";

interface StratumData {
  connected_workers: number;
  total_shares: number;
  accepted_shares: number;
  rejected_shares: number;
  blocks_found: number;
  uptime_seconds: number;
}

async function fetchStratumStats(): Promise<StratumData> {
  const res = await fetch(`${RPC_URL}/stratum/stats`);
  if (!res.ok) throw new Error("Failed to fetch stratum stats");
  return res.json();
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

/**
 * Stratum Mining Stats dashboard panel — shows pool mining information.
 */
export function StratumStats() {
  const { data, isError } = useQuery({
    queryKey: ["stratumStats"],
    queryFn: fetchStratumStats,
    refetchInterval: 10_000,
    retry: false,
  });

  if (isError || !data) {
    return (
      <Card>
        <h3 className="text-sm font-semibold text-text-secondary">
          Stratum Pool
        </h3>
        <p className="mt-2 text-xs text-text-secondary">
          Stratum server not available
        </p>
      </Card>
    );
  }

  const acceptRate =
    data.total_shares > 0
      ? ((data.accepted_shares / data.total_shares) * 100).toFixed(1)
      : "0.0";

  return (
    <Card>
      <h3 className="text-sm font-semibold text-text-secondary">
        Stratum Pool
      </h3>
      <div className="mt-3 space-y-2">
        <div className="flex justify-between">
          <span className="text-xs text-text-secondary">Workers</span>
          <span className="font-[family-name:var(--font-code)] text-sm font-bold text-quantum-green">
            {data.connected_workers}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-xs text-text-secondary">Shares</span>
          <span className="font-[family-name:var(--font-code)] text-sm">
            {data.accepted_shares.toLocaleString()} / {data.total_shares.toLocaleString()}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-xs text-text-secondary">Accept Rate</span>
          <span className="font-[family-name:var(--font-code)] text-sm">
            {acceptRate}%
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-xs text-text-secondary">Blocks Found</span>
          <span className="font-[family-name:var(--font-code)] text-sm font-bold">
            {data.blocks_found}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-xs text-text-secondary">Uptime</span>
          <span className="font-[family-name:var(--font-code)] text-sm">
            {formatUptime(data.uptime_seconds)}
          </span>
        </div>
      </div>
    </Card>
  );
}
