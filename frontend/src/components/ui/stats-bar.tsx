"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";

export function StatsBar() {
  const t = useTranslations("stats");
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
  const { data: engineInfo } = useQuery({
    queryKey: ["aetherEngineInfo"],
    queryFn: api.getAetherEngineInfo,
    refetchInterval: 15_000,
    retry: false,
  });

  const gatesPassed = phi?.gates_passed ?? (engineInfo?.gates_passed?.length ?? 0);
  const gatesTotal = phi?.gates_total ?? 10;

  const items = [
    { label: t("blockHeight"), value: chain?.height?.toLocaleString() ?? "---" },
    { label: t("phi"), value: phi?.phi?.toFixed(4) ?? "---" },
    {
      label: t("knowledgeNodes"),
      value: phi?.knowledge_nodes?.toLocaleString() ?? "---",
    },
    {
      label: t("graphEdges"),
      value: engineInfo?.edge_count ? engineInfo.edge_count.toLocaleString() : (phi?.knowledge_edges?.toLocaleString() ?? "---"),
    },
    { label: t("gates"), value: `${gatesPassed}/${gatesTotal}` },
  ];

  return (
    <div className="mx-auto grid max-w-5xl grid-cols-2 gap-4 sm:grid-cols-5">
      {items.map(({ label, value }) => (
        <div
          key={label}
          className="panel-inset px-4 py-3 text-center"
        >
          <p className="font-[family-name:var(--font-display)] text-[9px] uppercase tracking-widest text-text-secondary">{label}</p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-lg font-semibold glow-cyan">
            {value}
          </p>
        </div>
      ))}
    </div>
  );
}
