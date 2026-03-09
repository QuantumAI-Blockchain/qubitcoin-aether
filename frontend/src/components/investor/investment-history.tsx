"use client";

import { useQuery } from "@tanstack/react-query";
import { investorApi, type InvestmentRecord } from "@/lib/investor-api";

function formatUSD(val: string): string {
  const n = parseFloat(val);
  if (isNaN(n)) return "$0";
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function Row({ inv }: { inv: InvestmentRecord }) {
  return (
    <tr className="border-b border-white/5 last:border-0">
      <td className="py-2 text-sm text-text-secondary">
        {new Date(inv.created_at).toLocaleDateString()}
      </td>
      <td className="py-2 text-sm font-medium text-text-primary">
        {inv.token_symbol}
      </td>
      <td className="py-2 font-mono text-sm text-text-primary">
        {formatUSD(inv.usd_value)}
      </td>
      <td className="py-2 font-mono text-sm text-glow-gold">
        {parseFloat(inv.qbc_allocated).toLocaleString(undefined, { maximumFractionDigits: 0 })}
      </td>
      <td className="py-2 text-sm">
        <a
          href={`https://etherscan.io/tx/${inv.eth_tx_hash}`}
          target="_blank"
          rel="noopener noreferrer"
          className="font-mono text-glow-cyan hover:underline"
        >
          {inv.eth_tx_hash.slice(0, 8)}...
        </a>
      </td>
    </tr>
  );
}

export function InvestmentHistory() {
  const { data, isLoading } = useQuery({
    queryKey: ["investor-investments"],
    queryFn: () => investorApi.getInvestments(1, 50),
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border-subtle bg-bg-panel p-6 text-center text-text-secondary">
        Loading investments...
      </div>
    );
  }

  const investments = data?.investments ?? [];

  if (investments.length === 0) {
    return (
      <div className="rounded-xl border border-border-subtle bg-bg-panel p-6 text-center text-text-secondary">
        No investments yet
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
      <h3 className="mb-4 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-text-secondary">
        Investment History
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase text-text-secondary">
              <th className="pb-2">Date</th>
              <th className="pb-2">Token</th>
              <th className="pb-2">USD</th>
              <th className="pb-2">QBC</th>
              <th className="pb-2">Tx</th>
            </tr>
          </thead>
          <tbody>
            {investments.map((inv) => (
              <Row key={inv.id} inv={inv} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
