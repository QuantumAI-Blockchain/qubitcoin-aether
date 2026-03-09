"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { investorApi } from "@/lib/investor-api";
import { useInvestorStore } from "@/stores/investor-store";
import { useWalletStore } from "@/stores/wallet-store";
import { InvestorNav } from "@/components/investor/investor-nav";
import { VestingChart } from "@/components/investor/vesting-chart";
import { VestingClaim } from "@/components/investor/vesting-claim";

export default function VestingPage() {
  const { status, setStatus, vesting, setVesting } = useInvestorStore();
  const { address: ethAddress, connected: isConnected } = useWalletStore();

  const { data: statusData } = useQuery({
    queryKey: ["investor-status", ethAddress],
    queryFn: () => investorApi.getStatus(ethAddress!),
    enabled: isConnected && !!ethAddress,
  });

  const { data: vestingData } = useQuery({
    queryKey: ["investor-vesting", status?.qbc_address],
    queryFn: () => investorApi.getVesting(status!.qbc_address!),
    enabled: !!status?.qbc_address,
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (statusData) setStatus(statusData);
  }, [statusData, setStatus]);
  useEffect(() => {
    if (vestingData) setVesting(vestingData);
  }, [vestingData, setVesting]);

  return (
    <main className="mx-auto max-w-3xl px-4 pt-24 pb-16">
      <InvestorNav />

      <h1 className="mb-6 font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-text-primary">
        Vesting Schedule
      </h1>

      {!isConnected ? (
        <div className="rounded-xl border border-border-subtle bg-bg-panel p-8 text-center text-text-secondary">
          Connect your wallet to view your vesting schedule.
        </div>
      ) : !status?.has_invested ? (
        <div className="rounded-xl border border-border-subtle bg-bg-panel p-8 text-center text-text-secondary">
          No investments found.
        </div>
      ) : (
        <div className="space-y-6">
          <VestingChart vesting={vesting} />
          <VestingClaim vesting={vesting} />

          {/* Schedule details */}
          <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
            <h3 className="mb-4 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-text-secondary">
              Schedule Details
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">Cliff Period</span>
                <span className="text-text-primary">6 months (180 days)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Linear Vesting</span>
                <span className="text-text-primary">24 months (720 days)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Monthly Unlock (post-cliff)</span>
                <span className="text-text-primary">~4.17% per month</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Full Vest</span>
                <span className="text-text-primary">30 months after TGE</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Claim Method</span>
                <span className="text-text-primary">Merkle proof + on-chain claim</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
