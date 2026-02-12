"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function StatsBar() {
  const { data: chain } = useQuery({
    queryKey: ["chainInfo"],
    queryFn: api.getChainInfo,
    refetchInterval: 6_600,
  });
  const { data: phi } = useQuery({
    queryKey: ["phi"],
    queryFn: api.getPhi,
    refetchInterval: 10_000,
  });

  const items = [
    { label: "Block Height", value: chain?.height?.toLocaleString() ?? "---" },
    { label: "Phi (\u03A6)", value: phi?.phi?.toFixed(4) ?? "---" },
    {
      label: "Knowledge Nodes",
      value: phi?.knowledge_nodes?.toLocaleString() ?? "---",
    },
    { label: "Difficulty", value: chain?.difficulty?.toFixed(4) ?? "---" },
    { label: "Peers", value: chain?.peers?.toString() ?? "---" },
  ];

  return (
    <div className="mx-auto grid max-w-5xl grid-cols-2 gap-4 sm:grid-cols-5">
      {items.map(({ label, value }) => (
        <div
          key={label}
          className="rounded-lg border border-surface-light bg-surface/60 px-4 py-3 text-center backdrop-blur-sm"
        >
          <p className="text-xs text-text-secondary">{label}</p>
          <p className="mt-1 font-[family-name:var(--font-mono)] text-lg font-semibold text-quantum-green">
            {value}
          </p>
        </div>
      ))}
    </div>
  );
}
