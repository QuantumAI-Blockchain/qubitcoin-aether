"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { investorApi } from "@/lib/investor-api";
import { useInvestorStore } from "@/stores/investor-store";
import { useWalletStore } from "@/stores/wallet-store";
import { InvestorNav } from "@/components/investor/investor-nav";
import { RoundStats } from "@/components/investor/round-stats";
import { TreasuryLive } from "@/components/investor/treasury-live";
import { QBCAddressBinder } from "@/components/investor/qbc-address-binder";
import { InvestmentForm } from "@/components/investor/investment-form";

export default function InvestPage() {
  const { round, setRound, status, setStatus } = useInvestorStore();
  const { address: ethAddress, connected: isConnected } = useWalletStore();

  // Fetch round info
  const { data: roundData } = useQuery({
    queryKey: ["investor-round"],
    queryFn: () => investorApi.getRoundInfo(),
    refetchInterval: 15000,
  });

  // Fetch investor status when connected
  const { data: statusData } = useQuery({
    queryKey: ["investor-status", ethAddress],
    queryFn: () => investorApi.getStatus(ethAddress!),
    enabled: isConnected && !!ethAddress,
    refetchInterval: 15000,
  });

  useEffect(() => {
    if (roundData) setRound(roundData);
  }, [roundData, setRound]);

  useEffect(() => {
    if (statusData) setStatus(statusData);
  }, [statusData, setStatus]);

  return (
    <main className="mx-auto max-w-3xl px-4 pt-24 pb-16">
      <InvestorNav />

      <div className="mb-8 text-center">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight glow-gold">
          QUANTUM SEED ROUND
        </h1>
        <p className="mt-2 text-sm text-text-secondary">
          $10M cap. 1 QBC = $1. Every dollar invested = 1 QBC + 1 QUSD + lifetime revenue share.
        </p>
        <p className="mt-1 text-xs text-text-secondary">
          Open to everyone. No KYC. No whitelist. Connect &rarr; Bind QBC address &rarr; Invest.
        </p>
      </div>

      <div className="space-y-6">
        {/* Round stats */}
        <RoundStats round={round} />

        {/* Treasury — live on-chain transparency */}
        <TreasuryLive />

        {/* Connect wallet prompt */}
        {!isConnected && (
          <div className="rounded-xl border border-border-subtle bg-bg-panel p-6 text-center">
            <h3 className="mb-2 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-text-secondary">
              Step 1: Connect Wallet
            </h3>
            <p className="text-sm text-text-secondary">
              Connect your MetaMask wallet on Ethereum mainnet to start investing.
            </p>
          </div>
        )}

        {/* QBC address binding */}
        {isConnected && <QBCAddressBinder />}

        {/* Investment form */}
        {isConnected && (
          <InvestmentForm
            ethPrice={3500}
            contractAddress={round?.contract_address || ""}
          />
        )}

        {/* Already invested indicator */}
        {status?.has_invested && (
          <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-4 text-center">
            <p className="text-sm text-green-400">
              You have invested{" "}
              <span className="font-mono font-bold">
                ${parseFloat(status.invested_usd).toLocaleString()}
              </span>{" "}
              &rarr;{" "}
              <span className="font-mono font-bold text-glow-gold">
                {parseFloat(status.qbc_allocated).toLocaleString(undefined, { maximumFractionDigits: 0 })} QBC
              </span>{" "}
              +{" "}
              <span className="font-mono font-bold text-glow-cyan">
                {parseFloat(status.qbc_allocated).toLocaleString(undefined, { maximumFractionDigits: 0 })} QUSD
              </span>{" "}
              + lifetime revenue share
            </p>
          </div>
        )}

        {/* Security footer */}
        {/* What you get */}
        <div className="rounded-xl border border-glow-cyan/20 bg-glow-cyan/5 p-6">
          <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-glow-cyan">
            What You Get
          </h3>
          <div className="space-y-2 text-sm text-text-secondary">
            <div className="flex items-start gap-2">
              <span className="text-glow-gold">1.</span>
              <span><strong className="text-text-primary">QBC Tokens</strong> — 1:1 with your investment ($10 = 10 QBC)</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-glow-gold">2.</span>
              <span><strong className="text-text-primary">QUSD Stablecoin</strong> — 1:1 bonus ($10 = 10 QUSD)</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-glow-gold">3.</span>
              <span><strong className="text-text-primary">Lifetime Revenue Share</strong> — 10% of all protocol fees (Exchange + Aether Mind), proportional to your investment, recurring forever</span>
            </div>
          </div>
        </div>

        {/* Chainlink Oracle */}
        <div className="rounded-xl border border-border-subtle bg-bg-panel p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-secondary">ETH/USD Price Oracle</span>
              <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-[10px] font-medium text-blue-400">Chainlink</span>
            </div>
            <a
              href="https://data.chain.link/feeds/ethereum/mainnet/eth-usd"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-glow-cyan hover:underline"
            >
              View Live Feed &rarr;
            </a>
          </div>
          <p className="mt-1 text-[10px] text-text-secondary font-mono">
            Contract: 0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419
          </p>
        </div>

        {/* Security footer */}
        <div className="rounded-lg border border-border-subtle bg-bg-panel/50 p-4 text-xs text-text-secondary">
          <ul className="space-y-1">
            <li>Funds go directly to treasury — contract never holds funds.</li>
            <li>QBC address binding is one-time and irreversible.</li>
            <li>Chainlink ETH/USD oracle with 1-hour staleness check.</li>
            <li>$100 minimum per investment. $10M hard cap.</li>
            <li>Commit-reveal for investments over $50K (anti-front-running).</li>
          </ul>
        </div>
      </div>
    </main>
  );
}
