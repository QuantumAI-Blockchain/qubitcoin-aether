"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { investorApi } from "@/lib/investor-api";
import { useInvestorStore } from "@/stores/investor-store";
import { useWalletStore } from "@/stores/wallet-store";
import { InvestorNav } from "@/components/investor/investor-nav";
import { VestingChart } from "@/components/investor/vesting-chart";
import { RevenueTable } from "@/components/investor/revenue-table";
import { InvestmentHistory } from "@/components/investor/investment-history";

export default function InvestorDashboard() {
  const { status, setStatus, vesting, setVesting, revenue, setRevenue } =
    useInvestorStore();
  const { address: ethAddress, connected: isConnected } = useWalletStore();

  // Fetch investor status
  const { data: statusData } = useQuery({
    queryKey: ["investor-status", ethAddress],
    queryFn: () => investorApi.getStatus(ethAddress!),
    enabled: isConnected && !!ethAddress,
    refetchInterval: 15000,
  });

  // Fetch vesting info
  const { data: vestingData } = useQuery({
    queryKey: ["investor-vesting", status?.qbc_address],
    queryFn: () => investorApi.getVesting(status!.qbc_address!),
    enabled: !!status?.qbc_address,
    refetchInterval: 30000,
  });

  // Fetch revenue info
  const { data: revenueData } = useQuery({
    queryKey: ["investor-revenue", status?.qbc_address],
    queryFn: () => investorApi.getRevenue(status!.qbc_address!),
    enabled: !!status?.qbc_address,
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (statusData) setStatus(statusData);
  }, [statusData, setStatus]);
  useEffect(() => {
    if (vestingData) setVesting(vestingData);
  }, [vestingData, setVesting]);
  useEffect(() => {
    if (revenueData) setRevenue(revenueData);
  }, [revenueData, setRevenue]);

  return (
    <main className="mx-auto max-w-3xl px-4 pt-24 pb-16">
      <InvestorNav />

      <h1 className="mb-6 font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-text-primary">
        Your Investment
      </h1>

      {!isConnected ? (
        <div className="rounded-xl border border-border-subtle bg-bg-panel p-8 text-center text-text-secondary">
          Connect your wallet to view your investment dashboard.
        </div>
      ) : !status?.has_invested ? (
        <div className="rounded-xl border border-border-subtle bg-bg-panel p-8 text-center text-text-secondary">
          No investments found for this address. Go to the{" "}
          <a href="/invest" className="text-glow-cyan hover:underline">
            Invest page
          </a>{" "}
          to get started.
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary card */}
          <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div>
                <div className="text-xs text-text-secondary">Total Invested</div>
                <div className="font-mono text-lg font-bold text-text-primary">
                  ${parseFloat(status.invested_usd).toLocaleString()}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-secondary">QBC Allocated</div>
                <div className="font-mono text-lg font-bold text-glow-gold">
                  {parseFloat(status.qbc_allocated).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-secondary">QUSD Bonus</div>
                <div className="font-mono text-lg font-bold text-glow-cyan">
                  {parseFloat(status.qbc_allocated).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-secondary">QBC Address</div>
                <div className="font-mono text-sm text-glow-cyan">
                  {status.qbc_address?.slice(0, 8)}...{status.qbc_address?.slice(-6)}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-secondary">Investments</div>
                <div className="font-mono text-lg font-bold text-text-primary">
                  {status.investment_count}
                </div>
              </div>
            </div>
          </div>

          {/* Vesting */}
          <VestingChart vesting={vesting} />

          {/* Revenue */}
          <RevenueTable revenue={revenue} />

          {/* History */}
          <InvestmentHistory />
        </div>
      )}
    </main>
  );
}
