"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PHI_THRESHOLD } from "@/lib/constants";

export function PhiIndicator() {
  const { data } = useQuery({
    queryKey: ["phi"],
    queryFn: api.getPhi,
    refetchInterval: 10_000,
  });

  const phi = data?.phi ?? 0;
  const pct = Math.min((phi / PHI_THRESHOLD) * 100, 100);

  return (
    <div className="flex items-center gap-2 rounded-full bg-bg-panel px-3 py-1.5 text-xs">
      <span
        className={`h-2 w-2 rounded-full consciousness-pulse ${
          phi >= PHI_THRESHOLD ? "bg-glow-cyan" : "bg-quantum-violet"
        }`}
      />
      <span className="font-[family-name:var(--font-code)] text-text-secondary">
        &Phi; {phi.toFixed(2)}
      </span>
      <div className="h-1 w-12 overflow-hidden rounded-full bg-border-subtle">
        <div
          className="h-full rounded-full bg-quantum-violet transition-all duration-1000"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
